# Compute node provisioning

Scripts for turning a bare root-password VPS into an ab-initio compute node
running **FLEUR**, **Pcrystal** and **ABACUS**.

Validated on Contabo VPS, Debian 13 (trixie), AMD EPYC 7282 (24 vCPU, Zen 2),
94 GB RAM, 709 GB disk:

| Host              | Hostname   | vCPU | RAM   | Disk  |
|-------------------|------------|------|-------|-------|
| `62.171.154.152`  | vmi3699052 | 24   | 94 GB | 709 GB |
| `62.171.153.65`   | vmi3699049 | 24   | 94 GB | 709 GB |

## Order of operations

```shell
# 1. keys in, passwords out (run from the control machine)
NODE_PASSWORD='...' ./harden_ssh.sh 62.171.154.152 62.171.153.65

# 2. build the engines (runs on the node, ~1 h, mostly ABACUS)
for h in 62.171.154.152 62.171.153.65; do
    scp setup_compute_node.sh root@$h:/root/
    ssh root@$h 'setsid nohup bash /root/setup_compute_node.sh >/root/setup-stdout.log 2>&1 &'
done

# 3. watch
ssh root@62.171.154.152 'tail -f /root/setup-stdout.log'
```

## `harden_ssh.sh`

Installs the control machine's public keys (`PUBKEYS`, default: `id_ed25519`,
`id_rsa`, `private`) and then switches sshd to key-only.

It deliberately runs from *outside* the node:

* key-only login is verified from the control machine **before** password
  authentication is touched;
* before the sshd change, a `systemd-run --on-active=300` rollback is armed on
  the node, and it is only disarmed after key login has been re-verified on a
  fresh connection — so a mistake restores itself in five minutes instead of
  bricking access;
* the config lands in `/etc/ssh/sshd_config.d/10-hardening.conf`. The `10-`
  prefix matters: sshd keeps the **first** value it sees and `Include` sits at
  the top of `sshd_config`, so this must sort ahead of the
  `50-cloud-init.conf` that ships `PasswordAuthentication yes`. That file is
  moved aside and `ssh_pwauth: false` is pinned in `/etc/cloud/cloud.cfg.d/`,
  because cloud-init rewrites it on every boot.

`./harden_ssh.sh --check HOST` reports the current state and changes nothing.

The root password is read from `$NODE_PASSWORD` or an interactive prompt only —
never commit it.

## `setup_compute_node.sh`

Idempotent, stage-based. Each finished stage drops a marker in
`/var/lib/node-setup/`, so an interrupted run is restarted by just running it
again. Everything is appended to `/var/log/node-setup.log`.

```shell
bash setup_compute_node.sh                 # all remaining stages
bash setup_compute_node.sh elpa abacus     # only these
rm /var/lib/node-setup/abacus && bash setup_compute_node.sh   # redo one stage
```

Stages, in order:

| Stage       | What it does |
|-------------|--------------|
| `packages`  | apt deps |
| `firewall`  | `INPUT` default DROP, SSH + established + loopback only |
| `tuning`    | `ldconfig` path, `nofile`/`memlock` limits, runtime env |
| `openmpi`   | OpenMPI 4.1.8 from source into `/usr/local` |
| `fleur`     | FLEUR MaX-R6.2 → `~/data/engines/fleur/fleur_MPI` |
| `pcrystal`  | prebuilt `Pcrystal` → `~/data/engines/pcrystal/` |
| `scalapack` | ScaLAPACK 2.2.2 from source |
| `elpa`      | ELPA 2025.06.002 from source, AVX2 + OpenMP |
| `abacus`    | ABACUS with ELPA/ScaLAPACK/LibXC → `/usr/local/bin/abacus` |
| `verify`    | linkage and firewall checks |

### Why the stage order is what it is

* **`firewall` runs early.** With a default-ACCEPT `INPUT` chain and a public
  IP, every OpenMPI rank's TCP BTL listener (ports 1024+) is reachable from the
  internet. Scanners connect, the BTL blocks in `recvfrom()` waiting for an MPI
  handshake that never arrives, and the job wedges forever with all ranks at
  100% CPU. That caused multi-day FLEUR hangs on the Hetzner nodes in October
  2026; the Vultr nodes, which had `INPUT` rules, were unaffected. Applying it
  before the hour-long builds means the node is never exposed.
* **`fleur` runs before `scalapack`/`elpa`.** FLEUR's `configure.sh`
  autodetects whatever libraries are installed. Building it first reproduces
  exactly the linkage of the existing production nodes; installing ELPA into
  `/usr/local` first would silently give a differently-linked `fleur_MPI`.

### Why the libraries are built from source

Pcrystal is a prebuilt binary that needs OpenMPI 4.1.x in `/usr/local` — which
is why OpenMPI is compiled rather than installed from apt. Given that, ScaLAPACK
and ELPA must be compiled against the *same* MPI: `libscalapack-openmpi-dev`
and `libelpa-dev` from Debian would pull in a second MPI implementation
alongside ours, which is a reliable source of silent run-time breakage.

