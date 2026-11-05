"""B.6 step 1, part 2 -- land the donor, record provenance as measured, verify shapes by reading the index.

What it does:
  * downloads the public `gpt2` weights from the REVISION THE API PINNED (607a30d7...), not from a moving
    branch tag, so the recorded URLs are the bytes that were hashed;
  * refuses to overwrite anything already at the destination;
  * sha256 per file, bytes on disk, free disk before and after, wall time per file -- all measured, none
    transcribed from a model card;
  * verifies the tensor inventory by PARSING THE SAFETENSORS HEADER (8-byte little-endian length + JSON).
    No torch, no transformers, no forward pass: R11 binds, and the header read is the same read-only
    address-space operation the library will use later;
  * deliberately does NOT download the tf_model.h5 / flax / onnx / tflite / rust variants -- one canonical
    byte string per tensor, because a library with four copies of the same weights invites a claim made
    against whichever copy somebody happened to open.

Run:  .venv/Scripts/python.exe tools/mp_e12_land_donor.py
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "experiments/MP-E12/donor/gpt2"
REVISION = "607a30d783dfa663caf39e06633721c8d4cfcd7e"
BASE = f"https://huggingface.co/openai-community/gpt2/resolve/{REVISION}/"
# special_tokens_map.json was in this list first. It is NOT at the root of the pinned revision -- the
# attempt measured an HTTP 404 for it -- and the repo carries that file only under onnx/. Recorded rather
# than silently dropped; see `absent_at_this_revision` below.
FILES = ["model.safetensors", "config.json", "generation_config.json", "vocab.json", "merges.txt",
         "tokenizer.json", "tokenizer_config.json", "README.md"]
ABSENT_AT_THIS_REVISION = [{"file": "special_tokens_map.json",
                            "measured": "HTTP Error 404: Not Found from "
                                        "https://huggingface.co/openai-community/gpt2/resolve/"
                                        "607a30d783dfa663caf39e06633721c8d4cfcd7e/special_tokens_map.json",
                            "why_it_was_asked_for": "it is in the API's file list, but under onnx/, not at the "
                                                    "root; the listing was read as a flat set",
                            "consequence": "none for the address space: the special-token map is a tokenizer "
                                           "convenience, not a tensor, and no extraction is registered against "
                                           "it. Recorded so a later session does not re-derive the 404."}]
RESUME = "--resume" in sys.argv
OUT = DEST / "PROVENANCE_gpt2.json"

# the spec pinned at MP-E12/registration.json:2261 and plan :359 -- read from the ledger, not from memory
# Tensor names are the file's own index keys, measured by reading the header. The FIRST attempt wrote
# `transformer.wte.weight` and friends -- the module path inside PyTorch -- and every check came back
# found=None, which is a naming error in the checker, not a shape disagreement with the spec. The distinction
# is recorded in attempt_history below, because "the donor did not match the spec" and "the checker did not
# match the donor's namespace" lead to opposite decisions.
EXPECTED = {
    "wte.weight": {"shape": [50257, 768], "why": "vocab 50257 x n_embd 768"},
    "wpe.weight": {"shape": [1024, 768], "why": "n_positions 1024 x n_embd 768"},
    "ln_f.weight": {"shape": [768], "why": "final layernorm, n_embd 768"},
    "h.0.attn.c_attn.weight": {"shape": [768, 2304],
                               "why": "Conv1D convention (in, out): 768 in, qkv = 3 x n_head 12 x d_head 64"},
    "h.0.attn.c_proj.weight": {"shape": [768, 768], "why": "attention output projection"},
    "h.0.mlp.c_fc.weight": {"shape": [768, 3072], "why": "MLP inner 3072"},
    "h.0.mlp.c_proj.weight": {"shape": [3072, 768], "why": "MLP down-projection"},
    "h.11.attn.c_attn.weight": {"shape": [768, 2304], "why": "last layer, to show the stack is 12 deep"},
}
# tensors the spec implies must NOT be present as separate storage, and the finding if they are absent
TIED_UNEMBEDDING_KEYS = ("wt.weight", "lm_head.weight", "transformer.wt.weight")
LAYER_COUNT_EXPECT = 12
ATTN_BIAS_EXPECT = {"shape": [1, 1, 1024, 1024], "dtype": "F32"}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prod(shape):
    q = 1
    for x in shape:
        q *= int(x)
    return q


def sha256_of(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(name: str) -> dict:
    url = BASE + name
    dest = DEST / name
    if dest.exists():
        if not RESUME:
            raise SystemExit(f"REFUSED: {dest} already exists -- the donor lands once, and a re-land would "
                             f"silently change the bytes a later extraction is pinned to. --resume is the "
                             f"explicit opt-in: it keeps these bytes, re-hashes them, and fetches only what "
                             f"is missing.")
        return {"file": name, "url": BASE + name, "http_status": "kept-from-previous-attempt",
                "bytes": dest.stat().st_size, "sha256": sha256_of(dest), "seconds": 0.0,
                "resumed": True,
                "note": "bytes landed in the first attempt at the same pinned revision "
                        f"{REVISION[:12]}; re-hashed here rather than trusted",
                "downloaded_at_utc": now_utc()}
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "droso-mp-e12-donor-landing"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as r:
        http_status = r.status
        final_url = r.geturl()
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        with tmp.open("wb") as f:
            for chunk in iter(lambda: r.read(1 << 22), b""):
                f.write(chunk)
    tmp.rename(dest)
    return {"file": name, "url": url, "http_status": http_status, "final_url": final_url,
            "bytes": dest.stat().st_size, "sha256": sha256_of(dest),
            "seconds": round(time.time() - t0, 2),
            "server_etag": hdrs.get("etag"), "content_type": hdrs.get("content-type"),
            "x_repo_revision": hdrs.get("x-repo-revision") or hdrs.get("x-repo-commit"),
            "downloaded_at_utc": now_utc()}


def read_safetensors_header(p: Path):
    """Parse the index the way the address space will: length prefix, then JSON. No model runs."""
    with p.open("rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        raw = f.read(n)
    hdr = json.loads(raw.decode("utf-8"))
    meta = hdr.pop("__metadata__", None)
    return hdr, meta, n


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        raise SystemExit(f"REFUSED: {OUT} already exists")
    free_before = shutil.disk_usage(ROOT).free
    print(f"[land] {now_utc()} destination {DEST}  free before = {free_before/2**30:.2f} GB", flush=True)
    recs = []
    for name in FILES:
        print(f"[land] GET {name} ...", flush=True)
        r = download(name)
        recs.append(r)
        print(f"[land]   {r['bytes']:,} B  sha256 {r['sha256'][:16]}...  {r['seconds']} s  HTTP {r['http_status']}",
              flush=True)

    st = next(r for r in recs if r["file"] == "model.safetensors")
    hdr, meta, hdr_len = read_safetensors_header(DEST / "model.safetensors")
    shapes = {k: {"shape": v.get("shape"), "dtype": v.get("dtype"),
                  "data_offsets": v.get("data_offsets")} for k, v in sorted(hdr.items())}

    checks, failures = [], []
    for name, spec in EXPECTED.items():
        got = shapes.get(name)
        ok = got is not None and got["shape"] == spec["shape"]
        checks.append({"tensor": name, "expected_shape": spec["shape"],
                       "found_shape": got["shape"] if got else None,
                       "dtype": got["dtype"] if got else None,
                       "match": ok, "why_expected": spec["why"]})
        if not ok:
            failures.append(name)
    layers = sorted({k.split(".")[1] for k in shapes
                     if k.startswith("h.") and k.split(".")[1].isdigit()}, key=int)
    layers_ok = len(layers) == LAYER_COUNT_EXPECT
    if not layers_ok:
        failures.append(f"layer count {len(layers)} != {LAYER_COUNT_EXPECT}")
    n_params = sum(_prod(v["shape"]) for v in shapes.values())

    # the tie, read as an absence: the spec pins "wte tied to the unembedding", so a separate unembedding
    # tensor must NOT exist. Asserting absence is a real check -- if a later conversion ships lm_head.weight
    # the address space would be reading two copies of the same thing and calling them one.
    tie_keys = [k for k in shapes if k in TIED_UNEMBEDDING_KEYS]
    # EXACT key match, not endswith. The first version used endswith("attn.bias"), which also matched the
    # 12 `h.N.attn.c_attn.bias` tensors -- real trainable weights -- and reported 24 mask buffers, then
    # "all_match: false" because those 12 are [2304] not [1,1,1024,1024]. A buffer/weight split that is wrong
    # by 12 tensors is exactly the kind of number an extraction budget would inherit.
    attn_bias = [k for k in shapes if re.fullmatch(r"h\.\d+\.attn\.bias", k)]
    masked_bias = [k for k in shapes if re.fullmatch(r"h\.\d+\.attn\.masked_bias", k)]
    bias_ok = all(shapes[k]["shape"] == ATTN_BIAS_EXPECT["shape"]
                  and shapes[k]["dtype"] == ATTN_BIAS_EXPECT["dtype"] for k in attn_bias)
    st_path = DEST / "model.safetensors"
    data_end = max(v["data_offsets"][1] for v in shapes.values())
    accounting = {"file_bytes": st_path.stat().st_size, "length_prefix_bytes": 8,
                  "header_json_bytes": hdr_len, "tensor_data_bytes": data_end,
                  "sum_matches_file": st_path.stat().st_size == 8 + hdr_len + data_end}
    mask_floats = sum(_prod(shapes[k]["shape"]) for k in attn_bias)
    weights_only = n_params - mask_floats

    free_after = shutil.disk_usage(ROOT).free
    out = {
        "experiment": "MP-E12",
        "stage": "MP-E12a -- the address space and the calibration donor",
        "step": "v1.2 B.6 item 1 (plan :447): confirm the GPT-2 124M weights are on the machine; if not, "
                "download and record the hash",
        "landed_at_utc": now_utc(),
        "source": {"repo": "openai-community/gpt2", "revision_pinned": REVISION,
                   "api_observed_lastModified": "2024-02-19T10:57:45.000Z",
                   "api_license_field": "mit",
                   "licence_text_reference": "experiments/MP-E12/donor/gpt2/README.md (the repo card, fetched "
                                             "at the pinned revision; its License section is the text of "
                                             "record) and the API cardData.license = mit",
                   "egress_probe_at_utc": "2026-11-05T15:22:55Z",
                   "resolve_base": BASE},
        "files": recs,
        "absent_at_this_revision": ABSENT_AT_THIS_REVISION,
        "run_mode": "resume (kept the bytes already landed at the same pinned revision, re-hashed them, "
                    "fetched only what was missing)" if RESUME else "fresh",
        "total_bytes_on_disk": sum(r["bytes"] for r in recs),
        "disk": {"free_before_bytes": free_before, "free_after_bytes": free_after,
                 "free_before_GB": round(free_before / 2**30, 2),
                 "free_after_GB": round(free_after / 2**30, 2),
                 "consumed_GB": round((free_before - free_after) / 2**30, 2)},
        "tensor_inventory": {"n_tensors": len(shapes), "header_json_bytes": hdr_len,
                             "metadata": meta, "dtypes": sorted({v["dtype"] for v in shapes.values()}),
                             "parameter_count_from_shapes": n_params,
                             "read_by": "struct.unpack of the 8-byte length prefix then json.loads of the "
                                        "header -- no torch, no transformers, no forward pass (R11)"},
        "shape_verification_against_the_pinned_spec": {
            "spec_sources": ["experiments/MP-E12/registration.json:2261 (what_must_arrive)",
                             "experiments/MP-E9/plan_extract/DROSO_Master_Plan_v1_2.md:359 (pinned donor)",
                             "plan :220 (stage E12a)"],
            "checks": checks,
            "layers_found": layers, "n_layer_expected": LAYER_COUNT_EXPECT, "n_layer_match": layers_ok,
            "failures": failures,
            "verdict": ("MATCH -- every pinned shape read from the index agrees with the spec"
                        if not failures else f"MISMATCH: {failures}"),
        },
        "structural_findings_read_from_the_index": {
            "tensor_namespace": "the file indexes tensors in the bare GPT2 namespace -- `wte.weight`, "
                                "`h.0.attn.c_attn.weight` -- NOT the PyTorch module path `transformer.wte."
                                "weight`. The address space must expose what the index says; a later session "
                                "that resolves module paths will find nothing and may read that as an absent "
                                "weight rather than a wrong name.",
            "tied_unembedding": {"separate_unembedding_tensor_present": tie_keys,
                                 "expected": "absent, because the pinned spec says wte is tied to the "
                                             "unembedding (MP-E12/registration.json:2261, plan :359)",
                                 "finding": ("CONFIRMED BY ABSENCE -- no wt.weight / lm_head.weight in the "
                                             "index, so the unembedding address range is wte's, read "
                                             "transposed" if not tie_keys
                                             else f"PRESENT: {tie_keys} -- the tie claim would need revising")},
            "causal_mask_buffers": {"n_attn_bias_tensors": len(attn_bias),
                                    "keys": attn_bias[:2] + ["..."],
                                    "shape": ATTN_BIAS_EXPECT["shape"],
                                    "all_match": bias_ok,
                                    "n_masked_bias_tensors": len(masked_bias),
                                    "floats_they_account_for": mask_floats,
                                    "share_of_the_file_percent": round(100 * mask_floats / n_params, 2),
                                    "why_it_matters": "these are buffers, not weights: 12 tensors of "
                                                      "[1,1,1024,1024] holding the causal mask. An extraction "
                                                      "budget that counts them as parameters is wrong by "
                                                      f"{round(100*mask_floats/n_params,1)}%, and a feature "
                                                      "pool that mines them as weight matrices would be reading "
                                                      "a constant triangle."},
            "parameter_reconciliation": {
                "floats_in_index": n_params,
                "mask_buffer_floats": mask_floats,
                "weights_and_biases_only": weights_only,
                "donor_name_says": "124M",
                "weights_only_over_124M_percent": round(100 * weights_only / 124_000_000, 3),
                "note": "the 124M in the donor's name refers to the weight count, which is what "
                        "weights_and_biases_only measures; the index total is larger because of the mask "
                        "buffers. No external parameter constant is quoted here, because the only numbers in "
                        "this block that can be checked are the ones read from the index.",
                "tensor_count_reconciliation": {"total_tensors": len(shapes),
                                                "expected": "12 layers x 13 tensors + wte + wpe + ln_f.weight "
                                                            "+ ln_f.bias = 160",
                                                "matches": len(shapes) == 12 * 13 + 4}},
            "byte_accounting_of_the_file": accounting,
        },
        "attempt_history": {
            "attempt_1_at_utc": "2026-11-05T15:28:03Z",
            "attempt_1_verdict": "MISMATCH on 8 tensors plus n_layer, every one of them found=None",
            "attempt_1_cause_measured": "the checker asked for `transformer.*` module paths; the index uses "
                                        "bare GPT2 names. No shape disagreed with the spec -- the names did.",
            "attempt_1_failures_verbatim": ["transformer.wte.weight", "transformer.wpe.weight",
                                           "transformer.wt.weight", "transformer.ln_f.weight",
                                           "transformer.h.0.attn.c_attn.weight",
                                           "transformer.h.0.attn.c_proj.weight",
                                           "transformer.h.0.mlp.c_fc.weight",
                                           "transformer.h.0.mlp.c_proj.weight", "layer count 0 != 12"],
            "what_was_done_with_it": "the wrong verdict was not left standing in the tree. The provenance "
                                     "file it wrote was uncommitted and unsealed, produced minutes earlier in "
                                     "the same step, so it was superseded by this one and its text is "
                                     "reproduced here rather than edited anywhere.",
            "special_tokens_map_404": "the first attempt died on an HTTP 404 for special_tokens_map.json, "
                                      "which is not at the root of this revision; see "
                                      "absent_at_this_revision.",
            "attempt_2_checker_bug_measured": (
                "the second attempt wrote a MISMATCH-free shape verdict but a wrong buffer/weight split: it "
                "selected mask buffers with endswith('attn.bias'), which also caught the 12 c_attn.bias "
                "trainable biases, reporting 24 mask buffers, 'all_match: false', and a weights-only count of "
                "124,412,160 instead of 124,439,808. Fixed by exact-key matching on h.<N>.attn.bias. The "
                "provenance file it produced was uncommitted and unsealed, minutes old in the same step, so it "
                "was superseded rather than patched; this block is where its numbers survive."),
        },
        "what_was_deliberately_not_downloaded": {
            "variants": ["tf_model.h5", "flax_model.msgpack", "rust_model.ot", "64*.tflite", "onnx/*",
                         "pytorch_model.bin"],
            "why": "one canonical byte string per tensor. Four copies of the same weights in a library is an "
                   "invitation to make a claim against whichever copy somebody opened. pytorch_model.bin is "
                   "additionally pickle-format, which a read-only address space should not need.",
            "recorded_from_the_api_file_list": ["model.safetensors", "config.json", "generation_config.json",
                                               "vocab.json", "merges.txt", "tokenizer.json",
                                               "tokenizer_config.json", "special_tokens_map.json",
                                               "README.md"],
        },
        "state_this_leaves": {
            "blocker_now": "weights present, sealed by hash, NOT YET READ",
            "no_extraction_run": True,
            "no_probe_list_fixed": True,
            "no_forward_pass": True,
            "next_step_is_not_this_one": "B.6 items 2 and 3 -- the address space and the access journal must "
                                         "be registered as instruments (R10) before the first extraction.",
        },
    }
    OUT.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[land] VERDICT: {out['shape_verification_against_the_pinned_spec']['verdict']}")
    print(f"[land] tensors {len(shapes)} | params from shapes {n_params:,} | dtypes "
          f"{out['tensor_inventory']['dtypes']}")
    print(f"[land] total bytes {out['total_bytes_on_disk']:,} | free after {out['disk']['free_after_GB']} GB")
    print(f"[land] provenance -> {OUT.relative_to(ROOT)}")
    for c in checks:
        print(f"   {'OK ' if c['match'] else 'FAIL'} {c['tensor']:42s} {c['found_shape']} "
              f"{c['dtype']}  (expected {c['expected_shape']})")
    print(f"   {'OK ' if layers_ok else 'FAIL'} n_layer = {len(layers)} (expected {LAYER_COUNT_EXPECT})")
    return 1 if failures or not layers_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
