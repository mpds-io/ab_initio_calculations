# Manual FLEUR + phonopy phonon pipeline

A set of scripts to compute phonon spectra with FLEUR (FLAPW) and phonopy,
**without AiiDA or a job scheduler**. The goal is to isolate SCF convergence
physics from the AiiDA plumbing so that different parameter presets can be
tested quickly against the convergence problems observed in the failed
`PhonopyFleurWorkChain` runs.

## Overview

The pipeline reproduces what `PhonopyFleurWorkChain` was supposed to do:

1. **phonopy** generates displaced supercells from the unit cell.
2. **FLEUR** (`inpgen` + `fleur_MPI`) runs SCF + forces for each displacement.
3. Forces are extracted from `out.xml` into `FORCES` files.
4. **phonopy** assembles force constants and computes phonon frequencies.

All steps run via `subprocess` — no AiiDA, no scheduler, just `mpirun`.

## Prerequisites

| Dependency | Version tested | Purpose |
|---|---|---|
| FLEUR | MaX 6.2 (release) or develop 8.1 | SCF + forces |
| phonopy | 3.5.1 or 4.4.0 | phonon calculations |
| ASE | 3.2x | structure I/O, `fleur-inpgen` format |
| ase-fleur | 0.0.1 | ASE plugin for FLEUR inpgen text format |
| lxml | any | parsing `out.xml` / editing `inp.xml` |
| mpds_client | any | downloading structures from MPDS API |
| OpenMPI | 4.1.4 (system) or 5.0.8 (conda) | MPI runtime |
| numpy, PyYAML | any | phonopy dependencies |

For **FLEUR develop (MaX 8.1)**: gfortran >= 13 is required (system gfortran-12
is insufficient). Install via conda-forge:
```bash
conda install -c conda-forge gfortran_linux-64=13 openmpi=5.0.8 \
    openmpi-mpifort scalapack openblas
```

## Scripts

| Script | Purpose |
|---|---|
| `download_mpds_structure.py` | Download a crystal structure from MPDS by phase_id, save as POSCAR |
| `extract_failed_structures.py` | Extract structures from failed AiiDA PhonopyFleurWorkChain nodes |
| `build_fleur_develop.sh` | Clone and compile FLEUR develop (MaX 8.1) in an isolated directory |
| `run_fleur_scf.py` | Run a single FLEUR SCF (inpgen -> fleur_MPI) with parameter presets |
| `run_phonopy_manual.py` | Orchestrate phonopy + FLEUR for one system (displacements -> forces -> force constants) |
| `compute_frequencies.py` | Compute phonon frequencies from FORCES files, write phonon_frequencies.txt |
| `run_all.py` | **End-to-end**: download (optional) -> FLEUR SCF -> forces -> frequencies |
| `convergence_report.py` | Aggregate run_manifest.json files into a markdown comparison report |

## Quick start

### From an existing POSCAR

```bash
python3 scripts/phonon/run_all.py \
    --poscar data/manual_fleur_phonopy/structures/BiSe_164.poscar \
    --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \
    --preset tuningB_fast \
    --inpgen /root/fleur/build/inpgen \
    --fleur  /root/fleur/build/fleur_MPI \
    --outdir data/manual_fleur_phonopy/runs/BiSe_164 \
    --label BiSe_164 \
    --mpi-procs 8
```

### From an MPDS phase_id

```bash
python3 scripts/phonon/run_all.py \
    --phase-id 7282 \
    --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \
    --preset tuningB_fast \
    --inpgen /root/fleur/build/inpgen \
    --fleur  /root/fleur/build/fleur_MPI \
    --outdir data/manual_fleur_phonopy/runs/ZnO_7282 \
    --label ZnO_7282 \
    --mpi-procs 8
```

This will:
1. Download ZnO (wurtzite, phase_id=7282) from MPDS
2. Generate 8 displaced supercells (16 atoms each)
3. Run FLEUR SCF + forces for each displacement
4. Compute phonon frequencies on an 8x8x8 q-point mesh
5. Write `phonon_frequencies.txt` and `run_manifest.json`

### Individual steps

If you prefer to run each step separately:

```bash
# 1. Download structure
python3 scripts/phonon/download_mpds_structure.py \
    --phase-id 7282 \
    --output data/manual_fleur_phonopy/structures/ZnO_7282.poscar

# 2. Run FLEUR SCF + forces + force constants
python3 scripts/phonon/run_phonopy_manual.py \
    --poscar data/manual_fleur_phonopy/structures/ZnO_7282.poscar \
    --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \
    --preset tuningB_fast \
    --inpgen /root/fleur/build/inpgen \
    --fleur  /root/fleur/build/fleur_MPI \
    --outdir data/manual_fleur_phonopy/runs/ZnO_7282 \
    --label ZnO_7282 \
    --mpi-procs 8

# 3. Compute frequencies
python3 scripts/phonon/compute_frequencies.py \
    --run-dir data/manual_fleur_phonopy/runs/ZnO_7282 \
    --mesh 8 8 8

# 4. Generate comparison report (across multiple runs)
python3 scripts/phonon/convergence_report.py \
    --runs-glob 'data/manual_fleur_phonopy/runs/*/run_manifest.json' \
    --output manual_fleur_phonon_report.md
```

## Parameter presets

Presets are defined in `run_fleur_scf.py` (the `PRESETS` dict). Each preset
controls: mixing scheme, itmax, k-point mesh, convergence thresholds, and
whether a restart with halved k-points is attempted on non-convergence.

