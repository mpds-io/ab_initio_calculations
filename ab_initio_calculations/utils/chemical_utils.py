import os
import random
from copy import deepcopy

import numpy as np
import spglib
from ase.atoms import Atoms

from ab_initio_calculations.settings import Settings

settings = Settings()


def get_list_of_basis_elements() -> list:
    """Return list with chemical elements with existing basis"""
    dir = settings.basis_sets_dir

    files = [
        f.replace(".basis", "")
        for f in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
        )
    ]
    return files


def get_random_element() -> list:
    """Return random chemical element for which there exists a basis"""
    dir = settings.basis_sets_dir

    files = [
        f.replace(".basis", "")
        for f in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
        )
    ]
    return random.choice(files)


def define_same_structures(structures: list[dict]) -> list[dict]:
    """Define structures with same chemical formula and space group"""
    sg_n_set = list(set([i["sg_n"] for i in structures]))
    chem_formula_set = list(set([i["chemical_formula"] for i in structures]))

    curr_sg_n, curr_chem_form = sg_n_set[0], chem_formula_set[0]

    same_structures = [
        struct
        for struct in structures
        if struct["sg_n"] == curr_sg_n and struct["chemical_formula"] == curr_chem_form
    ]
    return same_structures


def guess_metal(ase_obj) -> bool:
    """
    Make an educated guess of the metallic compound character,
    returns bool
    """
    non_metallic_atoms = {
    'H',                                  'He',
    'Be',   'B',  'C',  'N',  'O',  'F',  'Ne',
                  'Si', 'P',  'S',  'Cl', 'Ar',
                  'Ge', 'As', 'Se', 'Br', 'Kr',
                        'Sb', 'Te', 'I',  'Xe',
                              'Po', 'At', 'Rn',
                                          'Og'
    }
    return not any(
        [el for el in set(ase_obj.get_chemical_symbols()) if el in non_metallic_atoms]
    )


def to_primitive(structure: Atoms, symprec=1e-5):
    """
    Convert ASE structure to primitive cell using spglib with preservation of atomic properties.
    
    Args:
        structure: ASE Atoms object
        symprec: Precision for symmetry detection (default: 1e-5)
        
    Returns:
        Primitive ASE Atoms object with preserved properties or None if failed
    """
    # here find primitive cell
    result = spglib.find_primitive(structure, symprec=symprec)
    if result is None:
        return None
    cell, positions, numbers = result
    prim_cart = np.dot(positions, cell)  # convert to cartesian coord
    
    # prepare original structure data
    orig_cell = structure.get_cell()
    orig_scaled = structure.get_scaled_positions()
    orig_numbers = structure.get_atomic_numbers()
    
    # calculate frac coord of prim atoms in original cell basis
    inv_orig_cell = np.linalg.inv(orig_cell.T)
    prim_in_orig_scaled = np.dot(prim_cart, inv_orig_cell)
    
    # find map between primitive and original atoms
    mapping = []
    for j in range(len(numbers)):
        found = False
        for i in range(len(structure)):
            # skip if atomic numbers dont match
            if numbers[j] != orig_numbers[i]:
                continue
                
            # calculate fractional coordinate difference
            diff = orig_scaled[i] - prim_in_orig_scaled[j]
            diff -= np.round(diff)  # wrap to [-0.5, 0.5)
            
            # convert to Cartesian distance
            diff_cart = np.dot(diff, orig_cell)
            distance = np.linalg.norm(diff_cart)
            
            if distance < symprec:
                mapping.append(i)
                found = True
                break
        
        if not found:
            raise RuntimeError(f"Atom mapping failed at index {j}. Try increasing symprec.")

    prim_atoms = Atoms(
        numbers=numbers,
        scaled_positions=positions,
        cell=cell,
        pbc=True,
        info=deepcopy(structure.info)
    )
    
    # copy per atom properties
    for key in structure.arrays:
        if key not in ['positions', 'numbers']:
            arr = structure.arrays[key]
            if len(arr) == len(structure):
                prim_atoms.set_array(key, arr[mapping].copy())
    
    return prim_atoms