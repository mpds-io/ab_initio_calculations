
import os

from ase.io import read


def get_basis(els: list, folder_path: str) -> list:
    basis = []

    for el in els:
        basis_file = os.path.join(folder_path, f"{el}.basis")
        if os.path.isfile(basis_file):
            with open(basis_file, "r", encoding="utf-8") as file:
                basis.append(file.read())
        else:
            raise NameError(f"Basis set for element {el} not found in {folder_path}")

    return basis


def cif_to_pcrystal_input(cif_file, path_to_basis, output_file=None):
    structure = read(cif_file)

    a, b, c = structure.cell.lengths()
    alpha, beta, gamma = structure.cell.angles()

    atom_types = structure.get_chemical_symbols()
    atomic_numbers = structure.get_atomic_numbers()
    frac_coords = structure.get_scaled_positions()

    unique_atoms = {}

    for num, symbol, coords in zip(atomic_numbers, atom_types, frac_coords):
        if symbol not in unique_atoms:
            unique_atoms[symbol] = (num, symbol, coords)

    if not(output_file):
        output_file = 'input' + structure.get_chemical_formula()
    with open(output_file, "w") as f:
        f.write(structure.get_chemical_formula())
        f.write("\nCRYSTAL\n")
        f.write("0 0 0\n")
        f.write(f"{structure.info['spacegroup'].no}\n")
        f.write(f"{a:.6f} {b:.6f} {c:.6f} {alpha:.6f} {beta:.6f} {gamma:.6f}\n")
        f.write(f"{len(unique_atoms)}\n")  #num noneq atoms


        for (atomic_number, symbol, coords) in unique_atoms.values():
            f.write(f"{atomic_number} {coords[0]:.6f} {coords[1]:.6f} {coords[2]:.6f}\n")

        f.write("END\n")

        # add basis
        basis_list = get_basis(set(atom_types), path_to_basis)
        for basis in basis_list:
            f.write(basis + "\n")

        f.write("99 0\n")

        f.write("END\n")

        # SCF
        f.write("SHRINK\n")
        f.write("8 8\n")
        f.write("FMIXING\n")
        f.write("30\n")
        f.write("PPAN\n")
        f.write("END\n")


    print(f"File {output_file} created!")


cif_to_pcrystal_input("./MgO_MPDS_S1021337.cif", "./MPDSBSL_NEUTRAL_24")

