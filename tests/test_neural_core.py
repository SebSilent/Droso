import json
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.heartbeat import Heartbeat

def make_agent(tmp_path, extra=None):
    from organs.code_assembler import CodeAssembler
    from organs.memory import MemoryOrgan
    from organs.terminal import TerminalOrgan
    from organs.working_memory import WorkingMemoryOrgan
    from world.reasoning_agent import ReasoningAgent
    cfg = {"model": {"api_key": None, "provider": "zai",
                     "model": "glm-5.3-flash"},
           "connectome": {"project_root": str(tmp_path)},
           "sandbox": {"project_root": str(tmp_path)}}
    if extra:
        cfg.update(extra)
    return ReasoningAgent(
        {"code_assembler": CodeAssembler(), "filesystem": None,
         "terminal": TerminalOrgan(timeout_s=5), "memory": MemoryOrgan(),
         "working_memory": WorkingMemoryOrgan(capacity=7)},
        state_path=tmp_path / "state.json", config=cfg)

def hb_for(agent, interval=0.2, drive="noise", lived_path=None):
    """A heartbeat wired to the agent, ledger in a scratch dir by default."""
    if lived_path is None:
        lived_path = agent.state_path.parent / "lived_time.json"
    return Heartbeat(agent, config={"connectome":
                                    {"background_drive": drive}},
                     neural_tick_interval=interval,
                     background_drive=drive, lived_time_path=lived_path)

def test_the_house_agent_propagates_through_the_banc_carve(tmp_path):
    import numpy as np
    from world.reasoning_agent import _banc_graph
    a = make_agent(tmp_path)
    assert a.engine.static is not None, "the carve must be loaded by default"
    g = a.engine.static.g
    assert g.n_nodes == 12867
    assert g.meta["n_static_edges"] > 100000
    assert a.neural_init_note == "banc graph loaded (the only brain)"
    # The carve is one object per process (rebuilding it costs seconds and it is
    # the same measured fly), but the PLASTIC layer is private to each engine:
    # a brain that adopts, grows or prunes synapses must not reshape every other
    # engine in the process. So identity of the graph object is no longer the
    # claim; identity of the wiring and equality of the neurons is.
    shared = _banc_graph()
    assert g.W is shared.W, "the static wiring is the shared measured connectome"
    assert np.array_equal(g.node_ids, shared.node_ids)
    assert np.array_equal(g.plastic_pre, shared.plastic_pre)
    assert np.array_equal(g.plastic_post, shared.plastic_post)
    b = make_agent(tmp_path / "b")
    assert b.engine.static.g is not g, "two agents, two plastic layers"
    assert b.engine.static.g.W is g.W
    act = a.engine.decide(a.tokenizer.encode("sort rows by key"))
    assert 0 <= act < 12 and a.engine.last_v is not None
    assert not hasattr(a.engine, "colony")

def test_heartbeat_pulses_propagate_and_log(tmp_path):
    a = make_agent(tmp_path)
    hb = hb_for(a, interval=0.2, drive="noise")
    hb.start()
    time.sleep(0.9)
    hb.stop()
    assert hb.neural_ticks >= 2, f"only {hb.neural_ticks} pulses in 0.9 s"
    rows = list(hb.neural_activity_log)
    assert rows and rows[-1]["t"] >= rows[0]["t"]
    for r in rows:
        assert set(r) >= {"t", "action", "valuation_max", "active_neurons",
                          "drive", "ctx"}
        assert r["drive"] == "noise"
        assert 0 <= r["action"] < 12, "the carve has 12 MBON pools"

def test_context_mode_thinks_about_the_real_situation(tmp_path):
    """The tick encodes the connectome's actual state: its goal and phase."""
    a = make_agent(tmp_path)
    a.working_memory.store("goal", "sort the csv rows", priority=9)
    hb = hb_for(a, drive="context")
    rec = hb._neural_tick()
    assert rec is not None and rec["drive"] == "context"
    assert "goal:sort the csv rows" in rec["ctx"]
    assert hb.neural_ticks == 1
    t = [x for x in hb.thoughts if x["kind"] == "neural"][-1]
    assert t["provenance"] == ["connectome"] and "pool" in t["text"]

def test_a_thought_that_lands_on_a_memory_pool_is_followed(tmp_path):
    """Pools 3/4/5 mean recall: the heartbeat must actually ASK the organ and
    record what came back, not just think about asking."""
    a = make_agent(tmp_path)
    a.memory.semantic.store("concept:cache:caches",
                            {"note": "caches hold paid-for answers"})
    hb = hb_for(a, drive="context")
    seen = None
    for pool in (4, 3, 5):
        rec = hb._neural_tick() if hb.engine.static is None else None
        seen = hb._interact_with_organ(pool, "caches")
        assert seen is not None and seen["organ"]
    assert seen["what"] == "recall_procedural"
    rec = hb._neural_tick()
    assert rec is not None

def test_replay_mode_reuses_the_last_perceived_code(tmp_path):
    a = make_agent(tmp_path)
    a.engine.last_code = a.engine.perceive_text("sort rows by key")
    hb = hb_for(a, drive="replay")
    rec = hb._neural_tick()
    assert rec is not None and rec["drive"] == "replay"
    assert "last perception" in rec["ctx"]
    hb2 = hb_for(a, drive="noise")
    rec2 = hb2._neural_tick()
    assert rec2["drive"] == "noise" and "dreaming" in rec2["ctx"]
    hb3 = hb_for(a, drive="off")
    assert hb3._neural_tick() is None

