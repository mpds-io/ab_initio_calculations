"""Pressure-convergence test for ABACUS plane-wave cutoffs.

Cu2O relaxed 16% too large (a = 4.96 vs 4.27 A) because the computed
pressure at the experimental volume was +160 kbar — a Pulay/cutoff
artefact, not physics. This script runs plain SCF-with-stress at the
*experimental* geometry for a ladder of ecutwfc values; the converged
cutoff is the one where pressure stops moving (a few kbar).

Inputs (code, pseudos, kpoints, structure) are cloned from an existing
calculation so the only variable is ecutwfc.

Usage:
    python abacus_ecut_pressure_test.py <reference_calc_pk> [cutoffs...]
    python abacus_ecut_pressure_test.py 137102 100 150 200 250
"""

import sys

from aiida import load_profile

load_profile()

from aiida.engine import submit
from aiida.orm import Dict, load_node
from aiida.plugins import WorkflowFactory

AbacusBaseWorkChain = WorkflowFactory("abacus.base")


def main(ref_pk, cutoffs):
    ref = load_node(ref_pk)
    structure = ref.inputs.structure
    label = structure.get_formula()
    submitted = []

    for ecut in cutoffs:
        params = ref.inputs.parameters.get_dict()
        params["input"].update(
            {
                "ecutwfc": ecut,
                "calculation": "scf",
                "cal_stress": 1,
                "cal_force": 1,
            }
        )
        params["input"].pop("relax_nmax", None)

        builder = AbacusBaseWorkChain.get_builder()
        builder.abacus.code = ref.inputs.code
        builder.abacus.structure = structure
        builder.abacus.parameters = Dict(dict=params)
        builder.abacus.pseudos = dict(ref.inputs.pseudos)
        builder.abacus.kpoints = ref.inputs.kpoints
        builder.abacus.metadata.options = dict(ref.get_options())
        if "settings" in ref.inputs:
            builder.abacus.settings = ref.inputs.settings
        builder.metadata.label = f"{label} ecut-test {ecut}Ry"

        wc = submit(builder)
        print(f"ecutwfc {ecut} Ry -> pk {wc.pk}")
        submitted.append((ecut, wc.pk))

    print("Submitted:", submitted)
    print("Read pressures with: abacus_ecut_pressure_test.py --report", 
          " ".join(str(pk) for _, pk in submitted))


def report(pks):
    for pk in pks:
        wc = load_node(int(pk))
        ecut = wc.label.split()[-1]
        try:
            calc = [c for c in wc.called if c.process_type and "calculation" in c.process_type][0]
            log = calc.outputs.retrieved.base.repository.get_object_content(
                next(f for f in calc.outputs.retrieved.base.repository.list_object_names()
                     if f.startswith("running_"))
            )
            press = [l.split(":")[-1].strip() for l in log.splitlines() if "TOTAL-PRESSURE" in l]
            print(f"{ecut:>8}  pressure: {press[-1] if press else 'n/a'}  ({wc.process_state.value})")
        except Exception as exc:
            print(f"{ecut:>8}  not available yet ({exc.__class__.__name__}: {exc})")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--report":
        report(sys.argv[2:])
    else:
        ref_pk = int(sys.argv[1]) if len(sys.argv) > 1 else 137102
        cuts = [int(x) for x in sys.argv[2:]] or [100, 150, 200, 250]
        main(ref_pk, cuts)
