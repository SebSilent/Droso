"""C4 PROCESS AUDIT -- what an entry point can REACH, not what a module imports.

WHY THIS EXISTS. R11 (plan v1_2.md:146) forbids a donor execution "in the deployment loop or in any mechanism whose
output reaches an answer". The check that existed before this file asserted an IMPORT SURFACE: the two instruments
name no torch, no transformers, no numpy. That assertion is true, cheap and worth keeping -- and it cannot answer
the rule it is standing in for. An import surface is a property of a MODULE; R11 constrains a PROCESS. The same
`import torch` is a violation on one path and a sanctioned offline act on another, and a test that looks only at
module headers has no vocabulary for the difference: it must either forbid torch everywhere -- which fails on sight
of tools/mp_e8_arm_b.py, a legitimate offline training arm -- or allow it everywhere, which misses the leak it was
written to catch.

WHAT THIS AUDIT MODELS. A process is an entry point plus everything statically reachable from it. Two questions are
asked of that reachable set, independently, and the verdict is the CONJUNCTION:
  (1) does it reach a DONOR-EXECUTING node -- a call that runs a library as a computed function;
  (2) does it reach the ANSWER PATH -- the organ and its speak/decide chain.
A process that does both fails. A process that executes and never joins an answer is PERMITTED, and the permission
is granted by the graph, not by the label it carries: a process declared offline that in fact reaches an answer is
reported as a mismatch, not waved through. That is the whole difference between auditing a process and auditing a
path.

TWO WAYS THE AUDIT CAN BE WRONGED, BOTH HANDLED EXPLICITLY.
  * OUTPUT TRAVELS BY FILE, NOT ONLY BY IMPORT. "Any mechanism whose output reaches an answer" includes a benchmark
    that writes an artifact the organ later reads. No import edge exists; the answer is reached anyway. So the audit
    also joins WRITE paths to READ paths across processes and reports the intersection.
  * IT SEES STATICALLY ONLY. Function-level imports are followed; importlib and other dynamic loads are not, and
    are counted and reported as a named blind spot rather than silently absent. A dispatch by computed name is
    invisible, so reaching the module that OWNS the answer is treated as reaching the answer. The conservative
    direction is the only acceptable one for a safety gate.

SCOPE. R11's prohibition sentence is unqualified ("No forward pass ... no inference of any kind"); its first
sentence is donor-specific ("A frozen donor's weights are used in exactly two ways"). Those two readings do not
cover the same code, so the audit runs BOTH and reports both verdicts instead of choosing one -- choosing one is
D-MPE12-09, and that is the PI's ruling, not this file's.

STDLIB ONLY, BY NECESSITY. An audit that imports a donor runtime to detect one would be a false negative with a
traceback. Nothing here imports torch, transformers or numpy.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

SCHEMA_VERSION = "droso.c4_process_audit.v1"

# A donor-executing RUNTIME: a library whose presence in a reachable set means a model could be computed. numpy is
# deliberately NOT on this list. It is imported by thirteen files under organs/, the answer path's own substrate,
# so treating it as donor-executing would fail the audit on sight of the organ and train readers to ignore the
# gate. The weaker import-surface test keeps numpy for the address path, where it is a real constraint.
DONOR_RUNTIME_MODULES = ("torch", "transformers", "tensorflow", "tf", "flax", "jax", "onnx", "keras",
                         "accelerate", "bitsandbytes")

# The repository's own donor-executing calls, named rather than patterned, so the audit cannot be satisfied by
# renaming nothing and cannot fire on an unrelated function that happens to be called generate.
DONOR_EXEC_SYMBOLS = ("reference_inference", "reference_inference_run")

# Execution idioms. These count ONLY when the same reachable set also imports a donor runtime, which is what keeps
# tools/teach_episode.py's episode generator from reading as an inference loop.
EXEC_DIRECTIONS = ("forward", "generate", "sample", "autoregress", "inference", "__call__", "step", "predict")

# The answer path, named by its owners. neural_language.py is the organ; the four symbols are the speak/decide chain
# that turns state into a reply.
ANSWER_MODULE = "organs/neural_language.py"
ANSWER_SYMBOLS = ("answer", "respond", "speak", "speak_sentence", "speak_plan")
DEPLOYMENT_LOOP = "run_house.py"


class AuditConfig:
    """The audit over a TREE, not only over this repository.

    Item 2 of the brief requires the audit to prove it can tell the two categories apart BY CONSTRUCTION -- one
    synthetic allowed case, one synthetic forbidden case. That is only a proof if the same code that judges the real
    program judges the fixtures, so the tree, the answer module and the answer symbols are parameters rather than
    globals baked into the walk.
    """

    def __init__(self, root=None, answer_module=ANSWER_MODULE, answer_symbols=ANSWER_SYMBOLS,
                 deployment_loop=DEPLOYMENT_LOOP):
        self.root = Path(root) if root is not None else ROOT
        self.answer_module = answer_module
        self.answer_symbols = tuple(answer_symbols)
        self.deployment_loop = deployment_loop


DEFAULT_CONFIG = AuditConfig()


def _rel(p: Path, root=None) -> str:
    return p.relative_to(root or ROOT).as_posix()


def _resolve_import(frm: str, level: int, cur: Path, root: Path) -> str | None:
    """Resolve an import to a tracked file path, or None when it is third-party or unresolvable."""
    if level:
        base = cur.parent
        for _ in range(level - 1):
            base = base.parent
        parts = [x for x in frm.split(".") if x]
        cand = base.joinpath(*parts) if parts else base
    else:
        parts = [x for x in frm.split(".") if x]
        if not parts:
            return None
        cand = root.joinpath(*parts)
    for path in (cand.with_suffix(".py"), cand / "__init__.py"):
        if path.exists() and path.is_file():
            return _rel(path, root)
    return None


class ModuleNode:
    __slots__ = ("rel", "imports_first_party", "imports_runtime", "calls", "writes", "reads",
                 "dynamic_imports", "sink_calls", "exec_calls", "parse_error")

    def __init__(self, rel: str):
        self.rel = rel
        self.imports_first_party: set[str] = set()
        self.imports_runtime: set[str] = set()
        self.calls: set[str] = set()
        self.writes: set[str] = set()
        self.reads: set[str] = set()
        self.dynamic_imports = 0
        self.sink_calls: set[str] = set()
        self.exec_calls: set[str] = set()
        self.parse_error: str | None = None


def analyse(rel: str, cfg: AuditConfig = None) -> ModuleNode:
    cfg = cfg or DEFAULT_CONFIG
    node = ModuleNode(rel)
    path = cfg.root / rel
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        node.parse_error = f"{type(exc).__name__}: {exc}"
        return node
    cur = path

    def lit_str(n):
        return n if isinstance(n, str) else None

    def call_name(fn) -> str | None:
        if isinstance(fn, ast.Name):
            return fn.id
        if isinstance(fn, ast.Attribute):
            return fn.attr
        return None

    for st in ast.walk(tree):
        if isinstance(st, ast.Import):
            for a in st.names:
                top = a.name.split(".")[0]
                if top in DONOR_RUNTIME_MODULES:
                    node.imports_runtime.add(top)
                else:
                    r = _resolve_import(a.name, 0, cur, cfg.root)
                    if r:
                        node.imports_first_party.add(r)
        elif isinstance(st, ast.ImportFrom):
            mod = st.module or ""
            top = mod.split(".")[0] if mod else ""
            if not st.level and top in DONOR_RUNTIME_MODULES:
                node.imports_runtime.add(top)
                continue
            if not st.level and top and not (cfg.root / top).exists():
                continue
            r = _resolve_import(mod, st.level, cur, cfg.root)
            if r:
                node.imports_first_party.add(r)
            for a in st.names:
                node.calls.add(a.name)
        elif isinstance(st, ast.Call):
            nm = call_name(st.func)
            if nm:
                node.calls.add(nm)
            f = st.func
            if isinstance(f, ast.Attribute) and f.attr in ("import_module", "__import__"):
                node.dynamic_imports += 1
            if isinstance(f, ast.Name) and f.id == "open":
                mode = "r"
                if len(st.args) > 1 and isinstance(st.args[1], ast.Constant):
                    mode = str(st.args[1].value)
                tgt = lit_str(st.args[0].value) if (st.args and isinstance(st.args[0], ast.Constant)) else None
                if tgt:
                    (node.writes if any(c in mode for c in "wax+") else node.reads).add(tgt)
        elif isinstance(st, (ast.Assign, ast.AnnAssign)):
            pass

    node.sink_calls = {c for c in node.calls if c in cfg.answer_symbols}
    node.exec_calls = {c for c in node.calls if c in DONOR_EXEC_SYMBOLS or
                       (c in EXEC_DIRECTIONS and node.imports_runtime)}
    return node


def closure(entry_rel: str, cfg: AuditConfig = None, max_nodes: int = 4000) -> tuple[dict, list[str]]:
    """Transitive first-party reachability from an entry point. Returns (nodes, unresolved_edges)."""
    cfg = cfg or DEFAULT_CONFIG
    todo = [entry_rel]
    seen: dict[str, ModuleNode] = {}
    unresolved: list[str] = []
    while todo:
        rel = todo.pop()
        if rel in seen or len(seen) >= max_nodes:
            continue
        n = analyse(rel, cfg)
        seen[rel] = n
        if n.parse_error:
            unresolved.append(f"{rel} :: {n.parse_error}")
        for dep in sorted(n.imports_first_party):
            if dep not in seen:
                todo.append(dep)
    return seen, unresolved


def audit_process(entry_rel: str, declared: str | None = None, cfg: AuditConfig = None) -> dict:
    cfg = cfg or DEFAULT_CONFIG
    nodes, unresolved = closure(entry_rel, cfg)
    reaches_runtime = sorted({m for n in nodes.values() for m in n.imports_runtime})
    reaches_exec_symbols = sorted({c for n in nodes.values() for c in n.exec_calls})
    # TWO SIGNALS, KEPT APART ON PURPOSE. A reachable runtime is a CAPABILITY; an execution idiom actually called
    # is an ACT. Collapsing them makes the audit fire on tools/electric_learn_bench.py, which imports torch inside
    # torch_version() to read get_num_threads() and never runs a forward pass -- and an audit that reports a
    # thread-count as a donor execution gets ignored, which is worse than not existing. So the verdict has three
    # states: BREACH (act on a path that reaches an answer), EXPOSURE (capability on such a path, no act found --
    # a thing to review, not a thing to stop), CLEAR.
    reaches_execution_act = sorted({r for r, n in nodes.items() if n.exec_calls})
    reaches_donor_exec = bool(reaches_runtime or reaches_exec_symbols)
    sink_modules = sorted(r for r, n in nodes.items()
                          if r == cfg.answer_module or n.sink_calls)
    reaches_answer = (bool(sink_modules) or entry_rel == cfg.deployment_loop
                      or cfg.deployment_loop in nodes)

    donor_scoped = [r for r, n in nodes.items() if n.exec_calls]
    any_model = donor_scoped if not reaches_donor_exec else sorted(
        {r for r, n in nodes.items() if n.imports_runtime or n.exec_calls})

    if reaches_answer and reaches_execution_act:
        verdict = "BREACH"
    elif reaches_answer and reaches_donor_exec:
        verdict = "EXPOSURE"
    else:
        verdict = "CLEAR"
    derived = "answer_path" if reaches_answer else "disconnected_from_answer"
    mismatch = bool(declared) and declared in ("offline_benchmark", "offline_control") and reaches_answer

    return {
        "entry_point": entry_rel,
        "declared_category": declared,
        "modules_reachable": len(nodes),
        "reaches_donor_runtime_module": reaches_runtime,
        "reaches_donor_executing_symbol": reaches_exec_symbols,
        "donor_executing_capability": reaches_donor_exec,
        "donor_execution_act_modules": reaches_execution_act,
        "answer_path_modules_reached": sink_modules,
        "answer_path_reached": reaches_answer,
        "verdict": verdict,
        "verdict_rule": {"BREACH": "an execution act is reachable AND the answer path is reachable",
                        "EXPOSURE": "a donor runtime is reachable AND the answer path is reachable, but no "
                                    "execution act was found -- review, not stop",
                        "CLEAR": "neither half of R11's conjunction holds on this process"},
        "derived_category": derived,
        "declared_vs_derived_mismatch": mismatch,
        "donor_scoped_scope_hits": donor_scoped,
        "any_model_execution_scope_hits": any_model,
        "writes": sorted({p for n in nodes.values() for p in n.writes}),
        "reads": sorted({p for n in nodes.values() for p in n.reads})[:40],
        "dynamic_imports_unfollowed": sum(n.dynamic_imports for n in nodes.values()),
        "unresolved_edges": unresolved[:10],
    }


def join_report(processes: list[dict]) -> list[dict]:
    """A benchmark's output reaches an answer if the answer path reads a file the benchmark writes."""
    joins = []
    answer_reads = {p for pr in processes if pr["answer_path_reached"] for p in pr["reads"]}
    for pr in processes:
        if pr["answer_path_reached"]:
            continue
        hit = sorted(set(pr["writes"]) & answer_reads)
        if hit:
            joins.append({"process": pr["entry_point"], "writes_read_by_answer_path": hit})
    return joins


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--entries", default=None,
                    help="JSON {entry_point: declared_category}; defaults to the registered process set")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    default_entries = {
        DEPLOYMENT_LOOP: "answer_path",
        ANSWER_MODULE: "answer_path",
        "tools/mp_e12_probes.py": "offline_extraction",
        "tools/mp_e12_address_space.py": "offline_extraction",
        "tools/mp_e12_access_journal.py": "offline_extraction",
        "tools/mp_e12_preregister_latency_benchmark.py": "offline_benchmark",
        "tools/mp_e8_arm_b.py": "offline_control",
        "tools/mp_e8_arm_c.py": "offline_control",
        "tools/electric_learn_bench.py": "offline_benchmark",
        "tools/mp_e10_resource_ledger.py": "offline_control",
    }
    entries = json.loads(Path(args.entries).read_text(encoding="utf-8")) if args.entries else default_entries

    cfg = DEFAULT_CONFIG
    processes = [audit_process(e, declared=c, cfg=cfg) for e, c in sorted(entries.items())]
    joins = join_report(processes)
    fails = [p for p in processes if p["verdict"] == "BREACH"]
    exposures = [p for p in processes if p["verdict"] == "EXPOSURE"]

    # D-MPE12-09 IN STRUCTURE, NOT IN DECISION. The >=10x clause needs two things in one comparison: a read (the
    # numerator) and a donor execution (the denominator). Which processes can host the denominator, and can any of
    # them reach an answer? That is a graph question with a measured answer, and the answer is what makes the ruling
    # enforceable whichever way it goes -- this block does not choose a side.
    answer_procs = [p for p in processes if p["answer_path_reached"]]
    hosts = [p for p in answer_procs if p["donor_execution_act_modules"]]
    offline_executors = [p for p in processes if p["donor_execution_act_modules"] and not p["answer_path_reached"]]
    ten_x = {
        "clause": "H2 / the >=10x per-association read cost against autoregressive inference",
        "denominator_requires": "a donor-executing act in the same process that reports it",
        "answer_path_processes_audited": len(answer_procs),
        "answer_path_processes_able_to_host_the_denominator": len(hosts),
        "offline_executing_processes_audited": [p["entry_point"] for p in offline_executors],
        "if_the_ruling_is_no": "no donor-executing act is permitted anywhere, so the denominator cannot be produced "
                               "at all and the >=10x clause has no executable form in the program",
        "if_the_ruling_is_yes": "the denominator may be produced only by a process that never joins an answer, so "
                                "the ratio exists solely as an offline artifact; the answer path can never compute "
                                "it or carry it",
        "common_consequence": "under either ruling the >=10x claim has no executable form ON THE ANSWER PATH. The "
                              "only way it could get there is the file-mediated join this audit also checks, which "
                              "is why that check exists",
        "measured_no_answer_path_host": len(hosts) == 0,
    }

    report = {
        "schema_version": SCHEMA_VERSION,
        "audited_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rule_under_audit": {"id": "R11", "plan_line": "experiments/MP-E9/plan_extract/"
                                                        "DROSO_Master_Plan_v1_2.md:146"},
        "answer_path_definition": {"module": ANSWER_MODULE, "symbols": list(ANSWER_SYMBOLS),
                                   "deployment_loop": DEPLOYMENT_LOOP},
        "donor_executing_definition": {"runtime_modules": list(DONOR_RUNTIME_MODULES),
                                       "named_symbols": list(DONOR_EXEC_SYMBOLS),
                                       "execution_idioms_gated_on_runtime": list(EXEC_DIRECTIONS),
                                       "numpy_excluded_reason": ("imported by 13 files under organs/ -- the answer "
                                                                 "path's own substrate; treating it as donor-"
                                                                 "executing fails the audit on sight of the organ")},
        "blind_spots": ["dynamic imports (importlib/__import__) are counted, not followed",
                        "dispatch by computed name is invisible; reaching the module that owns the answer is "
                        "therefore treated as reaching the answer",
                        "cross-process flow through files is checked only for literal path strings"],
        "processes": processes,
        "cross_process_output_joins": joins,
        "counts": {"processes_audited": len(processes),
                   "breach": len(fails),
                   "exposure": len(exposures),
                   "clear": len(processes) - len(fails) - len(exposures),
                   "declared_vs_derived_mismatches": sum(1 for p in processes if p["declared_vs_derived_mismatch"]),
                   "dynamic_imports_unfollowed": sum(p["dynamic_imports_unfollowed"] for p in processes)},
        "breach_processes": [p["entry_point"] for p in fails],
        "exposure_processes": [p["entry_point"] for p in exposures],
        # A cross-process join is an EXPOSURE, not a proven breach: the file edge is real, but whether what comes
        # back through it is an execution or a duration is a question about the artifact, not the graph.
        "join_exposures": joins,
        "benchmark_process_category_under_R11_as_written": {
            "the_two_clauses_that_disagree": {
                "enumeration": "R11 sentence 1: a donor's weights are used in EXACTLY TWO ways -- compile reads and "
                               "live address reads. A benchmark is neither, so the enumeration does not authorise it.",
                "prohibition": "R11 sentence 2: no forward pass, loop, sampling or inference may sit in the "
                               "deployment loop or in any mechanism whose output reaches an answer. A benchmark "
                               "sits in neither, so the prohibition does not bar it.",
            },
            "category_as_written": "UNAUTHORISED BUT NOT BARRED -- outside the two sanctioned uses, outside the "
                                   "prohibited locations. R11 as written has no clause that decides it, which is "
                                   "why D-MPE12-09 is a ruling and not a reading.",
            "what_the_audit_does_with_that": "the audit enforces the prohibition clause mechanically, whichever way "
                                             "the enumeration clause is ruled: if the ruling permits an offline "
                                             "benchmark, the audit is the thing that proves it stays off the answer "
                                             "path; if the ruling forbids it, the audit is the thing that catches it",
            "sanctioned_control_arm_is_a_third_thing": "the text-distillation arm R11 names is sanctioned by the "
                                                       "rule itself and is a different act (it emits text to train "
                                                       "on); it is registered as offline_control and audited on the "
                                                       "same graph, not exempted by its name",
        },
        "d_mpe12_09_structural_position": ten_x,
        # "audit_verdict", not "verdict": every process carries a "verdict" too, and a ledger coordinate that
        # resolves to two different lines in one artifact is not a coordinate. The top-level word is the one the
        # gate reads, so it gets the unique name.
        "audit_verdict": ("BREACH" if fails else "EXPOSURE" if (exposures or joins) else "CLEAR"),
    }
    txt = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(txt + "\n", encoding="utf-8")
    print(txt)
    # Only a BREACH is a non-zero exit. EXPOSURE exits zero and prints, because it is a review queue: a gate that
    # fails on every torch import trains people to skip the gate.
    return 0 if report["audit_verdict"] in ("CLEAR", "EXPOSURE") else 1


if __name__ == "__main__":
    sys.exit(main())
