import sys
import yaml
from aiida import load_profile
from aiida.plugins import DataFactory
from aiida.engine import submit
from mpds_aiida.workflows.mpds import MPDSStructureWorkChain

load_profile()

PHASES = [
    ("ND3", "194"),
    ("TaP", "109"),
    ("TiBr3", "148"),
    ("ND3", "19"),
    ("MgH2", "136"),
    ("H2S", "142"),
    ("UT3", "223"),
    ("PuH2", "225"),
    ("CrB4", "71"),
    ("Fe3B", "62"),
    ("Co2B", "140"),
    ("NbB", "63"),
    ("MoB2", "166"),
    ("YbB6", "221"),
    ("LuB12", "139"),
    ("WB", "63"),
    ("SiC", "156"),
    ("KC", "142"),
    ("V6C5", "151"),
    ("Fe2C", "58"),
    ("YC2", "225"),
]


if len(sys.argv) > 1:
    phase = tuple(sys.argv[1].split("/"))
    PHASES = [phase]
    print("Running single phase from CLI:", "/".join(phase))
else:
    print(f"Running batch of {len(PHASES)} phases")



with open(
    "templates/test_schema.yml"
) as f:
    workchain_options = yaml.load(f, Loader=yaml.SafeLoader)

for phase in PHASES:
    if len(phase) == 3:
        formula, sgs, pearson = phase
    else:
        formula, sgs = phase
        pearson = None

    sgs = int(sgs)

    inputs = MPDSStructureWorkChain.get_builder()
    inputs.workchain_options = workchain_options
    inputs.metadata = dict(label="/".join(map(str, phase)))
    inputs.mpds_query = DataFactory("dict")(
        dict={"formulae": formula, "sgs": sgs}
    )

    calc = submit(MPDSStructureWorkChain, **inputs)

    print(
        f"Submitted {formula}/{sgs} → PK={calc.pk}"
    )
