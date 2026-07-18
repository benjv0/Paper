#!/usr/bin/env python3
"""
benchmark_gpu.py — SHA-256 GPU Benchmark Orchestrator
======================================================
Executes the CUDA SHA-256 binary across different chunk sizes
(4KB, 16KB, 64KB, 256KB) and monitors discrete GPU power consumption
in real-time using nvidia-smi.

Computes:
  - Throughput (Kernel only & End-to-End Total) in MB/s and GB/s
  - Average GPU Power Draw (Watts)
  - GPU Energy Consumption (Joules)
  - GPU Energy Efficiency (J/GB)

Outputs:
  - Terminal summary table
  - gpu_results_raw.csv      — per-run data
  - gpu_results_summary.csv  — consolidated stats
"""

import argparse
import csv
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict

@dataclass
class GPURunResult:
    chunk_size_kb: int
    run_idx: int
    time_kernel_s: float
    time_total_s: float
    tput_kernel_mbs: float
    tput_total_mbs: float
    avg_power_w: float
    energy_kernel_j: float
    energy_total_j: float
    jpergb_kernel: float
    jpergb_total: float
    hash_hex: str

@dataclass
class GPUConfigResult:
    chunk_size_kb: int
    file_bytes: int
    runs: List[GPURunResult] = field(default_factory=list)

    def file_gb(self) -> float:
        return self.file_bytes / 1e9

    def avg_time_kernel(self) -> float:
        return sum(r.time_kernel_s for r in self.runs) / len(self.runs)

    def avg_time_total(self) -> float:
        return sum(r.time_total_s for r in self.runs) / len(self.runs)

    def avg_tput_kernel(self) -> float:
        return sum(r.tput_kernel_mbs for r in self.runs) / len(self.runs)

    def avg_tput_total(self) -> float:
        return sum(r.tput_total_mbs for r in self.runs) / len(self.runs)

    def avg_power(self) -> float:
        return sum(r.avg_power_w for r in self.runs) / len(self.runs)

    def avg_energy_total(self) -> float:
        return sum(r.energy_total_j for r in self.runs) / len(self.runs)

    def avg_jpergb_total(self) -> float:
        return sum(r.jpergb_total for r in self.runs) / len(self.runs)


