# CPU SHA-256 Benchmark

Benchmark de SHA-256 en CPU para el paper de aceleradores criptográficos.  
Plataforma: **Intel Core i7-1255U** (12th Gen Alder Lake) — SHA-NI, E-cores/P-cores.

## Implementaciones

| Archivo | Descripción |
|---------|-------------|
| `sha256_sw.c` | SHA-256 en C puro, single-thread, sin SHA-NI (`-mno-sha`) |
| `sha256_hw.c` | SHA-256 via OpenSSL EVP (usa SHA-NI automáticamente), single-thread |
| `sha256_mt_sw.c` | SHA-256 en C puro, multi-thread (pthreads) |
| `sha256_mt_hw.c` | SHA-256 via OpenSSL EVP, multi-thread (pthreads) |
| `benchmark.py` | Orquestador: RAPL, métricas, CSV |
| `Makefile` | Compilación y ejecución |

## Compilar

```bash
make all
```

## Ejecutar

```bash
# Sin medición de energía (no requiere sudo)
make run FILE=./dummy_1GB.bin

# Con medición RAPL (requiere sudo)
make run-sudo FILE=./dummy_1GB.bin
```

## Configuración del benchmark

- **Threads:** 1, 2, 4 E-cores (CPUs 4–7, 3500 MHz)
- **CPU pinning:** `taskset` fija cada proceso exclusivamente a E-cores
- **Energía:** Intel RAPL package domain (`/sys/class/powercap/intel-rapl:0/`)
- **Runs:** 5 por configuración (media ± σ)
- **Buffer:** 4 MB por lectura (fits in L3 cache)

## Resultados (Intel i7-1255U, E-cores, 2026-07-17)

| Config | Threads | Throughput (MB/s) | J/GB | Speedup vs SW_1T | Scale Eff. |
|--------|---------|------------------|------|-----------------|------------|
| SW_1T  | 1       | 189.73           | 69.76 | 1.00×          | —          |
| SW_2T  | 2       | 372.18           | 44.23 | 1.96×          | 98.1%      |
| SW_4T  | 4       | 735.65           | 32.89 | 3.88×          | 96.9%      |
| HW_1T  | 1       | 1763.18          | 7.00  | 9.29×          | —          |
| HW_2T  | 2       | 3315.00          | 5.37  | 17.47×         | 94.0%      |
| HW_4T  | 4       | 5126.07          | 5.17  | 27.02×         | 72.7%      |

Los datos por run están en `results/`.

## Verificar correctitud

```bash
make verify
```
Compara el hash SHA-256 producido por cada implementación contra `sha256sum` del sistema.
