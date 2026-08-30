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

    Note: PhonopyFleurWorkChain.run_forces does:
        inputs = self.inputs.fleur_parameters.get_dict()
        ... inputs["fleurinp"] = ...; submit(FleurForcesWorkChain, **inputs)

    So fleur_parameters is a Dict whose .get_dict() returns kwargs for
    FleurForcesWorkChain. The values must be plain JSON-serializable types.

    IMPORTANT: FleurScfWorkChain does NOT accept calc_parameters when
    fleurinp is given (exit 231 ERROR_INVALID_INPUT_CONFIG). The kmax/kpt
    are already baked into inp.xml by inpgen. We only pass wf_parameters
    with inpxml_changes to override the mixing scheme post-inpgen.

    "options" is forwarded by FleurForcesWorkChain to both its FleurScfWorkChain
    (SCF) and its own FleurBaseWorkChain (forces) sub-steps -- without it, both
    fall back to num_mpiprocs_per_machine=1 with no OMP threads, which is what
    crashed roughly half of the 8 displacement SCF jobs in earlier runs.

    num_mpiprocs_per_machine: FleurBaseWorkChain.check_kpts() auto-tunes MPI
    count to evenly divide the fleurinp's k-point count and REJECTS the job
    (ERROR_NOT_OPTIMAL_RESOURCES, exit 390) if the best achievable divisor
    covers <60% of the requested num_mpiprocs_per_machine
    (aiida_fleur/tools/common_fleur_wf.py:optimize_calc_options). There is no
    single value that cleanly divides every system's k-point counts:
    ZnO_7282's 8 displacements need 40/68 (4 divides both), KNbO3_16803's
    need 30/50 (10 divides both, but 68 only gives 40% with 10 -> rejected).
    10 is used here since it's correct for the systems currently submitted
    by this script; if you add a system whose k-point counts don't share a
    large-enough common divisor with 10, check_kpts will reject it the same
    way and this needs picking again (see the exact math in
    optimize_calc_options -- log a `verdi process report` and look for
    "Number of k-points is N" per displacement).

    itmax_per_run=10, fleur_runmax=4: matches scripts/phonon/manual/run_fleur_scf.py's
    tuningB_fast preset. A displacement that stalls within this budget (seen
    on one of KNbO3_16803's 4 displacements) is now handled by
    FleurForcesWorkChain.retry_scf_with_halved_kmesh in mpds-aiida, which
    retries once with the k-point mesh halved -- the mechanism that actually
    converges it in the manual pipeline (verified: same stalled energy_diff
    at the original mesh, converges within 10 more iterations after halving).
    A wider itmax_per_run alone was tried first and is not this value's
    purpose here; the real fix is the halved-mesh retry.
    """
    return Dict(
        dict={
            "fleur": "fleur@yascheduler",
            "wf_parameters": {
                "mode": "energy",
                "fleur_runmax": 4,
                "itmax_per_run": 10,
                "energy_converged": 0.0001,
            },
            "options": {
                "resources": {
                    "num_machines": 1,
                    "num_mpiprocs_per_machine": 10,
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
        {
            "phase_id": 9968,
            "formula": "MgO",
            "sgs": 225,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 6336,
            "formula": "SiC",
            "sgs": 186,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 8998,
            "formula": "BN",
            "sgs": 216,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 6769,
            "formula": "NaCl",
            "sgs": 225,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 86,
            "formula": "ZnS",
            "sgs": 216,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 5813,
            "formula": "GaAs",
            "sgs": 216,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 18989,
            "formula": "SrTiO3",
            "sgs": 221,
            "supercell": [[1, 1, 0], [-1, 1, 0], [0, 0, 2]],
        },
        {
            "phase_id": 12954,
            "formula": "BaTiO3",
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
