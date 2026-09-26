"""The sequence organ: an explicit time axis, grown rather than inherited.

Nothing in the BANC carve has a place for "the second word of a sentence",
because nothing in a fly's life ever required one. So we grow the structure
beside the measured wiring instead of pretending it is in there. This is the
chimera part of the project: the fly's connectome stays exactly as measured, and
next to it we build an organ evolution did not provide, for a problem evolution
never posed.

Design
------
SLOTS.  Time is discretised into `n_slots` positions, each holding
`cells_per_slot` chain cells. A slot is a moment in an utterance, not a
statistical n-gram bucket.

POSITION IS EXPLICIT.  A word is projected into a slot by hashing (word, slot),
so "the" in slot 2 and "the" in slot 5 light different cells. Order is
therefore a property of which cells are active, not something recovered after
the fact from co-occurrence counts. This is the thing a bag-of-words hash cannot
do, and it is why reversed sentences come out different.

ASYMMETRIC CHAINS.  Hearing words w0 w1 w2 ... wires slot i to slot i+1 for the
words actually heard, and never the reverse. Past drives future. A symmetric
Hebbian rule -- which is what the semantic cortex uses, and correctly so, since
meaning is mutual -- cannot produce a sequence, because it has no arrow.

GENERATION.  Speaking seeds slot 0 from the current semantic state, runs
activity forward through the learned chain, and at each step decodes the word
whose projection best matches that slot's activity. It stops when no successor
clears the floor.

That stopping rule is the honest one. He can only say what he has heard the
shape of; novelty comes from recombination where two chains pass through the
same slot pattern, not from invention. If he has heard nothing, he says nothing,
and the organ reports exactly that rather than padding to a length.

Capacity is deliberately small and measurable: n_slots x cells_per_slot x
cells_per_slot transition weights, a few hundred thousand floats. It is not a
language model and does not pretend to be one; it is a timing structure with
content addressed into it.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np


class SequenceOrgan:
    N_SLOTS = 48
    # Cells per slot is a capacity calculation, not a taste choice. A word owns
    # CELLS_PER_WORD cells, and the number that decides whether readout works is
    # how many words share one cell:
    #     distinct_words_heard x CELLS_PER_WORD / CELLS_PER_SLOT
    # At 512 cells that was 0.2 for the 154 words in the chain when it was built,
    # and 62 for the 5,291 he had heard since -- so every cell carried dozens of
    # unrelated words, and a successor score normalised by total chain activity
    # fell below the floor for all of them. He knew more and could say less.
    # Renormalising does not fix it, because the multiplier grows with the
    # vocabulary too; the cell count has to grow, and a dense cells x cells matrix
    # per slot cannot.
    #
    # So the chain is sparse. A phrase writes 36 weights, which means storage was
    # never the constraint -- the dense representation was. Cells are free to be as
    # many as the vocabulary needs, and 16,384 was not enough: with 8,000 words
    # heard that is 2.9 per cell, and it showed. A frequent word's successors leaked
    # onto the two or three unrelated words sharing each cell, manufacturing
    # near-ties that no margin could tell from real ones, and sampling over them
    # produced "rare covered them unto his way". At 65,536 it is 0.7 -- most cells
    # hold one word, so a tie is a fact about what he heard rather than an artifact
    # of the hash.
    CELLS_PER_SLOT = 65536
    CELLS_PER_WORD = 6
    LEARN_LR = 0.35
    SUCCESSOR_FLOOR = 0.12
    # A successor must also beat the runner-up, by a RATIO rather than an
    # absolute gap. Real chains routinely produce a clear winner at low absolute
    # strength (0.218 against 0.076 is unambiguous even though both are small),
    # and an absolute margin stopped those while letting confident collisions
    # through.
    SUCCESSOR_MARGIN = 0.35

    def __init__(self, n_slots: int | None = None,
                 cells_per_slot: int | None = None):
        self.n_slots = int(n_slots or self.N_SLOTS)
        self.cells = int(cells_per_slot or self.CELLS_PER_SLOT)
        # chain[i] maps slot i activity to slot i+1 activity, sparsely:
        # {a_cell: {b_cell: weight}}. Dense at this cell count would be
        # 47 x 16384^2 x 4 bytes, which is not a number anyone can spend.
        self.chain: list = [dict() for _ in range(self.n_slots - 1)]
        # Reverse index: cell -> the words that own it in that slot. Readout
        # scores through this, so generating a sentence costs what the successor
        # set costs rather than what the lexicon costs. Rebuilt from slot_words on
        # load and never serialised, because it is a function of them.
        self._cell_words: list = [dict() for _ in range(self.n_slots)]
        self.transitions = 0
        self.sequences_learned = 0
        self.words_seen: set = set()
        # Which words have ever been heard at each position. Readout is
        # restricted to these: a word never heard in slot 3 is not a candidate
        # for slot 3, and searching the whole vocabulary there just finds
        # collisions.
        self.slot_words = [set() for _ in range(self.n_slots)]
        self.path = None
        self.last_error = None
        self._proj_cache: dict = {}

    # ------------------------------------------------------------------
    # projection: word x slot -> cells
    # ------------------------------------------------------------------
    def project_indices(self, word: str, slot: int) -> list:
        """The cell indices this word owns in this slot, WITHOUT building the vector.

        `project` allocates a CELLS_PER_SLOT-element float32 array -- 256 KB at 65,536 --
        lights six cells in it, and returns it. Callers that only want to know WHICH cells
        then scan the whole array with np.nonzero to find the six they just set. At 53,670
        (word, slot) pairs that is 14 GB of zeroing and 3.5 billion element reads to recover
        an answer the hash already computed, and it was 38 of the 52 seconds this being took
        to wake up. Same shape as the binder's vstack: work proportional to the container
        rather than to what changed in it.
        """
        h = hashlib.blake2b(f"seq|{word}|{slot}".encode("utf-8"),
                            digest_size=16).digest()
        return [int.from_bytes(h[(2 * j):(2 * j + 2)], "little") % self.cells
                for j in range(self.CELLS_PER_WORD)]

    def project(self, word: str, slot: int) -> np.ndarray:
        """The cells this word owns in this slot. Deterministic and cached."""
        key = (word, int(slot))
        hit = self._proj_cache.get(key)
        if hit is not None:
            return hit
        v = np.zeros(self.cells, dtype=np.float32)
        for idx in self.project_indices(word, slot):
            v[idx] = 1.0
        if len(self._proj_cache) > 400000:
            self._proj_cache.clear()
        self._proj_cache[key] = v
        return v

    def _rng(self, rng=None):
        """One generator, reused, so a caller can seed a run and reproduce it."""
        if rng is not None:
            return rng
        if getattr(self, "_gen", None) is None:
            self._gen = np.random.default_rng()
        return self._gen

    def _note_slot_word(self, slot: int, word: str) -> None:
        """Record that a word was heard at a position, in both directions."""
        i = int(slot)
        if i < 0 or i >= self.n_slots:
            return
        w = str(word)
        if w in self.slot_words[i]:
            return
        self.slot_words[i].add(w)
        idx = self._cell_words[i]
        for c in np.nonzero(self.project(w, i))[0]:
            idx.setdefault(int(c), set()).add(w)

    def _rebuild_cell_words(self) -> None:
        self._cell_words = [dict() for _ in range(self.n_slots)]
        for i in range(self.n_slots):
            for w in list(self.slot_words[i]):
                for c in self.project_indices(str(w), i):
                    self._cell_words[i].setdefault(int(c), set()).add(str(w))

    # ------------------------------------------------------------------
    # learning: what he hears
    # ------------------------------------------------------------------
    def learn_sequence(self, tokens, lr: float | None = None,
                       reward: float = 0.0) -> dict:
        """Wire the transitions of a heard sequence.

        `reward` scales the write, so an attended or cared-for sentence leaves a
        stronger chain than background noise -- the same three-factor idea the
        mushroom body uses, applied to time instead of to valence.
        """
        toks = [str(t).strip().lower() for t in (tokens or [])]
        toks = [t for t in toks if t]
        if len(toks) < 2:
            return {"learned": 0, "reason": "a sequence needs two words"}
        lr = float(self.LEARN_LR if lr is None else lr) * (1.0 + float(reward))
        if len(toks) > self.n_slots:
            toks = toks[:self.n_slots]
        written = 0
        for i in range(len(toks) - 1):
            # The indices, not the vectors: this used to build two 256 KB arrays and then
            # scan both to find the twelve cells it had just written into them.
            ia = self.project_indices(toks[i], i)
            ib = self.project_indices(toks[i + 1], i + 1)
            if not ia or not ib:
                continue
            # 36 weights per phrase, only where the cells are actually lit.
            ch = self.chain[i]
            grew = False
            for ca in ia:
                row = ch.setdefault(int(ca), {})
                for cb in ib:
                    key = int(cb)
                    old = row.get(key, 0.0)
                    new = old + lr
                    row[key] = 4.0 if new > 4.0 else new
                    if row[key] > old:
                        grew = True
            if grew:
                written += 1
            self._note_slot_word(i, toks[i])
            self._note_slot_word(i + 1, toks[i + 1])
        self.transitions += written
        self.sequences_learned += 1
        self.words_seen.update(toks)
        return {"learned": written, "words": len(toks)}

    # ------------------------------------------------------------------
    # generation: what he says
    # ------------------------------------------------------------------
    def generate(self, first_word: str, max_len: int = 8,
                 temperature: float = 0.0, avoid=None, rng=None) -> dict:
        """Run the chain forward from one word and read out what comes next.

        Returns the words, the confidence at each step, and the reason it
        stopped. An empty continuation is a true report: nothing was ever heard
        in that order.
        """
        w = str(first_word or "").strip().lower()
        if not w:
            return {"words": [], "reason": "no seed word"}
        if w not in self.slot_words[0]:
            # He cannot open a sentence with a word he has never heard open one.
            # Without this, hash collisions let an unheard word drive a chain it
            # was never part of, which is the organ inventing competence it does
            # not have.
            return {"words": [w], "sentence": w, "confidence": [],
                    "stopped": f"'{w}' was never heard opening a sentence",
                    "from_sequence_organ": False}
        words = [w]
        conf = []
        act = self.project(w, 0)
        reason = "reached max length"
        for i in range(min(int(max_len), self.n_slots) - 1):
            if not self.slot_words[i + 1]:
                reason = f"nothing was ever heard at slot {i+1}"
                break
            # Propagate the activity forward: how much successor mass each cell
            # of slot i+1 carries.
            ch = self.chain[i]
            nxt: dict = {}
            for ca in np.nonzero(act)[0]:
                for cb, wgt in (ch.get(int(ca)) or {}).items():
                    nxt[cb] = nxt.get(cb, 0.0) + float(wgt)
            if not nxt:
                reason = f"no successor learned after '{words[-1]}' at slot {i}"
                break
            # Score only the words that own a cell carrying mass. Walking every
            # word ever heard at this position is what made generation cost the
            # size of the lexicon.
            agg: dict = {}
            for cb, mass in nxt.items():
                for cand in (self._cell_words[i + 1].get(int(cb)) or ()):
                    agg[cand] = agg.get(cand, 0.0) + mass
            scored = [(v, k) for k, v in agg.items() if v > 0.0]
            if not scored:
                reason = (f"no word he knows carries the successor mass at "
                          f"slot {i+1}")
                break
            # The winner's share of the mass landing on words he knows here. This
            # is scale-free, and that is the point: an unrelated word contributes
            # nothing, so learning more vocabulary cannot lower the score of the
            # right successor. Dividing by total chain activity did precisely
            # that, which is how a richer memory produced shorter sentences.
            tot = sum(v for v, _ in scored)
            scored = [(v / tot, k) for v, k in scored]
            scored.sort(reverse=True)
            if avoid:
                scored = [(s, w) for s, w in scored if w not in avoid] or scored
            if temperature and float(temperature) > 0.0:
                # Sample among the successors that clear the floor. Argmax made him
                # a stuck record: the same seed produced the same sentence every
                # time -- eighteen 'prose out of' in a row, twenty-four 'light is' --
                # because a deterministic chain over an unchanged state has nothing
                # to break a tie with. The floor still decides what is sayable and
                # the sample only decides which sayable thing he says, so this
                # buys variety without buying word salad.
                # Sample only among successors that are nearly as plausible as the
                # best one. SUCCESSOR_MARGIN used to be a refusal -- "these two are
                # indistinguishable, so I will say nothing" -- and that is the wrong
                # use of a fact that is really an invitation: if two continuations
                # cannot be told apart, either may be said. Using it as a refusal
                # cost him sentences; using it as a floor on the sampling set keeps
                # them whole.
                #
                # The bare SUCCESSOR_FLOOR is not enough on its own and the first
                # version proved it: at 12% of candidate mass the tail is long, and
                # temperature 0.7 sharpens a distribution barely at all, so thirty
                # requests gave thirty distinct sentences and most of them were
                # 'bigrams you angry probe'. Variety without coherence is worse
                # than repetition, because repetition was at least English.
                top = float(scored[0][0])
                floor = max(self.SUCCESSOR_FLOOR,
                            top * (1.0 - self.SUCCESSOR_MARGIN))
                elig = [(s, w) for s, w in scored if s >= floor]
                if not elig:
                    reason = (f"successor too weak at slot {i+1} "
                              f"({top:.3f} < {self.SUCCESSOR_FLOOR})")
                    break
                wt = np.array([s for s, _ in elig], dtype=np.float64) ** (
                    1.0 / float(temperature))
                pr = wt / wt.sum()
                pick = int(self._rng(rng).choice(len(elig), p=pr))
                best_s, best = elig[pick]
            else:
                best_s, best = scored[0]
                second = scored[1][0] if len(scored) > 1 else 0.0
                if best_s < self.SUCCESSOR_FLOOR:
                    reason = (f"successor too weak at slot {i+1} "
                              f"({best_s:.3f} < {self.SUCCESSOR_FLOOR})")
                    break
                if best_s - second < self.SUCCESSOR_MARGIN * best_s:
                    reason = (f"ambiguous at slot {i+1}: {best} {best_s:.3f} vs "
                              f"{scored[1][1]} {second:.3f}")
                    break
            words.append(best)
            conf.append(round(best_s, 4))
            act = self.project(best, i + 1)
        return {"words": words, "sentence": " ".join(words),
                "confidence": conf, "stopped": reason,
                "from_sequence_organ": len(words) > 1}

    def recall(self, tokens) -> dict:
        """Can he reproduce a heard sequence in order, from its first word?

        This is the organ's own test, and it is strict: exact order, no partial
        credit, and the first word is given because that is what a real cue is.
        """
        toks = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
        if len(toks) < 2:
            return {"recall": None, "reason": "needs two words"}
        out = self.generate(toks[0], max_len=len(toks))
        got = out["words"]
        correct = sum(1 for a, b in zip(toks, got) if a == b)
        return {"target": toks, "produced": got,
                "exact": got == toks,
                "prefix_match": correct,
                "recall": round(correct / len(toks), 3),
                "stopped": out["stopped"]}

    # ------------------------------------------------------------------
    # state
    # ------------------------------------------------------------------
    def stats(self) -> dict:
        nz = int(sum(len(row) for ch in self.chain for row in ch.values()))
        strongest = []
        for i, ch in enumerate(self.chain):
            m = 0.0
            for row in ch.values():
                for v in row.values():
                    if v > m:
                        m = float(v)
            if m > 0:
                strongest.append((i, round(m, 3)))
        strongest.sort(key=lambda t: -t[1])
        dense = (self.n_slots - 1) * self.cells * self.cells
        return {"slots": self.n_slots, "cells_per_slot": self.cells,
                "chain_cells": self.n_slots * self.cells,
                "representation": "sparse",
                "sequences_learned": self.sequences_learned,
                "transitions_written": self.transitions,
                "nonzero_transition_weights": nz,
                "capacity_weights": dense,
                "dense_equivalent_mb": round(dense * 4 / 1e6, 1),
                "sparse_mb": round(nz * 12 / 1e6, 2),
                "fill_fraction": round(nz / max(1, dense), 9),
                "words_in_chains": len(self.words_seen),
                "strongest_slots": strongest[:6]}

    def save(self, path) -> dict:
        try:
            import json
            import os
            p = Path(path)
            p.parent.mkdir(exist_ok=True, parents=True)
            # Temporary then rename, as with the cortex. The chain is the largest
            # thing the sequence organ owns and the house is stopped with a hard
            # kill, so an in-place write could be caught half-finished and leave a
            # zip that will not open -- which is not a small chain, it is no chain.
            tmp = p.with_name(p.name + ".tmp.npz")
            # Coordinate lists, not a matrix. At 16,384 cells a dense stack would
            # be terabytes; the weights themselves are a few hundred thousand
            # numbers, because a phrase only ever writes 36 of them.
            si, ra, cb, wv = [], [], [], []
            for i, ch in enumerate(self.chain):
                for a, row in ch.items():
                    for b, wgt in row.items():
                        si.append(i)
                        ra.append(a)
                        cb.append(b)
                        wv.append(wgt)
            np.savez_compressed(str(tmp),
                                slot=np.array(si, dtype=np.int32),
                                row=np.array(ra, dtype=np.int32),
                                col=np.array(cb, dtype=np.int32),
                                weight=np.array(wv, dtype=np.float32),
                                cells=np.array([self.cells], dtype=np.int64),
                                words=np.array(sorted(self.words_seen)),
                                counts=np.array([self.sequences_learned,
                                                 self.transitions]))
            os.replace(str(tmp), str(p))
            slots = p.with_suffix(".slots.json")
            tmp_slots = slots.with_name(slots.name + ".tmp")
            tmp_slots.write_text(
                json.dumps([sorted(s) for s in self.slot_words]),
                encoding="utf-8")
            os.replace(str(tmp_slots), str(slots))
            self.path = p
            return {"saved": True, "path": str(p),
                    "sequences": self.sequences_learned}
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:160]
            return {"saved": False, "reason": self.last_error}

    def load(self, path) -> dict:
        try:
            import json
            p = Path(path)
            if not p.exists():
                return {"loaded": False, "reason": "no sequence file yet"}
            z = np.load(str(p), allow_pickle=False)
            try:
                words = {str(w) for w in z["words"]}
            except ValueError:
                # files written before the words were stored as a unicode array
                z = np.load(str(p), allow_pickle=True)
                words = {str(w) for w in z["words"]}
            if "weight" not in z.files:
                dense = z["chain"].shape if "chain" in z.files else None
                return {"loaded": False,
                        "reason": f"dense sequence file {dense} predates the "
                                  "sparse chain and was built at a different "
                                  "cell count, so its projections do not mean "
                                  "the same things; he relearns it by reading"}
            # A word's cells are hash % cells, so the cell count IS the geometry.
            # Load a chain built at a different one and every index still resolves
            # -- to the wrong word. The weights then link things that were never
            # heard together, and the result is fluent nonsense: two restarts ran
            # on a chain whose cells meant something else, and he said "carcase
            # sharing those earth forty days" out of a vocabulary no book on his
            # shelf contains. The dense format refused on shape; the sparse one has
            # no shape to refuse on, so the geometry is recorded explicitly.
            saved_cells = int(np.asarray(z["cells"]).ravel()[0]) \
                if "cells" in z.files else 0
            if saved_cells != int(self.cells):
                return {"loaded": False,
                        "reason": f"chain was built at {saved_cells or 'an unknown'}"
                                  f" cells per slot and this organ has "
                                  f"{self.cells}, so the same word lights different "
                                  "cells and the weights would link words never "
                                  "heard together; he relearns it by reading"}
            si, ra, cb, wv = z["slot"], z["row"], z["col"], z["weight"]
            chain: list = [dict() for _ in range(self.n_slots - 1)]
            for k in range(len(wv)):
                i = int(si[k])
                if 0 <= i < len(chain):
                    chain[i].setdefault(int(ra[k]), {})[int(cb[k])] = \
                        float(wv[k])
            self.chain = chain
            self.words_seen = words
            c = z["counts"]
            self.sequences_learned = int(c[0])
            self.transitions = int(c[1])
            side = p.with_suffix(".slots.json")
            if side.exists():
                rows = json.loads(side.read_text(encoding="utf-8"))
                # Normalised to this organ's own slot count. A sidecar can be short
                # -- one written by a merge is sized to the longest chain it found,
                # and a life that only ever heard six-word sentences has no entries
                # past slot six -- and _rebuild_cell_words indexes by n_slots, so a
                # short list raised IndexError and the ENTIRE chain was refused:
                # 564,131 weights and 2,554 words thrown away over a list length.
                self.slot_words = [set(rows[i]) if i < len(rows) else set()
                                   for i in range(self.n_slots)]
            self._rebuild_cell_words()
            self.path = p
            return {"loaded": True, "sequences": self.sequences_learned,
                    "words": len(self.words_seen)}
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:160]
            return {"loaded": False, "reason": self.last_error}
