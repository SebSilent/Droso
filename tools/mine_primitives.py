"""Mine reusable primitives from the procedure stores.

Contract: docs/mine_criteria.md (frozen 2026-07-30). The miner reads only the
stores named in §1, the candidate-space constants of organs/reasoning_loop.py
(§2 dedupe), the criteria document, and an operator-supplied coverage-tasks
JSON (§7). It never reads the battery or held-out files. --dry-run only
reports; it writes nothing but its report under _tmp/.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

STORES = [("live", ROOT / "state" / "house_agent_learning.json"),
          ("seeder", ROOT / "exocortex" / "learned_procedures.json")]
SOURCE_KINDS = {"corpus", "local", "prim", "compose", "oracle",
                "reasoning_loop", "trial_replay"}
# §3: the fixed synthetic battery. One subprocess per fragment, timeout 10 s.
SYNTHETIC = ["droso", "Hello, World!", "", [1, 2, 3], [], [5, 5, 1],
             ["a", "b", "a"], 0, 1, 7, 13]
BUDGET_TOTAL, BUDGET_KIND, BUDGET_SOURCE = 12, 4, 2
_BUILTINS = set(dir(builtins))
_CLASS_PREDICATES = {"isalpha", "isdigit", "isspace", "isupper", "islower",
                     "isalnum"}
_SIG_ORDER = ["membership", "accumulate", "distinct-selection", "interleave",
              "char-shift", "DP"]


@dataclass
class Frag:
    code: str                    # the fragment, masked and unparsed (§2)
    kind: str = ""               # primary signature (first in §6 order)
    sigs: list = field(default_factory=list)
    params: list = field(default_factory=list)
    slots: dict = field(default_factory=dict)
    last: str | None = None      # name the wrapper returns
    store: str = ""
    src_sig: str = ""
    src_task: str = ""
    src_conf: float = 0.0
    norm: str = ""
    name: str = ""
    verify: dict = field(default_factory=dict)
    admit: str = ""              # admitted / rejected:<reason> / over_budget


STORE_STATS: dict = {}


# ---------------------------------------------------------------- lifting

def _mask(nodes: list) -> tuple[list, dict]:
    """Mask every literal to a slot; the original literal is the default (§2).
    Returns fresh AST copies plus the slot table."""
    slots: dict = {}

    def slot_for(value):
        for name, val in slots.items():
            if type(val) is type(value) and val == value:
                return name
        return f"_c{len(slots) + 1}"

    class M(ast.NodeTransformer):
        def visit_Constant(self, node):
            name = slot_for(node.value)
            slots.setdefault(name, node.value)
            return ast.copy_location(ast.Name(id=name, ctx=ast.Load()), node)

        def visit_JoinedStr(self, node):
            # An f-string's own literal parts and format specs are its text,
            # not parameterizable literals; mask only inside interpolations.
            for v in node.values:
                if isinstance(v, ast.FormattedValue):
                    self.visit(v.value)
            return node

    out = [M().visit(_parse(ast.unparse(n)).body[0]) for n in nodes]
    return out, slots


def _parse(code: str) -> ast.Module:
    """Parse stored code, silencing SyntaxWarnings from bad escapes in it."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return ast.parse(code)


def _canon(node: ast.AST) -> ast.AST:
    """Canonicalize non-builtin, non-slot names, for the normalized form."""
    mapping: dict = {}

    class C(ast.NodeTransformer):
        def visit_Name(self, node):
            if node.id in _BUILTINS or node.id.startswith("_c"):
                return node
            if node.id not in mapping:
                mapping[node.id] = f"n{len(mapping) + 1}"
            return ast.copy_location(ast.Name(id=mapping[node.id],
                                              ctx=node.ctx), node)

    return C().visit(node)


def _norm(stmts: list) -> str:
    """Normalized form: literals masked, names canonicalized (§2)."""
    masked, _ = _mask(stmts)
    mod = ast.Module(body=masked, type_ignores=[])
    return ast.dump(_canon(mod))


