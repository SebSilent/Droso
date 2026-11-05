"""Tests for the B.6 item 5 pre-registration.

These check a registration that has produced no measurement. That is the point: the failure mode of a
pre-registration is not a wrong number, it is a number that arrives in a shape nobody fixed in advance, or a
threshold quietly re-based by whoever ran the clock, or a proposed identifier that collides with one written in a
document nobody re-read. Each test guards one of those, and none of them requires a timing to exist.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "experiments" / "MP-E12" / "results" / "latency_benchmark_preregistration_v1.json"
PROBES = ROOT / "experiments" / "MP-E12" / "results" / "probe_list_v1.json"
GRAPH = ROOT / "experiments" / "MP-E12" / "results" / "association_graph_real_class1.json"
CLUST = ROOT / "experiments" / "MP-E12" / "results" / "clustering_limitation_v1.json"
LEDGER = ROOT / "experiments" / "MP-E12" / "registration.json"
OTHER_LEDGERS = [p for p in sorted(Path("experiments").glob("*/registration.json"))
                 if p != LEDGER]
PLAN = ROOT / "experiments" / "MP-E9" / "plan_extract" / "DROSO_Master_Plan_v1_2.md"
TOOL = ROOT / "tools" / "mp_e12_preregister_latency_benchmark.py"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def art():
    return json.loads(ART.read_text(encoding="utf-8"))


def test_artifact_exists_and_declares_itself_unexecuted():
    a = art()
    assert a["status"].startswith("PRE-REGISTERED AND UNEXECUTED")
    assert "No timing exists" in a["status"]
    assert a["prohibitions_observed_in_this_step"]["no_timing"] is True
    assert a["prohibitions_observed_in_this_step"]["no_donor_execution"] is True


def test_no_field_holds_a_duration():
    """The artifact says no timing exists. Checked structurally, not taken on trust.

    Any key whose name ends in a duration unit must be null. A key named e.g. `median_s` holding a float here
    would mean a clock was started, and the whole registration would be a description of that run rather than a
    rule written before it.
    """
    a = art()
    blob = json.dumps(a)
    assert "median_ms" not in blob
    offenders = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                if re.search(r"(_s|_ms|seconds|milliseconds|elapsed|duration)$", k) and v is not None:
                    offenders.append((path + "/" + k, v))
                walk(v, path + "/" + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(a, "")
    assert not offenders, offenders
    shape = a["result_table_shape_with_every_duration_null"]["per_cell_fields"]
    assert all(v is None for k, v in shape.items() if k.endswith("_s"))
    assert shape["median_s"] is None and shape["p95_s"] is None
    assert shape["identity_matches_section_3"] is None


def test_query_set_is_the_sealed_24_and_nothing_else():
    a = art()
    sealed = [p["word"] for p in json.loads(PROBES.read_text(encoding="utf-8"))["probes"]]
    q = a["1_query_set_named_before_any_timing"]
    assert q["queries"] == sealed, "the timed query set must be the pre-sealed one, in its sealed order"
    assert q["n_queries"] == 24
    assert len(set(q["queries"])) == 24
    # the deferred 17 are excluded because admitting them would change the set after the graph was sealed on it
    deferred = [d["word"] for d in json.loads(PROBES.read_text(encoding="utf-8"))["deferred_words"]]
    assert not (set(q["queries"]) & set(deferred))
    # the claim is in the KEY name; the value is the reason. A test that made the value repeat the key would be
    # testing prose, not the exclusion.
    assert q["the_17_deferred_words_are_EXCLUDED"].startswith("They are not probes under v1")


def test_curve_points_are_the_ones_the_ruling_fixed():
    """D-MPE12-05 fixed 1, 5, 9 plus the donor's measured mean answer length. This artifact may not move them."""
    a = art()
    d = json.loads(LEDGER.read_text(encoding="utf-8"))
    ruling = d["pi_rulings"]["D-MPE12-05"]["ruling"]
    pts = a["5_what_reference_inference_means"]["decoding_length"]["curve_points_generated_tokens"]
    assert pts == [1, 5, 9]
    for p in ("1, 5 and 9", "MEASURED mean answer length"):
        assert p in ruling
    assert a["5_what_reference_inference_means"]["decoding_length"]["fourth_point"] \
        == "donor_measured_mean_answer_length"
    assert "no point may be added, dropped or headlined selectively" in json.dumps(
        d["pi_rulings"]["D-MPE12-05"]), "the anti-selective-headlining clause lives in the ruling block"
    planned = json.dumps(a["2_repetitions_and_statistic"]["timed_measurements_planned"])
    assert "the fourth curve point cannot be counted until it has a value" in planned
    assert a["2_repetitions_and_statistic"]["timed_measurements_planned"]["read_arm"] == 1800


