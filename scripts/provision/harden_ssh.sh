#!/bin/bash
# =============================================================================
# harden_ssh.sh — install this machine's public keys on a node and then turn
# off password authentication.
#
# Runs on the CONTROL machine, not on the node, so that key-only login is
# verified from the outside *before* passwords are disabled, and a timed
# rollback on the node undoes the change if that verification ever fails.
#
#     NODE_PASSWORD='...' ./harden_ssh.sh 1.2.3.4 5.6.7.8
#     ./harden_ssh.sh --check 1.2.3.4          # report state, change nothing
#
# The password is only read from the environment or an interactive prompt —
# never store it in this file.
# =============================================================================
set -euo pipefail

PUBKEYS=${PUBKEYS:-"$HOME/.ssh/id_ed25519.pub $HOME/.ssh/id_rsa.pub $HOME/.ssh/private.pub"}
SSH_USER=${SSH_USER:-root}
ROLLBACK_SECONDS=${ROLLBACK_SECONDS:-300}
DROPIN=/etc/ssh/sshd_config.d/10-hardening.conf
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o LogLevel=ERROR)

CHECK_ONLY=0
[[ ${1:-} == --check ]] && { CHECK_ONLY=1; shift; }
[[ $# -ge 1 ]] || { echo "usage: [--check] $0 HOST [HOST...]" >&2; exit 1; }

log()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m  %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

# --- run a command on the node over an existing key, or over the password ----
key_sh() {
    ssh "${SSH_OPTS[@]}" -o BatchMode=yes -o PreferredAuthentications=publickey \
        "$SSH_USER@$HOST" "$@"
}
pw_sh() {
    sshpass -p "$NODE_PASSWORD" ssh "${SSH_OPTS[@]}" \
        -o PreferredAuthentications=password -o PubkeyAuthentication=no \
        -o NumberOfPasswordPrompts=1 \
        "$SSH_USER@$HOST" "$@"
}
# Whichever currently works.
node_sh() {
    if [[ $KEY_WORKS -eq 1 ]]; then key_sh "$@"; else pw_sh "$@"; fi
}

report_state() {
    node_sh 'sshd -T 2>/dev/null | grep -E "^(passwordauthentication|permitrootlogin|pubkeyauthentication)"; \
             echo "authorized_keys: $(wc -l < ~/.ssh/authorized_keys 2>/dev/null || echo 0) line(s)"' \
        | sed 's/^/  /'
}

harden_host() {
    # ---- 1. which credentials do we have? -----------------------------------
    KEY_WORKS=0
    if key_sh true 2>/dev/null; then KEY_WORKS=1; ok "key authentication already works"; fi
    if [[ $KEY_WORKS -eq 0 ]]; then
        [[ -n ${NODE_PASSWORD:-} ]] || { bad "no key access and NODE_PASSWORD unset"; return 1; }
        have_sshpass || { bad "sshpass is required for the first run"; return 1; }
        pw_sh true || { bad "password authentication failed too — cannot reach the node"; return 1; }
        log "reaching the node with the password for now"
    fi

    if [[ $CHECK_ONLY -eq 1 ]]; then report_state; return 0; fi

    # ---- 2. install the public keys (append, no duplicates) -----------------
    local keyblob="" f
    for f in $PUBKEYS; do
        [[ -r $f ]] || { log "skipping missing key $f"; continue; }
        keyblob+="$(cat "$f")"$'\n'
        log "installing $(ssh-keygen -lf "$f" | awk '{print $2, $4}')"
    done
    [[ -n $keyblob ]] || { bad "no readable public keys in PUBKEYS"; return 1; }
    printf '%s' "$keyblob" | node_sh '
        set -e
        umask 077
        mkdir -p ~/.ssh
        cat >> ~/.ssh/authorized_keys
        # de-duplicate while keeping order, then tighten permissions
        awk "!seen[\$0]++" ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.new
        mv ~/.ssh/authorized_keys.new ~/.ssh/authorized_keys
        chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'

    # ---- 3. key-only login must work before we touch password auth ----------
    key_sh true || { bad "key-only login still does not work — refusing to disable passwords"; return 1; }
    KEY_WORKS=1
    ok "key-only login verified"

    # ---- 4. arm a rollback on the node --------------------------------------
    # If anything below goes wrong and we lose access, the node restores the
    # old sshd config by itself after ROLLBACK_SECONDS.
    key_sh "systemctl stop sshd-rollback.timer 2>/dev/null || true; \
            systemd-run --quiet --unit=sshd-rollback --on-active=$ROLLBACK_SECONDS \
              /bin/bash -c 'rm -f $DROPIN; \
                            mv -f /etc/ssh/sshd_config.d/50-cloud-init.conf.disabled \
                                  /etc/ssh/sshd_config.d/50-cloud-init.conf 2>/dev/null; \
                            systemctl reload ssh'"
    log "rollback armed: sshd config is restored in ${ROLLBACK_SECONDS}s unless disarmed"

    # ---- 5. disable password authentication ---------------------------------
    # Two things fight us here:
    #  * sshd takes the FIRST value it sees, and `Include sshd_config.d/*.conf`
    #    sits at the top of sshd_config — hence the 10- prefix, which sorts
    #    ahead of the 50-cloud-init.conf that ships PasswordAuthentication yes.
    #  * cloud-init rewrites that 50- file on every boot, so ssh_pwauth is
    #    pinned off in cloud.cfg.d as well.
    key_sh "set -e
        cat > $DROPIN <<'EOF'
# written by harden_ssh.sh — key-only SSH access
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PermitEmptyPasswords no
EOF
        chmod 0600 $DROPIN
        if [ -f /etc/ssh/sshd_config.d/50-cloud-init.conf ]; then
            mv /etc/ssh/sshd_config.d/50-cloud-init.conf \
               /etc/ssh/sshd_config.d/50-cloud-init.conf.disabled
        fi
        if [ -d /etc/cloud ]; then
            mkdir -p /etc/cloud/cloud.cfg.d
            printf 'ssh_pwauth: false\n' > /etc/cloud/cloud.cfg.d/99-no-ssh-pwauth.cfg
        fi
        sshd -t
        systemctl reload ssh"
    log "sshd config validated and reloaded"

    # ---- 6. verify from the outside, on a brand new connection --------------
    key_sh true || { bad "key login broke after reload — leaving the rollback armed"; return 1; }
    ok "key login works after reload"
    if [[ -n ${NODE_PASSWORD:-} ]] && have_sshpass; then
        if pw_sh true 2>/dev/null; then
            bad "password login STILL accepted — leaving the rollback armed"
            return 1
        fi
        ok "password login refused"
    fi

    # ---- 7. disarm ----------------------------------------------------------
    key_sh 'systemctl stop sshd-rollback.timer 2>/dev/null || true'
    ok "rollback disarmed — node is key-only"
    report_state
}

have_sshpass() { command -v sshpass >/dev/null 2>&1; }

if [[ $CHECK_ONLY -eq 0 && -z ${NODE_PASSWORD:-} ]]; then
    # Only needed if some node has no key access yet; ask once, quietly.
    read -r -s -p "root password for the nodes (empty if keys already work): " NODE_PASSWORD
    echo
fi

rc=0
for HOST in "$@"; do
    printf '\n=== %s ===\n' "$HOST"
    harden_host || { rc=1; bad "$HOST not hardened"; }
done
exit $rc