### ABACUS

Step by step, if you need to do it by hand: [ABACUS.md](ABACUS.md).

ABACUS finds ELPA through `pkg-config` and, because it is built with OpenMP,
prefers `elpa_openmp.pc`; `PKG_CONFIG_PATH=/usr/local/lib/pkgconfig` is what
makes that work. `ELPA_DIR` still exists but is deprecated upstream. ELPA
≥ 2021.05.001 is required.

ELPA kernels are selected from the CPU: `--enable-avx2`, and `--disable-avx512`
unless `/proc/cpuinfo` advertises `avx512f` (Zen 2 does not).

Also enabled: `ENABLE_LCAO`, `ENABLE_LIBXC` (Debian's libxc 5.2.3 ships
`LibxcConfig.cmake`, which is what ABACUS's `find_package(Libxc CONFIG)` needs)
and `ENABLE_JSON` for machine-readable output. Deliberately *not* enabled:
`ENABLE_MLALGO`, `ENABLE_LIBRI`, `ENABLE_PEXSI` — they pull in libtorch /
PEXSI / SuperLU-dist and none of our workflows use them.

To move the ABACUS version, change `ABACUS_VERSION` at the top of the script and
`rm /var/lib/node-setup/abacus`. Upstream publishes a rolling `v3.11.0-betaN`
train; the pinned tag is the newest of those rather than `develop`, so the two
nodes are guaranteed to run identical binaries.

ABACUS needs pseudopotentials and numerical atomic orbitals at run time; those
are not installed here.

### Differences from the original ad-hoc script

* `libarpack2` → `libarpack2t64` on Debian 13 (the 64-bit `time_t` transition);
  with `set -e` the old name aborted the whole run.
* `export LD_LIBRARY_PATH=/usr/local/lib` replaced by
  `/etc/ld.so.conf.d/zz-usr-local.conf` + `ldconfig`. The export only lived in
  the setup shell and never reached the non-interactive SSH sessions AiiDA and
  yascheduler actually use.
* `ulimit -n 65536` replaced by `/etc/security/limits.d/90-hpc.conf` and
  `systemd` `DefaultLimitNOFILE`, for the same reason.
* `OMP_NUM_THREADS`, `OMP_STACKSIZE`, `OPENBLAS_NUM_THREADS` and the OpenMPI
  run-as-root flags are written to `/etc/environment` (read by `pam_env`, so
  they apply to `ssh node 'command'`) as well as `/etc/profile.d/`.
* `NPROC` uses `nproc --all`, not `nproc`: `nproc` honours `OMP_NUM_THREADS`,
  which the `tuning` stage pins to 1 in `/etc/environment`, so plain `nproc`
  reports 1 on every re-run and the builds silently go single-threaded.
* `MKL_DEBUG_CPU_TYPE=5` dropped — it is an Intel MKL workaround and nothing
  here links MKL.
* Downloads are resumable and verified, stages are idempotent, and `verify`
  checks that `ldd` resolves for every engine binary.

### Known knob, off by default

If MPI-port hangs ever reappear despite the firewall, `openmpi-mca-params.conf`
with `btl = self,vader` (commented out in `stage_tuning`) pins ranks to shared
memory and drops TCP entirely — all ranks of a job live on one node anyway. It
changes how every FLEUR job communicates, so it is not enabled unilaterally.

---

# Wiring the nodes into yascheduler

## What yascheduler does to a new node

`linux_setup_deb_node` in
[yascheduler/infra/ssh/platform/linux.py](../../yascheduler/yascheduler/infra/ssh/platform/linux.py):

1. `apt-get update` / `upgrade` / `install` of every engine's
   `platform_packages`, merged across all `[engine.*]` sections;
2. for each engine: `mkdir {[remote] engines_dir}/{engine name}` and SFTP the
   `deploy_local_files` into it, resolved from
   `{[local] engines_dir}/{engine name}/`.

With the live `/etc/yascheduler/yascheduler.conf` that means:

| Engine        | Remote path                        | Files |
|---------------|------------------------------------|-------|
| `fleur`       | `/data/engines/fleur`              | `fleur_MPI`, `fleur_wrapper.sh` |
| `pcrystal`    | `/data/engines/pcrystal`           | `Pcrystal` |
| `pproperties` | `/data/engines/pproperties`        | `Pproperties` |

`fleur_wrapper.sh` hardcodes `/data/engines/fleur/fleur_MPI`, and the
`pproperties` spawn passes `-mca orte_tmpdir_base /data/tmp`, so `/data/tmp`
has to exist too.

## Why step 1 cannot be used on these nodes

`setup_yascheduler_engines.sh` reproduces step 2 verbatim and deliberately
skips step 1:

* **`openmpi-bin` on trixie is OpenMPI 5.0.7.** Every engine binary we deploy
  was built against OpenMPI 4.1.x — `Pcrystal` and `Pproperties` still carry
  `RUNPATH /opt/openmpi-4.1.1-i21.4/lib`, and the fleet's `fleur_MPI` was built
  on `alinzh3` on 2025-05-23 against the same series. `libopenmpi40` installs
  `libmpi.so.40` into `/usr/lib/x86_64-linux-gnu`, i.e. under the *same soname*
  our 4.1.8 uses, so the two would be interchangeable at load time while
  `mpirun` stayed 4.1.8. The nodes therefore run exactly one MPI, the
  source-built OpenMPI 4.1.8 in `/usr/local`, and nothing from apt competes
  with it.
* **`libarpack2` does not exist on Debian 13** (renamed `libarpack2t64`), so the
  apt step would fail outright and leave a half-added node behind.
* **`libscalapack-openmpi2.2` would pull that OpenMPI 5 runtime in** as a
  dependency. `fleur_MPI` genuinely needs `libscalapack-openmpi.so.2.2`, so the
  script points that name at the ScaLAPACK 2.2.2 built against our own 4.1.8.

### The ScaLAPACK soname shim

Our source build's SONAME is `libscalapack.so.2.2`; the fleet's `fleur_MPI`
asks for `libscalapack-openmpi.so.2.2`. A symlink under the wanted name in
`/usr/local/lib` **does not work**: `ld.so.cache` is keyed by SONAME, not by
filename, so `ldconfig` registers the file under `libscalapack.so.2.2` and the
other name is never found however often you re-run it. The link has to sit in a
directory `ld.so` also searches by plain filename — the multiarch default dir:

```shell
ln -sfn /usr/local/lib/libscalapack.so.2.2.1 \
        /usr/lib/x86_64-linux-gnu/libscalapack-openmpi.so.2.2
```

Side effect worth knowing: apt will now refuse to install
`libscalapack-openmpi2.2` over that link, which is a useful tripwire.

## Verification

`smoke_test_engines.sh` runs the **exact** spawn commands from the config, with
`{task_path}`/`{engine_path}`/`{ncpus}` substituted, and checks the physics
rather than just the linkage:

| Check | Result on both nodes |
|-------|----------------------|
| FLEUR `CuBulkXML`, E_tot iteration 1 | `-3305.016030697` Htr, identical to FLEUR's upstream reference `out.xml` |
| CRYSTAL MgO STO-3G SCF | `-271.21814374981` a.u., SCF converged, bit-identical across nodes |

`Pproperties` is only checked for linkage — it needs a `fort.9` from a finished
CRYSTAL run, so it has no standalone test here.

## Adding the nodes — why not `yasetnode`

**`yasetnode root@HOST` cannot be used while the daemon is running.** Its add
path ([manage_node.py](../../yascheduler/yascheduler/entrypoints/cli/manage_node.py),
`_add_node`) inserts the row with `enabled=False` **and a real hostname**,
commits, then connects over SSH and runs the node setup, and only afterwards
flips `enabled=True`. Meanwhile the daemon's `deallocate_nodes`
([deallocate_nodes.py](../../yascheduler/yascheduler/application/deallocate_nodes.py),
`BLOCK_collect_disabled`) collects every non-busy disabled node with a
non-empty hostname and removes its row (`BLOCK_remove`). The row is reaped
inside that window and the CLI dies with:

```
Error: node row not found for node_id=43493
```

`add_nodes_to_yascheduler.py` reaches the same end state without the window: it
verifies the host over SSH exactly as the CLI does — same `SSHMachineRepository`,
same keys from the config's `keys_dir` — then inserts the row *already enabled*
in one transaction, so it is never visible as "disabled with a hostname".

```shell
python add_nodes_to_yascheduler.py --dry-run 62.171.154.152
python add_nodes_to_yascheduler.py 62.171.154.152 62.171.153.65
```

The real fix belongs in yascheduler: either the add path keeps `hostname=''`
(the documented tmp-row marker, which `list_disabled` already excludes) until
setup finishes, or the reaper only removes nodes it disabled itself.

Note that the daemon connects with the keys in `[local] keys_dir`
(`yascheduler/data/keys_for_clouds`), not with `~/.ssh` — the script authorizes
those separately from `harden_ssh.sh`.

## ABACUS is not a yascheduler engine yet

`setup_compute_node.sh` builds ABACUS and installs it to `/usr/local/bin/abacus`
(plus `~/data/engines/abacus/`), but there is no `[engine.abacus]` section in
`/etc/yascheduler/yascheduler.conf`, so the scheduler will not dispatch ABACUS
work to these nodes. Adding one needs a `spawn` command, `check_pname`,
`input_files`/`output_files`, and — unlike FLEUR and CRYSTAL — a decision about
where the pseudopotentials and numerical atomic orbitals live, since ABACUS
needs those at run time and nothing installs them today.