def test_repetitions_and_statistic_are_named_numbers_not_prose():
    a = art()
    r = a["2_repetitions_and_statistic"]
    assert isinstance(r["repetitions_per_query_per_point_per_arm"], int) and r["repetitions_per_query_per_point_per_arm"] == 25
    assert r["repetitions_per_query_per_point_per_arm"] % 2 == 1, "odd so the median is an observed value"
    assert r["warmup_repetitions_discarded_per_cell"] == 5
    assert r["statistic"] == "median"
    assert r["timed_measurements_planned"]["read_arm"] == 24 * 3 * 25
    assert "interleaved" in r["order_of_repetitions"]
    assert "never as a number with a smaller denominator" in r["a_run_that_stops_early"]
    assert "95th percentile" in r["pass_rule"] and ">= 10" in r["pass_rule"]


def test_identity_is_measured_fields_not_a_description():
    """R15 makes the interpreter a seal component: the record must carry read-back values, including the ones
    that are inconvenient (a GPU controller exists; torch exists; a CIM property returns null)."""
    a = art()
    sec = a["3_hardware_and_interpreter_identity_R15"]
    i = sec["measured_identity"]
    assert i["python"]["version"].count(".") == 2
    assert i["python"]["virtualenv"] is True
    assert i["cpu"]["name"].strip() and i["cpu"]["physical_cores"]
    assert i["memory"]["total_physical_bytes"] > 4 * 2**30
    assert i["machine"]["model"], "the machine model is read from CIM, not typed in"
    assert "how_obtained" in sec["measured_identity"]
    # the inconvenient findings, asserted so they cannot be quietly dropped on a regeneration
    assert i["modules"]["torch"]["available"] is True
    assert i["modules"]["transformers"]["available"] is False
    assert i["modules"]["safetensors"]["available"] is False
    assert "AMD" in i["cpu"]["name"] or "Intel" in i["cpu"]["name"]
    assert i["os"]["win32_operatingsystem_total_physical_memory"] is None, \
        "the null reading is part of the environment's identity; smoothing it out would be R15's failure mode"
    assert "NOT measured" in i["thermal_throttling"]
    assert i["threading_conditions_that_change_wall_clock_and_are_not_yet_pinned"]["OMP_NUM_THREADS"] == "unset"
    assert "not pinned" in json.dumps(sec["measured_identity"]["threading_conditions_that_change_wall_clock_and_are_not_yet_pinned"]) or \
        "unset" in json.dumps(sec["measured_identity"]["threading_conditions_that_change_wall_clock_and_are_not_yet_pinned"])