def monitor_power_start() -> subprocess.Popen:
    """Start nvidia-smi power monitoring in the background at 100ms intervals."""
    cmd = [
        "nvidia-smi",
        "--query-gpu=power.draw",
        "--format=csv,noheader,nounits",
        "-i", "0",
        "-lms", "100"
    ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def monitor_power_stop(proc: subprocess.Popen) -> List[float]:
    """Stop the nvidia-smi monitoring process and return the power readings in Watts."""
    proc.terminate()
    try:
        stdout, _ = proc.communicate(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()

    readings = []
    for line in stdout.strip().splitlines():
        try:
            val = float(line.strip())
            readings.append(val)
        except ValueError:
            pass
    return readings


def run_gpu_config(binary: str, chunk_size_kb: int, filepath: str, runs: int) -> GPUConfigResult:
    file_bytes = os.path.getsize(filepath)
    chunk_size_bytes = chunk_size_kb * 1024
    result = GPUConfigResult(chunk_size_kb=chunk_size_kb, file_bytes=file_bytes)

    print(f"\n  {'─'*65}")
    print(f"  [GPU] Hashing with Chunk Size = {chunk_size_kb} KB  ({chunk_size_bytes} bytes)")
    print(f"  {'─'*65}")

    for run_idx in range(1, runs + 1):
        # 1. Start power monitoring
        power_proc = monitor_power_start()
        time.sleep(0.1)  # allow monitor to warm up

        # 2. Run the CUDA binary
        # We pass runs=1 each time to isolate the power measurement window
        cmd = [binary, filepath, str(chunk_size_bytes), "1"]
        proc = subprocess.run(cmd, capture_output=True, text=True)

        # 3. Stop power monitoring
        power_readings = monitor_power_stop(power_proc)

        if proc.returncode != 0:
            print(f"  ERROR running GPU binary:\n{proc.stderr}", file=sys.stderr)
            sys.exit(1)

        # Parse output line:
        # RUN 1 TIME_KERNEL_S x.xx TIME_TOTAL_S x.xx THROUGHPUT_KERNEL_MBS x.xx THROUGHPUT_TOTAL_MBS x.xx CHUNK_0_HASH xxx
        out_line = next((l for l in proc.stdout.splitlines() if l.startswith("RUN ")), None)
        if not out_line:
            print(f"  ERROR: no output\n{proc.stdout}", file=sys.stderr)
            sys.exit(1)

        parts = out_line.split()
        time_kernel_s   = float(parts[parts.index("TIME_KERNEL_S") + 1])
        time_total_s    = float(parts[parts.index("TIME_TOTAL_S") + 1])
        tput_kernel_mbs = float(parts[parts.index("THROUGHPUT_KERNEL_MBS") + 1])
        tput_total_mbs  = float(parts[parts.index("THROUGHPUT_TOTAL_MBS") + 1])
        hash_hex        = parts[parts.index("CHUNK_0_HASH") + 1]

        # Calculate average power draw (exclude empty list case)
        avg_power = sum(power_readings) / len(power_readings) if power_readings else 15.0 # fallback

        # Energy in Joules = Power (W) * Time (s)
        energy_kernel = avg_power * time_kernel_s
        energy_total  = avg_power * time_total_s

        file_gb = file_bytes / 1e9
        jpergb_kernel = energy_kernel / file_gb
        jpergb_total  = energy_total / file_gb

        run = GPURunResult(
            chunk_size_kb=chunk_size_kb, run_idx=run_idx,
            time_kernel_s=time_kernel_s, time_total_s=time_total_s,
            tput_kernel_mbs=tput_kernel_mbs, tput_total_mbs=tput_total_mbs,
            avg_power_w=avg_power,
            energy_kernel_j=energy_kernel, energy_total_j=energy_total,
            jpergb_kernel=jpergb_kernel, jpergb_total=jpergb_total,
            hash_hex=hash_hex
        )
        result.runs.append(run)

        print(f"  Run {run_idx:2d}: Kernel: {time_kernel_s:.4f}s ({tput_kernel_mbs/1024:.2f} GB/s) | "
              f"Total E2E: {time_total_s:.4f}s ({tput_total_mbs/1024:.2f} GB/s) | "
              f"Power: {avg_power:.1f} W | Energy: {energy_total:.2f} J ({jpergb_total:.2f} J/GB)")

    return result


def print_gpu_summary_table(results: List[GPUConfigResult]):
    print("\n")
    print("╔══════════════════════════════════════════════════════════════════════════════════════════╗")
    print("║                     SHA-256 GPU BENCHMARK — SCALING ANALYSIS                             ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════╣")
    print(f"║  {'Chunk Size':<12} {'Kernel Tput':>15} {'E2E Tput':>13} {'Avg Power':>12} {'Energy E2E':>13} {'J/GB E2E':>13}  ║")
    print("╠══════════════════════════════════════════════════════════════════════════════════════════╣")

    for r in results:
        chunk_str = f"{r.chunk_size_kb} KB"
        k_tput = f"{r.avg_tput_kernel() / 1024:.2f} GB/s"
        t_tput = f"{r.avg_tput_total() / 1024:.2f} GB/s"
        power_str = f"{r.avg_power():.1f} W"
        energy_str = f"{r.avg_energy_total():.2f} J"
        jpergb_str = f"{r.avg_jpergb_total():.2f} J/GB"

        print(f"║  {chunk_str:<12} {k_tput:>15} {t_tput:>13} {power_str:>12} {energy_str:>13} {jpergb_str:>13}  ║")

    print("╚══════════════════════════════════════════════════════════════════════════════════════════╝")
    print()


def write_gpu_csv(results: List[GPUConfigResult], raw_path: str, summary_path: str):
    # Raw per-run CSV
    with open(raw_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chunk_size_kb", "run", "time_kernel_s", "time_total_s",
                         "tput_kernel_gbs", "tput_total_gbs", "avg_power_w",
                         "energy_total_j", "jpergb_total", "chunk_0_hash"])
        for r in results:
            for run in r.runs:
                writer.writerow([
                    run.chunk_size_kb, run.run_idx,
                    f"{run.time_kernel_s:.6f}", f"{run.time_total_s:.6f}",
                    f"{run.tput_kernel_mbs/1024:.4f}", f"{run.tput_total_mbs/1024:.4f}",
                    f"{run.avg_power_w:.2f}", f"{run.energy_total_j:.4f}",
                    f"{run.jpergb_total:.4f}", run.hash_hex
                ])
    print(f"  [✓] GPU raw per-run data  → {raw_path}")

    # Summary CSV
    with open(summary_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["chunk_size_kb", "avg_time_kernel_s", "avg_time_total_s",
                         "avg_tput_kernel_gbs", "avg_tput_total_gbs",
                         "avg_power_w", "avg_energy_total_j", "avg_jpergb_total"])
        for r in results:
            writer.writerow([
                r.chunk_size_kb,
                f"{r.avg_time_kernel():.6f}", f"{r.avg_time_total():.6f}",
                f"{r.avg_tput_kernel()/1024:.4f}", f"{r.avg_tput_total()/1024:.4f}",
                f"{r.avg_power():.2f}", f"{r.avg_energy_total():.4f}",
                f"{r.avg_jpergb_total():.4f}"
            ])
    print(f"  [✓] GPU summary statistics → {summary_path}")


def main():
    parser = argparse.ArgumentParser(description="SHA-256 GPU Benchmark (CUDA)")
    parser.add_argument("--file", default="../dummy_1GB.bin")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--gpu-bin", default="./sha256_gpu")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"ERROR: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)
    if not Path(args.gpu_bin).exists():
        print(f"ERROR: GPU binary not found: {args.gpu_bin}  (compile with nvcc first)", file=sys.stderr)
        sys.exit(1)

    print("\n" + "═"*66)
    print("   SHA-256 GPU Benchmark (NVIDIA GeForce RTX 2050)")
    print("═"*66)
    print(f"   Runs per config   : {args.runs}")
    print(f"   Input file        : {args.file}")
    print(f"   VRAM Buffer size  : {os.path.getsize(args.file)/1e9:.3f} GB")
    print("═"*66)

    # Chunk sizes to evaluate (in KB)
    chunk_sizes = [4, 16, 64, 256]

    results = []
    for cs in chunk_sizes:
        res = run_gpu_config(args.gpu_bin, cs, args.file, args.runs)
        results.append(res)

    print_gpu_summary_table(results)

    script_dir = Path(__file__).parent
    write_gpu_csv(results, str(script_dir / "results/gpu_results_raw.csv"),
                  str(script_dir / "results/gpu_results_summary.csv"))


if __name__ == "__main__":
    main()
