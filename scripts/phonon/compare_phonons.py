#!/usr/bin/env python3
"""
Compare phonon frequencies from CRYSTAL (PBE0) and FLEUR (PBE, tuningB_fast)
for ZnO (phase 7282) and KNbO3 (phase 16803).

All frequencies are reported in cm^-1 (CRYSTAL's native unit; FLEUR's
phonon_frequencies.txt, from phonopy, is expected to already be in cm^-1 -
see scripts/phonon/compute_frequencies.py).

Usage:
    python3 scripts/phonon/compare_phonons.py
"""

import io
import contextlib
import json
from pathlib import Path

IMAG_THRESHOLD = -1.67  # cm^-1
THZ_TO_CM1 = 33.3564095198152


def load_crystal(base: Path, system: str) -> dict:
    """Load CRYSTAL phonon frequencies from JSON (cm^-1)."""
    path = base / "crystal" / system / "phonon_data.json"
    with open(path) as f:
        d = json.load(f)
    freqs = d["phonons"]["modes_freqs"]  # cm^-1
    return {"freqs_cm": freqs, "source": "CRYSTAL PBE0"}


def load_fleur(base: Path, version: str, system: str) -> dict:
    """Load FLEUR phonon frequencies from phonon_frequencies.txt.

    Current files report cm^-1; older files (pre cm^-1 switch) reported THz
    and are still parsed correctly by sniffing the per-band unit suffix.
    """
    path = base / version / system / "phonon_frequencies.txt"
    if not path.exists():
        return {"freqs_cm": {}, "source": f"FLEUR {version} (no data)"}
    freqs = {}
    current_q = None
    is_thz = False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("q-point"):
                parts = line.split(":")
                current_q = parts[0].replace("q-point ", "").strip()
                freqs[current_q] = []
            elif line.startswith("band") and current_q:
                value_part = line.split(":")[1]
                if "THz" in value_part:
                    is_thz = True
                val = float(
                    value_part.replace("cm^-1", "")
                    .replace("THz", "")
                    .replace("*", "")
                    .strip()
                )
                freqs[current_q].append(val)
    if is_thz:
        freqs = {q: [f * THZ_TO_CM1 for f in modes] for q, modes in freqs.items()}
    return {"freqs_cm": freqs, "source": f"FLEUR {version} PBE"}


def count_imaginary(freqs_cm: dict) -> int:
    """Count imaginary modes (freq < -1.67 cm^-1)."""
    total = 0
    for modes in freqs_cm.values():
        total += sum(1 for f in modes if f < IMAG_THRESHOLD)
    return total


def find_qpoint(freqs: dict, target: str) -> str | None:
    """Find a q-point key that matches the target (e.g. '0 0 0')."""
    if target in freqs:
        return target
    for q in freqs:
        if q.replace(" ", "") == target.replace(" ", ""):
            return q
    return None


def format_freq(f: float) -> str:
    """Format frequency with imaginary marker."""
    if f < IMAG_THRESHOLD:
        return f"{f:8.3f}*"
    return f"{f:8.3f}"


def render(data: dict, systems: list[str]) -> None:
    for system in systems:
        print(f"\n{'=' * 80}")
        print(f"  {system}")
        print(f"{'=' * 80}")

        crystal = data[system]["crystal"]
        f62 = data[system]["fleur_62"]
        fdev = data[system]["fleur_develop"]

        print(
            f"\n  {'Source':<25} {'n_qpoints':>10} {'n_imaginary':>12} "
            f"{'min_cm1':>10} {'max_cm1':>10}"
        )
        print(f"  {'-' * 25} {'-' * 10} {'-' * 12} {'-' * 10} {'-' * 10}")
        for label, d in [
            ("CRYSTAL PBE0", crystal),
            ("FLEUR 6.2 PBE", f62),
            ("FLEUR 8.1 PBE", fdev),
        ]:
            freqs = d["freqs_cm"]
            n_q = len(freqs)
            n_imag = count_imaginary(freqs)
            all_f = [f for modes in freqs.values() for f in modes]
            min_f = min(all_f) if all_f else 0
            max_f = max(all_f) if all_f else 0
            print(f"  {label:<25} {n_q:>10} {n_imag:>12} {min_f:>10.3f} {max_f:>10.3f}")

        gamma_crystal = find_qpoint(crystal["freqs_cm"], "0 0 0")
        gamma_f62 = find_qpoint(f62["freqs_cm"], "0 0 0")
        gamma_fdev = find_qpoint(fdev["freqs_cm"], "0 0 0")

        if gamma_crystal and gamma_f62:
            print(f"\n  Gamma point (q = 0 0 0) — frequencies in cm^-1:")
            print(f"  {'Band':<6} {'CRYSTAL':>12} {'FLEUR 6.2':>12} {'FLEUR 8.1':>12}")
            print(f"  {'-' * 6} {'-' * 12} {'-' * 12} {'-' * 12}")
            crystal_modes = crystal["freqs_cm"][gamma_crystal]
            f62_modes = f62["freqs_cm"][gamma_f62]
            fdev_modes = fdev["freqs_cm"].get(gamma_fdev, []) if gamma_fdev else []

            max_bands = max(len(crystal_modes), len(f62_modes), len(fdev_modes))
            for i in range(max_bands):
                c = format_freq(crystal_modes[i]) if i < len(crystal_modes) else "—"
                f1 = format_freq(f62_modes[i]) if i < len(f62_modes) else "—"
                f2 = format_freq(fdev_modes[i]) if i < len(fdev_modes) else "—"
                print(f"  {i + 1:<6} {c:>12} {f1:>12} {f2:>12}")


def main():
    base = Path("data/phonon_comparison")
    if not base.exists():
        print(f"error: {base} not found")
        return

    systems = ["ZnO", "KNbO3"]
    versions = [("fleur_62", "FLEUR 6.2"), ("fleur_develop", "FLEUR 8.1")]

    data = {}
    for system in systems:
        data[system] = {}
        data[system]["crystal"] = load_crystal(base, system)
        for vdir, vname in versions:
            data[system][vdir] = load_fleur(base, vdir, system)

    render(data, systems)

    out = base / "comparison_table.txt"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        render(data, systems)
    out.write_text(buf.getvalue())
    print(f"\n  Written to {out}")


if __name__ == "__main__":
    main()
