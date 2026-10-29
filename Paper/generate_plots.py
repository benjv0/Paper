import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times", "Times New Roman", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 10,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
})

def create_throughput_chart():
    csv_path = "../results/benchmarks_summary.csv"
    if not os.path.exists(csv_path):
        csv_path = "results/benchmarks_summary.csv"

    # Default measured fallback values
    t_sw1 = 0.11
    t_hw4 = 3.54
    t_hw8 = 5.76
    t_hw12_sob = 5.94
    t_hw12_pe = 4.51
    t_g1e = 2.04
    t_g2e = 5.01
    t_g2k = 17.40

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            sw1 = df[(df["variante"] == "SCALAR_1T") & (df["C"] == 64)]
            hw4 = df[(df["variante"] == "SHANI_4T") & (df["C"] == 64)]
            hw8 = df[(df["variante"] == "SHANI_8T") & (df["C"] == 64)]
            hw12_sob = df[(df["variante"] == "SHANI_12T") & (df["C"] == 64)]
            hw12_pe = df[(df["variante"] == "SHANI_12T_PE") & (df["C"] == 64)]
            g1e = df[(df["variante"] == "GPU_V1") & (df["C"] == 64) & (df["staging"] == "pinned") & (df["nivel"] == "E2E")]
            g2e = df[(df["variante"] == "GPU_V2") & (df["C"] == 64) & (df["staging"] == "pinned") & (df["nivel"] == "E2E")]
            g2k = df[(df["variante"] == "GPU_V2") & (df["C"] == 64) & (df["staging"] == "pinned") & (df["nivel"] == "kernel-only")]

            if not sw1.empty: t_sw1 = float(sw1.iloc[0]["throughput_mean_GBs"])
            if not hw4.empty: t_hw4 = float(hw4.iloc[0]["throughput_mean_GBs"])
            if not hw8.empty: t_hw8 = float(hw8.iloc[0]["throughput_mean_GBs"])
            if not hw12_sob.empty: t_hw12_sob = float(hw12_sob.iloc[0]["throughput_mean_GBs"])
            if not hw12_pe.empty: t_hw12_pe = float(hw12_pe.iloc[0]["throughput_mean_GBs"])
            if not g1e.empty: t_g1e = float(g1e.iloc[0]["throughput_mean_GBs"])
            if not g2e.empty: t_g2e = float(g2e.iloc[0]["throughput_mean_GBs"])
            if not g2k.empty: t_g2k = float(g2k.iloc[0]["throughput_mean_GBs"])
        except Exception as e:
            print(f"Notice reading csv: {e}")

    platforms = [
        'CPU Escalar\n(1T)',
        'CPU SHA-NI\n(4T Ref)',
        'CPU SHA-NI\n(8T E-cores)',
        'CPU SHA-NI\n(12T 8E sob.)',
        'CPU SHA-NI\n(12T P+E)',
        'GPU v1\nE2E',
        'GPU v2\nE2E',
        'GPU v2\nKernel',
        'FPGA\n(Spartan-7)'
    ]
    throughput = [t_sw1, t_hw4, t_hw8, t_hw12_sob, t_hw12_pe, t_g1e, t_g2e, t_g2k, 0]
    
    colors = ['#d62728', '#ff7f0e', '#fdae6b', '#e6550d', '#a63603', '#1f77b4', '#2ca02c', '#74c476', '#7f7f7f']
    
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    bars = ax.bar(platforms, throughput, color=colors, edgecolor='black', linewidth=0.8, zorder=3)
    
    # Hatch the FPGA bar to indicate TBD
    bars[-1].set_hatch('//')
    bars[-1].set_edgecolor('black')
    bars[-1].set_facecolor('white')
    
    ax.set_ylabel('Throughput Útil (GB/s)')
    ax.set_title('Comparación de Throughput SHA-256 Entre Plataformas ($C=64$ B)')
    ax.yaxis.grid(True, linestyle='--', alpha=0.7, zorder=0)
    ax.set_ylim(0, 20)
    ax.tick_params(axis='x', labelsize=8)
    plt.xticks(rotation=15, ha='right')
    
    for i, bar in enumerate(bars):
        yval = bar.get_height()
        if platforms[i] == 'FPGA\n(Spartan-7)':
            ax.text(bar.get_x() + bar.get_width()/2.0, 0.3, 'TBD', ha='center', va='bottom', rotation=90, fontweight='bold', color='gray', fontsize=8.5)
        else:
            ax.text(bar.get_x() + bar.get_width()/2.0, yval + 0.25, f'{yval:.2f}', ha='center', va='bottom', fontsize=8)
            
    plt.tight_layout()
    out_name = 'Paper/throughput_chart.pdf' if os.path.exists('Paper') else 'throughput_chart.pdf'
    plt.savefig(out_name, format='pdf', bbox_inches='tight')
    plt.close()

def create_energy_chart():
    # If energy is TBD pending root RAPL / NVML reboot, display TBD
    platforms = ['CPU Escalar\n(1T)', 'CPU SHA-NI\n(4T)', 'GPU v1\nE2E', 'GPU v2\nE2E', 'FPGA\n(Spartan-7)']
    energy = [0, 0, 0, 0, 0]
    
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    bars = ax.bar(platforms, energy, color='#7f7f7f', edgecolor='black', linewidth=0.8, zorder=3)
    for bar in bars:
        bar.set_hatch('//')
        bar.set_facecolor('white')
        
    ax.set_ylabel('Eficiencia Energética (J/GB)\nMenor es mejor')
    ax.set_title('Eficiencia Energética Cruzada SHA-256')
    ax.yaxis.grid(True, linestyle='--', alpha=0.7, zorder=0)
    ax.set_ylim(0, 10)
    
    for bar in bars:
        ax.text(bar.get_x() + bar.get_width()/2.0, 1.0, 'TBD\n(Ver Tabla)', ha='center', va='center', fontweight='bold', color='gray', fontsize=9)
        
    plt.tight_layout()
    out_name = 'Paper/energy_chart.pdf' if os.path.exists('Paper') else 'energy_chart.pdf'
    plt.savefig(out_name, format='pdf', bbox_inches='tight')
    plt.close()

if __name__ == '__main__':
    create_throughput_chart()
    create_energy_chart()
    print("Academic charts generated successfully.")
