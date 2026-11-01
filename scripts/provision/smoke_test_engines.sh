#!/bin/bash
# =============================================================================
# smoke_test_engines.sh — run a real FLEUR and a real CRYSTAL calculation on
# each node using the *exact* spawn commands from the yascheduler config.
#
#     ./smoke_test_engines.sh 62.171.154.152 62.171.153.65
#
# This is the check that matters after provisioning: `ldd` only proves the
# libraries resolve, not that the MPI stack runs or that the physics comes out
# right.
#
# FLEUR   — tests/inputfiles/CuBulkXML from the FLEUR source tree, which ships
#           its own upstream reference out.xml. The first SCF iteration's total
#           energy is compared against it.
# CRYSTAL — testdata/mgo_sto3g_scf.INPUT (MgO, STO-3G, HF SCF; taken from
#           aiida-crystal-dft's test inputs, self-contained, ~seconds). There is
#           no upstream reference for it, so the run must converge and all nodes
#           must agree with each other to the same tolerance.
# =============================================================================
set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FLEUR_CASE=${FLEUR_CASE:-/root/src/fleur-MaX-R6.2/tests/inputfiles/CuBulkXML}
CRYSTAL_INPUT=${CRYSTAL_INPUT:-$HERE/testdata/mgo_sto3g_scf.INPUT}
CRYSTAL_FORT34=${CRYSTAL_FORT34:-$HERE/testdata/mgo_sto3g_scf.fort.34}
REMOTE_ENGINES=${REMOTE_ENGINES:-/data/engines}
REMOTE_TASKS=${REMOTE_TASKS:-/data/tasks}
NCPUS=${NCPUS:-4}
TIMEOUT=${TIMEOUT:-900}
TOL=${TOL:-1e-6}          # relative agreement required
KEEP=${KEEP:-0}           # 1 = leave the task dirs on the node
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR)

