import os
import time
from pathlib import Path

from ab_initio_calculations.utils.fleur_utils import convert_inp_to_xml
from yascheduler import Yascheduler

# Set correct path to inpgen binary
os.environ['FLEUR_INPGEN_PATH'] = "/root/fleur/build/inpgen"
yac = Yascheduler()


def run_by_yascheduler_from_inp_file(inp_file: Path):
    """
    Convert .inp to .xml, then submit to Yascheduler.
    """
    _, xml_content = convert_inp_to_xml(inp_file)
    if xml_content is None:
        print(f"[ERROR] Failed to convert {inp_file.name} to XML.")
        return

    task_name = inp_file.stem

    print(f"Submitting task for {task_name}...")
    submit_result = yac.queue_submit_task(
        task_name,
        {"inp.xml": xml_content},
        "fleur",
    )
    print(f"Task for {task_name} submitted with ID: {submit_result}")


def main(inp_dir: Path):
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Directory {input_dir} does not exist or is not a directory")
        return

    inp_files = sorted(input_dir.glob("*.inp"))
    if not inp_files:
        print(f"No .inp files found in {input_dir}")
        return

    for inp_file in inp_files:
        start_time = time.time()
        try:
            run_by_yascheduler_from_inp_file(inp_file)
        except Exception as e:
            print(f"Error processing {inp_file.name}: {e}")
        end_time = time.time()
        print(f"Elapsed time for {inp_file.name}: {end_time - start_time:.2f} seconds")


if __name__ == "__main__":
    input_dir = Path("/root/projects/ab_initio_calculations/fleur_input")
    main(input_dir)
