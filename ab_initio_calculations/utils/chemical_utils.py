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
