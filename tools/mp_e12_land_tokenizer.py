"""Land and prove the donor's tokenizer files at the SAME pinned revision as the weights.

STDONLY, AND THAT IS THE POINT. This tool reads bytes and hashes them. It does not import `tokenizers`,
`transformers` or `torch`: the address space's rule is that a tokenizer file is DATA, the same class of object as
the weight file, and a tool that reached for a runtime to check a byte string would put donor runtime on the
path that C4 audits. Every hash here is recomputed from the file on disk with hashlib.

The four tokenizer files were already on disk, recorded by the weights landing. They are NOT re-fetched: the
bytes are already provenance-recorded, and pulling 2.8 MB again to "verify" it would replace one trust with
another. What this tool does is re-hash them from disk, compare against the recorded sha256, and write a
tokenizer provenance entry in the same shape as the weights one -- URL, revision, hash, bytes, licence -- so a
later session can answer "which bytes, from where, checked when" without re-deriving the landing.
"""
from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DONOR = ROOT / "experiments/MP-E12/donor/gpt2"
OUT = DONOR / "PROVENANCE_tokenizer.json"
WEIGHTS_PROV = DONOR / "PROVENANCE_gpt2.json"
REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
REPO = "openai-community/gpt2"
BASE = f"https://huggingface.co/{REPO}/resolve/{REVISION}/"
TOKENIZER_FILES = ["vocab.json", "merges.txt", "tokenizer.json", "tokenizer_config.json"]
# the file the order named first. Whether it exists at this revision is measured below, not assumed: the
# weights landing recorded a 404 for special_tokens_map.json for exactly this reason.
EXTRA = ["vocab.bpe"]
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_of(path: Path) -> str:
    """Streamed, so a 548 MB file would not be pulled into RAM to be counted."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(name: str) -> tuple[int, bytes | None, str]:
    url = BASE + name
    try:
        with urllib.request.urlopen(url, timeout=60) as r:               # noqa: S310 -- fixed https URL
            return int(r.status or 200), r.read(), url
    except urllib.error.HTTPError as e:
        return int(e.code), None, url
    except Exception as e:                                                # noqa: BLE001 -- recorded, not hidden
        return -1, None, f"{url} ({type(e).__name__}: {e})"


weights = json.loads(WEIGHTS_PROV.read_text(encoding="utf-8"))
recorded = {f["file"]: f for f in weights["files"]}
entries, absent = [], []

for name in TOKENIZER_FILES:
    path = DONOR / name
    if not path.exists():
        status, body, url = fetch(name)
        if body is None:
            absent.append({"file": name, "measured": f"HTTP {status} from {url}",
                           "consequence": "the tokenizer cannot be re-derived from this revision"})
            continue
        path.write_bytes(body)
        source = "fetched now"
    else:
        source = ("already on disk from the weights landing at the same pinned revision; NOT re-fetched -- "
                  "re-hashed from disk instead")
        url = BASE + name
    digest = sha256_of(path)
    prior = recorded.get(name, {}).get("sha256")
    entries.append({"file": name, "url": url, "bytes": path.stat().st_size, "sha256": digest,
                    "verified_at_utc": NOW, "how_verified": "hashlib.sha256 over the bytes read from disk",
                    "provenance_of_this_byte_string": source,
                    "matches_the_weights_provenance_record": (prior == digest) if prior else None,
                    "prior_sha256_from_weights_provenance": prior})
    print(f"  {name:22s} {path.stat().st_size:>10,d} B  sha256={digest[:16]}...  "
          f"prior record agrees: {entries[-1]['matches_the_weights_provenance_record']}")
    if prior and prior != digest:
        raise SystemExit(f"REFUSED: {name} on disk does not match the sha256 the weights landing recorded")

for name in EXTRA:
    status, body, url = fetch(name)
    if body is None:
        absent.append({"file": name, "measured": f"HTTP {status} from {url}",
                       "consequence": "none for the BPE rule: the merges are in merges.txt and the token-id "
                                      "table is in vocab.json. vocab.bpe is an alternate serialisation of the "
                                      "same merge list, and this program does not need a second copy of a fact "
                                      "when it can hold one. Recorded so a later session does not re-derive the "
                                      "404.",
                       "why_it_was_asked_for": "named in the order among the tokenizer files, 'as available'"})
        print(f"  {name:22s} ABSENT at this revision: HTTP {status}")
    else:
        (DONOR / name).write_bytes(body)
        entries.append({"file": name, "url": url, "bytes": (DONOR / name).stat().st_size,
                        "sha256": sha256_of(DONOR / name), "verified_at_utc": NOW,
                        "how_verified": "hashlib.sha256 over the bytes just written",
                        "provenance_of_this_byte_string": "fetched now"})
        print(f"  {name:22s} landed: {(DONOR / name).stat().st_size:,} B")

doc = {
    "experiment": "MP-E12a",
    "step": "B.6 item 4 follow-on: the donor's tokenizer landed and provenanced at the weights' own revision, "
            "so the 17 deferred curriculum words become a rule with a table rather than a blocker with a name.",
    "stage": "tokenizer present, hashes recomputed from disk, no extraction performed",
    "landed_at_utc": NOW,
    "run_mode": "offline against the pinned revision; no donor runtime imported, no weight byte read",
    "source": {"repo": REPO, "revision_pinned": REVISION, "resolve_base": BASE,
               "same_revision_as_the_weights": weights["source"]["revision_pinned"] == REVISION,
               "licence_text_reference": weights["source"]["licence_text_reference"],
               "api_license_field": weights["source"].get("api_license_field")},
    "files": entries,
    "absent_at_this_revision": absent,
    "total_bytes_on_disk": sum(e["bytes"] for e in entries),
    "verification": {
        "method": "each file re-read from disk and hashed with hashlib.sha256 in this run; where the weights "
                  "landing had already recorded a sha256, the two are compared and a mismatch aborts the tool",
        "all_prior_records_agree": all(e["matches_the_weights_provenance_record"] is not False for e in entries),
        "what_was_not_imported": ["tokenizers", "transformers", "torch", "numpy"],
        "why": "a tokenizer file is data. Checking its bytes with a runtime would put donor runtime on the path "
               "C4 audits, which is the thing R11 and the instrument tests exist to keep off it."},
    "what_this_does_not_do": {
        "no_extraction": "no weight value was read by this tool, and none will be by the rule it enables",
        "no_probe_list_rewritten": "v1 and its deferral list are untouched; the 24 registered probes remain "
                                   "the probes of record for every sealed figure",
        "no_tokenizer_runtime": "the BPE applied in the v2 rule is arithmetic over merges.txt and vocab.json, "
                                "written for this program, not a call into a library that also knows how to "
                                "run a model",
        "no_appended_to_sealed_artifacts": "the sealed class-1 graph is not re-emitted with sub-token rows"},
    "disk_note": "the tokenizer bytes sit beside the weights and are deliberately NOT committed, on the same "
                 "rule as the weights: .gitignore excludes the donor directory, the sealed set carries the "
                 "provenance and the hashes, and R10's alternative to committing is re-derivability -- which a "
                 "pinned revision URL and a sha256 provide. Sealing the bytes would add ~2.9 MB of data to "
                 "every future anchor for no gain in proof.",
}
OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
print(f"\nwrote {OUT.relative_to(ROOT)}")
print(f"  files provenanced: {len(entries)}  absent: {len(absent)}  "
      f"total {doc['total_bytes_on_disk']:,} B")
print(f"  same revision as the weights: {doc['source']['same_revision_as_the_weights']}")
print(f"  all prior hash records agree: {doc['verification']['all_prior_records_agree']}")
