#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULTS = ["exocortex/api_cache.sqlite3", "state/house_agent_cache.sqlite3"]

def find_caches(extra=()):
    out = []
    for rel in list(DEFAULTS) + list(extra):
        p = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if p.exists() and p not in out:
            out.append(p)
    for p in sorted(ROOT.glob("agent_state/*_cache.sqlite3")):
        out.append(p)
    for p in sorted(ROOT.glob("state/*_cache.sqlite3")):
        if p not in out:
            out.append(p)
    return out

def census(path: Path) -> dict:
    try:
        con = sqlite3.connect(str(path))
        rows = con.execute("SELECT mode, COUNT(*) FROM entries GROUP BY mode"
                           ).fetchall()
        con.close()
    except sqlite3.OperationalError:
        return {"error": "no entries table"}
    return {str(m or ""): int(n) for m, n in rows}

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cache", action="append", default=[],
                    help="additional cache db path (repeatable)")
    args = ap.parse_args(argv)

    from organs.query_cache import QueryCache

    total_before = total_after = 0
    touched = 0
    for path in find_caches(args.cache):
        before = census(path)
        bad = sum(n for m, n in before.items() if m != "live")
        print(f"{path.relative_to(ROOT)}: {before}")
        if args.dry_run or not bad:
            total_before += sum(int(v) for v in before.values() if isinstance(v, int))
            continue
        c = QueryCache(path=path)
        removed = c.purge_non_live()
        after = census(path)
        c.close()
        print(f"    purged {removed} non-live row(s) -> {after}")
        touched += 1
        total_before += sum(int(v) for m, v in before.items() if isinstance(v, int))
        total_after += sum(int(v) for m, v in after.items() if isinstance(v, int))
    if args.dry_run:
        print("dry run: nothing deleted")
        return 0
    print(f"{touched} database(s) cleaned; {total_before - total_after} "
          f"non-live row(s) gone, {total_after} live row(s) remain")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())