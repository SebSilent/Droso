r"""Cost model for a breeding population of Droso brains: measure the machine
BEFORE choosing N, so the population size is a derived number and not a guess.

WHY THIS FILE EXISTS. The axis gets 8 GB of RAM and every core. Every later
design choice -- one shared substrate or one house per fly, sparse delta or full
weight copy, threads or serial -- is forced by four numbers, and none of them
are knowable from the source:

  (a) RSS of ONE fully loaded house substrate (corpus, band, embeddings, weights)
  (b) RSS of a SECOND loaded house in the same process -- does it share pages
      with the first, or duplicate them? numpy arrays read from disk are fresh
      allocations, so the honest expectation is duplicate; the number decides.
  (c) RSS cost of a small GENOMIC DELTA -- a fly's mutable layer, measured both
      ways: a full copy of the largest weight array, and a sparse dict of the
      cells a mutation actually touches.
  (d) wall-clock of one cheap fitness evaluation, and of the thing the design
      forbids (rebuilding a house from corpus), so "seconds not minutes" is a
      measured claim.

N is then derived from the budget with headroom, and published: it is whatever
comes out, 10 or 400.

RSS is read from the process itself in a fresh subprocess, so it is the RSS of
this work and not of an editor that has been open for three days.

  py -3.10 tools/fly_cost_model.py --phase all
  py -3.10 tools/fly_cost_model.py --phase rss
"""
from __future__ import annotations

import argparse
import ctypes
import json
import shutil
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BUDGET_MB = 8192          # what the task grants
HEADROOM_MB = 2048        # what must stay free for the OS and the harness


# ---------------------------------------------------------------- process RAM
def rss_bytes():
    """Resident set of this process, and which method produced it."""
    try:
        import psutil
        return int(psutil.Process().memory_info().rss), "psutil.rss"
    except Exception:
        pass

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    try:
        h = ctypes.windll.kernel32.GetCurrentProcess()
        m = PMC()
        m.cb = ctypes.sizeof(PMC)
        if ctypes.windll.psapi.GetProcessMemoryInfo(h, ctypes.byref(m), m.cb):
            # WorkingSetSize is the physical pages currently resident -- RSS by
            # another name. It can be trimmed under pressure, which only makes
            # the estimate of N conservative.
            return int(m.WorkingSetSize), "psapi.WorkingSetSize"
    except Exception:
        pass
    return 0, "unavailable"


def phys_mb():
    """Total and free physical RAM, and the machine's own load percentage."""
    class MSG(ctypes.Structure):
        _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

    try:
        m = MSG()
        m.dwLength = ctypes.sizeof(MSG)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return (int(m.ullTotalPhys) >> 20, int(m.ullAvailPhys) >> 20,
                    int(m.dwMemoryLoad))
    except Exception:
        pass
    return 0, 0, 0


MB = 1024 * 1024


def _big_arrays(obj, top=6):
    """The largest numpy arrays hanging off an object, by nbytes."""
    out = []
    for name, val in list(vars(obj).items()):
        if isinstance(val, np.ndarray):
            out.append((name, int(val.nbytes), list(val.shape), str(val.dtype)))
    for name, val in list(vars(obj).items()):
        if val is not None and hasattr(val, "__dict__") and not isinstance(val, type):
            try:
                for n2, v2 in vars(val).items():
                    if isinstance(v2, np.ndarray):
                        out.append((f"{name}.{n2}", int(v2.nbytes),
                                    list(v2.shape), str(v2.dtype)))
            except Exception:
                pass
    out.sort(key=lambda r: -r[1])
    return out[:top]


def _dir_mb(p: Path):
    try:
        return round(sum(f.stat().st_size for f in p.rglob("*")
                         if f.is_file()) / MB, 1)
    except Exception:
        return None


