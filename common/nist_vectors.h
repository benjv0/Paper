#ifndef NIST_VECTORS_H
#define NIST_VECTORS_H

#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* NIST SHA-256 Test Vectors */

typedef struct {
    const char *name;
    const uint8_t *data;
    size_t len;
    const char *expected_hex;
} NistVector;

/* Vector 1: Empty string */
static const uint8_t NIST_MSG_1[] = "";
static const char *NIST_HEX_1 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

/* Vector 2: "abc" */
static const uint8_t NIST_MSG_2[] = "abc";
static const char *NIST_HEX_2 = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";

/* Vector 3: 448 bits = 56 bytes */
static const uint8_t NIST_MSG_3[] = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
static const char *NIST_HEX_3 = "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1";

/* Vector 4: 1,000,000 repetitions of 'a' */
static const char *NIST_HEX_4 = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0";

static inline void digest_to_hex(const uint8_t *digest, char *out_hex) {
    for (int i = 0; i < 32; i++) {
        sprintf(out_hex + i * 2, "%02x", digest[i]);
    }
    out_hex[64] = '\0';
}

typedef void (*sha256_fn_t)(const uint8_t *data, size_t len, uint8_t *digest_out);

/* Verifies all 4 NIST test vectors. Returns 0 on success, non-zero on failure. */
static inline int verify_nist_vectors(sha256_fn_t sha_fn, const char *impl_name) {
    uint8_t digest[32];
    char hex[65];

    printf("[VERIFY] Testing NIST vectors on %s...\n", impl_name);

    /* V1: Empty */
    sha_fn(NIST_MSG_1, 0, digest);
    digest_to_hex(digest, hex);
    if (strcmp(hex, NIST_HEX_1) != 0) {
        fprintf(stderr, "[FAILED] NIST V1 (Empty)\n  Expected: %s\n  Got:      %s\n", NIST_HEX_1, hex);
        return 1;
    }

    /* V2: "abc" */
    sha_fn(NIST_MSG_2, 3, digest);
    digest_to_hex(digest, hex);
    if (strcmp(hex, NIST_HEX_2) != 0) {
        fprintf(stderr, "[FAILED] NIST V2 (\"abc\")\n  Expected: %s\n  Got:      %s\n", NIST_HEX_2, hex);
        return 2;
    }

    /* V3: 448-bit (56 bytes) */
    sha_fn(NIST_MSG_3, 56, digest);
    digest_to_hex(digest, hex);
    if (strcmp(hex, NIST_HEX_3) != 0) {
        fprintf(stderr, "[FAILED] NIST V3 (448-bit)\n  Expected: %s\n  Got:      %s\n", NIST_HEX_3, hex);
        return 3;
    }

    /* V4: 1,000,000 'a' */
    uint8_t *million_a = (uint8_t *)malloc(1000000);
    if (!million_a) {
        fprintf(stderr, "[ERROR] Out of memory allocating 1M 'a'\n");
        return 4;
    }
    memset(million_a, 'a', 1000000);
    sha_fn(million_a, 1000000, digest);
    digest_to_hex(digest, hex);
    free(million_a);

    if (strcmp(hex, NIST_HEX_4) != 0) {
        fprintf(stderr, "[FAILED] NIST V4 (1,000,000 'a')\n  Expected: %s\n  Got:      %s\n", NIST_HEX_4, hex);
        return 5;
    }

    printf("[PASS] All 4 NIST vectors verified successfully on %s.\n", impl_name);
    return 0;
}

#endif /* NIST_VECTORS_H */
