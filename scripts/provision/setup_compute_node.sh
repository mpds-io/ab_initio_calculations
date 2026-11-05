#!/bin/bash
# =============================================================================
# setup_compute_node.sh — provision a bare Debian 12/13 node as an ab-initio
# compute node: OpenMPI + FLEUR + Pcrystal + ABACUS (built against ELPA).
#
# Run ON the node, as root:
#     scp scripts/provision/setup_compute_node.sh root@NODE:/root/
#     ssh root@NODE 'bash /root/setup_compute_node.sh'
#
# Everything is logged to /var/log/node-setup.log.
#
# Idempotent: each stage drops a marker in /var/lib/node-setup/ and is skipped
# on re-run, so an interrupted build can simply be restarted.
#     bash setup_compute_node.sh                  # all remaining stages
#     bash setup_compute_node.sh elpa abacus      # only these stages
#     rm /var/lib/node-setup/abacus && bash setup_compute_node.sh   # redo one
#
# Stage order is deliberate, see the notes at stage_fleur and stage_firewall.
# =============================================================================
set -euo pipefail

# ----------------------------- configuration ---------------------------------
OPENMPI_VERSION=4.1.8          # Pcrystal is a prebuilt binary that needs
                               # OpenMPI 4.1.x in /usr/local — do not "upgrade"
                               # this to 5.x without re-testing Pcrystal.
SCALAPACK_VERSION=2.2.2
ELPA_VERSION=2025.06.002       # ABACUS requires >= 2021.05.001
ABACUS_VERSION=v3.11.0-beta11  # pin; see README for how to move it
FLEUR_TARBALL=https://tilde.pro/fleur.tar.gz
FLEUR_DIR=fleur-MaX-R6.2
PCRYSTAL_URL=https://tilde.pro/temp_6789953006/Pcrystal

PREFIX=/usr/local
SRC=/root/src
ENGINES="$HOME/data/engines"
# `nproc` is clamped by OMP_NUM_THREADS, which stage_tuning writes into
# /etc/environment — so on every re-run plain `nproc` would report 1 and the
# builds would go single-threaded. `nproc --all` ignores the limit.
NPROC=${NPROC:-$(nproc --all)}
MARKER_DIR=/var/lib/node-setup
LOG=/var/log/node-setup.log

# TCP ports allowed from the outside. SSH only: MPI ranks of a job all live on
# one node, so nothing else needs to be reachable. See stage_firewall.
SSH_PORT=22

# ------------------------------- plumbing ------------------------------------
ALL_STAGES=(packages firewall tuning openmpi fleur pcrystal scalapack elpa abacus verify)

log() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }

fetch() {  # fetch <url> <output>
    [[ -s "$2" ]] && { log "already downloaded: $2"; return 0; }
    wget --progress=dot:giga -O "$2.part" "$1"
    mv "$2.part" "$2"
}

run_stage() {
    local name=$1
    if [[ -e "$MARKER_DIR/$name" ]]; then
        log "stage '$name': already done, skipping (rm $MARKER_DIR/$name to redo)"
        return 0
    fi
    log "===== stage '$name' starting ====="
    "stage_$name"
    touch "$MARKER_DIR/$name"
    log "===== stage '$name' done ====="
}

# --------------------------------- stages ------------------------------------

stage_packages() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get -y update
    apt-get -y upgrade
    # Note: on Debian 13 (trixie) the 64-bit time_t transition renamed
    # libarpack2 -> libarpack2t64; ask for whichever one this release has.
    local arpack=libarpack2t64
    apt-cache show libarpack2t64 >/dev/null 2>&1 || arpack=libarpack2
    apt-get install -y \
        build-essential gfortran git cmake pkg-config swig p7zip-full \
        wget curl ca-certificates rsync xz-utils bzip2 \
        autoconf automake libtool m4 \
        libopenblas-dev libblas-dev liblapack-dev \
        libxml2-dev libxc-dev "$arpack" libarpack2-dev \
        libfftw3-dev libcereal-dev nlohmann-json3-dev \
        numactl htop tmux
}