def _free_names(nodes: list) -> set:
    """Names read before any binding in the fragment (use-before-def aware).

    A name written only AFTER it is read (e.g. an accumulator seeded inside
    the first loop iteration) is still free: the fragment crashes without it.
    Compound statements are walked in execution order -- an Assign reads its
    value then binds its targets; a For reads its iterable, binds its target,
    then runs its body.
    """
    bound: set = set()
    free: set = set()

    def rd(node) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load) \
                    and sub.id not in bound:
                free.add(sub.id)

    def wr(node) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx,
                                                        (ast.Store, ast.Del)):
                bound.add(sub.id)

    def go(n) -> None:
        if isinstance(n, ast.Assign):
            rd(n.value)
            for t in n.targets:
                wr(t)
        elif isinstance(n, ast.AugAssign):
            if isinstance(n.target, ast.Name) and n.target.id not in bound:
                free.add(n.target.id)          # read side of `x += ...`
            rd(n.value)
            wr(n.target)
        elif isinstance(n, (ast.For, ast.AsyncFor)):
            rd(n.iter)
            wr(n.target)
            for s in n.body:
                go(s)
            for s in n.orelse:
                go(s)
        elif isinstance(n, ast.While):
            rd(n.test)
            for s in n.body:
                go(s)
            for s in n.orelse:
                go(s)
        elif isinstance(n, ast.If):
            rd(n.test)
            for s in n.body:
                go(s)
            for s in n.orelse:
                go(s)
        elif isinstance(n, ast.comprehension):
            rd(n.iter)
            wr(n.target)
            for i in n.ifs:
                rd(i)
        elif isinstance(n, ast.NamedExpr):
            rd(n.value)
            wr(n.target)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                            ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.ExceptHandler):
            if n.name:
                bound.add(n.name)
            rd(n.type)
            for s in n.body:
                go(s)
        elif isinstance(n, ast.withitem):
            rd(n.context_expr)
            if n.optional_vars is not None:
                wr(n.optional_vars)
        else:
            rd(n)

    for n in nodes:
        go(n)
    return free


def _has_return(nodes: list) -> bool:
    return any(isinstance(s, ast.Return) for n in nodes for s in ast.walk(n))


def _loop_frag(stmt, body: list, i: int, params: set) -> dict | None:
    """A loop with an accumulator, plus the simple assigns that seed it (§2)."""
    if _has_return([stmt]):
        return None                      # control-flow-bound, not an accumulator
    init = []
    j = i - 1
    loop_names = {n.id for n in ast.walk(stmt) if isinstance(n, ast.Name)}
    while j >= 0 and isinstance(body[j], ast.Assign) and \
            all(isinstance(t, ast.Name) for t in body[j].targets):
        names = {t.id for t in body[j].targets}
        if not (names & loop_names):
            break
        init.insert(0, body[j])
        loop_names |= names
        j -= 1
    stmts = init + [stmt]
    free = _free_names(stmts)
    if not free <= (params | _BUILTINS):
        return None                      # context-bound (§2)
    if not (free & params):
        return None                      # reads no parameter -> constant (§2)
    last = None
    for sub in ast.walk(stmt):
        if isinstance(sub, ast.AugAssign) and isinstance(sub.target, ast.Name):
            last = sub.target.id
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr in ("append", "extend", "add") and \
                isinstance(sub.func.value, ast.Name):
            last = sub.func.value.id
    if last is None and init:
        last = init[-1].targets[0].id
    return {"stmts": stmts, "params": sorted(free & params), "last": last}


def _count_idiom(stmt: ast.AST) -> bool:
    """d[x] = d.get(x, c) + 1 (§2d)."""
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return False
    t, v = stmt.targets[0], stmt.value
    if not (isinstance(t, ast.Subscript) and isinstance(v, ast.BinOp)
            and isinstance(v.op, ast.Add)):
        return False
    call = v.left
    return (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and call.func.attr == "get"
            and isinstance(call.func.value, ast.Subscript))


