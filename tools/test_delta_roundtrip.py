"""Round-trip test for the cortex delta save, at two levels.

Level 1 is the organ alone: hear, save_delta, apply_delta into a fresh cortex,
and check the counts and the recall match. Level 2 is the house path: build a
session, teach it, save_state(delta=True), lay the state files into a second
root the way the cross-session benchmark's shadow does, boot a fresh language
organ there, and check the teaching survived the boundary -- the benchmark's
whole question at unit scale, in seconds instead of minutes.

Usage:  python tools/test_delta_roundtrip.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs.higher_cortex import HigherCortex  # noqa: E402

SENTENCES = [
    ["the", "sky", "is", "blue"],
    ["the", "grass", "is", "green"],
    ["mira", "keeps", "bees", "in", "the", "orchard"],
    ["the", "orchard", "smells", "of", "pears"],
    ["bees", "make", "honey", "from", "flowers"],
    ["the", "harbour", "freezes", "in", "winter"],
    ["the", "harbour", "freezes", "in", "winter"],  # duplicate: dedup check
]


def teach(cx: HigherCortex) -> None:
    # Fresh teaching: replay=False (the default) so the utterances are
    # recorded into _heard -- replay=True is the delta-application path and
    # deliberately records nothing. Paced: hear() is throttled in real time
    # (MIN_HEAR_INTERVAL_S), so a tight loop would teach one utterance and
    # skip the rest -- which is what the throttle is FOR, not a bug.
    for s in SENTENCES:
        cx.hear(s)
        time.sleep(0.06)


def level1() -> bool:
    print("== level 1: the organ alone ==")
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="delta_test_"))
    try:
        a = HigherCortex()
        teach(a)
        a.binder.bind_fact("keeps", "mira", "proc://bees", shape="who",
                           source="test")
        dpath = tmp / "cortex.delta.json"
        res = a.save_delta(dpath)
        print(f"  save_delta: {res}")
        ok &= bool(res.get("saved"))
        size = dpath.stat().st_size if dpath.exists() else -1
        print(f"  delta file: {size} bytes")
        ok &= 0 < size < 64 * 1024

        b = HigherCortex()
        applied = b.apply_delta(dpath)
        print(f"  apply_delta: {applied}")
        ok &= applied.get("applied") == len(SENTENCES)

        # The replay must reproduce the counts exactly: same utterances, same
        # dedup, same windowing.
        same = (a.predictor.updates == b.predictor.updates
                and a.binder.stored == b.binder.stored
                and a.binder.X.shape == b.binder.X.shape)
        print(f"  counts match: updates {a.predictor.updates}=="
              f"{b.predictor.updates}, stored {a.binder.stored}=="
              f"{b.binder.stored}, shape {a.binder.X.shape}=={b.binder.X.shape}")
        ok &= same

        # Recall: the taught first word comes back from the fresh cortex.
        ans = b.ask(["the", "sky", "is"], role=3,
                    candidates=["blue", "green", "red"])
        got = (ans.get("answer") or [None])[0] if isinstance(
            ans.get("answer"), list) else ans.get("answer")
        print(f"  recall 'the sky is _': {got}")
        ok &= got == "blue"

        # The fact rode along.
        ref = b.binder.recall_fact("keeps", "mira", shape="who")
        print(f"  fact recall: {ref}")
        ok &= ref == "proc://bees"

        # The cap: past it, the delta refuses rather than pretends.
        c = HigherCortex()
        c.HEARD_DELTA_CAP = 3
        teach(c)
        refused = c.save_delta(tmp / "refused.json")
        print(f"  past the cap: {refused}")
        ok &= refused.get("saved") is False and "cap" in str(
            refused.get("reason"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


def level2() -> bool:
    print("== level 2: the house path ==")
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="delta_house_"))
    try:
        import tools.converse as converse

        sess_a = tmp / "session_a"
        agent = converse.build(sess_a)
        lang = agent.language
        for s in SENTENCES:
            lang.hear(" ".join(s), speaker="user")
        save = lang.save_state(delta=True)
        print(f"  save_state(delta=True): mode={save.get('mode')} "
              f"delta={save.get('delta')}")
        ok &= save.get("saved") and save.get("mode") == "delta"
        dpath = Path(str(lang.state_path) + ".cortex.delta.json")
        ok &= dpath.exists()
        if dpath.exists():
            print(f"  delta file: {dpath.stat().st_size} bytes")
        # The full cortex npz must NOT have been written by a delta save.
        npz = Path(str(lang.state_path) + ".cortex.npz")
        print(f"  cortex.npz written by delta save: {npz.exists()} "
              f"(expected False)")
        ok &= not npz.exists()
        taught_stored = int(lang.cortex.binder.stored)
        taught_updates = int(lang.cortex.predictor.updates)

        # A second root, laid out the way build_shadow does: the LIVE state
        # files hardlinked in, then the tell session's saved files laid over
        # them. The delta save wrote no cortex.npz, so the cortex B loads is
        # the live corpus's -- and the teachings arrive only through the
        # delta. That is the exact condition the benchmark measures.
        root_b = tmp / "root_b"
        (root_b / "state").mkdir(parents=True)
        for name in ("language_state.json", "language_state.json.cortex.npz",
                     "language_state.json.cortex.facts.json",
                     "language_state.json.cortex.meta.json",
                     "language_state.json.cortex.npz.err.npy",
                     "language_state.json.seq.npz",
                     "language_state.json.seq.slots.json",
                     "language_state.san.npz",
                     "language_state.san.npy"):
            src = ROOT / "state" / name
            if src.exists():
                dst = root_b / "state" / name
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
        for f in sess_a.glob("*"):
            if f.is_file():
                shutil.copy2(f, root_b / "state" / f.name)
        sess_b = tmp / "session_b"
        agent_b = converse.build(sess_b, project_root=str(root_b))
        lang_b = agent_b.language
        stored = int(lang_b.cortex.binder.stored)
        updates = int(lang_b.cortex.predictor.updates)
        print(f"  after boot: stored {stored} (taught {taught_stored}), "
              f"updates {updates} (taught {taught_updates}), "
              f"delta_applied={lang_b._delta_applied}")
        # Exact reproduction: same corpus underneath, same utterances replayed
        # through the same fixed hash -- the counts must match to the digit.
        ok &= stored == taught_stored and updates == taught_updates
        ok &= lang_b._delta_applied == len(SENTENCES)

        ans = lang_b.cortex.ask(["the", "sky", "is"], role=3,
                                candidates=["blue", "green", "red"])
        got = (ans.get("answer") or [None])[0] if isinstance(
            ans.get("answer"), list) else ans.get("answer")
        print(f"  recall across the boundary: {got}")
        ok &= got == "blue"

        # This session's own delta must hold only what IT heard: the replay
        # must not have been re-recorded into _heard.
        save_b = lang_b.save_state(delta=True)
        doc = json.loads(Path(str(lang_b.state_path)
                              + ".cortex.delta.json").read_text(
                                  encoding="utf-8"))
        print(f"  session B's own delta holds {len(doc.get('heard') or [])} "
              f"utterances (expected 0)")
        ok &= save_b.get("saved") and not (doc.get("heard") or [])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


if __name__ == "__main__":
    t0 = time.time()
    r1 = level1()
    r2 = level2()
    print(f"\n{'PASS' if (r1 and r2) else 'FAIL'} "
          f"({time.time() - t0:.1f}s)")
    raise SystemExit(0 if (r1 and r2) else 1)