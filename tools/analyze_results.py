#!/usr/bin/env python3
"""
analyze_results.py — Paper Analysis, LaTeX Tables, and Academic Figures
======================================================================
Reads results/benchmarks_summary.csv and generates:
  1. Paper-ready LaTeX tables for CPU, GPU ablation (v1 -> v2), and cross-platform comparison.
  2. Figure 1: Throughput vs Chunk Size C (Kernel-only vs E2E).
  3. Figure 2: Energy Efficiency (J/GB) Comparison across platforms.
"""

import os
import sys
import csv
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times", "Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
})

def format_val(val, decimals=2):
    if pd.isna(val) or val == "N/A":
        return "\\TODO{}"
    try:
        f = float(val)
        return f"{f:.{decimals}f}"
    except Exception:
        return str(val)

def generate_latex_tables(df: pd.DataFrame, out_path: str = "results/latex_tables.tex"):
    lines = []
    lines.append("% Auto-generated LaTeX tables from benchmark results\n")

    # 1. CPU Results Table
    cpu_df = df[df["plataforma"] == "CPU"]
    if not cpu_df.empty:
        lines.append("% ── CPU Results Table ─────────────────────────────")
        lines.append("\\begin{table}[htbp]")
        lines.append("  \\caption{SHA-256 CPU Benchmark Results (Intel Core i7-1255U, 1~GB payload, $C=64$~B)}")
        lines.append("  \\label{tab:cpu}")
        lines.append("  \\centering")
        lines.append("  \\begin{tabular}{lcccc}")
        lines.append("    \\toprule")
        lines.append("    \\textbf{Configuración} & \\textbf{Throughput (GB/s)} & \\textbf{Speedup vs 4T} & \\textbf{Speedup vs 1T} & \\textbf{Energía (J/GB)} \\\\")
        lines.append("    \\midrule")
        for _, r in cpu_df[cpu_df["C"] == 64].iterrows():
            tput_str = f"{r['throughput_mean_GBs']:.2f} $\\pm$ {r['throughput_sd_GBs']:.2f}"
            sp_4t = r.get("speedup_vs_SHANI4T", "\\TODO{}")
            sp_1t = r.get("speedup_vs_escalar1T", "\\TODO{}")
            j_gb = format_val(r.get("J_GB_dispositivo", "N/A"))
            lines.append(f"    {r['variante']:<16} & {tput_str:<22} & {sp_4t:<12} & {sp_1t:<12} & {j_gb} \\\\")
        lines.append("    \\bottomrule")
        lines.append("  \\end{tabular}")
        lines.append("\\end{table}\n")

    # 2. GPU Ablation Table (v1 vs v2)
    gpu_df = df[df["plataforma"] == "GPU"]
    if not gpu_df.empty:
        lines.append("% ── GPU Ablation Table (v1 -> v2) ─────────────────")
        lines.append("\\begin{table}[htbp]")
        lines.append("  \\caption{Ablación Microarquitectónica de GPU: Kernel Base (v1) vs Alta Utilización (v2)}")
        lines.append("  \\label{tab:gpu_ablation}")
        lines.append("  \\centering")
        lines.append("  \\begin{tabular}{llcccc}")
        lines.append("    \\toprule")
        lines.append("    \\textbf{Versión} & \\textbf{Chunk ($C$)} & \\textbf{Staging} & \\textbf{Kernel (GB/s)} & \\textbf{E2E (GB/s)} & \\textbf{Speedup vs 4T} \\\\")
        lines.append("    \\midrule")
        for c in [64, 1024, 4096, 65536, 1048576]:
            for ver in ["GPU_V1", "GPU_V2"]:
                sub_k = gpu_df[(gpu_df["variante"] == ver) & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "kernel-only")]
                sub_e = gpu_df[(gpu_df["variante"] == ver) & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "E2E")]
                if not sub_k.empty and not sub_e.empty:
                    tk = f"{sub_k.iloc[0]['throughput_mean_GBs']:.2f}"
                    te = f"{sub_e.iloc[0]['throughput_mean_GBs']:.2f}"
                    sp = sub_e.iloc[0].get("speedup_vs_SHANI4T", "\\TODO{}")
                    c_label = f"{c//1024} KB" if c >= 1024 else f"{c} B"
                    if c >= 1048576: c_label = "1 MB"
                    lines.append(f"    {ver:<8} & {c_label:<8} & Pinned & {tk:<8} & {te:<8} & {sp} \\\\")
        lines.append("    \\bottomrule")
        lines.append("  \\end{tabular}")
        lines.append("\\end{table}\n")

    content = "\n".join(lines)
    with open(out_path, "w") as f:
        f.write(content)
    print(f"Generated LaTeX tables in '{out_path}'.")

