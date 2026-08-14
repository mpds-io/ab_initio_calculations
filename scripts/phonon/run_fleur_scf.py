"""
Run a single FLEUR SCF calculation (inpgen + fleur_MPI) outside AiiDA and
optionally a follow-up forces run (l_f=True) that writes the FORCES file.

The point of this module is to isolate the SCF convergence physics from the
AiiDA plumbing so we can quickly test different parameter presets against
the convergence problems seen in the failed PhonopyFleurWorkChain runs.

It reproduces the Fleur_setup logic from aiida-reoptimize:
    ASE atoms -> fleur-inpgen text -> inpgen -inc +all -noco -> inp.xml
and then runs fleur_MPI directly.

inp.xml modifications (mixing scheme, k-point mesh, itmax, l_f) are applied
through masci_tools, the same library aiida-fleur's FleurinpModifier uses
internally, so the semantics match what the AiiDA workflow would do.

Parameter presets encode the two competing convergence tweaks we want to
compare:

  baseline  - defaults that the failed runs used
              (mode=energy, fleur_runmax=4, itmax_per_run=60, no inpxml_changes)
  tuningA   - mpds-aiida updating_fleur_parameters branch:
              straight mixing imix=straight alpha=0.05, kmax=3.0,
              kpt mesh 4x4x4, itmax_per_run=300, fleur_runmax=10,
              density_converged=1e-4, energy_converged=0.01
  tuningB   - Anton PR #63 FlerSCFRestart rule: take the baseline run, and
              if it does not converge, restart it from the produced charge
              density with the k-point mesh halved in each direction.
              Encoded here as restart-on-failure behaviour of run_scf().
  tuningC   - tuningA from the start plus the halving restart on top.

Usage as a script (see run_phonopy_manual.py for orchestration):

    python3 scripts/phonon/run_fleur_scf.py run \
        --poscar data/.../BiSe_164.poscar \
        --preset tuningA \
        --inpgen /root/fleur/build/inpgen \
        --fleur  /root/fleur/build/fleur_MPI \
        --workdir /tmp/bise_tuningA
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

from lxml import etree

# ---------------------------------------------------------------------------
# Parameter presets
# ---------------------------------------------------------------------------

CALC_PARAMS_BASELINE: dict[str, Any] = {}
WF_PARAMS_BASELINE: dict[str, Any] = {
    "mode": "energy",
    "fleur_runmax": 4,
    "itmax_per_run": 60,
}

PRESETS: dict[str, dict[str, Any]] = {
    "baseline": {
        "calc_parameters": CALC_PARAMS_BASELINE,
        "wf_parameters": WF_PARAMS_BASELINE,
        "inpxml_changes": {},  # {attrib_name: value} fed to set_inpchanges
        "kpoint_mesh": None,
        "restart_kpoints_factor": None,
    },
    "fast": {
        # inpgen defaults + short itmax for quick pipeline validation.
        "calc_parameters": CALC_PARAMS_BASELINE,
        "wf_parameters": {
            "mode": "energy",
            "fleur_runmax": 4,
            "itmax_per_run": 15,
        },
        "inpxml_changes": {},
        "kpoint_mesh": None,
        "restart_kpoints_factor": None,
    },
    "tuningA": {
        "calc_parameters": {
            "comp": {"kmax": 3.0},
            "kpt": {"div1": 4, "div2": 4, "div3": 4},
        },
        "wf_parameters": {
            "mode": "energy",
            "fleur_runmax": 10,
            "itmax_per_run": 300,
            "density_converged": 1.0e-4,
            "energy_converged": 0.01,
        },
        "inpxml_changes": {"imix": "straight", "alpha": 0.05},
        "kpoint_mesh": (4, 4, 4),
        "restart_kpoints_factor": None,
    },
    "tuningB": {
        "calc_parameters": CALC_PARAMS_BASELINE,
        "wf_parameters": WF_PARAMS_BASELINE,
        "inpxml_changes": {},
        "kpoint_mesh": None,
        "restart_kpoints_factor": 2,
    },
    "tuningB_fast": {
        # Same as tuningB but with small itmax to force the restart to trigger
        # on systems where Anderson would eventually converge given enough
        # iterations. Used to test that the restart logic actually fires.
        "calc_parameters": CALC_PARAMS_BASELINE,
        "wf_parameters": {
            "mode": "energy",
            "fleur_runmax": 4,
            "itmax_per_run": 10,
            "energy_converged": 0.0001,
        },
        "inpxml_changes": {},
        "kpoint_mesh": None,
        "restart_kpoints_factor": 2,
    },
    "tuningC": {
        "calc_parameters": {
            "comp": {"kmax": 3.0},
            "kpt": {"div1": 4, "div2": 4, "div3": 4},
        },
        "wf_parameters": {
            "mode": "energy",
            "fleur_runmax": 10,
            "itmax_per_run": 300,
            "density_converged": 1.0e-4,
            "energy_converged": 0.01,
        },
        "inpxml_changes": {"imix": "straight", "alpha": 0.05},
        "kpoint_mesh": (4, 4, 4),
        "restart_kpoints_factor": 2,
    },
}


# ---------------------------------------------------------------------------
# inp.xml loading / writing via masci_tools
# ---------------------------------------------------------------------------


def _load_inp_xml_with_schema(inp_xml: Path):
    """Return (xmltree, schema_dict) using masci_tools, the same loader
    aiida-fleur's FleurinpData.load_inpxml uses."""
    from masci_tools.io.fleur_xml import load_inpxml

    with open(inp_xml, "rb") as fh:
        xmltree, schema_dict = load_inpxml(fh)
    return xmltree, schema_dict


