#!/usr/bin/env python3
"""
tools/exp_nvml_clocks_throttle.py
Experimento Opcional (e): Monitoreo de relojes, temperaturas y razones de throttle NVML
durante la ejecución continuada de GPU v2 kernel-only.
"""

import os
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Monitoreo NVML clocks y throttle")
    parser.add_argument("--sampling-hz", type=int, default=50, help="Frecuencia de muestreo en Hz")
    parser.add_argument("--duration", type=float, default=20.0, help="Duración en segundos")
    parser.add_argument("--dry-run", action="store_true", help="Solo reporte de esfuerzo")
    args = parser.parse_args()

    print("=================================================================")
    print("EXPERIMENTO (e): Monitoreo de Clocks y Throttle Reasons NVML")
    print("=================================================================")
    print(f"Muestreo: {args.sampling_hz} Hz ({1000.0/args.sampling_hz:.1f} ms) | Duración: {args.duration} s")
    print("Métricas: Graphics Clock (MHz), SM Clock (MHz), Temp (°C), Power (W), Throttle Bitmask.")
    print("Esfuerzo estimado: ~1.5 minutos.")

    if args.dry_run:
        print("\n[Dry-run activado: No se ejecutó ningún benchmark.]")
        return

    print("\n[AVISO]: Listo para ejecutar cuando sea aprobado.")

if __name__ == "__main__":
    main()
