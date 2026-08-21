#!/usr/bin/env python3
"""
Compare phonon frequencies from CRYSTAL (PBE0) and FLEUR (PBE, tuningB_fast)
for ZnO (phase 7282) and KNbO3 (phase 16803).

CRYSTAL outputs frequencies in cm^-1. FLEUR (via phonopy) outputs in THz.
This script converts everything to THz (1 THz = 33.356 cm^-1) and produces
a side-by-side comparison table.

Usage:
    python3 scripts/phonon/compare_phonons.py
"""

import json
import os
from pathlib import Path

# Conversion: 1 THz = 33.3564 cm^-1
CM1_TO_THZ = 1.0 / 33.3564
THZ_TO_CM1 = 33.3564

IMAG_THRESHOLD = -0.05  # THz


def load_crystal(base: Path, system: str) -> dict:
    """Load CRYSTAL phonon frequencies from JSON."""
    path = base / "crystal" / system / "phonon_data.json"
    with open(path) as f:
        d = json.load(f)
    freqs = d["phonons"]["modes_freqs"]  # cm^-1
    # Convert to THz
    thz = {q: [f * CM1_TO_THZ for f in modes] for q, modes in freqs.items()}
    return {"freqs_THz": thz, "freqs_cm": freqs, "source": "CRYSTAL PBE0"}


def load_fleur(base: Path, version: str, system: str) -> dict:
    """Load FLEUR phonon frequencies from phonon_frequencies.txt."""
    path = base / version / system / "phonon_frequencies.txt"
    if not path.exists():
        return {"freqs_THz": {}, "freqs_cm": {}, "source": f"FLEUR {version} (no data)"}
    freqs = {}
    current_q = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("q-point"):
                parts = line.split(":")
                current_q = parts[0].replace("q-point ", "").strip()
                freqs[current_q] = []
            elif line.startswith("band") and current_q:
                val = float(
                    line.split(":")[1].replace("THz", "").replace("*", "").strip()
                )
                freqs[current_q].append(val)
    # Convert THz to cm^-1
    cm = {q: [f * THZ_TO_CM1 for f in modes] for q, modes in freqs.items()}
    return {"freqs_THz": freqs, "freqs_cm": cm, "source": f"FLEUR {version} PBE"}


def count_imaginary(freqs_thz: dict) -> int:
    """Count imaginary modes (freq < -0.05 THz)."""
    total = 0
    for modes in freqs_thz.values():
        total += sum(1 for f in modes if f < IMAG_THRESHOLD)
    return total


def find_qpoint(freqs: dict, target: str) -> str | None:
    """Find a q-point key that matches the target (e.g. '0 0 0')."""
    # Try exact match
    if target in freqs:
        return target
    # Try with different formatting
    for q in freqs:
        if q.replace(" ", "") == target.replace(" ", ""):
            return q
    return None


def format_freq(f: float) -> str:
    """Format frequency with imaginary marker."""
    if f < IMAG_THRESHOLD:
        return f"{f:8.3f}*"
    return f"{f:8.3f}"


