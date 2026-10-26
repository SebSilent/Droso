"""The drift check: the same scripts through the HTTP layer and the CLI.

serve.py adds one layer between a client and the door: HTTP.  This check
measures what that layer adds.  For each seen script it runs the script
twice against the same shadow tree -- once through a fresh serve.py
process (one POST per turn) and once through converse.Session directly
(the code path the CLI and every harness run use) -- and compares the
reply text turn by turn.  Any difference is drift the HTTP layer
introduced; the report names the first turn that differs per script.

Both sides get a fresh agent on the same shadow (build_shadow with no
tell overlay: a pure hardlink copy of the live tree), so the only
difference between the runs is the transport.  The HTTP side is shut
down with a break signal so it saves its session state and runs its own
guard check, the same lifecycle as a CLI run.
"""

from __future__ import annotations

import json
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import tools.benchmark_cross_session as cross  # noqa: E402
import tools.converse as converse  # noqa: E402
from tools import state_hygiene  # noqa: E402

FITNESS = converse.STATE / "fitness"
SESSIONS = converse.STATE / "sessions"

# Debt entry 6 (docs/debt_log.md): the growth organ's first consolidation
# tick rewrites the live state/banc_brain.npz unconditionally at run start.
# np.savez embeds zip member timestamps, so the mtime moves on every build
# even when the arrays are identical (content verified identical in
# docs/evidence/cmp_banc.py).  This check guards the whole run -- snapshot
# before the first build -- so the churn shows up here; it is named, and
# its content is re-verified below, not silently whitelisted.
KNOWN_TOUCHES = {"banc_brain.npz"}


def banc_content_identical(before: Path, after: Path) -> bool | None:
    """Array-level comparison (byte hashes always differ for npz)."""
    import numpy as np
    try:
        a, b = np.load(str(before), allow_pickle=True), \
            np.load(str(after), allow_pickle=True)
    except Exception:
        return None
    if set(a.files) != set(b.files):
        return False
    for k in a.files:
        xa, xb = a[k], b[k]
        if xa.shape != xb.shape or xa.dtype != xb.dtype:
            return False
        if xa.dtype == object:
            if not all((x == y) for x, y in zip(xa.tolist(), xb.tolist())):
                return False
        elif not np.array_equal(xa, xb):
            return False
    return True


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_for_models(port: int, timeout_s: float = 240.0) -> None:
    """Poll GET /v1/models until the server answers or the load times out."""
    url = f"http://127.0.0.1:{port}/v1/models"
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(1.0)
    raise RuntimeError(f"serve.py did not answer /v1/models within {timeout_s}s")


def post_turn(port: int, text: str) -> str:
    """One utterance in, the reply's content out."""
    body = json.dumps({"messages": [{"role": "user", "content": text}]}
                      ).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        payload = json.loads(r.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def stop_server(proc: subprocess.Popen) -> None:
    """Break signal, so the server saves its state and checks its guard."""
    proc.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == "win32"
                     else signal.SIGINT)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_cli_side(script: dict, shadow: Path, session_dir: Path) -> list[dict]:
    """The CLI code path: build, Session, run_script, read the turns back."""
    agent = converse.build(session_dir, project_root=str(shadow))
    session = converse.Session(agent, beats=2)
    converse.run_script(session, script)
    out = []
    for t in session.turns:
        reply = t.get("reply") or {}
        said = str(reply.get("utterance") or reply.get("response") or "")
        out.append({"kind": t["kind"], "said": t["said"],
                    "spoken": bool(reply.get("spoken")), "reply_text": said})
    state_hygiene.save_session_state(agent.language, "drift cli side")
    return out


def run_http_side(script: dict, shadow: Path, session_dir: Path,
                  log_path: Path) -> tuple[list[dict], dict]:
    """The HTTP code path: a fresh serve.py, one POST per turn."""
    port = free_port()
    cmd = [sys.executable, str(ROOT / "tools" / "serve.py"),
           "--state", str(shadow), "--port", str(port),
           "--session-dir", str(session_dir)]
    with open(log_path, "w", encoding="utf-8") as log:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log,
                                stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                                if sys.platform == "win32" else 0)
        try:
            wait_for_models(port)
            out = []
            for step in script["turns"]:
                text = step.get("say") or step.get("ask") or ""
                content = post_turn(port, text)
                out.append({"kind": "tell" if "say" in step else "ask",
                            "said": text, "reply_text": content})
        finally:
            stop_server(proc)
    info = {"port": port, "session_dir": str(session_dir),
            "log": str(log_path)}
    return out, info


