#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_run.py - Verifica en el PC lo que midio la FPGA (valores del VIO).

Uso (pega los valores en HEX tal como los muestra el VIO, sin 0x):
    python3 check_run.py --n 00000000003A98F1 --cycles 00000000...  --digest ABCD...
    python3 check_run.py --n ... --cycles ... --digest ... --seconds 15.0
    python3 check_run.py --n ... --cycles ... --digest ... --mhz 33.333

  --n        msg_counter  (mensajes de 64 B completados)
  --cycles   cycles       (ciclos de reloj procesando mensajes)
  --digest   last_digest  (digest del ultimo mensaje)
  --seconds  tiempo (cronometro) que estuvo run=1  -> estima la frecuencia real
  --mhz      frecuencia del reloj, si ya la conoces -> calcula throughput

Repite la misma cadena que hace sha256_bench.v:
    bloque1 = {contador(64), digest_previo(256), ~contador(64), digest_previo[127:0]}
    digest  = SHA-256 de esos 64 bytes   (digest inicial = 0, contador inicial = 0)
Con n grande (millones) tarda unos segundos: hace n llamadas a hashlib.
"""
import argparse
import hashlib
import sys

M64 = (1 << 64) - 1
CICLOS_MSG_ESPERADOS = 136      # 2 bloques x 68 ciclos (modelo y testbench)
CICLOS_BLOQUE_TOP = 68
CICLOS_BLOQUE_NUCLEO = 66       # 1 carga + 64 rondas + 1 suma


def chain(n):
    ld = 0
    for k in range(n):
        blk = (k << 448) | (ld << 192) | ((~k & M64) << 128) | (ld & ((1 << 128) - 1))
        ld = int.from_bytes(hashlib.sha256(blk.to_bytes(64, "big")).digest(), "big")
    return ld


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", required=True)
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--digest", required=True)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--mhz", type=float)
    a = ap.parse_args()

    n = int(a.n, 16)
    cycles = int(a.cycles, 16)
    digest = int(a.digest, 16)
    ok = True

    print("Mensajes completados : %d" % n)
    print("Ciclos               : %d" % cycles)
    if n == 0:
        print("n = 0: no hay nada que verificar (¿run estuvo en 1?)")
        return 1

    esperado = chain(n)
    good = esperado == digest
    ok &= good
    print("[%s] digest final coincide con la cadena de hashlib (%d hashes)" % ("OK" if good else "FALLA", n))
    if not good:
        print("     FPGA     : %064x" % digest)
        print("     esperado : %064x" % esperado)

    cpm = cycles / n
    good = cycles == n * CICLOS_MSG_ESPERADOS
    ok &= good
    print("[%s] ciclos por mensaje = %.4f (esperado %d)" % ("OK" if good else "DIFIERE", cpm, CICLOS_MSG_ESPERADOS))

    f = a.mhz
    if a.seconds:
        f_est = cycles / a.seconds / 1e6
        print("Frecuencia estimada con el cronometro: %.2f MHz  (error de cronometro ~0.1 s / %.0f s = %.1f %%)"
              % (f_est, a.seconds, 0.1 / a.seconds * 100))
        if f is None:
            f = f_est
    if f:
        mh = f / cpm                                   # Mhash/s (1 hash = 1 mensaje de 64 B)
        print("\nCon f = %.3f MHz:" % f)
        print("  Mhash/s (mensajes de 64 B)        : %.4f" % mh)
        print("  GB/s utiles (64 B por mensaje)    : %.5f" % (mh * 64 / 1000))
        print("  Mbps por bloque, dentro del banco : %.2f   (512 bits x f / %d ciclos)" % (512 * f / CICLOS_BLOQUE_TOP, CICLOS_BLOQUE_TOP))
        print("  Mbps por bloque, solo el nucleo   : %.2f   (512 bits x f / %d ciclos)" % (512 * f / CICLOS_BLOQUE_NUCLEO, CICLOS_BLOQUE_NUCLEO))
    print("\nRESULTADO:", "TODO OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
