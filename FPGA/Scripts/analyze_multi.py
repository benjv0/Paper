#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_multi.py - Analiza las 5 corridas del diseno de N nucleos

Uso (en PowerShell, en la carpeta del CSV):
    py analyze_multi.py vio_runs_N8.csv --cores 8
    py analyze_multi.py vio_runs_N8.csv --cores 8 --pdyn 0.30
    py analyze_multi.py vio_runs_N8.csv --cores 8 --no-digest

Opciones:
  --cores N     numero de nucleos del diseno programado (obligatorio)
  --mhz F       frecuencia nominal (100.0)
  --pdyn W      potencia dinamica SAIF de u_multi en W (opcional): calcula J/GB
  --pstat W     potencia estatica del chip (0.089)
  --procs P     procesos para verificar (por defecto, todos los del PC)
  --no-digest   no verifica las cadenas (solo metricas)

Por corrida (fin - inicio): mensajes por nucleo, ciclos (debe ser 136 por
mensaje), frecuencia estimada con el reloj del PC y throughput TOTAL
(N x 64 B por mensaje).

Verificacion: el nucleo k procesa la cadena
    bloque1 = {c, d, ~c ^ (k << 56), d[127:0]}     (c = contador, d = digest previo)
y la FPGA entrega el XOR de los N digests. El script recalcula las N cadenas
(en paralelo) y compara el XOR en el punto final de cada corrida. Las cadenas
son acumulativas desde el arranque: con N nucleos verifica N veces mas hashes
que con 1 (~2 min por cadena; para N = 24, del orden de 10 a 30 minutos
repartido entre los nucleos del PC).
"""
import argparse
import csv
import hashlib
import os
import statistics as st
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

M64 = (1 << 64) - 1
CICLOS_MSG = 136


def h2i(s):
    s = str(s).strip().replace("[H]", "").replace("_", "").replace(" ", "")
    if s.lower().startswith("0x"):
        s = s[2:]
    return int(s, 16)


def core_chain(core_id, points):
    """Recorre la cadena del nucleo core_id y devuelve {n: digest} en los puntos pedidos."""
    pts = sorted(set(points))
    out = {}
    ld = b"\x00" * 32
    sha = hashlib.sha256
    salt = core_id << 56
    j = 0
    last = pts[-1]
    k = 0
    while k < last:
        f3 = ((~k) & M64) ^ salt
        ld = sha(k.to_bytes(8, "big") + ld + f3.to_bytes(8, "big") + ld[16:]).digest()
        k += 1
        while j < len(pts) and pts[j] == k:
            out[k] = int.from_bytes(ld, "big")
            j += 1
    return core_id, out


def ms(v, fmt="%.4f"):
    if len(v) > 1:
        return (fmt + " +/- " + fmt) % (st.mean(v), st.stdev(v))
    return fmt % v[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--cores", type=int, required=True)
    ap.add_argument("--mhz", type=float, default=100.0)
    ap.add_argument("--pdyn", type=float)
    ap.add_argument("--pstat", type=float, default=0.089)
    ap.add_argument("--procs", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--no-digest", action="store_true")
    a = ap.parse_args()
    N = a.cores

    rows = list(csv.DictReader(open(a.csv, newline="")))
    if not rows:
        print("CSV vacio")
        return 1

    ok = True
    res = []
    print("Diseno de %d nucleos, %d corridas" % (N, len(rows)))
    print("run  segundos   msg/nucleo   msg totales        ciclos  ciclos/msg  f_est[MHz]  GB/s(PC)")
    for r in rows:
        secs = float(r["ms"]) / 1000.0
        mi, ci, mf, cf = (h2i(r[x]) for x in ("msg_ini", "cyc_ini", "msg_fin", "cyc_fin"))
        n, c = mf - mi, cf - ci
        good = (c == CICLOS_MSG * n) and (cf == CICLOS_MSG * mf) and n > 0
        ok &= good
        f_est = c / secs / 1e6
        gbs_pc = N * n * 64 / secs / 1e9
        res.append(dict(run=r["run"], mf=mf, dig=h2i(r["dig_fin"]), f_est=f_est, gbs_pc=gbs_pc))
        print("%3s  %8.3f  %11d  %12d  %12d   %9.4f%s  %9.3f   %8.4f"
              % (r["run"], secs, n, N * n, c, c / n if n else float("nan"),
                 "" if good else " (!)", f_est, gbs_pc))

    if not a.no_digest:
        points = [x["mf"] for x in res]
        total = N * max(points)
        print("\nVerificando %d cadenas (%d hashes en total) con %d procesos..." % (N, total, a.procs))
        t0 = time.time()
        per_core = {}
        with ProcessPoolExecutor(max_workers=max(1, a.procs)) as ex:
            futs = [ex.submit(core_chain, k, points) for k in range(N)]
            done = 0
            for f in as_completed(futs):
                k, d = f.result()
                per_core[k] = d
                done += 1
                print("  nucleo %3d listo (%d/%d, %.0f s)" % (k, done, N, time.time() - t0))
        for x in res:
            xo = 0
            for k in range(N):
                xo ^= per_core[k][x["mf"]]
            g = xo == x["dig"]
            ok &= g
            print("[%s] corrida %s: XOR de %d digests tras %d mensajes/nucleo %s"
                  % ("OK" if g else "FALLA", x["run"], N, x["mf"], "coincide" if g else "NO coincide"))

    f = a.mhz
    mh = N * f / CICLOS_MSG
    gbs = mh * 64 / 1000
    print("\n=== Resumen (N = %d, %d corridas) ===" % (N, len(res)))
    print("Ciclos por mensaje (por nucleo) : %d (exacto, contado por la FPGA)" % CICLOS_MSG)
    print("Frecuencia estimada (PC)        : %s MHz" % ms([x["f_est"] for x in res], "%.3f"))
    print("GB/s medidos con reloj del PC   : %s" % ms([x["gbs_pc"] for x in res]))
    print("Mhash/s totales a %.0f MHz       : %.4f" % (f, mh))
    print("GB/s utiles totales a %.0f MHz   : %.5f" % (f, gbs))
    print("Mbps por bloque totales (banco) : %.2f" % (N * 512 * f / 68))
    if a.pdyn is not None:
        print("Potencia (SAIF)                 : dinamica %.3f W + estatica %.3f W = %.3f W"
              % (a.pdyn, a.pstat, a.pdyn + a.pstat))
        print("Energia neta  (dinamica)        : %.3f J/GB" % (a.pdyn / gbs))
        print("Energia bruta (din. + estatica) : %.3f J/GB" % ((a.pdyn + a.pstat) / gbs))

    print("\nRESULTADO:", "TODO OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