stage_firewall() {
    # Why this exists: with a default-ACCEPT INPUT chain and a public IP, every
    # OpenMPI rank's TCP BTL listener (ports 1024+) is reachable from the
    # internet. Port scanners connect, the BTL blocks in recvfrom() waiting for
    # an MPI handshake that never comes, and the whole job wedges forever with
    # all ranks burning 100% CPU. This cost us multi-day hangs on the Hetzner
    # nodes in Oct 2026; the Vultr nodes, which had INPUT rules, were fine.
    #
    # Applied early, before the long builds, so the node is never exposed.
    export DEBIAN_FRONTEND=noninteractive
    echo 'iptables-persistent iptables-persistent/autosave_v4 boolean true' | debconf-set-selections
    echo 'iptables-persistent iptables-persistent/autosave_v6 boolean true' | debconf-set-selections
    apt-get install -y iptables iptables-persistent

    local ipt
    for ipt in iptables ip6tables; do
        # Build the allow-list first, flip the policy to DROP only at the very
        # end — so an interrupted run can never leave SSH unreachable.
        "$ipt" -P INPUT ACCEPT
        "$ipt" -F INPUT
        "$ipt" -A INPUT -i lo -j ACCEPT
        "$ipt" -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
        "$ipt" -A INPUT -p tcp --dport "$SSH_PORT" -m conntrack --ctstate NEW -j ACCEPT
        "$ipt" -P FORWARD DROP
        "$ipt" -P OUTPUT ACCEPT
    done
    # ICMP: plain ping for v4, but v6 genuinely needs ND/MLD to work at all.
    iptables -A INPUT -p icmp -j ACCEPT
    ip6tables -A INPUT -p ipv6-icmp -j ACCEPT

    iptables -P INPUT DROP
    ip6tables -P INPUT DROP

    mkdir -p /etc/iptables
    iptables-save  > /etc/iptables/rules.v4
    ip6tables-save > /etc/iptables/rules.v6
    systemctl enable netfilter-persistent
    log "firewall: INPUT default DROP, SSH/$SSH_PORT + established + loopback allowed"
}

stage_tuning() {
    # 1. Make /usr/local/lib a first-class library path. The original script
    #    exported LD_LIBRARY_PATH, which does not survive into the
    #    non-interactive SSH sessions AiiDA and yascheduler actually use;
    #    ldconfig does.
    echo "$PREFIX/lib"   >  /etc/ld.so.conf.d/zz-usr-local.conf
    echo "$PREFIX/lib64" >> /etc/ld.so.conf.d/zz-usr-local.conf
    ldconfig

    # 2. File descriptors / locked memory for MPI (the old `ulimit -n 65536`
    #    only affected the setup shell itself).
    cat > /etc/security/limits.d/90-hpc.conf <<'EOF'
*       soft    nofile      65536
*       hard    nofile      65536
root    soft    nofile      65536
root    hard    nofile      65536
*       soft    memlock     unlimited
*       hard    memlock     unlimited
EOF
    mkdir -p /etc/systemd/system.conf.d
    cat > /etc/systemd/system.conf.d/90-hpc.conf <<'EOF'
[Manager]
DefaultLimitNOFILE=65536
DefaultLimitMEMLOCK=infinity
EOF

    # 3. Runtime environment. /etc/environment is read by pam_env, so it also
    #    applies to `ssh node 'command'` — which is how the schedulers run.
    #    profile.d covers interactive shells.
    local kv
    touch /etc/environment
    for kv in \
        'OMP_NUM_THREADS=1' \
        'OMP_STACKSIZE=16M' \
        'OPENBLAS_NUM_THREADS=1' \
        'OMPI_ALLOW_RUN_AS_ROOT=1' \
        'OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1'
    do
        grep -qxF "$kv" /etc/environment || echo "$kv" >> /etc/environment
    done
    cat > /etc/profile.d/hpc-env.sh <<EOF
# written by setup_compute_node.sh
export OMP_NUM_THREADS=1
export OMP_STACKSIZE=16M
export OPENBLAS_NUM_THREADS=1
export OMPI_ALLOW_RUN_AS_ROOT=1
export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
export PKG_CONFIG_PATH=$PREFIX/lib/pkgconfig\${PKG_CONFIG_PATH:+:\$PKG_CONFIG_PATH}
ulimit -n 65536 2>/dev/null || true
EOF
    chmod 0644 /etc/profile.d/hpc-env.sh

    # If the MPI-port hangs ever come back despite the firewall, uncommenting
    # this pins ranks to shared memory and drops TCP entirely. It changes how
    # every FLEUR job communicates, so it is off by default — discuss first.
    # mkdir -p $PREFIX/etc && echo 'btl = self,vader' > $PREFIX/etc/openmpi-mca-params.conf
}

stage_openmpi() {
    mkdir -p "$SRC" && cd "$SRC"
    fetch "https://download.open-mpi.org/release/open-mpi/v${OPENMPI_VERSION%.*}/openmpi-$OPENMPI_VERSION.tar.gz" \
          "openmpi-$OPENMPI_VERSION.tar.gz"
    rm -rf "openmpi-$OPENMPI_VERSION"
    tar xf "openmpi-$OPENMPI_VERSION.tar.gz"
    cd "openmpi-$OPENMPI_VERSION"
    ./configure --prefix="$PREFIX"
    make -j"$NPROC"
    make install
    ldconfig
    "$PREFIX/bin/mpirun" -V
}

