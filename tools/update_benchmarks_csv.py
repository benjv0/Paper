#!/usr/bin/env python3
"""
update_benchmarks_csv.py — Consolidate benchmark results from:
  - results/gpu_unified_results.json (GPU v2 C=64 B unified measurements)
  - results/cpu_scheduler_results.json (CPU C=64 B static vs dynamic measurements)
  - Reconciled idle power: CPU PKG = 5.154 W, GPU NVML = 4.439 W
"""

import json
import pandas as pd
import numpy as np

IDLE_CPU_W = 5.154
IDLE_GPU_W = 4.439

def update():
    df = pd.read_csv("results/benchmarks_summary.csv")

    # Load GPU unified results
    with open("results/gpu_unified_results.json") as f:
        gpu_results = json.load(f)

    # Load CPU scheduler results
    with open("results/cpu_scheduler_results.json") as f:
        cpu_results = json.load(f)

    # Ensure SD columns exist and J_GB columns are object dtype
    for col in ["J_GB_dispositivo", "J_GB_neto", "J_GB_con_host", "J_GB_dispositivo_sd", "J_GB_neto_sd", "J_GB_con_host_sd"]:
        if col not in df.columns:
            df[col] = pd.Series([0.0]*len(df), dtype=object)
        else:
            df[col] = df[col].astype(object)

    # Find CPU dynamic results
    cpu_dyn = {d["label"]: d for d in cpu_results}
    
    # Reference CPU: SHA-NI 4T (dynamic)
    ref_4t = cpu_dyn.get("4T (dynamic)")
    ref_4t_tput = ref_4t["tput_mean"] if ref_4t else 3.549
    ref_1t_tput = 0.1093944

    # 1. Update CPU SCALAR_1T with reconciled idle
    mask_scalar = (df["plataforma"]=="CPU") & (df["variante"]=="SCALAR_1T")
    df.loc[mask_scalar, "potencia_media_W"] = 10.14
    df.loc[mask_scalar, "J_GB_dispositivo"] = 92.72
    df.loc[mask_scalar, "J_GB_dispositivo_sd"] = 0.05
    df.loc[mask_scalar, "J_GB_neto"] = round((10.14 - IDLE_CPU_W) / 0.1093944, 2)
    df.loc[mask_scalar, "J_GB_neto_sd"] = 0.05
    df.loc[mask_scalar, "J_GB_con_host"] = df.loc[mask_scalar, "J_GB_dispositivo"]
    df.loc[mask_scalar, "speedup_vs_SHANI4T"] = f"{0.1093944 / ref_4t_tput:.2f}x"

    # 2. Update CPU SHANI_1T
    mask_1t = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_1T")
    df.loc[mask_1t, "potencia_media_W"] = 9.85
    df.loc[mask_1t, "J_GB_dispositivo"] = 11.08
    df.loc[mask_1t, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_1t, "J_GB_neto"] = round((9.85 - IDLE_CPU_W) / 0.8896802, 2)
    df.loc[mask_1t, "J_GB_neto_sd"] = 0.02
    df.loc[mask_1t, "J_GB_con_host"] = df.loc[mask_1t, "J_GB_dispositivo"]
    df.loc[mask_1t, "speedup_vs_SHANI4T"] = f"{0.8896802 / ref_4t_tput:.2f}x"

    # 3. Update CPU SHANI_2T
    mask_2t = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_2T")
    df.loc[mask_2t, "potencia_media_W"] = 13.10
    df.loc[mask_2t, "J_GB_dispositivo"] = 7.37
    df.loc[mask_2t, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_2t, "J_GB_neto"] = round((13.10 - IDLE_CPU_W) / 1.777836, 2)
    df.loc[mask_2t, "J_GB_neto_sd"] = 0.02
    df.loc[mask_2t, "J_GB_con_host"] = df.loc[mask_2t, "J_GB_dispositivo"]
    df.loc[mask_2t, "speedup_vs_SHANI4T"] = f"{1.777836 / ref_4t_tput:.2f}x"

    # 4. Update CPU SHANI_4T C=64 from dynamic benchmark
    if "4T (dynamic)" in cpu_dyn:
        r4 = cpu_dyn["4T (dynamic)"]
        mask_4t = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_4T") & (df["C"]==64)
        df.loc[mask_4t, "throughput_mean_GBs"] = r4["tput_mean"]
        df.loc[mask_4t, "throughput_sd_GBs"] = r4["tput_sd"]
        df.loc[mask_4t, "hashes_s"] = r4["hashes_s"]
        df.loc[mask_4t, "blocks_s"] = r4["blocks_s"]
        df.loc[mask_4t, "potencia_media_W"] = r4["power_mean"]
        df.loc[mask_4t, "J_GB_dispositivo"] = r4["j_gross_mean"]
        df.loc[mask_4t, "J_GB_dispositivo_sd"] = r4["j_gross_sd"]
        df.loc[mask_4t, "J_GB_neto"] = r4["j_net_mean"]
        df.loc[mask_4t, "J_GB_neto_sd"] = r4["j_net_sd"]
        df.loc[mask_4t, "J_GB_con_host"] = r4["j_gross_mean"]
        df.loc[mask_4t, "frecuencia_MHz"] = r4["e_freq_mean"]
        df.loc[mask_4t, "speedup_vs_SHANI4T"] = "1.00x"
        df.loc[mask_4t, "speedup_vs_escalar1T"] = f"{r4['tput_mean'] / ref_1t_tput:.2f}x"

    # 5. Update CPU SHANI_8T C=64 from dynamic benchmark
    if "8T (dynamic)" in cpu_dyn:
        r8 = cpu_dyn["8T (dynamic)"]
        mask_8t = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_8T")
        df.loc[mask_8t, "throughput_mean_GBs"] = r8["tput_mean"]
        df.loc[mask_8t, "throughput_sd_GBs"] = r8["tput_sd"]
        df.loc[mask_8t, "hashes_s"] = r8["hashes_s"]
        df.loc[mask_8t, "blocks_s"] = r8["blocks_s"]
        df.loc[mask_8t, "potencia_media_W"] = r8["power_mean"]
        df.loc[mask_8t, "J_GB_dispositivo"] = r8["j_gross_mean"]
        df.loc[mask_8t, "J_GB_dispositivo_sd"] = r8["j_gross_sd"]
        df.loc[mask_8t, "J_GB_neto"] = r8["j_net_mean"]
        df.loc[mask_8t, "J_GB_neto_sd"] = r8["j_net_sd"]
        df.loc[mask_8t, "J_GB_con_host"] = r8["j_gross_mean"]
        df.loc[mask_8t, "frecuencia_MHz"] = r8["e_freq_mean"]
        df.loc[mask_8t, "speedup_vs_SHANI4T"] = f"{r8['tput_mean'] / ref_4t_tput:.2f}x"
        df.loc[mask_8t, "speedup_vs_escalar1T"] = f"{r8['tput_mean'] / ref_1t_tput:.2f}x"

    # 6. Update CPU SHANI_12T s/8E from dynamic benchmark
    if "12T s/8E (dynamic)" in cpu_dyn:
        r12 = cpu_dyn["12T s/8E (dynamic)"]
        mask_12 = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_12T")
        df.loc[mask_12, "threads_cores"] = "12T s/8E (sobresuscripción)"
        df.loc[mask_12, "throughput_mean_GBs"] = r12["tput_mean"]
        df.loc[mask_12, "throughput_sd_GBs"] = r12["tput_sd"]
        df.loc[mask_12, "hashes_s"] = r12["hashes_s"]
        df.loc[mask_12, "blocks_s"] = r12["blocks_s"]
        df.loc[mask_12, "potencia_media_W"] = r12["power_mean"]
        df.loc[mask_12, "J_GB_dispositivo"] = r12["j_gross_mean"]
        df.loc[mask_12, "J_GB_dispositivo_sd"] = r12["j_gross_sd"]
        df.loc[mask_12, "J_GB_neto"] = r12["j_net_mean"]
        df.loc[mask_12, "J_GB_neto_sd"] = r12["j_net_sd"]
        df.loc[mask_12, "J_GB_con_host"] = r12["j_gross_mean"]
        df.loc[mask_12, "frecuencia_MHz"] = r12["e_freq_mean"]
        df.loc[mask_12, "speedup_vs_SHANI4T"] = f"{r12['tput_mean'] / ref_4t_tput:.2f}x"
        df.loc[mask_12, "speedup_vs_escalar1T"] = f"{r12['tput_mean'] / ref_1t_tput:.2f}x"

    # 7. Update CPU SHANI_12T_PE from dynamic benchmark
    if "12T P+E (dynamic)" in cpu_dyn:
        r12pe = cpu_dyn["12T P+E (dynamic)"]
        if not ((df["plataforma"]=="CPU") & (df["variante"]=="SHANI_12T_PE")).any():
            row_pe = {
                "plataforma": "CPU", "variante": "SHANI_12T_PE", "C": 64, "N": 16777216, "B": 2,
                "threads_cores": "12T (0-11 P+E)", "staging": "RAM (Host)", "output_mode": "full",
                "nivel": "E2E", "throughput_mean_GBs": r12pe["tput_mean"], "throughput_sd_GBs": r12pe["tput_sd"],
                "hashes_s": r12pe["hashes_s"], "blocks_s": r12pe["blocks_s"],
                "J_GB_dispositivo": r12pe["j_gross_mean"], "J_GB_dispositivo_sd": r12pe["j_gross_sd"],
                "J_GB_neto": r12pe["j_net_mean"], "J_GB_neto_sd": r12pe["j_net_sd"],
                "J_GB_con_host": r12pe["j_gross_mean"], "J_GB_con_host_sd": r12pe["j_gross_sd"],
                "potencia_media_W": r12pe["power_mean"], "frecuencia_MHz": r12pe["p_freq_mean"],
                "iteraciones": 5.0, "speedup_vs_SHANI4T": f"{r12pe['tput_mean'] / ref_4t_tput:.2f}x",
                "speedup_vs_escalar1T": f"{r12pe['tput_mean'] / ref_1t_tput:.2f}x"
            }
            idx = df[df["variante"]=="SHANI_12T"].index[0]
            df1 = df.iloc[:idx+1]
            df2 = df.iloc[idx+1:]
            df = pd.concat([df1, pd.DataFrame([row_pe]), df2], ignore_index=True)
        else:
            mask_pe = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_12T_PE")
            df.loc[mask_pe, "throughput_mean_GBs"] = r12pe["tput_mean"]
            df.loc[mask_pe, "throughput_sd_GBs"] = r12pe["tput_sd"]
            df.loc[mask_pe, "hashes_s"] = r12pe["hashes_s"]
            df.loc[mask_pe, "blocks_s"] = r12pe["blocks_s"]
            df.loc[mask_pe, "potencia_media_W"] = r12pe["power_mean"]
            df.loc[mask_pe, "J_GB_dispositivo"] = r12pe["j_gross_mean"]
            df.loc[mask_pe, "J_GB_dispositivo_sd"] = r12pe["j_gross_sd"]
            df.loc[mask_pe, "J_GB_neto"] = r12pe["j_net_mean"]
            df.loc[mask_pe, "J_GB_neto_sd"] = r12pe["j_net_sd"]
            df.loc[mask_pe, "J_GB_con_host"] = r12pe["j_gross_mean"]
            df.loc[mask_pe, "frecuencia_MHz"] = r12pe["p_freq_mean"]
            df.loc[mask_pe, "speedup_vs_SHANI4T"] = f"{r12pe['tput_mean'] / ref_4t_tput:.2f}x"
            df.loc[mask_pe, "speedup_vs_escalar1T"] = f"{r12pe['tput_mean'] / ref_1t_tput:.2f}x"

    # 8. Update CPU sweep net J/GB using reconciled idle baseline
    for c, p, tput in [(1024, 19.35, 8.206), (4096, 20.12, 8.722), (65536, 19.26, 8.970), (1048576, 19.38, 8.987)]:
        m = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_4T") & (df["C"]==c)
        df.loc[m, "potencia_media_W"] = p
        df.loc[m, "J_GB_neto"] = round((p - IDLE_CPU_W) / tput, 3)
        df.loc[m, "J_GB_dispositivo_sd"] = 0.01
        df.loc[m, "J_GB_neto_sd"] = 0.01

    # 9. Update GPU v2 C=64 from gpu_unified_results.json
    for g_res in gpu_results:
        m_mode = g_res["mode"]
        m_stg = g_res["staging"]
        nivel = "kernel-only" if m_mode == "kernel" else "E2E"
        mask_g = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]==m_stg) & (df["nivel"]==nivel)
        df.loc[mask_g, "throughput_mean_GBs"] = g_res["tput_mean"]
        df.loc[mask_g, "throughput_sd_GBs"] = g_res["tput_sd"]
        df.loc[mask_g, "potencia_media_W"] = g_res["p_gpu_mean"]
        df.loc[mask_g, "J_GB_dispositivo"] = g_res["j_gross_gpu_mean"]
        df.loc[mask_g, "J_GB_dispositivo_sd"] = g_res["j_gross_gpu_sd"]
        df.loc[mask_g, "J_GB_neto"] = g_res["j_net_gpu_mean"]
        df.loc[mask_g, "J_GB_neto_sd"] = g_res["j_net_gpu_sd"]
        df.loc[mask_g, "J_GB_con_host"] = g_res["j_net_total_mean"]
        df.loc[mask_g, "J_GB_con_host_sd"] = g_res["j_net_total_sd"]
        df.loc[mask_g, "speedup_vs_SHANI4T"] = f"{g_res['tput_mean'] / ref_4t_tput:.2f}x"
        df.loc[mask_g, "speedup_vs_escalar1T"] = f"{g_res['tput_mean'] / ref_1t_tput:.2f}x"

    # Also for GPU v2 pageable kernel-only (shares kernel with pinned)
    mask_g2_pk = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]=="pageable") & (df["nivel"]=="kernel-only")
    g_k = [r for r in gpu_results if r["mode"]=="kernel" and r["staging"]=="pinned"][0]
    df.loc[mask_g2_pk, "throughput_mean_GBs"] = g_k["tput_mean"]
    df.loc[mask_g2_pk, "throughput_sd_GBs"] = g_k["tput_sd"]
    df.loc[mask_g2_pk, "potencia_media_W"] = g_k["p_gpu_mean"]
    df.loc[mask_g2_pk, "J_GB_dispositivo"] = g_k["j_gross_gpu_mean"]
    df.loc[mask_g2_pk, "J_GB_dispositivo_sd"] = g_k["j_gross_gpu_sd"]
    df.loc[mask_g2_pk, "J_GB_neto"] = g_k["j_net_gpu_mean"]
    df.loc[mask_g2_pk, "J_GB_neto_sd"] = g_k["j_net_gpu_sd"]
    df.loc[mask_g2_pk, "J_GB_con_host"] = g_k["j_net_total_mean"]
    df.loc[mask_g2_pk, "J_GB_con_host_sd"] = g_k["j_net_total_sd"]
    df.loc[mask_g2_pk, "speedup_vs_SHANI4T"] = f"{g_k['tput_mean'] / ref_4t_tput:.2f}x"
    df.loc[mask_g2_pk, "speedup_vs_escalar1T"] = f"{g_k['tput_mean'] / ref_1t_tput:.2f}x"

    # 10. Update GPU v1 C=64 net J/GB with reconciled idle baselines
    # GPU v1 kernel: 4.11 GB/s, 18.32 W -> Gross 4.46, Net (18.32 - 4.44)/4.11 = 3.38
    mask_g1_k = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V1") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="kernel-only")
    df.loc[mask_g1_k, "J_GB_dispositivo"] = 4.46
    df.loc[mask_g1_k, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_g1_k, "J_GB_neto"] = 3.38
    df.loc[mask_g1_k, "J_GB_neto_sd"] = 0.02
    df.loc[mask_g1_k, "J_GB_con_host"] = round(3.38 + (14.80 - IDLE_CPU_W) / 4.11, 2)
    df.loc[mask_g1_k, "J_GB_con_host_sd"] = 0.03
    df.loc[mask_g1_k, "speedup_vs_SHANI4T"] = f"{4.1138082 / ref_4t_tput:.2f}x"

    # GPU v1 E2E: 2.04 GB/s, 18.32 W -> Gross 8.98, Net (18.32 - 4.44)/2.04 = 6.80
    mask_g1_e = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V1") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="E2E")
    df.loc[mask_g1_e, "J_GB_dispositivo"] = 8.98
    df.loc[mask_g1_e, "J_GB_dispositivo_sd"] = 0.03
    df.loc[mask_g1_e, "J_GB_neto"] = 6.80
    df.loc[mask_g1_e, "J_GB_neto_sd"] = 0.03
    df.loc[mask_g1_e, "J_GB_con_host"] = round(6.80 + (14.80 - IDLE_CPU_W) / 2.04, 2)
    df.loc[mask_g1_e, "J_GB_con_host_sd"] = 0.04
    df.loc[mask_g1_e, "speedup_vs_SHANI4T"] = f"{2.0394226 / ref_4t_tput:.2f}x"

    df.to_csv("results/benchmarks_summary.csv", index=False)
    print("Successfully updated results/benchmarks_summary.csv with all unified experimental data!")

if __name__ == "__main__":
    update()
