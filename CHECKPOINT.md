# CHECKPOINT — 2026-10-18T15:50

## Estado de Fases
- **Fase A (Auditoría Inicial)**: 100% Completada. Ver `AUDITORIA.md`.
- **Fase B (Corrección Inicial)**: 100% Completada.
- **Fase C (Fase 7, Redacción Inicial en LaTeX)**: 100% Completada.
- **Fase D (Revisión 2 — Correcciones Críticas de Benchmarking y Redacción IEEE)**: 100% Completada.
  - **T1 (Energía GPU inconsistente resuelta)**: Desacoplado `kernel-only` y `E2E`, muestreo NVML C API estricto en bucle cronometrado ($\ge 15$ s). Reposo base GPU medido en 6.11 W. Nuevos valores: Kernel-only 1.32 J/GB neto (1.74 bruto a 25.0 W); E2E 3.17 J/GB neto (4.57 bruto a 19.9 W). Ambos verifican $P_\text{activa} \le 30$ W TDP.
  - **T2 (Speedup del barrido de C)**: Columna de speedup en Tabla III recalculada contra CPU SHA-NI 4T al *mismo* $C$. Curva de CPU por $C$ agregada a Figura 1 (`throughput_vs_c.pdf`). Texto de IV-B4 reescrito reflejando la victoria de CPU para $C \ge 1$ KB.
  - **T3 (Bibliografía y Trabajo Relacionado)**: `references.bib` actualizado rigurosamente con entradas IEEEtran (r1=Pham, r2=Li, r3=Chaves, r4=Kieu-Do-Nguyen, Mehammed 2021/2025, StoreGPU, Gueron, etc.). Eliminado TODO de Kammoun et al. Restaurada sección CUDA/SIMT y párrafo multiplataforma. 0 errores BibTeX.
  - **T4 (CPU 12T desambiguado)**: Rotulado como "12 hilos sobre 8 E-cores (sobresuscripción)". Añadida y ejecutada configuración "SHA-NI, 12 CPUs lógicas (P+E)" (4.51 GB/s). Agregadas ambas a Tablas I, V y Figura 2 (`throughput_chart.pdf`).
  - **T5 (Potencia y límites RAPL CPU)**: Registrados límites sysfs (PL1=15 W nominal / 200 W OEM, PL2=39 W, PL4=60 W, reposo 3.36 W). Corregida potencia activa bajo carga: 21.7 W (4T), 21.0 W (12T), satisfaciendo $P_\text{activa} = J/\text{GB}_\text{bruto} \times \text{GB/s}$.
  - **T6 (Escalado con C cuantificado)**: Análisis de bloques/s (110.7 M a 64 B vs 140.4 M a 1 MB = 78.8%), demostrando $\approx$21.2% de sobrecarga por mensaje además del padding.
  - **T7 (Análisis PCIe full-duplex)**: Verificado enlace PCIe Gen 4 $\times$4, `asyncEngineCount=2`. Tasas direccionales calculadas (H2D=5.01 GB/s, D2H=2.51 GB/s). E2E alcanza $\approx$92% del límite efectivo a 1--4 KB (5.87 GB/s). Eliminada afirmación de que transferencias se suman.
  - **T8 (Consistencia de afirmaciones)**: Corregida Opt. 6 (grid-stride) eliminando "independientemente de N"; corregida convergencia a 1.0$\times$ en 1 MB; refinada introducción (eliminado "throughput insuficiente", eliminada "latencia", matizada resistencia a colisiones).
  - **T9 (Trazabilidad documentada)**: Auditada la evolución 5.13 $\to$ 8.97 GB/s en CPU (OpenSSL/fread a intrinsics directas SHA-NI en memoria) y 16.81 $\to$ 22.29 GB/s en GPU (`--maxrregcount=48`, occupancy 83.3%, 3-stream staging).
  - **T10 (Menores y tablas)**: Añadida desviación estándar a J/GB en Tablas I, II, IV, V y columna E2E en Tabla III. Erratas de math ($10^6$) corregidas. Aclarado uso de API NVML.

## Resumen de Resultados Finales ($C=64$~B)
- **CPU Escalar 1T**: 0.11 GB/s, 65.11 $\pm$ 0.05 J/GB neto (92.72 J/GB bruto a 10.1 W).
- **CPU SHA-NI 1T**: 0.89 GB/s, 6.83 $\pm$ 0.02 J/GB neto.
- **CPU SHA-NI 2T**: 1.78 GB/s, 5.16 $\pm$ 0.03 J/GB neto.
- **CPU SHA-NI 4T (Ref. Principal)**: 3.54 GB/s, 5.03 $\pm$ 0.02 J/GB neto (6.13 J/GB bruto a 21.7 W).
- **CPU SHA-NI 8T**: 5.76 GB/s, 3.07 $\pm$ 0.03 J/GB neto (3.75 J/GB bruto a 21.6 W).
- **CPU SHA-NI 12T (8E sob.)**: 5.94 GB/s, 2.87 $\pm$ 0.02 J/GB neto (3.53 J/GB bruto a 21.0 W).
- **CPU SHA-NI 12 CPUs (P+E)**: 4.51 $\pm$ 0.02 GB/s, 70.52 Mhash/s.
- **GPU v2 Kernel-only (Pinned)**: 17.40 GB/s, 1.32 $\pm$ 0.01 J/GB neto (1.74 J/GB bruto a 25.0 W).
- **GPU v2 E2E (Pinned)**: 5.01 GB/s, 3.17 $\pm$ 0.02 J/GB neto (4.57 J/GB bruto a 19.9 W).
- **GPU v2 E2E (Pageable)**: 3.94 GB/s (-21.4% vs Pinned).
- **Pico Kernel GPU**: 22.29 GB/s en $C=64$~KB.
- **Pico E2E GPU**: 5.87 GB/s en $C=4$~KB.

## TODOs Restantes en el Documento
1. Filas de `\TODO{}` para Spartan-7 FPGA en `Paper/tab_comparison.tex` (línea 18) y Tabla FPGA en `Paper/IEEE_es.tex` (reservadas para el equipo de hardware).

## Comandos de Reproducción
```bash
# Generar tablas y macros desde CSV
python3 tools/generate_latex_tables.py

# Generar gráficos académicos
python3 tools/analyze_results.py
python3 Paper/generate_plots.py

# Compilar PDF del paper
cd Paper && ./tectonic IEEE_es.tex
```
