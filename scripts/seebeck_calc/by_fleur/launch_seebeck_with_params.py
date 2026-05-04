#!/usr/bin/env python3
"""
Launch FleurDOSLocalWorkChain for Seebeck coefficient calculation
using temperature and chemical potential values from csv file.

Each row in the CSV specifies a chemical formula and its target temperature (K)
and chemical potential mu (eV) for the Seebeck calculation. These override
the defaults in DEFAULT_SEEBECK (T=5K, fermi_energy_ev=0.0).
"""

import uuid

import pandas as pd

from aiida import load_profile
from aiida.orm import Dict, Str, load_code, load_node
from aiida.engine import submit
from aiida.common.exceptions import NotExistent

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

SEEBECK_CSV = "seebeck_02_03_2026.csv"
SUMMARY_CSV = "/data/summary_2026_04_29_10_34_45.csv"


def extract_uuid(output_path):
    parts = output_path.strip("/").split("/")
    uuid_body = parts[-2]
    hex2 = parts[-3]
    hex1 = parts[-4]
    uuid_str = f"{hex1}{hex2}{uuid_body}"
    uuid.UUID(uuid_str)
    return uuid_str


def resolve_remote(uuid_str):
    calcjob = load_node(uuid_str)
    remote = calcjob.base.links.get_outgoing().get_node_by_label("remote_folder")
    return remote


load_profile()

fleur_code = load_code("fleur")

# Load Seebeck parameters CSV (temperature and mu per formula)
seebeck_df = pd.read_csv(SEEBECK_CSV, dtype={"chemical_formula": str}, keep_default_na=False)
seebeck_params = {}
for _, row in seebeck_df.iterrows():
    seebeck_params[row["chemical_formula"]] = {
        "temperature": float(row["temperature"]),
        "fermi_energy_ev": float(row["mu"]),
    }

# Load FLEUR summary CSV and pick last iteration per formula
summary_df = pd.read_csv(SUMMARY_CSV, dtype={"chemical_formula": str}, keep_default_na=False)
fleur_df = summary_df[summary_df["engine"] == "fleur"].copy()
fleur_df = fleur_df[fleur_df["chemical_formula"].str.strip() != ""]
last_per_formula = fleur_df.loc[fleur_df.groupby("chemical_formula")["rmsd_disp"].idxmin()]

# Only submit for formulas that have Seebeck parameters
formulas_with_params = set(seebeck_params.keys())
results = []

for _, row in last_per_formula.iterrows():
    formula = row["chemical_formula"]
    output_path = row["output_path"]

    if formula not in formulas_with_params:
        print(f"[SKIP] {formula}: no Seebeck parameters in CSV")
        results.append((formula, "-", "-", "-", "skipped_no_params"))
        continue

    try:
        uuid_str = extract_uuid(output_path)
    except (ValueError, IndexError) as e:
        print(f"[SKIP] {formula}: UUID extraction failed: {e}")
        results.append((formula, "-", "-", "-", "skipped"))
        continue

    try:
        remote = resolve_remote(uuid_str)
    except (NotExistent, RuntimeError) as e:
        print(f"[ERROR] {formula}: {e}")
        results.append((formula, uuid_str, "-", "-", "errored"))
        continue

    wf_para_dos = Dict(
        dict={
            "kpoints_mesh_dos": [6, 6, 6],
            "sigma": 0.002,
            "emin": -2.0,
            "emax": 2.0,
        }
    )

    # Override DEFAULT_SEEBECK with temperature and mu from CSV
    seebeck_dict = DEFAULT_SEEBECK.copy()
    seebeck_dict.update(seebeck_params[formula])
    seebeck_params_node = Dict(dict=seebeck_dict)

    inputs = {
        "fleur": fleur_code,
        "remote": remote,
        "wf_parameters": wf_para_dos,
        "seebeck_parameters": seebeck_params_node,
        "phase": Str(formula),
    }

    workchain = submit(FleurDOSLocalWorkChain, **inputs)
    print(f"[OK] {formula}: submitted FleurDOSLocalWorkChain PK={workchain.pk} T={seebeck_params[formula]['temperature']}K mu={seebeck_params[formula]['fermi_energy_ev']}eV")
    results.append((formula, uuid_str, remote.pk, workchain.pk, "submitted"))

print("\n{:<10} {:<38} {:<12} {:<12} {:<10}".format(
    "Formula", "UUID", "Remote PK", "WC PK", "Status"
))
print("-" * 82)
for r in results:
    print("{:<10} {:<38} {:<12} {:<12} {:<10}".format(*r))

submitted = sum(1 for r in results if r[4] == "submitted")
errored = sum(1 for r in results if r[4] == "errored")
skipped = sum(1 for r in results if r[4].startswith("skipped"))
print(f"\nTotal: {len(results)} | Submitted: {submitted} | Errored: {errored} | Skipped: {skipped}")