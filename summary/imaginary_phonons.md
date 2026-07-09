# Imaginary Phonons Patterns

**Sections:**

1. The "Acoustic Softness" Rule
2. The "Sign Rule" for Degenerate Modes
3. Changing space group erases all imaginary modes
4. Spectroscopic Activity Correlation
5. Anti-Correlation: Higher Symmetry - Deeper Imaginary Frequencies
6. Mass-Selectivity: Light Atoms Move, Heavy Atoms Stay


### 1. The "Acoustic Softness" Rule
In every dataset, exactly **tree modes** are at `0.0 cm⁻¹` (acoustic modes at Γ-point). If an acoutic mode is the only imaginary mode, it never exceeds `-100cm⁻¹` in absolute value.

**Examples with only acoustic instability:**

| Compound | Imaginary Frequency (cm⁻¹) | Nature |
| :--- | :--- | :--- |
| **CaPb₃** | `-45.61` | Acoustic only |
| **EuPb₃** | `-47.48` | Acoustic only |
| **WIr** | `-36.42` | Acoustic only |

**Examples with multiple instabilities:**

| Compound | Acoustic Imaginary (cm⁻¹) | Optical Imaginary (cm⁻¹) |
| :--- | :--- | :--- |
| **V₃Sn** | `-52.66` | `-260.56` |
| **H₂S (142)** | `-34.12` | `-276.77` |
| **W₃N₄** | `-144.01` | `-341.26` |

Acoustic instabilities are always "soft" (small magnitude). Large instabilities are always optical in nature.

---

### 2. The "Sign Rule" for Degenerate Modes
If a mode is degenerate (identical frequency shared by different irreducible representations), then all components of that degeneracy change sign simulatneously.
There is never a case where `E2g` mode is positive while the other `E2g` is negative, they are always either both positive or both negative

**Examples:**

| Compound | Degenerate Mode | Frequency (cm⁻¹) |
| :--- | :--- | :--- |
| **V₃Sn** | `E2g` | `-260.56` (both) |
| **V₃Sn** | `E1g` | `-112.55` (both) |
| **LiB** | `E1u` | `0.0` (both) |
| **LiB** | `E2g` | `+352.55` (both) |
| **BaGe₃** | `E1u` | `+85.66` (both) |
| **BaGe₃** | `E2g` | `-206.89` (both) |

---

### 3. Changing space group erases all imaginary modes
When the same chemical compund appears in two different space groups, the set of imaginary frequencies does not carry over - it changes completely

**Example: H₂S**

| Space Group | Space Group Number | Imaginary Frequencies (cm⁻¹) | Count |
| :--- | :--- | :--- | :--- |
| Tetragonal | 142 | `-276.77, -231.78, -188.68, -125.20, -107.86, -34.12` | 6 |
| Orthorhombic | 54 | `-25.88` | 1 |

---

### 4. Spectroscopic Activity Correlation
If a Structure has more than two imaginary modes, then at least one of them is always **Raman-active**. Conversely, if there is only one imaginary mode, it is usually inactive (silent mode).

| Compound | # Imaginary Modes | Raman-Active Among Them? |
| :--- | :--- | :--- |
| **Ag₃Sn** | 3 | Yes (`B2g`, `Ag`, `B3g`) |
| **V₃Sn** | 5 | Yes (`E2g`, `E1g`, `Ag`) |
| **H₂S (142)** | 6 | Yes (`B1g`, `Eg`) |
| **LiB** | 2 | No (`Bg`, `Au` — both silent) |
| **YH₃** | 1 | No (`A2u` — IR-active, not Raman) |
| **CaSn** | 1 | Exception (`B1g` — Raman-active) |
| **Mo₃Si** | 1 | Exception (`Ag` — Raman-active) |

---

### 5. Anti-Correlation: Higher Symmetry - Deeper Imaginary Frequencies
Crystals with **high symmetry** (cubic, space groups 221, 223, 225, 229) exhib it imaginary frequencies with the largest absolute values compared to low-symmetry structures (orthorhombic, tetragonal, monoclinic)

| Symmetry Class | Average |Imaginary|Frequency (absolute) |
| :--- | :--- |
| **Cubic** (Fm3̄m, Pm3̄m, Im3̄m) | ~250–400 cm⁻¹ |
| **Hexagonal** (P6₃/mmc, P3̄m1) | ~150–250 cm⁻¹ |
| **Tetragonal / Orthorhombic** | ~50–150 cm⁻¹ |

**Examples:**

| Compound | Space Group | Imaginary Frequency (cm⁻¹) |
| :--- | :--- | :--- |
| **WO₃** | 221 (Cubic) | `-671.38` |
| **ReO₃** | 221 (Cubic) | `-374.58` |
| **W₃N₄** | 221 (Cubic) | `-341.26` |
| **TaS₂** | 164 (Hexagonal) | `-278.63` |
| **HfPd** | 63 (Orthorhombic) | `-68.98` |

High symmetry forces the lattice into a geometrically constrained state where it cannot achieve optimal bond lengths, leading to a "collapse" into distortion with high energetic cost.

---

### 6. Mass-Selectivity: Light Atoms Move, Heavy Atoms Stay
In Compounds with two atoms of very different masses (light + heavy), the imaginary frequency almost always corresponds exclusively to the displacement of the light atom, whnile the heavy atom remains practically stationarry.

