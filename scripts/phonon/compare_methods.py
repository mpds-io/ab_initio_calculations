#!/usr/bin/env python3
"""Compare custom / phonopy / ase integration methods on all available structures.

Outputs a summary table (ZPE, F@1000K, S@1000K, Cv@1000K) for each structure
and method, plus max relative differences.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ab_initio_calculations.calculations.phonon_thermo import integrate_phonons

REPO = Path(__file__).resolve().parents[2]

STRUCTURES = [
    ("MgO_225", REPO / "data/aiida_phonon_results/MgO_225/phonon_frequencies.txt"),
    ("SiC_186", REPO / "data/aiida_phonon_results/SiC_186/phonon_frequencies.txt"),
    ("BN_216", REPO / "data/aiida_phonon_results/BN_216/phonon_frequencies.txt"),
    ("NaCl_225", REPO / "data/aiida_phonon_results/NaCl_225/phonon_frequencies.txt"),
    ("ZnS_216", REPO / "data/aiida_phonon_results/ZnS_216/phonon_frequencies.txt"),
    ("GaAs_216", REPO / "data/aiida_phonon_results/GaAs_216/phonon_frequencies.txt"),
    (
        "SrTiO3_221",
        REPO / "data/aiida_phonon_results/SrTiO3_221/phonon_frequencies.txt",
    ),
    (
        "ZnO_186 (aiida)",
        REPO / "data/aiida_phonon_results/ZnO_186/phonon_frequencies.txt",
    ),
    (
        "KNbO3_221 (aiida)",
        REPO
        / "data/manual_fleur_phonopy/runs/KNbO3_221_aiida_95161/phonon_frequencies.txt",
    ),
]

METHODS = ["custom", "phonopy", "ase"]


def main() -> int:
    print(
        f"{'Structure':<25} {'Method':<8} {'ZPE':>12} {'F@1000K':>12} {'S@1000K':>12} {'Cv@1000K':>12}"
    )
    print("-" * 95)

    for name, path in STRUCTURES:
        if not path.exists():
            print(f"{name:<25} FILE NOT FOUND: {path}")
            continue

        results = {}
        for method in METHODS:
            r = integrate_phonons(
                fleur_path=path, t_max=1000, t_step=200, method=method
            )
            d = r["fleur"]
            if "error" in d:
                print(f"{name:<25} {method:<8} ERROR: {d['error'][:50]}")
                continue
            tp = d["thermal_properties"]
            zpe = d["zero_point_energy"]
            row = tp[tp[:, 0] == 1000][0]
            results[method] = {
                "zpe": zpe,
                "F": row[1],
                "S": row[2],
                "Cv": row[3],
            }
            print(
                f"{name:<25} {method:<8} "
                f"{zpe:>12.6f} {row[1]:>12.6f} {row[2]:>12.6f} {row[3]:>12.6f}"
            )

        # Show max relative diff between methods
        if len(results) >= 2:
            for key in ["zpe", "F", "S", "Cv"]:
                vals = [results[m][key] for m in results]
                max_val = max(abs(v) for v in vals)
                if max_val > 1e-10:
                    max_diff = max(vals) - min(vals)
                    rel = max_diff / max_val
                    if rel > 1e-4:
                        print(
                            f"  ^ {key}: max_diff={max_diff:.2e} rel={rel:.2e}  "
                            f"vs custom={results.get('custom', {}).get(key, 'N/A')}"
                        )

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
