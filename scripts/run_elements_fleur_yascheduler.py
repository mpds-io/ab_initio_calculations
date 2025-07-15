import os
import time

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.settings import Settings
from ab_initio_calculations.utils.chemical_utils import \
    get_list_of_basis_elements
from ab_initio_calculations.utils.fleur_utils import Fleur_setup
from ab_initio_calculations.utils.structure_processor import process_structures
from yascheduler import Yascheduler

# set correct path here
os.environ['FLEUR_INPGEN_PATH'] = "/root/fleur/build/inpgen"
settings = Settings()
yac = Yascheduler()


def run_by_yascheduler(el: str):
    """Run task by the chain: MPDS -> create fleur input -> Yascheduler -> Fleur"""
    structs, response, el = download_structures(el)
    if structs is None:
        print(f"[WARNING] Skipping element {el} due to missing data.")
        return
    atoms_obj, _ = process_structures(structs, response)

    if atoms_obj is None:
        return

    setup = Fleur_setup(atoms_obj)
    error = setup.validate()

    inputs = {
        "inp.xml": setup.get_input_setup("fleur"),
    }
    if error:
        raise RuntimeError(error)

    print(inputs["inp.xml"])

    result = yac.queue_submit_task(
        str(atoms_obj.symbols),
        inputs,
        "fleur",
    )
    print(f"Task for {el} submitted with ID: {result}")
    
def main():
    """Main function to run the script for all elements."""
    for el in get_list_of_basis_elements():
        start_time = time.time()
        run_by_yascheduler(el)
        end_time = time.time()
        print(f"Success! Elapsed time for {el}: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()