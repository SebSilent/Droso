"""Memory organ tests: episodic bound, semantic LRU, procedural automation."""

from __future__ import annotations

from organs.memory import EpisodicMemory, MemoryOrgan, ProceduralMemory, SemanticMemory

def test_episodic_capacity_and_recent():
    em = EpisodicMemory(capacity=5)
    for i in range(20):
        em.record(i, f"task {i}", ["file_read"], "success" if i % 2 else "failure",
                  1.0 if i % 2 else -0.6)
    assert len(em.episodes) == 5
    assert em.recent(2)[0]["tick"] == 18
    assert abs(em.success_rate() - 0.6) < 1e-9

def test_semantic_store_query_lru_eviction():
    sm = SemanticMemory(capacity=3)
    sm.store("a", 1, source="t")
    sm.store("b", 2, source="t")
    sm.query("a")
    sm.store("c", 3, source="t")
    sm.store("d", 4, source="t")
    assert sm.query("a") is not None
    assert sm.query("b") is None
    hits = sm.search("value")
    assert len(hits) <= 3

def test_semantic_confidence_updates():
    sm = SemanticMemory()
    sm.store("pytest", "test runner", 0.5, "user")
    sm.store("pytest", "test runner v9", 0.9, "probe")
    fact = sm.query("pytest")
    assert fact["value"] == "test runner v9" and fact["confidence"] == 0.9

def test_procedural_record_match_and_floor():
    pm = ProceduralMemory()
    for _ in range(4):
        pm.record("run pytest and report the output", [0, 10], True)
    pm.record("write a haiku", [6], False)
    match = pm.match("please run pytest and report the output now")
    assert match is not None and match["action_sequence"] == [0, 10]
    assert pm.match("write a haiku about flies") is None

def test_memory_organ_save_load(tmp_path):
    path = tmp_path / "mem.json"
    mo = MemoryOrgan({"episodic_capacity": 10, "semantic_capacity": 10,
                      "procedural_capacity": 10}, persist_path=str(path))
    mo.note_episode(0, "read the file", ["file_read", "submit"], "success", 2.7)
    mo.semantic.store("fly", "an insect", 1.0, "seed")
    mo.procedural.record("read the file", [1, 10], True)
    mo.save()
    mo2 = MemoryOrgan(persist_path=str(path))
    assert mo2.episodic.recent(1)[0]["reward"] == 2.7
    assert mo2.semantic.query("fly")["value"] == "an insect"
    assert mo2.procedural.match("read the file") is not None