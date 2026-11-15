#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_results_summary.py - Figuras resumen de resultados (C = 64 B)

Lee results/benchmarks_summary.csv y FPGA/resumen_escalado.csv y genera:
  Paper/cpu_scaling.pdf          escalado de CPU: (a) throughput, (b) J/GB neto
  Paper/platform_comparison.pdf  comparación cruzada: (a) throughput, (b) J/GB neto

Mismo estilo y colores que plot_fpga_scaling.py (CPU púrpura, GPU verde, FPGA azul).
Uso:  python3 Paper/plot_results_summary.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import pandas as pd

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times", "Times New Roman", "DejaVu Serif"],
    "font.size": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "hatch.linewidth": 0.6,
})
C_FPGA, C_GPU, C_CPU, C_GREY = "#3182bd", "#31a354", "#984ea3", "#9a9a9a"
INK = "#222222"


def find_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.dirname(here), here, os.getcwd()):
        if os.path.exists(os.path.join(cand, "results", "benchmarks_summary.csv")):
            return cand
    sys.exit("No encuentro results/benchmarks_summary.csv")


def clean(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def cpu_row(b, var):
    return b[(b["variante"] == var) & (b["C"] == 64)].iloc[0]


def gpu_row(b, nivel):
    return b[(b["variante"] == "GPU_V2") & (b["C"] == 64) & (b["staging"] == "pinned")
             & (b["nivel"] == nivel)].iloc[0]


def fig_cpu(root, b):
    cfgs = [("SCALAR_1T", "Escalar\n1T"), ("SHANI_1T", "SHA-NI\n1T"), ("SHANI_4T", "SHA-NI\n4T"),
            ("SHANI_8T", "SHA-NI\n8T"), ("SHANI_12T_PE", "SHA-NI\n12 (P+E)")]
    rows = [cpu_row(b, v) for v, _ in cfgs]
    tput = [float(r["throughput_mean_GBs"]) for r in rows]
    sd = [float(r["throughput_sd_GBs"]) for r in rows]
    jnet = [float(r["J_GB_neto"]) for r in rows]
    labels = [l for _, l in cfgs]
    colors = [C_GREY] + [C_CPU] * 4
    x = range(len(cfgs))

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(3.5, 3.9), sharex=True,
                                 gridspec_kw={"hspace": 0.15})
    a1.bar(x, tput, yerr=sd, color=colors, width=0.62, capsize=2,
           error_kw={"elinewidth": 0.8, "ecolor": INK}, zorder=3)
    for i, t in enumerate(tput):
        a1.text(i, t + 0.15, f"{t:.2f}", ha="center", va="bottom", fontsize=7.5, color=INK)
    a1.set_ylabel("Throughput (GB/s)")
    a1.set_ylim(0, 7)
    a1.grid(True, axis="y", linestyle=":", alpha=0.6, zorder=0)
    a1.text(0.02, 0.95, "(a)", transform=a1.transAxes, va="top")

    a2.set_yscale("log")
    a2.vlines(list(x), 1, jnet, color=colors, linewidth=1.6, zorder=3)
    a2.scatter(list(x), jnet, color=colors, s=34, zorder=4)
    for i, j in enumerate(jnet):
        a2.text(i + 0.12, j * 1.08, f"{j:.2f}", ha="left", va="bottom", fontsize=7.5, color=INK)
    a2.set_ylim(1, 120)
    a2.set_ylabel("Energía neta (J/GB)")
    a2.set_xticks(list(x))
    a2.set_xticklabels(labels)
    a2.set_xlim(-0.5, len(cfgs) - 0.35)
    a2.grid(True, axis="y", linestyle=":", alpha=0.6, zorder=0)
    a2.text(0.02, 0.95, "(b)", transform=a2.transAxes, va="top")
    for a in (a1, a2):
        clean(a)
    out = os.path.join(root, "Paper", "cpu_scaling.pdf")
    plt.savefig(out, format="pdf", bbox_inches="tight")
    plt.close()
    print("Figura escrita en", out)


