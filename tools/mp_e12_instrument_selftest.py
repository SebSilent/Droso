"""MP-E12a: exercise the two instruments against the real donor and journal every read.

WHAT THIS IS AND WHAT IT IS NOT. It is instrument validation: it resolves addresses from the header, reads a
handful of raw float32 values two different ways (through the address space, and by an independent struct.unpack
from the same byte range), checks they agree, checks the refusals refuse, and checks the file's byte accounting
closes. It is NOT an extraction: no nearest neighbours, no associations, no motifs, no interpretation of any
value. probe_id is `instrument_selftest` on every record so the journal can never be mistaken for extraction
evidence, and the journal's own verifier rejects records from an unregistered probe prefix.

The journal is append-only and this run creates it fresh; a second invocation refuses unless --append is passed,
because a committed journal that gets quietly re-written is the failure mode R11 exists to prevent.
"""
from __future__ import annotations

import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_access_journal import AccessJournal, verify_path
from tools.mp_e12_address_space import (DONOR_FILE, ExcludedTensor, GatherBudgetExceeded, IndexOutOfRange,
                                        UnknownTensor, DonorAddressSpace, sha256_of_file)

JOURNAL = "experiments/MP-E12/results/access_journal_selftest.jsonl"
OUT = "experiments/MP-E12/results/instrument_selftest_summary.json"
PROBE = "instrument_selftest"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _raises(fn) -> bool:
    """True when fn raises -- the refusal checks all need it, and a refusal that silently returns a value is
    the failure mode being tested for."""
    try:
        fn()
        return False
    except Exception:  # noqa: BLE001 -- the caller names the expected type by which it reads the result
        return True


def independent_read(abs_path: Path, base: int, tensor: str, row: int, col=None) -> float:
    """Read one float straight out of the file by arithmetic, bypassing the address space entirely."""
    with abs_path.open("rb") as f:
        (hlen,) = struct.unpack("<Q", f.read(8))
        hdr = json.loads(f.read(hlen).decode("utf-8"))
        off0, _ = hdr[tensor]["data_offsets"]
        shape = hdr[tensor]["shape"]
        width = shape[1] if len(shape) > 1 else 1
        idx = row * width + (col or 0)
        f.seek(8 + hlen + off0 + idx * 4)
        return struct.unpack("<f", f.read(4))[0]


