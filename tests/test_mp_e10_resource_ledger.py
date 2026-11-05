"""The A10 resource ledger must be able to fail.

Registered at experiments/MP-E10/registration.json -> re_registration_2026_11_05_v1_2_BR_item1
.a10_resource_ledger, and the plan (v1.2:304, v1.2:390) makes a missing A10 dataset a gate failure from v1.2
onward -- so the instrument that produces it is held to the same standard as the numbers: it is tested, not
trusted. These tests pin the three ways it could lie: attributing a phase from a sample that never fell in
its window, substituting the process-lifetime OS peak for a per-phase peak, and silently dropping the
retained-item count so cost-per-retained-item reads null for a phase that did have items (the first smoke
run found exactly that, because the bench keys depths as "1" while the phase mark says "d1").
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mp_e10_resource_ledger import ResourceLedger  # noqa: E402


def _fake(ledger, schedule):
    """Feed the ledger marks and samples by hand: no thread, no timing luck."""
    ledger.available = True
    ledger.marks = [(label, t) for label, t, _ in schedule]
    ledger.samples = [(t, rss) for _l, t, rss in schedule if rss is not None]
    ledger.interval_s = 0.2
    ledger._thread = None
    return ledger


def test_a_phase_with_no_sample_in_its_window_reports_null_rather_than_borrowing_one():
    # A sample stamped exactly on a mark belongs to the window that OPENS there (t0 <= t < t1), so the
    # empty window is the middle one with nothing inside it at all.
    led = _fake(ResourceLedger(), [
        ("learn-d1:live", 0.0, 100),
        ("learn-d1:restarted", 1.0, None),
        ("learn-d1:reasked", 5.0, 300),
    ])
    out = led.finish({})
    by = {w["phase"]: w for w in out["per_phase"]}
    assert by["learn-d1:live"]["peak_rss_bytes"] == 100
    assert by["learn-d1:restarted"]["peak_rss_bytes"] is None, \
        "an empty window must not take its neighbour's number"
    assert by["learn-d1:restarted"]["no_sample_landed_in_this_window"] is True
    assert by["learn-d1:reasked"]["peak_rss_bytes"] == 300


def test_a_sample_is_attributed_to_the_window_it_fell_in_and_not_to_the_next_one():
    led = _fake(ResourceLedger(), [
        ("learn-d1:live", 0.0, None),
        ("learn-d1:restarted", 10.0, None),
    ])
    led.samples = [(0.5, 111), (1.5, 222), (9.9, 333), (10.5, 444), (11.0, 555)]
    led.marks = [("learn-d1:live", 0.0), ("learn-d1:restarted", 10.0)]
    led._stop.set()
    out = led.finish({})
    live, restarted = out["per_phase"][0], out["per_phase"][1]
    assert live["peak_rss_bytes"] == 333 and live["samples"] == 3
    assert restarted["peak_rss_bytes"] == 555 and restarted["samples"] == 2


def test_retained_counts_resolve_across_both_depth_spellings_so_cost_per_item_is_not_silently_null():
    arms = {"learn": {"probes": {"1": {"live": [
        {"taught": True, "cls": "correct"}, {"taught": True, "cls": "correct"},
        {"taught": True, "cls": "refused"}, {"taught": False, "cls": "correct"}]}}}}
    led = _fake(ResourceLedger(), [("learn-d1:live", 0.0, 1000)])
    led.marks = [("learn-d1:live", 0.0)]
    led.samples = [(0.0, 1000)]
    out = led.finish(arms)
    w = out["per_phase"][0]
    assert w["retained_items"] == 2, "two taught-and-correct rows, no distractor, no refusal"
    assert w["cost_per_retained_item_bytes"] == 500.0


def test_the_whole_run_peak_is_the_max_of_samples_and_the_os_peak_is_kept_separate():
    led = _fake(ResourceLedger(), [("x:a", 0.0, 10), ("x:b", 1.0, 40), ("x:c", 2.0, 20)])
    led.os_peak = lambda: {"field": "peak_wset", "bytes": 999}
    out = led.finish({})
    assert out["whole_run_peak_rss_bytes"] == 40
    assert out["os_peak"]["bytes"] == 999
    assert all(w["peak_rss_bytes"] != 999 for w in out["per_phase"]), \
        "the lifetime peak must never be handed out as a phase peak"


def test_vram_is_asserted_from_a_probe_and_not_declared():
    led = ResourceLedger()
    v = led.vram()
    assert set(v) >= {"asserted_zero", "method", "bytes_visible"}
    assert v["asserted_zero"] is True, "this build is CPU-only; if it ever were not, the ledger must say so"
    assert v["bytes_visible"] == 0 and "torch" in v["method"]


def test_the_ledger_degrades_loudly_when_psutil_is_absent():
    """Forced rather than skipped: this machine has psutil, so the honest way to cover the branch is to put
    the ledger in the state a missing dependency produces and check what it writes."""
    led = ResourceLedger()
    led.available = False
    led.unavailable_reason = "forced by this test -- psutil is installed here, the branch is still covered"
    out = led.finish({})
    assert out["available"] is False
    assert out["unavailable_reason"]
    assert out["whole_run_peak_rss_bytes"] is None
    assert out["per_phase"] == []
