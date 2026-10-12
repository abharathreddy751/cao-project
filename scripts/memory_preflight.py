"""Standalone memory preflight: exit 0 if free RAM >= threshold GB, else 1.

  python scripts/memory_preflight.py --min-free-gb 3
"""
import argparse
import sys

from caosched.experiment.runner import free_ram_gb

ap = argparse.ArgumentParser()
ap.add_argument("--min-free-gb", type=float, required=True)
a = ap.parse_args()
free = free_ram_gb()
print(f"free RAM {free:.2f} GB, threshold {a.min_free_gb} GB: {'OK' if free >= a.min_free_gb else 'ABORT'}")
sys.exit(0 if free >= a.min_free_gb else 1)
