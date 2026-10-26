"""The cross-session benchmark: tells in one session, asks in a later one.

The script benchmark's warm runs hold a script's tells and asks in ONE
session, so a pass can be credited to the fresh tier -- the sort key's
session-recency term -- rather than to memory that lasts.  This harness
splits each script across a session boundary:

  session A (tell)   a normal converse.py session: it hears the script's
                     "say" turns and exits, saving its state into its own
                     session directory.  The live state is never written.
  shadow root        state/ rebuilt as hardlinks to the live files with
                     session A's saved language files laid over them, so
                     the next session starts exactly where A left off.
                     Hardlinks, not copies: the tree is ~660 MB and B
                     never writes to it -- every persistence path is
                     re-pointed into B's own session directory, as in
                     every converse.py session.  No read-only attribute
                     is set: on NTFS attributes travel with the file, so
                     marking a shadow link read-only would mark the live
                     file read-only too.  The live-files guard watches
                     the real tree through both phases instead.
  session B (ask)    a new process on the shadow root: it asks the
                     script's questions and is graded with the same
                     expect block as the warm runs.

In B the taught propositions are no longer fresh -- their `when` is A's
wall clock, B's session_t0 is B's -- so they compete on the sort key alone
against every corpus fragment.  A pass means what he was told survived
the boundary and was still retrievable; a fail means the boundary lost
it.  The comparison is against the warm runs (same session, fresh tier
on) and the cold runs (no tells anywhere, graded on absence).

One honest asymmetry: B's first ask that lands on a taught row rehearses
it, and a rehearsed row's `when` moves to now -- so later asks in B may
see a memory B itself re-freshened.  That is what recall does to memory
and the report keeps the per-turn order so it can be seen.

Usage:
    python tools/benchmark_cross_session.py                  # all scripts
    python tools/benchmark_cross_session.py --only role_chain
    python tools/benchmark_cross_session.py --phase tell --name reference
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
FITNESS = STATE / "fitness"
SESSIONS = STATE / "sessions"

sys.path.insert(0, str(ROOT))
import tools.converse as converse  # noqa: E402
from tools import state_hygiene  # noqa: E402


# ----------------------------------------------------------------- phases ----

def run_phase(phase: str, name: str, scripts_path: Path, tag: str,
              shadow_root: str | None = None) -> int:
    """One session, one script, one half of it.  Writes its own report."""
    scripts = json.loads(scripts_path.read_text(encoding="utf-8"))["scripts"]
    script = next((s for s in scripts if s.get("name") == name), None)
    if script is None:
        print(f"[cross] no script named {name!r} in {scripts_path}")
        return 2

    session_dir = SESSIONS / f"{tag}_{time.strftime('%Y%m%d_%H%M%S')}"
    session_dir.mkdir(parents=True, exist_ok=True)
    # The guard window starts before the build, so the verdict covers the
    # whole run, not just the turns (debt entry 6's fix shape).
    guard_before = converse.guard_live_files(tag)
    agent = converse.build(session_dir, project_root=shadow_root)
    lang = agent.language

    before = converse.snapshot(agent)
    session = converse.Session(agent, beats=2)

    turns = []
    if phase == "tell":
        for step in script["turns"]:
            if "say" not in step:
                continue
            turn = session.ask(step["say"], kind="tell")
            turns.append({"kind": "tell", "say": step["say"],
                          "spoken": converse._spoken(turn)})
    else:
        for step in script["turns"]:
            if "ask" not in step:
                continue
            turn = session.ask(step["ask"], kind="ask")
            rec = {"kind": "ask", "ask": step["ask"],
                   "spoken": converse._spoken(turn),
                   "said": converse._said(turn)[:120],
                   "source": (turn.get("reply") or {}).get("source")}
            rec.update(converse._score_expect(turn, step.get("expect") or {}))
            turns.append(rec)

    after = converse.snapshot(agent)
    delta = converse.delta(before, after)
    changed = converse.guard_check(guard_before)
    untouched = not changed
    if not untouched:
        print(f"[cross] LIVE FILES TOUCHED in {phase} phase: {changed}")

    # delta=True, not force_san=True. force_san wrote the whole 640 MB state
    # (SAN matrix, chain, binder) twice per script per suite to carry a
    # conversation's worth of teachings, and nothing ever deleted a session --
    # that is where 450 GB of state directories came from. The delta save
    # writes the json (vocabulary) plus what this session heard as utterances
    # (kilobytes); the next phase replays them through hear() itself. If the
    # delta refuses, save_state falls back to the full save on its own.
    # Fatal on failure: a half-saved tell session has no cortex file, so the
    # shadow carries no teachings and the ask phase scores a fake 0.0.
    # Measured 2026-10-26: disk full, "67108864 requested and 0 written",
    # shadow overlay_files 2 instead of 8, two rows at 0.0 that looked like
    # a language regression.  The phase process now dies nonzero and the
    # orchestrator marks the row errored instead of scoring it.
    save = state_hygiene.save_session_state(lang, f"{phase} phase")

    asks = [t for t in turns if t["kind"] == "ask"]
    passed = sum(1 for t in asks if t.get("pass"))
    benchmark = {"name": name, "kind": script.get("kind", ""),
                 "phase": phase, "turns": turns, "asked": len(asks),
                 "passed": passed,
                 "pass_rate": round(passed / len(asks), 3) if asks else None}

    report = {"tag": tag, "session_dir": str(session_dir),
              "shadow_root": shadow_root,
              "interpreter": sys.executable,
              "measured_at": time.strftime(
                  "%Y-%m-%d %H:%M:%S"),
              "benchmark": benchmark, "transcript": session.transcript(),
              "delta": delta, "live_files_untouched": untouched,
              "live_files_changed": changed, "save": save,
              "guard_window": "build+turns",
              "guard_known_churn": list(converse.KNOWN_CHURN)}
    out = FITNESS / f"conversation_{tag}.json"
    out.write_text(json.dumps(report, indent=1, default=str),
                   encoding="utf-8")

    b = delta.get("binder", {})
    print(f"[cross] {phase:>4} {name:<16} asked {len(asks)} passed {passed} "
          f"| binder +{b.get('added_n', 0)} ~{b.get('rehearsed_n', 0)} "
          f"| live untouched {untouched} | {out.name}")
    return 0


# ----------------------------------------------------------------- shadow ----

def build_shadow(tell_session_dir: Path, shadow: Path) -> dict:
    """state/ as hardlinks to the live files, with session A's saves on top.

    Only the language-state family is overlaid: that is what save_state
    writes and what a conversation moves.  Everything else in the tree --
    curriculum, lineage, population, the reader's shelf -- is linked as
    the live house left it.
    """
    n_live = n_overlay = 0
    for p in sorted(STATE.rglob("*")):
        rel = p.relative_to(STATE)
        if rel.parts[0] in converse.GUARD_EXCLUDE:
            continue
        target = shadow / "state" / rel
        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        os.link(p, target)
        n_live += 1
    for p in sorted(tell_session_dir.iterdir()):
        if not p.is_file() or not p.name.startswith("language_state"):
            continue
        target = shadow / "state" / p.name
        if target.exists():
            target.unlink()
        os.link(p, target)
        n_overlay += 1
    (shadow / "house_workspace").mkdir(exist_ok=True)
    return {"live_files_linked": n_live, "overlay_files": n_overlay,
            "shadow": str(shadow)}


# ------------------------------------------------------------- baselines ----

def newest_benchmark_report() -> dict | None:
    """Newest by the report's own measured_at, not by filename.

    'script_benchmark_full_*' sorts after every dated report
    lexicographically, so a filename sort handed the warm/cold baselines
    the pre-fix numbers while a newer post-fix rerun sat next to them.
    """
    def recency(p: Path) -> tuple[int, float]:
        try:
            m = json.loads(p.read_text(encoding="utf-8")).get("measured_at")
            if isinstance(m, (int, float)):
                return (1, float(m))
            if isinstance(m, str):
                return (1, time.mktime(
                    time.strptime(m, "%Y-%m-%d %H:%M:%S")))
        except Exception:
            pass
        return (0, p.stat().st_mtime)

    reports = sorted(FITNESS.glob("script_benchmark_*.json"), key=recency)
    if not reports:
        return None
    return json.loads(reports[-1].read_text(encoding="utf-8"))


def ensure_baseline(name: str, scripts_path: Path, base: dict) -> dict | None:
    """Warm/cold numbers for one script, from the newest report or a run."""
    for row in base.get("rows", []):
        if row.get("name") == name:
            return {"warm": row.get("warm", {}).get("pass_rate"),
                    "cold": row.get("cold", {}).get("pass_rate"),
                    "source": base.get("tag") or base.get("measured_at", "")}
    # Never benchmarked: run it now through the existing harness, so the
    # table's other two columns exist for it too.
    print(f"[cross] {name}: no warm/cold baseline; running the script "
          f"benchmark for it")
    rates = {}
    sdirs = []
    for mode, flag in (("warm", []),
                       ("cold", ["--cold", str(scripts_path)])):
        tag = f"script_{name}_{mode}"
        cmd = [sys.executable, str(ROOT / "tools" / "converse.py"),
               "--scripts", str(scripts_path), "--name", name,
               "--save", tag] + flag
        rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
        if rc != 0:
            print(f"[cross] {name}: {mode} baseline run failed (exit {rc})")
            return None
        rep = FITNESS / f"conversation_{tag}.json"
        if not rep.exists():
            return None
        doc = json.loads(rep.read_text(encoding="utf-8"))
        rates[mode] = (doc.get("benchmark") or {}).get("pass_rate")
        # The baseline session's state directory is dead weight the moment its
        # numbers are in the report; the row prunes it with the rest.
        if doc.get("session_dir"):
            sdirs.append(doc["session_dir"])
    return {"warm": rates["warm"], "cold": rates["cold"],
            "source": "run now", "session_dirs": sdirs}


# ----------------------------------------------------------------- prune ----

def _reclaimable_bytes(p: Path) -> int:
    """Bytes a tree actually holds, not the bytes its hardlinks point at.

    The shadow tree is mostly hardlinks into the live state: counting their
    sizes would report ~660 MB freed by deleting a tree that frees almost
    nothing. st_nlink == 1 is a real file with its own blocks -- the session
    directories' state files and the shadow's overlay copies -- and only those
    are reclaimed.
    """
    total = 0
    try:
        for f in p.rglob("*"):
            try:
                if f.is_file() and f.stat().st_nlink == 1:
                    total += f.stat().st_size
            except OSError:
                pass
    except OSError:
        pass
    return total


def prune_artifacts(paths: list) -> int:
    """Delete session artifacts and report the bytes they were holding.

    The reports keep the transcripts and the scores; the state directories are
    ~640 MB each and nothing ever read one again. Rows that errored keep their
    artifacts -- those are the evidence.
    """
    freed = 0
    for p in paths:
        if not p:
            continue
        p = Path(p)
        if not p.exists():
            continue
        freed += _reclaimable_bytes(p)
        shutil.rmtree(p, ignore_errors=True)
    return freed


# --------------------------------------------------------------- orchestr ----

def run_suite(names: list[str], scripts_path: Path, keep: bool = False) -> int:
    base = newest_benchmark_report() or {}
    rows = []
    total_freed = 0
    for name in names:
        baseline = ensure_baseline(name, scripts_path, base)
        tell_tag, ask_tag = f"cross_{name}_tell", f"cross_{name}_ask"

        rc = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                             "--phase", "tell", "--name", name,
                             "--tag", tell_tag,
                             "--scripts", str(scripts_path)],
                            cwd=str(ROOT)).returncode
        tell_rep = FITNESS / f"conversation_{tell_tag}.json"
        if rc != 0 or not tell_rep.exists():
            print(f"[cross] {name}: tell phase failed (exit {rc}); skipping")
            rows.append({"name": name, "error": f"tell phase exit {rc}"})
            continue
        tell = json.loads(tell_rep.read_text(encoding="utf-8"))
        tell_save = tell.get("save") or {}
        if not tell_save.get("saved"):
            # A half-saved tell session has no cortex file, so the shadow
            # carries no teachings and the ask phase scores a fake 0.0.
            # Measured 2026-10-26: disk full, "67108864 requested and 0
            # written", shadow overlay_files 2 instead of 8, two rows at 0.0
            # that looked like a language regression.
            print(f"[cross] {name}: tell save failed "
                  f"({tell_save.get('reason')}); skipping ask")
            rows.append({"name": name, "baseline": baseline,
                         "tell": tell["benchmark"], "tell_delta": tell["delta"],
                         "tell_live_untouched": tell["live_files_untouched"],
                         "error": f"tell save failed: {tell_save.get('reason')}"})
            continue

        shadow = SESSIONS / f"cross_shadow_{name}_{time.strftime('%Y%m%d_%H%M%S')}"
        shadow_info = build_shadow(Path(tell["session_dir"]), shadow)

        rc = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                             "--phase", "ask", "--name", name,
                             "--tag", ask_tag, "--shadow", str(shadow),
                             "--scripts", str(scripts_path)],
                            cwd=str(ROOT)).returncode
        ask_rep = FITNESS / f"conversation_{ask_tag}.json"
        if rc != 0 or not ask_rep.exists():
            print(f"[cross] {name}: ask phase failed (exit {rc})")
            rows.append({"name": name, "baseline": baseline,
                         "tell": tell["benchmark"], "shadow": shadow_info,
                         "error": f"ask phase exit {rc}"})
            continue
        ask = json.loads(ask_rep.read_text(encoding="utf-8"))
        ask_save = ask.get("save") or {}

        row = {"name": name, "kind": ask["benchmark"].get("kind"),
               "tell_save_ok": bool(tell_save.get("saved")),
               "ask_save_ok": bool(ask_save.get("saved")),
               "baseline": baseline,
               "tell": tell["benchmark"], "tell_delta": tell["delta"],
               "tell_live_untouched": tell["live_files_untouched"],
               "shadow": shadow_info,
               "ask": ask["benchmark"], "ask_delta": ask["delta"],
               "ask_live_untouched": ask["live_files_untouched"],
               "tell_session_dir": tell["session_dir"],
               "ask_session_dir": ask["session_dir"]}
        if not keep:
            # The row is clean: its scores live in the reports, so the session
            # directories and the shadow tree are dead weight. Delete them now
            # or they accumulate at ~11 GB a suite -- which is exactly what
            # filled the disk. Errored rows keep theirs (see the branches above).
            freed = prune_artifacts([tell["session_dir"], ask["session_dir"],
                                     (shadow_info or {}).get("shadow")]
                                    + ((baseline or {}).get("session_dirs")
                                       or []))
            if freed:
                row["session_pruned"] = True
                total_freed += freed
        rows.append(row)

    report = {"tag": f"cross_session_{time.strftime('%Y%m%d_%H%M%S')}",
              "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "interpreter": sys.executable,
              "scripts_file": str(scripts_path), "rows": rows}
    out = FITNESS / f"{report['tag']}.json"
    out.write_text(json.dumps(report, indent=1, default=str),
                   encoding="utf-8")
    # Retention: errored rows keep their session dirs (the branches above
    # leave them for diagnosis), so the sweep bounds how long they stay.
    state_hygiene.prune_sessions()

    print(f"\n{'script':<16} {'warm':>6} {'cross':>6} {'cold':>6} "
          f"{'x-cold':>7}  live")
    ws = cs = xs = 0.0
    wn = cn = xn = 0
    for r in rows:
        if "error" in r:
            print(f"{r['name']:<16} ERROR: {r['error']}")
            continue
        b = r.get("baseline") or {}
        warm, cold = b.get("warm"), b.get("cold")
        cross = (r["ask"] or {}).get("pass_rate")
        ok = r.get("ask_live_untouched") and r.get("tell_live_untouched")
        print(f"{r['name']:<16} "
              f"{('%s' % warm) if warm is not None else '-':>6} "
              f"{('%s' % cross) if cross is not None else '-':>6} "
              f"{('%s' % cold) if cold is not None else '-':>6} "
              f"{('%+.2f' % (cross - cold)) if None not in (cross, cold) else '-':>7}"
              f"  {'ok' if ok else 'TOUCHED'}")
        if warm is not None:
            ws += warm; wn += 1
        if cold is not None:
            xs += cold; cn += 1
        if cross is not None:
            cs += cross; xn += 1
    if xn:
        print(f"{'overall':<16} "
              f"{(ws / wn if wn else 0):>6.3f} {cs / xn:>6.3f} "
              f"{(xs / cn if cn else 0):>6.3f}")
    print(f"\nreport: {out}")
    if total_freed:
        print(f"pruned session artifacts: {total_freed / (1024 * 1024):.1f} MB "
              f"reclaimed (--keep to preserve them)")
    # The suite-level leak: this used to return 0 no matter what the rows
    # said, so a suite with two errored rows exited green and the fake 0.0s
    # sailed into the log as a language regression.  Errored rows now exit 1.
    errored = [r for r in rows if "error" in r]
    if errored:
        print(f"\n{len(errored)} row(s) errored: "
              f"{', '.join(r['name'] for r in errored)}")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scripts", default=str(ROOT / "tools" / "scripts.json"))
    ap.add_argument("--only", default=None,
                    help="one script name, or several comma-separated")
    ap.add_argument("--phase", choices=("tell", "ask"), default=None,
                    help="run one half of one script and exit (the "
                         "orchestrator spawns this)")
    ap.add_argument("--name", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--shadow", default=None,
                    help="project root for the ask phase (the shadow tree)")
    ap.add_argument("--keep", action="store_true",
                    help="keep session directories and shadow trees after "
                         "clean rows (they are pruned by default: the reports "
                         "hold the scores, and the state directories "
                         "accumulated 450 GB before pruning existed)")
    args = ap.parse_args()
    scripts_path = Path(args.scripts)

    # Fail fast on an interpreter without numpy.  The 2026-10-25 21:55 run
    # imported cleanly under a Python 3.12 with no numpy (converse imports
    # numpy lazily inside build()), wrote a seven-error-row report, and
    # every spawned tell phase died on `import numpy` in under a second.
    # An error-row report must never masquerade as data.
    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        print(f"[cross] interpreter has no numpy ({exc}); refusing to run\n"
              f"[cross] interpreter: {sys.executable}\n"
              f"[cross] use the project's Python (the one with numpy)")
        return 2

    if args.phase:
        if not args.name or not args.tag:
            print("[cross] --phase needs --name and --tag")
            return 2
        return run_phase(args.phase, args.name, scripts_path, args.tag,
                         shadow_root=args.shadow)

    scripts = json.loads(scripts_path.read_text(encoding="utf-8"))["scripts"]
    names = ([n.strip() for n in args.only.split(",")] if args.only
             else [s["name"] for s in scripts])
    return run_suite(names, scripts_path, keep=args.keep)


if __name__ == "__main__":
    raise SystemExit(main())