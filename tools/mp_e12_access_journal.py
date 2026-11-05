"""MP-E12a instrument 2 (v1.2 B.6 item 3): the access journal.

WHAT IT IS. An append-only JSONL record with one entry per donor read: address, tensor, indices, the values
returned (or a hash of them, see the policy below), the requesting probe, a timestamp, the charged operation
count, and the identity of the donor bytes and the instrument that did the reading. R11 makes a library-sourced
address an admitted source *only through the journal*, so the journal is not instrumentation hygiene -- it is
the thing that makes a word quotable, and the thing that makes it refusable.

THE VALUES POLICY, stated rather than left implicit. A record inlines the returned values when there are at
most INLINE_MAX_VALUES of them, and otherwise stores `values_sha256` over the packed little-endian bytes plus
the value count. The reason is size and honesty in both directions: a journal that inlined every row of wte
would be a 548 MB second copy of the donor sitting next to the first one, which defeats the point of an address
space; and a journal that only said "read 768 floats" would not prove WHICH floats. Hashing the exact bytes
returned keeps the proof without keeping the payload, and a reviewer who has the donor file can recompute the
hash and see the same thing the probe saw.

WHAT A RECORD CANNOT SAY. It records that a read happened and what came back. It does not record an
interpretation. Association claims live in the extraction artifacts and cite journal sequence numbers; the
journal never becomes a place where a result can be quietly restated.
"""
from __future__ import annotations

import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNAL_SCHEMA_VERSION = "droso.access_journal.v1"
INLINE_MAX_VALUES = 32
REQUIRED_FIELDS = ("seq", "timestamp_utc", "probe_id", "tensor", "indices", "shape", "dtype", "n_values",
                   "raw_bytes", "values_repr", "charged_ops", "address_space_version", "donor_sha256")
PROBE_ID_PREFIXES = ("instrument_selftest", "extraction_", "unattributed")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def pack_floats(values, dtype: str = "F32") -> bytes:
    code = {"F32": "f", "F64": "d", "F16": "e", "I32": "i", "I64": "q", "U8": "B", "I8": "b"}[dtype]
    return b"".join(struct.pack("<" + code, v) for v in values)


class JournalIntegrityError(RuntimeError):
    """verify() found a record that does not match its own hash, its own schema, or its own sequence."""


class AccessJournal:
    """Append-only writer with a reader/verifier. One file per run; the file is an artifact, not a log."""

    def __init__(self, path: str, donor_sha256: str, run_label: str,
                 root: Path = ROOT, schema_version: str = JOURNAL_SCHEMA_VERSION):
        self.root = Path(root)
        self.rel_path = path
        self.abs_path = self.root / path
        self.donor_sha256 = donor_sha256
        self.run_label = run_label
        self.schema_version = schema_version
        self.seq = 0
        self.abs_path.parent.mkdir(parents=True, exist_ok=True)
        if self.abs_path.exists():
            # continue an existing journal rather than clobber it: append-only means append-only
            existing = [json.loads(l) for l in
                        self.abs_path.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.seq = len(existing)
            if existing and existing[0].get("schema_version") != schema_version:
                raise JournalIntegrityError(
                    f"{path} was written under schema {existing[0].get('schema_version')!r}; refusing to "
                    f"append {schema_version} records into it")
            self._fh = self.abs_path.open("a", encoding="utf-8", newline="\n")
        else:
            self._fh = self.abs_path.open("w", encoding="utf-8", newline="\n")

    def record(self, *, probe_id: str, tensor: str, indices: dict, shape: list, dtype: str, n_values: int,
               raw_bytes: int, values, charged_ops: int, address_space_version: str, extra: dict = None):
        self.seq += 1
        packed = pack_floats(list(values), dtype)
        small = len(values) <= INLINE_MAX_VALUES
        rec = {"seq": self.seq, "timestamp_utc": now_utc(), "run_label": self.run_label,
               "probe_id": probe_id, "tensor": tensor, "indices": indices, "shape": shape, "dtype": dtype,
               "n_values": n_values, "raw_bytes": raw_bytes,
               "values_repr": "inline" if small else "sha256_of_packed_bytes",
               "charged_ops": charged_ops, "address_space_version": address_space_version,
               "donor_sha256": self.donor_sha256, "schema_version": self.schema_version,
               "values_bytes_sha256": hashlib.sha256(packed).hexdigest()}
        if small:
            rec["values"] = list(values)
        if extra:
            rec.update(extra)
        self._fh.write(json.dumps(rec, sort_keys=True) + "\n")
        # flush per record. A buffered journal is a journal that loses reads on a crash, and it also makes
        # verify() under-report: the first self-test run saw 6 reads in the address space and 0 records on
        # disk, which looked like a sequence-number bug and was a buffering bug.
        self._fh.flush()
        return rec

    def flush(self):
        self._fh.flush()

    def close(self):
        self._fh.flush()
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # ---------------------------------------------------------------- verification
    def read(self):
        if not self.abs_path.exists():
            return []
        return [json.loads(l) for l in self.abs_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    def verify(self) -> dict:
        """Re-derive every hash from the bytes the record says it returned, and check the journal's own
        invariants. A journal that cannot be verified is a list of claims."""
        recs = self.read()
        problems = []
        for i, r in enumerate(recs, 1):
            missing = [f for f in REQUIRED_FIELDS if f not in r]
            if missing:
                problems.append(f"record {i}: missing {missing}")
                continue
            if r["seq"] != i:
                problems.append(f"record {i}: seq is {r['seq']}, position is {i} -- the journal is not "
                                f"monotonic or a record was deleted")
            if r["schema_version"] != self.schema_version:
                problems.append(f"record {i}: schema {r['schema_version']!r} != {self.schema_version!r}")
            if r["values_repr"] == "inline":
                packed = pack_floats(r["values"], r["dtype"])
                if hashlib.sha256(packed).hexdigest() != r["values_bytes_sha256"]:
                    problems.append(f"record {i}: inline values do not hash to the recorded digest")
                if len(r["values"]) != r["n_values"]:
                    problems.append(f"record {i}: n_values {r['n_values']} != {len(r['values'])} inline")
            elif r["values_repr"] != "sha256_of_packed_bytes":
                problems.append(f"record {i}: unknown values_repr {r['values_repr']!r}")
            if not str(r["probe_id"]).startswith(PROBE_ID_PREFIXES):
                problems.append(f"record {i}: probe_id {r['probe_id']!r} is not from a registered prefix")
            if r["charged_ops"] not in (0, int(r["charged_ops"])):
                problems.append(f"record {i}: charged_ops is not an integer")
        return {"n_records": len(recs), "schema_version": self.schema_version, "problems": problems,
                "clean": not problems,
                "probes_seen": sorted({r["probe_id"] for r in recs}),
                "tensors_touched": sorted({r["tensor"] for r in recs}),
                "total_values_read": sum(r["n_values"] for r in recs),
                "total_bytes_read": sum(r["raw_bytes"] for r in recs),
                "total_charged_ops": sum(r["charged_ops"] for r in recs),
                "journal": self.rel_path}


def verify_path(path: str, root: Path = ROOT, schema_version: str = JOURNAL_SCHEMA_VERSION) -> dict:
    """Verify a committed journal without a donor hash to compare against (the records carry their own)."""
    j = AccessJournal.__new__(AccessJournal)
    j.root = Path(root)
    j.rel_path = path
    j.abs_path = j.root / path
    j.schema_version = schema_version
    j.donor_sha256 = None
    j.run_label = None
    j.seq = 0
    return j.verify()
