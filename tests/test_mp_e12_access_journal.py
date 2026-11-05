"""MP-E12a instrument tests: the access journal's schema, its values policy, and its own integrity checks.

The journal is what makes R11 work: under the amended R9/R11 a library-sourced word is an admitted source only
through the journal, so a record that cannot be verified is not evidence. These tests tamper with copies in
tmp_path -- never with the committed journal -- because a test that mutates a sealed artifact is the thing the
seal exists to prevent.
"""
from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_access_journal import (INLINE_MAX_VALUES, JOURNAL_SCHEMA_VERSION, REQUIRED_FIELDS,
                                         AccessJournal, JournalIntegrityError, pack_floats, verify_path)

COMMITTED = "experiments/MP-E12/results/access_journal_selftest.jsonl"


def _rec(**over):
    base = dict(probe_id="instrument_selftest", tensor="wte.weight", indices={"row": 1, "col": 2},
                shape=[50257, 768], dtype="F32", n_values=1, raw_bytes=4, values=[0.5], charged_ops=0,
                address_space_version="droso.donor_address_space.v1")
    base.update(over)
    return base


def test_schema_version_is_pinned_and_written(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec())
        assert j.schema_version == JOURNAL_SCHEMA_VERSION == "droso.access_journal.v1"
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert rec["schema_version"] == JOURNAL_SCHEMA_VERSION


def test_every_required_field_is_present(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec())
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    missing = [f for f in REQUIRED_FIELDS if f not in rec]
    assert not missing, f"journal record is missing {missing}"


def test_the_record_answers_which_address_for_which_probe(tmp_path):
    """The whole point of the journal: any read must be able to say which address, for which probe."""
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec(probe_id="extraction_1_p07"))
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert rec["probe_id"] == "extraction_1_p07"
    assert rec["tensor"] == "wte.weight" and rec["indices"] == {"row": 1, "col": 2}
    assert rec["timestamp_utc"].endswith("Z") and rec["donor_sha256"] == "abc"


def test_values_policy_small_reads_inline_large_reads_hashed(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec(values=[0.25] * 8, n_values=8, raw_bytes=32))
        j.record(**_rec(values=[0.25] * (INLINE_MAX_VALUES + 1), n_values=INLINE_MAX_VALUES + 1,
                        raw_bytes=4 * (INLINE_MAX_VALUES + 1)))
    a, b = (json.loads(l) for l in p.read_text(encoding="utf-8").splitlines())
    assert a["values_repr"] == "inline" and a["values"] == [0.25] * 8
    assert b["values_repr"] == "sha256_of_packed_bytes" and "values" not in b
    # the hash is over the packed little-endian bytes, so a reviewer with the donor can recompute it
    expect = hashlib.sha256(b"".join(struct.pack("<f", 0.25) for _ in range(INLINE_MAX_VALUES + 1))).hexdigest()
    assert b["values_bytes_sha256"] == expect == hashlib.sha256(pack_floats([0.25] * 33)).hexdigest()


def test_verify_catches_a_tampered_inline_value(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec())
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["values"] = [0.5000001]                      # one float nudged, hash left alone
    p.write_text(json.dumps(rec, sort_keys=True) + "\n", encoding="utf-8")
    j2 = AccessJournal(str(p), donor_sha256="abc", run_label="t")
    res = j2.verify()
    assert not res["clean"]
    assert any("do not hash to the recorded digest" in s for s in res["problems"]), res["problems"]


def test_verify_catches_a_deleted_or_reordered_record(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        for i in range(4):
            j.record(**_rec(indices={"row": i}))
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines[:2] + lines[3:]) + "\n", encoding="utf-8")   # record 2 removed
    res = AccessJournal(str(p), donor_sha256="abc", run_label="t").verify()
    assert not res["clean"] and any("monotonic" in s for s in res["problems"])


def test_verify_rejects_a_foreign_probe_prefix(tmp_path):
    """A read with no attributable probe is not journalised evidence; the prefix list is the guard."""
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec(probe_id="curiosity"))
    res = AccessJournal(str(p), donor_sha256="abc", run_label="t").verify()
    assert not res["clean"] and any("registered prefix" in s for s in res["problems"])


def test_append_only_refuses_a_schema_mismatch(tmp_path):
    p = tmp_path / "j.jsonl"
    with AccessJournal(str(p), donor_sha256="abc", run_label="t") as j:
        j.record(**_rec())
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[0])
    rec["schema_version"] = "droso.access_journal.v0"
    p.write_text(json.dumps(rec, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(JournalIntegrityError):
        AccessJournal(str(p), donor_sha256="abc", run_label="t")


def test_records_are_flushed_per_write(tmp_path):
    """A buffered journal loses reads on a crash, and it made the first self-test run report 0 records while
    the address space had counted 6. Durability per record is the property, so it is tested."""
    p = tmp_path / "j.jsonl"
    j = AccessJournal(str(p), donor_sha256="abc", run_label="t")
    j.record(**_rec())
    seen = len(p.read_text(encoding="utf-8").splitlines())   # no close(), no explicit flush()
    j.close()
    assert seen == 1


def test_the_committed_journal_is_clean(tmp_path):
    if not (ROOT / COMMITTED).exists():
        pytest.skip("self-test journal not present")
    res = verify_path(COMMITTED)
    assert res["clean"], res["problems"]
    assert res["schema_version"] == JOURNAL_SCHEMA_VERSION
    assert all(r["probe_id"] == "instrument_selftest" for r in
               (json.loads(l) for l in (ROOT / COMMITTED).read_text(encoding="utf-8").splitlines() if l))
    # the committed journal must not have been extended by these tests. The count comes from the summary
    # artifact rather than a literal: a hard-coded 6 broke the moment the self-test added a seventh read,
    # which is a brittle assertion, not a finding about the journal.
    summary_path = ROOT / "experiments/MP-E12/results/instrument_selftest_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert res["n_records"] == summary["journal_records"], (res["n_records"], summary["journal_records"])
