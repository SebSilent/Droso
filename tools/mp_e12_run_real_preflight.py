"""B.6 item 4, second pass: attempt the FULL three-class item against the real donor and record the budget events.

The point of this pass is that it costs nothing. The pre-flight check is arithmetic on tensor shapes, so 24 items
abort before a single value is read, and the journal this run owns stays at zero records -- which is the proof
that "an over-budget item writes nothing" is true in the strong sense, not just in the sense of the artifact.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.mp_e12_probes import CLASSES, build_real_graph, load_probe_ids  # noqa: E402

OUT = ROOT / "experiments/MP-E12/results/association_graph_real_three_class_preflight.json"
JOURNAL = "experiments/MP-E12/results/access_journal_extraction_e12a_three_class_preflight.jsonl"
if OUT.exists() or (ROOT / JOURNAL).exists():
    raise SystemExit("REFUSED: this pre-flight pass has already been recorded.")

probes = load_probe_ids()
words = {t: w for t, w in probes}
graph, problems, mask_hits, sha = build_real_graph(n_items=len(probes), classes=list(CLASSES),
                                                   journal_rel=JOURNAL)
OUT.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"wrote {OUT.name}")
print(f"  items probed={graph['items_probed']}  items aborted={len(graph['items_aborted'])}")
print(f"  journal records for this pass={graph['access_journal']['n_records']}  "
      f"(zero reads is the claim being demonstrated)")
print(f"  accounting tallies: registered={graph['accounting_tallies']['registered_rule']['operations']} "
      f"conservative={graph['accounting_tallies']['conservative_reading']['operations']}")
a0 = graph["items_aborted"][0]
print(f"  first event: item {a0['item']} planned {a0['planned_ops']} vs budget {a0['budget']}")
for c, p in sorted(a0["planned"].items()):
    print(f"      {c:24s} registered={p['registered_ops']:3d} reads={p['read_calls']:4d} "
          f"conservative={p['conservative_ops']:4d} rows={p['rows_touched']:8d}")
print(f"  all 24 events identical in shape: "
      f"{len({json.dumps(a['planned'], sort_keys=True) for a in graph['items_aborted']}) == 1}")
print(f"  verify problems={problems}  mask records={mask_hits}")

print("\n--- named probe words, top-k as the committed graph records them ---")
G = json.loads((ROOT / "experiments/MP-E12/results/association_graph_real_class1.json").read_text(
    encoding="utf-8"))
for w in ("dog", "cat", "horse", "paris", "london", "water", "music", "car"):
    if w not in G["named_probe_words"]:
        print(f"  {w:7s} -- not in the registered probe list")
        continue
    e = G["named_probe_words"][w]
    a = e["source_address"]
    print(f"  {w:7s} token {e['token_id']:>6d}  {a['tensor']}[{a['row']}] @ byte {a['byte_offset']}  "
          f"pool={e['pool_size']}")
    for nb in e["top_k_neighbours"][:5]:
        print(f"          {nb['cosine']:+.6f}  {nb['token_id']:>6d}  {nb['word']:36s} "
              f"{nb['source_address']['tensor']}[{nb['source_address']['row']}] @ "
              f"{nb['source_address']['byte_offset']}  probe_word={nb['in_probe_list']}")
