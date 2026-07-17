#!/usr/bin/env python3
"""
benchmark.py — SHA-256 CPU Benchmark Orchestrator
==================================================
Executes SHA-256 implementations across thread counts (1, 2, 4) for both:
  - SW: pure C software implementation (no SHA-NI)
  - HW: OpenSSL + Intel SHA-NI hardware acceleration

All threads are pinned exclusively to Intel E-cores (CPUs 4-11, 3.5 GHz)
using taskset, so P-cores (4.7 GHz) are never used. This isolates the
E-core performance for a fair multi-core scaling analysis.

Measures per configuration:
  - Throughput (MB/s, GB/s)          — aggregate across all threads
  - Energy (Joules via Intel RAPL)   — package domain
  - Energy efficiency (J/GB)
  - Speedup vs SW 1-thread baseline
  - Scaling efficiency vs ideal linear scaling

Outputs:
  - Terminal summary tables
  - results_raw.csv      — per-run data for every configuration
  - results_summary.csv  — aggregated stats (ready for LaTeX)

Usage:
  sudo python3 benchmark.py [--file FILE] [--runs N] [--no-rapl]
"""

import argparse
import csv
import math
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict

# ─────────────────────────────────────────────
#  RAPL energy reader
# ─────────────────────────────────────────────

RAPL_PKG = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_MAX = "/sys/class/powercap/intel-rapl:0/max_energy_range_uj"

# E-cores on Intel i7-1255U (Alder Lake): CPUs 4–11, max 3500 MHz, no HT.
# The first N entries are used when running with N threads, ensuring each
# thread is pinned to one distinct E-core.
ECORE_CPUS = [4, 5, 6, 7, 8, 9, 10, 11]


def read_rapl_uj(path: str) -> Optional[int]:
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (PermissionError, FileNotFoundError):
        return None


def rapl_delta_joules(before: Optional[int], after: Optional[int],
                      max_uj: Optional[int]) -> Optional[float]:
    if before is None or after is None:
        return None
    if after >= before:
        return (after - before) / 1e6
    if max_uj:
        return (max_uj - before + after) / 1e6
    return None


# ─────────────────────────────────────────────
#  Data structures
# ─────────────────────────────────────────────

@dataclass
class RunResult:
    label: str           # e.g. "SW_1T", "HW_4T"
    impl: str            # "SW" or "HW"
    threads: int
    run_idx: int
    wall_s: float
    aggregate_mbs: float
    energy_j: Optional[float]
    joules_per_gb: Optional[float]


@dataclass
class ConfigResult:
    label: str
    impl: str
    threads: int
    file_bytes: int
    runs: List[RunResult] = field(default_factory=list)

    def file_gb(self) -> float:
        return self.file_bytes / 1e9

    def avg_wall(self) -> float:
        return sum(r.wall_s for r in self.runs) / len(self.runs)

    def stdev_wall(self) -> float:
        avg = self.avg_wall()
        return math.sqrt(sum((r.wall_s - avg)**2 for r in self.runs) / len(self.runs))

    def avg_throughput_mbs(self) -> float:
        return sum(r.aggregate_mbs for r in self.runs) / len(self.runs)

    def avg_throughput_gbs(self) -> float:
        return self.avg_throughput_mbs() / 1024.0

    def avg_energy_j(self) -> Optional[float]:
        valid = [r.energy_j for r in self.runs if r.energy_j is not None]
        return sum(valid) / len(valid) if valid else None

    def avg_jpergb(self) -> Optional[float]:
        valid = [r.joules_per_gb for r in self.runs if r.joules_per_gb is not None]
        return sum(valid) / len(valid) if valid else None


# ─────────────────────────────────────────────
#  Benchmark runner
# ─────────────────────────────────────────────

