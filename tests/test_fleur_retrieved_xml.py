"""Saved FLEUR XML must be copied as bytes before force extraction."""
from io import BytesIO
from pathlib import Path
import sys

import pytest
from aiida.orm import FolderData
from aiida.storage.sqlite_temp import SqliteTempBackend

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/phonon/manual"))
from run_fleur_scf import copy_retrieved_fleur_xml, write_forces_file_from_out_xml


@pytest.fixture
def saved_xml():
    backend = SqliteTempBackend(SqliteTempBackend.create_profile())
    try:
        folder = FolderData(backend=backend)
        contents = {
            "out.xml": (b'<?xml version="1.0" encoding="UTF-8"?>'
                        b'<fleurOutput><forceTotal F_x="0.01" F_y="-0.02" F_z="0.03"/>'
                        b'</fleurOutput>'),
            "inp.xml": (b'<?xml version="1.0" encoding="UTF-8"?>'
                        b'<fleurInput><atomGroups><atomGroup><relPos>0 0 0</relPos>'
                        b'</atomGroup></atomGroups></fleurInput>'),
        }
        for name, data in contents.items():
            folder.base.repository.put_object_from_filelike(BytesIO(data), name)
        yield folder, contents
    finally:
        backend.close()


def test_binary_xml_copy_preserves_repository_bytes(saved_xml, tmp_path):
    folder, contents = saved_xml
    # This default text return caused write_bytes() to raise TypeError.
    assert isinstance(folder.base.repository.get_object_content("out.xml"), str)
    out_xml, inp_xml = copy_retrieved_fleur_xml(folder, tmp_path)
    assert out_xml.read_bytes() == contents["out.xml"]
    assert inp_xml.read_bytes() == contents["inp.xml"]


def test_force_extraction_after_binary_copy(saved_xml, tmp_path):
    folder, _ = saved_xml
    out_xml, inp_xml = copy_retrieved_fleur_xml(folder, tmp_path)
    force_file = tmp_path / "FORCES"
    assert write_forces_file_from_out_xml(out_xml, force_file, inp_xml) == 1
    actual = [float(value) for value in force_file.read_text().splitlines()[0].split()]
    # Hartree/bohr -> eV/Angstrom; signs and atom count must be retained.
    from run_fleur_scf import HTR_PER_BOHR_TO_EV_PER_ANG
    assert actual == pytest.approx([value * HTR_PER_BOHR_TO_EV_PER_ANG
                                    for value in (0.01, -0.02, 0.03)])
