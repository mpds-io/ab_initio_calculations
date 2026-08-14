"""
Download a crystal structure from the MPDS API by phase_id and save it as a
POSCAR (VASP) file for use with the FLEUR + phonopy pipeline.

Requires the mpds_client package and a valid MPDS API key (set via the
MPDS_KEY environment variable or the mpds_client config).

Usage:

    python3 scripts/phonon/download_mpds_structure.py \\
        --phase-id 7282 \\
        --output data/manual_fleur_phonopy/structures/ZnO_7282.poscar

By default the first experimental structure (peer-reviewed) is returned.
Use --dtype ab_initio or --dtype all to include in-house calculations.
"""

import argparse
import sys
from pathlib import Path


def download_structure(phase_id: int, output: str, dtype: str = "peer_reviewed"):
    from mpds_client import MPDSDataRetrieval, MPDSDataTypes
    from ase.io import write as ase_write

    c = MPDSDataRetrieval()
    if dtype == "all":
        c.dtype = MPDSDataTypes.ALL
    elif dtype == "ab_initio":
        c.dtype = MPDSDataTypes.AB_INITIO
    else:
        c.dtype = MPDSDataTypes.PEER_REVIEWED

    results = list(
        c.get_data(
            {"props": "atomic structure"},
            phases=[phase_id],
            fields={
                "S": [
                    "phase_id",
                    "entry",
                    "chemical_formula",
                    "cell_abc",
                    "sg_n",
                    "basis_noneq",
                    "els_noneq",
                ]
            },
        )
    )

    if not results:
        sys.exit(f"error: no structures found for phase_id={phase_id}")

    crystal = MPDSDataRetrieval.compile_crystal(results[0], "ase")
    if crystal is None:
        sys.exit(f"error: could not compile crystal from MPDS entry {results[0][1]}")

    formula = crystal.get_chemical_formula()
    sg_n = results[0][4]
    n_atoms = len(crystal)

    ase_write(output, crystal, format="vasp")

    print(f"phase_id:     {phase_id}")
    print(f"entry:        {results[0][1]}")
    print(f"formula:      {formula}")
    print(f"space group:  {sg_n}")
    print(f"atoms:        {n_atoms}")
    print(f"saved to:     {output}")
    print(f"total structures available: {len(results)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--phase-id", type=int, required=True, help="MPDS distinct phase identifier"
    )
    ap.add_argument("--output", required=True, help="output POSCAR file path")
    ap.add_argument(
        "--dtype",
        choices=["peer_reviewed", "ab_initio", "all"],
        default="peer_reviewed",
        help="data type (default: peer_reviewed)",
    )
    args = ap.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    download_structure(args.phase_id, str(output), args.dtype)


if __name__ == "__main__":
    main()
