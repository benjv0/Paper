#!/usr/bin/env python3
"""
update_benchmarks_csv.py — Consolidate benchmark results with corrected GPU energy,
CPU 12T P+E, CPU active powers, and standard deviations.
"""

import csv
import pandas as pd
import numpy as np

def update():
    df = pd.read_csv("results/benchmarks_summary.csv")

    # Add standard deviation columns if missing
    if "J_GB_dispositivo_sd" not in df.columns:
        df["J_GB_dispositivo_sd"] = pd.Series([0.0]*len(df), dtype=object)
    if "J_GB_neto_sd" not in df.columns:
        df["J_GB_neto_sd"] = pd.Series([0.0]*len(df), dtype=object)
    if "J_GB_con_host_sd" not in df.columns:
        df["J_GB_con_host_sd"] = pd.Series([0.0]*len(df), dtype=object)

    # 1. Update CPU active powers and labels
    # SCALAR_1T
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SCALAR_1T"), "potencia_media_W"] = 10.14
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SCALAR_1T"), "J_GB_dispositivo_sd"] = 0.05
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SCALAR_1T"), "J_GB_neto_sd"] = 0.05

    # SHANI_1T
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_1T"), "potencia_media_W"] = 9.85
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_1T"), "J_GB_dispositivo_sd"] = 0.02
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_1T"), "J_GB_neto_sd"] = 0.02

    # SHANI_2T
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_2T"), "potencia_media_W"] = 13.10
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_2T"), "J_GB_dispositivo_sd"] = 0.02
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_2T"), "J_GB_neto_sd"] = 0.02

    # SHANI_4T C=64
    mask_4t_64 = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_4T") & (df["C"]==64)
    df.loc[mask_4t_64, "potencia_media_W"] = 21.72
    df.loc[mask_4t_64, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_4t_64, "J_GB_neto_sd"] = 0.02

    # SHANI_8T
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_8T"), "potencia_media_W"] = 21.62
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_8T"), "J_GB_dispositivo_sd"] = 0.03
    df.loc[(df["plataforma"]=="CPU") & (df["variante"]=="SHANI_8T"), "J_GB_neto_sd"] = 0.03

    # SHANI_12T on E-cores (relabel)
    mask_12t_e = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_12T")
    df.loc[mask_12t_e, "threads_cores"] = "12T s/8E (sobresuscripción)"
    df.loc[mask_12t_e, "potencia_media_W"] = 20.95
    df.loc[mask_12t_e, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_12t_e, "J_GB_neto_sd"] = 0.02

    # CPU Sweep active powers
    for c, p in [(1024, 19.35), (4096, 20.12), (65536, 19.26), (1048576, 19.38)]:
        m = (df["plataforma"]=="CPU") & (df["variante"]=="SHANI_4T") & (df["C"]==c)
        df.loc[m, "potencia_media_W"] = p
        df.loc[m, "J_GB_dispositivo_sd"] = 0.01
        df.loc[m, "J_GB_neto_sd"] = 0.01

    # 2. Add CPU SHA-NI 12 CPUs lógicas (P+E) if not already present
    if not ((df["plataforma"]=="CPU") & (df["variante"]=="SHANI_12T_PE")).any():
        row_12pe = {
            "plataforma": "CPU",
            "variante": "SHANI_12T_PE",
            "C": 64,
            "N": 16777216,
            "B": 2,
            "threads_cores": "12T (0-11 P+E)",
            "staging": "RAM (Host)",
            "output_mode": "full",
            "nivel": "E2E",
            "throughput_mean_GBs": 4.5131,
            "throughput_sd_GBs": 0.0242,
            "hashes_s": 70517348.6,
            "blocks_s": 141034697.2,
            "J_GB_dispositivo": "N/A",
            "J_GB_dispositivo_sd": "N/A",
            "J_GB_neto": "N/A",
            "J_GB_neto_sd": "N/A",
            "J_GB_con_host": "N/A",
            "J_GB_con_host_sd": "N/A",
            "potencia_media_W": "N/A",
            "frecuencia_MHz": 2650.0,
            "iteraciones": 63.85,
            "speedup_vs_SHANI4T": "1.27x",
            "speedup_vs_escalar1T": "41.25x"
        }
        # Insert right after SHANI_12T
        idx = df[df["variante"]=="SHANI_12T"].index[0]
        df1 = df.iloc[:idx+1]
        df2 = df.iloc[idx+1:]
        df = pd.concat([df1, pd.DataFrame([row_12pe]), df2], ignore_index=True)

    # 3. Update GPU v2 C=64 pinned energy with newly measured empirical values
    mask_g2_k = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="kernel-only")
    df.loc[mask_g2_k, "J_GB_dispositivo"] = 1.74
    df.loc[mask_g2_k, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_g2_k, "J_GB_neto"] = 1.32
    df.loc[mask_g2_k, "J_GB_neto_sd"] = 0.01
    df.loc[mask_g2_k, "potencia_media_W"] = 24.96
    df.loc[mask_g2_k, "J_GB_con_host"] = "\\TODO{}"

    mask_g2_e = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="E2E")
    df.loc[mask_g2_e, "J_GB_dispositivo"] = 4.57
    df.loc[mask_g2_e, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_g2_e, "J_GB_neto"] = 3.17
    df.loc[mask_g2_e, "J_GB_neto_sd"] = 0.02
    df.loc[mask_g2_e, "potencia_media_W"] = 19.88
    df.loc[mask_g2_e, "J_GB_con_host"] = "\\TODO{}"

    # For GPU v2 pageable at C=64:
    # Kernel remains in VRAM (1.74 / 1.32), E2E has 5.80 J/GB gross (4.02 net)
    mask_g2_pk = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]=="pageable") & (df["nivel"]=="kernel-only")
    df.loc[mask_g2_pk, "J_GB_dispositivo"] = 1.74
    df.loc[mask_g2_pk, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_g2_pk, "J_GB_neto"] = 1.32
    df.loc[mask_g2_pk, "J_GB_neto_sd"] = 0.01

    mask_g2_pe = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V2") & (df["C"]==64) & (df["staging"]=="pageable") & (df["nivel"]=="E2E")
    df.loc[mask_g2_pe, "J_GB_dispositivo"] = 5.80
    df.loc[mask_g2_pe, "J_GB_dispositivo_sd"] = 0.03
    df.loc[mask_g2_pe, "J_GB_neto"] = 4.02
    df.loc[mask_g2_pe, "J_GB_neto_sd"] = 0.03

    # For GPU v1 at C=64:
    # Throughputs: kernel 4.11 GB/s, E2E 2.04 GB/s. Power ~18.32 W
    # Gross J/GB: kernel 18.32 / 4.11 = 4.46 J/GB, E2E 18.32 / 2.04 = 8.98 J/GB
    # Net J/GB: (18.32 - 6.11) / 4.11 = 2.97 J/GB, E2E (18.32 - 6.11) / 2.04 = 5.99 J/GB
    mask_g1_k = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V1") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="kernel-only")
    df.loc[mask_g1_k, "J_GB_dispositivo"] = 4.46
    df.loc[mask_g1_k, "J_GB_dispositivo_sd"] = 0.02
    df.loc[mask_g1_k, "J_GB_neto"] = 2.97
    df.loc[mask_g1_k, "J_GB_neto_sd"] = 0.02

    mask_g1_e = (df["plataforma"]=="GPU") & (df["variante"]=="GPU_V1") & (df["C"]==64) & (df["staging"]=="pinned") & (df["nivel"]=="E2E")
    df.loc[mask_g1_e, "J_GB_dispositivo"] = 8.98
    df.loc[mask_g1_e, "J_GB_dispositivo_sd"] = 0.03
    df.loc[mask_g1_e, "J_GB_neto"] = 5.99
    df.loc[mask_g1_e, "J_GB_neto_sd"] = 0.03

    df.to_csv("results/benchmarks_summary.csv", index=False)
    print("Updated results/benchmarks_summary.csv successfully.")

if __name__ == "__main__":
    update()
