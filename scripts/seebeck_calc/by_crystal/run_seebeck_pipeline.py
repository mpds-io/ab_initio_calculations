import os
from aiida import load_profile
from aiida.plugins import DataFactory
from aiida.orm import Code
from aiida.engine import submit
from mpds_aiida.workflows.crystal_seebeck import MPDSCrystalSeebeckWorkChain

load_profile()

workchain_options_file = os.getenv("WORKCHAIN_OPTIONS", "nonmetallic.yml")
from mpds_aiida.common import get_template

PHASES = [
    ['Au2U', 191], ['AsF5', 194], ['BaSn3', 194], ['BiSe', 164],
    ['B2O3', 152], ['Ca2Sb', 139], ['CaC6', 166], ['CaGe2', 166],
    ['Ce5Ge3', 193], ['CoO2', 166], ['Co2As', 189], ['CrSb', 194],
    ['DyBr3', 148], ['DyNi5', 191], ['Er5Rh3', 193],
]

workchain_options = get_template(workchain_options_file)

properties_code = Code.get_from_string(os.getenv("PROPERTIES_CODE", "pproperties@yascheduler"))

PROPERTIES_PARAMETERS = {
    'newk': {'k_points': [48, 48], 'fermi': True},
    'boltztra': {
        'trange': [298, 600, 300],
        'murange': [-0.5, 0.5, 0.05],
        'tdfrange': [-0.5, 0.5, 0.05],
        'relaxtim': 10,
    },
}

PROPERTIES_OPTIONS = {
    'resources': {
        'num_machines': 1,
        'num_mpiprocs_per_machine': 1,
    },
    'max_wallclock_seconds': 42,
}

for formula, sgs in PHASES:
    inputs = {
        'workchain_options': DataFactory('dict')(dict=workchain_options),
        'mpds_query': DataFactory('dict')(dict={'formulae': formula, 'sgs': sgs}),
        'properties_code': properties_code,
        'properties_parameters': DataFactory('dict')(dict=PROPERTIES_PARAMETERS),
        'properties_options': DataFactory('dict')(dict=PROPERTIES_OPTIONS),
        'metadata': {'label': f"{formula}/{sgs} seebeck pipeline"},
    }

    wc = submit(MPDSCrystalSeebeckWorkChain, **inputs)
    print(f"Submitted MPDSCrystalSeebeckWorkChain for {formula}/{sgs} → PK={wc.pk}")