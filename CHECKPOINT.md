# CHECKPOINT — 2026-10-18T22:30

## Estado de Fases
- **Fase A (Auditoría Inicial)**: 100% Completada. Ver `AUDITORIA.md`.
- **Fase B (Corrección Inicial)**: 100% Completada.
- **Fase C (Fase 7, Redacción Inicial en LaTeX)**: 100% Completada.
- **Fase D (Revisión 2 — Correcciones Críticas de Benchmarking y Redacción IEEE)**: 100% Completada.
- **Fase E (Revisión 3 — Metodología Unificada, Telemetría y Scheduling)**: 100% Completada.
  - **T1 [CRÍTICA] (Energía GPU unificada y consistente)**: Resuelto el desajuste entre tiempo de kernel de evento y potencia sostenida en bucle de 15 s. Implementado `tools/run_gpu_energy_unified.py` midiendo throughput y energía en el mismo bucle continuo ($\ge 15$ s) usando el contador de hardware `nvmlDeviceGetTotalEnergyConsumption` (con verificación cruzada de muestreo a 10 Hz). Chequeo automático $|P / (J/\text{GB}_\text{bruto}) - \text{Throughput}| < 3\%$ verificado con **0.000% de error**.
  - **T2 [CRÍTICA] (Energía con Host y Reversión del Ranking)**: Medido simultáneamente el contador RAPL PKG del host en las mismas corridas de GPU. A 4.98 GB/s (E2E pinned), el host disipa 15.06 W activos (+1.99 J/GB netos), elevando el consumo total a **5.48 J/GB netos**. Reversión del ranking: CPU SHA-NI 4T (4.13 J/GB) es **24.7% más eficiente** que GPU+host; y la mejor CPU (12 CPUs P+E, 2.53 J/GB) es **2.16$\times$ más eficiente energéticamente** con un **17.2% mayor throughput útil** (5.84 vs. 4.98 GB/s).
  - **T3 [ALTA] (Planificación Dinámica en CPU y Desbloqueo de 12 CPUs P+E)**: Implementada cola de trabajo atómica libre de cerrojos (`--sched dynamic`, tareas de 64K mensajes = 4 MiB) en `cpu/sha256_cpu_bench.c`. El desbalance temporal entre hilos en 12 CPUs (P+E) cayó de 146.9 ms a **6.6 ms**, alcanzando **5.84 $\pm$ 0.02 GB/s** (91.25 Mhash/s) y **2.53 $\pm$ 0.02 J/GB netos**, posicionándola como la **mejor configuración de CPU**. Aclarada la anomalía 8T vs 12T s/8E: ambas saturan los 8 E-cores a 2.77 GHz bajo PL1=20 W con rendimientos equivalentes (~5.60 vs. 5.62 GB/s).
  - **T4 [ALTA] (Reconciliación de Reposo y Límites de Potencia MMIO)**: Re-medida la potencia en reposo con 3 corridas de 30 s: CPU PKG = **5.154 $\pm$ 0.060 W**, GPU = **4.439 $\pm$ 0.286 W**. Identificado en `/sys/class/powercap/intel-rapl-mmio:0` Constraint 0 el límite activo estricto **PL1 = 20.0 W** (39.98 s), el cual gobierna la disipación bajo carga ($\approx$20 W). Telemetría térmica confirmó 65–72 °C con `throttle_count = 0` (cero estrangulamiento térmico; limitación puramente por cota MMIO PL1).
  - **T5 (Correcciones Textuales, Bibliográficas y Gráficas)**: Corregidas citas de StoreGPU, Crypto-RV, Zhang & Liu, Gaspar y contextualización de Pham et al. Unificado el uso de "Tabla" y punto decimal (`es-tabla`, `es-nodecimaldot` en `babel`). Optimizadas figuras `throughput_vs_c.pdf` (leyenda reubicada) y `throughput_chart.pdf` (etiquetas rotadas 15°). Cuadro V actualizado con nota sobre no comparabilidad de speedup de kernel aislado con E2E.

## Resumen de Resultados Finales ($C=64$~B, Bucles Unificados $\ge 15$~s)
- **CPU Escalar 1T**: 0.11 GB/s, 45.58 $\pm$ 0.05 J/GB neto (92.72 J/GB bruto a 10.1 W).
- **CPU SHA-NI 1T**: 0.89 GB/s, 5.28 $\pm$ 0.02 J/GB neto.
- **CPU SHA-NI 2T**: 1.78 GB/s, 4.47 $\pm$ 0.02 J/GB neto.
- **CPU SHA-NI 4T (Ref. Principal)**: 3.55 $\pm$ 0.00 GB/s, 4.13 $\pm$ 0.05 J/GB neto (5.58 J/GB bruto a 19.8 W).
- **CPU SHA-NI 8T (Dynamic)**: 5.60 $\pm$ 0.02 GB/s, 2.67 $\pm$ 0.05 J/GB neto (3.59 J/GB bruto a 20.1 W).
- **CPU SHA-NI 12T s/8E (Dynamic)**: 5.62 $\pm$ 0.07 GB/s, 2.69 $\pm$ 0.09 J/GB neto (3.61 J/GB bruto a 20.3 W).
- **CPU SHA-NI 12 CPUs (P+E, Dynamic) — MEJOR CPU**: **5.84 $\pm$ 0.02 GB/s** (91.25 Mhash/s), **2.53 $\pm$ 0.02 J/GB neto** (3.42 J/GB bruto a 19.9 W).
- **GPU v2 Kernel-only (Pinned)**: 15.62 $\pm$ 0.15 GB/s, 1.62 $\pm$ 0.02 J/GB neto solo GPU (1.90 J/GB bruto a 29.7 W; **2.45 $\pm$ 0.04 J/GB con host**).
- **GPU v2 E2E (Pinned)**: 4.98 $\pm$ 0.02 GB/s, 3.49 $\pm$ 0.04 J/GB neto solo GPU (4.38 J/GB bruto a 21.8 W; **5.48 $\pm$ 0.07 J/GB con host**).
- **GPU v2 E2E (Pageable)**: 3.86 $\pm$ 0.02 GB/s, 3.77 $\pm$ 0.03 J/GB neto solo GPU (4.92 J/GB bruto a 19.0 W; **6.34 $\pm$ 0.09 J/GB con host**).
- **Pico Kernel GPU**: 22.29 GB/s en $C=64$~KB.
- **Pico E2E GPU**: 5.87 GB/s en $C=4$~KB.

## TODOs Restantes en el Documento
1. Fila de `\TODO{}` para Spartan-7 FPGA en `Paper/tab_comparison.tex` (línea 18) y Cuadro FPGA en `Paper/IEEE_es.tex` (reservadas para el equipo de desarrollo RTL/FPGA según instrucción de ignorar FPGA).

## Comandos de Reproducción
```bash
# 1. Actualizar CSV consolidado desde JSONs de telemetría unificada
python3 tools/update_benchmarks_csv.py

# 2. Generar tablas y macros desde CSV
python3 tools/generate_latex_tables.py

# 3. Generar gráficos académicos
python3 tools/analyze_results.py
python3 Paper/generate_plots.py

# 4. Compilar PDF del paper (cero errores)
cd Paper && ./tectonic IEEE_es.tex
```
