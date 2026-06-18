#!/usr/bin/env python3
"""
Launch FleurDOSLocalWorkChain for Seebeck coefficient calculation
for all phases from ab_initio_seebeck_data.csv.

Uses SCF + DOS mode: for each phase, fetches structure from MPDS,
runs SCF convergence, then DOS + Seebeck at T=298K.

Usage:
    python launch_seebeck_from_csv.py              # all phases
    python launch_seebeck_from_csv.py CaZrO3/221   # single phase
"""

import os
import sys
import time

import polars as pl
from mpds_client import MPDSDataRetrieval

from aiida import load_profile
from aiida.orm import Dict, Str, StructureData, Code
from aiida.engine import submit

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

load_profile()

MPDS_KEY = "KEY_HERE"
os.environ["MPDS_KEY"] = MPDS_KEY
CSV_PATH = "ab_initio_seebeck_data.csv"
TEMPERATURE = 298.0


def fetch_structure_from_mpds(formula, sg, max_retries=3):
    client = MPDSDataRetrieval(api_key=MPDS_KEY)
    for attempt in range(max_retries):
        try:
            answer = client.get_data(
                {"formulae": formula, "sgs": sg, "props": "atomic structure"},
                fields={"S": ["cell_abc", "sg_n", "basis_noneq", "els_noneq"]},
            )
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    if not answer:
        raise ValueError(f"No structure found for {formula}/{sg}")

    structs = [client.compile_crystal(line, flavor="ase") for line in answer]
    structs = list(filter(None, structs))
    if not structs:
        raise ValueError(f"No valid structures for {formula}/{sg}")

    import numpy as np
    minimal_struct = min(len(s) for s in structs)
    candidates = [s for s in structs if len(s) == minimal_struct]
    cells = np.array([s.get_cell().reshape(9) for s in candidates])
    median_cell = np.median(cells, axis=0)
    median_idx = int(np.argmin(np.linalg.norm(cells - median_cell, axis=1)))
    ase_struct = candidates[median_idx]

    return StructureData(ase=ase_struct)


fleur_code = Code.get_from_string("fleur")
inpgen_code = Code.get_from_string("inpgen")

df = pl.read_csv(CSV_PATH)
phases = [(row["formula"], int(row["sg"])) for row in df.iter_rows(named=True)]

if len(sys.argv) > 1:
    arg = sys.argv[1].split("/")
    phases = [(arg[0], int(arg[1]))]

results = []

for formula, sg in phases:
    print(f"\n{'='*60}")
    print(f"Processing {formula}/{sg}")

    try:
        structure = fetch_structure_from_mpds(formula, sg)
        structure.store()
        print(f"  Structure stored: PK={structure.pk}")
    except Exception as e:
        print(f"  [ERROR] Failed to fetch structure for {formula}/{sg}: {e}")
        results.append((formula, sg, "-", "-", "errored_structure"))
        continue

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
        "phase": Str(f"{formula}/{sg}"),
    }

    try:
        workchain = submit(FleurDOSLocalWorkChain, **inputs)
        print(f"  [OK] Submitted FleurDOSLocalWorkChain PK={workchain.pk} T={TEMPERATURE}K")
        results.append((formula, sg, structure.pk, workchain.pk, "submitted"))
    except Exception as e:
        print(f"  [ERROR] Submission failed: {e}")
        results.append((formula, sg, structure.pk, "-", "errored_submit"))

print(f"\n{'='*60}")
print(f"{'Formula':<12} {'SG':<6} {'Struct PK':<12} {'WC PK':<12} {'Status':<15}")
print("-" * 60)
for r in results:
    print(f"{r[0]:<12} {r[1]:<6} {r[2]:<12} {r[3]:<12} {r[4]:<15}")

submitted = sum(1 for r in results if r[4] == "submitted")
errored = sum(1 for r in results if r[4].startswith("errored"))
print(f"\nTotal: {len(results)} | Submitted: {submitted} | Errored: {errored}")