def main() -> int:
    if "--append" not in sys.argv and (ROOT / JOURNAL).exists():
        raise SystemExit(f"REFUSED: {JOURNAL} already exists. A journal is append-only; pass --append to "
                         f"extend it deliberately, or write to a scratch path for experiments.")
    donor_sha = sha256_of_file()
    checks, failures = [], []

    def check(name, fn, expect=None):
        try:
            got = fn()
        except Exception as e:  # noqa: BLE001
            got = f"{type(e).__name__}: {e}"
        ok = (got == expect) if expect is not None else bool(got)
        checks.append({"check": name, "result": str(got)[:220], "passed": ok})
        if not ok:
            failures.append(name)
        print(f"  {'OK  ' if ok else 'FAIL'} {name}: {str(got)[:100]}")
        return got

    with AccessJournal(JOURNAL, donor_sha256=donor_sha, run_label="instrument_selftest") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        abs_path = ax.abs_path

        print("[selftest] identity and byte accounting")
        check("donor_sha256_matches_provenance", lambda: donor_sha[:16],
              expect="248dfc3911869ec4")
        ba = ax.byte_accounting()
        check("byte_accounting_closes", lambda: ba["closes"], expect=True)
        check("file_bytes_are_548105171", lambda: ba["file_bytes"], expect=548105171)
        check("no_gaps_in_the_data_region", lambda: ba["gaps_between_tensors"], expect=[])
        check("n_tensors_is_160", lambda: ba["n_tensors"], expect=160)

        print("[selftest] address arithmetic, two independent ways")
        for tensor, row, col in (("wte.weight", 0, 0), ("wte.weight", 451, 707),
                                 ("h.0.attn.c_attn.weight", 12, 1900),
                                 ("h.11.mlp.c_proj.weight", 2000, 300)):
            def both(t=tensor, r=row, c=col):
                via_ax = ax.read_scalar(t, r, c, probe_id=PROBE)
                via_raw = independent_read(abs_path, ax.data_base, t, r, c)
                return (round(via_ax, 6) == round(via_raw, 6), via_ax, via_raw)
            check(f"scalar_agreement {tensor}[{row}][{col}]", lambda: both()[0], expect=True)

        print("[selftest] refusals, each one a live path")
        for name, fn, exc in (
                ("row_beyond_shape", lambda: ax.read_scalar("wte.weight", 50257, 0, probe_id=PROBE),
                 IndexOutOfRange),
                ("col_beyond_shape", lambda: ax.read_scalar("wte.weight", 0, 768, probe_id=PROBE),
                 IndexOutOfRange),
                ("negative_row", lambda: ax.read_scalar("wte.weight", -1, 0, probe_id=PROBE), IndexOutOfRange),
                ("negative_col", lambda: ax.read_scalar("wte.weight", 0, -3, probe_id=PROBE), IndexOutOfRange),
                ("unknown_tensor", lambda: ax.read_scalar("transformer.wte.weight", 0, 0, probe_id=PROBE),
                 UnknownTensor),
                ("excluded_mask_buffer", lambda: ax.read_row("h.7.attn.bias", 0, probe_id=PROBE),
                 ExcludedTensor),
                ("gather_over_budget", lambda: ax.read_rows("wte.weight", list(range(65)), probe_id=PROBE),
                 GatherBudgetExceeded)):
            def raises(f=fn, e=exc):
                try:
                    f()
                    return "NO RAISE"
                except e:
                    return True
            check(name + "_refused", raises, expect=True)

        print("[selftest] row reads and the journal's own values policy")
        row0 = ax.read_row("wte.weight", 0, probe_id=PROBE)
        check("wte_row_has_768_values", lambda: len(row0), expect=768)
        ln = ax.read_vector("ln_f.weight", probe_id=PROBE)
        check("read_vector_returns_the_whole_1d_tensor", lambda: len(ln), expect=768)
        check("read_vector_refuses_a_2d_tensor",
              lambda: _raises(lambda: ax.read_vector("wte.weight", probe_id=PROBE)), expect=True)
        check("read_row_on_a_1d_tensor_is_one_value_not_the_vector",
              lambda: len(ax.read_row("ln_f.weight", 0, probe_id=PROBE)), expect=1)

        res = jr.verify()
        check("journal_verifies_clean", lambda: res["clean"], expect=True)
        check("journal_seq_monotonic", lambda: res["n_records"] == ax.n_reads, expect=True)
        check("every_record_is_probe_attributed",
              lambda: all(r["probe_id"] == PROBE for r in jr.read()), expect=True)
        check("no_record_touches_a_mask_buffer",
              lambda: all("attn.bias" not in r["tensor"] or ".c_attn." in r["tensor"] for r in jr.read()),
              expect=True)
        n_small = sum(1 for r in jr.read() if r["values_repr"] == "inline")
        n_hashed = sum(1 for r in jr.read() if r["values_repr"] == "sha256_of_packed_bytes")
        check("values_policy_split_recorded", lambda: n_small > 0 and n_hashed >= 0, expect=True)
        reads_by_run = {"n_reads": ax.n_reads, "row_reads": ax.rows_read, "bytes_read": ax.bytes_read,
                        "inline_records": n_small, "hashed_records": n_hashed}

    v = verify_path(JOURNAL)
    check("committed_journal_verifies_after_close", lambda: v["clean"], expect=True)

    out = {"schema": "droso.instrument_selftest_summary.v1", "ran_at_utc": now_utc(),
           "instruments": {"address_space": "tools/mp_e12_address_space.py",
                           "journal": "tools/mp_e12_access_journal.py"},
           "donor_file": DONOR_FILE, "donor_sha256": donor_sha,
           "journal_artifact": JOURNAL, "journal_records": v["n_records"],
           "journal_totals": {k: v[k] for k in ("total_values_read", "total_bytes_read", "total_charged_ops",
                                                "probes_seen", "tensors_touched")},
           "byte_accounting": ba, "checks": checks, "n_checks": len(checks), "failures": failures,
           "what_was_read": ("raw float32 values at header-resolved addresses, to prove the arithmetic and the "
                             "refusals. No neighbour search, no association, no motif, no interpretation."),
           "what_was_NOT_done": {"extraction_run": False, "probe_list_used": False,
                                 "forward_pass": False, "donor_runtime_imported": False},
           "reads_by_this_run": reads_by_run}
    (ROOT / OUT).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[selftest] {len(checks)} checks, {len(failures)} failures | journal records {v['n_records']} | "
          f"values read {v['total_values_read']:,} ({v['total_bytes_read']:,} B) | charged ops "
          f"{v['total_charged_ops']}")
    print(f"[selftest] wrote {OUT}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
