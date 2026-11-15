# SHA-256 en CPU (SHA-NI), GPU (CUDA) y FPGA (Spartan-7): código, datos y reportes

Repositorio de acompañamiento del artículo

> **Desarrollo y evaluación de un Acelerador Criptográfico para el Algoritmo SHA-2 en Hardware Reconfigurable**
> Benjamín Oyarzún Valdebenito, Nicolás Ruminot Ahumada y Christian Fernández-Campusano.
> Departamento de Ingeniería Eléctrica, Universidad de Santiago de Chile.

Aquí está todo lo necesario para revisar o reproducir los resultados del artículo: el código de los benchmarks de CPU y GPU, el RTL y los reportes de Vivado de la FPGA, los datos crudos y resumidos de cada medición, y los scripts que generan las tablas y figuras.

- **Artículo (PDF, versión extendida en español):** [`Paper/IEEE_es.pdf`](Paper/IEEE_es.pdf)
- **Fuente LaTeX:** [`Paper/IEEE_es.tex`](Paper/IEEE_es.tex) (modular) y [`Paper/main.tex`](Paper/main.tex) (un solo archivo, para Overleaf)

---

## 1. Qué se evalúa

El artículo compara SHA-256 en tres plataformas con **la misma carga de trabajo**: un flujo masivo de mensajes cortos e independientes de 64 B, representativo de la validación de paquetes y de árboles de Merkle. No propone una arquitectura nueva; el aporte es medir las tres plataformas con el mismo mensaje, el mismo protocolo y las mismas métricas.

| | CPU | GPU | FPGA |
|---|---|---|---|
| Dispositivo | Intel Core i7-1255U (Alder Lake) | NVIDIA GeForce RTX 2050 móvil (Ampere GA107M) | AMD Spartan-7 xc7s100 (placa SP701) |
| Cómputo | 2 P-cores + 8 E-cores, 12 hilos | 16 SM, 2 048 núcleos CUDA | 64 000 LUT |
| Implementación | C con instrucciones SHA-NI, 1 a 12 hilos | kernels CUDA v1 y v2 | Verilog RTL, 1 a 24 núcleos replicados |
| Frecuencia | variable | variable | 100 MHz fija |
| Herramientas | GCC 15.2 | CUDA 12.4 | Vivado 2026.1 |
| Fuente de potencia | Intel RAPL (paquete), **medida** | NVML (tarjeta), **medida** | análisis de potencia de Vivado, **estimada** |

CPU y GPU comparten el mismo equipo portátil (Ubuntu 26.04 LTS, núcleo Linux 7.0, controlador NVIDIA 595.99.02). El entorno completo está registrado en [`results/env.txt`](results/env.txt).

---

## 2. Resultados principales (C = 64 B)

| Plataforma / configuración | Throughput (GB/s) | Mhash/s | J/GB neto (dispositivo) | J/GB neto (+host) |
|---|---|---|---|---|
| CPU escalar, 1 hilo | 0.11 | 1.71 | 45.58 | 45.58 |
| CPU SHA-NI, 1 hilo | 0.89 | 13.90 | 5.28 | 5.28 |
| CPU SHA-NI, 4 hilos (referencia) | 3.55 | 55.45 | 4.13 | 4.13 |
| CPU SHA-NI, 8 hilos | 5.60 | 87.45 | 2.67 | 2.67 |
| CPU SHA-NI, 12 CPUs (P+E) | 5.84 | 91.25 | 2.53 | 2.53 |
| GPU v2, solo kernel | 15.62 | 244.02 | 1.62 | 2.45 |
| GPU v2, extremo a extremo (pinned) | 4.98 | 77.86 | 3.49 | 5.48 |
| FPGA Spartan-7, 1 núcleo | 0.047 | 0.735 | 0.74 (estimado) | — |
| FPGA Spartan-7, 24 núcleos | 1.129 | 17.647 | 0.77 (0.75–0.80, estimado y extrapolado) | — |

Cómo leer esta tabla:

