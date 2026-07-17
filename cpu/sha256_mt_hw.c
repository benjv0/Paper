#define _POSIX_C_SOURCE 200809L
/*
 * sha256_mt_hw.c — Multi-threaded SHA-256 Hardware (SHA-NI) benchmark
 *
 * Same structure as sha256_mt_sw.c but each thread uses OpenSSL EVP,
 * which dispatches to Intel SHA-NI instructions automatically.
 * Each thread has its own EVP_MD_CTX (OpenSSL contexts are not thread-safe
 * when shared, but separate contexts per thread are perfectly safe).
 *
 * Compiled with -O3 -msha -msse4.1 -msse4.2
 *
 * Usage: ./sha256_mt_hw <file> <num_threads> [runs]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <openssl/evp.h>
#include <openssl/err.h>

#define BUF_SIZE (4 * 1024 * 1024)

typedef struct {
    const char *filepath;
    long        offset;
    long        length;
    double      elapsed_s;
    double      throughput_mbs;
    uint8_t     hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len;
    int         thread_id;
} ThreadArg;

static double get_time_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static void *thread_hash(void *arg)
{
    ThreadArg *a = (ThreadArg *)arg;

    uint8_t *buf = malloc(BUF_SIZE);
    if (!buf) { perror("malloc"); pthread_exit(NULL); }

    FILE *fp = fopen(a->filepath, "rb");
    if (!fp) { perror("fopen"); free(buf); pthread_exit(NULL); }

    if (fseek(fp, a->offset, SEEK_SET) != 0) {
        perror("fseek"); fclose(fp); free(buf); pthread_exit(NULL);
    }

    /* Each thread gets its own EVP context — required for thread safety */
    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    EVP_DigestInit_ex(ctx, EVP_sha256(), NULL);

    long remaining = a->length;
    double t0 = get_time_s();

    while (remaining > 0) {
        size_t to_read = (remaining < (long)BUF_SIZE) ? (size_t)remaining : BUF_SIZE;
        size_t n = fread(buf, 1, to_read, fp);
        if (n == 0) break;
        EVP_DigestUpdate(ctx, buf, n);
        remaining -= (long)n;
    }

    EVP_DigestFinal_ex(ctx, a->hash, &a->hash_len);
    a->elapsed_s = get_time_s() - t0;
    a->throughput_mbs = ((double)a->length / (1024.0*1024.0)) / a->elapsed_s;

    EVP_MD_CTX_free(ctx);
    fclose(fp);
    free(buf);
    return NULL;
}

/* ─── Main ─────────────────────────────────────────────────────────── */

int main(int argc, char *argv[])
{
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <file> <num_threads> [runs]\n", argv[0]);
        return 1;
    }

    const char *filepath = argv[1];
    int nthreads         = atoi(argv[2]);
    int runs             = (argc >= 4) ? atoi(argv[3]) : 5;

    if (nthreads < 1 || nthreads > 64) {
        fprintf(stderr, "num_threads must be 1–64\n"); return 1;
    }

    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);
    long file_bytes = ftell(fp);
    fclose(fp);

    long chunk = file_bytes / nthreads;

    fprintf(stderr, "[MT_HW] File: %s  Size: %ld bytes  Threads: %d  Runs: %d\n",
            filepath, file_bytes, nthreads, runs);
    fprintf(stderr, "[MT_HW] OpenSSL: %s\n", OPENSSL_VERSION_TEXT);

    pthread_t *threads = malloc(sizeof(pthread_t) * (size_t)nthreads);
    ThreadArg *args    = malloc(sizeof(ThreadArg) * (size_t)nthreads);

    double total_wall = 0.0, total_wall_sq = 0.0, total_agg = 0.0;

    for (int r = 0; r < runs; r++) {

        for (int t = 0; t < nthreads; t++) {
            args[t].filepath  = filepath;
            args[t].thread_id = t;
            args[t].offset    = (long)t * chunk;
            args[t].length    = (t == nthreads-1)
                                ? file_bytes - (long)t * chunk
                                : chunk;
        }

        double wall_start = get_time_s();
        for (int t = 0; t < nthreads; t++)
            pthread_create(&threads[t], NULL, thread_hash, &args[t]);
        for (int t = 0; t < nthreads; t++)
            pthread_join(threads[t], NULL);
        double wall_elapsed = get_time_s() - wall_start;

        double agg_mbs = ((double)file_bytes / (1024.0*1024.0)) / wall_elapsed;

        fprintf(stderr, "  Run %d: wall=%.4fs  agg=%.2f MB/s  [", r+1, wall_elapsed, agg_mbs);
        for (int t = 0; t < nthreads; t++)
            fprintf(stderr, "T%d:%.2f%s", t, args[t].throughput_mbs,
                    t<nthreads-1?", ":"");
        fprintf(stderr, " MB/s]\n");

        printf("RUN %d THREADS %d WALL_S %.6f AGGREGATE_MBS %.3f\n",
               r+1, nthreads, wall_elapsed, agg_mbs);
        fflush(stdout);

        total_wall    += wall_elapsed;
        total_wall_sq += wall_elapsed * wall_elapsed;
        total_agg     += agg_mbs;
    }

    double avg_wall = total_wall / runs;
    double var      = (total_wall_sq / runs) - (avg_wall * avg_wall);
    double stdev    = (var > 0.0) ? __builtin_sqrt(var) : 0.0;
    double avg_agg  = total_agg / runs;

    printf("SUMMARY MT_HW THREADS %d WALL_S %.6f STDEV_S %.6f "
           "AVG_AGGREGATE_MBS %.3f FILE_BYTES %ld\n",
           nthreads, avg_wall, stdev, avg_agg, file_bytes);

    free(threads);
    free(args);
    return 0;
}
