#ifndef WORKLOAD_H
#define WORKLOAD_H

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>

#define DEFAULT_CHUNK_SIZE 64

typedef enum {
    OUTPUT_MODE_FULL = 0,
    OUTPUT_MODE_REDUCE = 1
} OutputMode;

typedef enum {
    STAGING_PINNED = 0,
    STAGING_PAGEABLE = 1
} StagingMode;

typedef struct {
    uint8_t *buffer;           /* Contiguous host memory holding file payload */
    size_t file_bytes;         /* Exact size of file on disk */
    size_t chunk_size;         /* C: bytes per chunk */
    size_t num_chunks;         /* N = floor(file_bytes / C) */
    size_t blocks_per_chunk;   /* B = ceil((C + 9) / 64) */
    size_t payload_bytes;      /* N * C useful bytes */
    OutputMode output_mode;    /* FULL (Nx32 B) or REDUCE (32 B XOR) */
    StagingMode staging_mode;  /* PINNED or PAGEABLE */
} Workload;

/* Helper: ceiling division: ceil((C + 9) / 64) */
static inline size_t compute_blocks_per_chunk(size_t chunk_size) {
    return (chunk_size + 9 + 63) / 64;
}

/* Monotonic time helper in seconds */
static inline double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + (double)ts.tv_nsec * 1e-9;
}

/* Initialize workload from file */
static inline int init_workload(const char *filepath, size_t chunk_size, OutputMode out_mode, StagingMode stg_mode, Workload *wl, uint8_t *preallocated_buffer) {
    struct stat st;
    if (stat(filepath, &st) != 0) {
        perror("stat input file");
        return -1;
    }

    size_t file_bytes = (size_t)st.st_size;
    if (chunk_size == 0 || file_bytes < chunk_size) {
        fprintf(stderr, "Error: chunk_size (%zu) must be > 0 and <= file_bytes (%zu)\n", chunk_size, file_bytes);
        return -1;
    }

    size_t num_chunks = file_bytes / chunk_size;
    size_t blocks_per_chunk = compute_blocks_per_chunk(chunk_size);
    size_t payload_bytes = num_chunks * chunk_size;

    wl->file_bytes = file_bytes;
    wl->chunk_size = chunk_size;
    wl->num_chunks = num_chunks;
    wl->blocks_per_chunk = blocks_per_chunk;
    wl->payload_bytes = payload_bytes;
    wl->output_mode = out_mode;
    wl->staging_mode = stg_mode;

    if (preallocated_buffer) {
        wl->buffer = preallocated_buffer;
    } else {
        wl->buffer = (uint8_t *)malloc(file_bytes);
        if (!wl->buffer) {
            perror("malloc workload buffer");
            return -1;
        }
    }

    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        perror("fopen input file");
        if (!preallocated_buffer) free(wl->buffer);
        return -1;
    }

    size_t read_bytes = fread(wl->buffer, 1, file_bytes, fp);
    fclose(fp);

    if (read_bytes != file_bytes) {
        fprintf(stderr, "Error: read %zu of %zu bytes\n", read_bytes, file_bytes);
        if (!preallocated_buffer) free(wl->buffer);
        return -1;
    }

    return 0;
}

/* Reduce (XOR fold) an array of N digests (Nx32 bytes) into a single 32-byte digest */
static inline void reduce_digests_xor(const uint8_t *digests, size_t num_chunks, uint8_t *reduced_out) {
    memset(reduced_out, 0, 32);
    for (size_t i = 0; i < num_chunks; i++) {
        const uint64_t *d64 = (const uint64_t *)(digests + i * 32);
        uint64_t *r64 = (uint64_t *)reduced_out;
        r64[0] ^= d64[0];
        r64[1] ^= d64[1];
        r64[2] ^= d64[2];
        r64[3] ^= d64[3];
    }
}

/* Save digests to binary file if requested */
static inline int save_digests_file(const char *filepath, const uint8_t *digests, size_t total_bytes) {
    FILE *fp = fopen(filepath, "wb");
    if (!fp) {
        perror("fopen save_digests");
        return -1;
    }
    size_t written = fwrite(digests, 1, total_bytes, fp);
    fclose(fp);
    return (written == total_bytes) ? 0 : -1;
}

#endif /* WORKLOAD_H */
