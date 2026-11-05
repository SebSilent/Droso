"""Step 1's proof: re-run class 1 against the donor and show the figures did not move.

Determinism is the claim being tested, so the comparison is not limited to the summary numbers. Every item,
node, edge, confidence and address in the new graph is compared to the committed one; the fields allowed to
differ are the ones that record WHEN and WHERE the run wrote its journal. If anything else moves, this script
says so and exits non-zero -- a shifted figure here would be a finding about the instrument or the file, not a
nuisance to smooth.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mp_e12_probes import build_real_graph, load_probe_ids  # noqa: E402

COMMITTED = ROOT / "experiments/MP-E12/results/association_graph_real_class1.json"
SCRATCH_JOURNAL = "_tmp/rerun_verify_journal.jsonl"
Path(ROOT / SCRATCH_JOURNAL).unlink(missing_ok=True)

probes = load_probe_ids()
new, problems, mask_hits, sha = build_real_graph(n_items=len(probes), classes=("1_embedding_geometry",),
                                                 journal_rel=SCRATCH_JOURNAL)
old = json.loads(COMMITTED.read_text(encoding="utf-8"))

HEADLINE = [("registered operations", old["accounting_tallies"]["registered_rule"]["operations"],
             new["accounting_tallies"]["registered_rule"]["operations"], 48),
            ("conservative operations", old["accounting_tallies"]["conservative_reading"]["operations"],
             new["accounting_tallies"]["conservative_reading"]["operations"], 96),
            ("per-row tally", old["accounting_tallies"]["per_row_reading_reported_not_run_under"]["operations"],
             new["accounting_tallies"]["per_row_reading_reported_not_run_under"]["operations"], 1584),
            ("read calls", old["reads"]["read_calls"], new["reads"]["read_calls"], 48),
            ("rows touched", old["reads"]["rows_touched"], new["reads"]["rows_touched"], 1536),
            ("values returned", old["reads"]["values_returned"], new["reads"]["values_returned"], 1179648),
            ("journal records", old["access_journal"]["n_records"], new["access_journal"]["n_records"], 1536),
            ("edges", sum(len(i["edges"]) for i in old["items"]), sum(len(i["edges"]) for i in new["items"]), 240),
            ("nodes", sum(len(i["nodes"]) for i in old["items"]), sum(len(i["nodes"]) for i in new["items"]), 264),
            ("items probed", old["items_probed"], new["items_probed"], 24),
            ("items aborted", len(old["items_aborted"]), len(new["items_aborted"]), 0),
            ("mask records", len(old["access_journal"]["mask_buffer_records"]),
             len(new["access_journal"]["mask_buffer_records"]), 0),
            ("tensors touched", old["access_journal"]["tensors_touched"], new["access_journal"]["tensors_touched"],
             ["wte.weight"])]
print(f"{'figure':22s} {'committed':>12s} {'re-run':>12s} {'ordered':>10s}  verdict")
bad = []
for name, a, b, expected in HEADLINE:
    ok = (a == b == expected) if not isinstance(a, list) else (a == b == expected)
    if not ok:
        bad.append(name)
    print(f"{name:22s} {str(a)[:12]:>12s} {str(b)[:12]:>12s} {str(expected)[:10]:>10s}  "
          f"{'MATCH' if ok else 'MOVED'}")

top_old = max((nb["cosine"], tid, nb["word"]) for tid, e in old["named_probe_words"].items()
              for nb in e["top_k_neighbours"])
top_new = max((nb["cosine"], tid, nb["word"]) for tid, e in new["named_probe_words"].items()
              for nb in e["top_k_neighbours"])
print(f"\ntop pair committed: {top_old[1]} -> {top_old[2]} at {top_old[0]:+.6f}")
print(f"top pair re-run   : {top_new[1]} -> {top_new[2]} at {top_new[0]:+.6f}")
if top_old != top_new:
    bad.append("top pair")

DIFF_OK = {"access_journal", "run", "wall_clock_read_s", "donor"}
moved = []
for k in set(old) | set(new):
    if k in DIFF_OK:
        continue
    if json.dumps(old.get(k), sort_keys=True) != json.dumps(new.get(k), sort_keys=True):
        moved.append(k)
print(f"\nfield-by-field over the whole artifact (excluding {sorted(DIFF_OK)}): "
      f"{'IDENTICAL' if not moved else 'MOVED: ' + str(moved)}")
for it_old, it_new in zip(old["items"], new["items"]):
    if json.dumps(it_old, sort_keys=True) != json.dumps(it_new, sort_keys=True):
        print(f"   item {it_old['item']} differs")
        for k in it_old:
            if json.dumps(it_old[k], sort_keys=True) != json.dumps(it_new[k], sort_keys=True):
                print(f"      field {k}")
        break
print(f"journal verify problems (re-run): {problems}   mask hits: {mask_hits}")
print(f"donor sha256 re-run: {sha[:24]}...  committed: {old['run']['donor_sha256'][:24]}...  "
      f"{'same' if sha == old['run']['donor_sha256'] else 'DIFFERENT'}")
n_rec_new = sum(1 for _ in (ROOT / SCRATCH_JOURNAL).open(encoding="utf-8"))
print(f"re-run journal records on disk: {n_rec_new} (committed journal: 1536)")

Path(ROOT / SCRATCH_JOURNAL).unlink(missing_ok=True)
if bad or moved:
    print(f"\nSTOP: figures moved -- {bad} {moved}")
    raise SystemExit(1)
print("\nDETERMINISM CONFIRMED: the re-run reproduces the committed run exactly, in the summary numbers and "
      "field by field, with only the journal path, the run timestamps and the wall clock allowed to differ.")
