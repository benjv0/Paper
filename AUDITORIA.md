# Auditoría del Benchmark SHA-256 — Fase A

## (i) Lo que está correcto

1. **Workload**: `dummy_1GB.bin` = 1,073,741,824 bytes (2³⁰). N = floor(2³⁰/C) verificado para todo C. B = ceil((C+9)/64) consistente.
2. **Output mode**: `full` en todas las mediciones (arreglo completo de digests).
3. **Barrido de C**: 64 B, 1 KB, 4 KB, 64 KB, 1 MB — tanto en CPU (4T) como en GPU (v1/v2, pinned/pageable, kernel-only/E2E).
4. **CPU variantes C=64**: SCALAR_1T, SHANI_1T/2T/4T/8T/12T. Hilos fijados a E-cores (CPUs 4–11).
5. **GPU variantes**: v1 y v2, kernel-only vs E2E, staging pinned vs pageable.
6. **NIST verification**: Built into `sha256_cpu_bench` y `sha256_gpu_v2`; aborts on failure. Benchmarks ran to completion ⇒ NIST passed.
7. **Chunk digest verification**: Confirmed 10,100 SHA-NI digests (first 10K + last 100) match `hashlib.sha256` — **PASS**.
8. **Kernel-only ≥ E2E**: Verified for all GPU configurations — **OK**.
9. **N consistency across CPU/GPU**: Same N for same C — **OK**.
10. **Occupancy analysis**: ptxas data properly captured (v1: 33.3%, v2: 83.3%).

## (ii) Discrepancias con la especificación

| # | Discrepancia | Severidad | Acción |
|---|-------------|-----------|--------|
| D1 | **Energía CPU = N/A**: RAPL PKG no pudo leer (permisos). Toda columna J_GB es N/A. | Alta | No se puede corregir sin `sudo`. Marcar como `\TODO{}` en LaTeX. **Dato antiguo disponible**: SHA-NI 4T ≈ 5.17 J/GB (workload single-message, no comparable). |
| D2 | **Energía GPU = "NVML driver mismatch"**: Requiere reiniciar para sincronizar driver/lib. Toda métrica J/GB GPU es N/A. | Alta | Misma situación. Marcar como `\TODO{}`. |
| D3 | **Sin idle power baseline**: El protocolo exige reposo 10 s + energía bruta/neta. Sin RAPL/NVML, no existe. | Alta | Consecuencia de D1/D2. |
| D4 | **Iteraciones de SCALAR_1T = 3.0**: Con throughput 0.0675 GB/s, procesar 1 GiB toma ~15.8 s, así que 3 iteraciones × 15.8 s ≈ 47 s total. Cumple ≥15 s. | Info | OK. |
| D5 | **5 repeticiones**: El CSV es un resumen (mean ± sd). No hay raw CSV con las 5 corridas individuales para las nuevas mediciones. La sd implica que se hicieron, pero no hay evidencia directa. | Baja | Aceptable: las sd son consistentes con 5 muestras. |
| D6 | **CPU throughput ≠ referencia anterior**: SHA-NI 4T ahora = 1.70 GB/s (antes 5.13 GB/s), Scalar 1T = 0.0675 (antes 0.19). **CAUSA**: el workload cambió de single-message (1 bloque de padding para 1 GB) a chunked (B=2 bloques por 64 B de payload). El nuevo workload hace ~2× más bloques de compresión por byte de payload, más overhead de inicialización por mensaje. Los números son correctos para el workload chunked. | Info | Documentar en el paper que la comparación directa con mediciones anteriores no aplica por cambio de workload. |
| D7 | **LaTeX paper tiene datos OLD**: Tablas tab:cpu, tab:gpu_v1, tab:gpu_v2, tab:gpu_energy contienen números del benchmark anterior (chunks 4KB–256KB, throughput en MB/s). Deben reemplazarse completamente. | Alta | Reescribir en Fase C. |
| D8 | **Speedup anchor OLD**: Paper dice "speedup vs CPU SW 1T (189.73 MB/s)". Debe ser vs SHA-NI 4T según spec. | Alta | Corregir en Fase C. |
| D9 | **PCIe link**: No hay dato medido de generación/ancho PCIe en los CSV/logs. Paper dice "Gen 4 ×4" pero no hay evidencia de medición runtime. `nvidia-smi` no funciona (NVML mismatch). | Media | Usar dato del hardware spec; marcar como no medido runtime. |
| D10 | **Frecuencias CPU reportadas** en CSV: SCALAR_1T=400 MHz, SHA-NI_4T=400 MHz, etc. — parece que se leyó la frecuencia mínima del governor `powersave`, no la frecuencia real bajo carga. SHA-NI 4T C=1MB muestra 559 MHz. Frase "fijados vía a 3.5 GHz" en el paper es incorrecta. | Media | Corregir la frase; reportar governor powersave y que la frecuencia no fue fijada. |
| D11 | **12T config no en la spec**: SHANI_12T aparece en los datos pero no estaba en la especificación (que pide 1T/2T/4T/8T). | Baja | Incluir como dato extra en la tabla. |
| D12 | **Texto duplicado III.B.2 y IV.B**: No existe aún en las secciones actuales, pero III.B (Subsección GPU) ya tiene una descripción extensa de optimizaciones v2 que se replicará si no se maneja bien. | Media | En Fase C, optimizaciones en III, resultados en IV. |

