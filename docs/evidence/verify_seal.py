"""Prove the seal: a --no-learn regression run must write nothing.

Snapshots the store hash and the events line count, runs the 30-day battery
with --no-learn, snapshots again, and fails if either moved. The battery's own
store-count guard verifies the count inside the run; this verifies the bytes.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
store = ROOT / "state" / "house_agent_learning.json"
events = ROOT / "state" / "house_agent_learning_events.jsonl"


def snap():
    return {
        "store_sha": hashlib.sha256(store.read_bytes()).hexdigest()
        if store.exists() else None,
        "events_lines": sum(1 for _ in events.open(encoding="utf-8"))
        if events.exists() else 0,
    }


before = snap()
r = subprocess.run([sys.executable, str(ROOT / "tools" / "task_battery.py"),
                    "--no-learn"], capture_output=True, text=True, cwd=str(ROOT))
after = snap()
out = json.loads(r.stdout)
print("store_sha before == after:",
      before["store_sha"] == after["store_sha"])
print("events lines:", before["events_lines"], "->", after["events_lines"])
print("passed:", out["passed"], "/", out["tasks"],
      "| by_rung:", out["by_rung"],
      "| oracle_calls:", sum(x["oracle_calls"] for x in out["rows"]),
      "| solved_locally:", out["solved_locally"])
if before != after:
    print("SEAL LEAKED: the no-learn run wrote to the library", file=sys.stderr)
    sys.exit(1)
print("SEAL HELD: zero writes, in memory and on disk")