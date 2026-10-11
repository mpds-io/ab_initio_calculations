# Manual FLEUR + phonopy convergence report

Comparison of SCF convergence and phonon quality across parameter presets (baseline / tuningA / tuningB / tuningC) and FLEUR versions.

## Summary table

| Run | Preset | Supercell atoms | Disps | Converged (n/N) | Avg iters | Last dist | Energy diff (Htr) | Forces ok | Imag modes (mesh) | Min freq (cm^-1) | Elapsed (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MgO_fast | fast | 4 | 2 | 0/2 | 0.0 | - | - | 0/2 | 116 | -34.48 | 0 |
| MgO_fast_develop | fast | 4 | 2 | 2/2 | 15.0 | 0.1081 | 4.8e-06 | 2/2 | 116 | -34.48 | 1578 |
| MgO_tuningA | tuningA | 4 | 2 | 0/2 | 0.0 | - | - | 0/2 | 120 | -31.79 | 0 |

## Per-displacement detail

### MgO_fast — fast

| Disp | Converged | Runs | Iters | Last dist | Energy (Htr) | Energy diff (Htr) | Forces | Forces lines | Error |
|---|---|---|---|---|---|---|---|---|---|
| 1 | - | - | - | - | - | - | - | - | reused |
| 2 | - | - | - | - | - | - | - | - | reused |

**Phonon analysis:**

```json
{
  "mesh_n_qpoints": 40,
  "mesh_n_imaginary": 116,
  "mesh_min_freq_THz": -1.033561778820726,
  "mesh_max_freq_THz": 0.5763643348608245,
  "band_error": "band analysis failed (non-fatal): Generic Spglib error:\nlattice has to be a (3, 3) array."
}
```

### MgO_fast_develop — fast

| Disp | Converged | Runs | Iters | Last dist | Energy (Htr) | Energy diff (Htr) | Forces | Forces lines | Error |
|---|---|---|---|---|---|---|---|---|---|
| 1 | True | 1 | 15 | 1.023 | -550.9 | 3.347e-05 | True | 4 |  |
| 2 | True | 1 | 15 | 0.1081 | -550.9 | 4.8e-06 | True | 4 |  |

**Phonon analysis:**

```json
{
  "mesh_n_qpoints": 40,
  "mesh_n_imaginary": 116,
  "mesh_min_freq_THz": -1.0336609659975937,
  "mesh_max_freq_THz": 0.5773856156185463,
  "band_error": "band analysis failed (non-fatal): Generic Spglib error:\nlattice has to be a (3, 3) array."
}
```

### MgO_tuningA — tuningA

| Disp | Converged | Runs | Iters | Last dist | Energy (Htr) | Energy diff (Htr) | Forces | Forces lines | Error |
|---|---|---|---|---|---|---|---|---|---|
| 1 | - | - | - | - | - | - | - | - | reused |
| 2 | - | - | - | - | - | - | - | - | reused |

**Phonon analysis:**

```json
{
  "mesh_n_qpoints": 40,
  "mesh_n_imaginary": 120,
  "mesh_min_freq_THz": -0.9529486033355521,
  "mesh_max_freq_THz": -0.10212258781995702,
  "band_error": "band analysis failed (non-fatal): Generic Spglib error:\nlattice has to be a (3, 3) array."
}
```

## Preset definitions

- **baseline**: inpgen defaults (Anderson/BFGS mixing, auto k-mesh 6x6x6), itmax_per_run=60, fleur_runmax=4, mode=energy.
- **tuningA**: straight mixing (imix=straight, alpha=0.05), kmax=3.0, k-mesh 4x4x4, itmax_per_run=300, fleur_runmax=10, density_converged=1e-4, energy_converged=0.01. (mpds-aiida updating_fleur_parameters branch.)
- **tuningB**: baseline parameters, but on SCF non-convergence restart from the produced charge density with the k-point mesh halved in each direction. (absolidix-backend PR #63 FlerSCFRestart rule.)
- **tuningC**: tuningA from the start plus the halving restart on top.

