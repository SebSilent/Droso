#!/usr/bin/env python3
import os
import sys
import time
import threading

os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np

def hr(title):
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")

hr("1. THE SHIPPED HOUSE AGENT'S ENGINE (world/reasoning_agent.py:64)")
from world.reasoning_agent import ReasoningAgent
from organs.code_assembler import CodeAssembler
from organs.memory import MemoryOrgan
from organs.terminal import TerminalOrgan
from organs.filesystem import FilesystemOrgan
import tempfile

tp = tempfile.mkdtemp()
agent = ReasoningAgent(
    {"code_assembler": CodeAssembler(),
     "filesystem": FilesystemOrgan(os.path.join(tp, "sb")),
     "terminal": TerminalOrgan(timeout_s=10), "memory": MemoryOrgan()},
    state_path=os.path.join(tp, "state.json"),
    config={"model": {"api_key": None, "provider": "zai"},
            "connectome": {"project_root": tp, "max_context_tokens": 400},
            "sandbox": {"project_root": tp}})
eng = agent.engine
print(f"engine type            : {type(eng).__name__}")
print(f"brain                  : the carved BANC connectome (RateCore), "
      f"loaded={eng.static is not None}")
print(f"neurons / synapses     : {eng.static.g.n_nodes} / "
      f"{eng.static.g.meta['n_static_edges']}")
print(f"plastic KC->MBON       : {eng.static.g.meta['n_plastic_edges']} "
      f"(three-factor dopamine rule)")
print(f"compartments (actions) : {len(eng.static.g.mbon_pools)} real MBON pools "
      f"over {len(eng.static.g.mbon_idx)} measured MBONs")
print(f"colony (BANNED toy)    : {hasattr(eng, 'colony')} -- removed; "
      f"the carve is the only substrate")

code = agent.tokenizer.encode("phase:plan wm[goal] attempts1 sort rows")
nz = int((code > 0).sum())
act = eng.decide(code)
probs = eng.last_probs
print(f"\na decision, live:")
print(f"  code in   : {code.shape[0]} KC cells, {nz} active (k-of-n sparse)")
print(f"  action out: MBON pool {act}")
print(f"  softmax   : top3 {np.argsort(-eng.last_probs)[:3].tolist()} "
      f"p={np.sort(eng.last_probs)[::-1][:3].round(3).tolist()}")
print(f"  teach()   : rpe={eng.teach(1.0):.4f} (dopamine broadcast -> plasticity)")

hr("2. THE CARVED GRAPH (connectome/substrate.py -> RateCore.decide)")
t0 = time.perf_counter()
from connectome.substrate import build_core_graph
g = build_core_graph()
print(f"build_core_graph()     : {time.perf_counter() - t0:.2f}s "
      f"(parquet cache .cache/union_edges.parquet)")
m = g.meta
print(f"neurons                : {g.n_nodes:,}")
print(f"static signed edges    : {m['n_static_edges']:,}  "
      f"(W is scipy CSR, W[post,pre], row-L1-normalised x{m['row_gain']})")
print(f"plastic KC->MBON edges : {m['n_plastic_edges']:,} (three-factor)")
print(f"modulatory excluded    : {m['n_modulatory_edges_excluded_from_fast_graph']:,}")
print(f"role counts            : {m['role_counts']}")
print(f"graph format on disk   : BANC v888 CSV.gz (connectome/data/*.csv.gz) "
      f"-> parquet cache; root IDs are int64")

from connectome.rate_core import RateCore
rc = RateCore(g, dopamine=True)
print(f"\nRateCore: r shape={rc.r.shape}, sub_steps={rc.p.sub_steps}, "
      f"leak={rc.p.leak}, dt=5ms/sub-step -> {rc.p.sub_steps * 5} ms/decision")

from connectome.engine import text_code
code = text_code("the cache holds what was already paid for", n_kc=3840, k=16)
kc_of_code = g.kc_idx[:3840]
nz = np.nonzero(code)[0]
drive = [(kc_of_code[nz], code[nz].astype(float))]

