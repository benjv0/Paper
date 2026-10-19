#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>

#include "../common/workload.h"
#include "../common/nist_vectors.h"
#include "../common/cpu_affinity.h"
#include "sha256_scalar.h"
#include "sha256_shani.h"

typedef enum {
    SCHED_STATIC = 0,
    SCHED_DYNAMIC = 1
} SchedMode;

typedef struct {
    int thread_id;
    int cpu_core;
    const uint8_t *data;
    size_t chunk_size;
    size_t start_chunk;
    size_t end_chunk;
    size_t num_chunks;
    uint8_t *digests;
    int use_shani;
    SchedMode sched_mode;
    size_t dynamic_task_chunks;
    uint64_t *global_task_counter;
    volatile int *stop_flag;
    uint64_t chunks_processed;
    double busy_time_s;
    pthread_barrier_t *barrier_start;
    pthread_barrier_t *barrier_iter;
} ThreadContext;

static void *worker_thread_func(void *arg) {
    ThreadContext *ctx = (ThreadContext *)arg;
    pin_thread_to_core(pthread_self(), ctx->cpu_core);

    sha256_fn_t sha_fn = ctx->use_shani ? sha256_shani : sha256_scalar;

    /* Wait for all threads to be ready and pinned */
    pthread_barrier_wait(ctx->barrier_start);

    struct timespec ts0, ts1;
    clock_gettime(CLOCK_MONOTONIC, &ts0);

    if (ctx->sched_mode == SCHED_STATIC) {
        size_t n_c = ctx->end_chunk - ctx->start_chunk;
        do {
            for (size_t i = ctx->start_chunk; i < ctx->end_chunk; i++) {
                sha_fn(ctx->data + i * ctx->chunk_size, ctx->chunk_size, ctx->digests + i * 32);
            }
            ctx->chunks_processed += n_c;
            if (ctx->barrier_iter) {
                pthread_barrier_wait(ctx->barrier_iter);
            }
        } while (!(*ctx->stop_flag));
    } else {
        /* SCHED_DYNAMIC */
        size_t task_size = ctx->dynamic_task_chunks;
        size_t total_tasks = (ctx->num_chunks + task_size - 1) / task_size;
        do {
            uint64_t t_idx = __atomic_fetch_add(ctx->global_task_counter, 1, __ATOMIC_RELAXED);
            size_t local_t = (size_t)(t_idx % total_tasks);
            size_t s = local_t * task_size;
            size_t e = s + task_size;
            if (e > ctx->num_chunks) e = ctx->num_chunks;
            for (size_t i = s; i < e; i++) {
                sha_fn(ctx->data + i * ctx->chunk_size, ctx->chunk_size, ctx->digests + i * 32);
            }
            ctx->chunks_processed += (e - s);
        } while (!(*ctx->stop_flag));
    }

    clock_gettime(CLOCK_MONOTONIC, &ts1);
    ctx->busy_time_s = (ts1.tv_sec - ts0.tv_sec) + (ts1.tv_nsec - ts0.tv_nsec) * 1e-9;

    return NULL;
}

static void run_one_pass(const uint8_t *data, size_t chunk_size, size_t num_chunks,
                         uint8_t *digests, int num_threads, const int *cores, int use_shani) {
    pthread_t threads[MAX_DETECTED_CORES];
    ThreadContext contexts[MAX_DETECTED_CORES];
    pthread_barrier_t barrier_start;
    pthread_barrier_init(&barrier_start, NULL, num_threads + 1);

    volatile int stop_flag = 0;
    size_t chunks_per_thread = (num_chunks + num_threads - 1) / num_threads;

    for (int t = 0; t < num_threads; t++) {
        size_t s = t * chunks_per_thread;
        size_t e = s + chunks_per_thread;
        if (e > num_chunks) e = num_chunks;
        if (s > num_chunks) s = num_chunks;

        contexts[t].thread_id = t;
        contexts[t].cpu_core = cores[t];
        contexts[t].data = data;
        contexts[t].chunk_size = chunk_size;
        contexts[t].start_chunk = s;
        contexts[t].end_chunk = e;
        contexts[t].num_chunks = num_chunks;
        contexts[t].digests = digests;
        contexts[t].use_shani = use_shani;
        contexts[t].sched_mode = SCHED_STATIC;
        contexts[t].dynamic_task_chunks = 65536;
        contexts[t].global_task_counter = NULL;
        contexts[t].stop_flag = &stop_flag;
        contexts[t].chunks_processed = 0;
        contexts[t].busy_time_s = 0.0;
        contexts[t].barrier_start = &barrier_start;
        contexts[t].barrier_iter = NULL;

        pthread_create(&threads[t], NULL, worker_thread_func, &contexts[t]);
    }

    stop_flag = 1;
    pthread_barrier_wait(&barrier_start);

    for (int t = 0; t < num_threads; t++) {
        pthread_join(threads[t], NULL);
    }
    pthread_barrier_destroy(&barrier_start);
}

