"""Verify the generation-0 selection checkpoint against the committed records.

Asserts rather than prints: a checkpoint nobody can fail is not a checkpoint.
Every number quoted in docs/selection_design.md section 10 and in the
"Selection harness baseline" table of docs/STATE.md is re-derived here from
state/selection/generation_0.jsonl, its per-ask journal, and
tools/selection_baseline.json -- 80 checks, exit 1 on any failure.

What it pins beyond the arithmetic: that the three clone lines are the SAME
genome, that the per-ask journal agrees with the per-line rows (one of the two
records lying is the failure this exists for), that the three probe tiers account
for every probe exactly once with none in two, that every guarded probe really
passed at base and no paraphrase probe did, and that the seals and git head in the
baseline are the ones the design doc quotes.

  py -3.10 docs/evidence/verify_selection_checkpoint.py

Note on depth: this file is two directories down, so ROOT is parents[2]. The
sibling verify_seal.py uses parents[1], which resolves to docs/ and would make its
own state paths point at docs/state -- left alone here because fixing it is not
this checkpoint's business, but recorded so nobody copies it.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEL = ROOT / "state" / "selection"
BASELINE = ROOT / "tools" / "selection_baseline.json"

fails = []
total = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    total.append(msg)
    if not cond:
        fails.append(msg)


rows = [json.loads(l) for l in
        (SEL / "generation_0.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
asks = [json.loads(l) for l in
        (SEL / "generation_0_asks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
bl = json.loads(BASELINE.read_text(encoding="utf-8"))

print("generation_0.jsonl")
check(len(rows) == 3, f"3 lines (got {len(rows)})")
check([r["line"] for r in rows] == ["g0-1", "g0-2", "g0-3"],
      f"line ids {[r['line'] for r in rows]}")
check(len({r["genome_id"] for r in rows}) == 1,
      f"one genome id {sorted({r['genome_id'] for r in rows})}")
check(all(r["genome_id"] == "abffa2b7f101" for r in rows), "genome id is abffa2b7f101")
check(all(r["operator"] == "clone" for r in rows), "every line is a clone")
check(all(r["parent_genome_id"] is None for r in rows), "no parent (founder line)")

print("\nper-line scores")
for r in rows:
    cap = r["fitness"]["capability"]
    gen = r["fitness"]["generalisation"]
    check(cap["asked"] == 24 and cap["passed"] == 19,
          f"{r['line']} frozen {cap['passed']}/{cap['asked']} == 19/24")
    check(gen["probe_asked"] == 18 and gen["probe_passed"] == 4,
          f"{r['line']} probes {gen['probe_passed']}/{gen['probe_asked']} == 4/18")
    check(r["fitness"]["stages"] == {"recall": 10, "mouth": 4, "gating": 3,
                                     "shape_arbiter": 2},
          f"{r['line']} stages {json.dumps(r['fitness']['stages'])}")
    check(r["genome_verified"] is True, f"{r['line']} genome_verified")
    check(r["shim_clean"] is True, f"{r['line']} shim_clean")
    check(r["guard"]["live_files_untouched"] is True, f"{r['line']} state guard clean")
    check(r["asks"] == 42, f"{r['line']} ran 42 asks (got {r['asks']})")

print("\nidentity across clones")
sets = [set(r["fitness"]["capability"]["pass_set"]) for r in rows]
check(len(sets[0]) == 19, f"pass set has 19 ids (got {len(sets[0])})")
check(sets[0] == sets[1] == sets[2], "frozen pass sets identical across all 3 lines")
psets = [set(r["fitness"]["generalisation"]["probe_pass_set"]) for r in rows]
check(psets[0] == psets[1] == psets[2], "probe pass sets identical across all 3 lines")
check(len(psets[0]) == 4, f"probe pass set has 4 ids (got {len(psets[0])})")
union = set().union(*sets)
check(len(union) == 19, f"zero asks changed membership (union {len(union)} == 19)")
stages = [json.dumps(r["fitness"]["stages"], sort_keys=True) for r in rows]
check(len(set(stages)) == 1, "failure-stage distribution identical")

print("\nask journal")
check(len(asks) == 126, f"126 ask rows (got {len(asks)})")
check(sum(1 for a in asks if a["tier"] == "frozen") == 72, "72 frozen ask rows")
check(sum(1 for a in asks if a["tier"] == "probe") == 54, "54 probe ask rows")
check(all(a.get("genome_applied") for a in asks), "every ask reported its genome applied")
check(all((a.get("shim") or {}).get("clean") for a in asks),
      "every ask passed the shim check")
per_line = {}
for a in asks:
    per_line.setdefault(a["line"], []).append(a)
check(all(len(v) == 42 for v in per_line.values()),
      f"42 asks per line {[len(v) for v in per_line.values()]}")
# The journal's own pass counts must agree with the line rows, or one of the two
# records is not describing the run.
for r in rows:
    got = sum(1 for a in per_line[r["line"]]
              if a["tier"] == "frozen" and a["pass"])
    check(got == r["fitness"]["capability"]["passed"],
          f"{r['line']} journal frozen passes {got} == row "
          f"{r['fitness']['capability']['passed']}")

print("\nbaseline")
check(bl["clones"] == 3, f"baseline built from 3 clones (got {bl['clones']})")
check(bl["genome_id"] == "abffa2b7f101", "baseline genome id matches")
check(len(bl["frozen_pass_set"]) == 19, f"19 frozen passes (got {len(bl['frozen_pass_set'])})")
check(len(bl["frozen_fail_set"]) == 5, f"5 frozen failures (got {len(bl['frozen_fail_set'])})")
check(bl["frozen_unstable"] == [], f"frozen_unstable empty (got {bl['frozen_unstable']})")
check(len(bl["regression_pass_set"]) == 4,
      f"4 regression-guard probes (got {len(bl['regression_pass_set'])})")
check(len(bl["paraphrase_set"]) == 14,
      f"14 paraphrase probes (got {len(bl['paraphrase_set'])})")
check(bl["probe_ambiguous"] == [], f"probe_ambiguous empty (got {bl['probe_ambiguous']})")
check(set(bl["frozen_pass_set"]) == sets[0],
      "baseline frozen pass set == every clone's pass set")
all_probe_ids = {a["id"] for a in asks if a["tier"] == "probe"}
check(len(all_probe_ids) == 18, f"18 distinct probe ids in the journal (got {len(all_probe_ids)})")
check(set(bl["regression_pass_set"]) | set(bl["paraphrase_set"])
      | set(bl["probe_ambiguous"]) == all_probe_ids,
      "the three tiers account for every probe exactly once")
check(len(set(bl["regression_pass_set"]) & set(bl["paraphrase_set"])) == 0,
      "no probe is in both tiers")
check(set(bl["regression_pass_set"]) <= psets[0],
      "every guarded probe actually passed at base")
check(not (set(bl["paraphrase_set"]) & psets[0]),
      "no paraphrase probe passed at base")
check(bl["frozen_seal"] == "b9d0f2d83fbb7e78", f"frozen seal {bl['frozen_seal']}")
check(bl["probe_seal"] == "6b6117e9e0a7c331", f"probe seal {bl['probe_seal']}")
check(bl["git_head"] == "8af3ed9", f"git head {bl['git_head']}")

print("\nbaseline vs the committed floor in docs/STATE.md")
# STATE.md wraps prose, so two of the five asks are split across a newline
# ("what is wet but not on the\nhook?"). Compare on collapsed whitespace: the
# claim is that the ask is listed, not that it is listed on one line.
state_md = " ".join((ROOT / "docs" / "STATE.md").read_text(encoding="utf-8").split())
for a in bl["frozen_fail_set"]:
    ask = " ".join(a.split("::", 1)[1].split())
    check(ask in state_md, f"recorded failure still listed in STATE.md: {ask[:44]}")
check("19/24" in state_md, "STATE.md still records the 19/24 floor")

print("\nprovenance")
for r in rows:
    p = r["provenance"]
    check(p["as_found"]["epsilon"] == p["as_found"]["birth_epsilon"],
          f"{r['line']} epsilon at birth ({p['as_found']['epsilon']})")
    check(p["as_found"]["decisions"] == 0, f"{r['line']} no decisions during build")
    check(p["substrate"]["control"] is False, f"{r['line']} experimental carve")
    check(p["n_nodes"] == 12867, f"{r['line']} 12867 neurons")
    check(p["teaching_history"]["vocabulary"] == 11555,
          f"{r['line']} vocabulary 11555")

print(f"\n{len(fails)} failed of {len(total)} checks: "
      f"{'ALL PASSED' if not fails else 'FAILED'}")
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
