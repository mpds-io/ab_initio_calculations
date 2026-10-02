#!/usr/bin/env python3
"""
Save all SCF and forces output files from a completed AiiDA
PhonopyFleurWorkChain locally, in the same disp_NNN/ layout as the manual
pipeline (see e.g. data/manual_fleur_phonopy/runs/ZnO_7282_fleur62_fixed/),
then integrate the resulting frequencies into thermodynamic properties via
the existing integrate_phonons.py -- one command, give it a PK and an
output directory, done.

Per displacement, saves:
    inp_scf.xml, out_scf.xml       -- SCF calculation input/output
    inp_forces.xml, out_forces.xml -- forces calculation input/output
    FORCES                          -- parsed forces, same text format as
                                        run_fleur_scf.py's write_forces_file
At the top level, saves:
    phonon_frequencies.txt          -- mesh frequencies (via
                                        extract_aiida_frequencies.py's logic)
    run_manifest.json               -- per-displacement AiiDA PKs + status
    thermo_report.md                -- integrate_phonons.py's report on
                                        phonon_frequencies.txt

Usage:
    verdi -p presto_pg run scripts/phonon/by_aiida/save_aiida_outputs.py \
        --pk 93126 --output-dir data/manual_fleur_phonopy/runs/ZnO_186_aiida_93126
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Not derived from __file__: "verdi run" executes this script's source via
# exec() with a cwd that doesn't match where it was invoked from, so
# Path(__file__).resolve() silently resolves to the wrong directory (e.g.
# /root instead of the repo root) instead of raising.
REPO_ROOT = Path("/root/projects/ab_initio_calculations")
HTR_PER_BOHR_TO_EV_PER_ANG = 27.211386245988 / 0.529177210903


def write_forces_file(path: Path, forces):
    with open(path, "w") as fh:
        for fx, fy, fz in forces:
            fh.write(
                f"   {fx * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}   "
                f"{fy * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}   "
                f"{fz * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}\n"
            )
            fh.write("      force\n")


def save_calc_files(calc_node, outdir: Path, prefix: str):
    """Save inp.xml/out.xml (and out.error/usage.json if present) from a
    FleurCalculation's retrieved folder as <prefix>*.xml etc."""
    retrieved = calc_node.outputs.retrieved
    names = retrieved.list_object_names()
    mapping = {
        "inp.xml": f"inp_{prefix}.xml",
        "out.xml": f"out_{prefix}.xml",
        "out.error": f"out_{prefix}.error",
        "usage.json": f"usage_{prefix}.json",
    }
    saved = []
    for src, dst in mapping.items():
        if src in names:
            with retrieved.open(src, "rb") as fh:
                content = fh.read()
            (outdir / dst).write_bytes(content)
            saved.append(dst)
    return saved


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pk", type=int, required=True, help="PhonopyFleurWorkChain PK")
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--mesh", type=int, nargs=3, default=[8, 8, 8])
    ap.add_argument("--t-max", type=int, default=1000, help="passed to integrate_phonons.py")
    ap.add_argument("--t-step", type=int, default=25, help="passed to integrate_phonons.py")
    args = ap.parse_args()

    from aiida.orm import load_node

    wc = load_node(args.pk)
    if not wc.is_finished_ok:
        raise SystemExit(
            f"error: PK {args.pk} is not finished_ok (exit_status={wc.exit_status})"
        )

    run_dir = args.output_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    forces_wcs = sorted(
        (n for n in wc.called if n.process_label == "FleurForcesWorkChain"),
        key=lambda n: n.pk,
    )

    manifest = {
        "source": "aiida",
        "workchain_pk": args.pk,
        "workchain_uuid": wc.uuid,
        "label": wc.label,
        "structure_formula": wc.inputs.structure.get_formula(),
        "supercell_matrix": wc.inputs.supercell_matrix.get_list(),
        "n_displacements": len(forces_wcs),
        "displacements": [],
    }

    for i, fwc in enumerate(forces_wcs, start=1):
        disp_dir = run_dir / f"disp_{i:03d}"
        disp_dir.mkdir(exist_ok=True)

        entry = {
            "i": i,
            "forces_workchain_pk": fwc.pk,
            "converged": fwc.is_finished_ok,
            "exit_status": fwc.exit_status,
        }

        scf_wcs = [c for c in fwc.called if c.process_label == "FleurScfWorkChain"]
        if scf_wcs:
            scf_wc = sorted(scf_wcs, key=lambda n: n.pk)[-1]
            entry["scf_workchain_pk"] = scf_wc.pk
            entry["scf_converged"] = scf_wc.is_finished_ok
            # scf_wc.outputs.last_calc is a summary Dict, not the actual
            # calc node -- find the real FleurCalculation (the latest one,
            # in case of internal SCF restarts) among the called children.
            scf_calc = None
            for c in scf_wc.called:
                if c.process_label == "FleurBaseWorkChain":
                    for gc in c.called:
                        if gc.process_label == "FleurCalculation":
                            if scf_calc is None or gc.pk > scf_calc.pk:
                                scf_calc = gc
            if scf_calc is not None:
                saved = save_calc_files(scf_calc, disp_dir, "scf")
                entry["scf_files"] = saved
                entry["scf_calc_pk"] = scf_calc.pk

        # The forces calc is a direct FleurBaseWorkChain child of fwc (the
        # SCF's own FleurBaseWorkChain(s) are nested inside scf_wc, one
        # level deeper, so this loop over fwc.called only sees the forces one).
        forces_base_wc = None
        for c in fwc.called:
            if c.process_label == "FleurBaseWorkChain":
                forces_base_wc = c
        if forces_base_wc is not None:
            last_calc = None
            for c in forces_base_wc.called:
                if c.process_label == "FleurCalculation":
                    last_calc = c
            if last_calc is not None:
                saved = save_calc_files(last_calc, disp_dir, "forces")
                entry["forces_files"] = saved
                entry["forces_calc_pk"] = last_calc.pk

        if "forces" in fwc.outputs:
            forces_dict = fwc.outputs.forces.get_dict()
            key = f"forces_{i}"
            if key in forces_dict:
                write_forces_file(disp_dir / "FORCES", forces_dict[key])
                entry["forces_lines"] = len(forces_dict[key])

        manifest["displacements"].append(entry)
        print(f"disp {i}/{len(forces_wcs)}: saved to {disp_dir}")

    (run_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"wrote {run_dir / 'run_manifest.json'}")

    # Reuse extract_aiida_frequencies.py's logic for phonon_frequencies.txt.
    # It needs a loaded AiiDA profile, hence "verdi run" rather than plain
    # python3, even though this script is already running under verdi.
    freqs_path = run_dir / "phonon_frequencies.txt"
    subprocess.run(
        [
            "verdi",
            "-p",
            "presto_pg",
            "run",
            str(REPO_ROOT / "scripts/phonon/by_aiida/extract_aiida_frequencies.py"),
            "--pk",
            str(args.pk),
            "--mesh",
            *[str(m) for m in args.mesh],
            "--output",
            str(freqs_path),
        ],
        check=True,
    )

    # Integrate into thermodynamic properties via the existing script --
    # plain python3 here, integrate_phonons.py doesn't touch AiiDA.
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/phonon/integrate_phonons.py"),
            "--fleur",
            str(freqs_path),
            "--t-max",
            str(args.t_max),
            "--t-step",
            str(args.t_step),
            "--output",
            str(run_dir / "thermo_report.md"),
        ],
        check=True,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )


if __name__ == "__main__":
    main()
