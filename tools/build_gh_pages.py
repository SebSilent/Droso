"""Build the gh-pages payload from docs/ into _tmp/gh_pages/.

The site shell (kinpaku layout, stylesheet, config, index) lives in
tools/gh_pages_static/ and is copied verbatim, so a rebuild from main
reproduces the live branch's custom files instead of clobbering them.
Jekyll only processes files that carry YAML front matter, so each doc
gets a minimal block with its title taken from the first '# ' heading.
docs/evidence/ is copied through unchanged: no front matter, so Jekyll
serves those files as static downloads and the citations in the docs
resolve as written.
"""
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
STATIC = ROOT / "tools" / "gh_pages_static"
OUT = ROOT / "_tmp" / "gh_pages"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

# Site shell, verbatim from the live branch.
shutil.copytree(STATIC, OUT, dirs_exist_ok=True)

PAGES = [
    "STATE.md",
    "archive/experiment_log.md",
    "archive/role_chain_proposal.md",
    "cross_session_design.md",
    "benchmark_findings.md",
    "mine_criteria.md",
]

for name in PAGES:
    text = (DOCS / name).read_text(encoding="utf-8")
    m = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    title = m.group(1) if m else name.removesuffix(".md").replace("_", " ").title()
    fm = f"---\nlayout: default\ntitle: {title}\n---\n\n"
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(fm + text, encoding="utf-8")

# Evidence files: served as static downloads, no front matter.
if (DOCS / "evidence").is_dir():
    shutil.copytree(DOCS / "evidence", OUT / "docs" / "evidence")

for p in sorted(OUT.rglob("*")):
    if p.is_file():
        print(f"{p.relative_to(OUT).as_posix():40} {p.stat().st_size:7d} B")