- **Las cifras de energía de la FPGA no son mediciones físicas.** Son estimaciones del análisis de potencia de Vivado sobre el diseño ruteado: con actividad de simulación (SAIF) para N = 1, 4 y 8, y extrapoladas para N = 16 y 24 (el rango entre paréntesis es el de los dos métodos de extrapolación). Las de CPU y GPU sí son medidas en hardware.
- **La FPGA solo es comparable con la GPU "solo kernel"**, no con las cifras extremo a extremo: los mensajes se generan dentro del chip y no hay una interfaz de datos hacia el anfitrión (solo JTAG para leer contadores).
- "Neto" descuenta la potencia en reposo (5.15 W en CPU, 4.44 W en GPU); en la FPGA equivale a la potencia dinámica del bloque. Con la estática del chip (0.090 W), la energía bruta de la FPGA es 2.66 J/GB (N = 1) y 0.85 J/GB (N = 24).
- El throughput de la FPGA con 24 núcleos es 5.2 veces menor que el de la CPU con 12 CPUs y 13.8 veces menor que el de la GPU en solo kernel.

Los valores con su desviación estándar, el barrido de tamaño de fragmento y el escalado FPGA completo están en el artículo y en los archivos de la sección siguiente.

---

## 3. Del artículo al repositorio

Numeración según [`Paper/IEEE_es.pdf`](Paper/IEEE_es.pdf).

| En el artículo | Datos de origen | Tabla / script que lo genera |
|---|---|---|
| Tabla I — qué se paraleliza en cada plataforma | — | [`Paper/tab_strategy.tex`](Paper/tab_strategy.tex) |
| Tabla II — plataforma experimental | [`results/env.txt`](results/env.txt) | [`Paper/tab_setup.tex`](Paper/tab_setup.tex) |
| Tabla III — barrido de tamaño de fragmento C | [`results/benchmarks_summary.csv`](results/benchmarks_summary.csv) | [`Paper/tab_c_sweep.tex`](Paper/tab_c_sweep.tex) |
| Tabla IV — impacto del staging en GPU v2 | [`results/benchmarks_summary.csv`](results/benchmarks_summary.csv), [`results/gpu_unified_results.json`](results/gpu_unified_results.json) | [`Paper/tab_gpu_staging.tex`](Paper/tab_gpu_staging.tex) |
| Tabla V — comparación cruzada | [`results/benchmarks_summary.csv`](results/benchmarks_summary.csv), [`FPGA/resumen_escalado.csv`](FPGA/resumen_escalado.csv) | [`Paper/tab_comparison.tex`](Paper/tab_comparison.tex) |
| Tabla VI — escalado multinúcleo en FPGA | [`FPGA/resumen_escalado.csv`](FPGA/resumen_escalado.csv) y reportes en `FPGA/N=*/` | [`Paper/tab_fpga_scaling.tex`](Paper/tab_fpga_scaling.tex) |
| Tabla VII — trabajos FPGA de la literatura | artículos citados ([`Paper/references.bib`](Paper/references.bib)) | [`Paper/tab_fpga_lit.tex`](Paper/tab_fpga_lit.tex) |
| Figura 1 — resultados de CPU | [`results/benchmarks_summary.csv`](results/benchmarks_summary.csv) | [`Paper/plot_results_summary.py`](Paper/plot_results_summary.py) → `cpu_scaling.pdf` |
| Figura 2 — throughput vs. C | [`results/benchmarks_summary.csv`](results/benchmarks_summary.csv) | [`tools/analyze_results.py`](tools/analyze_results.py) → `throughput_vs_c.pdf` |
| Figura 3 — comparación entre plataformas | ambos CSV | [`Paper/plot_results_summary.py`](Paper/plot_results_summary.py) → `platform_comparison.pdf` |
| Figura 4 — escalado FPGA | ambos CSV | [`Paper/plot_fpga_scaling.py`](Paper/plot_fpga_scaling.py) → `fpga_scaling.pdf` |

Los valores numéricos que aparecen en el texto del artículo salen de [`Paper/macros.tex`](Paper/macros.tex), generado a partir de `results/benchmarks_summary.csv` por [`tools/generate_latex_tables.py`](tools/generate_latex_tables.py).

