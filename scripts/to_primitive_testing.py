import logging
import random
from collections import Counter

import numpy as np
import spglib
from aiida import load_profile
from ase import Atoms

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.utils.chemical_utils import (get_random_element,
                                                         to_primitive)

load_profile()

logger = logging.getLogger("cell_treatment")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler("cell_treatment_aiida_test.log", mode="w")
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

if logger.hasHandlers():
    logger.handlers.clear()

logger.addHandler(file_handler)


def get_random_structuredata():
    el = get_random_element()
    structs, _, _ = download_structures(el)
    struct = structs[random.randint(0, len(structs) - 1)]
    return struct


def normalize_composition(numbers):
    comp = Counter(numbers)
    total = sum(comp.values())
    return {k: v / total for k, v in comp.items()}


def get_conventional_cell(atoms: Atoms):
    cell = atoms.cell
    positions = atoms.get_scaled_positions()
    numbers = atoms.get_atomic_numbers()
    spg_cell = (cell, positions, numbers)
    conv = spglib.standardize_cell(
        spg_cell, to_primitive=False, no_idealize=False, symprec=1e-5
    )
    if conv is None:
        return None

    new_atoms = Atoms(conv[2], scaled_positions=conv[1], cell=conv[0], pbc=True)
    
    for key, value in atoms.info.items():
        new_atoms.info[key] = value
    
    for key in atoms.arrays:
        if key not in ['numbers', 'positions']:
            try:
                new_atoms.set_array(key, atoms.get_array(key).copy())
            except:
                pass
    
    if atoms.calc is not None:
        new_atoms.calc = atoms.calc
    
    return new_atoms

def test_primitive_vs_conventional(atoms: Atoms, index: int = 0):
    try:
        orig_info = atoms.info.copy()
        
        # fyi: original is alredy primitive
        ase_conv = get_conventional_cell(atoms)
        ase_prim = to_primitive(atoms) 

        if ase_conv is None or ase_prim is None:
            logger.warning(f"[{index}] One of cells is None")
            logger.info("-" * 60)
            return

        n_orig = len(atoms)
        n_prim = len(ase_prim)
        n_conv = len(ase_conv)

        vol_orig = atoms.get_volume() / n_orig
        vol_prim = ase_prim.get_volume() / n_prim
        vol_conv = ase_conv.get_volume() / n_conv

        comp_orig = normalize_composition(atoms.get_atomic_numbers())
        comp_prim = normalize_composition(ase_prim.get_atomic_numbers())

        # check if original matches primitive
        prim_match = (
            n_orig == n_prim
            and np.isclose(vol_orig, vol_prim, atol=1e-3)
            and comp_orig == comp_prim
        )

        reversible = True
        recovered_prim = None
        recovered_prim_match = False
        try:
            # transform back to primitive
            recovered_prim = to_primitive(ase_conv)
            if recovered_prim is not None:
                n_reprim = len(recovered_prim)
                vol_reprim = recovered_prim.get_volume() / n_reprim
                comp_reprim = normalize_composition(recovered_prim.get_atomic_numbers())
                
                # compare recovered primitive with original
                recovered_prim_match = (
                    n_orig == n_reprim
                    and np.isclose(vol_orig, vol_reprim, atol=1e-3)
                    and comp_orig == comp_reprim
                )
            else:
                reversible = False
        except Exception:
            reversible = False
            recovered_prim_match = False

        # check if info matches
        info_match_prim = ase_prim.info == orig_info
        info_match_conv = ase_conv.info
        info_match_recovered = recovered_prim is not None and recovered_prim.info == orig_info
        

        logger.info(f"[{index}] Structure test:")
        logger.info(f"Atoms: original={n_orig}, primitive={n_prim}, conventional={n_conv}")
        logger.info(
            f"Volume per atom: orig={vol_orig:.4f}, prim={vol_prim:.4f}, conv={vol_conv:.4f}"
        )
        logger.info(f"Original matches primitive: {prim_match}")
        logger.info(f"Reversible transformation: {reversible}")
        logger.info(f"Recovered primitive matches original: {recovered_prim_match}")
        logger.info(f"Metadata preserved: primitive={info_match_prim}, conventional={info_match_conv}, recovered={info_match_recovered}")

        # check space groups
        spg_orig = spglib.get_symmetry_dataset(
            (atoms.cell, atoms.get_scaled_positions(), atoms.get_atomic_numbers())
        )
        spg_prim = spglib.get_symmetry_dataset(
            (ase_prim.cell, ase_prim.get_scaled_positions(), ase_prim.get_atomic_numbers())
        )
        spg_conv = spglib.get_symmetry_dataset(
            (ase_conv.cell, ase_conv.get_scaled_positions(), ase_conv.get_atomic_numbers())
        )

        spg_orig_num = spg_orig['number'] if spg_orig is not None else None
        spg_prim_num = spg_prim['number'] if spg_prim is not None else None
        spg_conv_num = spg_conv['number'] if spg_conv is not None else None

        logger.info(
            f"Space groups: orig={spg_orig_num}, prim={spg_prim_num}, conv={spg_conv_num}"
        )

        spg_match = (spg_orig_num == spg_prim_num == spg_conv_num) and (spg_orig_num is not None)

        if prim_match and recovered_prim_match and spg_match and info_match_prim and info_match_conv and info_match_recovered:
            logger.info("SUCCESS: All transformations consistent")
        else:
            logger.warning("WARNING: Inconsistencies detected")
            if not prim_match:
                logger.warning(" - Original and primitive cells differ")
            if not recovered_prim_match:
                logger.warning(" - Recovered primitive doesn't match original")
            if not spg_match:
                logger.warning(" - Space group mismatch")
            if not info_match_prim:
                logger.warning(" - Metadata mismatch in primitive cell")
            if not info_match_conv:
                logger.warning(" - Metadata mismatch in conventional cell")
            if not info_match_recovered:
                logger.warning(" - Metadata mismatch in recovered primitive")

        logger.info("-" * 60)

    except Exception as e:
        logger.error("Anomaly: exception")
        logger.error(f"[{index}] Error: {e}")
        logger.error("-" * 60)


if __name__ == "__main__":
    for i in range(20):
        try:
            struct = get_random_structuredata()
            test_primitive_vs_conventional(struct, i + 1)
        except Exception as e:
            logging.error(f"[{i+1}] Failed to process structure: {e}")
