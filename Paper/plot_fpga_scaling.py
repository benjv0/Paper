#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_fpga_scaling.py - Figura de escalado multinucleo FPGA (SP701, xc7s100)

Lee FPGA/resumen_escalado.csv (fuente principal de la FPGA) y
results/benchmarks_summary.csv (referencias CPU/GPU) y genera
Paper/fpga_scaling.pdf, de una columna IEEE, con dos paneles:
  (a) throughput util [GB/s] vs numero de nucleos N (eje log), con las
      referencias GPU v2 kernel-only y CPU SHA-NI 12 CPUs (P+E);
  (b) energia por GB [J/GB] neta (solo dinamica) y bruta (dinamica +
      estatica del chip) vs N; los puntos N = 16 y 24 son extrapolados
      (marcador hueco + barra de rango min/max de los dos metodos).

Mismo estilo que tools/analyze_results.py (Times, 10 pt).
Uso:  python3 Paper/plot_fpga_scaling.py   (desde la raiz o desde Paper/)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times", "Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 7.5,
})

# Colores coherentes con throughput_vs_c.pdf:
#   GPU v2 kernel  -> verde  #31a354
#   CPU 12 CPUs P+E -> purpura #984ea3 (paleta validada CVD)
#   FPGA (nueva serie) -> azul #3182bd
C_FPGA = "#3182bd"
C_GPU = "#31a354"
C_CPU = "#984ea3"


def find_root():
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.dirname(here), here, os.getcwd()):
        if os.path.exists(os.path.join(cand, "FPGA", "resumen_escalado.csv")):
            return cand
    sys.exit("No encuentro FPGA/resumen_escalado.csv")


