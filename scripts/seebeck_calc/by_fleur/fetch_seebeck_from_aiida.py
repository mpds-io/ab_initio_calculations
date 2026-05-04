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

load_profile()

# query all FleurDOSLocalWorkChain instances (including failed ones)
qb = QueryBuilder()
qb.append(WorkChainNode, filters={'process_type': {'like': '%FleurDOSLocalWorkChain%'}})

# collect results from successfully completed workchains only.
# workchain is considered successful if it has the 'output_seebeck' output node,
# which is only attached when the Seebeck calculation completed without errors.
results = []
for (wc,) in qb.iterall():
    # workchain label convention: "Formula : Seebeck coefficient calculation from DOS (Fleur)"
    label = wc.label or ''
    phase = label.split(':')[0].strip() if ':' in label else label

    try:
        # output_seebeck: Dict with Seebeck coefficient and chemical potential
        seebeck = wc.outputs.output_seebeck.get_dict()
        # output_dos_local_wc_para: Dict with temperature, carrier type, doping
        dos_local = wc.outputs.output_dos_local_wc_para.get_dict()
    except Exception:
        # skip workchains that didn't produce output (failed or still running)
        continue

    results.append({
        "chemical_formula": phase,
        "workchain_pk": wc.pk,
        # seebeck coefficient (mV/K)
        "seebeck_coefficient_uvk": seebeck.get("seebeck_coefficient_uvk"),
        # chemical potential relative to Fermi level (eV)
        "mu_ev": seebeck.get("mu_ev"),
        # Integrated DOS at 0K (number of electrons below Fermi level)
        "N": seebeck.get("N"),
        # Temperature used in the Seebeck calculation (K)
        "temperature_k": dos_local.get("temperature_k"),
        # Carrier type: "hole" (p-type) or "electron" (n-type)
        "carrier_type": dos_local.get("carrier_type"),
        # Doping concentration (carriers per cm^3)
        "doping_cm3": dos_local.get("doping_cm3"),
    })

# save results to CSV
CSV_COLUMNS = [
    "chemical_formula", "workchain_pk", "seebeck_coefficient_uvk",
    "mu_ev", "N", "temperature_k", "carrier_type", "doping_cm3",
]
csv_path = os.path.join(os.path.dirname(__file__), "seebeck_fleur_results.csv")
with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for r in sorted(results, key=lambda x: x["chemical_formula"]):
        writer.writerow(r)
print(f"Saved {len(results)} rows to {csv_path}")

# print results as a formatted table
print(f"{'Formula':<12} {'WC PK':>8} {'S (muV/K)':>12} {'mu (eV)':>10} {'N':>10} {'T (K)':>6} {'carrier':>8} {'doping_cm3':>12}")
print("-" * 95)
for r in sorted(results, key=lambda x: x["chemical_formula"]):
    s = f"{r['seebeck_coefficient_uvk']:.4f}" if r['seebeck_coefficient_uvk'] is not None else "N/A"
    mu = f"{r['mu_ev']:.4f}" if r['mu_ev'] is not None else "N/A"
    n = f"{r['N']:.4f}" if r['N'] is not None else "N/A"
    t = f"{r['temperature_k']:.1f}" if r['temperature_k'] is not None else "N/A"
    ct = r['carrier_type'] or ''
    dp = f"{r['doping_cm3']:.1e}" if r['doping_cm3'] is not None else "N/A"
    print(f"{r['chemical_formula']:<12} {r['workchain_pk']:>8} {s:>12} {mu:>10} {n:>10} {t:>6} {ct:>8} {dp:>12}")
print(f"\nTotal: {len(results)}")