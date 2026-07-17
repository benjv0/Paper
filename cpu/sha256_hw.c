#define _POSIX_C_SOURCE 200809L
/*
 * sha256_hw.c — SHA-256 Hardware-accelerated benchmark (Intel SHA-NI)
 *
 * Uses OpenSSL EVP API which automatically dispatches to Intel SHA-NI
 * when the CPU supports it (CPUID check at runtime).
 * Compiled with -O3 -msha -msse4.1 -msse4.2 to enable SHA intrinsics.
 *
 * Usage: ./sha256_hw <file> [runs]
 *
 * Output format identical to sha256_sw for easy comparison.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <openssl/evp.h>
#include <openssl/err.h>

#define BUF_SIZE (4 * 1024 * 1024)  /* 4 MB read buffer */

static double get_time_s(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

static void openssl_check(int rc, const char *msg)
{
    if (rc != 1) {
        fprintf(stderr, "OpenSSL error in %s: ", msg);
        ERR_print_errors_fp(stderr);
        exit(1);
    }
}

int main(int argc, char *argv[])
{
    if (argc < 2) {
        fprintf(stderr, "Usage: %s <file> [runs]\n", argv[0]);
        return 1;
    }

    const char *filepath = argv[1];
    int runs = (argc >= 3) ? atoi(argv[2]) : 5;
    if (runs < 1) runs = 1;

    /* Verify OpenSSL can find SHA-256 */
    const EVP_MD *md = EVP_sha256();
    if (!md) {
        fprintf(stderr, "EVP_sha256() not available\n");
        return 1;
    }

    uint8_t *buf = malloc(BUF_SIZE);
    if (!buf) { perror("malloc"); return 1; }

    /* measure file size */
    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); free(buf); return 1; }
    fseek(fp, 0, SEEK_END);
    long file_bytes = ftell(fp);
    fclose(fp);

    double total_time = 0.0, total_sq = 0.0;
    uint8_t hash[EVP_MAX_MD_SIZE];
    unsigned int hash_len;
    char hash_hex[65];

    fprintf(stderr, "[HW] File: %s  Size: %ld bytes  Runs: %d\n",
            filepath, file_bytes, runs);
    fprintf(stderr, "[HW] OpenSSL version: %s\n", OPENSSL_VERSION_TEXT);

    for (int r = 0; r < runs; r++) {
        fp = fopen(filepath, "rb");
        if (!fp) { perror("fopen"); free(buf); return 1; }

        EVP_MD_CTX *ctx = EVP_MD_CTX_new();
        if (!ctx) { fprintf(stderr, "EVP_MD_CTX_new failed\n"); return 1; }

        openssl_check(EVP_DigestInit_ex(ctx, md, NULL), "DigestInit");

        double t0 = get_time_s();
        size_t n;
        while ((n = fread(buf, 1, BUF_SIZE, fp)) > 0)
            openssl_check(EVP_DigestUpdate(ctx, buf, n), "DigestUpdate");

        openssl_check(EVP_DigestFinal_ex(ctx, hash, &hash_len), "DigestFinal");
        double elapsed = get_time_s() - t0;

        EVP_MD_CTX_free(ctx);
        fclose(fp);

        for (unsigned int i = 0; i < hash_len; i++)
            sprintf(hash_hex + i*2, "%02x", hash[i]);
        hash_hex[64] = '\0';

        double throughput_mbs = ((double)file_bytes / (1024.0*1024.0)) / elapsed;

        printf("RUN %d TIME_S %.6f THROUGHPUT_MBS %.3f HASH %s\n",
               r+1, elapsed, throughput_mbs, hash_hex);
        fflush(stdout);

        total_time += elapsed;
        total_sq   += elapsed * elapsed;
    }

    double avg = total_time / runs;
    double variance = (total_sq / runs) - (avg * avg);
    double stdev = (variance > 0) ? __builtin_sqrt(variance) : 0.0;
    double avg_throughput = ((double)file_bytes / (1024.0*1024.0)) / avg;

    printf("SUMMARY HW AVG_TIME_S %.6f STDEV_S %.6f AVG_THROUGHPUT_MBS %.3f FILE_BYTES %ld\n",
           avg, stdev, avg_throughput, file_bytes);

    free(buf);
    return 0;
}
