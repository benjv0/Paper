#!/usr/bin/env python3
"""
tools/exp_sweep_c_12t_pe.py
Experimento Opcional (b): Barrido paramétrico de C para CPU SHA-NI 12 CPUs (P+E).
Evalúa C in {64 B, 1 KB, 4 KB, 64 KB, 1 MB} bajo planificación dinámica (--sched dynamic).
"""

import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="Barrido de C para 12 CPUs P+E")
    parser.add_argument("--chunks", nargs="+", type=int, default=[64, 1024, 4096, 65536, 1048576], help="Valores de C (bytes)")
    parser.add_argument("--file", type=str, default="dummy_1GB.bin", help="Archivo de datos")
    parser.add_argument("--duration", type=float, default=15.0, help="Duración en segundos por corrida")
    parser.add_argument("--runs", type=int, default=5, help="Número de repeticiones")
    parser.add_argument("--dry-run", action="store_true", help="Solo imprimir comandos")
    args = parser.parse_args()

    print("=================================================================")
    print("EXPERIMENTO (b): Barrido de C para CPU SHA-NI 12 CPUs (P+E)")
    print("=================================================================")
    print(f"Valores de C a evaluar: {args.chunks}")
    print(f"Duración por punto: {args.duration} s | Repeticiones: {args.runs}")
    total_time_s = len(args.chunks) * (args.duration + 3.0) * args.runs
    print(f"Esfuerzo estimado: {total_time_s / 60.0:.1f} minutos (total {len(args.chunks) * args.runs} corridas sostenidas).")

    for c in args.chunks:
        cmd = [
            "./cpu/sha256_cpu_bench",
            "--file", args.file,
            "--impl", "shani",
            "--threads", "12",
            "--cores", "0,1,2,3,4,5,6,7,8,9,10,11",
            "--sched", "dynamic",
            "--chunk-size", str(c),
            "--duration", str(args.duration),
            "--warmup", "3.0",
            "--runs", str(args.runs)
        ]
        print(f"Comando C={c}: {' '.join(cmd)}")

    if args.dry_run:
        print("\n[Dry-run activado: No se ejecutó ningún benchmark.]")
        return

    print("\n[AVISO]: Listo para ejecutar cuando sea aprobado.")

if __name__ == "__main__":
    main()
