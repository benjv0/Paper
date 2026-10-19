#!/usr/bin/env python3
"""
measure_idle.py — Measure CPU PKG (RAPL MSR/MMIO) and GPU (NVML counter & sampling)
idle power over 3 runs of 30 seconds.
"""
import time
import ctypes
import statistics
import os

RAPL_MSR = "/sys/class/powercap/intel-rapl:0/energy_uj"
RAPL_MMIO = "/sys/class/powercap/intel-rapl-mmio:0/energy_uj"

def read_rapl(path):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except Exception as e:
        return None

def init_nvml():
    try:
        nvml = ctypes.CDLL("libnvidia-ml.so.1")
        nvml.nvmlInit_v2()
        h = ctypes.c_void_p()
        nvml.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h))
        return nvml, h
    except Exception as e:
        print("NVML init error:", e)
        return None, None

def get_nvml_energy_mj(nvml, h):
    e = ctypes.c_ulonglong()
    res = nvml.nvmlDeviceGetTotalEnergyConsumption(h, ctypes.byref(e))
    if res == 0:
        return e.value
    return None

def get_nvml_power_w(nvml, h):
    p = ctypes.c_uint()
    res = nvml.nvmlDeviceGetPowerUsage(h, ctypes.byref(p))
    if res == 0:
        return p.value / 1000.0
    return None

def main():
    nvml, h = init_nvml()
    print("Measuring idle power: 3 runs of 30 seconds each...")
    
    cpu_msr_powers = []
    cpu_mmio_powers = []
    gpu_cnt_powers = []
    gpu_samp_powers = []
    
    for r in range(1, 4):
        print(f"\n--- Idle Run {r}/3 (30 s) ---")
        t0 = time.time()
        c_msr0 = read_rapl(RAPL_MSR)
        c_mmio0 = read_rapl(RAPL_MMIO)
        g_cnt0 = get_nvml_energy_mj(nvml, h) if nvml else None
        
        gpu_samples = []
        while True:
            now = time.time()
            if now - t0 >= 30.0:
                break
            if nvml:
                pw = get_nvml_power_w(nvml, h)
                if pw is not None:
                    gpu_samples.append(pw)
            time.sleep(0.1)
        
        t1 = time.time()
        dt = t1 - t0
        c_msr1 = read_rapl(RAPL_MSR)
        c_mmio1 = read_rapl(RAPL_MMIO)
        g_cnt1 = get_nvml_energy_mj(nvml, h) if nvml else None
        
        if c_msr0 is not None and c_msr1 is not None:
            p_msr = (c_msr1 - c_msr0) / (dt * 1e6)
            cpu_msr_powers.append(p_msr)
            print(f"  CPU PKG (MSR):  {p_msr:.3f} W (delta: {(c_msr1 - c_msr0)/1e6:.3f} J in {dt:.2f} s)")
            
        if c_mmio0 is not None and c_mmio1 is not None:
            p_mmio = (c_mmio1 - c_mmio0) / (dt * 1e6)
            cpu_mmio_powers.append(p_mmio)
            print(f"  CPU PKG (MMIO): {p_mmio:.3f} W (delta: {(c_mmio1 - c_mmio0)/1e6:.3f} J in {dt:.2f} s)")
            
        if g_cnt0 is not None and g_cnt1 is not None:
            p_g_cnt = (g_cnt1 - g_cnt0) / (dt * 1000.0)
            gpu_cnt_powers.append(p_g_cnt)
            print(f"  GPU (Counter):  {p_g_cnt:.3f} W (delta: {(g_cnt1 - g_cnt0)/1000.0:.3f} J in {dt:.2f} s)")
            
        if gpu_samples:
            p_g_samp = statistics.mean(gpu_samples)
            gpu_samp_powers.append(p_g_samp)
            print(f"  GPU (Sampling): {p_g_samp:.3f} W (samples: {len(gpu_samples)})")

    print("\n" + "="*50)
    print("FINAL IDLE BASELINE SUMMARY (mean ± std):")
    if cpu_msr_powers:
        m = statistics.mean(cpu_msr_powers)
        s = statistics.stdev(cpu_msr_powers) if len(cpu_msr_powers) > 1 else 0.0
        print(f"  CPU PKG (MSR):  {m:.3f} ± {s:.3f} W")
    if cpu_mmio_powers:
        m = statistics.mean(cpu_mmio_powers)
        s = statistics.stdev(cpu_mmio_powers) if len(cpu_mmio_powers) > 1 else 0.0
        print(f"  CPU PKG (MMIO): {m:.3f} ± {s:.3f} W")
    if gpu_cnt_powers:
        m = statistics.mean(gpu_cnt_powers)
        s = statistics.stdev(gpu_cnt_powers) if len(gpu_cnt_powers) > 1 else 0.0
        print(f"  GPU (Counter):  {m:.3f} ± {s:.3f} W")
    if gpu_samp_powers:
        m = statistics.mean(gpu_samp_powers)
        s = statistics.stdev(gpu_samp_powers) if len(gpu_samp_powers) > 1 else 0.0
        print(f"  GPU (Sampling): {m:.3f} ± {s:.3f} W")
    print("="*50)

if __name__ == "__main__":
    main()
