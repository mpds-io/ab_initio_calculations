"""
Compare ML-predicted Seebeck coefficient (via labs.mpds.io/predict)
with ab initio Fleur and CRYSTAL Seebeck for a given phase.

How it works:
1. Loads a crystal structure from AiiDA by PK (StructureData node).
2. Converts the structure to CIF format with correct space group information
   (using spglib to detect symmetry and reduce to asymmetric unit).
3. Sends the CIF to the MPDS ML prediction service (https://labs.mpds.io/predict),
   which returns predicted properties including the Seebeck coefficient (property "k").
4. Looks up Fleur Seebeck result by PK from FLEUR_SEEBECK_WCS.
5. Looks up CRYSTAL Seebeck result by PK from CRYSTAL_SEEBECK_WCS.
   The CRYSTAL Seebeck DAT file contains S_xx, S_yy, S_zz as a function of
   chemical potential (mu) and temperature. We extract S_avg = (S_xx + S_yy + S_zz)/3
   at T=298K and mu closest to 0 (intrinsic Seebeck).
6. Prints all values and their differences for comparison.

Usage:
    python compare_seebeck.py Au2U/191       # single phase
    python compare_seebeck.py --all           # all 15 phases
"""

import json

import numpy as np
import spglib
import urllib.parse
import urllib.request

from aiida import load_profile
from aiida.orm import load_node

ML_ENDPOINT = "https://labs.mpds.io/predict"

UNREALISTIC_THRESHOLD = 5000

PHASES = {
    "Au2U/191":   68561,
    "BaSn3/194":  68638,
    "BiSe/164":   68689,
    "B2O3/152":   68761,
    "Ce5Ge3/193": 68767,
    "Co2As/189":  68795,
    "CrSb/194":   68783,
    "DyNi5/191":  68812,
    "AsF5/194":   67165,
    "Ca2Sb/139":  67712,
    "CaC6/166":   67020,
    "CaGe2/166":  67728,
    "CoO2/166":   67045,
    "DyBr3/148":  68007,
    "Er5Rh3/193": 67095,
}

FLEUR_SEEBECK_WCS = {
    "Au2U/191":   [74992],
    "BaSn3/194":  [74995],
    "CrSb/194":   [75009],
    "Co2As/189":  [75006, 74864],
    "Ce5Ge3/193": [75003],
    "DyNi5/191":  [75013],
}

CRYSTAL_SEEBECK_WCS = {
    "AsF5/194":   [74831],
    "B2O3/152":   [74705],
    "CaGe2/166":  [74710],
    "Co2As/189":  [74719],
    "CrSb/194":   [68427],
    "DyBr3/148":  [74726],
    "Ca2Sb/139":  [67588],
}


