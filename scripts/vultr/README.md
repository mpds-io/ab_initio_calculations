# Vultr bare metal setup for FLEUR and CRYSTAL calculations

This directory contains scripts for provisioning Vultr bare metal servers.

## Choosing a plan

For example, in Amsterdam (region `ams`):

| Plan | CPU | RAM | Disk | Price | Notes |
|------|-----|-----|------|-------|-------|
| `vbm-8c-132gb` | Intel E-2288G, 8C/16T | 128 GB | 2x 960 GB NVMe (1.92 TB total) | $350/mo ($0.479/hr) | NVMe is the main disk, no extra setup needed |
| `vbm-8c-132gb-v2` | Intel E-2388G, 8C/16T | 128 GB | 2x 960 GB NVMe (1.92 TB total) | $350/mo ($0.479/hr) | Same, newer CPU |
| `vbm-24c-256gb-amd` | AMD EPYC 7443P, 24C/48T | 256 GB | 2x 480 GB SSD + 2x 1.92 TB NVMe | $725/mo ($0.993/hr) | NVMe drives are unformatted, must be mounted manually |

**Important:** The `vbm-24c-256gb-amd` plan physically ships with 4 drives:
- `sda` — 480 GB SSD (system, mounted at `/`)
- `sdb` — 480 GB SSD (unused)
- `nvme0n1` — 1.92 TB NVMe (unformatted)
- `nvme1n1` — 1.92 TB NVMe (unformatted)

But the Vultr API only reports `disk: 480 GB`, `disk_count: 2`, `type: SSD`.
The two NVMe drives are **not shown in the API** but are physically present on
the server. You must create a RAID0 and mount them manually (see section 2).

**Which plan to choose:**
- `vbm-8c-132gb` — simpler setup (NVMe is already the main disk, just mount it
  at `/data` or use as-is). Seebeck calculations will run fine, just slower on 8
  cores. No RAID0 needed.
- `vbm-24c-256gb-amd` — faster (24 cores), but requires NVMe RAID0 setup.
  Without it, only 447 GB is available and Seebeck calculations will crash with
  "No space left on device" after using ~419 GB.

CRYSTAL pproperties (Seebeck/TDF) calculations create large temporary files
(`fort.70.peXX`) — a single calculation can use **600+ GB** of disk space.

## 1. Provisioning

```shell
export VULTR_API_KEY='your_api_key_here'

# List available bare metal plans (e.g. ams = Amsterdam)
python vultr_create.py plans-baremetal --region ams --min-ram-gb 128

# Create a bare metal instance
# For vbm-24c-256gb-amd (recommended for speed):
python vultr_create.py create-baremetal \
    --region ams \
    --plan vbm-24c-256gb-amd \
    --os-id 2284 \
    --label crystal-bench-24c

# Or for vbm-8c-132gb (cheaper, simpler, slower):
python vultr_create.py create-baremetal \
    --region ams \
    --plan vbm-8c-132gb \
    --os-id 2284 \
    --label crystal-bench-8c

# Check status
python vultr_create.py baremetals

# Delete when done
python vultr_create.py delete-baremetal --id INSTANCE_ID
```

## 2. Mount NVMe RAID0 (vbm-24c-256gb-amd only)

**This step is required for `vbm-24c-256gb-amd`.** Without it, only 447 GB is
available and Seebeck calculations will crash.

For `vbm-8c-132gb`, NVMe is already the main disk — just make sure `/data`
exists and has enough space.

SSH into the new server and run:

```shell
# Verify NVMe drives are visible
lsblk
# vbm-24c-256gb-amd: you should see nvme0n1 and nvme1n1 (each 1.7 TB, unformatted)

# Create RAID0 array from both NVMe drives
mdadm --create /dev/md0 --level=0 --raid-devices=2 /dev/nvme0n1 /dev/nvme1n1

# Format with ext4 (stride=128 for 512KB chunk, stripe-width=256 for 2 devices)
mkfs.ext4 -b 4096 -E stride=128,stripe-width=256 /dev/md0

# Get UUID for fstab (persistent across reboots)
blkid /dev/md0
# Example: UUID="436709c9-ec43-4269-a6b4-e3af2174f393" TYPE="ext4"

# Mount at /data (yascheduler uses this as remote data directory)
mkdir -p /data
echo 'UUID=436709c9-ec43-4269-a6b4-e3af2174f393 /data ext4 defaults 0 2' >> /etc/fstab
mount /data

# Save RAID config for reassembly after reboot
mdadm --detail --scan >> /etc/mdadm/mdadm.conf
update-initramfs -u

# Verify
df -h /data
# Should show ~3.5 TB available
```

## 3. Increase /dev/shm

CRYSTAL pproperties uses `/dev/shm` for inter-process communication during
parallel Seebeck/TDF calculations. The default size (half of RAM) may not be
enough. Increase it to 200 GB:

```shell
echo 'tmpfs /dev/shm tmpfs defaults,size=200G 0 0' >> /etc/fstab
mount -o remount /dev/shm

# Verify
df -h /dev/shm
# Should show 200G
```

## 4. Increase ulimit

FLEUR and CRYSTAL parallel calculations open many files simultaneously.
The default `nofile` limit (1024) is too low and causes crashes:

```shell
cat >> /etc/security/limits.conf <<EOF
* soft nofile 65536
* hard nofile 65536
root soft nofile 65536
root hard nofile 65536
EOF

# Log out and log back in, then verify:
ulimit -n
# Should print 65536
```

## 5. Install software

```shell
apt update && apt install -y \
    openmpi-bin openmpi-common libopenmpi-dev \
    libscalapack-openmpi-dev \
    libxml2-dev libblas-dev liblapack-dev \
    build-essential gfortran cmake git

# ScaLAPACK symlink (FLEUR and CRYSTAL expect libscalapack.so.2.2)
ln -sf /usr/lib/x86_64-linux-gnu/libscalapack-openmpi.so.2.1 \
       /usr/lib/x86_64-linux-gnu/libscalapack-openmpi.so.2.2
```

Place binaries at:
- `/data/engines/fleur/fleur_MPI` — FLEUR executable
- `/data/engines/crystal/Pcrystal` and `Pproperties` — CRYSTAL executables

## 6. Cleanup

When calculations are done, download results from AiiDA, then destroy the
server to stop billing:

```shell
python vultr_create.py delete-baremetal --id INSTANCE_ID
```

**All data on the server is lost after destruction.**