def _write_inp_xml(xmltree, inp_xml: Path) -> None:
    # masci_tools operates on lxml etree; write it back. We avoid clear_xml
    # (which may rewrite included files) since we edit inp.xml directly.
    xmltree.write(str(inp_xml), xml_declaration=True, encoding="UTF-8")


def _find_attrib_by_local(root, local_name: str):
    """Find the first element whose local tag name matches and return it.
    Works with or without XML namespaces."""
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        if e.tag.split("}")[-1] == local_name:
            return e
    return None


def _find_attrib_on_tag(root, tag_local: str, attrib: str):
    """Find the first element with local tag ``tag_local`` that has attribute
    ``attrib`` and return the element (so the caller can set the attribute)."""
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        if e.tag.split("}")[-1] == tag_local and attrib in e.attrib:
            return e
    # fallback: tag may be the attribute's parent with a different name
    return None


def _format_attr_value(attrib: str, value: Any) -> str:
    """Format a Python value for an inp.xml attribute. FLEUR's schema expects
    booleans as 'T'/'F' (not Python's 'True'/'False'), and floats with enough
    precision. Integers as-is."""
    if isinstance(value, bool):
        return "T" if value else "F"
    return str(value)


def apply_inpxml_changes(
    inp_xml: Path,
    changes: dict[str, Any],
    kpoint_mesh: Optional[tuple[int, int, int]] = None,
) -> None:
    """Apply simple attribute changes to inp.xml directly via lxml, without
    masci_tools. This works across FLEUR input schema versions (0.37 / 0.39)
    because we only touch well-known attributes by local name.

    changes: {attrib_name: value}. Known attributes we set:
        itmax, imix, alpha, l_f, f_level, Kmax
    kpoint_mesh: (nx, ny, nz) - replaces the active k-point list's nx/ny/nz.
    """
    if not changes and not kpoint_mesh:
        return
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(inp_xml), parser)
    root = tree.getroot()

    # Map of which parent tag holds each attribute (best-effort; we search
    # by attribute name across the whole tree if the tag guess misses).
    tag_hints = {
        "itmax": "scfLoop",
        "imix": "scfLoop",
        "alpha": "scfLoop",
        "l_f": "geometryOptimization",
        "f_level": "geometryOptimization",
        "Kmax": "cutoffs",
    }

    for attrib, value in changes.items():
        # try the hinted parent tag first
        el = None
        hint = tag_hints.get(attrib)
        if hint:
            el = _find_attrib_by_local(root, hint)
            if el is not None and attrib not in el.attrib:
                el = None
        # fall back to scanning for the attribute anywhere
        if el is None:
            for e in root.iter():
                if not isinstance(e.tag, str):
                    continue
                if attrib in e.attrib:
                    el = e
                    break
        if el is None:
            # attribute doesn't exist on any element. For well-known force
            # attributes (l_f, f_level) on geometryOptimization, add it.
            if attrib in ("l_f", "f_level") and hint:
                geo = _find_attrib_by_local(root, hint)
                if geo is not None:
                    geo.attrib[attrib] = _format_attr_value(attrib, value)
                    continue
            import sys

            print(
                f"[run_fleur_scf] WARNING: inpxml_changes attribute '{attrib}' "
                f"not found in inp.xml, skipping",
                file=sys.stderr,
            )
            continue
        el.attrib[attrib] = _format_attr_value(attrib, value)

    if kpoint_mesh:
        # find the first kPointList with type='mesh' and set nx/ny/nz
        for e in root.iter():
            if not isinstance(e.tag, str):
                continue
            if e.tag.split("}")[-1] == "kPointList" and e.get("type") == "mesh":
                e.attrib["nx"] = str(int(kpoint_mesh[0]))
                e.attrib["ny"] = str(int(kpoint_mesh[1]))
                e.attrib["nz"] = str(int(kpoint_mesh[2]))
                break

    tree.write(str(inp_xml), xml_declaration=True, encoding="UTF-8")


