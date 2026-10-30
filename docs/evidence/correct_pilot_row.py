"""Correct the episode-99 pilot row, visibly, without deleting it.

Episode 99 was the instrument pilot: it ran --tier open, so the frozen and guarded
tiers were 0/0 and the erosion gate reported PASS on nothing it had measured. The
gate was fixed afterwards (unmeasured is now None, and None fails the verdict), but
the row was already in the append-only ledger claiming PASS.

Rewriting a row in an append-only ledger is not done quietly. The correction is
written INTO the row, the original verdict and gates are kept beside it, and the row
is marked so a reader and the tests can both tell it apart from a real episode.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # docs/evidence/ -> repo root
LEDGER = ROOT / "state" / "lineage" / "episodes.jsonl"

rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
shutil.copyfile(LEDGER, LEDGER.with_name("episodes_precorrection.jsonl"))

n = 0
for e in rows:
    if e.get("episode") != 99 or e.get("correction"):
        continue
    if e["eval"]["frozen_asked"] != 0:
        continue
    e["correction"] = {
        "at": "2026-10-30",
        "why": "instrument pilot run with --tier open before the erosion gate was "
               "made non-vacuous: frozen 0/0 and guarded 0/0, so erosion_zero "
               "reported PASS on nothing it had measured",
        "original_verdict": e["verdict"],
        "original_erosion_zero": e["gates"]["erosion_zero"],
        "rule_now": "a gate that was never run is None and None fails the verdict "
                    "(tools/teach_episode.py verdict_of, REQUIRED_GATES)",
    }
    e["gates"]["erosion_zero"] = None
    e["gates"]["erosion_zero_detail"] = (
        "NOT MEASURED: --tier open ran no frozen or guarded ask")
    e["verdict"] = "FAIL"
    e["kind"] = "instrument-pilot"
    n += 1

with LEDGER.open("w", encoding="utf-8") as fh:
    for e in rows:
        fh.write(json.dumps(e, default=str) + "\n")

print(f"corrected {n} row(s); backup at episodes_precorrection.jsonl")
for e in rows:
    print(f"  episode {e['episode']:3d}  verdict {e['verdict']:5s} "
          f"frozen {e['eval']['frozen_asked']:2d}  "
          f"kind {e.get('kind', 'episode')}")
sys.exit(0)