def run_config(binary: str, label: str, impl: str, threads: int,
               filepath: str, runs: int, use_rapl: bool) -> ConfigResult:

    file_bytes = os.path.getsize(filepath)
    result = ConfigResult(label=label, impl=impl, threads=threads,
                          file_bytes=file_bytes)
    rapl_max_uj = read_rapl_uj(RAPL_MAX)

    # Build taskset CPU list: use the first `threads` E-cores.
    # This pins the entire process (and all its pthreads) to exactly
    # N E-cores, so no P-core can be scheduled by the OS.
    ecores_for_run = ECORE_CPUS[:threads]
    taskset_cpus   = ",".join(str(c) for c in ecores_for_run)
    taskset_prefix = ["taskset", "-c", taskset_cpus]

    print(f"\n  {'─'*58}")
    print(f"  [{label}] — {binary}  threads={threads}")
    print(f"  E-cores pinned: CPUs {taskset_cpus}")
    print(f"  {'─'*58}")

    for run_idx in range(1, runs + 1):
        e_before = read_rapl_uj(RAPL_PKG) if use_rapl else None

        # Build the binary command (single run per invocation for accurate RAPL)
        if threads == 1 and impl == "SW":
            bin_cmd = ["./sha256_sw", filepath, "1"]
        elif threads == 1 and impl == "HW":
            bin_cmd = ["./sha256_hw", filepath, "1"]
        else:
            mt_bin  = f"./sha256_mt_{impl.lower()}"
            bin_cmd = [mt_bin, filepath, str(threads), "1"]

        # Prepend taskset to pin to E-cores only
        cmd = taskset_prefix + bin_cmd

        proc = subprocess.run(cmd, capture_output=True, text=True)
        e_after = read_rapl_uj(RAPL_PKG) if use_rapl else None

        if proc.returncode != 0:
            print(f"  ERROR: {proc.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse output:
        # Single-thread: "RUN N TIME_S x THROUGHPUT_MBS x HASH x"
        # Multi-thread:  "RUN N THREADS N WALL_S x AGGREGATE_MBS x"
        out_line = next((l for l in proc.stdout.splitlines() if l.startswith("RUN ")), None)
        if not out_line:
            print(f"  ERROR: no output\n{proc.stdout}", file=sys.stderr)
            sys.exit(1)

        parts = out_line.split()
        if "WALL_S" in parts:
            wall_s        = float(parts[parts.index("WALL_S") + 1])
            aggregate_mbs = float(parts[parts.index("AGGREGATE_MBS") + 1])
        else:
            wall_s        = float(parts[parts.index("TIME_S") + 1])
            aggregate_mbs = float(parts[parts.index("THROUGHPUT_MBS") + 1])

        energy_j = rapl_delta_joules(e_before, e_after, rapl_max_uj)
        jpergb   = energy_j / (file_bytes / 1e9) if energy_j is not None else None

        run = RunResult(
            label=label, impl=impl, threads=threads, run_idx=run_idx,
            wall_s=wall_s, aggregate_mbs=aggregate_mbs,
            energy_j=energy_j, joules_per_gb=jpergb
        )
        result.runs.append(run)

        e_str    = f"{energy_j:.2f} J"  if energy_j is not None else "   N/A  "
        jpgb_str = f"{jpergb:.2f} J/GB" if jpergb   is not None else "   N/A  "
        print(f"  Run {run_idx:2d}: {wall_s:.4f}s | {aggregate_mbs:8.2f} MB/s | "
              f"{e_str:10s} | {jpgb_str}")

    return result



# ─────────────────────────────────────────────
#  Scaling analysis
# ─────────────────────────────────────────────

def scaling_efficiency(throughput_nt: float, throughput_1t: float, n: int) -> float:
    """Actual speedup / ideal linear speedup, as percentage."""
    if n == 1 or throughput_1t == 0:
        return 100.0
    actual_speedup = throughput_nt / throughput_1t
    return (actual_speedup / n) * 100.0


# ─────────────────────────────────────────────
#  Output helpers
# ─────────────────────────────────────────────

def print_scaling_table(configs: Dict[str, ConfigResult]):
    sw_1t = configs.get("SW_1T")
    hw_1t = configs.get("HW_1T")

    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║              SHA-256 CPU BENCHMARK — SCALING ANALYSIS                   ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")
    print(f"║  {'Config':<12} {'Threads':>7} {'Throughput MB/s':>16} "
          f"{'Speedup vs SW_1T':>17} {'Scale Eff.':>11} {'J/GB':>8}  ║")
    print("╠══════════════════════════════════════════════════════════════════════════╣")

    order = ["SW_1T", "SW_2T", "SW_4T", "HW_1T", "HW_2T", "HW_4T"]
    for key in order:
        cfg = configs.get(key)
        if cfg is None:
            continue

        tput    = cfg.avg_throughput_mbs()
        speedup = tput / sw_1t.avg_throughput_mbs() if sw_1t else 0.0

        baseline_1t = sw_1t if cfg.impl == "SW" else hw_1t
        eff = scaling_efficiency(tput, baseline_1t.avg_throughput_mbs(), cfg.threads) \
              if baseline_1t else 0.0

        jpgb_str = f"{cfg.avg_jpergb():.2f}" if cfg.avg_jpergb() is not None else "  N/A"

        eff_str = f"{eff:.1f}%" if cfg.threads > 1 else "  —  "
        print(f"║  {key:<12} {cfg.threads:>7} {tput:>16.2f} {speedup:>17.2f}x "
              f"{eff_str:>11} {jpgb_str:>8}  ║")

        if key == "SW_4T":
            print("╠══════════════════════════════════════════════════════════════════════════╣")

    print("╚══════════════════════════════════════════════════════════════════════════╝")

    # Speedup summary
    if sw_1t and hw_1t:
        hw4 = configs.get("HW_4T")
        print(f"\n  Speedup HW_1T  vs SW_1T  : {hw_1t.avg_throughput_mbs()/sw_1t.avg_throughput_mbs():.2f}×")
        if hw4:
            print(f"  Speedup HW_4T  vs SW_1T  : {hw4.avg_throughput_mbs()/sw_1t.avg_throughput_mbs():.2f}×")
        print()


def write_raw_csv(configs: Dict[str, ConfigResult], path: str):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "impl", "threads", "run",
                         "wall_s", "aggregate_mbs", "aggregate_gbs",
                         "energy_j", "joules_per_gb"])
        for key in ["SW_1T","SW_2T","SW_4T","HW_1T","HW_2T","HW_4T"]:
            cfg = configs.get(key)
            if cfg is None:
                continue
            for r in cfg.runs:
                writer.writerow([
                    key, cfg.impl, cfg.threads, r.run_idx,
                    f"{r.wall_s:.6f}",
                    f"{r.aggregate_mbs:.3f}",
                    f"{r.aggregate_mbs/1024:.6f}",
                    f"{r.energy_j:.4f}"   if r.energy_j   is not None else "",
                    f"{r.joules_per_gb:.4f}" if r.joules_per_gb is not None else "",
                ])
    print(f"  [✓] Raw per-run data  → {path}")