def test_seal_identity_quoted_from_the_ledger_not_invented():
    """Verify the quote against the commit it NAMES, not against whatever the ledger is stamped at today.

    `seal_identity_at_registration` is a historical record: the anchor, file count and blob hashes as they were when
    the pre-registration was written. The first version of this test compared it to the LIVE seal, so it failed on
    every re-stamp by construction -- and the only way to make that version pass was to edit the quote to chase the
    present, which would turn a historical record into a rolling one and destroy the thing it records. A test that
    can only be satisfied by falsifying the artifact is the defect, not the artifact.

    What is actually checkable, and stronger than equality-with-the-present: the named commit must exist, each
    recorded git_blob_sha1 must equal the blob that commit holds at that path, each recorded sha256 must equal the
    sha256 of those exact bytes, and the named anchor must be an ancestor of the live anchor -- so the quote cannot
    have been invented and cannot name a commit that was later discarded.
    """
    a = art()
    sec = a["3_hardware_and_interpreter_identity_R15"]["seal_identity_at_registration"]
    anchor = sec["git_head"]
    live = json.loads(LEDGER.read_text(encoding="utf-8"))["harness_hashes"]

    assert sec["git_dirty_sealed"] == [], "a seal with uncommitted hashes cannot be quoted as an identity"
    assert subprocess.run(["git", "cat-file", "-t", anchor], capture_output=True, text=True).stdout.strip() == "commit", \
        f"the quoted anchor {anchor[:12]} is not a commit that exists"
    assert subprocess.run(["git", "merge-base", "--is-ancestor", anchor, live["git_head"]]).returncode == 0, \
        "the quoted anchor must be an ancestor of the live anchor, not a dangling commit"

    assert sec["the_read_path_tools_and_their_sealed_hashes"], "the read path must have sealed identities"
    for path, v in sec["the_read_path_tools_and_their_sealed_hashes"].items():
        got = subprocess.run(["git", "rev-parse", f"{anchor}:{path}"], capture_output=True, text=True).stdout.strip()
        assert got == v["git_blob_sha1"], f"{path}: anchor {anchor[:9]} holds {got[:12]}, quote says {v['git_blob_sha1'][:12]}"
        raw = subprocess.run(["git", "cat-file", "blob", f"{anchor}:{path}"], capture_output=True).stdout
        assert hashlib.sha256(raw).hexdigest() == v["sha256_of_git_blob"], f"{path}: sha256 does not match the blob bytes"

    whole = a["3_hardware_and_interpreter_identity_R15"]
    assert "not yet" in whole["consequence_for_the_benchmark_tool_itself"]
    assert "re-bases the figure" in whole["re_baseline_rule"]


def test_the_two_arms_are_named_as_access_classes_not_as_vibes():
    a = art()
    read = a["4_what_budgeted_static_read_means_operationally"]
    assert "class 1" in read["access_class"]
    assert "NOT class 2" in read["access_class"]
    assert "DonorAddressSpace" in read["the_only_access_path"]
    assert "no torch" in read["the_only_access_path"]
    assert "journal append" in read["what_is_inside_the_timed_region"]
    assert "process start" in read["what_is_outside_it"]
    assert "cold" in json.dumps(read) and "warm" in json.dumps(read)
    inf = a["5_what_reference_inference_means"]
    assert "greedy" in inf["decoding_strategy"] and "batch 1" in inf["decoding_strategy"]
    assert "the same GPT-2 124M bytes" in inf["arm"]
    assert "must not be reachable from the read path" in inf["isolation_required"]
    assert "Two processes" in inf["isolation_required"]


def test_caps_are_quoted_unchanged_from_the_sealed_artifacts():
    a = art()
    b = a["4_what_budgeted_static_read_means_operationally"]["budget_as_sealed"]
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    p = json.loads(PROBES.read_text(encoding="utf-8"))
    c = json.loads(CLUST.read_text(encoding="utf-8"))
    assert b["ops_per_item"] == g["read_budget"]["value"] == 24
    assert b["max_rows_per_read"] == p["budgets"]["max_rows_per_read"] == 64
    assert b["max_reads_per_probe"] == p["budgets"]["max_reads_per_probe"] == 256
    assert b["candidate_pool_size"] == c["cost_of_the_current_registration"]["pool_rows"] == 63
    assert b["neighbours_per_item"] == 10 and isinstance(b["neighbours_per_item"], int)
    assert b["conservative_ops_run_for_the_sealed_graph"] == 96
    assert a["prohibitions_observed_in_this_step"]["no_cap_raised"].count("64") == 1
    for n in ("64", "256", "24", "63", "10"):
        assert n in a["prohibitions_observed_in_this_step"]["no_cap_raised"]


