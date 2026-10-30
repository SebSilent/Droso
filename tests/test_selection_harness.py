r"""Pins the selection harness's contracts: the genome, the shim check, the
apply-and-verify rule, the tuple's ordering, and the probe file's own promises.

Nothing here builds a house. A build is ~16 s and the whole point of these tests
is that they can run on every commit, so the apply/verify logic is exercised
against a stub that has the same attribute paths the real brain has. The stub is
deliberately dumb: a test that needed a real organ to check whether a scalar was
written would be testing the organ, not the harness.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import organs.neural_language as nl  # noqa: E402
import tools.run_generation as rg  # noqa: E402
from connectome.engine import HybridEngineParams  # noqa: E402
from connectome.rate_core import CoreParams  # noqa: E402


# ------------------------------------------------------------------ stub ----

class _Graph:
    def __init__(self):
        self.meta = {"control": False, "seed": 0, "row_gain": 0.5,
                     "n_static_edges": 173294, "n_plastic_edges": 2983}
        self.n_actions = 12


class _Static:
    def __init__(self):
        self.p = CoreParams()
        self.rng = None


class _Engine:
    def __init__(self):
        self.static = _Static()
        self.params = HybridEngineParams()
        self.graph = _Graph()
        self.rng = None


class _Lang:
    def __init__(self):
        for k in rg.ANSWER_INSTANCE_GENES:
            setattr(self, k, 0.0)


class StubAgent:
    def __init__(self):
        self.engine = _Engine()
        self.language = _Lang()


class _StuckLang:
    """A language organ that silently refuses one write.

    This is the case the read-back exists for: a gene that was requested, reported
    as applied, and never took effect. Without the read-back the brain would be
    scored as carrying it.
    """

    def __init__(self, frozen):
        object.__setattr__(self, "_frozen", frozen)
        for k in rg.ANSWER_INSTANCE_GENES:
            object.__setattr__(self, k, 0.0)

    def __setattr__(self, name, value):
        if name == self._frozen:
            return
        object.__setattr__(self, name, value)


def base_genome() -> dict:
    """A base genome with the organ-side scalars filled in, as snapshot() would."""
    genes = rg.birth_genes()
    genes["answer"] = {
        **{k: 1.0 for k in rg.ANSWER_INSTANCE_GENES},
        **{k: 1.0 for k in rg.ANSWER_MODULE_GENES},
    }
    genes = rg._normalise(genes)
    return {"schema": rg.SCHEMA, "genes": genes, "genome_id": rg.gid(genes),
            "provenance": {}}


# ---------------------------------------------------------------- genome ----

def test_the_genome_id_is_a_function_of_the_genes_and_of_nothing_else():
    """Provenance describes the brain a genome ran on and moves when the lived
    state moves. Hashing it would give one behaviour two ids and break the parent
    chain, which is the defect fly_v2's lineage had."""
    a, b = base_genome(), base_genome()
    a["provenance"] = {"teaching_history": {"vocabulary": 11555}}
    b["provenance"] = {"teaching_history": {"vocabulary": 4}}
    assert a["genome_id"] == b["genome_id"]

    c = base_genome()
    c["genes"]["answer"]["reply_threshold"] = 0.9
    assert rg.gid(c["genes"]) != a["genome_id"]


def test_a_genome_survives_a_round_trip_through_json_byte_identically():
    """A lineage row has to be enough to rebuild the brain. numpy scalars do not
    serialise, and a float that prints differently on the way back is a different
    genome with the same behaviour."""
    g = base_genome()
    g["genes"]["plasticity"]["sub_steps"] = __import__("numpy").int64(10)
    g["genes"]["substrate"]["control"] = __import__("numpy").bool_(False)
    g = {"schema": g["schema"], "genes": rg._normalise(g["genes"]),
         "genome_id": g["genome_id"], "provenance": g["provenance"]}
    text = json.dumps(g["genes"], sort_keys=True, separators=(",", ":"))
    again = json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
    assert text == again
    assert rg.gid(json.loads(text)) == rg.gid(g["genes"])


