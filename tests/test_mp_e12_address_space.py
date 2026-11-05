"""MP-E12a instrument tests: the address space, its refusals, and the C4 import-surface assertion.

THE DONOR IS NOT IN GIT, BY DESIGN (548 MB, .gitignore:180). Every test here skips cleanly when the donor file
is absent, and says so in the skip reason, because a fresh clone cannot have it. The instrument itself is
committed; the bytes are re-derivable from the pinned revision by tools/mp_e12_land_donor.py.
"""
from __future__ import annotations

import ast
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_access_journal import AccessJournal, verify_path
from tools.mp_e12_address_space import (DONOR_FILE, DTYPE_CODE, ExcludedTensor, GatherBudgetExceeded,
                                        GatherNotPermitted, IndexOutOfRange, UnknownTensor,
                                        DonorAddressSpace, sha256_of_file)

DONOR = ROOT / DONOR_FILE
needs_donor = pytest.mark.skipif(not DONOR.exists(),
                                 reason=("donor bytes are not in git by design (.gitignore:180); re-derive "
                                         "with tools/mp_e12_land_donor.py"))

# the module names C4 audits for. A deployment path that imports any of them is running the donor.
FORBIDDEN_MODULES = ("torch", "transformers", "tensorflow", "tf", "flax", "jax", "onnx", "keras", "numpy",
                     "accelerate", "bitsandbytes")
INSTRUMENT_FILES = ["tools/mp_e12_address_space.py", "tools/mp_e12_access_journal.py"]


def imports_of(rel: str):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


# ------------------------------------------------------------------ C4: the named assertion
def test_no_donor_runtime_on_the_address_path():
    """C4 AUDIT, NAMED BEFORE THE TEMPTATION. The plan's C4 condition audits the deployment path for donor
    runtime; R11 forbids a forward pass, sampling or inference anywhere a value could reach an answer. This
    test is the check that exists now: the two instruments import nothing from the donor-runtime list -- not
    torch, not transformers, not even numpy -- and importing them does not put any of those names into
    sys.modules. If somebody later adds `import torch` to the address space to make a row read convenient,
    this test fails with the reason in its own name.
    """
    for rel in INSTRUMENT_FILES:
        mods = imports_of(rel)
        bad = sorted(m for m in mods if m in FORBIDDEN_MODULES)
        assert not bad, f"{rel} imports donor-runtime module(s) {bad}; C4 forbids that on this path"
    before = set(sys.modules)
    import importlib
    for rel in INSTRUMENT_FILES:
        importlib.import_module(rel[:-3].replace("/", "."))
    gained = {m.split(".")[0] for m in set(sys.modules) - before}
    runtime = sorted(gained & set(FORBIDDEN_MODULES))
    assert not runtime, f"importing the instruments pulled in donor runtime modules: {runtime}"


def test_the_probe_list_was_fixed_without_the_address_space():
    """The probe list's claim is that no weight value informed it. That is checkable, not a sentence: the
    script that produced it must not import the address space, must not mmap the donor, and must not touch
    struct on the tensor region."""
    rel = "tools/mp_e12_fix_probe_list.py"
    mods = imports_of(rel)
    # checked against the IMPORTS and the tensor file's name, not against the whole source: the script's
    # docstring contains the words "mmap" and "address space" precisely to say it uses neither, and a token
    # scan over prose would fail on its own explanation. That false positive was the first version of this
    # test, and the fix is to check what the code can do, not what it says about itself.
    forbidden_imports = {"mmap", "struct", "mp_e12_address_space", "mp_e12_access_journal", "numpy", "torch",
                         "transformers"}
    bad = sorted(mods & forbidden_imports)
    assert not bad, f"the probe-list script imports {bad}; its value-blind claim would then be void"
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert "model.safetensors" not in src, ("the probe-list script names the tensor file, so it could open it")
    assert "DonorAddressSpace" not in src.split('"""')[-1], "the code after the docstring uses the address space"


