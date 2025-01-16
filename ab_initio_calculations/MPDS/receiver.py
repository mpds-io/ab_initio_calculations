
import io
import os
import requests
import io       
import py7zr

import time
import requests
from mpds_client import MPDSDataRetrieval, MPDSDataTypes
from utils import get_props_names_mpds


mpds_api = MPDSDataRetrieval(dtype=MPDSDataTypes.AB_INITIO, api_key='KEY')

for prop in get_props_names_mpds():
    try:
        entrys = mpds_api.get_data({'props': prop}, fields={})
    except:
        time.sleep(2)
        continue

    try:
        for entry in entrys:
            archive_url = entry['sample']['measurement'][0]['raw_data'] 

            response = requests.get(archive_url)
            if response.status_code == 200:
                with py7zr.SevenZipFile(io.BytesIO(response.content), mode='r') as archive:
                    archive.extractall(path='data/'+prop+'/'+os.path.basename(archive_url)[:-3])  
                print(f"The archive {archive_url} is opening successfully")
            elif response.status_code == 400:
                break
            else:
                print(f"Failed to load archive {archive_url}. Status:{response.status_code}")
    except Exception as e:
        print(f"Error processing property{prop}: {e}")
        