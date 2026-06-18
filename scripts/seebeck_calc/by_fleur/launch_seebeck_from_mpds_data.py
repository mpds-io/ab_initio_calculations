#!/usr/bin/env python3
"""
Launch MPDSFleurStructureWorkChain (optimization) for each phase
from mpds_seebeck_data CSVs, then FleurDOSLocalWorkChain for Seebeck
at T=298K using remote from completed optimization.

Usage:
    python launch_seebeck_from_mpds_data.py              # all phases from both CSVs
    python launch_seebeck_from_mpds_data.py BaO/225       # single phase
"""

import os
import sys

import polars as pl

os.environ["MPDS_KEY"] = "KEY_HERE"

from aiida import load_profile
from aiida.engine import submit
from aiida.orm import Dict, Str, load_code
from aiida.plugins import DataFactory
from aiida.common.exceptions import NotExistent

from mpds_aiida.workflows.fleur_mpds import MPDSFleurStructureWorkChain
from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

load_profile()

CSV_DIR = "mpds_seebeck_data"
CSV_FILES = [
    os.path.join(CSV_DIR, "ab_initio_seebeck_data.csv"),
    os.path.join(CSV_DIR, "ab_initio_seebeck_data_3el.csv"),
]
TEMPERATURE = 298.0


def load_phases():
    all_phases = []
    for csv_path in CSV_FILES:
        df = pl.read_csv(csv_path)
        phases = [(row["formula"], int(row["sg"])) for row in df.iter_rows(named=True)]
        all_phases.extend(phases)
    seen = set()
    unique = []
    for p in all_phases:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


fleur_code = load_code("fleur")

phases = load_phases()

if len(sys.argv) > 1:
    arg = sys.argv[1].split("/")
    phases = [(arg[0], int(arg[1]))]

structure_results = []
seebeck_results = []

for formula, sg in phases:
    print(f"\n{'='*60}")
    print(f"Processing {formula}/{sg}")

    builder = MPDSFleurStructureWorkChain.get_builder()
    builder.metadata = dict(label="/".join(map(str, [formula, sg])))
    builder.mpds_query = DataFactory("dict")(
        dict={"formulae": formula, "sgs": sg},
    )
    builder.workchain_options = Dict(dict={
        "options": {
            "optimize_structure": True,
            "need_phonons": False,
            "optimizer": "CG",
            "calculator": "scf",
        }
    })

    try:
        wc = submit(builder)
        print(f"  [OK] Launched MPDSFleurStructureWorkChain PK={wc.pk}")
        structure_results.append((formula, sg, wc.pk, "submitted"))
    except Exception as e:
        print(f"  [ERROR] {e}")
        structure_results.append((formula, sg, "-", "errored"))
        continue

    try:
        remote = wc.outputs.optimized_structure
    except (NotExistent, AttributeError):
        print(f"  [SKIP] No optimized_structure yet for {formula}/{sg}, Seebeck will need remote manually")
        seebeck_results.append((formula, sg, wc.pk, "-", "no_remote_yet"))
        continue

    wf_para_dos = Dict(dict={
        "kpoints_mesh_dos": [54, 54, 54],
        "sigma": 0.002,
        "emin": -2.0,
        "emax": 2.0,
    })

    seebeck_dict = DEFAULT_SEEBECK.copy()
    seebeck_dict["temperature"] = TEMPERATURE
    seebeck_params_node = Dict(dict=seebeck_dict)

    inputs = {
        "fleur": fleur_code,
        "remote": remote,
        "wf_parameters": wf_para_dos,
        "seebeck_parameters": seebeck_params_node,
        "phase": Str(f"{formula}/{sg}"),
    }

    try:
        seebeck_wc = submit(FleurDOSLocalWorkChain, **inputs)
        print(f"  [OK] Submitted FleurDOSLocalWorkChain PK={seebeck_wc.pk} T={TEMPERATURE}K")
        seebeck_results.append((formula, sg, wc.pk, seebeck_wc.pk, "submitted"))
    except Exception as e:
        print(f"  [ERROR] Seebeck submission failed: {e}")
        seebeck_results.append((formula, sg, wc.pk, "-", "errored"))

print(f"\n{'='*60}")
print("Structure WorkChains:")
print(f"{'Formula':<12} {'SG':<6} {'WC PK':<12} {'Status':<15}")
print("-" * 50)
for r in structure_results:
    print(f"{r[0]:<12} {r[1]:<6} {r[2]:<12} {r[3]:<15}")

submitted = sum(1 for r in structure_results if r[2] != "-")
print(f"\nTotal: {len(structure_results)} | Submitted: {submitted}")

print(f"\n{'='*60}")
print("Seebeck WorkChains:")
print(f"{'Formula':<12} {'SG':<6} {'Struct WC':<12} {'Seebeck WC':<12} {'Status':<15}")
print("-" * 60)
for r in seebeck_results:
    print(f"{r[0]:<12} {r[1]:<6} {r[2]:<12} {r[3]:<12} {r[4]:<15}")

submitted_s = sum(1 for r in seebeck_results if r[3] != "-")
print(f"\nTotal: {len(seebeck_results)} | Submitted: {submitted_s}")