# ---------------------------------------------------------------- phases
def phase_rss(report):
    """(a) one house, (b) a second house in the same process, (c) delta cost."""
    from tools.converse import build

    stamp = time.strftime("%Y%m%d_%H%M%S")
    sess = []
    r0, how = rss_bytes()
    report["rss_method"] = how
    report["baseline_after_imports_mb"] = round(r0 / MB, 1)
    print(f"[rss] baseline after imports      : {r0/MB:8.1f} MB  ({how})")

    agent1 = None
    try:
        d = ROOT / "state" / "sessions" / f"flycost_{stamp}_1"
        sess.append(d)
        t = time.time()
        agent1 = build(d)
        dt = time.time() - t
        r1, _ = rss_bytes()
        report["house1_mb"] = round(r1 / MB, 1)
        report["house1_delta_mb"] = round((r1 - r0) / MB, 1)
        report["build_seconds"] = round(dt, 1)
        report["session_copy_mb"] = _dir_mb(d)
        print(f"[rss] one loaded house          : {r1/MB:8.1f} MB "
              f"(+{(r1-r0)/MB:.1f}) build {dt:.1f}s copy {report['session_copy_mb']} MB")

        d2 = ROOT / "state" / "sessions" / f"flycost_{stamp}_2"
        sess.append(d2)
        t = time.time()
        agent2 = build(d2)
        dt2 = time.time() - t
        r2, _ = rss_bytes()
        report["house2_total_mb"] = round(r2 / MB, 1)
        report["house2_delta_mb"] = round((r2 - r1) / MB, 1)
        report["build2_seconds"] = round(dt2, 1)
        # Share or duplicate: if the second house costs ~0 it is page-shared.
        report["second_house_shares"] = bool((r2 - r1) < 0.15 * max(r1 - r0, 1))
        print(f"[rss] second house, same process: {r2/MB:8.1f} MB "
              f"(+{(r2-r1)/MB:.1f}) build {dt2:.1f}s  "
              f"{'SHARED' if report['second_house_shares'] else 'DUPLICATED'}")
        del agent2
        r2f, _ = rss_bytes()
        report["after_free_second_mb"] = round(r2f / MB, 1)
        print(f"[rss]   after freeing it        : {r2f/MB:8.1f} MB")

        lang = getattr(agent1, "language", None)
        if lang is not None:
            big = _big_arrays(lang)
            report["largest_arrays"] = [(n, round(b / MB, 1), s, d_)
                                        for n, b, s, d_ in big]
            for n, b, s, d_ in big:
                print(f"[arr]   {n:28s} {b/MB:8.1f} MB  {s} {d_}")
            if big:
                name, nbytes, shape, _dt = big[0]
                src = getattr(lang, name, None)
                if isinstance(src, np.ndarray):
                    r3, _ = rss_bytes()
                    keep = np.array(src, copy=True)     # full mutable layer
                    r4, _ = rss_bytes()
                    report["full_weight_copy_mb"] = round((r4 - r3) / MB, 1)
                    report["full_weight_copy_array"] = name
                    print(f"[rss] full copy of {name}   : "
                          f"+{(r4-r3)/MB:8.1f} MB")
                    del keep

                    for k in (1000, 10000, 100000):
                        r5, _ = rss_bytes()
                        flat = np.zeros(k * 2, dtype=np.float64)
                        delta = {}
                        for i in range(k):
                            delta[(i, 0)] = float(flat[i])
                        r6, _ = rss_bytes()
                        report[f"sparse_delta_{k}_mb"] = round((r6 - r5) / MB, 2)
                        print(f"[rss] sparse delta, {k:7d} cells: "
                              f"+{(r6-r5)/MB:8.2f} MB")
                        del delta
    finally:
        for d in sess:
            shutil.rmtree(d, ignore_errors=True)
    return report


def phase_wall(report):
    """(d) wall-clock of one cheap fitness evaluation, and of a rebuild."""
    from tools.converse import build
    from tools.fly_population import (load_pairs, fitness_shape_vs_binder,
                                      base_genome)

    d = ROOT / "state" / "sessions" / f"flycost_{time.strftime('%Y%m%d_%H%M%S')}_w"
    try:
        t = time.time()
        agent = build(d)
        report["build_seconds"] = round(time.time() - t, 1)
        print(f"[wall] rebuild a house from corpus (FORBIDDEN per fly): "
              f"{report['build_seconds']}s")
        pairs, note = load_pairs(agent)
        report["fitness_pairs"] = len(pairs)
        report["fitness_pair_note"] = note
        g = base_genome(0)
        t = time.time()
        val = fitness_shape_vs_binder(agent, g, pairs)
        dt = time.time() - t
        report["fitness_seconds_1fly"] = round(dt, 3)
        report["fitness_value_1fly"] = val
        print(f"[wall] one cheap fitness eval ({len(pairs)} pairs): {dt*1000:.1f} ms"
              f"   value={val}")
        t = time.time()
        vals = [fitness_shape_vs_binder(agent, base_genome(i), pairs)
                for i in range(10)]
        dt10 = time.time() - t
        report["fitness_seconds_10fly"] = round(dt10, 3)
        print(f"[wall] ten of them                        : {dt10:.2f} s")
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return report


def phase_derive(report):
    """N from the budget. Whatever comes out, comes out."""
    per_fly = report.get("house2_delta_mb")
    full = report.get("full_weight_copy_mb")
    sparse = report.get("sparse_delta_10000_mb")
    avail = min(BUDGET_MB - HEADROOM_MB, max(256, phys_mb()[1]))
    report["budget_mb"] = BUDGET_MB
    report["headroom_mb"] = HEADROOM_MB
    report["usable_mb"] = avail
    report["machine_total_mb"], report["machine_free_mb"], report["machine_load_pct"] = phys_mb()
    models = {}
    if per_fly:
        models["house_per_fly"] = per_fly
    if full:
        models["shared_substrate_plus_full_weight_copy"] = full
    if sparse:
        models["shared_substrate_plus_sparse_delta"] = sparse
    for name, mb in sorted(models.items(), key=lambda kv: kv[1]):
        n = int(avail // max(mb, 0.01))
        report.setdefault("N_by_model", {})[name] = n
        print(f"[N] {name:38s} {mb:8.2f} MB/fly -> N = {n}")
    if report.get("fitness_seconds_1fly"):
        gen_s = 10 * report["fitness_seconds_1fly"]      # 10 flies per generation
        report["generation_seconds_10fly"] = round(gen_s, 2)
        turn_s = 3600
        report["generations_per_turn_10fly"] = int(turn_s // max(gen_s, 0.001))
        print(f"[N] generation of 10 flies = {gen_s:.2f}s -> "
              f"{report['generations_per_turn_10fly']} generations per hour")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--phase", default="all",
                    choices=["all", "rss", "wall", "derive"])
    ap.add_argument("--out", default=None, help="write JSON here")
    args = ap.parse_args()

    report = {"stamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    if args.phase in ("all", "rss"):
        phase_rss(report)
    if args.phase in ("all", "wall"):
        phase_wall(report)
    if args.phase in ("all", "derive"):
        phase_derive(report)
    out = Path(args.out) if args.out else (
        ROOT / "state" / "fitness" /
        f"fly_cost_{time.strftime('%Y%m%d_%H%M%S')}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
