# This script is emplemented to run the calculations elements via AiiDA-Fleur
# It`s expected to be used for testing or educations purposes
# Is is expected that the user has already set up the AiiDA-Fleur environment
import os
import random

import ase
import numpy as np
from aiida import load_profile
from aiida.engine import submit
from aiida.orm import Dict, QueryBuilder, StructureData, load_node
from aiida.orm.nodes.data.code import Code
from aiida_fleur.workflows.relax import FleurRelaxWorkChain
from mpds_client import APIError, MPDSDataRetrieval, MPDSDataTypes

load_profile()

INPGEN_LABEL = "inpgen"
FLEUR_LABEL = "fleur"

CHEMICAL_ELEMENTS = [
    'Li', 'Be', 'B', 'C', 'N', 'O', 'F',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl',
    'K', 'Ca', 'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se',
    'Rb', 'Sr', 'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
    'In', 'Sn', 'Sb', 'Te', 'I',
]


# Relaxation parameters
WF_RELAX = Dict(
    dict={
        "film_distance_relaxation": False,
        "force_criterion": 0.049,  # Convergence threshold (eV/Å)
        "relax_iter": 10,  # Maximum relaxation steps
    }
)

# SCF calculation parameters
WF_PARAMETERS = Dict(
    dict={
        "fleur_runmax": 10,  # Max SCF cycles
        "itmax_per_run": 100,  # Max iterations per SCF
        "energy_converged": 0.0001,  # Energy convergence (eV)
        "mode": "energy",  # Convergence criterion
        "force_dict": {  # Force mixing parameters
            "qfix": 2,
            "forcealpha": 0.5,
            "forcemix": "straight",
        },
    }
)

# Computational resource configuration
OPTIONS = Dict(
    dict={
        "resources": {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
            "num_cores_per_mpiproc": 4,
        },
        "queue_name": "devel",
        "max_wallclock_seconds": 10 * 60 * 6000,  # 10 hours
    }
)


def find_nodes(fleur_node_label, inpgen_node_label):
    qb = QueryBuilder()
    qb.append(
        Code, filters={"label": {"in": [fleur_node_label, inpgen_node_label]}}
    )  # noqa: E501
    nodes = qb.all()

    if not nodes:
        raise ValueError("No Fleur or inpgen codes found in the database")

    data = {}
    for node in nodes:
        data[node[0].label] = node[0].pk
    return data


# (Took it) from Alina`s code
def get_structure_from_mpds(el: str) -> ase.Atoms:
    """Request structures from MPDS, convert to ase.Atoms, return median structure from all"""

    api_key = os.getenv("MPDS_KEY")
    if not api_key:
        raise Exception(
            "MPDS API key not found. Please set the MPDS_KEY environment variable."
        )

    client = MPDSDataRetrieval(dtype=MPDSDataTypes.ALL, api_key=api_key)

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
        structs = [
            client.compile_crystal(line[2:], flavor="ase") for line in response
        ]
        structs = list(filter(None, structs))

        if not structs:
            print("No structures!")

        minimal_struct = min([len(s) for s in structs])

        # get structures with minimal number of atoms and find the one with median cell vectors
        cells = np.array([
            s.get_cell().reshape(9)
            for s in structs
            if len(s) == minimal_struct
        ])
        median_cell = np.median(cells, axis=0)
        median_idx = int(
            np.argmin(np.sum((cells - median_cell) ** 2, axis=1) ** 0.5)
        )

        response = [i for i in response if i != []]
        occs_noneq = [[line[1]] for line in response][median_idx][0]

        # check: all atoms have constant occupancy
        if any([occ for occ in occs_noneq if occ != 1]):
            for idx, res in enumerate(response):
                if all([i == 1 for i in res[1]]):
                    entry = [line[:1] for line in response][idx][0]
                    selected_struct = structs[idx]
                    return [selected_struct, entry]
            print(
                "No structures were found where all atoms have constant occupancy!"
            )
            return [False, False]
        else:
            selected_struct = structs[median_idx]
            entry = [line[:1] for line in response][median_idx][0]
            return [selected_struct, entry]
    except APIError as e:
        print(f"[ERROR] MPDS API error for element {el}: {e}")
        return None, None


def submit_aiida_fleur_task(
    structure: ase.Atoms, wf_parameters: dict, options: dict, wf_relax: dict
):
    """
    Submit a task via AiiDA.

    Parameters:
    - structure (ase.Atoms): An ASE Atoms object representing the atomic structure.
    - settings (dict): A dictionary containing SCF settings for the FleurRelaxWorkChain.
      Refer to the AiiDA-Fleur documentation for details:
      https://aiida-fleur.readthedocs.io/en/latest/user_guide/workflows/relax_wc.html
    """
    nodes = find_nodes(FLEUR_LABEL, INPGEN_LABEL)

    fleur_code = load_node(nodes[FLEUR_LABEL])
    inpgen_code = load_node(nodes[INPGEN_LABEL])

    structure = StructureData(ase=structure)

    # Submit FleurRelaxWorkChain
    future = submit(
        FleurRelaxWorkChain,
        scf={
            "wf_parameters": wf_parameters,
            "options": options,
            "inpgen": inpgen_code,
            "fleur": fleur_code,
            "structure": structure,
        },
        wf_parameters=wf_relax,
    )
    print("submitted WorkChain; calc=WorkCalculation(PK={})".format(future.pk))


# Example usage
if __name__ == "__main__":
    for el in random.choices(CHEMICAL_ELEMENTS, k=5):
        print(f"Processing element: {el}")
        # Get structure from MPDS
        structure, entry = get_structure_from_mpds(el)
        if structure:
            print(f"Structure for {el} retrieved successfully.")
            submit_aiida_fleur_task(
                structure,
                WF_PARAMETERS,
                OPTIONS,
                WF_RELAX,
            )
        else:
            print(f"Failed to retrieve structure for {el}.")