def test_the_threshold_is_carried_and_declared_never_re_based():
    a = art()
    t = a["6_the_threshold"]
    assert t["never_re_based_on_the_real_donor"] is True
    assert "ten times" in t["threshold"]
    assert t["status_of_the_claim"].startswith("UNMEASURED against the real donor")
    assert "Not failed, not passed" in t["status_of_the_claim"]
    plan = PLAN.read_text(encoding="utf-8").splitlines()
    n = int(t["plan_line"].rsplit(":", 1)[1])
    assert "at least ten times lower" in plan[n - 1], "the plan line quoted must be the H2 line"
    assert "un-re-based" in t["where_it_would_be_re_based"] or "re-based" in t["where_it_would_be_re_based"]
    # the synthetic calibration figures are named but fenced off from being evidence about GPT-2
    assert "forbids quoting" in t["what_exists_now"]


def test_R11_is_confronted_and_left_open_rather_than_resolved():
    a = art()
    r = a["7_R11_confronted_here_rather_than_at_the_bench"]
    assert r["rule_verbatim"].startswith("- **R11")
    assert "run once, offline" in r["the_sanctioned_execution_verbatim"]
    assert "requires running the donor" in r["plain_statement"]
    assert len(r["the_argument_that_it_is_the_same_category"]) >= 3
    assert len(r["the_argument_that_it_is_a_new_exception"]) >= 4
    nq = r["named_question_for_the_PI"]
    assert nq["proposed_identifier"] == "D-MPE12-09"
    assert "not resolving it" in nq["what_I_am_not_doing"]
    assert "cannot be measured AT ALL" in nq["consequence_if_the_answer_is_no"]
    assert "unfalsifiable" in nq["consequence_if_the_answer_is_no"]
    assert len(nq["sub_questions_the_answer_must_settle"]) >= 4


def test_proposed_identifier_does_not_collide_with_the_live_key_set():
    """AMD-MPE10-11: a proposed identifier is checked against the live key set BEFORE it is written down.

    The obvious next number after the ledger's five decisions was 06, and 06/07/08 were already taken by the
    MP-E12b compiler document. This test re-derives the live set from the files rather than trusting the list
    embedded in the artifact, because an embedded list is exactly as stale as the run that wrote it.
    """
    a = art()
    nq = a["7_R11_confronted_here_rather_than_at_the_bench"]["named_question_for_the_PI"]
    proposed = nq["proposed_identifier"]
    assert proposed == "D-MPE12-09"

    # A DECISION is an entry in a decisions block or a bolded item in a document. The proposal itself now names
    # D-MPE12-09 in the ledger and in this artifact, so a test that merely grepped for the string would fail the
    # moment the registration succeeded -- a check that breaks when it passes is not a check. What matters is that
    # no pre-existing decision owns the number.
    for f in [LEDGER] + OTHER_LEDGERS:
        d = json.loads(f.read_text(encoding="utf-8"))
        for blk in ("open_decisions", "open_decisions_for_PI", "decisions"):
            if isinstance(d.get(blk), dict):
                assert proposed not in d[blk], f"{proposed} already a decision key in {f} -> {blk}"
    for f in list(Path("docs").glob("*.md")) + [PLAN]:
        body = f.read_text(encoding="utf-8", errors="replace")
        assert f"**{proposed}**" not in body, f"{proposed} is already defined in {f}"
        assert f"**{proposed}" not in body

    # the eight ids the artifact claims are in use must really be decisions, not echoes
    preexisting = set()
    for f in [LEDGER] + OTHER_LEDGERS + list(Path("docs").glob("*.md")):
        body = f.read_text(encoding="utf-8", errors="replace")
        preexisting.update(re.findall(r"\*?\*?D-MPE12-0(\d)\*?\*?", body))
        d = json.loads(Path(f).read_text(encoding="utf-8")) if f.suffix == ".json" else None
    got = set()
    for f in [LEDGER] + OTHER_LEDGERS:
        d = json.loads(f.read_text(encoding="utf-8"))
        for blk in ("open_decisions", "open_decisions_for_PI"):
            if isinstance(d.get(blk), dict):
                got.update(k.split("_")[0] for k in d[blk])
    for f in list(Path("docs").glob("*.md")):
        got.update(re.findall(r"\*\*(D-MPE12-\d+)\*\*", f.read_text(encoding="utf-8", errors="replace")))
    assert {f"D-MPE12-0{i}" for i in range(1, 9)} <= got, f"missing from the real decision set: {sorted(set(f'D-MPE12-0{i}' for i in range(1,9)) - got)}"
    assert nq["identifier_checked_against_the_live_key_set_before_being_written"]["collision"] is False


