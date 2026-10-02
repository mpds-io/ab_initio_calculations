from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


THZ_TO_CM1 = 33.3564
CM1_TO_THZ = 1.0 / THZ_TO_CM1


class Constants:
    kb_J = 1.3806504e-23
    PlanckConstant = 4.13566733e-15
    Hbar = PlanckConstant / (2 * np.pi)
    Avogadro = 6.02214179e23
    SpeedOfLight = 299792458
    AMU = 1.6605402e-27
    Joule = 1.0
    EV = 1.60217733e-19
    Angstrom = 1.0e-10
    THzToEv = PlanckConstant * 1e12
    Kb = kb_J / EV
    THzToCm = 1.0e12 / (SpeedOfLight * 100)
    CmToEv = THzToEv / THzToCm
    VaspToEv = np.sqrt(EV / AMU) / Angstrom / (2 * np.pi) * PlanckConstant
    VaspToTHz = np.sqrt(EV / AMU) / Angstrom / (2 * np.pi) / 1e12
    VaspToCm = VaspToTHz * THzToCm
    EvTokJmol = EV / 1000 * Avogadro


class ThermalPropertiesBase:
    def __init__(self, eigenvalues, weights=None):
        self.temperature = 0
        self.eigenvalues = eigenvalues
        if weights is not None:
            self.weights = weights
        else:
            self.weights = np.ones(eigenvalues.shape[0], dtype=int)
        self.nqpoint = eigenvalues.shape[0]

    def set_temperature(self, temperature):
        self.temperature = temperature

    def get_free_energy(self):
        def func(temp, omega):
            return (
                Constants.Kb
                * temp
                * np.log(1.0 - np.exp((-omega) / (Constants.Kb * temp)))
            )

        free_energy = self.get_thermal_property(func)
        return (
            free_energy / np.sum(self.weights) * Constants.EvTokJmol
            + self.zero_point_energy
        )

    def get_free_energy2(self):
        if self.temperature > 0:

            def func(temp, omega):
                return (
                    Constants.Kb
                    * temp
                    * np.log(2.0 * np.sinh(omega / (2 * Constants.Kb * temp)))
                )

            free_energy = self.get_thermal_property(func)
            return free_energy / np.sum(self.weights) * Constants.EvTokJmol
        else:
            return self.zero_point_energy

    def get_heat_capacity_v(self):
        def func(temp, omega):
            expVal = np.exp(omega / (Constants.Kb * temp))
            return (
                Constants.Kb
                * (omega / (Constants.Kb * temp)) ** 2
                * expVal
                / (expVal - 1.0) ** 2
            )

        cv = self.get_thermal_property(func)
        return cv / np.sum(self.weights) * Constants.EvTokJmol

    def get_entropy(self):
        def func(temp, omega):
            val = omega / (2 * Constants.Kb * temp)
            return 1.0 / (2 * temp) * omega * np.cosh(val) / np.sinh(
                val
            ) - Constants.Kb * np.log(2 * np.sinh(val))

        entropy = self.get_thermal_property(func)
        return entropy / np.sum(self.weights) * Constants.EvTokJmol

    def get_entropy2(self):
        def func(temp, omega):
            val = omega / (Constants.Kb * temp)
            return -Constants.Kb * np.log(1 - np.exp(-val)) + 1.0 / temp * omega / (
                np.exp(val) - 1
            )

        entropy = self.get_thermal_property(func)
        return entropy / np.sum(self.weights) * Constants.EvTokJmol


