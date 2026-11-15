#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_model.py  -  Paso 1 del desarrollo SHA-256 en la SP701

Modelo en Python de tu RTL (sha256_core.v + maquina de estados de
sp701_sha256_top.v).  Copia el RTL tal cual: mismos cortes de bits
(a[1:0], a[31:2], ...), misma tabla K, misma FSM (IDLE/ROUNDS/UPDATE),
mismo handshake del top.  Sirve para:

  1) comprobar la tabla K y los H0 contra su definicion matematica,
  2) comprobar que el nucleo da el mismo hash que hashlib,
  3) contar los ciclos reales por bloque y por mensaje de 64 B,
  4) comprobar que el bucle del top produce digests correctos.

Uso:   python3 verify_model.py            (rapido)
       python3 verify_model.py --million  (agrega 1 000 000 de 'a')
"""
import copy
import hashlib
import math
import random
import sys

M32 = 0xFFFFFFFF
M64 = (1 << 64) - 1

# ----------------------------------------------------------------------
# Constantes copiadas LITERALMENTE de sha256_core.v
# ----------------------------------------------------------------------
K_RTL = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1,
    0x923f82a4, 0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
    0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147,
    0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
    0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]
H_RTL = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
         0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]

NIST_ABC_BLK = (0x616263 << 488) | (0x80 << 480) | 24      # {24'h616263, 8'h80, 416'd0, 64'd24}
NIST_ABC_EXP = 0xba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad
PAD_BLOCK_64B = (0x80 << 504) | 512                         # {8'h80, 440'd0, 64'd512}


# ----------------------------------------------------------------------
# Helpers que imitan Verilog:  x[hi:lo]  y  {a, b, c}
# ----------------------------------------------------------------------
def sl(x, hi, lo):
    return (x >> lo) & ((1 << (hi - lo + 1)) - 1)


def cat(*parts):
    r = 0
    for v, w in parts:
        r = (r << w) | (v & ((1 << w) - 1))
    return r


def Sigma0(a):
    return (cat((sl(a, 1, 0), 2), (sl(a, 31, 2), 30)) ^
            cat((sl(a, 12, 0), 13), (sl(a, 31, 13), 19)) ^
            cat((sl(a, 21, 0), 22), (sl(a, 31, 22), 10)))


def Sigma1(e):
    return (cat((sl(e, 5, 0), 6), (sl(e, 31, 6), 26)) ^
            cat((sl(e, 10, 0), 11), (sl(e, 31, 11), 21)) ^
            cat((sl(e, 24, 0), 25), (sl(e, 31, 25), 7)))


def sig0(w):
    return (cat((sl(w, 6, 0), 7), (sl(w, 31, 7), 25)) ^
            cat((sl(w, 17, 0), 18), (sl(w, 31, 18), 14)) ^ (w >> 3))


def sig1(w):
    return (cat((sl(w, 16, 0), 17), (sl(w, 31, 17), 15)) ^
            cat((sl(w, 18, 0), 19), (sl(w, 31, 19), 13)) ^ (w >> 10))


# ----------------------------------------------------------------------
# 1) Tabla K y H0 contra su definicion (raices cubicas / cuadradas)
# ----------------------------------------------------------------------
def first_primes(n):
    ps, c = [], 2
    while len(ps) < n:
        if all(c % p for p in ps if p * p <= c):
            ps.append(c)
        c += 1
    return ps


def icbrt(x):
    lo, hi = 0, 1 << ((x.bit_length() // 3) + 2)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid ** 3 <= x:
            lo = mid
        else:
            hi = mid - 1
    return lo


def check_constants():
    ps = first_primes(64)
    k_ref = [icbrt(p << 96) & M32 for p in ps]
    h_ref = [math.isqrt(p << 64) & M32 for p in ps[:8]]
    bad_k = [i for i in range(64) if k_ref[i] != K_RTL[i]]
    ok = (not bad_k) and h_ref == H_RTL
    print("[%s] Tabla K[0..63] y H0..H7 coinciden con la definicion FIPS 180-4"
          % ("OK" if ok else "FALLA"))
    if bad_k:
        print("     K con error en indices:", bad_k)
    return ok


# ----------------------------------------------------------------------
# 2) Modelo del nucleo (sha256_core.v), un tick = un flanco de reloj
# ----------------------------------------------------------------------
S_IDLE, S_ROUNDS, S_UPDATE = 0, 1, 2


class Core:
    def __init__(self):
        self.state = S_IDLE
        self.round_cnt = 0
        self.ready = 1
        self.digest_valid = 0
        self.H = list(H_RTL)
        self.v = [0] * 8          # a..h
        self.W = [0] * 16

    def digest_out(self):
        return cat(*[(h, 32) for h in self.H])

    def next(self, init_msg, next_block, block_in):
        n = Core.__new__(Core)
        n.state, n.round_cnt, n.ready = self.state, self.round_cnt, self.ready
        n.H, n.v, n.W = self.H, self.v, self.W      # se reemplazan abajo si cambian
        n.digest_valid = 0
        if self.state == S_IDLE:
            if init_msg or next_block:
                n.ready = 0
                n.round_cnt = 0
                n.state = S_ROUNDS
                n.W = [sl(block_in, 511 - 32 * i, 480 - 32 * i) for i in range(16)]
                if init_msg:
                    n.H = list(H_RTL)
                    n.v = list(H_RTL)
                else:
                    n.v = list(self.H)
            else:
                n.ready = 1
        elif self.state == S_ROUNDS:
            a, b, c, d, e, f, g, h = self.v
            W = self.W
            ch = (e & f) ^ (~e & M32 & g)
            maj = (a & b) ^ (a & c) ^ (b & c)
            t1 = (h + Sigma1(e) + ch + K_RTL[self.round_cnt] + W[0]) & M32
            t2 = (Sigma0(a) + maj) & M32
            w_new = (sig1(W[14]) + W[9] + sig0(W[1]) + W[0]) & M32
            n.v = [(t1 + t2) & M32, a, b, c, (d + t1) & M32, e, f, g]
            n.W = W[1:] + [w_new]
            if self.round_cnt == 63:
                n.state = S_UPDATE
            else:
                n.round_cnt = self.round_cnt + 1
        else:  # S_UPDATE
            n.H = [(self.H[i] + self.v[i]) & M32 for i in range(8)]
            n.digest_valid = 1
            n.ready = 1
            n.state = S_IDLE
        return n


def pad_blocks(msg):
    """Relleno FIPS 180-4 -> lista de bloques de 512 bits (enteros)."""
    data = msg + b"\x80"
    data += b"\x00" * ((56 - len(data)) % 64)
    data += (8 * len(msg)).to_bytes(8, "big")
    return [int.from_bytes(data[i:i + 64], "big") for i in range(0, len(data), 64)]


def send_block(core, blk, first):
    """Imita la tarea send_block del testbench.
    t=0: flanco donde se registra la peticion; t=1: el nucleo la ve.
    Devuelve (core, t) con t = flanco en que se observa digest_valid."""
    core = core.next(0, 0, 0)                         # t = 0
    t = 1
    req = (1 if first else 0, 0 if first else 1, blk)
    while True:
        seen = core.digest_valid                      # valor previo al flanco
        if seen:
            return core, t
        core = core.next(*(req if t == 1 else (0, 0, 0)))
        t += 1


def core_hash(msg):
    core = Core()
    lat = []
    for i, blk in enumerate(pad_blocks(msg)):
        core, t = send_block(core, blk, i == 0)
        lat.append(t)
    return core.digest_out(), lat


def check_vectors(million):
    ok = True
    vecs = [
        ("cadena vacia", b""),
        ("'abc'", b"abc"),
        ("56 bytes (2 bloques)", b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
        ("64 bytes 00..3F (caso C=64 B)", bytes(range(64))),
    ]
    for name, m in vecs:
        d, lat = core_hash(m)
        good = d == int(hashlib.sha256(m).hexdigest(), 16)
        ok &= good
        print("[%s] %-32s bloques=%d  latencia/bloque=%s ciclos"
              % ("OK" if good else "FALLA", name, len(lat), lat))
    rnd = random.Random(1234)
    bad = 0
    for _ in range(300):
        m = bytes(rnd.getrandbits(8) for _ in range(rnd.randint(0, 200)))
        d, _ = core_hash(m)
        bad += d != int(hashlib.sha256(m).hexdigest(), 16)
    print("[%s] 300 mensajes aleatorios de 0..200 bytes contra hashlib (errores=%d)"
          % ("OK" if bad == 0 else "FALLA", bad))
    ok &= bad == 0
    if million:
        core = Core()
        blk_a = int.from_bytes(b"a" * 64, "big")
        core, _ = send_block(core, blk_a, True)
        for _ in range(15624):
            core, _ = send_block(core, blk_a, False)
        core, _ = send_block(core, (0x80 << 504) | 8_000_000, False)
        good = core.digest_out() == int(hashlib.sha256(b"a" * 1_000_000).hexdigest(), 16)
        ok &= good
        print("[%s] 1 000 000 de 'a' (15 626 bloques encadenados)" % ("OK" if good else "FALLA"))
    return ok


# ----------------------------------------------------------------------
# 3) Modelo del top (FSM de benchmark) acoplado al nucleo
# ----------------------------------------------------------------------
(B_NIST_START, B_NIST_WAIT, B_MSG_BLK1,
 B_WAIT_BLK1, B_MSG_BLK2, B_WAIT_BLK2) = range(6)


class Top:
    def __init__(self):
        self.b_state = B_NIST_START
        self.init_msg = 0
        self.next_block = 0
        self.block_in = 0
        self.msg_counter = 0
        self.nist_pass = 0
        self.last_digest = 0

    def next(self, ready, digest_valid, digest_out):
        n = copy.copy(self)
        n.init_msg = 0
        n.next_block = 0
        st = self.b_state
        if st == B_NIST_START:
            if ready:
                n.block_in = NIST_ABC_BLK
                n.init_msg = 1
                n.b_state = B_NIST_WAIT
        elif st == B_NIST_WAIT:
            if digest_valid:
                if digest_out == NIST_ABC_EXP:
                    n.nist_pass = 1
                n.b_state = B_MSG_BLK1
        elif st == B_MSG_BLK1:
            if ready:
                mc, ld = self.msg_counter, self.last_digest
                n.block_in = cat((mc, 64), (ld, 256), (~mc & M64, 64), (ld & ((1 << 128) - 1), 128))
                n.init_msg = 1
                n.b_state = B_WAIT_BLK1
        elif st == B_WAIT_BLK1:
            if digest_valid:
                n.b_state = B_MSG_BLK2
        elif st == B_MSG_BLK2:
            if ready:
                n.block_in = PAD_BLOCK_64B
                n.next_block = 1
                n.b_state = B_WAIT_BLK2
        elif st == B_WAIT_BLK2:
            if digest_valid:
                n.last_digest = digest_out
                n.msg_counter = (self.msg_counter + 1) & M64
                n.b_state = B_MSG_BLK1
        return n


def check_top(n_msgs=200):
    core, top = Core(), Top()
    req1, req2, obs = [], [], []
    cur_msg, ok, checked = None, True, 0
    cyc = 0
    while checked < n_msgs:
        cn = core.next(top.init_msg, top.next_block, top.block_in)
        tn = top.next(core.ready, core.digest_valid, core.digest_out())
        if tn.init_msg and tn.b_state == B_WAIT_BLK1:
            req1.append(cyc)
            cur_msg = tn.block_in.to_bytes(64, "big")
        if tn.next_block:
            req2.append(cyc)
        if core.digest_valid:
            obs.append(cyc)
        if top.b_state == B_WAIT_BLK2 and core.digest_valid:
            good = tn.last_digest == int(hashlib.sha256(cur_msg).hexdigest(), 16)
            ok &= good
            checked += 1
        core, top = cn, tn
        cyc += 1
    per_msg = req1[-1] - req1[-2]
    blk1_to_blk2 = req2[0] - req1[0]
    nist_ok = top.nist_pass == 1
    print("[%s] Autotest NIST 'abc' dentro del top (nist_pass=%d)" % ("OK" if nist_ok else "FALLA", top.nist_pass))
    print("[%s] %d mensajes del bucle (2 bloques c/u) coinciden con hashlib" % ("OK" if ok else "FALLA", n_msgs))
    print("     Peticion bloque 1 -> peticion bloque 2 : %d ciclos" % blk1_to_blk2)
    print("     Mensaje de 64 B en regimen permanente  : %d ciclos" % per_msg)
    return ok and nist_ok, per_msg


def main():
    million = "--million" in sys.argv
    print("=== Modelo Python del RTL de tu SHA-256 ===")
    ok = check_constants()
    ok &= check_vectors(million)
    good, per_msg = check_top()
    ok &= good
    print("\n=== Metricas con los ciclos reales (RTL actual) ===")
    for f in (100.0,):
        mh = f / per_msg
        print("f = %6.2f MHz | %d ciclos/mensaje | %.4f Mhash/s | %.4f GB/s utiles (64 B)"
              % (f, per_msg, mh, mh * 64 / 1000))
    print("Referencia ideal del survey (R+1 = 65 ciclos/bloque, 2 bloques): 130 ciclos/mensaje")
    print("\nRESULTADO GLOBAL:", "TODO OK" if ok else "HAY FALLAS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