def write_summary_csv(configs: Dict[str, ConfigResult], path: str):
    sw_1t = configs.get("SW_1T")

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["config", "impl", "threads", "num_runs",
                         "avg_wall_s", "stdev_wall_s",
                         "avg_throughput_mbs", "avg_throughput_gbs",
                         "avg_energy_j", "avg_joules_per_gb",
                         "speedup_vs_SW_1T", "scaling_efficiency_pct"])

        for key in ["SW_1T","SW_2T","SW_4T","HW_1T","HW_2T","HW_4T"]:
            cfg = configs.get(key)
            if cfg is None:
                continue

            tput    = cfg.avg_throughput_mbs()
            speedup = tput / sw_1t.avg_throughput_mbs() if sw_1t else 0.0

            baseline_1t = configs.get(f"{cfg.impl}_1T")
            eff = scaling_efficiency(tput, baseline_1t.avg_throughput_mbs(), cfg.threads) \
                  if baseline_1t else 0.0

            writer.writerow([
                key, cfg.impl, cfg.threads, len(cfg.runs),
                f"{cfg.avg_wall():.6f}",
                f"{cfg.stdev_wall():.6f}",
                f"{tput:.3f}",
                f"{cfg.avg_throughput_gbs():.6f}",
                f"{cfg.avg_energy_j():.4f}" if cfg.avg_energy_j() is not None else "N/A",
                f"{cfg.avg_jpergb():.4f}"   if cfg.avg_jpergb()   is not None else "N/A",
                f"{speedup:.4f}",
                f"{eff:.2f}" if cfg.threads > 1 else "100.00",
            ])

    print(f"  [✓] Summary statistics → {path}")


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SHA-256 CPU Benchmark: SW vs HW, 1/2/4 E-cores")
    parser.add_argument("--file",    default="../dummy_1GB.bin")
    parser.add_argument("--runs",    type=int, default=5)
    parser.add_argument("--no-rapl", action="store_true")
    parser.add_argument("--threads", nargs="+", type=int, default=[1, 2, 4],
                        help="Thread counts to test (default: 1 2 4, E-cores only)")
    parser.add_argument("--sw-bin",    default="./sha256_sw")
    parser.add_argument("--hw-bin",    default="./sha256_hw")
    parser.add_argument("--mt-sw-bin", default="./sha256_mt_sw")
    parser.add_argument("--mt-hw-bin", default="./sha256_mt_hw")
    args = parser.parse_args()

    # Validate files
    for f in [args.file, args.sw_bin, args.hw_bin, args.mt_sw_bin, args.mt_hw_bin]:
        if not Path(f).exists():
            print(f"ERROR: not found: {f}  (run 'make all' first)", file=sys.stderr)
            sys.exit(1)

    use_rapl = not args.no_rapl
    if use_rapl:
        if read_rapl_uj(RAPL_PKG) is None:
            print("WARNING: RAPL not readable — use sudo or pass --no-rapl", file=sys.stderr)
            use_rapl = False
        else:
            print(f"[✓] RAPL energy measurement enabled")

    print("\n" + "═"*62)
    print("   SHA-256 CPU Benchmark — Intel i7-1255U (E-cores only)")
    print("═"*62)
    print(f"   Runs per config         : {args.runs}")
    print(f"   Thread counts           : {args.threads}")
    max_t = max(args.threads)
    ecores_shown = ECORE_CPUS[:max_t]
    print(f"   CPU pinning             : E-cores only (CPUs {ecores_shown[0]}-{ecores_shown[-1]}, 3500 MHz)")
    print(f"   Input file              : {args.file}")
    print(f"   RAPL energy measurement : {'ENABLED' if use_rapl else 'DISABLED'}")
    print("═"*62)

    # Pre-warm disk cache
    print("\n  [*] Pre-warming disk cache...")
    subprocess.run(["dd", f"if={args.file}", "of=/dev/null", "bs=4M"],
                   capture_output=True)

    configs: Dict[str, ConfigResult] = {}

    for impl in ["SW", "HW"]:
        for t in args.threads:
            key = f"{impl}_{t}T"
            binary = (args.sw_bin if t == 1 and impl == "SW" else
                      args.hw_bin if t == 1 and impl == "HW" else
                      args.mt_sw_bin if impl == "SW" else args.mt_hw_bin)

            cfg = run_config(binary, key, impl, t, args.file, args.runs, use_rapl)
            configs[key] = cfg

    print_scaling_table(configs)

    script_dir = Path(__file__).parent
    write_raw_csv(configs, str(script_dir / "results_raw.csv"))
    write_summary_csv(configs, str(script_dir / "results_summary.csv"))

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
