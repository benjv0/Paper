#!/usr/bin/env python3
"""
run_cpu_scheduler_bench.py — Rigorous CPU Scheduling & Telemetry Benchmark
==========================================================================
Evaluates Static vs Dynamic scheduling on Intel Core i7-1255U:
- Measures 4T (E-cores), 8T (E-cores), 12T (8E oversubscribed), and 12T (P+E)
- Continuous loop of >=15s x 5 runs
- RAPL PKG energy (gross and net with P_idle = 5.154 W)
- 10 Hz frequency sampler separating P-cores (0-3) and E-cores (4-11)
- Thermal throttling counter and temperature monitoring
- Thread busy time and chunk distribution analysis
"""

import os
import sys
import time
import threading
import subprocess
import argparse
import statistics
from typing import List, Dict, Optional, Tuple

RAPL_PKG = "/sys/class/powercap/intel-rapl:0/energy_uj"
IDLE_CPU_W = 5.154
THROTTLE_PKG = "/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count"
TEMP_INPUT = "/sys/devices/platform/coretemp.0/hwmon/hwmon6/temp1_input"

def read_rapl_uj() -> Optional[int]:
    try:
        with open(RAPL_PKG, "r") as f:
            return int(f.read().strip())
    except Exception:
        return None

def read_throttle_count() -> int:
    try:
        with open(THROTTLE_PKG, "r") as f:
            return int(f.read().strip())
    except Exception:
        return 0

def read_cpu_temp() -> float:
    try:
        with open(TEMP_INPUT, "r") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return 0.0

class TelemetrySampler:
    def __init__(self, cores: List[int], interval_s: float = 0.1):
        self.cores = cores
        self.interval = interval_s
        self.p_cores = [c for c in cores if c < 4]
        self.e_cores = [c for c in cores if c >= 4]
        self.freq_p_samples: List[float] = []
        self.freq_e_samples: List[float] = []
        self.temp_samples: List[float] = []
        self._stop = threading.Event()
        self._thread = None

    def _sample_freq(self, core: int) -> Optional[float]:
        path = f"/sys/devices/system/cpu/cpu{core}/cpufreq/scaling_cur_freq"
        try:
            with open(path, "r") as f:
                return float(f.read().strip()) / 1000.0 # MHz
        except Exception:
            return None

    def _worker(self):
        while not self._stop.is_set():
            p_vals = [self._sample_freq(c) for c in self.p_cores]
            p_vals = [v for v in p_vals if v is not None]
            if p_vals:
                self.freq_p_samples.append(statistics.mean(p_vals))

            e_vals = [self._sample_freq(c) for c in self.e_cores]
            e_vals = [v for v in e_vals if v is not None]
            if e_vals:
                self.freq_e_samples.append(statistics.mean(e_vals))

            t = read_cpu_temp()
            if t > 0:
                self.temp_samples.append(t)

            time.sleep(self.interval)

    def start(self):
        self.freq_p_samples = []
        self.freq_e_samples = []
        self.temp_samples = []
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self) -> Dict:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=1.0)
        return {
            "p_freq_mean": statistics.mean(self.freq_p_samples) if self.freq_p_samples else 0.0,
            "e_freq_mean": statistics.mean(self.freq_e_samples) if self.freq_e_samples else 0.0,
            "temp_mean": statistics.mean(self.temp_samples) if self.temp_samples else 0.0,
            "temp_max": max(self.temp_samples) if self.temp_samples else 0.0
        }

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

