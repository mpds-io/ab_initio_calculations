import time

from absolidix_backend.calculations import Calc_setup

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.settings import Settings
from ab_initio_calculations.utils.chemical_utils import get_list_of_basis_elements
from ab_initio_calculations.utils.structure_processor import process_structures
from yascheduler import Yascheduler

settings = Settings()
yac = Yascheduler()


def run_by_yascheduler(el: str):
    """Run task by the chain: MPDS -> create fleur input -> Yascheduler -> Fleur"""
    structs, response, el = download_structures(el)
    if structs is None:
        return None, None
    atoms_obj, _ = process_structures(structs, response)

    if atoms_obj is None:
        print(f"[WARNING] Skipping element {el} due to missing data.")
        return

    setup = Calc_setup()
    inputs, error = setup.preprocess(atoms_obj, "fleur", "AiiDA test")
    if error:
        raise RuntimeError(error)

    print(inputs["inp.xml"])

    result = yac.queue_submit_task(
        str(atoms_obj.symbols),
        inputs,
        "fleur",
    )
    print(f"Task for {el} submitted with ID: {result}")


if __name__ == "__main__":
    for el in get_list_of_basis_elements():
        start_time = time.time()
        path = settings.pcrystal_input_dir
        run_by_yascheduler(el)
        end_time = time.time()
        print("Success! Elapsed time: ", end_time - start_time)
