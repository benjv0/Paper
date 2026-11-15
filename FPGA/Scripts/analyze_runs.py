#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
analyze_runs.py - Paso 4: analiza vio_runs.csv (5 corridas del VIO)

Uso:
    python analyze_runs.py vio_runs.csv
    python analyze_runs.py vio_runs.csv --no-digest      (salta la verificacion)
    python analyze_runs.py vio_runs.csv --mhz 100.0       (frecuencia nominal)

Por cada corrida calcula, con la diferencia fin - inicio:
  mensajes, ciclos, ciclos/mensaje (debe ser 136), frecuencia estimada
  (ciclos / tiempo del PC), Mhash/s y GB/s.
Al final da media +/- desviacion estandar (muestral) de las 5 corridas.

Verificacion: recorre UNA vez la cadena de hashlib hasta el ultimo mensaje
y compara el digest de cada corrida (es acumulativo desde el arranque).
Con 5 corridas de 60 s son ~230 millones de hashes: 2 a 5 minutos.

Opcional: si agregas al CSV las columnas p_idle_w y p_run_w (potencia medida
con run=0 y run=1, en W), calcula la energia neta en J/GB.
"""
import argparse
import csv
import hashlib
import statistics as st
import sys

M64 = (1 << 64) - 1
CICLOS_MSG = 136


def h2i(s):
    s = s.strip().replace("[H]", "").replace("_", "").replace(" ", "")
    if s.lower().startswith("0x"):
        s = s[2:]
    return int(s, 16)


def verify_chain(targets):
    """targets: {n: digest_esperado}. Devuelve {n: digest_calculado}."""
    need = sorted(targets)
    out, ld, sha = {}, b"\x00" * 32, hashlib.sha256
    k, j = 0, 0
    last = need[-1]
    step = max(1, last // 20)
    while k < last:
        ld = sha(k.to_bytes(8, "big") + ld + ((~k) & M64).to_bytes(8, "big") + ld[16:]).digest()
        k += 1
        while j < len(need) and need[j] == k:
            out[k] = int.from_bytes(ld, "big")
            j += 1
        if k % step == 0:
            print("  verificando cadena: %3d %%" % (100 * k // last), end="\r", file=sys.stderr)
    print(" " * 40, end="\r", file=sys.stderr)
    return out


def ms(v):
    return "%.4f +/- %.4f" % (st.mean(v), st.stdev(v)) if len(v) > 1 else "%.4f" % v[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--mhz", type=float, default=100.0)
    ap.add_argument("--no-digest", action="store_true")
    a = ap.parse_args()

    rows = list(csv.DictReader(open(a.csv, newline="")))
    if not rows:
        print("CSV vacio")
        return 1

    ok = True
    res = []
    print("run   segundos     mensajes        ciclos   ciclos/msg  f_est[MHz]  Mhash/s(PC)")
    for r in rows:
        secs = float(r["ms"]) / 1000.0
        mi, ci, mf, cf = (h2i(r[x]) for x in ("msg_ini", "cyc_ini", "msg_fin", "cyc_fin"))
        n, c = mf - mi, cf - ci
        cpm = c / n if n else float("nan")
        good = (c == CICLOS_MSG * n) and (cf == CICLOS_MSG * mf)
        ok &= good
        f_est = c / secs / 1e6
        res.append(dict(run=r["run"], secs=secs, n=n, c=c, mf=mf, dig=h2i(r["dig_fin"]),
                        f_est=f_est, mh_pc=n / secs / 1e6,
                        p_idle=float(r["p_idle_w"]) if r.get("p_idle_w") else None,
                        p_run=float(r["p_run_w"]) if r.get("p_run_w") else None))
        print("%3s  %8.3f  %11d  %12d   %9.4f%s  %9.3f   %9.4f"
              % (r["run"], secs, n, c, cpm, "" if good else " (!)", f_est, n / secs / 1e6))

    if not a.no_digest:
        calc = verify_chain({x["mf"]: x["dig"] for x in res})
        for x in res:
            g = calc[x["mf"]] == x["dig"]
            ok &= g
            print("[%s] corrida %s: digest tras %d mensajes %s con hashlib"
                  % ("OK" if g else "FALLA", x["run"], x["mf"], "coincide" if g else "NO coincide"))

    mh_nom = a.mhz / CICLOS_MSG
    print("\n=== Resumen (%d corridas) ===" % len(res))
    print("Ciclos por mensaje             : %d (exacto, contado por la FPGA)" % CICLOS_MSG)
    print("Frecuencia estimada (PC)       : %s MHz   (nominal %.3f)" % (ms([x["f_est"] for x in res]), a.mhz))
    print("Mhash/s medido con reloj del PC: %s" % ms([x["mh_pc"] for x in res]))
    print("Mhash/s a %.0f MHz (ciclos)      : %.4f" % (a.mhz, mh_nom))
    print("GB/s utiles a %.0f MHz (64 B)    : %.5f" % (a.mhz, mh_nom * 64 / 1000))
    print("Mbps por bloque (banco, 68 c)  : %.2f" % (512 * a.mhz / 68))

    pw = [x for x in res if x["p_idle"] is not None and x["p_run"] is not None]
    if pw:
        gbs = mh_nom * 64 / 1000
        dp = [x["p_run"] - x["p_idle"] for x in pw]
        print("\nPotencia medida (placa)        : reposo %s W | activo %s W | delta %s W"
              % (ms([x["p_idle"] for x in pw]), ms([x["p_run"] for x in pw]), ms(dp)))
        print("Energia neta (Ec. 4)           : %s J/GB" % ms([d / gbs for d in dp]))
        print("Energia bruta (activo)         : %s J/GB" % ms([x["p_run"] / gbs for x in pw]))

    print("\nRESULTADO:", "TODO OK" if ok else "REVISAR")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
