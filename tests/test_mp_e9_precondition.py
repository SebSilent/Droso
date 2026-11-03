"""PRE-1: the organs/ design step is a GATE, not a memo.

Why these tests exist.  experiments/MP-E9/organs_precondition.md claims that B.2 steps 1-2 are
blocked until the document is committed and sealed.  When the document was written, nothing in
experiments/MP-E9/registration.json referenced it and nothing in the seal manifest hashed it,
so the claim was unenforceable prose -- the file could be deleted and every other test would
still pass.  A precondition that lives only in a markdown file is a memo.

The direction that matters: these tests fail when the registration LOSES its reference to the
document, and when the sealed bytes DRIFT from the worktree.  They also fail if someone starts
implementing the flags in organs/ while PRE-1 is unsealed, which is the case the gate exists to
catch.  They deliberately do NOT fail once the flags exist and PRE-1 is sealed -- the gate
gates the order of operations, not the outcome.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.registration_seal import DEFAULT_MANIFEST

ROOT = Path(__file__).resolve().parents[1]
REG_PATH = ROOT / "experiments" / "MP-E9" / "registration.json"
ORGANS = ROOT / "organs" / "neural_language.py"

FLAGS = ["ELECTRIC_ARBITER_HEAD_BOUND", "ELECTRIC_QA_MORPH_NORMALIZE"]


@pytest.fixture(scope="module")
def reg() -> dict:
    if not REG_PATH.exists():
        pytest.skip("MP-E9 registration not present")
    return json.loads(REG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pre1(reg) -> dict:
    p = (reg.get("preconditions") or {}).get("PRE-1")
    assert p, ("MP-E9 registration has no preconditions.PRE-1. The organs/ design step is a "
               "precondition of B.2 steps 1-2 and must be registered as one.")
    return p


def test_pre1_names_a_precondition_document(pre1):
    doc = pre1.get("document")
    assert doc, "PRE-1 does not name a document"
    assert doc.endswith(".md"), f"PRE-1 document is not a design doc: {doc}"


def test_the_precondition_document_exists(pre1):
    p = ROOT / pre1["document"]
    assert p.exists(), f"PRE-1 references {pre1['document']} which is not in the tree"
    assert p.stat().st_size > 4000, "the precondition document is a stub, not a design step"


def test_the_precondition_document_is_in_the_seal_manifest(pre1):
    """A file nothing hashes is a file nothing protects."""
    assert pre1["document"] in DEFAULT_MANIFEST, (
        f"{pre1['document']} is not in tools/registration_seal.py DEFAULT_MANIFEST, so the seal "
        "never checks it and the precondition can be edited or deleted without a signal")


def test_the_precondition_document_is_actually_sealed(pre1, reg):
    """Registered AND hashed: the manifest entry has to have produced a seal record."""
    files = (reg.get("harness_hashes") or {}).get("files") or {}
    h = files.get(pre1["document"])
    assert h, (f"{pre1['document']} is in the manifest but has no entry in "
               "harness_hashes.files -- the seal was never re-stamped after it was added, so "
               "PRE-1 is registered against bytes that are not under seal")
    assert h.get("sha256_lf"), "seal entry carries no LF-normalised hash"


def test_sealed_bytes_match_the_worktree(pre1, reg):
    """Drift is the failure mode. A sealed document that no longer matches its seal is a lie."""
    h = (reg.get("harness_hashes") or {}).get("files", {}).get(pre1["document"])
    if not h:
        pytest.skip("not sealed yet")
    import hashlib
    now = hashlib.sha256((ROOT / pre1["document"]).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert now == h["sha256_lf"], (
        f"{pre1['document']} changed after being sealed ({now[:12]} != {h['sha256_lf'][:12]}). "
        "Either restore the document or re-stamp -- do not edit a sealed precondition silently.")


def test_flag_names_do_not_drift_between_registration_and_document(pre1):
    """Two spellings of one flag is two flags. The registration is the normative list."""
    doc = (ROOT / pre1["document"]).read_text(encoding="utf-8")
    registered = set((pre1.get("flags") or {}))
    assert registered == set(FLAGS), f"PRE-1 flags drifted: {sorted(registered)}"
    for f in sorted(registered):
        assert f in doc, f"{f} is registered but the document never names it"


def test_pre1_blocks_the_right_steps(pre1):
    blocks = " ".join(pre1.get("blocks") or [])
    assert "B.2 step 1" in blocks and "B.2 step 2" in blocks, (
        "PRE-1 must name the steps it blocks, or 'precondition' means nothing")


def test_implementation_without_a_seal_is_the_case_the_gate_exists_to_catch(pre1, reg):
    """If the flags already exist in organs/, PRE-1 must be sealed.

    Before implementation this passes trivially (no flags in organs/). After implementation it
    passes because the seal was taken first. It FAILS in the one situation that matters: someone
    wrote the bound into the organ while the precondition document was still unsealed.
    """
    src = ORGANS.read_text(encoding="utf-8", errors="replace")
    implemented = [f for f in FLAGS if f in src]
    if not implemented:
        return
    files = (reg.get("harness_hashes") or {}).get("files") or {}
    assert pre1["document"] in files, (
        f"{implemented} implemented in organs/neural_language.py while {pre1['document']} is "
        "unsealed -- PRE-1 requires the design step to be committed and sealed BEFORE B.2 "
        "steps 1-2 run")


def test_must_not_change_counts_agree_with_the_evidence_file(pre1):
    """The row counts PRE-1 promises not to move, read from the sealed evidence, not from prose.

    36 arbiter-tell rows and 24 guarded-absence rows are the two populations the bound must
    leave alone row for row. If the evidence file no longer contains them, the promise is
    vacuous and this test says so rather than passing quietly.
    """
    ev = ROOT / "docs" / "evidence" / "electric_learn_bench.json"
    if not ev.exists():
        pytest.skip("committed bench evidence absent")
    data = json.loads(ev.read_text(encoding="utf-8"))
    # Shape, measured not assumed: data["probes"] is an INT (136), not a list. The rows live at
    # arms[arm]["probes"][depth][phase] as lists, and the four shadow rows live at data["shadow"].
    rows = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                if isinstance(x, dict) and "src" in x:
                    rows.append(x)
                else:
                    walk(x)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)

    walk(data.get("arms"))
    walk(data.get("shadow"))
    src = {}
    for r in rows:
        src[r.get("src") or ""] = src.get(r.get("src") or "", 0) + 1
    assert src.get("arbiter tell") == 36, f"arbiter-tell population moved: {src.get('arbiter tell')}"
    assert src.get("electric_absence") == 24, \
        f"guarded-absence population moved: {src.get('electric_absence')}"
    mnc = " ".join(pre1.get("must_not_change") or [])
    assert "36" in mnc and "24" in mnc, "PRE-1 does not state the two populations it protects"
