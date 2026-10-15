#!/usr/bin/env python3
"""
verify_digests.py — Rigorous Correctness Verification for SHA-256 Benchmark
===========================================================================
Verifies:
  1. NIST standard test vectors (empty, 'abc', 448-bit, 1M 'a').
  2. Output digest array against Python hashlib.sha256:
     - For C=64 B: full check of all N digests.
     - For C > 64 B: sample check of first 1,000,000 (or N) + 1,000,000 random chunks.
  3. Aborts with exit code 1 immediately on any discrepancy.
"""

import sys
import os
import math
import hashlib
import random
import argparse
from typing import Optional

# NIST Standard Vectors
NIST_VECTORS = [
    ("Empty String", b"", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    ("abc", b"abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    ("448-bit", b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq", "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"),
    ("1,000,000 'a'", b"a" * 1000000, "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")
]

def verify_nist():
    print("[VERIFY] Checking NIST test vectors against hashlib...")
    for name, data, expected in NIST_VECTORS:
        h = hashlib.sha256(data).hexdigest()
        if h != expected:
            print(f"[FAIL] NIST vector mismatch for '{name}':\n  Expected: {expected}\n  Got:      {h}", file=sys.stderr)
            sys.exit(1)
        print(f"  [✓] {name}: OK")
    print("[PASS] All NIST vectors matched.\n")

def verify_chunk_digests(data_file: str, digests_file: str, chunk_size: int, full_check: Optional[bool] = None):
    data_size = os.path.getsize(data_file)
    N = data_size // chunk_size
    expected_digests_size = N * 32
    actual_digests_size = os.path.getsize(digests_file)

    print(f"[VERIFY] Verifying digests from '{digests_file}' against '{data_file}'...")
    print(f"  File size:       {data_size} bytes")
    print(f"  Chunk size (C):  {chunk_size} bytes")
    print(f"  Total chunks (N):{N}")
    print(f"  Digests size:    {actual_digests_size} bytes (expected {expected_digests_size} bytes)")

    if actual_digests_size != expected_digests_size:
        print(f"[FAIL] Digest file size mismatch! Expected {expected_digests_size}, got {actual_digests_size}", file=sys.stderr)
        sys.exit(1)

    # Determine indices to verify
    if full_check or chunk_size == 64:
        print(f"[VERIFY] Running FULL verification of all {N:,} digests (C={chunk_size} B)...")
        indices_to_check = range(N)
    else:
        sample_first = min(N, 1_000_000)
        indices_set = set(range(sample_first))
        remaining = [i for i in range(sample_first, N)]
        if remaining:
            sample_random = min(len(remaining), 1_000_000)
            indices_set.update(random.sample(remaining, sample_random))
        indices_to_check = sorted(indices_set)
        print(f"[VERIFY] Running sample verification of {len(indices_to_check):,} digests (first 1M + random 1M)...")

    # Read memory-mapped or buffered
    import mmap
    with open(data_file, "rb") as df, open(digests_file, "rb") as hf:
        with mmap.mmap(df.fileno(), 0, access=mmap.ACCESS_READ) as mm_data, \
             mmap.mmap(hf.fileno(), 0, access=mmap.ACCESS_READ) as mm_hash:

            checked_count = 0
            for idx in indices_to_check:
                chunk = mm_data[idx * chunk_size : (idx + 1) * chunk_size]
                expected_digest = hashlib.sha256(chunk).digest()
                actual_digest = mm_hash[idx * 32 : (idx + 1) * 32]

                if actual_digest != expected_digest:
                    exp_hex = expected_digest.hex()
                    act_hex = actual_digest.hex()
                    print(f"\n[FAIL] Digest mismatch at chunk index {idx}!", file=sys.stderr)
                    print(f"  Expected: {exp_hex}", file=sys.stderr)
                    print(f"  Got:      {act_hex}", file=sys.stderr)
                    sys.exit(1)

                checked_count += 1
                if checked_count % 1_000_000 == 0:
                    print(f"  ... verified {checked_count:,} chunks OK")

    print(f"\n[PASS] Successfully verified {checked_count:,} digests. 0 errors detected.")

def main():
    parser = argparse.ArgumentParser(description="SHA-256 Digest Verification Utility")
    parser.add_argument("--nist-only", action="store_true", help="Only verify NIST test vectors")
    parser.add_argument("--data-file", type=str, help="Path to input data file (e.g. dummy_1GB.bin)")
    parser.add_argument("--digests-file", type=str, help="Path to binary file containing N x 32-byte digests")
    parser.add_argument("--chunk-size", "-C", type=int, default=64, help="Chunk size in bytes (default: 64)")
    parser.add_argument("--full", action="store_true", help="Force full verification of all N digests")
    args = parser.parse_args()

    verify_nist()

    if args.nist_only:
        return

    if not args.data_file or not args.digests_file:
        if args.data_file or args.digests_file:
            print("Error: Both --data-file and --digests-file must be provided for dataset verification.", file=sys.stderr)
            sys.exit(1)
        return

    verify_chunk_digests(args.data_file, args.digests_file, args.chunk_size, args.full)

if __name__ == "__main__":
    main()
