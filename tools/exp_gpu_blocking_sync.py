#!/usr/bin/env python3
"""
tools/exp_gpu_blocking_sync.py
Experimento Opcional (d): Efecto de cudaDeviceScheduleBlockingSync en la energía del host.
Compara cudaDeviceScheduleYield / Spin frente a cudaDeviceScheduleBlockingSync
para cuantificar la reducción de potencia activa del procesador anfitrión.
"""

import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="cudaDeviceScheduleBlockingSync vs Spin/Yield")
    parser.add_argument("--duration", type=float, default=15.0, help="Duración en segundos por corrida")
    parser.add_argument("--runs", type=int, default=3, help="Número de repeticiones")
    parser.add_argument("--dry-run", action="store_true", help="Solo reporte de esfuerzo")
    args = parser.parse_args()

    print("=================================================================")
    print("EXPERIMENTO (d): cudaDeviceScheduleBlockingSync y Potencia Host")
    print("=================================================================")
    print(f"Duración por modo: {args.duration} s | Repeticiones: {args.runs}")
    print(f"Modos a contrastar: [Yield/Spin (default), BlockingSync]")
    print(f"Esfuerzo estimado: ~3.5 minutos (2 modos x 3 corridas de 15 s + calentamiento).")

    if args.dry_run:
        print("\n[Dry-run activado: No se ejecutó ningún benchmark.]")
        return

    print("\n[AVISO]: Listo para ejecutar cuando sea aprobado.")

if __name__ == "__main__":
    main()
