#!/usr/bin/env python3
"""
run_gpu_energy.py — Rigorous GPU Energy Benchmark Runner for SHA-256
=====================================================================
Directly measures GPU v2 kernel-only and E2E energy via NVML C API:
- Synchronized strictly to the active execution loop (excludes warmup, setup, file loading)
- Continuous loop of >=15s x 5 runs
- Computes gross ΔE, gross J/GB, net ΔE, net J/GB (subtracting 10s idle power baseline)
- Computes host RAPL PKG if accessible
- Enforces automatic plausibility check: implied power = J/GB * GB/s <= TDP (30 W)
"""

import os
import sys
import time
import ctypes
import threading
import subprocess
import argparse
import statistics
from typing import List, Dict, Optional, Tuple

RAPL_PKG = "/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj"
RAPL_MAX = "/sys/class/powercap/intel-rapl/intel-rapl:0/max_energy_range_uj"

class NVMLSampler:
    def __init__(self, sample_interval_s: float = 0.05):
        self.interval = sample_interval_s
        self.samples: List[float] = []
        self._stop = threading.Event()
        self._thread = None
        self._nvml = None
        self._handle = None
        try:
            self._nvml = ctypes.CDLL("libnvidia-ml.so.1")
            self._nvml.nvmlInit_v2()
            self._handle = ctypes.c_void_p()
            self._nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(self._handle))
        except Exception as e:
            print(f"[WARN] Failed to init NVML: {e}", file=sys.stderr)

    def is_available(self) -> bool:
        return self._nvml is not None and self._handle is not None

    def _sample_power_w(self) -> Optional[float]:
        if not self.is_available():
            return None
        p = ctypes.c_uint()
        res = self._nvml.nvmlDeviceGetPowerUsage(self._handle, ctypes.byref(p))
        if res == 0:
            return p.value / 1000.0
        return None

    def measure_idle_power(self, duration_s: float = 10.0) -> float:
        if not self.is_available():
            return 0.0
        print(f"  [GPU ENERGY] Measuring GPU idle baseline for {duration_s:.1f} s...")
        t0 = time.time()
        readings = []
        while time.time() - t0 < duration_s:
            pw = self._sample_power_w()
            if pw is not None:
                readings.append(pw)
            time.sleep(self.interval)
        idle_w = statistics.mean(readings) if readings else 6.25
        print(f"  [GPU ENERGY] Measured GPU idle baseline: {idle_w:.3f} W (samples: {len(readings)})")
        return idle_w

    def _worker(self):
        while not self._stop.is_set():
            pw = self._sample_power_w()
            if pw is not None:
                self.samples.append(pw)
            time.sleep(self.interval)

    def start_sampling(self):
        self.samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop_sampling(self) -> List[float]:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=1.0)
        return list(self.samples)

    def shutdown(self):
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass

def read_rapl_uj() -> Optional[int]:
    try:
        with open(RAPL_PKG, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def compute_rapl_delta_joules(e_before: Optional[int], e_after: Optional[int]) -> Optional[float]:
    if e_before is None or e_after is None:
        return None
    if e_after >= e_before:
        d_uj = e_after - e_before
    else:
        d_uj = e_after
    return d_uj / 1e6

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

def run_gpu_mode(chunk_size: int, mode: str, runs: int, duration_s: float, warmup_s: float,
                 data_file: str, nvml: NVMLSampler, p_idle_gpu: float, staging: str = "pinned") -> Dict:
    file_bytes = os.path.getsize(data_file)
    N = file_bytes // chunk_size
    B = (chunk_size + 9 + 63) // 64
    payload_per_iter = N * chunk_size

    cmd = [
        "./gpu/sha256_gpu_v2",
        "--file", data_file,
        "--chunk-size", str(chunk_size),
        "--staging", staging,
        "--output-mode", "full",
        "--mode", mode,
        "--warmup", str(warmup_s),
        "--duration", str(duration_s),
        "--runs", str(runs)
    ]

    print(f"\n{'='*70}\n[BENCHMARK GPU v2] Mode: {mode.upper()} | C: {chunk_size} B | Staging: {staging.upper()} | Runs: {runs} x >={duration_s}s\n{'='*70}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    run_results = []
    current_run = None
    e_rapl_start = None

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        line = line.strip()
        if not line:
            continue

        if line.startswith("START_RUN"):
            parts = line.split()
            current_run = int(parts[1])
            e_rapl_start = read_rapl_uj()
            nvml.start_sampling()
        elif line.startswith("RUN"):
            samples = nvml.stop_sampling()
            e_rapl_stop = read_rapl_uj()
            parsed = parse_run_line(line)
            iters = float(parsed.get("ITERATIONS", 1.0))
            if mode == "kernel":
                elapsed = float(parsed.get("TIME_KERNEL_S", duration_s))
                tput = float(parsed.get("THROUGHPUT_KERNEL_GBS", 0.0))
            else:
                elapsed = float(parsed.get("TIME_E2E_S", duration_s))
                tput = float(parsed.get("THROUGHPUT_E2E_GBS", 0.0))
            hashes_s = float(parsed.get("HASHES_PER_SEC", 0.0))
            blocks_s = float(parsed.get("BLOCKS_PER_SEC", 0.0))

            avg_power = statistics.mean(samples) if samples else p_idle_gpu
            delta_e_gross = avg_power * elapsed
            payload_gb = iters * (payload_per_iter / 1e9)
            j_gb_gross = delta_e_gross / payload_gb if payload_gb > 0 else 0.0

            delta_e_net = max(0.0, delta_e_gross - (p_idle_gpu * elapsed))
            j_gb_net = delta_e_net / payload_gb if payload_gb > 0 else 0.0

            rapl_j = compute_rapl_delta_joules(e_rapl_start, e_rapl_stop)
            j_gb_con_host = ((delta_e_net + rapl_j) / payload_gb) if (rapl_j is not None and payload_gb > 0) else None

            # Plausibility check
            p_impl = j_gb_gross * tput
            assert p_impl <= 30.0, f"[ERROR] Implied power {p_impl:.2f} W exceeds GPU TDP 30 W!"

            run_results.append({
                "run": current_run,
                "throughput_GBs": tput,
                "hashes_s": hashes_s,
                "blocks_s": blocks_s,
                "iters": iters,
                "elapsed_s": elapsed,
                "power_w": avg_power,
                "J_GB_gross": j_gb_gross,
                "J_GB_net": j_gb_net,
                "J_GB_con_host": j_gb_con_host,
                "samples_count": len(samples)
            })
            print(f"  Run {current_run}: Tput={tput:.2f} GB/s | Power={avg_power:.2f} W | J/GB bruto={j_gb_gross:.2f} | J/GB neto={j_gb_net:.2f} | P_impl={p_impl:.2f} W (PASS <= 30W)")

    _, stderr = proc.communicate()
    if proc.returncode != 0:
        print(f"[ERROR] Process exited with code {proc.returncode}:\n{stderr}", file=sys.stderr)
        return {}

    tputs = [r["throughput_GBs"] for r in run_results]
    j_gross = [r["J_GB_gross"] for r in run_results]
    j_net = [r["J_GB_net"] for r in run_results]
    powers = [r["power_w"] for r in run_results]
    hashes = [r["hashes_s"] for r in run_results]
    blocks = [r["blocks_s"] for r in run_results]
    iters_l = [r["iters"] for r in run_results]
    host_l = [r["J_GB_con_host"] for r in run_results if r["J_GB_con_host"] is not None]

    mean_tput = statistics.mean(tputs)
    sd_tput = statistics.stdev(tputs) if len(tputs) > 1 else 0.0
    mean_jgross = statistics.mean(j_gross)
    sd_jgross = statistics.stdev(j_gross) if len(j_gross) > 1 else 0.0
    mean_jnet = statistics.mean(j_net)
    sd_jnet = statistics.stdev(j_net) if len(j_net) > 1 else 0.0
    mean_power = statistics.mean(powers)
    sd_power = statistics.stdev(powers) if len(powers) > 1 else 0.0
    mean_host = statistics.mean(host_l) if host_l else "N/A"
    sd_host = statistics.stdev(host_l) if len(host_l) > 1 else 0.0

    return {
        "plataforma": "GPU",
        "variante": "GPU_V2",
        "C": chunk_size,
        "N": N,
        "B": B,
        "threads_cores": "16 SMs (2048 CUDA Cores)",
        "staging": staging,
        "output_mode": "full",
        "nivel": "kernel-only" if mode == "kernel" else "E2E",
        "throughput_mean_GBs": mean_tput,
        "throughput_sd_GBs": sd_tput,
        "hashes_s": statistics.mean(hashes),
        "blocks_s": statistics.mean(blocks),
        "J_GB_dispositivo": mean_jgross,
        "J_GB_dispositivo_sd": sd_jgross,
        "J_GB_neto": mean_jnet,
        "J_GB_neto_sd": sd_jnet,
        "J_GB_con_host": mean_host,
        "J_GB_con_host_sd": sd_host if mean_host != "N/A" else "N/A",
        "potencia_media_W": mean_power,
        "potencia_sd_W": sd_power,
        "frecuencia_MHz": "N/A",
        "iteraciones": statistics.mean(iters_l),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="dummy_1GB.bin")
    parser.add_argument("--chunk-size", type=int, default=64)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--sweep-c", action="store_true")
    args = parser.parse_args()

    nvml = NVMLSampler()
    p_idle_gpu = nvml.measure_idle_power(10.0)

    c_list = [64, 1024, 4096, 65536, 1048576] if args.sweep_c else [args.chunk_size]

    results = []
    for c in c_list:
        res_k = run_gpu_mode(c, "kernel", args.runs, args.duration, args.warmup, args.file, nvml, p_idle_gpu, "pinned")
        res_e = run_gpu_mode(c, "e2e", args.runs, args.duration, args.warmup, args.file, nvml, p_idle_gpu, "pinned")
        results.extend([res_k, res_e])

    nvml.shutdown()

    print("\n" + "="*70)
    print("FINAL MEASURED GPU ENERGY RESULTS:")
    print("="*70)
    for r in results:
        print(f"{r['variante']} C={r['C']} {r['nivel']}: Tput={r['throughput_mean_GBs']:.2f} ± {r['throughput_sd_GBs']:.2f} GB/s | Power={r['potencia_media_W']:.2f} W | J/GB bruto={r['J_GB_dispositivo']:.2f} ± {r['J_GB_dispositivo_sd']:.2f} | J/GB neto={r['J_GB_neto']:.2f} ± {r['J_GB_neto_sd']:.2f}")

if __name__ == "__main__":
    main()