def test_every_plasticity_parameter_is_a_gene_and_starts_at_its_birth_value():
    """A CoreParams field added later must not silently miss the genome, and the
    recorded value must be the birth one: epsilon and temperature are mutated in
    place per decision, so an as-found value is a value already decaying."""
    assert set(rg.PLASTICITY_GENES) == set(CoreParams.__dataclass_fields__)
    birth = CoreParams()
    genes = rg.birth_genes()["plasticity"]
    assert set(genes) == set(CoreParams.__dataclass_fields__)
    for k, v in genes.items():
        assert v == getattr(birth, k), k
    assert genes["epsilon"] == 0.15 and genes["temperature"] == 0.02


def test_the_substrate_seed_gene_is_recorded_even_though_the_carve_ignores_it():
    """build_core_graph constructs its rng INSIDE `if control:`, so on the
    experimental carve `seed` does nothing. The gene stays in the schema because a
    control brain does use it, and the design doc says so; what must not happen is
    a sweep spending builds on a gene that cannot bite."""
    genes = rg.birth_genes()["substrate"]
    assert set(genes) == set(rg.SUBSTRATE_GENES)
    assert genes["control"] is False and genes["seed"] == 0


# ------------------------------------------------------------ shim check ----

def test_the_shim_check_passes_on_the_organ_as_committed():
    out = rg.shim_check()
    assert out["clean"] is True
    assert out["watched"]["_shape_matches"]["name"] == "_shape_matches"


def test_the_shim_check_refuses_a_patched_matcher():
    """The check has to have seen the thing it checks for. tools/_genome_patch.py
    is present and tracked in this tree and installs its patch at import time,
    while docs/STATE.md records it as moved out of tools/ -- so trusting the doc,
    or the absence of an import, is how a veto override gets scored as capability.
    """
    original = nl.NeuralLanguage.__dict__["_shape_matches"]
    try:
        def patched(self, shape, tokens):        # same name the real shim uses
            return original(self, shape, tokens)

        nl.NeuralLanguage._shape_matches = patched
        with pytest.raises(RuntimeError) as exc:
            rg.shim_check()
        msg = str(exc.value)
        assert "_shape_matches" in msg and "refusing to score" in msg
        # The offender is named with the file it came from, so the record says
        # where the replacement was compiled and not merely that there was one.
        assert "patched" in msg and str(Path(__file__).name).lower() in msg.lower()
    finally:
        nl.NeuralLanguage._shape_matches = original
    assert rg.shim_check()["clean"] is True


def test_the_shim_check_catches_a_wrapper_that_keeps_the_original_name():
    """A name check alone is not a check. This wrapper is called `answer`, takes the
    same signature and delegates to the real one -- exactly what functools.wraps
    produces -- and it was compiled in this file, so the source-file test is the
    only thing that can see it. The first version of shim_check passed it.
    """
    original = nl.NeuralLanguage.__dict__["answer"]
    try:
        def answer(self, question, speaker="you"):
            return original(self, question, speaker)

        assert answer.__name__ == "answer"
        nl.NeuralLanguage.answer = answer
        with pytest.raises(RuntimeError) as exc:
            rg.shim_check()
        assert "answer" in str(exc.value)
    finally:
        nl.NeuralLanguage.answer = original
    assert rg.shim_check()["clean"] is True


def test_every_watched_method_is_currently_the_organs_own():
    """The check above is only meaningful if the organ passes it as committed."""
    out = rg.shim_check()
    assert out["clean"] is True and out["offenders"] == []
    assert set(out["watched"]) == set(rg.WATCHED_METHODS)
    assert "_shape_matches" in out["watched"]


# --------------------------------------------------------- apply / verify ----

def test_every_post_build_gene_is_written_and_reads_back():
    agent, base = StubAgent(), base_genome()
    genome = base_genome()
    genome["genes"]["plasticity"]["lr"] = 2.5
    genome["genes"]["plasticity"]["input_gain"] = 1.25
    genome["genes"]["decision"]["ratecore_seed"] = 7
    genome["genes"]["answer"]["ANSWER_COVERAGE_FLOOR"] = 0.55
    genome["genes"]["answer"]["reply_threshold"] = 0.4
    genome["genes"]["answer"]["FRESH_TAU_S"] = 1800.0
    saved = {k: getattr(nl, k) for k in rg.ANSWER_MODULE_GENES}
    try:
        out = rg.apply_genome(agent, genome, base)
    finally:
        rg.restore_module_genes(saved)
    assert out["ok"] is True, out
    assert out["mismatch"] == [] and out["refused"] == []
    assert agent.engine.static.p.lr == 2.5
    assert agent.engine.static.p.input_gain == 1.25
    assert agent.language.ANSWER_COVERAGE_FLOOR == 0.55
    assert agent.language.reply_threshold == 0.4
    assert agent.engine.static.rng is not None
    assert "answer.FRESH_TAU_S" in out["process_wide"]


