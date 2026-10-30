#!/usr/bin/env python3
"""
diagnose_c1024_nvml.py
Performs repeated runs of GPU v2 for C=1024 B while monitoring NVML clocks,
power, temperature, and throttle reasons via ctypes.
"""

import ctypes
import time
import subprocess
import threading
import statistics

# Initialize NVML via ctypes
nvml = ctypes.CDLL("libnvidia-ml.so")
nvml.nvmlInit()
device = ctypes.c_void_p()
nvml.nvmlDeviceGetHandleByIndex(0, ctypes.byref(device))

THROTTLE_NAMES = {
    0x0000000000000001: "GpuIdle",
    0x0000000000000002: "AppClocks",
    0x0000000000000004: "SwPowerCap",
    0x0000000000000008: "HwSlowdown",
    0x0000000000000010: "SyncBoost",
    0x0000000000000020: "SwThermal",
    0x0000000000000040: "HwThermal",
    0x0000000000000080: "HwPowerBrake",
    0x0000000000000100: "DisplayClock",
}

def decode_throttle(mask):
    reasons = [name for bit, name in THROTTLE_NAMES.items() if (mask & bit)]
    return reasons if reasons else ["None"]

class NVMLMonitor(threading.Thread):
    def __init__(self, interval_s=0.005):
        super().__init__(daemon=True)
        self.interval_s = interval_s
        self.stop_event = threading.Event()
        self.records = []

    def run(self):
        clk = ctypes.c_uint()
        mem_clk = ctypes.c_uint()
        pwr = ctypes.c_uint()
        temp = ctypes.c_uint()
        thr = ctypes.c_ulonglong()

        while not self.stop_event.is_set():
            t = time.time()
            nvml.nvmlDeviceGetClockInfo(device, 0, ctypes.byref(clk))      # NVML_CLOCK_GRAPHICS = 0
            nvml.nvmlDeviceGetClockInfo(device, 2, ctypes.byref(mem_clk))  # NVML_CLOCK_MEM = 2
            nvml.nvmlDeviceGetPowerUsage(device, ctypes.byref(pwr))
            nvml.nvmlDeviceGetTemperature(device, 0, ctypes.byref(temp))
            nvml.nvmlDeviceGetCurrentClocksThrottleReasons(device, ctypes.byref(thr))

            self.records.append({
                "time": t,
                "clock_mhz": clk.value,
                "mem_clock_mhz": mem_clk.value,
                "power_w": pwr.value / 1000.0,
                "temp_c": temp.value,
                "throttle_mask": hex(thr.value),
                "throttle_reasons": decode_throttle(thr.value)
            })
            time.sleep(self.interval_s)

def run_oneshot_5runs():
    print("="*70)
    print("TEST 1: ONE-SHOT MODE (5 runs, 1 GB per run without loop)")
    print("="*70)
    
    monitor = NVMLMonitor(interval_s=0.005)
    monitor.start()
    
    cmd = [
        "./gpu/sha256_gpu_v2",
        "--file", "dummy_1GB.bin",
        "--chunk-size", "1024",
        "--staging", "pinned",
        "--runs", "5"
    ]
    t0 = time.time()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    t1 = time.time()
    
    monitor.stop_event.set()
    monitor.join()
    
    print("STDOUT:")
    print(stdout.strip())
    
    print("\nNVML Sampling Summary:")
    print(f"Total samples collected: {len(monitor.records)} over {t1 - t0:.3f} s")
    if monitor.records:
        clocks = [r["clock_mhz"] for r in monitor.records]
        powers = [r["power_w"] for r in monitor.records]
        temps = [r["temp_c"] for r in monitor.records]
        masks = set(r["throttle_mask"] for r in monitor.records)
        all_reasons = set()
        for r in monitor.records:
            all_reasons.update(r["throttle_reasons"])
            
        print(f"Graphics Clock: min={min(clocks)} MHz, max={max(clocks)} MHz, mean={statistics.mean(clocks):.1f} MHz")
        print(f"Power: min={min(powers):.1f} W, max={max(powers):.1f} W, mean={statistics.mean(powers):.1f} W")
        print(f"Temp: min={min(temps)} C, max={max(temps)} C")
        print(f"Throttle bitmasks seen: {masks}")
        print(f"Throttle reasons active during execution: {all_reasons}")

if __name__ == "__main__":
    run_oneshot_5runs()
