#!/usr/bin/env python3
"""
run_gpu_energy_unified.py — Unified GPU Benchmark & Telemetry Runner
=====================================================================
Measures GPU throughput and energy strictly in the SAME continuous loop:
- Primary GPU energy: nvmlDeviceGetTotalEnergyConsumption (hardware counter, mJ)
- Secondary GPU check: nvmlDeviceGetPowerUsage sampled at 10 Hz
- Host energy: /sys/class/powercap/intel-rapl:0/energy_uj (RAPL PKG)
- Idle baselines: GPU P_idle = 4.439 W, Host P_idle = 5.154 W (from 3x30s calibration)
- Consistency check: | power / (J/GB) - throughput | < 3%
"""

import os
import sys
import time
import ctypes
import threading
import subprocess
import argparse
import statistics
from typing import List, Dict, Optional

RAPL_PKG = "/sys/class/powercap/intel-rapl:0/energy_uj"
IDLE_GPU_W = 4.439
IDLE_HOST_W = 5.154

class NVMLHarness:
    def __init__(self):
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

    def read_counter_mj(self) -> Optional[int]:
        if not self.is_available():
            return None
        c = ctypes.c_ulonglong()
        res = self._nvml.nvmlDeviceGetTotalEnergyConsumption(self._handle, ctypes.byref(c))
        if res == 0:
            return c.value
        return None

    def sample_power_w(self) -> Optional[float]:
        if not self.is_available():
            return None
        p = ctypes.c_uint()
        res = self._nvml.nvmlDeviceGetPowerUsage(self._handle, ctypes.byref(p))
        if res == 0:
            return p.value / 1000.0
        return None

    def shutdown(self):
        if self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except Exception:
                pass

class PowerSampler:
    def __init__(self, harness: NVMLHarness, interval_s: float = 0.1):
        self.harness = harness
        self.interval = interval_s
        self.samples: List[float] = []
        self._stop = threading.Event()
        self._thread = None

    def _worker(self):
        while not self._stop.is_set():
            pw = self.harness.sample_power_w()
            if pw is not None:
                self.samples.append(pw)
            time.sleep(self.interval)

    def start(self):
        self.samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> List[float]:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=1.0)
        return list(self.samples)

