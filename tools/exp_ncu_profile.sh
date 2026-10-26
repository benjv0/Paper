#!/usr/bin/env bash
# tools/exp_ncu_profile.sh
# Experimento Opcional (f): Perfilado Nsight Compute de sha256_gpu_v2 en C=4 KB, 64 KB y 1 MB.

set -e

CHUNK_SIZES=(4096 65536 1048576)
NCU_BIN=$(which ncu || echo "/usr/local/cuda/bin/ncu")

echo "================================================================="
echo "EXPERIMENTO (f): Perfilado Nsight Compute (C = 4 KB, 64 KB, 1 MB)"
echo "================================================================="
echo "Nsight Compute binary: $NCU_BIN"
echo "Esfuerzo estimado: ~6-8 minutos (por reejecución de kernel multipase de NCU)."
echo "Secciones: SpeedOfLight, MemoryWorkloadAnalysis, WarpStateStats."
echo ""
echo "[AVISO]: Requiere privilegios de perf/GPU counters en el kernel de Linux."
echo "Comando prototipo para cada C:"
for c in "${CHUNK_SIZES[@]}"; do
    echo "  $NCU_BIN --set basic --target-processes all -o results/ncu_profile_C${c} ./gpu/sha256_gpu_v2 --chunk-size $c --runs 1"
done
