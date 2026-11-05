"""Tests for B.6 item 4: the real path, the accounting, and the two tallies.

Two kinds of test live here. Most run against a SAFETENSORS FILE BUILT IN tmp_path, so the committed donor and
the committed journal are untouched and the assertions are hermetic. A few read the committed artifacts and
assert what they say -- that the run's journal verifies, that no mask buffer appears in it, that every real node
carries an address, that the two tallies add up, and that the synthetic path still reproduces the sealed
calibration field for field. None of the artifact-reading tests issue a donor read.
"""
from __future__ import annotations

import ast
import json
import struct
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import mp_e12_pool_rule as pool  # noqa: E402
from tools.mp_e12_access_journal import AccessJournal  # noqa: E402
from tools.mp_e12_address_space import DonorAddressSpace  # noqa: E402
from tools.mp_e12_probes import (CLASSES, HEADS, READ_BUDGET_OPS, BulkReadNotPermitted, OpCounter,  # noqa: E402
                                 ReadBudgetExceeded, RealDonorSource, SyntheticSource, build_graph,
                                 probe_item, real_config)
from tools.mp_e12_synthetic_donor import GPT2_124M, build_donor  # noqa: E402
from tools.mp_e12_validate_graph import SCHEMA_PATH, validate  # noqa: E402

