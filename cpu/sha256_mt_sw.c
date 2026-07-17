#define _POSIX_C_SOURCE 200809L
/*
 * sha256_mt_sw.c — Multi-threaded SHA-256 Software benchmark
 *
 * Splits the input file into N equal chunks and hashes each chunk
 * in a separate pthread, using the pure-C SHA-256 implementation.
 * Compiled WITHOUT Intel SHA-NI (-mno-sha).
 *
 * Wall-clock time is measured around pthread_create → pthread_join,
 * so it captures the real end-to-end latency seen by the caller.
 *
 * Aggregate throughput = file_size / wall_time  (all bytes / all cores)
 *
 * Usage: ./sha256_mt_sw <file> <num_threads> [runs]
 * Output: SUMMARY MT_SW THREADS N WALL_S x AVG_AGGREGATE_MBS x STDEV_S x FILE_BYTES x
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <errno.h>

/* ─── SHA-256 pure C (same as sha256_sw.c) ────────────────────────── */

#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z)     (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z)    (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x)        (ROTRIGHT(x,2)  ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x)        (ROTRIGHT(x,6)  ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x)       (ROTRIGHT(x,7)  ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x)       (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

static const uint32_t K[64] = {
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
} SHA256_CTX_SW;

static void sha256_transform(SHA256_CTX_SW *ctx, const uint8_t *data)
{
    uint32_t a,b,c,d,e,f,g,h,i,j,t1,t2,m[64];
    for (i=0,j=0;i<16;++i,j+=4)
        m[i]=((uint32_t)data[j]<<24)|((uint32_t)data[j+1]<<16)|
             ((uint32_t)data[j+2]<<8)|((uint32_t)data[j+3]);
    for (;i<64;++i)
        m[i]=SIG1(m[i-2])+m[i-7]+SIG0(m[i-15])+m[i-16];
    a=ctx->state[0];b=ctx->state[1];c=ctx->state[2];d=ctx->state[3];
    e=ctx->state[4];f=ctx->state[5];g=ctx->state[6];h=ctx->state[7];
    for (i=0;i<64;++i){
        t1=h+EP1(e)+CH(e,f,g)+K[i]+m[i];
        t2=EP0(a)+MAJ(a,b,c);
        h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
    }
    ctx->state[0]+=a;ctx->state[1]+=b;ctx->state[2]+=c;ctx->state[3]+=d;
    ctx->state[4]+=e;ctx->state[5]+=f;ctx->state[6]+=g;ctx->state[7]+=h;
}

static void sha256_init(SHA256_CTX_SW *ctx) {
    ctx->datalen=0; ctx->bitlen=0;
    ctx->state[0]=0x6a09e667;ctx->state[1]=0xbb67ae85;
    ctx->state[2]=0x3c6ef372;ctx->state[3]=0xa54ff53a;
    ctx->state[4]=0x510e527f;ctx->state[5]=0x9b05688c;
    ctx->state[6]=0x1f83d9ab;ctx->state[7]=0x5be0cd19;
}

static void sha256_update(SHA256_CTX_SW *ctx, const uint8_t *data, size_t len) {
    for (size_t i=0;i<len;++i){
        ctx->data[ctx->datalen++]=data[i];
        if (ctx->datalen==64){
            sha256_transform(ctx,ctx->data);
            ctx->bitlen+=512; ctx->datalen=0;
        }
    }
}

