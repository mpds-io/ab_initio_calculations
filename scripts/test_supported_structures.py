
import os
import random

import numpy as np
from metis_backend.calculations import Calc_setup
from metis_backend.structures.cif_utils import cif_to_ase
from metis_backend.structures.struct_utils import refine
from mpds_client import MPDSDataRetrieval, MPDSDataTypes

from yascheduler import Yascheduler
import set_path
import ase

def get_random_element() -> list:
    """Return random chemical element for which there exists a basis"""
    files = [f.replace(".basis", "") for f in os.listdir(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "../basis_sets/MPDSBSL_NEUTRAL_24"
        )
    )]
    return files[random.randint(0, len(files))]


def get_structure_from_mpds(api_key: str) -> ase.Atoms:
    """Request structures from MPDS, convert to ase.Atoms, return median structure from all"""
    client = MPDSDataRetrieval(dtype=MPDSDataTypes.ALL, api_key=api_key)
    el = get_random_element()
    response = client.get_data(
        {
            "elements": el,
            "props": "atomic structure",
            "classes": "unary",
            "lattices": "cubic",
        },
        fields=
        {'S': [
                    'cell_abc',
                    'sg_n',
                    'basis_noneq',
                    'els_noneq'
                ]}
    )
    structs = [client.compile_crystal(line, flavor='ase') for line in response]
    structs = list(filter(None, structs))
    
    if not structs:
        print('No structures!')
    minimal_struct = min([len(s) for s in structs])

    # get structures with minimal number of atoms and find the one with median cell vectors
    cells = np.array([s.get_cell().reshape(9) for s in structs if len(s) == minimal_struct])
    median_cell = np.median(cells, axis=0)
    median_idx = int(np.argmin(np.sum((cells - median_cell) ** 2, axis=1) ** 0.5))
    
    selected_struct = structs[median_idx]
    
    return selected_struct


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
        {"fort.34": STRUCT_INPUT, "INPUT": SETUP_INPUT, "local_folder": None},
        "pcrystal",
    )
    print(label)
    print(result)


def convert_to_pcrystal_input(dir: str, atoms_obj: list[ase.Atoms]):
    """Convert structures from CIF file to Pcrystal input format (d12, fort.34)"""
    for idx, ase_obj in enumerate(atoms_obj):
        ase_obj, error = refine(ase_obj, conventional_cell=True)
        if error:
            raise RuntimeError(error)

        setup = Calc_setup()
        inputs, error = setup.preprocess(ase_obj, "pcrystal", "test " + str(idx + 1))
        if error:
            raise RuntimeError(error)

        subdir = os.path.join(dir, f"pcrystal_input_{ase_obj.get_chemical_formula()}")
        os.makedirs(subdir, exist_ok=True)

        input_file = os.path.join(subdir, f"input_{ase_obj.get_chemical_formula()}")
        fort_file = os.path.join(subdir, f"fort.34")

        with open(input_file, "w") as f_input:
            f_input.write(inputs["INPUT"])
        with open(fort_file, "w") as f_fort:
            f_fort.write(inputs["fort.34"])

        print(f"Data written to {input_file} and {fort_file}")
        submit_yascheduler_task(input_file)

if __name__ == "__main__":
    api_key = "KEY"
    pcrystal_input_dir = "./pcrystal_input"
    for i in range(20):
        atoms_obj = get_structure_from_mpds(
            api_key
        )
        convert_to_pcrystal_input(
            pcrystal_input_dir, [atoms_obj]
        )
