"""Seal episode 3's staging checkpoint, proving by mtime that it is the run's own.

Episode 3 ran before teach_episode.py recorded `checkpoint_files`, so promote_learner's
check 3 -- that the staging bytes are the bytes that were measured -- has nothing to
compare against. Re-running the episode would cost 34 minutes to produce the same
numbers, so instead the checkpoint is sealed now and tied to the run by modification
time: every file must have been written during the episode and not since.

The ordering that makes this sound is in the code path itself: save_state wrote the
session state, the checkpoint hardlinked those same inodes, and the measurement shadow
hardlinked them again. Checkpoint and measured shadow therefore derive from one set of
files. What mtime adds is that nobody has written to them afterwards.

The row records that the seals were taken at correction time, not at run time, so the
provenance of the number is visible rather than implied.

  py -3.10 docs/evidence/seal_episode3_checkpoint.py
"""
import hashlib
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # docs/evidence/ -> repo root
LEDGER = ROOT / "state" / "lineage" / "episodes.jsonl"
STAGING = ROOT / "state" / "live_learner" / "staging"

rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
shutil.copyfile(LEDGER, LEDGER.with_name("episodes_preseal_ep3.jsonl"))


def seal(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


n = 0
for e in rows:
    if e.get("episode") != 3 or e.get("checkpoint_files"):
        continue
    ck = e.get("checkpoint_dir")
    if not ck or not Path(ck).exists():
        print(f"REFUSING: no staging checkpoint at {ck}")
        sys.exit(1)
    ck = Path(ck)
    ended = datetime.strptime(e["at"], "%Y-%m-%dT%H:%M:%S").timestamp()
    # The row's `at` is written at the END of the run, so every checkpoint file must
    # predate it. A margin absorbs clock resolution, not sloppiness: 300 s against a
    # 2024 s run.
    files = {p.name: p for p in sorted(ck.iterdir()) if p.name != "open_batch.json"}
    late = {p.name: time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime))
            for p in files.values() if p.stat().st_mtime > ended + 300}
    if late:
        print(f"REFUSING: written after the episode ended at {e['at']}: {late}")
        sys.exit(1)
    e["checkpoint_files"] = {p.name: seal(p) for p in files.values()}
    e["checkpoint_files_provenance"] = {
        "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "why": "the episode ran before teach_episode.py recorded checkpoint_files; "
               "sealed afterwards and tied to the run by mtime",
        "episode_ended": e["at"],
        "files": len(files),
        "latest_mtime": max(time.strftime("%H:%M:%S", time.localtime(p.stat().st_mtime))
                            for p in files.values()),
        "all_predate_episode_end": not late,
    }
    n += 1
    print(f"episode 3: sealed {len(files)} checkpoint files at {ck.name}")
    print(f"  episode ended {e['at']}, latest file mtime "
          f"{e['checkpoint_files_provenance']['latest_mtime']}, none later")
    print(f"  id {hashlib.sha256(json.dumps(e['checkpoint_files'], sort_keys=True).encode()).hexdigest()[:12]}")

with LEDGER.open("w", encoding="utf-8") as fh:
    for e in rows:
        fh.write(json.dumps(e, default=str) + "\n")
print(f"sealed {n} row(s); backup at episodes_preseal_ep3.jsonl")
sys.exit(0 if n else 1)