def plot_throughput_vs_c(df: pd.DataFrame, out_path: str = "Paper/throughput_vs_c.pdf"):
    gpu_df = df[df["plataforma"] == "GPU"]
    if gpu_df.empty:
        return

    c_vals = sorted(gpu_df["C"].unique())
    x_labels = [f"{c//1024}K" if (1024 <= c < 1048576) else ("1M" if c >= 1048576 else f"{c}B") for c in c_vals]

    # GPU v2 Kernel-only vs E2E pinned
    v2_k = []
    v2_e = []
    v1_k = []
    v1_e = []

    for c in c_vals:
        s2k = gpu_df[(gpu_df["variante"] == "GPU_V2") & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "kernel-only")]
        s2e = gpu_df[(gpu_df["variante"] == "GPU_V2") & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "E2E")]
        s1k = gpu_df[(gpu_df["variante"] == "GPU_V1") & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "kernel-only")]
        s1e = gpu_df[(gpu_df["variante"] == "GPU_V1") & (gpu_df["C"] == c) & (gpu_df["staging"] == "pinned") & (gpu_df["nivel"] == "E2E")]

        v2_k.append(s2k.iloc[0]["throughput_mean_GBs"] if not s2k.empty else 0)
        v2_e.append(s2e.iloc[0]["throughput_mean_GBs"] if not s2e.empty else 0)
        v1_k.append(s1k.iloc[0]["throughput_mean_GBs"] if not s1k.empty else 0)
        v1_e.append(s1e.iloc[0]["throughput_mean_GBs"] if not s1e.empty else 0)

    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    x = np.arange(len(c_vals))
    width = 0.2

    ax.bar(x - 1.5*width, v1_k, width, label="GPU v1 Kernel", color="#9ecae1", edgecolor="black")
    ax.bar(x - 0.5*width, v1_e, width, label="GPU v1 E2E", color="#3182bd", edgecolor="black")
    ax.bar(x + 0.5*width, v2_k, width, label="GPU v2 Kernel", color="#a1d99b", edgecolor="black")
    ax.bar(x + 1.5*width, v2_e, width, label="GPU v2 E2E", color="#31a354", edgecolor="black")

    # CPU SHA-NI 4T series per C
    cpu_4t_vals = []
    for c in c_vals:
        s_cpu = df[(df["plataforma"] == "CPU") & (df["variante"] == "SHANI_4T") & (df["C"] == c)]
        cpu_4t_vals.append(s_cpu.iloc[0]["throughput_mean_GBs"] if not s_cpu.empty else 0)

    ax.plot(x, cpu_4t_vals, marker='o', markersize=5, linestyle='--', color="#de2d26", linewidth=1.6, label="CPU SHA-NI 4T", zorder=4)

    ax.set_xlabel("Tamaño de Fragmento $C$")
    ax.set_ylabel("Throughput Útil (GB/s)")
    ax.set_title("Throughput de SHA-256 vs Tamaño de Fragmento $C$")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.set_ylim(0, 26)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=8.5)
    ax.grid(True, linestyle=":", alpha=0.6, axis="y")

    plt.tight_layout()
    plt.savefig(out_path, format="pdf", bbox_inches="tight")
    plt.savefig("results/throughput_vs_c.pdf", format="pdf", bbox_inches="tight")
    plt.close()
    print(f"Generated plot '{out_path}'.")

def main():
    csv_file = "results/benchmarks_summary.csv"
    if not os.path.exists(csv_file):
        print(f"File '{csv_file}' not found. Run tools/run_benchmarks.py first.")
        sys.exit(1)

    df = pd.read_csv(csv_file)
    generate_latex_tables(df)
    plot_throughput_vs_c(df)

if __name__ == "__main__":
    main()
