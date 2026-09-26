"""A population, and the merge that makes it one animal.

This is the capability biology does not have. Twenty individuals can be raised in
parallel on different corpora and different organ parameters, and then their
learned structures can be combined into a single brain -- because everything he
knows is a matrix, a chain, a set of propositions and a set of Kenyon-cell
addresses, and all four have a sensible combination rule:

    vocabulary      union; on conflict keep the word that was heard more
    semantic cortex element-wise mean of san_w  (Hebbian weights average cleanly)
    sequence chains element-wise SUM  (a chain is a count of what was heard, so
                    two lives that heard the same order reinforce it)
    propositions    union by token tuple, counts summed
    plastic weights averaged across individuals that share the synapse identity

Nothing is invented here: this is the same arithmetic the organs already do, just
applied across individuals instead of across time. An individual gets one life;
this gives him N of them, and N lives of exposure is the difference between
learning English and learning a pamphlet.

Usage:
    python tools/population.py grow  --n 4 --seconds 240 --books 01,02,03,04
    python tools/population.py merge --n 4 --out state/merged
    python tools/population.py both  --n 4 --seconds 240

Each individual is isolated in its own project root, so no two of them can write
the same state file -- which is the mistake that once put six brains on one port
and saturated the machine.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
POP = ROOT / "state" / "population"
BOOKS = ROOT / "books"


def _agent_for(indiv_dir: Path, api_key=None):
    """A headless individual: full organs, no HTTP server, no teacher."""
    os.environ["HYBRIDLLM_OFFLINE"] = "1"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from world.connectome_house import build_house_agent
    indiv_dir.mkdir(parents=True, exist_ok=True)
    cfg = {"model": {"api_key": api_key, "provider": "qwen"},
           "language": {"state_path": str(indiv_dir / "language_state.json"),
                        "auto_train": False},
           "connectome": {"project_root": str(indiv_dir),
                          "accelerated_life": False},
           "sandbox": {"project_root": str(indiv_dir)},
           "house": {"enabled": False}}
    return build_house_agent(cfg, project_root=str(indiv_dir))


def _grow_one(indiv_dir: Path, book_names, seconds: float, seed: int) -> dict:
    """One life, raised through his REAL reading organ.

    Calling live() directly would have been faster to write and wrong: word
    assimilation, teaching and the question/answer adjacency all happen inside
    expose_tick, and bypassing it produced an individual with 612 propositions
    and a vocabulary of zero.
    """
    t0 = time.time()
    agent = _agent_for(indiv_dir)
    lang = agent.language
    from organs.tokenizer import TokenizerOrgan
    if getattr(lang, "tokenizer", None) is None:
        lang.tokenizer = TokenizerOrgan()
    # a private shelf: this individual's copy of the assigned books, so nobody
    # else's reading position can move under it
    shelf = indiv_dir / "books"
    if shelf.exists():
        shutil.rmtree(shelf, ignore_errors=True)
    shelf.mkdir(parents=True, exist_ok=True)
    # The reader iterates the shelf alphabetically, so the order has to be in the
    # filenames -- passing an ordered list means nothing to it. Without this the
    # question book sat fifth in alphabetical order and nobody reached it.
    for k, name in enumerate(book_names):
        src = BOOKS / (name if str(name).endswith(".txt") else str(name) + ".txt")
        if src.exists():
            shutil.copy(src, shelf / f"{k:02d}_{src.name}")
    lang.set_books_dir(shelf)
    lang.exposure_enabled = True
    lang.exposure_speed_s = 0.0
    lang.EXPOSURE_MIN_REAL_S = 0.0
    lang._book_words = []
    lang._book_lines = []
    lang._book_is_q = []
    lang._book_line_pos = 0
    lines_read = 0
    deadline = t0 + float(seconds)
    saves = 0
    while time.time() < deadline:
        before = (lang._book_idx, lang._book_line_pos)
        lang.expose_tick(1.0)
        after = (lang._book_idx, lang._book_line_pos)
        if after != before:
            lines_read += 1
        if lines_read and lines_read % 4000 == 0 and saves < 100:
            saves += 1
            lang.save_state(force_san=True)
    lang.save_state(force_san=True)
    try:
        agent.engine.save_brain(indiv_dir / "banc_brain.npz")
    except Exception:
        pass
    el = max(1e-9, time.time() - t0)
    return {"dir": str(indiv_dir), "lines_read": lines_read,
            "seconds": round(el, 1), "lines_per_second": round(lines_read / el, 1),
            "vocabulary": lang.vocabulary_size(),
            "propositions": int(lang.cortex.binder.X.shape[0]),
            "qa_pairs": int(lang.qa_pairs_seen),
            "interrogatives": sorted(lang.interrogatives),
            "sequences": int(lang.sequence.sequences_learned),
            "words_in_chains": len(lang.sequence.words_seen)}


def grow(n: int, seconds: float, books: str, workers: int | None = None) -> list:
    names = [b.strip() for b in books.split(",") if b.strip()]
    available = sorted(p.stem for p in BOOKS.glob("*.txt"))
    if not names:
        names = available
    jobs = []
    # The question/answer book goes first for everyone. It is only 386 lines, and
    # it is the sole source of supervision in the whole system -- an individual
    # that ran out of time before reaching it would learn a language with no
    # questions in it.
    qa = [b for b in names if "question" in b]
    rest = [b for b in names if b not in qa]
    for i in range(int(n)):
        shard = qa + rest[i % max(1, len(rest)):] + rest[:i % max(1, len(rest))]
        jobs.append((POP / f"indiv_{i}", shard, float(seconds), i))
    procs = min(int(workers or max(1, (os.cpu_count() or 2) - 1)), len(jobs))
    print(f"growing {len(jobs)} individuals, {procs} at a time, "
          f"{seconds}s each")
    out = []
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    for start in range(0, len(jobs), procs):
        batch = jobs[start:start + procs]
        with ctx.Pool(len(batch)) as pool:
            res = pool.starmap(_grow_one, batch)
        for r in res:
            print("  ", json.dumps({k: v for k, v in r.items() if k != "dir"}))
            out.append(r)
    return out


# ----------------------------------------------------------------------
# merge
# ----------------------------------------------------------------------
def _state_dir(d: Path) -> Path:
    """Where an individual's state actually lives.

    A grown individual gets a project root with a `state/` directory inside it. A
    lineage saved for safekeeping is the files themselves, flat, because that is
    what was copied out of a living animal. Both have to be readable or the saved
    lineages cannot be merged back in -- which is the whole reason to keep them.
    """
    d = Path(d)
    sub = d / "state"
    return sub if (sub / "language_state.json").exists() else d


def _load_state(d: Path):
    p = _state_dir(d) / "language_state.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def merge(n: int, out_dir: str, dirs=None, san_from: int | None = None) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if dirs:
        cand = [Path(d) for d in dirs]
    else:
        cand = [POP / f"indiv_{i}" for i in range(int(n))]
    dirs = [d for d in cand if (_state_dir(d) / "language_state.json").exists()]
    if not dirs:
        return {"merged": False, "reason": "no individuals to merge"}
    print(f"merging {len(dirs)} individuals: {[d.name for d in dirs]}")

    # ---- vocabulary: union, keeping the more-heard record on conflict -------
    words: dict = {}
    san_acc = None
    san_n = 0
    chain_words: set = set()
    chain_counts = None
    chain_geom = None
    chain_skipped = 0
    chain_merged_weights = 0
    seq_keys: list = []
    seq_wts: list = []
    san_keep = None
    props: dict = {}
    qa_roles: dict = {}
    answer_types: dict = {}
    statements: dict = {}
    merged_interrogatives: set = set()
    for k, d in enumerate(dirs):
        st = _load_state(d)
        if not st:
            continue
        for w, rec in (st.get("words") or {}).items():
            old = words.get(w)
            if old is None or int(rec.get("count", 1)) > int(old.get("count", 1)):
                words[w] = rec
        qs = st.get("questions") or {}
        merged_interrogatives.update(str(w) for w in (qs.get("interrogatives") or []))
        for k, v in (qs.get("roles") or {}).items():
            slot = qa_roles.setdefault(k, {})
            for r, c in v.items():
                slot[r] = int(slot.get(r, 0)) + int(c)
        for k, v in (qs.get("answer_types") or {}).items():
            slot = answer_types.setdefault(k, {})
            for r, c in v.items():
                slot[r] = int(slot.get(r, 0)) + int(c)
        for k, v in (qs.get("statement_words") or {}).items():
            statements[k] = max(int(statements.get(k, 0)), int(v))
        # semantic cortex: element-wise mean
        sanp = _state_dir(d) / "language_state.san.npy"
        if sanp.exists():
            if san_from is not None:
                if k == int(san_from):
                    san_keep = sanp
            else:
                m = np.load(str(sanp), mmap_mode="r")
                if san_acc is None:
                    san_acc = np.zeros(m.shape, dtype=np.float64)
                if san_acc.shape == m.shape:
                    san_acc += np.asarray(m, dtype=np.float64)
                    san_n += 1
        # sequence chains: element-wise sum
        seqp = _state_dir(d) / "language_state.json.seq.npz"
        if seqp.exists():
            try:
                z = np.load(str(seqp))
                zw = z["words"]
            except ValueError:
                z = np.load(str(seqp), allow_pickle=True)
                zw = z["words"]
            if "weight" not in z.files:
                # A dense chain from before the sparse rewrite. Its indices mean
                # something else at another cell count, so there is nothing sound to
                # sum it with.
                chain_skipped += 1
            else:
                cells = int(np.asarray(z["cells"]).ravel()[0]) \
                    if "cells" in z.files else 0
                if chain_geom is None:
                    chain_geom = cells
                if cells != chain_geom:
                    chain_skipped += 1
                else:
                    sl = np.asarray(z["slot"], dtype=np.int64)
                    rw = np.asarray(z["row"], dtype=np.int64)
                    cl = np.asarray(z["col"], dtype=np.int64)
                    seq_keys.append(sl * (cells * cells) + rw * cells + cl)
                    seq_wts.append(np.asarray(z["weight"], dtype=np.float64))
            # The word list has to be unioned too, and so do the counts. A chain's
            # cells are blake2b("seq|word|slot"), so the same word lights the same
            # cells in every individual and summing the matrices is sound -- but
            # writing one individual's word list left the merged animal able to
            # name 154 words through a chain whose weights covered far more, and
            # 89% of his vocabulary could not take part in a sentence.
            chain_words.update(str(w) for w in zw)
            cc = np.asarray(z["counts"], dtype=np.float64)
            chain_counts = cc if chain_counts is None else chain_counts + cc
        # propositions: union by token tuple, counts summed
        cp = _state_dir(d) / "language_state.json.cortex.npz"
        mp_ = _state_dir(d) / "language_state.json.cortex.meta.json"
        if cp.exists() and mp_.exists():
            z = np.load(str(cp))
            meta = json.loads(mp_.read_text(encoding="utf-8"))
            X, C = z["X"], z["C"]
            for i, m in enumerate(meta):
                key = tuple(str(t).lower() for t in m.get("tokens", []))
                prev = props.get(key)
                if prev is None:
                    props[key] = {"meta": m, "X": np.asarray(X[i], np.float32),
                                  "C": np.asarray(C[i], np.float32)}
                else:
                    prev["meta"]["count"] = int(prev["meta"].get("count", 1)) + \
                        int(m.get("count", 1))

    merged_state = dict(_load_state(dirs[0]) or {})
    merged_state["words"] = words
    merged_state["questions"] = {"roles": qa_roles,
                                 "interrogatives": sorted(
                                     set(merged_interrogatives)
                                     | {w for w, v in qa_roles.items()
                                        if v and max(int(x) for x in v.values()) >= 2}),
                                 "answer_types": answer_types,
                                 "statement_words": statements,
                                 "pairs_seen": sum(
                                     int((r or {}).get("0", 0))
                                     for r in qa_roles.values())}
    (out / "language_state.json").write_text(
        json.dumps(merged_state), encoding="utf-8")

    if san_keep is not None:
        # Averaging is the right rule for equals and the wrong one for a teacher and
        # a pupil. Two lives raised on the same corpus for the same time have
        # comparably trained semantic cortices, and the mean of them is better than
        # either. One life of 3,061 words merged with one of 582 does not: the mean
        # halves what the experienced animal learned and doubles what the other
        # barely started. Vocabulary, propositions, chains and question mappings are
        # all still unioned or summed -- those grow by pooling. Only the cortex is
        # taken whole, from the individual that actually has one.
        import shutil as _sh
        _sh.copy(str(san_keep), str(out / "language_state.san.npy"))
    elif san_acc is not None and san_n:
        np.save(str(out / "language_state.san.npy"),
                (san_acc / san_n).astype(np.float32))

    if seq_keys:
        # Sum the sparse chains by coordinate. Two lives that heard the same order
        # reinforce it, which is why a chain sums rather than averages: it is a
        # count of what was heard, not a rate.
        allk = np.concatenate(seq_keys)
        allw = np.concatenate(seq_wts)
        uk, inv = np.unique(allk, return_inverse=True)
        summed = np.bincount(inv, weights=allw)
        c2 = chain_geom * chain_geom
        m_slot = (uk // c2).astype(np.int32)
        rem = uk % c2
        m_row = (rem // chain_geom).astype(np.int32)
        m_col = (rem % chain_geom).astype(np.int32)
        np.savez_compressed(str(out / "language_state.json.seq.npz"),
                            slot=m_slot, row=m_row, col=m_col,
                            weight=summed.astype(np.float32),
                            cells=np.array([chain_geom], dtype=np.int64),
                            words=np.array(sorted(chain_words)),
                            counts=(chain_counts if chain_counts is not None
                                    else np.zeros(2)).astype(np.int64))
        chain_merged_weights = int(len(uk))
        # The slot vocabulary has to be merged too. Chains without it are unusable:
        # nothing can open a sentence, because the organ only seeds from words it
        # has actually heard in that position.
        n_slots = int(m_slot.max()) + 2 if len(m_slot) else 1
        slots: list = [set() for _ in range(n_slots)]
        for d in dirs:
            sp = _state_dir(d) / "language_state.json.seq.slots.json"
            if sp.exists():
                for i, srow in enumerate(
                        json.loads(sp.read_text(encoding="utf-8"))):
                    if i < len(slots):
                        slots[i].update(str(x) for x in srow)
        (out / "language_state.json.seq.slots.json").write_text(
            json.dumps([sorted(s) for s in slots]), encoding="utf-8")

    if props:
        X = np.vstack([v["X"][None, :] for v in props.values()])
        C = np.vstack([v["C"][None, :] for v in props.values()])
        meta = [v["meta"] for v in props.values()]
        np.savez_compressed(str(out / "language_state.json") + ".cortex.npz",
                            P=np.zeros((X.shape[1], X.shape[1]), np.float32),
                            X=X, C=C, counts=np.array([0, len(meta)]))
        (out / "language_state.json.cortex.meta.json").write_text(
            json.dumps(meta), encoding="utf-8")

    # plastic weights: average across individuals sharing the synapse identity
    brains = [d / "banc_brain.npz" for d in dirs if (d / "banc_brain.npz").exists()]
    if brains:
        acc, accn, pre0, post0 = None, 0, None, None
        for b in brains:
            z = np.load(str(b))
            key = list(zip(np.asarray(z["plastic_pre"]).tolist(),
                           np.asarray(z["plastic_post"]).tolist()))
            if acc is None:
                pre0, post0 = np.asarray(z["plastic_pre"]), np.asarray(z["plastic_post"])
                acc = np.zeros(len(key), dtype=np.float64)
                index = {k: i for i, k in enumerate(key)}
            for i, k in enumerate(key):
                j = index.get(k)
                if j is not None:
                    acc[j] += float(z["w"][i])
            accn += 1
        if acc is not None and accn:
            np.savez_compressed(str(out / "banc_brain.npz"),
                                w=(acc / accn).astype(np.float64),
                                plastic_pre=pre0, plastic_post=post0)

    return {"merged": True, "individuals": len(dirs), "out": str(out),
            "vocabulary": len(words),
            "semantic_matrices_averaged": san_n,
            "semantic_cortex_taken_from": (int(san_from) if san_keep is not None
                                           else None),
            "chains_summed": len(seq_keys),
            "chains_skipped": chain_skipped,
            "chain_weights_merged": chain_merged_weights,
            "words_in_chains": len(chain_words),
            "propositions": len(props),
            "slot_words": sum(len(s) for s in (slots if seq_keys else [])),
            "question_words": sorted(qa_roles),
            "brains_averaged": len(brains)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["grow", "merge", "both"])
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--seconds", type=float, default=240.0)
    ap.add_argument("--books", default="")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default=str(ROOT / "state" / "merged"))
    ap.add_argument("--from", dest="src", default="",
                    help="comma-separated individual or lineage directories to "
                         "merge, instead of state/population/indiv_0..n-1")
    ap.add_argument("--san-from", type=int, default=None,
                    help="index into --from whose semantic cortex to take whole, "
                         "instead of averaging all of them; use it when the lives "
                         "are not comparably experienced")
    a = ap.parse_args()
    src = [s.strip() for s in a.src.split(",") if s.strip()]
    if a.cmd in ("grow", "both"):
        grow(a.n, a.seconds, a.books, a.workers)
    if a.cmd in ("merge", "both"):
        print(json.dumps(merge(a.n, a.out, src or None, a.san_from), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
