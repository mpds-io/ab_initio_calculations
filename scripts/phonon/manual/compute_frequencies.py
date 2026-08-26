"""
Compute and dump phonon frequencies from a completed phonopy+FLEUR run.

Reads the FORCES files and phonopy_params.yaml produced by run_phonopy_manual.py,
builds force constants, and writes all phonon frequencies on a q-point mesh to
phonon_frequencies.txt. Also prints a summary (imaginary modes, Gamma point).

Usage:

    python3 scripts/phonon/manual/compute_frequencies.py \\
        --run-dir data/manual_fleur_phonopy/runs/BiSe_164 \\
        --mesh 8 8 8

The output file phonon_frequencies.txt is written into --run-dir.
"""

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import yaml
from phonopy import Phonopy
from phonopy.structure.atoms import PhonopyAtoms
from phonopy.interface.fleur import parse_set_of_forces
from phonopy.units import VaspToCm

# All frequencies here are in cm^-1 (not phonopy's default THz), to match the
# CRYSTAL/AiiDA convention used elsewhere in this repo.
# -1.67 cm^-1 ~= -0.05 THz, the previously used imaginary-mode cutoff.
DEFAULT_THRESHOLD_CM1 = -1.67


def load_phonopy(run_dir: Path):
    """Rebuild a Phonopy object from phonopy_params.yaml + FORCES files."""
    params_path = run_dir / "phonopy_params.yaml"
    if not params_path.exists():
        sys.exit(f"error: {params_path} not found")
    with open(params_path) as f:
        params = yaml.safe_load(f)

    uc = params["unit_cell"]
    cell = np.array(uc["lattice"])
    symbols = [p["symbol"] for p in uc["points"]]
    positions = [p["coordinates"] for p in uc["points"]]
    unitcell = PhonopyAtoms(symbols=symbols, cell=cell, scaled_positions=positions)
    sm = np.array(params["supercell_matrix"])

    ph = Phonopy(unitcell, supercell_matrix=sm, factor=VaspToCm)
    ph.generate_displacements()

    n_atoms = len(ph.supercell)
    forces_files = sorted(glob.glob(str(run_dir / "disp_*" / "FORCES")))
    if not forces_files:
        sys.exit(f"error: no FORCES files found in {run_dir}/disp_*/")
    print(f"loading {len(forces_files)} FORCES files ({n_atoms} atoms in supercell)")
    force_sets = parse_set_of_forces(n_atoms, forces_files)
    ph.forces = np.array(force_sets)
    ph.produce_force_constants()
    return ph


def write_frequencies(ph, run_dir: Path, mesh=(8, 8, 8), threshold=DEFAULT_THRESHOLD_CM1):
    """Run a mesh calculation and dump frequencies to phonon_frequencies.txt."""
    ph.run_mesh(list(mesh))
    mesh_data = ph.get_mesh_dict()
    all_freqs = mesh_data["frequencies"]
    qpoints = mesh_data["qpoints"]

    out_path = run_dir / "phonon_frequencies.txt"
    n_imag_total = 0
    with open(out_path, "w") as f:
        f.write("# Phonon frequencies (cm^-1)\n")
        f.write(f"# q-point mesh: {list(mesh)}\n")
        f.write(f"# n_qpoints = {len(all_freqs)}, n_bands = {len(all_freqs[0])}\n")
        f.write(f"# imaginary threshold: < {threshold} cm^-1 (marked with *)\n\n")
        for qi, (q, freqs) in enumerate(zip(qpoints, all_freqs)):
            n_imag = sum(1 for fr in freqs if fr < threshold)
            n_imag_total += n_imag
            f.write(
                f"q-point {qi + 1:4d}: [{q[0]:.4f}, {q[1]:.4f}, {q[2]:.4f}]  "
                f"imaginary={n_imag}\n"
            )
            for bi, fr in enumerate(freqs):
                marker = " *" if fr < threshold else ""
                f.write(f"  band {bi + 1:3d}: {fr:10.4f} cm^-1{marker}\n")
            f.write("\n")

    print(f"wrote {out_path}")
    print(
        f"q-points: {len(all_freqs)}, bands: {len(all_freqs[0])}, "
        f"total: {len(all_freqs) * len(all_freqs[0])}"
    )
    print(f"imaginary (< {threshold} cm^-1): {n_imag_total}")


def print_gamma(ph, threshold=DEFAULT_THRESHOLD_CM1):
    """Print frequencies at the Gamma point (q=0,0,0)."""
    ph.run_qpoints([[0, 0, 0]])
    freqs = ph.get_qpoints_dict()["frequencies"][0]
    print(f"\n=== Gamma point (q=0,0,0) ===")
    print(f"bands: {len(freqs)}")
    n_imag = 0
    for i, fr in enumerate(freqs):
        is_imag = fr < threshold
        if is_imag:
            n_imag += 1
        print(f"  band {i + 1:3d}: {fr:10.4f} cm^-1{'  IMAGINARY' if is_imag else ''}")
    print(f"imaginary at Gamma: {n_imag}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--run-dir",
        required=True,
        help="directory with disp_*/FORCES and phonopy_params.yaml",
    )
    ap.add_argument(
        "--mesh",
        type=int,
        nargs=3,
        default=[8, 8, 8],
        help="q-point mesh (default: 8 8 8)",
    )
    ap.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD_CM1,
        help=f"imaginary threshold in cm^-1 (default: {DEFAULT_THRESHOLD_CM1})",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    ph = load_phonopy(run_dir)
    write_frequencies(ph, run_dir, mesh=args.mesh, threshold=args.threshold)
    print_gamma(ph, threshold=args.threshold)


if __name__ == "__main__":
    main()
