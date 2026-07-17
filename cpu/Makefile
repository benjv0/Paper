# ─────────────────────────────────────────────────────────────────────
#  Makefile — SHA-256 CPU Benchmark
#  Targets: all | run | run-sudo | verify | clean
# ─────────────────────────────────────────────────────────────────────

CC      := gcc
LDFLAGS := -lm

# ── Software-only build (no SHA-NI) ─────────────────────────────────
SW_CFLAGS := -O2 -march=x86-64 -mno-sha -std=c11 -Wall -Wextra

# ── Hardware (SHA-NI) build ──────────────────────────────────────────
HW_CFLAGS := -O3 -march=native -msha -msse4.1 -msse4.2 -std=c11 -Wall -Wextra
HW_LIBS   := -lssl -lcrypto

# ── Multi-threaded needs pthreads ────────────────────────────────────
MT_LIBS   := -lpthread

FILE      ?= ../dummy_1GB.bin
RUNS    ?= 5
THREADS ?= 1 4 8

# ─────────────────────────────────────────────────────────────────────

.PHONY: all clean run run-sudo verify

all: sha256_sw sha256_hw sha256_mt_sw sha256_mt_hw
	@echo ""
	@echo "  Build complete:"
	@echo "    sha256_sw     — pure C, single-thread, no SHA-NI"
	@echo "    sha256_hw     — OpenSSL + SHA-NI, single-thread"
	@echo "    sha256_mt_sw  — pure C, multi-thread pthreads"
	@echo "    sha256_mt_hw  — OpenSSL + SHA-NI, multi-thread pthreads"
	@echo ""
	@echo "  Run (no energy):   make run"
	@echo "  Run (with RAPL):   make run-sudo"
	@echo ""

# ── Single-thread binaries ───────────────────────────────────────────
sha256_sw: sha256_sw.c
	$(CC) $(SW_CFLAGS) -o $@ $< $(LDFLAGS)
	@echo "  [✓] sha256_sw"

sha256_hw: sha256_hw.c
	$(CC) $(HW_CFLAGS) -o $@ $< $(LDFLAGS) $(HW_LIBS)
	@echo "  [✓] sha256_hw"

# ── Multi-thread binaries ────────────────────────────────────────────
sha256_mt_sw: sha256_mt_sw.c
	$(CC) $(SW_CFLAGS) -o $@ $< $(LDFLAGS) $(MT_LIBS)
	@echo "  [✓] sha256_mt_sw"

sha256_mt_hw: sha256_mt_hw.c
	$(CC) $(HW_CFLAGS) -o $@ $< $(LDFLAGS) $(HW_LIBS) $(MT_LIBS)
	@echo "  [✓] sha256_mt_hw"

# ── Run without RAPL (no sudo needed) ───────────────────────────────
run: all
	python3 benchmark.py --file $(FILE) --runs $(RUNS) --no-rapl

# ── Run with RAPL energy measurement (requires sudo) ─────────────────
run-sudo: all
	sudo python3 benchmark.py --file $(FILE) --runs $(RUNS)

# ── Quick hash correctness check ────────────────────────────────────
verify: sha256_sw sha256_hw
	@echo ""
	@REF=$$(sha256sum $(FILE) | awk '{print $$1}'); \
	 SW=$$(./sha256_sw  $(FILE) 1 2>/dev/null | grep "^RUN" | awk '{print $$NF}'); \
	 HW=$$(./sha256_hw  $(FILE) 1 2>/dev/null | grep "^RUN" | awk '{print $$NF}'); \
	 echo "  sha256sum : $$REF"; \
	 echo "  sha256_sw : $$SW"; \
	 echo "  sha256_hw : $$HW"; \
	 if [ "$$REF" = "$$SW" ] && [ "$$REF" = "$$HW" ]; then \
	   echo "  ✓ All hashes match!"; \
	 else \
	   echo "  ✗ HASH MISMATCH"; exit 1; \
	 fi

clean:
	rm -f sha256_sw sha256_hw sha256_mt_sw sha256_mt_hw \
	      results_raw.csv results_summary.csv
	@echo "  Cleaned."