| Preset | Mixing | itmax | k-mesh | Restart | Source |
|---|---|---|---|---|---|
| `baseline` | Anderson (default) | 60 | auto (inpgen) | no | original failed runs |
| `fast` | Anderson | 15 | auto | no | quick pipeline validation |
| `tuningA` | straight, alpha=0.05 | 300 | 4x4x4 | no | mpds-aiida `updating_fleur_parameters` branch |
| `tuningB` | Anderson | 60 | auto | yes (halve k-mesh) | absolidix-backend PR #63 (`FlerSCFRestart`) |
| `tuningB_fast` | Anderson | 10 | auto | yes (halve k-mesh) | forced restart variant (present pipeline) |
| `tuningC` | straight, alpha=0.05 | 300 | 4x4x4 | yes (halve k-mesh) | combination of tuningA + tuningB |

### How the restart works (tuningB / tuningB_fast)

1. Run FLEUR SCF with Anderson mixing and `itmax` iterations.
2. If SCF did not converge (energy difference above threshold):
   - Read the current k-point mesh from `inp.xml`.
   - Halve it in each direction (e.g. 6x6x1 -> 3x3x1).
   - Re-run FLEUR from the existing charge density (`cdn1`).
3. The restart counter (`n_runs`) is recorded in `run_manifest.json`.

## Output files

Each run produces the following in `--outdir`:

| File | Description |
|---|---|
| `run_manifest.json` | Full run metadata: preset, SCF results per displacement, phonon analysis, elapsed time |
| `phonopy_params.yaml` | phonopy parameters (unit cell, supercell, displacements) |
| `phonon_frequencies.txt` | All phonon frequencies on the q-point mesh (from `compute_frequencies.py`) |
| `disp_NNN/FORCES` | Forces for displacement NNN (extracted from `out.xml`) |
| `disp_NNN/out_scf.xml` | FLEUR out.xml snapshot from the SCF run (before forces run overwrites it) |
| `disp_NNN/out_scf_run1.xml` | FLEUR out.xml from the first SCF run (before restart, if restart occurred) |
| `disp_NNN/inp.xml` | FLEUR input XML |
| `disp_NNN/fleur.inp` | inpgen text input |
| `disp_NNN/fleur.stdout` | FLEUR stdout (warnings, timers) |

## Running on a remote node

To run on a remote Linux node over SSH (e.g. a bare-metal server with
OpenMPI and Python 3):

### 1. Set up the node

```bash
REMOTE=<user@host>
SSH_KEY=<path_to_ssh_key>

# Install dependencies
ssh -i $SSH_KEY $REMOTE \
    "apt-get update -qq && apt-get install -y -qq openmpi-bin libopenmpi-dev \
     libopenblas-dev libxml2-dev libscalapack-openmpi-dev python3-pip git xxd"

ssh -i $SSH_KEY $REMOTE \
    "pip3 install phonopy ase lxml pyyaml --break-system-packages -q"

# Install ase-fleur (for fleur-inpgen format)
git clone https://gitlab.com/ase/ase-fleur.git /tmp/ase-fleur
scp -i $SSH_KEY -r /tmp/ase-fleur $REMOTE:/root/ase-fleur
ssh -i $SSH_KEY $REMOTE \
    "cd /root/ase-fleur && pip3 install -e . --break-system-packages -q"
```

### 2. Copy FLEUR binaries + scripts

```bash
ssh -i $SSH_KEY $REMOTE "mkdir -p /root/fleur_MPI_files"
scp -i $SSH_KEY /path/to/fleur/build/fleur_MPI /path/to/fleur/build/inpgen \
    $REMOTE:/root/fleur_MPI_files/

# Scripts + POSCAR
scp -i $SSH_KEY scripts/phonon/run_fleur_scf.py scripts/phonon/run_phonopy_manual.py \
    scripts/phonon/compute_frequencies.py scripts/phonon/run_all.py \
    $REMOTE:/root/
scp -i $SSH_KEY data/manual_fleur_phonopy/structures/ZnO_7282.poscar $REMOTE:/root/
```

### 3. Launch

```bash
ssh -i $SSH_KEY $REMOTE "cd /root && \
    export OMPI_ALLOW_RUN_AS_ROOT=1 && \
    export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 && \
    nohup python3 run_all.py \
        --poscar /root/ZnO_7282.poscar \
        --supercell-matrix '[[1,1,0],[-1,1,0],[0,0,2]]' \
        --preset tuningB_fast \
        --inpgen /root/fleur_MPI_files/inpgen \
        --fleur  /root/fleur_MPI_files/fleur_MPI \
        --outdir /root/runs/ZnO_7282 \
        --label ZnO_7282 \
        --mpi-procs 24 \
    > /root/runs/ZnO_7282.log 2>&1 < /dev/null &"
```

### 4. Monitor

```bash
ssh -i $SSH_KEY $REMOTE \
    "tail -5 /root/runs/ZnO_7282.log; \
     ls /root/runs/ZnO_7282/disp_*/FORCES | wc -l"
```

### 5. Download results

```bash
ssh -i $SSH_KEY $REMOTE \
    "cd /root/runs/ZnO_7282 && tar czf /tmp/zno_results.tar.gz \
     run_manifest.json phonopy_params.yaml phonon_frequencies.txt disp_*/FORCES"
scp -i $SSH_KEY $REMOTE:/tmp/zno_results.tar.gz ./
```

