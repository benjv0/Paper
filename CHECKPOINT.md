# CHECKPOINT — 2026-10-16T11:10

## Estado de Fases
- **Fase A (Auditoría)**: Completada al 100%. Ver `AUDITORIA.md` para el desglose detallado.
  - Workload y métricas auditados: $N$, $B$, `output_mode=full`, kernel-only $\ge$ E2E verificados.
  - Verificación formal de digests contra NIST y Python `hashlib` (10,100 fragmentos) completada exitosamente.
  - Discrepancias identificadas: Telemetría de energía en CPU (RAPL permiso de lectura) y GPU (desajuste de versiones NVML) no disponibles en el entorno de ejecución actual (requieren permisos sudo / reinicio del SO).
  - Explicación de la diferencia de throughput de CPU frente a números anteriores: el benchmark anterior evaluaba 1 GB en un único mensaje sin sobrecarga de padding, mientras que el benchmark actual evalúa $16\,777\,216$ fragmentos independientes de $C=64$~B con $B=2$ bloques por fragmento (el doble de bloques de compresión requeridos).
- **Fase B (Corrección)**: Completada al 100%.
  - Speedup anclado unívocamente a SHA-NI 4T E2E ($C=64$~B, 1.70 GB/s), con Escalar 1T rotulado como referencia secundaria.
  - Generación de tablas desacoplada mediante script automatizado (`tools/generate_latex_tables.py`) que lee directamente de `results/benchmarks_summary.csv` y genera tablas con `\resizebox{\columnwidth}{!}{...}` individuales y combinadas.
  - Erratas de texto corregidas ("InteL", "geométrica", frecuencias dinámicas documentadas bajo governor `powersave`).
- **Fase C (Fase 7, Redacción en LaTeX)**: Completada al 100%.
  - `Paper/IEEE_es.tex` redactado rigurosamente siguiendo los 11 puntos de la especificación.
  - Tablas generadas por script e incluidas vía `\input` (`tab_cpu_results`, `tab_cpu_sweep`, `tab_gpu_ablation`, `tab_gpu_staging`, `tab_comparison`).
  - Gráficos regenerados y sincronizados (`throughput_vs_c.pdf`, `throughput_chart.pdf`).
  - Documento compilado con `tectonic` a `Paper/IEEE_es.pdf` sin errores.

## Mediciones Pendientes para rellenar \TODO{} (requieren intervención de usuario)
1. **Energía CPU (RAPL)**:
   ```bash
   sudo chmod 444 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
   python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5
   ```
2. **Energía GPU (NVML)**:
   Reiniciar la máquina física para sincronizar el módulo de kernel NVIDIA con la biblioteca NVML, luego ejecutar:
   ```bash
   python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5 --sweep-c
   ```
3. **Regenerar tablas y recompilar**:
   ```bash
   python3 tools/generate_latex_tables.py
   python3 tools/analyze_results.py
   python3 Paper/generate_plots.py
   cd Paper && ./tectonic IEEE_es.tex
   ```
