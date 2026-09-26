"""The reader, as its own process. Track B.

Reading inside the tick loop cost the world most of its life: `world_speed_x` measured
0.603 with exposure on against a 20x baseline, so the being spent ~97% of its time
serving the thing that teaches it language. The measured breakdown was 19.7 ms per
line, 54% of it a semantic-cortex gather, 7.6% full state writes triggered once per
new word.

Two of those were fixed in the organ itself, because they were waste rather than
architecture: `live()` built a meaning readout that the reading path discards (half of
that 54%), and save_state wrote 268 MB whenever a new word appeared. Throughput went
50.9 -> 133 lines/s. That helps every reader, in-process or not.

This process is the other half. It owns a reader individual in its own project root --
so it never touches the house's state files, which removes the collision class rather
than gating it -- and reads continuously at full speed. The house's own exposure is
turned off, so its tick loop serves the world again. What the reader learns comes back
through the population merge, which is built and verified: vocabulary unioned, chains
summed, propositions unioned, and `--san-from` to keep the experienced cortex whole
instead of averaging a teacher and a pupil.

That is a deliberate choice over running a per-line delta queue through an IPC channel:
the merge path already exists, is tested, and does the same job in bulk. A queue would
move the same numbers with more moving parts. The cost of the choice is that absorption
is periodic rather than continuous, and the merge is where the two lives are pooled.

Usage:
    python tools/reader.py --seconds 3600            # one hour, resumable
    python tools/reader.py --seconds 0               # until stopped
    python tools/reader.py --status                  # what has been read so far
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

READER_ROOT = ROOT / "state" / "reader"
SHELF = ROOT / "state" / "shelf"


def _build():
    """A reader individual, resumed from its own state if it has any."""
    os.environ.setdefault("HYBRIDLLM_OFFLINE", "1")
    from world.connectome_house import build_house_agent
    from organs.tokenizer import TokenizerOrgan
    READER_ROOT.mkdir(parents=True, exist_ok=True)
    cfg = {"model": {"api_key": None, "provider": "qwen"},
           "language": {"state_path": str(READER_ROOT / "language_state.json"),
                        "auto_train": False},
           "connectome": {"project_root": str(READER_ROOT),
                          "accelerated_life": False},
           "sandbox": {"project_root": str(READER_ROOT)},
           "house": {"enabled": False}}
    agent = build_house_agent(cfg, project_root=str(READER_ROOT))
    # A reader is not a being living in a world; it is a reader. The heartbeat, the
    # growth timer and the autotrainer are body functions that shape and time the
    # animal, and none of them teach language -- they only compete for the CPU the
    # reading needs. Stopped here rather than config-disabled because
    # build_house_agent arms them, and the point of this process is throughput.
    for _name in ("heartbeat", "autotraining", "neural_growth"):
        _organ = getattr(agent, _name, None)
        if _organ is not None and hasattr(_organ, "stop"):
            try:
                _organ.stop()
            except Exception:
                pass
    lang = agent.language
    if getattr(lang, "tokenizer", None) is None:
        lang.tokenizer = TokenizerOrgan()
    return agent, lang


def _shelf() -> Path:
    """Where it reads from. A curated shelf if present, else the whole corpus."""
    return SHELF if SHELF.exists() and any(SHELF.glob("*.txt")) else ROOT / "books"


def read(seconds: float = 3600.0, save_every: int = 30000) -> dict:
    agent, lang = _build()
    shelf = _shelf()
    lang.set_books_dir(shelf)
    lang.exposure_enabled = True
    lang.exposure_speed_s = 0.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang._book_words = []
    lang._book_lines = []
    lang._book_is_q = []
    lang._book_line_pos = 0
    t0 = time.time()
    deadline = t0 + float(seconds) if seconds and seconds > 0 else None
    lines = 0
    last_save = t0
    while deadline is None or time.time() < deadline:
        before = (lang._book_idx, lang._book_line_pos)
        lang.expose_tick(1.0)
        if (lang._book_idx, lang._book_line_pos) != before:
            lines += 1
        now = time.time()
        if now - last_save >= 180.0:
            lang.save_state(force=True)      # persists the sidecars as well
            last_save = now
    lang.save_state(force=True)
    el = max(1e-9, time.time() - t0)
    out = {"root": str(READER_ROOT), "shelf": str(shelf),
           "lines": lines, "seconds": round(el, 1),
           "lines_per_second": round(lines / el, 2),
           "vocabulary": lang.vocabulary_size(),
           "propositions": int(lang.cortex.binder.X.shape[0]),
           "deferred_saves": int(getattr(lang, "_save_deferrals", 0))}
    (READER_ROOT / "reader_report.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    return out


def status() -> dict:
    p = READER_ROOT / "state" / "language_state.json"
    if not p.exists():
        alt = READER_ROOT / "language_state.json"
        if not alt.exists():
            return {"started": False, "root": str(READER_ROOT)}
        p = alt
    st = json.loads(p.read_text(encoding="utf-8"))
    rep = READER_ROOT / "reader_report.json"
    out = {"started": True, "root": str(READER_ROOT),
           "vocabulary": len(st.get("words") or {}),
           "qa_pairs": (st.get("questions") or {}).get("pairs_seen"),
           "last_book": (st.get("narration") or {}).get("last_phase")}
    if rep.exists():
        out["last_run"] = json.loads(rep.read_text(encoding="utf-8"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=3600.0,
                    help="how long to read; 0 means until stopped")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--fresh", action="store_true",
                    help="start from nothing instead of resuming")
    a = ap.parse_args()
    if a.status:
        print(json.dumps(status(), indent=1))
        return 0
    if a.fresh and READER_ROOT.exists():
        shutil.rmtree(READER_ROOT, ignore_errors=True)
    out = read(a.seconds)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
