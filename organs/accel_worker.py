"""The accelerated life, running in its own process.

Why this exists, measured: the loop runs flat out, and inside the house process
it competes for the GIL with the heartbeat, the language organ and every
dashboard request. The same loop alone does 201 decisions/s; in the house it
managed 102. Separating them recovers the difference without touching the model.

The split is safe because of what the loop actually does. It decides -- it does
not teach, consolidate, grow or prune. So the worker only ever READS the plastic
weights; every write to the brain stays in the house process. One brain, one set
of weights, two processes, and no possibility of the two clobbering each other.

The worker picks up the house's consolidations by reloading the brain file
periodically, which is also what makes a restart of either side harmless.
"""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def load_word_patterns(language_path) -> list:
    """The KC addresses of every word he knows, as a drive rotation.

    Read from the persisted language state rather than passed in memory: the
    worker is a separate process, and the file is the honest shared record.
    """
    import json
    try:
        raw = json.loads(Path(language_path).read_text(encoding="utf-8"))
    except Exception:
        return []
    out = []
    for rec in (raw.get("words") or {}).values():
        if isinstance(rec, dict) and rec.get("kc") is not None:
            kc = [int(x) for x in rec["kc"]]
            if kc:
                out.append(np.asarray(kc, dtype=np.int64))
    return out


def _parent_alive(pid) -> bool:
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return True


def run_accel_worker(brain_path, language_path, counter, stop,
                     reload_every_s: float = 60.0, parent_pid=None) -> None:
    """Live continuously at full compute speed until `stop` is set.

    `counter` is a shared Value the house reads to report lived time; it is set
    to -1 if the worker could not start, so the house can say so instead of
    silently reporting zero.
    """
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from connectome.substrate import build_core_graph
    from connectome.engine import HybridEngine

    try:
        engine = HybridEngine(build_core_graph())
        if brain_path and Path(brain_path).exists():
            engine.load_brain(Path(brain_path))
    except Exception:
        counter.value = -1
        return

    core = engine.static
    kc_of_code = core.g.kc_idx
    n_kc = int(kc_of_code.size)
    patterns = load_word_patterns(language_path)
    n = 0
    last_reload = time.time()
    last_orphan_check = time.time()

    while not stop.is_set():
        # An orphan burns a core for nothing. On Windows a daemon child is NOT
        # killed when its parent is terminated, so every house restart leaked one
        # accelerated life: twelve were found alive at once, seven of them still
        # deciding, and the house measured a quarter of its real speed because
        # the box was full of its own previous lives.
        if parent_pid and time.time() - last_orphan_check >= 2.0:
            last_orphan_check = time.time()
            if not _parent_alive(parent_pid):
                return
        try:
            if not patterns:
                time.sleep(1.0)
                patterns = load_word_patterns(language_path)
                continue
            idx = patterns[n % len(patterns)]
            idx = idx[idx < n_kc]
            drive = [(kc_of_code[idx], np.ones(len(idx)) * 0.6)] \
                if len(idx) else None
            core.reset_episode()
            core.decide(drive)
            n += 1
            counter.value = n
            if n % 20 == 0:
                time.sleep(0.001)
            if time.time() - last_reload >= reload_every_s:
                last_reload = time.time()
                if brain_path and Path(brain_path).exists():
                    engine.load_brain(Path(brain_path))
                fresh = load_word_patterns(language_path)
                if fresh:
                    patterns = fresh
        except Exception:
            time.sleep(0.05)
