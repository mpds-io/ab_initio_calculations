import ase


def define_same_structures(structures: list[dict]) -> list[dict]:
    """Define structures with same chemical formula and space group"""
    sg_n_set = list(set([i["sg_n"] for i in structures]))
    chem_formula_set = list(set([i["chemical_formula"] for i in structures]))

    curr_sg_n, curr_chem_form = sg_n_set[0], chem_formula_set[0]

    same_structures = [
        struct
        for struct in structures
        if struct["sg_n"] == curr_sg_n and struct["chemical_formula"] == curr_chem_form
    ]
    return same_structures


def guess_metal(ase_obj) -> bool:
    """
    Make an educated guess of the metallic compound character,
    returns bool
    """
    non_metallic_atoms = {
    'H',                                  'He',
    'Be',   'B',  'C',  'N',  'O',  'F',  'Ne',
                  'Si', 'P',  'S',  'Cl', 'Ar',
                  'Ge', 'As', 'Se', 'Br', 'Kr',
                        'Sb', 'Te', 'I',  'Xe',
                              'Po', 'At', 'Rn',
                                          'Og'
    }
    return not any([el for el in set(ase_obj.get_chemical_symbols()) if el in non_metallic_atoms])


