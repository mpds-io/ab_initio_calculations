import asyncio
import time

from absolidix_client import AbsolidixAPIAsync, AbsolidixTokenAuth

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.settings import Settings
from ab_initio_calculations.utils.chemical_utils import get_list_of_basis_elements, get_poscar_content
from ab_initio_calculations.utils.structure_processor import process_structures
from yascheduler import Yascheduler

API_URL = "http://localhost:3000"

settings = Settings()
yac = Yascheduler()


async def create_calc_and_get_results(client: AbsolidixAPIAsync, poscar_content: str):
    "Create data source, run calculation and wait for the results"

    data = await client.v0.datasources.create(poscar_content)
    assert data

    results = await client.v0.calculations.create_get_results(
        data["id"], engine="fleur"
    )
    print(results)
    assert results


async def start_absolidix_calculation(poscar_content):
    """Start calculation using Absolidix client"""

    async with AbsolidixAPIAsync(
        API_URL, auth=AbsolidixTokenAuth("admin@test.com")
    ) as client:
        print(await client.v0.auth.whoami())
        print(
            "The following engines are available:",
            await client.calculations.supported(),
        )
        await create_calc_and_get_results(client, poscar_content)


def run_by_absolidix(el: str):
    """Run task by the chain: MPDS -> Absolidix -> Fleur -> Absolidix"""
    structs, response, el = download_structures(el)
    if structs is None:
        print(f"[WARNING] Skipping element {el} due to missing data.")
        return
    atoms_obj, _ = process_structures(structs, response)

    if atoms_obj is None:
        return

    poscar_content = get_poscar_content(atoms_obj)
    asyncio.run(start_absolidix_calculation(poscar_content))


def main():
    """Main function to run the script for all elements."""
    for el in get_list_of_basis_elements():
        start_time = time.time()
        run_by_absolidix(el)
        end_time = time.time()
        print(f"Success! Elapsed time for {el}: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
