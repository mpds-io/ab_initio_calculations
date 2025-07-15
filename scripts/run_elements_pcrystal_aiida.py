from aiida import load_profile
from aiida.orm import Dict, Code
from aiida.engine import submit
from mpds_aiida.workflows.mpds import MPDSStructureWorkChain
from ab_initio_calculations.utils.chemical_utils import (
    get_list_of_basis_elements,
)

load_profile()

def submit_mpds_workchain(formula, sgs=None):
    inputs = MPDSStructureWorkChain.get_builder()

    code = Code.get_from_string('crystal-dft@localhost')
    
    inputs.workchain_options = Dict(dict={
        "max_wallclock_seconds": 7200,
        "resources": {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 8,
        },
        "queue_name": "default",
    })

    # Error here (no such key)
    inputs.code = code

    query_dict = {"formulae": formula}
    if sgs is not None:
        query_dict["sgs"] = sgs

    inputs.mpds_query = Dict(dict=query_dict)
    inputs.metadata.label = f"{formula}/{sgs if sgs else 'any_sgs'}"

    calc = submit(MPDSStructureWorkChain, **inputs)
    print(f"Submitted MPDSStructureWorkChain for {formula} (PK={calc.pk})")

if __name__ == "__main__":
    for el in get_list_of_basis_elements():
        print(f"Submitting calculation for element {el}")
        submit_mpds_workchain(el)