def main():
    base = Path("data/phonon_comparison")
    if not base.exists():
        print(f"error: {base} not found")
        return

    systems = ["ZnO", "KNbO3"]
    versions = [("fleur_62", "FLEUR 6.2"), ("fleur_develop", "FLEUR 8.1")]

    # Load all data
    data = {}
    for system in systems:
        data[system] = {}
        data[system]["crystal"] = load_crystal(base, system)
        for vdir, vname in versions:
            data[system][vdir] = load_fleur(base, vdir, system)

    # Print comparison
    for system in systems:
        print(f"\n{'=' * 80}")
        print(f"  {system}")
        print(f"{'=' * 80}")

        crystal = data[system]["crystal"]
        f62 = data[system]["fleur_62"]
        fdev = data[system]["fleur_develop"]

        # Summary
        print(
            f"\n  {'Source':<25} {'n_qpoints':>10} {'n_imaginary':>12} {'min_THz':>10} {'max_THz':>10}"
        )
        print(f"  {'-' * 25} {'-' * 10} {'-' * 12} {'-' * 10} {'-' * 10}")
        for label, d in [
            (f"CRYSTAL PBE0", crystal),
            (f"FLEUR 6.2 PBE", f62),
            (f"FLEUR 8.1 PBE", fdev),
        ]:
            freqs = d["freqs_THz"]
            n_q = len(freqs)
            n_imag = count_imaginary(freqs)
            all_f = [f for modes in freqs.values() for f in modes]
            min_f = min(all_f) if all_f else 0
            max_f = max(all_f) if all_f else 0
            print(f"  {label:<25} {n_q:>10} {n_imag:>12} {min_f:>10.3f} {max_f:>10.3f}")

        # Per-q-point comparison (only Gamma and a few others)
        qpoints_crystal = list(crystal["freqs_THz"].keys())
        qpoints_fleur = list(f62["freqs_THz"].keys())

        # Show Gamma point (q=0 0 0) in detail
        gamma_crystal = find_qpoint(crystal["freqs_THz"], "0 0 0")
        gamma_f62 = find_qpoint(f62["freqs_THz"], "0 0 0")
        gamma_fdev = find_qpoint(fdev["freqs_THz"], "0 0 0")

        if gamma_crystal and gamma_f62:
            print(f"\n  Gamma point (q = 0 0 0) — frequencies in THz:")
            print(f"  {'Band':<6} {'CRYSTAL':>12} {'FLEUR 6.2':>12} {'FLEUR 8.1':>12}")
            print(f"  {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
            crystal_modes = crystal["freqs_THz"][gamma_crystal]
            f62_modes = f62["freqs_THz"][gamma_f62]
            fdev_modes = fdev["freqs_THz"].get(gamma_fdev, []) if gamma_fdev else []

            max_bands = max(len(crystal_modes), len(f62_modes), len(fdev_modes))
            for i in range(max_bands):
                c = format_freq(crystal_modes[i]) if i < len(crystal_modes) else "—"
                f1 = format_freq(f62_modes[i]) if i < len(f62_modes) else "—"
                f2 = format_freq(fdev_modes[i]) if i < len(fdev_modes) else "—"
                print(f"  {i + 1:<6} {c:>12} {f1:>12} {f2:>12}")

        # Also in cm^-1
        if gamma_crystal and gamma_f62:
            print(f"\n  Gamma point (q = 0 0 0) — frequencies in cm^-1:")
            print(f"  {'Band':<6} {'CRYSTAL':>12} {'FLEUR 6.2':>12} {'FLEUR 8.1':>12}")
            print(f"  {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
            crystal_cm = crystal["freqs_cm"][gamma_crystal]
            f62_cm = f62["freqs_cm"][gamma_f62]
            fdev_cm = fdev["freqs_cm"].get(gamma_fdev, []) if gamma_fdev else []

            max_bands = max(len(crystal_cm), len(f62_cm), len(fdev_cm))
            for i in range(max_bands):
                c = f"{crystal_cm[i]:8.2f}" if i < len(crystal_cm) else "—"
                f1 = f"{f62_cm[i]:8.2f}" if i < len(f62_cm) else "—"
                f2 = f"{fdev_cm[i]:8.2f}" if i < len(fdev_cm) else "—"
                marker = " *" if (i < len(crystal_cm) and crystal_cm[i] < -1) else ""
                print(f"  {i + 1:<6} {c:>12} {f1:>12} {f2:>12}{marker}")

    # Write to file
    out = base / "comparison_table.txt"
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main_inner(data, systems)
    out.write_text(buf.getvalue())
    print(f"\n  Written to {out}")


def main_inner(data, systems):
    for system in systems:
        print(f"\n{'=' * 80}")
        print(f"  {system}")
        print(f"{'=' * 80}")
        crystal = data[system]["crystal"]
        f62 = data[system]["fleur_62"]
        fdev = data[system]["fleur_develop"]
        print(
            f"\n  {'Source':<25} {'n_qpoints':>10} {'n_imaginary':>12} {'min_THz':>10} {'max_THz':>10}"
        )
        print(f"  {'-' * 25} {'-' * 10} {'-' * 12} {'-' * 10} {'-' * 10}")
        for label, d in [
            (f"CRYSTAL PBE0", crystal),
            (f"FLEUR 6.2 PBE", f62),
            (f"FLEUR 8.1 PBE", fdev),
        ]:
            freqs = d["freqs_THz"]
            n_q = len(freqs)
            n_imag = count_imaginary(freqs)
            all_f = [f for modes in freqs.values() for f in modes]
            min_f = min(all_f) if all_f else 0
            max_f = max(all_f) if all_f else 0
            print(f"  {label:<25} {n_q:>10} {n_imag:>12} {min_f:>10.3f} {max_f:>10.3f}")
        gamma_crystal = find_qpoint(crystal["freqs_THz"], "0 0 0")
        gamma_f62 = find_qpoint(f62["freqs_THz"], "0 0 0")
        gamma_fdev = find_qpoint(fdev["freqs_THz"], "0 0 0")
        if gamma_crystal and gamma_f62:
            print(f"\n  Gamma point (q = 0 0 0) — frequencies in THz:")
            print(f"  {'Band':<6} {'CRYSTAL':>12} {'FLEUR 6.2':>12} {'FLEUR 8.1':>12}")
            print(f"  {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
            crystal_modes = crystal["freqs_THz"][gamma_crystal]
            f62_modes = f62["freqs_THz"][gamma_f62]
            fdev_modes = fdev["freqs_THz"].get(gamma_fdev, []) if gamma_fdev else []
            max_bands = max(len(crystal_modes), len(f62_modes), len(fdev_modes))
            for i in range(max_bands):
                c = format_freq(crystal_modes[i]) if i < len(crystal_modes) else "—"
                f1 = format_freq(f62_modes[i]) if i < len(f62_modes) else "—"
                f2 = format_freq(fdev_modes[i]) if i < len(fdev_modes) else "—"
                print(f"  {i + 1:<6} {c:>12} {f1:>12} {f2:>12}")
        if gamma_crystal and gamma_f62:
            print(f"\n  Gamma point (q = 0 0 0) — frequencies in cm^-1:")
            print(f"  {'Band':<6} {'CRYSTAL':>12} {'FLEUR 6.2':>12} {'FLEUR 8.1':>12}")
            print(f"  {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
            crystal_cm = crystal["freqs_cm"][gamma_crystal]
            f62_cm = f62["freqs_cm"][gamma_f62]
            fdev_cm = fdev["freqs_cm"].get(gamma_fdev, []) if gamma_fdev else []
            max_bands = max(len(crystal_cm), len(f62_cm), len(fdev_cm))
            for i in range(max_bands):
                c = f"{crystal_cm[i]:8.2f}" if i < len(crystal_cm) else "—"
                f1 = f"{f62_cm[i]:8.2f}" if i < len(f62_cm) else "—"
                f2 = f"{fdev_cm[i]:8.2f}" if i < len(fdev_cm) else "—"
                marker = " *" if (i < len(crystal_cm) and crystal_cm[i] < -1) else ""
                print(f"  {i + 1:<6} {c:>12} {f1:>12} {f2:>12}{marker}")


if __name__ == "__main__":
    main()
