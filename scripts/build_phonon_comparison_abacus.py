"""Extend the October comparison using dft-organizer's phonon reporting API."""

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import numpy as np
from aiida import load_profile
from aiida.orm import load_node
from dft_organizer import phonon_utils as pu
from dft_organizer.aiida.reporting import save_aiida_phonon_reports
from mpds_aiida.abacus_forces import read_scf_log, restore_force_order, scf_has_converged

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "phonon_summary_2026_10_23_14_37_18"
PHASES = {
    "GaP": 137598,
    "InSb": 137602,
    "LaAlO3": 137606,
    "YAlO3": 137610,
    "Al2O3": 137618,
    "MgAl2O4": 138292,
    "CaTiO3": 140202,
}


def reconstruct_if_needed(wc):
    """Verify saved SCF force identity; rebuild only when atom rows were permuted."""
    children = sorted(
        [
            child
            for child in wc.called
            if child.process_label == "AbacusForcesWorkChain"
        ],
        key=lambda child: int(child.inputs.structure_label.value),
    )
    if not children or not all(child.is_finished_ok for child in children):
        raise ValueError(f"Incomplete force calculations for phonon node {wc.pk}")
    raw, corrected, displacements = [], [], []
    for child in children:
        misc = child.outputs.misc
        calculation = misc.creator
        if not calculation.is_finished_ok:
            raise ValueError(
                f"SCF calculation {calculation.pk} did not finish successfully"
            )
        data = misc.get_dict()
        if data.get("force_unit") != "eV/Angstrom":
            raise ValueError(f"Unexpected force units in {calculation.pk}")
        log = read_scf_log(calculation)
        if not scf_has_converged(log):
            raise ValueError(f"No SCF convergence marker in {calculation.pk}")
        restored, permutation = restore_force_order(
            child.inputs.structure,
            data["final_forces"],
            calculation.base.repository.get_object_content("STRU"),
        )
        raw.append(data["final_forces"])
        corrected.append(restored)
        displacements.append(
            {
                "label": child.inputs.structure_label.value,
                "force_workchain_pk": child.pk,
                "calcjob_pk": calculation.pk,
                "calcjob_uuid": str(calculation.uuid),
                "abacus_to_structure": permutation,
                "reordered_rows": sum(i != j for i, j in enumerate(permutation)),
            }
        )
    phonopy_data = wc.outputs.phonopy_data
    if phonopy_data.forces_index is not None:
        raise ValueError(
            "An explicit forces_index requires an explicit displacement mapping"
        )
    # Establish that these are exactly the forces used by the saved phonopy data.
    np.testing.assert_allclose(phonopy_data.forces, raw, atol=1e-12, rtol=0)
    changed = any(item["reordered_rows"] for item in displacements)
    audit = {
        "source_phonon_pk": wc.pk,
        "source_phonon_uuid": str(wc.uuid),
        "source_phonopy_data_pk": phonopy_data.pk,
        "force_order_corrected": changed,
        "displacements": displacements,
    }
    if not changed:
        return None, audit

    phonon = phonopy_data.get_phonopy_instance()
    original_fc = wc.outputs.output_phonopy.output_force_constants.get_array(
        "force_constants"
    )
    full_force_constants = original_fc.shape[0] == len(phonon.supercell)
    phonon.produce_force_constants(calculate_full_force_constants=full_force_constants)
    # Reproduce the old result before correcting it, to check the reconstruction.
    np.testing.assert_allclose(phonon.force_constants, original_fc, atol=1e-8, rtol=0)
    audit["raw_force_constants_max_absolute_error"] = float(
        np.max(np.abs(phonon.force_constants - original_fc))
    )
    phonon.forces = np.asarray(corrected, dtype=float)
    phonon.produce_force_constants(calculate_full_force_constants=True)
    # The full matrix allows the report's standard phonopy symmetrization
    # to enforce the acoustic sum rule to numerical precision.
    audit["reconstructed_format"] = "full"
    audit["source_force_constants_shape"] = list(original_fc.shape)
    audit["reconstructed_force_constants_shape"] = list(phonon.force_constants.shape)
    audit["n_imaginary_before"] = pu.extract_frequencies_from_workchain(
        wc.pk, mesh=[8, 8, 8], force_constants_override=original_fc
    )["n_imaginary"]
    return phonon.force_constants.copy(), audit


if __name__ == "__main__":
    load_profile()
    stamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    audit_path = ROOT / "summary" / f"phonon_force_order_audit_{stamp}.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_rows = []
    with BASE.with_suffix(".csv").open() as handle:
        old_csv = list(csv.DictReader(handle))
    source = {
        str(r["pk"]): r for r in json.loads(BASE.with_suffix(".json").read_text())
    }
    # Preserve exactly the selection and columns of the requested baseline.
    rows = [{k: source[r["pk"]].get(k) for k in r} for r in old_csv]
    for r in rows:
        key = f"{r['chemical_formula']}_{r['space_group']}"
        lo = [float(v) for v in (r.get("mpds_lo_cm1") or "").split(",") if v.strip()]
        to = [float(v) for v in (r.get("mpds_to_cm1") or "").split(",") if v.strip()]
        pu._MPDS_CACHE[key] = {
            "lo_cm1": lo,
            "to_cm1": to,
            "all_cm1": lo + to,
            "unmarked_cm1": [],
            "n_entries": r.get("mpds_n_entries") or 0,
        }
    for formula, parent_pk in PHASES.items():
        parent = load_node(parent_pk)
        wc = next(
            c for c in parent.called if "phonopy.abacus" in (c.process_type or "")
        )
        assert parent.is_finished_ok and all(
            c.is_finished_ok for c in parent.called_descendants
        )
        force_constants, audit = reconstruct_if_needed(wc)
        row = pu.get_phonon_workchain_summary(
            wc.pk,
            mesh=[8, 8, 8],
            t_eval=300,
            force_constants_override=force_constants,
        )
        assert not row.get("error"), row
        assert row["chemical_formula"] == formula
        row["engine"] = "abacus"
        row["force_order_corrected"] = audit["force_order_corrected"]
        row["force_order_audit"] = str(audit_path.relative_to(ROOT))
        if force_constants is not None:
            fc_path = (
                ROOT
                / "summary"
                / f"abacus_force_constants_corrected_{wc.pk}_{stamp}.npz"
            )
            np.savez_compressed(fc_path, force_constants=force_constants)
            row["force_constants_source"] = str(fc_path.relative_to(ROOT))
            audit["reconstructed_force_constants_file"] = row["force_constants_source"]
            audit["reconstructed_force_constants_sha256"] = hashlib.sha256(fc_path.read_bytes()).hexdigest()
        audit["n_imaginary_after"] = row["n_imaginary"]
        audit["threshold_cm1"] = pu.DEFAULT_THRESHOLD_CM1
        audit["mesh"] = [8, 8, 8]
        audit_rows.append(audit)
        rows.append(row)
        print(formula, "phonopy PK", wc.pk, "imaginary", row["n_imaginary"], flush=True)
    audit_path.write_text(json.dumps(audit_rows, indent=2) + "\n")
    save_aiida_phonon_reports(rows, output_dir=ROOT)
    print("Force-order reconstruction audit:", audit_path)
