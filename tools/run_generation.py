r"""One generation of brains, scored on one battery, with lineage.

WHY THIS IS NOT tools/fly_v2.py. That runner searches a genome of five weights
over a SYNTHETIC component (span-head matching on material it generates itself)
and never puts a fly in front of an ask. The log records what that bought: the
fitness surface peaked one mutation from the base, the winner overfitted a closed
modifier class, and the one time a bred rule was landed in the organ it scored
exactly the baseline. It also records the worse failure -- `tools/_genome_patch.py`
supplied a filler where the organ's matcher had returned None, converting a veto
into an answer, and the resulting 7/24 was withdrawn as a capability claim.

So this harness holds three rules that the previous one did not:

  1. NOTHING IS PATCHED. A genome is a set of scalars the organ and the core
     ALREADY read. Applying one sets attributes; it never replaces a method, and
     it never intercepts a refusal. `shim_check()` asserts the organ's matcher is
     still its own before every brain is scored, because a shim that answers
     where the organ refused scores the absence of a guard as capability.
  2. EVERY GENE IS READ BACK. `apply_genome` returns what it set and
     `verify_genome` reads it off the built brain again. A gene that cannot be
     verified refuses the brain instead of scoring it. The record therefore says
     which parameters actually ran, not which ones were requested.
  3. FITNESS IS A TUPLE AND SELECTION IS LEXICOGRAPHIC. No weighted sum. The
     first term is a hard constraint -- zero frozen passes lost -- and the
     generalisation term is a LABEL that can disqualify a winner, never a number
     that can compensate for one. A composite is how the previous surface came to
     have its ceiling on the incumbent's first neighbour.

Live state is read-only: every brain is built by converse.build(), which seals
the learning loop, blocks the oracle, turns books off and re-points every
persistence path into a session directory. The state tree is snapshotted before
the generation and checked after; any moved file fails the run.

  py -3.10 tools/run_generation.py --snapshot
  py -3.10 tools/run_generation.py --generation 0 --lines 3
  py -3.10 tools/run_generation.py --freeze-baseline --generation 0
  py -3.10 tools/run_generation.py --generation 1 --lines 3 --tier frozen --only exact-repeat
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import organs.neural_language as nl  # noqa: E402
from connectome.engine import HybridEngineParams  # noqa: E402
from connectome.rate_core import CoreParams  # noqa: E402
from tools.converse import (  # noqa: E402
    Session, build, guard_check, guard_live_files, _said, _spoken, _words)
from tools.heldout_eval import grade, stage_of  # noqa: E402

FROZEN_TASKS = ROOT / "tools" / "scripts_heldout.json"
PROBE_TASKS = ROOT / "tools" / "scripts_selection.json"
BASELINE = ROOT / "tools" / "selection_baseline.json"
SEL_DIR = ROOT / "state" / "selection"
# The ask journal is written here DURING a run and published to SEL_DIR only
# after the state guard has passed. state/sessions/ is inside the guard's own
# exclusion list, so the harness's incremental writes cannot be read as the
# harness damaging the state it is supposed to be protecting.
SCRATCH = ROOT / "state" / "sessions" / "_selection"

SCHEMA = 1


# ------------------------------------------------------------------ genes ----
# A GENE is a scalar the code sets once at construction and never restores from
# persisted state. That line is not taste: `social_drive` is also a number on the
# language organ, but load_state() writes it back (neural_language.py:4419), so
# setting it would not survive a restart and it could not be inherited. Values on
# the far side of that line are TEACHING HISTORY and belong in provenance, sealed
# by hash, never mutated.

PLASTICITY_GENES = tuple(CoreParams.__dataclass_fields__)
ENGINE_PARAM_GENES = tuple(HybridEngineParams.__dataclass_fields__)
SEED_GENES = ("engine_seed", "ratecore_seed")
ANSWER_INSTANCE_GENES = ("ANSWER_COVERAGE_FLOOR", "reply_threshold",
                         "reply_drive_min", "max_sentence_words",
                         "speech_temperature", "phrase_threshold")
# Read as module globals inside the organ's methods, so setting one is
# PROCESS-WIDE: it moves every brain in the interpreter. Restored after each
# brain, and a mutation run that touches one should use --isolate.
ANSWER_MODULE_GENES = ("FRESH_TAU_S", "FRESH_FLOOR_S", "SAN_ROW_CAP",
                       "SAN_TOP_K", "HEBB_LR", "SAN_DECAY_PER_S")
SUBSTRATE_GENES = ("control", "seed", "row_gain", "n_actions")

# Build-time genes are recorded and verified but NOT mutable in this step.
# Changing them means constructing a different carve, and the only two routes are
# editing build_house_agent (core code, out of scope by instruction) or pre-seeding
# world.reasoning_agent._BANC_GRAPH from a tool -- which is the shape of move that
# produced the withdrawn 7/24. A genome that asks for a non-base build-time gene is
# REFUSED, not silently scored as if it had been applied.
BUILD_TIME = {"substrate": SUBSTRATE_GENES,
              "decision": ENGINE_PARAM_GENES}


def birth_genes() -> dict:
    """The base genome, read from the DEFINITIONS rather than from a built brain.

    `epsilon` and `temperature` are mutated in place by every decision
    (rate_core.py:119-120), so a value read off a lived core is a value already
    partway to its floor. Birth values come from the dataclasses, which is what
    RateCore.__init__ installs when no params are passed -- and build_house_agent
    passes none.
    """
    cp, ep = CoreParams(), HybridEngineParams()
    return {
        "substrate": {"control": False, "seed": 0, "row_gain": 0.5,
                      "n_actions": 12},
        "plasticity": {k: getattr(cp, k) for k in PLASTICITY_GENES},
        "decision": {**{k: getattr(ep, k) for k in ENGINE_PARAM_GENES},
                     "engine_seed": 0, "ratecore_seed": 0},
        "answer": {},          # filled by snapshot(): organ-side, no dataclass
    }


# ------------------------------------------------------------- mutation ----
# ONE operator, pre-registered in docs/selection_design.md section 8 before any
# mutant existed, and the whitelist is the pre-registration: adding a gene is a
# code change with a dated entry in that file, not a flag on the command line.
# A harness that can be pointed at any scalar is a harness whose operator was
# chosen after someone saw what would win.

MUTATIONS = {
    "answer.ANSWER_COVERAGE_FLOOR": {
        "section": "answer",
        "gene": "ANSWER_COVERAGE_FLOOR",
        "base": 0.6,
        "sigma": 0.05,
        "bounds": (0.45, 0.75),
        "why": "two of the five frozen failures are stage=recall, and that stage "
               "IS this floor refusing (best_cov < ANSWER_COVERAGE_FLOOR in "
               "answer()), so the gene bites from the base rather than only in a "
               "context the base is not in",
    },
}


def mutate(parent: dict, key: str, rng) -> tuple:
    """One gene, one bounded Gaussian draw. Returns (genome, mutation record).

    The draw perturbs the PARENT's value, not the declared base, which is the
    difference between a lineage and a resampling of one point; at generation 1
    the two coincide because the parent is at the base. The record carries the raw
    draw, the pre-clip value and the clip flag, so a mutant sitting on a bound is
    visibly sitting on a bound instead of looking like a lucky sample.
    """
    if key not in MUTATIONS:
        raise KeyError(
            f"{key!r} is not a pre-registered mutation. Whitelisted: "
            f"{sorted(MUTATIONS)}. Adding one is a code change with a dated entry "
            f"in docs/selection_design.md, not a flag.")
    spec = MUTATIONS[key]
    section, gene = spec["section"], spec["gene"]
    cur = float(parent["genes"][section][gene])
    lo, hi = spec["bounds"]
    draw = rng.gauss(0.0, float(spec["sigma"]))
    raw = cur + draw
    val = round(min(hi, max(lo, raw)), 6)
    child = json.loads(json.dumps(parent, default=str))
    child["genes"][section][gene] = val
    child["genes"] = _normalise(child["genes"])
    child["genome_id"] = gid(child["genes"])
    child["parent_genome_id"] = parent["genome_id"]
    child["operator"] = f"gauss:{key}"
    rec = {"operator": "gauss_single_gene", "gene": key,
           "pre_registered": "docs/selection_design.md section 8",
           "parent_value": cur, "declared_base": spec["base"],
           "sigma": float(spec["sigma"]), "draw": round(draw, 6),
           "raw": round(raw, 6), "value": val,
           "delta": round(val - cur, 6), "bounds": [lo, hi],
           "clipped": bool(raw < lo or raw > hi)}
    return child, rec


def lineage_of(genome_id: str, parent_id) -> list:
    """Walk the parent chain back through every committed generation file.

    A lineage that stops at this generation's parent is a lineage of length two
    forever, which is fine at generation 1 and useless at generation 8. The walk
    reads the published rows rather than a separate index, so there is no second
    record to drift.
    """
    parent_of = {}
    for p in sorted(SEL_DIR.glob("generation_*.jsonl")):
        if p.name.endswith("_asks.jsonl"):
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    r = json.loads(line)
                    parent_of.setdefault(r.get("genome_id"), r.get("parent_genome_id"))
        except (OSError, ValueError):
            continue
    # The walk starts from the EXPLICIT parent, not from a lookup of the child.
    # A mutant being scored for the first time is not in any published file yet, so
    # parent_of.get(child) is None and the chain came back as [child] -- a lineage
    # of length one that never names the parent it was derived from. The first
    # generation of mutants exposed it; docs/evidence/verify_generation1.py is what
    # caught it.
    chain, seen, cur = [genome_id], {genome_id}, parent_id
    while cur and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        cur = parent_of.get(cur)
    return list(reversed(chain))


def cull(rows: list, control_row) -> dict:
    """The pre-registered selection rule, and the three outcomes it can produce.

    Eligibility is the hard constraint from section 3: zero frozen passes lost and
    zero guarded probes lost, both measured against the FROZEN BASELINE. Ranking is
    against the CONTROL's key measured in this same generation, not against
    generation 0's numbers, because the control is the parent re-measured under
    today's conditions and the difference between the two is the instrument.

    Ties go to the parent. Changing the animal for no measured gain is not a
    neutral act -- it is a new genome in the lineage that has to be carried, and
    the log already books 'landed and verified, zero score movement, no capability
    point' as its own outcome rather than as a win.
    """
    mutants = [r for r in rows if r is not control_row]

    def _eligible(r):
        reg = r["fitness"].get("regression") or {}
        if reg.get("frozen_lost_n", 1) != 0 or reg.get("probe_guard_lost"):
            return False
        # The phrasing_fitted veto, made real. Section 3 says a labelled line cannot
        # be declared a winner; a label nothing reads is a comment, not a rule. This
        # is the one place the paraphrase tier is allowed to change an outcome, and
        # it can only ever remove a winner.
        return not any(str(x).startswith("phrasing_fitted")
                       for x in (r["fitness"].get("labels") or []))

    eligible = [r for r in mutants if _eligible(r)]
    ctrl_key = list(control_row["fitness"]["select_key"]) if control_row else [0, 0, 0]
    better = [r for r in eligible if list(r["fitness"]["select_key"]) > ctrl_key]
    if better:
        win = max(better, key=lambda r: (list(r["fitness"]["select_key"]), r["line"]))
        outcome, survivor = "survivor", win
    elif eligible:
        outcome, survivor = "no_gain", control_row
    else:
        outcome, survivor = "stall", control_row
    return {
        "outcome": outcome,
        "survivor_line": survivor["line"] if survivor else None,
        "survivor_genome_id": survivor["genome_id"] if survivor else None,
        "control_key": ctrl_key,
        "mutants": len(mutants),
        "eligible": [r["line"] for r in eligible],
        "ineligible": [{"line": r["line"],
                        "frozen_lost": (r["fitness"].get("regression") or {}).get("frozen_lost"),
                        "probe_guard_lost": (r["fitness"].get("regression") or {}).get("probe_guard_lost"),
                        "phrasing_fitted": [x for x in (r["fitness"].get("labels") or [])
                                            if str(x).startswith("phrasing_fitted")]}
                       for r in mutants if r not in eligible],
        "better_than_control": [r["line"] for r in better],
        "rule": "survivor must lose zero frozen passes and zero guarded probes; "
                "ties and no-gain keep the parent; if no mutant is eligible the "
                "generation is a stall and the parent stands",
        "stall_rule": "do not lower sigma, widen the whitelist, add lines or soften "
                      "the guard to make a climb possible (docs/selection_design.md "
                      "section 8)",
    }


def canon(genes: dict) -> str:
    return json.dumps(genes, sort_keys=True, separators=(",", ":"))


def gid(genes: dict) -> str:
    """The lineage key. A function of the GENES only: provenance describes the
    brain a genome ran on and changes when the lived state changes, so hashing it
    would give one behaviour two ids and break the parent chain."""
    return hashlib.sha256(canon(genes).encode("utf-8")).hexdigest()[:12]


def seal(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def snapshot(agent) -> dict:
    """Read a genome off a built brain. Organ-side scalars are observed here
    (they are set once in __init__ and never restored, so as-found IS birth);
    core-side scalars come from birth_genes()."""
    genes = birth_genes()
    lang = agent.language
    genes["answer"] = {
        **{k: getattr(lang, k) for k in ANSWER_INSTANCE_GENES},
        **{k: getattr(nl, k) for k in ANSWER_MODULE_GENES},
    }
    genes = _normalise(genes)
    return {"schema": SCHEMA, "genes": genes, "genome_id": gid(genes),
            "provenance": observe(agent)}


def _normalise(genes: dict) -> dict:
    """numpy scalars and bools into plain JSON types, so canon() is stable and a
    genome round-trips through a file byte-identically."""
    out = {}
    for section, vals in genes.items():
        clean = {}
        for k, v in vals.items():
            if isinstance(v, (np.bool_,)):
                v = bool(v)
            elif isinstance(v, np.integer):
                v = int(v)
            elif isinstance(v, np.floating):
                v = float(v)
            elif isinstance(v, float):
                v = round(v, 9)
            clean[k] = v
        out[section] = clean
    return out


def observe(agent) -> dict:
    """Provenance: what this brain actually is. Not genes -- read-backs and
    digests, recorded so two brains built on different lived state are never
    compared as if they were the same animal."""
    eng, lang = agent.engine, agent.language
    g = eng.graph
    cp = CoreParams()
    san_nnz = int(np.count_nonzero(lang.san_w)) if hasattr(lang, "san_w") else None
    return {
        "substrate": {k: g.meta.get(k) for k in
                      ("control", "seed", "row_gain", "n_static_edges",
                       "n_plastic_edges")},
        "n_nodes": int(g.n_nodes),
        "plastic_synapses": int(len(eng.static.w)),
        # The two volatile core scalars as the build left them. Equal to birth on
        # an untouched build (measured: decisions == 0 after converse.build); a
        # difference here means something ran decisions during construction and
        # the birth-value assumption is wrong.
        "as_found": {"epsilon": float(eng.static.p.epsilon),
                     "temperature": float(eng.static.p.temperature),
                     "decisions": int(eng.decisions),
                     "birth_epsilon": float(cp.epsilon),
                     "birth_temperature": float(cp.temperature)},
        # TEACHING HISTORY, sealed not mutated. These are the LIVE files the build
        # read, not lang.state_path -- converse.build re-points that into the
        # session directory, so sealing it would digest a file that does not exist
        # yet and report null for the one thing that identifies which lifetime this
        # brain was built on.
        "teaching_history": {
            "vocabulary": len(lang.word_patterns),
            "binder_rows": int(lang.cortex.binder.X.shape[0]),
            "propositions": len(lang.cortex.binder.meta),
            "san_nnz": san_nnz,
            "bigrams": int(sum(lang.bigram_counts.values())),
            "persons": len(lang.persons),
            "question_roles": len(lang.question_roles),
            "answer_types": len(lang.answer_types),
            "live_state": {p.name: (seal(p) if p.exists() else None)
                           for p in (ROOT / "state" / "language_state.json",
                                     ROOT / "state" / "banc_brain.npz")},
        },
    }


# ------------------------------------------------------------------ apply ----

WATCHED_METHODS = ("_shape_matches", "_question_shape", "_arbitrate_shape",
                   "_provenance_vote", "answer", "respond")


def _organ_file() -> str:
    import os
    return os.path.normcase(os.path.realpath(nl.__file__))


def shim_check() -> dict:
    """Assert the answer path is the organ's own code, by NAME and by SOURCE FILE.

    `tools/_genome_patch.py` replaces NeuralLanguage._shape_matches with a closure
    named `patched` AT IMPORT TIME, and docs/STATE.md:59 records it as moved out of
    tools/ while the file is present and tracked. Trusting either the doc or the
    absence of an import is how a veto override gets scored as capability, so the
    check is on the object itself and runs before every brain.

    The name alone is not enough and a test proved it: a wrapper that happens to be
    called `answer` -- or one under functools.wraps, which copies the name -- sails
    through a name check while running somebody else's code. So the deciding test
    is `__code__.co_filename`: the function object has to have been compiled from
    organs/neural_language.py. A replacement defined in a tool, a test or a shim
    cannot satisfy that whatever it calls itself.
    """
    import os
    want_file = _organ_file()
    out = {"clean": True, "watched": {}, "offenders": []}
    for attr in WATCHED_METHODS:
        fn = nl.NeuralLanguage.__dict__.get(attr)
        code = getattr(fn, "__code__", None)
        src = os.path.normcase(os.path.realpath(code.co_filename)) if code else None
        name = getattr(fn, "__name__", None)
        out["watched"][attr] = {"name": name, "file": src, "line":
                                getattr(code, "co_firstlineno", None)}
        if fn is None or code is None or src != want_file or name != attr:
            out["clean"] = False
            out["offenders"].append(
                f"{attr}: name={name!r} file={src!r} (expected {attr!r} in "
                f"{want_file!r})")
    if not out["clean"]:
        raise RuntimeError(
            "the language organ's answer path is not its own code: "
            + "; ".join(out["offenders"])
            + " -- refusing to score. A patched matcher can answer where the organ "
              "refused, and that scores the absence of a guard as capability.")
    return out


def _set_and_read(agent, section: str, key: str, value):
    """Write one gene, then read it back through the same path. Returns
    (applied_value, touched_module_global)."""
    eng, lang = agent.engine, agent.language
    if section == "plasticity":
        setattr(eng.static.p, key, value)
        return getattr(eng.static.p, key), False
    if section == "decision":
        if key == "engine_seed":
            agent.engine.rng = np.random.default_rng(int(value))
            return int(value), False
        if key == "ratecore_seed":
            eng.static.rng = np.random.default_rng(int(value))
            return int(value), False
        return getattr(eng.params, key), False     # build-time: read only
    if section == "substrate":
        # n_actions lives on the graph, the rest in its meta; both are read back so
        # the record says which carve ran rather than which one was asked for.
        if key == "n_actions":
            return int(eng.graph.n_actions), False
        return eng.graph.meta.get(key), False
    if section == "answer":
        if key in ANSWER_INSTANCE_GENES:
            setattr(lang, key, value)
            return getattr(lang, key), False
        setattr(nl, key, value)
        return getattr(nl, key), True
    raise KeyError(f"unknown gene {section}.{key}")


def apply_genome(agent, genome: dict, base: dict) -> dict:
    """Set every gene, read it back, and refuse the brain on any mismatch.

    `base` is the snapshot of the committed brain. A BUILD-TIME gene that differs
    from base is refused here rather than ignored: silently scoring a genome whose
    substrate genes were never applied is the same class of dishonesty as the shim,
    only quieter.
    """
    genes = genome["genes"]
    applied, mismatch, process_wide, refused = {}, [], [], []
    for section in ("substrate", "plasticity", "decision", "answer"):
        for key, want in sorted(genes.get(section, {}).items()):
            if section in BUILD_TIME and key in BUILD_TIME[section]:
                have = base["genes"][section][key]
                if _ne(want, have):
                    refused.append(f"{section}.{key}={want!r} (build-time, base "
                                   f"is {have!r}; not mutable in this step)")
                applied.setdefault(section, {})[key] = have
                continue
            got, module_wide = _set_and_read(agent, section, key, want)
            if module_wide:
                process_wide.append(f"{section}.{key}")
            applied.setdefault(section, {})[key] = got
            if _ne(got, want):
                mismatch.append(f"{section}.{key}: wanted {want!r}, read back {got!r}")
    return {"applied": applied, "mismatch": mismatch,
            "process_wide": process_wide, "refused": refused,
            "ok": not (mismatch or refused)}


def _ne(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return bool(a) != bool(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > 1e-9
    return a != b


def restore_module_genes(saved: dict) -> None:
    for k, v in saved.items():
        setattr(nl, k, v)


# --------------------------------------------------------------- battery ----

def load_battery(tiers: tuple, only: str | None, open_batch=None,
                 retained_batches=()) -> list:
    """The frozen tier is READ FROM tools/scripts_heldout.json at runtime, never
    copied. A copy is a second contract that can drift from the first, and then
    'zero frozen passes lost' would be measured against whatever the copy said.

    The OPEN tier is the fourth tier of docs/open_learning_design.md section 5: a
    batch GENERATED per episode by tools/teach_episode.py, in the same script/turn
    schema as the other three so it runs through the same runner, the same grader and
    the same journal. It is reported and never selected on -- select_key does not
    read it, for the reason section 3 gives for keeping the paraphrase tier out of
    the key: a term in the key is a gradient.
    """
    out = []
    if "frozen" in tiers:
        for s in json.loads(FROZEN_TASKS.read_text(encoding="utf-8"))["scripts"]:
            out.append({"tier": "frozen", "script": s, "parent": s["name"]})
    if "probe" in tiers:
        for s in json.loads(PROBE_TASKS.read_text(encoding="utf-8"))["scripts"]:
            out.append({"tier": "probe", "script": s, "parent": s.get("parent")})
    if "open" in tiers:
        if not open_batch:
            raise SystemExit("--tier open needs --open-batch PATH: the open tier is "
                             "generated per episode, there is no committed default")
        p = Path(open_batch)
        if not p.exists():
            raise SystemExit(f"no open batch at {p}")
        for s in json.loads(p.read_text(encoding="utf-8"))["scripts"]:
            out.append({"tier": "open", "script": s, "parent": s.get("parent")})
    # RETAINED: an earlier episode's acquisition asks, put to a LATER learner. This is
    # the tier that makes promotion measurable -- without it a chained episode shows
    # only that it can learn new facts, not that the facts already promoted survived,
    # which is the entire reason a persistent learner is worth having.
    for rb in retained_batches or ():
        p = Path(rb)
        if not p.exists():
            raise SystemExit(f"no retained batch at {p}")
        for s in json.loads(p.read_text(encoding="utf-8"))["scripts"]:
            if s["name"] != "open-acquisition":
                continue          # only the taught form; held-out frames belong to
            for t in s["turns"]:  # the episode that generated them
                t["frame"] = "retained-" + p.parent.name
            out.append({"tier": "retained", "script": s, "parent": None})
    if only:
        out = [e for e in out if only in e["script"]["name"]]
    return out


def ask_id(script_name: str, ask: str) -> str:
    """The same id form heldout_eval journals, so a selection row and a campaign
    row name the same ask and the two records can be diffed."""
    return f"{script_name}::{ask}"


def run_ask(entry: dict, index: int, genome: dict, base: dict, tag: str,
            project_root=None) -> dict:
    """One ask against one freshly built brain carrying `genome`.

    Independent mode, for the reason heldout_eval gives: the tells that precede the
    ask are replayed into a new build and only that ask is put to it, so nothing an
    earlier ask did can move this number. The genome is applied BEFORE the tells,
    because the tells are part of the behaviour under selection -- they are where
    the Hebbian and binder genes do their work.
    """
    script = entry["script"]
    step = script["turns"][index]
    sd = SCRATCH / f"{tag}_{script['name']}_{index}"
    if sd.exists():
        shutil.rmtree(sd)
    t0 = time.time()
    err = None
    rec = {}
    agent = None
    try:
        # project_root is None for the frozen/guarded tiers, which are always
        # measured against the LIVE state so their numbers stay comparable to the
        # committed baseline. An open-tier episode passes its shadow, so the asks are
        # put to the state the teaching actually produced -- a cross-process
        # measurement, which is what makes it a retention test rather than a
        # same-session recall test.
        agent = build(sd, project_root=project_root)
        # Only the verdict rides in the journal; the per-method file and line map is
        # 126 copies of the same six strings.
        _shim = shim_check()
        shim = {"clean": _shim["clean"], "offenders": _shim["offenders"]}
        ap = apply_genome(agent, genome, base)
        if not ap["ok"]:
            return {"tier": entry["tier"], "script": script["name"],
                    "id": ask_id(script["name"], step.get("ask", "")),
                    "ask": step.get("ask"), "pass": False, "stage": "genome_refused",
                    "said": "", "why": "; ".join(ap["mismatch"] + ap["refused"])[:300],
                    "seconds": round(time.time() - t0, 2), "genome_applied": False,
                    "shim": shim}
        sess = Session(agent, beats=0)
        for st in script["turns"][:index]:
            if "say" in st:
                sess.ask(st["say"], kind="tell")
        t = sess.ask(step["ask"], kind="ask")
        r = t.get("reply") or {}
        words = _words(_said(t))
        ok, why = grade(words, _spoken(t), step.get("expect") or {})
        rec = {"tier": entry["tier"], "script": script["name"],
               "parent": entry["parent"],
               "id": ask_id(script["name"], step["ask"]),
               "probe": step.get("probe"), "rewords": step.get("rewords"),
               "frame": step.get("frame"), "taught": step.get("taught"),
               "ask": step["ask"], "said": _said(t)[:120], "words": words[:24],
               "spoken": _spoken(t), "pass": bool(ok), "why": why,
               "stage": None if ok else stage_of(t, why),
               "source": r.get("source"), "filler": r.get("recovered_filler"),
               "reason": r.get("reason"),
               # Raw recall diagnostics, recorded for EVERY ask and not just
               # failures, because a passing ask's coverage is the only way to
               # know where the gate actually sits for the asks that work.
               # `coverage` is the fraction of the cue's content words the best
               # binder posting covers; `required` is the word list it demanded
               # (empty means the cue reached no posting at all, which is a
               # different failure from a posting that scored too low);
               # `nearest` is the organ's own top-3 postings with their scores.
               # These three are what distinguishes "no memory", "memory the cue
               # cannot reach" and "memory refused by a threshold" -- without
               # them all three report stage=recall and look identical.
               "coverage": r.get("coverage"),
               "required": r.get("required"),
               "nearest": r.get("nearest"),
               "genome_applied": True, "shim": shim,
               "seconds": round(time.time() - t0, 2)}
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}"[:200]
        rec = {"tier": entry["tier"], "script": script["name"],
               "parent": entry["parent"],
               "id": ask_id(script["name"], step.get("ask", "")),
               "probe": step.get("probe"), "ask": step.get("ask"),
               "said": "", "spoken": False, "pass": False, "why": err,
               "stage": "engine_error", "error": err,
               "genome_applied": False,
               "seconds": round(time.time() - t0, 2)}
    finally:
        if agent is not None:
            del agent
        shutil.rmtree(sd, ignore_errors=True)
        gc.collect()
    return rec


# ---------------------------------------------------------------- fitness ----

def stage_distribution(rows: list) -> dict:
    out = {}
    for r in rows:
        if not r["pass"]:
            k = r.get("stage") or "unknown"
            out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def fitness_tuple(rows: list, baseline: dict | None, seals: dict) -> dict:
    """The four terms, kept separate on purpose.

    There is no scalar fitness and no weighted sum. `select_key` is lexicographic
    with a hard constraint first, and the generalisation term is a LABEL: it can
    disqualify a line that gained, it can never pay for a line that lost.
    """
    frozen = [r for r in rows if r["tier"] == "frozen"]
    probes = [r for r in rows if r["tier"] == "probe"]
    opened = [r for r in rows if r["tier"] == "open"]
    f_pass = sorted(r["id"] for r in frozen if r["pass"])
    p_pass = sorted(r["id"] for r in probes if r["pass"])

    out = {
        "capability": {
            "tier": "frozen", "asked": len(frozen), "passed": len(f_pass),
            "score": round(len(f_pass) / len(frozen), 4) if frozen else None,
            "pass_set": f_pass,
            "failures": [{"id": r["id"], "stage": r["stage"], "why": r["why"],
                          "said": r["said"]} for r in frozen if not r["pass"]],
        },
        # Stages over the GUARDED battery only. Mixing the open tier in would let a
        # batch of freshly generated asks reshape the failure map that generations 0-2
        # are comparable on, and the map's whole use is that it does not move unless
        # the animal does.
        "stages": stage_distribution(frozen + probes),
        "seals": seals,
    }
    retained = [r for r in rows if r["tier"] == "retained"]
    if retained:
        # An earlier episode's taught facts, asked of a later learner. Reported beside
        # the open tier and, like it, never selected on.
        out["retained"] = {
            "asked": len(retained),
            "passed": sum(1 for r in retained if r["pass"]),
            "score": round(sum(1 for r in retained if r["pass"]) / len(retained), 4),
            "pass_set": sorted(r["id"] for r in retained if r["pass"]),
            "stages": stage_distribution(retained),
            "lost": [{"id": r["id"], "stage": r["stage"], "said": r["said"]}
                     for r in retained if not r["pass"]],
        }
    if opened:
        # Reported, never selected on. `frame` is the rewording family the generator
        # declared for each ask, so a generalisation number can be attributed to a
        # phrasing class instead of being one lump.
        by_frame = {}
        for r in opened:
            k = str(r.get("frame") or "?")
            d = by_frame.setdefault(k, [0, 0])
            d[1] += 1
            d[0] += 1 if r["pass"] else 0
        out["open"] = {
            "asked": len(opened),
            "passed": sum(1 for r in opened if r["pass"]),
            "score": round(sum(1 for r in opened if r["pass"]) / len(opened), 4),
            "pass_set": sorted(r["id"] for r in opened if r["pass"]),
            "by_frame": {k: {"passed": v[0], "asked": v[1]}
                         for k, v in sorted(by_frame.items())},
            "stages": stage_distribution(opened),
            "failures": [{"id": r["id"], "stage": r["stage"], "why": r["why"],
                          "said": r["said"]} for r in opened if not r["pass"]],
        }

    if baseline is None:
        # No frozen baseline yet: the probe pool has not been split, so there is
        # nothing to guard and nothing to generalise against. This is the state of
        # generation 0, and saying so is the point -- the split is a PRODUCT of
        # the clone run, not an input to it.
        out["regression"] = {"verdict": "no baseline",
                             "reason": "tools/selection_baseline.json absent; run "
                                       "--freeze-baseline after generation 0"}
        out["generalisation"] = {"verdict": "no baseline", "probe_asked": len(probes),
                                 "probe_passed": len(p_pass), "probe_pass_set": p_pass}
        out["select_key"] = [1, len(f_pass), len(p_pass)]
        out["labels"] = ["baseline-run"]
        return out

    # Only asks this line ACTUALLY RAN can be lost. A chunked or --only run covers
    # fewer asks than the baseline, and charging it for the ones it never asked is
    # the exact error heldout_eval.compare() was hardened against: coverage read as
    # movement. The unrun set is reported so a partial run is visibly partial.
    ran = {r["id"] for r in frozen}
    base_pass = set(baseline["frozen_pass_set"])
    lost = sorted((base_pass & ran) - set(f_pass))
    not_run = sorted(base_pass - ran)
    guard_ids = set(baseline["regression_pass_set"])
    para_ids = set(baseline["paraphrase_set"])
    guard = [r for r in probes if r["id"] in guard_ids]
    para = [r for r in probes if r["id"] in para_ids]
    guard_lost = sorted(r["id"] for r in guard if not r["pass"])
    guard_pass = sorted(r["id"] for r in guard if r["pass"])
    para_pass = sorted(r["id"] for r in para if r["pass"])

    out["regression"] = {
        "frozen_lost": lost, "frozen_lost_n": len(lost),
        "frozen_baseline_n": len(base_pass),
        "frozen_guarded_and_run": len(base_pass & ran),
        "frozen_not_run": not_run,
        "probe_guard_asked": len(guard),
        "probe_guard_passed": sum(1 for r in guard if r["pass"]),
        "probe_guard_lost": guard_lost,
        # The set, not just the count: a guarded probe that changed has to be
        # nameable, or "did any guarded probe move" can only be answered by a
        # number that cannot say which.
        "probe_guard_pass_set": sorted(r["id"] for r in guard if r["pass"]),
        "score": (round(sum(1 for r in guard if r["pass"]) / len(guard), 4)
                  if guard else None),
        "verdict": "clean" if not (lost or guard_lost) else "LOST",
    }
    out["generalisation"] = {
        "asked": len(para), "passed": len(para_pass),
        "score": round(len(para_pass) / len(para), 4) if para else None,
        "pass_set": para_pass,
        "seal": seals.get("probes"),
        "seal_matches_baseline": seals.get("probes") == baseline.get("probe_seal"),
    }
    # The third term is the GUARDED probe count, not the paraphrase count, and the
    # difference is the whole of "do not train on generalisation probes". A term in
    # the key is a gradient: whatever it rewards, selection will eventually find.
    # The paraphrase tier is therefore allowed to appear in this function only in
    # the DEMOTING direction -- phrasing_fitted below, and the generalisation report
    # -- because a set that can only ever cost a line the win and never earn it one
    # gives selection no reason to fit it. Asymmetry is the mechanism, not a caveat:
    # promoting on held-out probes burns them, vetoing on them does not.
    out["select_key"] = [1 if not (lost or guard_lost) else 0,
                         len(f_pass), len(guard_pass)]
    labels = []
    if lost or guard_lost:
        labels.append("regression")
    if not_run or len(guard) < len(guard_ids):
        # The line did not cover the baseline. Its select_key is still computed,
        # but it is not comparable to a full line's and must not be ranked against
        # one -- a chunk that ran four asks cannot claim it lost nothing.
        labels.append("partial-run")
    if not out["generalisation"]["seal_matches_baseline"]:
        # The probe file moved after the baseline was frozen. Every generalisation
        # number in this row is about a different instrument than the baseline's.
        labels.append("probe-seal-broken")
    labels += phrasing_fitted(rows, baseline)
    out["labels"] = labels
    return out


def phrasing_fitted(rows: list, baseline: dict) -> list:
    """Name every frozen gain whose own paraphrases still fail.

    A paraphrase probe records the frozen ask it rewords, so a gain can be checked
    against the rewordings of THAT ask rather than against the tier's average. A
    mutant that lifts `what did i tell you about before the kettle?` while both of
    its rewordings still fail has fitted a phrasing, and under a weighted sum that
    trade would be a number someone could take. Here it is a label on the row, and
    section 3 of the design doc makes a labelled line ineligible to win.

    Only gains are labelled. A frozen ask that already passed at base has no
    paraphrase obligation -- the regression tier covers it -- and an ask that still
    fails has gained nothing to be suspicious of.
    """
    base_pass = set(baseline.get("frozen_pass_set") or [])
    by_probe = {}
    for r in rows:
        if r["tier"] == "probe" and r.get("rewords"):
            by_probe.setdefault(r["rewords"], []).append(r)
    out = []
    for r in rows:
        if r["tier"] != "frozen" or not r["pass"] or r["id"] in base_pass:
            continue
        sibs = by_probe.get(r["ask"]) or []
        if sibs and not any(s["pass"] for s in sibs):
            out.append(f"phrasing_fitted:{r['ask'][:48]}")
    return out


# ------------------------------------------------------------- generation ----

CODE_FLAGS = {}


def git_provenance() -> dict:
    def git(*a):
        try:
            return subprocess.run(["git", *a], cwd=str(ROOT), capture_output=True,
                                  text=True, timeout=30).stdout.strip()
        except Exception:
            return ""
    return {"head": git("rev-parse", "--short", "HEAD"),
            "dirty": bool(git("status", "--porcelain")),
            "python": platform.python_version(),
            "numpy": np.__version__,
            # Code-level flags are recorded beside the interpreter and the git head
            # because they are the same kind of fact: two arms of an A/B carry the SAME
            # genome, so the flag is the only thing that distinguishes them, and a row
            # that did not record it would make the two arms indistinguishable in the
            # record and the comparison unattributable.
            "code_flags": dict(CODE_FLAGS),
            "frozen_seal": seal(FROZEN_TASKS),
            "probes_seal": seal(PROBE_TASKS)}


def evaluate_line(gen: int, line_no: int, genome: dict, base: dict,
                  battery: list, journal: Path, baseline: dict | None,
                  limit: int | None, project_root=None) -> dict:
    tag = f"g{gen}-{line_no}"
    t0 = time.time()
    rows = []
    n = 0
    for entry in battery:
        idxs = [i for i, s in enumerate(entry["script"]["turns"]) if "ask" in s]
        for i in idxs:
            if limit is not None and n >= limit:
                break
            rec = run_ask(entry, i, genome, base, tag, project_root=project_root)
            rec.update({"generation": gen, "line": tag,
                        "genome_id": genome["genome_id"]})
            rows.append(rec)
            n += 1
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, default=str) + "\n")
            print(f"   [{tag}] {rec['tier']:6s} {n:3d} "
                  f"{'PASS' if rec['pass'] else 'fail'}  "
                  f"{(rec.get('ask') or '')[:44]:44s} "
                  f"stage={rec.get('stage') or '-'}  ({rec['seconds']:.0f}s)",
                  flush=True)
        if limit is not None and n >= limit:
            break

    prov = git_provenance()
    seals = {"frozen": prov.pop("frozen_seal"), "probes": prov.pop("probes_seal")}
    fit = fitness_tuple(rows, baseline, seals)
    row = {"generation": gen, "line": tag,
           "genome_id": genome["genome_id"],
           "parent_genome_id": genome.get("parent_genome_id"),
           "lineage": lineage_of(genome["genome_id"],
                                 genome.get("parent_genome_id")),
           "operator": genome.get("operator", "clone"),
           # The mutation in full: the gene, the parent's value, the raw draw, the
           # sigma it came from, the clip and the bounds. A winner whose delta is
           # not in the record is a winner nobody can reproduce.
           "mutation": genome.get("mutation"),
           "genome": genome["genes"],
           "genome_verified": bool(rows) and all(r.get("genome_applied") for r in rows),
           # Every build is checked for a patched matcher before it is scored, and
           # the line is clean only if all of them were. A line with no shim check
           # at all is not clean, it is unmeasured.
           "shim_clean": bool(rows) and all(
               bool((r.get("shim") or {}).get("clean")) for r in rows),
           "provenance": {**prov, **genome.get("provenance", {})},
           "fitness": fit,
           "asks": len(rows),
           "seconds": round(time.time() - t0, 1)}
    return row


def publish(gen: int, rows: list, journal: Path) -> Path:
    SEL_DIR.mkdir(parents=True, exist_ok=True)
    out = SEL_DIR / f"generation_{gen}.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, default=str) + "\n")
    shutil.copyfile(journal, SEL_DIR / f"generation_{gen}_asks.jsonl")
    return out


def movement(row: dict, control: dict) -> dict:
    """What moved between this line and the control, in the terms the
    pre-registration asks about.

    A diff of two measurements, not an interpretation: stage counts subtracted, and
    the guarded / paraphrase / frozen pass sets differenced as sets so a changed ask
    is NAMED rather than summarised as a count. `frozen_lost_vs_control` is not the
    same number as `regression.frozen_lost` -- the first is against this run's
    control, the second against the frozen baseline, which is the contract. Both are
    reported because they can disagree, and when they do the disagreement is the
    instrument moving between generations.
    """
    cs, ms = control["fitness"]["stages"], row["fitness"]["stages"]
    delta = {k: ms.get(k, 0) - cs.get(k, 0) for k in sorted(set(cs) | set(ms))}

    def _set(fit, term, key):
        return set((fit.get(term) or {}).get(key) or [])

    cg, mg = (_set(control["fitness"], "regression", "probe_guard_pass_set"),
              _set(row["fitness"], "regression", "probe_guard_pass_set"))
    cp, mp = (_set(control["fitness"], "generalisation", "pass_set"),
              _set(row["fitness"], "generalisation", "pass_set"))
    cf = set(control["fitness"]["capability"]["pass_set"])
    mf = set(row["fitness"]["capability"]["pass_set"])
    return {
        "stage_delta": {k: v for k, v in delta.items() if v},
        "recall_delta": delta.get("recall", 0),
        "recall_moved_out": delta.get("recall", 0) < 0,
        "guard_gained": sorted(mg - cg), "guard_lost": sorted(cg - mg),
        "guard_changed": bool((mg - cg) or (cg - mg)),
        "paraphrase_gained": sorted(mp - cp), "paraphrase_lost": sorted(cp - mp),
        "paraphrase_changed": bool((mp - cp) or (cp - mp)),
        "frozen_gained": sorted(mf - cf),
        "frozen_lost_vs_control": sorted(cf - mf),
    }


def print_culling(decision: dict, rows: list) -> None:
    print("\n=== SELECTION ===")
    print(f"  rule     : {decision['rule']}")
    print(f"  control  : {decision['control_line']}  key={decision['control_key']}")
    for r in rows:
        mv = r.get("mutation")
        tag = f"{mv['gene']}={mv['value']}" if mv else "parent, unmutated"
        reg = r["fitness"].get("regression") or {}
        m = r.get("movement") or {}
        print(f"  {r['line']:6s} {r['genome_id']:13s} {tag:34s} "
              f"key={r['fitness']['select_key']} "
              f"lost={reg.get('frozen_lost')} "
              f"guard_lost={reg.get('probe_guard_lost')} "
              f"recall{m.get('recall_delta', 0):+d}")
    print(f"  eligible : {decision['eligible'] or 'none'}")
    print(f"  better   : {decision['better_than_control'] or 'none'}")
    print(f"  OUTCOME  : {decision['outcome']} -> survivor "
          f"{decision['survivor_line']} ({decision['survivor_genome_id']})")
    if decision["outcome"] == "stall":
        print(f"  stall rule: {decision['stall_rule']}")
    print("\n=== MOVEMENT vs the control ===")
    for r in rows:
        m = r.get("movement")
        if not m:
            continue
        print(f"  {r['line']:6s} stages {json.dumps(m['stage_delta']) or 'unchanged'}")
        print(f"         frozen gained {m['frozen_gained'] or '-'}  "
              f"lost vs control {m['frozen_lost_vs_control'] or '-'}")
        print(f"         guarded probes changed: "
              f"{('YES gained ' + str(m['guard_gained']) if m['guard_gained'] else '')}"
              f"{(' YES lost ' + str(m['guard_lost']) if m['guard_lost'] else '')}"
              f"{'' if m['guard_changed'] else 'no'}")
        print(f"         paraphrase probes changed: "
              f"{('gained ' + str(m['paraphrase_gained'])) if m['paraphrase_gained'] else ''}"
              f"{(' lost ' + str(m['paraphrase_lost'])) if m['paraphrase_lost'] else ''}"
              f"{'' if m['paraphrase_changed'] else 'no'}")


def print_generation(rows: list) -> None:
    print("\n=== GENERATION ===")
    print(f"{'line':8s} {'genome_id':13s} {'frozen':>9s} {'probes':>9s} "
          f"{'guard':>9s}  {'verdict':14s} labels")
    for r in rows:
        f = r["fitness"]
        cap, reg, gen = f["capability"], f.get("regression") or {}, \
            f.get("generalisation") or {}
        if "probe_asked" in gen:            # no baseline: the pool is unsplit
            probes = f"{gen.get('probe_passed')}/{gen.get('probe_asked')}"
            guard = "-"
        else:
            probes = f"{gen.get('passed', 0)}/{gen.get('asked', 0)}"
            guard = f"{reg.get('probe_guard_passed', 0)}/{reg.get('probe_guard_asked', 0)}"
        print(f"{r['line']:8s} {r['genome_id']:13s} "
              f"{cap['passed']:4d}/{cap['asked']:<4d} {probes:>9s} {guard:>9s}  "
              f"{reg.get('verdict', '-')} "
              f"{','.join(f.get('labels') or []) or '-'}")
    print("\nFAILURE STAGES per line:")
    for r in rows:
        print(f"  {r['line']:8s} {json.dumps(r['fitness']['stages'])}")
    by_genome = {}
    for r in rows:
        by_genome.setdefault(r["genome_id"], []).append(r)
    print(f"\ngenome ids in this generation: {len(by_genome)} "
          f"({'ONE genome, clones' if len(by_genome) == 1 else 'distinct genomes'})")
    for g in sorted(by_genome):
        print(f"  {g}  {[r['line'] for r in by_genome[g]]}")

    # NOISE and GENE EFFECT are different things and must not share a label.
    # Disagreement between lines carrying the SAME genome is the instrument. An ask
    # that differs between DIFFERENT genomes is the gene doing what it was mutated
    # to do. The first version of this block pooled every line together and printed
    # a mutation's real effect as "UNSTABLE across identical genomes ... the
    # instrument's noise floor" -- generation 2 did exactly that to the scarf
    # invariant, which is the one mislabelling that could get a genuine regression
    # dismissed as jitter.
    noise = set()
    for g, grp in by_genome.items():
        if len(grp) > 1:
            s = [set(r["fitness"]["capability"]["pass_set"]) for r in grp]
            noise |= set().union(*s) - set.intersection(*s)
    allsets = [set(r["fitness"]["capability"]["pass_set"]) for r in rows]
    inter = set.intersection(*allsets) if allsets else set()
    union = set().union(*allsets) if allsets else set()
    print(f"MEMBERSHIP: {len(inter)} asks passed in every line, "
          f"{len(union)} in at least one")
    if noise:
        print(f"  NOISE ({len(noise)}): differs between lines carrying the SAME "
              f"genome -- this is the instrument, not a capability difference")
        for u in sorted(noise):
            print(f"     {u}")
    else:
        print("  noise: none. Every genome's lines agree ask for ask, so the "
              "instrument is reproducible at the level of the ask, not just the "
              "score")
    if len(by_genome) > 1:
        ref = by_genome[sorted(by_genome, key=lambda g: -len(by_genome[g]))[0]]
        base_set = set.intersection(*[set(r["fitness"]["capability"]["pass_set"])
                                      for r in ref]) if ref else set()
        for r in rows:
            s = set(r["fitness"]["capability"]["pass_set"])
            gained, lost = sorted(s - base_set), sorted(base_set - s)
            if gained or lost:
                mv = r.get("mutation") or {}
                print(f"  GENE EFFECT on {r['line']} "
                      f"({mv.get('gene', 'parent')}={mv.get('value', '-')}): "
                      f"gained {gained or '-'}  lost {lost or '-'}")


# ------------------------------------------------------------ baseline ----

def split_by_unanimity(outcomes: dict) -> tuple:
    """id -> {line: passed} into (every line passed, every line failed, disagreed).

    An ask with no rows at all -- a truncated run, a killed job -- lands in
    `disagreed`, which is the conservative side: it joins no guarded set, so a
    half-record cannot freeze a pass that was never measured.
    """
    yes, no, mixed = [], [], []
    for k in sorted(outcomes):
        v = list(outcomes[k].values())
        if not v:
            mixed.append(k)
        elif all(v):
            yes.append(k)
        elif any(v):
            mixed.append(k)
        else:
            no.append(k)
    return yes, no, mixed


def freeze_baseline(gen: int) -> int:
    """Split the probe pool by MEASUREMENT at the base genome, and freeze it.

    A probe that passed in EVERY clone becomes a regression guard: it may only be
    lost. A probe that failed in EVERY clone becomes a paraphrase probe: it may
    only be gained. A probe the clones disagreed about joins NEITHER set -- an
    unstable pass is not a guard and an unstable fail is not a gap, and pretending
    otherwise would let the instrument's own noise be selected on.
    """
    path = SEL_DIR / f"generation_{gen}.jsonl"
    if not path.exists():
        print(f"no generation {gen} at {path}")
        return 1
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    asks = SEL_DIR / f"generation_{gen}_asks.jsonl"
    per_ask = {}
    for line in asks.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        per_ask.setdefault(r["id"], {})[r["line"]] = r
    tier_of = {i: next(iter(v.values()))["tier"] for i, v in per_ask.items() if v}
    outcomes = {t: {i: {ln: bool(r["pass"]) for ln, r in v.items()}
                    for i, v in per_ask.items() if tier_of[i] == t}
                for t in ("frozen", "probe")}
    n_frozen = len(outcomes["frozen"])
    # ONE rule for both tiers, so the frozen pass set and the regression guard
    # cannot drift apart: an ask joins a guarded set only if EVERY clone passed it.
    # An ask that passed in two of three identical brains is not a frozen pass, it
    # is a coin the instrument flips, and guarding on it would charge a mutant for
    # the harness's own noise.
    frozen_pass, frozen_fail, frozen_unstable = split_by_unanimity(outcomes["frozen"])
    guard, para, ambiguous = split_by_unanimity(outcomes["probe"])

    prov = git_provenance()
    out = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "generation": gen, "clones": len(rows),
           "genome_id": rows[0]["genome_id"] if rows else None,
           "genome_ids": sorted({r["genome_id"] for r in rows}),
           "frozen_seal": prov["frozen_seal"], "probe_seal": prov["probes_seal"],
           "frozen_pass_set": frozen_pass,
           "frozen_fail_set": frozen_fail,
           "frozen_unstable": frozen_unstable,
           "regression_pass_set": guard,
           "paraphrase_set": para,
           "probe_ambiguous": ambiguous,
           "git_head": prov["head"],
           "note": "Frozen before any mutant was scored. The regression guard is "
                   "the intersection of the clones, not their union: an ask that "
                   "passed in two of three identical brains is instrument noise "
                   "and cannot be a pass that a mutant 'lost'."}
    BASELINE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {BASELINE}")
    print(f"  frozen pass set   {len(frozen_pass)}/{n_frozen}")
    print(f"  frozen unstable   {len(frozen_unstable)} {frozen_unstable}")
    print(f"  regression guard  {len(guard)} probes")
    print(f"  paraphrase set    {len(para)} probes")
    print(f"  ambiguous         {len(ambiguous)} {ambiguous}")
    print(f"  seals             frozen={out['frozen_seal']} probes={out['probe_seal']}")
    return 0


# ------------------------------------------------------------------ main ----

def load_base() -> dict:
    p = SEL_DIR / "base_genome.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cmd_snapshot(args) -> int:
    sd = SCRATCH / "_snapshot"
    if sd.exists():
        shutil.rmtree(sd)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    try:
        agent = build(sd)
        shim_check()
        genome = snapshot(agent)
        genome["operator"] = "founder"
        genome["parent_genome_id"] = None
    finally:
        shutil.rmtree(sd, ignore_errors=True)
    SEL_DIR.mkdir(parents=True, exist_ok=True)
    out = SEL_DIR / "base_genome.json"
    out.write_text(json.dumps(genome, indent=1, default=str), encoding="utf-8")
    print(f"wrote {out}")
    print(f"  genome_id {genome['genome_id']}")
    print(json.dumps(genome["genes"], indent=1, sort_keys=True))
    print("provenance:", json.dumps(genome["provenance"], indent=1, default=str))
    return 0


def cmd_run(args) -> int:
    base = load_base()
    if base is None:
        print("no base genome: run --snapshot first")
        return 1
    baseline = (json.loads(BASELINE.read_text(encoding="utf-8"))
                if BASELINE.exists() else None)
    if baseline is not None:
        prov = git_provenance()
        if prov["frozen_seal"] != baseline["frozen_seal"]:
            print(f"REFUSING: tools/scripts_heldout.json has changed since the "
                  f"baseline was frozen ({baseline['frozen_seal']} -> "
                  f"{prov['frozen_seal']}). The frozen pass set describes a "
                  f"different suite; re-freeze deliberately, do not drift.")
            return 1
        if prov["probes_seal"] != baseline["probe_seal"]:
            print(f"WARNING: tools/scripts_selection.json changed since the "
                  f"baseline ({baseline['probe_seal']} -> {prov['probes_seal']}). "
                  f"Generalisation scores are not comparable to the baseline's and "
                  f"every row will carry the label probe-seal-broken.")
    if args.shape_extra:
        words = tuple(w.strip().lower() for w in args.shape_extra.split(",") if w.strip())
        nl.NeuralLanguage.SHAPE_EXTRA_INTERROGATIVES = words
        CODE_FLAGS["shape_extra_interrogatives"] = list(words)
        print(f"R1 ON: SHAPE_EXTRA_INTERROGATIVES = {words} -> "
              f"{nl.NeuralLanguage.SHAPE_BASE_INTERROGATIVES + words}")
    else:
        CODE_FLAGS["shape_extra_interrogatives"] = []
    if args.shape_determiner:
        det = tuple(w.strip().lower() for w in args.shape_determiner.split(",")
                    if w.strip())
        nl.NeuralLanguage.SHAPE_DETERMINER_INTERROGATIVES = det
        CODE_FLAGS["shape_determiner_interrogatives"] = list(det)
        print(f"R1' ON: SHAPE_DETERMINER_INTERROGATIVES = {det}")
    else:
        CODE_FLAGS["shape_determiner_interrogatives"] = []
    if args.shape_passive:
        nl.NeuralLanguage.SHAPE_ALLOW_PASSIVE = True
        CODE_FLAGS["shape_allow_passive"] = True
        print("R2 ON: SHAPE_ALLOW_PASSIVE = True")
    else:
        CODE_FLAGS["shape_allow_passive"] = False
    if args.recall_fallback:
        nl.NeuralLanguage.RECALL_UNFILTERED_FALLBACK = True
        CODE_FLAGS["recall_unfiltered_fallback"] = True
        print("E7 ON: RECALL_UNFILTERED_FALLBACK = True")
    else:
        nl.NeuralLanguage.RECALL_UNFILTERED_FALLBACK = False
        CODE_FLAGS["recall_unfiltered_fallback"] = False
    tiers = tuple(args.tier.split(","))
    battery = load_battery(tiers, args.only, args.open_batch)
    pop = build_population(args, base)
    n_asks = sum(1 for e in battery
                 for s in e["script"]["turns"] if "ask" in s)
    print(f"generation {args.generation}: {len(pop)} line(s) x {n_asks} asks "
          f"= {len(pop) * n_asks} builds "
          f"(~{len(pop) * n_asks * 26 / 60:.0f} min at the measured 26 s/ask)")
    for g in pop:
        mv = g.get("mutation")
        print(f"  line g{args.generation}-{g['line_no']}: "
              f"{g['operator']:15s} {g['genome_id']}"
              + (f"  {mv['gene']} {mv['parent_value']} -> {mv['value']} "
                 f"(draw {mv['draw']:+.4f}, sigma {mv['sigma']}"
                 f"{', CLIPPED' if mv['clipped'] else ''})" if mv else
                 "  (parent, unmutated)"))
    if args.dry_run:
        print("\n--dry-run: population built and printed, nothing evaluated, "
              "nothing written")
        return 0
    if baseline is None:
        print("no frozen baseline yet: probes are reported unsplit, and the "
              "regression guard cannot fire."
              + (" This is correct for the clone run, which is what produces the "
                 "baseline." if args.generation == 0 else
                 " Generation 0 has not been frozen yet."))

    before = guard_live_files("selection")
    SCRATCH.mkdir(parents=True, exist_ok=True)
    journal = SCRATCH / f"gen{args.generation}_asks.jsonl"
    if journal.exists():
        journal.rename(journal.with_name(
            f"gen{args.generation}_asks_prev_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"))
    if args.isolate:
        rows = run_isolated(args, base, baseline, battery, pop)
    else:
        rows = []
        for i, genome in enumerate(pop, 1):
            mv = genome.get("mutation")
            print(f"\n--- line g{args.generation}-{i}  genome {genome['genome_id']} "
                  f"({genome['operator']}"
                  + (f", {mv['gene']}={mv['value']}" if mv else "") + ") ---",
                  flush=True)
            rows.append(evaluate_line(args.generation, i, genome, base, battery,
                                      journal, baseline, args.limit,
                                      project_root=args.state_root))

    moved = guard_check(before)
    ok = True
    for r in rows:
        r["guard"] = {"live_files_untouched": not moved, "moved": moved}
    if moved:
        ok = False
        print(f"\nSTATE GUARD FAILED: {len(moved)} live file(s) moved: {moved[:12]}")
    else:
        print("\nstate guard: live files untouched")

    # The culling decision is a fact about the GENERATION, so it is computed once
    # after every line is scored and stamped into every row: a single line pulled
    # out of the file should still say whether it survived.
    if baseline is not None and any(r.get("mutation") for r in rows):
        control = next((r for r in rows if not r.get("mutation")), rows[0])
        for r in rows:
            if r is not control:
                r["movement"] = movement(r, control)
        decision = cull(rows, control)
        decision["generation"] = args.generation
        decision["control_line"] = control["line"]
        for r in rows:
            r["culling"] = decision
        print_culling(decision, rows)
    elif any(r.get("mutation") for r in rows):
        print("\nno baseline: mutants were scored but nothing can be culled "
              "against, so no selection decision is recorded")

    out = publish(args.generation, rows, journal)
    print(f"published {out}")
    print(f"ask journal {SEL_DIR / f'generation_{args.generation}_asks.jsonl'}")
    print_generation(rows)
    if not ok:
        return 1
    if baseline is None:
        print(f"\nnext: py -3.10 tools/run_generation.py --freeze-baseline "
              f"--generation {args.generation}")
    return 0


EPISODES = ROOT / "state" / "lineage" / "episodes.jsonl"


def print_episode(e: dict) -> None:
    """One episode row, printed in the order the design's success criteria are
    written so a reader can check the gate without hunting through JSON."""
    g = e.get("gates") or {}
    ev = e.get("eval") or {}
    print(f"\n=== EPISODE {e.get('episode')} ===")
    print(f"  at            {e.get('at')}")
    print(f"  checkpoint    {e.get('checkpoint_id')}  parent {e.get('parent_checkpoint')}")
    print(f"  generator     seed={e.get('generator', {}).get('seed')} "
          f"seal={e.get('generator', {}).get('seal')} "
          f"vocab_source={e.get('generator', {}).get('vocab_source')}")
    print(f"  taught        {e.get('teaching', {}).get('taught')} facts, "
          f"consolidated={e.get('teaching', {}).get('consolidated')}")
    print("\n  GATES (all must hold):")
    for k in ("absence_verified", "erosion_zero", "census_reported",
              "live_seals_unchanged", "row_self_contained"):
        v = g.get(k)
        print(f"    {k:22s} "
              f"{'PASS' if v is True else 'NOT MEASURED' if v is None else 'FAIL'}"
              f"   {g.get(k + '_detail', '')}")
    print("\n  MEASURED (reported, not gated):")
    for tier in ("acquisition", "generalisation"):
        t = ev.get(tier) or {}
        print(f"    {tier:16s} {t.get('passed')}/{t.get('asked')} "
              f"= {t.get('score')}")
        for f, v in sorted((t.get("by_frame") or {}).items()):
            print(f"        frame {f:22s} {v['passed']}/{v['asked']}")
    print(f"    {'frozen':16s} {ev.get('frozen_passed')}/{ev.get('frozen_asked')}"
          f"   guarded {ev.get('guard_passed')}/{ev.get('guard_asked')}")
    print(f"    {'stages':16s} {json.dumps(ev.get('stages'))}")
    d = e.get("displacement") or {}
    print("\n  DISPLACEMENT:")
    print(f"    binder rows  {d.get('rows_before')} -> {d.get('rows_after')}")
    print(f"    evicted      {d.get('evicted_n')}  by who {json.dumps(d.get('evicted_who'))}")
    print(f"                 by count {json.dumps(d.get('evicted_count'))}")
    print(f"    added        {d.get('added_n')}  who {json.dumps(d.get('added_who'))}")
    w = e.get("san") or {}
    print(f"    SAN          rows_changed {w.get('rows_changed')}  nnz "
          f"{w.get('nnz_before')} -> {w.get('nnz_after')}  total "
          f"{w.get('total_before')} -> {w.get('total_after')}")
    print(f"\n  VERDICT       {e.get('verdict')}")
    if e.get("erosion"):
        print(f"  EROSION       {e['erosion']}")


def cmd_report(args) -> int:
    """Re-print a generation's or an episode's summary from its published rows. Reads
    nothing else and writes nothing, so a summary can be regenerated after a
    reporting fix without touching the record the fix was needed for."""
    if args.episode is not None:
        if not EPISODES.exists():
            print(f"no episode ledger at {EPISODES}")
            return 1
        rows = [json.loads(l) for l in
                EPISODES.read_text(encoding="utf-8").splitlines() if l.strip()]
        hit = [r for r in rows if r.get("episode") == args.episode]
        if not hit:
            print(f"no episode {args.episode} in {EPISODES} "
                  f"(has: {sorted(r.get('episode') for r in rows)})")
            return 1
        for e in hit:
            print_episode(e)
        return 0
    p = SEL_DIR / f"generation_{args.generation}.jsonl"
    if not p.exists():
        print(f"no generation {args.generation} at {p}")
        return 1
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    dec = rows[0].get("culling") if rows else None
    if dec:
        print_culling(dec, rows)
    print_generation(rows)
    return 0


def cmd_recompute(args) -> int:
    """Rebuild generation_N.jsonl from its ask journal with the CURRENT rules.

    The per-ask journal is the primary record; a per-line row is a pure function of
    its own asks plus the genome, provenance and guard it was stamped with. So when
    the fitness or selection rule changes between a run starting and it finishing,
    the honest move is to recompute from the journal and print both verdicts side by
    side -- not to leave the earlier rule's decision standing as though it had been
    the declared one, and not to quietly overwrite it either.

    This is what happened to generation 1: the paraphrase tier came OUT of
    select_key while the run was in flight, because a scenario drive showed it
    promoting a mutant whose only gain was a held-out probe. The process had already
    imported the old rule. The journal is unaffected by any of it.
    """
    gen = args.generation
    rowf = SEL_DIR / f"generation_{gen}.jsonl"
    askf = SEL_DIR / f"generation_{gen}_asks.jsonl"
    if not rowf.exists() or not askf.exists():
        print(f"need both {rowf.name} and {askf.name}")
        return 1
    old = [json.loads(l) for l in rowf.read_text(encoding="utf-8").splitlines() if l.strip()]
    per_line = {}
    for line in askf.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            per_line.setdefault(r["line"], []).append(r)
    baseline = (json.loads(BASELINE.read_text(encoding="utf-8"))
                if BASELINE.exists() else None)

    new = []
    for r in old:
        asks = per_line.get(r["line"], [])
        fit = fitness_tuple(asks, baseline, r["fitness"].get("seals") or {})
        nr = dict(r)
        # Lineage is derived, not measured, so it is recomputed too: a row published
        # by an older build carries whatever that build's walk produced.
        nr["lineage"] = lineage_of(r["genome_id"], r.get("parent_genome_id"))
        nr["fitness_before_recompute"] = {
            "select_key": r["fitness"].get("select_key"),
            "labels": r["fitness"].get("labels"),
            "capability_passed": (r["fitness"].get("capability") or {}).get("passed"),
        }
        nr["fitness"] = fit
        new.append(nr)

    control = next((r for r in new if not r.get("mutation")), new[0])
    if baseline is not None and any(r.get("mutation") for r in new):
        for r in new:
            if r is not control:
                r["movement"] = movement(r, control)
        dec = cull(new, control)
        dec["generation"] = gen
        dec["control_line"] = control["line"]
        dec["recomputed_from"] = askf.name
        for r in new:
            r["culling"] = dec
        print_culling(dec, new)

    print("\n=== RECOMPUTED vs AS-RUN ===")
    print(f"{'line':7s} {'as-run key':16s} {'recomputed key':16s} changed")
    for o, n in zip(old, new):
        ok_, nk = o["fitness"].get("select_key"), n["fitness"].get("select_key")
        print(f"{n['line']:7s} {str(ok_):16s} {str(nk):16s} "
              f"{'YES' if ok_ != nk else 'no'}")
    old_dec = (old[0].get("culling") or {}).get("outcome")
    new_dec = (new[0].get("culling") or {}).get("outcome") if new else None
    print(f"culling outcome: as-run {old_dec!r} -> recomputed {new_dec!r}")

    # The as-run copy is written once. Recomputing twice must not overwrite the
    # first snapshot with the already-recomputed rows, or the record of what the run
    # actually printed is gone and the two verdicts can no longer be compared.
    prev = rowf.with_name(f"generation_{gen}_asrun.jsonl")
    if prev.exists():
        prev = rowf.with_name(
            f"generation_{gen}_prev_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
    shutil.copyfile(rowf, prev)
    with rowf.open("w", encoding="utf-8") as fh:
        for r in new:
            fh.write(json.dumps(r, default=str) + "\n")
    print(f"\nkept the as-run rows at {prev.name}")
    print(f"rewrote {rowf.name}")
    return 0


def cmd_worker(args) -> int:
    """Evaluate ONE line in its own interpreter and write its row.

    Exists for the module-globals hazard: `FRESH_TAU_S` and the other ANSWER_MODULE
    genes are read as globals inside the organ's methods, so setting one moves every
    brain in the process. They are saved and restored around each line, but a
    restore is a promise and a subprocess is a fact. A mutation run that touches one
    of them should not depend on the promise.
    """
    base = load_base()
    genome = json.loads(Path(args.genome_file).read_text(encoding="utf-8"))
    baseline = (json.loads(BASELINE.read_text(encoding="utf-8"))
                if BASELINE.exists() else None)
    battery = load_battery(tuple(args.tier.split(",")), args.only, args.open_batch)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    journal = SCRATCH / f"gen{args.generation}_asks.jsonl"
    row = evaluate_line(args.generation, args.line_no, genome, base, battery,
                        journal, baseline, args.limit,
                        project_root=args.state_root)
    Path(args.worker_out).write_text(json.dumps(row, default=str), encoding="utf-8")
    return 0


def build_population(args, base) -> list:
    """The generation's population: one control clone of the parent, then mutants.

    The control is not a formality. It re-measures the parent under THIS run's
    conditions, so a mutant's difference can be attributed to the gene rather than
    to whatever the machine did between generation 0 and now -- and because the
    core samples its action and decays its weights on wall clock, "whatever the
    machine did" is a real variable and not a hypothetical one.
    """
    if args.mutants and args.lines is not None:
        raise SystemExit("--mutants and --lines both size the population; pass one")
    pop = []
    ctrl = json.loads(json.dumps(base, default=str))
    ctrl["operator"] = "control-clone" if args.mutants else "clone"
    ctrl["mutation"] = None
    pop.append(ctrl)
    if args.mutants:
        rng = random.Random(args.mut_seed)
        for i in range(args.mutants):
            child, rec = mutate(base, args.mutate, rng)
            rec["rng_seed"] = args.mut_seed
            rec["draw_index"] = i + 1
            child["mutation"] = rec
            pop.append(child)
    else:
        for _ in range((args.lines or 3) - 1):
            clone = json.loads(json.dumps(base, default=str))
            clone["operator"] = "clone"
            clone["mutation"] = None
            pop.append(clone)
    for i, g in enumerate(pop, 1):
        g["line_no"] = i
    return pop


def run_isolated(args, base, baseline, battery, pop) -> list:
    """One subprocess per line. Serial, so the shared ask journal cannot
    interleave, and the parent still owns the state guard and the publish."""
    rows = []
    for i, genome in enumerate(pop, 1):
        gfile = SCRATCH / f"genome_g{args.generation}-{i}.json"
        ofile = SCRATCH / f"row_g{args.generation}-{i}.json"
        gfile.write_text(json.dumps(genome, default=str), encoding="utf-8")
        cmd = [sys.executable, str(Path(__file__).resolve()), "--worker",
               "--generation", str(args.generation), "--line-no", str(i),
               "--genome-file", str(gfile), "--worker-out", str(ofile),
               "--tier", args.tier]
        if args.only:
            cmd += ["--only", args.only]
        if args.limit is not None:
            cmd += ["--limit", str(args.limit)]
        if args.open_batch:
            cmd += ["--open-batch", str(args.open_batch)]
        if args.state_root:
            cmd += ["--state-root", str(args.state_root)]
        mv = genome.get("mutation") or {}
        print(f"\n--- line g{args.generation}-{i}  genome {genome['genome_id']} "
              f"({genome.get('operator', 'clone')}"
              + (f", {mv.get('gene')}={mv.get('value')}" if mv else "")
              + ", isolated subprocess) ---", flush=True)
        rc = subprocess.run(cmd, cwd=str(ROOT)).returncode
        if rc != 0:
            print(f"line g{args.generation}-{i} exited {rc}: recorded, not scored")
            rows.append({"generation": args.generation, "line": f"g{args.generation}-{i}",
                         "genome_id": genome["genome_id"],
                         "parent_genome_id": genome.get("parent_genome_id"),
                         "lineage": lineage_of(genome["genome_id"],
                                               genome.get("parent_genome_id")),
                         "operator": genome.get("operator", "clone"),
                         "mutation": genome.get("mutation"),
                         "genome": genome["genes"],
                         "genome_verified": False, "shim_clean": False,
                         "exit_code": rc,
                         "fitness": {"capability": {"asked": 0, "passed": 0,
                                                    "score": None, "pass_set": [],
                                                    "failures": []},
                                     "regression": {"verdict": "line crashed"},
                                     "generalisation": {}, "stages": {},
                                     "select_key": [0, 0, 0],
                                     "labels": ["line-crashed"]},
                         "asks": 0, "seconds": 0.0})
            continue
        rows.append(json.loads(ofile.read_text(encoding="utf-8")))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--snapshot", action="store_true",
                    help="build one brain, read its genome off it, write "
                         "state/selection/base_genome.json")
    ap.add_argument("--generation", type=int, default=None)
    ap.add_argument("--lines", type=int, default=None,
                    help="evaluate this many CLONES of the base, no mutation "
                         "(default 3). Mutually exclusive with --mutants")
    ap.add_argument("--mutants", type=int, default=0,
                    help="run 1 control clone plus this many mutants, and record a "
                         "culling decision")
    ap.add_argument("--mutate", default="answer.ANSWER_COVERAGE_FLOOR",
                    choices=sorted(MUTATIONS),
                    help="which pre-registered operator to use. The choices ARE "
                         "the pre-registration: adding one is a code change with a "
                         "dated entry in docs/selection_design.md, not a flag")
    ap.add_argument("--mut-seed", type=int, default=1,
                    help="seed for the mutation draws, so a generation's mutants "
                         "can be regenerated exactly")
    ap.add_argument("--shape-extra", default="",
                    help="comma-separated question words to add to the shape parser's "
                         "gate (repair R1). A CODE flag, not a genome gene: both arms of "
                         "an A/B carry the same genome, so this is what distinguishes "
                         "them and it is recorded in provenance.code_flags. Must be run "
                         "one arm per process, since it is a module-level constant")
    ap.add_argument("--shape-determiner", default="",
                    help="comma-separated DETERMINER question words (repair R1'): these "
                         "take a noun-phrase head, so the parser skips it before looking "
                         "for the verb. `which` is the only candidate. Separate from "
                         "--shape-extra so R1 and R1' are separately attributable")
    ap.add_argument("--shape-passive", action="store_true",
                    help="repair R2: parse `what is <verb> by <agent>` into the existing "
                         "object_unknown kind. Separate flag again, so a result is "
                         "attributable to one cut")
    ap.add_argument("--recall-fallback", action="store_true",
                    help="experiment E7: when the three retrieval filters remove EVERY "
                         "posting the binder offered, hand the raw postings to the "
                         "coverage gate instead of dying as ABSENT. The gate still "
                         "demands every distinctive word at IDF weight and still refuses "
                         "below the floor, so this converts an unmeasured silence into a "
                         "measured refusal. Default off; inert when off because the only "
                         "use site is guarded by `not hits`")
    ap.add_argument("--dry-run", action="store_true",
                    help="build and print the population -- genome ids and mutation "
                         "values -- then stop. Costs nothing and shows the mutants "
                         "before a generation commits an hour of builds")
    ap.add_argument("--tier", default="frozen,probe",
                    help="frozen | probe | open | any comma combination")
    ap.add_argument("--open-batch", default=None,
                    help="generated open-tier batch file, required with --tier open")
    ap.add_argument("--state-root", default=None,
                    help="measure against this shadow state tree instead of the live "
                         "one; an episode's shadow is how a retention test becomes a "
                         "cross-process measurement")
    ap.add_argument("--episode", type=int, default=None,
                    help="with --report, print this episode from "
                         "state/lineage/episodes.jsonl instead of a generation")
    ap.add_argument("--only", default=None, help="run scripts whose name matches")
    ap.add_argument("--limit", type=int, default=None,
                    help="stop after this many asks per line (harness smoke test)")
    ap.add_argument("--freeze-baseline", action="store_true",
                    help="split the probe pool by the measured clone outcomes and "
                         "write tools/selection_baseline.json")
    ap.add_argument("--isolate", action="store_true",
                    help="run each line in its own subprocess. Required for a "
                         "mutation run that touches an ANSWER_MODULE gene, since "
                         "those are process-wide; the restore is a promise and a "
                         "subprocess is a fact")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--line-no", type=int, default=1, help=argparse.SUPPRESS)
    ap.add_argument("--genome-file", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--worker-out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--report", action="store_true",
                    help="re-print a generation's selection and membership summary "
                         "from its published rows; reads and writes nothing else")
    ap.add_argument("--recompute", action="store_true",
                    help="rebuild generation_N.jsonl from its ask journal with the "
                         "current fitness and selection rules, keeping the as-run "
                         "rows beside it and printing both verdicts")
    a = ap.parse_args()
    if a.worker:
        return cmd_worker(a)
    if a.report:
        return cmd_report(a)
    if a.recompute:
        return cmd_recompute(a)
    if a.snapshot:
        return cmd_snapshot(a)
    if a.freeze_baseline:
        return freeze_baseline(a.generation if a.generation is not None else 0)
    if a.generation is None:
        ap.error("--generation N is required to run")
    return cmd_run(a)


if __name__ == "__main__":
    sys.exit(main())
