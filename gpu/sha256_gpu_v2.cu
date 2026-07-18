/*
 * sha256_gpu_v2.cu — High-Utilization CUDA SHA-256 Benchmark
 * ===========================================================
 * Target: NVIDIA GeForce RTX 2050 (GA107M, sm_86)
 *   16 SMs | 1536 max threads/SM | 48 warps/SM | 65536 regs/SM | 94.4 GB/s GDDR6
 *
 * Key optimizations vs v1:
 *  1. __constant__ K[64]           — warp-broadcast, zero L2 cache pressure
 *  2. Sliding-window w[16] not w[64] — saves 48 registers/thread:
 *       v1: ~100 regs/thread → 2 blocks/SM → 33% occupancy
 *       v2: ~34  regs/thread → 5+ blocks/SM → 83%+ occupancy
 *  3. __byte_perm() big-endian load  — 1 PTX instruction instead of 4 shifts
 *  4. #pragma unroll on all 64 rounds — zero loop overhead, max ILP
 *  5. Zero-copy padding block        — w[] computed inline, no local memory needed
 *  6. Grid-stride loop kernel        — always saturates all 16 SMs
 *  7. Pinned (page-locked) host mem  — enables async DMA via cudaMemcpyAsync
 *  8. Triple CUDA streams            — overlaps H2D, compute, D2H simultaneously
 *
 * Usage:  ./sha256_gpu_v2 <file> <chunk_size> [runs]
 *         chunk_size MUST be a multiple of 64 bytes.
 *         Recommended: 4096, 16384, 65536, 262144 (4KB, 16KB, 64KB, 256KB)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <cuda_runtime.h>

/* ── SHA-256 macros ────────────────────────────────────────────────────────── */
#define ROTR32(x,n)  (((x) >> (n)) | ((x) << (32-(n))))
#define CH(x,y,z)    (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)   (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)       (ROTR32((x), 2) ^ ROTR32((x),13) ^ ROTR32((x),22))
#define EP1(x)       (ROTR32((x), 6) ^ ROTR32((x),11) ^ ROTR32((x),25))
#define SIG0(x)      (ROTR32((x), 7) ^ ROTR32((x),18) ^ ((x) >> 3))
#define SIG1(x)      (ROTR32((x),17) ^ ROTR32((x),19) ^ ((x) >> 10))

/* Optimization 1: K in __constant__ memory — one hardware broadcast per warp    */
/* All 32 threads in a warp read K_CONST[i] simultaneously → single transaction  */
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

/* SHA-256 IV in __constant__ memory                                              */
__constant__ uint32_t SHA256_IV[8] = {
    0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,
    0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u
};

/* ── Optimized SHA-256 block compression ──────────────────────────────────────
 *
 * Optimization 2: Sliding window w[16] (circular buffer) instead of w[64].
 *   Standard SHA-256 expands the 16-word message into 64 words. We avoid storing
 *   all 64 by updating in-place: w[i % 16] becomes w[i] the moment w[i-16] is
 *   no longer needed. This saves 48 × 4 = 192 bytes = 48 registers per thread.
 *
 * Optimization 3: __byte_perm() for big-endian word load.
 *   On little-endian x86/CUDA hosts, a raw uint32 load reverses byte order vs
 *   the SHA-256 big-endian specification. __byte_perm() corrects this in exactly
 *   one PTX instruction (sel.b32) rather than four shifts and three ORs.
 *   Selector 0x0123 maps: out[byte 0] ← in[byte 3], ..., out[byte 3] ← in[byte 0]
 *
 * Optimization 4: #pragma unroll exposes all 64 rounds as straight-line code,
 *   enabling the compiler to maximise instruction-level parallelism and eliminate
 *   branch misprediction penalties.
 * ─────────────────────────────────────────────────────────────────────────── */
