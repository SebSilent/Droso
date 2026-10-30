r"""Promotion: shadow episode -> versioned persistent learner state, with rollback.

WHY A SEPARATE AREA. The guarded baseline means something only because the live state
it was measured against has not moved. `state/language_state*` and
`state/banc_brain.npz` are that state, and tools/run_generation.py refuses to run if
the frozen suite's seal moves. Promoting a taught episode ON TOP of them would quietly
redefine what 19/24 refers to, and every generation recorded so far would become
uncomparable to the next. So the learner lives in `state/live_learner/` and the live
state is never written by this tool. Bootstrap copies it; promotion never touches it.

    state/live_learner/
      manifest.json            the version chain and the current pointer
      current/                 the promoted state an episode builds on
      versions/v<N>_<id>/      immutable snapshots, one per promotion
      staging/ep<N>_<id>/      checkpoints an episode left awaiting promotion

HARDLINKS, NOT COPIES. A checkpoint is 260 MB, 222 MB of it the binder's cortex.npz,
so full copies would make versioning unusable. Every file here is a hardlink, which is
safe for the same reason tools/benchmark_cross_session.py's build_shadow is safe:
save_state writes tmp-then-rename, which REPLACES a link rather than writing through
it, and a learner checkpoint is only ever read. The invariant is asserted by --verify,
which re-seals current/ against the manifest and compares the live state's seals to
the ones recorded at bootstrap.

PROMOTION IS NEVER AUTOMATIC. teach_episode.py always records promoted_to_live false
and cannot promote; this tool is a separate command with an explicit --promote. Five
checks gate it, and any one failing refuses the promotion rather than warning:

  1 the episode's verdict is PASS and all five of its gates are True
  2 the live state's seals now equal the seals the episode recorded before it ran,
    so the episode is not being promoted against a state that has since drifted
  3 the staging checkpoint exists and every file seal matches what the episode
    recorded, so what is promoted is what was measured
  4 the new version's parent is the current version, so the chain stays linear
  5 the guarded live state is untouched, checked before and after

  py -3.10 tools/promote_learner.py --bootstrap
  py -3.10 tools/promote_learner.py --status
  py -3.10 tools/promote_learner.py --promote --episode 3
  py -3.10 tools/promote_learner.py --rollback
  py -3.10 tools/promote_learner.py --verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.converse import guard_check, guard_live_files  # noqa: E402

STATE = ROOT / "state"
LL = STATE / "live_learner"
MANIFEST = LL / "manifest.json"
CURRENT = LL / "current"
VERSIONS = LL / "versions"
STAGING = LL / "staging"
LEDGER = STATE / "lineage" / "promotions.jsonl"

# The learner state is the language family plus the plastic weights. Everything else
# in state/ (curriculum, reader, house_agent.json) stays live and is hardlinked in by
# the shadow builder, because the learner is a MEMORY, not a whole house.
LEARNER_GLOBS = ("language_state*", "banc_brain.npz")
SCHEMA = 1
MAX_VERSIONS = 4


def seal(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16]


def learner_files(root: Path) -> dict:
    out = {}
    for g in LEARNER_GLOBS:
        for p in sorted(root.glob(g)):
            if p.is_file():
                out[p.name] = p
    return out


def live_seals() -> dict:
    return {n: seal(p) for n, p in sorted(learner_files(STATE).items())}


def dir_seals(root: Path) -> dict:
    return {n: seal(p) for n, p in sorted(learner_files(root).items())}


def state_id(seals: dict) -> str:
    """A checkpoint's identity: the sha256 of its per-file seals. Two directories with
    the same id hold the same bytes, which is what makes the chain auditable and what
    lets a re-promotion of identical content be recognised as a no-op."""
    return hashlib.sha256(json.dumps(seals, sort_keys=True).encode()).hexdigest()[:12]


def load_manifest() -> dict | None:
    if not MANIFEST.exists():
        return None
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def save_manifest(m: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, MANIFEST)


def finish_guard(before: dict, live_before: dict, what: str) -> tuple:
    """Close out a run: separate this tool's own writes from real damage, and check the
    one invariant that actually matters directly.

    `state/live_learner/` is inside `state/` and is not in converse.GUARD_EXCLUDE, so
    creating a checkpoint shows up as "live files moved". Reading that as damage would
    make the tool unable to do its job; ignoring it wholesale would hide a real leak.
    So the moved list is split by prefix and anything outside the learner area fails the
    run. And because the guarded baseline's whole meaning is that the live animal has
    not moved, the live learner files are re-sealed and compared explicitly rather than
    inferred from a directory walk.
    """
    moved = guard_check(before)
    own = [m for m in moved if str(m).replace("\\", "/").startswith("live_learner/")]
    other = [m for m in moved if m not in own]
    live_after = live_seals()
    drift = {k: (live_before.get(k), live_after.get(k))
             for k in set(live_before) | set(live_after)
             if live_before.get(k) != live_after.get(k)}
    print(f"  guard ({what}): {len(own)} own write(s) under state/live_learner/, "
          f"{len(other)} elsewhere")
    if other:
        print(f"  FAIL: live files moved outside the learner area: {other[:8]}")
    if drift:
        print(f"  FAIL: the guarded live state changed: {drift}")
    else:
        print(f"  live learner files byte-identical ({len(live_after)} sealed): "
              f"the guarded baseline still describes the live animal")
    return other, drift


def ledger(row: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, default=str) + "\n")


def link_tree(src: dict, dest: Path) -> dict:
    """Hardlink each file into dest. Returns {name: {"seal":…, "bytes":…, "link":bool}}.
    A file that cannot be linked (different volume, permissions) is copied and recorded
    as a copy, because silently copying 222 MB and calling it a link would make the
    disk cost of versioning invisible."""
    dest.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, p in src.items():
        t = dest / name
        if t.exists():
            t.unlink()
        try:
            os.link(p, t)
            linked = True
        except OSError:
            shutil.copyfile(p, t)
            linked = False
        out[name] = {"seal": seal(p), "bytes": p.stat().st_size, "link": linked}
    return out


# --------------------------------------------------------------- bootstrap ----

def cmd_bootstrap(a) -> int:
    if MANIFEST.exists() and not a.force:
        print(f"REFUSING: {MANIFEST} already exists. The learner area is versioned; "
              f"re-bootstrapping would orphan every version descended from it. "
              f"--force only if you mean to start a new chain.")
        return 1
    before = guard_live_files("bootstrap")
    live = live_seals()
    if not live:
        print("REFUSING: no learner files found in state/ -- nothing to bootstrap from")
        return 1
    vid = state_id(live)
    vname = f"v0_{vid}"
    vdir = VERSIONS / vname
    if MANIFEST.exists() and a.force:
        shutil.rmtree(VERSIONS, ignore_errors=True)
        shutil.rmtree(CURRENT, ignore_errors=True)
    files = link_tree(learner_files(STATE), vdir)
    link_tree({n: vdir / n for n in files}, CURRENT)
    m = {"schema": SCHEMA, "bootstrapped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "bootstrapped_from": {"root": "state/", "seals": live, "id": vid},
         "current": vname,
         "versions": [{"version": vname, "parent": None, "source": "bootstrap",
                       "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "episode": None,
                       "id": vid, "seals": live, "files": files}]}
    save_manifest(m)
    print(f"bootstrapped the learner from live state")
    print(f"  version   {vname}")
    print(f"  files     {len(files)} ({sum(f['bytes'] for f in files.values()) / 1e6:.1f} MB, "
          f"{sum(1 for f in files.values() if f['link'])} hardlinked)")
    print(f"  manifest  {MANIFEST}")
    other, drift = finish_guard(before, live, "bootstrap")
    ledger({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": "bootstrap",
            "version": vname, "parent": None, "id": vid, "seals": live,
            "live_untouched": not (other or drift)})
    return 0 if not (other or drift) else 1


# ---------------------------------------------------------------- promote ----

def find_staging(episode: int) -> Path | None:
    hits = sorted(STAGING.glob(f"ep{episode}_*")) if STAGING.exists() else []
    return hits[-1] if hits else None


def episode_row(episode: int) -> dict | None:
    p = STATE / "lineage" / "episodes.jsonl"
    if not p.exists():
        return None
    rows = [json.loads(l) for l in
            p.read_text(encoding="utf-8").splitlines() if l.strip()]
    # A corrected row is still the row for that episode -- episode 3's gate was
    # corrected from a guard false alarm and it is the one worth promoting. Skipping
    # corrected rows here was written to avoid the failed pilot and instead hid the
    # only promotable episode. Check 1 below already refuses anything whose verdict is
    # not PASS, which is what actually keeps the pilot out.
    hit = [r for r in rows if r.get("episode") == episode]
    return hit[-1] if hit else None


def cmd_promote(a) -> int:
    m = load_manifest()
    if m is None:
        print("REFUSING: no learner manifest. Run --bootstrap first.")
        return 1
    row = episode_row(a.episode)
    if row is None:
        print(f"REFUSING: no episode {a.episode} in state/lineage/episodes.jsonl")
        return 1

    fails = []
    # 1 -- the episode must have passed, on a real measurement
    if row.get("verdict") != "PASS":
        fails.append(f"episode {a.episode} verdict is {row.get('verdict')!r}, not PASS")
    gates = row.get("gates") or {}
    for g in ("absence_verified", "erosion_zero", "census_reported",
              "live_seals_unchanged", "row_self_contained"):
        if gates.get(g) is not True:
            fails.append(f"gate {g} is {gates.get(g)!r}, not True")
    if (row.get("eval") or {}).get("frozen_asked") != 24:
        fails.append(f"episode ran {(row.get('eval') or {}).get('frozen_asked')} "
                     f"frozen asks, not 24: erosion was never really measured")

    # 2 -- the live state must not have drifted since the episode measured it.
    # Two comparisons, because an episode row only seals the files teach_episode.py
    # knew about (language_state.json and banc_brain.npz) while this tool seals the
    # whole learner family of eight. Comparing the union reported six files as
    # "drifted" that had never moved -- the episode simply had no opinion about them.
    # So: (a) every file the episode DID seal must still match, and (b) the whole live
    # family must still match the manifest's bootstrap seals, which is the stronger and
    # complete check, since the learner's ancestry is defined as that bootstrap state.
    live_now = live_seals()
    recorded = (row.get("seals") or {}).get("before") or {}
    drift = {k: (recorded.get(k), live_now.get(k)) for k in recorded
             if recorded.get(k) != live_now.get(k)}
    if drift:
        fails.append(f"live state drifted since the episode ran: {drift}")
    boot = (m.get("bootstrapped_from") or {}).get("seals") or {}
    boot_drift = {k: (boot.get(k), live_now.get(k)) for k in set(boot) | set(live_now)
                  if boot.get(k) != live_now.get(k)}
    if boot_drift:
        fails.append(f"live state no longer matches the learner's bootstrap state, so "
                     f"the chain's root is not the animal the guarded baseline "
                     f"describes: {boot_drift}")

    # 3 -- the staging checkpoint must exist and match what the episode recorded
    stage = find_staging(a.episode)
    if stage is None:
        fails.append(f"no staging checkpoint for episode {a.episode} under {STAGING}; "
                     f"teach_episode.py needs --keep-checkpoint")
        stage_seals = {}
    else:
        stage_seals = dir_seals(stage)
        want = (row.get("checkpoint_files") or {})
        if want and want != stage_seals:
            bad = {k: (want.get(k), stage_seals.get(k))
                   for k in set(want) | set(stage_seals) if want.get(k) != stage_seals.get(k)}
            fails.append(f"staging seals differ from the episode's record: {bad}")
        if not want:
            fails.append("the episode row records no checkpoint_files, so the staging "
                         "checkpoint cannot be tied to what was measured")

    # 4 -- linear chain
    parent = m["current"]
    new_id = state_id(stage_seals) if stage_seals else None
    if new_id and any(v["id"] == new_id for v in m["versions"]):
        fails.append(f"checkpoint {new_id} is already version "
                     f"{[v['version'] for v in m['versions'] if v['id'] == new_id]}; "
                     f"promoting it again would fork the chain onto identical bytes")

    if fails:
        print(f"REFUSING to promote episode {a.episode}:")
        for f in fails:
            print(f"  - {f}")
        return 1

    before = guard_live_files("promote")
    live_at_start = live_now          # already sealed during check 2 above
    vname = f"v{len(m['versions'])}_{new_id}"
    vdir = VERSIONS / vname
    files = link_tree(learner_files(stage), vdir)
    # current/ is repointed by rebuilding it from the new immutable version, so a
    # failed half-write cannot leave current/ pointing at a mixture.
    tmpcur = LL / "current.tmp"
    shutil.rmtree(tmpcur, ignore_errors=True)
    link_tree({n: vdir / n for n in files}, tmpcur)
    shutil.rmtree(CURRENT, ignore_errors=True)
    os.replace(tmpcur, CURRENT)

    m["versions"].append({"version": vname, "parent": parent, "source": "promotion",
                          "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "episode": a.episode, "id": new_id,
                          "seals": stage_seals, "files": files,
                          "episode_checkpoint": row.get("checkpoint_id"),
                          "acquisition": (row.get("eval") or {}).get("acquisition"),
                          "erosion": row.get("erosion")})
    m["current"] = vname
    # Cap the immutable versions, but NEVER the ones the chain still needs: the
    # current version and its parent, so --rollback always has somewhere to go.
    keep = {m["current"]}
    pv = next((v for v in m["versions"] if v["version"] == m["current"]), None)
    while pv and pv.get("parent"):
        keep.add(pv["parent"])
        pv = next((v for v in m["versions"] if v["version"] == pv["parent"]), None)
    droppable = [v for v in m["versions"] if v["version"] not in keep]
    for v in droppable[:-MAX_VERSIONS] if len(droppable) > MAX_VERSIONS else []:
        shutil.rmtree(VERSIONS / v["version"], ignore_errors=True)
        m["versions"] = [x for x in m["versions"] if x["version"] != v["version"]]
        print(f"  pruned version {v['version']} (outside the cap of {MAX_VERSIONS}, "
              f"not on the rollback path)")
    save_manifest(m)

    other, drift = finish_guard(before, live_at_start, "promote")
    print(f"promoted episode {a.episode} -> {vname}")
    print(f"  parent    {parent}")
    print(f"  id        {new_id}   episode checkpoint {row.get('checkpoint_id')}")
    print(f"  files     {len(files)} "
          f"({sum(f['bytes'] for f in files.values()) / 1e6:.1f} MB, "
          f"{sum(1 for f in files.values() if f['link'])} hardlinked)")
    print(f"  versions  {[v['version'] for v in m['versions']]}")
    ledger({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": "promote",
            "episode": a.episode, "version": vname, "parent": parent, "id": new_id,
            "seals": stage_seals, "live_untouched": not (other or drift),
            "episode_verdict": row.get("verdict")})
    return 0 if not (other or drift) else 1


# --------------------------------------------------------------- rollback ----

def cmd_rollback(a) -> int:
    m = load_manifest()
    if m is None:
        print("REFUSING: no learner manifest")
        return 1
    cur = next((v for v in m["versions"] if v["version"] == m["current"]), None)
    if cur is None or not cur.get("parent"):
        print(f"REFUSING: {m['current']} has no parent to roll back to")
        return 1
    target = cur["parent"]
    tver = next((v for v in m["versions"] if v["version"] == target), None)
    if tver is None:
        print(f"REFUSING: parent {target} is not in the manifest (pruned?)")
        return 1
    before = guard_live_files("rollback")
    live_at_start = live_seals()
    tmpcur = LL / "current.tmp"
    shutil.rmtree(tmpcur, ignore_errors=True)
    link_tree({n: VERSIONS / target / n for n in tver["seals"]}, tmpcur)
    actual = dir_seals(tmpcur)
    if actual != tver["seals"]:
        shutil.rmtree(tmpcur, ignore_errors=True)
        print(f"REFUSING: rebuilt current/ does not match {target}'s recorded seals: "
              f"{ {k: (tver['seals'].get(k), actual.get(k)) for k in set(tver['seals']) | set(actual) if tver['seals'].get(k) != actual.get(k)} }")
        return 1
    shutil.rmtree(CURRENT, ignore_errors=True)
    os.replace(tmpcur, CURRENT)
    m["current"] = target
    m.setdefault("rollbacks", []).append(
        {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": cur["version"],
         "to": target, "reason": a.reason})
    save_manifest(m)
    other, drift = finish_guard(before, live_at_start, "rollback")
    print(f"rolled back {cur['version']} -> {target}")
    print(f"  the rolled-back version is KEPT at versions/{cur['version']}")
    ledger({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": "rollback",
            "from": cur["version"], "to": target, "reason": a.reason,
            "live_untouched": not (other or drift)})
    return 0 if not (other or drift) else 1


# ----------------------------------------------------------------- verify ----

def cmd_verify(a) -> int:
    m = load_manifest()
    if m is None:
        print("no manifest")
        return 1
    ok = True
    cur = m["current"]
    ver = next((v for v in m["versions"] if v["version"] == cur), None)
    print(f"learner current: {cur}")
    if ver is None:
        print("  FAIL: current is not in the version list")
        return 1
    got = dir_seals(CURRENT)
    if got != ver["seals"]:
        ok = False
        print(f"  FAIL: current/ does not match its recorded seals: "
              f"{ {k: (ver['seals'].get(k), got.get(k)) for k in set(ver['seals']) | set(got) if ver['seals'].get(k) != got.get(k)} }")
    else:
        print(f"  ok: {len(got)} files match the manifest "
              f"({sum(p.stat().st_size for p in learner_files(CURRENT).values()) / 1e6:.1f} MB)")
    boot = m["bootstrapped_from"]["seals"]
    live = live_seals()
    if boot != live:
        # Not automatically a failure: the live animal may have been taught by the
        # house since bootstrap. But it MUST be reported, because the guarded
        # baseline was measured against the bootstrap state.
        diff = {k: (boot.get(k), live.get(k)) for k in set(boot) | set(live)
                if boot.get(k) != live.get(k)}
        print(f"  NOTE: live state has moved since bootstrap: {list(diff)}")
        print(f"        the guarded baseline was measured against the bootstrap state")
    else:
        print("  ok: live state is byte-identical to the bootstrap state, so the "
              "guarded baseline still describes it")
    chain, seen, v = [], set(), ver
    while v and v["version"] not in seen:
        seen.add(v["version"])
        chain.append(v["version"])
        v = next((x for x in m["versions"] if x["version"] == v.get("parent")), None)
    print(f"  chain: {' <- '.join(chain)}")
    for x in m["versions"]:
        p = VERSIONS / x["version"]
        if not p.exists():
            ok = False
            print(f"  FAIL: version {x['version']} is in the manifest but not on disk")
    print(f"  versions on disk: {len(m['versions'])}, rollbacks: {len(m.get('rollbacks') or [])}")
    print("VERIFY OK" if ok else "VERIFY FAILED")
    return 0 if ok else 1


def cmd_status(a) -> int:
    m = load_manifest()
    if m is None:
        print(f"no learner at {LL}; run --bootstrap")
        return 0
    print(f"learner: {LL}")
    print(f"  bootstrapped {m['bootstrapped_at']} from {m['bootstrapped_from']['root']} "
          f"(id {m['bootstrapped_from']['id']})")
    print(f"  current {m['current']}")
    for v in m["versions"]:
        acq = (v.get("acquisition") or {}).get("passed")
        print(f"    {v['version']:22s} parent {str(v['parent']):22s} "
              f"{v['source']:10s} episode {str(v.get('episode')):5s} "
              f"acq {acq if acq is not None else '-'}")
    print(f"  staging: {sorted(p.name for p in STAGING.glob('*')) if STAGING.exists() else []}")
    if LEDGER.exists():
        rows = [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
        print(f"  ledger: {len(rows)} entries, last {rows[-1]['action']} "
              f"{rows[-1].get('version') or rows[-1].get('to')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bootstrap", action="store_true",
                    help="create v0 from the live state; the live state is read, never written")
    ap.add_argument("--force", action="store_true",
                    help="with --bootstrap, start a new chain and orphan the old one")
    ap.add_argument("--promote", action="store_true")
    ap.add_argument("--episode", type=int, default=None)
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--reason", default="")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.bootstrap:
        return cmd_bootstrap(a)
    if a.promote:
        if a.episode is None:
            ap.error("--promote needs --episode N")
        return cmd_promote(a)
    if a.rollback:
        return cmd_rollback(a)
    if a.verify:
        return cmd_verify(a)
    return cmd_status(a)


if __name__ == "__main__":
    sys.exit(main())
