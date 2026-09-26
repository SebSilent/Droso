"""One place for throwaway files, and the policy that keeps it throwaway.

Nothing that must be consulted may live here. Everything under `_tmp/` is
gitignored and swept once it is older than the TTL, so a file that matters and
a file that does not are indistinguishable to this module -- it deletes by age.
Verification snippets, one-off test scripts and battery runs belong here rather
than in the project root, where 4,945 `_verify_*.py` accumulated because the
sandbox anchored a relative name at the project root and nothing ever removed
it.

Sweeping is deliberately forgiving: it never raises, it skips anything it
cannot stat, and it leaves recent files alone. A cleaner that can fail a run is
worse than the mess it was written to prevent.
"""
from __future__ import annotations

import time
from pathlib import Path

#: The folder itself, at the project root, next to the code it serves.
TMP_DIRNAME = "_tmp"
#: Subfolder for snippets the sandbox writes to execute. Kept apart from a
#: human's own scratch so a `ls _tmp/` still shows what a person put there.
SANDBOX_DIRNAME = "sandbox"

#: Files older than this are swept. A day is long enough to read yesterday's
#: run and short enough that the folder cannot grow without bound.
DEFAULT_TTL_SECONDS = 24 * 3600
#: At most one sweep this often, per process. Callers can ask on every run and
#: pay nothing for it.
SWEEP_INTERVAL_SECONDS = 600

_last_sweep = 0.0


def temp_root(project_root) -> Path:
    return Path(project_root) / TMP_DIRNAME


def scratch_dir(project_root) -> Path:
    return temp_root(project_root) / SANDBOX_DIRNAME


def ensure(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def clean(root, ttl_seconds: float = DEFAULT_TTL_SECONDS,
          now: float | None = None) -> dict:
    """Delete files under `root` older than `ttl_seconds`, then remove any
    directories left empty. Returns counts; never raises."""
    now = time.time() if now is None else float(now)
    root = Path(root)
    out = {"root": str(root), "removed": 0, "dirs_removed": 0, "kept": 0}
    if not root.is_dir():
        return out
    # Deepest first, so a directory is visited after its contents and can be
    # removed in the same pass once it is empty.
    for p in sorted(root.rglob("*"), key=lambda q: -len(q.parts)):
        try:
            if p.is_dir():
                try:
                    p.rmdir()
                    out["dirs_removed"] += 1
                except OSError:
                    pass                # not empty yet, or not ours to remove
                continue
            if now - p.stat().st_mtime > float(ttl_seconds):
                p.unlink()
                out["removed"] += 1
            else:
                out["kept"] += 1
        except OSError:
            continue
    return out


def sweep_if_due(root, ttl_seconds: float = DEFAULT_TTL_SECONDS,
                 interval: float = SWEEP_INTERVAL_SECONDS,
                 now: float | None = None) -> dict | None:
    """Clean only if the last sweep in this process was long enough ago.
    Returns the clean() result when it ran, None when it was skipped."""
    global _last_sweep
    now = time.time() if now is None else float(now)
    if now - _last_sweep < float(interval):
        return None
    _last_sweep = now
    return clean(root, ttl_seconds=ttl_seconds, now=now)
