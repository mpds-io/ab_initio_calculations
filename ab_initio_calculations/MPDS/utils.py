import requests

def get_props_names_mpds() -> list:
    """
    Get all avalible properties names in MPDS database
    """
    url = 'https://mpds.io/wmdata.json'
    res = requests.get(url).json()
    props = res['props']
    return props
    