def lift(code: str) -> list[dict]:
    """Candidate fragments out of one solution, per §2."""
    try:
        tree = _parse(code)
    except SyntaxError:
        return [], 0
    fn = next((n for n in tree.body
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))), None)
    if fn is None:
        return [], 0
    params = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
    for extra in (fn.args.vararg, fn.args.kwarg):
        if extra:
            params.add(extra.arg)
    out, seen = [], set()
    n_bound = 0
    body = fn.body
    for i, stmt in enumerate(body):
        cands = []
        for node in ast.walk(stmt):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                                 ast.GeneratorExp)):
                free = _free_names([node])
                if free <= (params | _BUILTINS) and (free & params):
                    cands.append({"stmts": [node], "params":
                                  sorted(free & params), "last": None})
                else:
                    n_bound += 1
        if isinstance(stmt, (ast.For, ast.While)):
            cand = _loop_frag(stmt, body, i, params)
            if cand:
                cands.append(cand)
            else:
                n_bound += 1          # context-bound, constant, or return-bound
        if _count_idiom(stmt):
            free = _free_names([stmt])
            if free <= (params | _BUILTINS) and (free & params):
                tgt = stmt.targets[0]
                base = tgt.value.id if isinstance(tgt.value, ast.Name) else None
                cands.append({"stmts": [stmt], "params": sorted(free & params),
                              "last": base})
            else:
                n_bound += 1
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            free = _free_names([stmt.value])
            if free <= (params | _BUILTINS) and (free & params):
                cands.append({"stmts": [stmt.value], "params":
                              sorted(free & params), "last": None})
            else:
                n_bound += 1
        for c in cands:
            if not c:
                continue
            # Dedupe like-for-like: the wrapper appends `return last`, and the
            # existing space's shapes are full bodies ending in return, so the
            # normalized form of a fragment with an accumulator includes it.
            norm_stmts = list(c["stmts"])
            if c["last"]:
                norm_stmts.append(ast.Return(value=ast.Name(id=c["last"],
                                                            ctx=ast.Load())))
            norm = _norm(norm_stmts)
            if norm in seen:
                continue
            seen.add(norm)
            masked, slots = _mask(c["stmts"])
            c["code"] = "\n".join(ast.unparse(m) for m in masked)
            c["slots"] = slots
            c["norm"] = norm
            out.append(c)
    return out, n_bound


# ------------------------------------------------------- kind signatures (§6)

def _signatures(stmts: list) -> list:
    sigs, has_ord, has_chr = set(), False, False
    appends, loops, count_dicts, selects, dp = 0, 0, 0, 0, False
    for n in stmts:
        for sub in ast.walk(n):
            if isinstance(sub, ast.Call):
                f = sub.func
                if isinstance(f, ast.Attribute):
                    if f.attr in _CLASS_PREDICATES:
                        sigs.add("membership")
                    if f.attr in ("append", "extend", "add"):
                        appends += 1
                if isinstance(f, ast.Name):
                    if f.id == "ord":
                        has_ord = True
                    if f.id == "chr":
                        has_chr = True
                    if f.id in ("max", "min") and any(
                            kw.arg == "key" for kw in sub.keywords):
                        selects += 1
            elif isinstance(sub, ast.Compare):
                if isinstance(sub.ops[0], ast.In) and \
                        isinstance(sub.comparators[0], ast.Constant) and \
                        isinstance(sub.comparators[0].value, str):
                    sigs.add("membership")
                for o, c in zip(sub.ops, sub.comparators):
                    if isinstance(o, ast.Eq) and \
                            isinstance(c, ast.Constant) and c.value == 1:
                        selects += 1
            elif isinstance(sub, (ast.For, ast.While)):
                loops += 1
            if _count_idiom(sub):
                count_dicts += 1
            if isinstance(sub, ast.Subscript) and \
                    isinstance(sub.value, ast.Subscript):
                dp = True
    if loops and appends:
        sigs.add("accumulate")
        if appends >= 2:
            sigs.add("interleave")
    if count_dicts and (selects or appends == 0):
        sigs.add("distinct-selection")
    if has_ord and has_chr:
        sigs.add("char-shift")
    if dp:
        sigs.add("DP")
    return [s for s in _SIG_ORDER if s in sigs]


# ------------------------------------------------------------ existing space

def _existing_space() -> set:
    """Normalized bodies of PRIMITIVES/HINTS/HINT_PAIRS/PROGRAM_SHAPES (§2).
    The constants are read by parsing the source (PROGRAM_SHAPES is local to
    the 5b generator, so no import is needed or wanted)."""
    src = (ROOT / "organs" / "reasoning_loop.py").read_text(encoding="utf-8")
    consts: dict = {}
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in (
                        "PRIMITIVES", "HINTS", "HINT_PAIRS", "PROGRAM_SHAPES"):
                    consts[t.id] = ast.literal_eval(node.value)
    bodies = [b for _, b in consts.get("PRIMITIVES", ())]
    bodies += [b for _, b in consts.get("HINTS", ())]
    bodies += [b for _, _, b in consts.get("HINT_PAIRS", ())]
    bodies += [b.replace("{c}", "True").replace("{e}", "x")
               for _, b, _ in consts.get("PROGRAM_SHAPES", ())]
    norms = set()
    for b in bodies:
        src = textwrap.dedent(b).strip()
        if src.startswith("return "):
            src = src[len("return "):]
        try:
            tree = _parse(src)
        except SyntaxError:
            continue
        stmts = tree.body[0].body if isinstance(tree.body[0],
                                                ast.FunctionDef) else tree.body
        norms.add(_norm(stmts))
        for node in ast.walk(ast.Module(body=stmts, type_ignores=[])):
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp,
                                 ast.GeneratorExp)):
                norms.add(_norm([node]))
    return norms


