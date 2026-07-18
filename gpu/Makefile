# ─────────────────────────────────────────────────────────────────────
#  Makefile — SHA-256 GPU (CUDA) Benchmark
#  Targets: all | run | verify | clean
# ─────────────────────────────────────────────────────────────────────

NVCC     := nvcc
NVCCFLAGS := -O3 -arch=sm_86 -std=c++11

FILE     ?= ../dummy_1GB.bin
RUNS     ?= 5

.PHONY: all clean run verify

all: sha256_gpu
	@echo ""
	@echo "  Build complete:"
	@echo "    sha256_gpu  — CUDA parallel SHA-256 binary"
	@echo ""
	@echo "  Run:       make run"
	@echo ""

sha256_gpu: sha256_gpu.cu
	$(NVCC) $(NVCCFLAGS) -o $@ $<
	@echo "  [✓] sha256_gpu compiled successfully  ($(NVCCFLAGS))"

run: all
	@mkdir -p results
	python3 benchmark_gpu.py --file $(FILE) --runs $(RUNS)

# ─── Quick validation check: compare GPU chunk 0 hash with CPU/openssl ────────
verify: sha256_gpu
	@echo ""
	@echo "  Verifying GPU output correctness against CPU sha256sum..."
	@echo ""
	@# We extract the first chunk of 64KB (65536 bytes) of the file
	@# and check its hash using system sha256sum.
	@REF_HASH=$$(dd if=$(FILE) bs=64K count=1 2>/dev/null | sha256sum | awk '{print $$1}'); \
	 GPU_HASH=$$(./sha256_gpu $(FILE) 65536 1 2>/dev/null | grep "^RUN" | head -1 | awk '{print $$NF}'); \
	 echo "  Reference (dd | sha256sum): $$REF_HASH"; \
	 echo "  GPU chunk 0 (sha256_gpu):   $$GPU_HASH"; \
	 if [ "$$REF_HASH" = "$$GPU_HASH" ]; then \
	   echo "  ✓ GPU hashing correctness verified successfully!"; \
	 else \
	   echo "  ✗ HASH MISMATCH! Check implementation."; exit 1; \
	   exit 1; \
	 fi

clean:
	rm -f sha256_gpu
	rm -rf results
	@echo "  Cleaned GPU folder."
