# Building ABACUS with ELPA, step by step

Verified on Debian 13 (trixie), gcc 14, AMD EPYC 7282 (Zen 2, AVX2, no AVX-512).
`setup_compute_node.sh` does all of this for you (stages `scalapack`, `elpa`,
`abacus`). What follows is the same thing by hand.

## 0. Prerequisite

OpenMPI 4.1.8 in `/usr/local`, built from source. This is not a preference: the
prebuilt `Pcrystal` is linked against OpenMPI 4.1.x, while `openmpi-bin` on
trixie is already 5.0.7. ScaLAPACK and ELPA have to be built with that same
`mpicc`/`mpifort`, otherwise one process ends up with two different MPI
implementations loaded.

```bash
export PATH=/usr/local/bin:$PATH
mpirun -V      # expect 4.1.8
```

## 1. apt packages

```bash
apt-get install -y build-essential gfortran git cmake pkg-config \
    autoconf automake libtool \
    libopenblas-dev libfftw3-dev libcereal-dev libxc-dev nlohmann-json3-dev
```

ABACUS looks for cereal and LibXC through `find_package(... CONFIG)`, and Debian
ships the cmake configs for both (`/usr/lib/x86_64-linux-gnu/cmake/cereal/`,
`/usr/share/cmake/Libxc/`), so there is no need to build them separately.

Do **not** install `libelpa-dev` or `libscalapack-openmpi-dev` from apt: they
pull in OpenMPI 5 as a dependency.

## 2. ScaLAPACK 2.2.2

```bash
cd /root/src
wget https://github.com/Reference-ScaLAPACK/scalapack/archive/refs/tags/v2.2.2.tar.gz
tar xf v2.2.2.tar.gz

cmake -S scalapack-2.2.2 -B build-scalapack \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON -DBUILD_TESTING=OFF \
    -DMPI_C_COMPILER=/usr/local/bin/mpicc \
    -DMPI_Fortran_COMPILER=/usr/local/bin/mpifort \
    -DBLAS_LIBRARIES=/usr/lib/x86_64-linux-gnu/libopenblas.so \
    -DLAPACK_LIBRARIES=/usr/lib/x86_64-linux-gnu/libopenblas.so \
    -DCMAKE_C_FLAGS="-O2 -fPIC -std=gnu17 -Wno-implicit-function-declaration -Wno-implicit-int -Wno-int-conversion" \
    -DCMAKE_Fortran_FLAGS="-O2 -fPIC -fallow-argument-mismatch"

cmake --build build-scalapack -j$(nproc --all)
cmake --install build-scalapack
ldconfig
```

Two of those flags are not optional, the build fails without them:

* `-fallow-argument-mismatch`: gfortran 10 and newer rejects the argument
  mismatches ScaLAPACK is full of;
* `-Wno-implicit-function-declaration`: gcc 14 turned implicit function
  declarations into errors, and the BLACS sources inside (`BLACS/SRC/*.c`) are
  written in K&R style.

## 3. ELPA 2025.06.002

```bash
cd /root/src
wget https://elpa.mpcdf.mpg.de/software/tarball-archive/Releases/2025.06.002/elpa-2025.06.002.tar.gz
tar xf elpa-2025.06.002.tar.gz
mkdir elpa-2025.06.002/build && cd elpa-2025.06.002/build

../configure \
    --prefix=/usr/local \
    --enable-openmp \
    --enable-avx --enable-avx2 --disable-avx512 \
    --disable-threading-support-check-during-build \
    --disable-c-tests --disable-cpp-tests \
    FC=/usr/local/bin/mpifort CC=/usr/local/bin/mpicc CXX=/usr/local/bin/mpicxx \
    FCFLAGS="-O3 -march=native -ffree-line-length-none" \
    CFLAGS="-O3 -march=native -funsafe-math-optimizations" \
    SCALAPACK_LDFLAGS="-L/usr/local/lib -lscalapack -lopenblas -lgfortran" \
    SCALAPACK_FCFLAGS="-L/usr/local/lib"

make -j$(nproc --all)
make install
ldconfig
```

About the flags:

* `--enable-openmp` produces `libelpa_openmp` and `elpa_openmp.pc`. That is the
  build ABACUS prefers, because it is itself built with OpenMP.
* `--disable-avx512` is passed explicitly, based on `/proc/cpuinfo`. Zen 2 has
  no AVX-512 and configure should not be left to guess.
* `SCALAPACK_LDFLAGS` and `SCALAPACK_FCFLAGS` are the documented way to tell
  ELPA where ScaLAPACK lives.

Check:

```bash
PKG_CONFIG_PATH=/usr/local/lib/pkgconfig pkg-config --modversion elpa_openmp
```

## 4. ABACUS

```bash
cd /root/src
git clone --depth 1 --branch v3.11.0-beta11 \
    https://github.com/deepmodeling/abacus-develop.git
cd abacus-develop

export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH
cmake -B build \
    -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_COMPILER=/usr/local/bin/mpicxx \
    -DCMAKE_C_COMPILER=/usr/local/bin/mpicc \
    -DENABLE_MPI=ON -DENABLE_LCAO=ON -DENABLE_ELPA=ON -DENABLE_OPENMP=ON \
    -DENABLE_LIBXC=ON -DENABLE_JSON=ON \
    -DSCALAPACK_DIR=/usr/local

cmake --build build -j$(nproc --all)
cmake --install build
```

`PKG_CONFIG_PATH` is the part that matters here: ELPA is discovered through
pkg-config (`cmake/modules/FindELPA.cmake`), and `ELPA_DIR` is deprecated
upstream and only prints a warning. ABACUS needs ELPA 2021.05.001 or newer.

`ENABLE_MLALGO`, `ENABLE_LIBRI` and `ENABLE_PEXSI` are left off on purpose:
they pull in libtorch, PEXSI and SuperLU-dist, and none of our workflows use
them.

## 5. Verify

```bash
abacus --version
ldd $(command -v abacus) | grep -E 'elpa|scalapack|libmpi'
```

Expect `libelpa_openmp.so.19` and `libscalapack.so.2.2` from `/usr/local/lib`,
and `libmpi.so.40` from there too, not from `/usr/lib/x86_64-linux-gnu`.

Then start it under MPI in an empty directory:

```bash
mpirun --allow-run-as-root -np 2 abacus
```

A correct result looks like this:

```
Info: Local MPI proc number: 2,OpenMP thread number: 1,Total thread number: 2,Local thread limit: 24
 Can't find the INPUT file.
```

The binary loaded, MPI and OpenMP came up, and it stopped only because there is
nothing to compute.

## 6. Traps

**`nproc` returns 1.** It is capped by `OMP_NUM_THREADS`, which we pin in
`/etc/environment`. Always use `nproc --all` for `-j`, otherwise the build runs
single-threaded and takes hours instead of minutes.

**`libmpi.so.40` drifts.** The Debian OpenMPI 5.0.7 package installs a library
under the same soname as our 4.1.8. If it ever gets installed, the engines start
loading whichever one wins. One command tells you:

```bash
ldd $(command -v abacus) | grep libmpi
```

**No pseudopotentials or orbitals.** The binary is installed, but ABACUS cannot
compute anything without them and the scripts do not deploy them. Separate job.

**ABACUS is not wired into yascheduler.** There is no `[engine.abacus]` section
in the config, see the README in this directory.
