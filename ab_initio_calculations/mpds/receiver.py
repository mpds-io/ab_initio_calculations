import io
import os
import shutil
import time

import py7zr
import requests
from mpds_client import MPDSDataRetrieval, MPDSDataTypes
from ab_initio_calculations.mpds.utils import get_props_folders_map
from mpds_client.errors import APIError
from ase import Atoms


def download_and_process_archives(arch_dir = "./mpds_archives/"):
    """Downloads MPDS archives, extracts and validates them."""
    mpds_api = MPDSDataRetrieval(dtype=MPDSDataTypes.AB_INITIO)
    result_count = {}

    for prop in get_props_folders_map().keys():
        cnt = 0
        try:
            entries = mpds_api.get_data({"props": prop}, fields={})
            len(entries)
        except:
            time.sleep(2)
            continue

        try:
            for entry in entries:
                archive_url = entry["sample"]["measurement"][0]["raw_data"]

                response = requests.get(archive_url)
                if response.status_code == 200:
                    curr_folder = arch_dir + prop + "/" + os.path.basename(archive_url)[:-3]
                    with py7zr.SevenZipFile(
                        io.BytesIO(response.content), mode="r"
                    ) as archive:
                        archive.extractall(path=curr_folder)
                    print(f"The archive {archive_url} is opening successfully")

                    if os.path.exists(curr_folder + "/" + get_props_folders_map()[prop]):
                        cnt += 1
                        shutil.rmtree(curr_folder)
                        os.makedirs(arch_dir + prop + "/true/", exist_ok=True)
                        with open(
                            arch_dir + prop + "/true/" + os.path.basename(archive_url), "wb"
                        ) as f:
                            f.write(response.content)
                    else:
                        shutil.rmtree(curr_folder)
                        os.makedirs(arch_dir + prop + "/false/", exist_ok=True)
                        with open(
                            arch_dir + prop + "/false/" + os.path.basename(archive_url),
                            "wb",
                        ) as f:
                            f.write(response.content)

                elif response.status_code == 400:
                    break
                else:
                    print(
                        f"Failed to load archive {archive_url}. Status:{response.status_code}"
                    )
            result_count[prop] = {"n_mpds_api": len(entries), "n_real": cnt}
            print("Result for current iteration: ", result_count[prop])
        except Exception as e:
            print(f"Error processing property{prop}: {e}")

    print("Result: ", result_count)
    

def download_structures(el: str = None, query_dict: dict = None) -> tuple[list[Atoms], list[list], str]:
    """Request structures from MPDS and return raw data
    
    Args:
        el: Element symbol (optional)
        query_dict: Custom query dictionary (optional)
        
    Returns:
        tuple: (list of ASE Atoms structures, raw response data, element symbol)
    """
    client = MPDSDataRetrieval(dtype=MPDSDataTypes.ALL)
    
    if not el:
        from utils import get_random_element  # here to avoid circular import issues
        el = get_random_element()
    if query_dict:
        try:
            response = client.get_data(query_dict, fields={
                "S": [
                    "entry",
                    "occs_noneq",
                    "cell_abc",
                    "sg_n",
                    "basis_noneq",
                    "els_noneq",
                ]
            })
            
            structs = [client.compile_crystal(line[2:], flavor="ase") for line in response]
            structs = list(filter(None, structs))
            
            return structs, response, el
        except APIError as e:
            print(f"[ERROR] MPDS API error for element {el} with custom query: {e}")
            return None, None, el
    
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
        
        return structs, response, el
        
    except APIError as e:
        print(f"[ERROR] MPDS API error for element {el}: {e}")
        return None, None, el
    
    
if __name__ == "__main__":
    # example
    download_and_process_archives(arch_dir="./mpds_archives/")
