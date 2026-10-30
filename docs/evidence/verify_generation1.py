"""Verify generation 1: the stamps, the operator, and the culling rule.

Structural checks and rule-consistency checks only. It does NOT assert a score, a
winner or a direction -- a verifier that knows the answer it expects is a verifier
that cannot be surprised, and the whole point of the run is that the direction was
not known.

What it pins:
  stamps      every line carries interpreter, numpy, git head, genome id, parent
              lineage and its mutation values (step 2 of the instruction)
  population  1 control clone + 3 mutants; the control is the parent byte for byte;
              each mutant differs from the parent in exactly ONE gene
  operator    the gene is the pre-registered one, sigma 0.05, bounds [0.45, 0.75],
              value == clip(parent + draw), and the draw is regenerable from the
              recorded seed
  guards      every line reports genome_verified, shim_clean and a clean state guard
  culling     the decision follows the stated rule when recomputed from the rows:
              eligible == zero frozen passes lost AND zero guarded probes lost,
              survivor == best eligible strictly above the control key, ties and
              no-gain keep the parent, no eligible mutant is a stall
  movement    every mutant names the asks that changed rather than only counting them

Despite the filename this is generation-parameterised and makes no assumption
specific to generation 1 -- it was written for that run and the name stuck. Use
--generation N for any mutant generation. Generation 0 has its own checker,
verify_selection_checkpoint.py, because a clone generation has no mutation, no
culling decision and no movement blocks to verify.

  py -3.10 docs/evidence/verify_generation1.py [--generation 1]
"""
import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import tools.run_generation as rg  # noqa: E402

fails, total = [], []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    total.append(msg)
    if not cond:
        fails.append(msg)


ap = argparse.ArgumentParser()
ap.add_argument("--generation", type=int, default=1)
a = ap.parse_args()

path = rg.SEL_DIR / f"generation_{a.generation}.jsonl"
if not path.exists():
    print(f"no generation {a.generation} at {path}")
    sys.exit(1)
rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
base = json.loads((rg.SEL_DIR / "base_genome.json").read_text(encoding="utf-8"))
bl = json.loads(rg.BASELINE.read_text(encoding="utf-8"))
spec = rg.MUTATIONS["answer.ANSWER_COVERAGE_FLOOR"]

print(f"generation {a.generation}: {len(rows)} lines from {path.name}")

print("\npopulation")
check(len(rows) == 4, f"4 lines, 1 control + 3 mutants (got {len(rows)})")
ctrl = [r for r in rows if not r.get("mutation")]
muts = [r for r in rows if r.get("mutation")]
check(len(ctrl) == 1, f"exactly one control (got {len(ctrl)})")
check(len(muts) == 3, f"exactly three mutants (got {len(muts)})")
ctrl = ctrl[0] if ctrl else None
if ctrl:
    check(ctrl["operator"] == "control-clone", f"control operator {ctrl['operator']}")
    check(ctrl["genome_id"] == base["genome_id"],
          f"control genome is the parent ({ctrl['genome_id']})")
    # A row's "genome" field IS the genes block (evaluate_line stores genome["genes"]).
    check(rg.canon(ctrl["genome"]) == rg.canon(base["genes"]),
          "control genes are the parent's byte for byte")
    check(ctrl["parent_genome_id"] in (None, base["genome_id"]),
          f"control parent {ctrl['parent_genome_id']}")

print("\nstamps (step 2: interpreter, numpy, git head, genome id, lineage, mutation)")
for r in rows:
    p = r["provenance"]
    check(bool(p.get("python")), f"{r['line']} interpreter stamped: {p.get('python')}")
    check(bool(p.get("numpy")), f"{r['line']} numpy stamped: {p.get('numpy')}")
    check(bool(p.get("head")), f"{r['line']} git head stamped: {p.get('head')}")
    check(len(r["genome_id"]) == 12, f"{r['line']} genome id {r['genome_id']}")
    check(isinstance(r.get("lineage"), list) and r["lineage"][-1] == r["genome_id"],
          f"{r['line']} lineage {r.get('lineage')}")
    check("mutation" in r, f"{r['line']} carries a mutation field")
