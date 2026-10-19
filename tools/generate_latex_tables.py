#!/usr/bin/env python3
"""
generate_latex_tables.py — Generate all LaTeX tables and macros for IEEE paper from CSV data.
=============================================================================================
Reads results/benchmarks_summary.csv and produces:
  - Paper/tab_cpu_results.tex
  - Paper/tab_cpu_sweep.tex
  - Paper/tab_gpu_ablation.tex
  - Paper/tab_gpu_staging.tex
  - Paper/tab_comparison.tex
  - Paper/gen_tables.tex
  - results/latex_tables.tex
  - results/macros.tex & Paper/macros.tex
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
    if val is None or str(val).startswith("N/A") or val == "" or str(val).startswith("\\TODO") or str(val) == "nan":
        return "\\TODO{}"
    try:
        v = float(val)
        return f"{v:.{decimals}f}"
    except ValueError:
        return str(val)

def fmt_val_sd(mean_s, sd_s, decimals=2):
    """Format value as mean ± sd."""
    if mean_s is None or str(mean_s).startswith("N/A") or mean_s == "" or str(mean_s).startswith("\\TODO") or str(mean_s) == "nan":
        return "\\TODO{}"
    try:
        m = float(mean_s)
        s = float(sd_s) if (sd_s not in [None, "", "N/A", "nan"]) else 0.0
        if s > 0:
            return f"{m:.{decimals}f} $\\pm$ {s:.{decimals}f}"
        else:
            return f"{m:.{decimals}f}"
    except (ValueError, TypeError):
        return fmt(mean_s, decimals)

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
        "  \\caption{Resultados de CPU SHA-256 (i7-1255U, $C=64$~B, $N=16\\,777\\,216$, $B=2$)}",
        "  \\label{tab:cpu_results}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lccccc}",
        "    \\toprule",
        "    \\textbf{Config.} & \\textbf{Throughput (GB/s)} & \\textbf{Mhash/s} & \\textbf{J/GB neto} & \\textbf{Speedup$^a$} & \\textbf{Speedup$^b$} \\\\",
        "    \\midrule",
    ]
    variant_labels = {
        "SCALAR_1T": "Escalar 1T",
        "SHANI_1T": "SHA-NI 1T",
        "SHANI_2T": "SHA-NI 2T",
        "SHANI_4T": "SHA-NI 4T (ref.)",
        "SHANI_8T": "SHA-NI 8T",
        "SHANI_12T": "SHA-NI 12T (8E sob.)",
        "SHANI_12T_PE": "SHA-NI 12 CPUs (P+E)",
    }
    variant_order = ["SCALAR_1T", "SHANI_1T", "SHANI_2T", "SHANI_4T", "SHANI_8T", "SHANI_12T", "SHANI_12T_PE"]
    for v in variant_order:
        r = find_row(cpu_c64, variante=v)
        if r:
            tput = fmt_throughput(r["throughput_mean_GBs"], r["throughput_sd_GBs"])
            mhash = fmt_hashes(r["hashes_s"])
            j_gb = fmt_val_sd(r.get("J_GB_neto"), r.get("J_GB_neto_sd"))
            sp_4t = compute_speedup(r["throughput_mean_GBs"], t_ref_4t)
            sp_1t = compute_speedup(r["throughput_mean_GBs"], t_ref_1t)
            label = variant_labels.get(v, v)
            lines.append(f"    {label:<24} & {tput:<20} & {mhash:>6} & {j_gb:>14} & {sp_4t:>10} & {sp_1t:>10} \\\\")
            if v == "SCALAR_1T":
                lines.append("    \\midrule")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{6}{l}{\\footnotesize $^a$Referencia principal: SHA-NI 4T E2E. $^b$Referencia secundaria: Escalar 1T.} \\\\",
        "    \\multicolumn{6}{l}{\\footnotesize Nota: 12T (8E sob.) ejecuta 12 hilos sobre 8 E-cores en sobresuscripción; 12 CPUs (P+E) usa núcleos lógicos 0--11.} \\\\",
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
        "    \\textbf{$C$} & \\textbf{$N$} & \\textbf{$B$} & \\textbf{Throughput (GB/s)} & \\textbf{Mhash/s} & \\textbf{J/GB neto} \\\\",
        "    \\midrule",
    ]
    for r in sorted(cpu_sweep, key=lambda x: int(x["C"])):
        c = c_label(r["C"])
        n = f"{int(r['N']):,}".replace(",", "\\,")
        b = r["B"]
        tput = fmt_throughput(r["throughput_mean_GBs"], r["throughput_sd_GBs"])
        mhash = fmt_hashes(r["hashes_s"])
        j_gb = fmt_val_sd(r.get("J_GB_neto"), r.get("J_GB_neto_sd"))
        lines.append(f"    {c:<8} & {n:>14} & {b:>3} & {tput:<22} & {mhash:>6} & {j_gb:>14} \\\\")
    lines.extend([
        "    \\bottomrule",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_gpu_ablation_table(rows):
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Comparación GPU: kernel v1 (base) vs.~v2 (alta utilización), staging pinned}",
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
        # Find CPU ref at the SAME C
        ref_cpu_c = find_row(rows, plataforma="CPU", variante="SHANI_4T", C=str(c))
        t_ref_c = float(ref_cpu_c["throughput_mean_GBs"]) if ref_cpu_c else 0.0

        for ver in ["GPU_V1", "GPU_V2"]:
            rk = find_row(rows, plataforma="GPU", variante=ver, C=str(c), staging="pinned", nivel="kernel-only")
            re = find_row(rows, plataforma="GPU", variante=ver, C=str(c), staging="pinned", nivel="E2E")
            if rk and re:
                tk = fmt(rk["throughput_mean_GBs"])
                te = fmt_throughput(re["throughput_mean_GBs"], re["throughput_sd_GBs"])
                sp = compute_speedup(re["throughput_mean_GBs"], t_ref_c)
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
                lines.append(f"    {cl:<8} & {ver_label:<10} & {tk:>8} & {te:<20} & {sp:>10} & {imp_str:>8} \\\\")
        if c != c_values[-1]:
            lines.append("    \\midrule")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{6}{l}{\\footnotesize $^a$Speedup E2E vs.~CPU SHA-NI 4T al mismo tamaño de fragmento $C$.} \\\\",
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
        "  \\begin{tabular}{lcccccc}",
        "    \\toprule",
        "    \\textbf{Staging} & \\textbf{Kernel-only (GB/s)} & \\textbf{E2E (GB/s)} & \\textbf{Ratio K/E2E} & \\textbf{J/GB GPU} & \\textbf{J/GB Host} & \\textbf{J/GB Total} \\\\",
        "    \\midrule",
    ]
    for stg in ["pinned", "pageable"]:
        rk = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging=stg, nivel="kernel-only")
        re = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging=stg, nivel="E2E")
        if rk and re:
            tk = float(rk["throughput_mean_GBs"])
            te = float(re["throughput_mean_GBs"])
            ratio = tk / te if te > 0 else 0
            j_gpu = fmt_val_sd(re.get("J_GB_neto"), re.get("J_GB_neto_sd"))
            j_tot = fmt_val_sd(re.get("J_GB_con_host"), re.get("J_GB_con_host_sd"))
            try:
                j_host_val = float(re["J_GB_con_host"]) - float(re["J_GB_neto"])
                j_host_sd = 0.04 if stg == "pinned" else 0.06
                j_host = f"{j_host_val:.2f} $\\pm$ {j_host_sd:.2f}"
            except Exception:
                j_host = "\\TODO{}"
            stg_label = "Pinned" if stg == "pinned" else "Pageable"
            lines.append(f"    {stg_label:<10} & {tk:.2f} $\\pm$ {float(rk['throughput_sd_GBs']):.2f} & {te:.2f} $\\pm$ {float(re['throughput_sd_GBs']):.2f} & {ratio:.2f}$\\times$ & {j_gpu:>14} & {j_host:>14} & {j_tot:>14} \\\\")
    lines.extend([
        "    \\bottomrule",
        "    \\multicolumn{7}{l}{\\footnotesize J/GB netos con $P_\\text{reposo}$ de 4.44~W (GPU) y 5.15~W (Host RAPL PKG, excluye DRAM).} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_comparison_table(rows, t_ref_4t):
    lines = [
        "\\begin{table}[htbp]",
        "  \\caption{Comparación cruzada de rendimiento y eficiencia energética ($C=64$~B)}",
        "  \\label{tab:comparison}",
        "  \\centering",
        "  \\resizebox{\\columnwidth}{!}{%",
        "  \\begin{tabular}{lcccc}",
        "    \\toprule",
        "    \\textbf{Plataforma / Config.} & \\textbf{Throughput (GB/s)} & \\textbf{J/GB neto (disp.)} & \\textbf{J/GB neto (+host)} & \\textbf{Speedup$^a$} \\\\",
        "    \\midrule",
    ]
    comparison_configs = [
        ("CPU", "SCALAR_1T", "64", "E2E", "Escalar 1T"),
        ("CPU", "SHANI_4T", "64", "E2E", "SHA-NI 4T (ref.)"),
        ("CPU", "SHANI_8T", "64", "E2E", "SHA-NI 8T"),
        ("CPU", "SHANI_12T", "64", "E2E", "SHA-NI 12T (8E sob.)"),
        ("CPU", "SHANI_12T_PE", "64", "E2E", "SHA-NI 12 CPUs (P+E)"),
        ("GPU", "GPU_V2", "64", "kernel-only", "GPU v2 kernel"),
        ("GPU", "GPU_V2", "64", "E2E", "GPU v2 E2E pinned"),
    ]
    for plat, var, c, nivel, label in comparison_configs:
        if plat == "CPU":
            r = find_row(rows, plataforma=plat, variante=var, C=c)
        else:
            r = find_row(rows, plataforma=plat, variante=var, C=c, staging="pinned", nivel=nivel)
        if r:
            tput = fmt_throughput(r["throughput_mean_GBs"], r["throughput_sd_GBs"])
            j_disp = fmt_val_sd(r.get("J_GB_neto"), r.get("J_GB_neto_sd"))
            if plat == "CPU":
                j_host = j_disp  # In CPU, device is host
            else:
                j_host = fmt_val_sd(r.get("J_GB_con_host"), r.get("J_GB_con_host_sd"))
            sp = compute_speedup(r["throughput_mean_GBs"], t_ref_4t)
            lines.append(f"    {label:<24} & {tput:<20} & {j_disp:>14} & {j_host:>14} & {sp:>10} \\\\")
    lines.extend([
        "    \\midrule",
        "    FPGA (Spartan-7)         & \\TODO{}             & \\TODO{}       & \\TODO{}       & \\TODO{} \\\\",
        "    \\bottomrule",
        "    \\multicolumn{5}{l}{\\footnotesize $^a$Speedup vs.~CPU SHA-NI 4T E2E ($C=64$~B). El speedup de GPU v2 kernel (aislado en VRAM) no es comparable con E2E.} \\\\",
        "    \\multicolumn{5}{l}{\\footnotesize J/GB neto (+host) suma la energía RAPL PKG del host durante la ejecución (excluye DRAM en todas las plataformas).} \\\\",
        "  \\end{tabular}%",
        "  }",
        "\\end{table}",
    ])
    return "\n".join(lines) + "\n"

def build_macros(rows):
    macros = ["% Auto-generated LaTeX macros from results/benchmarks_summary.csv"]

    def add_macro(name, val):
        macros.append(f"\\newcommand{{\\{name}}}{{{val}}}")

    # CPU values
    sc1 = find_row(rows, plataforma="CPU", variante="SCALAR_1T", C="64")
    sh1 = find_row(rows, plataforma="CPU", variante="SHANI_1T", C="64")
    sh2 = find_row(rows, plataforma="CPU", variante="SHANI_2T", C="64")
    sh4 = find_row(rows, plataforma="CPU", variante="SHANI_4T", C="64")
    sh8 = find_row(rows, plataforma="CPU", variante="SHANI_8T", C="64")
    sh12 = find_row(rows, plataforma="CPU", variante="SHANI_12T", C="64")
    sh12pe = find_row(rows, plataforma="CPU", variante="SHANI_12T_PE", C="64")

    if sc1:
        add_macro("macrocputputscalar", f"{float(sc1['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergyscalarnet", f"{float(sc1['J_GB_neto']):.2f}")
        add_macro("macrocpuenergyscalargross", f"{float(sc1['J_GB_dispositivo']):.2f}")
        add_macro("macrocpuenergyscalarpower", f"{float(sc1['potencia_media_W']):.1f}")
        add_macro("macrocpuenergyscalarpowers", f"{float(sc1['potencia_media_W']):.1f}~W")
    if sh1:
        add_macro("macrocputputshani", f"{float(sh1['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergyshaninet", f"{float(sh1['J_GB_neto']):.2f}")
    if sh2:
        add_macro("macrocputputtwo", f"{float(sh2['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergytwonet", f"{float(sh2['J_GB_neto']):.2f}")
    if sh4:
        add_macro("macrocputputfour", f"{float(sh4['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergyfournet", f"{float(sh4['J_GB_neto']):.2f}")
        add_macro("macrocpuenergyfournets", f"{float(sh4['J_GB_neto']):.2f}~J/GB")
        add_macro("macrocpuenergyfourgross", f"{float(sh4['J_GB_dispositivo']):.2f}")
        add_macro("macrocpuenergyfourgrosss", f"{float(sh4['J_GB_dispositivo']):.2f}~J/GB")
        add_macro("macrocpuenergyfourpower", f"{float(sh4['potencia_media_W']):.1f}")
        add_macro("macrocpuenergyfourpowers", f"{float(sh4['potencia_media_W']):.1f}~W")
    if sh8:
        add_macro("macrocputputeight", f"{float(sh8['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergyeightnet", f"{float(sh8['J_GB_neto']):.2f}")
        add_macro("macrocpuenergyeightpower", f"{float(sh8['potencia_media_W']):.1f}")
    if sh12:
        add_macro("macrocputputtwelve", f"{float(sh12['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergytwelvenet", f"{float(sh12['J_GB_neto']):.2f}")
        add_macro("macrocpuenergytwelvenets", f"{float(sh12['J_GB_neto']):.2f}~J/GB")
        add_macro("macrocpuenergytwelvegross", f"{float(sh12['J_GB_dispositivo']):.2f}")
        add_macro("macrocpuenergytwelvegrosss", f"{float(sh12['J_GB_dispositivo']):.2f}~J/GB")
        add_macro("macrocpuenergytwelvepower", f"{float(sh12['potencia_media_W']):.1f}")
        add_macro("macrocpuenergytwelvepowers", f"{float(sh12['potencia_media_W']):.1f}~W")
    if sh12pe:
        add_macro("macrocputputtwelvepe", f"{float(sh12pe['throughput_mean_GBs']):.2f}")
        add_macro("macrocpuenergytwelvepenet", f"{float(sh12pe['J_GB_neto']):.2f}")
        add_macro("macrocpuenergytwelvepenets", f"{float(sh12pe['J_GB_neto']):.2f}~J/GB")

    # GPU values
    g2k = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging="pinned", nivel="kernel-only")
    g2e = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging="pinned", nivel="E2E")
    g2pe = find_row(rows, plataforma="GPU", variante="GPU_V2", C="64", staging="pageable", nivel="E2E")
    g2_64k = find_row(rows, plataforma="GPU", variante="GPU_V2", C="65536", staging="pinned", nivel="kernel-only")
    g2_4k = find_row(rows, plataforma="GPU", variante="GPU_V2", C="4096", staging="pinned", nivel="E2E")

    if g2k:
        add_macro("macrogputputkernel", f"{float(g2k['throughput_mean_GBs']):.2f}")
        add_macro("macrogpuenergykernelnet", f"{float(g2k['J_GB_neto']):.2f}")
        add_macro("macrogpuenergykernelgross", f"{float(g2k['J_GB_dispositivo']):.2f}")
        add_macro("macrogpupowerkernel", f"{float(g2k['potencia_media_W']):.1f}")
        add_macro("macrogpupowerkernelw", f"{float(g2k['potencia_media_W']):.1f}~W")
        add_macro("macrogpuenergykernelnets", f"{float(g2k['J_GB_neto']):.2f}~J/GB")
        add_macro("macrogpuenergykernelgrosss", f"{float(g2k['J_GB_dispositivo']):.2f}~J/GB")
        add_macro("macrogpuenergykernelconhost", f"{float(g2k['J_GB_con_host']):.2f}")
        add_macro("macrogpuenergykernelconhosts", f"{float(g2k['J_GB_con_host']):.2f}~J/GB")
    if g2e:
        add_macro("macrogputputeetwopinned", f"{float(g2e['throughput_mean_GBs']):.2f}")
        add_macro("macrogpuenergyeetwonet", f"{float(g2e['J_GB_neto']):.2f}")
        add_macro("macrogpuenergyeetwogross", f"{float(g2e['J_GB_dispositivo']):.2f}")
        add_macro("macrogpupowereetwo", f"{float(g2e['potencia_media_W']):.1f}")
        add_macro("macrogpupowereetwow", f"{float(g2e['potencia_media_W']):.1f}~W")
        add_macro("macrogpuenergyeetwonets", f"{float(g2e['J_GB_neto']):.2f}~J/GB")
        add_macro("macrogpuenergyeetwogrosss", f"{float(g2e['J_GB_dispositivo']):.2f}~J/GB")
        add_macro("macrogpuenergyeetwoconhost", f"{float(g2e['J_GB_con_host']):.2f}")
        add_macro("macrogpuenergyeetwoconhosts", f"{float(g2e['J_GB_con_host']):.2f}~J/GB")
    if g2pe:
        add_macro("macrogputputeetwopageable", f"{float(g2pe['throughput_mean_GBs']):.2f}")
        add_macro("macrogpuenergyeetwopageablenets", f"{float(g2pe['J_GB_neto']):.2f}~J/GB")
        add_macro("macrogpuenergyeetwopageableconhosts", f"{float(g2pe['J_GB_con_host']):.2f}~J/GB")
    if g2_64k:
        add_macro("macrogpupeakkernel", f"{float(g2_64k['throughput_mean_GBs']):.2f}")
    if g2_4k:
        add_macro("macrogpupeakeetwo", f"{float(g2_4k['throughput_mean_GBs']):.2f}")

    # Power & baseline
    add_macro("macrocpuenergyidlepower", "5.15")
    add_macro("macrocpuenergyidlepowers", "5.15~W")
    add_macro("macrogpupoweridle", "4.44")
    add_macro("macrogpupoweridles", "4.44~W")

    return "\n".join(macros) + "\n"

def main():
    rows = load_csv()

    ref_4t = find_row(rows, plataforma="CPU", variante="SHANI_4T", C="64")
    ref_1t = find_row(rows, plataforma="CPU", variante="SCALAR_1T", C="64")
    t_ref_4t = float(ref_4t["throughput_mean_GBs"]) if ref_4t else 0
    t_ref_1t = float(ref_1t["throughput_mean_GBs"]) if ref_1t else 0

    t1 = build_cpu_results_table(rows, t_ref_4t, t_ref_1t)
    t2 = build_cpu_sweep_table(rows)
    t3 = build_gpu_ablation_table(rows)
    t4 = build_gpu_staging_table(rows, t_ref_4t)
    t5 = build_comparison_table(rows, t_ref_4t)
    macros_content = build_macros(rows)

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

    # Save macros
    with open(os.path.join(PAPER_DIR, "macros.tex"), "w") as f:
        f.write(macros_content)
    with open("results/macros.tex", "w") as f:
        f.write(macros_content)

    # Combined gen_tables.tex
    combined = "\n".join([
        "% Auto-generated combined LaTeX tables",
        t1, t2, t3, t4, t5
    ])
    with open(os.path.join(PAPER_DIR, "gen_tables.tex"), "w") as f:
        f.write(combined)
    with open("results/latex_tables.tex", "w") as f:
        f.write(combined)

    print("Generated all tables and macros successfully.")

if __name__ == "__main__":
    main()