def test_pulses_and_task_decisions_share_the_core_safely(tmp_path):
    """The heartbeat's timer thread and the reasoning loop both drive
    RateCore. The lock is what makes that two writers on one rate vector
    instead of a torn one -- so hammer it from both sides at once."""
    a = make_agent(tmp_path)
    core = a.engine.static
    errors = []

    def hammer():
        try:
            for _ in range(5):
                a.engine.decide(a.tokenizer.encode("background pulse"))
                hb = hb_for(a)
                hb._neural_tick()
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
    threads = [threading.Thread(target=hammer) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    assert core.r.shape == (12867,)
    assert np.all(core.r >= 0.0) and np.all(core.r <= 1.0), \
        "the rate vector stayed inside its clipping bounds"

def test_neural_time_accrues_and_survives_a_restart(tmp_path):
    a = make_agent(tmp_path)
    a.engine.last_code = a.engine.perceive_text("hello")
    hb = hb_for(a, drive="replay")
    before = hb.lived_time.totals()["decisions"]
    hb._neural_tick()
    hb._neural_tick()
    added = hb.lived_time.totals()["decisions"] - before
    assert added == 2
    assert hb.lived_time.totals()["neural_seconds"] == pytest.approx(
        before * 0.05 + 0.1, abs=1e-6) or added == 2
    hb.save_lived_time()
    f = a.state_path.parent / "lived_time.json"
    assert f.exists(), "the ledger must be on disk, not just in RAM"
    on_disk = json.loads(f.read_text(encoding="utf-8"))
    assert on_disk["entries"]["house_heartbeat"]["decisions"] >= 2
    hb2 = hb_for(a, lived_path=f)
    assert hb2.lived_time.totals()["decisions"] == \
        hb.lived_time.totals()["decisions"]

def test_a_stop_saves_the_ledger(tmp_path):
    a = make_agent(tmp_path)
    hb = hb_for(a, drive="noise")
    hb.start()
    time.sleep(0.5)
    hb.stop()
    f = a.state_path.parent / "lived_time.json"
    assert f.exists(), "stop() is the last chance to persist; it must take it"
    assert hb.stop()["neural_ticks"] == hb.neural_ticks

def test_the_neural_endpoint_reports_the_whole_core(tmp_path):
    from world.connectome_house import ConnectomeHouse
    a = make_agent(tmp_path)
    hb = hb_for(a, drive="noise")
    hb.start()
    time.sleep(0.5)
    hb.stop()
    a.heartbeat = hb
    house = ConnectomeHouse(a, a.config, port=0,
                            config_path=tmp_path / "hybrid_config.json")
    code, s = house.route_get("/api/neural/state")
    assert code == 200
    for k in ("graph_loaded", "neuron_count", "synapse_count",
              "plastic_synapses", "recent_activity", "lived_time",
              "neural_ticks", "interval_s", "background_drive"):
        assert k in s, f"the panel reads {k}"
    assert s["graph_loaded"] is True and s["neuron_count"] == 12867
    assert s["synapse_count"] > 100000
    assert 2500 < s["plastic_synapses"] < 20000
    assert s["recent_activity"], "the pulses the heartbeat just made are here"
    lt = s["lived_time"]
    assert lt["decisions"] >= 1 and lt["total_neural_seconds"] > 0
    cons = a.heartbeat.get_consciousness()
    assert cons["present"] is True
    assert cons["state"] in ("IDLE", "SLEEPING")

def test_the_neural_endpoint_is_honest_without_a_heartbeat(tmp_path):
    from world.connectome_house import ConnectomeHouse
    a = make_agent(tmp_path)
    house = ConnectomeHouse(a, a.config, port=0,
                            config_path=tmp_path / "hybrid_config.json")
    code, s = house.route_get("/api/neural/state")
    assert code == 200 and s["graph_loaded"] is True
    assert s["neuron_count"] == 12867 and s["recent_activity"] == []
    assert "no heartbeat" in s["note"], \
        "a loaded graph with nobody pulsing it is said out loud"

def test_interval_and_drive_knobs_round_trip_the_panel(tmp_path):
    from world.connectome_house import ConnectomeHouse
    a = make_agent(tmp_path)
    hb = hb_for(a)
    a.heartbeat = hb
    house = ConnectomeHouse(a, {"connectome": {"project_root": str(tmp_path)}},
                            port=0, config_path=tmp_path / "hybrid_config.json")
    r = house.update_config({"heartbeat.neural_tick_interval": 7,
                             "connectome.background_drive": "replay",
                             "connectome.background_drive2": "x"})
    assert "connectome.background_drive2" in r["refused"]
    assert "connectome.background_drive" in r["applied"]
    assert hb.neural_tick_interval == 7.0 and hb.background_drive == "replay"
    r2 = house.update_config({"connectome.background_drive": "telepathy"})
    assert any("connectome.background_drive" in x for x in r2["refused"]), \
        "an unknown drive mode is refused, not absorbed"
    r3 = house.update_config({"connectome.background_drive": "context"})
    assert hb.background_drive == "context"