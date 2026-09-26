"""Higher cortex: prediction and binding, grown beside the measured connectome.

Two capacities the fly's wiring does not provide, because a fly's world never
asked for them. Both operate on a fixed-dimension CONCEPT SPACE that words and
people are projected into, so neither depends on the size of the semantic cortex
and neither adds a trainable language model.

PREDICTOR.  The semantic cortex learns with a symmetric Hebbian rule, which is
correct for meaning -- "night" and "dark" are mutually associated -- and useless
for time, because a symmetric matrix has no arrow. This organ keeps a separate
ASYMMETRIC matrix, written as next-on-rows, now-on-columns, so multiplying it by
the present gives the future. That single asymmetry is the difference between
representing the world and anticipating it. It also produces the only
unsupervised signal worth having: prediction error, which is surprise, and
surprise is what should decide how hard a moment gets written.

BINDER.  Association can say "parent" and "feed" belong together. It cannot say
WHO fed WHOM, because a superposition of two concepts loses the pairing. Binding
restores it: each word is circularly convolved with a role vector before the
concepts are summed, so the proposition `agent(parent) + action(feed) +
object(droso)` is one vector from which any role can be recovered by
unbinding -- convolution's approximate inverse. That is compositionality as
arithmetic: no training, no weights to fit, and a query with a right answer that
can be scored against a shuffled control.

Roles are indexed by POSITION, not by English grammar. Nothing here assumes a
subject-verb-object language; slot 0 is simply "first", and whether first means
agent is something his exposure has to teach him.
"""
from __future__ import annotations

import hashlib
import threading
import time

import numpy as np

from .stemming import stem

DIM = 1024
ACTIVE_CELLS = 64
# Sized to hold a whole corpus rather than to fit a round number. Eviction is a
# full copy of two n x dim matrices, so the right answer is to not evict: at
# 20,000 the store churned on every new sentence once a 45,000-line corpus came
# in, and each churn copied 160 MB.
MAX_PROPOSITIONS = 60000
BETA = 8.0