---

## 4. Estructura del repositorio

```
common/     Cabeceras compartidas: carga de trabajo, afinidad de CPU, vectores NIST
cpu/        Benchmark de CPU (escalar y SHA-NI, mono y multihilo) y sus resultados crudos
gpu/        Kernels CUDA v1 y v2, y un documento explicativo de la paralelización
tools/      Orquestación de mediciones, telemetría de energía, verificación y análisis
results/    Resultados consolidados de CPU y GPU (CSV, JSON, entorno, tablas)
FPGA/       RTL, testbenches, scripts y reportes de Vivado por número de núcleos
Paper/      Fuente LaTeX del artículo, tablas, figuras y scripts de gráficos
```

Otros archivos: [`AUDITORIA.md`](AUDITORIA.md) y [`CHECKPOINT.md`](CHECKPOINT.md) registran las revisiones internas de las mediciones; `Paper/archive/` guarda versiones anteriores del artículo.

---

## 5. Reproducir las mediciones de CPU y GPU

### 5.1 Requisitos

- Linux x86-64 con una CPU con SHA-NI. Los scripts fijan los hilos a los E-cores leyendo `/sys/devices/cpu_atom/cpus` (CPUs 4–11 en el i7-1255U); en otro procesador hay que indicar los núcleos con `--cores`.
- GCC y, para la GPU, el toolkit CUDA con `nvcc`. El `Makefile` de GPU compila para `sm_86`.
- Python 3 con `numpy`, `pandas` y `matplotlib`.
- Lectura de energía: Intel RAPL (`/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`) y NVML.

### 5.2 Archivo de datos

El archivo de entrada `dummy_1GB.bin` (exactamente 1 073 741 824 bytes, 2³⁰) **no está en el repositorio** por su tamaño. El del artículo se generó con un PRNG de semilla fija. Cualquier archivo de ese tamaño sirve para ejecutar los benchmarks, por ejemplo:

```bash
head -c 1073741824 /dev/urandom > dummy_1GB.bin
```

Con un archivo distinto los digests cambian, pero la verificación sigue siendo válida porque se compara contra `hashlib` sobre el mismo archivo.

El archivo se divide en N = ⌊2³⁰ / C⌋ fragmentos independientes de C bytes; cada uno requiere B = ⌈(C + 9) / 64⌉ bloques de compresión. El escenario principal es C = 64 B (N = 16 777 216, B = 2) y el barrido cubre 64 B, 1 KB, 4 KB, 64 KB y 1 MB.

### 5.3 Compilación

```bash
make -C cpu all     # escalar y SHA-NI
make -C gpu all     # kernels v1 y v2 (guarda el registro de ptxas)
```

### 5.4 Verificación de correctitud

Cada implementación valida los 4 vectores estándar del NIST antes de medir, y todos los digests se comparan con `hashlib.sha256`:

```bash
python3 tools/verify_digests.py --nist-only

./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl shani --threads 4 --chunk-size 64 --runs 1 --save-digests /tmp/digests.bin
python3 tools/verify_digests.py --data-file dummy_1GB.bin --digests-file /tmp/digests.bin --chunk-size 64
```

### 5.5 Ejecución

Protocolo del artículo: 3 s de calentamiento y bucles sostenidos de al menos 15 s por corrida, 5 corridas consecutivas, media ± desviación estándar.

```bash
# Suite completa con barrido de C
python3 tools/run_benchmarks.py --file dummy_1GB.bin --duration 15.0 --warmup 3.0 --runs 5 --sweep-c

# Prueba rápida
python3 tools/run_benchmarks.py --quick
```

Ejecuciones individuales:

```bash
# CPU: SHA-NI con 4 hilos fijados a E-cores
./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl shani --threads 4 --cores 4,5,6,7 --chunk-size 64 --duration 15.0 --runs 5

# CPU: escalar, 1 hilo
./cpu/sha256_cpu_bench --file dummy_1GB.bin --impl scalar --threads 1 --cores 4 --chunk-size 64 --duration 15.0 --runs 5

# GPU v1 (línea base)
./gpu/sha256_gpu --file dummy_1GB.bin --chunk-size 64 --staging pinned --runs 5

# GPU v2 (alta utilización, lote de 64 MiB por stream)
./gpu/sha256_gpu_v2 --file dummy_1GB.bin --chunk-size 64 --staging pinned --batch-size 67108864 --runs 5
```

