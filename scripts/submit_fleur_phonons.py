#!/usr/bin/env python3
"""
Submit PhonopyFleurWorkChain for ZnO (phase_id=7282) and KNbO3 (phase_id=16803)
through AiiDA + yascheduler.

wf_parameters match the manual pipeline's tuningB_fast preset (the one that
produced a clean 0-imaginary-mode result for ZnO_7282 by hand). Mixing is
plain inpgen defaults (Anderson) in both the manual and AiiDA paths -- the
actual gap was resources: previous AiiDA runs used num_mpiprocs_per_machine=1
with no OMP threads for a 16-atom/1991-basis-function supercell, and several
of the 8 displacement SCF jobs crashed outright (FLEUR killed mid-setup, no
juDFT error, no usage.json -- see summary/ for the full diagnosis). options
below gives each FLEUR job real resources instead of the FleurForcesWorkChain/
FleurScfWorkChain built-in single-process defaults.

Usage:
    # Dry-run first (validates inp.xml generation, no FLEUR SCF):
    python3 scripts/submit_fleur_phonons.py --dry-run

    # Full run:
    python3 scripts/submit_fleur_phonons.py
"""

import os
import sys

os.environ.setdefault("FLEUR_INPGEN_PATH", "/root/fleur/build/inpgen")

from aiida import load_profile
from aiida.orm import Dict, List, Bool, Str, load_code
from aiida.plugins import DataFactory
from aiida.engine import submit

load_profile()

STRUCTURE_DATA = DataFactory("core.structure")


def get_structure(phase_id: int, formula: str, sgs: int):
    """Download a structure from MPDS and convert to AiiDA StructureData."""
    from mpds_client import MPDSDataRetrieval, MPDSDataTypes
    from ase.io import read as ase_read
    import tempfile

    c = MPDSDataRetrieval()
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
    formula = crystal.get_chemical_formula()
    print(f"  downloaded: {formula}, {len(crystal)} atoms, sg={results[0][4]}")

    # ASE -> AiiDA StructureData
    structure = STRUCTURE_DATA()
    structure.set_cell(crystal.cell.array)
    structure.set_pbc(True)
    for atom in crystal:
        structure.append_atom(
            position=atom.position.tolist()
            if hasattr(atom.position, "tolist")
            else atom.position,
            symbols=atom.symbol,
        )
    return structure


def build_fleur_parameters():
    """Build fleur_parameters (kwargs for FleurForcesWorkChain).

    Loads the standard flapw_default.yml template from mpds_aiida and
    extracts wf_parameters for the SCF step. This ensures we use exactly
    the same parameters as the standard pipeline.

    options.resources are NOT in the template but are required for
    yascheduler: without num_mpiprocs_per_machine, AiiDA defaults to
    1 MPI process, making FLEUR with 300 iterations take weeks.
    """
    from mpds_aiida.common import get_template

    template = get_template("flapw_default.yml")
    scf_wf = template["default"]["scf"]["wf_parameters"]

    return Dict(
        dict={
            "fleur": "fleur@yascheduler",
            "wf_parameters": scf_wf,
            "options": {
                "resources": {
                    "num_machines": 1,
                    "num_mpiprocs_per_machine": 2,
                },
                "environment_variables": {"OMP_NUM_THREADS": "1"},
                "max_wallclock_seconds": 4 * 10**5,
                "withmpi": True,
                "import_sys_environment": False,
                "queue_name": "",
                "custom_scheduler_commands": "",
            },
        }
    )


def submit_phonons(structure, supercell_matrix, label, dry_run=False):
    """Submit PhonopyFleurWorkChain."""
    from mpds_aiida.workflows.fleur_phonopy import PhonopyFleurWorkChain

    inputs = {
        "structure": structure,
        "supercell_matrix": List(list=supercell_matrix),
        "fleur_parameters": build_fleur_parameters(),
        "kpoints_mesh": List(list=[2, 2, 3]),
        "phonopy": {
            "code": load_code("phonopy@local_machine"),
            "parameters": Dict(dict={"WRITE_FORCE_CONSTANTS": True}),
        },
        "clean_workdir": Bool(False),
        "test_magmoms_run": Bool(dry_run),
        "metadata": {"label": label},
    }

    node = submit(PhonopyFleurWorkChain, **inputs)
    print(f"  submitted: PK={node.pk} label={label} dry_run={dry_run}")
    return node


def main():
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true", help="validate inp.xml only, no SCF"
    )
    ap.add_argument(
        "--formula",
        default=None,
        help="only submit this formula (e.g. ZnO or KNbO3); default: all systems",
    )
    args = ap.parse_args()

    systems = [
        # --- Old structures (commented out) ---
        # {
        #     "phase_id": 9968,
        #     "formula": "MgO",
        #     "sgs": 225,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 6336,
        #     "formula": "SiC",
        #     "sgs": 186,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 8998,
        #     "formula": "BN",
        #     "sgs": 216,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 6769,
        #     "formula": "NaCl",
        #     "sgs": 225,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 86,
        #     "formula": "ZnS",
        #     "sgs": 216,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 5813,
        #     "formula": "GaAs",
        #     "sgs": 216,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 18989,
        #     "formula": "SrTiO3",
        #     "sgs": 221,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 12954,
        #     "formula": "BaTiO3",
        #     "sgs": 221,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 7282,
        #     "formula": "ZnO",
        #     "sgs": 186,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # {
        #     "phase_id": 16803,
        #     "formula": "KNbO3",
        #     "sgs": 221,
        #     "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        # },
        # --- New structures: 5 binary + 5 complex ---
        # Binary
        {
            "phase_id": 6597,
            "formula": "Al2O3",
            "sgs": 167,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 6376,
            "formula": "GaP",
            "sgs": 216,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 6409,
            "formula": "InSb",
            "sgs": 216,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 5250,
            "formula": "Cu2O",
            "sgs": 224,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 5344,
            "formula": "Fe2O3",
            "sgs": 167,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        # Complex
        {
            "phase_id": 13167,
            "formula": "CaTiO3",
            "sgs": 62,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 12744,
            "formula": "LaAlO3",
            "sgs": 221,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 10561,
            "formula": "YAlO3",
            "sgs": 62,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 8713,
            "formula": "MgAl2O4",
            "sgs": 227,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 9013,
            "formula": "BiFeO3",
            "sgs": 221,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
    ]
    if args.formula:
        systems = [s for s in systems if s["formula"] == args.formula]

    for sys_info in systems:
        label = f"{sys_info['formula']}/{sys_info['sgs']} - phonons"
        print(f"\n=== {label} ===")
        print(f"  phase_id={sys_info['phase_id']}, supercell={sys_info['supercell']}")

        structure = get_structure(
            sys_info["phase_id"], sys_info["formula"], sys_info["sgs"]
        )
        submit_phonons(
            structure,
            sys_info["supercell"],
            label,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