class ConceptSpace:
    """A fixed random projection from tokens to dense bipolar concept vectors.

    Deterministic and stateless: the same token always lands on the same vector,
    in every process, for the life of the animal.

    These are DENSE ±1 vectors, not sparse codes, and that is a requirement
    rather than a preference. Unbinding multiplies by the conjugate of a role's
    spectrum, which recovers the filler only if |F(role)|² is approximately flat
    across frequencies -- true for dense random vectors, badly false for sparse
    binary ones. Measured: with 64-of-1024 sparse codes, role-filler queries ran
    at chance (3/12); the same memory with dense codes recovers the filler.
    Sparsity still exists where it matters -- in the Kenyon cells that carry a
    word into the carve. This algebra is an internal representational space.
    """

    def __init__(self, dim: int = DIM, active: int = ACTIVE_CELLS, seed: int = 0):
        self.dim = int(dim)
        self.active = int(active)      # kept for the KC side; unused here
        self.seed = int(seed)
        self._cache: dict = {}
        self._norm = float(np.sqrt(self.dim))

    def of(self, token: str) -> np.ndarray:
        key = str(token or "").strip().lower()
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        h = hashlib.blake2b(f"concept|{self.seed}|{key}".encode("utf-8"),
                            digest_size=8).digest()
        rng = np.random.default_rng(int.from_bytes(h, "little"))
        v = ((rng.integers(0, 2, self.dim) * 2 - 1).astype(np.float32)
             / self._norm)
        if len(self._cache) > 200000:
            self._cache.clear()
        self._cache[key] = v
        return v

    def role(self, index: int) -> np.ndarray:
        return self.of(f"__role_{int(index)}")


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Circular convolution: the binding operation. Associative and commutative,
    and the reason a role and a filler can be merged into one vector and still
    be separated later."""
    out = np.fft.irfft(np.fft.rfft(a) * np.fft.rfft(b), n=a.shape[0])
    n = float(np.linalg.norm(out))
    return (out / n).astype(np.float32) if n else out.astype(np.float32)


def unbind(p: np.ndarray, role: np.ndarray) -> np.ndarray:
    """Approximate inverse of binding: recover the filler given the role."""
    out = np.fft.irfft(np.fft.rfft(p) * np.conj(np.fft.rfft(role)),
                       n=p.shape[0])
    n = float(np.linalg.norm(out))
    return (out / n).astype(np.float32) if n else out.astype(np.float32)


class OutcomeHead:
    """(state, action, goal) -> expected outcome, trained online.

    The predictor beside this learns state -> next_state: it says what will happen and
    nothing about whether it is worth doing. Multi-step search needs the second
    question answered -- would this action, in this state, toward this goal, pass --
    and that is a different input tuple, so it is a different head. Same error-driven
    rule, same online update, no batch step and nothing trained off-line.

    Deliberately small: a linear read over the combined context in the same concept
    space the binder uses, so a goal and an action are comparable vectors and the
    weights stay inspectable. A large head here would be capacity this loop has no
    evidence to fill yet, and the number that matters is whether its error trends
    down on attempted actions -- which a linear head shows honestly.
    """

    def __init__(self, dim: int = DIM, lr: float = 0.08):
        self.dim = int(dim)
        self.lr = float(lr)
        self.w = np.zeros(self.dim, dtype=np.float32)
        self.bias = 0.0
        self.updates = 0
        self.errors: list = []
        self.last_error = None
        self.predictions = 0

    def context(self, state, action, goal) -> np.ndarray:
        """The input tuple as one vector.

        Goal and action are weighted above state because the question is about the
        pair, not about where he happens to be standing -- and because an unweighted
        sum lets a large state swamp both.
        """
        s = np.asarray(state if state is not None
                       else np.zeros(self.dim), dtype=np.float32)
        a = np.asarray(action if action is not None
                       else np.zeros(self.dim), dtype=np.float32)
        g = np.asarray(goal if goal is not None
                       else np.zeros(self.dim), dtype=np.float32)
        c = 0.5 * s + 1.5 * a + 1.5 * g
        n = float(np.linalg.norm(c))
        return c / n if n else c

    def predict(self, state, action, goal) -> float:
        c = self.context(state, action, goal)
        z = float(np.dot(self.w, c) + self.bias)
        self.predictions += 1
        return float(1.0 / (1.0 + np.exp(-np.clip(z, -30.0, 30.0))))

    def update(self, state, action, goal, observed: float) -> float:
        """One online step. Returns the error made BEFORE it corrected anything.

        Predicted first, then corrected -- so the recorded error is a genuine
        prediction and not a fit, the same discipline the state head uses.
        """
        c = self.context(state, action, goal)
        pred = self.predict(state, action, goal)
        target = float(np.clip(observed, 0.0, 1.0))
        err = abs(target - pred)
        grad = (pred - target) * self.lr
        self.w = np.clip(self.w - grad * c, -4.0, 4.0)
        self.bias = float(np.clip(self.bias - grad, -4.0, 4.0))
        self.updates += 1
        self.last_error = round(err, 4)
        self.errors.append(err)
        if len(self.errors) > 500:
            self.errors = self.errors[-500:]
        return err

    def stats(self) -> dict:
        e = self.errors
        first = round(sum(e[:10]) / 10, 4) if len(e) >= 10 else None
        last = round(sum(e[-10:]) / 10, 4) if len(e) >= 10 else None
        return {"dim": self.dim, "updates": self.updates,
                "predictions": self.predictions,
                "nonzero_weights": int(np.count_nonzero(self.w)),
                "mean_error_first_10": first, "mean_error_last_10": last,
                "trending_down": (None if first is None or last is None
                                  else bool(last < first))}


class Predictor:
    """An asymmetric sequence memory over the concept space.

    Written as `P[next, now] += lr`, so `P @ now` is a prediction of what comes
    next. The symmetric cortex cannot do this and should not be asked to.
    """

    def __init__(self, dim: int = DIM, lr: float = 0.25, decay: float = 0.9995):
        self.dim = int(dim)
        self.lr = float(lr)
        self.decay = float(decay)
        self.P = np.zeros((self.dim, self.dim), dtype=np.float32)
        self.updates = 0
        self.errors: list = []
        self.last_error = None
        self._pending = None
        self._pending_t = 0.0

    def observe(self, concept: np.ndarray, surprise_weight: float = 1.0) -> dict:
        """See one percept. Predicts it from the previous one, records the error,
        then writes the transition. Returns the error made BEFORE seeing it, so
        the number is a genuine prediction and not a fit."""
        now = np.asarray(concept, dtype=np.float32)
        out = {"error": None, "predicted_cosine": None}
        if self._pending is not None:
            pred = self.P @ self._pending
            pn = float(np.linalg.norm(pred))
            if pn > 0:
                pred = pred / pn
                cos = float(np.dot(pred, now))
                out["predicted_cosine"] = round(cos, 4)
                out["error"] = round(max(0.0, 1.0 - cos), 4)
                self.last_error = out["error"]
                self.errors.append(out["error"])
                if len(self.errors) > 500:
                    self.errors = self.errors[-500:]
        # write, scaled by surprise: an unsurprising moment is already known
        w = self.lr * float(np.clip(surprise_weight, 0.05, 4.0))
        if self._pending is not None:
            self.P += w * np.outer(now, self._pending)
            np.clip(self.P, -4.0, 4.0, out=self.P)
            self.updates += 1
        self.P *= self.decay
        self._pending = now
        self._pending_t = time.time()
        return out

    def predict(self, concept: np.ndarray) -> np.ndarray:
        pred = self.P @ np.asarray(concept, dtype=np.float32)
        n = float(np.linalg.norm(pred))
        return pred / n if n else pred

    def mean_error(self, last: int = 50) -> float | None:
        e = self.errors[-int(last):]
        return round(float(np.mean(e)), 4) if e else None

    def stats(self) -> dict:
        nz = int(np.count_nonzero(np.abs(self.P) > 1e-4))
        return {"dim": self.dim, "updates": self.updates,
                "nonzero_weights": nz,
                "capacity_weights": self.dim * self.dim,
                "fill_fraction": round(nz / float(self.dim * self.dim), 6),
                "mean_error_last_50": self.mean_error(50),
                "mean_error_last_200": self.mean_error(200),
                "samples": len(self.errors),
                "first_50_mean": (round(float(np.mean(self.errors[:50])), 4)
                                  if len(self.errors) >= 50 else None),
                "last_50_mean": self.mean_error(50)}


class Binder:
    """Compositional memory: propositions as bound role-filler vectors.

    Stored in a modern-Hopfield-style associative memory, which retrieves with
    one softmax-weighted read and holds exponentially many patterns in the
    dimension -- the reason a thousand episodes cost 4 MB instead of a database.
    """

    def __init__(self, space: ConceptSpace, max_roles: int = 8,
                 capacity: int = MAX_PROPOSITIONS, beta: float = BETA):
        self.space = space
        self.max_roles = int(max_roles)
        self.capacity = int(capacity)
        # Growth buffers. X and C are appended through views onto these, so every
        # reader still sees X.shape[0] == the proposition count while the storage
        # doubles instead of being copied per row.
        self._xb = None
        self._cb = None
        # (concept, subject) -> procedure reference. AN EXACT KEY, DELIBERATELY NOT A
        # SIMILARITY. A sphere and a cylinder share the concept "surface area" and share
        # no formula, so asking for the wrong subject has to MISS -- and only a fixed key
        # can miss. This is also why facts are not stored as proposition rows: his grounded
        # acts all begin with "droso", and adding rows with a constant first token is
        # exactly what collapsed the role-recovery candidate pool to one and turned a real
        # metric into a zero.
        self.facts: dict = {}
        self.beta = float(beta)
        self.X = np.zeros((0, space.dim), dtype=np.float32)
        # Position-agnostic cue vectors, one per proposition: the normalised sum
        # of its words' concepts, with no role binding. Retrieval ranks against
        # these, because a question does not know which position its words
        # occupied in the memory it is looking for. Ranking by word overlap
        # instead tied dozens of lookalikes together and broke ties by recency,
        # which is how "droso sees what" came back as "droso sees the name".
        self.C = np.zeros((0, space.dim), dtype=np.float32)
        self.meta: list = []
        self.stored = 0
        # One row per distinct proposition. Without this the same few hundred
        # lines were stored a dozen times each: 20,000 rows holding 157 distinct
        # words, which crowds out the specific fact a question is after and turns
        # every aggregate into a popularity contest.
        self._seen: dict = {}
        self._idf_cache = None
        self._idf_at = -1
        # word -> rows, so overlap counting touches only the memories that could
        # possibly match. Ranking used to walk every stored proposition in Python
        # on every query, and the self-evaluation runs two hundred of them.
        self._postings: dict = {}
        # The same index keyed by stem, so an inflection he has not heard in that
        # exact form still finds the memory it belongs to.
        self._stem_postings: dict = {}
        self._cand_cache = None
        self._cand_at = -1
        # Exposure, the narrator and the chat all write here from different
        # threads. Without a lock the three arrays interleave and end up one row
        # apart, which surfaces later as a broadcast error in retrieval --
        # measured live as (1456,) against (1457,).
        self._lock = threading.Lock()

    def encode(self, tokens) -> np.ndarray:
        toks = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
        toks = toks[:self.max_roles]
        if not toks:
            return np.zeros(self.space.dim, dtype=np.float32)
        p = np.zeros(self.space.dim, dtype=np.float32)
        for i, t in enumerate(toks):
            p = p + bind(self.space.role(i), self.space.of(t))
        n = float(np.linalg.norm(p))
        return (p / n).astype(np.float32) if n else p

    def _idf(self) -> dict:
        """How distinctive each word is across everything he remembers.

        Without this, "who feeds droso" is cueed equally by `feeds` and by
        `droso` -- and `droso` is in half his memories, so the retrieval came
        back with whatever mentioned him most recently. A rare word is evidence;
        a common one is background. Cached, because recomputing document
        frequencies per query is the same O(n) walk this organ already suffers.
        """
        if self._idf_cache is not None and \
                abs(self.stored - self._idf_at) < 64:
            return self._idf_cache
        import math
        n = max(1, len(self.meta))
        df: dict = {}
        for m in self.meta:
            for w in {str(x).strip().lower() for x in m.get("tokens", [])}:
                df[w] = df.get(w, 0) + 1
        self._idf_cache = {w: math.log((n + 1.0) / (c + 0.5))
                           for w, c in df.items()}
        self._idf_at = self.stored
        return self._idf_cache

    def cue_of(self, tokens) -> np.ndarray:
        toks = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
        if not toks:
            return np.zeros(self.space.dim, dtype=np.float32)
        idf = self._idf()
        v = np.zeros(self.space.dim, dtype=np.float32)
        for t in toks:
            v = v + float(idf.get(t, 1.0)) * self.space.of(t)
        n = float(np.linalg.norm(v))
        return (v / n).astype(np.float32) if n else v

    def remember(self, tokens, who: str = "", when: float = 0.0) -> dict:
        p = self.encode(tokens)
        if not float(np.linalg.norm(p)):
            return {"stored": False, "reason": "empty"}
        cue = self.cue_of(tokens)
        key = tuple(str(t).strip().lower() for t in tokens)[:self.max_roles]
        row = {"tokens": list(key), "who": who,
               "when": float(when or time.time()), "count": 1}
        with self._lock:
            at = self._seen.get(key)
            if at is not None and at < len(self.meta):
                # Heard again: stronger, not duplicated.
                self.meta[at]["count"] = int(self.meta[at].get("count", 1)) + 1
                self.meta[at]["when"] = row["when"]
                self.stored += 1
                return {"stored": True, "repeat": True,
                        "count": self.meta[at]["count"],
                        "propositions": self.X.shape[0]}
            if self.X.shape[0] >= self.capacity:
                self._seen.pop(tuple(
                    str(t).strip().lower() for t in self.meta[0]["tokens"]), None)
                self.X = np.roll(self.X, -1, axis=0)
                self.C = np.roll(self.C, -1, axis=0)
                # roll returned new arrays; the old buffers no longer describe X
                self._xb = None
                self._cb = None
                self.meta.pop(0)
                self.X[-1] = p
                self.C[-1] = cue
                self.meta.append(row)
                self._seen = {k: (v - 1 if v > 0 else v)
                              for k, v in self._seen.items()}
                self._seen[key] = len(self.meta) - 1
                # Every row index shifted, so the index is worthless; rebuild it.
                self._rebuild_postings()
            else:
                # Appended through a view onto a doubling buffer, not by vstack. The
                # vstack copied both matrices for every memory -- 130 MB per
                # proposition once X and C reached 15,805 rows, 15,805 times -- and
                # Windows keeps the freed arenas in the working set, so a 420 MB
                # animal showed a 6.9 GB peak and its load had to grind through the
                # same churn. This is amortised O(1) with a copy at each doubling.
                n = len(self.meta)
                if self._xb is None or n + 1 > self._xb.shape[0]:
                    rows = 1024
                    while rows < 2 * max(1, n + 1):
                        rows *= 2
                    xb = np.zeros((rows, self.space.dim), dtype=np.float32)
                    cb = np.zeros((rows, self.space.dim), dtype=np.float32)
                    if n:
                        xb[:n] = self.X[:n]
                        cb[:n] = self.C[:n]
                    self._xb, self._cb = xb, cb
                self._xb[n] = p
                self._cb[n] = cue
                self.X = self._xb[:n + 1]
                self.C = self._cb[:n + 1]
                self.meta.append(row)
                self._seen[key] = len(self.meta) - 1
            for w in set(key):
                self._postings.setdefault(w, []).append(len(self.meta) - 1)
                self._stem_postings.setdefault(stem(w), []).append(
                    len(self.meta) - 1)
            self._cand_cache = None
            self.stored += 1
        return {"stored": True, "propositions": self.X.shape[0]}

    def recall(self, cue_tokens, k: int = 1) -> list:
        """Which remembered propositions contain the cue words.

        Retrieval is lexical on purpose. Scoring it by similarity between bound
        vectors fails silently and completely: the cue word sits at a DIFFERENT
        position in each proposition, so `role0 * verb` never resembles
        `role1 * verb`, and the ranking came back as noise (measured: 22% against
        20% chance, with the shuffled control scoring higher). The compositionality
        this organ claims is in the unbinding, not in the lookup.
        """
        toks = {str(t).strip().lower() for t in (cue_tokens or []) if str(t).strip()}
        if not self.X.shape[0] or not toks:
            return []
        with self._lock:
            C, X, meta = self.C, self.X, list(self.meta)
        if C.shape[0] != len(meta):
            return []
        sims = C @ self.cue_of(sorted(toks))
        # Overlap by inverted index, weighted by how distinctive each shared word
        # is. Counting shared words treats `droso` and `sees` as equal evidence,
        # so a question about seeing retrieved whichever memory mentioned him most
        # often. Same principle the cue already uses: a rare word is evidence, a
        # common one is background.
        # Count only DISTINCTIVE shared words. "where is the light" shares three
        # words with "is the light open" and one with "light is here", so raw
        # overlap picked the wrong memory on the strength of `the` and `is` -- and
        # no later term could overrule an integer gap. A word is distinctive if it
        # appears in fewer than a quarter of what he remembers, which is a fact
        # about his own memory rather than a stopword list written by hand. The
        # first attempt used the median IDF and filtered `light` out along with
        # `the`, because most of his vocabulary is rare.
        n_mem = max(1, len(meta))
        rows_for = {t: self.stem_rows(t) for t in toks}
        distinctive = [t for t in toks if len(rows_for[t]) * 4 <= n_mem]
        use = distinctive or list(toks)
        idf = self._idf()
        overlap = np.zeros(len(meta), dtype=np.float32)
        weighted = np.zeros(len(meta), dtype=np.float32)
        for t in use:
            rows = rows_for[t]
            if not rows:
                continue
            w = float(idf.get(t, 0.0))
            if w <= 0.0:
                # He has not heard this exact form. That is not the same as it
                # being rare, and treating an unknown inflection as maximally
                # informative is what let one conjugation decide a retrieval.
                w = float(np.log(1.0 + n_mem / float(max(1, len(rows)))))
            for i in rows:
                if i < overlap.shape[0]:
                    overlap[i] += 1.0
                    weighted[i] += w
        # Semantic similarity decides; shared words break ties between memories
        # that mean nearly the same thing.
        #
        # And how often he has heard it decides between those. A fact read fifty
        # times is a better answer than a sentence that passed through once, and
        # this was the one signal that could separate what he KNOWS from what he has
        # merely seen -- with ten thousand propositions of which 99% are prose read
        # a single time, similarity alone ranks a passing clause beside something
        # his whole corpus repeated. It was computed, stored, reported in the result
        # and never used.
        counts = np.array([float(m.get("count", 1) or 1) for m in meta],
                          dtype=np.float32)
        if counts.shape[0] != sims.shape[0]:
            counts = np.ones(sims.shape[0], dtype=np.float32)
        score = sims + 0.05 * overlap + 0.05 * np.log1p(counts)
        order = np.argsort(-score)[:int(k)]
        return [{"tokens": meta[int(i)]["tokens"],
                 "who": meta[int(i)].get("who", ""),
                 "count": int(meta[int(i)].get("count", 1)),
                 "overlap": int(overlap[int(i)]),
                 "overlap_idf": round(float(weighted[int(i)]), 4),
                 "distinctive_cue": list(use),
                 "similarity": round(float(sims[int(i)]), 4),
                 "proposition": X[int(i)]} for i in order]

    def role_of(self, proposition, role: int, candidates) -> dict:
        """Unbind one role from ONE proposition the caller already chose.

        `query_role` retrieves and then unbinds, which is wrong when the caller
        has already filtered what may be retrieved: asked "who feeds droso" it
        fetched the question itself back out of memory and answered "who". This
        takes the chosen memory as given and only does the algebra.
        """
        rec = unbind(np.asarray(proposition, dtype=np.float32),
                     self.space.role(int(role)))
        scored = sorted(((float(np.dot(rec, self.space.of(c))), c)
                         for c in candidates), reverse=True)
        if not scored:
            return {"answer": None, "score": None, "runner_up": None}
        return {"answer": scored[0][1], "score": round(scored[0][0], 4),
                "runner_up": ({"token": scored[1][1],
                               "score": round(scored[1][0], 4)}
                              if len(scored) > 1 else None),
                "role": int(role)}

    def _rebuild_postings(self) -> None:
        self._postings = {}
        self._stem_postings = {}
        for i, m in enumerate(self.meta):
            for w in {str(t).strip().lower() for t in m.get("tokens", [])}:
                self._postings.setdefault(w, []).append(i)
                self._stem_postings.setdefault(stem(w), []).append(i)
        self._cand_cache = None

    def stem_rows(self, word) -> list:
        """The rows whose tokens share a stem with this word.

        Indexed on raw tokens, an unfamiliar inflection had a document frequency of
        zero, which the distinctiveness rule read as maximally distinctive. It was
        then required of every candidate memory and could never be satisfied, so
        "who is holding the light" was refused against a memory that says "parent
        holds light" -- not because he did not know, but because the asker
        conjugated a verb.
        """
        return self._stem_postings.get(stem(word), [])

    def idf(self) -> dict:
        """Public view of how distinctive each remembered word is."""
        return self._idf()

    def candidates(self) -> list:
        """Every word that appears in any remembered proposition, cached.

        Recomputing this per query walks the whole memory in Python, which is
        what made a single question cost more than a neural tick.
        """
        if self._cand_cache is not None and self._cand_at == self.stored:
            return self._cand_cache
        self._cand_cache = sorted({str(t).strip().lower()
                                   for m in self.meta for t in m.get("tokens", [])})
        self._cand_at = self.stored
        return self._cand_cache

    def self_test(self) -> dict:
        """Does the algebra actually invert? Bind a filler to a role, unbind it,
        and measure how much of the filler survives. If this is not near 1.0,
        nothing downstream of it means anything."""
        ok = []
        for i in range(6):
            role = self.space.role(i)
            fill = self.space.of(f"__selftest_{i}")
            rec = unbind(bind(role, fill), role)
            ok.append(round(float(np.dot(rec, fill)), 4))
        return {"bind_unbind_fidelity": ok,
                "mean": round(float(np.mean(ok)), 4)}

    def query_role(self, cue_tokens, role: int, candidates,
                   k: int = 12) -> dict:
        """Ask a question of memory and get a filler back.

        Every proposition the cue matches is retrieved, each is unbound at the
        requested role, and the recovered vectors are summed weighted by how much
        of the cue they matched. Aggregation matters: cueing on a single common
        verb matches dozens of memories with different doers, and picking one of
        them at random scored at chance (4% against 8%) while the same memory
        queried with the rest of the sentence as context recovers the doer.

        This is the test that separates composition from association: association
        can say that parent and feed co-occur, only binding can say which one was
        the doer.
        """
        hits = self.recall(cue_tokens, k=int(k))
        if not hits:
            return {"answer": None, "reason": "nothing remembered"}
        rv = self.space.role(int(role))
        acc = np.zeros(self.space.dim, dtype=np.float32)
        for h in hits:
            # Square the overlap weight. Linear weighting let 23 partial matches
            # outvote the one proposition that actually contained the whole cue,
            # and asking with more context scored WORSE than asking with a single
            # word (15.5% against 24%) -- dilution, not memory.
            w = float(h.get("overlap", 1)) ** 2
            acc = acc + w * unbind(h["proposition"], rv)
        n = float(np.linalg.norm(acc))
        if n:
            acc = acc / n
        scored = []
        for c in candidates:
            scored.append((float(np.dot(acc, self.space.of(c))), c))
        scored.sort(reverse=True)
        return {"answer": scored[0][1] if scored else None,
                "score": round(scored[0][0], 4) if scored else None,
                "runner_up": ({"token": scored[1][1],
                               "score": round(scored[1][0], 4)}
                              if len(scored) > 1 else None),
                "memories_matched": len(hits),
                "best_match": hits[0]["tokens"],
                "role": int(role)}

    def stats(self) -> dict:
        return {"propositions": int(self.X.shape[0]),
                "capacity": self.capacity, "stored_total": self.stored,
                "roles": self.max_roles, "dim": self.space.dim,
                "memory_mb": round(self.X.nbytes / 2 ** 20, 2)}


    # ------------------------------------------------------------------ facts
    def bind_fact(self, concept: str, subject: str, proc_ref: str,
                  shape: str = "unknown") -> bool:
        """File a verified procedure under concept+subject. True if newly bound.

        Both halves are required. A fact with only one of them is not fileable, because
        a key with a hole in it is a key that will match the wrong thing.
        """
        c, s = str(concept or "").strip(), str(subject or "").strip()
        sh = str(shape or "unknown").strip() or "unknown"
        if not c or not s or not str(proc_ref or "").strip():
            return False
        key = (c, s, sh)
        if key in self.facts:
            return False
        self.facts[key] = str(proc_ref)
        return True

    def recall_fact(self, concept: str, subject: str, shape: str = "unknown"):
        """The procedure filed under this exact key, or None. No fuzzy fallback.

        The absence of a similarity fallback is the whole design. If this returned the
        nearest fact instead of the right one, the oracle would be asked for nothing, a
        near-miss formula would be executed, and the assertions would reject it -- which
        looks like a failed attempt rather than the wrong question, and sends the search
        off to generate candidates for a fact it was never given.
        """
        c, s = str(concept or "").strip(), str(subject or "").strip()
        sh = str(shape or "unknown").strip() or "unknown"
        if not c or not s:
            return None
        hit = self.facts.get((c, s, sh))
        if hit:
            return hit
        # An UNKNOWN shape on both sides still means "we could not read it", so it may fall
        # back to the two-part key. A KNOWN shape must not: a string answer is not a count,
        # and that is the whole reason the third component exists.
        if sh == "unknown":
            for (cc, ss, ssh), ref in self.facts.items():
                if cc == c and ss == s and ssh == "unknown":
                    return ref
        return None

    def fact_stats(self) -> dict:
        by_concept: dict = {}
        for (c, _s, _sh) in self.facts:
            by_concept[c] = by_concept.get(c, 0) + 1
        return {"facts": len(self.facts),
                "concepts": len(by_concept),
                "subjects_per_concept": by_concept}


class HigherCortex:
    """The two organs together, with the concept space they share."""

    def __init__(self, dim: int = DIM, seed: int = 0):
        self.space = ConceptSpace(dim=dim, seed=seed)
        self.predictor = Predictor(dim=dim)
        self.binder = Binder(self.space)
        # The goal-conditioned head. Track E ranks candidates by whether they are
        # expected to pass toward a held goal; the state predictor beside it learns
        # what comes next and cannot answer that at all.
        self.outcome = OutcomeHead(dim)
        self.last_error = None
        self.MIN_HEAR_INTERVAL_S = 0.05
        self._last_hear = 0.0
        self.skipped = 0

    def hear(self, tokens, who: str = "", surprise_weight: float = 1.0,
             chunk: bool = True) -> dict:
        """One utterance arrives. Predict it, then bind and store it.

        Prediction uses the running concept of what came before, so error is
        measured on the transition into this utterance, not within it.

        Throttled in REAL time, not world time. At 35x world speed the book
        exposure delivers about 70 lines per second, and each one costs a rank-1
        update over a 1024x1024 matrix -- enough to cut the world tick rate to a
        third. Sampling the stream instead of exhausting it keeps the cost bounded
        and is honest about what it does: the count of skipped utterances is
        reported, not hidden.
        """
        toks = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
        if not toks:
            return {"error": None}
        now = time.time()
        if now - self._last_hear < self.MIN_HEAR_INTERVAL_S:
            self.skipped += 1
            return {"error": None, "skipped": True}
        self._last_hear = now
        phrase = self.space.of(" ".join(toks[:6]))
        step = self.predictor.observe(phrase, surprise_weight=surprise_weight)
        self.last_error = step.get("error")
        mr = int(self.binder.max_roles)
        if len(toks) <= mr or not chunk:
            self.binder.remember(toks, who=who)
        else:
            # A sentence longer than the role count used to lose its tail: the
            # binder kept the first eight words and the rest was never bound at
            # all. His diet is now mostly prose at eleven words a line, so most of
            # what he read stopped existing at the seventh word. Overlapping
            # windows keep the whole sentence in play, and the overlap is what
            # makes them share structure rather than sit side by side.
            step_w = max(2, mr // 2)
            for i in range(0, max(1, len(toks) - mr + 1), step_w):
                self.binder.remember(toks[i:i + mr], who=who)
        return {"error": step.get("error"),
                "predicted_cosine": step.get("predicted_cosine"),
                "propositions": self.binder.X.shape[0]}

    def speak_plan(self, tokens) -> dict:
        """What he intends to say, as a bound proposition -- the structure the
        sequence organ then puts into order."""
        return {"proposition_tokens": list(tokens)[:self.binder.max_roles],
                "roles": min(len(tokens), self.binder.max_roles)}

    def ask(self, cue, role: int = 0, candidates=None, k: int = 1) -> dict:
        """A question put to memory, answered by unbinding.

        `candidates` defaults to every word that appears in any remembered
        proposition, so the answer is chosen from what he has actually heard
        rather than from a list supplied by the questioner.
        """
        cands = list(candidates) if candidates else sorted(
            {str(t).lower() for m in self.binder.meta for t in m["tokens"]})
        if not cands:
            return {"answer": None, "reason": "nothing remembered"}
        return self.binder.query_role(cue, int(role), cands, k=k)

    def save(self, path) -> dict:
        try:
            import json
            import os
            from pathlib import Path as _P
            p = _P(str(path))
            p.parent.mkdir(exist_ok=True, parents=True)
            # Written to a temporary and renamed, never written in place. This
            # file is 35 MB and takes a moment to compress, and the house is
            # stopped with a hard kill -- which caught it mid-save and left a
            # 477 KB zip with a valid header and no contents. That reads as
            # BadZipFile, and the individual came up with 597 propositions instead
            # of 7,468 and no idea why. A rename either happens or it does not, so
            # the worst case now is losing the last few minutes rather than the
            # whole memory.
            tmp = p.with_name(p.name + ".tmp.npz")
            np.savez_compressed(
                str(tmp), P=self.predictor.P, X=self.binder.X, C=self.binder.C,
                counts=np.array([self.predictor.updates,
                                 self.binder.stored]))
            os.replace(str(tmp), str(p))
            # Meta goes in a JSON sidecar, not inside the npz. Storing it as a
            # numpy bytes scalar was fragile: a failed decode left X restored with
            # an empty meta, which reads as "4,096 propositions, nothing
            # remembered" -- a memory full of rows nobody can name.
            side = p.with_suffix(".meta.json")
            tmp_side = side.with_name(side.name + ".tmp")
            tmp_side.write_text(json.dumps(self.binder.meta), encoding="utf-8")
            os.replace(str(tmp_side), str(side))
            # The fact index rides in its own sidecar: it is tiny, it is a list of
            # triples rather than a dict with tuple keys so the file stays readable, and
            # losing it costs a retrieval path rather than his memory.
            fside = p.with_suffix(".facts.json")
            ftmp = fside.with_name(fside.name + ".tmp")
            ftmp.write_text(json.dumps([[c, s, r, sh] for (c, s, sh), r
                                        in self.binder.facts.items()]),
                            encoding="utf-8")
            os.replace(str(ftmp), str(fside))
            errs = np.array(self.predictor.errors[-2000:], dtype=np.float32)
            if errs.size:
                etmp = _P(str(p) + ".err.tmp.npy")
                with open(str(etmp), "wb") as fh:
                    np.save(fh, errs, allow_pickle=False)
                os.replace(str(etmp), str(p) + ".err.npy")
            return {"saved": True, "path": str(p),
                    "propositions": int(self.binder.X.shape[0])}
        except Exception as e:
            return {"saved": False, "reason": f"{type(e).__name__}: {e}"[:160]}

    def load(self, path) -> dict:
        try:
            import json
            from pathlib import Path as _P
            p = _P(str(path))
            if not p.exists():
                return {"loaded": False, "reason": "no cortex file yet"}
            z = np.load(str(p))
            P = z["P"]
            if P.shape != (self.predictor.dim, self.predictor.dim):
                return {"loaded": False,
                        "reason": f"predictor shape {P.shape} is not ours"}
            self.predictor.P = np.asarray(P, dtype=np.float32)
            X = z["X"]
            C = z["C"] if "C" in z.files else None
            side = p.with_suffix(".meta.json")
            meta = []
            if side.exists():
                meta = json.loads(side.read_text(encoding="utf-8"))
            elif "meta" in z.files:
                meta = json.loads(bytes(z["meta"]).decode("utf-8"))
            fside = p.with_suffix(".facts.json")
            if fside.exists():
                try:
                    for row in json.loads(fside.read_text(encoding="utf-8")):
                        if isinstance(row, (list, tuple)) and len(row) >= 3:
                            sh = str(row[3]) if len(row) > 3 else "unknown"
                            self.binder.facts[(str(row[0]), str(row[1]), sh)] = str(row[2])
                except Exception:
                    pass
            if X.size and X.shape[1] == self.space.dim:
                if C is None or C.shape != X.shape:
                    # The cue vectors are what retrieval ranks against; without
                    # them the propositions are unreachable, so refuse the whole
                    # restore rather than keep rows nothing can find.
                    return {"loaded": False,
                            "reason": "propositions saved without matching cue "
                                      f"vectors (X {X.shape}, C "
                                      f"{None if C is None else C.shape})"}
                if len(meta) != X.shape[0]:
                    # Keep what can be named instead of throwing everything away.
                    # An unnamed row answers no query, so dropping it costs one
                    # memory; refusing the whole file cost all of them, which is
                    # what happened the first time this raced.
                    keep = min(len(meta), X.shape[0])
                    truncated = X.shape[0] - keep
                    X, C, meta = X[:keep], C[:keep], meta[:keep]
                else:
                    truncated = 0
                self.binder.X = np.asarray(X, dtype=np.float32)
                self.binder.C = np.asarray(C, dtype=np.float32)
                self.binder.meta = meta
                self.binder._rebuild_postings()
                # Rebuild the deduplication index, or a reloaded memory would
                # store a second copy of everything it already holds.
                self.binder._seen = {}
                for i, m in enumerate(self.binder.meta):
                    self.binder._seen[tuple(
                        str(t).strip().lower() for t in m.get("tokens", []))] = i
            c = z["counts"]
            self.predictor.updates = int(c[0])
            self.binder.stored = int(c[1])
            errf = _P(str(path) + ".err.npy")
            if errf.exists():
                self.predictor.errors = [float(x) for x in np.load(str(errf))]
            return {"loaded": True,
                    "propositions": int(self.binder.X.shape[0]),
                    "predictor_updates": self.predictor.updates}
        except Exception as e:
            return {"loaded": False, "reason": f"{type(e).__name__}: {e}"[:160]}

    def _score_props(self, props: list) -> dict:
        if not props:
            return {"samples": 0}
        pool = sorted({str(t[0]).lower() for t in props})
        ok_ctx = ok_word = 0
        for t in props:
            first = str(t[0]).lower()
            r = self.binder.query_role([str(x).lower() for x in t[1:]], 0, pool)
            if r.get("answer") == first:
                ok_ctx += 1
            r2 = self.binder.query_role([str(t[1]).lower()], 0, pool)
            if r2.get("answer") == first:
                ok_word += 1
        n = len(props)
        chance = round(1.0 / max(1, len(pool)), 4)
        return {"samples": n,
                "accuracy_given_rest_of_sentence": round(ok_ctx / float(n), 4),
                "accuracy_given_one_word": round(ok_word / float(n), 4),
                "chance": chance,
                "candidate_agents": len(pool),
                # A POOL OF ONE IS NOT A MEASUREMENT. Every sampled proposition started
                # with the same word, so accuracy is 1.0 by construction and skill over
                # chance is 0.0 by construction -- and the composite read that as a real
                # zero on a goal it is supposed to be scoring. It is not a failure of
                # binding, it is the absence of a test, and the two must not look alike.
                # His grounded acts all begin with "droso", so as grounded memory grew
                # this pool collapsed to one and the metric quietly stopped measuring.
                "degenerate": len(pool) < 2}

    def self_evaluate(self, limit: int = 200) -> dict:
        """Score role recovery on his OWN memory, split by where it came from.

        The split is the point. 9,567 of his 9,620 propositions were read out of
        books, where the first word of a sentence is "the" or "so" and role 0 is
        not an agent at all. Pooled together, the number moved with his diet rather
        than with his binding: it read 0.64 on a memory of grounded caregiver
        sentences and 0.03 after a week of prose, with the binder unchanged. Only
        the grounded sample measures what this metric claims to.

        For each, ask role 0 cued by the rest of the sentence and see whether word
        0 comes back, against the chance rate of the actual candidate pool.
        """
        meta = self.binder.meta

        def usable(m):
            return len({str(t).lower() for t in m.get("tokens", [])}) >= 2

        grounded = [m["tokens"] for m in meta
                    if usable(m) and str(m.get("who") or "") not in ("book", "")]
        read = [m["tokens"] for m in meta
                if usable(m) and str(m.get("who") or "") == "book"]
        g = self._score_props(grounded[-int(limit):])
        b = self._score_props(read[-int(limit):])

        def usable(s):
            return int(s.get("samples") or 0) >= 8 and not s.get("degenerate")

        # The headline number is the grounded one where there is enough of it to mean
        # anything, because that is the only sample where role 0 is a role -- but "enough"
        # now has to include "has more than one possible answer", or a collapsed pool wins
        # the headline by being empty of information.
        head = g if usable(g) else (b if usable(b) else
                                    (g if int(g.get("samples") or 0) >= 8 else b))
        out = dict(head)
        out["measurement_degenerate"] = bool(head.get("degenerate"))
        out["grounded"] = g
        out["read_from_books"] = b
        out["propositions_held"] = int(self.binder.X.shape[0])
        out["grounded_share"] = round(len(grounded) / max(1, len(meta)), 4)
        out["headline_source"] = "grounded" if head is g else "books"
        return out

    def stats(self) -> dict:
        return {"predictor": self.predictor.stats(),
                "binder": self.binder.stats(),
                "utterances_skipped_by_throttle": self.skipped}