Opciones de la GPU:

- `--staging pinned` usa memoria del anfitrión fijada (`cudaMallocHost`); `--staging pageable` usa memoria paginable e incluye su copia en la medición extremo a extremo.
- `--output-mode full` (por defecto) devuelve los N × 32 bytes de digests al anfitrión; `--output-mode reduce` hace un XOR de los digests en la GPU y devuelve solo 32 bytes, para aislar el efecto del bus.

El kernel v2 se diferencia del v1 en: ventana circular de 16 palabras en lugar de `w[64]`, `--maxrregcount=48`, constantes en memoria `__constant__`, las 64 rondas desenrolladas, `__byte_perm()` para el cambio de orden de bytes, bucle grid-stride, memoria fijada y un pipeline asíncrono de 3 streams.

### 5.6 Notas sobre la telemetría de energía

- **Intel RAPL:** el contador `energy_uj` requiere permiso de lectura (`sudo chmod 444 /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj`, o ejecutar con `sudo`). El orquestador maneja el desbordamiento del contador y mide el reposo para calcular energía bruta y neta. El dominio PKG no incluye la DRAM del anfitrión.
- **NVML:** si aparece `Driver/library version mismatch`, hay que reiniciar para recuperar las lecturas de potencia. Las mediciones de tiempo con CUDA Events no dependen de NVML.

---

## 6. FPGA

La carpeta [`FPGA/`](FPGA/) contiene el diseño y toda la evidencia del escalado de 1 a 24 núcleos en la placa SP701 (xc7s100fgga676-2) a 100 MHz.

| Carpeta / archivo | Contenido |
|---|---|
| [`FPGA/RTL/`](FPGA/RTL/) | `sha_256.v` (núcleo iterativo, 1 ronda por ciclo), `sha256_bench.v` (banco de prueba en chip), `sha256_multi.v` (N bancos en paralelo y XOR de digests), tops con y sin VIO, y restricciones `sp701.xdc`. `diseno_1_nucleo/` conserva el diseño inicial de un núcleo. |
| [`FPGA/Testbench/`](FPGA/Testbench/) | Simulaciones del núcleo, del banco, del multinúcleo y el estímulo para generar el SAIF. |
| [`FPGA/Scripts/`](FPGA/Scripts/) | `vio_runs.tcl` (5 corridas de 60 s desde el Hardware Manager), `analyze_multi.py` (métricas y verificación de las N cadenas), `check_run.py`, `verify_model.py` (modelo en Python del RTL) y una guía paso a paso (`LEEME_multinucleo.txt`). |
| `FPGA/N=1/` … `FPGA/N=24/` | Por cada N: CSV de las corridas en placa, análisis, y reportes de Vivado de utilización, temporización y potencia. |
| [`FPGA/resumen_escalado.csv`](FPGA/resumen_escalado.csv) | Resultados consolidados y método de extrapolación de la potencia. |
| [`FPGA/INDICE.txt`](FPGA/INDICE.txt), [`FPGA/WORKFLOW.txt`](FPGA/WORKFLOW.txt) | Índice de archivos y flujo de trabajo seguido en Vivado. |

**Cómo se mide.** Cada núcleo procesa una cadena de mensajes de 64 B generada en el chip, en la que el digest de un mensaje alimenta al siguiente; cada núcleo recibe un identificador distinto para que las cadenas difieran. Un núcleo VIO controla el inicio y la parada y expone los mensajes completados, los ciclos activos, el último digest y el resultado de un autotest NIST. El throughput se calcula con los ciclos contados en hardware (136 por mensaje y núcleo).

