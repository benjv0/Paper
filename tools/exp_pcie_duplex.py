#!/usr/bin/env python3
"""
tools/exp_pcie_duplex.py
Experimento Opcional (c): Microbenchmark PCIe full-duplex simultáneo H2D + D2H.
Mide el ancho de banda efectivo simultáneo frente a transferencias unidireccionales simplex.
"""

import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Microbenchmark PCIe Duplex")
    parser.add_argument("--buffer-mb", type=int, default=512, help="Tamaño de buffer por sentido en MiB")
    parser.add_argument("--iterations", type=int, default=50, help="Número de iteraciones de transferencia")
    parser.add_argument("--dry-run", action="store_true", help="Solo reporte de esfuerzo")
    args = parser.parse_args()

    print("=================================================================")
    print("EXPERIMENTO (c): Microbenchmark PCIe Duplex H2D/D2H Simultáneo")
    print("=================================================================")
    print(f"Tamaño de buffer: {args.buffer_mb} MiB | Iteraciones: {args.iterations}")
    print("Esfuerzo estimado: ~2 minutos (incluye compilación de harness CUDA y ejecución).")

    if args.dry_run:
        print("\n[Dry-run activado: No se ejecutó ningún benchmark.]")
        return

    print("\n[AVISO]: Listo para ejecutar cuando sea aprobado.")

if __name__ == "__main__":
    main()
