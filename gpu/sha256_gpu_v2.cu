/*
 * sha256_gpu_v2.cu — High-Utilization CUDA SHA-256 Benchmark (Kernel v2)
 * =======================================================================
 * Target: NVIDIA GeForce RTX 2050 (GA107M, sm_86)
 *
 * 8 Architectural Optimizations vs v1:
 *  1. __constant__ K[64]           — warp-broadcast, zero L2 cache pressure
 *  2. Sliding-window w[16] not w[64] — saves 48 registers/thread (occupancy 33% -> 83%)
 *  3. __byte_perm() big-endian load  — 1 PTX instruction instead of 4 shifts
 *  4. #pragma unroll on all 64 rounds — zero loop overhead, max ILP
 *  5. Inline padding block          — w[] computed inline, zero stack/local spill
 *  6. Grid-stride loop kernel        — always saturates all 16 SMs
 *  7. Pinned (page-locked) host mem  — enables async DMA via cudaMemcpyAsync
 *  8. Triple CUDA streams            — overlaps H2D, compute, D2H simultaneously
 *
 * Parameters:
 *  --chunk-size <C> : chunk size (bytes)
 *  --batch-size <B> : stream batch size (bytes), default 64 MiB
 *  --output-mode {full, reduce} : full (Nx32 B) or device reduction (32 B)
 *  --staging {pinned, pageable}
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <cuda_runtime.h>

#include "../common/workload.h"
#include "../common/nist_vectors.h"

#define ROTR32(x,n)  (((x) >> (n)) | ((x) << (32-(n))))
#define CH(x,y,z)    (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)   (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)       (ROTR32((x), 2) ^ ROTR32((x),13) ^ ROTR32((x),22))
#define EP1(x)       (ROTR32((x), 6) ^ ROTR32((x),11) ^ ROTR32((x),25))
#define SIG0(x)      (ROTR32((x), 7) ^ ROTR32((x),18) ^ ((x) >> 3))
#define SIG1(x)      (ROTR32((x),17) ^ ROTR32((x),19) ^ ((x) >> 10))

/* Opt 1: K in __constant__ memory */
__constant__ uint32_t K_CONST[64] = {
    0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,
    0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,
    0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,
    0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,
    0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,
    0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,
    0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,
    0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,
    0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,
    0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,
    0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,
    0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,
    0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,
    0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,
    0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,
    0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u
};

/* SHA-256 IV in __constant__ memory */
__constant__ uint32_t SHA256_IV[8] = {
    0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
    0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u
};