stage_fleur() {
    # Built BEFORE scalapack/elpa on purpose: FLEUR's configure.sh autodetects
    # whatever is installed, and this recipe is the one validated on the
    # existing production nodes. Putting ELPA in /usr/local first would
    # silently produce a differently-linked fleur_MPI.
    mkdir -p "$SRC" && cd "$SRC"
    fetch "$FLEUR_TARBALL" fleur.tar.gz
    rm -rf "$FLEUR_DIR"
    tar xf fleur.tar.gz
    cd "$FLEUR_DIR"
    export FC=mpifort CXX=mpicxx CC=mpicc
    export PATH="$PREFIX/bin:$PATH"
    ./configure.sh
    cd build
    make -j"$NPROC"
    unset FC CXX CC
    mkdir -p "$ENGINES/fleur"
    install -m 0755 "$SRC/$FLEUR_DIR/build/fleur_MPI" "$ENGINES/fleur/fleur_MPI"
    install -m 0755 "$SRC/$FLEUR_DIR/build/inpgen"    "$ENGINES/fleur/inpgen" 2>/dev/null || \
        log "note: inpgen not found in the FLEUR build tree"
}

stage_pcrystal() {
    mkdir -p "$ENGINES/pcrystal"
    fetch "$PCRYSTAL_URL" "$ENGINES/pcrystal/Pcrystal"
    chmod 0755 "$ENGINES/pcrystal/Pcrystal"
    # Confirm the prebuilt binary's MPI dependency is actually satisfied —
    # this is the whole reason OpenMPI is built from source into /usr/local.
    if ldd "$ENGINES/pcrystal/Pcrystal" | grep -q 'not found'; then
        ldd "$ENGINES/pcrystal/Pcrystal" | grep 'not found'
        echo "ERROR: Pcrystal has unresolved shared libraries" >&2
        return 1
    fi
}

stage_scalapack() {
    # From source against the /usr/local OpenMPI. Debian's
    # libscalapack-openmpi-dev would drag in a *second* MPI implementation
    # (Debian's libopenmpi3) next to ours — a reliable way to get silent
    # breakage at run time.
    mkdir -p "$SRC" && cd "$SRC"
    fetch "https://github.com/Reference-ScaLAPACK/scalapack/archive/refs/tags/v$SCALAPACK_VERSION.tar.gz" \
          "scalapack-$SCALAPACK_VERSION.tar.gz"
    rm -rf "scalapack-$SCALAPACK_VERSION" build-scalapack
    tar xf "scalapack-$SCALAPACK_VERSION.tar.gz"
    local blas=/usr/lib/x86_64-linux-gnu/libopenblas.so
    cmake -S "scalapack-$SCALAPACK_VERSION" -B build-scalapack \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_SHARED_LIBS=ON \
        -DBUILD_TESTING=OFF \
        -DMPI_C_COMPILER="$PREFIX/bin/mpicc" \
        -DMPI_Fortran_COMPILER="$PREFIX/bin/mpifort" \
        -DBLAS_LIBRARIES="$blas" \
        -DLAPACK_LIBRARIES="$blas" \
        -DCMAKE_C_FLAGS="-O2 -fPIC -std=gnu17 -Wno-implicit-function-declaration -Wno-implicit-int -Wno-int-conversion" \
        -DCMAKE_Fortran_FLAGS="-O2 -fPIC -fallow-argument-mismatch"
        # ScaLAPACK 2.2.x predates two compiler defaults:
        #  * gfortran >= 10 rejects its argument mismatches without
        #    -fallow-argument-mismatch;
        #  * gcc >= 14 turns implicit function declarations into errors, which
        #    the K&R-era BLACS sources in BLACS/SRC trip over immediately.
    cmake --build build-scalapack -j"$NPROC"
    cmake --install build-scalapack
    ldconfig
}

stage_elpa() {
    # ABACUS finds ELPA through pkg-config and prefers the OpenMP build
    # (elpa_openmp.pc) when built with OpenMP, which it is by default.
    mkdir -p "$SRC" && cd "$SRC"
    fetch "https://elpa.mpcdf.mpg.de/software/tarball-archive/Releases/$ELPA_VERSION/elpa-$ELPA_VERSION.tar.gz" \
          "elpa-$ELPA_VERSION.tar.gz"
    rm -rf "elpa-$ELPA_VERSION"
    tar xf "elpa-$ELPA_VERSION.tar.gz"
    mkdir -p "elpa-$ELPA_VERSION/build"
    cd "elpa-$ELPA_VERSION/build"

    # Kernel selection follows the CPU: EPYC 7282 is Zen 2 — AVX2/FMA, no
    # AVX-512. --disable-avx512 keeps configure from guessing wrong.
    local avx512=--disable-avx512
    grep -qw avx512f /proc/cpuinfo && avx512=--enable-avx512
    ../configure \
        --prefix="$PREFIX" \
        --enable-openmp \
        --enable-avx --enable-avx2 $avx512 \
        --disable-threading-support-check-during-build \
        --disable-c-tests --disable-cpp-tests \
        FC="$PREFIX/bin/mpifort" \
        CC="$PREFIX/bin/mpicc" \
        CXX="$PREFIX/bin/mpicxx" \
        FCFLAGS="-O3 -march=native -ffree-line-length-none" \
        CFLAGS="-O3 -march=native -funsafe-math-optimizations" \
        SCALAPACK_LDFLAGS="-L$PREFIX/lib -lscalapack -lopenblas -lgfortran" \
        SCALAPACK_FCFLAGS="-L$PREFIX/lib"
    make -j"$NPROC"
    make install
    ldconfig
    PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" pkg-config --modversion elpa_openmp
}