def fig_platforms(root, b, f):
    c4, c12 = cpu_row(b, "SHANI_4T"), cpu_row(b, "SHANI_12T_PE")
    ge, gk = gpu_row(b, "E2E"), gpu_row(b, "kernel-only")
    f1, f24 = f[f["N"] == 1].iloc[0], f[f["N"] == 24].iloc[0]
    # (etiqueta, color, throughput, J/GB neto dispositivo, J/GB neto +host, estimado)
    data = [
        ("CPU 4T (ref.)", C_CPU, float(c4["throughput_mean_GBs"]), float(c4["J_GB_neto"]), None, False),
        ("CPU 12 (P+E)", C_CPU, float(c12["throughput_mean_GBs"]), float(c12["J_GB_neto"]), None, False),
        ("GPU v2 E2E", C_GPU, float(ge["throughput_mean_GBs"]), float(ge["J_GB_neto"]), float(ge["J_GB_con_host"]), False),
        ("GPU v2 kernel", C_GPU, float(gk["throughput_mean_GBs"]), float(gk["J_GB_neto"]), float(gk["J_GB_con_host"]), False),
        ("FPGA 1 núcleo", C_FPGA, float(f1["GB_s"]), float(f1["J_GB_neto"]), None, True),
        ("FPGA 24 núcleos", C_FPGA, float(f24["GB_s"]), float(f24["J_GB_neto"]), None, True),
    ]
    y = list(range(len(data)))[::-1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(3.5, 2.5), sharey=True,
                                 gridspec_kw={"wspace": 0.08})
    # (a) throughput, eje log: puntos con tallo
    a1.set_xscale("log")
    for yi, (lab, col, t, jd, jh, est) in zip(y, data):
        a1.hlines(yi, 0.02, t, color=col, linewidth=1.6, zorder=3)
        a1.scatter([t], [yi], s=34, color=col, zorder=4)
        a1.text(t * 1.6, yi, f"{t:.2f}" if t >= 1 else f"{t:.3f}", va="center", fontsize=7, color=INK)
    a1.set_xlim(0.02, 300)
    a1.set_yticks(y)
    a1.set_yticklabels([d[0] for d in data])
    a1.set_xlabel("Throughput (GB/s)")
    a1.set_title("(a)", fontsize=9, loc="left", pad=3)
    a1.grid(True, axis="x", linestyle=":", alpha=0.6, zorder=0)
    # (b) energía neta: barra del dispositivo + extensión del anfitrión
    for yi, (lab, col, t, jd, jh, est) in zip(y, data):
        a2.barh(yi, jd, height=0.6, color=col if not est else "white", edgecolor=col,
                hatch="////" if est else None, linewidth=1.0, zorder=3)
        end = jd
        if jh is not None:
            a2.barh(yi, jh - jd, left=jd, height=0.6, color="white", edgecolor=col,
                    linewidth=1.0, zorder=3)
            end = jh
        txt = f"{jd:.2f}" + (f" / {jh:.2f}" if jh is not None else "")
        a2.text(end + 0.12, yi, txt, va="center", fontsize=7, color=INK)
    a2.set_xlim(0, 8.2)
    a2.set_xlabel("Energía neta (J/GB)")
    a2.set_title("(b)", fontsize=9, loc="left", pad=3)
    a2.grid(True, axis="x", linestyle=":", alpha=0.6, zorder=0)
    a2.tick_params(axis="y", length=0)
    for a in (a1, a2):
        clean(a)
    handles = [Patch(facecolor="#555555", edgecolor="#555555", label="dispositivo (medido)"),
               Patch(facecolor="white", edgecolor="#555555", label="+ anfitrión"),
               Patch(facecolor="white", edgecolor="#555555", hatch="////", label="estimado (Vivado)")]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=6.8, frameon=False,
               bbox_to_anchor=(0.5, -0.2), handlelength=1.4, columnspacing=1.0)
    out = os.path.join(root, "Paper", "platform_comparison.pdf")
    plt.savefig(out, format="pdf", bbox_inches="tight")
    plt.close()
    print("Figura escrita en", out)


if __name__ == "__main__":
    root = find_root()
    bench = pd.read_csv(os.path.join(root, "results", "benchmarks_summary.csv"))
    fpga = pd.read_csv(os.path.join(root, "FPGA", "resumen_escalado.csv"), comment="#")
    fig_cpu(root, bench)
    fig_platforms(root, bench, fpga)
