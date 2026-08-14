#!/usr/bin/env bash
# Build the latest FLEUR from the develop branch into an isolated directory
# so it does not contaminate the existing MaX-6.2 installation in /root/fleur.
#
# Resulting binaries:
#   /root/fleur_develop/build/fleur_MPI
#   /root/fleur_develop/build/inpgen
#
# Usage:
#   bash scripts/phonon/build_fleur_develop.sh             # clone + build
#   bash scripts/phonon/build_fleur_develop.sh --rebuild    # rebuild only
#
# This script mirrors the options that the existing 6.2 build used
# (see /root/fleur/build/CMakeCache.txt): MPI, OpenMP, LAPACK, Scalapack,
# no HDF5, no ELPA, no libxc.

set -euo pipefail

DEST="${FLEUR_DEVELOP_DIR:-/root/fleur_develop}"
BUILD="$DEST/build"

clone_repo() {
    if [[ -d "$DEST/.git" ]]; then
        echo "[build_fleur_develop] $DEST already a git repo, fetching..."
        git -C "$DEST" fetch origin develop
    else
        echo "[build_fleur_develop] Cloning FLEUR develop into $DEST"
        git clone --branch develop --depth 50 \
            https://iffgit.fz-juelich.de/fleur/fleur.git "$DEST"
    fi
    git -C "$DEST" checkout origin/develop -B develop
    git -C "$DEST" log --oneline -3
}

build() {
    echo "[build_fleur_develop] Configuring in $BUILD"
    mkdir -p "$BUILD"
    cd "$DEST"

    # FLEUR develop requires gfortran >13. The system gfortran is 12, so use
    # the conda-forge gcc 13 toolchain + conda openmpi + conda scalapack/openblas.
    CONDA_PREFIX="/root/miniconda3"
    FC_BIN="$CONDA_PREFIX/bin/mpifort"
    CC_BIN="$CONDA_PREFIX/bin/mpicc"
    CXX_BIN="$CONDA_PREFIX/bin/mpicxx"
    export PATH="$CONDA_PREFIX/bin:$PATH"
    export LIBRARY_PATH="$CONDA_PREFIX/lib:${LIBRARY_PATH:-}"
    export LD_LIBRARY_PATH="$CONDA_PREFIX/lib:${LD_LIBRARY_PATH:-}"
    export OMP_NUM_THREADS=1
    if [[ ! -x "$FC_BIN" ]]; then
        echo "[build_fleur_develop] conda mpifort not found at $FC_BIN"
        echo "[build_fleur_develop] run: conda install -c conda-forge gfortran_linux-64=13 openmpi openmpi-mpifort scalapack openblas"
        exit 1
    fi
    echo "[build_fleur_develop] Using: $FC_BIN"

    # Run plain cmake directly (configure.sh tends to auto-enable HDF5
    # download which fails offline; we disable it explicitly).
    (
        cd "$BUILD"
        cmake "$DEST" \
            -DCMAKE_Fortran_COMPILER="$FC_BIN" \
            -DCMAKE_C_COMPILER="$CC_BIN" \
            -DCMAKE_CXX_COMPILER="$CXX_BIN" \
            -DCMAKE_EXE_LINKER_FLAGS="-L$CONDA_PREFIX/lib -lscalapack -lopenblas -lm" \
            -DFLEUR_USE_MPI=ON \
            -DFLEUR_USE_OPENMP=ON \
            -DFLEUR_USE_SCALAPACK=ON \
            -DFLEUR_USE_HDF5=OFF \
            -DFLEUR_USE_HDF5MPI=OFF \
            -DFLEUR_USE_ELPA=OFF \
            -DFLEUR_USE_LIBXC=OFF \
            -DFLEUR_USE_SPFFT=OFF \
            -DFLEUR_USE_CHASE=OFF
    ) || {
        echo "[build_fleur_develop] cmake configuration failed"
        tail -40 "$BUILD/CMakeFiles/CMakeError.log" 2>/dev/null || true
        exit 1
    }

    echo "[build_fleur_develop] Compiling (this may take a while)"
    cd "$BUILD"
    # develop builds inpgen2 (installs as 'inpgen')
    make -j"$(nproc)" fleur_MPI inpgen2

    echo
    echo "[build_fleur_develop] Build complete:"
    ls -la "$BUILD/fleur_MPI" "$BUILD/inpgen"
    "$BUILD/fleur_MPI" -h 2>&1 | head -5 || true
}

if [[ "${1:-}" == "--rebuild" ]]; then
    if [[ ! -d "$DEST" ]]; then
        echo "[build_fleur_develop] --rebuild given but $DEST missing, cloning"
        clone_repo
    fi
else
    clone_repo
fi
build

echo "[build_fleur_develop] done"