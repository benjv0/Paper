#!/usr/bin/env python3
"""
run_cpu_suite.py — Execute CPU benchmarks (static vs dynamic) for:
- 4T (E-cores 4,5,6,7)
- 8T (E-cores 4-11)
- 12T s/8E (cores 4-11 oversubscribed)
- 12T P+E (cores 0-11)
Runs 5 iterations x >=15s with RAPL PKG, frequency, and thermal telemetry.
"""
import json
import time
from run_cpu_scheduler_bench import run_cpu_bench

def main():
    configs = [
        # Static variants
        {"threads": 4,  "cores": "4,5,6,7",                "sched": "static",  "label": "4T (static)"},
        {"threads": 8,  "cores": "4,5,6,7,8,9,10,11",       "sched": "static",  "label": "8T (static)"},
        {"threads": 12, "cores": "4,5,6,7,8,9,10,11",       "sched": "static",  "label": "12T s/8E (static)"},
        {"threads": 12, "cores": "0,1,2,3,4,5,6,7,8,9,10,11","sched": "static",  "label": "12T P+E (static)"},
        # Dynamic variants
        {"threads": 4,  "cores": "4,5,6,7",                "sched": "dynamic", "label": "4T (dynamic)"},
        {"threads": 8,  "cores": "4,5,6,7,8,9,10,11",       "sched": "dynamic", "label": "8T (dynamic)"},
        {"threads": 12, "cores": "4,5,6,7,8,9,10,11",       "sched": "dynamic", "label": "12T s/8E (dynamic)"},
        {"threads": 12, "cores": "0,1,2,3,4,5,6,7,8,9,10,11","sched": "dynamic", "label": "12T P+E (dynamic)"},
    ]

    results = []
    for cfg in configs:
        print(f"\n>>> Running CPU {cfg['label']} C=64 B...")
        res = run_cpu_bench(
            impl="shani",
            sched=cfg["sched"],
            threads=cfg["threads"],
            cores=cfg["cores"],
            chunk_size=64,
            runs=5,
            duration_s=15.0,
            warmup_s=3.0,
            data_file="dummy_1GB.bin"
        )
        res["label"] = cfg["label"]
        results.append(res)
        time.sleep(3.0)

    with open("results/cpu_scheduler_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\n[DONE] Saved results/cpu_scheduler_results.json successfully.")

if __name__ == "__main__":
    main()
