from aiida.plugins import DataFactory
from aiida.engine import submit
from mpds_aiida.workflows.aiida import AiidaStructureWorkChain
from absolidix_backend.structures.struct_utils import get_formula

from mpds_client import APIError

from ab_initio_calculations.mpds.receiver import download_structures
from data.ref_structures import reference_states

from ab_initio_calculations.utils.structure_processor import process_structures
from aiida import load_profile

load_profile()

def main():
    for row in reference_states:
        if row is None:
            continue
        try:    
            el = row.get('formula')
            sgs = row.get('sgs')
            
            if not el or not sgs:
                print(f"[WARNING] Skipping element with incomplete data: {row}")
                continue
            
            mpds_query = {
                "formulae": el,
                "sgs": sgs,
                "classes": "unary"
            }       
            structs, response, el = download_structures(el, mpds_query)
            if structs is None:
                print(f"[WARNING] Skipping element {el} due to missing data.")
                continue
            atoms_obj, entry = process_structures(structs, response)

            if atoms_obj is None:
                continue
            if atoms_obj:
                label = get_formula(atoms_obj) + '_' + entry 
                inputs = AiidaStructureWorkChain.get_builder()
                inputs.metadata.label = label
                inputs.structure = DataFactory('structure')(ase=atoms_obj)
                inputs.structure.label = label


                wc = submit(AiidaStructureWorkChain, **inputs)
                print("Submitted WorkChain %s" % wc.pk)

        except APIError as ex:
            if ex.code == 204:
                pass


if __name__ == "__main__":
    main()