def run_cpu_bench(impl: str, sched: str, threads: int, cores: str,
                  chunk_size: int, runs: int, duration_s: float, warmup_s: float,
                  data_file: str, p_idle: float = IDLE_CPU_W) -> Dict:
    file_bytes = os.path.getsize(data_file)
    N = file_bytes // chunk_size
    B = (chunk_size + 9 + 63) // 64
    payload_per_iter = N * chunk_size

    cores_list = [int(c) for c in cores.split(",") if c.strip().isdigit()]

    cmd = [
        "./cpu/sha256_cpu_bench",
        "--file", data_file,
        "--impl", impl,
        "--threads", str(threads),
        "--cores", cores,
        "--chunk-size", str(chunk_size),
        "--sched", sched,
        "--output-mode", "full",
        "--warmup", str(warmup_s),
        "--duration", str(duration_s),
        "--runs", str(runs)
    ]

    print(f"\n{'='*75}\n[CPU BENCHMARK] Sched: {sched.upper()} | Threads: {threads} ({cores}) | Runs: {runs} x >={duration_s}s\n{'='*75}")

    telemetry = TelemetrySampler(cores_list, interval_s=0.1)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    run_records = []
    current_run = None
    r_start_uj = None
    t0_wall = None
    throt_start = None

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        line = line.strip()
        if not line:
            continue

        if line.startswith("START_RUN"):
            r_start_uj = read_rapl_uj()
            throt_start = read_throttle_count()
            telemetry.start()
        elif line.startswith("RUN "):
            telem_data = telemetry.stop()
            r_end_uj = read_rapl_uj()
            throt_end = read_throttle_count()

            parsed = parse_run_line(line)
            current_run = int(parsed.get("RUN", 1))
            elapsed = float(parsed.get("ELAPSED_S", duration_s))
            tput = float(parsed.get("THROUGHPUT_GBS", 0.0))
            iters = float(parsed.get("ITERATIONS", 1.0))
            min_busy = float(parsed.get("MIN_BUSY_S", 0.0))
            max_busy = float(parsed.get("MAX_BUSY_S", 0.0))
            busy_imb = float(parsed.get("BUSY_IMBALANCE_S", 0.0))
            min_chunks = int(parsed.get("MIN_CHUNKS", 0))
            max_chunks = int(parsed.get("MAX_CHUNKS", 0))
            chunks_imb_pct = float(parsed.get("CHUNKS_IMBALANCE_PCT", 0.0))
            hashes_s = float(parsed.get("HASHES_PER_SEC", 0.0))
            blocks_s = float(parsed.get("BLOCKS_PER_SEC", 0.0))

            # RAPL PKG
            delta_uj = (r_end_uj - r_start_uj) if (r_start_uj and r_end_uj) else 0
            delta_j = delta_uj / 1e6
            p_pkg = delta_j / elapsed if elapsed > 0 else 0.0

            payload_gb = iters * (payload_per_iter / 1e9)
            j_gb_gross = delta_j / payload_gb if payload_gb > 0 else 0.0
            delta_j_net = max(0.0, delta_j - (p_idle * elapsed))
            j_gb_net = delta_j_net / payload_gb if payload_gb > 0 else 0.0

            d_throt = throt_end - throt_start if throt_start is not None else 0

            print(f"  Run {current_run}: Tput={tput:.3f} GB/s | Power={p_pkg:.2f} W | J/GB bruto={j_gb_gross:.3f} | J/GB neto={j_gb_net:.3f}")
            print(f"    Freq: P-cores={telem_data['p_freq_mean']:.0f} MHz, E-cores={telem_data['e_freq_mean']:.0f} MHz | Temp={telem_data['temp_mean']:.1f}°C (max {telem_data['temp_max']:.1f}°C) | Throttle={d_throt}")
            print(f"    Balance: Busy time range [{min_busy:.4f}s .. {max_busy:.4f}s] (Δ={busy_imb*1000:.1f}ms) | Chunks imbalance={chunks_imb_pct:.1f}%")

            run_records.append({
                "run": current_run,
                "throughput_GBs": tput,
                "elapsed_s": elapsed,
                "iters": iters,
                "payload_gb": payload_gb,
                "power_pkg_w": p_pkg,
                "j_gb_gross": j_gb_gross,
                "j_gb_net": j_gb_net,
                "min_busy_s": min_busy,
                "max_busy_s": max_busy,
                "busy_imb_s": busy_imb,
                "min_chunks": min_chunks,
                "max_chunks": max_chunks,
                "chunks_imb_pct": chunks_imb_pct,
                "p_freq_mhz": telem_data["p_freq_mean"],
                "e_freq_mhz": telem_data["e_freq_mean"],
                "temp_mean": telem_data["temp_mean"],
                "temp_max": telem_data["temp_max"],
                "throt_events": d_throt,
                "hashes_s": hashes_s,
                "blocks_s": blocks_s
            })

        elif line.startswith("[CPU] Warming up"):
            pass

    _, stderr = proc.communicate()
    telemetry.stop()
    if proc.returncode != 0:
        raise RuntimeError(f"CPU bench failed code {proc.returncode}:\n{stderr}")

    def mean_sd(vals):
        m = statistics.mean(vals)
        s = statistics.stdev(vals) if len(vals) > 1 else 0.0
        return m, s

    m_tput, s_tput = mean_sd([r["throughput_GBs"] for r in run_records])
    m_p, s_p = mean_sd([r["power_pkg_w"] for r in run_records])
    m_jgross, s_jgross = mean_sd([r["j_gb_gross"] for r in run_records])
    m_jnet, s_jnet = mean_sd([r["j_gb_net"] for r in run_records])
    m_pfreq, _ = mean_sd([r["p_freq_mhz"] for r in run_records])
    m_efreq, _ = mean_sd([r["e_freq_mhz"] for r in run_records])
    m_temp, _ = mean_sd([r["temp_mean"] for r in run_records])
    m_imb, _ = mean_sd([r["chunks_imb_pct"] for r in run_records])
    m_bimb, _ = mean_sd([r["busy_imb_s"] for r in run_records])

    summary = {
        "impl": impl,
        "sched": sched,
        "threads": threads,
        "cores": cores,
        "tput_mean": m_tput,
        "tput_sd": s_tput,
        "power_mean": m_p,
        "power_sd": s_p,
        "j_gross_mean": m_jgross,
        "j_gross_sd": s_jgross,
        "j_net_mean": m_jnet,
        "j_net_sd": s_jnet,
        "p_freq_mean": m_pfreq,
        "e_freq_mean": m_efreq,
        "temp_mean": m_temp,
        "chunks_imb_mean_pct": m_imb,
        "busy_imb_mean_s": m_bimb,
        "hashes_s": statistics.mean([r["hashes_s"] for r in run_records]),
        "blocks_s": statistics.mean([r["blocks_s"] for r in run_records]),
        "raw_records": run_records
    }
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--impl", default="shani")
    parser.add_argument("--sched", default="dynamic", choices=["static", "dynamic"])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--cores", default="4,5,6,7")
    parser.add_argument("--chunk-size", type=int, default=64)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--duration", type=float, default=15.0)
    parser.add_argument("--warmup", type=float, default=3.0)
    parser.add_argument("--file", default="dummy_1GB.bin")
    args = parser.parse_args()

    res = run_cpu_bench(
        impl=args.impl,
        sched=args.sched,
        threads=args.threads,
        cores=args.cores,
        chunk_size=args.chunk_size,
        runs=args.runs,
        duration_s=args.duration,
        warmup_s=args.warmup,
        data_file=args.file
    )
    print("\n" + "="*75)
    print(f"SUMMARY: {args.impl} {args.sched} {args.threads}T ({args.cores})")
    print(f"Throughput: {res['tput_mean']:.3f} ± {res['tput_sd']:.3f} GB/s")
    print(f"Power PKG:  {res['power_mean']:.2f} ± {res['power_sd']:.2f} W")
    print(f"J/GB bruto: {res['j_gross_mean']:.3f} ± {res['j_gross_sd']:.3f}")
    print(f"J/GB neto:  {res['j_net_mean']:.3f} ± {res['j_net_sd']:.3f}")
    print(f"P-freq:     {res['p_freq_mean']:.0f} MHz | E-freq: {res['e_freq_mean']:.0f} MHz")
    print(f"Imbalance:  Chunks={res['chunks_imb_mean_pct']:.1f}% | Busy Δ={res['busy_imb_mean_s']*1000:.1f} ms")
    print("="*75)
