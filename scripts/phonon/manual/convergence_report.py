"""
Aggregate run_manifest.json files from one or more run_phonopy_manual.py
runs into a single markdown report comparing FLEUR SCF convergence and
phonon quality across presets and FLEUR versions.

Usage:

    python3 scripts/phonon/manual/convergence_report.py \\
        --runs-glob 'data/manual_fleur_phonopy/runs/*/run_manifest.json' \\
        --output manual_fleur_phonon_report.md
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

THZ_TO_CM1 = 33.3564095198152


def load_manifests(pattern: str) -> list[dict]:
    paths = sorted(glob.glob(pattern))
    out = []
    for p in paths:
        try:
            with open(p) as f:
                out.append(json.load(f))
        except Exception as e:
            print(f"[convergence_report] skip {p}: {e}", file=sys.stderr)
    return out


def fmt(x, default="-"):
    if x is None:
        return default
    if isinstance(x, float):
        return f"{x:.4g}"
    return str(x)


def render(manifests: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# Manual FLEUR + phonopy convergence report\n")
    lines.append(
        "Comparison of SCF convergence and phonon quality across parameter "
        "presets (baseline / tuningA / tuningB / tuningC) and FLEUR versions.\n"
    )

    lines.append("## Summary table\n")
    lines.append(
        "| Run | Preset | Supercell atoms | Disps | Converged (n/N) | "
        "Avg iters | Last dist | Energy diff (Htr) | Forces ok | "
        "Imag modes (mesh) | Min freq (cm^-1) | Elapsed (s) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in manifests:
        label = m.get("label", "?")
        preset = m.get("preset", "?")
        nat = m.get("n_supercell_atoms", "?")
        ndisp = m.get("n_displacements", "?")
        scfs = m.get("scf_results", [])
        n_conv = sum(1 for s in scfs if s.get("converged"))
        n_force = sum(1 for s in scfs if s.get("forces_present"))
        iters = [s.get("total_iterations", 0) for s in scfs if "total_iterations" in s]
        avg_iter = sum(iters) / len(iters) if iters else 0
        dists = [
            s.get("last_charge_distance")
            for s in scfs
            if s.get("last_charge_distance") is not None
        ]
        last_dist = dists[-1] if dists else None
        ediffs = [
            s.get("energy_diff_htr")
            for s in scfs
            if s.get("energy_diff_htr") is not None
        ]
        last_ediff = ediffs[-1] if ediffs else None
        pa = m.get("phonon_analysis", {})
        imag = pa.get("mesh_n_imaginary", "-")
        minf = pa.get("mesh_min_freq_cm1")
        if minf is None and pa.get("mesh_min_freq_THz") is not None:
            # older manifests reported THz
            minf = pa["mesh_min_freq_THz"] * THZ_TO_CM1
        elapsed = m.get("elapsed_sec", 0)
        lines.append(
            f"| {label} | {preset} | {nat} | {ndisp} | "
            f"{n_conv}/{len(scfs)} | {avg_iter:.1f} | {fmt(last_dist)} | "
            f"{fmt(last_ediff)} | {n_force}/{len(scfs)} | {imag} | "
            f"{fmt(minf)} | {elapsed:.0f} |"
        )

    lines.append("\n## Per-displacement detail\n")
    for m in manifests:
        label = m.get("label", "?")
        preset = m.get("preset", "?")
        lines.append(f"### {label} — {preset}\n")
        scfs = m.get("scf_results", [])
        if not scfs:
            lines.append("(no SCF results)\n")
            continue
        lines.append(
            "| Disp | Converged | Runs | Iters | Last dist | Energy (Htr) | "
            "Energy diff (Htr) | Forces | Forces lines | Error |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|")
        for s in scfs:
            i = s.get("i", "?")
            conv = s.get("converged", "-")
            nruns = s.get("n_runs", "-")
            it = s.get("total_iterations", "-")
            d = s.get("last_charge_distance")
            te = s.get("total_energy_htr")
            ed = s.get("energy_diff_htr")
            fp = s.get("forces_present", "-")
            fl = s.get("forces_lines", "-")
            err = s.get("error", "") or ("" if not s.get("reused") else "reused")
            lines.append(
                f"| {i} | {conv} | {nruns} | {it} | {fmt(d)} | {fmt(te)} | "
                f"{fmt(ed)} | {fp} | {fl} | {err} |"
            )
        lines.append("")

        pa = m.get("phonon_analysis", {})
        if pa:
            lines.append("**Phonon analysis:**\n")
            lines.append("```json")
            lines.append(json.dumps(pa, indent=2))
            lines.append("```\n")

    lines.append("## Preset definitions\n")
    lines.append(
        "- **baseline**: inpgen defaults (Anderson/BFGS mixing, auto k-mesh "
        "6x6x6), itmax_per_run=60, fleur_runmax=4, mode=energy.\n"
        "- **tuningA**: straight mixing (imix=straight, alpha=0.05), kmax=3.0, "
        "k-mesh 4x4x4, itmax_per_run=300, fleur_runmax=10, "
        "density_converged=1e-4, energy_converged=0.01. (mpds-aiida "
        "updating_fleur_parameters branch.)\n"
        "- **tuningB**: baseline parameters, but on SCF non-convergence restart "
        "from the produced charge density with the k-point mesh halved in "
        "each direction. (absolidix-backend PR #63 FlerSCFRestart rule.)\n"
        "- **tuningC**: tuningA from the start plus the halving restart on top.\n"
    )
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-glob", required=True)
    ap.add_argument("--output", default=None)
    args = ap.parse_args()

    manifests = load_manifests(args.runs_glob)
    if not manifests:
        print("[convergence_report] no manifests found", file=sys.stderr)
        sys.exit(1)
    report = render(manifests)
    if args.output:
        Path(args.output).write_text(report)
        print(f"[convergence_report] report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
