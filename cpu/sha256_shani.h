#ifndef SHA256_SHANI_H
#define SHA256_SHANI_H

#include <immintrin.h>
#include <tmmintrin.h>
#include <smmintrin.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>

static const uint32_t K256_SHANI[64] = {
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

static inline void sha256_transform_shani(__m128i *state0, __m128i *state1, const uint8_t *data) {
    __m128i MASK = _mm_set_epi64x(0x0c0d0e0f08090a0bULL, 0x0405060700010203ULL);
    
    __m128i msg0 = _mm_shuffle_epi8(_mm_loadu_si128((const __m128i*)(data + 0)), MASK);
    __m128i msg1 = _mm_shuffle_epi8(_mm_loadu_si128((const __m128i*)(data + 16)), MASK);
    __m128i msg2 = _mm_shuffle_epi8(_mm_loadu_si128((const __m128i*)(data + 32)), MASK);
    __m128i msg3 = _mm_shuffle_epi8(_mm_loadu_si128((const __m128i*)(data + 48)), MASK);

    __m128i abef = *state0;
    __m128i cdgh = *state1;
    __m128i abef_orig = abef;
    __m128i cdgh_orig = cdgh;

    __m128i tmp, msg_k;

    /* Rounds 0-3 */
    msg_k = _mm_add_epi32(msg0, _mm_loadu_si128((const __m128i*)(K256_SHANI + 0)));
    cdgh = _mm_sha256rnds2_epu32(cdgh, abef, msg_k);
    msg_k = _mm_shuffle_epi32(msg_k, 0x0E);
    abef = _mm_sha256rnds2_epu32(abef, cdgh, msg_k);

    /* Rounds 4-7 */
    msg_k = _mm_add_epi32(msg1, _mm_loadu_si128((const __m128i*)(K256_SHANI + 4)));
    cdgh = _mm_sha256rnds2_epu32(cdgh, abef, msg_k);
    msg_k = _mm_shuffle_epi32(msg_k, 0x0E);
    abef = _mm_sha256rnds2_epu32(abef, cdgh, msg_k);

    /* Rounds 8-11 */
    msg_k = _mm_add_epi32(msg2, _mm_loadu_si128((const __m128i*)(K256_SHANI + 8)));
    cdgh = _mm_sha256rnds2_epu32(cdgh, abef, msg_k);
    msg_k = _mm_shuffle_epi32(msg_k, 0x0E);
    abef = _mm_sha256rnds2_epu32(abef, cdgh, msg_k);

    /* Rounds 12-15 */
    msg_k = _mm_add_epi32(msg3, _mm_loadu_si128((const __m128i*)(K256_SHANI + 12)));
    cdgh = _mm_sha256rnds2_epu32(cdgh, abef, msg_k);
    msg_k = _mm_shuffle_epi32(msg_k, 0x0E);
    abef = _mm_sha256rnds2_epu32(abef, cdgh, msg_k);

    /* Rounds 16-63 */
    #define ROUND_BLOCK(i, m0, m1, m2, m3) \
        m0 = _mm_sha256msg1_epu32(m0, m1); \
        tmp = _mm_alignr_epi8(m3, m2, 4); \
        m0 = _mm_add_epi32(m0, tmp); \
        m0 = _mm_sha256msg2_epu32(m0, m3); \
        msg_k = _mm_add_epi32(m0, _mm_loadu_si128((const __m128i*)(K256_SHANI + (i)))); \
        cdgh = _mm_sha256rnds2_epu32(cdgh, abef, msg_k); \
        msg_k = _mm_shuffle_epi32(msg_k, 0x0E); \
        abef = _mm_sha256rnds2_epu32(abef, cdgh, msg_k);

    ROUND_BLOCK(16, msg0, msg1, msg2, msg3);
    ROUND_BLOCK(20, msg1, msg2, msg3, msg0);
    ROUND_BLOCK(24, msg2, msg3, msg0, msg1);
    ROUND_BLOCK(28, msg3, msg0, msg1, msg2);

    ROUND_BLOCK(32, msg0, msg1, msg2, msg3);
    ROUND_BLOCK(36, msg1, msg2, msg3, msg0);
    ROUND_BLOCK(40, msg2, msg3, msg0, msg1);
    ROUND_BLOCK(44, msg3, msg0, msg1, msg2);

    ROUND_BLOCK(48, msg0, msg1, msg2, msg3);
    ROUND_BLOCK(52, msg1, msg2, msg3, msg0);
    ROUND_BLOCK(56, msg2, msg3, msg0, msg1);
    ROUND_BLOCK(60, msg3, msg0, msg1, msg2);

    #undef ROUND_BLOCK

    *state0 = _mm_add_epi32(abef, abef_orig);
    *state1 = _mm_add_epi32(cdgh, cdgh_orig);
}

static inline void sha256_shani(const uint8_t *data, size_t len, uint8_t *digest) {
    __m128i state0 = _mm_set_epi32(0x6a09e667, 0xbb67ae85, 0x510e527f, 0x9b05688c);
    __m128i state1 = _mm_set_epi32(0x3c6ef372, 0xa54ff53a, 0x1f83d9ab, 0x5be0cd19);

    size_t full_blocks = len / 64;
    for (size_t i = 0; i < full_blocks; i++) {
        sha256_transform_shani(&state0, &state1, data + i * 64);
    }

    uint8_t tail[128];
    memset(tail, 0, sizeof(tail));
    size_t rem = len % 64;
    if (rem > 0) {
        memcpy(tail, data + full_blocks * 64, rem);
    }
    tail[rem] = 0x80;

    size_t total_pad_blocks = (rem < 56) ? 1 : 2;
    uint64_t bit_len = (uint64_t)len * 8ULL;
    size_t len_pos = total_pad_blocks * 64 - 8;
    for (int i = 0; i < 8; i++) {
        tail[len_pos + i] = (uint8_t)(bit_len >> ((7 - i) * 8));
    }

    for (size_t b = 0; b < total_pad_blocks; b++) {
        sha256_transform_shani(&state0, &state1, tail + b * 64);
    }

    uint32_t s0[4], s1[4];
    _mm_storeu_si128((__m128i*)s0, state0);
    _mm_storeu_si128((__m128i*)s1, state1);

    uint32_t a = s0[3], b = s0[2], e = s0[1], f = s0[0];
    uint32_t c = s1[3], d = s1[2], g = s1[1], h = s1[0];

    digest[0]  = (uint8_t)(a >> 24); digest[1]  = (uint8_t)(a >> 16);
    digest[2]  = (uint8_t)(a >> 8);  digest[3]  = (uint8_t)(a);
    digest[4]  = (uint8_t)(b >> 24); digest[5]  = (uint8_t)(b >> 16);
    digest[6]  = (uint8_t)(b >> 8);  digest[7]  = (uint8_t)(b);
    digest[8]  = (uint8_t)(c >> 24); digest[9]  = (uint8_t)(c >> 16);
    digest[10] = (uint8_t)(c >> 8);  digest[11] = (uint8_t)(c);
    digest[12] = (uint8_t)(d >> 24); digest[13] = (uint8_t)(d >> 16);
    digest[14] = (uint8_t)(d >> 8);  digest[15] = (uint8_t)(d);
    digest[16] = (uint8_t)(e >> 24); digest[17] = (uint8_t)(e >> 16);
    digest[18] = (uint8_t)(e >> 8);  digest[19] = (uint8_t)(e);
    digest[20] = (uint8_t)(f >> 24); digest[21] = (uint8_t)(f >> 16);
    digest[22] = (uint8_t)(f >> 8);  digest[23] = (uint8_t)(f);
    digest[24] = (uint8_t)(g >> 24); digest[25] = (uint8_t)(g >> 16);
    digest[26] = (uint8_t)(g >> 8);  digest[27] = (uint8_t)(g);
    digest[28] = (uint8_t)(h >> 24); digest[29] = (uint8_t)(h >> 16);
    digest[30] = (uint8_t)(h >> 8);  digest[31] = (uint8_t)(h);
}

#endif /* SHA256_SHANI_H */