def get_kpoint_mesh(inp_xml: Path) -> tuple[int, int, int]:
    """Read the active k-point mesh (nx, ny, nz) from the kPointList currently
    in use (first one with type='mesh')."""
    tree = etree.parse(str(inp_xml))
    root = tree.getroot()
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        if e.tag.split("}")[-1] == "kPointList" and e.get("type") == "mesh":
            return (
                int(float(e.get("nx", "0"))),
                int(float(e.get("ny", "0"))),
                int(float(e.get("nz", "0"))),
            )
    return (0, 0, 0)


# ---------------------------------------------------------------------------
# out.xml convergence parsing
# ---------------------------------------------------------------------------


def _local(e) -> str:
    return e.tag.split("}")[-1] if isinstance(e.tag, str) else ""


def parse_out_xml(out_xml: Path) -> dict[str, Any]:
    """Pull the total iteration count, last charge distance, total energy and
    last energy difference from out.xml. Returns {} on parse failure or if
    the file is truncated (FLEUR still running / killed mid-iteration)."""
    if not out_xml.exists():
        return {}
    # Recover parser: if the file is truncated we still want the data from the
    # iterations that completed before the cutoff.
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        tree = etree.parse(str(out_xml), parser)
    except Exception:
        return {}
    root = tree.getroot()

    info: dict[str, Any] = {}
    iters = [e for e in root.iter() if _local(e) == "iteration"]
    # overallNumber tracks total iterations across restarts
    overall = [
        int(e.get("overallNumber", "0")) for e in iters if e.get("overallNumber")
    ]
    if overall:
        info["n_iterations_xml"] = max(overall)
    else:
        info["n_iterations_xml"] = len(iters)

    # total energies per iteration (attribute 'value' on totalEnergy)
    energies = []
    dists = []
    for it in iters:
        for c in it:
            ln = _local(c)
            if ln == "totalEnergy" and c.get("value"):
                try:
                    energies.append(float(c.get("value")))
                except ValueError:
                    pass
            if ln == "densityConvergence":
                for cc in c:
                    if _local(cc) == "chargeDensity" and cc.get("distance"):
                        try:
                            dists.append(float(cc.get("distance")))
                        except ValueError:
                            pass
    if dists:
        info["last_charge_distance"] = dists[-1]
    if energies:
        info["total_energy_htr"] = energies[-1]
        if len(energies) >= 2:
            info["energy_diff_htr"] = abs(energies[-1] - energies[-2])
    return info


# ---------------------------------------------------------------------------
# Run logic
# ---------------------------------------------------------------------------