before = rc.r.copy()
t0 = time.perf_counter()
action, v = rc.decide(drive)
dt_ms = (time.perf_counter() - t0) * 1000
touched = int((rc.r != before).sum())
active = int((rc.r > 0.01).sum())
print(f"\none decide(): {dt_ms:.1f} ms wall for 50 ms neural time")
print(f"  neurons whose rate moved : {touched:,} / {g.n_nodes:,}")
print(f"  neurons above 0.01       : {active:,}")
print(f"  action (MBON pool)       : {action}")
print(f"  valuation v[:6]          : {np.round(v[:6], 4).tolist()}")
mbon_r = rc.r[g.mbon_idx]
print(f"  MBON rates: max={mbon_r.max():.4f}, mean={mbon_r.mean():.5f}, "
      f"active={(mbon_r > 0.01).sum()}/{len(g.mbon_idx)}")
w_before = rc.w.copy()
rpe = rc.reinforce(reward=1.0, v_chosen=float(v[action]), v_next_max=0.0)
delta = int((rc.w != w_before).sum())
print(f"  reinforce(): rpe={rpe:.4f}, plastic synapses changed: {delta:,} "
      f"of {len(rc.w):,}")

hr("3. CONTINUOUS OPERATION: the heartbeat pulses the core")
from organs.heartbeat import Heartbeat
from pathlib import Path

print(f"graph loaded in the house agent : {agent.engine.static is not None} "
      f"({agent.neural_init_note})")
hb = Heartbeat.from_config(
    agent, {"heartbeat": {"neural_tick_interval": 0.2},
            "connectome": {"background_drive": "replay",
                           "lived_time_save_interval": 60}})
agent.engine.perceive_text("the connectome is awake between your requests")
hb.start()
t_start = time.perf_counter()
time.sleep(1.2)
hb.stop()
elapsed = time.perf_counter() - t_start
print(f"heartbeat ran {elapsed:.1f} s at {hb.neural_tick_interval}s cadence")
print(f"  neural pulses              : {hb.neural_ticks}")
print(f"  last pulse                 : {dict(hb.neural_activity_log[-1])}")
lt = hb.lived_time.totals()
print(f"  lived ledger               : {lt['decisions']} decisions = "
      f"{lt['neural_seconds']:.2f}s neural = "
      f"{lt['neuron_update_events']:.2e} neuron-update events")
f = Path(tp) / "lived_time.json"
print(f"  ledger on disk             : {f.exists()} ({f})")
hb2 = Heartbeat.from_config(agent,
                            {"heartbeat": {"neural_tick_interval": 0.2}})
print(f"  resumed after 'restart'    : "
      f"{hb2.lived_time.totals()['decisions'] == lt['decisions']} decisions")

from world.connectome_house import ConnectomeHouse
agent.heartbeat = hb
house = ConnectomeHouse(agent, {"connectome": {"project_root": tp}}, port=0,
                        config_path=Path(tp) / "hybrid_config.json")
_, ns = house.route_get("/api/neural/state")
print("\n  GET /api/neural/state ->")
for k in ("graph_loaded", "neuron_count", "synapse_count",
          "plastic_synapses", "neural_ticks", "interval_s",
          "background_drive"):
    print(f"    {k:22s}: {ns.get(k)}")
print(f"    lived_time             : {ns.get('lived_time')}")
print("\nVERDICT: the core propagates on task decisions AND on the heartbeat's")
print("own cadence -- always alive, at ~50 ms of neural time per pulse.")

hr("4. THE BRAIN GROWS: NeuralGrowth organ + neural readout (speech)")
from organs.neural_growth import NeuralGrowth
growth = NeuralGrowth(agent, interval=60.0, save_interval=300.0,
                      brain_path=Path(tp) / "banc_brain.npz")
lang = agent.language
lang.teach_word("verify", "verify the result and check that it stands", source="probe")
lang.teach_word("stale", "the stale value is older than its source", source="probe")
tick = growth.growth_tick()
print(f"consolidation tick           : replayed {tick['replayed']} word "
      f"pattern(s), {tick['synapses_changed']} synapse(s) changed")
saved = growth.save_brain()
print(f"brain persisted              : {saved['path']} "
      f"({saved['changed_from_birth']}/{saved['synapses']} synapses "
      f"changed from birth)")
gs = growth.growth_stats()
print(f"growth census                : strengthened {gs['strengthened']}, "
      f"weakened {gs['weakened']}, mean |w| {gs['mean_abs_weight']}")
sp = lang.speak("verify the stale cache")
print(f"SPEAK (neural readout)       : spoken={sp['spoken']} "
      f"words={sp.get('words')} overlaps={sp.get('overlaps')} "
      f"pool={sp.get('pool')}")