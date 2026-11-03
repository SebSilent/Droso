"""MP-E9 battery instrument: turn a run_generation journal into H4's measured state.

WHY THIS EXISTS.  H4's threshold says "battery frozen 19/24 with ELECTRIC off AND battery
guarded 4/4".  For three weeks that clause was carried as prose copied out of a generation
journal nobody re-read.  A threshold with no instrument is a quotation, and a quotation cannot
fail -- so it cannot hold either.  This tool makes the battery clause measurable and puts the
four numbers behind the same registration-driven check the other hypotheses use.

SINGLE SOURCE OF TRUTH, twice over:
  * the guarded/paraphrase/frozen SPLIT is read from tools/selection_baseline.json, which is
    what tools/run_generation.py --freeze-baseline wrote from measured clone outcomes.  The
    four guarded ids are NOT restated here.  They are also hard-coded in
    tests/test_stage_cause.py as GUARDED_PROBES; if this instrument and that test ever
    disagree about which probes are guarded, one of them is wrong, and the disagreement is
    reported in `split_consistency` rather than hidden.
  * the EXPECTED numbers are read from the registration's H4 numeric_thresholds, not from
    literals in this file.  Changing a threshold changes the verdict without touching code.

IT DOES NOT RUN THE BATTERY.  Running it is tools/run_generation.py's job and costs ~18 min
for one line over 42 asks.  This tool reads what that run wrote.  The separation is
deliberate: the measurement and the grading of the measurement must be different files, so
that re-grading an old journal cannot silently become a new measurement.

ELECTRIC OFF IS VERIFIED, NOT ASSERTED.  tools/run_generation.py:1410-1416 stamps
electric_teach / electric_answer into provenance.code_flags on EVERY path, "per the E25
invariant that a missing key must never be indistinguishable from a deliberate off".  A run
whose journal predates those keys is reported as `unrecorded`, not as off.  That is a real
limitation of the historical baseline and it stays visible.

COMMIT NAMING, and why the artifact does not name its own commit.  The G0-prime ordering
defect was a record naming a commit that did not contain the bytes it sealed.  This file
therefore names ONLY the commit the measurement ran under.  The commit that CONTAINS this
artifact is recorded in seal.json and is resolvable by `git log -- <this path>`; the seal's
anchor check is what proves the two are consistent.

  py tools/mp_e9_battery.py --journal state/selection/generation_9001_asks.jsonl \
      --rows state/selection/generation_9001.jsonl \
      --out experiments/MP-E9/results/battery_pre_flag.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "tools" / "selection_baseline.json"
REGISTRATION = ROOT / "experiments" / "MP-E9" / "registration.json"


def sha256_lf(path: Path) -> str:
    """LF-normalised hash -- the same form the seal uses, so the two agree by construction."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def git(*args: str) -> str:
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else ""


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def split_consistency(rows: list[dict], base: dict) -> dict:
    """Do the baseline's split and tests/test_stage_cause.py's GUARDED_PROBES still agree?

    A probe is guarded if its id is in regression_pass_set.  The test file names four probes
    by short name (R-count-moon, ...).  If the two sets have different sizes the split moved
    and every guarded number this tool prints is suspect.
    """
    guarded_ids = set(base.get("regression_pass_set") or [])
    test_src = ROOT / "tests" / "test_stage_cause.py"
    named: list[str] = []
    if test_src.exists():
        # Parse the constant rather than import it: importing tests drags in pytest fixtures.
        import ast
        for node in ast.parse(test_src.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "GUARDED_PROBES":
                named = sorted(ast.literal_eval(node.value))
    return {
        "regression_pass_set_n": len(guarded_ids),
        "test_guarded_probes_n": len(named),
        "test_guarded_probes": named,
        "sizes_agree": len(guarded_ids) == len(named) if named else None,
        "note": ("sizes agree" if named and len(guarded_ids) == len(named) else
                 "MISMATCH or constant not found -- the guarded count is not cross-checked"),
    }


def electric_state(rows_journal: list[dict]) -> dict:
    """What the journal says about ELECTRIC.  Three outcomes, and `unrecorded` is one of them."""
    if not rows_journal:
        return {"verified": False, "state": "no rows journal"}
    flags = (rows_journal[0].get("provenance") or {}).get("code_flags") or {}
    teach = flags.get("electric_teach")
    answer = flags.get("electric_answer")
    if teach is None and answer is None:
        return {"verified": False, "state": "unrecorded (journal predates the code_flags keys)",
                "code_flags": flags}
    off = (teach is False) and (answer is False)
    return {"verified": True, "state": "off" if off else "ON",
            "electric_teach": teach, "electric_answer": answer, "code_flags": flags}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--journal", required=True, help="generation_N_asks.jsonl to grade")
    ap.add_argument("--rows", default=None, help="generation_N.jsonl (provenance source)")
    ap.add_argument("--baseline", default=str(BASELINE))
    ap.add_argument("--registration", default=str(REGISTRATION))
    ap.add_argument("--out", default=None, help="write the artifact here")
    ap.add_argument("--invocation", default="", help="the command line that produced the journal")
    a = ap.parse_args()

    # Comma-separated: a chunked --only run writes one journal per chunk, and the harness itself
    # says a partial run must be "visibly partial" (run_generation.py:880-887). Merging here keeps
    # that honesty -- the merge records which chunks fed it.
    def _paths(s):
        return [Path(x) for x in s.split(",") if x.strip()]

    jpaths = [p if p.is_absolute() else ROOT / p for p in _paths(a.journal)]
    rows = []
    for jp in jpaths:
        rows.extend(read_jsonl(jp))
    if not rows:
        print(f"ABORT: no rows in {a.journal}", file=sys.stderr)
        return 2

    base = json.loads(Path(a.baseline).read_text(encoding="utf-8"))
    reg = json.loads(Path(a.registration).read_text(encoding="utf-8"))
    thr = ((reg.get("hypotheses") or {}).get("H4") or {}).get("numeric_thresholds") or {}
    row_journals = []
    if a.rows:
        for rp in _paths(a.rows):
            rp = rp if rp.is_absolute() else ROOT / rp
            row_journals.append((rp, read_jsonl(rp)))
    genomes = {(r or [{}])[0].get("genome_id") for _, r in row_journals if r}
    if len(genomes) > 1:
        print(f"ABORT: chunks disagree on genome {sorted(genomes)} -- not one measurement",
              file=sys.stderr)
        return 2

    frozen = [r for r in rows if r.get("tier") == "frozen"]
    guarded_ids = set(base.get("regression_pass_set") or [])
    para_ids = set(base.get("paraphrase_set") or [])
    guarded = [r for r in rows if r.get("id") in guarded_ids]
    para = [r for r in rows if r.get("id") in para_ids]

    frozen_pass = sorted(r["id"] for r in frozen if r.get("pass"))
    exp_pass = sorted(base.get("frozen_pass_set") or [])
    per_chunk_flags = {}
    for rp, rj in row_journals:
        if rj:
            per_chunk_flags[rp.name] = ((rj[0].get("provenance") or {}).get("code_flags") or {})
    states = {f.get("electric_teach") for f in per_chunk_flags.values()}
    all_off = bool(per_chunk_flags) and all(
        f.get("electric_teach") is False and f.get("electric_answer") is False
        for f in per_chunk_flags.values())
    elec = ({"verified": True, "state": "off" if all_off else "ON or mixed",
             "chunks": len(per_chunk_flags)}
            if per_chunk_flags and not (None in states)
            else {"verified": False, "state": "unrecorded (journal predates code_flags)",
                  "chunks": len(per_chunk_flags)})

    measured = {
        "frozen_correct": len(frozen_pass),
        "frozen_total": len(frozen),
        "guarded_pass": sum(1 for r in guarded if r.get("pass")),
        "guarded_total": len(guarded_ids),
        "paraphrase_pass": sum(1 for r in para if r.get("pass")),
        "paraphrase_total": len(para_ids),
        "asked_rows": len(rows),
    }
    # NAMED differences, never a count: a changed ask is a different claim, not a smaller score.
    differences = {
        "frozen_lost_vs_baseline": sorted(set(exp_pass) - set(frozen_pass)),
        "frozen_gained_vs_baseline": sorted(set(frozen_pass) - set(exp_pass)),
        "guarded_not_asked": sorted(guarded_ids - {r.get("id") for r in rows}),
        "guarded_failed": sorted(r["id"] for r in guarded if not r.get("pass")),
    }

    checks = {
        "battery_frozen_correct": (measured["frozen_correct"], thr.get("battery_frozen_correct")),
        "battery_frozen_total": (measured["frozen_total"], thr.get("battery_frozen_total")),
        "battery_guarded_pass": (measured["guarded_pass"], thr.get("battery_guarded_pass")),
        "battery_guarded_total": (measured["guarded_total"], thr.get("battery_guarded_total")),
    }
    verdict = {}
    for k, (got, want) in checks.items():
        verdict[k] = {"measured": got, "expected": want, "pass": (want is not None and got == want)}
    verdict["electric_off"] = {"measured": elec["state"], "pass": bool(elec["verified"] and elec["state"] == "off")}
    verdict["no_frozen_ask_lost"] = {
        "measured": differences["frozen_lost_vs_baseline"],
        "pass": not differences["frozen_lost_vs_baseline"]}
    all_pass = all(v["pass"] for v in verdict.values())

    first = (row_journals[0][1] or [{}])[0] if row_journals else {}
    prov = first.get("provenance") or {}
    heads = sorted({((rj[0].get("provenance") or {}).get("head") if rj else None)
                    for _, rj in row_journals})
    run_seconds = round(sum((rj[0].get("seconds") or 0) for _, rj in row_journals if rj), 1)
    art = {
        "schema": "droso.battery.v1",
        "experiment": "MP-E9",
        "role": "H4 battery clause, measured before any MP-E9 treatment (pre-flag)",
        "written_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "measured": measured,
        "differences": differences,
        "verdict": verdict,
        "h4_battery_clause_pass": all_pass,
        "provenance": {
            "journals": [str(p.relative_to(ROOT)).replace("\\", "/") for p in jpaths],
            "journal_sha256_lf": {p.name: sha256_lf(p) for p in jpaths},
            "journal_bytes": {p.name: p.stat().st_size for p in jpaths},
            "chunk_row_journals": [rp.name for rp, _ in row_journals],
            "generation": first.get("generation"),
            "generations": sorted({rj[0].get("generation") for _, rj in row_journals if rj}),
            "line": first.get("line"),
            "genome_id": first.get("genome_id"),
            "operator": first.get("operator"),
            "run_seconds": run_seconds,
            "chunk_heads": heads,
            "single_commit_measurement": len(heads) == 1,
            "measured_under_commit": prov.get("head") or None,
            "measured_under_commit_dirty": prov.get("dirty") if prov else None,
            "interpreter": prov.get("python") or sys.version.split()[0],
            "numpy": prov.get("numpy") or None,
            "n_nodes": prov.get("n_nodes") or None,
            "plastic_synapses": prov.get("plastic_synapses") or None,
            "code_flags": prov.get("code_flags") or None,
            "electric": elec,
            "invocation": a.invocation or None,
            "baseline_file": str(Path(a.baseline).relative_to(ROOT)).replace("\\", "/")
                             if str(Path(a.baseline)).startswith(str(ROOT)) else a.baseline,
            "baseline_frozen_seal": base.get("frozen_seal"),
            "baseline_probe_seal": base.get("probe_seal"),
            "baseline_frozen_at": base.get("frozen_at"),
            "containing_commit_note": (
                "This block names the commit the MEASUREMENT ran under. It does not name the "
                "commit that contains this artifact, because an artifact cannot attest to its "
                "own inclusion -- that is the G0-prime ordering defect. The containing commit "
                "is in seal.json and is proven by tools/registration_seal.py --check's anchor "
                "axis (git ls-tree -r <git_head>)."),
            "commit_at_write": git("rev-parse", "HEAD"),
            "tree_at_write": git("rev-parse", "HEAD^{tree}"),
        },
        "split_consistency": split_consistency(rows, base),
        "limitations": [
            "One line, one clone (operator=clone, genome %s). The battery's own clone criterion "
            "is unanimity across lines; a single line cannot register instability, so an ask that "
            "would flip between identical brains is reported here as stable by construction."
            % first.get("genome_id"),
            "Measured as %d chunks of one script-pair each (--only), because the shell caps a "
            "single command at 600 s and the full 42-ask run needs ~18 min. Chunking is a "
            "sanctioned mode (run_generation.py:880-887) and every script builds a FRESH house "
            "per ask, so a chunk boundary cannot leak state between asks -- but it does mean the "
            "measurement spans %d processes, and the per-chunk provenance is recorded above so "
            "that is visible rather than implied." % (len(row_journals), len(row_journals)),
            "The guarded set is the baseline's regression_pass_set, which is by construction the "
            "set that PASSED when the split was frozen. guarded_pass == guarded_total therefore "
            "confirms the four still pass; it cannot discover a fifth invariant that was never "
            "guarded.",
        ],
    }

    print(f"battery: frozen {measured['frozen_correct']}/{measured['frozen_total']}  "
          f"guarded {measured['guarded_pass']}/{measured['guarded_total']}  "
          f"paraphrase {measured['paraphrase_pass']}/{measured['paraphrase_total']}  "
          f"electric={elec['state']}")
    for k, v in verdict.items():
        print(f"  {'PASS' if v['pass'] else 'FAIL'}  {k}: {v['measured']!r} vs {v.get('expected')!r}")
    print(f"H4 battery clause: {'PASS' if all_pass else 'FAIL'}")

    if a.out:
        op = Path(a.out)
        if not op.is_absolute():
            op = ROOT / op
        op.parent.mkdir(parents=True, exist_ok=True)
        op.write_text(json.dumps(art, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        print(f"wrote {op.relative_to(ROOT)}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
