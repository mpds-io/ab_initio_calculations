from aiida import load_profile
from aiida.orm import Dict, Str, load_code, load_node
from aiida.engine import submit

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

load_profile()

fleur_code = load_code("fleur")
inpgen_code = load_code("inpgen")
structure = load_node(57090)  # AlAs

wf_para_scf = Dict(
    dict={
        "fleur_runmax": 5,
        "density_converged": 1.0e-6,
        "mode": "density",
        "itmax_per_run": 50,
    }
)

wf_para_dos = Dict(
    dict={
        "kpoints_mesh_dos": [6, 6, 6],
        "sigma": 0.002,
        "emin": -2.0,
        "emax": 2.0,
    }
)

seebeck_params = Dict(dict=DEFAULT_SEEBECK)

inputs = {
    "scf": {
        "wf_parameters": wf_para_scf,
        "structure": structure,
        "inpgen": inpgen_code,
        "fleur": fleur_code,
    },
    "fleur": fleur_code,
    "wf_parameters": wf_para_dos,
    "seebeck_parameters": seebeck_params,
    "structure": structure,
    "phase": Str("AlAs/225"),
}

workchain = submit(FleurDOSLocalWorkChain, **inputs)
print(f"Submitted FleurDOSLocalWorkChain: PK={workchain.pk}")



if __name__ == "__main__":
    pass