def compare(cli_turns: list[dict], http_turns: list[dict]) -> dict:
    """Turn-by-turn reply comparison; the first difference is the finding."""
    n = min(len(cli_turns), len(http_turns))
    first_diff = None
    for i in range(n):
        a, b = cli_turns[i]["reply_text"], http_turns[i]["reply_text"]
        if a != b:
            first_diff = {"turn": i + 1, "ask": cli_turns[i]["said"],
                          "cli": a, "http": b}
            break
    if first_diff is None and len(cli_turns) != len(http_turns):
        first_diff = {"turn": None,
                      "note": f"turn counts differ: cli {len(cli_turns)}, "
                              f"http {len(http_turns)}"}
    return {"turns": n, "identical": first_diff is None,
            "first_diff": first_diff}


def run_suite(scripts: list[dict]) -> int:
    live_banc = converse.STATE / "banc_brain.npz"
    banc_before = Path(tempfile.mkdtemp(prefix="drift_banc_")) / "banc_brain.npz"
    banc_before_exists = live_banc.exists()
    if banc_before_exists:
        shutil.copy2(live_banc, banc_before)
    guard_before = converse.guard_live_files("drift")
    tell_dir = Path(tempfile.mkdtemp(prefix="drift_empty_tell_"))
    shadow = SESSIONS / f"drift_shadow_{time.strftime('%Y%m%d_%H%M%S')}"
    shadow_info = cross.build_shadow(tell_dir, shadow)
    print(f"[drift] shadow: {shadow} "
          f"({shadow_info['live_files_linked']} files hardlinked)", flush=True)

    rows = []
    for script in scripts:
        name = script.get("name", "")
        print(f"[drift] {name}: cli side ...", flush=True)
        cli_dir = SESSIONS / f"drift_cli_{name}_{time.strftime('%Y%m%d_%H%M%S')}"
        cli_turns = run_cli_side(script, shadow, cli_dir)
        print(f"[drift] {name}: http side ...", flush=True)
        http_dir = SESSIONS / f"drift_http_{name}_{time.strftime('%Y%m%d_%H%M%S')}"
        log_path = FITNESS / f"drift_http_{name}.log"
        http_turns, http_info = run_http_side(script, shadow, http_dir,
                                              log_path)
        row = {"name": name, "cli_turns": cli_turns, "http_turns": http_turns,
               "cli_session_dir": str(cli_dir), "http_side": http_info}
        row.update(compare(cli_turns, http_turns))
        mark = "identical" if row["identical"] else "DIFFERS"
        print(f"[drift] {name}: {row['turns']} turns, {mark}", flush=True)
        if row["first_diff"]:
            print(f"[drift]   first diff: {row['first_diff']}", flush=True)
        rows.append(row)

    moved = converse.guard_check(guard_before)
    known = sorted(m for m in moved if m in KNOWN_TOUCHES)
    unexpected = sorted(m for m in moved if m not in KNOWN_TOUCHES)
    banc_same = None
    if "banc_brain.npz" in known and banc_before_exists:
        banc_same = banc_content_identical(banc_before, live_banc)
    untouched = not unexpected and banc_same is not False
    report = {"tag": f"drift_check_{time.strftime('%Y%m%d_%H%M%S')}",
              "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "shadow": shadow_info,
              "live_files_untouched": untouched,
              "known_touches": known,
              "banc_brain_content_identical": banc_same,
              "unexpected_touches": unexpected,
              "rows": rows}
    out = FITNESS / f"{report['tag']}.json"
    out.write_text(json.dumps(report, indent=1, default=str),
                   encoding="utf-8")

    print(f"\n{'script':<16} {'turns':>6}  result")
    for r in rows:
        print(f"{r['name']:<16} {r['turns']:>6}  "
              f"{'identical' if r['identical'] else 'DIFFERS'}")
    n_ok = sum(1 for r in rows if r["identical"])
    n_turns = sum(r["turns"] for r in rows)
    print(f"{'overall':<16} {n_turns:>6}  {n_ok}/{len(rows)} scripts identical")
    if untouched:
        churn = f" (known no-op churn: {', '.join(known)}, content identical)" \
            if known and banc_same else ""
        print(f"live files untouched: True{churn}")
    else:
        print(f"live files untouched: False -- unexpected: {unexpected}, "
              f"known: {known}, banc content identical: {banc_same}")
    print(f"\nreport: {out}")
    return 0 if (n_ok == len(rows) and untouched) else 1


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scripts", default=str(ROOT / "tools" / "scripts.json"))
    ap.add_argument("--only", default=None,
                    help="one script name, or several comma-separated")
    args = ap.parse_args()

    try:
        import numpy  # noqa: F401
    except ImportError as exc:
        print(f"[drift] interpreter has no numpy ({exc}); refusing to run")
        return 2

    scripts = json.loads(Path(args.scripts).read_text(encoding="utf-8"))["scripts"]
    names = ([n.strip() for n in args.only.split(",")] if args.only
             else [s["name"] for s in scripts])
    chosen = [s for s in scripts if s.get("name") in names]
    missing = set(names) - {s.get("name") for s in chosen}
    if missing:
        raise SystemExit(f"no script(s) named {sorted(missing)} in {args.scripts}")
    return run_suite(chosen)


if __name__ == "__main__":
    raise SystemExit(main())