for r in rows:
    check(r["lineage"][0] == base["genome_id"],
          f"{r['line']} lineage roots at the committed parent")
check(len({r["provenance"]["python"] for r in rows}) == 1, "one interpreter for all lines")
check(len({r["provenance"]["head"] for r in rows}) == 1, "one git head for all lines")

print("\nthe operator is the pre-registered one and nothing else")
for r in muts:
    mv = r["mutation"]
    check(mv["gene"] == "answer.ANSWER_COVERAGE_FLOOR", f"{r['line']} gene {mv['gene']}")
    check(mv["operator"] == "gauss_single_gene", f"{r['line']} operator {mv['operator']}")
    check(mv["sigma"] == spec["sigma"], f"{r['line']} sigma {mv['sigma']}")
    check(mv["bounds"] == list(spec["bounds"]), f"{r['line']} bounds {mv['bounds']}")
    check(mv["parent_value"] == spec["base"],
          f"{r['line']} parent value {mv['parent_value']} == declared base {spec['base']}")
    lo, hi = spec["bounds"]
    check(lo <= mv["value"] <= hi, f"{r['line']} value {mv['value']} inside bounds")
    want = round(min(hi, max(lo, mv["parent_value"] + mv["draw"])), 6)
    check(mv["value"] == want, f"{r['line']} value == clip(parent + draw) = {want}")
    check(mv["clipped"] == bool(mv["raw"] < lo or mv["raw"] > hi),
          f"{r['line']} clip flag consistent (raw {mv['raw']})")
    check(abs(mv["delta"] - (mv["value"] - mv["parent_value"])) < 1e-9,
          f"{r['line']} delta {mv['delta']} consistent")
    # exactly one gene moved
    diff = [(s, k) for s in base["genes"] for k in base["genes"][s]
            if base["genes"][s][k] != r["genome"][s][k]]
    check(diff == [("answer", "ANSWER_COVERAGE_FLOOR")],
          f"{r['line']} moved exactly one gene: {diff}")
    check(r["parent_genome_id"] == base["genome_id"],
          f"{r['line']} parent is the committed base")
    check(r["genome_id"] == rg.gid(r["genome"]),
          f"{r['line']} genome id re-derives from its genes")
check(len({r["genome_id"] for r in muts}) == len(muts) or
      all(m["mutation"]["clipped"] for m in muts),
      "mutant genome ids are distinct (or identical only because both clipped)")

print("\ndraws regenerate from the recorded seed")
seeds = {r["mutation"]["rng_seed"] for r in muts}
check(len(seeds) == 1, f"one mutation seed for the generation: {sorted(seeds)}")
rng = random.Random(next(iter(seeds)))
again = [round(rng.gauss(0.0, spec["sigma"]), 6) for _ in muts]
recorded = [r["mutation"]["draw"] for r in
            sorted(muts, key=lambda r: r["mutation"]["draw_index"])]
check(again == recorded, f"regenerated {again} == recorded {recorded}")
check([r["mutation"]["draw_index"] for r in
       sorted(muts, key=lambda r: r["mutation"]["draw_index"])] == [1, 2, 3],
      "draw indices are 1, 2, 3")

print("\nguards and evaluation integrity")
for r in rows:
    check(r["genome_verified"] is True, f"{r['line']} genome verified")
    check(r["shim_clean"] is True, f"{r['line']} shim clean")
    check(r["guard"]["live_files_untouched"] is True, f"{r['line']} state guard clean")
    check(r["asks"] == 42, f"{r['line']} ran the full 42-ask battery (got {r['asks']})")
    cap = r["fitness"]["capability"]
    check(cap["asked"] == 24, f"{r['line']} frozen tier is the whole 24")
    check(r["fitness"]["seals"]["frozen"] == bl["frozen_seal"],
          f"{r['line']} frozen seal matches the baseline")
    check(r["fitness"]["seals"]["probes"] == bl["probe_seal"],
          f"{r['line']} probe seal matches the baseline")
    check("partial-run" not in (r["fitness"].get("labels") or []),
          f"{r['line']} is a full run, not a chunk")