def main():
    root = find_root()
    fpga = pd.read_csv(os.path.join(root, "FPGA", "resumen_escalado.csv"), comment="#")
    bench = pd.read_csv(os.path.join(root, "results", "benchmarks_summary.csv"))

    # Referencias CPU/GPU (C = 64 B) tomadas del CSV consolidado
    gpu = bench[(bench["variante"] == "GPU_V2") & (bench["C"] == 64)
                & (bench["staging"] == "pinned") & (bench["nivel"] == "kernel-only")].iloc[0]
    cpu = bench[(bench["variante"] == "SHANI_12T_PE") & (bench["C"] == 64)].iloc[0]
    gpu_tput, gpu_net, gpu_gross = (float(gpu["throughput_mean_GBs"]),
                                    float(gpu["J_GB_neto"]), float(gpu["J_GB_dispositivo"]))
    cpu_tput, cpu_net, cpu_gross = (float(cpu["throughput_mean_GBs"]),
                                    float(cpu["J_GB_neto"]), float(cpu["J_GB_dispositivo"]))

    N = fpga["N"].to_numpy()
    meas = fpga["Pdyn_metodo"].str.strip().eq("SAIF").to_numpy()
    extr = ~meas
    tput = fpga["GB_s"].to_numpy()
    jnet = fpga["J_GB_neto"].to_numpy()
    jgross = fpga["J_GB_bruto"].to_numpy()
    # Rango de la extrapolacion: bruto desde el CSV; neto = Pdyn_min/max / GB/s
    jgross_lo = jgross - fpga["J_GB_bruto_min"].to_numpy()
    jgross_hi = fpga["J_GB_bruto_max"].to_numpy() - jgross
    jnet_lo = jnet - fpga["Pdyn_min_W"].to_numpy() / tput
    jnet_hi = fpga["Pdyn_max_W"].to_numpy() / tput - jnet

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(3.5, 4.6), sharex=True,
                                   gridspec_kw={"hspace": 0.12})

    # ── (a) Throughput ───────────────────────────────────────────────
    ax1.set_yscale("log")
    ax1.axhline(gpu_tput, color=C_GPU, linestyle="--", linewidth=1.2, zorder=2)
    ax1.axhline(cpu_tput, color=C_CPU, linestyle="-.", linewidth=1.2, zorder=2)
    ax1.text(24.6, gpu_tput, f"GPU v2 kernel-only {gpu_tput:.2f}", color=C_GPU,
             fontsize=7.5, ha="right", va="bottom")
    ax1.text(24.6, cpu_tput, f"CPU 12 CPUs (P+E) {cpu_tput:.2f}", color=C_CPU,
             fontsize=7.5, ha="right", va="bottom")
    ax1.plot(N, tput, color=C_FPGA, linewidth=1.4, zorder=3)
    ax1.plot(N, tput, linestyle="None", marker="o", markersize=5.5,
             markerfacecolor=C_FPGA, markeredgecolor=C_FPGA, zorder=4)
    for n, t in zip(N, tput):
        ax1.annotate(f"{t:.3f}", (n, t), textcoords="offset points",
                     xytext=(0, -11), ha="center", fontsize=7, color="#222222")
    ax1.set_ylim(0.025, 40)
    ax1.set_ylabel("Throughput útil (GB/s)")
    ax1.grid(True, linestyle=":", alpha=0.6, axis="y", which="major")
    ax1.text(0.02, 0.96, "(a)", transform=ax1.transAxes, va="top", fontsize=9)

    # ── (b) Energía por GB ───────────────────────────────────────────
    ax2.axhline(gpu_net, color=C_GPU, linestyle="--", linewidth=1.2, zorder=2)
    ax2.axhline(gpu_gross, color=C_GPU, linestyle=":", linewidth=1.2, zorder=2)
    ax2.axhline(cpu_net, color=C_CPU, linestyle="-.", linewidth=1.2, zorder=2)
    ax2.axhline(cpu_gross, color=C_CPU, linestyle=":", linewidth=1.2, zorder=2)
    ax2.annotate(f"GPU kernel neto {gpu_net:.2f}", (24.6, gpu_net), textcoords="offset points",
                 xytext=(0, -3), color=C_GPU, fontsize=7, ha="right", va="top")
    ax2.text(24.6, gpu_gross, f"GPU kernel bruto {gpu_gross:.2f}", color=C_GPU,
             fontsize=7, ha="right", va="bottom")
    ax2.text(24.6, cpu_net, f"CPU 12 CPUs neto {cpu_net:.2f}", color=C_CPU,
             fontsize=7, ha="right", va="bottom")
    ax2.text(24.6, cpu_gross, f"CPU 12 CPUs bruto {cpu_gross:.2f}", color=C_CPU,
             fontsize=7, ha="right", va="bottom")

    ax2.plot(N, jgross, color=C_FPGA, linewidth=1.4, linestyle="-", zorder=3)
    ax2.plot(N, jnet, color=C_FPGA, linewidth=1.4, linestyle="--", zorder=3)
    kw = dict(elinewidth=0.9, ecolor="#222222", capsize=2.5, capthick=0.9, zorder=4)
    # Medidos (SAIF): marcadores llenos
    ax2.plot(N[meas], jgross[meas], linestyle="None", marker="s", markersize=5.5,
             markerfacecolor=C_FPGA, markeredgecolor=C_FPGA, zorder=5)
    ax2.plot(N[meas], jnet[meas], linestyle="None", marker="o", markersize=5.5,
             markerfacecolor=C_FPGA, markeredgecolor=C_FPGA, zorder=5)
    # Extrapolados: marcadores huecos + rango min/max
    ax2.errorbar(N[extr], jgross[extr], yerr=[jgross_lo[extr], jgross_hi[extr]],
                 linestyle="None", marker="s", markersize=5.5,
                 markerfacecolor="white", markeredgecolor=C_FPGA, markeredgewidth=1.3, **kw)
    ax2.errorbar(N[extr], jnet[extr], yerr=[jnet_lo[extr], jnet_hi[extr]],
                 linestyle="None", marker="o", markersize=5.5,
                 markerfacecolor="white", markeredgecolor=C_FPGA, markeredgewidth=1.3, **kw)
    ax2.annotate(f"{jgross[0]:.2f}", (N[0], jgross[0]), textcoords="offset points",
                 xytext=(8, 0), ha="left", va="center", fontsize=7, color="#222222")
    ax2.annotate(f"{jnet[-1]:.2f}", (N[-1], jnet[-1]), textcoords="offset points",
                 xytext=(0, -12), ha="center", fontsize=7, color="#222222")
    ax2.annotate(f"{jgross[-1]:.2f}", (N[-1], jgross[-1]), textcoords="offset points",
                 xytext=(0, 7), ha="center", fontsize=7, color="#222222")

    ax2.set_ylim(0, 5.6)
    ax2.set_xlim(-0.5, 25.5)
    ax2.set_xticks([1, 4, 8, 16, 24])
    ax2.set_xlabel("Número de núcleos SHA-256, $N$")
    ax2.set_ylabel("Energía (J/GB)")
    ax2.grid(True, linestyle=":", alpha=0.6, axis="y")
    ax2.text(0.02, 0.96, "(b)", transform=ax2.transAxes, va="top", fontsize=9)

    handles = [
        Line2D([], [], color=C_FPGA, linestyle="-", marker="s", markersize=5,
               markerfacecolor=C_FPGA, label="FPGA bruto (dinámica + estática)"),
        Line2D([], [], color=C_FPGA, linestyle="--", marker="o", markersize=5,
               markerfacecolor=C_FPGA, label="FPGA neto (dinámica)"),
        Line2D([], [], color=C_FPGA, linestyle="None", marker="o", markersize=5,
               markerfacecolor="white", markeredgewidth=1.3,
               label="Extrapolado (rango de 2 métodos)"),
    ]
    ax2.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 1.0),
               frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=7)

    for ax in (ax1, ax2):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    out = os.path.join(root, "Paper", "fpga_scaling.pdf")
    plt.savefig(out, format="pdf", bbox_inches="tight")
    plt.close()
    print("Figura escrita en", out)
    print("Referencias: GPU kernel %.2f GB/s, %.2f/%.2f J/GB; CPU 12 P+E %.2f GB/s, %.2f/%.2f J/GB"
          % (gpu_tput, gpu_net, gpu_gross, cpu_tput, cpu_net, cpu_gross))


if __name__ == "__main__":
    main()
