"""
End-to-end phonon calculation: download structure (optional) -> FLEUR SCF +
forces for each displacement -> phonopy force constants -> phonon frequencies.

This is a convenience wrapper that chains three steps:

  1. (optional) download_mpds_structure: fetch a crystal structure from the
     MPDS API by phase_id and save as POSCAR.
  2. run_phonopy_manual: generate displaced supercells with phonopy, run
     inpgen + fleur_MPI for each, extract forces, build force constants.
  3. compute_frequencies: diagonalise the dynamical matrix on a q-point mesh,
     write phonon_frequencies.txt, print imaginary-mode summary.

Usage (from MPDS phase_id):

    python3 scripts/phonon/manual/run_all.py \\
        --phase-id 7282 \\
        --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \\
        --preset tuningB_fast \\
        --inpgen /root/fleur/build/inpgen \\
        --fleur  /root/fleur/build/fleur_MPI \\
        --outdir data/manual_fleur_phonopy/runs/ZnO_7282 \\
        --label ZnO_7282 \\
        --mpi-procs 8

Usage (from existing POSCAR):

    python3 scripts/phonon/manual/run_all.py \\
        --poscar data/manual_fleur_phonopy/structures/BiSe_164.poscar \\
        --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \\
        --preset tuningB_fast \\
        --inpgen /root/fleur/build/inpgen \\
        --fleur  /root/fleur/build/fleur_MPI \\
        --outdir data/manual_fleur_phonopy/runs/BiSe_164 \\
        --label BiSe_164 \\
        --mpi-procs 8
"""

import argparse
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from run_phonopy_manual import run_phonopy_manual  # noqa: E402
from compute_frequencies import (  # noqa: E402
    load_phonopy,
    write_frequencies,
    print_gamma,
    DEFAULT_THRESHOLD_CM1,
)
from run_fleur_scf import PRESETS  # noqa: E402


def maybe_download_structure(phase_id: int, outdir: str, label: str) -> str:
    """Download a structure from MPDS and return the POSCAR path."""
    from download_mpds_structure import download_structure

    poscar = os.path.join(outdir, f"{label}.poscar")
    download_structure(phase_id, poscar)
    return poscar


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Structure source (one required)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--poscar", help="path to an existing POSCAR file")
    src.add_argument("--phase-id", type=int, help="MPDS phase_id to download")

    # FLEUR / phonopy parameters
    ap.add_argument(
        "--supercell-matrix",
        default="[[1,1,0],[-1,1,0],[0,0,2]]",
        help="3x3 supercell matrix as JSON (default: [[1,1,0],[-1,1,0],[0,0,2]])",
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

    # Frequency calculation
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
    ap.add_argument(
        "--skip-frequencies",
        action="store_true",
        help="skip frequency calculation (SCF only)",
    )

    args = ap.parse_args()

    import json
    import numpy as np

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    supercell_matrix = np.array(json.loads(args.supercell_matrix)).tolist()

    # --- Step 1: obtain POSCAR ---
    if args.poscar:
        poscar = args.poscar
        print(f"[run_all] using existing POSCAR: {poscar}")
    else:
        poscar = maybe_download_structure(args.phase_id, str(outdir), args.label)
        print(f"[run_all] downloaded POSCAR for phase_id={args.phase_id}: {poscar}")

    # --- Step 2: run FLEUR SCF + forces for each displacement ---
    print(f"\n[run_all] === Step 2: FLEUR SCF + forces (preset={args.preset}) ===")
    manifest = run_phonopy_manual(
        poscar=poscar,
        supercell_matrix=supercell_matrix,
        preset=args.preset,
        inpgen_bin=args.inpgen,
        fleur_bin=args.fleur,
        outdir=str(outdir),
        label=args.label,
        mpi_procs=args.mpi_procs,
        with_mpi=not args.no_mpi,
        displacement_distance=args.displacement_distance,
        skip_existing=not args.no_skip_existing,
    )

    # --- Step 3: compute phonon frequencies ---
    if args.skip_frequencies:
        print("\n[run_all] --skip-frequencies given, skipping frequency calculation")
        return

    print(f"\n[run_all] === Step 3: phonon frequencies (mesh={args.mesh}) ===")
    ph = load_phonopy(outdir)
    write_frequencies(ph, outdir, mesh=tuple(args.mesh), threshold=args.threshold)
    print_gamma(ph, threshold=args.threshold)

    # --- Summary ---
    pa = manifest.get("phonon_analysis", {})
    scfs = manifest.get("scf_results", [])
    n_conv = sum(1 for s in scfs if s.get("converged"))
    n_forces = sum(1 for s in scfs if s.get("forces_present"))
    n_err = sum(1 for s in scfs if s.get("error"))

    print(f"\n[run_all] === Summary ===")
    print(f"  label:          {args.label}")
    print(f"  preset:         {args.preset}")
    print(f"  displacements:  {len(scfs)}")
    print(f"  converged:      {n_conv}/{len(scfs)}")
    print(f"  forces:         {n_forces}/{len(scfs)}")
    print(f"  errors:         {n_err}/{len(scfs)}")
    print(f"  elapsed:        {manifest.get('elapsed_sec', 0) / 60:.1f} min")
    print(f"  phonon_frequencies.txt: {outdir / 'phonon_frequencies.txt'}")
    print(f"  run_manifest.json:      {outdir / 'run_manifest.json'}")


if __name__ == "__main__":
    main()
