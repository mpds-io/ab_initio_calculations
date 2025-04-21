import os

import periodictable
from ab_initio_calculations.settings import Settings


if __name__ == "__main__":
    dir = Settings().basis_sets_dir

    files = [
        f.replace(".basis", "")
        for f in os.listdir(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), dir)
        )
    ]

    els_no_basis = []
    for element in periodictable.elements:
        if element.symbol not in files:
            els_no_basis.append(element)

    print(els_no_basis)