@dataclass
class ScfResult:
    converged: bool
    n_runs: int
    total_iterations: int
    last_charge_distance: Optional[float]
    total_energy_htr: Optional[float]
    energy_diff_htr: Optional[float]
    elapsed_sec: float
    forces_present: bool
    forces_lines: int = 0
    workdir: str = ""
    preset: str = ""
    restarts: list[dict[str, Any]] = field(default_factory=list)
    error: str = ""


def _ase_to_fleur_inpgen_text(atoms, title: str = "phonopy_displaced") -> str:
    from io import StringIO
    from ase.io import write as ase_write

    buf = StringIO()
    ase_write(buf, atoms, format="fleur-inpgen", parameters={"title": title})
    return buf.getvalue()


def _run_inpgen(inpgen_bin: str, workdir: Path, fleur_inp_text: str) -> Path:
    """Write fleur.inp, run inpgen -inc +all -noco, return path to inp.xml."""
    # FLEUR develop (8.1) refuses to overwrite an existing inp.xml, so remove
    # any stale inp.xml + schemas + cdn1 from a previous run in this workdir.
    for stale in (
        "inp.xml",
        "out.xml",
        "cdn1",
        "FleurInputSchema.xsd",
        "FleurOutputSchema.xsd",
    ):
        p = workdir / stale
        if p.exists():
            p.unlink()
    inp_path = workdir / "fleur.inp"
    inp_path.write_text(fleur_inp_text)
    cmd = [inpgen_bin, "-f", "fleur.inp", "-inc", "+all", "-noco"]
    p = subprocess.run(cmd, cwd=str(workdir), capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"inpgen failed (rc={p.returncode}):\nSTDOUT:\n{p.stdout}\n"
            f"STDERR:\n{p.stderr}"
        )
    inp_xml = workdir / "inp.xml"
    if not inp_xml.exists():
        raise RuntimeError(f"inpgen produced no inp.xml\nSTDERR:\n{p.stderr}")
    return inp_xml


def _ensure_schema(fleur_bin: str, workdir: Path) -> None:
    """Copy the input/output schema shipped next to the fleur binary into the
    workdir. FLEUR develop (MaX 8.x) validates inp.xml strictly and the schema
    baked into the binary may lag behind the inp.xml version inpgen produces,
    so we always overwrite with the shipped schema if present."""
    fleur_bin_dir = Path(fleur_bin).resolve().parent
    for schema_name in ("FleurInputSchema.xsd", "FleurOutputSchema.xsd"):
        shipped = fleur_bin_dir / schema_name
        if shipped.exists():
            shutil.copy2(shipped, workdir / schema_name)


