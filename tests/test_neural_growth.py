import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.neural_growth import NeuralGrowth

def make(tmp_path, **over):
    import os
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from organs.code_assembler import CodeAssembler
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    from organs.tokenizer import TokenizerOrgan
    from world.reasoning_agent import ReasoningAgent
    cfg = {"model": {"api_key": None, "provider": "zai"},
           "language": {"state_path": str(tmp_path / "lang.json"),
                        "auto_train": False},
           "connectome": {"project_root": str(tmp_path)},
           "sandbox": {"project_root": str(tmp_path)}}
    a = ReasoningAgent(
        {"code_assembler": CodeAssembler(), "filesystem": None,
         "terminal": TerminalOrgan(timeout_s=5), "memory": MemoryOrgan()},
        state_path=tmp_path / "state.json", config=cfg)
    tok = TokenizerOrgan()
    a.language.tokenizer = tok
    growth = NeuralGrowth(a, interval=60.0, save_interval=300.0,
                          brain_path=tmp_path / "banc_brain.npz", **over)
    return a, growth, tok

def test_growth_tick_replays_words_and_changes_synapses(tmp_path):
    a, growth, tok = make(tmp_path)
    a.language.teach_word("verify", "verify the result and check it", source="test")
    a.language.teach_word("stale", "the stale value is older than its source", source="test")
    core = a.engine.static
    before = core.w.copy()
    rec = growth.growth_tick()
    assert rec["status"] == "ok" and rec["replayed"] == 2
    assert rec["synapses_changed"] > 0, \
        "consolidation replay must leave real synaptic deltas"
    assert not np.array_equal(core.w, before)
    st = growth.growth_stats()
    assert st["graph_loaded"] and st["growth_ticks"] == 1
    assert st["changed_from_birth"] > 0, "the brain differs from its birth state"

def test_brain_persists_and_loads_into_a_fresh_process(tmp_path):
    a, growth, _ = make(tmp_path)
    for w in ("verify", "stale", "budget"):
        a.language.teach_word(w, f"the word {w} in use right now", source="test")
    growth.growth_tick()
    saved = growth.save_brain()
    assert saved["saved"] is True and saved["changed_from_birth"] > 0
    weights = a.engine.static.w.copy()
    reborn = NeuralGrowth(a, brain_path=tmp_path / "banc_brain.npz")
    r = reborn.load_brain()
    assert r["loaded"] is True and r["changed_from_birth"] == \
        saved["changed_from_birth"]
    assert np.array_equal(a.engine.static.w, weights), \
        "the grown synapses came back exactly"

def test_a_brain_from_a_different_carve_is_refused(tmp_path):
    """The control condition must never donate weights to the experimental brain.

    Degree-matched random wiring keeps the SAME neurons and the SAME plastic
    pairs, so this is invisible to geometry: it takes the provenance stamp.
    """
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    a, growth, _ = make(tmp_path)
    control = HybridEngine(build_core_graph(control=True))
    bad = control.save_brain(tmp_path / "alien.npz")
    assert bad["saved"] is True
    r = growth.load_brain_from(bad["path"])
    assert r["loaded"] is False and "condition" in r["reason"], r


def test_a_pruned_brain_is_adopted_on_restart(tmp_path):
    """A life that pruned synapses must still come back.

    Consolidation removes dead synapses, so a lived brain is SMALLER than a fresh
    carve. The loader used to accept only "identical" or "grew beyond", which
    meant every restart answered "different carve geometry" and began life again
    from birth -- all learning discarded, silently, on a healthy file. Adoption
    is now by (pre, post) identity, so grown AND pruned geometries both load.
    """
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    a, growth, _ = make(tmp_path)
    core = a.engine.static
    base = len(core.g.plastic_w0)
    core.w[:25] = 0.0                      # 25 synapses gone dead
    removed = core.prune_plastic(threshold=0.004)
    assert removed >= 25 and len(core.w) == base - removed
    lived = core.w.copy()
    saved = growth.save_brain()
    assert saved["saved"] is True and saved["synapses"] == base - removed

    fresh = HybridEngine(build_core_graph())
    assert len(fresh.static.w) == base, "a fresh carve is full size"
    r = fresh.load_brain(saved["path"])
    assert r["loaded"] is True, r
    assert r["synapses"] == base - removed
    assert np.array_equal(fresh.static.w, lived), "the lived weights came back"
    adopted = r.get("adopted_geometry") or {}
    assert adopted.get("pruned_since_birth") == removed, adopted
    assert adopted.get("shared_with_birth") == base - removed, adopted


def test_adopting_a_brain_does_not_reshape_other_engines(tmp_path):
    """The carve is shared process-wide; the plastic layer is not."""
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine
    a, growth, _ = make(tmp_path)
    base = len(a.engine.static.w)
    other = HybridEngine(build_core_graph())
    a.engine.static.w[:25] = 0.0
    removed = a.engine.static.prune_plastic(threshold=0.004)
    assert len(a.engine.static.w) == base - removed
    assert len(other.static.w) == base, "another engine kept its own shape"

def test_homeostasis_keeps_mean_weight_sane(tmp_path):
    a, growth, _ = make(tmp_path)
    core = a.engine.static
    core.w[core._plastic_active] *= 25.0
    growth.growth_tick()
    active = core._plastic_active
    mean_w = float(np.mean(np.abs(core.w[active])))
    assert 0.1 < mean_w <= 2.0, f"scaling failed: mean |w| = {mean_w}"
    assert np.all(core.w[core._w_sign > 0] >= 0.0)
    assert np.all(core.w[core._w_sign < 0] <= 0.0), "sign is a hard constraint"

def test_speak_is_a_readout_of_learned_synapses(tmp_path):
    a, growth, tok = make(tmp_path)
    core = a.engine.static
    core.p.epsilon = 0.0
    nl = a.language
    rec = nl.teach_word("verify", "verify the result and check it", source="test")
    code = tok.encode("verify: check it")
    for _ in range(8):
        nl.engine.decide(code)
        nl.engine.teach(0.6)
    sp = nl.speak("verify: check it")
    assert sp["spoken"] is True, sp
    assert sp["words"] == ["verify"], \
        "the only learned pattern is the one on the pool the brain chose"
    assert sp["pool"] == rec["pool"], \
        "the WTA landed where the lived-in word actually lives"

def test_speak_before_any_thing_learned_is_silence(tmp_path):
    a, growth, _ = make(tmp_path)
    sp = a.language.speak("anything")
    assert sp["spoken"] is False, \
        "no patterns, no pool owners: the connectome stays SILENT"

def test_the_house_exposes_growth_and_speak(tmp_path):
    import os
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from world.connectome_house import ConnectomeHouse
    a, growth, tok = make(tmp_path)
    a.heartbeat = None
    house = ConnectomeHouse(a, a.config, port=0,
                            config_path=tmp_path / "hybrid_config.json")
    code, g = house.route_get("/api/neural/growth")
    assert code == 200 and g["present"] is True
    assert g["growth"]["plastic_synapses"] == 2983
    assert "pool_weight_share" in g["growth"]
    code, sp = house.route_get("/api/language/speak")
    assert code == 200 and "spoken" in sp
    organs = house.get_organs_state()
    assert organs["neural_growth"]["present"] is True