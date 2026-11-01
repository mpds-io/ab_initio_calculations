#!/usr/bin/env python3
"""Register static nodes in yascheduler without losing them to a race.

`yasetnode root@HOST` cannot be used while the daemon is running. Its add path
(entrypoints/cli/manage_node.py, _add_node) inserts the row with
``enabled=False`` and a real hostname, commits, *then* connects over SSH and
runs the node setup, and only afterwards flips ``enabled=True``. Meanwhile
``deallocate_nodes`` collects every non-busy disabled node with a non-empty
hostname (application/deallocate_nodes.py, BLOCK_collect_disabled) and removes
its row (BLOCK_remove). A node added while the daemon is up is therefore reaped
inside that window and the CLI dies with::

    Error: node row not found for node_id=...

This script reaches the same end state the CLI aims for, without the window:
it verifies the host over SSH exactly as the CLI does (same repository, same
keys from the config's ``keys_dir``), then inserts the row already enabled in a
single transaction, so the row is never visible as "disabled with a hostname".

    ./add_nodes_to_yascheduler.py 62.171.154.152 62.171.153.65
    ./add_nodes_to_yascheduler.py --dry-run 62.171.154.152

The proper fix belongs in yascheduler itself — either the add path keeps
``hostname=''`` (the documented tmp-row marker, which ``list_disabled``
excludes) until setup finishes, or the reaper only removes nodes it disabled
itself.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from yascheduler.domain import NewNode
from yascheduler.entrypoints import make_cli_deps
from yascheduler.entrypoints.config_parser import parse_config
from yascheduler.entrypoints.paths import CONFIG_FILE
from yascheduler.infra import SSHMachineRepository, list_private_keys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("hosts", nargs="+", help="host or user@host[:port][~ncpus]")
    p.add_argument("--config", default=CONFIG_FILE, help=f"default: {CONFIG_FILE}")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="verify reachability and report, write nothing",
    )
    return p.parse_args(argv)


def split_spec(spec: str) -> tuple[str, str | None, int, int | None]:
    """Parse [user@]host[:port][~ncpus] the way yasetnode does."""
    username = None
    if "@" in spec:
        username, spec = spec.split("@", 1)
    ncpus = None
    if "~" in spec:
        spec, ncpus_s = spec.split("~", 1)
        ncpus = int(ncpus_s) or None
    port = 22
    if ":" in spec:
        spec, port_s = spec.split(":", 1)
        port = int(port_s)
    return spec, username, port, ncpus


async def add_one(deps, repository, config, spec: str, *, dry_run: bool) -> bool:
    host, username, port, ncpus = split_spec(spec)
    username = username or config.remote.username

    async with deps.uow_factory() as uow:
        existing = [n for n in await uow.nodes.list_all() if n.hostname == host]
    if existing:
        node = existing[0]
        print(f"{host}: already present as node_id={node.node_id} "
              f"(enabled={node.enabled}) — skipping")
        return True

    node = NewNode(
        hostname=host,
        port=port,
        username=username,
        ncpus=ncpus,
        # Enabled from the start: a disabled row with a hostname is what the
        # reaper eats.
        enabled=True,
        jump_host=config.remote.jump_host,
        jump_username=config.remote.jump_username or "root",
        jump_port=config.remote.jump_port,
    )

    # Same reachability check the CLI performs, against a throwaway row-less
    # Node object; `connect` only needs the connection parameters.
    async with deps.uow_factory() as uow:
        probe = await uow.nodes.insert(node)
        # Deliberately not committed — the insert exists only so `connect` has
        # a node_id to register the session under, mirroring the CLI.
        try:
            session = await repository.connect(
                node=probe,
                client_keys=list_private_keys(config.local.keys_dir),
                engines_dir=config.remote.engines_dir,
            )
            detected = await session.get_cpu_cores()
            print(f"{host}: reachable as {username}@{host}:{port}, "
                  f"{detected} CPUs, platforms={session.machine.platforms}")
        finally:
            await repository.disconnect(probe.node_id)
        if dry_run:
            await uow.rollback()
            print(f"{host}: dry run, nothing written")
            return True
        await uow.commit()
        print(f"{host}: added as node_id={probe.node_id}, enabled=True, "
              f"ncpus={'auto' if ncpus is None else ncpus}")
    return True


async def main_async(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = parse_config(args.config)
    deps = make_cli_deps(config)
    repository = SSHMachineRepository()
    rc = 0
    for spec in args.hosts:
        try:
            await add_one(deps, repository, config, spec, dry_run=args.dry_run)
        except Exception as err:  # noqa: BLE001 - CLI boundary
            print(f"{spec}: FAILED: {err}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main_async()))
