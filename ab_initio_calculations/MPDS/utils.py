from math import log

import numpy as np
import requests

ab_props_mapping = {
    "electrical conductivity": "TRANSPORT/SIGMA.DAT",
    "Seebeck coefficient": "TRANSPORT/SEEBECK.DAT",
    "enthalpy of formation": "HFORM",
    "vibrational spectra": "PHONON",
    "infrared spectra": "PHONON",
    "Raman spectra": "PHONON",
    "heat capacity at constant pressure": "PHONON",
    "isothermal bulk modulus": "ELASTIC",
    "poisson ratio": "ELASTIC",
    "effective charge": "STRUCT",
    "energy gap for direct transition": "STRUCT",
    "energy gap for indirect transition": "STRUCT",
    "energy gap": "STRUCT",
    "magnetic moment": "STRUCT",
}


def get_props_folders_map() -> dict:
    return ab_props_mapping


def get_props_names_mpds() -> list:
    """
    Get all avalible properties names from the MPDS database
    """
    url = "https://mpds.io/wmdata.json"
    res = requests.get(url).json()
    props = res["props"]
    return props


def get_ab_initio_props_names_mpds() -> list:
    return list(ab_props_mapping.keys())


def assert_conforming_input(content):
    return (
        "PBE0" in content
        and "XLGRID" in content
        and "TOLLDENS\n8" in content
        and "TOLLGRID\n16" in content
        and "TOLDEE\n9" in content
    )


def get_raw_input_type(string):
    if "MOLECULE" in string:
        return "ISLD_ATOM"
    elif "FREQCALC" in string:
        return "PHONON"
    elif "ELASTCON" in string or "ELAPIEZO" in string:
        return "ELASTIC"
    elif "OPTGEOM" in string:
        return "STRUCT"
    else:
        return None


def get_raw_output_type(parser):
    if parser.info["periodicity"] == 0x5:
        return "ISLD_ATOM"
    elif parser.phonons["modes"]:
        return "PHONON"
    elif parser.elastic.get("K"):
        return "ELASTIC"
    elif parser.tresholds:
        return "STRUCT"
    else:
        return None


def get_input_precision(string):
    try:
        tol = tuple(
            [
                -int(x)
                for x in string.split("TOLINTEG")[-1].strip().split("\n")[0].split()
            ]
        )
    except:
        tol = (-6, -6, -6, -6, -12)  # default for CRYSTAL09-17
    try:
        kset = int(string.split("SHRINK")[-1].strip().split()[0])
    except:
        kset = None  # molecule or isolated atom
    kset = tuple([kset] * 3)
    return tol, kset


def get_input_spin(string):
    spin = string.split("SPINLOCK")[-1].strip().split("\n")[0].strip().split()
    # assert int(spin[1]) > 50
    return int(spin[0])


def get_basis_fingerprint(basis_set):

    multipliers = {
        "S": 10,
        "SP": 100,
        "P": 1000,
        "D": 10000,
        "F": 10000,
        "G": 10000,
        "H": 10000,
    }
    bs_fgpt = {}

    for el in basis_set:
        bs_repr = []
        for channel in basis_set[el]:
            bs_repr.append([])
            for coeffs in channel[1:]:
                bs_repr[-1].append(
                    sum([round(coeff, 1) * multipliers[channel[0]] for coeff in coeffs])
                )
            bs_repr[-1] = sum(bs_repr[-1])
        if sum(bs_repr) == 0:
            bs_repr = [1]  # gives fgpt = 0
        bs_fgpt[el] = int(round(log(sum(bs_repr)) * 10000))

    return tuple(
        sorted([(key, value) for key, value in bs_fgpt.items()], key=lambda x: x[0])
    )


def ase_to_optimade(ase_obj, name_id=None):
    result = dict(id=name_id, attributes={}, links=dict(self=None), type="structures")
    result["attributes"]["immutable_id"] = name_id
    result["attributes"]["lattice_vectors"] = np.round(ase_obj.cell, 4).tolist()
    result["attributes"]["cartesian_site_positions"] = []
    result["attributes"]["species_at_sites"] = []
    for atom in ase_obj:
        result["attributes"]["cartesian_site_positions"].append(
            np.round(atom.position, 4).tolist()
        )
        result["attributes"]["species_at_sites"].append(atom.symbol)
    return dict(data=[result])
