"""Force-convergence test for the ABACUS phonon campaign settings.

The campaign is moving to FLEUR-matched parameters: phonons on the
experimental MPDS cell with a coarse k-mesh (kpoints_distance 0.5 instead
of 0.15). Forces — not energies — are what phonon frequencies are built
from, so the setting has to be validated on forces.

Each test clones a *finished* displacement calculation (same structure,
same pseudos, same cutoff) and only changes kpoints_distance and/or
ecutwfc, so the reference forces of the original calculation are a direct
comparison baseline.

Usage:
    python abacus_force_convergence_test.py submit <ref_pk> [--distance 0.5] [--ecut 100]
    python abacus_force_convergence_test.py submit <ref_pk> --structure <structure_pk> --ecut 150
    python abacus_force_convergence_test.py report <test_pk> [<test_pk> ...]
"""

import argparse
import sys

import numpy as np
from aiida import load_profile

load_profile()

from aiida.engine import submit
from aiida.orm import Dict, Float, load_node
from aiida.plugins import WorkflowFactory

AbacusBaseWorkChain = WorkflowFactory("abacus.base")


def _forces(node):
    """Max/RMS forces of a finished calculation, as an (array, maxF) pair."""
    misc = node.outputs.misc.get_dict()
    return np.array(misc["final_forces"])


def submit_test(ref_pk, distance, ecut, structure_pk=None):
    ref = load_node(ref_pk)
    structure = load_node(structure_pk) if structure_pk else ref.inputs.structure

    params = ref.inputs.parameters.get_dict()
    scf = dict(params["input"])
    scf.update({"calculation": "scf", "cal_force": 1, "cal_stress": 1, "ecutwfc": ecut})
    scf.pop("relax_nmax", None)

    builder = AbacusBaseWorkChain.get_builder()
    builder.abacus.code = ref.inputs.code
    builder.abacus.structure = structure
    builder.abacus.parameters = Dict(dict={"input": scf})
    builder.abacus.pseudos = dict(ref.inputs.pseudos)
    builder.abacus.metadata.options = dict(ref.get_options())
    # yascheduler downloads results flat, so the retrieve list must stay flat
    if "settings" in ref.inputs:
        builder.abacus.settings = ref.inputs.settings
    else:
        builder.abacus.settings = Dict(dict={"flat_output": True})
    builder.kpoints_distance = Float(distance)
    builder.metadata.label = (
        f"force-test {structure.get_formula()} d={distance} ecut={ecut} (ref {ref_pk})"
    )

    wc = submit(builder)
    print(f"submitted pk {wc.pk}: {builder.metadata.label}")
    return wc.pk


def report(pks):
    print(f"{'test':>8} {'label':52s} {'mesh':14s} {'maxF':>9} {'vs ref maxF':>12} {'max dev':>9} {'RMS dev':>9}")
    for pk in pks:
        wc = load_node(int(pk))
        label = wc.label or ""
        ref_pk = label.split("ref ")[-1].rstrip(")") if "ref " in label else None
        try:
            calc = [c for c in wc.called if c.process_type and "AbacusCalculation" in str(type(c).__name__) or "calculations" in (c.process_type or "")][-1]
            f = _forces(calc)
            mesh = str(calc.inputs.kpoints.get_kpoints_mesh()[0])
        except Exception as exc:
            print(f"{pk:>8} {label:52s} pending/failed ({exc.__class__.__name__}: {exc})")
            continue
        dev_max = dev_rms = ref_max = float("nan")
        if ref_pk:
            try:
                fr = _forces(load_node(int(ref_pk)))
                if fr.shape == f.shape:
                    d = np.abs(f - fr)
                    dev_max, dev_rms = d.max(), float(np.sqrt((d**2).mean()))
                ref_max = np.abs(fr).max()
            except Exception:
                pass
        print(f"{pk:>8} {label:52s} {mesh:14s} {np.abs(f).max():9.5f} {ref_max:12.5f} {dev_max:9.5f} {dev_rms:9.5f}")
    print("\nForces in eV/Angstrom. A coarse mesh is safe when 'max dev' is small")
    print("relative to the force magnitudes that build the force constants.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("submit")
    s.add_argument("ref_pk", type=int)
    s.add_argument("--distance", type=float, default=0.5)
    s.add_argument("--ecut", type=int, default=100)
    s.add_argument("--structure", type=int, default=None)
    r = sub.add_parser("report")
    r.add_argument("pks", nargs="+")
    args = p.parse_args()
    if args.cmd == "submit":
        submit_test(args.ref_pk, args.distance, args.ecut, args.structure)
    else:
        report(args.pks)
