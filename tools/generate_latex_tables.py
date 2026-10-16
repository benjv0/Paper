#!/usr/bin/env python3
"""
generate_latex_tables.py — Generate all LaTeX tables for IEEE paper from CSV data.
==================================================================================
Reads results/benchmarks_summary.csv and produces:
  - Individual table files in Paper/:
      * tab_cpu_results.tex
      * tab_cpu_sweep.tex
      * tab_gpu_ablation.tex
      * tab_gpu_staging.tex
      * tab_comparison.tex
  - Paper/gen_tables.tex (combined file)

All tables use \\resizebox{\\columnwidth}{!}{...} to strictly obey IEEEtran 3.5 in column width.
"""

import csv
import math
import sys
import os

CSV_PATH = "results/benchmarks_summary.csv"
PAPER_DIR = "Paper"

def load_csv():
    with open(CSV_PATH) as f:
        return list(csv.DictReader(f))

def fmt(val, decimals=2):
    """Format a numeric value, returning \\TODO{} for N/A."""
    if val is None or str(val).startswith("N/A") or val == "":
        return "\\TODO{}"
    try:
        v = float(val)
        return f"{v:.{decimals}f}"
    except ValueError:
        return str(val)

def fmt_throughput(mean_s, sd_s, decimals=2):
    """Format throughput as mean ± sd."""
    try:
        m = float(mean_s)
        s = float(sd_s)
        return f"{m:.{decimals}f} $\\pm$ {s:.{decimals}f}"
    except (ValueError, TypeError):
        return "\\TODO{}"

def fmt_hashes(val):
    """Format hashes/s in millions."""
    try:
        v = float(val)
        return f"{v/1e6:.2f}"
    except (ValueError, TypeError):
        return "\\TODO{}"

def c_label(c_val):
    c = int(c_val)
    if c < 1024:
        return f"{c}~B"
    elif c < 1048576:
        return f"{c // 1024}~KB"
    else:
        return f"{c // 1048576}~MB"

def find_row(rows, **kwargs):
    """Find a single row matching all kwargs."""
    for r in rows:
        if all(str(r.get(k, "")) == str(v) for k, v in kwargs.items()):
            return r
    return None

def find_rows(rows, **kwargs):
    """Find all rows matching all kwargs."""
    return [r for r in rows if all(str(r.get(k, "")) == str(v) for k, v in kwargs.items())]

def compute_speedup(throughput, ref_throughput):
    """Compute speedup as ratio of throughputs."""
    try:
        t = float(throughput)
        r = float(ref_throughput)
        if r == 0:
            return "\\TODO{}"
        return f"{t/r:.2f}$\\times$"
    except (ValueError, TypeError):
        return "\\TODO{}"

