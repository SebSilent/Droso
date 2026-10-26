"""Merge the six per-script warm/cold reports into one combined report.

Same row shape as tools/script_benchmark.py, built from the per-script files
the orchestrator's subprocess runs already wrote, so a lost background run
does not have to be repeated end to end.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITNESS = ROOT / "state" / "fitness"
NAMES = ["reference", "accumulation", "discrimination", "role_chain",
         "switch_back", "override"]

kinds = {s["name"]: s["kind"] for s in json.loads(
    (ROOT / "tools" / "scripts.json").read_text(encoding="utf-8"))["scripts"]}

rows = []
for name in NAMES:
    warm = json.loads((FITNESS / f"conversation_script_{name}_warm.json")
                      .read_text(encoding="utf-8"))
    cold = json.loads((FITNESS / f"conversation_script_{name}_cold.json")
                      .read_text(encoding="utf-8"))
    rows.append({"name": name, "kind": kinds[name],
                 "warm": warm["benchmark"], "cold": cold["benchmark"],
                 "warm_delta": warm["delta"], "cold_delta": cold["delta"],
                 "live_files_untouched":
                     warm.get("live_files_untouched") and
                     cold.get("live_files_untouched")})

print(f"{'script':<16}{'kind':<16}{'warm':>6}{'cold':>6}{'delta':>7}")
tot_w = tot_c = 0.0
for r in rows:
    w = r["warm"]["pass_rate"] or 0.0
    c = r["cold"]["pass_rate"] or 0.0
    tot_w += w
    tot_c += c
    print(f"{r['name']:<16}{str(r['kind']):<16}{w:>6.2f}{c:>6.2f}{w - c:>+7.2f}")
n = len(rows)
print(f"{'overall':<16}{'':<16}{tot_w / n:>6.2f}{tot_c / n:>6.2f}"
      f"{(tot_w - tot_c) / n:>+7.2f}")

for r in rows:
    for t in r["warm"]["turns"] + r["cold"]["turns"]:
        if t.get("kind") in ("ask", "cold_ask") and not t.get("pass"):
            print(f"  FAIL {r['name']}/{t['kind']}: {t.get('ask')}")
            print(f"       said: {t.get('said') or '(silent)'} "
                  f"(words: {t.get('said_words')})")

ov = next((r for r in rows if r["name"] == "override"), None)
if ov:
    winners = [t.get("winner") for t in ov["warm"]["turns"]
               if t.get("kind") == "ask"]
    print(f"  override winners (warm): {winners}")

out = {"measured_at": round(time.time(), 1),
       "scripts_file": str(ROOT / "tools" / "scripts.json"),
       "rows": rows,
       "overall": {"warm": round(tot_w / n, 3), "cold": round(tot_c / n, 3),
                   "delta": round((tot_w - tot_c) / n, 3)},
       "one_session_connectome_delta": rows[0]["warm_delta"]}
outp = FITNESS / f"script_benchmark_full_{time.strftime('%Y%m%d_%H%M%S')}.json"
outp.write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\nreport: {outp}")