class ThermalProperties(ThermalPropertiesBase):
    def __init__(
        self,
        eigenvalues,
        weights=None,
        factor=Constants.VaspToTHz,
        cutoff_eigenvalue=None,
    ):
        ThermalPropertiesBase.__init__(self, eigenvalues, weights)
        self.factor = factor
        if cutoff_eigenvalue:
            self.cutoff_eigenvalue = cutoff_eigenvalue
        else:
            self.cutoff_eigenvalue = 0.0
        self._frequencies()
        self._zero_point_energy()
        self._high_T_entropy()

    def _frequencies(self):
        frequencies = []
        for eigs in self.eigenvalues:
            frequencies.append(
                np.sqrt(np.extract(eigs > self.cutoff_eigenvalue, eigs))
                * self.factor
                * Constants.THzToEv
            )
        self.frequencies = frequencies

    def _zero_point_energy(self):
        z_energy = 0.0
        for i, freqs in enumerate(self.frequencies):
            z_energy += np.sum(1.0 / 2 * freqs) * self.weights[i]
        self.zero_point_energy = z_energy / np.sum(self.weights) * Constants.EvTokJmol

    def get_zero_point_energy(self):
        return self.zero_point_energy

    def _high_T_entropy(self):
        entropy = 0.0
        for i, freqs in enumerate(self.frequencies):
            entropy -= np.sum(np.log(freqs)) * self.weights[i]
        self.high_T_entropy = (
            entropy * Constants.Kb / np.sum(self.weights) * Constants.EvTokJmol
        )

    def get_high_T_entropy(self):
        return self.high_T_entropy

    def get_thermal_property(self, func):
        property = 0.0

        if self.temperature > 0:
            temp = self.temperature
            for i, freqs in enumerate(self.frequencies):
                property += np.sum(func(temp, freqs)) * self.weights[i]

        return property

    def get_c_thermal_properties(self):
        import phonopy._phonopy as phonoc

        if self.temperature > 0:
            return phonoc.thermal_properties(
                self.temperature,
                self.eigenvalues,
                self.weights,
                self.factor * Constants.THzToEv,
                self.cutoff_eigenvalue,
            )
        else:
            return (0.0, 0.0, 0.0)

    def plot_thermal_properties(self):
        import matplotlib.pyplot as plt

        temps, fe, entropy, cv = self.thermal_properties

        plt.plot(temps, fe, "r-")
        plt.plot(temps, entropy, "b-")
        plt.plot(temps, cv, "g-")
        plt.legend(
            ("Free energy [kJ/mol]", "Entropy [J/K/mol]", r"C$_\mathrm{V}$ [J/K/mol]"),
            "best",
            shadow=True,
        )
        plt.grid(True)
        plt.xlabel("Temperature [K]")

        return plt

    def set_thermal_properties(self, t_step=10, t_max=1000, t_min=0):
        t = t_min
        temps = []
        fe = []
        entropy = []
        cv = []
        while t < t_max + t_step / 2.0:
            self.set_temperature(t)
            temps.append(t)

            fe.append(self.get_free_energy())
            entropy.append(self.get_entropy() * 1000)
            cv.append(self.get_heat_capacity_v() * 1000)

            t += t_step

        thermal_properties = [temps, fe, entropy, cv]
        self.thermal_properties = np.array(thermal_properties)

    def get_thermal_properties(self):
        return self.thermal_properties

    def write_yaml(self):
        with open("thermal_properties.yaml", "w") as file:
            file.write("# Thermal properties / unit cell (natom)\n")
            file.write("\n")
            file.write("unit:\n")
            file.write("  temperature:   K\n")
            file.write("  free_energy:   kJ/mol\n")
            file.write("  entropy:       J/K/mol\n")
            file.write("  heat_capacity: J/K/mol\n")
            file.write("\n")
            file.write("natom: %5d\n" % ((self.eigenvalues[0].shape)[0] / 3))
            file.write("zero_point_energy: %15.7f\n" % self.zero_point_energy)
            file.write("high_T_entropy:    %15.7f\n" % (self.high_T_entropy * 1000))
            file.write("\n")
            file.write("thermal_properties:\n")
            temperatures, fe, entropy, cv = self.thermal_properties
            for i, t in enumerate(temperatures):
                file.write("- temperature:   %15.7f\n" % t)
                file.write("  free_energy:   %15.7f\n" % fe[i])
                file.write("  entropy:       %15.7f\n" % entropy[i])
                if np.isnan(cv[i]):
                    file.write("  heat_capacity: %15.7f\n" % 0)
                else:
                    file.write("  heat_capacity: %15.7f\n" % cv[i])
                file.write(
                    "  energy:        %15.7f\n" % (fe[i] + entropy[i] * t / 1000)
                )
                file.write("\n")


