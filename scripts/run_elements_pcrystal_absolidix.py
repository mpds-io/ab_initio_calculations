import asyncio
import io
import os
import random
import time

import ase
import ase.io
from absolidix_client import AbsolidixAPIAsync, AbsolidixTokenAuth

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.settings import Settings
from ab_initio_calculations.utils.chemical_utils import (
    get_list_of_basis_elements,
    guess_metal,
)
from ab_initio_calculations.utils.pcrystal_utils import Pcrystal_setup
from ab_initio_calculations.utils.structure_processor import process_structures
from yascheduler import Yascheduler

settings = Settings()
API_URL = "http://localhost:3000"
TARGET_ENGINE = "pcrystal"


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
    use_demo_template: bool = True,
):
    """Convert structures from ase.Atoms to Pcrystal input format (d12, fort.34)"""
    el_hight_tolinteg = ["Ta", "Se", "P"]

    for ase_obj in atoms_obj:

        if not (use_demo_template):
            is_metall = guess_metal(ase_obj)
            if is_metall:
                template = "pcrystal_metals_production.yml"
            else:
                template = "pcrystal_nonmetals_production.yml"
            setup = Pcrystal_setup(ase_obj, template)
        else:
            setup = Pcrystal_setup(ase_obj)

        if any([item in el_hight_tolinteg for item in list(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"][
                "TOLINTEG"
            ] = "8 8 8 8 16"

        elif any([item == "Sb" for item in list(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"][
                "TOLINTEG"
            ] = "10 10 10 10 16"

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


def run_with_custom_d12(
    pcrystal_input_dir: os.PathLike, el: str, use_demo_template: bool = True
):
    """Run task by the chain: MPDS -> create d12 -> Absolidix client"""
    structs, response, el = download_structures(el)
    if structs is None:
        return None, None
    atoms_obj, entry = process_structures(structs, response)

    if atoms_obj is None:
        print(f"[WARNING] Skipping element {el} due to missing data.")
        return

    with io.StringIO() as fd:
        ase.io.write(fd, atoms_obj, format="vasp")
        poscar_content = fd.getvalue()

    if atoms_obj:
        input, fort34 = convert_to_pcrystal_and_run(
            pcrystal_input_dir,
            [atoms_obj],
            entry,
            run_yascheduler=False,
            use_demo_template=use_demo_template,
        )
        asyncio.run(run_by_absolidix_client(input, fort34, poscar_content))


if __name__ == "__main__":
    # use templates for production
    use_demo_template = False

    for el in get_list_of_basis_elements():
        start_time = time.time()
        path = settings.pcrystal_input_dir
        run_with_custom_d12(path, el, use_demo_template)
        end_time = time.time()
        print("Success! Elapsed time: ", end_time - start_time)
