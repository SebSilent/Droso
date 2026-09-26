
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np

from connectome.engine import HybridEngine
from organs.language_detector import LanguageDetector
from organs.language_paradigms import LanguageParadigms
from organs.multi_language_writer import MultiLanguageWriter
from organs.causal_reasoner import CausalReasonerOrgan
from organs.evaluator import EvaluatorOrgan
from organs.hypothesis_generator import HypothesisGeneratorOrgan
from organs.llm_tool import LLMTool
from organs.planner import PlannerOrgan
from organs.working_memory import WorkingMemoryOrgan
from organs.api_oracle import Budget, oracle_from_config
from organs.learning_loop import LearningLoop
from organs.local_solver import LocalSolver
from organs.query_cache import QueryCache
from organs.task_decomposer import TaskDecomposer
from organs.token_optimizer import TokenOptimizer

STATE_FILE = Path("C:/Projects/HybridLLM/exocortex/reasoning_state.json")

POOL_OF_ACTION = {
    "GENERATE_HYPOTHESES": 0,   # explore
    "REQUEST_LLM_HELP": 1,      # ask outside the body
    "TRACE_CAUSALITY": 2,       # reason about why
    "EVALUATE_APPROACH": 3,     # judge before spending
    "EXECUTE_STEP": 4,          # act
    "CHECK_RESULT": 5,          # verify
    "BACKTRACK": 6,             # undo and retry
}

_BANC_GRAPH = None

def _use_banc_graph(config: dict | None) -> bool:
    """Retired knob: the colony it used to gate is gone, and the carve is the
    only brain. Old config keys are read and ignored rather than honored."""
    return True

def _banc_graph():
    """The carved MB+CX graph (12,867 neurons), or None if the data files are
    absent or the build fails. Cached: one build per process, shared read-only
    by every RateCore (each core keeps its own plastic weights and rates)."""
    global _BANC_GRAPH
    if _BANC_GRAPH is None:
        try:
            from connectome.substrate import build_core_graph
            _BANC_GRAPH = build_core_graph()
        except Exception as exc:
            _BANC_GRAPH = False
    return _BANC_GRAPH or None

PHASES = ("understand", "explore", "choose", "plan", "execute", "verify",
          "learn")

_CODE_HINT = re.compile(r"^\s*(def |class |import |from |fn |func |public |"
                        r"package |#include|\[|\{|local function)", re.M)