## (iii) Anomalías de datos

| # | Anomalía | Valoración |
|---|---------|-----------|
| A1 | GPU_V2 C=1024 pinned kernel-only: sd=3.15 (19.7% del mean=16.04). | ⚠ Alto sd. Posible thermal throttling o scheduling transient. Los datos E2E correspondientes tienen sd normal (0.009). Mantener con nota. |
| A2 | GPU_V2 C=1024 pageable kernel-only: sd=2.02 (11% del mean=18.41). | ⚠ Marginal. Mismo fenómeno que A1. |
| A3 | Pageable kernel-only a veces supera pinned kernel-only (v2, C=64: 13.28 vs 12.89; C=1024: 18.41 vs 16.04). | El staging no debería afectar kernel-only (datos ya en VRAM). La diferencia sugiere scheduling variability entre runs, no un efecto real. |
| A4 | GPU v2 C=1MB: throughput kernel-only (3.38) ≈ v1 (3.31). La ventaja v2 desaparece porque con N=1024 chunks hay insuficiente paralelismo para saturar los SMs. | Esperado — coherente con la teoría. |

## (iv) Correcciones aplicadas y pendientes

### Aplicadas en esta sesión:
- ✅ Verificación de digests contra hashlib (10,100 chunks) — PASS
- ✅ Verificación NIST via script independiente — PASS

### Pendientes (requieren acción del usuario):
- ⏳ **Energía CPU**: Ejecutar benchmark con `sudo` para leer RAPL PKG, o `sudo chmod 444` el archivo RAPL.
- ⏳ **Energía GPU**: Reiniciar el equipo para resolver NVML driver/library mismatch, luego re-ejecutar benchmarks GPU.
- ⏳ **PCIe link**: Tras reinicio, ejecutar `nvidia-smi -q | grep -A5 -i pcie` para confirmar Gen/Width.
- ⏳ **Frecuencias reales**: Fijar governor a `performance` y/o leer frecuencias bajo carga, o reportar que se usó governor `powersave`.

### Comandos para recuperar datos faltantes (tras reinicio/permisos):
```bash
# 1. Energía CPU (requiere sudo o chmod)
sudo chmod 444 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5

# 2. Energía GPU (requiere reinicio previo)
# Tras reiniciar:
python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5 --sweep-c

# 3. PCIe link
nvidia-smi -q | grep -A5 -i pcie
```
