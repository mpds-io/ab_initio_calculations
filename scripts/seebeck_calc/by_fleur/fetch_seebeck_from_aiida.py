#!/usr/bin/env python3
"""
Fetch Seebeck coefficient results from AiiDA database.

This script queries the AiiDA database for completed FleurDOSLocalWorkChain instances
and retrieves the calculated Seebeck coefficients along with relevant parameters.

Data sources (all stored as AiiDA Dict nodes inside each workchain):
  - output_seebeck: Seebeck coefficient (uV/K), chemical potential (eV), electron count N
  - output_dos_local_wc_para: calculation parameters (temperature, carrier type, doping)

Only workchains that finished successfully (i.e. have output_seebeck) are included.
Failed or in-progress workchains are silently skipped.
"""

import csv
import os

from aiida import load_profile
from aiida.orm import QueryBuilder, WorkChainNode

FILTER_KPOINTS_MESH = [54, 54, 54]  # e.g. [54, 54, 54] to filter, None to return all

load_profile()

qb = QueryBuilder()
qb.append(WorkChainNode, filters={'process_type': {'like': '%FleurDOSLocalWorkChain%'}})

results = []
skipped_kmesh = 0
for (wc,) in qb.iterall():
    label = wc.label or ''
    phase = label.split(':')[0].strip() if ':' in label else label

    try:
        seebeck = wc.outputs.output_seebeck.get_dict()
        dos_local = wc.outputs.output_dos_local_wc_para.get_dict()
    except Exception:
        continue

    kpoints_mesh_dos = dos_local.get("kpoints_mesh_dos", [])

    if FILTER_KPOINTS_MESH is not None and kpoints_mesh_dos != FILTER_KPOINTS_MESH:
        skipped_kmesh += 1
        continue

    calc_date = wc.ctime.strftime("%Y-%m-%d %H:%M:%S")

    results.append({
        "chemical_formula": phase,
        "workchain_pk": wc.pk,
        "calc_date": calc_date,
        "seebeck_coefficient_uvk": seebeck.get("seebeck_coefficient_uvk"),
        "mu_ev": seebeck.get("mu_ev"),
        "N": seebeck.get("N"),
        "temperature_k": dos_local.get("temperature_k"),
        "carrier_type": dos_local.get("carrier_type"),
        "doping_cm3": dos_local.get("doping_cm3"),
        "kpoints_mesh_dos": kpoints_mesh_dos if kpoints_mesh_dos else None,
    })

if FILTER_KPOINTS_MESH is not None:
    print(f"Filter: k-mesh = {FILTER_KPOINTS_MESH} | Matched: {len(results)} | Skipped: {skipped_kmesh}")

CSV_COLUMNS = [
    "chemical_formula", "workchain_pk", "calc_date", "seebeck_coefficient_uvk",
    "mu_ev", "N", "temperature_k", "carrier_type", "doping_cm3",
    "kpoints_mesh_dos",
]
csv_path = os.path.join(os.path.dirname(__file__), "seebeck_fleur_results.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in sorted(results, key=lambda x: x["chemical_formula"]):
        writer.writerow(r)
print(f"Saved {len(results)} rows to {csv_path}")

print(f"{'Formula':<12} {'WC PK':>8} {'Date':>19} {'S (muV/K)':>12} {'mu (eV)':>10} {'N':>10} {'T (K)':>6} {'carrier':>8} {'doping_cm3':>12} {'k-mesh':>12}")
print("-" * 128)
for r in sorted(results, key=lambda x: x["chemical_formula"]):
    s = f"{r['seebeck_coefficient_uvk']:.4f}" if r['seebeck_coefficient_uvk'] is not None else "N/A"
    mu = f"{r['mu_ev']:.4f}" if r['mu_ev'] is not None else "N/A"
    n = f"{r['N']:.4f}" if r['N'] is not None else "N/A"
    t = f"{r['temperature_k']:.1f}" if r['temperature_k'] is not None else "N/A"
    ct = r['carrier_type'] or ''
    dp = f"{r['doping_cm3']:.1e}" if r['doping_cm3'] is not None else "N/A"
    km = str(r['kpoints_mesh_dos']) if r['kpoints_mesh_dos'] else "N/A"
    dt = r['calc_date'] or 'N/A'
    print(f"{r['chemical_formula']:<12} {r['workchain_pk']:>8} {dt:>19} {s:>12} {mu:>10} {n:>10} {t:>6} {ct:>8} {dp:>12} {km:>12}")
print(f"\nTotal: {len(results)}")