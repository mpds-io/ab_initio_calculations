#!/usr/bin/env python3
"""
Wait for MPDSFleurStructureWorkChain optimizations to complete,
then submit FleurDOSLocalWorkChain for Seebeck calculation.

Usage:
    python launch_seebeck_after_optimization.py              # auto-detect from mpds_seebeck_data CSVs
    python launch_seebeck_after_optimization.py 64361 64365   # specific WorkChain PKs
"""

import os
import sys
import time

from aiida import load_profile
from aiida.engine import submit
from aiida.orm import Dict, Str, load_code, load_node
from aiida.common.exceptions import NotExistent

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

load_profile()

CSV_DIR = "/root/projects/ab_initio_calculations/mpds_seebeck_data"
CSV_FILES = [
    os.path.join(CSV_DIR, "ab_initio_seebeck_data.csv"),
    os.path.join(CSV_DIR, "ab_initio_seebeck_data_3el.csv"),
]
TEMPERATURE = 298.0
POLL_INTERVAL = 30


def find_recent_structure_workchains():
    from aiida.orm import WorkChainNode
    from mpds_aiida.workflows.fleur_mpds import MPDSFleurStructureWorkChain
    qb = WorkChainNode
    nodes = WorkChainNode.collection.all()
    results = []
    for node in WorkChainNode.collection.find(filters={"process_label": "MPDSFleurStructureWorkChain"}):
        if not node.is_finished and not node.is_excepted and not node.is_killed:
            results.append(node.pk)
    return sorted(results)


def get_phase_from_label(wc):
    label = wc.base.attributes.get("label", "")
    if "/" in label:
        parts = label.split("/")
        return parts[0], int(parts[1])
    return label, None


def poll_and_submit(workchain_pks):
    fleur_code = load_code("fleur")
    inpgen_code = load_code("inpgen")

    pending = set(workchain_pks)
    submitted_seebeck = {}
    failed = {}

    while pending:
        still_pending = set()
        for pk in pending:
            wc = load_node(pk)
            if wc.is_finished:
                try:
                    optimized = wc.outputs.optimized_structure
                except NotExistent:
                    print(f"[FAIL] PK={pk}: finished but no optimized_structure output")
                    failed[pk] = "no_optimized_structure"
                    continue

                formula, sg = get_phase_from_label(wc)
                print(f"[DONE] PK={pk}: {formula}/{sg} optimized_structure PK={optimized.pk}")

                scf_wf_parameters = Dict(dict={
                    "fleur_runmax": 5,
                    "density_converged": 1.0e-6,
                    "mode": "density",
                    "itmax_per_run": 50,
                })

                dos_wf_parameters = Dict(dict={
                    "kpoints_mesh_dos": [54, 54, 54],
                    "sigma": 0.002,
                    "emin": -2.0,
                    "emax": 2.0,
                })

                seebeck_dict = DEFAULT_SEEBECK.copy()
                seebeck_dict["temperature"] = TEMPERATURE
                seebeck_params = Dict(dict=seebeck_dict)

                inputs = {
                    "scf": {
                        "wf_parameters": scf_wf_parameters,
                        "structure": optimized,
                        "inpgen": inpgen_code,
                        "fleur": fleur_code,
                    },
                    "fleur": fleur_code,
                    "wf_parameters": dos_wf_parameters,
                    "seebeck_parameters": seebeck_params,
                    "structure": optimized,
                    "phase": Str(f"{formula}/{sg}"),
                }

                try:
                    seebeck_wc = submit(FleurDOSLocalWorkChain, **inputs)
                    print(f"  [OK] Seebeck submitted: FleurDOSLocalWorkChain PK={seebeck_wc.pk}")
                    submitted_seebeck[pk] = seebeck_wc.pk
                except Exception as e:
                    print(f"  [ERROR] Seebeck submission failed: {e}")
                    failed[pk] = str(e)

            elif wc.is_excepted or wc.is_killed:
                print(f"[FAIL] PK={pk}: process {wc.process_state}")
                failed[pk] = str(wc.process_state)
            else:
                still_pending.add(pk)

        pending = still_pending
        if pending:
            print(f"\nWaiting for {len(pending)} workchains... (next poll in {POLL_INTERVAL}s)")
            time.sleep(POLL_INTERVAL)

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")
    if submitted_seebeck:
        print(f"Seebeck submitted: {len(submitted_seebeck)}")
        print(f"{'Struct WC PK':<15} {'Seebeck WC PK':<15}")
        print("-" * 30)
        for struct_pk, seebeck_pk in submitted_seebeck.items():
            print(f"{struct_pk:<15} {seebeck_pk:<15}")
    if failed:
        print(f"\nFailed: {len(failed)}")
        for pk, reason in failed.items():
            print(f"  PK={pk}: {reason}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        wc_pks = [int(a) for a in sys.argv[1:]]
    else:
        wc_pks = find_recent_structure_workchains()

    if not wc_pks:
        print("No pending MPDSFleurStructureWorkChain instances found.")
        sys.exit(1)

    print(f"Monitoring {len(wc_pks)} workchains: {wc_pks}")
    poll_and_submit(wc_pks)