/* Opt 2, 3, 4: Sliding window w[16], __byte_perm(), #pragma unroll */
__device__ static __forceinline__ void sha256_compress_v2(
    uint32_t s[8], const uint8_t *blk)
{
    uint32_t w[16];

    #pragma unroll 16
    for (int i = 0; i < 16; ++i) {
        uint32_t raw;
        memcpy(&raw, blk + i * 4, 4);
        w[i] = __byte_perm(raw, 0u, 0x0123u);
    }

    uint32_t a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
    uint32_t t1, t2;

    #pragma unroll 16
    for (int i = 0; i < 16; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + K_CONST[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    #pragma unroll 48
    for (int i = 16; i < 64; ++i) {
        const int j = i & 15;
        w[j] = SIG1(w[(i-2)&15]) + w[(i-7)&15] + SIG0(w[(i-15)&15]) + w[j];
        t1 = h + EP1(e) + CH(e,f,g) + K_CONST[i] + w[j];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    s[0]+=a; s[1]+=b; s[2]+=c; s[3]+=d;
    s[4]+=e; s[5]+=f; s[6]+=g; s[7]+=h;
}

/* Opt 5: Inline padding block */
__device__ static __forceinline__ void sha256_compress_padding_v2(
    uint32_t s[8], uint64_t byte_len)
{
    const uint64_t bits = byte_len * 8ull;
    uint32_t w[16];
    w[0] = 0x80000000u;
    #pragma unroll 13
    for (int i = 1; i < 14; ++i) w[i] = 0u;
    w[14] = (uint32_t)(bits >> 32);
    w[15] = (uint32_t)(bits & 0xFFFFFFFFu);

    uint32_t a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
    uint32_t t1, t2;

    #pragma unroll 16
    for (int i = 0; i < 16; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + K_CONST[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    #pragma unroll 48
    for (int i = 16; i < 64; ++i) {
        const int j = i & 15;
        w[j] = SIG1(w[(i-2)&15]) + w[(i-7)&15] + SIG0(w[(i-15)&15]) + w[j];
        t1 = h + EP1(e) + CH(e,f,g) + K_CONST[i] + w[j];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }
    s[0]+=a; s[1]+=b; s[2]+=c; s[3]+=d;
    s[4]+=e; s[5]+=f; s[6]+=g; s[7]+=h;
}

__device__ static __forceinline__ void write_be32_v2(uint8_t *p, uint32_t v)
{
    p[0]=(v>>24)&0xff; p[1]=(v>>16)&0xff; p[2]=(v>>8)&0xff; p[3]=v&0xff;
}

/* Opt 6: Grid-stride loop */
__global__ void sha256_kernel_v2(
    const uint8_t * __restrict__ d_in,
    uint8_t       * __restrict__ d_out,
    long chunk_size,
    int num_blocks_data,
    long num_chunks)
{
    for (long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
         idx < num_chunks;
         idx += (long)gridDim.x * blockDim.x)
    {
        uint32_t s[8];
        #pragma unroll 8
        for (int i = 0; i < 8; ++i) s[i] = SHA256_IV[i];

        const uint8_t *src = d_in + (long)idx * chunk_size;
        for (int b = 0; b < num_blocks_data; ++b)
            sha256_compress_v2(s, src + (long)b * 64);

        sha256_compress_padding_v2(s, (uint64_t)chunk_size);

        uint8_t *out = d_out + (long)idx * 32;
        #pragma unroll 8
        for (int i = 0; i < 8; ++i) write_be32_v2(out + i*4, s[i]);
    }
}

__global__ void xor_reduce_kernel_v2(const uint8_t * __restrict__ d_in, uint8_t * __restrict__ d_out, long num_chunks) {
    uint32_t local[8] = {0};
    for (long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
         idx < num_chunks;
         idx += (long)gridDim.x * blockDim.x)
    {
        const uint32_t *src = (const uint32_t *)(d_in + idx * 32);
        #pragma unroll 8
        for (int i = 0; i < 8; i++) local[i] ^= src[i];
    }

    for (int offset = 16; offset > 0; offset /= 2) {
        #pragma unroll 8
        for (int i = 0; i < 8; i++) local[i] ^= __shfl_down_sync(0xffffffff, local[i], offset);
    }

    if ((threadIdx.x & 31) == 0) {
        uint32_t *d32 = (uint32_t *)d_out;
        #pragma unroll 8
        for (int i = 0; i < 8; i++) atomicXor(&d32[i], local[i]);
    }
}

#define CUDA_CHECK(v) cuda_check_((v),#v,__FILE__,__LINE__)
static inline void cuda_check_(cudaError_t r, const char *f, const char *file, int line)
{
    if (r != cudaSuccess) {
        fprintf(stderr,"CUDA error at %s:%d  %s\n  -> %s\n",
                file, line, f, cudaGetErrorString(r));
        exit(1);
    }
}

int main(int argc, char *argv[])
{
    const char *filepath = "dummy_1GB.bin";
    size_t chunk_sz = 64;
    int runs = 5;
    OutputMode out_mode = OUTPUT_MODE_FULL;
    StagingMode stg_mode = STAGING_PINNED;
    size_t batch_size_bytes = 64 * 1024 * 1024; /* 64 MiB default */
    const char *save_digests_path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--file") == 0 && i + 1 < argc) {
            filepath = argv[++i];
        } else if (strcmp(argv[i], "--chunk-size") == 0 && i + 1 < argc) {
            chunk_sz = (size_t)atol(argv[++i]);
        } else if (strcmp(argv[i], "--batch-size") == 0 && i + 1 < argc) {
            batch_size_bytes = (size_t)atol(argv[++i]);
        } else if (strcmp(argv[i], "--output-mode") == 0 && i + 1 < argc) {
            if (strcmp(argv[i+1], "reduce") == 0) out_mode = OUTPUT_MODE_REDUCE;
            else out_mode = OUTPUT_MODE_FULL;
            i++;
        } else if (strcmp(argv[i], "--staging") == 0 && i + 1 < argc) {
            if (strcmp(argv[i+1], "pageable") == 0) stg_mode = STAGING_PAGEABLE;
            else stg_mode = STAGING_PINNED;
            i++;
        } else if (strcmp(argv[i], "--runs") == 0 && i + 1 < argc) {
            runs = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--save-digests") == 0 && i + 1 < argc) {
            save_digests_path = argv[++i];
        } else if (argv[i][0] != '-' && i == 1) {
            /* Support legacy positional arguments: <file> <chunk_size> [runs] */
            filepath = argv[1];
            if (i + 1 < argc && argv[i+1][0] != '-') chunk_sz = (size_t)atol(argv[++i]);
            if (i + 1 < argc && argv[i+1][0] != '-') runs = atoi(argv[++i]);
        }
    }

    if (chunk_sz < 64 || chunk_sz % 64 != 0) {
        fprintf(stderr, "Error: chunk_size=%zu is not a multiple of 64.\n", chunk_sz);
        return 1;
    }
    const int blocks_per_chunk = (int)(chunk_sz / 64);
    const size_t total_blocks_per_chunk = compute_blocks_per_chunk(chunk_sz);

    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);
    size_t file_bytes = (size_t)ftell(fp);
    fseek(fp, 0, SEEK_SET);

    size_t num_chunks = file_bytes / chunk_sz;
    if (num_chunks < 1) {
        fprintf(stderr, "File too small for chunk_size=%zu\n", chunk_sz);
        fclose(fp); return 1;
    }
    size_t used_bytes = num_chunks * chunk_sz;

    /* Allocate host buffers */
    uint8_t *h_in = NULL;
    uint8_t *h_pinned_stage = NULL;
    uint8_t *h_out = NULL;

    if (stg_mode == STAGING_PINNED) {
        CUDA_CHECK(cudaMallocHost(&h_in, used_bytes));
    } else {
        h_in = (uint8_t *)malloc(used_bytes);
        CUDA_CHECK(cudaMallocHost(&h_pinned_stage, used_bytes));
    }
    CUDA_CHECK(cudaMallocHost(&h_out, num_chunks * 32));

    size_t rb = fread(h_in, 1, used_bytes, fp);
    fclose(fp);
    if (rb != used_bytes) {
        fprintf(stderr, "Error reading file\n");
        return 1;
    }

    /* Device buffers */
    uint8_t *d_in, *d_out, *d_reduced;
    CUDA_CHECK(cudaMalloc(&d_in,  used_bytes));
    CUDA_CHECK(cudaMalloc(&d_out, num_chunks * 32));
    CUDA_CHECK(cudaMalloc(&d_reduced, 32));

    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));

    const int THREADS_PER_BLOCK = 256;
    int min_blocks = prop.multiProcessorCount * 5 * 2;
    long needed_blocks = (num_chunks + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    int grid_size = (int)(needed_blocks > min_blocks ? needed_blocks : min_blocks);
    int max_blocks = prop.multiProcessorCount * prop.maxThreadsPerMultiProcessor / THREADS_PER_BLOCK;
    if (grid_size > max_blocks * 4) grid_size = max_blocks * 4;

    fprintf(stderr,
        "[GPU v2] File: %s (%zu B) | C: %zu B | N: %zu | B: %zu | Grid: %d x %d | SMs: %d | BatchSize: %zu B | Staging: %s | OutMode: %s | Runs: %d\n",
        filepath, file_bytes, chunk_sz, num_chunks, total_blocks_per_chunk,
        grid_size, THREADS_PER_BLOCK, prop.multiProcessorCount, batch_size_bytes,
        (stg_mode == STAGING_PINNED) ? "PINNED" : "PAGEABLE",
        (out_mode == OUTPUT_MODE_FULL) ? "FULL" : "REDUCE", runs);

    /* Opt 8: Triple CUDA streams */
    const int N_STREAMS = 3;
    cudaStream_t streams[N_STREAMS];
    for (int s = 0; s < N_STREAMS; ++s)
        CUDA_CHECK(cudaStreamCreate(&streams[s]));

    /* Calculate batch chunk count based on batch_size_bytes */
    size_t chunks_per_batch = batch_size_bytes / chunk_sz;
    if (chunks_per_batch < 1) chunks_per_batch = 1;
    size_t total_batches = (num_chunks + chunks_per_batch - 1) / chunks_per_batch;

    for (int r = 0; r < runs; ++r) {
        /* ── Measure kernel-only time ── */
        CUDA_CHECK(cudaMemcpy(d_in, h_in, used_bytes, cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaDeviceSynchronize());

        cudaEvent_t k_start, k_stop;
        CUDA_CHECK(cudaEventCreate(&k_start));
        CUDA_CHECK(cudaEventCreate(&k_stop));
        CUDA_CHECK(cudaEventRecord(k_start, 0));

        sha256_kernel_v2<<<grid_size, THREADS_PER_BLOCK>>>(
            d_in, d_out, chunk_sz, blocks_per_chunk, num_chunks);

        CUDA_CHECK(cudaEventRecord(k_stop, 0));
        CUDA_CHECK(cudaEventSynchronize(k_stop));
        float ms_kernel;
        CUDA_CHECK(cudaEventElapsedTime(&ms_kernel, k_start, k_stop));
        double time_kernel_s = ms_kernel / 1000.0;
        CUDA_CHECK(cudaEventDestroy(k_start));
        CUDA_CHECK(cudaEventDestroy(k_stop));

        /* ── Measure E2E time with pipelined streams ── */
        CUDA_CHECK(cudaDeviceSynchronize());

        cudaEvent_t e_start, e_stop;
        CUDA_CHECK(cudaEventCreate(&e_start));
        CUDA_CHECK(cudaEventCreate(&e_stop));
        CUDA_CHECK(cudaEventRecord(e_start, 0));

        uint8_t *src_h2d_base = h_in;
        if (stg_mode == STAGING_PAGEABLE) {
            /* Pageable -> pinned copy */
            memcpy(h_pinned_stage, h_in, used_bytes);
            src_h2d_base = h_pinned_stage;
        }

        if (out_mode == OUTPUT_MODE_REDUCE) {
            CUDA_CHECK(cudaMemset(d_reduced, 0, 32));
        }

        for (size_t b = 0; b < total_batches; ++b) {
            int s = (int)(b % N_STREAMS);
            size_t start_c = b * chunks_per_batch;
            size_t end_c   = start_c + chunks_per_batch;
            if (end_c > num_chunks) end_c = num_chunks;
            size_t n_c = end_c - start_c;

            size_t byte_off = start_c * chunk_sz;
            size_t byte_len = n_c    * chunk_sz;
            size_t hash_off = start_c * 32L;
            size_t hash_len = n_c    * 32L;

            /* Async H2D */
            CUDA_CHECK(cudaMemcpyAsync(d_in + byte_off, src_h2d_base + byte_off,
                                       byte_len, cudaMemcpyHostToDevice, streams[s]));

            /* Kernel execution */
            int seg_blocks = (int)((n_c + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK);
            if (seg_blocks < prop.multiProcessorCount * 5)
                seg_blocks = prop.multiProcessorCount * 5;

            sha256_kernel_v2<<<seg_blocks, THREADS_PER_BLOCK, 0, streams[s]>>>(
                d_in + byte_off, d_out + hash_off, chunk_sz, blocks_per_chunk, n_c);

            /* D2H in full mode */
            if (out_mode == OUTPUT_MODE_FULL) {
                CUDA_CHECK(cudaMemcpyAsync(h_out + hash_off, d_out + hash_off,
                                           hash_len, cudaMemcpyDeviceToHost, streams[s]));
            }
        }

        uint8_t h_reduced[32];
        if (out_mode == OUTPUT_MODE_REDUCE) {
            /* Reduce on device across all digests */
            CUDA_CHECK(cudaDeviceSynchronize());
            xor_reduce_kernel_v2<<<64, 256>>>(d_out, d_reduced, num_chunks);
            CUDA_CHECK(cudaMemcpy(h_reduced, d_reduced, 32, cudaMemcpyDeviceToHost));
        }

        CUDA_CHECK(cudaDeviceSynchronize());
        CUDA_CHECK(cudaEventRecord(e_stop, 0));
        CUDA_CHECK(cudaEventSynchronize(e_stop));
        float ms_e2e;
        CUDA_CHECK(cudaEventElapsedTime(&ms_e2e, e_start, e_stop));
        double time_e2e_s = ms_e2e / 1000.0;
        CUDA_CHECK(cudaEventDestroy(e_start));
        CUDA_CHECK(cudaEventDestroy(e_stop));

        char hex_chunk0[65];
        if (out_mode == OUTPUT_MODE_FULL) {
            digest_to_hex(h_out, hex_chunk0);
        } else {
            /* Copy chunk 0 for reporting */
            uint8_t c0[32];
            CUDA_CHECK(cudaMemcpy(c0, d_out, 32, cudaMemcpyDeviceToHost));
            digest_to_hex(c0, hex_chunk0);
        }

        char hex_reduced[65] = "none";
        if (out_mode == OUTPUT_MODE_REDUCE) {
            digest_to_hex(h_reduced, hex_reduced);
        }

        double tput_kernel_gbs = ((double)used_bytes / time_kernel_s) / 1e9;
        double tput_e2e_gbs    = ((double)used_bytes / time_e2e_s) / 1e9;
        double hashes_per_sec  = (double)num_chunks / time_e2e_s;
        double blocks_per_sec  = ((double)num_chunks * (double)total_blocks_per_chunk) / time_e2e_s;

        printf("RUN %d TIME_KERNEL_S %.6f TIME_E2E_S %.6f THROUGHPUT_KERNEL_GBS %.6f THROUGHPUT_E2E_GBS %.6f HASHES_PER_SEC %.2f BLOCKS_PER_SEC %.2f CHUNK_0_HASH %s REDUCED_HASH %s\n",
               r + 1, time_kernel_s, time_e2e_s, tput_kernel_gbs, tput_e2e_gbs, hashes_per_sec, blocks_per_sec, hex_chunk0, hex_reduced);
        fflush(stdout);
    }

    if (save_digests_path && out_mode == OUTPUT_MODE_FULL) {
        fprintf(stderr, "[GPU v2] Saving full digests (%zu bytes) to '%s'...\n", num_chunks * 32, save_digests_path);
        save_digests_file(save_digests_path, h_out, num_chunks * 32);
    }

    /* Cleanup */
    for (int s = 0; s < N_STREAMS; ++s) CUDA_CHECK(cudaStreamDestroy(streams[s]));
    CUDA_CHECK(cudaFree(d_in));
    CUDA_CHECK(cudaFree(d_out));
    CUDA_CHECK(cudaFree(d_reduced));
    CUDA_CHECK(cudaFreeHost(h_out));
    if (stg_mode == STAGING_PINNED) CUDA_CHECK(cudaFreeHost(h_in));
    else { free(h_in); CUDA_CHECK(cudaFreeHost(h_pinned_stage)); }

    return 0;
}
