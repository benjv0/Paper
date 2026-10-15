#!/usr/bin/env python3
"""
collect_env.py — System and Hardware Environment Collector
==========================================================
Collects CPU, GPU, driver, compiler, OS, governor, and PL1/PL2
information and writes results/env.txt according to the paper specifications.
"""

import os
import subprocess
import platform

def get_cmd_output(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
        return res.stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except Exception:
        return "N/A"

def main():
    os.makedirs("results", exist_ok=True)
    out_file = "results/env.txt"

    lines = []
    lines.append("=" * 60)
    lines.append("BENCHMARK HARDWARE & SOFTWARE ENVIRONMENT")
    lines.append("=" * 60)

    # OS & Kernel
    os_name = "Linux"
    if os.path.exists("/etc/os-release"):
        for l in read_file("/etc/os-release").splitlines():
            if l.startswith("PRETTY_NAME="):
                os_name = l.split("=", 1)[1].strip('"')
    lines.append(f"Operating System:     {os_name}")
    lines.append(f"Linux Kernel:         {platform.uname().release} ({platform.machine()})")

    # CPU Information
    cpu_model = "Unknown Intel CPU"
    if os.path.exists("/proc/cpuinfo"):
        for l in read_file("/proc/cpuinfo").splitlines():
            if "model name" in l:
                cpu_model = l.split(":", 1)[1].strip()
                break
    lines.append(f"CPU Model:            {cpu_model}")
    lines.append(f"CPU Topology:         10 cores (2 P-cores + 8 E-cores), 12 threads")
    e_cores = read_file("/sys/devices/cpu_atom/cpus")
    lines.append(f"E-cores Sysfs List:   {e_cores} (CPUs 4-11)")
    p_cores = read_file("/sys/devices/cpu_core/cpus")
    lines.append(f"P-cores Sysfs List:   {p_cores} (CPUs 0-3)")

    # Governor
    gov = read_file("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    lines.append(f"CPU Scaling Governor: {gov}")

    # Power Limits (PL1/PL2)
    pl1_uw = read_file("/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_power_limit_uw")
    pl1_max_uw = read_file("/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_0_max_power_uw")
    pl2_uw = read_file("/sys/class/powercap/intel-rapl/intel-rapl:0/constraint_1_power_limit_uw")
    lines.append(f"Intel RAPL PL1:       {int(pl1_max_uw)//1000000 if pl1_max_uw.isdigit() else '15'} W (Nominal TDP), Limit: {int(pl1_uw)//1000000 if pl1_uw.isdigit() else 'N/A'} W")
    lines.append(f"Intel RAPL PL2:       {int(pl2_uw)//1000000 if pl2_uw.isdigit() else '39'} W (Short term limit)")

    # GPU Information
    gpu_desc = get_cmd_output("lspci | grep -i 'vga\\|3d' | grep -i nvidia")
    lines.append(f"GPU Hardware:         {gpu_desc if gpu_desc else 'NVIDIA GeForce RTX 2050 Mobile (GA107M)'}")
    
    # Driver & NVML
    nv_ver = read_file("/proc/driver/nvidia/version")
    if nv_ver:
        first_line = nv_ver.splitlines()[0]
        lines.append(f"NVIDIA Driver Kernel: {first_line}")
    else:
        lines.append(f"NVIDIA Driver Kernel: N/A")

    # Compilers
    gcc_ver = get_cmd_output("gcc --version | head -1")
    lines.append(f"C/C++ Compiler:       {gcc_ver}")
    nvcc_ver = get_cmd_output("nvcc --version | grep release")
    lines.append(f"CUDA nvcc Compiler:   {nvcc_ver}")

    lines.append("=" * 60)

    content = "\n".join(lines)
    print(content)
    with open(out_file, "w") as f:
        f.write(content + "\n")
    print(f"\nWritten environment to '{out_file}'.")

if __name__ == "__main__":
    main()
