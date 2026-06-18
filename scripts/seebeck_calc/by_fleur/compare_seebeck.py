#!/usr/bin/env python3
"""
Compare Seebeck coefficients from MPDS, CRYSTAL, and FLEUR calculations.

Reads:
  - seebeck_02_03_2026.csv (seebeck_mpds, seebeck_avg -> seebeck_crystal)
  - seebeck_fleur_results.csv (seebeck_coefficient_uvk -> seebeck_fleur)

Joins on: chemical_formula, temperature
Mu is matched with tolerance (MU_TOLERANCE_EV).
"""

import os

import polars as pl

MU_TOLERANCE_EV = 0.1

MPDS_CSV = "seebeck_02_03_2026.csv"
FLEUR_CSV = os.path.join(os.path.dirname(__file__), "seebeck_fleur_results.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "seebeck_comparison.csv")

df_mpds = (
    pl.read_csv(MPDS_CSV, schema_overrides={"chemical_formula": pl.Utf8}, null_values=[])
    .select("chemical_formula", "temperature", "mu", "seebeck_mpds", "seebeck_avg")
    .rename({"seebeck_avg": "seebeck_crystal"})
)

df_fleur = (
    pl.read_csv(FLEUR_CSV, dtypes={"chemical_formula": pl.Utf8, "kpoints_mesh_dos": pl.Utf8}, null_values=[])
    .select("chemical_formula", "temperature_k", "mu_ev", "seebeck_coefficient_uvk")
    .rename({
        "temperature_k": "temperature",
        "mu_ev": "mu_fleur",
        "seebeck_coefficient_uvk": "seebeck_fleur",
    })
)

joined = df_mpds.join(df_fleur, on=["chemical_formula", "temperature"], how="inner")

matched = (
    joined.filter((pl.col("mu") - pl.col("mu_fleur")).abs() <= MU_TOLERANCE_EV)
    .with_columns(mu=pl.col("mu"))
    .with_columns(
        pl.col("temperature").round(2),
        pl.col("mu").round(2),
        pl.col("seebeck_mpds").round(2),
        pl.col("seebeck_crystal").round(2),
        pl.col("seebeck_fleur").round(2),
    )
    .select("chemical_formula", "temperature", "mu", "seebeck_mpds", "seebeck_crystal", "seebeck_fleur")
    .sort("chemical_formula", "temperature")
)

matched.write_csv(OUTPUT_CSV)
print(matched)
total = joined.height
matched_count = matched.height
print(f"\nMatched: {matched_count}/{total} (mu tolerance = {MU_TOLERANCE_EV} eV)")
print(f"Saved to {OUTPUT_CSV}")