def read_rapl_uj() -> Optional[int]:
    try:
        with open(RAPL_PKG, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

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

def run_benchmark(binary: str, chunk_size: int, mode: str, staging: str,
                  runs: int, duration_s: float, warmup_s: float,
                  data_file: str, p_idle_gpu: float = IDLE_GPU_W,
                  p_idle_host: float = IDLE_HOST_W) -> Dict:
    nvml = NVMLHarness()
    if not nvml.is_available():
        raise RuntimeError("NVML is not available!")

    file_bytes = os.path.getsize(data_file)
    N = file_bytes // chunk_size
    B = (chunk_size + 9 + 63) // 64
    payload_per_iter = N * chunk_size

    cmd = [
        binary,
        "--file", data_file,
        "--chunk-size", str(chunk_size),
        "--staging", staging,
        "--output-mode", "full",
        "--mode", mode,
        "--warmup", str(warmup_s),
        "--duration", str(duration_s),
        "--runs", str(runs)
    ]
    if "gpu_v2" in binary:
        cmd += ["--batch-size", "67108864"]

    print(f"\n{'='*75}\n[BENCHMARK] Binary: {binary} | Mode: {mode.upper()} | C: {chunk_size} B | Staging: {staging.upper()} | Runs: {runs} x >={duration_s}s\n{'='*75}")

    sampler = PowerSampler(nvml, interval_s=0.1)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    run_records = []
    current_run = None
    g_cnt_start = None
    rapl_start = None
    t_start = None

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
            g_cnt_start = nvml.read_counter_mj()
            rapl_start = read_rapl_uj()
            t_start = time.time()
            sampler.start()
        elif line.startswith("RUN"):
            samples = sampler.stop()
            t_end = time.time()
            g_cnt_end = nvml.read_counter_mj()
            rapl_end = read_rapl_uj()

            parsed = parse_run_line(line)
            iters = float(parsed.get("ITERATIONS", 1.0))
            if mode == "kernel":
                elapsed_c = float(parsed.get("TIME_KERNEL_S", duration_s))
                tput_c = float(parsed.get("THROUGHPUT_KERNEL_GBS", 0.0))
            else:
                elapsed_c = float(parsed.get("TIME_E2E_S", duration_s))
                tput_c = float(parsed.get("THROUGHPUT_E2E_GBS", 0.0))

            dt_wall = t_end - t_start if t_start else elapsed_c
            # Use elapsed reported by binary as primary time window
            elapsed = elapsed_c
            payload_gb = iters * (payload_per_iter / 1e9)
            derived_tput = payload_gb / elapsed if elapsed > 0 else 0.0

            # GPU Energy & Power (Counter)
            if g_cnt_start is not None and g_cnt_end is not None:
                delta_g_mj = g_cnt_end - g_cnt_start
                delta_g_j = delta_g_mj / 1000.0
            else:
                delta_g_j = 0.0

            p_gpu_w = delta_g_j / elapsed if elapsed > 0 else 0.0
            j_gb_gross_gpu = delta_g_j / payload_gb if payload_gb > 0 else 0.0
            delta_g_net = max(0.0, delta_g_j - (p_idle_gpu * elapsed))
            j_gb_net_gpu = delta_g_net / payload_gb if payload_gb > 0 else 0.0

            # GPU Sampling check
            p_gpu_samp = statistics.mean(samples) if samples else p_gpu_w
            diff_pct_gpu = abs(p_gpu_w - p_gpu_samp) / p_gpu_w * 100.0 if p_gpu_w > 0 else 0.0

            # Host Energy & Power (RAPL PKG)
            if rapl_start is not None and rapl_end is not None:
                delta_h_uj = rapl_end - rapl_start
                delta_h_j = delta_h_uj / 1e6
            else:
                delta_h_j = 0.0

            p_host_w = delta_h_j / elapsed if elapsed > 0 else 0.0
            j_gb_gross_host = delta_h_j / payload_gb if payload_gb > 0 else 0.0
            delta_h_net = max(0.0, delta_h_j - (p_idle_host * elapsed))
            j_gb_net_host = delta_h_net / payload_gb if payload_gb > 0 else 0.0

            # Total (GPU + Host)
            j_gb_net_total = j_gb_net_gpu + j_gb_net_host
            j_gb_gross_total = j_gb_gross_gpu + j_gb_gross_host

            # Strict consistency check: | power / (J/GB) - throughput | < 3%
            impl_tput = (p_gpu_w / j_gb_gross_gpu) if j_gb_gross_gpu > 0 else 0.0
            err_pct = abs(impl_tput - tput_c) / tput_c * 100.0 if tput_c > 0 else 0.0

            print(f"  Run {current_run}:")
            print(f"    Loop: iters={int(iters)}, dt={elapsed:.4f} s, payload={payload_gb:.4f} GB")
            print(f"    Throughput: {tput_c:.4f} GB/s (derived: {derived_tput:.4f} GB/s, diff={abs(derived_tput-tput_c):.6f})")
            print(f"    GPU (Counter):  ΔE={delta_g_j:.3f} J, P={p_gpu_w:.2f} W, J/GB bruto={j_gb_gross_gpu:.3f}, J/GB neto={j_gb_net_gpu:.3f}")
            print(f"    GPU (Sampling): P={p_gpu_samp:.2f} W (samples={len(samples)}, counter diff={diff_pct_gpu:.2f}%)")
            print(f"    Host (RAPL):    ΔE={delta_h_j:.3f} J, P={p_host_w:.2f} W, J/GB neto={j_gb_net_host:.3f}")
            print(f"    GPU+Host:       J/GB neto total={j_gb_net_total:.3f} J/GB")
            print(f"    Consistency:    P/(J/GB)={impl_tput:.4f} GB/s vs Tput={tput_c:.4f} GB/s | Error={err_pct:.3f}% (LIMIT < 3.0%)")

            if err_pct >= 3.0:
                raise AssertionError(f"[ABORT] Consistency check failed: error={err_pct:.2f}% >= 3.0% on run {current_run}!")

            run_records.append({
                "run": current_run,
                "throughput_GBs": tput_c,
                "elapsed_s": elapsed,
                "iters": iters,
                "payload_gb": payload_gb,
                "power_gpu_w": p_gpu_w,
                "power_gpu_samp_w": p_gpu_samp,
                "diff_gpu_pct": diff_pct_gpu,
                "j_gb_gross_gpu": j_gb_gross_gpu,
                "j_gb_net_gpu": j_gb_net_gpu,
                "power_host_w": p_host_w,
                "j_gb_gross_host": j_gb_gross_host,
                "j_gb_net_host": j_gb_net_host,
                "j_gb_net_total": j_gb_net_total,
                "j_gb_gross_total": j_gb_gross_total,
                "hashes_s": float(parsed.get("HASHES_PER_SEC", 0.0)),
                "blocks_s": float(parsed.get("BLOCKS_PER_SEC", 0.0))
            })

    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Binary failed with return code {proc.returncode}:\n{stderr}")

    def mean_sd(vals):
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return m, s

    m_tput, s_tput = mean_sd([r["throughput_GBs"] for r in run_records])
    m_pgpu, s_pgpu = mean_sd([r["power_gpu_w"] for r in run_records])
    m_jgross_g, s_jgross_g = mean_sd([r["j_gb_gross_gpu"] for r in run_records])
    m_jnet_g, s_jnet_g = mean_sd([r["j_gb_net_gpu"] for r in run_records])
    m_phost, s_phost = mean_sd([r["power_host_w"] for r in run_records])
    m_jnet_h, s_jnet_h = mean_sd([r["j_gb_net_host"] for r in run_records])
    m_jnet_tot, s_jnet_tot = mean_sd([r["j_gb_net_total"] for r in run_records])
    m_diff_g, _ = mean_sd([r["diff_gpu_pct"] for r in run_records])

    summary = {
        "binary": binary,
        "mode": mode,
        "staging": staging,
        "C": chunk_size,
        "N": N,
        "B": B,
        "runs": runs,
        "tput_mean": m_tput,
        "tput_sd": s_tput,
        "p_gpu_mean": m_pgpu,
        "p_gpu_sd": s_pgpu,
        "j_gross_gpu_mean": m_jgross_g,
        "j_gross_gpu_sd": s_jgross_g,
        "j_net_gpu_mean": m_jnet_g,
        "j_net_gpu_sd": s_jnet_g,
        "p_host_mean": m_phost,
        "p_host_sd": s_phost,
        "j_net_host_mean": m_jnet_h,
        "j_net_host_sd": s_jnet_h,
        "j_net_total_mean": m_jnet_tot,
        "j_net_total_sd": s_jnet_tot,
        "diff_counter_sampling_pct": m_diff_g,
        "hashes_s": statistics.mean([r["hashes_s"] for r in run_records]),
        "blocks_s": statistics.mean([r["blocks_s"] for r in run_records]),
        "raw_records": run_records
    }
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", default="./gpu/sha256_gpu_v2")
    parser.add_argument("--chunk-size", type=int, default=64)
    parser.add_argument("--mode", default="e2e", choices=["kernel", "e2e"])
    parser.add_argument("--staging", default="pinned", choices=["pinned", "pageable"])
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--file", default="dummy_1GB.bin")
    args = parser.parse_args()

    res = run_benchmark(
        binary=args.binary,
        chunk_size=args.chunk_size,
        mode=args.mode,
        staging=args.staging,
        runs=args.runs,
        duration_s=args.duration,
        warmup_s=args.warmup,
        data_file=args.file
    )
    print("\n" + "="*75)
    print(f"SUMMARY: {args.binary} {args.mode} {args.staging} C={args.chunk_size}")
    print(f"Throughput: {res['tput_mean']:.3f} ± {res['tput_sd']:.3f} GB/s")
    print(f"GPU Power:  {res['p_gpu_mean']:.2f} ± {res['p_gpu_sd']:.2f} W")
    print(f"J/GB bruto GPU:   {res['j_gross_gpu_mean']:.3f} ± {res['j_gross_gpu_sd']:.3f}")
    print(f"J/GB neto GPU:    {res['j_net_gpu_mean']:.3f} ± {res['j_net_gpu_sd']:.3f}")
    print(f"Host Power: {res['p_host_mean']:.2f} ± {res['p_host_sd']:.2f} W")
    print(f"J/GB neto Host:   {res['j_net_host_mean']:.3f} ± {res['j_net_host_sd']:.3f}")
    print(f"J/GB neto Total:  {res['j_net_total_mean']:.3f} ± {res['j_net_total_sd']:.3f}")
    print("="*75)