def test_a_build_time_gene_that_differs_from_base_is_refused_not_ignored():
    """Silently scoring a genome whose substrate genes were never applied is the
    shim's dishonesty in a quieter register: the row would say the brain ran on a
    control carve when it ran on the experimental one."""
    agent, base = StubAgent(), base_genome()
    genome = base_genome()
    genome["genes"]["substrate"]["control"] = True
    genome["genes"]["decision"]["k_code"] = 32
    out = rg.apply_genome(agent, genome, base)
    assert out["ok"] is False
    assert any("substrate.control" in r for r in out["refused"])
    assert any("decision.k_code" in r for r in out["refused"])
    assert agent.engine.graph.meta["control"] is False
    assert agent.engine.params.k_code == 16


def test_a_gene_that_does_not_take_is_a_mismatch_and_fails_the_brain():
    agent = StubAgent()
    agent.language = _StuckLang("reply_threshold")
    base = base_genome()
    genome = base_genome()
    genome["genes"]["answer"]["reply_threshold"] = 0.42
    out = rg.apply_genome(agent, genome, base)
    assert out["ok"] is False
    assert len(out["mismatch"]) == 1
    assert "answer.reply_threshold" in out["mismatch"][0]
    assert "0.42" in out["mismatch"][0]


def test_a_clone_of_the_base_genome_applies_clean_and_changes_nothing():
    """Generation 0 is three clones. A clone must verify against the base with no
    mismatch and no refusal, or the reproducibility measurement is measuring the
    harness applying genes rather than the instrument."""
    agent, base = StubAgent(), base_genome()
    saved = {k: getattr(nl, k) for k in rg.ANSWER_MODULE_GENES}
    try:
        out = rg.apply_genome(agent, base, base)
    finally:
        rg.restore_module_genes(saved)
    assert out["ok"] is True and out["mismatch"] == [] and out["refused"] == []
    assert agent.engine.static.p.lr == CoreParams().lr
    assert agent.engine.graph.meta["control"] is False


# ------------------------------------------------------------- the tuple ----

def _rows(frozen_pass, frozen_all, probe=None):
    probe = probe or {}
    out = [{"tier": "frozen", "id": f"s::a{i}", "ask": f"a{i}", "pass": i < frozen_pass,
            "stage": None if i < frozen_pass else "recall", "why": "x", "said": ""}
           for i in range(frozen_all)]
    for pid, (rewords, ok) in probe.items():
        out.append({"tier": "probe", "id": pid, "ask": pid, "rewords": rewords,
                    "pass": ok, "stage": None if ok else "recall", "why": "x",
                    "said": ""})
    return out


def _baseline(frozen_pass_n=2, frozen_all=4, guard=(), para=()):
    return {"frozen_pass_set": [f"s::a{i}" for i in range(frozen_pass_n)],
            "regression_pass_set": list(guard), "paraphrase_set": list(para),
            "probe_seal": rg.seal(rg.PROBE_TASKS), "frozen_seal": rg.seal(rg.FROZEN_TASKS)}


def test_fitness_has_four_terms_and_no_scalar_anywhere():
    fit = rg.fitness_tuple(_rows(2, 4), None, {"frozen": "f", "probes": "p"})
    assert set(fit) >= {"capability", "regression", "generalisation", "stages",
                        "select_key", "labels"}
    for k, v in fit.items():
        assert not (isinstance(v, float) and k not in ("select_key",)), k
    assert "composite" not in fit and "fitness" not in fit
    assert isinstance(fit["select_key"], list) and len(fit["select_key"]) == 3


