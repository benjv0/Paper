/*
 * sha256_gpu.cu — Baseline CUDA SHA-256 Benchmark (Kernel v1)
 * ============================================================
 * Baseline implementation:
 *  - Standard w[64] message schedule expansion in local memory
 *  - Constant/device table K[64]
 *  - One thread per message chunk
 *  - Supports --output-mode {full, reduce}
 *  - Supports --staging {pinned, pageable}
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <cuda_runtime.h>

#include "../common/workload.h"
#include "../common/nist_vectors.h"

#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z)     (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)    (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)        (ROTRIGHT(x,2)  ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x)        (ROTRIGHT(x,6)  ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x)       (ROTRIGHT(x,7)  ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x)       (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

__device__ static const uint32_t K[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,
    0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,
    0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,
    0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,
    0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,
    0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,
    0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,
    0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,
    0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

typedef struct {
    uint8_t  data[64];
    uint32_t datalen;
    uint64_t bitlen;
    uint32_t state[8];
} SHA256_CTX_GPU;

__device__ static void sha256_transform_gpu(SHA256_CTX_GPU *ctx, const uint8_t *data)
{
    uint32_t a,b,c,d,e,f,g,h,i,j,t1,t2,m[64];

    for (i=0,j=0; i<16; ++i,j+=4)
        m[i] = ((uint32_t)data[j]<<24)|((uint32_t)data[j+1]<<16)|
               ((uint32_t)data[j+2]<<8)|((uint32_t)data[j+3]);

    for (; i<64; ++i)
        m[i] = SIG1(m[i-2]) + m[i-7] + SIG0(m[i-15]) + m[i-16];

    a=ctx->state[0]; b=ctx->state[1]; c=ctx->state[2]; d=ctx->state[3];
    e=ctx->state[4]; f=ctx->state[5]; g=ctx->state[6]; h=ctx->state[7];

    for (i=0; i<64; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + K[i] + m[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1;
        d=c; c=b; b=a; a=t1+t2;
    }

    ctx->state[0]+=a; ctx->state[1]+=b; ctx->state[2]+=c; ctx->state[3]+=d;
    ctx->state[4]+=e; ctx->state[5]+=f; ctx->state[6]+=g; ctx->state[7]+=h;
}

__device__ static void sha256_init_gpu(SHA256_CTX_GPU *ctx)
{
    ctx->datalen = 0;
    ctx->bitlen  = 0;
    ctx->state[0]=0x6a09e667; ctx->state[1]=0xbb67ae85;
    ctx->state[2]=0x3c6ef372; ctx->state[3]=0xa54ff53a;
    ctx->state[4]=0x510e527f; ctx->state[5]=0x9b05688c;
    ctx->state[6]=0x1f83d9ab; ctx->state[7]=0x5be0cd19;
}

__device__ static void sha256_update_gpu(SHA256_CTX_GPU *ctx, const uint8_t *data, size_t len)
{
    for (size_t i=0; i<len; ++i) {
        ctx->data[ctx->datalen++] = data[i];
        if (ctx->datalen == 64) {
            sha256_transform_gpu(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

__device__ static void sha256_final_gpu(SHA256_CTX_GPU *ctx, uint8_t *hash)
{
    uint32_t i = ctx->datalen;
    ctx->bitlen += (uint64_t)ctx->datalen * 8;
    if (ctx->datalen < 56) {
        ctx->data[i++] = 0x80;
        while (i < 56) ctx->data[i++] = 0x00;
    } else {
        ctx->data[i++] = 0x80;
        while (i < 64) ctx->data[i++] = 0x00;
        sha256_transform_gpu(ctx, ctx->data);
        memset(ctx->data, 0, 56);
    }
    ctx->data[63]=  ctx->bitlen        & 0xff;
    ctx->data[62]= (ctx->bitlen >>  8) & 0xff;
    ctx->data[61]= (ctx->bitlen >> 16) & 0xff;
    ctx->data[60]= (ctx->bitlen >> 24) & 0xff;
    ctx->data[59]= (ctx->bitlen >> 32) & 0xff;
    ctx->data[58]= (ctx->bitlen >> 40) & 0xff;
    ctx->data[57]= (ctx->bitlen >> 48) & 0xff;
    ctx->data[56]= (ctx->bitlen >> 56) & 0xff;
    sha256_transform_gpu(ctx, ctx->data);
    for (i=0; i<4; ++i) {
        hash[i]    = (ctx->state[0] >> (24-i*8)) & 0xff;
        hash[i+4]  = (ctx->state[1] >> (24-i*8)) & 0xff;
        hash[i+8]  = (ctx->state[2] >> (24-i*8)) & 0xff;
        hash[i+12] = (ctx->state[3] >> (24-i*8)) & 0xff;
        hash[i+16] = (ctx->state[4] >> (24-i*8)) & 0xff;
        hash[i+20] = (ctx->state[5] >> (24-i*8)) & 0xff;
        hash[i+24] = (ctx->state[6] >> (24-i*8)) & 0xff;
        hash[i+28] = (ctx->state[7] >> (24-i*8)) & 0xff;
    }
}

__global__ void sha256_kernel_v1(const uint8_t * __restrict__ d_in, uint8_t * __restrict__ d_out, long chunk_size, long num_chunks)
{
    long i = (long)blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= num_chunks) return;

    SHA256_CTX_GPU ctx;
    sha256_init_gpu(&ctx);
    sha256_update_gpu(&ctx, d_in + (i * chunk_size), chunk_size);
    sha256_final_gpu(&ctx, d_out + (i * 32));
}

__global__ void xor_reduce_kernel(const uint8_t * __restrict__ d_in, uint8_t * __restrict__ d_out, long num_chunks) {
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

#define checkCudaErrors(val) check_cuda((val), #val, __FILE__, __LINE__)
static inline void check_cuda(cudaError_t result, char const *const func, const char *const file, int const line) {
    if (result != cudaSuccess) {
        fprintf(stderr, "CUDA error at %s:%d code=%d(%s) \"%s\" \n",
                file, line, (unsigned int)result, cudaGetErrorName(result), func);
        exit(EXIT_FAILURE);
    }
}

int main(int argc, char *argv[])
{
    const char *filepath = "dummy_1GB.bin";
    size_t chunk_size = 64;
    int runs = 5;
    OutputMode out_mode = OUTPUT_MODE_FULL;
    StagingMode stg_mode = STAGING_PINNED;
    const char *save_digests_path = NULL;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--file") == 0 && i + 1 < argc) {
            filepath = argv[++i];
        } else if (strcmp(argv[i], "--chunk-size") == 0 && i + 1 < argc) {
            chunk_size = (size_t)atol(argv[++i]);
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
            /* Support legacy positional argument: <file> <chunk_size> [runs] */
            filepath = argv[1];
            if (i + 1 < argc && argv[i+1][0] != '-') chunk_size = (size_t)atol(argv[++i]);
            if (i + 1 < argc && argv[i+1][0] != '-') runs = atoi(argv[++i]);
        }
    }

    uint8_t *h_in = NULL;
    uint8_t *h_pinned_stage = NULL;

    /* Query file size */
    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);
    size_t file_bytes = (size_t)ftell(fp);
    fseek(fp, 0, SEEK_SET);

    size_t num_chunks = file_bytes / chunk_size;
    size_t blocks_per_chunk = compute_blocks_per_chunk(chunk_size);
    size_t payload_bytes = num_chunks * chunk_size;

    if (stg_mode == STAGING_PINNED) {
        checkCudaErrors(cudaMallocHost(&h_in, file_bytes));
    } else {
        h_in = (uint8_t *)malloc(file_bytes);
        checkCudaErrors(cudaMallocHost(&h_pinned_stage, file_bytes));
    }

    size_t read_bytes = fread(h_in, 1, file_bytes, fp);
    fclose(fp);
    if (read_bytes != file_bytes) {
        fprintf(stderr, "Error reading full file\n");
        return 1;
    }

    uint8_t *h_out = NULL;
    checkCudaErrors(cudaMallocHost(&h_out, num_chunks * 32));

    fprintf(stderr, "[GPU v1] File: %s (%zu B) | C: %zu B | N: %zu | B: %zu | Staging: %s | OutMode: %s | Runs: %d\n",
            filepath, file_bytes, chunk_size, num_chunks, blocks_per_chunk,
            (stg_mode == STAGING_PINNED) ? "PINNED" : "PAGEABLE",
            (out_mode == OUTPUT_MODE_FULL) ? "FULL" : "REDUCE", runs);

    /* Allocate device buffers */
    uint8_t *d_in, *d_out, *d_reduced;
    checkCudaErrors(cudaMalloc(&d_in, file_bytes));
    checkCudaErrors(cudaMalloc(&d_out, num_chunks * 32));
    checkCudaErrors(cudaMalloc(&d_reduced, 32));

    int threadsPerBlock = 256;
    int blocksPerGrid = (int)((num_chunks + threadsPerBlock - 1) / threadsPerBlock);

    for (int r = 0; r < runs; r++) {
        /* ── Measure kernel-only time ── */
        checkCudaErrors(cudaMemcpy(d_in, (stg_mode == STAGING_PINNED) ? h_in : h_in, file_bytes, cudaMemcpyHostToDevice));
        checkCudaErrors(cudaDeviceSynchronize());

        cudaEvent_t start_kernel, stop_kernel;
        checkCudaErrors(cudaEventCreate(&start_kernel));
        checkCudaErrors(cudaEventCreate(&stop_kernel));
        checkCudaErrors(cudaEventRecord(start_kernel));

        sha256_kernel_v1<<<blocksPerGrid, threadsPerBlock>>>(d_in, d_out, chunk_size, num_chunks);
        checkCudaErrors(cudaGetLastError());

        checkCudaErrors(cudaEventRecord(stop_kernel));
        checkCudaErrors(cudaEventSynchronize(stop_kernel));

        float ms_kernel = 0;
        checkCudaErrors(cudaEventElapsedTime(&ms_kernel, start_kernel, stop_kernel));
        double time_kernel_s = ms_kernel / 1000.0;
        checkCudaErrors(cudaEventDestroy(start_kernel));
        checkCudaErrors(cudaEventDestroy(stop_kernel));

        /* ── Measure E2E time ── */
        checkCudaErrors(cudaDeviceSynchronize());

        cudaEvent_t start_total, stop_total;
        checkCudaErrors(cudaEventCreate(&start_total));
        checkCudaErrors(cudaEventCreate(&stop_total));
        checkCudaErrors(cudaEventRecord(start_total));

        const uint8_t *src_h2d = h_in;
        if (stg_mode == STAGING_PAGEABLE) {
            /* Pageable to pinned staging copy included in E2E */
            memcpy(h_pinned_stage, h_in, file_bytes);
            src_h2d = h_pinned_stage;
        }

        checkCudaErrors(cudaMemcpy(d_in, src_h2d, file_bytes, cudaMemcpyHostToDevice));

        sha256_kernel_v1<<<blocksPerGrid, threadsPerBlock>>>(d_in, d_out, chunk_size, num_chunks);
        checkCudaErrors(cudaGetLastError());

        uint8_t h_reduced[32];
        if (out_mode == OUTPUT_MODE_FULL) {
            checkCudaErrors(cudaMemcpy(h_out, d_out, num_chunks * 32, cudaMemcpyDeviceToHost));
        } else {
            checkCudaErrors(cudaMemset(d_reduced, 0, 32));
            xor_reduce_kernel<<<64, 256>>>(d_out, d_reduced, num_chunks);
            checkCudaErrors(cudaMemcpy(h_reduced, d_reduced, 32, cudaMemcpyDeviceToHost));
        }

        checkCudaErrors(cudaEventRecord(stop_total));
        checkCudaErrors(cudaEventSynchronize(stop_total));

        float ms_total = 0;
        checkCudaErrors(cudaEventElapsedTime(&ms_total, start_total, stop_total));
        double time_total_s = ms_total / 1000.0;
        checkCudaErrors(cudaEventDestroy(start_total));
        checkCudaErrors(cudaEventDestroy(stop_total));

        double tput_kernel_gbs = ((double)payload_bytes / time_kernel_s) / 1e9;
        double tput_e2e_gbs = ((double)payload_bytes / time_total_s) / 1e9;
        double hashes_per_sec = (double)num_chunks / time_total_s;
        double blocks_per_sec = ((double)num_chunks * (double)blocks_per_chunk) / time_total_s;

        char hex_chunk0[65];
        digest_to_hex(h_out, hex_chunk0);

        char hex_reduced[65] = "none";
        if (out_mode == OUTPUT_MODE_REDUCE) {
            digest_to_hex(h_reduced, hex_reduced);
        }

        printf("RUN %d TIME_KERNEL_S %.6f TIME_E2E_S %.6f THROUGHPUT_KERNEL_GBS %.6f THROUGHPUT_E2E_GBS %.6f HASHES_PER_SEC %.2f BLOCKS_PER_SEC %.2f CHUNK_0_HASH %s REDUCED_HASH %s\n",
               r + 1, time_kernel_s, time_total_s, tput_kernel_gbs, tput_e2e_gbs, hashes_per_sec, blocks_per_sec, hex_chunk0, hex_reduced);
        fflush(stdout);
    }

    if (save_digests_path && out_mode == OUTPUT_MODE_FULL) {
        fprintf(stderr, "[GPU v1] Saving full digests (%zu bytes) to '%s'...\n", num_chunks * 32, save_digests_path);
        save_digests_file(save_digests_path, h_out, num_chunks * 32);
    }

    checkCudaErrors(cudaFree(d_in));
    checkCudaErrors(cudaFree(d_out));
    checkCudaErrors(cudaFree(d_reduced));
    checkCudaErrors(cudaFreeHost(h_out));
    if (stg_mode == STAGING_PINNED) checkCudaErrors(cudaFreeHost(h_in));
    else { free(h_in); checkCudaErrors(cudaFreeHost(h_pinned_stage)); }

    return 0;
}
