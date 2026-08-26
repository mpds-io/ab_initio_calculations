#!/usr/bin/env python3
"""
Extract phonon frequencies from a completed AiiDA PhonopyFleurWorkChain and
write them in the same phonon_frequencies.txt format compute_frequencies.py
produces for the manual pipeline, so the existing integrate_phonons.py /
phonon_thermo.py tooling can read them unchanged.

Reads structure + supercell_matrix from the workchain inputs and
force_constants from output_phonopy.output_force_constants -- no FORCES
files or phonopy_params.yaml needed, since AiiDA already has everything.

Usage:
    verdi -p presto_pg run scripts/phonon/by_aiida/extract_aiida_frequencies.py \
        --pk 93126 --mesh 8 8 8 \
        --output data/aiida_phonon_results/ZnO_186/phonon_frequencies.txt
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from phonopy import Phonopy
from phonopy.structure.atoms import PhonopyAtoms
from phonopy.units import VaspToCm

DEFAULT_THRESHOLD_CM1 = -1.67


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pk", type=int, required=True, help="PhonopyFleurWorkChain PK")
    ap.add_argument("--mesh", type=int, nargs=3, default=[8, 8, 8])
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_CM1)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    from aiida.orm import load_node

    wc = load_node(args.pk)
    if not wc.is_finished_ok:
        sys.exit(
            f"error: PK {args.pk} is not finished_ok "
            f"(exit_status={wc.exit_status})"
        )

    structure = wc.inputs.structure
    supercell_matrix = np.array(wc.inputs.supercell_matrix.get_list())
    fc = wc.outputs.output_phonopy.output_force_constants.get_array(
        "force_constants"
    )

    ase_atoms = structure.get_ase()
    unitcell = PhonopyAtoms(
        symbols=ase_atoms.get_chemical_symbols(),
        cell=ase_atoms.get_cell(),
        scaled_positions=ase_atoms.get_scaled_positions(),
    )

    ph = Phonopy(unitcell, supercell_matrix=supercell_matrix, factor=VaspToCm)
    ph.force_constants = fc
    # AiiDA's raw force constants don't exactly satisfy the acoustic sum
    # rule (translating the whole crystal must cost zero energy): without
    # this, the 3 acoustic branches at Gamma come out tens of cm^-1 away
    # from zero instead of ~0, which reads as spurious "instabilities".
    ph.symmetrize_force_constants()

    ph.run_mesh(list(args.mesh))
    mesh_data = ph.get_mesh_dict()
    all_freqs = mesh_data["frequencies"]
    qpoints = mesh_data["qpoints"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    n_imag_total = 0
    with open(args.output, "w") as f:
        f.write("# Phonon frequencies (cm^-1)\n")
        f.write(f"# source: AiiDA PhonopyFleurWorkChain<{args.pk}>\n")
        f.write(f"# q-point mesh: {list(args.mesh)}\n")
        f.write(f"# n_qpoints = {len(all_freqs)}, n_bands = {len(all_freqs[0])}\n")
        f.write(f"# imaginary threshold: < {args.threshold} cm^-1 (marked with *)\n\n")
        for qi, (q, freqs) in enumerate(zip(qpoints, all_freqs)):
            n_imag = sum(1 for fr in freqs if fr < args.threshold)
            n_imag_total += n_imag
            f.write(
                f"q-point {qi + 1:4d}: [{q[0]:.4f}, {q[1]:.4f}, {q[2]:.4f}]  "
                f"imaginary={n_imag}\n"
            )
            for bi, fr in enumerate(freqs):
                marker = " *" if fr < args.threshold else ""
                f.write(f"  band {bi + 1:3d}: {fr:10.4f} cm^-1{marker}\n")
            f.write("\n")

    print(f"wrote {args.output}")
    print(
        f"q-points: {len(all_freqs)}, bands: {len(all_freqs[0])}, "
        f"total: {len(all_freqs) * len(all_freqs[0])}"
    )
    print(f"imaginary (< {args.threshold} cm^-1): {n_imag_total}")

    ph.run_qpoints([[0, 0, 0]])
    gamma_freqs = ph.get_qpoints_dict()["frequencies"][0]
    n_imag_gamma = sum(1 for fr in gamma_freqs if fr < args.threshold)
    print(f"\n=== Gamma point (q=0,0,0) ===")
    print(f"imaginary at Gamma: {n_imag_gamma}")


if __name__ == "__main__":
    main()
