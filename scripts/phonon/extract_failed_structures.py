"""
Extract the pristine StructureData of the failed PhonopyFleurWorkChain runs
to POSCAR files and dump the accompanying fleur_parameters / supercell_matrix
to JSON so the manual pipeline can reproduce the original setup exactly.

Run from the ab_initio_calculations repo root:

    python3 scripts/phonon/extract_failed_structures.py \\
        --profile presto_pg \\
        --outdir data/manual_fleur_phonopy/structures

The four default systems (BiSe/164, Au2U/191, Co2As/189, Ce5Ge3/193) are
hardcoded; use --pk to add more.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_SYSTEMS = [
    # (system_label, phonopy_wc_pk, structure_pk, fleur_params_pk,
    #  supercell_matrix_pk, phonopy_params_pk)
    ("BiSe_164", 69694, 68689, 69690, 69689, 69691),
    ("Au2U_191", 72237, 68561, 72233, 72232, None),
    ("Co2As_189", 71002, 68795, 70998, 70997, None),
    ("Ce5Ge3_193", 70996, 68767, 70992, 70991, None),
]


def to_ase(node) -> "ase.Atoms":  # noqa: F821
    return node.get_ase()


def write_poscar(atoms, path: Path):
    import io
    from ase.io import write as ase_write

    buf = io.StringIO()
    ase_write(buf, atoms, format="vasp")
    path.write_text(buf.getvalue())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", default="presto_pg")
    ap.add_argument("--outdir", default="data/manual_fleur_phonopy/structures")
    ap.add_argument(
        "--pk",
        type=int,
        nargs="+",
        default=None,
        help="Extra PhonopyFleurWorkChain PKs to extract (structure + params).",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    from aiida import load_profile
    from aiida.orm import load_node

    load_profile(args.profile)

    systems = list(DEFAULT_SYSTEMS)
    if args.pk:
        for pk in args.pk:
            wc = load_node(pk)
            try:
                struct = wc.inputs.structure
                fp = wc.inputs.fleur_parameters
                sm = wc.inputs.supercell_matrix
            except AttributeError as e:
                print(f"[skip] PK {pk}: {e}", file=sys.stderr)
                continue
            systems.append(
                (
                    wc.label.replace(" - phonons", "")
                    .replace(" ", "_")
                    .replace("/", "_"),
                    pk,
                    struct.pk,
                    fp.pk,
                    sm.pk,
                    None,
                )
            )

    manifest = {}
    for entry in systems:
        (
            label,
            wc_pk,
            struct_pk,
            fp_pk,
            sm_pk,
            pp_pk,
        ) = entry
        print(f"== {label} (wc={wc_pk}, struct={struct_pk}) ==")
        struct = load_node(struct_pk)
        atoms = to_ase(struct)
        poscar = outdir / f"{label}.poscar"
        write_poscar(atoms, poscar)
        print(f"  wrote {poscar} ({len(atoms)} atoms)")

        rec = {
            "phonopy_workchain_pk": wc_pk,
            "structure_pk": struct_pk,
            "poscar": str(poscar),
            "n_atoms": len(atoms),
        }
        if fp_pk is not None:
            fp = load_node(fp_pk)
            try:
                rec["fleur_parameters"] = fp.get_dict()
            except Exception:
                rec["fleur_parameters"] = dict(fp.base.attributes.all)
        if sm_pk is not None:
            sm = load_node(sm_pk)
            try:
                rec["supercell_matrix"] = sm.get_list()
            except Exception:
                rec["supercell_matrix"] = list(sm.base.attributes.all.get("list", []))
        if pp_pk is not None:
            pp = load_node(pp_pk)
            try:
                rec["phonopy_parameters"] = pp.get_dict()
            except Exception:
                rec["phonopy_parameters"] = dict(pp.base.attributes.all)

        manifest[label] = rec

    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest written to {manifest_path}")


if __name__ == "__main__":
    main()
