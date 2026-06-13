#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


API_BASE = "https://api.vultr.com/v2"


def get_api_key() -> str:
    api_key = os.environ.get("VULTR_API_KEY")
    if not api_key:
        print("ERROR: environment variable VULTR_API_KEY is not set", file=sys.stderr)
        print("Run: export VULTR_API_KEY='your_key_here'", file=sys.stderr)
        sys.exit(1)
    return api_key


def vultr_request(method: str, path: str, body: dict | None = None) -> dict:
    api_key = get_api_key()
    url = API_BASE + path

    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return {}
            return json.loads(raw)

    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        print(f"HTTP ERROR {e.code}: {raw}", file=sys.stderr)
        sys.exit(1)

    except urllib.error.URLError as e:
        print(f"URL ERROR: {e}", file=sys.stderr)
        sys.exit(1)


def print_table(rows: list[list[str]]) -> None:
    if not rows:
        return

    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]

    for row in rows:
        print("  ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))


def list_large_vm_plans(region: str, min_vcpu: int, min_ram_gb: int) -> None:
    data = vultr_request("GET", "/plans?type=all&per_page=500")

    rows = [[
        "PLAN_ID",
        "TYPE",
        "VCPU",
        "RAM",
        "DISK",
        "MONTHLY",
        "REGION",
    ]]

    min_ram_mb = min_ram_gb * 1024

    for plan in data.get("plans", []):
        locations = plan.get("locations", [])

        if region not in locations:
            continue

        if plan.get("vcpu_count", 0) < min_vcpu:
            continue

        if plan.get("ram", 0) < min_ram_mb:
            continue

        rows.append([
            plan.get("id", ""),
            plan.get("type", ""),
            str(plan.get("vcpu_count", "")),
            f"{plan.get('ram', 0) // 1024} GB",
            f"{plan.get('disk', '')} GB",
            f"${plan.get('monthly_cost', '')}/mo",
            region,
        ])

    if len(rows) == 1:
        print(
            f"No VM plans found in region={region} "
            f"with >= {min_vcpu} vCPU and >= {min_ram_gb} GB RAM"
        )
        return

    print_table(rows)


def list_baremetal_plans(region: str, min_ram_gb: int) -> None:
    data = vultr_request("GET", "/plans-metal?per_page=500")

    rows = [[
        "PLAN_ID",
        "CPU",
        "CORES",
        "THREADS",
        "RAM",
        "DISK",
        "MONTHLY",
        "REGION",
    ]]

    min_ram_mb = min_ram_gb * 1024

    for plan in data.get("plans_metal", []):
        locations = plan.get("locations", [])

        if region not in locations:
            continue

        if plan.get("ram", 0) < min_ram_mb:
            continue

        rows.append([
            plan.get("id", ""),
            plan.get("cpu_model", ""),
            str(plan.get("cpu_count", "")),
            str(plan.get("cpu_threads", "")),
            f"{plan.get('ram', 0) // 1024} GB",
            f"{plan.get('disk', '')} GB",
            f"${plan.get('monthly_cost', '')}/mo",
            region,
        ])

    if len(rows) == 1:
        print(
            f"No Bare Metal plans found in region={region} "
            f"with >= {min_ram_gb} GB RAM"
        )
        return

    print_table(rows)


def create_vm(
    region: str,
    plan_id: str,
    os_id: int,
    label: str,
    hostname: str,
    sshkey_id: str | None = None,
) -> None:
    body = {
        "region": region,
        "plan": plan_id,
        "os_id": os_id,
        "label": label,
        "hostname": hostname,
        "enable_ipv6": True,
    }

    if sshkey_id:
        body["sshkey_id"] = [sshkey_id]

    data = vultr_request("POST", "/instances", body)

    print(json.dumps(data, indent=2, ensure_ascii=False))


def create_baremetal(
    region: str,
    plan_id: str,
    os_id: int,
    label: str,
    hostname: str,
    sshkey_id: str | None = None,
) -> None:
    body = {
        "region": region,
        "plan": plan_id,
        "os_id": os_id,
        "label": label,
        "hostname": hostname,
        "enable_ipv6": True,
    }

    if sshkey_id:
        body["sshkey_id"] = [sshkey_id]

    data = vultr_request("POST", "/bare-metals", body)

    print(json.dumps(data, indent=2, ensure_ascii=False))


def list_instances() -> None:
    data = vultr_request("GET", "/instances?per_page=500")

    rows = [[
        "ID",
        "LABEL",
        "STATUS",
        "POWER",
        "VCPU",
        "RAM",
        "IP",
        "REGION",
    ]]

    for inst in data.get("instances", []):
        rows.append([
            inst.get("id", ""),
            inst.get("label", ""),
            inst.get("status", ""),
            inst.get("power_status", ""),
            str(inst.get("vcpu_count", "")),
            f"{inst.get('ram', 0)} MB",
            inst.get("main_ip", ""),
            inst.get("region", ""),
        ])

    print_table(rows)


def list_baremetals() -> None:
    data = vultr_request("GET", "/bare-metals?per_page=500")

    rows = [[
        "ID",
        "LABEL",
        "STATUS",
        "IP",
        "REGION",
    ]]

    for bm in data.get("bare_metals", []):
        rows.append([
            bm.get("id", ""),
            bm.get("label", ""),
            bm.get("status", ""),
            bm.get("main_ip", ""),
            bm.get("region", ""),
        ])

    print_table(rows)


def delete_vm(instance_id: str) -> None:
    vultr_request("DELETE", f"/instances/{instance_id}")
    print(f"Deleted VM instance: {instance_id}")


def delete_baremetal(baremetal_id: str) -> None:
    vultr_request("DELETE", f"/bare-metals/{baremetal_id}")
    print(f"Deleted Bare Metal instance: {baremetal_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Vultr helper for large crystal-calculation machines"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plans-vm", help="List VM plans")
    p.add_argument("--region", default="fra")
    p.add_argument("--min-vcpu", type=int, default=32)
    p.add_argument("--min-ram-gb", type=int, default=128)

    p = sub.add_parser("plans-baremetal", help="List Bare Metal plans")
    p.add_argument("--region", default="fra")
    p.add_argument("--min-ram-gb", type=int, default=128)

    p = sub.add_parser("create-vm", help="Create VM instance")
    p.add_argument("--region", default="fra")
    p.add_argument("--plan", required=True)
    p.add_argument("--os-id", type=int, default=2284)
    p.add_argument("--label", default="crystal-calc-32c128g")
    p.add_argument("--hostname", default="crystal-calc-32c128g")
    p.add_argument("--sshkey-id", default=None)

    p = sub.add_parser("create-baremetal", help="Create Bare Metal instance")
    p.add_argument("--region", default="fra")
    p.add_argument("--plan", required=True)
    p.add_argument("--os-id", type=int, default=2284)
    p.add_argument("--label", default="crystal-baremetal-128g")
    p.add_argument("--hostname", default="crystal-baremetal-128g")
    p.add_argument("--sshkey-id", default=None)

    sub.add_parser("instances", help="List VM instances")
    sub.add_parser("baremetals", help="List Bare Metal instances")

    p = sub.add_parser("delete-vm", help="Delete VM instance")
    p.add_argument("--id", required=True)

    p = sub.add_parser("delete-baremetal", help="Delete Bare Metal instance")
    p.add_argument("--id", required=True)

    args = parser.parse_args()

    if args.command == "plans-vm":
        list_large_vm_plans(args.region, args.min_vcpu, args.min_ram_gb)

    elif args.command == "plans-baremetal":
        list_baremetal_plans(args.region, args.min_ram_gb)

    elif args.command == "create-vm":
        create_vm(
            region=args.region,
            plan_id=args.plan,
            os_id=args.os_id,
            label=args.label,
            hostname=args.hostname,
            sshkey_id=args.sshkey_id,
        )

    elif args.command == "create-baremetal":
        create_baremetal(
            region=args.region,
            plan_id=args.plan,
            os_id=args.os_id,
            label=args.label,
            hostname=args.hostname,
            sshkey_id=args.sshkey_id,
        )

    elif args.command == "instances":
        list_instances()

    elif args.command == "baremetals":
        list_baremetals()

    elif args.command == "delete-vm":
        delete_vm(args.id)

    elif args.command == "delete-baremetal":
        delete_baremetal(args.id)


if __name__ == "__main__":
    main()