# ----------------------------------------------------------------- verify §3

def _wrap(f: Frag) -> str:
    args = ", ".join(f.params + [f"{s}={f.slots[s]!r}" for s in f.slots])
    body = textwrap.indent(f.code, "    ")
    ret = f"\n    return {f.last}" if f.last else ""
    return f"def {f.name}({args}):\n{body}{ret}"


def _verify(f: Frag) -> dict:
    """§3: one subprocess per fragment, timeout 10 s. The harness passes the
    input as every positional parameter (a fixed, mechanical choice, applied
    to every fragment alike); slots keep their defaults."""
    harness = (_wrap(f)
               + f"\n\n_INPUTS = {SYNTHETIC!r}\n"
               + "import traceback\n"
               + f"for _inp in _INPUTS:\n"
               + "    try:\n"
               + f"        _out = {f.name}(*[_inp] * {max(len(f.params), 1)})\n"
               + "        print('OK', repr(_out)[:100])\n"
               + "    except Exception as _e:\n"
               + "        print('ERR', type(_e).__name__, str(_e)[:60])\n")
    try:
        r = subprocess.run([sys.executable, "-c", harness],
                           capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        return {"ok": False, "clean": 0, "oks": [], "errs": ["timeout"],
                "detail": ""}
    oks, errs = [], []
    for line in (r.stdout or "").splitlines():
        if line.startswith("OK"):
            oks.append(line[:110])
        elif line.startswith("ERR"):
            errs.append(line[:110])
    clean = len(oks)
    return {"ok": clean >= 3, "clean": clean, "oks": oks, "errs": errs[:4],
            "detail": (r.stderr or "")[-200:]}


# ------------------------------------------------------------------- stores

def load_sources() -> list:
    """§1: the source corpus, both stores inventoried and kept separate."""
    out = []
    for store, path in STORES:
        data = json.loads(path.read_text(encoding="utf-8"))
        recs = data.get("procedures", {})
        stats = {"entries": len(recs), "by_source": {}, "selected": 0}
        for sig, rec in recs.items():
            src = str(rec.get("source") or "?")
            stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
            if rec.get("language") != "python" or src not in SOURCE_KINDS:
                continue
            sols = [s for s in (rec.get("solutions") or [])
                    if s.get("verified") and str(s.get("text") or "").strip()]
            if not sols:
                continue
            stats["selected"] += 1
            out.append({"store": store, "sig": sig, "rec": rec,
                        "code": sols[-1]["text"],
                        "conf": float(rec.get("confidence") or 0.0)})
        STORE_STATS[store] = stats
    return out


# ------------------------------------------------------------------ pipeline

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--coverage", default=str(ROOT / "_tmp" /
                                              "coverage_tasks.json"))
    ap.add_argument("--out", default=str(ROOT / "_tmp" / "mine_report.json"))
    args = ap.parse_args()
    if not args.dry_run:
        print("refusing: only --dry-run is implemented; admission is a "
              "later, logged change (criteria §8)")
        return 2

    sources = load_sources()
    existing = _existing_space()
    frags: list[Frag] = []
    rejected = {"context_bound_or_constant": 0, "dup_existing": 0,
                "dup_mined": 0, "verify_fail": 0, "no_signature": 0}
    verify_failed: list = []
    for s in sources:
        cands, n_bound = lift(s["code"])
        rejected["context_bound_or_constant"] += n_bound
        for c in cands:
            if c["norm"] in existing:
                rejected["dup_existing"] += 1
                continue
            if any(c["norm"] == g.norm for g in frags):
                rejected["dup_mined"] += 1
                continue
            sigs = _signatures(c["stmts"])
            if not sigs:
                rejected["no_signature"] += 1   # outside the six kinds (§6)
                continue
            frags.append(Frag(code=c["code"], sigs=sigs,
                              kind=sigs[0] if sigs else "",
                              params=c["params"], slots=c["slots"],
                              last=c["last"], store=s["store"],
                              src_sig=s["sig"],
                              src_task=str(s["rec"].get("task") or ""),
                              src_conf=s["conf"], norm=c["norm"]))
    live = []
    for i, f in enumerate(frags):
        slug = re.sub(r"[^a-z0-9]+", "_", f.src_task.lower()).strip("_")[:24]
        f.name = f"mined_{slug or 'frag'}_{i}"
        f.verify = _verify(f)
        if f.verify["ok"]:
            live.append(f)
        else:
            f.admit = "rejected:verify"
            rejected["verify_fail"] += 1
            if len(verify_failed) < 8:
                verify_failed.append({"name": f.name, "code": f.code,
                                      "errs": f.verify.get("errs", [])})
    # §5 budget: source confidence desc, then fragment size asc
    cand = sorted(live, key=lambda f: (-f.src_conf, len(f.code)))
    admitted, per_kind, per_src = [], {}, {}
    for f in cand:
        if len(admitted) >= BUDGET_TOTAL:
            f.admit = "over_budget"
            continue
        k = f.kind or "(none)"
        if per_kind.get(k, 0) >= BUDGET_KIND:
            f.admit = "over_budget"
            continue
        key = (f.store, f.src_sig)
        if per_src.get(key, 0) >= BUDGET_SOURCE:
            f.admit = "over_budget"
            continue
        per_kind[k] = per_kind.get(k, 0) + 1
        per_src[key] = per_src.get(key, 0) + 1
        f.admit = "admitted"
        admitted.append(f)

    # §7 coverage, refused and fresh sets, from the operator-supplied JSON
    coverage: dict = {}
    tasks: list = []
    try:
        tasks = json.loads(Path(args.coverage).read_text(encoding="utf-8"))
    except Exception as e:
        coverage["error"] = f"{type(e).__name__}: {e}"
    for t in tasks:
        words = set(re.findall(r"[a-z]{4,}", str(t.get("task") or "").lower()))
        hits = []
        for f in admitted:
            if t.get("kind") not in f.sigs:
                continue
            tw = set(re.findall(r"[a-z]{4,}", f.src_task.lower()))
            if words & tw:
                hits.append(f.name)
        coverage.setdefault(t.get("set") or "refused", []).append(
            {"name": t.get("name"), "kind": t.get("kind"),
             "covered": bool(hits), "by": hits})

    report = {
        "criteria": "docs/mine_criteria.md (frozen 2026-07-30)",
        "inventory": STORE_STATS,
        "sources_selected": len(sources),
        "fragments_lifted": len(frags),
        "rejections": rejected,
        "admitted": [{"name": f.name, "kind": f.kind, "sigs": f.sigs,
                      "params": f.params, "slots": f.slots, "store": f.store,
                      "src_task": f.src_task, "src_conf": f.src_conf,
                      "code": f.code,
                      "verify": {"clean": f.verify.get("clean"),
                                 "oks": f.verify.get("oks", [])[:3],
                                 "errs": f.verify.get("errs", [])}}
                     for f in admitted],
        "over_budget": [{"name": f.name, "kind": f.kind,
                         "src_task": f.src_task}
                        for f in live if f.admit == "over_budget"],
        "verify_failed_sample": verify_failed,
        "coverage": coverage,
    }
    Path(args.out).write_text(json.dumps(report, indent=1, default=str),
                              encoding="utf-8")
    print(f"sources: {len(sources)}  fragments: {len(frags)}  "
          f"admitted: {len(admitted)}  rejected: {rejected}")
    for f in admitted:
        print(f"  {f.name}  kind={f.kind or '(none)'}  "
              f"clean={f.verify.get('clean')}/11  src={f.src_task[:40]}")
    for setname, rows in coverage.items():
        if setname == "error":
            continue
        n = sum(1 for r in rows if r["covered"])
        print(f"coverage[{setname}]: {n}/{len(rows)}")
        for r in rows:
            print(f"  {'Y' if r['covered'] else 'N'} {r['name']} "
                  f"({r['kind']}) <- {', '.join(r['by']) or '-'}")
    print(f"report -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())