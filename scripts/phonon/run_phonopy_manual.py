#!/usr/bin/env python3
"""
Orchestrate a complete manual FLEUR + phonopy phonon calculation for one
system, reproducing what PhonopyFleurWorkChain was supposed to do but
outside AiiDA so we can test convergence parameter presets directly.

Pipeline:
  1. phonopy generates the supercell and displaced supercells from the
     pristine unit cell (POSCAR) and the supercell matrix.
  2. For each displaced supercell: convert to ASE atoms, run inpgen + fleur_MPI
     with the chosen preset (scripts.phonon.run_fleur_scf.run_scf), extract
     forces into a FORCES file.
  3. Collect the FORCES files, feed them to phonopy to build force constants.
  4. Compute the band structure / mesh and report the number of imaginary
     modes and the most-negative frequency.

The pristine supercell SCF is also run once (its forces are subtracted as the
drift by phonopy automatically, but we write a zero-force FORCES for it if the
phonopy interface expects it; here we rely on phonopy.parse_set_of_forces
which only needs the displaced supercell force files).

Usage:

    python3 scripts/phonon/run_phonopy_manual.py \\
        --poscar data/manual_fleur_phonopy/structures/BiSe_164.poscar \\
        --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \\
        --preset tuningA \\
        --inpgen /root/fleur/build/inpgen \\
        --fleur  /root/fleur/build/fleur_MPI \\
        --mpi-procs 2 \\
        --outdir data/manual_fleur_phonopy/runs/BiSe_164_tuningA_fleur62 \\
        --label BiSe_164

A run_manifest.json is written to --outdir summarising every SCF result and
the final phonon analysis.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

# Make run_fleur_scf importable whether run from repo root or scripts/phonon
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_fleur_scf import run_scf, write_forces_file_from_out_xml, PRESETS  # noqa: E402


def _poscar_to_phonopy_atoms(poscar: str):
    from phonopy.structure.atoms import PhonopyAtoms
    from ase.io import read as ase_read

    atoms = ase_read(poscar)
    return PhonopyAtoms(
        symbols=atoms.get_chemical_symbols(),
        cell=atoms.get_cell().array,
        scaled_positions=atoms.get_scaled_positions(),
    )


def _phonopy_supercell_to_ase(supercell) -> "ase.Atoms":  # noqa: F821
    from ase import Atoms

    return Atoms(
        symbols=supercell.symbols,
        positions=supercell.positions,
        cell=supercell.cell,
        pbc=True,
    )


def build_phonopy(unitcell, supercell_matrix) -> "Phonopy":
    from phonopy import Phonopy

    ph = Phonopy(unitcell, supercell_matrix=supercell_matrix)
    ph.generate_displacements()
    return ph


def collect_force_sets(ph, forces_files: list[Path]) -> np.ndarray | None:
    """Feed the per-displacement FORCES files into phonopy and produce the
    force constants."""
    from phonopy.interface.fleur import parse_set_of_forces

    n_atoms = len(ph.supercell)
    force_sets = parse_set_of_forces(n_atoms, [str(f) for f in forces_files])
    if len(force_sets) != len(ph.displacements):
        print(
            f"[run_phonopy_manual] force set count {len(force_sets)} != "
            f"displacement count {len(ph.displacements)}",
            file=sys.stderr,
        )
        return None
    ph.forces = np.array(force_sets)
    ph.produce_force_constants()
    return np.array(force_sets)


def analyse_phonons(ph, n_qpoints_band: int = 51) -> dict[str, Any]:
    """Run a mesh calculation and report imaginary modes. Returns a dict with
    mesh frequencies and, if seekpath is available, a band structure."""
    result: dict[str, Any] = {}

    # Mesh statistics — this is what we need for imaginary-mode detection.
    try:
        ph.run_mesh([8, 8, 8])
        mesh = ph.get_mesh_dict()
        mesh_freqs = np.array(mesh["frequencies"])
        all_mesh = np.ravel(mesh_freqs)
        result["mesh_n_qpoints"] = int(all_mesh.size // 3) if all_mesh.size else 0
        result["mesh_n_imaginary"] = (
            int(np.sum(all_mesh < -0.05)) if all_mesh.size else 0
        )
        result["mesh_min_freq_THz"] = float(np.min(all_mesh)) if all_mesh.size else None
        result["mesh_max_freq_THz"] = float(np.max(all_mesh)) if all_mesh.size else None
    except Exception as e:
        result["mesh_error"] = f"mesh analysis failed: {e}"

    # Band structure (optional, needs seekpath)
    try:
        import seekpath

        paths = seekpath.get_path(ph.primitive.cell)
        pts = []
        labels = []
        for seg in paths["path"]:
            for name in seg:
                coord = paths["point_coords"][name]
                if (
                    not pts
                    or np.linalg.norm(np.array(coord) - np.array(pts[-1])) > 1e-9
                ):
                    pts.append(coord)
                    labels.append(name)
        ph.run_band_structure([pts], with_eigenvectors=False)
        band_freqs = ph.get_band_structure_dict()["frequencies"]
        all_band = (
            np.concatenate([np.ravel(f) for f in band_freqs])
            if band_freqs
            else np.array([])
        )
        if all_band.size:
            result["band_n_imaginary"] = int(np.sum(all_band < -0.05))
            result["band_min_freq_THz"] = float(np.min(all_band))
        result["band_labels"] = labels
    except Exception as e:
        result["band_error"] = f"band analysis failed (non-fatal): {e}"

    return result


def run_phonopy_manual(
    poscar: str,
    supercell_matrix,
    preset: str,
    inpgen_bin: str,
    fleur_bin: str,
    outdir: str,
    label: str = "system",
    mpi_procs: int = 1,
    with_mpi: bool = True,
    displacement_distance: float = 0.01,
    skip_existing: bool = True,
) -> dict[str, Any]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    unitcell = _poscar_to_phonopy_atoms(poscar)
    ph = build_phonopy(unitcell, np.array(supercell_matrix))
    n_disp = len(ph.displacements)
    supercells = ph.supercells_with_displacements
    print(
        f"[run_phonopy_manual] {label}: {len(ph.supercell)} atoms in supercell, "
        f"{n_disp} displacements, preset={preset}"
    )

    manifest: dict[str, Any] = {
        "label": label,
        "poscar": str(poscar),
        "supercell_matrix": [[int(x) for x in r] for r in np.array(supercell_matrix)],
        "preset": preset,
        "inpgen_bin": inpgen_bin,
        "fleur_bin": fleur_bin,
        "n_supercell_atoms": len(ph.supercell),
        "n_displacements": n_disp,
        "displacement_distance": displacement_distance,
        "scf_results": [],
        "forces_files": [],
        "phonon_analysis": {},
        "elapsed_sec": 0.0,
    }

    t0 = time.time()
    forces_files: list[Path] = []
    all_ok = True

    for i, (disp, scell) in enumerate(zip(ph.displacements, supercells), start=1):
        disp_dir = outdir / f"disp_{i:03d}"
        forces_file = disp_dir / "FORCES"
        if skip_existing and forces_file.exists():
            print(
                f"[run_phonopy_manual] {label} disp {i}/{n_disp}: reuse {forces_file}"
            )
            manifest["scf_results"].append(
                {"i": i, "reused": True, "forces_file": str(forces_file)}
            )
            forces_files.append(forces_file)
            continue

        atoms = _phonopy_supercell_to_ase(scell)
        print(
            f"[run_phonopy_manual] {label} disp {i}/{n_disp}: "
            f"{len(atoms)} atoms, workdir={disp_dir}"
        )
        res = run_scf(
            atoms,
            disp_dir,
            inpgen_bin,
            fleur_bin,
            preset=preset,
            mpi_procs=mpi_procs,
            with_mpi=with_mpi,
            do_forces=True,
            f_level=0,
        )
        entry = {"i": i, "displacement": disp, **asdict(res)}
        manifest["scf_results"].append(entry)
        if res.forces_present and res.converged and forces_file.exists():
            forces_files.append(forces_file)
        else:
            print(
                f"[run_phonopy_manual] {label} disp {i}: NO FORCES "
                f"(converged={res.converged}, error={res.error!r})",
                file=sys.stderr,
            )
            all_ok = False

    manifest["forces_files"] = [str(f) for f in forces_files]

    # Build force constants + analyse
    if len(forces_files) == n_disp and all_ok:
        print(f"[run_phonopy_manual] {label}: collecting force sets")
        collect_force_sets(ph, forces_files)
        ph.save(str(outdir / "phonopy_params.yaml"))
        analysis = analyse_phonons(ph)
        manifest["phonon_analysis"] = analysis
        print(
            f"[run_phonopy_manual] {label}: imaginary modes (mesh) = "
            f"{analysis.get('mesh_n_imaginary')}, "
            f"min freq = {analysis.get('mesh_min_freq_THz')} THz"
        )
    else:
        manifest["phonon_analysis"] = {
            "error": f"only {len(forces_files)}/{n_disp} force files available"
        }

    manifest["elapsed_sec"] = time.time() - t0
    (outdir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str)
    )
    print(
        f"[run_phonopy_manual] {label}: manifest written to {outdir / 'run_manifest.json'}"
    )
    return manifest


def _parse_matrix(s: str):
    return np.array(json.loads(s)).tolist()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--poscar", required=True)
    ap.add_argument(
        "--supercell-matrix",
        default="[[1,1,0],[-1,1,0],[0,0,2]]",
        help="3x3 supercell matrix as JSON (default matches the failed runs).",
    )
    ap.add_argument("--preset", choices=list(PRESETS), default="baseline")
    ap.add_argument(
        "--inpgen",
        default=os.environ.get("FLEUR_INPGEN_PATH", "/root/fleur/build/inpgen"),
    )
    ap.add_argument(
        "--fleur",
        default=os.environ.get("FLEUR_MPI_PATH", "/root/fleur/build/fleur_MPI"),
    )
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--label", default="system")
    ap.add_argument("--mpi-procs", type=int, default=1)
    ap.add_argument("--no-mpi", action="store_true")
    ap.add_argument("--displacement-distance", type=float, default=0.01)
    ap.add_argument("--no-skip-existing", action="store_true")
    args = ap.parse_args()

    run_phonopy_manual(
        args.poscar,
        _parse_matrix(args.supercell_matrix),
        args.preset,
        args.inpgen,
        args.fleur,
        args.outdir,
        label=args.label,
        mpi_procs=args.mpi_procs,
        with_mpi=not args.no_mpi,
        displacement_distance=args.displacement_distance,
        skip_existing=not args.no_skip_existing,
    )


if __name__ == "__main__":
    main()
