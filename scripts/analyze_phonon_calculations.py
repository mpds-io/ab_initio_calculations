#!/usr/bin/env python3
"""
Analysis of CRYSTAL phonon calculations via AiiDA.

The script connects to an AiiDA profile, queries all phonon calculations
(standalone and part of optimization steps), classifies them by status
and error, and prints a detailed report.

Usage:
    python3 scripts/analyze_phonon_calculations.py [--profile PROFILE]
        [--output REPORT.md] [--csv phonon_status.csv] [--quiet]

Options:
    --profile   AiiDA profile name (default: the default profile).
    --output    Path to a markdown file to save the report to.
                If not given, the report is only printed to stdout.
    --csv       Path to a CSV file for the per-node status dump.
    --quiet     Don't print the report to stdout (useful with --output/--csv).

Requirements:
    - AiiDA (aiida-core) installed and configured.
    - An environment with the aiida-crystal-dft plugin active.
    - Access to an AiiDA profile with calculations (presto_pg etc).

Calculation categories:
    1. Standalone phonon workchains/calcjobs — "Phonon frequencies" (BaseCrystalWorkChain
       + CrystalParallelCalculation). Launched separately, not as part of optimization.
    2. Optimization-step phonons — "optimization step: Phonon frequencies" (a phonon
       step inside a structure-optimization process).
    3. PhonopyFleur — a separate category of FLEUR phonon calculations
       (PhonopyFleurWorkChain). Included in the report, but its errors are
       usually unrelated to CRYSTAL.

Error classification:
    - "ok"                 — calcjob Finished [0], the parser ran without errors.
    - "parser_error"       — calcjob Excepted due to an aiida-crystal-dft parser bug
                             (ValueError: Symbol lists / TypeError: unhashable type).
                             CRYSTAL itself finished normally.
    - "crystal_symmops"    — calcjob Finished [400]: CRYSTAL failed with
                             "ERROR **** MULTIP **** SYMMOPS DO NOT FORM A GROUP".
    - "workchain_bug"      — workchain Excepted due to a BaseCrystalWorkChain bug
                             (AttributeError: 'ExitCodesNamespace' object has no
                             attribute 'UNKNOWN_ERROR').
    - "killed"             — process killed manually (Killed).
    - "phonopy_fleur"      — PhonopyFleurWorkChain Excepted
                             (FileNotFoundError: FLEUR_INPGEN_PATH is not set).
    - "other_error"        — any other error.
"""

from __future__ import annotations

import argparse
import collections
import csv
import dataclasses
import re
import sys
from pathlib import Path
from typing import Optional

from aiida import load_profile
from aiida.common.links import LinkType
from aiida.orm import CalcJobNode, QueryBuilder, WorkChainNode


# ---------------------------------------------------------------------------
# Constants and classification heuristics
# ---------------------------------------------------------------------------

#: Substrings in the exception used to detect the parser error type.
PARSER_ERROR_MARKERS = (
    "Symbol lists have to be the same",
    "unhashable type: 'list'",
    "parse_out_trajectory",
)

#: Substrings for the CRYSTAL symmetry error.
CRYSTAL_SYMMOPS_MARKERS = (
    "SYMMOPS DO NOT FORM A GROUP",
    "MULTIP",
)

#: Substrings for the workchain bug.
WORKCHAIN_BUG_MARKERS = (
    "ExitCodesNamespace",
    "UNKNOWN_ERROR",
)

#: Substrings for PhonopyFleur.
PHONOPY_FLEUR_MARKERS = (
    "FLEUR_INPGEN_PATH",
    "inpgen",
)

#: Substrings for invalid CRYSTAL output (parser can't read it).
INVALID_OUTPUT_MARKERS = ("is not a valid CRYSTAL output file",)

#: Substrings for a missing OUTPUT file in retrieved.
MISSING_OUTPUT_MARKERS = ("object with path `OUTPUT` does not exist",)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class PhononNodeInfo:
    """Information about one AiiDA node related to phonons."""

    pk: int
    label: str
    process_label: str
    process_state: str  # "finished", "excepted", "killed", ...
    exit_status: Optional[int]
    exception: Optional[str]
    node_type: str  # "workchain" | "calcjob" | "phonopyfleur"
    category: str  # "standalone" | "optimization_step" | "phonopyfleur"
    error_class: str  # see classify_error()


