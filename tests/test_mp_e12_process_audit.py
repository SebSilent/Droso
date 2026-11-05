"""C4 PROCESS AUDIT -- tests, including the proof that it can tell the two categories apart BY CONSTRUCTION.

The brief's requirement is not "the audit passes on today's tree". Today's tree could pass for the wrong reason --
if the audit cannot fire, its silence means nothing. So the discriminating power is shown on synthetic fixtures
that differ in exactly ONE respect, whether the donor-executing process joins the answer path, and the audit must
call them differently. Both directions are asserted: the allowed case must not be failed, the forbidden case must
not be passed.

The fixtures are PARSED, never imported: a fixture file says `import torch` and nothing executes it, because the
audit reads source with ast. That is also why the audit can run on a machine with no donor runtime installed.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.mp_e12_process_audit import (ANSWER_MODULE, DEPLOYMENT_LOOP, DONOR_RUNTIME_MODULES, AuditConfig,
                                        audit_process, analyse, closure, join_report, main)

EXECUTOR = '''
import torch

class Tiny:
    def forward(self, x):
        return torch.matmul(x, x)

def run(x):
    return Tiny().forward(x)
'''

ANSWER_MOD = '''
class Organ:
    def answer(self, question):
        return {"reply": question}
'''

# Imports ONLY the executor. Executes a donor-shaped thing, never touches an answer.
BENCH_OK = '''
import executor

def bench():
    return run(1)
'''

# Identical to BENCH_OK except for ONE added import: the answer module. If the audit cannot separate these two,
# it is not auditing processes at all -- it is pattern-matching module bodies.
BENCH_BAD = '''
import executor
import answer_mod

def bench():
    return run(1)
'''

# The answer path reads what the offline process wrote. No import edge exists between them.
FILE_WRITER = '''
import json

def emit():
    with open("out/result.json", "w") as fh:
        json.dump({"seconds": 1.0}, fh)
'''

FILE_READER = '''
import json

class Organ:
    def answer(self, q):
        with open("out/result.json") as fh:
            return {"reply": q, "bias": json.load(fh)["seconds"]}
'''


@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "executor.py").write_text(EXECUTOR, encoding="utf-8")
    (tmp_path / "answer_mod.py").write_text(ANSWER_MOD, encoding="utf-8")
    (tmp_path / "bench_ok.py").write_text(BENCH_OK, encoding="utf-8")
    (tmp_path / "bench_bad.py").write_text(BENCH_BAD, encoding="utf-8")
    return tmp_path


@pytest.fixture()
def cfg(tree):
    return AuditConfig(root=tree, answer_module="answer_mod.py", answer_symbols=("answer",),
                       deployment_loop="main_entry.py")


# --------------------------------------------------------------- item 2: the construction proof
def test_allowed_case_an_executing_process_that_never_joins_an_answer_is_permitted(tree, cfg):
    """The offline benchmark category, made executable. This process DOES run a forward pass -- the audit is not
    passing it because the execution is absent, it is passing it because the output reaches no answer."""
    r = audit_process("bench_ok.py", declared="offline_benchmark", cfg=cfg)
    assert r["donor_execution_act_modules"], "fixture failed to register an execution act; the test proves nothing"
    assert not r["answer_path_reached"]
    assert r["verdict"] == "CLEAR", r
    assert r["declared_vs_derived_mismatch"] is False


def test_forbidden_case_the_same_execution_joining_an_answer_is_a_breach(tree, cfg):
    r = audit_process("bench_bad.py", declared="offline_benchmark", cfg=cfg)
    assert r["donor_execution_act_modules"]
    assert r["answer_path_reached"]
    assert r["verdict"] == "BREACH", r


def test_the_two_cases_differ_only_in_the_join(tree, cfg):
    """The discriminating claim, stated as a diff rather than asserted twice.

    Everything the audit reports about the executor is identical across the two processes; the ONLY reported
    difference is answer reachability. So a verdict change between them can only have come from the path, which is
    what makes this a process audit rather than a module audit.
    """
    a = audit_process("bench_ok.py", declared="offline_benchmark", cfg=cfg)
    b = audit_process("bench_bad.py", declared="offline_benchmark", cfg=cfg)
    for key in ("donor_execution_act_modules", "reaches_donor_runtime_module", "reaches_donor_executing_symbol"):
        assert a[key] == b[key], key
    assert a["answer_path_reached"] != b["answer_path_reached"]
    assert (a["verdict"], b["verdict"]) == ("CLEAR", "BREACH")


def test_a_label_does_not_grant_permission(tree, cfg):
    """Declared offline, derived answer-path: the audit reports the mismatch instead of honouring the label."""
    r = audit_process("bench_bad.py", declared="offline_benchmark", cfg=cfg)
    assert r["declared_category"] == "offline_benchmark"
    assert r["derived_category"] == "answer_path"
    assert r["declared_vs_derived_mismatch"] is True


def test_output_reaches_an_answer_through_a_file_not_only_through_an_import(tmp_path):
    """R11 says "any mechanism whose output reaches an answer". A benchmark that writes a number the organ reads
    satisfies that with no import edge anywhere, which is the hole a module-level check cannot see."""
    (tmp_path / "out").mkdir()
    (tmp_path / "writer.py").write_text(FILE_WRITER, encoding="utf-8")
    (tmp_path / "reader.py").write_text(FILE_READER, encoding="utf-8")
    cfg = AuditConfig(root=tmp_path, answer_module="reader.py", answer_symbols=("answer",),
                      deployment_loop="main_entry.py")
    w = audit_process("writer.py", declared="offline_benchmark", cfg=cfg)
    rd = audit_process("reader.py", declared="answer_path", cfg=cfg)
    assert w["answer_path_reached"] is False
    joins = join_report([w, rd])
    assert joins, "the file-mediated join was not detected"
    assert joins[0]["process"] == "writer.py"
    assert "out/result.json" in joins[0]["writes_read_by_answer_path"]


# --------------------------------------------------------------- the weaker second check, kept in place
def _surface_imports(rel: str, root: Path) -> set:
    tree = ast.parse((root / rel).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[0])
    return out


def test_the_import_surface_check_would_miss_the_forbidden_case(tree, cfg):
    """WHY the import-surface assertion is the weaker check, demonstrated rather than asserted.

    bench_bad.py imports no forbidden module -- only a local one, which imports torch downstream. A test that reads
    module headers passes it. The process audit fails it. The old assertion stays in force (see
    tests/test_mp_e12_address_space.py::test_no_donor_runtime_on_the_address_path, untouched) because it is cheap
    and it catches direct imports; it is simply not sufficient, and this test is the record of that.
    """
    bad = sorted(_surface_imports("bench_bad.py", tree) & set(DONOR_RUNTIME_MODULES))
    assert bad == [], "fixture changed; the demonstration needs bench_bad to import no runtime directly"
    assert audit_process("bench_bad.py", cfg=cfg)["verdict"] == "BREACH"


def test_the_existing_import_surface_assertion_is_still_in_force():
    """Not replaced. The named C4 assertion on the instruments still runs, and its file is untouched by this audit."""
    src = (ROOT / "tests/test_mp_e12_address_space.py").read_text(encoding="utf-8")
    assert "def test_no_donor_runtime_on_the_address_path():" in src
    for rel in ("tools/mp_e12_address_space.py", "tools/mp_e12_access_journal.py"):
        mods = _surface_imports(rel, ROOT)
        assert not (mods & set(DONOR_RUNTIME_MODULES)), f"{rel} imports {sorted(mods & set(DONOR_RUNTIME_MODULES))}"


# --------------------------------------------------------------- the real tree
def test_the_deployment_loop_reaches_no_donor_execution():
    r = audit_process(DEPLOYMENT_LOOP, declared="answer_path")
    assert r["answer_path_reached"] is True
    assert r["donor_execution_act_modules"] == []
    assert r["verdict"] == "CLEAR", r


def test_the_organ_alone_reaches_no_donor_execution():
    r = audit_process(ANSWER_MODULE, declared="answer_path")
    assert r["answer_path_reached"] is True
    assert r["verdict"] == "CLEAR", r


def test_an_offline_arm_that_executes_is_permitted_on_the_real_tree():
    """Not a fixture: tools/mp_e8_arm_b.py really does run a forward pass under torch, on the current tree, and the
    audit permits it because it never joins the answer path. This is the sanctioned category, evidenced by an
    existing process rather than by a synthetic one."""
    r = audit_process("tools/mp_e8_arm_b.py", declared="offline_control")
    assert r["donor_execution_act_modules"], "arm B should register an execution act"
    assert r["answer_path_reached"] is False
    assert r["verdict"] == "CLEAR", r


def test_the_instruments_reach_no_answer_path():
    for rel in ("tools/mp_e12_probes.py", "tools/mp_e12_address_space.py", "tools/mp_e12_access_journal.py"):
        r = audit_process(rel, declared="offline_extraction")
        assert r["answer_path_reached"] is False, rel
        assert r["verdict"] == "CLEAR", rel


def test_numpy_is_excluded_on_purpose_and_the_exclusion_is_load_bearing():
    """numpy sits in the answer path's own substrate. If it were classed as donor-executing the audit would fail on
    sight of the organ and the gate would be ignored within a week. Pinned as a test so the decision is visible."""
    r = audit_process(ANSWER_MODULE)
    assert r["answer_path_reached"] is True
    assert "numpy" not in DONOR_RUNTIME_MODULES
    assert r["verdict"] == "CLEAR", "the organ imports numpy; a runtime classed here would break the audit"


def test_the_audit_judges_itself_and_passes():
    """An audit that exempts its own code is a ritual. The auditor is run over itself: it must reach no answer path
    and import no donor runtime -- and it genuinely cannot, since it only reads source."""
    r = audit_process("tools/mp_e12_process_audit.py", declared="offline_extraction")
    assert r["verdict"] == "CLEAR", r
    assert r["reaches_donor_runtime_module"] == []
    mods = _surface_imports("tools/mp_e12_process_audit.py", ROOT)
    assert not (mods & set(DONOR_RUNTIME_MODULES)), mods


def test_closure_reports_its_own_blind_spot_instead_of_hiding_it(tmp_path):
    """Dynamic imports are counted, not followed. A fixture that uses importlib must show up in the count -- if the
    audit claimed CLEAR with an unfollowed edge and reported nothing, the CLEAR would be a lie of omission."""
    (tmp_path / "dyn.py").write_text(
        "import importlib\nm = importlib.import_module('answer_mod')\n", encoding="utf-8")
    (tmp_path / "answer_mod.py").write_text(ANSWER_MOD, encoding="utf-8")
    cfg = AuditConfig(root=tmp_path, answer_module="answer_mod.py", answer_symbols=("answer",),
                      deployment_loop="main_entry.py")
    r = audit_process("dyn.py", cfg=cfg)
    assert r["dynamic_imports_unfollowed"] == 1
    assert r["answer_path_reached"] is False, "the edge was not followed -- which is exactly why it is reported"


def test_the_audit_computes_the_position_that_makes_the_ruling_enforceable(tmp_path):
    """Item 2, the part that must be measured rather than asserted.

    The >=10x clause needs a donor-executing act to produce its denominator. The audit counts how many answer-path
    processes can host such an act -- on the real tree the answer is zero -- so the clause has no executable form on
    the answer path whichever way D-MPE12-09 is ruled. The test asserts the count AND the shape of the argument,
    without asserting a ruling.
    """
    import json
    out = tmp_path / "r.json"
    main(["--out", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    pos = r["d_mpe12_09_structural_position"]
    assert pos["answer_path_processes_able_to_host_the_denominator"] == 0
    assert pos["measured_no_answer_path_host"] is True
    assert pos["offline_executing_processes_audited"], "the synthetic/offline executor class must be populated"
    assert "no answer path" in pos["if_the_ruling_is_no"] or "cannot be produced" in pos["if_the_ruling_is_no"]
    assert "offline artifact" in pos["if_the_ruling_is_yes"]
    # the category statement must name BOTH clauses and must not pick one
    cat = r["benchmark_process_category_under_R11_as_written"]["category_as_written"]
    assert "UNAUTHORISED BUT NOT BARRED" in cat
    assert len(r["benchmark_process_category_under_R11_as_written"]["the_two_clauses_that_disagree"]) == 2


def test_main_runs_and_returns_zero_when_there_is_no_breach(tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["--out", str(out)])
    assert rc == 0, "the real tree must not report a breach"
    import json
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["counts"]["breach"] == 0
    assert r["audit_verdict"] in ("CLEAR", "EXPOSURE")
