"""Validate the real base-workchain builder in temporary SQLite storage."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

from aiida import orm
from aiida.manage import get_manager
from aiida.storage.sqlite_temp import SqliteTempBackend


def test_cutoff_builder(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        'cutoff_script', Path(__file__).resolve().parents[1] / 'scripts/abacus_ecut_pressure_test.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    backend = SqliteTempBackend(SqliteTempBackend.create_profile())
    monkeypatch.setattr(get_manager(), 'get_profile_storage', lambda: backend)
    try:
        structure = orm.StructureData(cell=[[5, 0, 0], [0, 5, 0], [0, 0, 5]])
        structure.append_atom(position=[0, 0, 0], symbols='Si')
        kpoints = orm.KpointsData()
        kpoints.set_kpoints_mesh([2, 2, 2])
        pseudo_path = tmp_path / 'Si.upf'
        pseudo_path.write_text('<UPF version="2.0.1">\n<PP_HEADER element="Si"/>\n</UPF>\n')
        pseudo = orm.UpfData(file=str(pseudo_path))
        computer = orm.Computer(label='test', hostname='localhost',
                                transport_type='core.local', scheduler_type='core.direct',
                                workdir='/tmp/aiida-test').store()
        code = orm.InstalledCode(computer=computer, filepath_executable='/bin/true',
                                 default_calc_job_plugin='abacus.abacus')
        parameters = orm.Dict(dict={'input': {'calculation': 'cell-relax', 'relax_nmax': 10}})
        ref = SimpleNamespace(inputs=SimpleNamespace(structure=structure, code=code,
                              kpoints=kpoints, pseudos={'Si': pseudo}, parameters=parameters),
                              get_options=lambda: {'resources': {'num_machines': 1, 'num_mpiprocs_per_machine': 1}})
        # AiiDA inputs support both membership and attribute access.
        from aiida.common import AttributeDict
        ref.inputs = AttributeDict(vars(ref.inputs))
        builder = script.build_cutoff_builder(ref, 150)
        assert script.AbacusBaseWorkChain.spec().inputs.validate(dict(builder)) is None
        assert builder.kpoints is kpoints
        assert 'kpoints' not in builder.abacus
        assert builder.abacus.parameters.get_dict()['input']['calculation'] == 'scf'
        assert builder.abacus.parameters.get_dict()['input']['ecutwfc'] == 150
        assert 'relax_nmax' not in builder.abacus.parameters.get_dict()['input']
        assert parameters.get_dict()['input']['calculation'] == 'cell-relax'
    finally:
        backend.close()
