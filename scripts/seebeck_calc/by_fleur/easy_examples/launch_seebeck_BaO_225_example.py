#!/usr/bin/env python3
"""
Launch FleurDOSLocalWorkChain for Seebeck coefficient calculation
for BaO space group 225.

Uses existing FLEUR SCF result (PK=55464) and submits
DOS + Seebeck calculation at T=298K.
"""

from aiida import load_profile
from aiida.orm import Dict, Str, load_code, load_node
from aiida.engine import submit

from mpds_aiida.workflows.fleur_seebeck import FleurDOSLocalWorkChain, DEFAULT_SEEBECK

SCF_UUID = "81085a93-b41f-47dd-bf67-9b37e42f1336"

FORMULA = "BaO"
SPACE_GROUP = 225
TEMPERATURE = 298.0

load_profile()

fleur_code = load_code("fleur")

calcjob = load_node(SCF_UUID)
remote = calcjob.base.links.get_outgoing().get_node_by_label("remote_folder")

wf_para_dos = Dict(
    dict={
        "kpoints_mesh_dos": [72, 72, 72],
        "sigma": 0.0005,
        "emin": -2.0,
        "emax": 2.0,
    }
)

seebeck_dict = DEFAULT_SEEBECK.copy()
seebeck_dict["temperature"] = TEMPERATURE
seebeck_params_node = Dict(dict=seebeck_dict)

inputs = {
    "fleur": fleur_code,
    "remote": remote,
    "wf_parameters": wf_para_dos,
    "seebeck_parameters": seebeck_params_node,
    "phase": Str(FORMULA),
    "options": Dict(
        dict={
            "resources": {
                "num_machines": 1,
                "num_mpiprocs_per_machine": 4,
                "num_cores_per_mpiproc": 2,
            },
            "max_wallclock_seconds": 3600,
        }
    ),
}

workchain = submit(FleurDOSLocalWorkChain, **inputs)
print(
    f"[OK] {FORMULA}/{SPACE_GROUP}: submitted FleurDOSLocalWorkChain PK={workchain.pk} T={TEMPERATURE}K"
)
print(f"     SCF UUID: {SCF_UUID}")
print(f"     Remote PK: {remote.pk}")
