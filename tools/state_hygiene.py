"""State hygiene: one save path, fatal on failure, with a retention sweep.

Three failures produced 450 GB of state directories and two fake 0.0
regressions before this module existed:

  1. every harness saved full state trees (the delta handover fixed the
     benchmark's own writes but not converse.py's, serve.py's or
     drift_check.py's);
  2. nothing ever deleted a session directory, so probes, one-offs and
     errored rows accumulated forever;
  3. a failed save was printed and swallowed, so a full disk scored ask
     phases against half-saved shadows and the suite exited 0 with two
     rows at 0.0 that looked like a language regression (measured
     2026-10-26 10:07: "67108864 requested and 0 written").

This module is the one place that fixes all three.  Harnesses call
`save_session_state` instead of `lang.save_state` (fatal on failure),
and `prune_sessions` after writing a report (keep the last N per kind).

Usage:
    python tools/state_hygiene.py            # sweep now, print the table
    python tools/state_hygiene.py --dry-run  # what would be deleted
    python tools/state_hygiene.py --keep 5   # override the retention
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
SESSIONS = STATE / "sessions"
LINEAGE = STATE / "lineage"

# Retention per kind: the newest N directories survive a sweep.  Sessions
# are evidence whose numbers live in the reports -- three of a kind is
# enough to re-derive anything.  Lineage copies are merge stock, so they
# keep a little more headroom.
DEFAULT_KEEP = {"sessions": 3, "lineage": 2}

_TS = re.compile(r"_(\d{8})_(\d{6})$|_(\d{4})-(\d{2})-(\d{2})$")


def _kind_of(name: str) -> str:
    """`cross_reference_tell_20261026_100704` -> `cross_reference_tell`,
    `live_2026-10-26` -> `live`.

    Two timestamp shapes exist: sessions stamp `_%Y%m%d_%H%M%S`, lineage
    copies stamp `_%Y-%m-%d`.  A directory without either is its own kind,
    so a one-off probe named `wordcheck` is swept as a kind of one.
    """
    return _TS.sub("", name)


def _real_bytes(p: Path) -> int:
    """Bytes a tree actually holds, not the bytes its hardlinks point at.

    A hardlinked file's size belongs to its first link; counting it per
    link would report a shadow tree as ~660 MB when it holds none.
    """
    total = 0
    if p.is_file():
        st = p.stat()
        return st.st_size if st.st_nlink == 1 else 0
    for e in p.rglob("*"):
        try:
            if e.is_file():
                st = e.stat()
                if st.st_nlink == 1:
                    total += st.st_size
        except OSError:
            pass
    return total


def _rmtree(p: Path) -> int:
    freed = _real_bytes(p)
    shutil.rmtree(p, ignore_errors=True)
    return freed


def sweep(root: Path, keep: int, dry_run: bool = False) -> tuple[int, int]:
    """Retention sweep of one root.  Returns (bytes freed, dirs deleted)."""
    if not root.is_dir():
        return 0, 0
    groups: dict[str, list[Path]] = {}
    for d in root.iterdir():
        if d.is_dir():
            groups.setdefault(_kind_of(d.name), []).append(d)
    freed = deleted = 0
    for kind, dirs in sorted(groups.items()):
        dirs.sort(key=lambda d: d.name)  # names embed the timestamp
        for old in dirs[:-keep] if keep > 0 else dirs:
            if dry_run:
                try:
                    shown = old.relative_to(ROOT)
                except ValueError:  # a root outside the project (tests)
                    shown = old
                print(f"  would delete {shown} "
                      f"({_real_bytes(old) / 1e6:.1f} MB)")
                freed += _real_bytes(old)
            else:
                freed += _rmtree(old)
            deleted += 1
    return freed, deleted


def prune_sessions(keep: int | None = None, dry_run: bool = False) -> dict:
    """Sweep every retention root.  Called after each report write."""
    out = {"freed": 0, "deleted": 0, "roots": {}}
    for name, root in (("sessions", SESSIONS), ("lineage", LINEAGE)):
        n = DEFAULT_KEEP[name] if keep is None else keep
        freed, deleted = sweep(root, n, dry_run)
        out["roots"][name] = {"freed": freed, "deleted": deleted}
        out["freed"] += freed
        out["deleted"] += deleted
    if out["freed"] and not dry_run:
        print(f"[hygiene] pruned {out['deleted']} old state dirs, "
              f"{out['freed'] / 1e6:.1f} MB reclaimed")
    return out


def require_saved(res: dict, what: str) -> dict:
    """A failed save is fatal, loud, and says why.

    The disk-full incident scored ask phases against shadows that held
    two files instead of eight and reported the result as a 0.0 pass
    rate.  A save failure must stop the run, not the truth.
    """
    if not (res or {}).get("saved"):
        reason = (res or {}).get("reason") or "no reason given"
        hint = " -- disk full?" if "requested and 0 written" in str(reason) else ""
        raise SystemExit(f"FATAL: {what} save failed{hint}: {reason}")
    return res


def save_session_state(lang, what: str) -> dict:
    """The one save path for session copies: delta, fatal on failure.

    `save_state(delta=True)` writes the json plus what this session
    heard (kilobytes) and falls back to a full save when the delta
    refuses (cap exceeded), so only real I/O failures reach the check.
    """
    res = lang.save_state(delta=True)
    if res.get("mode") == "full":
        print(f"[hygiene] {what}: delta refused, full save written "
              f"({res.get('delta_refused')})")
    return require_saved(res, what)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", type=int, default=None,
                    help="override the per-kind retention for this sweep")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be deleted, delete nothing")
    args = ap.parse_args()
    print(f"retention sweep of {STATE} "
          f"(sessions keep {DEFAULT_KEEP['sessions'] if args.keep is None else args.keep}, "
          f"lineage keep {DEFAULT_KEEP['lineage'] if args.keep is None else args.keep})"
          f"{' -- DRY RUN' if args.dry_run else ''}")
    t0 = time.time()
    out = prune_sessions(keep=args.keep, dry_run=args.dry_run)
    for name, r in out["roots"].items():
        print(f"  {name:<9} {r['deleted']} deleted, "
              f"{r['freed'] / 1e6:.1f} MB freed")
    print(f"done in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())