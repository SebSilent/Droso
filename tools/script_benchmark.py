"""The script benchmark: warm vs cold, per script kind.

Six scripts (tools/scripts.json), 4-6 turns each, where later turns depend
on earlier ones.  Each script runs twice through the same harness
(tools/converse.py), each run as its own process so the connectome delta is
one session's and nothing leaks between runs:

  warm  one persistent session: the script's tells land first, its final
        questions are asked at the end, and the expects are graded against
        what the session taught him.  A pass means the session context
        survived to the end of the script and was used.

  cold  a fresh session: only the final questions, graded on the ABSENCE of
        the words the warm session taught.  If he says one of those words
        cold, training memory already held the fact and the warm pass for
        that question is not evidence that session context was used.  A
        refusal passes: the honest answer to a question about a
        conversation that never happened is not to assert one.

The headline number is the warm-cold delta per script kind: does session
context persist and get used?  The connectome delta of one warm session is
reported alongside, because a conversation with Droso must leave a trace.

Usage:
    python tools/script_benchmark.py            # all six scripts
    python tools/script_benchmark.py --only reference,override
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import state_hygiene  # noqa: E402  (needs ROOT on sys.path)

SCRIPTS = ROOT / "tools" / "scripts.json"
FITNESS = ROOT / "state" / "fitness"


def run_one(mode: str, name: str, tag: str) -> dict:
    """One script, one mode, one process, one report file."""
    cmd = [sys.executable, str(ROOT / "tools" / "converse.py"),
           f"--{mode}", str(SCRIPTS), "--name", name,
           "--save", tag, "--beats", "2"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=600)
    dt = time.time() - t0
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit(f"{mode} {name} failed ({r.returncode})")
    out = FITNESS / f"conversation_{tag}.json"
    if not out.exists():
        raise SystemExit(f"no report written for {tag}")
    rep = json.loads(out.read_text(encoding="utf-8"))
    rep["_seconds"] = round(dt, 1)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--only", type=str, default=None,
                    help="comma-separated script names to run")
    args = ap.parse_args()

    scripts = json.loads(SCRIPTS.read_text(encoding="utf-8"))["scripts"]
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        scripts = [s for s in scripts if s["name"] in want]
    if not scripts:
        raise SystemExit("no scripts selected")

    rows = []
    for s in scripts:
        name = s["name"]
        print(f"=== {name} ({s['kind']}) ===", flush=True)
        warm = run_one("scripts", name, f"script_{name}_warm")
        print(f"  warm: {warm['benchmark']['passed']}/"
              f"{warm['benchmark']['asked']} "
              f"({warm['_seconds']}s)", flush=True)
        cold = run_one("cold", name, f"script_{name}_cold")
        print(f"  cold: {cold['benchmark']['passed']}/"
              f"{cold['benchmark']['asked']} "
              f"({cold['_seconds']}s)", flush=True)
        rows.append({"name": name, "kind": s["kind"],
                     "warm": warm["benchmark"], "cold": cold["benchmark"],
                     "warm_delta": warm["delta"],
                     "cold_delta": cold["delta"],
                     "live_files_untouched":
                         warm.get("live_files_untouched") and
                         cold.get("live_files_untouched")})

    print()
    print(f"{'script':<16}{'kind':<16}{'warm':>6}{'cold':>6}{'delta':>7}")
    tot_w = tot_c = 0.0
    for r in rows:
        w = r["warm"]["pass_rate"] or 0.0
        c = r["cold"]["pass_rate"] or 0.0
        tot_w += w
        tot_c += c
        print(f"{r['name']:<16}{r['kind']:<16}{w:>6.2f}{c:>6.2f}"
              f"{w - c:>+7.2f}")
    n = len(rows)
    print(f"{'overall':<16}{'':<16}{tot_w / n:>6.2f}{tot_c / n:>6.2f}"
          f"{(tot_w - tot_c) / n:>+7.2f}")

    # Failures, so the table is not the end of the story.
    for r in rows:
        for t in r["warm"]["turns"] + r["cold"]["turns"]:
            if t.get("kind") in ("ask", "cold_ask") and not t.get("pass"):
                print(f"  FAIL {r['name']}/{t['kind']}: {t.get('ask')}")
                print(f"       said: {t.get('said') or '(silent)'} "
                      f"(words: {t.get('said_words')})")

    # Which predicate won the override script, per run: the nondeterminism
    # is the finding, so it is reported, never graded.
    ov = next((r for r in rows if r["name"] == "override"), None)
    if ov:
        winners = [t.get("winner") for t in ov["warm"]["turns"]
                   if t.get("kind") == "ask"]
        print(f"  override winners (warm): {winners}")

    out = {
        "measured_at": round(time.time(), 1),
        "scripts_file": str(SCRIPTS),
        "rows": rows,
        "overall": {"warm": round(tot_w / n, 3),
                    "cold": round(tot_c / n, 3),
                    "delta": round((tot_w - tot_c) / n, 3)},
        "one_session_connectome_delta": rows[0]["warm_delta"],
    }
    outp = FITNESS / f"script_benchmark_{time.strftime('%Y%m%d_%H%M%S')}.json"
    outp.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nreport: {outp}")
    # converse.py exits nonzero on a failed save, so run_one already raises
    # SystemExit before this line; the sweep bounds what a green run leaves.
    state_hygiene.prune_sessions()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())