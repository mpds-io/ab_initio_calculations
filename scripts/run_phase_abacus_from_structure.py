"""Submit one ABACUS phonon phase from an existing StructureData node.

Needed where the MPDS route returns an unusable structure: for CaTiO3/62 the
MPDS entry converts to a 19-atom, oxygen-deficient cell (Ca4O11Ti4), which
breaks the symmetry and blows the displacement count up to 64. The October
FLEUR runs used a hand-built 20-atom cell (node 126128, Ca4O12Ti4) with no
provenance; reusing that exact node also makes our phonons directly
comparable to the FLEUR row for this phase.

Usage:
    python run_phase_abacus_from_structure.py <structure_pk> <label> [distance] [ecut]
    python run_phase_abacus_from_structure.py 126128 CaTiO3/62 0.5 150
"""

import sys

from aiida import load_profile

load_profile()

from aiida.engine import submit
from aiida.orm import Dict, Str, load_node

from mpds_aiida.workflows.abacus_base import MPDSAbacusWorkChain

SUPERCELL_MATRIX = [[1, 1, 0], [-1, 1, 0], [0, 0, 2]]


def main(structure_pk, label, distance, ecut):
    structure = load_node(structure_pk)
    print(f"structure {structure_pk}: {structure.get_formula()} ({len(structure.sites)} atoms)")

    builder = MPDSAbacusWorkChain.get_builder()
    builder.structure = structure
    builder.phase_label = Str(label)
    builder.workchain_options = Dict(
        dict={
            "codes": {
                "abacus": "abacus@yascheduler",
                "phonopy": "phonopy@local_machine",
            },
            "options": {
                "kpoints": [6, 6, 6],
                "kpoints_distance": distance,
                "calculation": "cell-relax",
                "need_phonons": True,
                "optimize_structure": False,
                "run": {
                    "resources": {"num_machines": 1, "num_mpiprocs_per_machine": 24},
                    "max_wallclock_seconds": 172800,
                },
            },
            "calculations": {
                "phonons": {"parameters": {"supercell_matrix": SUPERCELL_MATRIX}}
            },
            "default": {"scf": {"input": {"ecutwfc": ecut}}},
        }
    )
    builder.metadata.label = label

    wc = submit(builder)
    print(f"Submitted {label}: pk {wc.pk}")


if __name__ == "__main__":
    main(
        int(sys.argv[1]),
        sys.argv[2],
        float(sys.argv[3]) if len(sys.argv) > 3 else 0.5,
        int(sys.argv[4]) if len(sys.argv) > 4 else 100,
    )
