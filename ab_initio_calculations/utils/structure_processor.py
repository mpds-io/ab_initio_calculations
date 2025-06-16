import numpy as np
from ase import Atoms
from typing import Union, Tuple


def process_structures(structs: list[Atoms], response: list[list]) -> Union[Tuple[Atoms, str], Tuple[bool, bool]]:
    """Process structures from MPDS and return the best candidate
    
    Args:
        structs: List of ASE Atoms structures
        response: Raw response data from MPDS
        
    Returns:
        tuple: (selected structure, entry) or (False, False) if no suitable structure
    """
    if not structs:
        print("No structures!")
        return False, False
    
    # find struct with minimal number of atoms
    minimal_struct = min([len(s) for s in structs])
    minimal_structs = [s for s in structs if len(s) == minimal_struct]
    # find struct with median cell vectors
    cells = np.array([s.get_cell().reshape(9) for s in minimal_structs])
    median_cell = np.median(cells, axis=0)
    median_idx = int(np.argmin(np.sum((cells - median_cell) ** 2, axis=1) ** 0.5))
    
    # filter
    response = [item for item in response if item != []]
    occs_noneq = [[line[1]] for line in response][median_idx][0]
    
    # check: constant occupancy
    if any([occ for occ in occs_noneq if occ != 1]):
        for idx, res in enumerate(response):
            if all([item == 1 for item in res[1]]):
                entry = [line[:1] for line in response][idx][0]
                selected_struct = structs[idx]
                return selected_struct, entry
        print("No structures were found where all atoms have constant occupancy!")
        return False, False
    else:
        selected_struct = structs[median_idx]
        entry = [line[:1] for line in response][median_idx][0]
        return selected_struct, entry