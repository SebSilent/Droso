"""Why did the warm scripts fail?  Replay the benchmark's failing scripts in
process through the same doors the harness uses (build -> respond -> tick),
capture the full answer() retrieval trace the reports dropped, and measure
the SAN occupancy that explains the unchanged nnz.

Read-only against the live state: build() re-points every write into a
diag_* session directory and nothing is saved at exit.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import numpy as np
from converse import build


def main() -> int:
    session_dir = ROOT / "state" / "sessions" / \
        f"diag_{time.strftime('%Y%m%d_%H%M%S')}"
    print(f"loading Droso (session dir: {session_dir}) ...", flush=True)
    t0 = time.time()
    agent = build(session_dir)
    lang = agent.language
    binder = lang.cortex.binder
    print(f"  loaded in {time.time() - t0:.1f}s, "
          f"{len(lang.word_patterns)} words", flush=True)

    # ---- SAN occupancy: were the scripts' word pairs already wired? ----
    fp = lang._footprint

    def cells(w: str) -> list:
        return [int(i) for i in np.nonzero(fp(w))[0]]

    pairs = [("box", "shelf"), ("box", "heavy"), ("box", "red"),
             ("garden", "quiet"), ("street", "loud"), ("garden", "loud"),
             ("kettle", "noon"), ("lantern", "midnight")]
    print("\n== SAN pair wiring BEFORE the session ==")
    for a, b in pairs:
        ca, cb = cells(a), cells(b)
        sub = lang.san_w[np.ix_(ca, cb)]
        print(f"  {a:9s} x {b:9s}: "
              f"{int(np.count_nonzero(sub))}/{sub.size} cross cells wired, "
              f"max {float(sub.max()):.3f}")

    nnz0 = int(np.count_nonzero(lang.san_w))

    # ---- replay in benchmark order, capturing full ask returns ----
    scripts = json.loads(
        (ROOT / "tools" / "scripts.json").read_text(encoding="utf-8"))["scripts"]
    order = ["reference", "accumulation", "discrimination"]
    full: dict[str, dict] = {}
    for name in order:
        sc = next(s for s in scripts if s["name"] == name)
        print(f"\n== script {name} ==")
        for step in sc["turns"]:
            text = step.get("say") or step.get("ask")
            r = lang.respond(text, speaker="you")
            for _ in range(2):
                lang.tick(world_dt=2.0)
            said = r.get("utterance") or r.get("response") or ""
            tag = "TELL" if "say" in step else "ASK "
            print(f"  {tag} you: {text}")
            print(f"       droso: {said}  [{r.get('source')}] "
                  f"role={r.get('queried_role')}")
            if "ask" in step:
                full[text] = r

    nnz1 = int(np.count_nonzero(lang.san_w))
    print(f"\n== SAN nnz {nnz0} -> {nnz1} (delta {nnz1 - nnz0}) ==")

    # ---- the retrieval traces the reports never kept ----
    for text, r in full.items():
        print(f"\n==== trace for: {text} ====")
        print(json.dumps(r.get("retrieval") or {}, indent=1,
                         default=str)[:4000])
        print(f"  said: {r.get('utterance') or r.get('response')}")
        print(f"  filler: {r.get('recovered_filler')} "
              f"score={r.get('filler_score')}")
        print(f"  proposition: {r.get('proposition')}")

    # ---- raw binder recall on the failing cues ----
    for cue in (["box"], ["garden"]):
        hits = binder.recall(cue, k=12)
        print(f"\n== binder.recall({cue}, k=12) ==")
        for h in hits:
            print(f"  sim={h['similarity']:.4f} ov={h['overlap']} "
                  f"ovw={h['overlap_idf']:.3f} cnt={h['count']:4d}  "
                  f"{' '.join(str(t) for t in h['tokens'])}")

    # ---- hear counts of the competing propositions ----
    want = [("the", "box", "is", "heavy"), ("the", "box", "is", "red"),
            ("the", "box", "is", "on", "the", "shelf"),
            ("the", "garden", "is", "quiet"), ("the", "street", "is", "loud"),
            ("the", "garden", "is", "calm")]
    meta = list(binder.meta)
    print("\n== hear counts of competing propositions ==")
    for t in want:
        found = [m for m in meta
                 if tuple(str(x) for x in (m.get("tokens") or [])) == t]
        if found:
            print(f"  count={found[0].get('count', 1):4d}  {' '.join(t)}")
        else:
            print(f"  ABSENT        {' '.join(t)}")

    # ---- role machinery state ----
    print("\n== role machinery ==")
    for w in ("where", "how", "who", "what"):
        print(f"  role_for({w!r}) = {lang.role_for(w)}  "
              f"votes={lang.question_roles.get(w)}")
    print(f"  answer_types['where'] = {lang.answer_types.get('where')}")
    print(f"  answer_types['how']   = {lang.answer_types.get('how')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())