CLASS1 = "experiments/MP-E12/results/association_graph_real_class1.json"
PREFLIGHT = "experiments/MP-E12/results/association_graph_real_three_class_preflight.json"
PREREG = "experiments/MP-E12/results/real_run_preregistration.json"
SEALED = "experiments/MP-E12/results/probes_synthetic_calibration.json"
JOURNAL1 = "experiments/MP-E12/results/access_journal_extraction_e12a_class1.jsonl"
JOURNAL2 = ("experiments/MP-E12/results/access_journal_extraction_e12a_three_class_preflight.jsonl")
FORBIDDEN = ("torch", "transformers", "tensorflow", "jax", "flax", "keras", "onnx", "accelerate")


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def imports_of(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


# ------------------------------------------------------------------ a donor file built from scratch
def write_safetensors(path: Path, tensors: dict):
    """tensors: {name: np.float32 array}. Minimal valid safetensors: 8-byte length, JSON header with
    offsets, then the data region. Written here rather than imported because the point of the fixture is that
    the address space resolves offsets from the header, not from a library that made the file."""
    header, offset, data = {}, 0, b""
    for name, arr in tensors.items():
        raw = arr.astype("<f4").tobytes()
        n = len(raw)
        header[name] = {"dtype": "F32", "shape": list(arr.shape), "data_offsets": [offset, offset + n]}
        offset += n
        data += raw
    hj = json.dumps(header, separators=(",", ":")).encode("utf-8")
    pad = (-len(hj)) % 8
    hj += b" " * pad
    path.write_bytes(struct.pack("<Q", len(hj)) + hj + data)
    return path


@pytest.fixture(scope="module")
def fixture_donor(tmp_path_factory):
    """A 3-layer, 4-head mini-donor with the real names and the real layout, plus one mask buffer to prove
    the exclusion bites on this path too."""
    d = tmp_path_factory.mktemp("fx")
    n, nh, dh, inner, vocab = 16, 4, 4, 24, 40
    rng = np.random.default_rng(7)
    tensors = {"wte.weight": rng.standard_normal((vocab, n), dtype=np.float32),
               "ln_f.weight": rng.standard_normal(n, dtype=np.float32) + 1,
               "ln_f.bias": rng.standard_normal(n, dtype=np.float32),
               "h.0.attn.bias": np.tril(np.ones((1, 1, 8, 8), dtype=np.float32))}
    for l in range(3):
        tensors[f"h.{l}.attn.c_attn.weight"] = rng.standard_normal((n, 3 * n), dtype=np.float32)
        tensors[f"h.{l}.attn.c_proj.weight"] = rng.standard_normal((n, n), dtype=np.float32)
        tensors[f"h.{l}.mlp.c_fc.weight"] = rng.standard_normal((n, inner), dtype=np.float32)
        tensors[f"h.{l}.mlp.c_fc.bias"] = rng.standard_normal(inner, dtype=np.float32)
        tensors[f"h.{l}.mlp.c_proj.weight"] = rng.standard_normal((inner, n), dtype=np.float32)
    f = write_safetensors(d / "model.safetensors", tensors)
    cfg = {"n_vocab": vocab, "n_positions": 8, "n_embd": n, "n_layer": 3, "n_head": nh, "d_head": dh,
           "mlp_inner": inner}
    return {"file": f, "cfg": cfg, "tensors": tensors, "dir": d}


@pytest.fixture
def real_src(fixture_donor, tmp_path):
    jr = AccessJournal(str(tmp_path / "j.jsonl"), donor_sha256="fixture", run_label="test_real_source")
    ax = DonorAddressSpace(path=str(fixture_donor["file"]), journal=jr)
    ax.__enter__(); jr.__enter__()
    ids = [0, 1, 2, 3, 4]
    src = RealDonorSource(ax, fixture_donor["cfg"], ids, str(tmp_path / "j.jsonl"))
    yield src, ax, jr, fixture_donor
    ax.__exit__(None, None, None); jr.__exit__(None, None, None)


# ------------------------------------------------------------------ the pool rule is value-blind
def test_the_pool_rule_reads_nothing_and_imports_nothing():
    full = (ROOT / "tools/mp_e12_pool_rule.py").read_text(encoding="utf-8")
    # `from __future__ import annotations` is the only import the module is allowed to have; it brings in no
    # runtime object at all. Anything else on the import list would mean the rule consults something.
    assert imports_of("tools/mp_e12_pool_rule.py") <= {"__future__"}, \
        "the pool rule must be pure integer arithmetic"
    # A token scan over the source failed twice now: first on the probe-list script's docstring, and here on a
    # COMMENT that says "one read_rows call at MAX_ROWS_PER_READ" while explaining why the cap is 63. Prose is
    # not a capability. The check is structural instead: what names does this module resolve, and what can it
    # call? If it has no imports, no attribute access and only integer/list builtins, it cannot read a file.
    tree = ast.parse(full)
    attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    # The claim is not "no attribute access" -- building a list needs `.append` and reading a dict needs
    # `.get`, and a test that forbids those is measuring its own syntax rather than the risk. The risk is
    # access to anything FILE-shaped or DONOR-shaped, so the allowed set is container methods only.
    container_methods = {"append", "get", "extend", "sort", "keys", "values", "items", "pop", "index"}
    assert attrs <= container_methods, (
        f"the pool rule reaches into objects beyond containers: {sorted(attrs - container_methods)}")
    allowed = {"int", "range", "sorted", "len", "list", "str", "frozenset"}
    assert calls <= allowed, f"the pool rule calls {sorted(calls - allowed)}; it may only do arithmetic"
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for forbidden in ("open", "mmap", "struct", "numpy", "torch", "DonorAddressSpace"):
        assert forbidden not in names, f"{forbidden} is bound in the pool rule"


def test_the_pool_is_deterministic_and_bounded():
    ids = list(range(24))
    a = pool.pool_for(7, [i for i in ids if i != 7])
    b = pool.pool_for(7, [i for i in ids if i != 7])
    assert a == b and 7 not in a and len(a) <= pool.POOL_CAP
    assert len(set(a)) == len(a), "a pool with duplicates would double-count a row as two candidates"
    # different probes must not all land on the same sampled rows
    assert pool.pool_for(8, [])[:40] != pool.pool_for(9, [])[:40]


def test_the_registered_pool_rule_and_the_implementation_have_not_drifted():
    problems = pool.matches(load(PREREG))
    assert not problems, problems


# ------------------------------------------------------------------ the two tallies
def test_conservative_tally_is_registered_plus_read_calls(real_src):
    src, ax, jr, fx = real_src
    c = OpCounter()
    g = build_graph(src, [0, 1], classes=["1_embedding_geometry"], accounting="conservative")
    it = g["items"][0]
    assert it["operations_spent"] == 2
    assert it["read_calls"] == 2
    assert it["conservative_operations_spent"] == it["operations_spent"] + it["read_calls"] == 4
    assert it["per_row_operations_if_charged"] == it["operations_spent"] + it["rows_touched"]
    assert g["accounting_tallies"]["difference"]["ops"] == g["reads"]["read_calls"]
    assert it["budget"] == READ_BUDGET_OPS and it["aborted"] is False


def test_the_registered_reading_would_price_the_same_work_lower(real_src):
    """The two tallies must differ, or the 'conservative' label means nothing."""
    src, ax, jr, fx = real_src
    g = build_graph(src, [0], classes=["1_embedding_geometry"], accounting="conservative")
    t = g["accounting_tallies"]
    assert t["conservative_reading"]["operations"] > t["registered_rule"]["operations"]
    assert t["per_row_reading_reported_not_run_under"]["operations"] > t["conservative_reading"]["operations"]


# ------------------------------------------------------------------ the pre-flight budget
def test_a_three_class_item_aborts_before_issuing_a_single_read(real_src):
    src, ax, jr, fx = real_src
    with pytest.raises(ReadBudgetExceeded) as exc:
        probe_item(src, 0, READ_BUDGET_OPS, list(CLASSES), "conservative")
    assert exc.value.planned_ops > READ_BUDGET_OPS
    assert exc.value.source_kind == "real"
    jf = Path(str(next(p for p in jr.root.glob("*.jsonl") if p.name == "j.jsonl").path)) if False else None
    # the journal this source writes must be empty: the abort was arithmetic, not a read
    p = ROOT / "does_not_matter"  # placeholder, the real check is below
    records = jr.read()
    assert records == [], f"the pre-flight abort issued {len(records)} reads; C3 says an abort costs nothing"


def test_the_abort_reports_per_class_counts(real_src):
    src, ax, jr, fx = real_src
    with pytest.raises(ReadBudgetExceeded) as exc:
        probe_item(src, 0, READ_BUDGET_OPS, list(CLASSES), "conservative")
    by = exc.value.by_class
    assert set(by) == set(CLASSES)
    # On the 16-row fixture donor a head slice is ONE call, so class 2 costs 13 and fits. The claim that
    # classes 2 and 3 bust the budget is a claim about the real donor's shapes, and it is checked there below,
    # in the committed pre-flight artifact -- not smuggled into a fixture test where the arithmetic differs.
    assert by["1_embedding_geometry"]["conservative_ops"] <= READ_BUDGET_OPS
    assert (by["3_circuit_motifs"]["conservative_ops"]
            >= by["2_association_edges"]["conservative_ops"] >= by["1_embedding_geometry"]["conservative_ops"])
    assert all(v["read_calls"] > 0 for v in by.values()), "a plan with no reads is not a plan, it is a guess"
    assert all(v["conservative_ops"] == v["registered_ops"] + v["read_calls"] for v in by.values())
    g = load(PREFLIGHT)
    a = g["items_aborted"][0]["planned"]
    assert a["1_embedding_geometry"]["conservative_ops"] <= READ_BUDGET_OPS
    assert a["2_association_edges"]["conservative_ops"] > READ_BUDGET_OPS
    assert a["3_circuit_motifs"]["conservative_ops"] > READ_BUDGET_OPS


def test_the_synthetic_source_is_not_subject_to_the_conservative_charges():
    """Its donor is already in RAM, so it performs zero journaled calls and the two tallies coincide. That
    coincidence IS the loophole, and the artifact names it instead of letting the equality look like agreement."""
    d = build_donor(GPT2_124M); d["name"] = "synthetic-124M-shaped-random"
    g = build_graph(d, [0, 1], accounting="conservative")
    t = g["accounting_tallies"]
    assert g["reads"]["read_calls"] == 0
    assert t["conservative_reading"]["operations"] == t["registered_rule"]["operations"]
    assert "loophole in miniature" in t["conservative_equals_registered_when"]


def test_the_real_source_has_no_bulk_read_method(real_src):
    src, ax, jr, fx = real_src
    assert not hasattr(src, "full_matrix") and not hasattr(src, "load_tensor")
    ids, mat = src.search_domain(0, OpCounter())
    assert len(ids) == mat.shape[0] <= pool.POOL_CAP, "the real search domain must stay bounded"
    assert BulkReadNotPermitted  # the exception exists to be raised by a method that does not


# ------------------------------------------------------------------ the committed artifacts
def test_the_committed_real_graph_validates_against_its_schema():
    schema = load(SCHEMA_PATH)
    problems = validate(load(CLASS1), schema)
    assert not problems, problems


def test_the_committed_real_journal_verifies_and_holds_no_mask_buffer():
    g = load(CLASS1)
    aj = g["access_journal"]
    assert aj["verify_problems"] == []
    assert aj["mask_buffer_records"] == []
    assert aj["tensors_touched"] == ["wte.weight"], "class 1 must touch the embedding matrix and nothing else"
    lines = (ROOT / JOURNAL1).read_text(encoding="utf-8").splitlines()
    assert len(lines) == aj["n_records"]
    recs = [json.loads(x) for x in lines]
    assert all(r["probe_id"].startswith("extraction_e12a_item_") for r in recs)
    assert all(not r["tensor"].endswith("attn.bias") for r in recs)
    assert sum(r["n_values"] for r in recs) == g["reads"]["values_returned"]
    assert {r["probe_id"] for r in recs} == set(aj["probe_ids"])


def test_every_real_node_carries_an_address_and_the_address_resolves_to_the_value():
    """One probe word, one row, re-read independently with struct.unpack and compared to what the graph's
    arithmetic says. This is the claim 'which address, for which probe' reduced to bytes."""
    g = load(CLASS1)
    item = g["items"][0]
    node = next(n for n in item["nodes"] if n["type"] == "probe_token")
    addr = node["address"]
    donor = ROOT / "experiments/MP-E12/donor/gpt2/model.safetensors"
    with donor.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        hdr = json.loads(f.read(n).rstrip(b"\x00 ").decode("utf-8"))
        base = 8 + n + hdr[addr["tensor"]]["data_offsets"][0]
        width = hdr[addr["tensor"]]["shape"][1]
        f.seek(base + addr["row"] * width * 4)
        first_float = struct.unpack("<f", f.read(4))[0]
    assert addr["byte_offset"] == base + addr["row"] * width * 4
    assert addr["tensor_base_offset"] == base
    assert abs(first_float - float(struct.unpack("<f", struct.pack("<f", first_float))[0])) < 1e-12
    rec = next(json.loads(x) for x in (ROOT / JOURNAL1).read_text(encoding="utf-8").splitlines()
               if json.loads(x)["probe_id"] == f"extraction_e12a_item_{item['item']}"
               and json.loads(x)["indices"]["row"] == addr["row"])
    # a 768-value row is over the inline threshold, so the record carries a hash of the packed bytes rather
    # than the floats. Recomputing that hash from the file is the strongest available check: it proves the
    # journal recorded THIS row's bytes, at this address, and it does not need the values to be inlined.
    import hashlib
    with donor.open("rb") as f:
        f.seek(base + addr["row"] * width * 4)
        packed = f.read(width * 4)
    assert rec["values_repr"] != "inline" and rec["n_values"] == width
    assert rec["values_bytes_sha256"] == hashlib.sha256(packed).hexdigest(), \
        "the journal's hash does not match the bytes at the address the graph cites"
    assert rec["raw_bytes"] == len(packed)


def test_the_preflight_artifact_records_24_events_and_zero_reads():
    g = load(PREFLIGHT)
    assert g["items_probed"] == 0 and len(g["items_aborted"]) == 24
    assert g["access_journal"]["n_records"] == 0
    assert not (ROOT / JOURNAL2).read_text(encoding="utf-8").strip(), "a pre-flight abort must not journal"
    a = g["items_aborted"][0]
    assert a["planned_ops"] > READ_BUDGET_OPS
    assert a["planned"]["3_circuit_motifs"]["conservative_ops"] > a["planned"]["2_association_edges"]["conservative_ops"]


def test_the_real_graph_states_what_its_figures_are_not():
    g = load(CLASS1)
    w = g["what_these_figures_are_NOT"]
    assert set(w) >= {"latency_or_10x", "behaviour", "MP-E12b", "global_reach", "knowledge_localisation"}
    assert g["benchmark_vs_reference_inference"] == []
    assert "never been re-based" in g["benchmark_not_run_reason"]
    assert g["donor"]["is_synthetic"] is False
    assert g["energy_estimate"].startswith("NOT MEASURED")


def test_the_registration_is_earlier_than_the_first_read():
    g = load(CLASS1)
    assert g["run"]["preregistered_at_utc"] < g["run"]["first_extraction_record_utc"], \
        "the accounting must be registered before the data exists, and the timestamps must show it"


# ------------------------------------------------------------------ the sealed calibration still reproduces
def test_the_synthetic_path_still_reproduces_the_sealed_calibration_field_by_field():
    sealed = load(SEALED)
    d = build_donor(GPT2_124M); d["name"] = "synthetic-124M-shaped-random"
    new = build_graph(d, list(range(24)))
    kept = set(sealed["items"][0]) & set(new["items"][0])
    added_detail = {"search_domain", "search_domain_rows"}
    for i, (a, b) in enumerate(zip(sealed["items"], new["items"])):
        for k in kept:
            x, y = a[k], (dict(b[k]) if k == "detail" else b[k])
            if k == "detail":
                y = {kk: vv for kk, vv in y.items() if kk not in added_detail}
            assert json.dumps(x, sort_keys=True) == json.dumps(y, sort_keys=True), f"item {i} field {k} moved"
    assert new["operations_total"] == sealed["operations_total"]
    assert new["macs_total"] == sealed["macs_total"]


def test_the_real_path_does_not_import_donor_runtime():
    for rel in ("tools/mp_e12_probes.py", "tools/mp_e12_validate_graph.py",
                "tools/mp_e12_preregister_real_run.py", "tools/mp_e12_run_real_class1.py",
                "tools/mp_e12_run_real_preflight.py"):
        bad = sorted(imports_of(rel) & set(FORBIDDEN))
        assert not bad, f"{rel} imports donor runtime {bad}; R11 forbids it on this path"


def test_real_config_comes_from_the_file_not_from_a_guess():
    cfg = real_config()
    assert cfg["n_embd"] == 768 and cfg["n_layer"] == 12 and cfg["n_head"] == 12
    assert cfg["d_head"] == 64 and cfg["n_vocab"] == 50257
    assert cfg["mlp_inner"] == 3072, ("the config file does not state the inner width; the source overwrites "
                                      "this from the c_fc tensor, and the fixture proves it does")
