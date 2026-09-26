"""Sweep the project's temporal folder.

    python tools/temp_clean.py              # remove anything older than the TTL
    python tools/temp_clean.py --ttl 3600   # remove anything older than an hour
    python tools/temp_clean.py --status     # list what is in there and its age

`_tmp/` is gitignored and holds nothing that must be consulted: it is where the
sandbox writes verification snippets (and removes them again), plus any one-off
run a tool drops there. Safe to run on a schedule.

The house sweeps it periodically on its own -- see Heartbeat._fire and
Sandbox.run_python -- so this tool exists for the case where nothing is
running, and for looking before you sweep.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs import tempstore


def _fmt(seconds: float) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds >= size:
            return f"{seconds / size:.1f}{unit}"
    return f"{seconds:.0f}s"


def _status(root: Path) -> None:
    if not root.is_dir():
        print(f"{root} does not exist yet (nothing temporal has been written)")
        return
    now = time.time()
    files = [p for p in root.rglob("*") if p.is_file()]
    if not files:
        print(f"{root} is empty")
        return
    total = 0
    for p in sorted(files, key=lambda q: q.stat().st_mtime):
        size = p.stat().st_size
        total += size
        print(f"  {_fmt(now - p.stat().st_mtime):>6} old  {size:>9,} B  "
              f"{p.relative_to(root)}")
    print(f"{len(files)} file(s), {total:,} bytes under {root}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Sweep the project's temporal folder (_tmp/).")
    ap.add_argument("--ttl", type=float,
                    default=tempstore.DEFAULT_TTL_SECONDS,
                    help="seconds; files older than this are removed "
                         f"(default {tempstore.DEFAULT_TTL_SECONDS:.0f})")
    ap.add_argument("--status", action="store_true",
                    help="show contents and age instead of removing")
    a = ap.parse_args(argv)

    root = tempstore.temp_root(ROOT)
    if a.status:
        _status(root)
        return 0

    out = tempstore.clean(root, ttl_seconds=a.ttl)
    print(f"removed {out['removed']} file(s), {out['dirs_removed']} empty "
          f"dir(s); kept {out['kept']} newer than {_fmt(a.ttl)} under "
          f"{out['root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
