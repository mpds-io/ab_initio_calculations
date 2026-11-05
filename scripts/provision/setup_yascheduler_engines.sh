#!/bin/bash
# =============================================================================
# setup_yascheduler_engines.sh — put a node into the state yascheduler's own
# `setup_node` would leave it in, on a Debian 13 node where its apt step
# cannot be used.
#
# Run from the CONTROL machine (the one running the yascheduler daemon):
#     ./setup_yascheduler_engines.sh 62.171.154.152 62.171.153.65
#
# What yascheduler does on node creation (yascheduler/infra/ssh/platform/
# linux.py, linux_setup_deb_node + linux_deploy_engines):
#   1. apt-get update / upgrade / install of every engine's platform_packages;
#   2. for each [engine.*] section: mkdir {remote engines_dir}/{engine name}
#      and SFTP the deploy_local_files there, resolved from
#      {local engines_dir}/{engine name}/.
#
# Step 2 is reproduced here verbatim. Step 1 is deliberately NOT, because on
# Debian 13 it would break the node:
#
#   * `openmpi-bin` on trixie is OpenMPI 5.0.7, while every prebuilt engine
#     binary we deploy was built against OpenMPI 4.1.x — Pcrystal and
#     Pproperties still carry RUNPATH /opt/openmpi-4.1.1-i21.4/lib. The nodes
#     therefore run the OpenMPI 4.1.8 that setup_compute_node.sh builds into
#     /usr/local, and nothing from apt may compete with it.
#   * `libscalapack-openmpi2.2` would pull that OpenMPI 5 runtime in as a
#     dependency. fleur_MPI does need libscalapack-openmpi.so.2.2, so instead
#     we point that soname at the ScaLAPACK 2.2.2 that was compiled against
#     our own OpenMPI 4.1.8 — same reference implementation, same version,
#     matched MPI.
#
# Prerequisite: setup_compute_node.sh has finished on the node (OpenMPI and
# ScaLAPACK in /usr/local).
# =============================================================================
set -euo pipefail

PROJECT=${PROJECT:-/root/projects/ab_initio_calculations}
LOCAL_ENGINES=${LOCAL_ENGINES:-$PROJECT/engines}
YASCHEDULER_CONF=${YASCHEDULER_CONF:-/etc/yascheduler/yascheduler.conf}
# [remote] from the yascheduler config
REMOTE_DATA=${REMOTE_DATA:-/data}
REMOTE_ENGINES=${REMOTE_ENGINES:-$REMOTE_DATA/engines}
REMOTE_TASKS=${REMOTE_TASKS:-$REMOTE_DATA/tasks}
# engine name -> files to deploy, mirroring deploy_local_files in the config
ENGINE_FLEUR_FILES="fleur_MPI fleur_wrapper.sh"
ENGINE_PCRYSTAL_FILES="Pcrystal"
ENGINE_PPROPERTIES_FILES="Pproperties"
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR)

