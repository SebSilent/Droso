"""Launch a long run detached, and leave a pidfile. Check on runs by reading the file.

WHY A PIDFILE AND NOT A SCAN. Checking on the last run was done by searching process command
lines for the script name, and that filter matched ITS OWN COMMAND LINE -- twice, because the
shell heredoc doing the searching contained the string being searched for. It reported five
processes; whether any were real is now unprovable either way. A filter that matches itself
cannot be used to conclude "nothing is running".

A scan is still allowed, but it must carry a POSITIVE CONTROL: find a process that is known to
be running before its "found nothing" is allowed to mean anything. `self_check` below does
exactly that, on the calling process itself.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIDDIR = ROOT / "state"


def _pidfile(name: str) -> Path:
    return PIDDIR / f"{name}.pid"


def launch(args: list, name: str, log: str | None = None) -> dict:
    """Start `args` detached and record who it is. Returns the pidfile contents.

    `args` is a command WITHOUT an interpreter (`["tools/x.py", "--flag"]`). A leading
    `python` is tolerated and stripped, because the smoke test called it the other way and
    got `python -u python -c ...` -- which exits instantly with "can't open file 'python'",
    and a launcher that silently fails to start is worse than one that refuses.
    """
    args = list(args)
    if args and Path(args[0]).name.lower() in ("python", "python.exe", "python3", "py"):
        args = args[1:]
    PIDDIR.mkdir(parents=True, exist_ok=True)
    logpath = PIDDIR / (log or f"{name}.log")
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    with open(logpath, "ab") as fh:
        p = subprocess.Popen([sys.executable, "-u"] + list(args),
                             stdout=fh, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, cwd=str(ROOT),
                             creationflags=flags, close_fds=True)
    rec = {"name": name, "pid": p.pid, "started": round(time.time(), 1),
           "cmd": list(args), "log": str(logpath)}
    _pidfile(name).write_text(json.dumps(rec), encoding="utf-8")
    return rec


def read(name: str) -> dict | None:
    p = _pidfile(name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def alive(name: str) -> dict:
    """Is the recorded process still the recorded process?

    The creation time is checked as well as the pid, because pids are recycled: a stale
    pidfile whose number now belongs to an unrelated process would otherwise report a run as
    alive forever.
    """
    rec = read(name)
    if not rec:
        return {"known": False, "alive": False, "reason": "no pidfile"}
    try:
        import psutil
        p = psutil.Process(int(rec["pid"]))
        started = p.create_time()
    except Exception as exc:
        return {"known": True, "alive": False, "rec": rec,
                "reason": f"{type(exc).__name__}"}
    drift = abs(started - float(rec.get("started") or 0))
    if drift > 30:
        return {"known": True, "alive": False, "rec": rec,
                "reason": f"pid recycled (started {drift:.0f}s from the record)"}
    log = Path(rec["log"])
    return {"known": True, "alive": True, "rec": rec, "pid": rec["pid"],
            "log_bytes": log.stat().st_size if log.exists() else None,
            "reason": "running and matching the record"}


def self_check() -> dict:
    """The positive control. Called before any scan is trusted."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        found = any(x.pid == os.getpid() for x in psutil.process_iter())
        return {"control": "self", "pid": os.getpid(),
                "found": bool(found), "cmd_visible": bool(me.cmdline())}
    except Exception as exc:
        return {"control": "self", "found": False, "error": type(exc).__name__}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: detached.py status <name> | launch <name> <cmd...>")
        return 2
    if sys.argv[1] == "status":
        print(json.dumps(self_check(), indent=1))
        print(json.dumps(alive(sys.argv[2]), indent=1))
        return 0
    if sys.argv[1] == "launch":
        print(json.dumps(launch(sys.argv[3:], sys.argv[2]), indent=1))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