int main(int argc, char *argv[]) {
    const char *filepath = "dummy_1GB.bin";
    const char *impl_str = "shani";
    int num_threads = 1;
    size_t chunk_size = 64;
    OutputMode out_mode = OUTPUT_MODE_FULL;
    int runs = 5;
    double warmup_sec = 3.0;
    double duration_sec = 15.0;
    const char *save_digests_path = NULL;
    int verify_nist = 1;
    char cores_arg[256] = "";
    SchedMode sched_mode = SCHED_STATIC;
    size_t dynamic_task_chunks = 65536; /* 64K chunks = 4 MiB for C=64 B */

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--file") == 0 && i + 1 < argc) {
            filepath = argv[++i];
        } else if (strcmp(argv[i], "--impl") == 0 && i + 1 < argc) {
            impl_str = argv[++i];
        } else if (strcmp(argv[i], "--threads") == 0 && i + 1 < argc) {
            num_threads = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--chunk-size") == 0 && i + 1 < argc) {
            chunk_size = (size_t)atol(argv[++i]);
        } else if (strcmp(argv[i], "--output-mode") == 0 && i + 1 < argc) {
            if (strcmp(argv[i+1], "reduce") == 0) out_mode = OUTPUT_MODE_REDUCE;
            else out_mode = OUTPUT_MODE_FULL;
            i++;
        } else if (strcmp(argv[i], "--runs") == 0 && i + 1 < argc) {
            runs = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--warmup") == 0 && i + 1 < argc) {
            warmup_sec = atof(argv[++i]);
        } else if (strcmp(argv[i], "--duration") == 0 && i + 1 < argc) {
            duration_sec = atof(argv[++i]);
        } else if (strcmp(argv[i], "--cores") == 0 && i + 1 < argc) {
            strncpy(cores_arg, argv[++i], sizeof(cores_arg) - 1);
        } else if (strcmp(argv[i], "--save-digests") == 0 && i + 1 < argc) {
            save_digests_path = argv[++i];
        } else if (strcmp(argv[i], "--no-nist") == 0) {
            verify_nist = 0;
        } else if (strcmp(argv[i], "--sched") == 0 && i + 1 < argc) {
            if (strcmp(argv[i+1], "dynamic") == 0) sched_mode = SCHED_DYNAMIC;
            else sched_mode = SCHED_STATIC;
            i++;
        } else if (strcmp(argv[i], "--task-chunks") == 0 && i + 1 < argc) {
            dynamic_task_chunks = (size_t)atol(argv[++i]);
        }
    }

    int use_shani = 0;
    if (strcmp(impl_str, "shani") == 0 || strcmp(impl_str, "sha-ni") == 0) {
        use_shani = 1;
    } else if (strcmp(impl_str, "scalar") == 0) {
        use_shani = 0;
    } else {
        fprintf(stderr, "Unknown implementation: %s (choose 'shani' or 'scalar')\n", impl_str);
        return 1;
    }

    if (verify_nist) {
        sha256_fn_t fn = use_shani ? sha256_shani : sha256_scalar;
        if (verify_nist_vectors(fn, use_shani ? "SHA-NI" : "Scalar") != 0) {
            fprintf(stderr, "NIST verification failed! Aborting benchmark.\n");
            return 1;
        }
    }

    /* Configure CPU core pinning */
    int assigned_cores[MAX_DETECTED_CORES];
    int available_cores = 0;
    if (strlen(cores_arg) > 0) {
        available_cores = parse_cpu_list(cores_arg, assigned_cores, MAX_DETECTED_CORES);
    } else {
        available_cores = detect_ecores(assigned_cores, MAX_DETECTED_CORES);
    }

    if (available_cores < num_threads) {
        fprintf(stderr, "Warning: Only %d cores available for %d threads; wrapping around.\n",
                available_cores, num_threads);
        for (int i = available_cores; i < num_threads; i++) {
            assigned_cores[i] = assigned_cores[i % available_cores];
        }
    }

    /* Initialize workload */
    Workload wl;
    if (init_workload(filepath, chunk_size, out_mode, STAGING_PINNED, &wl, NULL) != 0) {
        return 1;
    }

    uint8_t *digests = (uint8_t *)malloc(wl.num_chunks * 32);
    if (!digests) {
        perror("malloc digests buffer");
        free(wl.buffer);
        return 1;
    }

    char cores_str[512] = "";
    for (int i = 0; i < num_threads; i++) {
        char tmp[16];
        snprintf(tmp, sizeof(tmp), "%d%s", assigned_cores[i], (i + 1 < num_threads) ? "," : "");
        strcat(cores_str, tmp);
    }

    fprintf(stderr, "[CPU] Impl: %s | Sched: %s | Threads: %d (Cores: %s) | File: %s (%zu B) | C: %zu B | N: %zu | B: %zu | Payload: %zu B | OutMode: %s\n",
            use_shani ? "SHA-NI" : "Scalar",
            (sched_mode == SCHED_DYNAMIC) ? "DYNAMIC" : "STATIC",
            num_threads, cores_str, filepath,
            wl.file_bytes, wl.chunk_size, wl.num_chunks, wl.blocks_per_chunk,
            wl.payload_bytes, (out_mode == OUTPUT_MODE_FULL) ? "FULL" : "REDUCE");

    /* Warmup loop */
    if (warmup_sec > 0.0) {
        fprintf(stderr, "[CPU] Warming up for %.1f s...\n", warmup_sec);
        double t_warm_start = get_time_sec();
        while ((get_time_sec() - t_warm_start) < warmup_sec) {
            run_one_pass(wl.buffer, wl.chunk_size, wl.num_chunks, digests, num_threads, assigned_cores, use_shani);
        }
    }

    /* Benchmark Runs */
    for (int r = 1; r <= runs; r++) {
        pthread_t threads[MAX_DETECTED_CORES];
        ThreadContext contexts[MAX_DETECTED_CORES];
        pthread_barrier_t barrier_start;
        pthread_barrier_init(&barrier_start, NULL, num_threads + 1);

        volatile int stop_flag = 0;
        uint64_t global_task_counter = 0;
        size_t chunks_per_thread = (wl.num_chunks + num_threads - 1) / num_threads;

        for (int t = 0; t < num_threads; t++) {
            size_t s = t * chunks_per_thread;
            size_t e = s + chunks_per_thread;
            if (e > wl.num_chunks) e = wl.num_chunks;
            if (s > wl.num_chunks) s = wl.num_chunks;

            contexts[t].thread_id = t;
            contexts[t].cpu_core = assigned_cores[t];
            contexts[t].data = wl.buffer;
            contexts[t].chunk_size = wl.chunk_size;
            contexts[t].start_chunk = s;
            contexts[t].end_chunk = e;
            contexts[t].num_chunks = wl.num_chunks;
            contexts[t].digests = digests;
            contexts[t].use_shani = use_shani;
            contexts[t].sched_mode = sched_mode;
            contexts[t].dynamic_task_chunks = dynamic_task_chunks;
            contexts[t].global_task_counter = &global_task_counter;
            contexts[t].stop_flag = &stop_flag;
            contexts[t].chunks_processed = 0;
            contexts[t].busy_time_s = 0.0;
            contexts[t].barrier_start = &barrier_start;
            contexts[t].barrier_iter = NULL;

            pthread_create(&threads[t], NULL, worker_thread_func, &contexts[t]);
        }

        /* Synchronized timed section start */
        printf("START_RUN %d\n", r);
        fflush(stdout);
        pthread_barrier_wait(&barrier_start);
        double t0 = get_time_sec();

        /* Sleep duration */
        usleep((useconds_t)(duration_sec * 1e6));
        stop_flag = 1;

        for (int t = 0; t < num_threads; t++) {
            pthread_join(threads[t], NULL);
        }
        double elapsed_s = get_time_sec() - t0;
        pthread_barrier_destroy(&barrier_start);

        /* Sum iterations */
        uint64_t total_chunks_processed = 0;
        double min_busy_s = 1e9, max_busy_s = 0.0;
        uint64_t min_chunks = UINT64_MAX, max_chunks = 0;

        for (int t = 0; t < num_threads; t++) {
            total_chunks_processed += contexts[t].chunks_processed;
            if (contexts[t].busy_time_s < min_busy_s) min_busy_s = contexts[t].busy_time_s;
            if (contexts[t].busy_time_s > max_busy_s) max_busy_s = contexts[t].busy_time_s;
            if (contexts[t].chunks_processed < min_chunks) min_chunks = contexts[t].chunks_processed;
            if (contexts[t].chunks_processed > max_chunks) max_chunks = contexts[t].chunks_processed;
        }

        double busy_imbalance_s = max_busy_s - min_busy_s;
        double chunks_imbalance_pct = (max_chunks > 0) ? ((double)(max_chunks - min_chunks) / (double)max_chunks * 100.0) : 0.0;

        double total_payload_bytes = (double)total_chunks_processed * (double)wl.chunk_size;
        double iterations = (double)total_chunks_processed / (double)wl.num_chunks;
        double throughput_gbs = (total_payload_bytes / elapsed_s) / 1e9;
        double hashes_per_sec = (double)total_chunks_processed / elapsed_s;
        double blocks_per_sec = ((double)total_chunks_processed * (double)wl.blocks_per_chunk) / elapsed_s;

        uint8_t reduced_hash[32];
        if (out_mode == OUTPUT_MODE_REDUCE) {
            reduce_digests_xor(digests, wl.num_chunks, reduced_hash);
        }

        char hex_chunk0[65];
        digest_to_hex(digests, hex_chunk0);

        char hex_reduced[65] = "none";
        if (out_mode == OUTPUT_MODE_REDUCE) {
            digest_to_hex(reduced_hash, hex_reduced);
        }

        printf("RUN %d ELAPSED_S %.6f ITERATIONS %.2f THROUGHPUT_GBS %.6f HASHES_PER_SEC %.2f BLOCKS_PER_SEC %.2f MIN_BUSY_S %.6f MAX_BUSY_S %.6f BUSY_IMBALANCE_S %.6f MIN_CHUNKS %lu MAX_CHUNKS %lu CHUNKS_IMBALANCE_PCT %.2f CHUNK_0_HASH %s REDUCED_HASH %s\n",
               r, elapsed_s, iterations, throughput_gbs, hashes_per_sec, blocks_per_sec,
               min_busy_s, max_busy_s, busy_imbalance_s,
               (unsigned long)min_chunks, (unsigned long)max_chunks, chunks_imbalance_pct,
               hex_chunk0, hex_reduced);
        
        for (int t = 0; t < num_threads; t++) {
            printf("  THREAD %d CORE %d BUSY_S %.6f CHUNKS %lu\n",
                   t, contexts[t].cpu_core, contexts[t].busy_time_s, (unsigned long)contexts[t].chunks_processed);
        }
        fflush(stdout);
    }

    if (save_digests_path) {
        fprintf(stderr, "[CPU] Saving full digests (%zu bytes) to '%s'...\n", wl.num_chunks * 32, save_digests_path);
        if (save_digests_file(save_digests_path, digests, wl.num_chunks * 32) != 0) {
            fprintf(stderr, "Error saving digests file\n");
        }
    }

    free(digests);
    free(wl.buffer);
    return 0;
}
