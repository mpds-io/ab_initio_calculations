import logging
import os
import subprocess
import tempfile
from io import StringIO

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
    
    