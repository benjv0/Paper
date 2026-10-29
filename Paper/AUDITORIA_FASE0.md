# Auditoría Inicial - Fase 0

## 1. Estado de Compilación
- **Compilador**: `./tectonic IEEE_es.tex` (Tectonic 0.15.0).
- **Resultado**: Código de salida 0 (compilación limpia y exitosa).
- **Páginas actuales**: 10 páginas.
- **Distribución actual de páginas**:
  - Pág. 1: Título, Autores, Resumen, Palabras clave, Inicio de Introducción.
  - Pág. 2: Fin de Introducción, Inicio de Trabajo Relacionado (Secciones II-A, II-B).
  - Pág. 3: Trabajo Relacionado (Secciones II-C, II-D, II-E).
  - Pág. 4: Trabajo Relacionado (Secciones II-F, II-G), Inicio de Metodología (III-A, III-B).
  - Pág. 5: Metodología (III-B cont., III-C Protocolo, III-D CPU, III-E GPU inicio).
  - Pág. 6: Metodología (III-E GPU v1/v2, III-F, III-G), Inicio de Resultados (IV, IV-A, Tabla I).
  - Pág. 7: Resultados CPU (Tabla II, barrido C), Resultados GPU (IV-B, Tabla III).
  - Pág. 8: Resultados GPU (Tabla IV, análisis PCIe, Figura 1, IV-C Comparación, Figura 2, Tabla V).
  - Pág. 9: Notas Tabla V, IV-D FPGA, Tabla VI, Inicio de Referencias.
  - Pág. 10: Fin de Referencias (58 líneas).

## 2. Inventario de Figuras
- **Figura 1 (`fig:throughput_vs_c`)**:
  - Archivo: `throughput_vs_c.pdf`.
  - Epígrafe: *Throughput de SHA-256 vs.~tamaño de fragmento $C$ para GPU v1/v2 (kernel-only y E2E, staging pinned) y serie de referencia CPU SHA-NI 4T evaluada a cada tamaño $C$*.
  - Citada en texto: **SÍ** (1 cita, línea 295).
- **Figura 2 (`fig:throughput_chart`)**:
  - Archivo: `throughput_chart.pdf`.
  - Epígrafe: *Comparación de throughput útil entre las principales configuraciones de CPU y GPU ($C=64$~B)*.
  - Citada en texto: **NO** (0 citas en el texto). Se eliminará en Fase 1 según instrucción.

## 3. Inventario de Tablas
- **Tabla I (`tab:cpu_results`)**:
  - Archivo: `tab_cpu_results.tex`.
  - Epígrafe: *Resultados de CPU SHA-256 (i7-1255U, $C=64$~B, $N=16\,777\,216$, $B=2$)*.
  - Citada en texto: **SÍ** (1 cita, línea 245).
- **Tabla II (`tab:cpu_sweep`)**:
  - Archivo: `tab_cpu_sweep.tex`.
  - Epígrafe: *Barrido de tamaño de fragmento $C$ en CPU SHA-NI 4T*.
  - Citada en texto: **SÍ** (1 cita, línea 258). Se eliminará en Fase 1 (integrada en Fig. 1).
- **Tabla III (`tab:gpu_ablation`)**:
  - Archivo: `tab_gpu_ablation.tex`.
  - Epígrafe: *Comparación GPU: kernel v1 (base) vs.~v2 (alta utilización), staging pinned*.
  - Citada en texto: **SÍ** (1 cita, línea 268). Se eliminará en Fase 1 (integrada en Fig. 1).
- **Tabla IV (`tab:gpu_staging`)**:
  - Archivo: `tab_gpu_staging.tex`.
  - Epígrafe: *Impacto del staging en GPU v2 ($C=64$~B)*.
  - Citada en texto: **SÍ** (1 cita, línea 278). Se mantiene en Fase 1.
- **Tabla V (`tab:comparison`)**:
  - Archivo: `tab_comparison.tex`.
  - Epígrafe: *Comparación cruzada de rendimiento y eficiencia energética ($C=64$~B)*.
  - Citada en texto: **SÍ** (2 citas, líneas 299 y 302). Se mantiene en Fase 1 con TODOs de FPGA intactos.
- **Tabla VI (`tab:fpga`)**:
  - Ubicación: En línea en `IEEE_es.tex`.
  - Epígrafe: *Resultados del Acelerador RTL SHA-256 en FPGA (Xilinx Spartan-7)*.
  - Citada en texto: **SÍ** (1 cita, línea 324). Se mantiene intacta con TBDs.

## 4. Inventario de Referencias Bibliográficas
- Total de entradas en `references.bib`: **32**.
- Total de referencias citadas en el texto: **32**.
- Entradas no citadas en `.bib`: **0**.
- Citas sin entrada en `.bib`: **0**.
- **Referencias tangenciales identificadas para supresión en Fase 1**:
  - `alkiswany2012storegpu`: StoreGPU (hashing en almacenamiento masivo sobre MD5 y SHA-1).
  - `feldhofer2006`: RFID (argumento contra el uso de funciones hash en tags pasivos).
  - `algredo2022`: Redundancia híbrida espacial y temporal (tolerancia a fallos, tangencial a rendimiento y energía).
  - Entradas redundantes de arquitectura de hardware: `crowe2004`, `aisopos2006`, `michail2005`, `dadda2004`, `macchetti2005`, `kim2008`.