def structure_to_cif(structure_node):
    """Convert an AiiDA StructureData to a CIF string with correct space group.

    The MPDS ML predictor requires proper space group information in the CIF
    (_symmetry_Int_Tables_number and _symmetry_space_group_name_H-M).
    ASE's default CIF writer sets space group to P 1, which the predictor rejects.
    This function uses spglib to detect the real space group and writes a minimal
    CIF with only the asymmetric unit atoms (removes symmetry-equivalent positions).
    """
    ase_obj = structure_node.get_ase()
    cell = ase_obj.get_cell()
    scaled_pos = ase_obj.get_scaled_positions().tolist()
    atomic_numbers = ase_obj.get_atomic_numbers()
    symbols = ase_obj.get_chemical_symbols()

    cell_tuple = (cell.tolist(), scaled_pos, atomic_numbers)
    sym_dataset = spglib.get_symmetry_dataset(cell_tuple, symprec=1e-3)

    if sym_dataset:
        sg_number = sym_dataset["number"]
        sg_name = sym_dataset["international"]
        equiv = sym_dataset["equivalent_atoms"]
        unique_indices = []
        seen = set()
        for i, e in enumerate(equiv):
            if e not in seen:
                unique_indices.append(i)
                seen.add(e)
    else:
        sg_number = 1
        sg_name = "P 1"
        unique_indices = list(range(len(symbols)))

    a = np.linalg.norm(cell[0])
    b = np.linalg.norm(cell[1])
    c = np.linalg.norm(cell[2])
    alpha = np.degrees(np.arccos(np.clip(np.dot(cell[1], cell[2]) / (b * c), -1, 1)))
    beta = np.degrees(np.arccos(np.clip(np.dot(cell[0], cell[2]) / (a * c), -1, 1)))
    gamma = np.degrees(np.arccos(np.clip(np.dot(cell[0], cell[1]) / (a * b), -1, 1)))

    lines = [
        f"data_{ase_obj.get_chemical_formula()}",
        f"_cell_length_a       {a:.6f}",
        f"_cell_length_b       {b:.6f}",
        f"_cell_length_c       {c:.6f}",
        f"_cell_angle_alpha    {alpha:.6f}",
        f"_cell_angle_beta     {beta:.6f}",
        f"_cell_angle_gamma    {gamma:.6f}",
        f"_symmetry_Int_Tables_number    {sg_number}",
        f"_symmetry_space_group_name_H-M '{sg_name}'",
        "",
        "loop_",
        " _atom_site_type_symbol",
        " _atom_site_fract_x",
        " _atom_site_fract_y",
        " _atom_site_fract_z",
        " _atom_site_occupancy",
    ]
    for i in unique_indices:
        fx, fy, fz = scaled_pos[i]
        lines.append(f" {symbols[i]}  {fx:.6f}  {fy:.6f}  {fz:.6f}  1.0")

    return "\n".join(lines) + "\n"


