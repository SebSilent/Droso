"""Apply the admission report: bank the admitted mined primitives into the
live store (docs/mine_criteria.md §4).

This is the human-applied change the miner refuses to make (it is --dry-run
only by design). Default prints the plan and touches nothing; --apply writes
the store in the LearningLoop's own save format.

Per entry:
  key        mined_key(kind, wrapped, params) -- the fragment's own
             vocabulary (tools/rekey_mined.py), not the source task's. The
             first admission (2026-10-25) keyed fragments as
             signature(src_task) + " mined", which made each fragment's
             surface a strict superset of its source's: any query recalling
             the source scored the fragment identically and the margin gate
             read a tie, so the fragment shadowed its own source (measured:
             the flatten probe fell WIN -> TIE on banking). Re-keyed in
             place by tools/rekey_mined.py; new admissions use the same
             scheme from the start.
  task       the source task's own wording (§4: trigger text).
  code       the generalized fragment wrapped by the miner's own _wrap:
             params plus the literal holes (_c1, _c2) as defaulted
             keyword arguments, returning the last assigned name. The raw
             fragment is not a function; _functions_in would skip it and
             the compose lane -- the primary path per §4 -- would never
             see it.
  confidence 0.5. Plausible (the miner's verifier ran it clean on its
             synthetic cases) but below the trust floor (0.7), so it is
             never handed back as trusted; above the trial floor (0.35)
             and at the compose pool's >= 0.5 bar, so both existing lanes
             can reach it. No score bonus, no floor change (§4).
  successes  0. No task has accepted it yet; the verifier's "runs" is not
             a task success. The verify evidence stays in the report.

Faithfulness gate: before banking, every wrapped fragment is re-run on the
miner's synthetic inputs under the miner's own protocol (input as every
positional parameter, slots keep their defaults) and the OK outputs must
reproduce the report's recorded ones exactly. A mismatch aborts the whole
run -- a banked fragment that behaves differently from what was reviewed
must never enter the store.

"""
import argparse
import ast
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.mine_primitives import SYNTHETIC, Frag, _wrap  # noqa: E402
from tools.rekey_mined import mined_key  # noqa: E402

REPORT = Path("_tmp/mine_report.json")
STORE = Path("state/house_agent_learning.json")


def derive_last(code: str) -> str | None:
    """The miner's rule (mine_primitives.py:230-239) applied to the stored
    fragment: the last AugAssign target or append/extend/add receiver in the
    final statement, else the last earlier statement's assignment target."""
    stmts = ast.parse(code).body
    main, init = stmts[-1], stmts[:-1]
    last = None
    for sub in ast.walk(main):
        if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name):
            last = sub.target.id
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr in ("append", "extend", "add") and \
                isinstance(sub.func.value, ast.Name):
            last = sub.func.value.id
    if last is None and init:
        last = init[-1].targets[0].id
    return last


def reproduce(entry: dict, wrapped: str) -> tuple[bool, str]:
    """Re-run the wrapped fragment exactly as the miner's verifier did and
    require the OK outputs to match the report's recorded ones."""
    harness = (wrapped
               + f"\n\n_INPUTS = {SYNTHETIC!r}\n"
               + "import traceback\n"
               + "for _inp in _INPUTS:\n"
               + "    try:\n"
               + f"        _out = {entry['name']}(*[_inp] * "
               f"{max(len(entry['params']), 1)})\n"
               + "        print('OK', repr(_out)[:100])\n"
               + "    except Exception as _e:\n"
               + "        print('ERR', type(_e).__name__, str(_e)[:60])\n")
    import subprocess
    r = subprocess.run([sys.executable, "-c", harness],
                       capture_output=True, text=True, timeout=10)
    got = [ln[:110] for ln in (r.stdout or "").splitlines()
           if ln.startswith("OK")]
    want = [ok[:110] for ok in entry["verify"]["oks"]]
    # The report stores only the first three OK lines (mine_primitives.py:588),
    # so the recorded list is a prefix of the full run: the prefix must
    # reproduce exactly, in order.
    if got[:len(want)] != want:
        return False, f"oks differ:\n  want {want}\n  got  {got}"
    return True, f"oks reproduce (recorded prefix {len(want)}, run {len(got)})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the store; default reports only")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--store", default=str(STORE))
    args = ap.parse_args()

    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    admitted = report.get("admitted") or []
    if not admitted:
        print("no admitted entries in", args.report)
        return 2

    state = json.loads(Path(args.store).read_text(encoding="utf-8"))
    store = state["procedures"]

    mined = [rec for rec in store.values() if rec.get("source") == "mined"]
    if mined:
        print(f"refusing: store already holds {len(mined)} mined entries "
              "(double-apply guard)")
        return 2

    plan = []
    for e in admitted:
        last = derive_last(e["code"])
        frag = Frag(code=e["code"], kind=e["kind"], sigs=list(e["sigs"]),
                    params=list(e["params"]), slots=dict(e["slots"]),
                    last=last, store=e["store"], src_task=e["src_task"],
                    src_conf=e["src_conf"], name=e["name"],
                    verify=dict(e["verify"]), admit=e.get("admit", "admitted"))
        wrapped = _wrap(frag)
        compile(wrapped, e["name"], "exec")          # syntactic gate
        ok, why = reproduce(e, wrapped)
        key = mined_key(e["kind"], wrapped, list(e["params"]))
        clash = key in store
        plan.append((e, key, wrapped, ok, why, clash))

    print(f"{len(plan)} admitted entries, budget check against §5:")
    kinds: dict = {}
    for e, *_ in plan:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    for k, n in sorted(kinds.items()):
        flag = "OK" if n <= 4 else "OVER §5"
        print(f"  {k}: {n} (per-kind cap 4) {flag}")
    print(f"  total: {len(plan)} (cap 12) "
          f"{'OK' if len(plan) <= 12 else 'OVER §5'}")

    for e, key, wrapped, ok, why, clash in plan:
        print(f"[{'BANK' if ok and not clash else 'SKIP'}] {e['name']}"
              f" kind={e['kind']} key={key!r}")
        print(f"        {why}")
        if clash:
            print("        key already in store")

    if not args.apply:
        print("\nreport only; pass --apply to write the store")
        return 0

    if any(not ok or clash for _, _, _, ok, _, clash in plan):
        print("\nrefusing to apply: faithfulness or key-clash failures above")
        return 2

    now = time.time()
    for e, key, wrapped, *_ in plan:
        store[key] = {
            "signature": key,
            "task": e["src_task"],
            "tries": 0, "successes": 0, "failures": 0,
            "confidence": 0.5,
            "solutions": [{"text": wrapped, "truncated": False,
                           "ts": round(now, 3), "verified": False}],
            "source": "mined",
            "source_history": ["mined"],
            "created": now, "last_used": now,
            "last_evidence": "mined_verify",
            "language": "python",
        }
    state["saved"] = round(time.time(), 1)
    Path(args.store).write_text(
        json.dumps({"procedures": store, "adopted": state.get("adopted", {}),
                    "discarded": state.get("discarded", {}),
                    "min_confidence": state.get("min_confidence", 0.7),
                    "saved": state["saved"]},
                   indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(f"\napplied: {len(plan)} mined entries banked into {args.store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())