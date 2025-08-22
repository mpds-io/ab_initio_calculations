import logging
import os
import shutil
import subprocess
import tempfile
from io import StringIO
from pathlib import Path

from ase import Atoms
from ase.io import write as ase_write


class Fleur_setup:
    """Class to prepare input for inpgen."""
    def __init__(self, ase_obj):
        self.ase_obj = ase_obj

    def validate(self):
        self.xml_input = self.ase_to_fleur_xml(self.ase_obj)
        if not self.xml_input:
            return "Fleur inpgen misconfiguration occured"
        return None

    def get_input_setup(self, label):
        if self.xml_input:
            return self.xml_input.replace("%ABSDX_%", label)

    def ase_to_fleur_xml(self, ase_obj: Atoms):
        """
        Skipping the textual Fleur input generation
        in order to simplify our provenance persistence layers
        """
        buff = StringIO()
        ase_write(
            buff,
            ase_obj,
            format="fleur-inpgen",
            parameters={
                "title": "%ABSDX_%",
            },
        )
        buff.seek(0)
        txt_input = buff.getvalue()

        with tempfile.TemporaryDirectory(prefix="fleur_inpgen_") as tmp_dir:
            input_path = os.path.join(tmp_dir, "fleur.inp")
            with open(input_path, "w") as f:
                f.write(txt_input)

            opts = ["-f", "fleur.inp", "-inc", "+all", "-noco"]
            p = subprocess.Popen(
                [os.environ['FLEUR_INPGEN_PATH']] + opts,
                cwd=tmp_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            p.communicate()
            if p.returncode != 0:
                logging.error("Bad news: inpgen failed")
                return None

            xml_path = os.path.join(tmp_dir, "inp.xml")
            if not os.path.exists(xml_path):
                logging.error("Bad news: inpgen produced no result")
                return None

            with open(xml_path, "r") as f:
                xml_input = f.read()

        return xml_input
    

def convert_inp_to_xml(inp_file: Path):
    inp_dir = inp_file.parent
    name_stem = inp_file.stem
    output_base_dir = inp_dir / "xml"

    print(f"Processing {inp_file.name}...")
    output_base_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [os.environ['FLEUR_INPGEN_PATH'], "-f", str(inp_file)],
        cwd=inp_dir
    )

    if result.returncode != 0:
        print(f"Error while processing {inp_file.name}")
        return None

    generated_xml = inp_dir / "inp.xml"
    if not generated_xml.exists():
        print(f"inp.xml not found for {inp_file.name}")
        return None

    out_dir = output_base_dir / name_stem
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{name_stem}.xml"

    shutil.move(str(generated_xml), str(out_file))
    print(f"Saved to {out_file}")

    content = out_file.read_text(encoding="utf-8")
    return out_file, content


if __name__ == "__main__":
    from dotenv import load_dotenv

    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(ROOT_DIR, 'config.env')
    
    load_dotenv(CONFIG_PATH)

    def list_inp_files(dir):
        inp_files = sorted(dir.rglob("*.inp"))  
        return [inp_file.resolve() for inp_file in inp_files]

    base_dir = os.environ['FLEUR_INP_DIR']
    errors = []
    for file in list_inp_files(base_dir):
        try:
            out_file, content = convert_inp_to_xml(file)
            print(f"Converted {file.name} to XML and saved to {out_file}")
        except:
            errors.append(file)
            print(f"Failed to convert {file.name}")
            
    if errors:
        print("Errors occurred for the following files:")
        for error_file in errors:
            print(error_file)