[[ $# -ge 1 ]] || { echo "usage: $0 HOST [HOST...]" >&2; exit 1; }

log() { printf '  %s\n' "$*"; }
ok()  { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
bad() { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

nsh() { ssh "${SSH_OPTS[@]}" "root@$HOST" "$@"; }

# Relative comparison of two numbers; prints the verdict, exits non-zero on
# disagreement or on a missing value.
cmp_rel() {  # cmp_rel <label> <got> <want>
    python3 - "$1" "${2:-}" "${3:-}" "$TOL" <<'PY'
import sys
label, got, want, tol = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
try:
    g, w = float(got), float(want)
except ValueError:
    print(f"{label}: missing value (got={got!r} ref={want!r})")
    raise SystemExit(1)
rel = abs(g - w) / max(abs(w), 1e-30)
print(f"{label}: {g!r} vs {w!r}  (rel. diff {rel:.2e})")
raise SystemExit(0 if rel <= tol else 1)
PY
}

# FLEUR pads the tag out with spaces ("<totalEnergy          value=\"   -3305.01\"")
# and pads the number inside the quotes too, so the pattern has to be tolerant
# of whitespace in both places.
fleur_energy() {  # fleur_energy <remote out.xml> -> first totalEnergy value
    nsh "sed -n 's/.*<totalEnergy[[:space:]]*value=\"[[:space:]]*\([-0-9.Ee+]*\).*/\1/p' $1 2>/dev/null | head -1"
}

run_fleur() {
    local dir="$REMOTE_TASKS/smoke-fleur-$STAMP"
    log "FLEUR CuBulkXML -> $dir (np=$NCPUS)"
    nsh "set -e; test -f $FLEUR_CASE/inp.xml; mkdir -p $dir; cp $FLEUR_CASE/inp.xml $dir/" \
        || { bad "FLEUR: cannot stage input (is $FLEUR_CASE there?)"; return 1; }

    # Verbatim [engine.fleur] spawn from the yascheduler config, with
    # {task_path}/{engine_path}/{ncpus} substituted.
    nsh "timeout $TIMEOUT bash -c \"ldconfig && cd $dir && chmod +x $REMOTE_ENGINES/fleur/fleur_wrapper.sh && export OMPI_ALLOW_RUN_AS_ROOT=1 && export OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 && mpirun --oversubscribe -x OMP_NUM_THREADS -np $NCPUS $REMOTE_ENGINES/fleur/fleur_wrapper.sh > shell.out 2> out.error\"" \
        >/dev/null 2>&1 || true

    local got want
    got=$(fleur_energy "$dir/out.xml")
    want=$(fleur_energy "$FLEUR_CASE/out.xml")
    if [[ -z $got ]]; then
        bad "FLEUR produced no total energy; out.error tail:"
        nsh "tail -15 $dir/out.error 2>/dev/null" | sed 's/^/      /'
        return 1
    fi
    if cmp_rel "FLEUR Cu bulk E_tot it.1 [Htr]" "$got" "$want" | sed 's/^/  /'; then
        ok "FLEUR runs and reproduces the upstream reference energy"
    else
        bad "FLEUR energy disagrees with the upstream reference"
        return 1
    fi
}

run_crystal() {
    local dir="$REMOTE_TASKS/smoke-crystal-$STAMP"
    log "CRYSTAL MgO STO-3G SCF -> $dir (np=$NCPUS)"
    nsh "mkdir -p $dir" || { bad "CRYSTAL: cannot create task dir"; return 1; }
    scp -q "${SSH_OPTS[@]}" "$CRYSTAL_INPUT"  "root@$HOST:$dir/INPUT"   || return 1
    scp -q "${SSH_OPTS[@]}" "$CRYSTAL_FORT34" "root@$HOST:$dir/fort.34" || return 1

    # Verbatim [engine.pcrystal] spawn; yascheduler runs it with cwd=task_path.
    nsh "timeout $TIMEOUT bash -c 'cd $dir && cp $dir/INPUT OUTPUT && mpirun --oversubscribe -np $NCPUS --allow-run-as-root -wd $dir $REMOTE_ENGINES/pcrystal/Pcrystal >> OUTPUT 2>&1'" \
        >/dev/null 2>&1 || true

    local conv energy
    conv=$(nsh "grep -ac 'SCF ENDED - CONVERGENCE ON ENERGY' $dir/OUTPUT 2>/dev/null || true")
    energy=$(nsh "sed -n 's/.*SCF ENDED.*E(AU)[[:space:]]*\([-0-9.E+]*\).*/\1/p' $dir/OUTPUT 2>/dev/null | tail -1")
    if [[ ${conv:-0} -lt 1 || -z $energy ]]; then
        bad "CRYSTAL did not converge; OUTPUT tail:"
        nsh "tail -20 $dir/OUTPUT 2>/dev/null" | sed 's/^/      /'
        return 1
    fi
    log "CRYSTAL MgO E_tot = $energy a.u. (SCF converged)"
    CRYSTAL_ENERGIES+=("$HOST=$energy")
    ok "Pcrystal runs and the SCF converges"
}

cleanup_host() {
    [[ $KEEP -eq 1 ]] && { log "keeping task dirs (KEEP=1)"; return 0; }
    nsh "rm -rf $REMOTE_TASKS/smoke-fleur-$STAMP $REMOTE_TASKS/smoke-crystal-$STAMP" || true
}

rc=0
STAMP=$(date -u +%Y%m%d-%H%M%S)
CRYSTAL_ENERGIES=()
for HOST in "$@"; do
    printf '\n=== %s ===\n' "$HOST"
    run_fleur   || rc=1
    run_crystal || rc=1
    cleanup_host
done

# Cross-node agreement: the same deck on identical hardware must give the same
# number, which catches a node whose libraries resolved but differ.
if [[ ${#CRYSTAL_ENERGIES[@]} -gt 1 ]]; then
    printf '\n=== cross-node agreement ===\n'
    first_host=${CRYSTAL_ENERGIES[0]%%=*}; first_e=${CRYSTAL_ENERGIES[0]#*=}
    for entry in "${CRYSTAL_ENERGIES[@]:1}"; do
        h=${entry%%=*}; e=${entry#*=}
        if cmp_rel "CRYSTAL MgO: $h vs $first_host" "$e" "$first_e" | sed 's/^/  /'; then
            ok "$h agrees with $first_host"
        else
            bad "$h disagrees with $first_host"
            rc=1
        fi
    done
fi
exit $rc
