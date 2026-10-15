# Benchmark y Aceleración Criptográfica SHA-256 en CPU (SHA-NI) y GPU (CUDA)

Este repositorio contiene la suite de benchmarking riguroso para la evaluación del algoritmo SHA-256 en arquitecturas heterogéneas (CPU Intel Alder Lake y GPU NVIDIA RTX 2050), con soporte para hashing por fragmentos independientes, medición de throughput, energía (RAPL / NVML) y verificación criptográfica formal frente a vectores de prueba del NIST y `hashlib` / OpenSSL.

---

## 1. Plataforma de Hardware y Entorno

- **CPU:** Intel Core i7-1255U (10 núcleos: 2 P-cores + 8 E-cores, 12 hilos lógicos). Soporte nativo para instrucciones **SHA-NI** (`-msha`).
  - E-cores fijados vía sysfs (`/sys/devices/cpu_atom/cpus` $\to$ CPUs 4–11).
  - Telemetría de energía: Dominio Intel RAPL PKG (`/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`).
- **GPU:** NVIDIA GeForce RTX 2050 Mobile (GA107M, Ampere, `sm_86`, 16 SMs, 2048 CUDA cores).
  - Kernel v1: Baseline con expansión estándar $w[64]$ en memoria local.
  - Kernel v2: Alta utilización con ventana deslizante circular $w[16]$, `--maxrregcount=48`, constantes en memoria `__constant__`, desenrollado `#pragma unroll 64`, permutación de bytes en 1 instrucción `__byte_perm()`, bucle grid-stride, memoria host fijada (*pinned*) y pipeline asíncrono de 3 streams CUDA.

---

## 2. Decisión de Diseño del Workload (Hashing por Fragmentos)

El archivo de datos `dummy_1GB.bin` tiene un tamaño exacto de **1,073,741,824 bytes** ($2^{30}$ bytes = 1 GiB).
Se divide en $N = \lfloor 1073741824 / C \rfloor$ fragmentos independientes de $C$ bytes, generando un arreglo contiguo de digests de $N \times 32$ bytes.
Cada mensaje requiere $B = \lceil (C + 9) / 64 \rceil$ bloques de compresión SHA-256 de 64 bytes.

- **Escenario Principal:** $C = 64$ B ($N = 16,777,216$ fragmentos; $B = 2$ bloques; payload útil = 1,073,741,824 bytes; digests = 512 MiB).
- **Barrido de $C$:** 64 B, 1 KB (1,024 B), 4 KB (4,096 B), 64 KB (65,536 B) y 1 MB (1,048,576 B).

### Modos de Salida y Staging:
- `--output-mode full` (por defecto): Escribe los $N \times 32$ bytes en memoria host (en GPU incluye D2H).
- `--output-mode reduce`: Realiza reducción XOR de los $N$ digests en el dispositivo, retornando un digest de 32 bytes para aislar el rendimiento del bus.
- `--staging pinned`: Buffer fijado en memoria (*page-locked* vía `cudaMallocHost`).
- `--staging pageable`: Buffer paginable (`malloc`), incluyendo la copia de *staging* pageable $\to$ pinned en la medición E2E.

---

## 3. Compilación

```bash
# Compilar benchmark CPU (Scalar C y SHA-NI)
make -C cpu all

# Compilar kernels GPU (v1 y v2) con registro de ptxas
make -C gpu all
```

---

## 4. Verificación de Correctitud Criptográfica

Antes de medir, cada implementación valida los 4 vectores estándar del NIST (cadena vacía, `"abc"`, vector de 448 bits y 1,000,000 de `'a'`), y compara los digests generados frente a `hashlib.sha256`:

```bash
# 1. Verificar vectores NIST
python3 tools/verify_digests.py --nist-only

# 2. Verificar digests completos (16,777,216 fragmentos) de dummy_1GB.bin
./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl shani --threads 4 --chunk-size 64 --runs 1 --save-digests /tmp/digests.bin
python3 tools/verify_digests.py --data-file dummy_1GB.bin --digests-file /tmp/digests.bin --chunk-size 64
```

---

## 5. Ejecución del Benchmark

### 5.1 Suite Completa Automatizada

```bash
# Modo completo con protocolo (calentamiento 3s + >=15s de ejecución x 5 corridas)
python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5 --sweep-c

# Modo rápido preliminar (smoke test)
python3 tools/run_benchmarks.py --quick
```

### 5.2 Comandos Individuales

#### CPU (Escalar y SHA-NI con afinidad a E-cores):
```bash
# SHA-NI con 4 hilos fijados a E-cores (CPUs 4,5,6,7)
./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl shani --threads 4 --cores 4,5,6,7 --chunk-size 64 --duration 15.0 --runs 5

# Escalar 1 hilo (baseline secundario)
./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl scalar --threads 1 --cores 4 --chunk-size 64 --duration 15.0 --runs 5
```

#### GPU (Kernel v1 y v2):
```bash
# GPU v1 Baseline (pinned, C=64 B)
./gpu/sha256_gpu --file dummy_1GB.bin --chunk-size 64 --staging pinned --runs 5

# GPU v2 Alta Utilización (pinned, C=64 B, lote de 64 MiB por stream)
./gpu/sha256_gpu_v2 --file dummy_1GB.bin --chunk-size 64 --staging pinned --batch-size 67108864 --runs 5
```

---

## 6. Generación de Tablas LaTeX y Figuras

```bash
# Generar tablas para el paper en results/latex_tables.tex y gráfico Throughput vs C
python3 tools/analyze_results.py

# Regenerar figuras para el documento PDF
python3 Paper/generate_plots.py
```

---

## 7. Notas sobre Telemetría de Energía

- **Intel RAPL:** El contador `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` en Ubuntu requiere permisos de lectura (`sudo chmod 444 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` o ejecutar con `sudo`). El orquestador maneja desbordamientos y mide el consumo en reposo durante 10 s para computar energía bruta y neta.
- **NVIDIA NVML:** Si existe una discrepancia entre la versión del módulo de kernel y la biblioteca (`Driver/library version mismatch`), reiniciar el equipo para habilitar las lecturas de potencia de `nvidia-smi` / NVML. Las métricas de tiempo y throughput vía CUDA Events funcionan con precisión de microsegundos en todo momento.
