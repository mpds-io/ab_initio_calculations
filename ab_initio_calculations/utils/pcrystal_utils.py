import os
from collections import namedtuple
import ase
import yaml
from aiida_crystal_dft.io.basis import BasisFile
from aiida_crystal_dft.io.d12 import D12
from aiida_crystal_dft.io.f34 import Fort34
from ase.data import chemical_symbols

from ab_initio_calculations.settings import Settings

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "conf/templates"
)
ELS_REPO_DIR = Settings().basis_sets_dir

verbatim_basis = namedtuple("basis", field_names="content, all_electron")


def get_basis_sets(repo_dir=ELS_REPO_DIR):
    """
    Keeps all available BS in a dict for convenience
    NB we assume BS repo_dir = AiiDA's *basis_family*
    """
    assert os.path.exists(repo_dir), "No folder %s with the basis sets found" % repo_dir

    bs_repo = {}
    for filename in os.listdir(repo_dir):
        if not filename.endswith(".basis"):
            continue

        el = filename.split(".")[0]
        assert el in chemical_symbols, "Unexpected basis set file %s" % filename
        with open(repo_dir + os.sep + filename, "r") as f:
            bs_str = f.read().strip()

        bs_parsed = BasisFile().parse(bs_str)
        bs_repo[el] = verbatim_basis(
            content=bs_str, all_electron=("ecp" not in bs_parsed)
        )

    return bs_repo


def get_template(template="pcrystal_demo.yml"):
    """
    Templates control the calc setup which is not supposed to be changed
    """
    template_loc = os.path.join(TEMPLATE_DIR, template)
    if not os.path.exists(template_loc):
        template_loc = template

    assert os.path.exists(template_loc)

    with open(template_loc) as f:
        calc = yaml.load(f.read(), Loader=yaml.SafeLoader)
    return calc


def get_input(calc_params_crystal, elements, bs_src, label):
    """
    Generates a program input
    """
    calc_params_crystal["label"] = label

    if isinstance(bs_src, dict):
        return D12(
            parameters=calc_params_crystal, basis=[bs_src[el] for el in elements]
        )

    elif isinstance(bs_src, str):
        return D12(parameters=calc_params_crystal, basis=bs_src)

    raise RuntimeError("Unknown basis set source format!")


class Pcrystal_setup:
    els_repo = get_basis_sets()
    calc_setup = get_template()
    assert calc_setup["default"]["crystal"]

    def __init__(self, ase_obj, custom_template=None):
        self.ase_obj = ase_obj
        self.els = list(set(self.ase_obj.get_chemical_symbols()))
        self.custom_template = None

        if custom_template:
            self.custom_template = get_template(custom_template)
            assert self.custom_template["default"]["crystal"]

    def validate(self):
        for el in self.els:
            if el not in Pcrystal_setup.els_repo:
                return f"Element {el} is not supported"

        return None

    def get_input_struct(self):
        f34_input = Fort34([Pcrystal_setup.els_repo[el] for el in self.els])
        return str(f34_input.from_ase(self.ase_obj))

    def get_input_setup(self, label):
        return str(
            get_input(
                (
                    self.custom_template["default"]["crystal"]
                    if self.custom_template
                    else Pcrystal_setup.calc_setup["default"]["crystal"]
                ),
                self.els,
                Pcrystal_setup.els_repo,
                label,
            )
        )


def convert_to_pcrystal_input(dir: str, atoms_obj: list[ase.Atoms], entry: str = None) -> str:
    """Convert structures from ase.Atoms to Pcrystal input format (d12, fort.34)"""
    el_hight_tolinteg = ["Ta", "Se", "P"]

    for ase_obj in atoms_obj:
        setup = Pcrystal_setup(ase_obj)
        if any([el in el_hight_tolinteg for el in set(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = "8 8 8 8 16"
        elif "Sb" in set(ase_obj.symbols):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = "10 10 10 10 16"
        input = setup.get_input_setup("test " + entry)
        fort34 = setup.get_input_struct()

        subdir = os.path.join(dir, f"pcrystal_input_{ase_obj.get_chemical_formula()}_{entry}")
        os.makedirs(subdir, exist_ok=True)

        input_file = os.path.join(subdir, f"input_{ase_obj.get_chemical_formula()}_{entry}")
        fort_file = os.path.join(subdir, f"fort.34")

        with open(input_file, "w") as f_input:
            f_input.write(input)
        with open(fort_file, "w") as f_fort:
            f_fort.write(fort34)

        print(f"Data written to {input_file} and {fort_file}")
        return input_file
