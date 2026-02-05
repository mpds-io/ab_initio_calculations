import os
from collections import namedtuple
import ase
import yaml
from aiida_crystal_dft.io.basis import BasisFile
from aiida_crystal_dft.io.d12 import D12
from aiida_crystal_dft.io.f34 import Fort34
from ase.data import chemical_symbols
import numpy as np

from ab_initio_calculations.settings import Settings
from pycrystal import CRYSTOUT

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "conf/templates"
)
ELS_REPO_DIR = Settings().basis_sets_dir

verbatim_basis = namedtuple("basis", field_names="content, all_electron")


class Data_type:
    structure = 1
    calculation = 2
    property = 3
    workflow = 4
    pattern = 5
    user_input = 6
    
def get_avg_charges(ase_obj):
    """
    Get an average Mulliken charge for each chemical element in a crystal
    """
    at_type_chgs = {}
    for atom in ase_obj:
        at_type_chgs.setdefault(atom.symbol, []).append(atom.charge)

    if sum([sum(at_type_chgs[at_type]) for at_type in at_type_chgs]) == 0.0:
        return None

    return {at_type: np.average(at_type_chgs[at_type]) for at_type in at_type_chgs}


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
        params = (
            self.custom_template["default"]["crystal"]
            if self.custom_template
            else Pcrystal_setup.calc_setup["default"]["crystal"]
        )

        return str(get_input(params, self.els, Pcrystal_setup.els_repo, label))


    @staticmethod
    def parse(resource):
        if not CRYSTOUT.acceptable(resource):
            return False

        result = CRYSTOUT(resource)
        output = {"content": {}}

        if result.info["optgeom"]:
            # output['content'] = ase_serialize(result.info['structures'][-1])
            output["type"] = Data_type.structure

        # immediately detect a domain-specific error and exit
        if result.info["finished"] != 2:
            try:
                with open(os.path.join(os.path.dirname(resource), "fort.87"), "r") as f:
                    errmsg = f.read()
            except IOError:
                errmsg = "Sorry, an engine has crashed"

            return {"content": {"error": errmsg, "correctly_finalized": False}}

        # TODO
        # Below is just a quick example
        # this should be more systematic

        conductor, band_gap = "no data", "no data"
        try:
            bands_data = result.info["conduction"][-1]
        except Exception:
            bands_data = {}
        if bands_data.get("state") == "CONDUCTING":
            conductor, band_gap = True, None
        elif bands_data.get("state") == "INSULATING":
            conductor, band_gap = False, f"{bands_data['band_gap']:.1f}"
        try:
            charges = get_avg_charges(result.info["structures"][-1])
            charges = {el: f"{val:.2f}" for el, val in charges.items()}
        except Exception:
            charges = None

        output["content"] = {
            #"total_energy": result.info["energy"],
            #"total_energy_units": "eV",
            "conductor": conductor,
            "band_gap": band_gap,
            "band_gap_units": "eV",
            "charges": charges,
            #'magmoms': magmoms,
            "n_electrons": result.info["n_electrons"],
            "correctly_finalized": result.info["finished"] == 2,
        }
        return output


def convert_to_pcrystal_input(dir: str, atoms_obj: list[ase.Atoms], entry: str = None, optimise: bool = False) -> str:
    """Convert structures from ase.Atoms to Pcrystal input format (d12, fort.34)"""
    el_high_tolinteg = ["Ta", "Se", "P"]

    for ase_obj in atoms_obj:
        setup = Pcrystal_setup(ase_obj)
        
        if any([el in el_high_tolinteg for el in set(ase_obj.symbols)]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = [8, 8, 8, 8, 16]
            
        elif any([i in list(ase_obj.symbols) for i in ['C', 'Ag', 'Mg', 'Tc', 'Ni', 'Sb', 'Pr']]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = [20, 20, 20, 20, 40]
            setup.calc_setup["default"]["properties"]["shrink"] = 8
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLDEE"] = 6
        elif any([i in list(ase_obj.symbols) for i in ['P', 'Se', 'Mn', 'Fe', 'Ru', 'V', 'Tc']]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = [6, 6, 6, 6, 12]
            setup.calc_setup["default"]["properties"]["shrink"] = 7
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLDEE"] = 6
        elif any([i in list(ase_obj.symbols) for i in ['Co', 'Cr']]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = [8, 8, 8, 8, 16]
            setup.calc_setup["default"]["crystal"]["scf"]['k_points'] = [32, 32]
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLDEE"] = 8
        elif any([i in list(ase_obj.symbols) for i in ['Es']]):
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLINTEG"] = [8, 8, 8, 8, 16]
            setup.calc_setup["default"]["crystal"]["scf"]['k_points'] = [10, 10]
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["TOLDEE"] = 8
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["MAXCYCLE"] = 1000
            setup.calc_setup["default"]["crystal"]["scf"]["numerical"]["FMIXING"] = 90

        if optimise:
            setup.calc_setup["options"]["optimize_structure"] = "optimise"
            setup.calc_setup["default"]["crystal"]["geometry"] = {
                "optimise": {
                    "type": "FULLOPTG",
                    "convergence": {
                        "MAXCYCLE": 200,
                    }
                }
            }

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
