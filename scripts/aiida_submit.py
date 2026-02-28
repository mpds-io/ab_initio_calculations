import sys
import yaml
from aiida import load_profile
from aiida.plugins import DataFactory
from aiida.engine import submit
from mpds_aiida.workflows.mpds import MPDSStructureWorkChain
import polars as pl

load_profile()

df = pl.read_csv('ab_initio_seebeck_data.csv')
PHASES = list(zip(df["formula"], df["sg"], df["phase_id"]))

if len(sys.argv) > 1:
    phase = tuple(sys.argv[1].split("/"))
    PHASES = [phase]
    print("Running single phase from CLI:", "/".join(phase))
else:
    print(f"Running batch of {len(PHASES)} phases")

with open(
    "templates/base.yml"
) as f:
    workchain_options = yaml.load(f, Loader=yaml.SafeLoader)

for phase in PHASES:
    if len(phase) == 3:
        formula, sgs, id = phase
    else:
        formula, sgs = phase
        pearson = None

    sgs = int(sgs)

    inputs = MPDSStructureWorkChain.get_builder()
    inputs.workchain_options = workchain_options
    inputs.metadata = dict(label="/".join(map(str, phase[:-1])))
    inputs.mpds_query = DataFactory("dict")(
        dict={"formulae": formula, "sgs": sgs},
    )

    calc = submit(MPDSStructureWorkChain, **inputs)

    print(
        f"Submitted {formula}/{sgs} → PK={calc.pk}"
    )