def test_R17_reading_is_registered_and_names_the_right_rule_for_each_quantity():
    a = art()
    r = a["8_R17_what_it_does_and_does_not_require_here"]
    assert r["rule_verbatim"].startswith("- **R17")
    blob = json.dumps(r)
    assert "does not require a fresh-vs-" in blob or "fresh-vs-fresh floor pair for a latency figure" in blob
    assert "dispersion INSIDE the same process" in blob
    assert "R15 and R16, not R17" in blob
    m = r["quantity_to_rule_map"]
    assert len(m) == 4
    assert "no floor" in m["per-association read cost"]
    assert "D-MPE12-09" in m["per-association inference cost"]
    assert "R17 applies in full" in m["any behavioural claim resting on a latency figure"]
    assert "never carries a behavioural claim across that boundary" in blob


def test_the_tool_is_stdlib_only_and_reads_no_donor_bytes():
    src = TOOL.read_text(encoding="utf-8")
    mods = set(re.findall(r"^\s*(?:from|import)\s+([\w\.]+)", src, re.M))
    allowed = {"argparse", "json", "os", "platform", "shutil", "subprocess", "sys", "datetime", "pathlib", "__future__"}
    assert mods <= allowed, f"unexpected imports: {sorted(mods - allowed)}"
    for forbidden in ("torch", "transformers", "tokenizers", "safetensors", "numpy"):
        assert f"import {forbidden}" not in src and f"from {forbidden}" not in src
    assert "safetensors" not in [m for m in mods]
    # the identity probe names modules as strings to import at runtime; that is a measurement of the environment,
    # not a use of them -- asserted so a future edit cannot turn the string list into a real dependency
    assert "time.perf_counter" not in src and "perf_counter" not in src, "this tool must not be able to time anything"


def test_quoted_plan_lines_resolve_to_the_claims_they_are_cited_for():
    a = art()
    plan = PLAN.read_text(encoding="utf-8").splitlines()
    checks = {
        "7_R11_confronted_here_rather_than_at_the_bench.rule_line": ("R11 — The library is addressed",),
        "8_R17_what_it_does_and_does_not_require_here.rule_line": ("R17 — No behavioural claim",),
        "7_R11_confronted_here_rather_than_at_the_bench.sanctioned_execution_line": ("The control (the rival",),
    }
    for dotted, needles in checks.items():
        sec, field = dotted.split(".", 1)
        ln = int(a[sec][field].rsplit(":", 1)[1])
        for nd in needles:
            assert nd in plan[ln - 1], f"{dotted} -> line {ln} does not contain {nd!r}"
    for entry in a["quoted_sources"]["plan_lines_quoted_verbatim"]:
        ln = int(entry.rsplit(":", 1)[1])
        assert 0 < ln <= len(plan), f"{entry} out of range"
    assert "any donor forward pass detected in the deployment loop" in a["c4_sentence_extracted_from_that_line"]


def test_preconditions_are_a_list_and_include_the_ruling_and_the_sealed_tool():
    a = art()
    pre = " ".join(a["9_preconditions_of_the_run_this_registers"])
    assert "D-MPE12-09" in pre
    assert "sealed" in pre and "thread" in pre and "cold and warm" in pre
    assert len(a["9_preconditions_of_the_run_this_registers"]) >= 5
