from aiida.plugins import DataFactory
from aiida.engine import submit
from mpds_aiida.workflows.aiida import AiidaStructureWorkChain
from absolidix_backend.structures.struct_utils import get_formula

from mpds_client import APIError

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.utils.chemical_utils import (
    get_list_of_basis_elements,
)
from ab_initio_calculations.utils.structure_processor import process_structures
from aiida import load_profile

load_profile()

def main():
    for el in get_list_of_basis_elements():
        try:            
            structs, response, el = download_structures(el)
            if structs is None:
                print(f"[WARNING] Skipping element {el} due to missing data.")
                continue
            atoms_obj, entry = process_structures(structs, response)

            if atoms_obj is None:
                continue
            if atoms_obj:
                label = get_formula(atoms_obj) + entry 
                inputs = AiidaStructureWorkChain.get_builder()
                inputs.metadata = dict(label=label)
                inputs.structure = DataFactory('structure')(ase=atoms_obj)

                wc = submit(AiidaStructureWorkChain, **inputs)
                print("Submitted WorkChain %s" % wc.pk)

        except APIError as ex:
            if ex.code == 204:
                pass


if __name__ == "__main__":
    main()