def test_a_lost_frozen_pass_outranks_any_capability_gain():
    """The first term of the key is a gate, not a weight. A line that gained two
    asks and lost one must sort BELOW a line that gained nothing and lost nothing,
    which is the trade a weighted composite would happily accept."""
    bl = _baseline(frozen_pass_n=2, frozen_all=4)
    gained = rg.fitness_tuple(_rows(3, 4), bl, {"frozen": "f", "probes": "p"})
    # a line that passes 3 of 4 but not the first two: it lost s::a0 and s::a1
    lost = rg.fitness_tuple(
        [{"tier": "frozen", "id": f"s::a{i}", "ask": f"a{i}",
          "pass": i in (2, 3, 0) and i != 1, "stage": "recall", "why": "x",
          "said": ""} for i in range(4)], bl, {"frozen": "f", "probes": "p"})
    assert lost["regression"]["frozen_lost"] == ["s::a1"]
    assert lost["regression"]["verdict"] == "LOST"
    assert lost["select_key"][0] == 0
    assert gained["select_key"][0] == 1 or lost["select_key"] < gained["select_key"]
    assert lost["select_key"] < [1, 0, 0]


def test_a_frozen_gain_whose_own_paraphrases_still_fail_is_labelled():
    """Per-ask, not per-tier: the probe records the frozen ask it rewords, so a
    gain is checked against the rewordings of THAT ask. A tier average would hide
    one fitted phrasing inside eighteen unrelated results."""
    bl = _baseline(frozen_pass_n=1, frozen_all=2, para=["p1", "p2"])
    rows = _rows(2, 2, probe={"p1": ("a1", False), "p2": ("a1", False)})
    fit = rg.fitness_tuple(rows, bl, {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    assert any(l.startswith("phrasing_fitted:a1") for l in fit["labels"]), fit["labels"]


def test_a_frozen_gain_that_its_paraphrases_share_is_not_labelled():
    bl = _baseline(frozen_pass_n=1, frozen_all=2, para=["p1", "p2"])
    rows = _rows(2, 2, probe={"p1": ("a1", True), "p2": ("a1", False)})
    fit = rg.fitness_tuple(rows, bl, {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    assert not any(l.startswith("phrasing_fitted") for l in fit["labels"]), fit["labels"]


def test_an_ask_that_already_passed_carries_no_paraphrase_obligation():
    bl = _baseline(frozen_pass_n=2, frozen_all=2, para=["p1"])
    rows = _rows(2, 2, probe={"p1": ("a0", False)})
    fit = rg.fitness_tuple(rows, bl, {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    assert fit["labels"] == []


def test_a_partial_run_is_not_charged_for_the_asks_it_never_ran():
    """A chunked or --only run covers fewer asks than the baseline. Counting the
    unrun ones as lost is coverage read as movement -- the error that produced a
    retracted drift claim in the log, and the one heldout_eval.compare() refuses a
    raw delta for. The line still reports a key, but it is labelled partial so it
    cannot be ranked against a full one.
    """
    bl = _baseline(frozen_pass_n=4, frozen_all=4, guard=["g1"])
    rows = _rows(2, 2, probe={"g1": ("a0", True)})
    fit = rg.fitness_tuple(rows, bl, {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    reg = fit["regression"]
    assert reg["frozen_lost"] == [], reg
    assert reg["frozen_lost_n"] == 0
    assert reg["frozen_not_run"] == ["s::a2", "s::a3"]
    assert reg["frozen_guarded_and_run"] == 2
    assert reg["verdict"] == "clean"
    assert "partial-run" in fit["labels"]


def test_a_full_run_that_loses_a_guarded_ask_is_charged_for_exactly_that_one():
    bl = _baseline(frozen_pass_n=4, frozen_all=4, guard=["g1"])
    rows = _rows(3, 4, probe={"g1": ("a0", False)})
    fit = rg.fitness_tuple(rows, bl, {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    reg = fit["regression"]
    assert reg["frozen_lost"] == ["s::a3"]
    assert reg["probe_guard_lost"] == ["g1"]
    assert reg["verdict"] == "LOST"
    assert reg["frozen_not_run"] == []
    assert "partial-run" not in fit["labels"]
    assert "regression" in fit["labels"]
    assert fit["select_key"][0] == 0


def test_a_broken_probe_seal_is_labelled_rather_than_silently_compared():
    bl = _baseline(frozen_pass_n=2, frozen_all=2)
    bl["probe_seal"] = "0" * 16
    fit = rg.fitness_tuple(_rows(2, 2), bl,
                           {"frozen": "f", "probes": rg.seal(rg.PROBE_TASKS)})
    assert "probe-seal-broken" in fit["labels"]
    assert fit["generalisation"]["seal_matches_baseline"] is False


def test_the_stage_distribution_counts_failures_and_is_not_a_score():
    rows = _rows(1, 4)
    for r, st in zip([x for x in rows if not x["pass"]], ["recall", "recall", "gating"]):
        r["stage"] = st
    fit = rg.fitness_tuple(rows, None, {"frozen": "f", "probes": "p"})
    assert fit["stages"] == {"recall": 2, "gating": 1}
    assert "stages" not in fit["select_key"]


# ------------------------------------------------------------ unanimity ----

def test_an_ask_the_clones_disagreed_about_joins_neither_guarded_set():
    """An unstable pass is not a guard and an unstable fail is not a gap. Letting
    either in would let the instrument's own noise be selected on."""
    yes, no, mixed = rg.split_by_unanimity({
        "a": {"g0-1": True, "g0-2": True, "g0-3": True},
        "b": {"g0-1": False, "g0-2": False, "g0-3": False},
        "c": {"g0-1": True, "g0-2": False, "g0-3": True},
    })
    assert yes == ["a"] and no == ["b"] and mixed == ["c"]


def test_an_ask_that_was_never_scored_is_not_a_pass():
    """A killed job leaves a half journal. The conservative side is 'disagreed',
    so a truncated run cannot freeze a pass nobody measured."""
    yes, no, mixed = rg.split_by_unanimity({"a": {}, "b": {"g0-1": True}})
    assert yes == ["b"] and mixed == ["a"] and no == []


def test_the_frozen_pass_set_is_the_intersection_not_the_union():
    yes, _no, mixed = rg.split_by_unanimity({
        "x": {"g0-1": True, "g0-2": True, "g0-3": False},
        "y": {"g0-1": True, "g0-2": True, "g0-3": True},
    })
    assert yes == ["y"] and mixed == ["x"]


# --------------------------------------------------------- the eval set ----

def test_the_frozen_tier_is_read_from_the_committed_suite_not_copied():
    """A copy is a second contract that can drift, and then 'zero frozen passes
    lost' would be measured against whatever the copy said."""
    src = json.loads(rg.FROZEN_TASKS.read_text(encoding="utf-8"))["scripts"]
    want = [f"{s['name']}::{t['ask']}" for s in src for t in s["turns"] if "ask" in t]
    got = [rg.ask_id(e["script"]["name"], t["ask"])
           for e in rg.load_battery(("frozen",), None)
           for t in e["script"]["turns"] if "ask" in t]
    assert got == want
    assert len(want) == 24
    # The harness holds no ask text of its own.
    own = Path(rg.__file__).read_text(encoding="utf-8")
    assert "the coat is wet" not in own
    assert "how many times did i tell you" not in own


def test_every_probe_rewords_a_real_frozen_ask_and_keeps_its_expect_verbatim():
    """The claim in section 4.2 is that phrasing is the only variable. This makes
    it mechanical: a probe whose expect block drifted from its parent's is grading
    a different question, and a probe that rewords nothing is a new task wearing a
    paraphrase's label."""
    frozen = json.loads(rg.FROZEN_TASKS.read_text(encoding="utf-8"))["scripts"]
    by_ask = {t["ask"]: t for s in frozen for t in s["turns"] if "ask" in t}
    parent_of = {s["name"]: s.get("parent") for s in
                 json.loads(rg.PROBE_TASKS.read_text(encoding="utf-8"))["scripts"]}
    probes = json.loads(rg.PROBE_TASKS.read_text(encoding="utf-8"))["scripts"]
    n = 0
    for s in probes:
        assert parent_of[s["name"]] in {f["name"] for f in frozen}, s["name"]
        tells = [t["say"] for t in s["turns"] if "say" in t]
        parent_tells = [t["say"] for t in
                        next(f for f in frozen if f["name"] == parent_of[s["name"]])
                        ["turns"] if "say" in t]
        assert tells == parent_tells, f"{s['name']} changed its parent's tells"
        for t in s["turns"]:
            if "ask" not in t:
                continue
            n += 1
            assert t.get("probe"), f"{s['name']} has an unnamed probe"
            assert t["rewords"] in by_ask, f"{t['probe']} rewords nothing real"
            assert t["expect"] == by_ask[t["rewords"]]["expect"], \
                f"{t['probe']} changed its parent's expect block"
            assert t["ask"] != t["rewords"], f"{t['probe']} is not a rewording"
    assert n == 18


def test_the_probe_pool_covers_every_current_frozen_failure():
    """A paraphrase tier that skips a failure cannot detect a fitted fix for it."""
    probes = json.loads(rg.PROBE_TASKS.read_text(encoding="utf-8"))["scripts"]
    reworded = {t["rewords"] for s in probes for t in s["turns"] if "ask" in t}
    known_failures = {
        "what did i tell you about before the kettle?",
        "what is wet but not on the hook?",
        "how many times does the bell turn?",
        "what does the thing the frost bites hold?",
        "does the door hold the frost?",
    }
    assert known_failures <= reworded, sorted(known_failures - reworded)


def test_a_probe_does_not_reuse_the_cue_word_it_is_measuring_past():
    """Spot-checked against the organ's own tables. A probe that kept its parent's
    cue word would measure the cue table and report it as generalisation."""
    probes = json.loads(rg.PROBE_TASKS.read_text(encoding="utf-8"))["scripts"]
    by_probe = {t["probe"]: t["ask"] for s in probes for t in s["turns"] if "ask" in t}
    words = lambda s: set(__import__("re").findall(r"[a-z']+", s.lower()))
    # 'how often' carries neither 'how many' nor a COUNT_QUANTS word
    assert not (words(by_probe["P-numeral-often"]) & nl.NeuralLanguage.COUNT_QUANTS)
    assert "many" not in words(by_probe["P-numeral-often"])
    # 'earlier than' is in neither ordinal nor first-cue table
    assert not (words(by_probe["P-before-earlier"]) & nl.NeuralLanguage.ORDINAL_CUES)
    assert not (words(by_probe["P-before-earlier"])
                & nl.NeuralLanguage.COUNT_FIRST_CUES)
    # The second before-probe keeps a record VERB ("said") but not the record
    # FRAME, and the frame is what the path tests: _record_answer returns None
    # unless words[0] is one of did/do/does/have/has. Asserting the mechanism
    # rather than the vocabulary, because the vocabulary claim would be false.
    assert words(by_probe["P-before-came"]) & nl.NeuralLanguage.RECORD_VERBS
    first = by_probe["P-before-came"].split()[0]
    assert first not in ("did", "do", "does", "have", "has")
    # and the ordinal path needs a literal "which", which this probe does not have
    assert "which" not in words(by_probe["P-before-came"])
    assert "which" in words(by_probe["P-before-earlier"])


def test_a_changed_frozen_suite_refuses_the_run_before_any_build(tmp_path, monkeypatch):
    """'Zero frozen passes lost' is measured against a suite. Change the suite and
    the baseline describes something else, so the harness must stop -- not warn, and
    not score. Checked by pointing the harness at a modified COPY: the committed
    file is never touched, and the refusal has to happen before a house is built,
    or the test would cost a minute and prove nothing about the order.
    """
    if not rg.BASELINE.exists():
        pytest.skip("no frozen baseline yet; run generation 0 and --freeze-baseline")
    src = json.loads(rg.FROZEN_TASKS.read_text(encoding="utf-8"))
    src["scripts"][0]["turns"][0]["say"] = "the coat is damp"
    moved = tmp_path / "scripts_heldout.json"
    moved.write_text(json.dumps(src), encoding="utf-8")
    monkeypatch.setattr(rg, "FROZEN_TASKS", moved)

    built = []
    monkeypatch.setattr(rg, "build", lambda *a, **k: built.append(1))
    args = argparse.Namespace(generation=97, lines=1, tier="frozen", only=None,
                              limit=None, isolate=False)
    assert rg.cmd_run(args) == 1
    assert built == [], "a build ran before the seal was checked"


def test_the_committed_suite_still_matches_the_frozen_baseline():
    """The other half: the refusal above is only meaningful if the real file
    currently agrees with the real baseline."""
    if not rg.BASELINE.exists():
        pytest.skip("no frozen baseline yet")
    bl = json.loads(rg.BASELINE.read_text(encoding="utf-8"))
    assert rg.seal(rg.FROZEN_TASKS) == bl["frozen_seal"]
    assert rg.seal(rg.PROBE_TASKS) == bl["probe_seal"]


def test_the_harness_seals_both_eval_files():
    assert len(rg.seal(rg.FROZEN_TASKS)) == 16
    assert len(rg.seal(rg.PROBE_TASKS)) == 16
    assert rg.seal(rg.FROZEN_TASKS) != rg.seal(rg.PROBE_TASKS)