@dataclasses.dataclass
class MaterialSummary:
    """Aggregated status for one material."""

    material: str
    has_ok_calcjob: bool
    error_classes: list[str]
    calcjob_count: int
    workchain_count: int
    pks_ok: list[int]
    pks_failed: list[int]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_error(
    node_type: str,
    process_state: str,
    exit_status: Optional[int],
    exception: Optional[str],
) -> str:
    """Determine the error class from status and exception.

    Returns one of:
        "ok", "parser_error", "crystal_symmops",
        "workchain_bug", "killed", "phonopy_fleur",
        "other_error".
    """
    if process_state == "killed":
        return "killed"

    if process_state == "finished" and exit_status == 0:
        return "ok"

    exc = exception or ""

    if any(marker in exc for marker in PARSER_ERROR_MARKERS):
        return "parser_error"

    if any(marker in exc for marker in INVALID_OUTPUT_MARKERS):
        return "invalid_output"

    if any(marker in exc for marker in MISSING_OUTPUT_MARKERS):
        return "missing_output"

    if process_state == "finished" and exit_status == 400:
        return "crystal_symmops"

    if any(marker in exc for marker in WORKCHAIN_BUG_MARKERS):
        return "workchain_bug"

    if any(marker in exc for marker in PHONOPY_FLEUR_MARKERS):
        return "phonopy_fleur"

    return "other_error"


def extract_material(label: str) -> str:
    """Extract the material name from a node label.

    Labels look like "MaterialName: Phonon frequencies [1]" or
    "CRYSTAL optimization step: Phonon frequencies" (no material).
    For optimization-step labels without a colon before "Phonon",
    the whole part before "Phonon" (or the whole string) is returned.
    """
    if ":" in label:
        return label.split(":")[0].strip()
    return label.strip()


def determine_category(label: str, process_label: str) -> str:
    """Determine the calculation category from label and process_label.

    Returns "standalone", "optimization_step" or "phonopyfleur".
    """
    if process_label == "PhonopyFleurWorkChain":
        return "phonopyfleur"
    if "optimization step" in label.lower():
        return "optimization_step"
    return "standalone"


def determine_node_type(process_label: str) -> str:
    """Determine the node type from process_label.

    Returns "workchain", "calcjob" or "phonopyfleur".
    """
    if process_label == "PhonopyFleurWorkChain":
        return "phonopyfleur"
    if process_label == "CrystalParallelCalculation":
        return "calcjob"
    return "workchain"


# ---------------------------------------------------------------------------
# AiiDA queries
# ---------------------------------------------------------------------------


def query_phonon_nodes() -> list[PhononNodeInfo]:
    """Query all phonon-related nodes from AiiDA.

    Looks for WorkChainNode and CalcJobNode with a label containing "Phonon"
    (case-insensitive), as well as PhonopyFleurWorkChain by process_label.
    Returns a list of PhononNodeInfo.
    """
    nodes: list[PhononNodeInfo] = []

    # WorkChainNode with "Phonon" in the label (BaseCrystalWorkChain etc)
    qb_wc = QueryBuilder().append(
        WorkChainNode,
        filters={"label": {"like": "%Phonon%"}},
        project=["*"],
    )
    for (node,) in qb_wc.iterall():
        label = node.label or ""
        plabel = node.process_label or ""
        state = node.process_state.value if node.process_state else "unknown"
        exc = node.exception or None
        cat = determine_category(label, plabel)
        ntype = determine_node_type(plabel)
        err = classify_error(ntype, state, node.exit_status, exc)
        nodes.append(
            PhononNodeInfo(
                pk=node.pk,
                label=label,
                process_label=plabel,
                process_state=state,
                exit_status=node.exit_status,
                exception=exc,
                node_type=ntype,
                category=cat,
                error_class=err,
            )
        )

    # CalcJobNode with "Phonon" in the label (CrystalParallelCalculation)
    qb_cj = QueryBuilder().append(
        CalcJobNode,
        filters={"label": {"like": "%Phonon%"}},
        project=["*"],
    )
    for (node,) in qb_cj.iterall():
        label = node.label or ""
        plabel = node.process_label or ""
        state = node.process_state.value if node.process_state else "unknown"
        exc = node.exception or None
        cat = determine_category(label, plabel)
        ntype = determine_node_type(plabel)
        err = classify_error(ntype, state, node.exit_status, exc)
        nodes.append(
            PhononNodeInfo(
                pk=node.pk,
                label=label,
                process_label=plabel,
                process_state=state,
                exit_status=node.exit_status,
                exception=exc,
                node_type=ntype,
                category=cat,
                error_class=err,
            )
        )

    # PhonopyFleurWorkChain (process_label; label doesn't always contain "Phonon")
    qb_pf = QueryBuilder().append(
        WorkChainNode,
        filters={"attributes.process_label": "PhonopyFleurWorkChain"},
        project=["*"],
    )
    existing_pks = {n.pk for n in nodes}
    for (node,) in qb_pf.iterall():
        if node.pk in existing_pks:
            continue
        label = node.label or ""
        plabel = node.process_label or ""
        state = node.process_state.value if node.process_state else "unknown"
        exc = node.exception or None
        cat = "phonopyfleur"
        ntype = "phonopyfleur"
        err = classify_error(ntype, state, node.exit_status, exc)
        nodes.append(
            PhononNodeInfo(
                pk=node.pk,
                label=label,
                process_label=plabel,
                process_state=state,
                exit_status=node.exit_status,
                exception=exc,
                node_type=ntype,
                category=cat,
                error_class=err,
            )
        )

    return nodes


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def aggregate_by_material(
    nodes: list[PhononNodeInfo],
) -> dict[str, MaterialSummary]:
    """Aggregate statuses by material.

    For each material this determines:
    - whether it has at least one fully successful calcjob (Finished [0]);
    - which error classes occur;
    - the PK lists of successful and failed calcjobs.
    """
    by_mat: dict[str, list[PhononNodeInfo]] = collections.defaultdict(list)
    for n in nodes:
        mat = extract_material(n.label)
        by_mat[mat].append(n)

    summaries: dict[str, MaterialSummary] = {}
    for mat, mat_nodes in by_mat.items():
        calcjobs = [n for n in mat_nodes if n.node_type == "calcjob"]
        workchains = [n for n in mat_nodes if n.node_type == "workchain"]
        ok_cjs = [n for n in calcjobs if n.error_class == "ok"]
        fail_cjs = [n for n in calcjobs if n.error_class != "ok"]
        # error_classes only covers calcjobs (workchain status doesn't reflect
        # whether the CRYSTAL calculation itself succeeded).
        error_classes = sorted({n.error_class for n in calcjobs})
        summaries[mat] = MaterialSummary(
            material=mat,
            has_ok_calcjob=len(ok_cjs) > 0,
            error_classes=error_classes,
            calcjob_count=len(calcjobs),
            workchain_count=len(workchains),
            pks_ok=[n.pk for n in ok_cjs],
            pks_failed=[n.pk for n in fail_cjs],
        )
    return summaries


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