__device__ static __forceinline__ void sha256_compress(
    uint32_t s[8], const uint8_t *blk)
{
    uint32_t w[16];   /* 16 registers instead of 64 — the key saving */

    /* Load 16 big-endian SHA-256 message words with a single PTX instruction */
    #pragma unroll 16
    for (int i = 0; i < 16; ++i) {
        uint32_t raw;
        memcpy(&raw, blk + i * 4, 4);
        w[i] = __byte_perm(raw, 0u, 0x0123u);  /* byte-swap: 1 instruction */
    }

    uint32_t a=s[0],b=s[1],c=s[2],d=s[3],e=s[4],f=s[5],g=s[6],h=s[7];
    uint32_t t1, t2;

    /* Rounds 0–15: message schedule already in w[0..15] */
    #pragma unroll 16
    for (int i = 0; i < 16; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + K_CONST[i] + w[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h=g; g=f; f=e; e=d+t1; d=c; c=b; b=a; a=t1+t2;
    }

    /* Rounds 16–63: expand message schedule in the sliding window.
     * w[j] (j = i & 15) holds w[i-16] before the assignment and w[i] after.
     * All prior values needed (w[i-2], w[i-7], w[i-15]) are already updated
     * in earlier iterations, so the circular addressing is always correct.   */
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

/* Optimization 5: Padding block computed inline using known uint32 values.
 * When chunk_size is a multiple of 64 the data fills an integer number of
 * SHA-256 blocks exactly, so the padding block is always:
 *   w[0] = 0x80000000 | w[1..13] = 0 | w[14] = bit_len_hi | w[15] = bit_len_lo
 * We materialise this as a local w[] array and call a specialised compressor,
 * avoiding any local-memory (stack) byte buffer.                               */
__device__ static __forceinline__ void sha256_compress_padding(
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

/* Helper: write uint32 big-endian into byte buffer */
__device__ static __forceinline__ void write_be32(uint8_t *p, uint32_t v)
{
    p[0]=(v>>24)&0xff; p[1]=(v>>16)&0xff; p[2]=(v>>8)&0xff; p[3]=v&0xff;
}

/* ── Main CUDA kernel ──────────────────────────────────────────────────────────
 *
 * Optimization 6: Grid-stride loop.
 *   Instead of launching exactly one thread per chunk (which may leave SMs idle
 *   at the tail), we launch a FIXED number of threads equal to the GPU's maximum
 *   concurrent occupancy and have each thread process multiple chunks in a stride.
 *   This guarantees that all 16 SMs are always occupied, from first to last chunk.
 * ─────────────────────────────────────────────────────────────────────────── */
__global__ void sha256_kernel_v2(
    const uint8_t * __restrict__ d_in,
    uint8_t       * __restrict__ d_out,
    int chunk_size,         /* bytes per chunk; must be multiple of 64 */
    int num_blocks_data,    /* SHA-256 blocks per chunk = chunk_size / 64 */
    long num_chunks)
{
    /* Grid-stride: each thread steps by the total number of launched threads */
    for (long idx = (long)blockIdx.x * blockDim.x + threadIdx.x;
         idx < num_chunks;
         idx += (long)gridDim.x * blockDim.x)
    {
        /* Initialise SHA-256 state from IV */
        uint32_t s[8];
        #pragma unroll 8
        for (int i = 0; i < 8; ++i) s[i] = SHA256_IV[i];

        /* Process all data blocks for this chunk */
        const uint8_t *src = d_in + (long)idx * chunk_size;
        for (int b = 0; b < num_blocks_data; ++b)
            sha256_compress(s, src + (long)b * 64);

        /* Process the deterministic SHA-256 padding block */
        sha256_compress_padding(s, (uint64_t)chunk_size);

        /* Write 32-byte output hash (big-endian) */
        uint8_t *out = d_out + (long)idx * 32;
        #pragma unroll 8
        for (int i = 0; i < 8; ++i) write_be32(out + i*4, s[i]);
    }
}

/* ── CUDA error checking helper ───────────────────────────────────────────── */
#define CUDA_CHECK(v) cuda_check_((v),#v,__FILE__,__LINE__)
static void cuda_check_(cudaError_t r, const char *f, const char *file, int line)
{
    if (r != cudaSuccess) {
        fprintf(stderr,"CUDA error at %s:%d  %s\n  → %s\n",
                file, line, f, cudaGetErrorString(r));
        exit(1);
    }
}

/* ── Main ─────────────────────────────────────────────────────────────────── */
int main(int argc, char *argv[])
{
    if (argc < 3) {
        fprintf(stderr, "Usage: %s <file> <chunk_size> [runs]\n", argv[0]);
        fprintf(stderr, "  chunk_size must be a multiple of 64 bytes.\n");
        return 1;
    }

    const char *filepath  = argv[1];
    int         chunk_sz  = atoi(argv[2]);
    int         runs      = (argc >= 4) ? atoi(argv[3]) : 5;

    if (chunk_sz < 64 || chunk_sz % 64 != 0) {
        fprintf(stderr, "Error: chunk_size=%d is not a multiple of 64.\n", chunk_sz);
        return 1;
    }
    const int blocks_per_chunk = chunk_sz / 64;

    /* Open and read file */
    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);
    long file_bytes = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    long num_chunks = file_bytes / chunk_sz;
    if (num_chunks < 1) {
        fprintf(stderr, "File too small for chunk_size=%d\n", chunk_sz);
        fclose(fp); return 1;
    }
    long used_bytes = num_chunks * (long)chunk_sz;

    /* Optimization 7: Pinned (page-locked) host memory
     * cudaMallocHost allocates memory that bypasses the OS virtual memory system,
     * allowing the GPU's DMA engine to access it directly without a staging copy.
     * This increases practical PCIe bandwidth by up to 2× for async transfers.  */
    uint8_t *h_in, *h_out;
    CUDA_CHECK(cudaMallocHost(&h_in,  used_bytes));
    CUDA_CHECK(cudaMallocHost(&h_out, num_chunks * 32));

    fread(h_in, 1, used_bytes, fp);
    fclose(fp);

    /* Device buffers */
    uint8_t *d_in, *d_out;
    CUDA_CHECK(cudaMalloc(&d_in,  used_bytes));
    CUDA_CHECK(cudaMalloc(&d_out, num_chunks * 32));

    /* Query GPU occupancy parameters */
    cudaDeviceProp prop;
    CUDA_CHECK(cudaGetDeviceProperties(&prop, 0));

    /* Choose launch configuration:
     *   Target 100% occupancy on all SMs.
     *   With ~34 live registers/thread + maxrregcount=48: 5 blocks/SM achievable.
     *   We launch enough blocks to keep all SMs busy, and grid-stride handles
     *   any remaining chunks beyond the initially launched thread count.         */
    const int THREADS_PER_BLOCK = 256;
    /* 5 resident blocks per SM (based on register budget) × all SMs × 2× safety margin */
    int min_blocks = prop.multiProcessorCount * 5 * 2;
    long needed_blocks = (num_chunks + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    int grid_size = (int)(needed_blocks > min_blocks ? needed_blocks : min_blocks);
    /* Cap at hardware maximum to avoid scheduler overhead */
    int max_blocks = prop.multiProcessorCount * prop.maxThreadsPerMultiProcessor / THREADS_PER_BLOCK;
    if (grid_size > max_blocks * 4) grid_size = max_blocks * 4;

    fprintf(stderr,
        "[GPU v2] File: %ld B | Chunk: %d B | Chunks: %ld | "
        "Grid: %d blocks × %d threads | SMs: %d\n",
        file_bytes, chunk_sz, num_chunks,
        grid_size, THREADS_PER_BLOCK, prop.multiProcessorCount);

    /* Optimization 8: Triple CUDA streams
     * By dividing the workload into 3 equal segments and assigning each segment
     * to a different CUDA stream, we create a pipeline where:
     *   - Stream 0: H2D transfer of segment 0 → kernel on segment 0 → D2H
     *   - Stream 1: overlapping with S0 kernel: H2D segment 1 → kernel → D2H
     *   - Stream 2: same pattern, one pipeline stage behind S1
     * The RTX 2050 has independent Copy Engines for H2D and D2H, so data transfer
     * and kernel execution can proceed concurrently on separate engines.          */
    const int N_STREAMS = 3;
    cudaStream_t streams[N_STREAMS];
    for (int s = 0; s < N_STREAMS; ++s)
        CUDA_CHECK(cudaStreamCreate(&streams[s]));

    long chunks_per_stream = (num_chunks + N_STREAMS - 1) / N_STREAMS;

    for (int r = 0; r < runs; ++r) {

        /* ── Measure kernel-only time (pre-copy data, then time just the kernel) ── */
        CUDA_CHECK(cudaMemcpy(d_in, h_in, used_bytes, cudaMemcpyHostToDevice));
        CUDA_CHECK(cudaDeviceSynchronize());

        cudaEvent_t k_start, k_stop;
        cudaEventCreate(&k_start);
        cudaEventCreate(&k_stop);
        cudaEventRecord(k_start, 0);

        sha256_kernel_v2<<<grid_size, THREADS_PER_BLOCK>>>(
            d_in, d_out, chunk_sz, blocks_per_chunk, num_chunks);

        cudaEventRecord(k_stop, 0);
        cudaEventSynchronize(k_stop);
        float ms_kernel;
        cudaEventElapsedTime(&ms_kernel, k_start, k_stop);
        double time_kernel_s = ms_kernel / 1000.0;
        cudaEventDestroy(k_start);
        cudaEventDestroy(k_stop);

        /* ── Measure E2E time with triple-stream pipeline ── */
        CUDA_CHECK(cudaDeviceSynchronize());

        cudaEvent_t e_start, e_stop;
        cudaEventCreate(&e_start);
        cudaEventCreate(&e_stop);
        cudaEventRecord(e_start, 0);   /* record on default stream (after sync) */

        for (int s = 0; s < N_STREAMS; ++s) {
            long start_c = (long)s * chunks_per_stream;
            long end_c   = start_c + chunks_per_stream;
            if (end_c > num_chunks) end_c = num_chunks;
            if (start_c >= num_chunks) break;
            long n_c = end_c - start_c;

            long byte_off = start_c * (long)chunk_sz;
            long byte_len = n_c    * (long)chunk_sz;
            long hash_off = start_c * 32L;
            long hash_len = n_c    * 32L;

            /* Async H2D for this segment */
            CUDA_CHECK(cudaMemcpyAsync(d_in  + byte_off, h_in  + byte_off,
                                       byte_len, cudaMemcpyHostToDevice, streams[s]));

            /* Kernel for this segment (after H2D in same stream) */
            int seg_blocks = (int)((n_c + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK);
            if (seg_blocks < prop.multiProcessorCount * 5)
                seg_blocks = prop.multiProcessorCount * 5;

            sha256_kernel_v2<<<seg_blocks, THREADS_PER_BLOCK, 0, streams[s]>>>(
                d_in  + byte_off,
                d_out + hash_off,
                chunk_sz, blocks_per_chunk, n_c);

            /* Async D2H for this segment (after kernel in same stream) */
            CUDA_CHECK(cudaMemcpyAsync(h_out + hash_off, d_out + hash_off,
                                       hash_len, cudaMemcpyDeviceToHost, streams[s]));
        }

        CUDA_CHECK(cudaDeviceSynchronize());
        cudaEventRecord(e_stop, 0);
        cudaEventSynchronize(e_stop);
        float ms_e2e;
        cudaEventElapsedTime(&ms_e2e, e_start, e_stop);
        double time_e2e_s = ms_e2e / 1000.0;
        cudaEventDestroy(e_start);
        cudaEventDestroy(e_stop);

        /* Extract and print hash of first chunk for validation */
        char hex[65];
        for (int i = 0; i < 32; ++i)
            sprintf(hex + i*2, "%02x", h_out[i]);
        hex[64] = '\0';

        double tput_kernel = (used_bytes / 1048576.0) / time_kernel_s;
        double tput_e2e    = (used_bytes / 1048576.0) / time_e2e_s;

        printf("RUN %d TIME_KERNEL_S %.6f TIME_TOTAL_S %.6f "
               "THROUGHPUT_KERNEL_MBS %.3f THROUGHPUT_TOTAL_MBS %.3f "
               "CHUNK_0_HASH %s\n",
               r+1, time_kernel_s, time_e2e_s,
               tput_kernel, tput_e2e, hex);
        fflush(stdout);
    }

    /* Cleanup */
    for (int s = 0; s < N_STREAMS; ++s) CUDA_CHECK(cudaStreamDestroy(streams[s]));
    CUDA_CHECK(cudaFree(d_in));
    CUDA_CHECK(cudaFree(d_out));
    CUDA_CHECK(cudaFreeHost(h_in));
    CUDA_CHECK(cudaFreeHost(h_out));

    return 0;
}