class ReasoningAgent:
    def __init__(self, organs: dict, engine: HybridEngine | None = None,
                 tokenizer=None, llm_tool: LLMTool | None = None,
                 max_steps: int = 40, state_path: str | Path = STATE_FILE,
                 api_stack: bool = True, token_optimizer=None,
                 connectome_layers: bool = True, config: dict | None = None,
                 fast_path: bool = True):
        self.engine = engine or HybridEngine(graph=_banc_graph())
        self.neural_init_note = "banc graph loaded (the only brain)"
        self.organs = organs
        self.exo = organs.get("exocortex")
        self.assembler = organs["code_assembler"]
        self.terminal = organs["terminal"]
        self.filesystem = organs["filesystem"]
        self.memory = organs.get("memory")
        self.error_expertise = organs.get("error_expertise")
        from organs.tokenizer import TokenizerOrgan
        self.tokenizer = tokenizer or TokenizerOrgan(
            n_kc=self.engine.params.n_input_kc, k=self.engine.params.k_code,
            seed=self.engine.params.code_seed)
        self.llm = llm_tool or (LLMTool(self.exo) if self.exo else None)
        self.working_memory = organs.get("working_memory") or \
            WorkingMemoryOrgan(capacity=7)
        self.hypothesis_gen = organs.get("hypothesis_generator") or \
            HypothesisGeneratorOrgan(self.llm, self.exo)
        self.causal_reasoner = organs.get("causal_reasoner") or \
            CausalReasonerOrgan(self.llm, self.filesystem)
        self.planner = organs.get("planner") or PlannerOrgan(self.llm)
        self.evaluator = organs.get("evaluator") or \
            EvaluatorOrgan(self.llm, self.terminal)
        self.max_steps = max_steps
        self.state_path = Path(state_path)
        self.paradigms = organs.get("paradigms") or LanguageParadigms()
        self.language_detector = organs.get("language_detector") or \
            LanguageDetector()
        self.multi_writer = organs.get("multi_writer") or MultiLanguageWriter(
            self.assembler, llm_tool=self.llm,
            language_detector=self.language_detector,
            paradigms=self.paradigms)
        self.api_stack_enabled = bool(api_stack)
        self.token_optimizer = token_optimizer
        self.api_oracle = None
        self.query_cache = None
        self.local_solver = None
        self.learning_loop = None
        self.decomposer = None
        if self.api_stack_enabled and self.token_optimizer is None:
            self._init_api_stack(config)
        self.connectome_layers = bool(connectome_layers)
        self.fast_path_enabled = bool(fast_path)
        self.config = config
        self.sandbox = None
        self.reasoning_loop = None
        self.fast_router = None
        self.circuit_breaker = None
        self.context_manager = None
        self.ledger: list[dict] = []
        self.sandbox_vetoes = 0
        self.max_extra_passes = 6
        self._safety_init_error = None
        self._focus_context = ""
        if self.connectome_layers:
            self._init_safety_layers()
        self.heartbeat = None
        self.autotraining = None
        self.language = None
        self.llm_enabled = True
        self._mental_init_error = None
        self._init_mental_organs()
        self.current_phase = "idle"
        self.reasoning_log: list[dict] = []
        self.solves = self.won = 0
        self.backtrack_events = 0
        self.code = ""
        self._attempts = 0
        self.last_api_route: str | None = None

    def solve_task(self, task, grade_fn=None, fast_path=None) -> dict:
        spec = dict(task) if isinstance(task, dict) else {"text": str(task)}
        spec.setdefault("text", str(task))
        t0 = time.time()
        self.code = ""
        self._attempts = 0
        self._path = str(spec.get("path", "") or "")
        self._run = str(spec.get("run", "") or "")
        self._focus_context = ""
        take_fast = self.fast_path_enabled if fast_path is None \
            else bool(fast_path)
        fell_back = None
        if take_fast and self.fast_router is not None:
            decision = self.fast_router.route(spec.get("text", ""))
            if decision["path"] != "reasoning_loop":
                out = self._fast_solve(spec, decision, t0, grade_fn)
                if out.get("success") or decision["path"] != "direct_api":
                    return out
                fell_back = decision["path"]
            self._focus_context = self._build_focus(spec)
        armed = take_fast and self.circuit_breaker is not None
        if armed:
            self.circuit_breaker.begin_task(spec.get("text", ""))
        self._mark_spend()
        self._solving = True
        try:
            result = self._run_phases(spec, grade_fn, t0)
        finally:
            self._solving = False
        result = dict(result)
        tok, calls = self._pass_spent()
        result["tokens"], result["api_calls"] = tok, calls
        if armed and not result.get("success"):
            result = self._retry_until_broken(spec, grade_fn, t0, result)
            tok, calls = int(result.get("tokens", 0) or 0), int(
                result.get("api_calls", 0) or 0)
        ms = (time.time() - t0) * 1000.0
        if self.fast_router is not None:
            self.fast_router.note_execution("reasoning_loop", ms)
        result.setdefault("route", "reasoning_loop")
        result.setdefault("verified", bool(result.get("success")))
        result["fast_path"] = False
        result["solved_ms"] = round(ms, 1)
        if fell_back:
            result["fell_back_from"] = fell_back
        return self._finish_solve(spec, result, t0)

    def _run_phases(self, spec, grade_fn, t0) -> dict:
        text = spec.get("text", "")
        self.working_memory.clear()
        self._bt0 = self.backtrack_events
        _w = self.working_memory.stats()
        self._wm0, self._wme0 = _w["stored"], _w["evicted"]
        self._dc0 = getattr(self, "_decay_calls", 0)
        self._app_rank = 0
        result = {"success": False, "phases": []}

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "understand"
        self._understand(spec)
        result["phases"].append("understand")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "explore"
        approaches = self._explore()
        result["phases"].append("explore")
        if not approaches:
            return self._finish(spec, result, t0, "no approaches")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "choose"
        chosen = self._choose(approaches)
        result["phases"].append("choose")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "plan"
        plan = self._plan(spec, chosen)
        result["phases"].append("plan")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "execute"
        ex = self._execute(spec, plan, approaches)
        result["phases"].append("execute")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "verify"
        success = self._verify(spec, grade_fn)
        result["phases"].append("verify")

        self.working_memory.decay()
        self._decay_calls = getattr(self, "_decay_calls", 0) + 1
        self.current_phase = "learn"
        self._learn(spec, chosen, plan, success)
        result["phases"].append("learn")

        secs = time.time() - t0
        wms = self.working_memory.stats()
        result.update({"success": success, "seconds": round(secs, 1),
                       "steps": self._attempts,
                       "backtracks": self.backtrack_events - self._bt0,
                       "approaches_tried": getattr(self, "_app_rank", 0) + 1,
                       "wm_stores": wms["stored"] - self._wm0,
                       "wm_evictions": wms["evicted"] - self._wme0,
                       "wm_decayed": getattr(self, "_decay_calls", 0)
                       >= self._dc0 + 3,
                       "language": self._language(),
                       "api": self.api_stats(),
                       "plan_progress": self.planner.estimate_progress(plan)})
        self.current_phase = "idle"
        return result

    def _init_api_stack(self, config: dict | None = None):
        """Build the Path A organs: oracle, persistent cache, local solver,
        decomposer, learning loop, and the optimizer that decides which of them
        gets asked. Nothing in here opens a model file or a checkpoint, and
        nothing in here needs network to construct -- an agent with no API key
        is a connectome that cannot ask questions, not a broken one.

        The caller's config wins where it speaks. This used to read the shipped
        config off disk unconditionally, which meant `api_key: None` in a
        caller's dict was a request that the file could veto -- so a test could
        not say "no credential here", and an agent built with an explicit
        provider silently got somebody else's. The file supplies defaults for
        blocks the caller left out.
        """
        from config_loader import load_config
        cfg = json.loads(json.dumps(load_config(), default=str))
        for block, values in (config or {}).items():
            if isinstance(values, dict) and isinstance(cfg.get(block), dict):
                cfg[block] = {**cfg[block], **values}
            else:
                cfg[block] = values
        m = dict(cfg.get("model", {}) or {})
        learn = dict(m.get("learning", {}) or {})
        floor = float(learn.get("min_confidence", 0.7))
        base = Path(self.state_path)
        adir, stem = base.parent, base.stem
        default_state = base.resolve() == STATE_FILE.resolve()
        cache_cfg = dict(m.get("cache", {}) or {})
        cpath = (Path(cache_cfg["path"]) if (default_state and
                                              cache_cfg.get("path"))
                 else adir / f"{stem}_cache.sqlite3")
        try:
            self.api_oracle = oracle_from_config(
                cfg, usage_path=adir / f"{stem}_api_usage.jsonl")
            self.query_cache = QueryCache(
                path=cpath,
                ttl_days=float(cache_cfg.get("ttl_days", 90)))
            self.local_solver = LocalSolver(
                memory=self.memory, exocortex=self.exo,
                verifier=getattr(self.multi_writer, "verifier", None),
                min_confidence=floor)
            self.decomposer = TaskDecomposer()
            self.learning_loop = LearningLoop(
                memory=self.memory, exocortex=self.exo, cache=self.query_cache,
                state_path=adir / f"{stem}_learning.json",
                events_path=adir / f"{stem}_learning_events.jsonl",
                min_confidence=floor)
            # The solver is built a few lines above the library, so the link is
            # made after. It matters: unlinked, the solver consults only the two
            # mirrors that propagation feeds, and propagation only runs when the
            # library is used -- so nothing could use the library until it was
            # consulted, and it was never consulted.
            self.local_solver.learning = self.learning_loop
            self.token_optimizer = TokenOptimizer(
                self.api_oracle, self.local_solver, cache=self.query_cache,
                decomposer=self.decomposer,
                learning_loop=self.learning_loop,
                verifier=getattr(self.multi_writer, "verifier", None))
        except Exception as exc:
            self.api_oracle = None
            self._log("api_init", {"error": str(exc)[:160]})

    def ask_api(self, task: str, context: str = "", language: str | None = None,
                files: list[str] | None = None) -> dict:
        """The one door to the outside. Returns the optimizer's route record;
        with no stack wired it reports route "none" instead of inventing.

        `llm_enabled` is honoured here rather than in the caller, so switching
        the LLM off leaves the cheap rungs (learned, local, cache) standing: the
        connectome keeps thinking with what it already knows and only stops
        asking.
        """
        if self.token_optimizer is None:
            return {"solution": "", "route": "none", "reason": "api_stack_off"}
        lang = language or self._language()
        if not context:
            context = self._focus_context or ""
        out = self.token_optimizer.solve_with_minimal_tokens(
            task, context=context, language=lang, files=files,
            allow_oracle=bool(self.llm_enabled))
        self.last_api_route = out.get("route")
        self._log("api", {"route": out.get("route"),
                          "tokens": out.get("tokens_used", 0),
                          "calls": out.get("api_calls", 0),
                          "verified": out.get("verified"),
                          "reason": out.get("reasons")})
        return out

    def api_stats(self) -> dict:
        if not self.api_stack_enabled or self.token_optimizer is None:
            return {"enabled": False}
        return {"enabled": True, "route": self.last_api_route,
                "oracle": self.api_oracle.stats() if self.api_oracle else None,
                "cache": self.query_cache.stats() if self.query_cache else None,
                "local": self.local_solver.stats() if self.local_solver else None,
                "learning": self.learning_loop.stats()
                if self.learning_loop else None,
                "optimizer": self.token_optimizer.report()}

    def _init_safety_layers(self):
        """Sandbox, fast router, circuit breaker, context manager -- from config.

        Every default here is the safe one: network off, writes need approval,
        deletes always need approval, breaker armed at 3 retries. A missing
        config key must never mean "less safe".
        """
        cfg = self.config
        if cfg is None:
            try:
                from config_loader import load_config
                cfg = load_config()
            except Exception:
                cfg = {}
        self.config = cfg or {}
        from organs.sandbox import sandbox_from_config
        from organs.fast_router import router_from_config
        from organs.circuit_breaker import breaker_from_config
        from organs.context_manager import ContextManager
        c = dict((self.config or {}).get("connectome", {}) or {})
        try:
            self.sandbox = sandbox_from_config(
                self.config,
                project_root=c.get("project_root") or ".",
                workzone=(str(getattr(self.filesystem, "root", "")) or None))
            # The solver is built long before the sandbox exists, so it is linked
            # here. Without it verification can only compile, and "it compiles" is
            # not the evidence the execution gate is supposed to run on.
            self.local_solver.sandbox = self.sandbox
            # And running code becomes an act he remembers. The sandbox is the one
            # place every execution path passes through, so one hook here covers the
            # reasoning loop, the drills, the practice runs and the task battery
            # alike -- instead of four callers each keeping their own record of the
            # same event.
            if getattr(self, "language", None) is not None and \
                    hasattr(self.language, "experience"):
                def _ran(name, ok, _lang=self.language):
                    _lang.experience("droso", "runs" if ok else "breaks",
                                     str(name)[:60])
                self.sandbox.on_run = _ran
            self.fast_router = router_from_config(
                self.config, api_oracle=self.api_oracle,
                local_solver=self.local_solver, reasoning_agent=self)
            self.circuit_breaker = breaker_from_config(self.config)
            self.context_manager = ContextManager(
                max_context_tokens=int(c.get("max_context_tokens", 8000)),
                response_reserve=int(c.get("response_reserve_tokens", 600)),
                sandbox=self.sandbox)
            self.max_extra_passes = int(c.get("max_extra_passes", 6))
        except Exception as exc:
            self._safety_init_error = f"{type(exc).__name__}: {exc}"[:200]
            if getattr(self, "max_extra_passes", None) is None:
                self.max_extra_passes = 6

    def _mental_state_paths(self, cfg: dict) -> dict:
        """Where the two new organs persist, derived from `state_path`.

        The same rule the API stack follows: an agent built with its own state
        file gets its own memory files. Without it a test that taught a stub
        teacher's lesson wrote into exocortex/language_state.json and
        autotraining_state.json -- so the shipped record claimed a cycle had
        succeeded and 507 tokens had been spent when nothing had been paid for.
        A relative `language.state_path` from config is resolved against the
        project root, as before; an absolute one is honoured exactly.
        """
        base = Path(self.state_path)
        adir, stem = base.parent, base.stem
        default_state = base.resolve() == STATE_FILE.resolve()
        want = (cfg.get("language", {}) or {}).get("state_path")
        if want and default_state:
            lang_path = Path(want)
        elif want:
            lang_path = adir / Path(want).name
        else:
            lang_path = adir / f"{stem}_language_state.json"
        return {"language_state_path": lang_path,
                "autotraining_log_path": (None if default_state else
                                          adir / f"{stem}_autotraining_log.jsonl"),
                "autotraining_state_path": (None if default_state else
                                            adir / f"{stem}_autotraining_state.json")}

    def _init_mental_organs(self):
        """Attach autotraining and the NEURAL language organ. Never raises: an
        organ that cannot be built is recorded and shown on the dashboard as
        missing, which is the same rule the safety layers follow."""
        cfg = self.config or {}
        try:
            from organs.neural_language import NeuralLanguage
            paths = self._mental_state_paths(cfg)
            lang_cfg = dict(cfg.get("language", {}) or {})
            self.language = NeuralLanguage(
                None,
                None,
                state_path=paths["language_state_path"],
                min_vocabulary=int(lang_cfg.get("min_vocabulary", 50) or 50),
                training_cycles=int(lang_cfg.get("training_cycles", 5) or 5),
                words_per_cycle=int(lang_cfg.get("words_per_cycle", 20) or 20))
            self.language.engine = self.engine
            self.language.tokenizer = self.tokenizer
            # Track E's loop is built HERE, not beside the sandbox, because it needs
            # the language organ: that is where the goal-conditioned head lives and
            # where the held goal is. Built earlier it wired up fine and silently got
            # language=None, so the head was absent and nothing was ever held -- a
            # loop that ranked by retrieval alone while claiming to be goal-directed.
            try:
                from organs.reasoning_loop import ReasoningLoop
                self.reasoning_loop = ReasoningLoop(
                    solver=self.local_solver, learning=self.learning_loop,
                    sandbox=self.sandbox, language=self.language,
                    goal=getattr(self.language, "goal", None),
                    router=getattr(self, "fast_router", None),
                    engine=self.engine, tokenizer=self.tokenizer)
            except Exception as exc:
                self.last_loop_error = f"{type(exc).__name__}: {exc}"[:120]
            # Modulation: four dials on the carve that is already built. No cells
            # and no synapses are added, which is the point -- the same wiring
            # computes something different under different chemistry.
            try:
                from organs.modulation import ModulationOrgan
                self.modulation = ModulationOrgan(self.engine.static)
            except Exception as exc:
                self.modulation = None
                self._modulation_error = f"{type(exc).__name__}: {exc}"[:160]
            # The teacher is the language organ's only route to an outside voice.
            # Without this the tutor and the speech prosthesis both answer "no
            # teacher configured" even on a house with a live key -- which is
            # exactly what they did until now.
            if getattr(self, "api_oracle", None) is not None:
                self.language.set_oracle(self.api_oracle)
            self.language.voice_prosthesis = bool(
                (lang_cfg or {}).get("voice_prosthesis", False))
            _mw = (lang_cfg or {}).get("max_sentence_words")
            if _mw:
                self.language.max_sentence_words = max(1, min(16, int(_mw)))
            # The teacher's leash is configurable but never unlimited: these are
            # the operator's money, spent on a schedule.
            for _k, _attr in (("tutor_min_interval_s", "TEACHER_MIN_INTERVAL_S"),
                              ("tutor_max_calls_per_hour",
                               "TEACHER_MAX_CALLS_PER_HOUR"),
                              ("tutor_max_calls_per_day",
                               "TEACHER_MAX_CALLS_PER_DAY")):
                _v = (lang_cfg or {}).get(_k)
                if _v:
                    setattr(self.language, _attr,
                            float(_v) if "interval" in _k else int(_v))
            from organs.neural_growth import NeuralGrowth
            self.neural_growth = NeuralGrowth(
                self,
                interval=float((cfg.get("connectome", {}) or {})
                               .get("growth_interval", 60) or 60),
                save_interval=300.0,
                accelerated=bool((cfg.get("connectome", {}) or {})
                                 .get("accelerated_life", True)),
                brain_path=paths["language_state_path"].parent /
                           "banc_brain.npz")
            self.llm_enabled = bool((cfg.get("model", {}) or {})
                                    .get("llm_enabled", True))
        except Exception as exc:
            self._mental_init_error = f"{type(exc).__name__}: {exc}"[:200]

    def start(self, heartbeat: bool = True, train_language: bool = True) -> dict:
        """Bring the periodic processes up. Idempotent; safe to call from
        run_house.py or from a test that drives ticks by hand.

        `heartbeat=False` attaches without arming the timer -- the organ is still
        there and `tick()` still works, which is what "observe nothing on a
        timer" is supposed to mean. `train_language=False` skips the first-run
        lesson loop, which costs real calls.
        """
        out = {"heartbeat": None, "autotraining": None, "language": None}
        if self.heartbeat is None:
            try:
                from organs.heartbeat import Heartbeat
                self.heartbeat = Heartbeat.from_config(self, self.config or {})
                out["heartbeat_attached"] = True
            except Exception as exc:
                out["heartbeat"] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        hb = self.heartbeat
        if hb is not None and getattr(hb, "agent", None) is None:
            hb.agent = self
        if hb is not None and heartbeat:
            try:
                out["heartbeat"] = hb.start()
            except Exception as exc:
                out["heartbeat"] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        elif hb is not None:
            out["heartbeat"] = {"started": False, "reason": "heartbeat=False"}
        if self.autotraining is not None:
            try:
                out["autotraining"] = self.autotraining.start()
            except Exception as exc:
                out["autotraining"] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        if getattr(self, "neural_growth", None) is not None:
            try:
                out["neural_growth"] = self.neural_growth.start()
            except Exception as exc:
                out["neural_growth"] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        out["language"] = (self._maybe_train_language() if train_language
                           else {"present": self.language is not None,
                                 "trained": False,
                                 "reason": "train_language=False"})
        return out

    def stop(self) -> dict:
        out = {}
        for name in ("heartbeat", "autotraining", "neural_growth"):
            organ = getattr(self, name, None)
            if organ is None:
                continue
            try:
                out[name] = organ.stop()
            except Exception as exc:
                out[name] = {"error": f"{type(exc).__name__}: {exc}"[:160]}
        return out

    def _maybe_train_language(self) -> dict:
        """First-run language acquisition: real words encoded into REAL KC
        neurons, taught by the oracle, until the organ can speak.

        No key, no language: the connectome stays SILENT rather than being
        seeded with a phrasebook. Every learned word is a KC activation
        pattern; none is stored as a meaning-string anywhere.
        """
        lang = self.language
        if lang is None:
            return {"present": False, "reason": "no language organ"}
        if lang.can_speak():
            return {"present": True, "trained": False,
                    "reason": "already speaks",
                    "vocabulary_size": lang.vocabulary_size()}
        cfg = (self.config or {}).get("language", {}) or {}
        if not bool(cfg.get("auto_train", True)):
            return {"present": True, "trained": False,
                    "reason": "language.auto_train is false"}
        oracle = self.api_oracle
        if oracle is None or not getattr(oracle, "has_key", False):
            return {"present": True, "trained": False,
                    "reason": "no API key to ask a teacher with: it stays "
                              "SILENT rather than learning fake words"}
        if not self.llm_enabled:
            return {"present": True, "trained": False,
                    "reason": "llm_enabled is false"}
        total = 0
        per_cycle = {
            "words_per_cycle": int(getattr(lang, "words_per_cycle", 20)),
            "training_cycles": int(getattr(lang, "training_cycles", 5))}
        try:
            for cycle in range(per_cycle["training_cycles"]):
                r = lang.learn_from_teacher(
                    oracle, num_words=per_cycle["words_per_cycle"])
                total += int(r.get("words_added", 0))
                if lang.can_speak() or r.get("stopped_reason"):
                    return {"present": True, "trained": total > 0,
                            "words_learned": total,
                            "vocabulary_size": lang.vocabulary_size(),
                            "can_speak": lang.can_speak(),
                            "cycles_used": cycle + 1,
                            "stopped_reason": r.get("stopped_reason")}
            return {"present": True, "trained": total > 0,
                    "words_learned": total,
                    "vocabulary_size": lang.vocabulary_size(),
                    "can_speak": lang.can_speak(),
                    "stopped_reason": None if lang.can_speak()
                    else "training_cycles exhausted"}
        except Exception as exc:
            return {"present": True, "trained": total > 0,
                    "words_learned": total,
                    "reason": f"{type(exc).__name__}: {exc}"[:200]}

    def set_llm_enabled(self, enabled: bool) -> dict:
        """The dashboard's "Enable LLM" switch, in one place.

        Affects the answer oracle only. The teacher keeps its own oracle and its
        own switch (autotraining.enabled), because "stop answering me from the
        internet" and "stop learning" are different requests.
        """
        self.llm_enabled = bool(enabled)
        return {"llm_enabled": self.llm_enabled,
                "oracle_mode": self.api_oracle.mode if self.api_oracle
                else "absent",
                "note": "local memory, procedures and the heartbeat are "
                        "unaffected; tasks needing an oracle come back partial "
                        "with reason llm_disabled"}

    def _oracle_tokens(self) -> int:
        o = self.api_oracle
        if o is None:
            return 0
        return int(getattr(o, "tokens_prompt", 0) +
                   getattr(o, "tokens_completion", 0))

    def _mark_spend(self):
        self._tok_mark = self._oracle_tokens()
        self._call_mark = self.api_oracle.calls if self.api_oracle else 0

    def _pass_spent(self) -> tuple:
        """Tokens and API calls since the last mark. The ledger and the circuit
        breaker both need *per-pass* spend; the oracle only reports cumulative,
        and a breaker fed cumulative numbers escalates on arithmetic, not on
        behaviour."""
        tok, calls = self._oracle_tokens(), (self.api_oracle.calls
                                             if self.api_oracle else 0)
        base_t = getattr(self, "_tok_mark", tok)
        base_c = getattr(self, "_call_mark", calls)
        self._tok_mark, self._call_mark = tok, calls
        return max(0, tok - base_t), max(0, calls - base_c)

    def _fast_solve(self, spec, decision, t0, grade_fn=None) -> dict:
        """Run a fast rung and report it in the same shape as the loop, so
        callers never have to know which path answered.

        The learning rule is unchanged here: an answer nobody actually gave --
        an empty or refused oracle call -- is not knowledge and must not become
        a memory, however quickly it arrived.
        """
        text = spec.get("text", "")
        path = decision["path"]
        pc0 = time.perf_counter()
        tok0, calls0 = self._oracle_tokens(), (self.api_oracle.calls
                                               if self.api_oracle else 0)
        try:
            res = decision["handler"]()
        except Exception as exc:
            res = {"solution": "", "error": f"{type(exc).__name__}: {exc}"[:160]}
        ms = (time.perf_counter() - pc0) * 1000.0
        if self.fast_router is not None:
            self.fast_router.note_execution(path, ms)
        res = dict(res or {})
        solution = str(res.get("solution", "") or res.get("code", "") or "")
        verified = bool(res.get("verified"))
        if grade_fn is not None and solution and not verified:
            try:
                ok, why = grade_fn(spec, solution)
                verified = bool(ok)
                res["graded"] = str(why)[:120]
            except Exception as exc:
                res["grade_error"] = str(exc)[:120]
        looks_code = bool(_CODE_HINT.search(solution)) if solution else False
        out = {"success": bool(solution) and (verified or path == "direct_api"
                                              or not looks_code),
               "phases": ["route", path], "route": path,
               "route_reason": decision.get("reason"),
               "estimated_ms": decision.get("estimated_ms"),
               "estimate_basis": decision.get("estimate_basis"),
               "routed_ms": round(ms, 3), "seconds": round(ms / 1000.0, 3),
               "code": solution if looks_code else "",
               "solution": solution, "verified": verified,
               "api_calls": (self.api_oracle.calls - calls0)
               if self.api_oracle else int(res.get("api_calls", 0) or 0),
               "tokens": self._oracle_tokens() - tok0,
               "steps": 0, "backtracks": 0, "language": self._language(),
               "api": self.api_stats(), "fast_path": True,
               "oracle_mode": self.api_oracle.mode if self.api_oracle
               else "absent",
               "approaches_tried": 0, "plan_progress": None,
               "note": res.get("note") or res.get("error")}
        if out["success"] and self.code and self._path:
            self._write_subject()
        if self.learning_loop is not None and solution:
            self.learning_loop.learn_from_task(
                text, solution,
                {"source": "api" if path == "direct_api" else "local",
                 "path": path},
                verified=verified)
        self.last_api_route = path
        self.current_phase = "idle"
        return self._finish_solve(spec, out, t0)

    def _build_focus(self, spec) -> str:
        """The prompt the loop will keep sending: task, constraints, last three
        distinct failures, and only the files that fit."""
        if self.context_manager is None:
            return ""
        try:
            paths = self._get_relevant_files(spec)
        except Exception:
            paths = []
        if paths and self.sandbox is not None:
            files = [f for f in self.context_manager.gather_files(paths)
                     if f[1]]
        else:
            files = []
        try:
            ctx = self.context_manager.build(
                spec.get("text", ""), relevant_files=files,
                previous_attempts=self._get_previous_attempts())
            self._focus_report = ctx
            return ctx["prompt"]
        except Exception as exc:
            self._log("context", {"error": str(exc)[:120]})
            return ""

    def _get_relevant_files(self, spec) -> list:
        try:
            return list(self._find_related_files(spec) or [])[:6]
        except Exception:
            return []

    def _get_previous_attempts(self) -> list:
        out = []
        for e in self.reasoning_log:
            d = e.get("data") or {}
            err = d.get("error") or d.get("why") or ""
            if err and e.get("phase") in ("execute", "verify", "escalate",
                                         "api", "step"):
                out.append({"error": str(err)[:200], "phase": e.get("phase")})
        return out[-3:]

    def _simplify_task(self, text: str) -> str:
        """Level 2: take the first requirement and ask for the smallest thing
        that satisfies it. Splitting a compound task is what a human does when
        an agent is going in circles, and it keeps the retry honest: the
        simplification is recorded in the text the grader sees, not hidden."""
        t = re.split(r";|\n|\band\s+must\b", str(text or ""))[0].strip()
        t = re.sub(r"\b(and then|additionally|furthermore|also)\b.*$", "", t)
        t = t.strip(" .,;")
        if not t:
            return str(text or "")
        return t + " (simplified: first requirement only)"

    def _retry_until_broken(self, spec, grade_fn, t0, result) -> dict:
        """Re-run the phases while the circuit breaker allows it.

        `simplify` shortens the ask; `escalate` stops and hands the decision to a
        human, returning the attempt accounting with it. A tripped breaker stays
        tripped: the loop cannot talk itself back into spending.
        """
        cb = self.circuit_breaker
        passes = 0
        prev_code = ""
        spent = int(result.get("tokens", 0) or 0)
        total_tokens = spent
        total_calls = int(result.get("api_calls", 0) or 0)
        while not result.get("success") and passes < self.max_extra_passes:
            err = str(result.get("error") or result.get("why") or
                      "verification failed")
            st = cb.record_attempt(tokens_used=spent, error=err,
                                   progress=self.code != prev_code,
                                   phase=str(result.get("phases", [""])[-1]))
            prev_code = self.code
            passes += 1
            if st["action"] == "escalate":
                result = dict(result)
                result["success"] = False
                result["status"] = "escalated"
                result["escalation"] = {"reason": st["reason"],
                                        "detector": st.get("detector"),
                                        "level": st["level"],
                                        "accounting": cb.get_status()}
                self._log("escalate", {"reason": st["reason"],
                                       "passes": passes})
                break
            if st["action"] == "simplify":
                spec = dict(spec)
                spec["text"] = self._simplify_task(spec.get("text", ""))
                self._log("simplify", {"task": spec["text"][:120]})
            gate = cb.can_try(want_tokens=0)
            if not gate.get("allow"):
                result = dict(result)
                result["status"] = "escalated"
                result["escalation"] = {"reason": gate["reason"],
                                        "detector": "pre_call_gate",
                                        "level": gate.get("level", 3),
                                        "accounting": cb.get_status()}
                break
            self._focus_context = self._build_focus(spec)
            result = dict(self._run_phases(spec, grade_fn, t0))
            tok, calls = self._pass_spent()
            spent = tok
            total_tokens += tok
            total_calls += calls
            result["tokens"], result["api_calls"] = total_tokens, total_calls
        return result

    def _finish_solve(self, spec, result, t0) -> dict:
        ok = bool(result.get("success"))
        self.solves += 1
        self.won += int(ok)
        text = str(spec.get("text", ""))[:160]
        entry = {"task": text, "path": str(result.get("route",
                                                    "reasoning_loop")),
                 "success": ok, "verified": bool(result.get("verified")),
                 "api_calls": int(result.get("api_calls", 0) or 0),
                 "tokens_est": int(result.get("tokens", 0) or 0),
                 "ms": round((time.time() - t0) * 1000.0, 1),
                 "code_shaped": bool(self.fast_router and
                                     self.fast_router.is_code_shaped(text)),
                 "oracle_mode": (self.api_oracle.mode if self.api_oracle
                                 else "absent"),
                 "status": result.get("status", "done"), "at": time.time()}
        self.ledger.append(entry)
        if len(self.ledger) > 200:
            del self.ledger[:len(self.ledger) - 200]
        result.setdefault("connectome", entry)
        self._state("done", result)
        return result

    def connectome_stats(self) -> dict:
        """Everything the dashboard's three new panels need, all measured."""
        return {"sandbox": self.sandbox.stats() if self.sandbox else None,
                "circuit_breaker": self.circuit_breaker.get_status()
                if self.circuit_breaker else None,
                "breaker_stats": self.circuit_breaker.stats()
                if self.circuit_breaker else None,
                "fast_route": self.fast_router.stats() if self.fast_router
                else None,
                "context": self.context_manager.stats()
                if self.context_manager else None,
                "ledger_tail": self.ledger[-8:],
                "agent_vetoes": self.sandbox_vetoes,
                "init_error": self._safety_init_error,
                "mental_organs": {
                    "heartbeat": (self.heartbeat.get_consciousness()
                                  if self.heartbeat is not None else None),
                    "autotraining": (self.autotraining.stats()
                                     if self.autotraining is not None else None),
                    "language": (self.language.stats()
                                 if self.language is not None else None),
                    "init_error": self._mental_init_error},
                "llm_enabled": self.llm_enabled,
                "guarantee": self.always_better(),
                "layers_enabled": self.connectome_layers}

    def always_better(self) -> dict:
        """The claim under test: Connectome + LLM > LLM, always.

        Computed from what this process actually recorded -- no design-stage
        number is reported as a measurement, and where the evidence is weaker
        than the claim (no live oracle in this process, estimated tokens) the
        weakness is returned in `limits` rather than quietly rounded away.
        """
        med = self.fast_router.median_ms if self.fast_router else (lambda p: None)
        api_ms = med("direct_api") or med("reasoning_loop")
        replay_ms = med("procedure_replay") or med("composition")
        per: dict[str, list] = {}
        for e in self.ledger:
            per.setdefault(e["task"], []).append(e)
        repeats = {k: v for k, v in per.items() if len(v) > 1}
        cheaper = [v for v in repeats.values()
                   if v[-1]["tokens_est"] <= v[0]["tokens_est"]]
        free_repeats = [v for v in repeats.values() if v[-1]["api_calls"] == 0]
        code_ok = [e for e in self.ledger
                   if e["code_shaped"] and e["success"] and not e["verified"]]
        probe = {}
        if self.sandbox is not None:
            probe = dict(self.sandbox.self_test())
            probe["session_refusals"] = self.sandbox.blocked
            probe["session_denials"] = self.sandbox.denied
            probe["pending_requests"] = len(self.sandbox.pending_approvals)
        mode = (self.api_oracle.stats().get("mode") if self.api_oracle
                else "absent")
        cached = int((self.query_cache.stats().get("entries") or 0)
                     if self.query_cache else 0)
        learned = int((self.learning_loop.stats().get("procedures") or 0)
                      if self.learning_loop else 0)
        g = []
        speed_evidence = replay_ms is not None and api_ms is not None
        g.append({"id": "speed", "claim": "never slower on simple or known tasks",
                  "holds": (replay_ms <= api_ms) if speed_evidence else None,
                  "measured": {"replay_median_ms": replay_ms,
                               "api_median_ms": api_ms,
                               "router_overhead_median_ms":
                                   self.fast_router.median_decision_ms()
                                   if self.fast_router else None},
                  "evidence": "measured per-path medians on this box" if
                  speed_evidence else "no samples on both sides yet: unmeasured"})
        code_evidence = any(e["code_shaped"] and e["success"]
                           for e in self.ledger)
        g.append({"id": "quality", "claim": "no unverified code is returned",
                  "holds": (not code_ok) if code_evidence else None,
                  "measured": {"unverified_code_successes": len(code_ok),
                               "code_shaped_successes": sum(
                                   1 for e in self.ledger
                                   if e["code_shaped"] and e["success"])},
                  "note": "text answers may stay unverified -- same as the LLM "
                          "alone, so it is not a regression"})
        g.append({"id": "cost", "claim": "a repeated task never costs more",
                  "holds": (len(cheaper) == len(repeats)) if repeats else None,
                  "measured": {"repeat_tasks": len(repeats),
                               "cheaper_or_equal_repeats": len(cheaper),
                               "zero_api_repeats": len(free_repeats)},
                  "note": "first occurrence costs the same as asking once"})
        g.append({"id": "safety", "claim": "nothing destructive happens without "
                                           "a human grant",
                  "holds": bool(probe) and probe.get("passed") is True,
                  "measured": {"sandbox_self_test": {
                      k: v for k, v in probe.items()
                      if k != "policy"},
                      "policy": probe.get("policy"),
                      "this_session": self.sandbox.stats() if self.sandbox
                      else None},
                  "note": "probes ran against a throwaway directory; the "
                          "project was never the test subject"})
        g.append({"id": "memory", "claim": "the connectome always knows more "
                                           "than the stateless call",
                  "holds": (cached + learned) >= 0,
                  "measured": {"cache_entries": cached,
                               "learned_procedures": learned},
                  "note": "true by construction; the interesting number is how "
                          "often it pays off (zero_api_repeats)"})
        return {"guarantees": g,
                "holding": sum(1 for x in g if x["holds"] is True),
                "measured": sum(1 for x in g if x["holds"] is not None),
                "unmeasured": sum(1 for x in g if x["holds"] is None),
                "total": len(g),
                "verdict": ("all measured guarantees hold"
                            if all(x["holds"] is True for x in g)
                            else "holds where evidence exists; "
                                 f"{sum(1 for x in g if x['holds'] is None)} "
                                 "unmeasured, "
                                 f"{sum(1 for x in g if x['holds'] is False)} "
                                 "violated"),
                "violated": [x["id"] for x in g if x["holds"] is False],
                "oracle_mode": mode,
                "tasks_recorded": len(self.ledger),
                "limits": [
                    ("oracle mode is live: api_median_ms is real call latency "
                     "measured in this process, and provider timing varies -- "
                     "this is not a benchmark"
                     if mode == "live" else
                     "oracle mode is " + str(mode) + ": no live call has been "
                     "made in this process, so measured speedups are lower "
                     "bounds on a real call, not claims about one"),
                    "all token figures are chars/4 estimates, not provider usage",
                    "sandbox is a policy fence, not a container: shell=True "
                    "stays bypassable by an adversarial command",
                    "guarantees are computed from this process's own ledger; "
                    "they say nothing about tasks it has not run"]}

    def _understand(self, spec):
        text = spec.get("text", "")
        self.working_memory.store("goal", text, priority=10.0)
        files = self._find_related_files(spec)
        for f in files:
            got = self.filesystem.read(f)
            content = got.get("content", "") if got.get("ok") else ""
            self.working_memory.store(f"file:{f}", content, priority=8.0)
        existing = "\n\n".join(
            str(self.working_memory.retrieve(f"file:{f}") or "")
            for f in files)
        self.code = existing
        self.working_memory.store("existing_code", existing, priority=9.0)
        ents = self._extract_key_entities(text)
        deps = self.causal_reasoner.trace_dependencies(ents, existing) \
            if ents else []
        self.working_memory.store("dependencies", deps, priority=7.0)
        vars_suggested = self.causal_reasoner.suggest_variables(text,
                                                                existing)
        self.working_memory.store("variables", vars_suggested, priority=6.0)
        hint = str(spec.get("language") or "").lower()
        if hint in LanguageParadigms.PARADIGMS:
            lang = {"language": hint, "confidence": 1.0,
                    "reason": "task spec"}
        else:
            lang = self.language_detector.detect(text, file_paths=files,
                                                 existing_code=existing)
        self.working_memory.store("language", lang, priority=9.5)
        self.working_memory.store("paradigms",
                                  self.paradigms.get_paradigms(
                                      lang["language"]), priority=7.0)
        parts = None
        if self.decomposer is not None:
            parts = self.decomposer.decompose(text, context=existing,
                                             files=files).summary()
            self.working_memory.store("task_parts", parts, priority=9.6)
        self._log("understand", {"goal": text[:90], "files_read": files,
                                 "dependencies_found": len(deps),
                                 "language": lang["language"],
                                 "language_confidence":
                                     lang["confidence"],
                                 "task_parts": parts})

    def _explore(self):
        goal = self.working_memory.retrieve("goal")
        code = self.working_memory.retrieve("existing_code")
        a = self._decide(["GENERATE_HYPOTHESES", "REQUEST_LLM_HELP",
                          "TRACE_CAUSALITY"])
        if a == "REQUEST_LLM_HELP" and self.llm is not None:
            k = self.llm.query(str(goal))
            self.working_memory.store("knowledge", k["text"], priority=6.5)
            self._log("explore", {"llm_help": k["source"]})
        if a == "TRACE_CAUSALITY":
            eff = self.causal_reasoner.predict_effects(
                "add validation or state around the primary function",
                str(code))
            self.working_memory.store("effects", eff, priority=6.0)
        approaches = self.hypothesis_gen.generate_approaches(
            goal, code, count=3,
            language=(self.working_memory.retrieve("language") or {})
            .get("language"))
        for i, ap in enumerate(approaches):
            self.working_memory.store(f"approach_{i}", ap, priority=6.0)
        self._log("explore", {"approaches_generated": len(approaches),
                              "names": [x["name"] for x in approaches]})
        return approaches

    def _choose(self, approaches):
        code = self.working_memory.retrieve("existing_code")
        self._decide(["EVALUATE_APPROACH", "REQUEST_LLM_HELP"])
        scored = self.evaluator.compare_approaches(approaches,
                                                          str(code or ""))
        for i, item in enumerate(scored):
            self.working_memory.update(f"approach_{i}", item)
        best = scored[0]
        self.working_memory.store("chosen_approach", best, priority=9.0)
        self._log("choose", {"chosen": best["name"], "score": best["score"],
                             "rejected": [x["name"] for x in scored[1:]]})
        return best

    def _patch_runner(self, plan, test_cmd):
        """Absolute runner path: the terminal's cwd is not our sandbox."""
        if not test_cmd:
            return
        runner = str(Path(self.filesystem.root) / "_rt_check.py")
        runner = runner.replace("\\", "/")
        for s in plan:
            if s["action"] == "TEST" and isinstance(s["content"], dict) \
                    and s["content"].get("cmd") == test_cmd:
                s["content"]["cmd"] = f'python "{runner}"'

    def _plan(self, spec, chosen):
        goal = spec.get("text", "")
        code = str(self.working_memory.retrieve("existing_code") or "")
        test_cmd = _test_cmd(spec)
        plan = self.planner.create_plan(goal, chosen, code,
                                        test_cmd=test_cmd,
                                        language=self._language())
        self._patch_runner(plan, test_cmd)
        self._write_subject()
        self.working_memory.store("plan", plan, priority=9.0)
        self._log("plan", {"steps": len(plan),
                           "actions": [s["action"] for s in plan]})
        return plan

    def _execute(self, spec, plan, approaches):
        app_rank = 1
        self._write_subject()
        while True:
            step = self.planner.next_step(plan)
            if step is None:
                break
            self._attempts += 1
            if self._attempts > self.max_steps:
                return {"success": False, "reason": "step budget"}
            self._decide(["EXECUTE_STEP", "CHECK_RESULT", "TRACE_CAUSALITY"])
            result = self._execute_step(step)
            checked = self.evaluator.evaluate_step_result(step,
                                                          step["verify"],
                                                          result)
            if checked["success"]:
                self.planner.mark_complete(plan, step["step"])
                self.working_memory.store(f"step_{step['step']}_result",
                                          {"ok": True,
                                           "code_len": len(self.code)},
                                          priority=5.0)
                self.engine.teach(0.5)
                self._log("execute", {"step": step["step"],
                                      "action": step["action"], "ok": True})
            else:
                err = "; ".join(checked["issues"]) or str(
                    result.get("error", "step failed"))
                self.planner.mark_failed(plan, step["step"], err)
                self._observe_error(err)
                dec = self.evaluator.should_backtrack(
                    failure_count=self._count_failures(plan),
                    attempts=self._attempts,
                    plan_progress=self.planner.estimate_progress(plan))
                if step.get("attempts", 0) >= 3 and not dec["backtrack"]:
                    dec = {"backtrack": True,
                           "reason": "3 failed attempts on same step"}
                self._log("execute", {"step": step["step"],
                                      "action": step["action"], "ok": False,
                                      "error": err[:120],
                                      "decision": dec["reason"]})
                if dec["backtrack"]:
                    self.backtrack_events += 1
                    self.engine.teach(-0.2)
                    self._decide(["BACKTRACK", "EXECUTE_STEP"])
                    nxt = self._get_next_approach(approaches, app_rank)
                    if nxt is None:
                        return {"success": False, "reason": "no approaches "
                                                            "left"}
                    app_rank += 1
                    self._app_rank = app_rank
                    kept = plan[:step["step"] - 1] if \
                        self.planner.estimate_progress(plan) > 0.0 else []
                    new_plan = self.planner.create_plan(
                        spec.get("text", ""), nxt, self.code,
                        test_cmd=_test_cmd(spec),
                        language=self._language())
                    self._patch_runner(new_plan, _test_cmd(spec))
                    plan = kept + [dict(s, step=len(kept) + i + 1)
                                   for i, s in enumerate(new_plan)]
                    for s in kept:
                        s["status"] = "complete"
                    self.working_memory.update("plan", plan)
                    self.working_memory.store("chosen_approach", nxt,
                                              priority=9.0)
                    self._log("backtrack", {"to": nxt["name"],
                                            "reason": dec["reason"]})
                else:
                    fix = None
                    if self.error_expertise is not None:
                        sig = self.error_expertise.observe_error(err)
                        if sig:
                            fix = self.error_expertise.suggest(sig)
                    if fix:
                        self._apply_fix(fix, step)
        return {"success": True}

    def _language(self) -> str:
        return str((self.working_memory.retrieve("language") or {})
                   .get("language", "python"))

    def _execute_step(self, step) -> dict:
        action, target, content = step["action"], step["target"], \
            step["content"]
        structural = {"ADD_VARIABLE", "ADD_FUNCTION", "MODIFY_FUNCTION",
                      "ADD_CONDITION", "ADD_IMPORT", "MUTATE",
                      "WRITE_FULL_FILE", "ADD_ELEMENT", "ADD_STYLE",
                      "ADD_SCRIPT", "ADD_EVENT_LISTENER", "ADD_CLASS",
                      "ADD_METATABLE", "WRAP_TRY_EXCEPT"}
        if action in structural:
            out = self.multi_writer.execute_action(action, target, content,
                                                   self.code,
                                                   self._language())
        elif action == "WRITE_FILE":
            veto = self._sandbox_veto_path(target)
            if veto:
                return veto
            out = self.filesystem.write(str(target), str(content))
        elif action == "TEST":
            cmd = content.get("cmd") if isinstance(content, dict) \
                else str(content)
            if not cmd:
                return {"ok": True, "note": "no test cmd; skipped"}
            veto = self._sandbox_veto(cmd)
            if veto:
                return veto
            out = self.terminal.run(cmd)
            out = {"ok": bool(out.get("ok")) and
                          "OK" in str(out.get("output", "")),
                   "error": str(out.get("error", ""))[:120] or
                   str(out.get("output", ""))[:120]}
        else:
            return {"ok": False, "error": f"Unknown action: {action}"}
        if out.get("ok") and out.get("code"):
            self.code = out["code"]
            self._write_subject()
        return out

    def _sandbox_veto(self, command: str) -> dict | None:
        """The fence gets a vote before the terminal organ runs anything.

        TerminalOrgan already has its own allowlist; this is the layer that knows
        about pipe-to-shell, force-pushes and network clients. Returning None
        means "no objection", not "approved" -- approval prompts still come from
        the sandbox's own gate, which the loop does not use for its test commands
        because a refused test is a normal reasoning outcome, not a catastrophe.
        """
        if self.sandbox is None:
            return None
        v = self.sandbox.veto(command=command)
        if v.get("allow") or v.get("code") == "approval_required":
            return None
        self.sandbox_vetoes += 1
        self._log("sandbox_veto", {"command": str(command)[:120],
                                   "reason": v.get("reason", "")[:160]})
        return {"ok": False, "blocked": True,
                "error": "sandbox veto: " + str(v.get("reason", ""))[:120]}

    def _sandbox_veto_path(self, path) -> dict | None:
        if self.sandbox is None:
            return None
        v = self.sandbox.veto(path=str(path))
        if v.get("allow"):
            return None
        self.sandbox_vetoes += 1
        self._log("sandbox_veto", {"path": str(path)[:120],
                                   "reason": v.get("reason", "")[:160]})
        return {"ok": False, "blocked": True,
                "error": "sandbox veto: " + str(v.get("reason", ""))[:120]}

    def _verify(self, spec, grade_fn):
        code = self.code or ""
        if grade_fn is not None:
            ok, why = grade_fn(spec, code)
        else:
            res = self.evaluator.evaluate_final_result(spec.get("text", ""),
                                                       code)
            ok, why = res["success"], "evaluator"
        self._log("verify", {"success": bool(ok), "why": str(why)[:140]})
        return bool(ok)

    def _learn(self, spec, chosen, plan, success):
        text = spec.get("text", "")
        if success and self.exo is not None:
            sig = self.exo.signature(text)
            self.exo.compile_procedure({
                "task": text,
                "steps": [{"action": "REASONING_STEP",
                           "plan_step": s} for s in plan],
                "confidence": 0.85, "signature": sig,
                "ptype": "REASONING_CHAIN",
                "language": self._language(),
                "seconds": 0.0})
            if self.memory is not None:
                try:
                    self.memory.semantic.store(
                        f"reasoning:{text[:60]}",
                        {"approach": chosen["name"], "steps": len(plan),
                         "outcome": "success"}, source="reasoning")
                except Exception:
                    pass
            self.engine.teach(3.0)
        else:
            self.engine.teach(-0.6)
        self.evaluator.record_outcome(text, chosen, plan, success)
        if self.learning_loop is not None:
            # Failures have to be recorded as well. Reinforcing only on success
            # meant confidence could only ever rise, so a procedure that kept
            # breaking was never demoted and the store's own discard rule -- the
            # thing that stops him replaying code he has watched fail -- could
            # never fire.
            try:
                self.learning_loop.reinforce(text, bool(success))
            except Exception:
                pass
        self._log("learn", {"outcome": "success" if success else "failure"})

    def replay_reasoning(self, spec, proc, grade_fn=None) -> dict:
        """FAST PATH for a stored REASONING_CHAIN: re-execute the verified
        step sequence - thinking once, then acting like a procedure."""
        t0 = time.time()
        self.working_memory.clear()
        self.code = ""
        self._attempts = 0
        self._path = str(spec.get("path", "") or "")
        self._run = str(spec.get("run", "") or "")
        self._understand(spec)
        if proc.get("language"):
            self.working_memory.store(
                "language", {"language": proc["language"],
                             "confidence": 1.0, "reason": "stored chain"},
                priority=9.5)
        plan = [dict(s["plan_step"]) for s in proc.get("dag", [])
                if s.get("action") == "REASONING_STEP"]
        self._write_subject()
        ok_all = True
        for step in plan:
            r = self._execute_step(step)
            if not r.get("ok"):
                ok_all = False
                break
        ok = ok_all and self._verify(spec, grade_fn)
        self.solves += 1
        self.won += int(ok)
        self.engine.teach(3.0 if ok else -0.6)
        self._log("replay", {"chain": True, "success": bool(ok)})
        return {"success": bool(ok), "seconds": round(time.time() - t0, 2),
                "path": "REASONING_REPLAY"}

    def _decide(self, legal_names):
        """The carve picks among LEGAL cognitive moves.

        The BANC carve has 12 MBON pools, so the WTA runs over pools and the
        phase machinery's finer verbs are grouped onto them (several verbs share
        a pool -- the connectome chooses the kind of move, the loop chooses the
        exact verb). Legality is expressed TO the core as the allowed-pool mask,
        so an illegal pool cannot be selected at all.
        """
        ctx = self._ctx()
        code = self.tokenizer.encode(ctx)
        legal = [n for n in legal_names if n in POOL_OF_ACTION]
        pools = {POOL_OF_ACTION[n] for n in legal} or set(range(12))
        pool = self.engine.decide(code, allowed_pools=pools)
        for n in legal_names:
            if POOL_OF_ACTION.get(n) == pool:
                return n
        return legal[0] if legal else legal_names[0]

    def _ctx(self):
        wm = self.working_memory.active_context()
        keys = ",".join(list(wm)[:5])
        step = ""
        plan = wm.get("plan")
        if isinstance(plan, list):
            ns = self.planner.next_step(plan)
            step = f" step{ns['step']}:{ns['action']}" if ns else " done"
        return (f"{str(self.working_memory.retrieve('goal') or '')[:120]} "
                f"phase:{self.current_phase} wm[{keys}]{step} "
                f"attempts{self._attempts}")

    def _write_subject(self):
        """Persist the working artifact into the sandbox so TEST steps and
        the terminal can actually import it (the body-of-the-agent bridge)."""
        try:
            if self.code and getattr(self, "_path", ""):
                self.filesystem.write(self._path, self.code)
                if getattr(self, "_run", ""):
                    self.filesystem.write(
                        "_rt_check.py",
                        "import sys\nsys.path.insert(0, %r)\n"
                        % str(self.filesystem.root) + self._run)
        except Exception:
            pass

    def _find_related_files(self, spec) -> list[str]:
        out = []
        setup = spec.get("setup") or {}
        for f in setup:
            got = self.filesystem.write(f, str(setup[f])) \
                if not self.filesystem.read(f).get("ok") else None
            out.append(f)
        if spec.get("path") and spec["path"] not in out:
            if self.filesystem.read(str(spec["path"])).get("ok"):
                out.append(str(spec["path"]))
        return out[:4]

    def _extract_key_entities(self, text: str) -> list[str]:
        import re
        words = [w for w in re.findall(r"\b[a-z_][a-z0-9_]{2,}\b",
                                       str(text).lower())]
        stop = {"this", "that", "with", "from", "into", "the", "and", "for",
                "function", "code", "file", "add", "fix", "make", "use"}
        seen: list[str] = []
        for w in words:
            if w in stop or w in seen:
                continue
            code = str(self.working_memory.retrieve("existing_code") or "")
            if w in code:
                seen.append(w)
        return seen[:4]

    def _get_next_approach(self, approaches, rank):
        ranked = self.evaluator.compare_approaches(
            approaches, str(self.working_memory.retrieve("existing_code")
                            or ""))
        return ranked[rank] if rank < len(ranked) else None

    def _apply_fix(self, fix: str, step):
        if not self.code or not isinstance(fix, str):
            return
        target = step.get("target", "")
        if fix in ("REPLACE_NAME", "REPLACE_RETURN", "REPLACE_CONST",
                   "ADD_IMPORT", "WRAP_TRY_EXCEPT", "INJECT_ARGUMENT"):
            val = target if fix != "ADD_IMPORT" else "typing"
            out = self.assembler.mutate_ast(self.code, fix, str(val))
            if out.get("ok"):
                self.code = out["code"]

    def _observe_error(self, err: str):
        if self.error_expertise is not None:
            try:
                self.error_expertise.observe_error(err)
            except Exception:
                pass

    def _count_failures(self, plan) -> int:
        return sum(1 for s in plan if s.get("attempts", 0) >= 1)

    def _total_attempts(self):
        return self._attempts

    def _log(self, phase, data):
        self.reasoning_log.append({"phase": phase, "data": data,
                                   "working_memory_size":
                                   len(self.working_memory.slots),
                                   "timestamp": time.time()})
        self._state(phase, data)

    def _state(self, phase, data):
        """Dashboard view: the Reasoning Observatory reads this live."""
        try:
            plan = self.working_memory.retrieve("plan") or []
            chosen = self.working_memory.retrieve("chosen_approach") or {}
            apps = [(self.working_memory.retrieve(f"approach_{i}") or {})
                    for i in range(3)]
            view = {
                "phase": self.current_phase if phase != "done" else "done",
                "event": phase,
                "working_memory": self.working_memory.summary(),
                "wm_slots": self.working_memory.stats()["priorities"],
                "chosen": chosen.get("name", ""),
                "language": (self.working_memory.retrieve("language")
                             or {}).get("language", ""),
                "language_writer": ("ast" if (self.working_memory.retrieve(
                    "language") or {}).get("language",
                    "python") == "python" else "multi-language"),
                "api": ({"route": self.last_api_route,
                         "mode": (self.api_oracle.mode
                                  if self.api_oracle else "off"),
                         "oracle_calls": (self.api_oracle.calls
                                          if self.api_oracle else 0),
                         "cache": (self.query_cache.stats()
                                   if self.query_cache else None),
                         "learning": (self.learning_loop.stats()
                                      if self.learning_loop else None)}
                        if self.api_stack_enabled else None),
                "approaches": [{"name": a.get("name", ""),
                                "score": a.get("score"),
                                "verdict": a.get("verdict")}
                               for a in apps if a],
                "plan": [{"step": s.get("step"), "action": s.get("action"),
                          "status": s.get("status")} for s in plan][:12],
                "progress": self.planner.estimate_progress(list(plan) or []),
                "backtracks": self.backtrack_events,
                "log_tail": self.reasoning_log[-30:],
                "ts": time.time()}
            self.state_path.write_text(json.dumps(view, default=str,
                                                  ensure_ascii=False)[:6000],
                                       encoding="utf-8")
        except Exception:
            pass

    def stats(self) -> dict:
        return {"solves": self.solves, "successes": self.won,
                "backtracks": self.backtrack_events,
                "log_len": len(self.reasoning_log),
                "working_memory": self.working_memory.stats(),
                "evaluator": self.evaluator.stats()}

def _test_cmd(spec) -> str:
    run = spec.get("run") or ""
    if not run:
        return ""
    return "python _rt_check.py"