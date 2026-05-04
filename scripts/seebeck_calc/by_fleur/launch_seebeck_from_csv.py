#!/usr/bin/env python3

import uuid

import pandas as pd

from aiida import load_profile
from aiida.orm import Dict, Str, load_code, load_node
from aiida.engine import submit
from aiida.common.exceptions import NotExistent

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

CSV_PATH = "/data/summary_2026_04_29_10_34_45.csv"


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

df = pd.read_csv(CSV_PATH, dtype={"chemical_formula": str}, keep_default_na=False)
fleur_df = df[df["engine"] == "fleur"].copy()
fleur_df = fleur_df[fleur_df["chemical_formula"].str.strip() != ""]
last_per_formula = fleur_df.loc[fleur_df.groupby("chemical_formula")["rmsd_disp"].idxmin()]
results = []

for _, row in last_per_formula.iterrows():
    formula = row["chemical_formula"]
    output_path = row["output_path"]

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
            "kpoints_mesh_dos": [54, 54, 54],
            "sigma": 0.002,
            "emin": -2.0,
            "emax": 2.0,
        }
    )
    seebeck_params = Dict(dict=DEFAULT_SEEBECK)

    inputs = {
        "fleur": fleur_code,
        "remote": remote,
        "wf_parameters": wf_para_dos,
        "seebeck_parameters": seebeck_params,
        "phase": Str(formula),
    }

    workchain = submit(FleurDOSLocalWorkChain, **inputs)
    print(f"[OK] {formula}: submitted FleurDOSLocalWorkChain PK={workchain.pk}")
    results.append((formula, uuid_str, remote.pk, workchain.pk, "submitted"))

print("\n{:<10} {:<38} {:<12} {:<12} {:<10}".format(
    "Formula", "UUID", "Remote PK", "WC PK", "Status"
))
print("-" * 82)
for r in results:
    print("{:<10} {:<38} {:<12} {:<12} {:<10}".format(*r))

submitted = sum(1 for r in results if r[4] == "submitted")
errored = sum(1 for r in results if r[4] == "errored")
skipped = sum(1 for r in results if r[4] == "skipped")
print(f"\nTotal: {len(results)} | Submitted: {submitted} | Errored: {errored} | Skipped: {skipped}")