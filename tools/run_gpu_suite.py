#!/usr/bin/env python3
"""
run_gpu_suite.py — Execute GPU v2 benchmarks (kernel-only, E2E pinned, E2E pageable)
at C=64 B with 5 runs of >=15s and record unified throughput, counter energy, sampling, and host RAPL.
"""
import json
import time
from run_gpu_energy_unified import run_benchmark

def main():
    configs = [
        {"mode": "kernel", "staging": "pinned"},
        {"mode": "e2e",    "staging": "pinned"},
        {"mode": "e2e",    "staging": "pageable"}
    ]
    
    results = []
    for cfg in configs:
        print(f"\n>>> Running GPU v2 {cfg['mode']} {cfg['staging']} C=64 B...")
        res = run_benchmark(
            binary="./gpu/sha256_gpu_v2",
            chunk_size=64,
            mode=cfg["mode"],
            staging=cfg["staging"],
            runs=5,
            duration_s=15.0,
            warmup_s=3.0,
            data_file="dummy_1GB.bin"
        )
        results.append(res)
        time.sleep(3.0) # cooldown
        
    with open("results/gpu_unified_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n[DONE] Saved results/gpu_unified_results.json successfully.")

if __name__ == "__main__":
    main()
