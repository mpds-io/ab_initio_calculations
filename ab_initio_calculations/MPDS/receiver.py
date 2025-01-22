
import io
import os
import requests
import io       
import py7zr
import shutil

import time
import requests
from mpds_client import MPDSDataRetrieval, MPDSDataTypes
from utils import get_props_folders_map


arch_dir = "./mpds_archives/"
mpds_api = MPDSDataRetrieval(dtype=MPDSDataTypes.AB_INITIO, api_key='KEY')
result_counter = {}

for prop in get_props_folders_map().keys():
    cnt = 0
    try:
        entrys = mpds_api.get_data({'props': prop}, fields={})
        len(entrys)
    except:
        time.sleep(2)
        continue

    try:
        for entry in entrys:
            archive_url = entry['sample']['measurement'][0]['raw_data'] 

            response = requests.get(archive_url)
            if response.status_code == 200:
                curr_folder = arch_dir + prop + '/' + os.path.basename(archive_url)[:-3]
                with py7zr.SevenZipFile(io.BytesIO(response.content), mode='r') as archive:
                    archive.extractall(path=curr_folder)  
                print(f"The archive {archive_url} is opening successfully")
                
                if os.path.exists(curr_folder + '/' + get_props_folders_map()[prop]):
                    cnt += 1    
                    shutil.rmtree(curr_folder)
                    os.makedirs(arch_dir + prop + '/true/', exist_ok=True)
                    with open(arch_dir + prop + '/true/' + os.path.basename(archive_url), 'wb') as f:
                        f.write(response.content)
                else:
                    shutil.rmtree(curr_folder)
                    os.makedirs(arch_dir + prop + '/false/', exist_ok=True)
                    with open(arch_dir + prop + '/false/' + os.path.basename(archive_url), 'wb') as f:
                        f.write(response.content)
                
            elif response.status_code == 400:
                break
            else:
                print(f"Failed to load archive {archive_url}. Status:{response.status_code}")
        result_counter[prop] = {"n_mpds_api": len(entrys), "n_real": cnt}
        print('Result for current iteration: ', result_counter[prop])
    except Exception as e:
        print(f"Error processing property{prop}: {e}")
        
print('Result: ', result_counter)

        