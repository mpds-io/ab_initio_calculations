import os
import orjson
from mpds_client import MPDSDataRetrieval, MPDSDataTypes


filename = "imaginary_phonons.jsonl"
query = {
    "props": "phonons",
    "classes": "binary",
}

client = MPDSDataRetrieval()
client.dtype = MPDSDataTypes.AB_INITIO
records = client.get_data(query, fields=None)

if not os.path.exists(filename):
    open(filename, "wb").close()


def get_entry(record):
    return record.get("sample", {}).get("material", {}).get("entry")


existing_entries = set()
with open(filename, "rb") as f:
    for line in f:
        if line.strip():
            entry = get_entry(orjson.loads(line))
            if entry is not None:
                existing_entries.add(entry)


def iter_freqs(modes_freqs):
    if isinstance(modes_freqs, dict):
        for freqs in modes_freqs.values():
            for f in freqs:
                yield f
    elif isinstance(modes_freqs, list):
        for f in modes_freqs:
            yield f


def has_imaginary(record):
    for measurement in record.get("sample", {}).get("measurement", []):
        matrix = measurement.get("property", {}).get("matrix", {})
        modes_freqs = matrix.get("modes_freqs")
        if modes_freqs is None:
            continue
        if any(f < 0 for f in iter_freqs(modes_freqs)):
            return True
    return False


new_records = [
    record for record in records
    if get_entry(record) not in existing_entries and has_imaginary(record)
]

with open(filename, "ab") as f:
    for record in new_records:
        f.write(orjson.dumps(record) + b"\n")