def build_cpu_results_table(rows, t_ref_4t, t_ref_1t):
    cpu_c64 = find_rows(rows, plataforma="CPU", C="64")
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Resultados de CPU SHA-256 (i7-1255U, E-cores, $C=64$~B, $N=16\\,777\\,216$, $B=2$)}",
        "  \\label{tab:cpu_results}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lccccc}",
        "    \\toprule",
        "    \\textbf{Config.} & \\textbf{Throughput (GB/s)} & \\textbf{Mhash/s} & \\textbf{J/GB} & \\textbf{Speedup$^a$} & \\textbf{Speedup$^b$} \\\\",
        "    \\midrule",
    ]
    variant_labels = {
        "SCALAR_1T": "Escalar 1T",
        "SHANI_1T": "SHA-NI 1T",
        "SHANI_2T": "SHA-NI 2T",
        "SHANI_4T": "SHA-NI 4T",
        "SHANI_8T": "SHA-NI 8T",
        "SHANI_12T": "SHA-NI 12T",
    }
    variant_order = ["SCALAR_1T", "SHANI_1T", "SHANI_2T", "SHANI_4T", "SHANI_8T", "SHANI_12T"]
    for v in variant_order:
        r = find_row(cpu_c64, variante=v)
        if r:
            tput = fmt_throughput(r["throughput_mean_GBs"], r["throughput_sd_GBs"])
            mhash = fmt_hashes(r["hashes_s"])
            j_gb = fmt(r.get("J_GB_neto") if r.get("J_GB_neto") not in [None, "", "N/A"] else r.get("J_GB_dispositivo"))
            sp_4t = compute_speedup(r["throughput_mean_GBs"], t_ref_4t)
            sp_1t = compute_speedup(r["throughput_mean_GBs"], t_ref_1t)
            label = variant_labels.get(v, v)
            lines.append(f"    {label:<14} & {tput:<22} & {mhash:>6} & {j_gb:>8} & {sp_4t:>12} & {sp_1t:>12} \\\\")
            if v == "SCALAR_1T":
                lines.append("    \\midrule")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{6}{l}{\\footnotesize $^a$Referencia principal: SHA-NI 4T E2E. $^b$Referencia secundaria: Escalar 1T.} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_cpu_sweep_table(rows):
    cpu_sweep = find_rows(rows, plataforma="CPU", variante="SHANI_4T")
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Barrido de tamaño de fragmento $C$ en CPU SHA-NI 4T}",
        "  \\label{tab:cpu_sweep}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lccccc}",
        "    \\toprule",
        "    \\textbf{$C$} & \\textbf{$N$} & \\textbf{$B$} & \\textbf{Throughput (GB/s)} & \\textbf{Mhash/s} & \\textbf{J/GB} \\\\",
        "    \\midrule",
    ]
    for r in sorted(cpu_sweep, key=lambda x: int(x["C"])):
        c = c_label(r["C"])
        n = f"{int(r['N']):,}".replace(",", "\\,")
        b = r["B"]
        tput = fmt_throughput(r["throughput_mean_GBs"], r["throughput_sd_GBs"])
        mhash = fmt_hashes(r["hashes_s"])
        j_gb = fmt(r.get("J_GB_neto") if r.get("J_GB_neto") not in [None, "", "N/A"] else r.get("J_GB_dispositivo"))
        lines.append(f"    {c:<8} & {n:>14} & {b:>3} & {tput:<22} & {mhash:>6} & {j_gb:>8} \\\\")
    lines.extend([
        "    \\bottomrule",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_gpu_ablation_table(rows, t_ref_4t):
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Ablación GPU: kernel v1 (base) vs.~v2 (alta utilización), staging pinned}",
        "  \\label{tab:gpu_ablation}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{llcccc}",
        "    \\toprule",
        "    \\textbf{$C$} & \\textbf{Kernel} & \\textbf{Kernel-only (GB/s)} & \\textbf{E2E (GB/s)} & \\textbf{Speedup$^a$} & \\textbf{Mejora v1$\\to$v2} \\\\",
        "    \\midrule",
    ]
    c_values = [64, 1024, 4096, 65536, 1048576]
    for c in c_values:
        for ver in ["GPU_V1", "GPU_V2"]:
            rk = find_row(rows, plataforma="GPU", variante=ver, C=str(c), staging="pinned", nivel="kernel-only")
            re = find_row(rows, plataforma="GPU", variante=ver, C=str(c), staging="pinned", nivel="E2E")
            if rk and re:
                tk = fmt(rk["throughput_mean_GBs"])
                te = fmt(re["throughput_mean_GBs"])
                sp = compute_speedup(re["throughput_mean_GBs"], t_ref_4t)
                if ver == "GPU_V2":
                    rk_v1 = find_row(rows, plataforma="GPU", variante="GPU_V1", C=str(c), staging="pinned", nivel="kernel-only")
                    if rk_v1:
                        imp = float(rk["throughput_mean_GBs"]) / float(rk_v1["throughput_mean_GBs"])
                        imp_str = f"{imp:.1f}$\\times$"
                    else:
                        imp_str = "---"
                else:
                    imp_str = "---"
                cl = c_label(c)
                ver_label = "v1" if ver == "GPU_V1" else "\\textbf{v2}"
                lines.append(f"    {cl:<8} & {ver_label:<10} & {tk:>8} & {te:>8} & {sp:>12} & {imp_str:>8} \\\\")
        if c != c_values[-1]:
            lines.append("    \\midrule")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{6}{l}{\\footnotesize $^a$Speedup E2E vs.~CPU SHA-NI 4T ($C=64$~B).} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_gpu_staging_table(rows, t_ref_4t):
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Impacto del staging en GPU v2 ($C=64$~B)}",
        "  \\label{tab:gpu_staging}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lcccc}",
        "    \\toprule",
        "    \\textbf{Staging} & \\textbf{Kernel-only (GB/s)} & \\textbf{E2E (GB/s)} & \\textbf{Ratio K/E2E} & \\textbf{Speedup$^a$} \\\\",
        "    \\midrule",
    ]
    for stg in ["pinned", "pageable"]:
        rk = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging=stg, nivel="kernel-only")
        re = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging=stg, nivel="E2E")
        if rk and re:
            tk = float(rk["throughput_mean_GBs"])
            te = float(re["throughput_mean_GBs"])
            ratio = tk / te if te > 0 else 0
            sp = compute_speedup(re["throughput_mean_GBs"], t_ref_4t)
            stg_label = "Pinned" if stg == "pinned" else "Pageable"
            lines.append(f"    {stg_label:<10} & {tk:.2f} $\\pm$ {float(rk['throughput_sd_GBs']):.2f} & {te:.2f} $\\pm$ {float(re['throughput_sd_GBs']):.2f} & {ratio:.2f}$\\times$ & {sp} \\\\")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{5}{l}{\\footnotesize $^a$Speedup E2E vs.~CPU SHA-NI 4T ($C=64$~B).} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_comparison_table(rows, t_ref_4t):
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Comparación cruzada de rendimiento y eficiencia energética}",
        "  \\label{tab:comparison}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lccccc}",
        "    \\toprule",
        "    \\textbf{Plataforma / Config.} & \\textbf{$C$} & \\textbf{Throughput (GB/s)} & \\textbf{J/GB} & \\textbf{Speedup$^a$} \\\\",
        "    \\midrule",
    ]
    comparison_configs = [
        ("CPU", "SCALAR_1T", "64", "E2E", "Escalar 1T"),
        ("CPU", "SHANI_4T", "64", "E2E", "SHA-NI 4T (ref.)"),
        ("CPU", "SHANI_8T", "64", "E2E", "SHA-NI 8T"),
        ("CPU", "SHANI_12T", "64", "E2E", "SHA-NI 12T"),
        ("GPU", "GPU_V2", "64", "kernel-only", "GPU v2 kernel"),
        ("GPU", "GPU_V2", "64", "E2E", "GPU v2 E2E pinned"),
    ]
    for plat, var, c, nivel, label in comparison_configs:
        if plat == "CPU":
            r = find_row(rows, plataforma=plat, variante=var, C=c)
        else:
            r = find_row(rows, plataforma=plat, variante=var, C=c, staging="pinned", nivel=nivel)
        if r:
            tput = fmt(r["throughput_mean_GBs"])
            j_gb = fmt(r.get("J_GB_neto") if r.get("J_GB_neto") not in [None, "", "N/A"] else r.get("J_GB_dispositivo"))
            sp = compute_speedup(r["throughput_mean_GBs"], t_ref_4t)
            cl = c_label(c)
            lines.append(f"    {label:<22} & {cl:<8} & {tput:>8} & {j_gb:>8} & {sp:>12} \\\\")
    lines.extend([
        "    \\midrule",
        "    FPGA (Spartan-7) & --- & \\TODO{} & \\TODO{} & \\TODO{} \\\\",
        "    \\bottomrule",
        "    \\multicolumn{5}{l}{\\footnotesize $^a$Speedup vs.~CPU SHA-NI 4T E2E ($C=64$~B, throughput " + f"{t_ref_4t:.2f}" + "~GB/s).} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def main():
    rows = load_csv()

    ref_4t = find_row(rows, plataforma="CPU", variante="SHANI_4T", C="64")
    ref_1t = find_row(rows, plataforma="CPU", variante="SCALAR_1T", C="64")
    t_ref_4t = float(ref_4t["throughput_mean_GBs"]) if ref_4t else 0
    t_ref_1t = float(ref_1t["throughput_mean_GBs"]) if ref_1t else 0

    t1 = build_cpu_results_table(rows, t_ref_4t, t_ref_1t)
    t2 = build_cpu_sweep_table(rows)
    t3 = build_gpu_ablation_table(rows, t_ref_4t)
    t4 = build_gpu_staging_table(rows, t_ref_4t)
    t5 = build_comparison_table(rows, t_ref_4t)

    # Save individual tables
    with open(os.path.join(PAPER_DIR, "tab_cpu_results.tex"), "w") as f:
        f.write(t1)
    with open(os.path.join(PAPER_DIR, "tab_cpu_sweep.tex"), "w") as f:
        f.write(t2)
    with open(os.path.join(PAPER_DIR, "tab_gpu_ablation.tex"), "w") as f:
        f.write(t3)
    with open(os.path.join(PAPER_DIR, "tab_gpu_staging.tex"), "w") as f:
        f.write(t4)
    with open(os.path.join(PAPER_DIR, "tab_comparison.tex"), "w") as f:
        f.write(t5)

    # Combined gen_tables.tex
    combined = "\n".join([
        "% Auto-generated combined LaTeX tables",
        t1, t2, t3, t4, t5
    ])
    with open(os.path.join(PAPER_DIR, "gen_tables.tex"), "w") as f:
        f.write(combined)
    with open("results/latex_tables.tex", "w") as f:
        f.write(combined)

    print("Generated all individual and combined LaTeX tables successfully.")

if __name__ == "__main__":
    main()
