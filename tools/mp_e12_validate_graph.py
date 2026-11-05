"""Validate an association-graph artifact against its versioned schema.

There is no jsonschema package in this environment, so the checks are written out. That is not a downgrade: the
invariants that matter are arithmetic over the two operation tallies and the mask-buffer exclusion, and a
generic validator would not have known to check them.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA_PATH = "experiments/MP-E12/association_graph.schema.json"
MASK = re.compile(r"^h\.\d+\.attn\.bias$")
NODE_TYPES = {"probe_token", "pool_candidate", "feature_detector", "successor_token"}
EDGE_TYPES = {"co_clustered", "association", "directed_map", "detector_value"}


def validate(graph: dict, schema: dict) -> list[str]:
    p = []
    for k in schema["required"]:
        if k not in graph:
            p.append(f"missing required top-level field {k!r}")
    if graph.get("schema_version") != schema["schema_version"]:
        p.append(f"schema_version is {graph.get('schema_version')!r}, schema declares "
                 f"{schema['schema_version']!r}")
    kind = graph.get("source_kind")
    if kind not in ("synthetic", "real"):
        p.append(f"source_kind {kind!r} is not synthetic or real")
    else:
        for k in schema["conditional"][f"source_kind={kind}"]:
            if k not in graph:
                p.append(f"source_kind={kind} requires {k!r} and it is absent")
    if graph.get("read_budget", {}).get("value") != 24:
        p.append("the registered per-item budget is 24 and the artifact does not say 24")
    if graph.get("accounting_used") not in ("registered", "conservative"):
        p.append("accounting_used must be registered or conservative")
    if "energy_estimate" in graph and graph["energy_estimate"] != schema["properties"]["energy_estimate"]["const"]:
        p.append("energy_estimate must remain the D-MPE12-02 non-measurement string")
    tal = graph.get("accounting_tallies", {})
    for k in ("registered_rule", "conservative_reading", "per_row_reading_reported_not_run_under", "difference"):
        if k not in tal:
            p.append(f"accounting_tallies.{k} is absent -- all three tallies are required every run")
    if tal:
        reg = tal["registered_rule"]["operations"]
        cons = tal["conservative_reading"]["operations"]
        calls = graph["reads"]["read_calls"]
        rows = graph["reads"]["rows_touched"]
        if cons != reg + calls:
            p.append(f"conservative ({cons}) != registered ({reg}) + read calls ({calls})")
        if tal["per_row_reading_reported_not_run_under"]["operations"] != reg + rows:
            p.append("the per-row tally is not registered + rows touched")
        if tal["difference"]["ops"] != cons - reg:
            p.append("the stated difference does not match the two tallies")
    if len(graph.get("items", [])) != graph.get("items_probed"):
        p.append("items_probed does not match the length of items")
    for i, it in enumerate(graph.get("items", [])):
        for k in ("item", "nodes", "edges", "detail", "operations_spent", "macs_spent", "per_extraction",
                  "budget", "aborted", "conservative_operations_spent", "read_calls", "rows_touched",
                  "planned", "extraction_classes", "accounting"):
            if k not in it:
                p.append(f"item {i} missing {k!r}")
        if it.get("conservative_operations_spent") != it.get("operations_spent", 0) + it.get("read_calls", 0):
            p.append(f"item {i}: conservative != registered + calls")
        if it.get("per_row_operations_if_charged") != it.get("operations_spent", 0) + it.get("rows_touched", 0):
            p.append(f"item {i}: per-row tally != registered + rows")
        if not it.get("aborted") and it.get("operations_spent", 0) > it.get("budget", 24):
            p.append(f"item {i} is over budget and not marked aborted")
        for r in it.get("reads", []):
            if MASK.match(r.get("tensor", "")):
                p.append(f"item {i} read a causal-mask buffer: {r['tensor']}")
            if kind == "real" and not r.get("probe_id", "").startswith("extraction_"):
                p.append(f"item {i} read without an extraction probe_id: {r!r}")
        seen_ids = set()
        for nd in it.get("nodes", []):
            for k in ("node_id", "type", "source", "confidence"):
                if k not in nd:
                    p.append(f"item {i} node {nd.get('node_id')} missing {k!r}")
            if nd.get("type") not in NODE_TYPES:
                p.append(f"item {i} node type {nd.get('type')!r} not in the schema's enum")
            if nd["node_id"] in seen_ids:
                p.append(f"item {i} duplicates node_id {nd['node_id']!r}")
            seen_ids.add(nd["node_id"])
            if kind == "real" and nd.get("type") in ("probe_token", "successor_token") and "address" not in nd:
                p.append(f"item {i} real-path node {nd['node_id']} carries no address")
            if "address" in nd:
                for k in ("tensor", "row", "byte_offset", "dtype", "shape"):
                    if k not in nd["address"]:
                        p.append(f"item {i} node {nd['node_id']} address missing {k!r}")
        for e in it.get("edges", []):
            for k in ("src", "dst", "type", "confidence", "extraction", "provenance"):
                if k not in e:
                    p.append(f"item {i} edge {e.get('src')}->{e.get('dst')} missing {k!r}")
            if e.get("type") not in EDGE_TYPES:
                p.append(f"item {i} edge type {e.get('type')!r} not in the schema's enum")
            for k in ("source_model", "method"):
                if k not in e.get("provenance", {}):
                    p.append(f"item {i} edge provenance missing {k!r}")
            if e.get("src") not in seen_ids and e.get("dst") not in seen_ids:
                p.append(f"item {i} edge {e.get('src')}->{e.get('dst')} references no node in the item")
    for a in graph.get("items_aborted", []):
        for k in ("item", "planned_ops", "budget", "planned", "accounting", "source_kind"):
            if k not in a:
                p.append(f"aborted item {a.get('item')} missing {k!r}")
    aj = graph.get("access_journal")
    if aj:
        for k in ("path", "n_records", "verify_problems", "mask_buffer_records", "probe_ids"):
            if k not in aj:
                p.append(f"access_journal missing {k!r}")
        if aj.get("verify_problems"):
            p.append(f"the access journal does not verify: {aj['verify_problems']}")
        if aj.get("mask_buffer_records"):
            p.append(f"mask buffers appear in the access journal: {aj['mask_buffer_records']}")
    return p


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: python tools/mp_e12_validate_graph.py <graph.json> [<graph2.json> ...]")
        return 2
    schema = json.loads((ROOT / SCHEMA_PATH).read_text(encoding="utf-8"))
    rc = 0
    for rel in argv:
        graph = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        problems = validate(graph, schema)
        print(f"{rel}: {'VALID against ' + schema['schema_version'] if not problems else str(len(problems)) + ' PROBLEM(S)'}"
              f"  [source_kind={graph.get('source_kind')}]")
        for pr in problems:
            print(f"   - {pr}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
