
import os
from mpds_client import APIError


from ab_initio_calculations.utils.pcrystal_utils import convert_to_pcrystal_input
from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.utils.chemical_utils import (
    get_list_of_basis_elements,
)
from ab_initio_calculations.utils.structure_processor import process_structures
from yascheduler import Yascheduler


def submit_yascheduler_task(input_file):
    """Give task to yascheduler"""
    target = os.path.abspath(input_file)
    work_folder = os.path.dirname(target)
    with open(target, encoding="utf-8") as f:
        SETUP_INPUT = f.read()

    f34_name = os.path.basename(target).split(".")[0] + ".f34"

    if os.path.exists(os.path.join(work_folder, "fort.34")):
        assert "EXTERNAL" in SETUP_INPUT
        with open(os.path.join(work_folder, "fort.34"), encoding="utf-8") as f:
            STRUCT_INPUT = f.read()
    elif os.path.exists(os.path.join(work_folder, f34_name)):
        assert "EXTERNAL" in SETUP_INPUT
        with open(os.path.join(work_folder, f34_name), encoding="utf-8") as f:
            STRUCT_INPUT = f.read()
    else:
        assert "EXTERNAL" not in SETUP_INPUT
        STRUCT_INPUT = "UNUSED"

    label = SETUP_INPUT.splitlines()[0]

    yac = Yascheduler()
    result = yac.queue_submit_task(
        label,
        {"fort.34": STRUCT_INPUT, "INPUT": SETUP_INPUT, "local_folder": work_folder},
        "pcrystal",
    )
    print(label)
    print(result)
    
def main():
    pcrystal_task_dir = "./pcrystal_tasks_yascheduler"
    for i in range(len(get_list_of_basis_elements())):
        for el in get_list_of_basis_elements():
            try:
                structs, response, el = download_structures(el)
                if structs is None:
                    print(f"[WARNING] Skipping element {el} due to missing data.")
                    continue
                atoms_obj, _ = process_structures(structs, response)

                if atoms_obj is None:
                    continue
                if atoms_obj:
                    task_path = convert_to_pcrystal_input(
                        pcrystal_task_dir, [atoms_obj], 'test_' + el
                    )
                    submit_yascheduler_task(task_path)
            except APIError as ex:
                if ex.code == 204:
                    pass


if __name__ == "__main__":
    main()