"""B.6 item 4, the run: the class-1 extraction against the real donor, 24 probes, conservative accounting.

Writes the committed artifact and the committed journal. Refuses to overwrite either: one run owns one journal.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mp_e12_probes import build_real_graph, load_probe_ids  # noqa: E402
from tools.mp_e12_validate_graph import SCHEMA_PATH, validate  # noqa: E402

OUT = ROOT / "experiments/MP-E12/results/association_graph_real_class1.json"
JOURNAL = "experiments/MP-E12/results/access_journal_extraction_e12a_class1.jsonl"
if (ROOT / JOURNAL).exists() or OUT.exists():
    raise SystemExit("REFUSED: the committed journal or artifact already exists. This run has already happened.")

# the schema is parsed BEFORE any read is issued. The first attempt of this run validated after the run, so a
# syntax error in the schema file cost 1,032 journaled donor reads and produced no artifact. The reads were
# recoverable; the lesson is that an instrument checked after the fact is an instrument that can bill you.
schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
print(f"schema parses: {schema['schema_version']}")

probes = load_probe_ids()
words = {t: w for t, w in probes}
print(f"probing {len(probes)} registered words against the real donor, classes=['1_embedding_geometry']")
graph, problems, mask_hits, sha = build_real_graph(n_items=len(probes), classes=("1_embedding_geometry",),
                                                   journal_rel=JOURNAL)
vp = validate(graph, schema)
print(f"schema validation against {schema['schema_version']}: {'VALID' if not vp else vp}")
if vp:
    raise SystemExit("REFUSED: the artifact does not satisfy its own schema")

# the named-word view is emitted by the instrument now (tools/mp_e12_probes.py), not by this driver: an
# untested wrapper producing the most-quoted section of the artifact was drift waiting to happen. This script
# adds only the run's own timestamps and the ordering proof.
assert "named_probe_words" in graph, "the instrument must emit the named-word view itself"
graph["run"] = {"journal_records": graph["access_journal"]["n_records"],
                "donor_sha256": sha,
                "preregistration": "experiments/MP-E12/results/real_run_preregistration.json",
                "preregistered_at_utc": json.loads((ROOT / "experiments/MP-E12/results/"
                                                    "real_run_preregistration.json").read_text(
                                                        encoding="utf-8"))["registered_at_utc"],
                "first_extraction_record_utc": (ROOT / JOURNAL).read_text(encoding="utf-8").splitlines()[0]
                                               .split('"timestamp_utc": "')[1].split('"')[0]}
OUT.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
t = graph["accounting_tallies"]
print(f"\nwrote {OUT.name}")
print(f"  items={graph['items_probed']} aborted={len(graph['items_aborted'])} "
      f"classes={graph['extraction_classes_run']}")
print(f"  registered ops={t['registered_rule']['operations']}  conservative ops="
      f"{t['conservative_reading']['operations']}  per-row-if-charged="
      f"{t['per_row_reading_reported_not_run_under']['operations']}")
print(f"  read calls={graph['reads']['read_calls']}  rows={graph['reads']['rows_touched']}  values="
      f"{graph['reads']['values_returned']}  journal records={graph['access_journal']['n_records']}")
print(f"  tensors touched={graph['access_journal']['tensors_touched']}  mask-buffer records={mask_hits}  "
      f"verify problems={problems}")
print(f"  preregistered {graph['run']['preregistered_at_utc']} BEFORE first record "
      f"{graph['run']['first_extraction_record_utc']}: "
      f"{graph['run']['preregistered_at_utc'] < graph['run']['first_extraction_record_utc']}")
for ab in graph["items_aborted"]:
    print(f"  BUDGET EVENT item {ab['item']}: planned {ab['planned_ops']} vs {ab['budget']}")
print("\nthree named words, as the graph records them:")
for w in ("dog", "cat", "king"):
    if w in graph["named_probe_words"]:
        e = graph["named_probe_words"][w]
        a = e["source_address"]
        print(f"  {w:5s} token {e['token_id']:>6d}  wte.weight[{a['row']}] @ byte {a['byte_offset']}")
        for nb in e["top_k_neighbours"][:4]:
            print(f"        {nb['cosine']:+.6f}  token {nb['token_id']:>6d}  {nb['word']:34s} "
                  f"wte.weight[{nb['source_address']['row']}] @ {nb['source_address']['byte_offset']}")
