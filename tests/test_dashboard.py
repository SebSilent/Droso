"""The page and the server must not drift apart.

This file used to test `frontend/index.html` against `server/app.py`, which is a house
that no longer exists: the page moved to `world/house/`, the Flask routes became one router
in `world/connectome_house.py`, and the cost/token/guarantee panels were removed
deliberately along with their backend. It had been failing since 2026-09-20 and nobody had
read it, so it was testing an architecture that had been rewritten out from under it.

Four of its checks are worth keeping, because they catch the class of bug this project
actually produces -- a page that looks plausible while every panel has stopped refreshing.
Two of those bugs really happened: a status-bar element that no longer existed threw on
every poll and took the whole refresh chain down with it, and a panel went on polling
/api/language/tutor every four seconds for the life of the page after that endpoint had
been deleted.

What was dropped, and why: the cost and token estimation panels, the guarantee panel and
the API-usage field map. They are not stale, they are gone -- the UI that estimated cost
was removed on purpose. A test for a removed feature is how a suite fills up with red that
nobody reads, which is exactly what had happened here.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
HOUSE = ROOT / "world" / "house"
INDEX = HOUSE / "index.html"
SERVER = ROOT / "world" / "connectome_house.py"

# Ids built by concatenation at runtime ("mf-" + name) cannot be resolved statically and
# are not missing parts of the markup. Named here so the check stays exact for the rest.
DYNAMIC_ID_PREFIXES = ("mf-", "mv-", "tog-", "cl-", "ws-", "lsub-")


def _static_js() -> dict:
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted((HOUSE / "static").glob("*.js"))}


def _page_sources() -> str:
    """Every byte of frontend served to a browser: the markup and every script."""
    return INDEX.read_text(encoding="utf-8") + "\n" + "\n".join(_static_js().values())


def _served_paths() -> set:
    """Every /api path the house answers, however it is matched.

    The first version of this only understood `path == "..."`, and the house also uses
    `path in (...)` -- so it reported /api/state as missing when the house has served it
    all along. A false alarm in this direction is how a real one gets ignored.
    """
    src = SERVER.read_text(encoding="utf-8")
    served = set(re.findall(r"""path\s*==\s*"(/api/[a-z_/]+)""", src))
    for group in re.findall(r"""path\s+in\s+\(([^)]*)\)""", src):
        served |= set(re.findall(r"""(/api/[a-z_/]+)""", group))
    served |= set(re.findall(r"""path\.startswith\(\s*"(/api/[a-z_/]+)""", src))
    return served


def _called_paths() -> set:
    src = _page_sources()
    called = set(re.findall(r"""(?:api|post|del)\w*\(\s*['"`](/api/[a-z_/]+)""", src))
    called |= set(re.findall(r"""fetch\(\s*['"`](/api/[a-z_/]+)""", src))
    return called


def test_the_page_and_its_scripts_are_present():
    assert INDEX.exists(), "the house serves world/house/index.html"
    assert len(INDEX.read_text(encoding="utf-8")) > 5000
    js = _static_js()
    assert len(js) >= 5, f"expected the panel scripts, found {sorted(js)}"


def test_every_static_script_parses_as_javascript():
    """node --check over every file, the JS equivalent of compileall.

    This replaces a check that parsed only the single inline script of the old page. The
    house loads external files now, so that check was reading a script tag that no longer
    held any code -- and a syntax error in chat.js and another in files.js both shipped to
    the user while it passed.
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("no node on PATH: cannot syntax-check the scripts")
    bad = []
    for name in _static_js():
        r = subprocess.run([node, "--check", str(HOUSE / "static" / name)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad.append((name, (r.stdout + r.stderr).strip()[:200]))
    assert not bad, bad


def test_the_removed_local_model_panels_stay_removed():
    """A resurrected reference means dead JS or a dead endpoint being called."""
    src = _page_sources().lower()
    for gone in ("moe", "expert_stream", "nvfp4", "bf16", "rendermoe",
                 "/api/moe_state", "ram_used_gb", "safetensors"):
        assert gone not in src, gone


def test_every_endpoint_the_page_calls_is_served_by_the_house():
    """The check that would have caught the tutor panel polling a deleted endpoint."""
    called = _called_paths()
    assert called, "no endpoints found: the regex or the page changed"
    served = _served_paths()
    assert served, "no served paths found: the router changed shape"
    missing = sorted(e for e in called
                     if e not in served
                     and not any(e.startswith(s.rstrip("/") + "/") for s in served))
    assert not missing, ("the page calls endpoints the house does not serve "
                         "-- every poll is a 404: %s" % missing)


def test_every_id_the_js_writes_exists_in_the_markup():
    """The check that caught brain3d.js never being loaded and three dead id reads."""
    markup = INDEX.read_text(encoding="utf-8")
    ids = set(re.findall(r"""id="([A-Za-z0-9_-]+)""", markup))
    written = set()
    for src in _static_js().values():
        written |= set(re.findall(r"""byId\(\s*['"]([A-Za-z0-9_-]+)['"]""", src))
        written |= set(re.findall(
            r"""getElementById\(\s*['"]([A-Za-z0-9_-]+)['"]""", src))
    assert written, "no id reads found: the helper changed shape"
    missing = sorted(w for w in written - ids
                     if not w.startswith(DYNAMIC_ID_PREFIXES))
    assert not missing, f"js reads elements that are not in the markup: {missing}"


def test_every_script_the_markup_references_actually_exists():
    """A script tag pointing at a missing file is a 404 on every page load."""
    markup = INDEX.read_text(encoding="utf-8")
    refs = re.findall(r"""<script[^>]+src="([^"]+)""", markup)
    assert refs, "no script tags found"
    missing = []
    for r in refs:
        path = r.split("?")[0]
        if path.startswith("/static/") and not (HOUSE / "static" /
                                                 path[len("/static/"):]).exists():
            missing.append(r)
    assert not missing, f"the page loads scripts that are not on disk: {missing}"


def test_measured_and_estimated_are_never_the_same_field():
    """The router ships the brief's priors as `estimated_ms` and this box's own
    timings as `median_ms_by_path`. If a rename ever merges them, a number from a
    specification gets reported as a result -- which is the same error as quoting a
    transient peak as a steady state, and this project has made it.

    Kept from the old dashboard suite because the invariant outlived the panel.
    """
    from organs.fast_router import FastRouter
    fr = FastRouter()
    stats = fr.stats()
    assert "median_ms_by_path" in stats, "the measured timings moved or vanished"
    assert "estimated_ms" not in stats, "a prior leaked into the measured panel"
    plan = fr.route("What is a monad?")
    assert "estimated_ms" in plan, "the prior is gone from the route decision"

