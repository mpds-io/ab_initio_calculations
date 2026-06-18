from aiida import load_profile
load_profile()
from aiida.orm import load_code, Dict, Str
from mpds_aiida.workflows.properties import SeebeckPropertiesWorkChain
from aiida.engine import submit

PHASES = [
    ('AsF5/194', '0e8fb054-0b07-4940-85a5-0c53b71653cc'),
    # ('B2O3/152', '688f10e9-060a-47b7-bf2b-bf2a850958eb'),
    # ('CaGe2/166', '13434b32-c3c4-42cf-b3e7-5bdb2bfe3350'),
    # ('Co2As/189', 'd78a64e2-17ab-4b21-b53a-ce3a6eba0f03'),
    # ('DyBr3/148', '3e1d1766-b770-42c7-b4d7-08c3795ccaca'),
]

PARAMS = {
    'newk': {'k_points': [42, 42], 'fermi': True},
    'boltztra': {
        'trange': [298, 600, 300],
        'murange': [-0.5, 0.5, 0.05],
        'tdfrange': [-0.5, 0.5, 0.05],
        'relaxtim': 10,
    },
}

OPTIONS = {
    'resources': {
        'num_machines': 1,
        'num_mpiprocs_per_machine': 1,
    },
    'max_wallclock_seconds': 3600,
}

for label, uuid in PHASES:
    builder = SeebeckPropertiesWorkChain.get_builder()
    builder.code = load_code("pproperties@yascheduler")
    builder.crystal_calc_uuid = Str(uuid)
    builder.parameters = Dict(dict=PARAMS)
    builder.options = Dict(dict=OPTIONS)
    builder.metadata = {'label': f'{label} Seebeck direct'}

    wc = submit(builder)
    print(f"Submitted {label} → PK={wc.pk} (uuid={uuid})")