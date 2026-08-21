#!/usr/bin/env python3
"""
Integrate phonon frequencies from CRYSTAL and FLEUR calculations into
thermodynamic properties (free energy, entropy, C_V, zero-point energy).

Reads:
  - CRYSTAL: phonon_data.json (frequencies in cm^-1, from AiiDA parser)
  - FLEUR:   phonon_frequencies.txt (frequencies in THz, from phonopy)

Outputs a markdown table of [T, free_energy, entropy, C_V] over a temperature
grid. At least one of --crystal / --fleur is required; both may be given to
produce a side-by-side comparison.

Usage:
    PYTHONPATH=. python scripts/phonon/integrate_phonons.py \
        --crystal data/phonon_comparison/crystal/ZnO/phonon_data.json \
        --fleur data/phonon_comparison/fleur_62/ZnO/phonon_frequencies.txt \
        --t-max 1000 --t-step 25 [--output report.md]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ab_initio_calculations.calculations.phonon_thermo import (
    format_report,
    integrate_phonons,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--crystal",
        type=Path,
        default=None,
        help="Path to CRYSTAL phonon_data.json (frequencies in cm^-1).",
    )
    parser.add_argument(
        "--fleur",
        type=Path,
        default=None,
        help="Path to FLEUR phonon_frequencies.txt (frequencies in THz).",
    )
    parser.add_argument("--t-max", type=int, default=1000, help="Max temperature [K].")
    parser.add_argument("--t-step", type=int, default=25, help="Temperature step [K].")
    parser.add_argument("--t-min", type=int, default=0, help="Min temperature [K].")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write markdown report to this file instead of stdout.",
    )
    args = parser.parse_args()

    if not args.crystal and not args.fleur:
        parser.error("at least one of --crystal or --fleur is required")

    result = integrate_phonons(
        crystal_path=args.crystal,
        fleur_path=args.fleur,
        t_max=args.t_max,
        t_step=args.t_step,
        t_min=args.t_min,
    )
    report = format_report(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