def predict_seebeck(cif_content):
    """Send a CIF structure to the MPDS ML predictor and return the full response.

    The endpoint expects a POST request with Content-Type application/x-www-form-urlencoded
    and a "structure" field containing the CIF text. It returns JSON with a "prediction" dict
    containing property codes as keys ("k" = Seebeck coefficient in uV/K).
    Each prediction has "value" and "mae" fields.
    """
    data = urllib.parse.urlencode({"structure": cif_content})
    req = urllib.request.Request(
        ML_ENDPOINT,
        data=data.encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if "error" in result:
        raise RuntimeError(f"ML prediction error: {result['error']}")
    return result


def get_fleur_seebeck(phase_label):
    """Get Fleur Seebeck coefficient by looking up workchain PK.

    Uses FLEUR_SEEBECK_WCS dict to find the workchain by PK.
    For phases with multiple PKs (fallback list), tries each in order.
    Returns (seebeck_uVK, None) on success, or (None, error_string) on failure.
    """
    pks = FLEUR_SEEBECK_WCS.get(phase_label)
    if not pks:
        return None, "no Fleur WC for this phase"

    last_error = "no Fleur data"
    for pk in pks:
        wc = load_node(pk)
        if wc.process_state.name != "FINISHED":
            last_error = f"WC PK={pk} state={wc.process_state.name}"
            continue
        if wc.exit_status != 0:
            last_error = f"WC PK={pk} exit={wc.exit_status}"
            continue
        try:
            seebeck_dict = wc.outputs.output_seebeck.get_dict()
            val = seebeck_dict.get("seebeck_coefficient_uvk")
            if val is not None:
                return val, None
        except Exception as e:
            last_error = f"WC PK={pk} no output_seebeck: {e}"
            continue

    return None, last_error


def parse_seebeck_dat(content):
    """Parse CRYSTAL Seebeck DAT content and return S_avg at T=298K, mu=0.

    The DAT file format is:
        # Mu(eV) T(K) N(#carriers) S_xx S_xy S_xz S_yx S_yy S_yz S_zx S_zy S_zz
    Values are in V/K. We extract S_avg = (S_xx + S_yy + S_zz)/3 at T=298K
    and mu closest to 0 (intrinsic Seebeck), then convert to uV/K.

    Returns (seebeck_uVK, None) on success, or (None, error_string) on failure.
    """
    lines = content.strip().split("\n")
    if len(lines) <= 2:
        return None, "empty DAT"

    best_seebeck = None
    best_mu = 999.0
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split()
        if len(parts) < 12:
            continue
        try:
            mu_ev = float(parts[0])
            t_k = float(parts[1])
            s_xx = float(parts[3])
            s_yy = float(parts[7])
            s_zz = float(parts[10])
        except (ValueError, IndexError):
            continue

        if abs(t_k - 298.0) < 1.0 and abs(mu_ev) < abs(best_mu):
            best_mu = mu_ev
            best_seebeck = (s_xx + s_yy + s_zz) / 3.0 * 1e6

    if best_seebeck is not None:
        return best_seebeck, None
    return None, "no T=298K data"


def get_crystal_seebeck(phase_label):
    """Get CRYSTAL Seebeck coefficient by looking up workchain PK.

    Uses CRYSTAL_SEEBECK_WCS dict to find the workchain by PK.
    Tries PKs in order (first = preferred). Supports both output labels:
    - seebeck_dat (SeebeckPropertiesWorkChain)
    - properties__seebeck_dat (mpds_seebeck pipeline)

    Returns (seebeck_uVK, None) on success, or (None, error_string) on failure.
    """
    pks = CRYSTAL_SEEBECK_WCS.get(phase_label)
    if not pks:
        return None, "no CRYSTAL WC for this phase"

    for pk in pks:
        wc = load_node(pk)
        if wc.exit_status != 0:
            return None, f"WC PK={pk} exit={wc.exit_status}"

        content = None
        try:
            if hasattr(wc.outputs, "seebeck_dat"):
                with wc.outputs.seebeck_dat.open(mode="r") as f:
                    content = f.read()
            elif hasattr(wc.outputs, "properties") and hasattr(wc.outputs.properties, "seebeck_dat"):
                with wc.outputs.properties.seebeck_dat.open(mode="r") as f:
                    content = f.read()
        except Exception:
            continue

        if content is None:
            return None, f"WC PK={pk} no seebeck_dat output"

        seebeck, error = parse_seebeck_dat(content)
        if seebeck is not None:
            return seebeck, None
        return None, f"WC PK={pk} parse error: {error}"

    return None, "no CRYSTAL data"


def format_seebeck(value, source=""):
    """Format Seebeck value with reliability flag if needed."""
    if value is None:
        return "N/A"
    flag = ""
    if abs(value) > UNREALISTIC_THRESHOLD:
        flag = " (unreliable)"
    return f"{value:.2f} uV/K{flag}"


def compare_phase(phase_label):
    """Compare ML, Fleur, and CRYSTAL Seebeck for a single phase."""
    structure_pk = PHASES.get(phase_label)
    if structure_pk is None:
        print(f"Phase: {phase_label}")
        print(f"Structure PK: unknown")
        print(f"ML Seebeck:      N/A (no structure)")
        fleur_seebeck, fleur_error = get_fleur_seebeck(phase_label)
        if fleur_seebeck is not None:
            print(f"Fleur Seebeck:    {format_seebeck(fleur_seebeck)}")
        else:
            print(f"Fleur Seebeck:    N/A ({fleur_error})")
        crystal_seebeck, crystal_error = get_crystal_seebeck(phase_label)
        if crystal_seebeck is not None:
            print(f"CRYSTAL Seebeck:  {format_seebeck(crystal_seebeck)}")
        else:
            print(f"CRYSTAL Seebeck:  N/A ({crystal_error})")
        print()
        return {
            "phase": phase_label,
            "ml": None,
            "ml_mae": None,
            "fleur": fleur_seebeck,
            "crystal": crystal_seebeck,
        }

    structure_node = load_node(structure_pk)
    cif_content = structure_to_cif(structure_node)

    print(f"Phase: {phase_label}")
    print(f"Structure PK: {structure_pk}")
    print(f"Formula: {structure_node.get_ase().get_chemical_formula()}")
    print()

    ml_seebeck = None
    ml_mae = None
    print("Sending to ML predictor...")
    try:
        ml_result = predict_seebeck(cif_content)
        if "prediction" in ml_result and "k" in ml_result["prediction"]:
            ml_seebeck = ml_result["prediction"]["k"]["value"]
            ml_mae = ml_result["prediction"]["k"]["mae"]
            print(f"ML Seebeck:       {ml_seebeck:.2f} uV/K (MAE: {ml_mae:.2f})")
        else:
            print(f"ML result: {json.dumps(ml_result, indent=2)}")
    except Exception as e:
        print(f"ML prediction failed: {e}")

    fleur_seebeck, fleur_error = get_fleur_seebeck(phase_label)
    if fleur_seebeck is not None:
        print(f"Fleur Seebeck:    {format_seebeck(fleur_seebeck)}")
    else:
        print(f"Fleur Seebeck:    N/A ({fleur_error})")

    crystal_seebeck, crystal_error = get_crystal_seebeck(phase_label)
    if crystal_seebeck is not None:
        print(f"CRYSTAL Seebeck:  {format_seebeck(crystal_seebeck)}")
    else:
        print(f"CRYSTAL Seebeck:  N/A ({crystal_error})")

    print()

    diffs = []
    if ml_seebeck is not None and fleur_seebeck is not None:
        diffs.append(f"ML-Fleur={ml_seebeck - fleur_seebeck:.2f}")
    if ml_seebeck is not None and crystal_seebeck is not None:
        diffs.append(f"ML-CRYSTAL={ml_seebeck - crystal_seebeck:.2f}")
    if fleur_seebeck is not None and crystal_seebeck is not None:
        diffs.append(f"Fleur-CRYSTAL={fleur_seebeck - crystal_seebeck:.2f}")

    if diffs:
        print(f"Differences: {', '.join(diffs)}")

    return {
        "phase": phase_label,
        "ml": ml_seebeck,
        "ml_mae": ml_mae,
        "fleur": fleur_seebeck,
        "crystal": crystal_seebeck,
    }


def print_summary_table(results):
    """Print a markdown summary table of all results."""
    print("\n" + "=" * 100)
    print("SUMMARY TABLE")
    print("=" * 100)
    print(f"| {'Phase':<12} | {'ML (uV/K)':>10} | {'Fleur (uV/K)':>12} | {'CRYSTAL (uV/K)':>14} | {'ML-Fleur':>9} | {'ML-CRYSTAL':>11} | {'F-C':>9} |")
    print(f"|{'-'*14}|{'-'*12}|{'-'*14}|{'-'*16}|{'-'*11}|{'-'*13}|{'-'*11}|")
    for r in results:
        ml_str = f"{r['ml']:.2f}" if r['ml'] is not None else "N/A"
        fleur_str = f"{r['fleur']:.2f}" if r['fleur'] is not None else "N/A"
        crystal_str = f"{r['crystal']:.2f}" if r['crystal'] is not None else "N/A"
        if r['crystal'] is not None and abs(r['crystal']) > UNREALISTIC_THRESHOLD:
            crystal_str += "*"
        ml_f = f"{r['ml'] - r['fleur']:.2f}" if r['ml'] is not None and r['fleur'] is not None else "N/A"
        ml_c = f"{r['ml'] - r['crystal']:.2f}" if r['ml'] is not None and r['crystal'] is not None else "N/A"
        f_c = f"{r['fleur'] - r['crystal']:.2f}" if r['fleur'] is not None and r['crystal'] is not None else "N/A"
        print(f"| {r['phase']:<12} | {ml_str:>10} | {fleur_str:>12} | {crystal_str:>14} | {ml_f:>9} | {ml_c:>11} | {f_c:>9} |")
    print(f"\n* = unreliable (|S| > {UNREALISTIC_THRESHOLD} uV/K)")


def main():
    load_profile()

    phase_label = "Au2U/191"
    compare_phase(phase_label)


if __name__ == "__main__":
    main()