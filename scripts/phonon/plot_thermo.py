#!/usr/bin/env python3
"""
Plot phonon thermodynamic properties (free energy, entropy, C_V) vs temperature
for ZnO and KNbO3, comparing CRYSTAL, FLEUR 6.2, and FLEUR 8.1 data.

Reads phonon data from data/phonon_comparison/ and writes a 2x3 plot grid
(2 systems x 3 properties) over 0-1000 K with a 25 K step.

Usage:
    python3 scripts/phonon/plot_thermo.py [--t-max 1000] [--t-step 25]
        [--output summary/phonon_thermo/phonon_thermo_0_1000K.png]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ab_initio_calculations.calculations.phonon_thermo import integrate_phonons


SYSTEMS = ["ZnO", "KNbO3"]

SOURCES = [
    ("CRYSTAL", "crystal", "json", "r", "-"),
    ("FLEUR 6.2", "fleur_62", "txt", "b", "-"),
    ("FLEUR 8.1", "fleur_develop", "txt", "g", "--"),
]

PROP_LABELS = ["Free energy [kJ/mol]", "Entropy [J/K/mol]", "C_V [J/K/mol]"]
PROP_IDX = [1, 2, 3]


def load_system(
    base: Path, system: str, folder: str, ftype: str, t_max: int, t_step: int
):
    if ftype == "json":
        p = base / "crystal" / system / "phonon_data.json"
        res = integrate_phonons(crystal_path=p, t_max=t_max, t_step=t_step)
        return res.get("crystal")
    p = base / folder / system / "phonon_frequencies.txt"
    res = integrate_phonons(fleur_path=p, t_max=t_max, t_step=t_step)
    return res.get("fleur")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=Path("data/phonon_comparison"),
        help="Base directory with phonon data (default: data/phonon_comparison).",
    )
    parser.add_argument("--t-max", type=int, default=1000, help="Max temperature [K].")
    parser.add_argument("--t-step", type=int, default=25, help="Temperature step [K].")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("summary/phonon_thermo/phonon_thermo_0_1000K.png"),
        help="Output PNG path.",
    )
    args = parser.parse_args()

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    for row, system in enumerate(SYSTEMS):
        results = {}
        for label, folder, ftype, _, _ in SOURCES:
            results[label] = load_system(
                args.base, system, folder, ftype, args.t_max, args.t_step
            )

        for col, (plabel, pidx) in enumerate(zip(PROP_LABELS, PROP_IDX)):
            ax = axes[row][col]
            for label, _, _, color, ls in SOURCES:
                d = results.get(label)
                if d is None or "error" in d:
                    continue
                tp = d["thermal_properties"]
                ax.plot(
                    tp[:, 0],
                    tp[:, pidx],
                    color=color,
                    linestyle=ls,
                    label=label,
                    linewidth=1.8,
                )
            ax.set_xlabel("Temperature [K]")
            ax.set_ylabel(plabel)
            ax.set_title(f"{system}: {plabel}")
            ax.grid(True, alpha=0.3)
            ax.legend(fontsize=9)

    plt.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(args.output, dpi=150)
    print(f"saved {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
