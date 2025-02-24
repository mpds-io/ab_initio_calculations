import os

from pycrystal import CRYSTOUT
from tabulate import tabulate


def get_property_from_output(file_path: str, prop: str = "energy") -> float:
    """
    Extract specified property from output file.

    Parameters
    ----------
    file_path : str
        Path to output file.
    prop : str, optional
        The property to extract (default is 'energy').

    Returns
    -------
    float
        The value of the specified property.
    """
    out = CRYSTOUT(file_path)
    return out.info[prop]


def get_duration(file_path: str) -> str:
    """
    Retrieve the duration of calculation from CRYSTOUT output file.

    Parameters
    ----------
    file_path : str
        Path to the output file.

    Returns
    -------
    str
        The duration of the calculation (e.g., '10.5s').
    """
    out = CRYSTOUT(file_path)
    return out.info["duration"]


def start_parsing(dir_path: str) -> list:
    """
    Parse subdirectories and extract energy and duration from the 'OUTPUT' file.

    Parameters
    ----------
    dir_path : str
        Path to main dir containing subdirectories with 'OUTPUT' files.

    Returns
    -------
    list
        A list of lists containing subdirectory names, energy, and duration.
    """
    res = []
    for subdir in os.listdir(dir_path):
        subdir_path = os.path.join(dir_path, subdir)
        if os.path.isdir(subdir_path):
            output_path = os.path.join(subdir_path, "OUTPUT")
            if os.path.exists(output_path):
                try:
                    energy = get_property_from_output(output_path, "energy")
                    duration = get_duration(output_path)
                    res.append([subdir, energy, duration])
                    print(f"Total energy from {output_path}: {energy}")
                except Exception as e:
                    print(f"Error processing {output_path}: {e}")
            else:
                print(f"Warning: No OUTPUT file found in {subdir_path}")
    return res


if __name__ == "__main__":
    # root dir containing subdirectories with OUTPUT files
    path = "./pcrystal_input"

    # start parsing dir and retrieve the results
    res = start_parsing(path)

    print(
        tabulate(res, headers=["folder", "Energy", "Duration (sec)"], tablefmt="grid")
    )
