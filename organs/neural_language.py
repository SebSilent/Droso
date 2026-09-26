
from __future__ import annotations

import base64
import hashlib
import re
import threading
import time
from collections import deque
from pathlib import Path

from .stemming import stem
from .goal import GoalOrgan

import numpy as np

N_SAN = 8192
INTRO_CELLS = 128
INTRO_BASE = N_SAN - INTRO_CELLS
DAY_WORLD_S = 240.0
SAN_FOOTPRINT = 12
HEBB_LR = 0.10
SAN_DECAY = 0.999
SAN_DECAY_PER_S = 0.995
SAN_SAVE_MIN_S = 600

class NeuralLanguage:
    """Words as KC activation patterns in the carved BANC graph."""

    def __init__(self, engine, tokenizer, *, state_path: Path | None = None,
                 min_vocabulary: int = 50, training_cycles: int = 5,
                 words_per_cycle: int = 20, persist: bool = True):
        self.engine = engine
        self.tokenizer = tokenizer
        self.word_patterns: dict[str, dict] = {}
        self.state_path = Path(state_path) if state_path else None
        self.min_vocabulary = int(min_vocabulary)
        self.training_cycles = int(training_cycles)
        self.words_per_cycle = int(words_per_cycle)
        self.persist = bool(persist)
        self.lessons_received = 0
        self.exchanges_observed = 0
        self.last_error = None
        self.n_san = N_SAN
        self.san_w = np.zeros((N_SAN, N_SAN), dtype=np.float32)
        self.san_act = np.zeros(N_SAN, dtype=np.float32)
        self._san_last_save = 0.0
        self.speech_stream: deque = deque(maxlen=200)
        self.event_stream: deque = deque(maxlen=600)
        # Thoughts get their own stream. They used to share event_stream, and at
        # 17 ticks a second 600 slots is about 35 seconds of history -- so a
        # parent's phrase, a book line or anything else he actually HEARD was
        # evicted before the dashboard could show it. That looked like the input
        # was bypassing the air entirely; it never was.
        self.thought_stream: deque = deque(maxlen=200)
        self.recent_words: deque = deque(maxlen=24)
        self.reply_threshold = 0.55
        self.ticks = 0
        self._last_thought_at = 0.0
        self.world_clock = 0.0
        self._last_thought_world = 0.0
        self.spontaneous_thought_every = 6.0
        self.babble_p = 0.35
        self.social_drive = 0.6
        self.reply_drive_min = 0.30
        self.mood_wander = 0.04
        self.reward_social = 0.40
        self.reward_babble = 0.08
        self.reward_teach = 0.50
        self.reward_exposure = 0.05
        self.books_dir = None
        self.exposure_enabled = False
        self.exposure_speed_s = 2.0
        self.exposure_intensity = 12
        self.assimilation_threshold = 12
        self.exposure_counts = {}
        self.bigram_counts: dict = {}
        self.phrase_threshold = 6
        self.attention = 0.5
        self.curriculum_done = False
        self._cur_pos = 0
        self._events = deque(maxlen=40)
        self._spoken_at: dict = {}
        self._phrase_lived: dict = {}
        self._last_phase = None
        self._was_tired = False
        self._nar_last_save = 0.0
        self._last_decay = time.time()
        self.persons: dict = {}
        self.max_sentence_words = 6
        # The speech prosthesis is OFF unless the operator turns it on: it spends
        # API calls, and an unlabelled render would pass a device's grammar off
        # as his.
        self.voice_prosthesis = False
        self.reward_adverse = 0.45
        self._adverse_until = 0.0
        self._adverse_severity = 0.0
        self._last_adverse_at = 0.0
        self._last_exhausted_at = 0.0
        # The teacher's leash. Every lesson is bought with the operator's money,
        # so the limits are hard, counted, and persisted: a restart must not
        # reset the day's spending, and a key that keeps failing must not be
        # retried every two minutes forever.
        self.teacher_stats: dict = {}
        self.teacher_last_refusal = None
        self._spoken_times: dict = {}
        # Which role each question word asks about, learned from question/answer
        # pairs he has been read. Votes rather than a single value, because the
        # same interrogative can ask about different positions in different
        # sentences and the common case should win.
        self.question_roles: dict = {}
        self.interrogatives: set = set()
        self.qa_pairs_seen = 0
        self.answer_types: dict = {}
        self.statement_words: dict = {}
        # How often a word has OPENED a question. This is the signal that decides
        # whether a word is interrogative, and it is positional rather than
        # statistical because English question words spend most of their time not
        # opening questions: "what the loop does", "where the state lives".
        self.question_initial: dict = {}
        # What went wrong at boot, kept separately from what is wrong now. A load
        # refusal used to sit in last_error forever, so a healthy animal that had
        # rebuilt his chain from reading still reported a corrupt file from three
        # restarts ago -- the same dishonesty as a silent refusal, only louder.
        self.load_error = None
        # Phase 5a: somewhere to hold a goal while he works on it.
        self.goal = GoalOrgan(self)
        # How much his unprompted speech is allowed to vary. Zero is the old
        # behaviour: the same seed produced the same sentence forever. It is kept
        # low because the sampling set is already restricted to successors within
        # SUCCESSOR_MARGIN of the best -- the variety comes from breaking genuine
        # ties, not from raiding the tail.
        self.speech_temperature = 0.35
        self._grounds: dict = {}
        # The grown organ that gives his speech an order. Not part of BANC: the
        # fly never needed a slot for "second word", so there is no measured
        # structure to borrow and we build the thing beside it.
        from organs.sequence_organ import SequenceOrgan
        self.sequence = SequenceOrgan()
        # Prediction and binding. Grown beside the carve, sharing nothing with it
        # but the words: the predictor gives him anticipation and therefore
        # surprise, the binder gives him propositions he can be asked about.
        from organs.higher_cortex import HigherCortex
        self.cortex = HigherCortex()
        self.lessons = [{"s": l[0], "tag": l[1],
                         "care": (l[2] if len(l) > 2 else None)}
                        for l in self.CURRICULUM]
        self.curriculum_attention = 0.95
        self.curriculum_reward = 0.35
        self.need_social = 0.3
        self.need_novelty = 0.2
        self.energy = 0.85
        self._tag_cells = np.zeros(32, dtype=np.float32)
        self.reward_feed = 0.30
        self.reward_pet = 0.20
        self.reward_praise = 0.35
        self.reward_self_speak = 0.20
        self._oracle = None
        self._lock = threading.RLock()
        self._book_idx = 0
        self._book_words = []
        self._book_pos = 0
        self._book_lines = []
        self._book_is_q = []
        self._book_line_pos = 0
        self._expose_real_last = 0.0
        self._expose_accum = 0.0
        self.load_state()

    def _note_spoken(self, words) -> None:
        """Record words that actually left the mouth (dashboard telemetry)."""
        for w in words:
            if w:
                self.recent_words.append(str(w))
                self._spoken_times[str(w)] = float(self.world_clock)
        # What he said is something he did. One word is not worth a proposition --
        # that would fill his memory with "droso says the" -- but a sentence is an
        # act with a doer attached, and it is the only autobiographical record he
        # will ever have of his own speech. Without it he can be asked what anyone
        # else said and never what he said, which is a strange shape for a self.
        ws = [str(w).strip().lower() for w in (words or []) if str(w).strip()]
        if len(ws) >= 2:
            now = time.time()
            if now - float(getattr(self, "_last_speech_act", 0.0)) >= 2.0:
                self._last_speech_act = now
                try:
                    self.experience("droso", "says", " ".join(ws))
                except Exception:
                    pass

    REFRACTORY_WORLD_S = 90.0

    def _refractory(self, w) -> float:
        """Adaptation: a word just said is harder to say again for a while.

        Not randomness and not a filter. It is the same thing a real neuron does
        after firing, and without it the highest-resonance word wins every single
        tick over an unchanged state -- which from outside looks like "wept wept
        wept", the honest output of a deterministic argmax with nothing to break
        the tie.
        """
        last = self._spoken_times.get(str(w))
        if last is None:
            return 1.0
        age = float(self.world_clock) - float(last)
        if age >= self.REFRACTORY_WORLD_S:
            return 1.0
        return 0.12 + 0.88 * (max(0.0, age) / self.REFRACTORY_WORLD_S)

    def _footprint(self, token: str) -> np.ndarray:
        """The born projection of one token onto the SAN bank."""
        v = np.zeros(self.n_san, dtype=np.float32)
        h = hashlib.blake2b(f"san|{token}".encode("utf-8"),
                            digest_size=8).digest()
        idx = int.from_bytes(h, "little")
        for j in range(SAN_FOOTPRINT):
            h = hashlib.blake2b(f"san|{token}|{j}".encode("utf-8"),
                                digest_size=8).digest()
            v[(idx + int.from_bytes(h, "little")) % INTRO_BASE] = 1.0
        return v

    def _interoception(self) -> np.ndarray:
        """The body, as neural state: mood, world time-of-day, needs and
        care tags, each encoded as position inside its own band of the
        reserved interoceptive cells. This vector rides along with every
        experience, so words wire to the STATES they were lived in."""
        v = np.zeros(self.n_san, dtype=np.float32)
        b = INTRO_BASE
        v[b + min(31, int(self.social_drive * 32))] = 1.0
        frac = (self.world_clock % DAY_WORLD_S) / DAY_WORLD_S
        v[b + 32 + min(31, int(frac * 32))] = 1.0
        for i, lvl in enumerate((self.need_social, self.need_novelty,
                                 1.0 - self.energy)):
            v[b + 64 + i * 10 + min(9, int(lvl * 10))] = 1.0
        v[b + 96:] += self._tag_cells
        return 0.6 * v[:self.n_san]

    def live(self, text: str, *, learn: bool = True,
             attention: float | None = None, speaker: str | None = None,
             announce: bool = True, readout: bool = True) -> dict:
        """Experience language through the semantic cortex.

        Every token lights its SAN footprint; learned associations spread
        activation through san_w; then -- when this is LEARNING time --
        Hebb's rule wires what fired together. This is where meaning GROWS:
        meet a word among greetings often enough and it becomes a greeting
        word, neuronally, with nobody storing a definition anywhere.
        """
        toks = [w for w in str(text or "").lower().split() if w]
        surprise = 1.0
        if speaker and toks:
            # Predict, then write. The error is measured BEFORE this utterance is
            # stored, so it is a real prediction and not a fit -- and surprise is
            # what scales how hard the moment gets written, because an unsurprising
            # sentence is one he already knows.
            try:
                # A question is bound whole or not at all. Windowing one produces
                # fragments with no interrogative in them, and the rule that keeps
                # questions out of his answers only recognises a question by its
                # question word -- so "what is the capital of a country he has
                # never heard of" came back as the answer "of a country he has
                # never heard of". He was answering with the asking.
                is_q = str(text or "").strip().endswith("?") or \
                    any(self.is_interrogative(t) for t in toks)
                res = self.cortex.hear(toks, who=str(speaker), chunk=not is_q)
                if res.get("error") is not None:
                    surprise = 1.0 + 2.0 * float(res["error"])
            except Exception:
                surprise = 1.0
        if speaker and len(toks) >= 2:
            # Order is learned from everything someone says to him, attended or
            # not: a book drifting past still has a word order in it, and the
            # write costs 36 numbers. Attention scales how hard it is written.
            # Gated on `speaker` so his own rehearsal never trains the chain --
            # a voice that learns from itself collapses into whatever it said
            # first.
            self.sequence.learn_sequence(toks, reward=float(self.attention))
        act = np.zeros(self.n_san, dtype=np.float32)
        known = []
        for w in toks:
            act += self._footprint(w)
            if w in self.word_patterns:
                known.append(w)
        for a, b in zip(toks, toks[1:]):
            act += 0.7 * self._footprint(a + " " + b)
        act += self._interoception()
        for gkey, ( _perc, guntil) in list(self._grounds.items()):
            if guntil >= time.time():
                # Whatever is present in his world rides along with the words, so
                # "the file is open" said while a file is open wires to the file.
                act += 0.7 * self._footprint(gkey)
        sal = 1.0
        if speaker:
            # WHO said it is part of the percept. The speaker's own cells fire
            # alongside the words, so the cortex wires person to phrase, and a
            # parent's words are wired harder than a page of a book -- which is
            # the whole point of having parents.
            rec = self.note_person(speaker, kind=self._person_kind(speaker),
                                   heard=text)
            sal = self.salience(rec["name"])
            # Salience buys ATTENTION and reward, not loudness. At 1.7x amplitude
            # a parent's own cells outshone the words being said and become the
            # strongest associate of everything he hears -- which is the opposite
            # of learning the words.
            act += (0.6 + 0.1 * min(2.0, sal - 1.0)) * self._footprint(
                "person:" + rec["name"])
            if announce:
                if rec.get("kind") == "human":
                    self.note_event("user", f"{rec['name']} said: {str(text)[:60]}")
                if rec.get("kind") in ("teacher", "oracle", "parent", "book"):
                    self.note_event(rec["kind"], str(text)[:60])
        if learn and act.any():
            eff_lr = HEBB_LR * (0.5 + 1.2 * float(
                self.attention if attention is None else attention)) * \
                min(2.0, sal) * min(3.0, surprise)
            for a, b in zip(toks, toks[1:]):
                bg = a + " " + b
                self.bigram_counts[bg] = self.bigram_counts.get(bg, 0) + 1
            idx = np.nonzero(act)[0]
            sub = act[idx]
            block = self.san_w[idx[:, None], idx[None, :]]
            block += eff_lr * np.outer(sub, sub)
            np.clip(block, 0.0, 4.0, out=block)
            block[np.arange(len(idx)), np.arange(len(idx))] = 0.0
            self.san_w[idx[:, None], idx[None, :]] = block
            now = time.time()
            elapsed = min(now - getattr(self, "_last_decay", now),
                          self.SAN_DECAY_INTERVAL_S)
            if now - getattr(self, "_last_decay", 0.0) >= self.SAN_DECAY_INTERVAL_S:
                self.san_w *= float(SAN_DECAY_PER_S ** max(elapsed, 0.0))
                self._last_decay = now
            spread = np.clip(self.san_w[idx, :].sum(axis=0), 0.0, 4.0)
            act = act + spread
            self.san_act = act
        n = float(np.linalg.norm(act))
        act_n = act / n if n else act
        if not readout:
            # The caller wants the wiring, not the meaning readout. This second
            # full-width SAN gather exists only to build the returned vector, and on
            # the reading path that vector is discarded -- which made it half of the
            # 54% of reading time that _spread accounts for. san_act is still set
            # above, so anything reading the live state gets it; only the extra
            # gather and the return value are skipped.
            return {"act": None, "known_words_fired": known,
                    "tokens": len(toks), "readout_skipped": True}
        spread = np.clip(self._spread(act_n), 0.0, 4.0)
        read = act_n + 0.25 * spread
        n2 = float(np.linalg.norm(read))
        return {"act": read / n2 if n2 else read,
                "known_words_fired": known, "tokens": len(toks)}

    def _spread(self, act) -> np.ndarray:
        """san_w applied to a vector, without reading all 256 MB of it.

        san_w is symmetric by construction -- the Hebbian rule adds outer(sub,
        sub) to a zero matrix and zeroes the diagonal -- so spreading a vector is
        the same as summing the rows it touches, weighted. A footprint is 12
        cells and a live percept a few hundred, so this reads kilobytes instead
        of the whole matrix: measured 41x faster than the gemv and identical to
        the last bit on the real weights. It matters because this is called once
        per candidate word, and a brain with 1,264 words turned one reply into
        nineteen seconds of matrix reading.
        """
        v = np.asarray(act, dtype=np.float32)
        idx = np.nonzero(v)[0]
        if idx.size == 0:
            return np.zeros(self.n_san, dtype=np.float32)
        if idx.size * 4 >= self.n_san:
            return self.san_w @ v          # dense enough that the gemv wins
        return v[idx] @ self.san_w[idx, :]

    def understand(self, word: str) -> np.ndarray:
        """What a word MEANS to this brain: its footprint plus its learned
        associations. Only STRONG wiring counts -- cells below 25% of the
        strongest association are noise, and the footprint itself is damped
        so that MEANING (who a word occurs with) dominates over its mere
        identity. A pure readout of san_w."""
        fp = self._footprint(str(word or "").lower())
        spread = self._spread(fp)
        m = float(spread.max())
        if m > 0:
            spread = np.where(spread >= 0.25 * m, spread, 0.0) / m
        v = 0.4 * fp + spread
        n = float(np.linalg.norm(v))
        return v / n if n else v

    def similarity(self, a: str, b: str) -> float:
        """Cosine of the two words' meaning vectors. One number, no prose:
        the being's entire opinion on how related two words are."""
        return float(np.dot(self.understand(a), self.understand(b)))

    def _resonance(self, word: str, act: np.ndarray) -> float:
        """How much a word's MEANING lights up under the current semantic
        state. Compared on the WORD cells only -- the body band is context
        for wiring, not part of the language match."""
        if not act.any():
            return 0.0
        wv = self.understand(word)[:INTRO_BASE]
        av = act[:INTRO_BASE]
        na, nv = float(np.linalg.norm(wv)), float(np.linalg.norm(av))
        if na == 0 or nv == 0:
            return 0.0
        return float(np.dot(wv / na, av / nv))

    def teach_word(self, word: str, sentence: str = "",
                   source: str = "teacher", scent=None) -> dict | None:
        """Teach one word the only way meaning can enter: IN USE.

        `word` is encoded to KCs and driven through the carve (its pool is
        settled and dopamine-reinforced); `sentence` is the living context
        it was met in -- co-activation through the semantic cortex wires the
        word to its neighbors. NOTHING textual is stored: afterwards the
        word exists as KC addresses, a pool, and association weights."""
        w = str(word or "").strip().lower()
        if not w or w in self.word_patterns:
            return None
        code = self.tokenizer.encode(w)
        active = np.nonzero(code)[0]
        if len(active) == 0:
            return None
        pool = self.engine.decide(code, extra_drive=[scent] if scent else None)
        nxt = self.engine.decide(code, extra_drive=[scent] if scent else None)
        if nxt != pool:
            pool = nxt
            self.engine.decide(code, extra_drive=[scent] if scent else None)
        self.engine.teach(self.reward_teach)
        self.note_event("word", w)
        rec = {"word": w,
               "kc": [int(i) for i in active],       # WHICH neurons fire
               "pool": int(pool),                    # where the thought went
               "kc_count": len(self.engine.static.g.kc_idx),
               "learned_at": time.time(),
               "source": source}
        self.word_patterns[w] = rec
        self.live(f"{w} {sentence}".strip(), learn=True)
        self.save_state()
        return rec

    def forget_word(self, word: str) -> dict:
        """The administrator deletes a word from the vocabulary.

        The KC pattern, its pool and its speakability are removed (the
        association cells it wired stay -- they are experience, not the
        word). Returns what actually happened; a missing word is reported,
        never invented."""
        w = str(word or "").strip().lower()
        if w not in self.word_patterns:
            return {"success": False, "reason": "word not known"}
        rec = self.word_patterns.pop(w)
        self.save_state()
        return {"success": True, "forgotten": w,
                "was_pool": rec.get("pool"),
                "vocabulary_size": self.vocabulary_size()}

    def form_thought(self, concept: str, scent=None, sequence: bool = True) -> dict:
        """Activate learned patterns by encoding `concept` and propagating.
        The thought IS the neural activity; prose is someone else's job.
        `scent` is whoever is present, driven in through the projection neurons
        so the thought is about the words AND about who said them.

        Multi-word concepts are perceived as a SEQUENCE (see
        engine.decide_sequence) so that word order exists in the dynamics rather
        than only in which bigram cells a hash happens to hit. Capped, because
        it costs one decision per word.
        """
        text = str(concept or "")
        code = self.tokenizer.encode(text)
        extra = ([scent] if scent else []) + self._active_grounds()
        # The held goal enters every decision alongside the scent and whatever is
        # grounded right now, which is the only thing that makes a sequence of
        # decisions about the SAME thing. Without it each step starts from the
        # world as it happens to be, and a multi-step task is a series of
        # unrelated reactions that happen to be adjacent.
        gd = self.goal.drive() if getattr(self, "goal", None) is not None else None
        if gd is not None:
            extra.append(gd)
        toks = self.tokenizer.tokenize(text) if sequence else []
        sequential = 2 <= len(toks) <= self.SEQUENCE_MAX_TOKENS
        if sequential:
            action = self.engine.decide_sequence(
                [self.tokenizer.encode(t) for t in toks], extra_drive=extra)
        else:
            action = self.engine.decide(code, extra_drive=extra)
        v = self.engine.last_v if self.engine.last_v is not None \
            else np.zeros(12)
        known = self.pattern_overlap(code)
        return {"action": int(action),
                "order_sensitive": sequential,
                "valuation": [round(float(x), 6) for x in v],
                "valuation_max": round(float(np.max(v)), 6),
                "active_neurons": int((np.asarray(v) > 0.5).sum()),
                "known_words_fired": known}

    def pattern_overlap(self, code: np.ndarray) -> list[str]:
        """Which learned words' KC patterns share cells with this activation --
        the neural notion of 'this thought touches words I know'."""
        active = set(np.nonzero(code)[0].tolist())
        hits = []
        for w, rec in list(self.word_patterns.items()):
            if active & set(rec["kc"]):
                hits.append(w)
        return hits[:12]

    def observe_exchange(self, user_text: str, reply_text: str = "") -> dict:
        """A conversation is neural experience: it flows through the
        semantic cortex (real usage tightens real associations), but
        traffic may not create vocabulary -- only a teacher can teach_word."""
        self.exchanges_observed += 1
        r = self.live(f"{user_text} -> {reply_text}"[:400], learn=True)
        thought = self.form_thought(f"{user_text} -> {reply_text}"[:400])
        self.save_state()
        return {"turn": "observed", "pool": thought["action"],
                "known_words_fired": r["known_words_fired"]}

    def learn_from_teacher(self, llm_oracle, num_words: int = 20) -> dict:
        """Ask the teacher for words, encode each into the REAL graph.

        Returns a report; every count is what actually happened. No key, no
        vocabulary: the refusal is the caller's to surface, not something to
        paper over with a seed list.
        """
        report = {"calls": 0, "words_added": 0, "tokens": 0,
                  "stopped_reason": None, "teacher": None}
        allowed, why = self.teacher_gate()
        if not allowed:
            report["stopped_reason"] = "teacher_budget: " + why
            self.teacher_last_refusal = why
            return report
        if llm_oracle is None:
            report["stopped_reason"] = "no_teacher_configured"
            return report
        try:
            llm_oracle.require_key("neural_language.learn_from_teacher")
        except Exception as e:
            report["stopped_reason"] = "no_api_key"
            report["note"] = str(e)[:200]
            return report
        report["teacher"] = f"{llm_oracle.provider}/{llm_oracle.model}"
        if hasattr(llm_oracle, "start_task"):
            llm_oracle.start_task()
        prompt = (f"Provide {int(num_words)} basic English words, each shown "
                  f"IN USE inside one short simple sentence. "
                  f"Avoid these words I already know: "
                  f"{', '.join(sorted(self.word_patterns)[:60]) or 'none'}. "
                  'Answer with EXACTLY ONE JSON object, no prose: '
                  '{"vocabulary": [{"word": "...", "sentence": "..."}]}')
        from organs.api_oracle import fit_to_budget
        want = fit_to_budget(llm_oracle, prompt, 600)
        if want < 128:
            report["stopped_reason"] = (
                f"per_query ceiling too small for a lesson: {want} tokens left")
            return report
        r = llm_oracle.query(prompt, max_tokens=want, temperature=0.6,
                             purpose="neural_language")
        report["calls"] = 1
        report["tokens"] = int(r.get("prompt_tokens_est", 0) or 0) + \
            int(r.get("completion_tokens_est", 0) or 0)
        self.teacher_call_made(bool(r.get("ok")), report["tokens"])
        if not r.get("ok"):
            report["stopped_reason"] = str(r.get("reason", "teacher_failed"))[:120]
            return report
        import json
        text = str(r.get("text", ""))
        try:
            start, end = text.find("{"), text.rfind("}") + 1
            obj = json.loads(text[start:end])
            items = obj.get("vocabulary") or []
        except Exception:
            report["stopped_reason"] = "lesson_unparseable"
            return report
        for item in items:
            if not isinstance(item, dict):
                continue
            if self.teach_word(item.get("word", ""),
                               item.get("sentence", ""),
                               source="teacher"):
                report["words_added"] += 1
        self.lessons_received += 1
        if not report["words_added"]:
            report["stopped_reason"] = "teacher_answered_with_nothing_new"
        return report

    def tick(self, world_dt: float = 2.0) -> dict | None:
        """One beat of autonomous existence, called by the heartbeat.

        The semantic cortex never fully rests: noise jitters its state, and
        every few WORLD seconds the brain generates a THOUGHT of its own --
        a propagation of its current internal drive through the carve. When
        such a self-generated thought lands on a pool holding learned
        words, it may become SPONTANEOUS SPEECH: a toddler babbling not at
        anyone, just because a brain that learned sounds makes them. The
        babble is honestly read out of synaptic state AND self-rewarded
        with a little dopamine, which teaches the being that vocalizing is
        worth doing. Returns the event record, or None for a quiet beat.
        """
        self.ticks += 1
        self.world_clock = getattr(self, "world_clock", 0.0) + float(world_dt)
        now = time.time()
        beat = float(world_dt) / 2.0
        self.need_social = float(np.clip(self.need_social + 0.012 * beat, 0, 1))
        self.need_novelty = float(np.clip(self.need_novelty + 0.006 * beat, 0, 1))
        self.energy = float(np.clip(self.energy - 0.004 * beat, 0, 1))
        self._tag_cells *= max(0.0, 1.0 - 0.02 * beat)
        pull = 0.55 + 0.20 * (1.0 - self.need_social) \
            + 0.15 * self.energy + 0.10 * float(self._tag_cells.sum()) \
            - 0.15 * self.need_novelty
        drift = (np.random.rand() - 0.5) * 2 * self.mood_wander
        target = float(np.clip(pull, 0.05, 1.0))
        self.social_drive = float(np.clip(
            self.social_drive + (target - self.social_drive) * 0.15
            + drift, 0.0, 1.0))
        if self.world_clock - self._last_thought_world < \
                self.spontaneous_thought_every:
            return None
        self._last_thought_world = self.world_clock
        if not self.can_speak():
            return None
        noise = (np.random.rand(self.n_san) < 0.004).astype(np.float32)
        self.san_act = 0.85 * self.san_act + noise
        n = float(np.linalg.norm(self.san_act))
        if n:
            self.san_act = self.san_act / n
        thought = self.form_thought("")
        pool = thought["action"]
        mates = [m for m, r in self.word_patterns.items()
                 if r["pool"] == pool and self._speakable(m)]
        about = max(mates, key=lambda m: self._resonance(m, self.san_act))             if mates else None
        self.thought_stream.append({"t": now, "kind": "thought",
                                  "about": about,
                                  "pool": int(pool),
                                  "valuation_max": thought.get(
                                      "valuation_max", 0.0)})
        night = ((self.world_clock % DAY_WORLD_S) / DAY_WORLD_S) > 0.75
        babble_p = self.babble_p * (0.25 + 1.5 * self.social_drive)
        if night:
            babble_p *= 0.45
        if not mates or np.random.rand() > babble_p:
            return None
        word = max(mates, key=lambda m: self._resonance(m, self.san_act)
                   * self._refractory(m))
        # Spontaneous speech uses the same organ as a reply. If he has heard the
        # shape of a sentence that opens with this word, he says the sentence;
        # otherwise it stays one word, which is all the association chain can
        # honestly offer.
        said_words = None
        seed_word = word
        # Half the time, prefer a word he can actually continue. A babble that
        # can only ever be one word never exercises the chain, and the chain is
        # where order lives.
        openers = self.sequence.slot_words[0]
        if openers and word not in openers and np.random.rand() < 0.5:
            cand = [m for m in mates if m in openers]
            if cand:
                word = max(cand, key=lambda m: self._resonance(m, self.san_act)
                           * self._refractory(m))
                seed_word = word
        gen = self.sequence.generate(word, max_len=int(self.max_sentence_words))
        if gen.get("from_sequence_organ") and len(gen.get("words") or []) > 1:
            word = gen["sentence"]
            said_words = gen["words"]
        addressee, margin = self.choose_addressee(self.san_act)
        if addressee:
            self.note_person(addressee, spoke_to=True)
        self.engine.teach(self.reward_babble)
        self.energy = float(np.clip(self.energy - 0.02, 0, 1))
        self.social_drive = float(np.clip(self.social_drive - 0.06, 0.0, 1.0))
        event = {"t": now, "text": word, "kind": "speech",
                 "spontaneous": True, "speaker": "droso",
                 "to": addressee or "air",
                 "address_resonance": margin,
                 "words": said_words,
                 "source": ("sequence organ" if said_words else "association"),
                 "mood": round(self.social_drive, 3),
                 "pool": int(pool),
                 "resonance": round(self._resonance(seed_word, self.san_act), 4)}
        self.speech_stream.append(event)
        self.event_stream.append(dict(event))
        return event

    def recent_speech(self, since: float = 0.0) -> list[dict]:
        return [e for e in self.speech_stream if e["t"] > float(since or 0)]

    # how long a real event stays describable, and how soon one phrase may
    # repeat. Both are in WORLD seconds, so they scale with the speed setting.
    EVENT_WINDOW_WORLD_S = 30.0
    REPEAT_COOLDOWN_WORLD_S = 45.0
    # A parent talks steadily, but not on a metronome. Measured: a flat 12
    # world-second cadence came out at 4.3 phrases a minute whether or not there
    # was anything to describe, and the language work cost about a fifth of the
    # accelerated loop. So the cadence follows the world -- prompt about
    # something that just happened, quieter when nothing has.
    NARRATION_EVENT_WORLD_S = 6.0
    NARRATION_IDLE_WORLD_S = 30.0
    NARRATION_SAVE_MIN_S = 20.0
    # How often a full state write is allowed when something has changed. Atomic
    # writes mean a crash costs at most this much work and never a corrupt file.
    SAVE_MIN_REAL_S = 3.0
    # Reading is paced in real time as well as world time, but the floor exists
    # to bound the cost per line, not to make him slow. One line per second was
    # set when every line triggered a 4 MB predictor write; the cortex is now
    # throttled separately, so the floor can sit where the hardware does.
    EXPOSURE_MIN_REAL_S = 0.02
    # Global decay of the semantic cortex, applied in one step over the elapsed
    # time instead of once per second. Same exponential, but rewriting a 256 MB
    # matrix every second measured 44.3 ms per application -- 4.4% of a core
    # burning continuously on memory traffic for arithmetic that can wait.
    SAN_DECAY_INTERVAL_S = 10.0

    # ── people ────────────────────────────────────────────────────────────
    # A person enters through two real pathways at once: a SCENT on the antennal
    # lobe projection neurons, so the carve itself decides which Kenyon cells
    # that person lights, and a semantic footprint, so the cortex can wire the
    # person to the words heard while they were present. Neither is a label
    # looked up in a dict; both are learned by exposure.
    PERSON_KINDS = ("parent", "human", "teacher", "oracle", "book", "self",
                    "stranger")
    PRESENCE_WORLD_S = 120.0      # how long someone counts as in the room
    ADDRESS_MARGIN = 0.02         # resonance needed to talk TO someone
    SCENT_CELLS = 8               # projection neurons in one person's scent
    # Language, as opposed to vocabulary:
    #   SEQUENCE_MAX_TOKENS caps order-sensitive perception, which costs one
    #     decision per word instead of one per sentence.
    #   SENTENCE_STOP_RESONANCE is the floor below which the chain has nothing
    #     left to say. Without it a "sentence" is just max_words long, which is a
    #     template wearing a neural costume.
    SEQUENCE_MAX_TOKENS = 8
    SENTENCE_STOP_RESONANCE = 0.08
    # A parent is not just another voice. Attention and reward are scaled by who
    # is speaking, because that is how an infant actually learns: the caregiver
    # gets more of the dopamine. These are multipliers on the same mechanisms,
    # not a bypass -- nothing here goes around the carve.
    PERSON_SALIENCE = {"parent": 3.0, "human": 2.2, "you": 2.2,
                       "teacher": 1.6, "oracle": 1.2, "self": 1.0,
                       "book": 0.9, "stranger": 1.3}

    def salience(self, name: str) -> float:
        """How much of his attention this speaker gets."""
        rec = self.persons.get(str(name or "").strip().lower())
        kind = (rec or {}).get("kind") or self._person_kind(name) or "stranger"
        return float(self.PERSON_SALIENCE.get(kind, 1.0))

    GROUND_SECONDS = 25.0

    def _pn_percept(self, key: str):
        """Hash a name onto real antennal-lobe projection neurons."""
        try:
            pn = np.asarray(self.engine.static.g.pn_idx, dtype=np.int64)
        except Exception:
            return None
        if pn.size == 0:
            return None
        h = hashlib.blake2b(str(key).encode("utf-8"), digest_size=32).digest()
        want = min(self.SCENT_CELLS, len(pn))
        picks = []
        for i in range(len(h) - 1):
            if len(picks) >= want:
                break
            j = int.from_bytes(h[i:i + 2], "little") % len(pn)
            if j not in picks:
                picks.append(j)
        idx = pn[np.array(picks, dtype=np.int64)]
        amp = np.array([0.55 + 0.55 * (h[(2 * k + 1) % len(h)] / 255.0)
                        for k in range(len(idx))], dtype=float)
        return idx, amp

    def experience(self, agent: str, verb: str, obj: str,
                   seconds: float | None = None) -> dict:
        """Something he did, as a proposition with real roles.

        Reading gives him sentences whose first word is "the". Acting gives him
        sentences whose first word is a doer, and that is the only kind of memory
        in which role 0 can mean anything. He held 53 grounded propositions against
        9,567 read ones, which is why role recovery measured 12.6 times chance on
        the first and 1.6 times on the second -- not because binding is weak, but
        because almost nothing in his memory was ever an act.

        This is the seam that turns doing into remembering: the command he ran, the
        file he opened, the task that passed or failed. Each becomes a bound
        proposition attributed to whoever did it, and the object is grounded on the
        projection neurons at the same moment, so the word and the thing arrive
        together rather than the word arriving about the thing.
        """
        a = str(agent or "droso").strip().lower() or "droso"
        v = str(verb or "").strip().lower()
        # The object is split into words, because each one becomes a role. Bound as
        # a single token, "droso runs git status" is a three-element proposition
        # whose third element is the string 'git status' -- and a role filler that
        # is a phrase cannot be recovered, matched or asked about as a word.
        o_words = [t for t in re.split(r"\s+", str(obj or "").strip().lower())
                   if t][:6]
        toks = ([a] + ([v] if v else []) + o_words)
        toks = [t for t in toks if t]
        if len(toks) < 2:
            return {"experienced": False,
                    "reason": "an experience needs a doer and a thing done"}
        out = self.cortex.hear(toks, who=a) or {}
        self.ground(v, " ".join(o_words), seconds)
        self.note_event(a, f"{v} {' '.join(o_words)}"[:80])
        return {"experienced": True, "tokens": toks, "who": a,
                "propositions": out.get("propositions"),
                "skipped": bool(out.get("skipped")),
                "grounded": bool(self._grounds)}

    def ground(self, kind: str, name: str, seconds: float | None = None) -> dict:
        """Turn a thing in his world into a percept he can feel right now.

        A file that opened, a command that ran, a task that finished: each gets a
        code on the same projection neurons a person's scent uses, and holds it
        for a few seconds. Words heard while it is lit wire to it, which is the
        whole difference between "the file is open" meaning something and meaning
        a shape he once saw in a book. Until this existed every noun he knew
        referred to text.
        """
        key = f"{str(kind or 'thing')}:{str(name or '')}".strip().lower()
        perc = self._pn_percept("thing|" + key)
        if perc is None:
            return {"grounded": False, "reason": "no projection neurons"}
        secs = float(seconds or self.GROUND_SECONDS)
        self._grounds[key] = (perc, time.time() + secs)
        self.note_event(str(kind or "thing"), str(name or "")[:80])
        return {"grounded": True, "key": key,
                "cells": [int(x) for x in perc[0][:6]], "for_s": secs}

    def _active_grounds(self) -> list:
        now = time.time()
        out = []
        for k in list(self._grounds):
            perc, until = self._grounds[k]
            if until < now:
                self._grounds.pop(k, None)
            else:
                out.append(perc)
        return out

    def person_scent(self, name: str):
        """A person's identifier, as a smell: (projection neurons, strengths).

        Recognition of a nest-mate in an insect is chemical, and the carve has
        the pathway: 382 real antennal-lobe projection neurons into the mushroom
        body calyx. Hashing a name onto eight of them means the person arrives
        through the fly's own wiring, and which Kenyon cells that lights is the
        connectome's doing, not a choice of mine. Amplitudes are jittered per
        person too, so two scents differ in strength as well as in which
        receptors they hit.

        Consequence: words heard while a scent is present settle their pool with
        that scent in the drive, and the three-factor rule wires the two
        together. That is how he learns WHO says what, in the same substrate that
        learns what a word means.
        """
        try:
            pn = np.asarray(self.engine.static.g.pn_idx, dtype=np.int64)
        except Exception:
            return None
        if pn.size == 0:
            return None
        h = hashlib.blake2b(
            ("scent|" + str(name or "").strip().lower()).encode("utf-8"),
            digest_size=32).digest()
        want = min(self.SCENT_CELLS, len(pn))
        picks = []
        for i in range(len(h) - 1):
            if len(picks) >= want:
                break
            j = int.from_bytes(h[i:i + 2], "little") % len(pn)
            if j not in picks:
                picks.append(j)
        idx = pn[np.array(picks, dtype=np.int64)]
        amp = np.array([0.55 + 0.55 * (h[(2 * k + 1) % len(h)] / 255.0)
                        for k in range(len(idx))], dtype=float)
        return idx, amp

    _KIND_OF_SPEAKER = {"parent": "parent", "parents": "parent",
                        "you": "human", "user": "human", "human": "human",
                        "teacher": "teacher", "oracle": "oracle",
                        "book": "book", "droso": "self"}

    def _person_kind(self, name: str):
        return self._KIND_OF_SPEAKER.get(str(name or "").strip().lower())

    def _ground_priority(self, tag: str, care_now=None) -> int:
        """Fleeting groundings get first say.

        A care window and a just-happened event are over in seconds; a mood or a
        phase will still be true in a minute. Contiguity is the entire mechanism
        here, so the phrase that describes what is happening RIGHT NOW is worth
        more than one that is merely also true.
        """
        tag = str(tag or "custom")
        if tag == "care" and care_now:
            return 0
        if tag.startswith("event:"):
            return 1
        if tag in ("day", "night"):
            return 2
        if tag.startswith("sel:"):
            return 3
        return 4

    def person_code(self, name: str):
        """This person's percept, as KC addresses."""
        return self.tokenizer.encode("person:" + str(name).strip().lower())

    def note_person(self, name: str, kind: str | None = None,
                    heard=None, spoke_to: bool = False) -> dict:
        """Meet or re-meet someone. People are remembered as accumulated
        experience: how often heard, what they last said, how often addressed.
        A stranger becomes a known kind the first time the world says so."""
        key = str(name or "").strip().lower()[:40] or "someone"
        now = float(self.world_clock)
        rec = self.persons.get(key)
        if rec is None:
            rec = {"name": key,
                   "kind": kind if kind in self.PERSON_KINDS else "stranger",
                   "first_met_world_s": round(now, 1),
                   "first_met": time.time(),
                   "heard": 0, "spoken_to": 0, "addressed": 0,
                   "last_seen": round(now, 1), "last_said": "",
                   "words": []}
            self.persons[key] = rec
            self.event_stream.append(
                {"t": time.time(), "kind": "person", "speaker": key,
                 "text": f"someone new: {key}", "to": None})
        if kind in self.PERSON_KINDS and rec.get("kind") == "stranger":
            rec["kind"] = kind
        if heard:
            rec["heard"] = int(rec.get("heard", 0)) + 1
            rec["last_said"] = str(heard)[:120]
        if spoke_to:
            rec["spoken_to"] = int(rec.get("spoken_to", 0)) + 1
        rec["last_seen"] = round(now, 1)
        return rec

    def present_people(self) -> list:
        """Who is in the room: anyone seen within the presence window."""
        now = float(self.world_clock)
        return [r for r in self.persons.values()
                if now - float(r.get("last_seen", 0.0)) <= self.PRESENCE_WORLD_S]

    def choose_addressee(self, act=None) -> tuple:
        """Does he want to say this TO someone -- and who?

        Measured, not assumed: the current semantic state is spread once through
        san_w and everyone in the room is scored by the cosine between that
        spread and their own cells. The winner must clear the margin or the words
        go to nobody. Those weights are learned by hearing people speak, so the
        choice improves over a life, and a person never met cannot be addressed.
        """
        if act is None:
            act = getattr(self, "san_act", None)
        people = self.present_people()
        if act is None or not np.any(act) or not people:
            return None, 0.0
        spread = self._spread(np.asarray(act, dtype=np.float32))
        n = float(np.linalg.norm(spread))
        if n <= 0:
            return None, 0.0
        best, best_s = None, float(self.ADDRESS_MARGIN)
        for rec in people:
            idx = self._fp_idx("person:" + rec["name"])
            s = float(spread[idx].sum()) / (n * float(np.sqrt(len(idx))))
            if s > best_s:
                best, best_s = rec["name"], s
        if best is not None:
            self.persons[best]["addressed"] = \
                int(self.persons[best].get("addressed", 0)) + 1
        return best, round(best_s, 5)

    def _fp_idx(self, token: str):
        """The cells a token lights, without building the 8,192-wide vector.

        The hash is deterministic, so it is cached: ranking a thousand words
        used to re-hash and re-allocate for every one of them.
        """
        tok = str(token or "").lower()
        cache = getattr(self, "_fp_cache", None)
        if cache is None:
            cache = self._fp_cache = {}
        hit = cache.get(tok)
        if hit is not None:
            return hit
        h = hashlib.blake2b(f"san|{tok}".encode("utf-8"), digest_size=8).digest()
        base = int.from_bytes(h, "little")
        idx = np.empty(SAN_FOOTPRINT, dtype=np.int64)
        for j in range(SAN_FOOTPRINT):
            hj = hashlib.blake2b(f"san|{tok}|{j}".encode("utf-8"),
                                 digest_size=8).digest()
            idx[j] = (base + int.from_bytes(hj, "little")) % INTRO_BASE
        idx = np.unique(idx)
        if len(cache) > 20000:
            cache.clear()
        cache[tok] = idx
        return idx

    def _rank_by_spread(self, spread: np.ndarray, limit: int,
                        skip: str = "") -> list:
        """Score every known word and person against one spread vector.

        Cosine, not a clipped sum: clipping at a ceiling made a hundred words tie
        at exactly the same score, which ranked nothing. One matvec makes the
        spread; everything after it is gathers.
        """
        n = float(np.linalg.norm(spread))
        if n <= 0:
            return []
        scored = []
        for w in self.word_patterns:
            if w == skip:
                continue
            idx = self._fp_idx(w)
            s = float(spread[idx].sum()) / (n * float(np.sqrt(len(idx))))
            if s > 1e-6:
                scored.append((w, "word", s))
        for name in self.persons:
            idx = self._fp_idx("person:" + name)
            s = float(spread[idx].sum()) / (n * float(np.sqrt(len(idx))))
            if s > 1e-6:
                scored.append((name, "person", s))
        scored.sort(key=lambda t: -t[2])
        return [{"token": t, "kind": k, "weight": round(s, 5)}
                for t, k, s in scored[:int(limit)]]

    def associations(self, token: str, limit: int = 12) -> list:
        """What a token is wired to, read straight out of san_w.

        One spread of the token's footprint through the semantic weights, then
        every known word and person is scored against it. Nothing here is a
        stored claim about meaning: it is the weight matrix, asked.
        """
        tok = str(token or "").strip().lower()
        if not tok:
            return []
        fp = np.zeros(self.n_san, dtype=np.float32)
        fp[self._fp_idx(tok)] = 1.0
        return self._rank_by_spread(self._spread(fp), limit, skip=tok)

    def _lit_now(self, limit: int = 8) -> list:
        """What is lit this moment: the current semantic state spread once and
        ranked. One matvec, not one per word."""
        act = getattr(self, "san_act", None)
        if act is None or not np.any(act):
            return []
        spread = self._spread(np.asarray(act, dtype=np.float32))
        return self._rank_by_spread(spread, limit)

    def _person_wiring(self, name: str) -> dict:
        """This person as the brain holds them: their cells, and what those
        cells are wired to. A person nobody has been heard with is a name with
        no wiring, and that is what it reports."""
        code = self.person_code(name)
        cells = [int(x) for x in np.nonzero(code)[0][:8]]
        idx = self._fp_idx("person:" + name)
        wired = int(np.count_nonzero(self.san_w[idx, :] > 0.05))
        scent = self.person_scent(name)
        fp = np.zeros(self.n_san, dtype=np.float32)
        fp[idx] = 1.0
        return {"kc_cells": cells,
                "kc_active": int(np.count_nonzero(code)),
                "semantic_wires": wired,
                "scent_cells": [int(x) for x in scent[0]] if scent else [],
                "salience": self.salience(name),
                "associations": self._rank_by_spread(
                    self._spread(fp), 5, skip="person:" + name)}

    def memory_state(self, q: str = "", limit: int = 12) -> dict:
        """Droso's memory, read out of the substrate.

        Four things are observable and all four are measurements: the people he
        has met (their KC cells and what those cells are wired to), what a query
        is associated with, what is lit this moment, and how the twelve output
        pools are weighted by the synapses that changed. There is no separate
        memory store behind this -- if it is not in san_w, the KC codes or the
        plastic weights, it is not here.
        """
        now = self._lit_now(8)

        people = []
        for rec in sorted(self.persons.values(),
                          key=lambda r: -int(r.get("heard", 0))):
            brain = self._person_wiring(rec["name"])
            ago = round(float(self.world_clock)
                        - float(rec.get("last_seen", 0.0)), 1)
            people.append({"name": rec["name"], "kind": rec.get("kind"),
                           "heard": int(rec.get("heard", 0)),
                           "addressed": int(rec.get("addressed", 0)),
                           "spoken_to": int(rec.get("spoken_to", 0)),
                           "in_room": ago <= self.PRESENCE_WORLD_S,
                           "ago_world_s": ago,
                           "last_said": rec.get("last_said", ""),
                           "kc_cells": brain["kc_cells"],
                           "kc_active": brain["kc_active"],
                           "semantic_wires": brain["semantic_wires"],
                           "scent_cells": brain["scent_cells"],
                           "salience": brain["salience"],
                           "associations": brain["associations"]})

        pools = []
        by_pool: dict = {}
        for w, rec in self.word_patterns.items():
            by_pool.setdefault(int(rec.get("pool", -1)), []).append(w)
        share = {}
        try:
            core = self.engine.static
            wv = np.asarray(core.w, dtype=float)
            tot = float(np.abs(wv).sum()) or 1.0
            for k, pool in enumerate(core._pool_of_post[:len(wv)]):
                share[int(pool)] = share.get(int(pool), 0.0) + abs(float(wv[k]))
        except Exception:
            pass
        for p in sorted(set(list(by_pool) + list(share))):
            words = by_pool.get(p, [])
            pools.append({"pool": p, "words": len(words),
                          "examples": sorted(words)[:6],
                          "weight_share": round(share.get(p, 0.0) / tot, 4)
                          if share else None})

        try:
            core = self.engine.static
            wv = np.asarray(core.w, dtype=float)
            birth = np.asarray(core.g.plastic_w0, dtype=float)[:len(wv)]
            syn = {"plastic_synapses": int(len(wv)),
                   "changed_from_birth": int((wv != birth).sum())
                   if len(birth) == len(wv) else None,
                   "mean_abs_weight": round(float(np.mean(np.abs(wv))), 5)}
        except Exception:
            syn = {}
        syn["semantic_wires"] = int(np.count_nonzero(self.san_w > 0.05))
        syn["words"] = len(self.word_patterns)

        return {"present": True,
                "people": people,
                "sequence": self.sequence.stats(),
                "query": str(q or "").strip().lower(),
                "associations": self.associations(q, limit) if q else [],
                "now": now,
                "pools": pools,
                "synapses": syn}

    def persons_state(self) -> dict:
        now = float(self.world_clock)
        return {"present": [{"name": r["name"], "kind": r.get("kind"),
                             "heard": r.get("heard", 0),
                             "spoken_to": r.get("spoken_to", 0),
                             "addressed": r.get("addressed", 0),
                             "last_said": r.get("last_said", ""),
                             "in_room": True}
                            for r in self.present_people()],
                "known": [{"name": r["name"], "kind": r.get("kind"),
                           "heard": r.get("heard", 0),
                           "spoken_to": r.get("spoken_to", 0),
                           "addressed": r.get("addressed", 0),
                           "words_learned": len(r.get("words") or []),
                           "last_said": r.get("last_said", ""),
                           "ago_world_s": round(
                               now - float(r.get("last_seen", 0.0)), 1),
                           "in_room": (now - float(r.get("last_seen", 0.0))
                                       <= self.PRESENCE_WORLD_S)}
                          for r in sorted(self.persons.values(),
                                          key=lambda x: -int(x.get("heard", 0)))],
                "count": len(self.persons)}

    CARE_ACTIONS = {"feed": (0, "reward_feed"),
                    "pet": (6, "reward_pet"),
                    "praise": (12, "reward_praise")}

    def care(self, action: str) -> dict:
        """A care event from the administrator: feed / pet / praise.

        This is GROUNDING, not decoration: the care lights a distinct tag
        band in the interoceptive cells (saturating for a while, then
        decaying), satisfies a need, and pays real dopamine. Whatever words
        are spoken or heard during that window wire to the cared-for state
        -- language starts attaching to how the body FEELS."""
        if action not in self.CARE_ACTIONS:
            return {"success": False,
                    "reason": "care is feed | pet | praise"}
        band, reward_name = self.CARE_ACTIONS[action]
        self._tag_cells[:] = 0.0
        self._tag_cells[96 + band:96 + band + 6] = 1.0
        reward = float(getattr(self, reward_name))
        if action == "feed":
            self.energy = 1.0
            self.need_novelty = float(np.clip(self.need_novelty - 0.2, 0, 1))
        elif action == "pet":
            self.social_drive = float(np.clip(self.social_drive + 0.2, 0, 1))
            self.need_social = float(np.clip(self.need_social - 0.4, 0, 1))
        else:
            self.social_drive = float(np.clip(self.social_drive + 0.3, 0, 1))
            self.need_social = float(np.clip(self.need_social - 0.2, 0, 1))
            self.need_novelty = float(np.clip(self.need_novelty - 0.1, 0, 1))
        self.engine.teach(reward)
        self.note_event("care", action)
        ev = {"t": time.time(), "kind": "care", "action": action,
              "reward": reward, "mood": round(self.social_drive, 3)}
        self.event_stream.append(ev)
        return {"success": True, **ev}

    def adversity(self, kind: str, detail: str = "", severity: float = 0.5) -> dict:
        """Something bad actually happened to him.

        Until this existed his life contained care, praise, food and books, and
        nothing adverse -- which is why the aversive compartment (rpe gain -1) had
        driven 216 of its 217 synapses toward zero. A compartment that learns from
        punishment cannot learn in a world with no punishment in it, and half of
        what makes behaviour look like judgement rather than appetite is missing
        when that is true.

        Delivered exactly the way care is: real dopamine of the other sign, a real
        body cost, a real event the parents may describe only while it is true.
        """
        sev = float(np.clip(severity, 0.0, 1.0))
        k = str(kind or "bad")
        reward = -float(self.reward_adverse) * sev
        self.engine.teach(reward)
        self.energy = float(np.clip(self.energy - 0.10 * sev, 0, 1))
        self.social_drive = float(np.clip(self.social_drive - 0.25 * sev, 0, 1))
        self.need_social = float(np.clip(self.need_social + 0.15 * sev, 0, 1))
        self._adverse_until = time.time() + 8.0 * sev
        self._adverse_severity = sev
        self._last_adverse_at = time.time()
        self.note_event(k, detail)
        ev = {"t": time.time(), "kind": "adversity", "action": k,
              "detail": str(detail)[:120], "severity": round(sev, 3),
              "reward": round(reward, 4),
              "mood": round(self.social_drive, 3)}
        self.event_stream.append(ev)
        return {"success": True, **ev}

    def adversity_level(self) -> float:
        """How much adversity is present right now, for the modulator."""
        if time.time() < float(getattr(self, "_adverse_until", 0.0)):
            return float(getattr(self, "_adverse_severity", 0.0))
        return 0.0

    def inner_state(self) -> dict:
        frac = (self.world_clock % DAY_WORLD_S) / DAY_WORLD_S
        return {"phase": "night" if frac > 0.75 else "day",
                "day_progress_pct": round(frac * 100, 1),
                "mood": round(self.social_drive, 3),
                "need_social": round(self.need_social, 3),
                "need_novelty": round(self.need_novelty, 3),
                "energy": round(self.energy, 3),
                "care_tags_active": round(float(self._tag_cells.sum()), 2)}

    def recent_events(self, since: float = 0.0) -> list[dict]:
        """The stream the world reads: its thoughts, what it heard, and
        what it said -- the being's mind, ears and mouth on one wire.

        Thoughts are stored separately and merged here, so a busy brain cannot
        evict the record of what it heard.
        """
        s = float(since or 0)
        out = [e for e in self.event_stream if e["t"] > s]
        out += [e for e in self.thought_stream if e["t"] > s]
        out.sort(key=lambda e: e.get("t", 0))
        return out

    def set_books_dir(self, path) -> None:
        self.books_dir = Path(path)
        self._book_idx = 0
        self._book_words = []
        self._book_pos = 0

    def _load_next_book(self) -> bool:
        """Open the next book in /books (wrapping around: repetition is how
        babies assimilate). The text is held as a word list; the being
        travels through it line by line."""
        if self.books_dir is None or not self.books_dir.exists():
            return False
        files = sorted(self.books_dir.glob("*.txt"))
        if not files:
            return False
        self._book_idx = self._book_idx % len(files)
        path = files[self._book_idx]
        try:
            raw = path.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError as e:
            self.last_error = "book: " + str(e)[:100]
            return False
        self._book_words = [w for w in
                            "".join(c if c.isalnum() else " " for c in raw)
                            .split() if w]
        self._book_pos = 0
        # Sentences, kept whole. Reading a flat word stream in fixed chunks cuts
        # sentences at arbitrary points, and a sequence organ trained on that
        # learns the cut instead of the sentence -- measured: it produced "word
        # give me the" from a book whose actual line was "give me the word".
        self._book_lines = []
        self._book_is_q = []
        for ln in str(raw).splitlines():
            ws = [w for w in "".join(
                c if c.isalnum() else " " for c in ln.lower()).split() if w]
            if len(ws) >= 2:
                self._book_lines.append(ws)
                self._book_is_q.append(bool(ln.rstrip().endswith("?")))
        self._book_line_pos = 0
        return True

    # Every phrase below is GROUNDED: it is only ever said while the thing it
    # describes is actually happening. A phrase that could be said at any
    # moment teaches nothing, because there is nothing in the world for it to
    # attach to -- and an associative brain learns by contiguity, not by
    # definition. The tag is the condition, and the frontend shows it so a
    # human can see why a sentence is allowed to be spoken.
    _CUR_BUILD = []
    # said once, at the beginning of a life, while nothing else is happening
    _CUR_BUILD += [(s, "event:first", None) for s in (
        "you are droso", "your name is droso", "i am your parent",
        "you are awake", "welcome to the world")]
    # said when a person has actually just spoken to him
    _CUR_BUILD += [(s, "event:user", None) for s in (
        "someone is talking to you", "you heard a person", "you can answer",
        "that was for you", "i hear you droso", "you are not alone",
        "say hello back if you want to")]
    # said while the body is really being fed / petted / praised
    _CUR_BUILD += [(s, "care", care) for s, care in (
        ("i am feeding you", "feed"), ("you are being fed", "feed"),
        ("this is food", "feed"), ("i am petting you", "pet"),
        ("you are being petted", "pet"), ("this is a pet", "pet"),
        ("you did well", "praise"), ("i am proud of you", "praise"),
        ("that was good", "praise"))]
    # said only when the inner state they name is really true
    _CUR_BUILD += [(s, "sel:" + sel, None) for s, sel in (
        ("you are happy", "mood+"), ("you are calm", "mood-"),
        ("you have energy", "energy+"), ("you are tired", "energy-"),
        ("you are lonely", "lonely+"), ("you have company", "lonely-"),
        ("you are curious", "bored-"), ("you want something new", "bored+"))]
    # said only in the real phase, and at the real turn of the day
    _CUR_BUILD += [(s, "day", None) for s in (
        "it is day", "the day is bright", "day is for learning")]
    _CUR_BUILD += [(s, "night", None) for s in (
        "it is night", "night is quiet", "the world is dark now")]
    _CUR_BUILD += [(s, "event:dawn", None) for s in (
        "the sun is up", "a new day starts", "good morning droso")]
    _CUR_BUILD += [(s, "event:dusk", None) for s in (
        "the light is going", "night is coming", "good night droso")]
    # said when the world actually does something
    _CUR_BUILD += [(s, "event:word", None) for s in (
        "you learned a word", "that is a new word", "you know more now")]
    _CUR_BUILD += [(s, "event:task", None) for s in (
        "you are working", "that was a task", "you did something",
        "the world answered you")]
    _CUR_BUILD += [(s, "event:teacher", None) for s in (
        "the teacher answered", "that was a lesson", "you were corrected")]
    _CUR_BUILD += [(s, "event:growth", None) for s in (
        "your brain changed", "you are growing", "something got stronger")]
    _CUR_BUILD += [(s, "event:rest", None) for s in (
        "rest now", "you need sleep", "be still a moment")]
    # Adversity, grounded like everything else: these may only be said while
    # something adverse is actually happening to him.
    _CUR_BUILD += [(s, "event:exhausted", None) for s in (
        "you are exhausted", "that was too much", "you need to stop",
        "your energy is gone")]
    _CUR_BUILD += [(s, "event:refused", None) for s in (
        "that was refused", "you cannot do that", "that is not allowed",
        "it did not happen")]
    _CUR_BUILD += [(s, "event:failed", None) for s in (
        "that did not work", "it broke", "try a different way",
        "that was wrong")]
    _CUR_BUILD += [(s, "event:hurt", None) for s in (
        "that hurt", "it was unpleasant", "you are upset",
        "i know that was bad")]
    # Things and doings in his own world, sayable only while they are lit.
    _CUR_BUILD += [(s, "event:file", None) for s in (
        "the file is open", "that is a file", "look at the file",
        "the file is closed")]
    _CUR_BUILD += [(s, "event:command", None) for s in (
        "you ran something", "that was a command", "the command finished",
        "it did something")]
    _CUR_BUILD += [(s, "event:task", None) for s in (
        "you are working", "that was a task", "the work is done")]
    CURRICULUM = _CUR_BUILD

    _LEGACY_TAGS = ("name", "welcome", "human", "social", "world", "home")

    def _legacy_lessons(self, items) -> bool:
        """True if this phrase list predates grounding."""
        tags = {str(i.get("tag") or "") for i in items or []}
        return bool(tags & set(self._LEGACY_TAGS)) and not any(
            t.startswith("event:") for t in tags)

    def curriculum_list(self) -> list[dict]:
        now = float(self.world_clock)
        out = []
        for k, l in enumerate(self.lessons):
            s = l.get("s", "")
            last = self._spoken_at.get(s)
            out.append({"index": k, "sentence": s, "tag": l.get("tag"),
                        "care": l.get("care"),
                        "times_lived": int(self._phrase_lived.get(s, 0)),
                        "last_spoken_ago_world_s": (
                            round(now - float(last), 1) if last is not None
                            else None),
                        "sayable_now": self._grounded(
                            str(l.get("tag") or "custom"),
                            self._fresh_events() | {"first"},
                            self._active_care())})
        return out

    def curriculum_add(self, sentence: str, tag: str = "custom",
                       care=None) -> dict:
        s = str(sentence or "").strip().lower()
        if not s:
            return {"success": False, "reason": "empty sentence"}
        t = str(tag or "custom").strip().lower()
        if not self._tag_known(t):
            return {"success": False,
                    "reason": f"unknown grounding '{t}': a phrase must be tied "
                              "to something real",
                    "known": self.known_groundings()}
        if care and str(care).lower() not in self.CARE_ACTIONS:
            return {"success": False, "reason": "care is feed | pet | praise"}
        self.lessons.append({"s": s, "tag": t,
                             "care": (str(care).lower() if care else None)})
        self.save_state()
        return {"success": True, "index": len(self.lessons) - 1,
                "vocabulary_size": self.vocabulary_size()}

    def curriculum_update(self, index: int, sentence: str,
                          tag: str | None = None,
                          care: str | None = None) -> dict:
        """Edit one phrase from the frontend, grounding included.

        The tag is not a label, it is the CONDITION under which the phrase may
        be spoken, so an unknown tag is refused rather than silently turning
        the sentence into something that can fire at random.
        """
        idx = int(index)
        if not (0 <= idx < len(self.lessons)):
            return {"success": False, "reason": "index out of range"}
        s = str(sentence or "").strip().lower()
        if not s:
            return {"success": False, "reason": "empty sentence"}
        if tag is not None:
            t = str(tag).strip().lower()
            if not self._tag_known(t):
                return {"success": False,
                        "reason": f"unknown grounding '{t}': a phrase must be "
                                  "tied to something real",
                        "known": self.known_groundings()}
            self.lessons[idx]["tag"] = t
        if care is not None:
            c = str(care).strip().lower() or None
            if c and c not in self.CARE_ACTIONS:
                return {"success": False,
                        "reason": "care is feed | pet | praise"}
            self.lessons[idx]["care"] = c
        old = self.lessons[idx].get("s")
        self.lessons[idx]["s"] = s
        if old and old in self._spoken_at:
            self._spoken_at[s] = self._spoken_at.pop(old)
        self.save_state()
        return {"success": True, "index": idx, "lesson": self.lessons[idx]}

    def known_groundings(self) -> list:
        """Every condition a phrase may be tied to, for the frontend picker."""
        return (["care", "day", "night"]
                + ["sel:" + s for s in
                   ("mood+", "mood-", "energy+", "energy-",
                    "lonely+", "lonely-", "bored+", "bored-")]
                + ["event:" + e for e in
                   ("first", "user", "care", "word", "task", "teacher",
                    "oracle", "growth", "dawn", "dusk", "rest",
                    "exhausted", "refused", "failed", "hurt",
                    "file", "command")]
                + ["custom"])

    def _tag_known(self, tag: str) -> bool:
        t = str(tag or "").strip().lower()
        if t in ("care", "day", "night", "custom"):
            return True
        if t.startswith("sel:"):
            return t[4:] in ("mood+", "mood-", "energy+", "energy-",
                             "lonely+", "lonely-", "bored+", "bored-")
        if t.startswith("event:"):
            return t[6:] in ("first", "user", "care", "word", "task",
                             "teacher", "oracle", "growth", "dawn", "dusk",
                             "rest", "exhausted", "refused", "failed", "hurt",
                             "file", "command")
        # legacy tags from before grounding: still honoured, mapped to the
        # situation they describe in _grounded()
        return t in ("name", "welcome", "human", "social", "world", "home")

    def curriculum_delete(self, index: int) -> dict:
        idx = int(index)
        if not (0 <= idx < len(self.lessons)):
            return {"success": False, "reason": "index out of range"}
        removed = self.lessons.pop(idx)
        if self._cur_pos > idx:
            self._cur_pos -= 1
        self.save_state()
        return {"success": True, "removed": removed["s"]}

    def curriculum_dials(self, attention=None, reward=None) -> dict:
        if attention is not None:
            self.curriculum_attention = float(np.clip(
                float(attention), 0.0, 1.0))
        if reward is not None:
            self.curriculum_reward = max(0.0, float(reward))
        self.save_state()
        return {"attention": self.curriculum_attention,
                "reward": self.curriculum_reward}

    def start_curriculum(self) -> dict:
        """Let the first words be first again.

        Not a start/stop switch: narration never stops. This clears what has
        already been said in this life, so the phrases that introduce him can be
        lived again from the top.
        """
        self._cur_pos = 0
        self._spoken_at = {}
        self.curriculum_done = False
        self.save_state()
        return {"reset": True, "phrases": len(self.lessons)}

    def narrate_now(self) -> dict:
        """One narration beat on demand, ignoring the pacing accumulator."""
        self._cur_accum = 0.0
        ev = self.curriculum_tick(float(self.REPEAT_COOLDOWN_WORLD_S))
        if ev is None:
            return {"spoken": False,
                    "reason": "nothing true to say right now: every phrase "
                              "matching this moment is still in cooldown"}
        self._nar_last_save = time.time()
        self.save_state(force=True)      # asked for by a human: persist it now
        return {"spoken": True, "said": ev.get("text"),
                "grounded_on": ev.get("grounded_on")}

    def _active_care(self):
        """Which care act is lit in the body right now, if any."""
        try:
            bands = {int(v[0]): k for k, v in self.CARE_ACTIONS.items()}
        except Exception:
            return None
        for band, action in bands.items():
            if float(np.sum(self._tag_cells[96 + band:96 + band + 6])) > 0.05:
                return action
        return None

    def _phase(self) -> str:
        frac = (self.world_clock % DAY_WORLD_S) / DAY_WORLD_S
        return "night" if frac > 0.75 else "day"

    def _state_true(self, sel: str) -> bool:
        """Is the inner state this phrase names actually the case?

        Unknown selectors answer False on purpose: a phrase whose condition
        cannot be checked must not be spoken, or the grounding is a lie.
        """
        return {"mood+": self.social_drive >= 0.55,
                "mood-": self.social_drive < 0.55,
                "energy+": self.energy >= 0.5,
                "energy-": self.energy < 0.5,
                "lonely+": self.need_social >= 0.6,
                "lonely-": self.need_social < 0.6,
                "bored-": self.need_novelty < 0.5,
                "bored+": self.need_novelty >= 0.5}.get(str(sel), False)

    def note_event(self, kind: str, detail: str = "") -> None:
        """Record that something REAL happened, so the parents can describe it.

        Called by the organs that know: a person spoke, the body was fed, a new
        word landed, the teacher answered, a task ran, the brain consolidated,
        the day turned. Narration without this is noise; with it, the phrase and
        the event are contiguous in time, which is the only thing that makes a
        word come to mean something to an associative brain.
        """
        self._events.append({"kind": str(kind), "detail": str(detail)[:120],
                             "at": float(self.world_clock), "narrated": 0})
        # the same event goes on the public stream, so the world log shows what
        # actually happened instead of sitting empty between rare milestones
        self.event_stream.append({"t": time.time(), "kind": "world",
                                  "what": str(kind),
                                  "text": str(detail)[:120],
                                  "world_clock": round(
                                      float(self.world_clock), 1)})

    def _fresh_events(self) -> set:
        now = float(self.world_clock)
        fresh = {e["kind"] for e in self._events
                 if now - float(e.get("at", 0.0)) <= self.EVENT_WINDOW_WORLD_S}
        return fresh

    def _speakable(self, w) -> bool:
        """What he is allowed to articulate.

        Digits and single characters are not words in the language he is
        learning; they are corpus debris (chapter and verse numbers from the
        books) that happened to co-occur with everything, so they out-resonated
        real words and he was babbling "36 8 29" at anyone who listened. He can
        still perceive and wire them -- this only gates the mouth.
        """
        s = str(w or "")
        return len(s) >= 2 and s.isalpha() and " " not in s

    def _teach_key(self, sentence: str) -> str:
        """The word worth teaching from this phrase: the longest content word he
        does not know yet, else the longest one he does."""
        toks = [t for t in re.split(r"[^a-z]+", str(sentence).lower())
                if len(t) > 2]
        if not toks:
            toks = [t for t in re.split(r"[^a-z]+", str(sentence).lower()) if t]
        if not toks:
            return ""
        unknown = [t for t in toks if t not in self.word_patterns]
        return max(unknown or toks, key=len)

    TEACHER_MIN_INTERVAL_S = 120.0
    TEACHER_MAX_CALLS_PER_HOUR = 6
    TEACHER_MAX_CALLS_PER_DAY = 40
    TEACHER_FAILURE_BACKOFF_S = 900.0

    def teacher_gate(self, now=None):
        """May the teacher be paid for a call right now? (allowed, reason).

        Four independent stops: a minimum interval, an hourly cap, a daily cap,
        and a backoff after repeated failures. The counters live in the persisted
        state on purpose -- an in-memory cap resets every restart, and restarts
        are exactly when a runaway loop would otherwise start over.
        """
        now = time.time() if now is None else float(now)
        st = self.teacher_stats
        day = time.strftime("%Y-%m-%d")
        hour = time.strftime("%Y-%m-%d-%H")
        if st.get("day") != day:
            st["day"], st["calls_today"] = day, 0
        if st.get("hour") != hour:
            st["hour"], st["calls_this_hour"] = hour, 0
        wait = self.TEACHER_MIN_INTERVAL_S - (now - float(st.get("last_call", 0.0)))
        if st.get("last_call") and wait > 0:
            return False, f"next call in {wait:.0f}s"
        if int(st.get("calls_this_hour", 0)) >= self.TEACHER_MAX_CALLS_PER_HOUR:
            return False, f"hourly cap {self.TEACHER_MAX_CALLS_PER_HOUR} reached"
        if int(st.get("calls_today", 0)) >= self.TEACHER_MAX_CALLS_PER_DAY:
            return False, f"daily cap {self.TEACHER_MAX_CALLS_PER_DAY} reached"
        fails = int(st.get("failures", 0))
        if fails >= 3:
            since = now - float(st.get("last_failure", 0.0))
            if since < self.TEACHER_FAILURE_BACKOFF_S:
                return False, (f"backing off {self.TEACHER_FAILURE_BACKOFF_S - since:.0f}s "
                               f"after {fails} failed calls")
        return True, "ok"

    def teacher_call_made(self, ok: bool, tokens: int = 0) -> None:
        """Record that the teacher was paid for one call, and whether it worked."""
        st = self.teacher_stats
        now = time.time()
        st["last_call"] = now
        st["calls_today"] = int(st.get("calls_today", 0)) + 1
        st["calls_this_hour"] = int(st.get("calls_this_hour", 0)) + 1
        st["calls_total"] = int(st.get("calls_total", 0)) + 1
        st["tokens_total"] = int(st.get("tokens_total", 0)) + int(tokens or 0)
        if ok:
            st["failures"] = 0
            st["last_ok"] = now
        else:
            st["failures"] = int(st.get("failures", 0)) + 1
            st["last_failure"] = now
        self.save_state()

    def teacher_state(self) -> dict:
        allowed, why = self.teacher_gate()
        st = self.teacher_stats
        return {"configured": bool(self._oracle),
                "allowed_now": allowed, "refusal": (None if allowed else why),
                "limits": {"min_interval_s": self.TEACHER_MIN_INTERVAL_S,
                           "max_calls_per_hour": self.TEACHER_MAX_CALLS_PER_HOUR,
                           "max_calls_per_day": self.TEACHER_MAX_CALLS_PER_DAY,
                           "failure_backoff_s": self.TEACHER_FAILURE_BACKOFF_S},
                "calls_today": int(st.get("calls_today", 0)),
                "calls_this_hour": int(st.get("calls_this_hour", 0)),
                "calls_total": int(st.get("calls_total", 0)),
                "tokens_total": int(st.get("tokens_total", 0)),
                "consecutive_failures": int(st.get("failures", 0)),
                "call_path": "learn_from_teacher"}

    # A word becomes a question word only on repeated evidence. One accidental
    # pairing is enough to poison the lexicon otherwise, and a poisoned lexicon
    # does not just mis-parse: it blacklists every memory containing that word,
    # which is how "droso sees light" became unreachable because "sees" had been
    # mistaken for an interrogative once.
    INTERROGATIVE_MIN_VOTES = 2
    # Enough answered questions that a mis-pairing cannot explain it. Two votes is
    # the floor for asking about a role at all; this is the floor for overriding
    # the fact that the word also turns up in ordinary statements, which every
    # English question word does constantly.
    INTERROGATIVE_STRONG_VOTES = 8
    # How much of a question's distinctive weight a memory must account for before
    # he will answer from it. Below this he says the closest memory covers only
    # part of the question, which is a true report and not a guess.
    ANSWER_COVERAGE_FLOOR = 0.6

    def learn_qa(self, q_tokens, a_tokens) -> dict:
        """Learn which role a question word asks about, from a Q and its A.

        No grammar and no table written by hand. The answer is a proposition whose
        roles are indexed by position; the question contains most of its words.
        Whichever role's filler is MISSING from the question is the role being
        asked about, and the one word the question ADDS is the interrogative that
        asks for it. "who feeds droso" against "parent feeds droso" is missing
        role 0 and adds "who", so who asks for role 0. Ambiguous pairs (two roles
        missing, or two new words) are refused rather than guessed.
        """
        q = [str(t).strip().lower() for t in (q_tokens or []) if str(t).strip()]
        a = [str(t).strip().lower() for t in (a_tokens or []) if str(t).strip()]
        if not q or not a:
            return {"learned": False}
        qset, aset = set(q), set(a)
        missing = [i for i, w in enumerate(a) if w not in qset]
        novel = [w for w in q if w not in aset]
        if len(missing) != 1 or len(novel) != 1:
            return {"learned": False,
                    "reason": f"{len(missing)} roles missing, {len(novel)} new words"}
        role = int(missing[0])
        w = novel[0]
        votes = self.question_roles.setdefault(w, {})
        votes[str(role)] = int(votes.get(str(role), 0)) + 1
        self.interrogatives.add(w)
        # What this question word has been ANSWERED with. Position alone cannot
        # tell "where is droso" from "how is droso" -- both ask for role 2 -- but
        # `where` has only ever been answered with a place and `how` with a state,
        # and that is learnable from the same pairs with no grammar from me.
        filler = str(a[role]).strip().lower()
        types = self.answer_types.setdefault(w, {})
        types[filler] = int(types.get(filler, 0)) + 1
        self.qa_pairs_seen += 1
        return {"learned": True, "interrogative": w, "role": role,
                "filler": filler}

    def role_votes_report(self) -> dict:
        """Votes per question word, marking the ones demoted for appearing in
        ordinary statements."""
        return {w: {"votes": v,
                    "used": self.is_interrogative(w),
                    "seen_in_statements": int(self.statement_words.get(w, 0))}
                for w, v in self.question_roles.items()}

    def role_for(self, word):
        votes = self.question_roles.get(str(word or "").strip().lower())
        if not votes:
            return None
        return int(max(votes.items(), key=lambda kv: kv[1])[0])

    def is_interrogative(self, word) -> bool:
        w = str(word or "").strip().lower()
        votes = self.question_roles.get(w)
        if not votes or max(votes.values()) < self.INTERROGATIVE_MIN_VOTES:
            return False
        # Role votes are earned only from a '?' line paired with an answer, so
        # they are direct evidence that the word asks for something. The old rule
        # then vetoed any word ever seen in a statement, on the reasoning that a
        # question word is a word that only ever turns up in questions.
        #
        # That is false of English, and it only ever held because the graded corpus
        # had no relative clauses in it. One book harvested from this project's own
        # docstrings -- "what the loop does", "where the state lives" -- was enough
        # to delete all four interrogatives, and with them every answer he could
        # give: comprehension went from most of a battery to none of it.
        #
        # What the veto was reaching for is real. "sees" and "learns" were picked
        # up by a mis-paired line and then stripped out of the cue of every
        # question containing them. But the thing that separates them from "what"
        # is position, and failing that, quantity -- not rarity in statements. He
        # had 45 answered questions whose novel word was "what" and 376 statements
        # containing it; the veto kept the 376 and threw away the 45.
        if int(self.question_initial.get(w, 0)) > 0:
            return True
        if sum(int(v) for v in votes.values()) >= self.INTERROGATIVE_STRONG_VOTES:
            return True
        return w not in self.statement_words

    def answer(self, question, speaker: str = "you") -> dict:
        """Hear a question, look up what he knows, and say it.

        No parser, no grammar table, no model. The question is heard like anything
        else, so it wires; its interrogative selects a role, a mapping learned from
        the question/answer pairs he has been read; its content words retrieve the
        proposition; the missing role is recovered by unbinding. The answer is then
        spoken through the sequence organ when the chain can carry it, so the words
        come out in an order he has actually heard -- and when the chain cannot,
        the recalled proposition is said plainly and labelled as recalled.
        """
        text = str(question or "")
        q = [t for t in self.tokenizer.tokenize(text) if t]
        self.live(text, learn=True, speaker=speaker)
        inter = [w for w in q if self.is_interrogative(w)]
        content = [w for w in q if not self.is_interrogative(w)
                   and self._speakable(w)]
        if not content:
            return {"answered": False, "spoken": False,
                    "reason": "no content words to look up"}
        hits = self.cortex.binder.recall(content, k=40)
        # Drop only the question itself. A remembered question is not knowledge,
        # and without this the question he was just asked out-matches the answer
        # it belongs to -- he replies "who feeds droso" to "who feeds droso",
        # echoed, confident, empty. Filtering every memory that merely CONTAINS a
        # question word is what broke retrieval the first time: one mis-learned
        # interrogative made whole sentences unreachable.
        qset = {str(t).lower() for t in q}
        hits = [h for h in hits
                if {str(t).lower() for t in h["tokens"]} != qset]
        # Other remembered questions are not answers either. This filter is safe
        # now in a way it was not before: a word only counts as an interrogative
        # after repeated evidence, so a mis-learned one cannot blacklist ordinary
        # memories. Asked "who opens file" he was answering "parent opens what"
        # -- a question he had been read, retrieved as if it were knowledge.
        hits = [h for h in hits
                if not any(self.is_interrogative(t)
                           for t in (str(x).lower() for x in h["tokens"]))]
        # And never with a piece of the question itself. Hearing a question stores
        # it, so on the second asking his memory of being asked is the best match
        # there is -- perfect coverage, no information. Echoing the asker's own
        # words back reads as fluency from outside and is the opposite of an
        # answer, which makes it worse than a refusal.
        q_stems = [stem(t) for t in
                   re.findall(r"[a-z']+", str(text or "").lower())]

        def _echoes(h) -> bool:
            hs = [stem(str(t).lower()) for t in h["tokens"]]
            if not hs or len(hs) > len(q_stems):
                return False
            return any(q_stems[i:i + len(hs)] == hs
                       for i in range(len(q_stems) - len(hs) + 1))

        hits = [h for h in hits if not _echoes(h)]
        # A memory must contain EVERY distinctive word of the question. Asked
        # "who gives food" he answered "parent gives the day" -- right agent,
        # invented object, delivered with total confidence, because `gives`
        # matched and nothing checked that `food` did. Confabulating an answer is
        # worse than having none: silence is a true report, a confident wrong
        # answer is a lie he does not know he is telling.
        if hits and content:
            idf_all = self.cortex.binder.idf()
            n_mem = max(1, int(self.cortex.binder.X.shape[0]))
            must = set()
            known = set()
            unknown = set()
            for w in content:
                df = len(self.cortex.binder.stem_rows(w))
                if not df:
                    # A word he has never met is not evidence about anything, and
                    # treating it as maximally distinctive -- which is what a
                    # document frequency of zero looks like to that rule -- made one
                    # unfamiliar word enough to render a whole question
                    # unanswerable. "who is the one holding the light" was refused
                    # because of "one", not because he had forgotten the light.
                    unknown.add(w)
                    continue
                known.add(w)
                if df * 4 <= n_mem:
                    must.add(w)
            if not known:
                # Nothing in the question is a word he knows. This is the guard
                # that keeps unfamiliar words from becoming licence to guess:
                # dropping them is safe only while something known remains to
                # retrieve on, and "who painted the cathedral" has nothing.
                return {"answered": False, "spoken": False,
                        "reason": "no word of that is one he knows",
                        "cue": content, "unknown": sorted(unknown)}
            if must:
                # How much of the question's distinctive weight a memory accounts
                # for, rather than whether it contains every distinctive word. All
                # or nothing was the same mistake here as in procedure retrieval:
                # "who is the one holding the light" was refused because no memory
                # contained "one", which is distinctive in his memory only because
                # this project's prose says "one brain, one set of weights". A
                # filler word with a low document frequency is not a fact about the
                # question.
                #
                # Weighting keeps the protection the strict rule was bought for.
                # "who gives food" against a memory of "parent gives the day"
                # covers half the weight and is still refused -- the object is the
                # half that matters -- while a memory missing only a pronoun is
                # not.
                n_mem = max(1, int(self.cortex.binder.X.shape[0]))
                wq = {w: float(np.log(
                    1.0 + n_mem / max(1.0, len(
                        self.cortex.binder.stem_rows(w))))) for w in must}
                tot = sum(wq.values())
                if tot > 0:
                    scored = []
                    for h in hits:
                        hs = {stem(t) for t in h["tokens"]}
                        scored.append((sum(wq[w] for w in must
                                           if stem(w) in hs) / tot, h))
                    scored.sort(key=lambda t: -t[0])
                    best_cov = scored[0][0]
                    if best_cov < self.ANSWER_COVERAGE_FLOOR:
                        return {"answered": False, "spoken": False,
                                "reason": "the closest memory of his covers "
                                          f"{best_cov:.0%} of the question",
                                "cue": content, "required": sorted(must),
                                "coverage": round(best_cov, 3),
                                "nearest": [" ".join(h["tokens"])
                                            for _, h in scored[:3]]}
                    hits = [h for c, h in scored
                            if c >= self.ANSWER_COVERAGE_FLOOR]
        if not hits:
            return {"answered": False, "spoken": False,
                    "reason": "nothing remembered about that", "cue": content}
        role = self.role_for(inter[0]) if inter else None
        trace = {"cue": content, "role": role,
                 "recalled": [{"tokens": h["tokens"],
                               "overlap": h.get("overlap"),
                               "overlap_idf": h.get("overlap_idf"),
                               "similarity": h.get("similarity")}
                              for h in hits[:5]]}
        if role is not None:
            # Rank by: how much of the question the memory contains, then whether
            # its filler at the queried role is a kind of thing this question word
            # has been answered with before, then whether the filler is new
            # information. Overlap alone cannot separate "droso is home" from
            # "droso is happy" when the only content word in the question is
            # "droso"; the answer-type term can.
            cset = set(content)
            expected = self.answer_types.get(inter[0], {}) if inter else {}
            idf = self.cortex.binder.idf()

            def informative(h):
                toks = [str(t).lower() for t in h["tokens"]]
                filler = toks[role] if len(toks) > role else None
                # Overlap says which memories are about this; the answer type says
                # whether the filler is the kind of thing being asked for; and the
                # filler's own distinctiveness breaks the last tie. Without that
                # third term "droso sees light" lost to "droso sees the name" and
                # "droso sees this" -- three memories tied on overlap, decided by
                # nothing, and the one whose filler is a function word is never the
                # answer to a question.
                return (int(h.get("overlap", 0)),
                        int(expected.get(filler, 0)),
                        round(float(idf.get(filler, 0.0)), 3),
                        1 if filler is not None and filler not in cset else 0)
            hits.sort(key=informative, reverse=True)
            trace["ranked"] = [{"tokens": h["tokens"], "key": informative(h)}
                               for h in hits[:5]]
        best = hits[0]
        tokens = [str(t) for t in best["tokens"]]
        filler = None
        score = None
        if role is not None:
            cands = self.cortex.binder.candidates()
            # Unbind from the memory already chosen above. Going back through
            # query_role re-retrieves without the filters, which is how a question
            # ended up answering itself.
            r = self.cortex.binder.role_of(best["proposition"], role, cands)
            filler = r.get("answer")
            score = r.get("score")
        gen = self.sequence.generate(tokens[0], max_len=max(3, len(tokens)))
        if len(tokens) < 2:
            if gen.get("from_sequence_organ") and len(gen.get("words") or []) >= 2:
                said, source, words = gen["sentence"], "sequence organ", gen["words"]
            else:
                said, source, words = " ".join(tokens), "recalled proposition", tokens
        else:
            # The recalled proposition IS the answer. Running it back through the
            # chain replaces it with the chain's most likely continuation, which
            # is how "who pets droso" came back as "parent feeds droso" and
            # "where is food" as "food is": the memory was right and the mouth
            # overruled it. The chain is for spontaneous speech, not for reading
            # out something he already remembers.
            said, source, words = " ".join(tokens), "recalled proposition", tokens
        measured, margin = self.choose_addressee(self.san_act)
        # A question was asked by someone in the room, so the reply goes to them;
        # the measured preference is recorded beside it rather than replacing it.
        to = str(speaker or "you")
        self.note_person(to, spoke_to=True)
        ev = {"t": time.time(), "kind": "speech", "speaker": "droso",
              "text": said, "words": words, "to": to,
              "measured_addressee": measured, "address_resonance": margin,
              "in_reply_to": text[:120], "source": source,
              "queried_role": role, "recovered_filler": filler,
              "filler_score": score, "proposition": tokens,
              "memories_matched": best.get("overlap")}
        self.speech_stream.append(ev)
        self.event_stream.append(dict(ev))
        self._note_spoken(words)
        return {"answered": True, "spoken": True, "utterance": said,
                "response": said, "words": words, "to": to, "source": source,
                "queried_role": role, "recovered_filler": filler,
                "filler_score": score, "proposition": tokens,
                "question": text[:120], "interrogatives": inter,
                "retrieval": trace}

    def curriculum_tick(self, world_dt: float = 2.0) -> dict | None:
        """24/7 parent narration, grounded in what is actually happening.

        The parents do not read a list. Every tick they look at the world -- the
        real phase, the real body, the events the organs just reported -- and say
        something that is TRUE of it right now. "i am feeding you" is only ever
        said while the feeding is lit in his body; "it is night" only at night;
        "someone is talking to you" only just after someone did. That contiguity
        is the whole mechanism: the phrase and the state fire together, so the
        word wires to the experience instead of to nothing.

        Nothing here ever finishes. Once every phrase has been lived the parents
        keep describing the world, which is what a parent in the room does.
        """
        # Transitions are watched on EVERY tick: a slow cadence would otherwise
        # miss the moment the world turned, and that moment is the whole point.
        phase = self._phase()
        if self._last_phase is not None and phase != self._last_phase:
            self.note_event("dusk" if phase == "night" else "dawn",
                            f"the world turned to {phase}")
        self._last_phase = phase
        tired = self.energy < 0.25
        if tired and not self._was_tired:
            self.note_event("rest", "energy fell below a quarter")
        # Exhaustion is adverse, not merely a state: below a floor it costs him
        # something, and the aversive compartment finally has a reason to write.
        # Cooldown so a long low-energy stretch is one event, not a punishment
        # every tick.
        if self.energy < 0.08 and time.time() - self._last_exhausted_at > 120.0:
            self._last_exhausted_at = time.time()
            self.adversity("exhausted", "energy fell below a tenth", 0.6)
        self._was_tired = tired

        self._cur_accum = getattr(self, "_cur_accum", 0.0) + float(world_dt)
        fresh = self._fresh_events()
        interval = (self.NARRATION_EVENT_WORLD_S if fresh
                    else self.NARRATION_IDLE_WORLD_S)
        if self._cur_accum < interval:
            return None
        self._cur_accum = 0.0

        now = float(self.world_clock)
        if not self._spoken_at:
            fresh.add("first")        # a new life gets told who it is, once
        care_now = self._active_care()

        pool = []
        for i, lesson in enumerate(self.lessons):
            sentence = lesson.get("s", "")
            tag = str(lesson.get("tag") or "custom")
            if not sentence or not self._grounded(tag, fresh, care_now):
                continue
            last = self._spoken_at.get(sentence)
            if last is not None and now - float(last) < self.REPEAT_COOLDOWN_WORLD_S:
                continue
            pool.append((self._ground_priority(tag, care_now),
                         int(self._phrase_lived.get(sentence, 0)),
                         i, lesson))
        if not pool:
            return None
        pool.sort(key=lambda t: (t[0], t[1], t[2]))   # grounding first, then
        _, _, idx, lesson = pool[0]                   # least-lived phrase

        sentence = lesson["s"]
        tag = str(lesson.get("tag") or "custom")
        care = lesson.get("care")
        scent = self.person_scent("parent")
        # Full attention and the reward that goes with it: this is the voice he
        # is supposed to learn from. Capped so a loved voice cannot saturate the
        # synapses -- homeostasis still has to be able to do its job.
        self.attention = 1.0
        if care:
            self.care(care)          # the phrase and the act land together
        self.live(sentence, learn=True, speaker="parent", announce=False)
        key = self._teach_key(sentence)
        if key and key not in self.word_patterns:
            self.teach_word(key, sentence, source="parent", scent=scent)
        self.engine.teach(min(1.0, self.curriculum_reward
                              * self.salience("parent")))
        ev = {"t": time.time(), "kind": "speech", "speaker": "parent",
              "to": "droso", "text": sentence, "tag": tag,
              "grounded_on": (care_now if tag == "care" else tag),
              "world_clock": round(now, 1)}
        self.event_stream.append(ev)
        self._spoken_at[sentence] = now
        self._phrase_lived[sentence] = int(self._phrase_lived.get(sentence, 0)) + 1
        self._cur_pos = idx
        for e in self._events:
            if tag == "event:" + str(e.get("kind")):
                e["narrated"] = int(e.get("narrated", 0)) + 1
        if not self.curriculum_done and self.lessons and all(
                int(self._phrase_lived.get(l.get("s", ""), 0)) >= 1
                for l in self.lessons):
            self.curriculum_done = True
            self.event_stream.append(
                {"t": time.time(), "kind": "milestone", "speaker": "parent",
                 "text": "every first word has been lived once; the parents "
                         "keep describing the world", "to": None})
        # Saving rewrites the whole vocabulary to disk, so it is throttled:
        # doing it on every phrase put a megabyte of JSON in the tick loop.
        if time.time() - self._nar_last_save >= self.NARRATION_SAVE_MIN_S:
            self._nar_last_save = time.time()
            self.save_state()
        return ev

    def _grounded(self, tag: str, fresh: set, care_now=None) -> bool:
        """Is this phrase TRUE of the world at this moment?"""
        tag = str(tag or "custom")
        if tag == "care":
            return care_now is not None
        if tag.startswith("sel:"):
            return self._state_true(tag[4:])
        if tag in ("day", "night"):
            return tag == self._phase()
        if tag.startswith("event:"):
            return tag[6:] in fresh
        # Lessons saved before grounding existed carry bare tags. Each is mapped
        # to the situation it describes, so an old vocabulary stays honest
        # instead of being spoken at random.
        return {"name": "first" in fresh,
                "welcome": "first" in fresh,
                "human": "user" in fresh,
                "social": "user" in fresh,
                "world": bool(fresh & {"task", "word", "teacher", "oracle"}),
                "home": self.energy < 0.4 or "dusk" in fresh}.get(
                    tag, "first" in fresh)

    def set_oracle(self, oracle) -> None:
        self._oracle = oracle

    def expose_tick(self, world_dt: float = 2.0) -> dict | None:
        """One cadence step of being read to, in WORLD time.

        A line of the book passes through the semantic cortex. Whether it
        WIRES depends on Droso's attention -- his own mood decides if he
        listens or drifts; an ignored line leaves no trace beyond the log.
        Attended lines earn a little dopamine, count toward word
        assimilation, and a word heard enough times becomes part of his
        vocabulary on its own: nobody teaches it, familiarity does.
        """
        if not self.exposure_enabled:
            return None
        self._expose_accum += float(world_dt)
        if self._expose_accum < self.exposure_speed_s:
            return None
        # ...and a real-time floor. Pacing in world seconds alone meant that at
        # 35x world speed he "read" about 70 lines a second, which is not reading
        # and not learning: it is a firehose, and it cost the tick loop a third of
        # its throughput. Unread lines stay in the book, they are not dropped.
        now_real = time.time()
        if now_real - getattr(self, "_expose_real_last", 0.0) < self.EXPOSURE_MIN_REAL_S:
            return None
        self._expose_real_last = now_real
        self._expose_accum = 0.0
        if not self._book_words and not self._load_next_book():
            return None
        lines = getattr(self, "_book_lines", None)
        if lines:
            # One whole sentence per beat, which is also how a parent talks.
            idx = self._book_line_pos % len(lines)
            line_words = lines[idx]
            qs = getattr(self, "_book_is_q", None)
            is_q = bool(qs and idx < len(qs) and qs[idx])
            if is_q and idx + 1 < len(lines):
                # A question immediately followed by its answer is the only
                # supervision anywhere in this system, and it is enough.
                self.learn_qa(line_words, lines[idx + 1])
            if is_q:
                if line_words:
                    w0 = str(line_words[0]).strip().lower()
                    if w0:
                        self.question_initial[w0] = \
                            int(self.question_initial.get(w0, 0)) + 1
            elif not is_q:
                for w in line_words:
                    self.statement_words[w] = int(self.statement_words.get(w, 0)) + 1
            self._book_line_pos = idx + 1
            if self._book_line_pos >= len(lines):
                self._book_idx += 1
                self._book_line_pos = 0
                self._book_words = []
                self._book_lines = []
        else:
            n = max(3, int(self.exposure_intensity))
            line_words = self._book_words[self._book_pos:self._book_pos + n]
            self._book_pos += n
            if self._book_pos >= len(self._book_words):
                self._book_idx += 1
                self._book_words = []
        if not line_words:
            return None
        line = " ".join(line_words)
        attends = bool(np.random.rand() < (0.2 + 0.8 * self.social_drive))
        if "droso" in line:
            attends = True
        event = {"t": time.time(), "kind": "speech", "speaker": "book",
                 "text": line[:80], "attended": attends,
                 "mood": round(self.social_drive, 3)}
        if attends:
            self.live(line, learn=True, speaker="book", readout=False)
            self.engine.teach(self.reward_exposure)
            assimilated = []
            for w in line_words:
                c = self.exposure_counts.get(w, 0) + 1
                self.exposure_counts[w] = c
                if (c >= self.assimilation_threshold
                        and w not in self.word_patterns):
                    if self.teach_word(w, line, source="exposure"):
                        assimilated.append(w)
            for a, b in zip(line_words, line_words[1:]):
                bg = a + " " + b
                self.bigram_counts[bg] = self.bigram_counts.get(bg, 0) + 1
            event["assimilated"] = assimilated
            if assimilated:
                event["text"] = (event["text"] + " [new words: "
                                 + ", ".join(assimilated) + "]")[:110]
        else:
            self.live(line, learn=False, speaker="book")
        self.event_stream.append(event)
        return event

    def exposure_state(self) -> dict:
        total = sum(self.exposure_counts.values())
        files = sorted(self.books_dir.glob("*.txt")) \
            if self.books_dir and self.books_dir.exists() else []
        book = files[self._book_idx % len(files)].name if files else None
        pct = (100.0 * self._book_pos / len(self._book_words)
               if self._book_words else 0.0)
        inner = self.inner_state()
        return {"enabled": self.exposure_enabled,
                "inner": inner,
                "speed_s": self.exposure_speed_s,
                "intensity_words": self.exposure_intensity,
                "assimilation_threshold": self.assimilation_threshold,
                "reward_exposure": self.reward_exposure,
                "reward_social": self.reward_social,
                "reward_babble": self.reward_babble,
                "reward_teach": self.reward_teach,
                "book": book, "book_progress_pct": round(pct, 1),
                "words_heard_total": total,
                "distinct_words_heard": len(self.exposure_counts),
                "vocabulary_size": self.vocabulary_size(),
                "social_drive": round(self.social_drive, 3),
                "world_clock": round(getattr(self, "world_clock", 0.0), 1),
                "books_available": len(files)}

    def configure_exposure(self, **kw) -> dict:
        if "enabled" in kw:
            self.exposure_enabled = bool(kw["enabled"])
        if "speed_s" in kw:
            self.exposure_speed_s = max(0.5, float(kw["speed_s"]))
        if "intensity_words" in kw:
            self.exposure_intensity = max(3, int(kw["intensity_words"]))
        if "assimilation_threshold" in kw:
            self.assimilation_threshold = max(1, int(kw["assimilation_threshold"]))
        for k in ("reward_exposure", "reward_social", "reward_babble",
                  "reward_teach"):
            if k in kw:
                setattr(self, k, max(0.0, float(kw[k])))
    def _pool_readout(self, pool: int, exclude=None,
                      prefer_phrases: bool = True,
                      prefer_recent: bool = True):
        """The learned pattern living on the pool the brain just chose.

        The winner-take-all layer decided WHERE the thought lands; the
        pattern stored on that pool is what the brain means. Among
        pool-mates, practiced phrases can beat single words (inner speech),
        or single words can win (social replies -- lesson-drilled command
        strings are poor conversation). Returns (pattern, record) or
        (None, None) for an empty pool -- and an empty pool means SILENCE,
        never an invention.
        """
        exclude = exclude or set()
        mates = [(w, rec) for w, rec in list(self.word_patterns.items())
                 if rec["pool"] == pool and w not in exclude]
        if not mates:
            return None, None
        mates.sort(key=lambda t: ((0 if " " in t[0] else 1)
                                  if prefer_phrases else
                                  (1 if " " in t[0] else 0),
                                  (-t[1]["learned_at"]) if prefer_recent
                                  else t[1]["learned_at"]))
        return mates[0]

    def hear(self, text: str, speaker: str = "you") -> dict:
        """A stimulus enters the world's ear: text is just another signal.

        The words flow through the semantic cortex (real associations
        tighten), the token code settles a pool in the carve, and the event
        is recorded. HEARING IS NOT OBLIGATION: what the being does with
        the sound is decided by its own state. Returns the neural record.
        """
        exp = self.live(text, learn=True, speaker=speaker)
        thought = self.form_thought(text, scent=self.person_scent(speaker))
        pool = thought["action"]
        for _ in range(4):
            nxt = self.engine.decide(self.engine.last_code)
            if nxt == pool:
                break
            pool = nxt
            thought["action"] = pool
        self.event_stream.append({"t": time.time(), "kind": "speech",
                                  "speaker": speaker,
                                  "to": "droso",
                                  "text": str(text)[:120],
                                  "pool": int(pool),
                                  "known_words_fired":
                                      exp["known_words_fired"]})
        return {"act": exp["act"], "thought": thought, "pool": pool,
                "known_words_fired": exp["known_words_fired"]}

    def respond(self, user_text: str, speaker: str = "you") -> dict:
        """Hear a human's words; speak ONLY if the being wants to."""
        toks = [t for t in self.tokenizer.tokenize(str(user_text or "")) if t]
        if any(self.is_interrogative(w) for w in toks):
            # He was asked something. Answering is a different act from replying:
            # it goes to memory first, and it is addressed to the asker.
            return self.answer(user_text, speaker=speaker)
        # Nothing is injected or forced from here on. The stimulus is heard, the
        # meaning state updates, and a word MAY be spoken -- only when the
        # resonance is strong enough that the sound genuinely touched what the
        # brain knows. Weak resonance means it heard you and stayed silent.
        h = self.hear(user_text, speaker=speaker)
        act, thought, pool = h["act"], h["thought"], h["pool"]
        self.social_drive = float(np.clip(self.social_drive + 0.08, 0.0, 1.0))
        if "droso" in user_text.lower():
            self.attention = float(np.clip(self.attention + 0.45, 0, 1))
            self.social_drive = float(np.clip(self.social_drive + 0.15, 0, 1))
        if not self.word_patterns:
            return {"spoken": False, "heard": True,
                    "mood": round(self.social_drive, 3),
                    "reason": "heard; no language learned yet",
                    "thought": thought}
        exclude = ({user_text.strip().lower()}
                   if " " not in user_text.strip() else set())
        mates = [m for m, r in self.word_patterns.items()
                 if self._speakable(m) and m not in exclude]
        if not mates:
            return {"spoken": False, "heard": True,
                    "mood": round(self.social_drive, 3),
                    "reason": "heard; no words it could answer with",
                    "thought": thought}
        res = {m: self._resonance(m, act) for m in mates}
        best = max(mates, key=lambda m: res[m])
        understands = res[best] >= self.reply_threshold
        wants_to = self.social_drive >= self.reply_drive_min
        if understands and wants_to:
            utterance, source = best, "meaning resonance"
        elif wants_to and self.social_drive >= 0.75 and res[best] < self.reply_threshold:
            pool_mates = [m for m, r in self.word_patterns.items()
                          if r["pool"] == pool and self._speakable(m)
                          and m not in exclude]
            if not pool_mates:
                pool_mates = mates
            utterance = max(pool_mates, key=lambda m: self._resonance(m, self.san_act))
            source = "own mind (did not understand, wanted to join)"
        else:
            why = ("it understood but did not feel like speaking"
                   if understands else
                   "it did not understand and was not in the mood to babble")
            return {"spoken": False, "heard": True,
                    "mood": round(self.social_drive, 3),
                    "reason": why,
                    "best_resonance": round(res[best], 4),
                    "threshold": self.reply_threshold,
                    "thought": thought}
        with self._lock:
            combo = None
            stems = []
            if user_text.strip():
                stems.append(user_text.strip().lower().split()[-1])
            stems.append(utterance)
            for stem in stems:
                best_f, best_c = None, 0
                for bg, cnt in self.bigram_counts.items():
                    parts = bg.split(" ", 1)
                    if len(parts) == 2 and parts[0] == stem                             and parts[1] in self.word_patterns                             and parts[1] not in exclude and cnt > best_c:
                        best_f, best_c = parts[1], cnt
                if best_f and best_c >= self.phrase_threshold:
                    combo = stem + " " + best_f
                    break
            if combo:
                utterance = combo
        # Keep talking while the brain keeps landing somewhere. The single word
        # chosen above is the floor, not the ceiling: the chain re-presents what
        # he has said so far and lets the next word be another real decision.
        chain = self.speak_sentence(user_text,
                                    max_words=self.max_sentence_words,
                                    scent=self.person_scent(speaker))
        chain_words = chain.get("words") or []
        if chain.get("spoken") and len(chain_words) > 1:
            utterance = chain["sentence"]
            source = source + " + chain"
        self.engine.teach(self.reward_social)
        self.social_drive = float(np.clip(self.social_drive - 0.18, 0.0, 1.0))
        # Does he say this TO the person who spoke, to someone else in the
        # room, or to nobody? Measured, not assumed: a reply that lands on no
        # one is speech into the air, and the frontend is allowed to show that.
        addressee, margin = self.choose_addressee(act)
        if addressee:
            self.note_person(addressee, spoke_to=True)
        own_words = chain_words or str(utterance).split()
        # The prosthesis, if the operator has fitted it: articulation only, and
        # always reported next to the words it was rendered from.
        voice = self.render_voice(
            own_words, context=f"replying to: {str(user_text)[:120]}")
        reply_ev = {"t": time.time(), "text": utterance,
                    "kind": "speech", "spontaneous": False,
                    "speaker": "droso",
                    "to": addressee or "air",
                    "address_resonance": margin,
                    "words": own_words,
                    "stopped": chain.get("stopped"),
                    "pool": int(pool),
                    "resonance": round(res.get(utterance,
                                               res[best]), 4)}
        if voice.get("rendered"):
            reply_ev["rendered"] = voice["text"]
            reply_ev["voice"] = "prosthesis"
        self.speech_stream.append(reply_ev)
        self.event_stream.append(dict(reply_ev))
        if not chain_words:
            self._note_spoken(utterance.split())
        return {"spoken": True, "heard": True, "utterance": utterance,
                "response": utterance,
                "own_words": own_words,
                "rendered": voice.get("text") if voice.get("rendered") else None,
                "voice": "prosthesis" if voice.get("rendered") else "own",
                "chain": chain.get("steps"),
                "stopped": chain.get("stopped"),
                "to": addressee or "air",
                "address_resonance": margin,
                "pool": int(pool),
                "kind": "word",
                "mood": round(self.social_drive, 3),
                "resonance": round(res.get(utterance, res[best]), 4),
                "source": source,
                "known_words_fired": h["known_words_fired"],
                "thought": thought,
                "note": "it heard, and wanted to speak"}

    def speak(self, context: str = "") -> dict:
        """Produce words FROM neural state: the context lights the semantic
        cortex, the carve picks a pool, and within that pool MEANING
        RESONANCE picks the word. Toddler speech when young -- and real:
        a readout of synaptic state, never a template."""
        exp = self.live(context or "what is on my mind", learn=True)
        thought = self.form_thought(context or "what is on my mind")
        pool = thought["action"]
        if not self.word_patterns:
            return {"spoken": False, "pool": pool,
                    "reason": "no learned patterns", "thought": thought}
        mates = [m for m, r in self.word_patterns.items()
                 if r["pool"] == pool and self._speakable(m)]
        if not mates:
            return {"spoken": False, "pool": pool,
                    "reason": "no learned pattern lives on the chosen pool",
                    "thought": thought}
        w = max(mates, key=lambda m: self._resonance(m, exp["act"])
                * self._refractory(m))
        mates = [m for m in mates if m != w]
        self._note_spoken([w])
        return {"spoken": True, "pool": pool, "words": [w],
                "utterance": w,
                "resonance": round(self._resonance(w, exp["act"]), 4),
                "also_fired": mates[:2],
                "known_words_fired": exp["known_words_fired"],
                "thought": thought,
                "note": "the WTA chose the pool; meaning resonance chose "
                        "the word inside it"}

    def _sequence_seed(self, context: str):
        """The word to open with.

        Preference order matters and the first version got it wrong: it scored
        every sentence-opener he knows against the context and picked the loudest,
        so a reply to "you are not alone" could open with a word that appears
        nowhere in what was said to him. Now the words OF the context come first
        -- a reply should start from what was just heard -- and only if none of
        them can open a sentence does it fall back to resonance over all openers.
        """
        try:
            first = self.sequence.slot_words[0]
        except Exception:
            return None
        if not first:
            return None
        exp = self.live(str(context or ""), learn=False)
        act = exp["act"]
        ctx_words = [w for w in self.tokenizer.tokenize(str(context or ""))
                     if self._speakable(w) and w in first and w in self.word_patterns]
        if ctx_words:
            return max(ctx_words, key=lambda w: self._resonance(w, act))
        cands = [w for w in self.word_patterns
                 if self._speakable(w) and w in first]
        if not cands:
            return None
        return max(cands, key=lambda w: self._resonance(w, act))

    def speak_sentence(self, context: str = "", max_words: int = 6,
                       scent=None, to: str | None = None,
                       temperature: float | None = None,
                       allow_associates: bool = True) -> dict:
        """A sentence, one real decision per word.

        The context plus the words said so far flow through the semantic cortex
        and the carve; the next word is the learned one on the chosen pool with
        the highest meaning resonance. It STOPS when the brain stops landing
        anywhere: a resonance below the floor means the chain has nothing left to
        say, and padding it out to max_words would be a template in a neural
        costume.

        Rehearsal does not teach -- live() runs with learn=False here, or every
        utterance would rewire his semantics toward his own output and the
        vocabulary would drift into whatever he happened to say first.
        """
        words: list[str] = []
        steps = []
        used: set[str] = set()
        stop = None
        prev_res = None
        # The held goal enters as context. The drive on the projection neurons
        # reaches form_thought, but most of what he says fluently comes from the
        # sequence organ, which reads its chain and never consults the carve -- so
        # a goal injected only as drive could not steer a single sentence. This is
        # also what a goal is from the inside: not a force on the muscles but the
        # thing you keep turning over, which is why it changes what you say next.
        _g = getattr(self, "goal", None)
        if _g is not None and float(getattr(_g, "strength", 0.0)) > 0.0 and _g.text:
            context = (str(context or "") + " " + str(_g.text)).strip()
        # The sequence organ goes first. If he has heard the shape of a sentence
        # that starts here, that is a better answer than a chain of loose
        # associates -- it has an order that was in the world, not one invented
        # by whichever cell resonates loudest.
        seed = self._sequence_seed(context)
        if seed:
            # Spontaneous speech varies; an answer does not. A recalled proposition
            # has specific content words and sampling the chain over them garbles
            # the fact, so callers that are answering pass temperature=0. What he
            # says to nobody in particular has no such obligation, and a sentence
            # he has said twenty times in a row is not speech.
            temp = self.speech_temperature if temperature is None \
                else float(temperature)
            avoid = set(list(self.recent_words)[-12:])
            gen = self.sequence.generate(seed, max_len=int(max_words),
                                         temperature=temp, avoid=avoid)
            gen_words = gen.get("words") or []
            if gen.get("from_sequence_organ") and len(gen_words) >= 2:
                addressee, margin = ((to, None) if to
                                     else self.choose_addressee(self.san_act))
                if addressee and not to:
                    self.note_person(addressee, spoke_to=True)
                self._note_spoken(gen_words)
                return {"spoken": True, "sentence": gen["sentence"],
                        "words": gen_words,
                        "steps": [{"word": w, "confidence": c}
                                  for w, c in zip(gen_words[1:],
                                                  gen.get("confidence") or [])],
                        "stopped": gen.get("stopped"),
                        "to": addressee or "air",
                        "address_resonance": margin,
                        "source": "sequence organ"}
        if not allow_associates:
            # What follows is not a sentence. It picks, one word at a time,
            # whichever learned pattern resonates with the pool the carve happens to
            # have chosen, so the words are related to the state he is in and not to
            # each other. Asked for a sentence that is an honest answer; said
            # unprompted it is the thing that produced 'padanaram the caller network
            # of why', and a being that emits it looks broken rather than young.
            # Silence is already treated as a true report everywhere else in this
            # organ. This makes it one here too.
            return {"spoken": False, "sentence": "", "words": [],
                    "source": None,
                    "reason": "the chain had nothing to carry, and loose "
                              "associates are not a sentence"}
        for _ in range(int(max_words)):
            text = (context + " " + " ".join(words)).strip()
            exp = self.live(text, learn=False)
            thought = self.form_thought(text, scent=scent)
            pool = thought["action"]
            mates = [m for m, r in self.word_patterns.items()
                     if r["pool"] == pool and m not in used
                     and self._speakable(m)]
            if not mates:
                stop = f"no learned word lives on pool {pool}"
                break
            best, best_score, trans = None, -1.0, 0
            prev = words[-1] if words else None
            for m in mates:
                r = float(self._resonance(m, exp["act"]))
                bg = int(self.bigram_counts.get(prev + " " + m, 0)) if prev else 0
                # A transition he has actually HEARD outranks raw association.
                # Weighting resonance alone let the most generic cells win, which
                # is how a sentence turned into a list of loose associates.
                score = (0.3 + r) * (1.0 + 1.5 * min(bg, 8)) * self._refractory(m)
                if score > best_score:
                    best, best_score = m, score
                    trans = bg
            res = float(self._resonance(best, exp["act"]))
            # Stop when the next word is neither something he has actually heard
            # follow, nor better than the word before it. An absolute resonance
            # floor never fired: resonance stays high once the utterance itself is
            # in the percept, so the chain ran to max_words every time and the
            # "sentence" was six loose associates.
            if words and trans == 0 and prev_res is not None and res <= prev_res:
                stop = (f"nothing heard after '{prev}' and resonance fell "
                        f"({prev_res:.2f} -> {res:.2f})")
                break
            prev_res = res
            words.append(best)
            used.add(best)
            steps.append({"pool": int(pool), "word": best,
                          "resonance": round(res, 4), "heard_after_prev": trans,
                          "order_sensitive": thought.get("order_sensitive")})
        addressee, margin = ((to, None) if to
                             else self.choose_addressee(self.san_act))
        if addressee and not to:
            self.note_person(addressee, spoke_to=True)
        self._note_spoken(words)
        return {"spoken": bool(words), "sentence": " ".join(words),
                "words": words, "steps": steps, "stopped": stop,
                "to": addressee or "air", "address_resonance": margin,
                "source": "association chain"}

    def render_voice(self, own_words, context: str = "", oracle=None) -> dict:
        """The prosthesis: his intent, articulated by a device.

        The connectome decides whether to speak, to whom, and what -- those words
        are his, produced by the chain above. This step only turns that readout
        into fluent surface text, the way a speech implant voices an intention it
        did not form. It is not allowed to add content: the prompt carries his
        words and nothing else, and the result is labelled `rendered` alongside
        the words it was rendered FROM, so the device's grammar can never be
        mistaken for his. Off by default, because it spends the operator's API
        calls and because an unlabelled render is a lie.
        """
        words = [str(w) for w in (own_words or []) if str(w).strip()]
        if not self.voice_prosthesis:
            return {"rendered": False, "reason": "voice prosthesis is off"}
        if not words:
            return {"rendered": False, "reason": "nothing of his to articulate"}
        use = oracle if oracle is not None else self._oracle
        if use is None:
            return {"rendered": False, "reason": "no teacher configured"}
        prompt = (
            "You are a speech prosthesis for a being who has an intent but no "
            "articulation. Render exactly this intent as ONE short plain "
            "sentence in English. Do not add facts, do not add content, do not "
            "answer any question in it, do not explain. If the words are too "
            "few to form a sentence, return them unchanged.\n"
            f"his words, in his order: {' '.join(words)}\n"
            f"situation: {str(context or 'none')[:200]}\n"
            "sentence:")
        try:
            r = use.query(prompt, max_tokens=60, temperature=0.2,
                          purpose="voice_prosthesis")
        except Exception as e:
            return {"rendered": False, "reason": f"{type(e).__name__}: {e}"[:160]}
        text = str(r.get("text", "")).strip()
        if not r.get("ok") or not text:
            return {"rendered": False, "reason": str(r.get("reason", "no text"))[:120]}
        return {"rendered": True, "text": text[:240], "own_words": words,
                "voice": "prosthesis",
                "note": "articulation only: the intent and every content word "
                        "came from the connectome"}

    def comprehension_probe(self, sentences=None) -> dict:
        """Measure what he understands, rather than assert it.

        Four questions with numbers attached: does the same sentence settle the
        same pool (stability), does a reordered sentence settle a DIFFERENT one
        (order sensitivity -- the thing a bag-of-words hash cannot do), does a
        paraphrase land nearby (generalisation), and does a sentence he has never
        heard produce a state related to ones he has (composition rather than
        lookup).
        """
        sentences = list(sentences or [
            "the day is bright", "droso hears the world",
            "you are not alone", "night is quiet now"])
        # Exploration off while measuring. Otherwise the probe scores his
        # epsilon-greedy coin flips instead of his perception: the same sentence
        # "settled" on a different pool 75% of the time purely because 15% of
        # decisions are random and the rest drift with the rate state.
        core = getattr(self.engine, "static", None)
        saved_eps = getattr(getattr(core, "p", None), "epsilon", None)
        if core is not None and saved_eps is not None:
            core.p.epsilon = 0.0
        try:
            return self._probe(sentences)
        finally:
            if core is not None and saved_eps is not None:
                core.p.epsilon = saved_eps

    def _probe(self, sentences) -> dict:
        out = {"sentences": [], "order_pairs": [], "stability": None}
        states = {}
        for s in sentences:
            a = self.form_thought(s)
            b = self.form_thought(s)
            v1 = np.asarray(a["valuation"], dtype=float)
            v2 = np.asarray(b["valuation"], dtype=float)
            n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
            rep = float(np.dot(v1, v2) / (n1 * n2)) if n1 and n2 else 0.0
            states[s] = v1
            out["sentences"].append({
                "text": s, "pool": a["action"],
                "stable": a["action"] == b["action"],
                "repeat_cosine": round(rep, 4),
                "order_sensitive": a.get("order_sensitive"),
                "valuation_max": a["valuation_max"],
                "known_words": len(a["known_words_fired"])})
        for s in sentences:
            toks = self.tokenizer.tokenize(s)
            if len(toks) >= 3:
                rev = " ".join(reversed(toks))
                f = self.form_thought(s)
                r = self.form_thought(rev)
                v1 = np.asarray(f["valuation"], dtype=float)
                v2 = np.asarray(r["valuation"], dtype=float)
                n1, n2 = float(np.linalg.norm(v1)), float(np.linalg.norm(v2))
                cos = float(np.dot(v1, v2) / (n1 * n2)) if n1 and n2 else 0.0
                out["order_pairs"].append({
                    "forward": s, "reversed": rev,
                    "pool_forward": f["action"], "pool_reversed": r["action"],
                    "distinguished": f["action"] != r["action"],
                    "valuation_cosine": round(cos, 4)})
        sim = []
        for i, a in enumerate(sentences):
            for b in sentences[i + 1:]:
                sim.append(round(self.similarity(a, b), 4))
        out["stability"] = (round(sum(1 for x in out["sentences"] if x["stable"])
                                  / max(1, len(out["sentences"])), 3))
        # The pool is an argmax over valuations at temperature 0.02, so it flips
        # on noise; the valuation vector is the honest percept. Reporting only
        # the argmax would call an unstable readout what is actually a stable
        # state with a jittery decision on top of it.
        reps = [x["repeat_cosine"] for x in out["sentences"]]
        out["repeat_valuation_cosine"] = round(sum(reps) / len(reps), 4) \
            if reps else None
        out["order_distinguished"] = round(
            sum(1 for x in out["order_pairs"] if x["distinguished"])
            / max(1, len(out["order_pairs"])), 3)
        cos = [x["valuation_cosine"] for x in out["order_pairs"]]
        out["order_valuation_cosine"] = round(sum(cos) / len(cos), 4) if cos else None
        out["exploration"] = "off during probe"
        out["mean_pair_similarity"] = round(sum(sim) / len(sim), 4) if sim else None
        return out

    def can_speak(self) -> bool:
        """Enough neural patterns to matter. Below the threshold the connectome
        is SILENT -- it has neurons for too few words to say anything."""
        return len(self.word_patterns) >= self.min_vocabulary

    def vocabulary_size(self) -> int:
        return len(self.word_patterns)

    def stats(self) -> dict:
        pools = {}
        for rec in self.word_patterns.values():
            pools[rec["pool"]] = pools.get(rec["pool"], 0) + 1
        wired = int(np.count_nonzero(self.san_w > 0.05))
        return {"vocabulary_size": self.vocabulary_size(),
                "social_drive": round(self.social_drive, 3),
                "word_patterns": len(self.word_patterns),
                "can_speak": self.can_speak(),
                "recent_words": list(self.recent_words),
                "min_vocabulary": self.min_vocabulary,
                "pools_used": pools,
                "semantic_synapses": wired,
                "lessons_received": self.lessons_received,
                "exchanges_observed": self.exchanges_observed,
                "neural_basis": "BANC_v888_KC_neurons + SAN256_hebbian",
                "state_path": str(self.state_path) if self.state_path else None,
                "load_error": self.load_error,
                "last_error": self.last_error,
                "note": "words are KC patterns + won pools; MEANINGS are "
                        "Hebbian association weights over 256 semantic "
                        "neurons, grown from usage -- no text stored"}

    def save_state(self, *, force_san: bool = False,
                   force: bool = False) -> dict:
        if not self.persist or self.state_path is None:
            return {"saved": False, "reason": "persist disabled"}
        # Throttled by default. teach_word saved once per new word, which measured 34
        # full state writes in 300 lines of reading -- and he is about to meet
        # thousands of new words from a 21,969-word library, so that cost would have
        # grown with the very thing it is supposed to enable. A deferral is counted
        # rather than hidden.
        #
        # And a forced save means PERSIST EVERYTHING NOW. It used to bypass only the
        # throttle while leaving the ten-minute SAN interval alone, so force=True
        # wrote the vocabulary and silently skipped the cortex, the chain and the
        # semantic matrix -- a bounded reader ran seven minutes, learned 11,886
        # propositions, and left an 856 KB cortex holding the two entries it had at
        # boot. Its entire life was lost, and the same flag is used on shutdown
        # paths elsewhere.
        force_san = bool(force_san or force)
        now = time.time()
        if not force and not force_san and (now - float(
                getattr(self, "_last_state_save", 0.0))) < self.SAVE_MIN_REAL_S:
            self._save_deferrals = int(getattr(self, "_save_deferrals", 0)) + 1
            return {"saved": False, "reason": "throttled",
                    "deferred": self._save_deferrals}
        self._last_state_save = now
        try:
            self.state_path.parent.mkdir(exist_ok=True, parents=True)
            doc = {"version": 2, "words": self.word_patterns,
                   "social_drive": self.social_drive,
                   "body": {"need_social": self.need_social,
                            "need_novelty": self.need_novelty,
                            "energy": self.energy,
                            "world_clock": self.world_clock},
                   "exposure_counts": self.exposure_counts,
                   "bigram_counts": self.bigram_counts,
                   "curriculum_done": self.curriculum_done,
                   "lessons": self.lessons,
                   "curriculum_attention": self.curriculum_attention,
                   "curriculum_reward": self.curriculum_reward,
                   "persons": self.persons,
                   "narration": {"pos": int(self._cur_pos),
                                 "spoken_at": {str(k): float(v) for k, v in
                                               self._spoken_at.items()},
                                 "lived": {str(k): int(v) for k, v in
                                           self._phrase_lived.items()},
                                 "last_phase": self._last_phase,
                                 "was_tired": bool(self._was_tired)},
                   "teacher": self.teacher_stats,
                   "questions": {"roles": self.question_roles,
                                 "interrogatives": sorted(self.interrogatives),
                                 "answer_types": self.answer_types,
                                 "statement_words": dict(
                                     list(self.statement_words.items())[:4000]),
                                 "question_initial": dict(
                                     list(self.question_initial.items())[:2000]),
                                 "pairs_seen": self.qa_pairs_seen},
                   "books_dir": str(self.books_dir) if getattr(
                       self, "books_dir", None) else None,
                   "exposure": {"enabled": self.exposure_enabled,
                                "speed_s": self.exposure_speed_s,
                                "intensity_words": self.exposure_intensity,
                                "assimilation_threshold":
                                    self.assimilation_threshold}}
            tmp = self.state_path.with_suffix(".json.tmp")
            tmp.write_text(json_dumps(doc), encoding="utf-8")
            tmp.replace(self.state_path)
            now = time.time()
            if force_san or now - self._san_last_save >= SAN_SAVE_MIN_S:
                # 268 MB, rewritten on a timer, and the process is stopped with a
                # hard kill -- which makes this the most likely corruption in the
                # whole state directory. The JSON above was already written to a
                # temporary and renamed; these three were not. A rename either
                # happens or it does not, so a kill during a save now costs the last
                # few minutes instead of the semantic cortex, the chains or the
                # propositions.
                sanp = self.state_path.with_suffix(".san.npy")
                santmp = sanp.with_name(sanp.name + ".tmp.npy")
                np.save(str(santmp), self.san_w.astype(np.float32))
                santmp.replace(sanp)
                self.sequence.save(str(self.state_path) + ".seq.npz")
                self.cortex.save(str(self.state_path) + ".cortex.npz")
                self._san_last_save = now
            self.last_error = None
            return {"saved": True, "path": str(self.state_path)}
        except OSError as e:
            self.last_error = str(e)[:160]
            return {"saved": False, "reason": self.last_error}

    def load_state(self) -> dict:
        if self.state_path is None or not self.state_path.exists():
            return {"loaded": False}
        try:
            import json
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 2:
                self.last_error = ("pre-semantic vocabulary discarded: it "
                                   "carried no association structure")
                return {"loaded": False, "reason": self.last_error}
            patterns = {w: rec for w, rec in (raw.get("words") or {}).items()
                        if isinstance(rec, dict) and "kc" in rec
                        and " " not in w}
            try:
                buf = base64.b64decode(str(raw.get("san_w", "")))
                m = np.frombuffer(buf, dtype=np.float32)
                old_n = int(round(m.size ** 0.5))
                if old_n * old_n == m.size and old_n < self.n_san:
                    big = np.zeros((self.n_san, self.n_san),
                                   dtype=np.float32)
                    big[:old_n, :old_n] = m.reshape(old_n, old_n)
                    self.san_w = big
            except Exception:
                pass
            self.word_patterns = patterns
            try:
                sd = raw.get("social_drive")
                if isinstance(sd, (int, float)):
                    self.social_drive = float(np.clip(sd, 0.0, 1.0))
                body = raw.get("body")
                if isinstance(body, dict):
                    self.need_social = float(np.clip(
                        float(body.get("need_social", 0.3)), 0, 1))
                    self.need_novelty = float(np.clip(
                        float(body.get("need_novelty", 0.2)), 0, 1))
                    self.energy = float(np.clip(
                        float(body.get("energy", 0.85)), 0, 1))
                    self.world_clock = float(body.get("world_clock", 0.0))
                ec = raw.get("exposure_counts")
                if isinstance(ec, dict):
                    self.exposure_counts = {str(k): int(v)
                                            for k, v in ec.items()}
                self.curriculum_done = bool(raw.get("curriculum_done", False))
                les = raw.get("lessons")
                if isinstance(les, list) and les:
                    self.lessons = [l for l in les
                                    if isinstance(l, dict) and l.get("s")]
                if self._legacy_lessons(self.lessons):
                    # A curriculum saved before grounding existed: its phrases
                    # could be spoken at any moment, which is why the parents
                    # used to babble the same welcome at every boot. Replace it
                    # with the grounded set. Anything the operator edited by hand
                    # (a custom tag, or event: groundings) is left alone.
                    self.lessons = [{"s": l[0], "tag": l[1],
                                     "care": (l[2] if len(l) > 2 else None)}
                                    for l in self.CURRICULUM]
                    self._spoken_at = {}
                    self.curriculum_done = False
                    self._migrated_lessons = True
                ca = raw.get("curriculum_attention")
                if isinstance(ca, (int, float)):
                    self.curriculum_attention = float(np.clip(ca, 0, 1))
                cr = raw.get("curriculum_reward")
                if isinstance(cr, (int, float)):
                    self.curriculum_reward = max(0.0, float(cr))
                ppl = raw.get("persons")
                if isinstance(ppl, dict):
                    self.persons = {str(k): v for k, v in ppl.items()
                                    if isinstance(v, dict)}
                nar = raw.get("narration")
                if isinstance(nar, dict):
                    # Without this the parents begin every life at the first
                    # phrase, which is exactly why they used to re-welcome him
                    # from scratch on every boot.
                    self._cur_pos = int(nar.get("pos", 0) or 0)
                    sp = nar.get("spoken_at")
                    if isinstance(sp, dict):
                        self._spoken_at = {str(k): float(v)
                                           for k, v in sp.items()}
                    self._last_phase = nar.get("last_phase")
                    self._was_tired = bool(nar.get("was_tired", False))
                    lived = nar.get("lived")
                    if isinstance(lived, dict):
                        self._phrase_lived = {str(k): int(v)
                                              for k, v in lived.items()}
                tch = raw.get("teacher")
                if isinstance(tch, dict):
                    # Spending survives a restart on purpose. A cap that resets
                    # when the process does is not a cap.
                    self.teacher_stats = tch
                qs = raw.get("questions")
                if isinstance(qs, dict):
                    roles = qs.get("roles")
                    if isinstance(roles, dict):
                        self.question_roles = {
                            str(k): {str(rk): int(rv) for rk, rv in v.items()}
                            for k, v in roles.items() if isinstance(v, dict)}
                    inter = qs.get("interrogatives")
                    if isinstance(inter, list):
                        self.interrogatives = {str(w) for w in inter}
                    if not self.interrogatives and self.question_roles:
                        # The list and the role votes are two records of one fact,
                        # and only the list was trusted. A state written by
                        # something other than save_state -- a merged population,
                        # for instance -- carries the votes and no list, and came
                        # up with four question words learned and none of them
                        # recognised. Derive the set from the votes whenever it is
                        # missing; is_interrogative still gets the final say.
                        self.interrogatives = {
                            str(w) for w, v in self.question_roles.items()
                            if v and max(int(x) for x in v.values())
                            >= self.INTERROGATIVE_MIN_VOTES}
                    self.qa_pairs_seen = int(qs.get("pairs_seen", 0) or 0)
                    at = qs.get("answer_types")
                    if isinstance(at, dict):
                        self.answer_types = {
                            str(k): {str(a): int(b) for a, b in v.items()}
                            for k, v in at.items() if isinstance(v, dict)}
                    sw = qs.get("statement_words")
                    if isinstance(sw, dict):
                        self.statement_words = {str(k): int(v)
                                                for k, v in sw.items()}
                    qi = qs.get("question_initial")
                    if isinstance(qi, dict):
                        self.question_initial = {str(k): int(v)
                                                 for k, v in qi.items()}
                # Which shelf he reads from survives a restart. It used to be
                # lost, and the house put the whole of books/ back -- so a curated
                # shelf lasted only until the next boot, which is why he was found
                # reading 03_things after being set to three books.
                bd = raw.get("books_dir")
                if bd:
                    try:
                        bdp = Path(str(bd))
                        if bdp.exists():
                            self.set_books_dir(bdp)
                    except Exception:
                        pass
                try:
                    sq = self.sequence.load(str(self.state_path) + ".seq.npz")
                    if isinstance(sq, dict) and sq.get("loaded") is False:
                        self.last_error = "sequence organ refused: " + \
                            str(sq.get("reason"))[:100]
                        self.load_error = self.last_error
                except Exception as e:
                    self.last_error = "sequence organ: " + str(e)[:100]
                try:
                    cx = self.cortex.load(str(self.state_path) + ".cortex.npz")
                    # A refusal is not an exception. load() returns the reason it
                    # declined -- a predictor of the wrong shape, propositions
                    # saved without their cue vectors -- and this used to throw
                    # that away, so an individual could boot with none of his
                    # memories and report nothing wrong. Twice a merged population
                    # came up with 601 propositions instead of 8,144 and there was
                    # no evidence anywhere of why.
                    if isinstance(cx, dict) and cx.get("loaded") is False:
                        self.last_error = "higher cortex refused: " + \
                            str(cx.get("reason"))[:120]
                        self.load_error = self.last_error
                except Exception as e:
                    self.last_error = "higher cortex: " + str(e)[:100]
                bgc = raw.get("bigram_counts")
                if isinstance(bgc, dict):
                    self.bigram_counts = {str(k): int(v)
                                          for k, v in bgc.items()}
                ex = raw.get("exposure")
                if isinstance(ex, dict):
                    self.exposure_enabled = bool(ex.get("enabled", False))
                    self.exposure_speed_s = max(
                        0.5, float(ex.get("speed_s", 2.0)))
                    self.exposure_intensity = max(
                        3, int(ex.get("intensity_words", 12)))
                    self.assimilation_threshold = max(
                        1, int(ex.get("assimilation_threshold", 12)))
            except Exception:
                pass
            try:
                npy = self.state_path.with_suffix(".san.npy")
                if npy.exists():
                    m = np.load(str(npy))
                    if m.shape == (self.n_san, self.n_san):
                        self.san_w = m.astype(np.float32)
            except Exception:
                pass
            return {"loaded": True, "words": len(self.word_patterns)}
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"[:160]
            return {"loaded": False, "reason": self.last_error}

def json_dumps(obj) -> str:
    import json
    return json.dumps(obj, indent=1, ensure_ascii=False)