# ------------------------------------------------------------------ header arithmetic
@needs_donor
def test_byte_accounting_closes_to_the_recorded_file_size(tmp_path):
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        ba = ax.byte_accounting()
        assert ba["closes"] is True
        assert ba["file_bytes"] == 548105171
        assert 8 + ba["header_json_bytes"] + ba["tensor_data_bytes"] == ba["file_bytes"]
        assert ba["gaps_between_tensors"] == [], "the data region must tile without holes"
        assert ba["n_tensors"] == 160


@needs_donor
def test_address_arithmetic_matches_the_header_offsets(tmp_path):
    """Two independent ways to reach one float: the address space's arithmetic, and a raw seek computed from
    the header by hand. They must land on the same four bytes."""
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        for tensor, row, col in (("wte.weight", 0, 0), ("wte.weight", 50256, 767), ("wpe.weight", 1023, 5),
                                 ("h.0.attn.c_attn.weight", 767, 2303),
                                 ("h.11.mlp.c_fc.weight", 700, 3000)):
            via_space = ax.read_scalar(tensor, row, col, probe_id="instrument_selftest")
            spec = ax.table[tensor]
            width = spec["shape"][1]
            off = ax.data_base + spec["offsets"][0] + (row * width + col) * DTYPE_CODE[spec["dtype"]][1]
            with DONOR.open("rb") as f:
                f.seek(off)
                via_raw = struct.unpack("<f", f.read(4))[0]
            assert via_space == via_raw, f"{tensor}[{row}][{col}] disagrees: {via_space} vs {via_raw}"


@needs_donor
def test_row_read_returns_the_recorded_width(tmp_path):
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        assert len(ax.read_row("wte.weight", 0, probe_id="instrument_selftest")) == 768
        assert len(ax.read_row("h.0.mlp.c_fc.weight", 0, probe_id="instrument_selftest")) == 3072
        assert len(ax.read_row("ln_f.weight", 0, probe_id="instrument_selftest")) == 1  # 1-D tensor


# ------------------------------------------------------------------ refusals
@needs_donor
def test_out_of_range_row_is_refused(tmp_path):
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        with pytest.raises(IndexOutOfRange):
            ax.read_scalar("wte.weight", 50257, 0, probe_id="instrument_selftest")
        with pytest.raises(IndexOutOfRange):
            ax.read_scalar("wte.weight", 0, 768, probe_id="instrument_selftest")


@needs_donor
def test_negative_index_is_refused_not_wrapped(tmp_path):
    """Python would happily read the last row for [-1]. An address has to be a position in the file, or the
    journal records something that is not where the value came from."""
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        with pytest.raises(IndexOutOfRange):
            ax.read_scalar("wte.weight", -1, 0, probe_id="instrument_selftest")
        with pytest.raises(IndexOutOfRange):
            ax.read_scalar("wte.weight", 0, -1, probe_id="instrument_selftest")


@needs_donor
def test_tensor_not_in_the_index_is_refused(tmp_path):
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        # the PyTorch module path, which is NOT how this file indexes tensors -- the trap the landing tool
        # fell into first, now a test
        with pytest.raises(UnknownTensor):
            ax.read_scalar("transformer.wte.weight", 0, 0, probe_id="instrument_selftest")
        with pytest.raises(UnknownTensor):
            ax.read_scalar("wt.weight", 0, 0, probe_id="instrument_selftest")  # tied away; absent