def _run_fleur(
    fleur_bin: str,
    workdir: Path,
    mpi_procs: int = 1,
    with_mpi: bool = True,
    itmax: Optional[int] = None,
) -> dict[str, Any]:
    """Run one fleur_MPI invocation in workdir."""
    inp_xml = workdir / "inp.xml"
    if itmax is not None:
        apply_inpxml_changes(inp_xml, {"itmax": int(itmax)})
    # Ensure the schema shipped with this fleur binary is in the workdir
    # (FLEUR dumps its own baked-in schema on startup, which may be stale).
    _ensure_schema(fleur_bin, workdir)

    # Build a clean environment. FLEUR auto-detects OMP threads and will
    # oversubscribe the CPU when several MPI ranks each spawn N_OMP threads
    # on the same node. Pin OMP to 1 so MPI ranks map 1:1 to cores.
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = "1"
    # Allow running mpirun as root (needed on Vultr bare metal)
    env["OMPI_ALLOW_RUN_AS_ROOT"] = "1"
    env["OMPI_ALLOW_RUN_AS_ROOT_CONFIRM"] = "1"

    if with_mpi and mpi_procs > 1:
        # Prefer the system OpenMPI mpirun (/usr/bin/mpirun.openmpi, 4.1.4)
        # over any conda-installed prterun (OpenMPI 5.x), which is incompatible
        # with FLEUR 6.2 built against system OpenMPI.
        mpirun_bin = os.environ.get("MPIRUN_BIN", "")
        if not mpirun_bin or not os.path.exists(mpirun_bin):
            for cand in ("/usr/bin/mpirun.openmpi", "/usr/bin/mpirun"):
                if os.path.exists(cand):
                    mpirun_bin = cand
                    break
        if not mpirun_bin:
            mpirun_bin = "mpirun"
        cmd = [
            mpirun_bin,
            "--allow-run-as-root",
            "--oversubscribe",
            "-np",
            str(mpi_procs),
            fleur_bin,
            "-no_cdn_hdf",
        ]
    else:
        cmd = [fleur_bin, "-no_cdn_hdf"]
    t0 = time.time()
    with open(workdir / "fleur.stdout", "w") as fout:
        p = subprocess.run(
            cmd,
            cwd=str(workdir),
            stdout=fout,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
    elapsed = time.time() - t0
    out: dict[str, Any] = {
        "rc": p.returncode,
        "elapsed_sec": elapsed,
    }
    out.update(parse_out_xml(workdir / "out.xml"))
    return out


def _check_converged(run_info: dict[str, Any], wf_parameters: dict[str, Any]) -> bool:
    """Decide if the SCF converged. A non-zero FLEUR return code means the
    process crashed and must never be considered converged. energy mode
    compares |E_n-E_{n-1}|, density mode compares the last charge density
    distance."""
    if run_info.get("rc", 0) != 0:
        return False
    mode = wf_parameters.get("mode", "energy")
    if mode == "density":
        if run_info.get("last_charge_distance") is not None:
            thr = float(wf_parameters.get("density_converged", 2e-5))
            return float(run_info["last_charge_distance"]) <= thr
        return False
    # energy / spex
    ediff = run_info.get("energy_diff_htr")
    if ediff is not None:
        thr = float(wf_parameters.get("energy_converged", 0.002))
        return ediff <= thr
    return False


# Conversion factor: FLEUR forces are in Hartree/bohr, phonopy default (vasp)
# expects eV/Angstrom.
#   1 Hartree = 27.211386245988 eV
#   1 bohr    = 0.529177210903  Angstrom
#   factor   = 27.211386245988 / 0.529177210903 = 51.422067476532
HTR_PER_BOHR_TO_EV_PER_ANG = 51.422067476532


def write_forces_file_from_out_xml(out_xml: Path, forces_file: Path) -> int:
    """Extract forces from out.xml (totalForcesOnRepresentativeAtoms/forceTotal)
    and write a FORCES file in the two-line-per-atom format phonopy expects:

        F_x F_y F_z
        force

    FLEUR 6.2 does not emit a standalone FORCES text file, so we synthesize
    one from out.xml. Forces in out.xml are in Hartree/bohr (F_x/F_y/F_z
    attributes on forceTotal). They are converted to eV/Angstrom here so that
    phonopy (which defaults to the vasp unit system: Angstrom + eV/Angstrom)
    receives consistent units.

    Returns the number of force entries written.
    """
    parser = etree.XMLParser(recover=True, huge_tree=True)
    try:
        tree = etree.parse(str(out_xml), parser)
    except Exception:
        return 0
    root = tree.getroot()
    forces = []
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        if e.tag.split("}")[-1] == "forceTotal":
            fx = e.get("F_x")
            fy = e.get("F_y")
            fz = e.get("F_z")
            if fx is not None and fy is not None and fz is not None:
                forces.append((float(fx), float(fy), float(fz)))
    if not forces:
        return 0
    with open(forces_file, "w") as fh:
        for fx, fy, fz in forces:
            fh.write(
                f"   {fx * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}   "
                f"{fy * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}   "
                f"{fz * HTR_PER_BOHR_TO_EV_PER_ANG: .16E}\n"
            )
            fh.write("      force\n")
    return len(forces)


def run_scf(
    atoms,
    workdir: Path,
    inpgen_bin: str,
    fleur_bin: str,
    preset: str = "baseline",
    mpi_procs: int = 1,
    with_mpi: bool = True,
    do_forces: bool = False,
    f_level: int = 0,
) -> ScfResult:
    """Run inpgen + fleur_MPI for one structure, optionally a forces run, and
    (for tuningB/tuningC) a restart with halved k-point mesh if the first run
    did not converge."""
    preset_def = PRESETS[preset]
    wf_parameters = dict(preset_def["wf_parameters"])
    inpxml_changes = dict(preset_def["inpxml_changes"])
    kpoint_mesh = preset_def.get("kpoint_mesh")
    restart_factor = preset_def.get("restart_kpoints_factor")

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    result = ScfResult(
        converged=False,
        n_runs=0,
        total_iterations=0,
        last_charge_distance=None,
        total_energy_htr=None,
        energy_diff_htr=None,
        elapsed_sec=0.0,
        forces_present=False,
        workdir=str(workdir),
        preset=preset,
    )

    try:
        # 1. inpgen
        inp_text = _ase_to_fleur_inpgen_text(atoms, title=preset)
        inp_xml = _run_inpgen(inpgen_bin, workdir, inp_text)
        # 2. apply inpxml_changes (mixing scheme, kmax via attribs)
        #    Plus kmax if the preset defines it.
        changes = dict(inpxml_changes)
        if "comp" in preset_def["calc_parameters"]:
            kmax = preset_def["calc_parameters"]["comp"].get("kmax")
            if kmax is not None:
                changes["Kmax"] = kmax
        apply_inpxml_changes(inp_xml, changes, kpoint_mesh=kpoint_mesh)
        # 3. first SCF run
        itmax = int(wf_parameters.get("itmax_per_run", 60))
        run_info = _run_fleur(fleur_bin, workdir, mpi_procs, with_mpi, itmax=itmax)
        result.n_runs = 1
        result.total_iterations = int(run_info.get("n_iterations_xml", 0))
        result.last_charge_distance = run_info.get("last_charge_distance")
        result.total_energy_htr = run_info.get("total_energy_htr")
        result.energy_diff_htr = run_info.get("energy_diff_htr")
        result.restarts.append(
            {
                "run": 1,
                "rc": run_info["rc"],
                **{
                    k: v
                    for k, v in run_info.items()
                    if k
                    in (
                        "last_charge_distance",
                        "total_energy_htr",
                        "energy_diff_htr",
                        "n_iterations_xml",
                        "elapsed_sec",
                    )
                },
            }
        )
        converged = _check_converged(run_info, wf_parameters)
        result.converged = converged

        # 4. restart if needed and configured
        if not converged and restart_factor:
            cur_mesh = get_kpoint_mesh(inp_xml)
            if any(cur_mesh):
                # snapshot out.xml before restart overwrites it
                shutil.copy2(workdir / "out.xml", workdir / "out_scf_run1.xml")
                new_mesh = tuple(max(1, d // restart_factor) for d in cur_mesh)
                apply_inpxml_changes(inp_xml, {}, kpoint_mesh=new_mesh)
                run_info2 = _run_fleur(
                    fleur_bin, workdir, mpi_procs, with_mpi, itmax=itmax
                )
                result.n_runs = 2
                result.total_iterations += int(run_info2.get("n_iterations_xml", 0))
                if run_info2.get("last_charge_distance") is not None:
                    result.last_charge_distance = run_info2["last_charge_distance"]
                if run_info2.get("total_energy_htr") is not None:
                    result.total_energy_htr = run_info2["total_energy_htr"]
                if run_info2.get("energy_diff_htr") is not None:
                    result.energy_diff_htr = run_info2["energy_diff_htr"]
                result.restarts.append(
                    {
                        "run": 2,
                        "kpoint_mesh": list(new_mesh),
                        "rc": run_info2["rc"],
                        **{
                            k: v
                            for k, v in run_info2.items()
                            if k
                            in (
                                "last_charge_distance",
                                "total_energy_htr",
                                "energy_diff_htr",
                                "n_iterations_xml",
                                "elapsed_sec",
                            )
                        },
                    }
                )
                result.converged = _check_converged(run_info2, wf_parameters)

        # 5. optional forces run (l_f=True) to produce forces.
        #    Forces are only computed from a *converged* SCF density. If SCF
        #    did not converge (or crashed), skip the forces run entirely —
        #    forces from an unconverged density are physically meaningless and
        #    would produce imaginary phonon modes.
        #    Use itmax=1: read forces from the already-converged density,
        #    do not continue iterating. FLEUR 6.2 does not write a separate
        #    FORCES text file; forces live in out.xml under
        #    totalForcesOnRepresentativeAtoms/forceTotal. We extract them into
        #    a FORCES file (converting to eV/Angstrom) in the two-line format
        #    phonopy expects.
        #
        #    The forces run overwrites out.xml, so we snapshot the SCF out.xml
        #    to out_scf.xml first and parse convergence from there.
        if do_forces and result.converged:
            scf_out_xml = workdir / "out_scf.xml"
            shutil.copy2(workdir / "out.xml", scf_out_xml)
            apply_inpxml_changes(inp_xml, {"l_f": True, "f_level": int(f_level)})
            forces_info = _run_fleur(fleur_bin, workdir, mpi_procs, with_mpi, itmax=1)
            forces_file = workdir / "FORCES"
            nforce = write_forces_file_from_out_xml(workdir / "out.xml", forces_file)
            result.forces_present = nforce > 0
            result.forces_lines = nforce
            # Re-parse SCF convergence from the snapshot (the live out.xml now
            # holds the forces run, which has only 1 iteration).
            scf_info = parse_out_xml(scf_out_xml)
            if scf_info.get("n_iterations_xml"):
                result.total_iterations = int(scf_info["n_iterations_xml"])
            if scf_info.get("last_charge_distance") is not None:
                result.last_charge_distance = scf_info["last_charge_distance"]
            if scf_info.get("total_energy_htr") is not None:
                result.total_energy_htr = scf_info["total_energy_htr"]
            if scf_info.get("energy_diff_htr") is not None:
                result.energy_diff_htr = scf_info["energy_diff_htr"]
            result.restarts.append(
                {
                    "run_forces": True,
                    "rc": forces_info["rc"],
                    "forces_present": result.forces_present,
                    "forces_lines": result.forces_lines,
                }
            )
    except Exception as e:
        result.error = f"{type(e).__name__}: {e}"
        import traceback

        (workdir / "scf_error.log").write_text(traceback.format_exc())
    result.elapsed_sec = time.time() - t0
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_poscar(path: str):
    from ase.io import read as ase_read

    return ase_read(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="Run inpgen + fleur_MPI on one POSCAR")
    r.add_argument("--poscar", required=True)
    r.add_argument("--preset", choices=list(PRESETS), default="baseline")
    r.add_argument(
        "--inpgen",
        default=os.environ.get("FLEUR_INPGEN_PATH", "/root/fleur/build/inpgen"),
    )
    r.add_argument(
        "--fleur",
        default=os.environ.get("FLEUR_MPI_PATH", "/root/fleur/build/fleur_MPI"),
    )
    r.add_argument("--workdir", required=True)
    r.add_argument("--mpi-procs", type=int, default=1)
    r.add_argument("--no-mpi", action="store_true")
    r.add_argument(
        "--forces", action="store_true", help="do a forces run (l_f=True) after SCF"
    )
    r.add_argument("--f-level", type=int, default=0)
    r.add_argument("--json", help="write ScfResult as JSON to this path")

    args = ap.parse_args()
    if args.cmd == "run":
        atoms = _load_poscar(args.poscar)
        res = run_scf(
            atoms,
            Path(args.workdir),
            args.inpgen,
            args.fleur,
            preset=args.preset,
            mpi_procs=args.mpi_procs,
            with_mpi=not args.no_mpi,
            do_forces=args.forces,
            f_level=args.f_level,
        )
        print(json.dumps(asdict(res), indent=2))
        if args.json:
            Path(args.json).write_text(json.dumps(asdict(res), indent=2))


if __name__ == "__main__":
    main()
