#!/usr/bin/env python3

import os
import random
from mpds_client import MPDSDataRetrieval, MPDSDataTypes
import requests
from yascheduler import Yascheduler

import set_path
from metis_backend.structures.struct_utils import refine
from metis_backend.structures.cif_utils import cif_to_ase
from metis_backend.calculations import Calc_setup


def get_random_element() -> list:
    files = [f.replace('.basis', '') for f in os.listdir('/MPDSBSL_NEUTRAL_24')]
    return files[random.randint(0, len(files))]

def get_structure_from_mpds(api_key: str, num: int, cif_dir: str) -> list[str]:
    file_names = []
    mpds_api = MPDSDataRetrieval(dtype=MPDSDataTypes.ALL, api_key=api_key)
    response = mpds_api.get_data({
        'elements': get_random_element(), 
        'props': "structural properties", 
        "classes": "unary", 
        "lattices": "cubic"}, fields={})
    if len(response) >= num:
        response = response[:num]
    
    for entry in response:  
        url = f"https://api.mpds.io/v0/download/s?q={entry['entry']}&fmt=cif&sid={sid}&export=1&ed=0"  
        cif_response = requests.get(url)
        if cif_response.status_code == 200:
            filename = f"{entry['entry']}.cif"
            with open(cif_dir + '/' + filename, "wb") as file:
                file.write(cif_response.content)
            print(f"File {filename} saved!")
            file_names.append(filename)
        else:
            print(f"Error {response.status_code}: {response.text}")
            
    return file_names

def submit_yascheduler_task(input_file):
    target = os.path.abspath(input_file)
    work_folder = os.path.dirname(target)
    with open(target, encoding="utf-8") as f:
        SETUP_INPUT = f.read()

    f34_name = os.path.basename(target).split('.')[0] + '.f34' 

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
            
def convert_to_pcrystal_input(dir: str, file_names: list):
    for idx, file in enumerate(file_names):
        structure = open(os.path.join(dir, file)).read()
        ase_obj, error = cif_to_ase(structure)
        ase_obj, error = refine(ase_obj, conventional_cell=True)
        if error:
            raise RuntimeError(error)

        setup = Calc_setup()
        inputs, error = setup.preprocess(ase_obj, 'pcrystal', 'test ' + str(idx + 1))
        if error:
            raise RuntimeError(error)

        print(inputs['INPUT'])
        print('=' * 100)
        print(inputs['fort.34'])
        
        subdir = os.path.join(dir, f"pcrystal_input_{file.replace('.cif', '')}")
        os.makedirs(subdir, exist_ok=True)
        
        input_file = os.path.join(subdir, f"input_{file.replace('.cif', '')}")
        fort_file = os.path.join(subdir, f"fort.34")

        with open(input_file, 'w') as f_input:
            f_input.write(inputs['INPUT'])
        with open(fort_file, 'w') as f_fort:
            f_fort.write(inputs['fort.34'])

        print(f"Data written to {input_file} and {fort_file}")
        submit_yascheduler_task(input_file)
        

    
if __name__ == "__main__":
    sid = "SID"
    api_key='KEY'
    files = get_structure_from_mpds(api_key, 2, 'cif_dir')
    convert_to_pcrystal_input('cif_dir', files)
