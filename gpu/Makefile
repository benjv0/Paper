# ─────────────────────────────────────────────────────────────────────
#  Makefile — SHA-256 GPU (CUDA) Benchmark (v1 and v2)
# ─────────────────────────────────────────────────────────────────────

NVCC      := nvcc
NVCCFLAGS := -O3 -arch=sm_86 -std=c++11 -Xptxas -v

FILE      ?= ../dummy_1GB.bin
RUNS      ?= 5

.PHONY: all clean run verify v1 v2

all: v1 v2
	@echo ""
	@echo "  GPU binaries built successfully:"
	@echo "    sha256_gpu    — Kernel v1 baseline (w[64])"
	@echo "    sha256_gpu_v2 — Kernel v2 high-utilization (w[16], --maxrregcount=48, 3 streams)"
	@echo ""

v1: sha256_gpu
v2: sha256_gpu_v2

sha256_gpu: sha256_gpu.cu ../common/workload.h ../common/nist_vectors.h
	@mkdir -p results
	$(NVCC) $(NVCCFLAGS) -o $@ $< 2> results/ptxas_v1.log
	@cat results/ptxas_v1.log
	@echo "  [✓] sha256_gpu compiled successfully (logged to results/ptxas_v1.log)"

sha256_gpu_v2: sha256_gpu_v2.cu ../common/workload.h ../common/nist_vectors.h
	@mkdir -p results
	$(NVCC) $(NVCCFLAGS) --maxrregcount=48 -o $@ $< 2> results/ptxas_v2.log
	@cat results/ptxas_v2.log
	@echo "  [✓] sha256_gpu_v2 compiled successfully (logged to results/ptxas_v2.log)"

clean:
	rm -f sha256_gpu sha256_gpu_v2
	rm -rf results
	@echo "  Cleaned GPU folder."
