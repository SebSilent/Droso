import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from organs import tempstore


def test_clean_removes_only_what_is_older_than_the_ttl(tmp_path):
    root = tempstore.temp_root(tmp_path)
    root.mkdir()
    old, new = root / "old.py", root / "new.py"
    old.write_text("x")
    new.write_text("x")
    now = time.time()
    os.utime(old, (now - 3600, now - 3600))
    os.utime(new, (now, now))
    out = tempstore.clean(root, ttl_seconds=600, now=now)
    assert out["removed"] == 1 and out["kept"] == 1, out
    assert not old.exists() and new.exists()


def test_clean_removes_directories_left_empty(tmp_path):
    root = tempstore.temp_root(tmp_path)
    d = root / "sandbox"
    d.mkdir(parents=True)
    f = d / "gone.py"
    f.write_text("x")
    now = time.time()
    os.utime(f, (now - 10, now - 10))
    tempstore.clean(root, ttl_seconds=1, now=now)
    assert not f.exists() and not d.exists()


def test_clean_is_harmless_when_there_is_nothing_to_clean(tmp_path):
    out = tempstore.clean(tempstore.temp_root(tmp_path))
    assert out["removed"] == 0 and out["kept"] == 0, out


def test_sweep_if_due_sweeps_once_per_interval(tmp_path):
    tempstore._last_sweep = 0.0
    root = tempstore.temp_root(tmp_path)
    root.mkdir()
    now = time.time()
    first = root / "old.py"
    first.write_text("x")
    os.utime(first, (now - 10 ** 6, now - 10 ** 6))
    assert tempstore.sweep_if_due(root, ttl_seconds=1, interval=999,
                                  now=now) is not None
    assert not first.exists()
    # Inside the interval it declines to run, so a second stale file survives.
    second = root / "old2.py"
    second.write_text("x")
    os.utime(second, (now - 10 ** 6, now - 10 ** 6))
    assert tempstore.sweep_if_due(root, ttl_seconds=1, interval=999,
                                  now=now + 5) is None
    assert second.exists()


def test_scratch_lives_under_the_temp_root(tmp_path):
    s = tempstore.scratch_dir(tmp_path)
    assert s.parent == tempstore.temp_root(tmp_path)
    assert tempstore.TMP_DIRNAME in str(s)
