"""Correct episode 3's live_seals_unchanged gate, from recorded evidence.

Episode 3 ran before teach_episode.py split the guard's moved list by prefix, so
--keep-checkpoint's own writes under state/live_learner/ were read as damage and the
episode was marked FAIL on a gate whose substance had passed.

The correction is recomputed from data already in the row plus two independent checks
run at correction time, and the original verdict is kept beside it. Nothing is
re-measured and no ask is re-run.

  py -3.10 docs/evidence/correct_episode3_gate.py
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # docs/evidence/ -> repo root
sys.path.insert(0, str(ROOT))
LEDGER = ROOT / "state" / "lineage" / "episodes.jsonl"

rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
shutil.copyfile(LEDGER, LEDGER.with_name("episodes_precorrection_ep3.jsonl"))

n = 0
for e in rows:
    if e.get("episode") != 3 or e.get("correction"):
        continue
    moved = e["guard"]["moved"]
    own = [m for m in moved if str(m).replace("\\", "/").startswith("live_learner/")]
    other = [m for m in moved if m not in own]
    seals_ok = e["seals"]["unchanged"] is True
    # Independent check: the learner root the episode started from still matches its
    # manifest, and the live state still matches the bootstrap state.
    v = subprocess.run([sys.executable, str(ROOT / "tools" / "promote_learner.py"),
                        "--verify"], cwd=str(ROOT), capture_output=True, text=True)
    verify_ok = v.returncode == 0 and "VERIFY OK" in v.stdout
    justified = (not other) and seals_ok and verify_ok
    e["correction"] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "why": "the episode ran before teach_episode.py split the guard's moved list "
               "by prefix, so --keep-checkpoint's own writes under state/live_learner/ "
               "were read as damage; two hardlinked .npz files were also reported moved "
               "while their sha256 was identical, because converse's guard keys .npz by "
               "zip-member CRC and size rather than by a hash of the bytes",
        "original_verdict": e["verdict"],
        "original_gate": e["gates"]["live_seals_unchanged"],
        "evidence": {
            "moved_paths": len(moved),
            "moved_under_live_learner": len(own),
            "moved_elsewhere": other,
            "live_sha256_seals_unchanged": seals_ok,
            "promote_learner_verify_ok": verify_ok,
        },
        "rule_now": "teach_episode.py splits own writes under state/live_learner/ from "
                    "damage elsewhere, and sha256-seals both the live learner files and "
                    "the learner root it started from",
    }
    if justified:
        e["gates"]["live_seals_unchanged"] = True
        e["gates"]["live_seals_unchanged_detail"] = (
            f"CORRECTED: {len(own)} own writes under state/live_learner/, "
            f"{len(other)} elsewhere; live sha256 seals unchanged; "
            f"promote_learner --verify OK")
        e["guard"]["live_files_untouched"] = True
        e["guard"]["own_writes_under_live_learner"] = len(own)
        e["guard"]["moved"] = other
        gates = e["gates"]
        e["verdict"] = ("PASS" if all(gates.get(k) is True for k in
                        ("absence_verified", "erosion_zero", "census_reported",
                         "live_seals_unchanged", "row_self_contained")) else "FAIL")
    n += 1
    print(f"episode 3: {e['correction']['original_verdict']} -> {e['verdict']}  "
          f"(justified={justified}: other={other}, seals_ok={seals_ok}, verify={verify_ok})")

with LEDGER.open("w", encoding="utf-8") as fh:
    for e in rows:
        fh.write(json.dumps(e, default=str) + "\n")
print(f"corrected {n} row(s); backup at episodes_precorrection_ep3.jsonl")
sys.exit(0 if n else 1)
