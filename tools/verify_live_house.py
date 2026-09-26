#!/usr/bin/env python3
"""Verify the live house: accelerated life, state badge, growth, speak."""
import json
import sys
import time
import urllib.request

sys.path.insert(0, "C:/Projects/HybridLLM")
PORT = 7773

def get(p, tries=5):
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{p}", timeout=30) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            time.sleep(2)
    raise last

wait_for = int(sys.argv[1]) if len(sys.argv) > 1 else 10
for _ in range(40):
    try:
        get("/api/state")
        break
    except Exception:
        time.sleep(1)
time.sleep(wait_for)

g = get("/api/neural/growth")["growth"]
print("ACCELERATED LIFE :", g.get("accelerated"),
      "| decisions", g.get("accel_decisions"),
      "| per s", g.get("accel_decisions_per_s"),
      "| ACCELERATION x", g.get("acceleration_x"))
st = get("/api/state")
print("badge            :", st["mental"]["heartbeat"]["state"],
      "| activity:", st["mental"]["activity"])
ns = get("/api/neural/state")
print("lived neural time:", round(ns["lived_time"]["total_neural_seconds"], 1),
      "s | neuron-update events",
      f"{ns['lived_time']['neuron_update_events']:.2e}")
sp = get("/api/language/speak")
print("SPEAK            :", sp.get("utterance"), "| overlaps",
      sp.get("overlaps"))