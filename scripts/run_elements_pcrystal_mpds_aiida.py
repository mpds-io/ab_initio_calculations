from aiida.plugins import DataFactory
from aiida.engine import submit
from mpds_aiida.workflows.aiida import AiidaStructureWorkChain
from absolidix_backend.structures.struct_utils import get_formula
import yaml

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
        if el in [
                    'Ta', 'Se', 'P',    # el_hight_tolinteg 
                    'C', 'Ag', 'Mg', 'Tc', 'Ni', 'Sb', 'Pr', 
                    'Mn', 'Fe', 'Ru', 'V',  
                    'Co', 'Cr',         
                    'Es'               
                ]:
            continue
        try:            
            structs, response, el = download_structures(el)
            if structs is None:
                print(f"[WARNING] Skipping element {el} due to missing data.")
                continue
            atoms_obj, entry = process_structures(structs, response)

            if atoms_obj is None:
                continue
            if atoms_obj:
                label = get_formula(atoms_obj) + '_test_ePBE0_23jan_2_' + entry 
                inputs = AiidaStructureWorkChain.get_builder()
                with open(f'/root/projects/mpds-aiida/mpds_aiida/calc_templates/ePBE0.yml') as f:
                    inputs.workchain_options = yaml.load(f.read(), Loader=yaml.SafeLoader)

                inputs.metadata.label = label

                inputs.structure = DataFactory('structure')(ase=atoms_obj)

                wc = submit(AiidaStructureWorkChain, **inputs)
                
                print("Submitted WorkChain %s" % wc.pk)

        except APIError as ex:
            if ex.code == 204:
                pass


if __name__ == "__main__":
    main()