# ------------------------------------------------------------------ the mask-buffer exclusion
@needs_donor
def test_the_twelve_causal_mask_buffers_are_excluded_by_name(tmp_path):
    """Registered exclusion: h.<N>.attn.bias are constant causal masks, not weights. 12 tensors, 1,048,576
    floats each, 12,582,912 in total -- 9.18% of the index. A feature pool that mined them would learn a
    triangle and call it a donor."""
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        excluded = ax.excluded_tensors()
        assert len(excluded) == 12, excluded
        assert excluded[0] == "h.0.attn.bias" and excluded[-1] == "h.9.attn.bias"  # sorted lexicographically
        floats = sum(1 for _ in excluded) * 1048576
        assert floats == 12582912
        total = sum(_prod(ax.shape(t)) for t in ax.tensor_names())
        assert total == 137022720
        assert total - floats == 124439808, "the weights-only count that the sealed synthetic premise uses"
        assert round(100 * floats / total, 2) == 9.18
        for t in excluded:
            with pytest.raises(ExcludedTensor):
                ax.read_row(t, 0, probe_id="instrument_selftest")
            with pytest.raises(ExcludedTensor):
                ax.read_scalar(t, 0, 0, probe_id="instrument_selftest")
        # the exclusion must not swallow the trainable bias that shares the suffix. It is 1-D, so it is read
        # as a row -- read_scalar asks for (row, col) and refuses a 1-D tensor, which is the correct refusal.
        assert not ax.is_excluded("h.0.attn.c_attn.bias")
        assert len(ax.read_vector("h.0.attn.c_attn.bias", probe_id="instrument_selftest")) == 2304
        with pytest.raises(IndexOutOfRange):
            ax.read_scalar("h.0.attn.c_attn.bias", 0, 0, probe_id="instrument_selftest")
        with pytest.raises(IndexOutOfRange):
            ax.read_vector("wte.weight", probe_id="instrument_selftest")   # 2-D: read_rows is the door


def _prod(shape):
    q = 1
    for x in shape:
        q *= int(x)
    return q


@needs_donor
def test_gather_budget_stops_a_free_bulk_read(tmp_path):
    """Under the registered op rule a gather costs zero operations, so without this cap a probe could pull the
    whole embedding matrix for free. The loophole is registered; the cap is enforced here."""
    with AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="test", run_label="t") as jr, \
            DonorAddressSpace(journal=jr) as ax:
        with pytest.raises(GatherBudgetExceeded):
            ax.read_rows("wte.weight", list(range(65)), probe_id="instrument_selftest")
        rows = ax.read_rows("wte.weight", list(range(64)), probe_id="instrument_selftest")
        assert len(rows) == 64


@needs_donor
def test_there_is_no_unjournaled_read_path(tmp_path):
    with pytest.raises(GatherNotPermitted):
        DonorAddressSpace()


# ------------------------------------------------------------------ the committed self-test artifact
@needs_donor
def test_the_committed_selftest_journal_verifies(tmp_path):
    """The journal that shipped with this step must still verify against the donor bytes it recorded."""
    rel = "experiments/MP-E12/results/access_journal_selftest.jsonl"
    if not (ROOT / rel).exists():
        pytest.skip("self-test journal not present")
    res = verify_path(rel)
    assert res["clean"], res["problems"]
    assert res["probes_seen"] == ["instrument_selftest"]
    assert res["total_charged_ops"] == 0
    summary = json.loads((ROOT / "experiments/MP-E12/results/instrument_selftest_summary.json")
                         .read_text(encoding="utf-8"))
    assert summary["journal_records"] == res["n_records"]
    assert summary["failures"] == []
    assert summary["what_was_NOT_done"]["extraction_run"] is False
    assert summary["what_was_NOT_done"]["forward_pass"] is False
    assert summary["what_was_NOT_done"]["donor_runtime_imported"] is False


@needs_donor
def test_donor_hash_matches_the_provenance_record(tmp_path):
    prov = json.loads((ROOT / "experiments/MP-E12/donor/gpt2/PROVENANCE_gpt2.json").read_text(encoding="utf-8"))
    rec = next(f for f in prov["files"] if f["file"] == "model.safetensors")
    assert sha256_of_file() == rec["sha256"], "the bytes on disk are not the bytes that were sealed"
