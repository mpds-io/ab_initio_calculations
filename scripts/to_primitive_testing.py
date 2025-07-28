import logging
import random
import numpy as np
from collections import Counter
import spglib
from ab_initio_calculations.utils.chemical_utils import get_random_element
from ase import Atoms
from aiida.orm import StructureData
from ab_initio_calculations.mpds.receiver import download_structures
from aiida import load_profile
load_profile()

from aiida_crystal_dft.utils.geometry import to_primitive

logger = logging.getLogger("cell_treatment")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler('cell_treatment_aiida_test.log', mode='w')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

if logger.hasHandlers():
    logger.handlers.clear()

logger.addHandler(file_handler)


def get_random_structuredata():
    el = get_random_element()
    structs, _, _ = download_structures(el)
    structe = structs[random.randint(0, len(structs)-1)]
    return structe

def normalize_composition(numbers):
    comp = Counter(numbers)
    total = sum(comp.values())
    return {k: v / total for k, v in comp.items()}

def get_conventional_cell(atoms: Atoms):
    cell = atoms.cell
    positions = atoms.get_scaled_positions()
    numbers = atoms.get_atomic_numbers()
    spg_cell = (cell, positions, numbers)
    conv = spglib.standardize_cell(spg_cell, to_primitive=False, no_idealize=False, symprec=1e-5)
    if conv is None:
        return None
    return Atoms(conv[2], scaled_positions=conv[1], cell=conv[0], pbc=True)

def test_primitive_vs_conventional(atoms: Atoms, index: int = 0):
    try:
        ase_conv = get_conventional_cell(atoms)
        ase_prim = to_primitive(StructureData(ase=atoms)).get_ase()

        if ase_conv is None or ase_prim is None:
            logger.warning(f"[{index}] One of cells is None")
            logger.info("-" * 60)
            return

        n_prim = len(ase_prim)
        n_conv = len(ase_conv)

        vol_prim = ase_prim.get_volume() / n_prim
        vol_conv = ase_conv.get_volume() / n_conv

        comp_prim = normalize_composition(ase_prim.get_atomic_numbers())
        comp_conv = normalize_composition(ase_conv.get_atomic_numbers())

        composition_match = np.allclose(
            [comp_prim.get(k, 0) for k in sorted(set(comp_prim) | set(comp_conv))],
            [comp_conv.get(k, 0) for k in sorted(set(comp_prim) | set(comp_conv))],
            atol=1e-3
        )

        spg_prim = spglib.get_symmetry_dataset((ase_prim.cell, ase_prim.get_scaled_positions(), ase_prim.get_atomic_numbers()))
        spg_conv = spglib.get_symmetry_dataset((ase_conv.cell, ase_conv.get_scaled_positions(), ase_conv.get_atomic_numbers()))

        reversible = True
        try:
            reconv = get_conventional_cell(ase_prim)
            reprim = to_primitive(StructureData(ase=ase_conv)).get_ase()
            reversible = reconv is not None and reprim is not None
        except Exception:
            reversible = False

        logger.info(f"[{index}] Structure test:")
        logger.info(f"Atoms: primitive={n_prim}, conventional={n_conv}")
        logger.info(f"Volume per atom: primitive={vol_prim:.4f}, conventional={vol_conv:.4f}")
        logger.info(f"Composition match: {composition_match}")
        logger.info(f"Space group: primitive={spg_prim['international']} ({spg_prim['number']}), "
                    f"conventional={spg_conv['international']} ({spg_conv['number']})")
        logger.info(f"Reversible transformation: {reversible}")

        composition_same = composition_match
        volume_ratio = abs(vol_prim - vol_conv) / min(vol_prim, vol_conv)
        volume_same = volume_ratio <= 0.5
        spg_same = (spg_prim['number'] == spg_conv['number'])
        reversible_same = reversible
        atoms_same = (n_prim == n_conv)

        if composition_same and volume_same and spg_same and reversible_same and atoms_same:
            logger.info("Same: all parameters match")
        else:
            logger.info("Different: parameters do not match")

        logger.info("-" * 60)

    except Exception as e:
        logger.error(f"[{index}] Error: {e}")
        logger.info(f"Anomaly: exception")
        logger.info("-" * 60)


if __name__ == "__main__":
    logger.info("Script started")
    N = 20
    for i in range(N):
        try:
            s = get_random_structuredata()
            test_primitive_vs_conventional(s, i + 1)
        except Exception as e:
            logging.error(f"[{i+1}] Failed to process structure: {e}")
