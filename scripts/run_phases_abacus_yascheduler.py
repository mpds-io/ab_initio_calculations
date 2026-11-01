"""Submit the ABACUS phonon campaign (8 non-magnetic phases from the October
phonon_summary CSV) through MPDSAbacusStructureWorkChain on the Contabo
nodes via yascheduler.

Supercell matrix matches the October FLEUR runs: [[1,1,0],[-1,1,0],[0,0,2]].
Waves: light -> medium -> heavy, so the two nodes are never clogged by a
single heavy phase upfront.

Usage:
    MPDS_KEY=... python run_phases_abacus_yascheduler.py [wave1|wave2|wave3|all]
"""

import os
import sys

from aiida import load_profile

load_profile()

from aiida.engine import submit
from aiida.orm import Dict

from mpds_aiida.workflows.abacus_mpds import MPDSAbacusStructureWorkChain

SUPERCELL_MATRIX = [[1, 1, 0], [-1, 1, 0], [0, 0, 2]]

# (formulae, sgs, classes, kpoints for the unit-cell relax mesh)
# Per-phase k-density and cutoff, each justified by a force-convergence test
# (abacus_force_convergence_test.py) against a dense reference. The force error
# tracks the band gap: wide-gap oxides tolerate a coarse mesh, the near-zero-gap
# InSb does not. A single global setting is wrong in both directions.
#
#   phase        distance  mesh      RMS force error vs dense reference
#   LaAlO3/221   0.5       3x3x2     0.9%
#   GaP/216      0.3       6x4x4     1.4%  (0.5 -> 2.6%)
#   InSb/216     0.25      6x4x4     <3.3% (0.3 -> 3.3%, 0.4 -> 25%, 0.5 -> 118%;
#                                       near-zero PBE gap, very sharp knee, so
#                                       one step denser than the validated point)
#   Cu2O/224     pending   narrow gap like InSb: 2x2x2 -> 3x3x3 moved forces by
#                        14.7% RMS, so the mesh dominated, not the cutoff
#                        (100 -> 150 Ry was 2.9% on the too-coarse mesh)
#   CaTiO3/62    0.5       at 150 Ry as a Ti 3s3p semicore precaution, untested
#
# The remaining oxides inherit LaAlO3's setting: same wide-gap character.
PHASES = {
    "wave1": [
        ("GaP", 216, "binary", [6, 6, 6], 0.3, 100),
        ("InSb", 216, "binary", [6, 6, 6], 0.25, 100),
        ("LaAlO3", 221, "ternary", [6, 6, 6], 0.5, 100),
        ("Cu2O", 224, "binary", [6, 6, 6], 0.3, 150),
    ],
    "wave2": [
        ("YAlO3", 62, "ternary", [6, 6, 6], 0.5, 100),
        ("CaTiO3", 62, "ternary", [6, 6, 6], 0.5, 150),
    ],
    "wave3": [
        ("Al2O3", 167, "binary", [4, 4, 4], 0.5, 100),
        ("MgAl2O4", 227, "ternary", [4, 4, 4], 0.5, 100),
    ],
}


def main(wave, skip=()):
    assert os.getenv("MPDS_KEY"), "MPDS_KEY must be set"
    phases = PHASES[wave] if wave != "all" else sum(PHASES.values(), [])
    if skip:
        phases = [p for p in phases if p[0] not in skip]
        print("skipping:", ", ".join(skip))
    submitted = []
    for formulae, sgs, classes, kpoints, distance, ecut in phases:
        inputs = MPDSAbacusStructureWorkChain.get_builder()
        # NB query by formulae+sgs only, as the October FLEUR/CRYSTAL runs did.
        # Passing "classes" adds nothing and silently returns 204 No Results
        # when it disagrees with the phase (MgAl2O4 is ternary, not quaternary).
        inputs.mpds_query = Dict(dict={"formulae": formulae, "sgs": sgs})
        inputs.workchain_options = Dict(
            dict={
                "codes": {
                    "abacus": "abacus@yascheduler",
                    "phonopy": "phonopy@local_machine",
                },
                "options": {
                    "kpoints": kpoints,
                    # Validated per phase (see PHASES); FLEUR's fixed [2,2,3]
                    # is in this range but undersamples the doubled axis.
                    "kpoints_distance": distance,
                    "calculation": "cell-relax",
                    "need_phonons": True,
                    # Phonons on the experimental MPDS cell, as in FLEUR
                    "optimize_structure": False,
                    "run": {
                        "resources": {
                            "num_machines": 1,
                            "num_mpiprocs_per_machine": 24,
                        },
                        "max_wallclock_seconds": 172800,
                    },
                },
                "calculations": {
                    "phonons": {"parameters": {"supercell_matrix": SUPERCELL_MATRIX}}
                },
                # ecutwfc lives in the template's scf block, not in options;
                # recursive_update merges this over the template.
                "default": {"scf": {"input": {"ecutwfc": ecut}}},
            }
        )
        inputs.metadata.label = f"{formulae}/{sgs}"
        wc = submit(MPDSAbacusStructureWorkChain, **inputs)
        print(f"Submitted {formulae}/{sgs}: pk {wc.pk}")
        submitted.append((formulae, sgs, wc.pk))
    print("Done:", submitted)


if __name__ == "__main__":
    wave = sys.argv[1] if len(sys.argv) > 1 else "wave1"
    skip = sys.argv[2].split(",") if len(sys.argv) > 2 else ()
    main(wave, skip)
