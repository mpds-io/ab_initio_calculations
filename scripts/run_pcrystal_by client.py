import asyncio
import io
import os
import random

import ase
import ase.io
import numpy as np
import yaml
from absolidix_backend.calculations import Pcrystal_setup
from absolidix_client import AbsolidixAPIAsync, AbsolidixTokenAuth
from mpds_client import APIError, MPDSDataRetrieval, MPDSDataTypes
from yascheduler import Yascheduler

CONF = "./ab_initio_calculations/conf/conf.yaml"
API_URL = "http://localhost:3000"
TARGET_ENGINE = "pcrystal"


def get_list_of_basis_elements() -> list:
    """Return list with chemical elements with existing basis"""
    with open(CONF, "r") as file:
        dir = yaml.safe_load(file)["basis_sets_path"]

    files = [
        f.replace(".basis", "")
        for f in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
        )
    ]
    return files


def get_random_element() -> list:
    """Return random chemical element for which there exists a basis"""
    with open(CONF, "r") as file:
        dir = yaml.safe_load(file)["basis_sets_path"]

    files = [
        f.replace(".basis", "")
        for f in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
        )
    ]
    return random.choice(files)


def get_structure_from_mpds(el: str = None) -> ase.Atoms:
    """Request structures from MPDS, convert to ase.Atoms, return median structure from all"""
    client = MPDSDataRetrieval(dtype=MPDSDataTypes.ALL)

    if not (el):
        el = get_random_element()
    try:
        response = client.get_data(
            {
                "elements": el,
                "props": "atomic structure",
                "classes": "unary",
                "lattices": "cubic",
            },
            fields={
                "S": [
                    "entry",
                    "occs_noneq",
                    "cell_abc",
                    "sg_n",
                    "basis_noneq",
                    "els_noneq",
                ]
            },
        )
        structs = [client.compile_crystal(line[2:], flavor="ase") for line in response]
        structs = list(filter(None, structs))

        if not structs:
            print("No structures!")

        minimal_struct = min([len(s) for s in structs])

        # get structures with minimal number of atoms and find the one with median cell vectors
        cells = np.array(
            [s.get_cell().reshape(9) for s in structs if len(s) == minimal_struct]
        )
        median_cell = np.median(cells, axis=0)
        median_idx = int(np.argmin(np.sum((cells - median_cell) ** 2, axis=1) ** 0.5))

        response = [i for i in response if i != []]
        occs_noneq = [[line[1]] for line in response][median_idx][0]

        # check: all atoms have constant occupancy
        if any([occ for occ in occs_noneq if occ != 1]):
            for idx, res in enumerate(response):
                if all([i == 1 for i in res[1]]):
                    entry = [line[:1] for line in response][idx][0]
                    selected_struct = structs[idx]
                    return [selected_struct, entry]
            print("No structures were found where all atoms have constant occupancy!")
            return [False, False]
        else:
            selected_struct = structs[median_idx]
            entry = [line[:1] for line in response][median_idx][0]
            return [selected_struct, entry]
    except APIError as e:
        print(f"[ERROR] MPDS API error for element {el}: {e}")
        return None, None


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
        TARGET_ENGINE,
    )
    print(label)
    print(result)


def convert_to_pcrystal_and_run(
    dir: str,
    atoms_obj: list[ase.Atoms],
    entry: str = None,
    run_yascheduler: bool = False,
):
    """Convert structures from ase.Atoms to Pcrystal input format (d12, fort.34)"""
    el_hight_tolinteg = ["Ta", "Se", "P"]

    for ase_obj in atoms_obj:
        setup = Pcrystal_setup(ase_obj)
        if any([i in el_hight_tolinteg for i in list(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = (
                "8 8 8 8 16"
            )
        elif any([i == "Sb" for i in list(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = (
                "10 10 10 10 16"
            )
        input = setup.get_input_setup("test " + entry)
        fort34 = setup.get_input_struct()

        subdir = os.path.join(
            dir, f"pcrystal_input_{ase_obj.get_chemical_formula()}_{entry}"
        )
        os.makedirs(subdir, exist_ok=True)

        input_file = os.path.join(
            subdir, f"input_{ase_obj.get_chemical_formula()}_{entry}"
        )
        fort_file = os.path.join(subdir, f"fort.34")

        with open(input_file, "w") as f_input:
            f_input.write(input)
        with open(fort_file, "w") as f_fort:
            f_fort.write(fort34)

        print(f"Data written to {input_file} and {fort_file}")

        if run_yascheduler:
            submit_yascheduler_task(input_file)

        return input, fort34


async def create_calc_and_get_results(
    client: AbsolidixAPIAsync, poscar_content: str, input: list
):
    "Create data source, run calculation and wait for the results"

    data = await client.v0.datasources.create(poscar_content)
    assert data

    results = await client.v0.calculations.create_get_results(
        data["id"], engine=TARGET_ENGINE, input=input
    )
    print(results)
    assert results
    print("=" * 50 + "Test passed")


async def run_by_absolidix_client(input, fort34, poscar_content):
    """Run task by the chain: MPDS -> create POSCAR -> Absolidix client"""
    content = [input, fort34]

    async with AbsolidixAPIAsync(
        API_URL, auth=AbsolidixTokenAuth("admin@test.com")
    ) as client:
        print(await client.v0.auth.whoami())
        print(
            "The following engines are available:",
            await client.calculations.supported(),
        )
        await create_calc_and_get_results(client, poscar_content, content)


def run_with_custom_d12(pcrystal_input_dir: os.PathLike, el: str):
    """Run task by the chain: MPDS -> create d12 -> Absolidix client"""
    atoms_obj, entry = get_structure_from_mpds(el)
    if atoms_obj is None:
        print(f"[WARNING] Skipping element {el} due to missing data.")
        return

    with io.StringIO() as fd:
        ase.io.write(fd, atoms_obj, format="vasp")
        poscar_content = fd.getvalue()

    if atoms_obj:
        input, fort34 = convert_to_pcrystal_and_run(
            pcrystal_input_dir, [atoms_obj], entry, run_yascheduler=False
        )
        asyncio.run(run_by_absolidix_client(input, fort34, poscar_content))


if __name__ == "__main__":
    for el in get_list_of_basis_elements():
        path = "./pcrystal_input"
        run_with_custom_d12(path, el)
