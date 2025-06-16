# the AiiDA-Fleur environment is expected to be already set up
import random

import ase
from aiida import load_profile
from aiida.engine import submit
from aiida.orm import Dict, QueryBuilder, StructureData, load_node
from aiida.orm.nodes.data.code import Code
from aiida_fleur.workflows.relax import FleurRelaxWorkChain
from ase import Atoms

from ab_initio_calculations.mpds.receiver import download_structures
from ab_initio_calculations.utils.structure_processor import process_structures

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
        "max_wallclock_seconds": 10 * 3600,  # 10 hours
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
        structs, response, el = download_structures(el)
        if structs is None:
            print(f"[WARNING] Skipping element {el} due to missing data.")
            continue
        structure, entry = process_structures(structs, response)
        
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
