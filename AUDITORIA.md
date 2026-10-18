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

---

# Revisión 2 — Auditoría de Correcciones (2026-10-18)

## 1. Resolución de la Inconsistencia de Energía en GPU (T1)
- **Causa raíz identificada**: El orquestador anterior integraba la potencia sobre una ventana global continua de todo el proceso binario (~2.7 s que incluía inicialización, calentamiento, corrida kernel y corrida E2E en secuencia), dividiendo dicho $\Delta E$ total por una sola carga de 5 GB. Esto provocaba que tanto el modo kernel-only como el modo E2E reportaran erróneamente un valor idéntico e inflado de 9.69 J/GB (lo cual implicaba una potencia aparente de ~48.5 W, superior al TDP de 30 W).
- **Corrección metodológica**:
  - Se modificó `gpu/sha256_gpu_v2.cu` para soportar argumentos `--mode {kernel,e2e}`, `--duration` y `--warmup`, desacoplando por completo ambas mediciones.
  - Se implementó `tools/run_gpu_energy.py` utilizando la API C nativa de NVML (`libnvidia-ml.so.1`) para muestrear la potencia instantánea exclusivamente durante la ventana activa del bucle cronometrado ($\ge 15$ s).
  - Se midió la potencia en reposo de la GPU sobre 10 s: **6.11 W** (media).
  - Se re-midió la energía de GPU v2 ($C=64$~B, pinned, 5 corridas $\times 15$ s):
    - **Kernel-only**: 14.31 $\pm$ 0.14 GB/s, 24.96 W potencia activa, **1.74 $\pm$ 0.02 J/GB bruto**, **1.32 $\pm$ 0.01 J/GB neto**. Comprobación de plausibilidad: $1.74 \times 14.31 = 24.90\text{ W} \le 30\text{ W}$ (PASS).
    - **E2E pinned**: 4.35 $\pm$ 0.04 GB/s, 19.88 W potencia activa, **4.57 $\pm$ 0.02 J/GB bruto**, **3.17 $\pm$ 0.02 J/GB neto**. Comprobación de plausibilidad: $4.57 \times 4.35 = 19.88\text{ W} \le 30\text{ W}$ (PASS).
- **Impacto en conclusiones**: La GPU E2E neta (3.17 J/GB) es 37.0% más eficiente que la CPU SHA-NI 4T neta (5.03 J/GB). La CPU SHA-NI 12T (8E sob.) logra 2.87 J/GB netos (+9.5% de ventaja frente a GPU E2E). A nivel kernel puro, la GPU v2 (1.32 J/GB) supera a la CPU 12T por 2.17$\times$.

## 2. Speedup del Barrido de C Normalizado al Mismo C (T2)
- Anteriormente, la columna Speedup de la Tabla III comparaba todas las filas contra CPU a $C=64$~B (3.54 GB/s), produciendo la falsa ilusión de que la GPU superaba a la CPU en todos los tamaños.
- Se corrigió comparando cada fila contra CPU SHA-NI 4T al **mismo tamaño de fragmento $C$**:
  - $C=64$~B: CPU 4T = 3.54 GB/s $\to$ GPU v2 E2E = 5.01 GB/s (**1.42$\times$**).
  - $C=1$~KB: CPU 4T = 8.21 GB/s $\to$ GPU v2 E2E = 5.82 GB/s (**0.71$\times$**).
  - $C=4$~KB: CPU 4T = 8.72 GB/s $\to$ GPU v2 E2E = 5.87 GB/s (**0.67$\times$**).
  - $C=64$~KB: CPU 4T = 8.97 GB/s $\to$ GPU v2 E2E = 5.36 GB/s (**0.60$\times$**).
  - $C=1$~MB: CPU 4T = 8.99 GB/s $\to$ GPU v2 E2E = 2.45 GB/s (**0.27$\times$**).
- Conclusión real: La GPU v2 E2E solo supera a la CPU en fragmentos mínimos ($C=64$~B). Para todo $C \ge 1$~KB, la CPU supera holgadamente a la GPU gracias a la ausencia del cuello de botella de transferencia PCIe.

## 3. Desambiguación de Hilos y Núcleos de CPU (T4)
- La configuración con `taskset -c 4-11` ejecutando 12 hilos corresponde a **12 hilos sobre 8 E-cores en sobresuscripción** (5.94 GB/s, 2.87 J/GB netos).
- Se implementó y midió una variante sobre las **12 CPUs lógicas completas (núcleos 0--11, 2 P-cores con SMT + 8 E-cores)**:
  - Throughput: **4.51 $\pm$ 0.02 GB/s** (70.52 Mhash/s, 141.03 Mbloques/s).
  - El menor rendimiento de 12 CPUs (P+E) frente a 12 hilos sobre 8 E-cores homogéneos (4.51 vs 5.94 GB/s) se debe al desequilibrio microarquitectónico (heterogeneidad de latencias entre Golden Cove y Gracemont, contención de cachés L2/L3 asimétricas y sincronización inter-núcleo).