static void sha256_final(SHA256_CTX_SW *ctx, uint8_t *hash) {
    uint32_t i=ctx->datalen;
    if (ctx->datalen<56){
        ctx->data[i++]=0x80;
        while(i<56)ctx->data[i++]=0x00;
    } else {
        ctx->data[i++]=0x80;
        while(i<64)ctx->data[i++]=0x00;
        sha256_transform(ctx,ctx->data);
        memset(ctx->data,0,56);
    }
    ctx->bitlen+=(uint64_t)ctx->datalen*8;
    ctx->data[63]=ctx->bitlen&0xff;
    ctx->data[62]=(ctx->bitlen>>8)&0xff;
    ctx->data[61]=(ctx->bitlen>>16)&0xff;
    ctx->data[60]=(ctx->bitlen>>24)&0xff;
    ctx->data[59]=(ctx->bitlen>>32)&0xff;
    ctx->data[58]=(ctx->bitlen>>40)&0xff;
    ctx->data[57]=(ctx->bitlen>>48)&0xff;
    ctx->data[56]=(ctx->bitlen>>56)&0xff;
    sha256_transform(ctx,ctx->data);
    for(i=0;i<4;++i){
        hash[i]   =(ctx->state[0]>>(24-i*8))&0xff;
        hash[i+4] =(ctx->state[1]>>(24-i*8))&0xff;
        hash[i+8] =(ctx->state[2]>>(24-i*8))&0xff;
        hash[i+12]=(ctx->state[3]>>(24-i*8))&0xff;
        hash[i+16]=(ctx->state[4]>>(24-i*8))&0xff;
        hash[i+20]=(ctx->state[5]>>(24-i*8))&0xff;
        hash[i+24]=(ctx->state[6]>>(24-i*8))&0xff;
        hash[i+28]=(ctx->state[7]>>(24-i*8))&0xff;
    }
}

/* ─── Thread work unit ─────────────────────────────────────────────── */

#define BUF_SIZE (4 * 1024 * 1024)

typedef struct {
    const char *filepath;
    long        offset;       /* byte offset into file for this chunk */
    long        length;       /* bytes this thread must hash */
    double      elapsed_s;    /* output: wall time for this thread */
    double      throughput_mbs;
    uint8_t     hash[32];
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

    SHA256_CTX_SW ctx;
    sha256_init(&ctx);

    long remaining = a->length;
    double t0 = get_time_s();

    while (remaining > 0) {
        size_t to_read = (remaining < (long)BUF_SIZE) ? (size_t)remaining : BUF_SIZE;
        size_t n = fread(buf, 1, to_read, fp);
        if (n == 0) break;
        sha256_update(&ctx, buf, n);
        remaining -= (long)n;
    }

    sha256_final(&ctx, a->hash);
    a->elapsed_s = get_time_s() - t0;
    a->throughput_mbs = ((double)a->length / (1024.0*1024.0)) / a->elapsed_s;

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

    const char *filepath   = argv[1];
    int         nthreads   = atoi(argv[2]);
    int         runs       = (argc >= 4) ? atoi(argv[3]) : 5;

    if (nthreads < 1 || nthreads > 64) {
        fprintf(stderr, "num_threads must be 1–64\n"); return 1;
    }

    /* get file size */
    FILE *fp = fopen(filepath, "rb");
    if (!fp) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);
    long file_bytes = ftell(fp);
    fclose(fp);

    long chunk = file_bytes / nthreads;

    fprintf(stderr, "[MT_SW] File: %s  Size: %ld bytes  Threads: %d  Runs: %d\n",
            filepath, file_bytes, nthreads, runs);

    pthread_t   *threads = malloc(sizeof(pthread_t)   * (size_t)nthreads);
    ThreadArg   *args    = malloc(sizeof(ThreadArg)   * (size_t)nthreads);

    double total_wall = 0.0, total_wall_sq = 0.0;
    double total_agg  = 0.0;

    for (int r = 0; r < runs; r++) {

        /* set up thread arguments */
        for (int t = 0; t < nthreads; t++) {
            args[t].filepath  = filepath;
            args[t].thread_id = t;
            args[t].offset    = (long)t * chunk;
            /* last thread takes any remaining bytes */
            args[t].length = (t == nthreads-1)
                             ? file_bytes - (long)t * chunk
                             : chunk;
        }

        /* launch all threads simultaneously */
        double wall_start = get_time_s();
        for (int t = 0; t < nthreads; t++)
            pthread_create(&threads[t], NULL, thread_hash, &args[t]);

        /* wait for all */
        for (int t = 0; t < nthreads; t++)
            pthread_join(threads[t], NULL);
        double wall_elapsed = get_time_s() - wall_start;

        double agg_mbs = ((double)file_bytes / (1024.0*1024.0)) / wall_elapsed;

        /* per-thread breakdown */
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

    printf("SUMMARY MT_SW THREADS %d WALL_S %.6f STDEV_S %.6f "
           "AVG_AGGREGATE_MBS %.3f FILE_BYTES %ld\n",
           nthreads, avg_wall, stdev, avg_agg, file_bytes);

    free(threads);
    free(args);
    return 0;
}