ERROR_DESCRIPTIONS = {
    "ok": "Finished [0], no errors",
    "parser_error": (
        "Excepted: aiida-crystal-dft parser bug (Symbol lists / unhashable type). "
        "CRYSTAL finished normally, but the parser crashed."
    ),
    "crystal_symmops": (
        "Finished [400]: CRYSTAL failed with "
        "'ERROR **** MULTIP **** SYMMOPS DO NOT FORM A GROUP'."
    ),
    "workchain_bug": (
        "Excepted: BaseCrystalWorkChain bug "
        "(AttributeError: 'ExitCodesNamespace' has no attribute 'UNKNOWN_ERROR')."
    ),
    "killed": "Process killed manually (Killed).",
    "phonopy_fleur": (
        "Excepted: PhonopyFleurWorkChain — "
        "FileNotFoundError: FLEUR_INPGEN_PATH is not set."
    ),
    "invalid_output": (
        "Excepted: the parser could not read the CRYSTAL output "
        "(FileNotFoundError: ... is not a valid CRYSTAL output file)."
    ),
    "missing_output": (
        "Excepted: OUTPUT file missing from retrieved "
        "(FileNotFoundError: object with path `OUTPUT` does not exist)."
    ),
    "other_error": "Other error (unclassified).",
}


def build_report(
    nodes: list[PhononNodeInfo],
    summaries: dict[str, MaterialSummary],
) -> str:
    """Build the markdown report."""
    lines: list[str] = []
    lines.append("# Phonon calculation analysis via AiiDA\n")

    # --- Summary ---
    all_mats = set(summaries)
    ok_mats = {m for m, s in summaries.items() if s.has_ok_calcjob}
    fail_mats = all_mats - ok_mats

    # Counts by error class (at the calcjob level)
    err_counts = collections.Counter(
        n.error_class for n in nodes if n.node_type == "calcjob"
    )
    wc_err_counts = collections.Counter(
        n.error_class for n in nodes if n.node_type == "workchain"
    )
    pf_err_counts = collections.Counter(
        n.error_class for n in nodes if n.node_type == "phonopyfleur"
    )

    lines.append("## Summary\n")
    lines.append(f"- Total phonon-related nodes: **{len(nodes)}**")
    lines.append(f"- Unique materials: **{len(all_mats)}**")
    lines.append(
        f"- Materials with at least one successful calcjob (Finished [0]): **{len(ok_mats)}**"
    )
    lines.append(f"- Materials with no successful calcjobs: **{len(fail_mats)}**\n")

    lines.append("### Calcjobs (CrystalParallelCalculation)")
    for err, cnt in err_counts.most_common():
        lines.append(f"- {err}: {cnt}")
    lines.append("")

    lines.append("### Workchains (BaseCrystalWorkChain)")
    for err, cnt in wc_err_counts.most_common():
        lines.append(f"- {err}: {cnt}")
    lines.append("")

    if pf_err_counts:
        lines.append("### PhonopyFleurWorkChain")
        for err, cnt in pf_err_counts.most_common():
            lines.append(f"- {err}: {cnt}")
        lines.append("")

    # --- Error class descriptions ---
    lines.append("## Error classes\n")
    for err, desc in ERROR_DESCRIPTIONS.items():
        if (
            err in err_counts
            or err in wc_err_counts
            or err in pf_err_counts
            or err == "ok"
        ):
            lines.append(f"- **{err}**: {desc}")
    lines.append("")

    # --- Fully successful materials ---
    lines.append("## Fully successful materials\n")
    if ok_mats:
        lines.append("| Material | Calcjobs OK | PKs |")
        lines.append("|---|---|---|")
        for mat in sorted(ok_mats):
            s = summaries[mat]
            lines.append(
                f"| {mat} | {len(s.pks_ok)} | {', '.join(map(str, s.pks_ok))} |"
            )
    else:
        lines.append("_(none)_")
    lines.append("")

    # --- Failed materials by category ---
    lines.append("## Materials with no successful calcjobs\n")

    # Group by the dominant error
    by_err_group: dict[str, list[str]] = collections.defaultdict(list)
    for mat in sorted(fail_mats):
        s = summaries[mat]
        # Pick the "primary" error: prefer parser_error, crystal_symmops, etc.
        primary = "other_error"
        for err in (
            "parser_error",
            "crystal_symmops",
            "invalid_output",
            "missing_output",
            "workchain_bug",
            "phonopy_fleur",
            "killed",
        ):
            if err in s.error_classes:
                primary = err
                break
        by_err_group[primary].append(mat)

    for err in (
        "parser_error",
        "crystal_symmops",
        "invalid_output",
        "missing_output",
        "workchain_bug",
        "phonopy_fleur",
        "killed",
        "other_error",
    ):
        mats = by_err_group.get(err, [])
        if not mats:
            continue
        lines.append(f"### {err} ({len(mats)} materials)\n")
        lines.append(f"{ERROR_DESCRIPTIONS[err]}\n")
        for mat in mats:
            s = summaries[mat]
            lines.append(
                f"- {mat} — calcjobs: {s.calcjob_count}, errors: {', '.join(s.error_classes)}"
            )
        lines.append("")

    # --- Detailed node list ---
    lines.append("## Detailed node list\n")
    lines.append("| PK | Label | Type | State | Exit | Error class |")
    lines.append("|---|---|---|---|---|---|")
    for n in sorted(nodes, key=lambda x: x.pk):
        exit_str = str(n.exit_status) if n.exit_status is not None else "-"
        lines.append(
            f"| {n.pk} | {n.label} | {n.node_type} | {n.process_state} | {exit_str} | {n.error_class} |"
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------


def write_csv(nodes: list[PhononNodeInfo], path: Path) -> None:
    """Save the per-node status to a CSV file."""
    fieldnames = [
        "pk",
        "label",
        "process_label",
        "node_type",
        "category",
        "process_state",
        "exit_status",
        "error_class",
        "material",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for n in sorted(nodes, key=lambda x: x.pk):
            writer.writerow(
                {
                    "pk": n.pk,
                    "label": n.label,
                    "process_label": n.process_label,
                    "node_type": n.node_type,
                    "category": n.category,
                    "process_state": n.process_state,
                    "exit_status": n.exit_status if n.exit_status is not None else "",
                    "error_class": n.error_class,
                    "material": extract_material(n.label),
                }
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AiiDA profile name (default: the default profile).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to a markdown file for the report.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Path to a CSV file for the status dump.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Don't print the report to stdout.",
    )
    args = parser.parse_args()

    # Load profile
    load_profile(args.profile) if args.profile else load_profile()

    # Query nodes
    print("Querying phonon nodes from AiiDA...", file=sys.stderr)
    nodes = query_phonon_nodes()
    print(f"Nodes found: {len(nodes)}", file=sys.stderr)

    # Aggregate
    summaries = aggregate_by_material(nodes)
    print(f"Unique materials: {len(summaries)}", file=sys.stderr)

    # Report
    report = build_report(nodes, summaries)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(report, encoding="utf-8")
        print(f"Report saved: {out_path}", file=sys.stderr)

    if args.csv:
        csv_path = Path(args.csv)
        write_csv(nodes, csv_path)
        print(f"CSV saved: {csv_path}", file=sys.stderr)

    if not args.quiet:
        print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