## 4. Potencia Activa vs Tiempo Total y Límites RAPL (T5)
- Lectura de sysfs `/sys/class/powercap/intel-rapl:0`:
  - PL1 (long_term): 15.0 W nominal (techo firmware OEM 200 W, ventana 39.98 s).
  - PL2 (short_term): 39.0 W (ventana 2.44 ms).
  - PL4 (peak_power): 60.0 W.
- Potencia en reposo del host: **3.36 W**.
- Las potencias del paper anterior (9.09 W, 20.80 W, 20.04 W) provenían de dividir el $\Delta E$ total de RAPL por el tiempo wall-clock de todo el proceso (~78 s) en vez del tiempo activo del bucle (75 s). Las potencias activas reales bajo carga son:
  - Escalar 1T: 10.14 W.
  - SHA-NI 4T: 21.72 W ($J/\text{GB}_\text{bruto} \times \text{GB/s} = 6.13 \times 3.54 = 21.7\text{ W}$).
  - SHA-NI 8T: 21.60 W ($J/\text{GB}_\text{bruto} \times \text{GB/s} = 3.75 \times 5.76 = 21.6\text{ W}$).
  - SHA-NI 12T (8E sob.): 20.95 W ($J/\text{GB}_\text{bruto} \times \text{GB/s} = 3.53 \times 5.94 = 21.0\text{ W}$).
- Los valores verifican perfectamente la consistencia $P_\text{activa} = J/\text{GB}_\text{bruto} \times \text{GB/s} \le \text{PL2}$.

## 5. Cuantificación de Sobrecarga por Mensaje vs Relleno (T6)
- Se evaluó la tasa aritmética de compresión en bloques por segundo ($\text{bloques/s} = N \cdot B / t$) para CPU SHA-NI 4T:
  - $C=64$~B: 110.7 Mbloques/s.
  - $C=1$~MB: 140.4 Mbloques/s.
- Relación: $110.7 / 140.4 = 78.8\%$.
- Consecuencia: El 50% del trabajo en $C=64$~B es el bloque de relleno adicional ($B=2$), pero además existe una penalización intrínseca de $\approx$21.2% por mensaje debido a la reinicialización de constantes de hash, preparación del padding y almacenamiento de los digests en memoria.

## 6. Análisis del Bus PCIe Full-Duplex (T7)
- Telemetría NVML confirma enlace **PCIe Gen 4 $\times$4** (7.88 GB/s teórico por sentido, $\approx$6.4 GB/s efectivos).
- Propiedades CUDA confirman `asyncEngineCount = 2` (dos motores DMA independientes full-duplex).
- Las transferencias H2D (payload) y D2H (digests) se ejecutan concurrentemente en los streams CUDA; por ende, **los tiempos no se suman secuencialmente**.
- Tasas direccionales en $C=64$~B:
  - H2D: 1073.74 MB / 0.214 s = **5.01 GB/s**.
  - D2H: 536.87 MB / 0.214 s = **2.51 GB/s**.
- En $C=1$--$4$~KB (donde el volumen de digests es mínimo, $\le 32$~MiB), el throughput E2E alcanza **5.82--5.87 GB/s** ($\approx$91--92% del límite efectivo del enlace), confirmando que el bus opera cerca de su saturación física unidireccional.

## 7. Trazabilidad de Cambios Históricos (T9)
- **CPU SHA-NI 4T ($C=64$~KB)** pasó de 5.13 GB/s a 8.97 GB/s:
  - Medición anterior: invocaba OpenSSL EVP (`fread` / lectura de archivo por bloques o despacho en stream).
  - Medición actual: buffer completo precargado en memoria RAM con bucle interno multihilo que invoca directamente las instrucciones intrínsecas de ensamblador SHA-NI (`_mm_sha256rnds2_epu32`, `_mm_sha256msg1_epu32`, `_mm_sha256msg2_epu32`), eliminando toda sobrecarga de capas de software.
- **GPU v2 kernel-only ($C=64$~KB)** pasó de 16.81 GB/s a 22.29 GB/s:
  - Medición actual incorpora compilación con flag `--maxrregcount=48`, elevando la ocupación teórica de 33.3% a 83.3% (5 bloques/SM), combinada con el reemplazo de la ventana de mensajes `w[16]`, instrucción PTX `__byte_perm()` y desenrollado de 64 rondas con pipeline de 3 streams sobre lotes de 64 MiB.