print("\nculling decision recomputed from the rows")
dec = ctrl.get("culling") if ctrl else None
check(dec is not None, "a culling decision is recorded")
if dec:
    check(all(r.get("culling") == dec for r in rows),
          "the same decision is stamped into every line")
    elig = [r["line"] for r in muts
            if r["fitness"]["regression"]["frozen_lost_n"] == 0
            and not r["fitness"]["regression"]["probe_guard_lost"]]
    check(sorted(dec["eligible"]) == sorted(elig),
          f"eligible recomputed {elig} == recorded {dec['eligible']}")
    ckey = list(ctrl["fitness"]["select_key"])
    check(dec["control_key"] == ckey, f"control key {ckey}")
    better = [r["line"] for r in muts
              if r["line"] in elig and list(r["fitness"]["select_key"]) > ckey]
    check(sorted(dec["better_than_control"]) == sorted(better),
          f"better-than-control recomputed {better} == recorded {dec['better_than_control']}")
    if better:
        want = max((r for r in muts if r["line"] in better),
                   key=lambda r: (list(r["fitness"]["select_key"]), r["line"]))
        check(dec["outcome"] == "survivor", f"outcome {dec['outcome']} == survivor")
        check(dec["survivor_line"] == want["line"],
              f"survivor {dec['survivor_line']} == best eligible {want['line']}")
    elif elig:
        check(dec["outcome"] == "no_gain", f"outcome {dec['outcome']} == no_gain")
        check(dec["survivor_genome_id"] == base["genome_id"], "the parent stands on a tie")
    else:
        check(dec["outcome"] == "stall", f"outcome {dec['outcome']} == stall")
        check(dec["survivor_genome_id"] == base["genome_id"], "the parent stands on a stall")
        check(bool(dec["stall_rule"]), "the stall rule is quoted in the record")
    check(len(dec["ineligible"]) == len(muts) - len(elig),
          f"{len(dec['ineligible'])} ineligible accounted for")

print("\nmovement is reported per mutant, by name")
for r in muts:
    m = r.get("movement")
    check(isinstance(m, dict), f"{r['line']} carries a movement block")
    if m:
        check("stage_delta" in m and "recall_delta" in m,
              f"{r['line']} stage movement recorded")
        check(isinstance(m["guard_lost"], list) and isinstance(m["guard_gained"], list),
              f"{r['line']} guarded-probe movement named, not counted")
        check(isinstance(m["paraphrase_gained"], list),
              f"{r['line']} paraphrase movement named, not counted")
        check(m["recall_moved_out"] == (m["recall_delta"] < 0),
              f"{r['line']} recall_moved_out consistent with recall_delta "
              f"{m['recall_delta']}")

print("\nthe generalisation tier was reported and not selected on")
for r in rows:
    fit = r["fitness"]
    check(fit["select_key"][0] in (0, 1) and fit["select_key"][1] >= 0,
          f"{r['line']} select key {fit['select_key']}")
    # The key's third term is the paraphrase count, which is allowed to be there;
    # what is NOT allowed is the paraphrase tier deciding eligibility.
    reg = fit["regression"]
    check("paraphrase" not in json.dumps(reg).lower(),
          f"{r['line']} eligibility does not consult the paraphrase tier")

print(f"\n{len(fails)} failed of {len(total)} checks: "
      f"{'ALL PASSED' if not fails else 'FAILED'}")
for f in fails:
    print("   - " + f)
sys.exit(1 if fails else 0)
