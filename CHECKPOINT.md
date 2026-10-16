# CHECKPOINT — 2026-10-16T12:10

## Estado de Fases
- **Fase A (Auditoría)**: 100% Completada. Ver `AUDITORIA.md`.
  - Workload y métricas auditados: $N$, $B$, `output_mode=full`, kernel-only $\ge$ E2E verificados.
  - Verificación formal de digests contra NIST y Python `hashlib` (10,100 fragmentos) completada exitosamente (100% PASS).
  - Telemetría resuelta: reinicio del equipo sincronizó driver/NVML y `chmod` habilitó RAPL PKG.
- **Fase B (Corrección)**: 100% Completada.
  - Orquestador `tools/run_benchmarks.py` actualizado con muestreador de frecuencia activa en CPU (`FreqSampler`), lectura RAPL PKG (bruta, neta, reposo 3.36 W) y telemetría continua de GPU a 10 Hz (`nvidia-smi`) en paralelo con RAPL del host.
  - Speedup anclado unívocamente a SHA-NI 4T E2E ($C=64$~B, 3.54 GB/s), con Escalar 1T rotulado como referencia secundaria.
  - Enlace PCIe Gen 4 $\times$4 confirmado mediante telemetría NVML (`nvidia-smi`).
  - Generación de tablas desacoplada mediante script automatizado (`tools/generate_latex_tables.py`) que lee directamente de `results/benchmarks_summary.csv` y genera tablas con `\resizebox{\columnwidth}{!}{...}` eliminando advertencias de overfull `\hbox`.
- **Fase C (Fase 7, Redacción en LaTeX)**: 100% Completada.
  - `Paper/IEEE_es.tex` redactado rigurosamente siguiendo los 11 puntos de la especificación.
  - Todos los números provienen exclusivamente de `results/benchmarks_summary.csv`.
  - Tablas generadas por script e incluidas vía `\input` (`tab_cpu_results`, `tab_cpu_sweep`, `tab_gpu_ablation`, `tab_gpu_staging`, `tab_comparison`).
  - Gráficos regenerados y sincronizados (`throughput_vs_c.pdf`, `throughput_chart.pdf`, `energy_chart.pdf`).
  - Documento compilado con `tectonic` a `Paper/IEEE_es.pdf` (8 páginas, 0 errores, 0 overfull table warnings).
  - Sección FPGA (III.C, Tabla FPGA, Abstract, Verilog) intacta según las restricciones.

## Resumen de Resultados Principales ($C=64$~B, $N=16\,777\,216$, $B=2$)
- **CPU Escalar 1T**: 0.11 GB/s, 1.71 Mhash/s, 65.11 J/GB neto (92.72 J/GB bruto a 9.09 W, ~3487 MHz).
- **CPU SHA-NI 1T**: 0.89 GB/s, 13.90 Mhash/s, 6.83 J/GB neto (9.38 W, ~3483 MHz), 8.13$\times$ vs 1T.
- **CPU SHA-NI 2T**: 1.78 GB/s, 27.78 Mhash/s, 5.16 J/GB neto (12.55 W, ~3472 MHz), 16.25$\times$ vs 1T, 0.50$\times$ vs 4T.
- **CPU SHA-NI 4T (Ref. Principal)**: 3.54 GB/s, 55.34 Mhash/s, 5.03 J/GB neto (6.13 J/GB bruto a 20.80 W, ~3474 MHz), 32.38$\times$ vs 1T, 1.00$\times$ vs 4T.
- **CPU SHA-NI 8T**: 5.76 GB/s, 90.07 Mhash/s, 3.07 J/GB neto (20.69 W, ~2860 MHz), 52.69$\times$ vs 1T, 1.63$\times$ vs 4T.
- **CPU SHA-NI 12T**: 5.94 GB/s, 92.86 Mhash/s, 2.87 J/GB neto (20.04 W, ~2450 MHz), 54.33$\times$ vs 1T, 1.68$\times$ vs 4T.
- **GPU v2 Kernel-only (Pinned)**: 17.40 GB/s, 9.69 J/GB dev, 20.17 J/GB con host (17.67 W), 4.91$\times$ vs 4T.
- **GPU v2 E2E (Pinned)**: 5.01 GB/s, 9.69 J/GB dev, 20.17 J/GB con host (17.67 W), 1.42$\times$ vs 4T (+41.5% vs SHA-NI 4T).
- **GPU v2 E2E (Pageable)**: 3.94 GB/s, 11.73 J/GB dev, 24.86 J/GB con host, 1.11$\times$ vs 4T (-21.4% vs Pinned).
- **Pico Kernel GPU**: 22.29 GB/s en $C=64$~KB (7.3$\times$ v1 kernel a 3.06 GB/s).
- **Pico E2E GPU**: 5.87 GB/s en $C=4$~KB.

## TODOs Restantes en el Documento
1. `\TODO{Referencia [18] (Anonymous) pendiente de completar a mano}` en línea 88 de `Paper/IEEE_es.tex`.
2. Filas de `\TODO{}` para Spartan-7 FPGA en `Paper/tab_comparison.tex` (línea 17) y Tabla FPGA en `Paper/IEEE_es.tex` (reservadas para el equipo de hardware).

## Comandos de Reproducción
```bash
# Ejecutar suite completa (50 configuraciones, 5 repeticiones >= 15 s)
python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5 --sweep-c

# Generar tablas y figuras
python3 tools/generate_latex_tables.py
python3 tools/analyze_results.py
python3 Paper/generate_plots.py

# Compilar PDF del paper
cd Paper && ./tectonic IEEE_es.tex
```