stage_abacus() {
    mkdir -p "$SRC" && cd "$SRC"
    rm -rf abacus-develop
    git clone --depth 1 --branch "$ABACUS_VERSION" \
        https://github.com/deepmodeling/abacus-develop.git
    cd abacus-develop
    export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig${PKG_CONFIG_PATH:+:$PKG_CONFIG_PATH}"
    cmake -B build \
        -DCMAKE_INSTALL_PREFIX="$PREFIX" \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_COMPILER="$PREFIX/bin/mpicxx" \
        -DCMAKE_C_COMPILER="$PREFIX/bin/mpicc" \
        -DENABLE_MPI=ON \
        -DENABLE_LCAO=ON \
        -DENABLE_ELPA=ON \
        -DENABLE_OPENMP=ON \
        -DENABLE_LIBXC=ON \
        -DENABLE_JSON=ON \
        -DSCALAPACK_DIR="$PREFIX"
    cmake --build build -j"$NPROC"
    cmake --install build
    mkdir -p "$ENGINES/abacus"
    install -m 0755 "$PREFIX/bin/abacus" "$ENGINES/abacus/abacus"
}

stage_verify() {
    local fail=0 b missing

    log "--- mpirun ---"
    "$PREFIX/bin/mpirun" -V | head -1

    log "--- elpa ---"
    PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig" pkg-config --modversion elpa_openmp

    # Every engine binary must have all of its shared libraries resolved.
    # Note on the shape of this loop: the earlier
    #   ldd x | grep -c 'not found' | grep -qx 0 || { ldd x | grep 'not found'; }
    # was wrong twice over — pipefail made the clean case look like a failure,
    # and the group after `||` is the final command of the ||-list, so errexit
    # is *not* suppressed inside it and the no-match grep killed the script.
    # Capturing into a variable sidesteps both.
    for b in "$ENGINES/fleur/fleur_MPI" "$ENGINES/pcrystal/Pcrystal" "$PREFIX/bin/abacus"; do
        log "--- $(basename "$b") ---"
        if [[ ! -x $b ]]; then
            log "MISSING: $b"
            fail=1
            continue
        fi
        missing=$(ldd "$b" 2>/dev/null | grep 'not found' || true)
        if [[ -n $missing ]]; then
            printf '%s\n' "$missing"
            fail=1
        else
            log "shared libraries all resolved"
        fi
    done

    # ABACUS specifically must have picked up ELPA and ScaLAPACK, which is the
    # whole point of building them.
    log "--- abacus linkage ---"
    missing=$(ldd "$PREFIX/bin/abacus" 2>/dev/null | grep -E 'elpa|scalapack' || true)
    if [[ -n $missing ]]; then
        printf '%s\n' "$missing"
    else
        log "ELPA/ScaLAPACK are NOT linked into abacus"
        fail=1
    fi
    "$PREFIX/bin/abacus" --version 2>&1 | head -3 || true

    log "--- firewall ---"
    iptables -S INPUT

    log "--- resources ---"
    log "nproc=$NPROC  mem=$(free -g | awk '/^Mem:/{print $2}')GB  disk free=$(df -h / | awk 'NR==2{print $4}')"

    if [[ $fail -ne 0 ]]; then
        echo "VERIFY FAILED" >&2
        return 1
    fi
    log "all checks passed"
}

# --------------------------------- driver ------------------------------------
main() {
    [[ $EUID -eq 0 ]] || { echo "must run as root" >&2; exit 1; }
    mkdir -p "$MARKER_DIR" "$SRC"
    export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1
    local stages=("$@")
    [[ ${#stages[@]} -eq 0 ]] && stages=("${ALL_STAGES[@]}")
    local s
    for s in "${stages[@]}"; do
        declare -F "stage_$s" >/dev/null || { echo "unknown stage: $s" >&2; exit 1; }
    done
    log "provisioning $(hostname) — stages: ${stages[*]}"
    for s in "${stages[@]}"; do run_stage "$s"; done
    log "DONE"
}

main "$@" 2>&1 | tee -a "$LOG"