**Cómo se verifica.** Al final de cada corrida, `analyze_multi.py` recalcula las N cadenas completas en el PC y compara su XOR con el digest leído de la FPGA. En total se verificaron 12 293 millones de hashes entre los cinco valores de N.

**Cómo se estima la potencia.** Análisis de potencia de Vivado sobre el diseño ruteado sin la infraestructura de depuración. Para N = 1, 4 y 8 la actividad proviene de una simulación post-implementación (SAIF). Para N = 16 y 24 esa simulación excede el límite de la licencia gratuita de XSim, así que la potencia dinámica se extrapola como el promedio de dos métodos (recta ajustada a los tres puntos SAIF y estimación *vectorless* calibrada); el detalle está en las últimas líneas de `resumen_escalado.csv`.

**Para reproducirlo** se necesita Vivado y una placa SP701. El número de núcleos se cambia editando `N_CORES` en `sp701_multi_top.v` (placa) o `sp701_pwr_multi_top.v` (potencia). Los pasos están en `FPGA/Scripts/LEEME_multinucleo.txt`; las rutas de Windows que aparecen ahí y en `WORKFLOW.txt` son las del equipo original y hay que adaptarlas.

```bash
# Modelo del RTL en Python (no requiere Vivado)
python3 FPGA/Scripts/verify_model.py

# Volver a analizar y verificar una corrida en placa ya registrada
cd "FPGA/N=8" && python3 ../Scripts/analyze_multi.py vio_runs_N8.csv --cores 8 --pdyn 0.298 --pstat 0.090
```

La verificación recalcula todas las cadenas y tarda del orden de minutos por núcleo; con `--no-digest` solo calcula las métricas.

---

## 7. Regenerar tablas, figuras y el PDF

```bash
# Figuras del artículo (ejecutar desde la raíz del repositorio)
python3 Paper/plot_results_summary.py    # Figuras 1 y 3
python3 tools/analyze_results.py         # Figura 2 y results/latex_tables.tex
python3 Paper/plot_fpga_scaling.py       # Figura 4

# Macros numéricas y tablas de CPU y GPU a partir de results/benchmarks_summary.csv
python3 tools/generate_latex_tables.py

# main.tex de un solo archivo y paquete para Overleaf
python3 Paper/make_overleaf.py
```

**Precaución:** `generate_latex_tables.py` reescribe `Paper/tab_comparison.tex`, que en la versión actual incluye además las filas de FPGA añadidas a partir de `FPGA/resumen_escalado.csv`; si se ejecuta, hay que restaurar esas filas (`git checkout Paper/tab_comparison.tex`). `Paper/generate_plots.py` corresponde a figuras de una versión anterior del artículo (`Paper/archive/`).

`Paper/IEEE_es.tex` es la fuente; `Paper/main.tex`, `Paper/overleaf_paper/` y `Paper/overleaf_paper.zip` se regeneran con `make_overleaf.py` y no se editan a mano. Para compilar, basta subir `overleaf_paper.zip` a Overleaf o usar `latexmk -pdf IEEE_es.tex` dentro de `Paper/`.

---

## 8. Limitaciones que conviene tener presentes

- La potencia de la FPGA es estimada, parcialmente extrapolada, y su perímetro es el chip (no la placa); la de CPU y GPU es medida.
- La FPGA no tiene una vía de datos hacia el anfitrión en este montaje, por lo que no hay cifra extremo a extremo para ella.
- La energía "con host" de la GPU usa RAPL PKG y excluye la DRAM del anfitrión.
- Todos los resultados corresponden a un único equipo y una única placa.

El artículo discute estas y otras amenazas a la validez en su sección de metodología.

---

## 9. Cita y contacto

Si usas este material, cita el artículo:

> B. Oyarzún Valdebenito, N. Ruminot Ahumada y C. Fernández-Campusano, "Desarrollo y evaluación de un Acelerador Criptográfico para el Algoritmo SHA-2 en Hardware Reconfigurable", Departamento de Ingeniería Eléctrica, Universidad de Santiago de Chile.

Contacto: benjamin.oyarzun.v@usach.cl

Este repositorio aún no declara una licencia; para reutilizar el código, consulta a los autores.