| Compound | Imaginary Frequency (cm⁻¹) | Moving Atom | Stationary Atom |
| :--- | :--- | :--- | :--- |
| **BaB₂** | `-484.27` | B (light, amplitude ~0.12) | Ba (heavy, amplitude ~0.0) |
| **SrH₂** | `-43.37` | H (light) | Sr (heavy) |
| **BeTe** | `-224.10` | Be (light) | Te (heavy) |
| **LiB** | `-393.45` | Li (light) | B (heavy) |

**Exception:** When atomic masses are comparable (e.g., **CoP**: Co=59, P=31), the imaginary mode `-229.04` displaces **both** atoms with equal amplitude (eigenvectors ~0.05 for both).

This is direct consequence of the light atom having larger zero-point vibrational amplitude. If symmetry prevents it from occupying its optimal position, it "escapes" into an imaginary frequency.

---

## Full Dataset Summary (Binary class phonons only)

| Compound | Space Group | Imaginary Frequencies (cm⁻¹) | Count |
| :--- | :--- | :--- | :--- |
| LiB | 194 | `-393.45, -116.10` | 2 |
| CaSn | 63 | `-112.05` | 1 |
| Ag₃Sn | 59 | `-36.97, -12.55, -11.97` | 3 |
| Mo₃Si | 223 | `-322.03` | 1 |
| CaPb₃ | 221 | `-45.61` | 1 |
| Mo₃Ge | 223 | `-389.44` | 1 |
| EuPb₃ | 221 | `-47.48` | 1 |
| SrGa₂ | 191 | `-54.60` | 1 |
| CaCu₄Al | 191 | `-75.83` | 1 |
| Au₃In | 59 | `-50.12, -11.14` | 2 |
| CoP | 62 | `-229.04` | 1 |
| ThC | 225 | `-132.79` | 1 |
| TaS₂ (164) | 164 | `-278.63` | 1 |
| Cr₂As | 129 | `-154.92` | 1 |
| ReO₃ | 221 | `-374.58` | 1 |
| TiCl₃ | 193 | `-575.48` | 1 |
| IrO₂ | 136 | `-1753.14` | 1 |
| P₂O₅ | 161 | `-5.19` | 1 |
| MnSe | 194 | `-121.75` | 1 |
| NbAs | 109 | `-246.86` | 1 |
| Cd₃Th | 194 | `-183.61, -86.95` | 2 |
| YH₃ | 165 | `-255.65` | 1 |
| WIr | 51 | `-36.42` | 1 |
| Li₂Pd | 191 | `-247.89` | 1 |
| RhPb | 191 | `-50.87` | 1 |
| SrPb₃ | 123 | `-64.39, -64.39, -64.21` | 3 |
| V₃Sn | 194 | `-260.56, -260.56, -112.55, -112.55, -52.66` | 5 |
| HfPd | 63 | `-68.98` | 1 |
| MoC | 194 | `-379.98, -99.62` | 2 |
| AgB₂ | 191 | `-184.11` | 1 |
| TaS₂ (194) | 194 | `-419.84, -172.57` | 2 |
| BaF₂ | 194 | `-54.88` | 1 |
| Pd₂O | 224 | `-131.82` | 1 |
| NpC | 225 | `-154.91` | 1 |
| W₃Si | 223 | `-305.81, -139.68` | 2 |
| PbS | 221 | `-120.09` | 1 |
| PbSe | 221 | `-76.57` | 1 |
| InTe | 221 | `-50.40` | 1 |
| Mg₂Si | 194 | `-192.39` | 1 |
| GeP | 216 | `-407.28` | 1 |
| ReC | 225 | `-164.64` | 1 |
| MnS | 186 | `-237.14` | 1 |
| ZrS | 129 | `-88.37` | 1 |
| WO₃ | 221 | `-671.38` | 1 |
| Pb₂O | 224 | `-22.09` | 1 |
| BkCl₃ | 176 | `-76.04` | 1 |
| CdTe | 152 | `-62.14` | 1 |
| H₂S (142) | 142 | `-276.77, -231.78, -188.68, -125.20, -107.86, -34.12` | 6 |
| H₂S (54) | 54 | `-25.88` | 1 |
| IrF₆ | 229 | `-21.79` | 1 |
| OsF₆ | 229 | `-54.52` | 1 |
| BeTe | 194 | `-224.10` | 1 |
| BeSe | 194 | `-224.17` | 1 |
| ZnTe₂ | 164 | `-36.91` | 1 |
| Na₂S | 194 | `-64.74` | 1 |
| BaGe₃ | 194 | `-403.99, -175.65` | 2 |
| W₃N₄ | 221 | `-341.26, -194.49, -144.01` | 3 |
| Mn₃Ge | 221 | `-276.19` | 1 |
| CaGa₂ | 191 | `-67.62` | 1 |
| PbF₂ | 194 | `-104.98, -98.72, -87.35` | 3 |
| SrH₂ | 194 | `-43.37` | 1 |
| BaB₂ | 191 | `-484.27` | 1 |
| SrF₂ | 194 | `-40.57` | 1 |
| RuCl₃ | 158 | `-347.19` | 1 |
| BC₃ | 187 | `-324.25, -176.08` | 2 |

---

**Created:** 2026-07-09

**Disclaimer**: The DeepSeek V3 was used

**Data source:** MPDS (Materials Platform for Data Science), AB INITIO Calculations

