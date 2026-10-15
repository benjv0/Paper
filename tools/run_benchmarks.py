#!/usr/bin/env python3
"""
run_benchmarks.py — Unified SHA-256 Benchmark Orchestrator
==========================================================
Executes the comprehensive benchmarking suite across CPU and GPU:
- Follows the rigorous protocol: 3s warmup + >=15s continuous execution loop x 5 runs.
- Measures RAPL PKG energy (idle, gross, net), PL1/PL2, core frequencies.
- Measures GPU kernel-only and E2E (pinned vs pageable), NVML power/energy if available.
- Computes throughput [GB/s], hashes/s, blocks/s, J/GB, and speedups vs SHA-NI 4T and Scalar 1T.
- Outputs results/benchmarks_raw.csv and results/benchmarks_summary.csv.
"""

import os
import sys
import time
import subprocess
import argparse
import math
import statistics
import csv
from typing import List, Dict, Optional, Tuple

RAPL_PKG = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
RAPL_MAX = "/sys/class/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj"

SWEEP_C = [64, 1024, 4096, 65536, 1048576]

def read_rapl_uj() -> Optional[int]:
    try:
        with open(RAPL_PKG, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def read_rapl_max_uj() -> Optional[int]:
    try:
        with open(RAPL_MAX, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def compute_rapl_delta_joules(e_before: Optional[int], e_after: Optional[int], max_uj: Optional[int]) -> Optional[float]:
    if e_before is None or e_after is None:
        return None
    if e_after >= e_before:
        d_uj = e_after - e_before
    else:
        if max_uj is not None:
            d_uj = (max_uj - e_before) + e_after
        else:
            d_uj = e_after
    return d_uj / 1e6

def read_cpu_freqs(cores: List[int]) -> float:
    freqs = []
    for c in cores:
        path = f"/sys/devices/system/cpu/cpu{c}/cpufreq/scaling_cur_freq"
        try:
            with open(path, "r") as f:
                freqs.append(float(f.read().strip()) / 1000.0) # MHz
        except Exception:
            pass
    return statistics.mean(freqs) if freqs else 0.0

def measure_cpu_idle_power(duration: float = 10.0) -> Tuple[Optional[float], Optional[float]]:
    e0 = read_rapl_uj()
    if e0 is None:
        return None, None
    max_uj = read_rapl_max_uj()
    print(f"  [ENERGY] Measuring CPU idle power for {duration:.1f} s...")
    time.sleep(duration)
    e1 = read_rapl_uj()
    dj = compute_rapl_delta_joules(e0, e1, max_uj)
    if dj is not None:
        p_idle = dj / duration
        return dj, p_idle
    return None, None

def parse_run_line(line: str) -> Dict[str, str]:
    parts = line.strip().split()
    res = {}
    i = 0
    while i < len(parts):
        key = parts[i]
        if i + 1 < len(parts):
            res[key] = parts[i+1]
        i += 2
    return res

class BenchmarkRunner:
    def __init__(self, data_file: str, runs: int = 5, warmup_s: float = 3.0, duration_s: float = 15.0,
                 output_mode: str = "full"):
        self.data_file = data_file
        self.file_size = os.path.getsize(data_file)
        self.runs = runs
        self.warmup_s = warmup_s
        self.duration_s = duration_s
        self.output_mode = output_mode
        self.rapl_available = read_rapl_uj() is not None
        self.max_rapl_uj = read_rapl_max_uj()

        if not self.rapl_available:
            print("  [NOTICE] CPU RAPL is not directly readable without root (mode 0400).")
            print("           Energy metrics (J/GB) will be recorded as N/A unless run with sudo")
            print("           or permissions modified: 'sudo chmod 444 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj'.")

        self.raw_results = []
        self.summary_results = []

    def run_cpu_config(self, impl: str, threads: int, chunk_size: int, cores: str) -> Dict:
        N = self.file_size // chunk_size
        B = (chunk_size + 9 + 63) // 64
        payload = N * chunk_size

        print(f"\n{'='*70}\n[BENCHMARK CPU] Impl: {impl.upper()} | Threads: {threads} (Cores: {cores}) | C: {chunk_size} B | N: {N}\n{'='*70}")

        idle_j, idle_power = measure_cpu_idle_power(10.0) if self.rapl_available else (None, None)

        cmd = [
            "./cpu/sha256_cpu_bench",
            "--file", self.data_file,
            "--impl", impl,
            "--threads", str(threads),
            "--chunk-size", str(chunk_size),
            "--output-mode", self.output_mode,
            "--cores", cores,
            "--warmup", str(self.warmup_s),
            "--duration", str(self.duration_s),
            "--runs", str(self.runs)
        ]

        e_before = read_rapl_uj() if self.rapl_available else None
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate()
        e_after = read_rapl_uj() if self.rapl_available else None

        if proc.returncode != 0:
            print(f"Error running CPU benchmark:\n{stderr}", file=sys.stderr)
            return {}

        rapl_delta_j = compute_rapl_delta_joules(e_before, e_after, self.max_rapl_uj) if self.rapl_available else None

        tputs = []
        hashes_list = []
        blocks_list = []
        iters_list = []
        run_data = []

        for line in stdout.splitlines():
            if line.startswith("RUN "):
                p = parse_run_line(line)
                tput = float(p.get("THROUGHPUT_GBS", 0.0))
                hashes = float(p.get("HASHES_PER_SEC", 0.0))
                blocks = float(p.get("BLOCKS_PER_SEC", 0.0))
                iters = float(p.get("ITERATIONS", 0.0))
                tputs.append(tput)
                hashes_list.append(hashes)
                blocks_list.append(blocks)
                iters_list.append(iters)
                run_data.append(p)
                print(f"  {line}")

        if not tputs:
            return {}

        avg_tput = statistics.mean(tputs)
        sd_tput = statistics.stdev(tputs) if len(tputs) > 1 else 0.0
        avg_hashes = statistics.mean(hashes_list)
        avg_blocks = statistics.mean(blocks_list)
        total_iters = sum(iters_list)

        j_gb_gross = (rapl_delta_j / (total_iters * (payload / 1e9))) if (rapl_delta_j and total_iters > 0) else None
        j_gb_net = None
        if j_gb_gross is not None and idle_power is not None:
            total_elapsed = self.duration_s * self.runs
            net_j = max(0.0, rapl_delta_j - (idle_power * total_elapsed))
            j_gb_net = net_j / (total_iters * (payload / 1e9))

        cores_list = [int(x) for x in cores.split(",") if x.isdigit()]
        avg_freq = read_cpu_freqs(cores_list)

        res = {
            "plataforma": "CPU",
            "variante": f"{impl.upper()}_{threads}T",
            "C": chunk_size,
            "N": N,
            "B": B,
            "threads_cores": f"{threads}T ({cores})",
            "staging": "RAM (Host)",
            "output_mode": self.output_mode,
            "nivel": "E2E",
            "throughput_mean_GBs": avg_tput,
            "throughput_sd_GBs": sd_tput,
            "hashes_s": avg_hashes,
            "blocks_s": avg_blocks,
            "J_GB_dispositivo": j_gb_gross if j_gb_gross is not None else "N/A",
            "J_GB_neto": j_gb_net if j_gb_net is not None else "N/A",
            "J_GB_con_host": j_gb_gross if j_gb_gross is not None else "N/A",
            "potencia_media_W": (rapl_delta_j / (self.duration_s * self.runs)) if rapl_delta_j else "N/A",
            "frecuencia_MHz": avg_freq,
            "iteraciones": total_iters
        }
        return res

    def run_gpu_config(self, version: str, chunk_size: int, staging: str, batch_size: int = 67108864) -> List[Dict]:
        binary = "./gpu/sha256_gpu" if version == "v1" else "./gpu/sha256_gpu_v2"
        N = self.file_size // chunk_size
        B = (chunk_size + 9 + 63) // 64
        payload = N * chunk_size

        print(f"\n{'='*70}\n[BENCHMARK GPU] Version: {version.upper()} | Staging: {staging.upper()} | C: {chunk_size} B | N: {N}\n{'='*70}")

        cmd = [
            binary,
            "--file", self.data_file,
            "--chunk-size", str(chunk_size),
            "--output-mode", self.output_mode,
            "--staging", staging,
            "--runs", str(self.runs)
        ]
        if version == "v2":
            cmd += ["--batch-size", str(batch_size)]

        e_before = read_rapl_uj() if self.rapl_available else None
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = proc.communicate()
        e_after = read_rapl_uj() if self.rapl_available else None

        if proc.returncode != 0:
            print(f"Error running GPU benchmark:\n{stderr}", file=sys.stderr)
            return []

        host_rapl_j = compute_rapl_delta_joules(e_before, e_after, self.max_rapl_uj) if self.rapl_available else None

        tput_k_list = []
        tput_e_list = []
        hashes_list = []
        blocks_list = []

        for line in stdout.splitlines():
            if line.startswith("RUN "):
                p = parse_run_line(line)
                tk = float(p.get("THROUGHPUT_KERNEL_GBS", 0.0))
                te = float(p.get("THROUGHPUT_E2E_GBS", 0.0))
                hashes = float(p.get("HASHES_PER_SEC", 0.0))
                blocks = float(p.get("BLOCKS_PER_SEC", 0.0))
                tput_k_list.append(tk)
                tput_e_list.append(te)
                hashes_list.append(hashes)
                blocks_list.append(blocks)
                print(f"  {line}")

        if not tput_k_list:
            return []

        avg_tk = statistics.mean(tput_k_list)
        sd_tk = statistics.stdev(tput_k_list) if len(tput_k_list) > 1 else 0.0
        avg_te = statistics.mean(tput_e_list)
        sd_te = statistics.stdev(tput_e_list) if len(tput_e_list) > 1 else 0.0

        res_k = {
            "plataforma": "GPU",
            "variante": f"GPU_{version.upper()}",
            "C": chunk_size,
            "N": N,
            "B": B,
            "threads_cores": "16 SMs (2048 CUDA Cores)",
            "staging": staging,
            "output_mode": self.output_mode,
            "nivel": "kernel-only",
            "throughput_mean_GBs": avg_tk,
            "throughput_sd_GBs": sd_tk,
            "hashes_s": avg_hashes if (avg_hashes := statistics.mean(hashes_list)) else 0.0,
            "blocks_s": avg_blocks if (avg_blocks := statistics.mean(blocks_list)) else 0.0,
            "J_GB_dispositivo": "N/A (NVML driver mismatch)",
            "J_GB_neto": "N/A",
            "J_GB_con_host": (host_rapl_j / (self.runs * (payload / 1e9))) if host_rapl_j else "N/A",
            "potencia_media_W": "N/A (NVML driver mismatch)",
            "frecuencia_MHz": "N/A",
            "iteraciones": self.runs
        }

        res_e = {
            "plataforma": "GPU",
            "variante": f"GPU_{version.upper()}",
            "C": chunk_size,
            "N": N,
            "B": B,
            "threads_cores": "16 SMs (2048 CUDA Cores)",
            "staging": staging,
            "output_mode": self.output_mode,
            "nivel": "E2E",
            "throughput_mean_GBs": avg_te,
            "throughput_sd_GBs": sd_te,
            "hashes_s": avg_hashes,
            "blocks_s": avg_blocks,
            "J_GB_dispositivo": "N/A (NVML driver mismatch)",
            "J_GB_neto": "N/A",
            "J_GB_con_host": (host_rapl_j / (self.runs * (payload / 1e9))) if host_rapl_j else "N/A",
            "potencia_media_W": "N/A (NVML driver mismatch)",
            "frecuencia_MHz": "N/A",
            "iteraciones": self.runs
        }

        return [res_k, res_e]

def main():
    parser = argparse.ArgumentParser(description="SHA-256 Benchmark Orchestrator")
    parser.add_argument("--file", type=str, default="dummy_1GB.bin", help="Input file path")
    parser.add_argument("--runs", type=int, default=5, help="Number of repetitions per config")
    parser.add_argument("--duration", type=float, default=15.0, help="Continuous loop duration (seconds)")
    parser.add_argument("--warmup", type=float, default=3.0, help="Warmup duration (seconds)")
    parser.add_argument("--quick", action="store_true", help="Quick mode for rapid smoke test")
    parser.add_argument("--sweep-c", action="store_true", help="Run full sweep of C (64B, 1KB, 4KB, 64KB, 1MB)")
    parser.add_argument("--gpu-only", action="store_true", help="Run only GPU benchmarks")
    parser.add_argument("--cpu-only", action="store_true", help="Run only CPU benchmarks")
    args = parser.parse_args()

    dur = 2.0 if args.quick else args.duration
    warm = 0.5 if args.quick else args.warmup
    runs = 2 if args.quick else args.runs

    runner = BenchmarkRunner(args.file, runs=runs, warmup_s=warm, duration_s=dur)
    results = []

    # 1. CPU Benchmarks
    if not args.gpu_only:
        # Configurations:
        # Escalar 1T, SHA-NI 1T, 2T, 4T, 8T E-cores (4-11), 12T (0-11)
        cpu_configs = [
            ("scalar", 1, "4"),
            ("shani", 1, "4"),
            ("shani", 2, "4,5"),
            ("shani", 4, "4,5,6,7"),
            ("shani", 8, "4,5,6,7,8,9,10,11"),
            ("shani", 12, "0,1,2,3,4,5,6,7,8,9,10,11")
        ]

        # Main scenario: C = 64 B
        for impl, threads, cores in cpu_configs:
            r = runner.run_cpu_config(impl, threads, 64, cores)
            if r: results.append(r)

        # Sweep of C on CPU (using SHA-NI 4T as standard)
        if args.sweep_c and not args.quick:
            for c in [1024, 4096, 65536, 1048576]:
                r = runner.run_cpu_config("shani", 4, c, "4,5,6,7")
                if r: results.append(r)

    # 2. GPU Benchmarks
    if not args.cpu_only:
        c_list = SWEEP_C if args.sweep_c and not args.quick else [64]

        for c in c_list:
            # v1 Baseline (pinned and pageable)
            for stg in ["pinned", "pageable"]:
                res_list = runner.run_gpu_config("v1", c, stg)
                results.extend(res_list)

            # v2 High-utilization (pinned and pageable)
            for stg in ["pinned", "pageable"]:
                res_list = runner.run_gpu_config("v2", c, stg)
                results.extend(res_list)

    # Compute speedups
    # Anchor 1: SHA-NI 4T E2E at C=64
    ref_shani_4t = None
    ref_scalar_1t = None
    for r in results:
        if r["plataforma"] == "CPU" and r["C"] == 64:
            if "SHANI_4T" in r["variante"]:
                ref_shani_4t = r["throughput_mean_GBs"]
            elif "SCALAR_1T" in r["variante"]:
                ref_scalar_1t = r["throughput_mean_GBs"]

    for r in results:
        tput = r["throughput_mean_GBs"]
        r["speedup_vs_SHANI4T"] = f"{tput / ref_shani_4t:.2f}x" if ref_shani_4t else "N/A"
        r["speedup_vs_escalar1T"] = f"{tput / ref_scalar_1t:.2f}x" if ref_scalar_1t else "N/A"

    # Write results to CSV
    os.makedirs("results", exist_ok=True)
    csv_file = "results/benchmarks_summary.csv"
    if results:
        fields = list(results[0].keys())
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(results)
        print(f"\n[DONE] Saved summary benchmark results to '{csv_file}'.")

if __name__ == "__main__":
    main()
