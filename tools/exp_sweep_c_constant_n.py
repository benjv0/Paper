#!/usr/bin/env python3
"""
tools/exp_sweep_c_constant_n.py
Experimento Opcional (a): Barrido de C manteniendo N constante.
Desacopla el número de fragmentos (concurrencia) del tamaño de fragmento C.
"""

import os
import sys
import argparse
import subprocess

def main():
    parser = argparse.ArgumentParser(description="Barrido de C con N constante")
    parser.add_argument("--n-chunks", type=int, default=65536, help="Número constante de fragmentos N")
    parser.add_argument("--chunks", nargs="+", type=int, default=[64, 1024, 4096, 65536], help="Valores de C (bytes)")
    parser.add_argument("--duration", type=float, default=15.0, help="Duración en segundos por corrida")
    parser.add_argument("--runs", type=int, default=3, help="Número de repeticiones")
    parser.add_argument("--dry-run", action="store_true", help="Solo imprimir comandos sin ejecutar")
    args = parser.parse_args()

    print("=================================================================")
    print(f"EXPERIMENTO (a): Barrido de C con N constante (N = {args.n_chunks})")
    print("=================================================================")
    print(f"Valores de C a evaluar: {args.chunks}")
    print(f"Duración por punto: {args.duration} s | Repeticiones: {args.runs}")
    print(f"Esfuerzo estimado: {len(args.chunks) * args.duration * args.runs / 60.0:.1f} minutos de cómputo activo.")

    if args.dry_run:
        print("\n[Dry-run activado: No se ejecutó ningún benchmark.]")
        return

    print("\n[AVISO]: Para ejecutar este experimento, solicite confirmación explícita.")

if __name__ == "__main__":
    main()