def _freqs_cm1_to_thz(freqs_cm1_per_q: list[list[float]]) -> np.ndarray:
    return np.array(
        [[f / THZ_TO_CM1 for f in modes] for modes in freqs_cm1_per_q], dtype=float
    )


def _freqs_cm1_to_vasp_eigs(freqs_cm1_per_q: list[list[float]]) -> np.ndarray:
    freqs_thz = _freqs_cm1_to_thz(freqs_cm1_per_q)
    return (freqs_thz / Constants.VaspToTHz) ** 2


def _freqs_thz_to_vasp_eigs(freqs_thz_per_q: list[list[float]]) -> np.ndarray:
    freqs_thz = np.array(freqs_thz_per_q, dtype=float)
    return (freqs_thz / Constants.VaspToTHz) ** 2


def load_crystal_phonons_freqs(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load CRYSTAL phonon frequencies, returning (freqs_thz, weights).

    freqs_thz shape (n_q, n_bands) in THz; negative = imaginary.
    """
    with open(path) as f:
        d = json.load(f)
    modes_freqs = d["phonons"]["modes_freqs"]
    q_keys = list(modes_freqs.keys())
    freqs_cm = [modes_freqs[q] for q in q_keys]
    freqs_thz = _freqs_cm1_to_thz(freqs_cm)
    weights = np.ones(len(q_keys), dtype=int)
    return freqs_thz, weights


def load_crystal_phonons(path: Path) -> tuple[np.ndarray, np.ndarray]:
    freqs_thz, weights = load_crystal_phonons_freqs(path)
    eigs = (freqs_thz / Constants.VaspToTHz) ** 2
    return eigs, weights


def load_fleur_phonons_freqs(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse phonon_frequencies.txt, returning (freqs_thz, weights).

    freqs_thz shape (n_q, n_bands) in THz; negative = imaginary.
    Handles both cm^-1 (current) and THz (legacy) file formats.
    """
    freqs: dict[str, list[float]] = {}
    current_q: Optional[str] = None
    is_thz = False
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("q-point"):
                parts = line.split(":")
                current_q = parts[0].replace("q-point ", "").strip()
                freqs[current_q] = []
            elif line.startswith("band") and current_q:
                value_part = line.split(":")[1]
                if "THz" in value_part:
                    is_thz = True
                val = float(
                    value_part.replace("cm^-1", "")
                    .replace("THz", "")
                    .replace("*", "")
                    .strip()
                )
                freqs[current_q].append(val)
    q_keys = list(freqs.keys())
    freqs_per_q = [freqs[q] for q in q_keys]
    if is_thz:
        freqs_thz = np.array(freqs_per_q, dtype=float)
    else:
        freqs_thz = _freqs_cm1_to_thz(freqs_per_q)
    weights = np.ones(len(q_keys), dtype=int)
    return freqs_thz, weights


def load_fleur_phonons(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse phonon_frequencies.txt, returning (vasp_eigs, weights)."""
    freqs_thz, weights = load_fleur_phonons_freqs(path)
    eigs = (freqs_thz / Constants.VaspToTHz) ** 2
    return eigs, weights


class _MockMesh:
    """Lightweight mock of a phonopy Mesh object for ThermalProperties."""

    class _Primitive:
        Z = 1

    class _DynamicalMatrix:
        def __init__(self):
            self.primitive = _MockMesh._Primitive()

    def __init__(self, frequencies: np.ndarray, weights: np.ndarray):
        self.frequencies = frequencies  # THz, shape (n_q, n_bands)
        self.weights = weights  # ints, shape (n_q,)
        self.eigenvectors = None
        self.dynamical_matrix = self._DynamicalMatrix()


def _integrate_one_phonopy(
    freqs_thz: np.ndarray, weights: np.ndarray, t_max: int, t_step: int, t_min: int
) -> dict:
    from phonopy.phonon.thermal_properties import ThermalProperties as PhTP

    mesh = _MockMesh(freqs_thz, weights)
    tp = PhTP(mesh, pretend_real=True)
    tp.run(t_min=t_min, t_max=t_max, t_step=t_step)
    temps, fe, entropy, cv = tp.thermal_properties
    tp_arr = np.column_stack([temps, fe, entropy, cv])
    return {
        "thermal_properties": tp_arr,
        "zero_point_energy": float(tp.zero_point_energy),
        "high_T_entropy": None,
        "n_qpoints": int(freqs_thz.shape[0]),
    }


def _integrate_one_ase(
    freqs_thz: np.ndarray, t_max: int, t_step: int, t_min: int
) -> dict:
    from ase.thermochemistry import HarmonicThermo

    n_qpoints = freqs_thz.shape[0]
    # HarmonicThermo takes a flat list of vibrational energies in eV.
    # It has no q-point weighting, so we flatten all q-points and divide
    # the result by n_qpoints (equivalent to equal weights = 1/n_q).
    # ASE raises on imaginary modes; use absolute values
    flat_ev = np.abs(freqs_thz).flatten() * Constants.THzToEv
    ht = HarmonicThermo(flat_ev.tolist(), ignore_imag_modes=True)

    temps = list(range(t_min, t_max + t_step // 2, t_step))
    fe_arr, s_arr, cv_arr = [], [], []
    for t in temps:
        if t == 0:
            fe = ht.get_ZPE_correction()
            s = 0.0
            cv = 0.0
        else:
            fe = ht.get_helmholtz_energy(t, verbose=False)
            s = ht.get_entropy(t, verbose=False)
            # Cv = dU/dT via central finite difference
            u_plus = ht.get_internal_energy(t + 1, verbose=False)
            u_minus = ht.get_internal_energy(t - 1, verbose=False)
            cv = (u_plus - u_minus) / 2.0
        # Per-q-point average, then convert units
        # eV -> kJ/mol: * EvTokJmol (96.485)
        # eV/K -> J/K/mol: * EvTokJmol * 1000
        fe_arr.append(fe / n_qpoints * Constants.EvTokJmol)
        s_arr.append(s / n_qpoints * Constants.EvTokJmol * 1000)
        cv_arr.append(cv / n_qpoints * Constants.EvTokJmol * 1000)

    zpe = ht.get_ZPE_correction() / n_qpoints * Constants.EvTokJmol
    tp_arr = np.column_stack([temps, fe_arr, s_arr, cv_arr])
    return {
        "thermal_properties": tp_arr,
        "zero_point_energy": float(zpe),
        "high_T_entropy": None,
        "n_qpoints": int(n_qpoints),
    }


def integrate_phonons_phonopy(
    crystal_path: Optional[Path] = None,
    fleur_path: Optional[Path] = None,
    t_max: int = 1000,
    t_step: int = 10,
    t_min: int = 0,
) -> dict:
    """Integrate using phonopy's ThermalProperties (lazy import)."""
    result: dict = {"crystal": None, "fleur": None}

    if crystal_path is not None and Path(crystal_path).exists():
        try:
            freqs_thz, w = load_crystal_phonons_freqs(Path(crystal_path))
            result["crystal"] = _integrate_one_phonopy(
                freqs_thz, w, t_max, t_step, t_min
            )
        except Exception as e:
            logger.exception("Failed to integrate CRYSTAL phonons (phonopy): %s", e)
            result["crystal"] = {"error": str(e)}
    elif crystal_path is not None:
        result["crystal"] = {"error": f"file not found: {crystal_path}"}

    if fleur_path is not None and Path(fleur_path).exists():
        try:
            freqs_thz, w = load_fleur_phonons_freqs(Path(fleur_path))
            result["fleur"] = _integrate_one_phonopy(freqs_thz, w, t_max, t_step, t_min)
        except Exception as e:
            logger.exception("Failed to integrate FLEUR phonons (phonopy): %s", e)
            result["fleur"] = {"error": str(e)}
    elif fleur_path is not None:
        result["fleur"] = {"error": f"file not found: {fleur_path}"}

    return result


def integrate_phonons_ase(
    crystal_path: Optional[Path] = None,
    fleur_path: Optional[Path] = None,
    t_max: int = 1000,
    t_step: int = 10,
    t_min: int = 0,
) -> dict:
    """Integrate using ASE HarmonicThermo (lazy import).

    Note: ASE has no q-point weighting; results are averaged over q-points
    with equal weights. Imaginary modes are treated as |freq| via
    ignore_imag_modes=True.
    """
    result: dict = {"crystal": None, "fleur": None}

    if crystal_path is not None and Path(crystal_path).exists():
        try:
            freqs_thz, _ = load_crystal_phonons_freqs(Path(crystal_path))
            result["crystal"] = _integrate_one_ase(freqs_thz, t_max, t_step, t_min)
        except Exception as e:
            logger.exception("Failed to integrate CRYSTAL phonons (ase): %s", e)
            result["crystal"] = {"error": str(e)}
    elif crystal_path is not None:
        result["crystal"] = {"error": f"file not found: {crystal_path}"}

    if fleur_path is not None and Path(fleur_path).exists():
        try:
            freqs_thz, _ = load_fleur_phonons_freqs(Path(fleur_path))
            result["fleur"] = _integrate_one_ase(freqs_thz, t_max, t_step, t_min)
        except Exception as e:
            logger.exception("Failed to integrate FLEUR phonons (ase): %s", e)
            result["fleur"] = {"error": str(e)}
    elif fleur_path is not None:
        result["fleur"] = {"error": f"file not found: {fleur_path}"}

    return result


VALID_METHODS = ("custom", "phonopy", "ase")


def integrate_phonons(
    crystal_path: Optional[Path] = None,
    fleur_path: Optional[Path] = None,
    t_max: int = 1000,
    t_step: int = 10,
    t_min: int = 0,
    method: str = "custom",
) -> dict:
    """Integrate phonon thermodynamic properties.

    Args:
        crystal_path: Path to CRYSTAL phonon_data.json.
        fleur_path: Path to FLEUR phonon_frequencies.txt.
        t_max, t_step, t_min: Temperature grid in Kelvin.
        method: One of "custom" (our ThermalProperties fork),
            "phonopy" (phonopy's ThermalProperties), or "ase" (ASE HarmonicThermo).
    """
    if method == "custom":
        return _integrate_custom(crystal_path, fleur_path, t_max, t_step, t_min)
    elif method == "phonopy":
        return integrate_phonons_phonopy(crystal_path, fleur_path, t_max, t_step, t_min)
    elif method == "ase":
        return integrate_phonons_ase(crystal_path, fleur_path, t_max, t_step, t_min)
    else:
        raise ValueError(f"Unknown method '{method}'. Valid: {VALID_METHODS}")


def _integrate_custom(
    crystal_path: Optional[Path] = None,
    fleur_path: Optional[Path] = None,
    t_max: int = 1000,
    t_step: int = 10,
    t_min: int = 0,
) -> dict:
    result: dict = {"crystal": None, "fleur": None}

    if crystal_path is not None and Path(crystal_path).exists():
        try:
            eigs, w = load_crystal_phonons(Path(crystal_path))
            tp = ThermalProperties(eigs, w)
            tp.set_thermal_properties(t_step=t_step, t_max=t_max, t_min=t_min)
            result["crystal"] = {
                "thermal_properties": tp.get_thermal_properties().T,
                "zero_point_energy": tp.get_zero_point_energy(),
                "high_T_entropy": tp.get_high_T_entropy(),
                "n_qpoints": int(eigs.shape[0]),
            }
        except Exception as e:
            logger.exception("Failed to integrate CRYSTAL phonons: %s", e)
            result["crystal"] = {"error": str(e)}
    elif crystal_path is not None:
        result["crystal"] = {"error": f"file not found: {crystal_path}"}

    if fleur_path is not None and Path(fleur_path).exists():
        try:
            eigs, w = load_fleur_phonons(Path(fleur_path))
            tp = ThermalProperties(eigs, w)
            tp.set_thermal_properties(t_step=t_step, t_max=t_max, t_min=t_min)
            result["fleur"] = {
                "thermal_properties": tp.get_thermal_properties().T,
                "zero_point_energy": tp.get_zero_point_energy(),
                "high_T_entropy": tp.get_high_T_entropy(),
                "n_qpoints": int(eigs.shape[0]),
            }
        except Exception as e:
            logger.exception("Failed to integrate FLEUR phonons: %s", e)
            result["fleur"] = {"error": str(e)}
    elif fleur_path is not None:
        result["fleur"] = {"error": f"file not found: {fleur_path}"}

    return result


def format_report(result: dict, method: str = "custom") -> str:
    lines: list[str] = []
    lines.append(
        f"# Phonon thermodynamic integration (method: {method}): CRYSTAL vs FLEUR\n"
    )

    for src in ("crystal", "fleur"):
        lines.append(f"## {src.upper()}\n")
        d = result.get(src)
        if d is None:
            lines.append("_(not provided)_\n")
            continue
        if "error" in d:
            lines.append(f"Error: {d['error']}\n")
            continue
        lines.append(f"- q-points: {d['n_qpoints']}")
        lines.append(f"- zero point energy [kJ/mol]: {d['zero_point_energy']:.7f}")
        if d.get("high_T_entropy") is not None:
            lines.append(
                f"- high-T entropy [J/K/mol]: {d['high_T_entropy'] * 1000:.7f}\n"
            )
        else:
            lines.append("")
        tp = d["thermal_properties"]
        temps, fe, entropy, cv = tp[:, 0], tp[:, 1], tp[:, 2], tp[:, 3]
        lines.append(
            "| T [K] | Free energy [kJ/mol] | Entropy [J/K/mol] | C_V [J/K/mol] |"
        )
        lines.append("|---|---|---|---|")
        for i, t in enumerate(temps):
            cv_val = 0.0 if np.isnan(cv[i]) else cv[i]
            lines.append(f"| {t:.1f} | {fe[i]:.7f} | {entropy[i]:.7f} | {cv_val:.7f} |")
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integrate phonon thermodynamic properties from CRYSTAL and FLEUR calculations.",
    )
    parser.add_argument(
        "--crystal",
        type=Path,
        default=None,
        help="Path to CRYSTAL phonon_data.json (frequencies in cm^-1).",
    )
    parser.add_argument(
        "--fleur",
        type=Path,
        default=None,
        help="Path to FLEUR phonon_frequencies.txt (frequencies in cm^-1).",
    )
    parser.add_argument("--t-max", type=int, default=1000, help="Max temperature [K].")
    parser.add_argument("--t-step", type=int, default=10, help="Temperature step [K].")
    parser.add_argument("--t-min", type=int, default=0, help="Min temperature [K].")
    parser.add_argument(
        "--method",
        choices=list(VALID_METHODS),
        default="custom",
        help="Integration method: custom (our fork), phonopy, or ase.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write markdown report to this file instead of stdout.",
    )
    args = parser.parse_args()

    if not args.crystal and not args.fleur:
        parser.error("at least one of --crystal or --fleur is required")

    result = integrate_phonons(
        crystal_path=args.crystal,
        fleur_path=args.fleur,
        t_max=args.t_max,
        t_step=args.t_step,
        t_min=args.t_min,
        method=args.method,
    )
    report = format_report(result, method=args.method)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