[[ $# -ge 1 ]] || { echo "usage: $0 HOST [HOST...]" >&2; exit 1; }

log()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

# The key yascheduler itself will connect with — whatever lives in its
# keys_dir. Without it the daemon cannot reach the node even though we can.
yascheduler_keys_dir() {
    awk -F= '/^[[:space:]]*keys_dir[[:space:]]*=/ {gsub(/[[:space:]]/,"",$2); print $2}' \
        "$YASCHEDULER_CONF" | tail -1
}

install_scheduler_key() {
    local keys_dir pub k count=0
    keys_dir=$(yascheduler_keys_dir)
    [[ -n $keys_dir && -d $keys_dir ]] || { bad "keys_dir '$keys_dir' from $YASCHEDULER_CONF not usable"; return 1; }
    for k in "$keys_dir"/*; do
        [[ -f $k ]] || continue
        case "$k" in *.pub) continue;; esac
        pub=$(ssh-keygen -y -f "$k" 2>/dev/null) || { log "skipping unreadable key $(basename "$k")"; continue; }
        printf '%s %s\n' "$pub" "yascheduler:$(basename "$k")" | \
            ssh "${SSH_OPTS[@]}" "root@$HOST" '
                set -e; umask 077; mkdir -p ~/.ssh
                cat >> ~/.ssh/authorized_keys
                awk "!seen[\$1 FS \$2]++" ~/.ssh/authorized_keys > ~/.ssh/ak.new
                mv ~/.ssh/ak.new ~/.ssh/authorized_keys
                chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
        log "authorized yascheduler key $(basename "$k") ($(ssh-keygen -lf "$k" | awk '{print $2}'))"
        count=$((count + 1))
    done
    [[ $count -gt 0 ]] || { bad "no private keys found in $keys_dir"; return 1; }
}

prepare_node() {
    # /data/tmp is not in [remote]; the pproperties spawn command passes
    # `-mca orte_tmpdir_base /data/tmp`, so it has to exist up front.
    ssh "${SSH_OPTS[@]}" "root@$HOST" "
        set -e
        mkdir -p $REMOTE_ENGINES $REMOTE_TASKS $REMOTE_DATA/tmp
        test -x /usr/local/bin/mpirun || { echo 'OpenMPI missing — run setup_compute_node.sh first' >&2; exit 1; }
        real=\$(readlink -f /usr/local/lib/libscalapack.so 2>/dev/null || true)
        test -n \"\$real\" -a -f \"\$real\" || { echo 'ScaLAPACK missing — run setup_compute_node.sh first' >&2; exit 1; }
        # The prebuilt fleur_MPI from the rest of the fleet asks for Debian's
        # soname, libscalapack-openmpi.so.2.2. Our source build's SONAME is
        # libscalapack.so.2.2, and ld.so.cache is keyed by SONAME — so a
        # symlink under the other name in /usr/local/lib is never found, no
        # matter how often ldconfig runs. It has to sit in a directory ld.so
        # also searches by plain filename, i.e. the multiarch default dir.
        # Side effect worth knowing: apt would refuse to install
        # libscalapack-openmpi2.2 over this link, which is a useful tripwire.
        rm -f /usr/local/lib/libscalapack-openmpi.so.2.2 /usr/local/lib/libscalapack-openmpi.so.2.2.1
        ln -sfn \"\$real\" /usr/lib/\$(gcc -dumpmachine)/libscalapack-openmpi.so.2.2
        ldconfig"
    ok "$REMOTE_ENGINES, $REMOTE_TASKS, $REMOTE_DATA/tmp ready; ScaLAPACK soname shim in place"
}

deploy_engine() {
    local engine=$1 files=$2 f src
    ssh "${SSH_OPTS[@]}" "root@$HOST" "mkdir -p $REMOTE_ENGINES/$engine"
    for f in $files; do
        src="$LOCAL_ENGINES/$engine/$f"
        [[ -f $src ]] || { bad "missing local engine file $src"; return 1; }
        # -p mirrors asyncssh's sftp.put(..., preserve=True)
        scp -p -q "${SSH_OPTS[@]}" "$src" "root@$HOST:$REMOTE_ENGINES/$engine/$f"
        log "deployed $engine/$f ($(stat -c%s "$src") bytes)"
    done
    ssh "${SSH_OPTS[@]}" "root@$HOST" "chmod 0755 $REMOTE_ENGINES/$engine/*"
}

verify_node() {
    # errexit is disabled inside an ||-guarded block, so the ssh status is
    # captured explicitly instead of relied upon.
    local out vrc
    out=$(ssh "${SSH_OPTS[@]}" "root@$HOST" "
        fail=0
        for b in $REMOTE_ENGINES/fleur/fleur_MPI $REMOTE_ENGINES/pcrystal/Pcrystal $REMOTE_ENGINES/pproperties/Pproperties; do
            miss=\$(ldd \$b 2>/dev/null | grep 'not found' || true)
            if [ -n \"\$miss\" ]; then echo \"UNRESOLVED \$b: \$miss\"; fail=1; fi
        done
        # every engine must end up on the same MPI
        for b in $REMOTE_ENGINES/fleur/fleur_MPI $REMOTE_ENGINES/pcrystal/Pcrystal $REMOTE_ENGINES/pproperties/Pproperties; do
            echo \"mpi \$(basename \$b) -> \$(ldd \$b | awk '/libmpi.so.40/{print \$3}')\"
        done
        echo \"mpirun -> \$(command -v mpirun) \$(mpirun -V 2>/dev/null | head -1 | awk '{print \$NF}')\"
        echo \"scalapack -> \$(ldd $REMOTE_ENGINES/fleur/fleur_MPI | awk '/scalapack/{print \$3}')\"
        exit \$fail") && vrc=0 || vrc=$?
    printf '%s\n' "$out" | sed 's/^/  /'
    return "$vrc"
}

rc=0
for HOST in "$@"; do
    printf '\n=== %s ===\n' "$HOST"
    # Explicit && chain: inside an ||-guarded group errexit is off, so a
    # failing step would otherwise be followed by the next one anyway.
    if install_scheduler_key \
        && prepare_node \
        && deploy_engine fleur       "$ENGINE_FLEUR_FILES" \
        && deploy_engine pcrystal    "$ENGINE_PCRYSTAL_FILES" \
        && deploy_engine pproperties "$ENGINE_PPROPERTIES_FILES" \
        && verify_node
    then
        ok "engines deployed and resolvable"
    else
        rc=1
        bad "$HOST incomplete"
    fi
done
exit $rc
