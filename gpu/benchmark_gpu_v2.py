#!/usr/bin/env python3
"""
benchmark_gpu_v2.py — SHA-256 High-Utilization GPU Benchmark
=============================================================
Benchmarks sha256_gpu_v2 (the optimized kernel with sliding window,
constant memory, unrolled rounds, pinned memory, and triple CUDA streams).

Evaluates 4 chunk sizes and compares results with v1 for the paper.
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class GPURun:
    chunk_kb: int
    run_idx: int
    time_kernel_s: float
    time_e2e_s: float
    tput_kernel_mbs: float
    tput_e2e_mbs: float
    avg_power_w: float
    energy_e2e_j: float
    jpergb_e2e: float
    hash_hex: str


@dataclass
class GPUConfig:
    chunk_kb: int
    file_bytes: int
    runs: List[GPURun] = field(default_factory=list)

    def file_gb(self): return self.file_bytes / 1e9
    def avg_tput_kernel(self): return sum(r.tput_kernel_mbs for r in self.runs)/len(self.runs)
    def avg_tput_e2e(self): return sum(r.tput_e2e_mbs for r in self.runs)/len(self.runs)
    def avg_power(self): return sum(r.avg_power_w for r in self.runs)/len(self.runs)
    def avg_energy(self): return sum(r.energy_e2e_j for r in self.runs)/len(self.runs)
    def avg_jpergb(self): return sum(r.jpergb_e2e for r in self.runs)/len(self.runs)


def monitor_power_start():
    return subprocess.Popen(
        ["nvidia-smi","--query-gpu=power.draw","--format=csv,noheader,nounits","-i","0","-lms","100"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def monitor_power_stop(proc):
    proc.terminate()
    try: stdout, _ = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired: proc.kill(); stdout, _ = proc.communicate()
    readings = []
    for line in stdout.strip().splitlines():
        try: readings.append(float(line.strip()))
        except ValueError: pass
    return readings


def run_config(binary, chunk_kb, filepath, runs):
    file_bytes = os.path.getsize(filepath)
    chunk_bytes = chunk_kb * 1024
    cfg = GPUConfig(chunk_kb=chunk_kb, file_bytes=file_bytes)

    print(f"\n  {'─'*68}")
    print(f"  [GPU v2] Chunk Size = {chunk_kb} KB ({chunk_bytes} bytes)")
    print(f"  {'─'*68}")

    for run_idx in range(1, runs + 1):
        pmon = monitor_power_start()
        time.sleep(0.1)

        proc = subprocess.run(
            [binary, filepath, str(chunk_bytes), "1"],
            capture_output=True, text=True)

        power_r = monitor_power_stop(pmon)

        if proc.returncode != 0:
            print(f"  ERROR:\n{proc.stderr}", file=sys.stderr)
            sys.exit(1)

        line = next((l for l in proc.stdout.splitlines() if l.startswith("RUN ")), None)
        if not line:
            print(f"  No output\n{proc.stdout}", file=sys.stderr)
            sys.exit(1)

        parts = line.split()
        tk = float(parts[parts.index("TIME_KERNEL_S")+1])
        te = float(parts[parts.index("TIME_TOTAL_S")+1])
        tpk = float(parts[parts.index("THROUGHPUT_KERNEL_MBS")+1])
        tpe = float(parts[parts.index("THROUGHPUT_TOTAL_MBS")+1])
        hexh = parts[parts.index("CHUNK_0_HASH")+1]

        avg_p = sum(power_r)/len(power_r) if power_r else 12.0
        energy = avg_p * te
        jpergb = energy / (file_bytes / 1e9)

        run = GPURun(chunk_kb=chunk_kb, run_idx=run_idx,
                     time_kernel_s=tk, time_e2e_s=te,
                     tput_kernel_mbs=tpk, tput_e2e_mbs=tpe,
                     avg_power_w=avg_p, energy_e2e_j=energy, jpergb_e2e=jpergb,
                     hash_hex=hexh)
        cfg.runs.append(run)

        print(f"  Run {run_idx:2d}: Kernel {tpk/1024:.2f} GB/s "
              f"| E2E {tpe/1024:.2f} GB/s "
              f"| Power {avg_p:.1f} W "
              f"| Energy {energy:.2f} J ({jpergb:.2f} J/GB)")

    return cfg


def print_comparison_table(v2_results, v1_results=None):
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════════════════════╗")
    print("║               SHA-256 GPU v2 BENCHMARK — HIGH-UTILIZATION ANALYSIS                       ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  {'Chunk':<10} {'Kernel Tput':>14} {'E2E Tput':>12} {'Avg Pwr':>10} {'J/GB E2E':>12}  ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════╣")
    for r in v2_results:
        print(f"║  {str(r.chunk_kb)+' KB':<10} "
              f"{r.avg_tput_kernel()/1024:.2f} GB/s{'':<6} "
              f"{r.avg_tput_e2e()/1024:.2f} GB/s{'':<4} "
              f"{r.avg_power():.1f} W{'':<3} "
              f"{r.avg_jpergb():.2f} J/GB{'':<3}  ║")
    print("╚══════════════════════════════════════════════════════════════════════════════════════════╝")

    # Show uplift vs v1
    v1_best_kernel = 7587.84   # MB/s from v1 results (256KB)
    v1_best_e2e    = 2662.40
    best = max(v2_results, key=lambda r: r.avg_tput_kernel())
    print(f"\n  vs. GPU v1 best (256KB, kernel): {v1_best_kernel:.1f} MB/s → v2: {best.avg_tput_kernel():.1f} MB/s  "
          f"(+{(best.avg_tput_kernel()/v1_best_kernel -1)*100:.1f}% uplift)")
    print(f"  vs. GPU v1 best (256KB, E2E):    {v1_best_e2e:.1f} MB/s → v2: {best.avg_tput_e2e():.1f} MB/s  "
          f"(+{(best.avg_tput_e2e()/v1_best_e2e -1)*100:.1f}% uplift)\n")


def write_csv(results, raw_path, summary_path):
    with open(raw_path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["chunk_kb","run","time_kernel_s","time_e2e_s",
                     "tput_kernel_gbs","tput_e2e_gbs","avg_power_w","energy_j","jpergb","hash"])
        for cfg in results:
            for r in cfg.runs:
                wr.writerow([r.chunk_kb, r.run_idx,
                              f"{r.time_kernel_s:.6f}", f"{r.time_e2e_s:.6f}",
                              f"{r.tput_kernel_mbs/1024:.4f}", f"{r.tput_e2e_mbs/1024:.4f}",
                              f"{r.avg_power_w:.2f}", f"{r.energy_e2e_j:.4f}",
                              f"{r.jpergb_e2e:.4f}", r.hash_hex])
    print(f"  [✓] Raw data → {raw_path}")

    with open(summary_path, "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["chunk_kb","avg_tput_kernel_gbs","avg_tput_e2e_gbs",
                     "avg_power_w","avg_energy_j","avg_jpergb"])
        for r in results:
            wr.writerow([r.chunk_kb,
                         f"{r.avg_tput_kernel()/1024:.4f}", f"{r.avg_tput_e2e()/1024:.4f}",
                         f"{r.avg_power():.2f}", f"{r.avg_energy():.4f}",
                         f"{r.avg_jpergb():.4f}"])
    print(f"  [✓] Summary  → {summary_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",    default="../dummy_1GB.bin")
    parser.add_argument("--runs",    type=int, default=5)
    parser.add_argument("--gpu-bin", default="./sha256_gpu_v2")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"ERROR: {args.file} not found", file=sys.stderr); sys.exit(1)
    if not Path(args.gpu_bin).exists():
        print(f"ERROR: {args.gpu_bin} not found (compile with make v2)", file=sys.stderr); sys.exit(1)

    print("\n" + "═"*70)
    print("   SHA-256 GPU v2 — High-Utilization Benchmark (RTX 2050, sm_86)")
    print("   Optimizations: w[16] sliding window | __constant__ K | #pragma unroll")
    print("   Pinned memory | Triple CUDA Streams | Grid-stride kernel")
    print("═"*70)

    chunk_sizes = [4, 16, 64, 256]
    results = [run_config(args.gpu_bin, cs, args.file, args.runs) for cs in chunk_sizes]

    print_comparison_table(results)

    out_dir = Path(__file__).parent / "results"
    out_dir.mkdir(exist_ok=True)
    write_csv(results, str(out_dir/"gpu_v2_results_raw.csv"),
              str(out_dir/"gpu_v2_results_summary.csv"))


if __name__ == "__main__":
    main()
