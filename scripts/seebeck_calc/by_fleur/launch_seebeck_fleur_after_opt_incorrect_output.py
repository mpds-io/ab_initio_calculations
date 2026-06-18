#!/usr/bin/env python3
"""
Launch FleurDOSLocalWorkChain (Seebeck via Fleur DOS) for 8 optimized phases.

Each phase has a known optimized StructureData PK from the Fleur optimization.
"""

import os
import sys

from aiida import load_profile
from aiida.engine import submit
from aiida.orm import Dict, Str, load_code, load_node

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

load_profile()

TEMPERATURE = 298.0

PHASES = {
    "Au2U/191": 68561,
    "BaSn3/194": 68638,
    "BiSe/164": 68689,
    "B2O3/152": 68761,
    "Ce5Ge3/193": 68767,
    "Co2As/189": 68795,
    "CrSb/194": 68783,
    "DyNi5/191": 68812,
}


def main():
    fleur_code = load_code("fleur")
    inpgen_code = load_code("inpgen")

    scf_wf_parameters = Dict(
        dict={
            "fleur_runmax": 5,
            "density_converged": 1.0e-6,
            "mode": "density",
            "itmax_per_run": 50,
        }
    )

    dos_wf_parameters = Dict(
        dict={
            "kpoints_mesh_dos": [54, 54, 54],
            "sigma": 0.002,
            "emin": -2.0,
            "emax": 2.0,
        }
    )

    seebeck_dict = DEFAULT_SEEBECK.copy()
    seebeck_dict["temperature"] = TEMPERATURE
    seebeck_params = Dict(dict=seebeck_dict)

    submitted = {}

    for phase_label, struct_pk in PHASES.items():
        structure = load_node(struct_pk)
        formula, sg = phase_label.split("/")

        inputs = {
            "scf": {
                "wf_parameters": scf_wf_parameters,
                "structure": structure,
                "inpgen": inpgen_code,
                "fleur": fleur_code,
            },
            "fleur": fleur_code,
            "wf_parameters": dos_wf_parameters,
            "seebeck_parameters": seebeck_params,
            "structure": structure,
            "phase": Str(phase_label),
        }

        try:
            seebeck_wc = submit(FleurDOSLocalWorkChain, **inputs)
            print(f"[OK] {phase_label}: FleurDOSLocalWorkChain PK={seebeck_wc.pk}")
            submitted[phase_label] = seebeck_wc.pk
        except Exception as e:
            print(f"[ERROR] {phase_label}: {e}")

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    print(f"{'Phase':<20} {'Seebeck WC PK':<15}")
    print("-" * 35)
    for phase_label, wc_pk in sorted(submitted.items()):
        print(f"{phase_label:<20} {wc_pk:<15}")

    if len(submitted) < len(PHASES):
        print(f"\nFailed: {len(PHASES) - len(submitted)}/{len(PHASES)}")


if __name__ == "__main__":
    main()