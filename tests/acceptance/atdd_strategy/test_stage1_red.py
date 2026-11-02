"""Scenario group C of the four-layer acceptance strategy: the stage 1 red.

Stage 1 ends when the acceptance suite fails because the driver is not written
yet. With `--loop outer`, `compass tdd-red` records that failure when pytest
reports it as a setup error from the driver-factory fixture, or as a collection
error, for a module of the project. An exit 4 is still refused, and its message
names the fix when `conftest.py` imports the driver at module level. A red
recorded at refine moves no document and writes no `.red` marker.

The specification is `acceptance-criteria.md` of the Compass issue
`atdd-strategy` (ayeo-io/compass-delivery#307), built in
ayeo-io/compass-delivery#324. Each test names the scenario it checks; the
suites run real pytest, and `support.py` builds them.
"""
from __future__ import annotations

import json
import subprocess
from xml.etree import ElementTree

import pytest

from tests.acceptance.atdd_strategy import support

HOOK = support.ROOT / "hooks" / "pre-tool.sh"


def _at_refine(tmp_path, **suite):
    project = support.Project(tmp_path / "repo")
    return project, support.stage_one_issue(project, **suite)


def _red(issue, *flags):
    """`compass tdd-red --loop outer` on the suite, with `flags` before the command."""
    return issue.run("tdd-red", "--issue", issue.slug, "--loop", "outer", *flags,
                     "--", *support.PYTEST)


def _records(issue):
    """`{file name: record}` of the red records on disk."""
    folder = issue.dir / "evidence"
    if not folder.is_dir():
        return {}
    return {p.name: json.loads(p.read_text(encoding="utf-8"))
            for p in folder.glob("red*.json")}


def _hook(project):
    """`(exit code, stderr)` of the pre-tool hook judging an edit to a production
    file of the issue."""
    payload = {"tool_name": "Edit", "tool_input": {
        "file_path": str(project.root / "shop" / "orders.py"),
        "old_string": "ORDERS = []", "new_string": "ORDERS = ['book']"}}
    r = subprocess.run(["bash", str(HOOK)], input=json.dumps(payload), cwd=project.root,
                       env=support.env(project.root), capture_output=True, text=True,
                       timeout=60)
    return r.returncode, r.stderr


# --- `TRC-C1` ------------------------------------------------------------------------------

def test_trc_c1(tmp_path):
    """An import red raised in a specification file is recorded as the outer-loop red."""
    _, issue = _at_refine(tmp_path, conftest="no fixture", spec="imports the driver")
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 0, out + err
    record = _records(issue)["red-TRC-1.outer.json"]
    assert record["loop"] == "outer"
    assert record["scenario"] == "TRC-1"
    assert record["red_kind"] == "import"
    assert record["missing_modules"] == ["shop.driver"]


# --- `TRC-C2` ------------------------------------------------------------------------------

def test_trc_c2(tmp_path):
    """Stage 1 ends in a recorded red when the import fails in conftest.py."""
    project, issue = _at_refine(tmp_path, conftest="fixture import")
    code, report, _ = support.run_pytest(project.root)
    assert code == 1
    errors = [e.get("message") for e in ElementTree.fromstring(report).iter("error")]
    assert errors == ["failed on setup with \"ModuleNotFoundError: No module named "
                      "'shop.driver'\""], errors
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 0, out + err
    record = _records(issue)["red-TRC-1.outer.json"]
    assert (record["loop"], record["scenario"]) == ("outer", "TRC-1")
    assert record["missing_modules"] == ["shop.driver"]


# --- `TRC-C3` ------------------------------------------------------------------------------

@pytest.mark.parametrize("fault, conftest, extra, quoted", [
    ("has a syntax error in conftest.py", "syntax error", (),
     "pytest's first error line: \"ImportError while loading conftest"),
    ("is run with a command-line option pytest does not know", "fixture import",
     ("--no-such-option",), "pytest's first error line: \"ERROR: usage:"),
    ("makes pytest exit 4 with nothing on stderr", "silent exit 4", (),
     "pytest printed nothing on stderr"),
])
def test_trc_c3(tmp_path, fault, conftest, extra, quoted):
    """An exit 4 that is not a missing module is refused."""
    project, issue = _at_refine(tmp_path, conftest=conftest)
    assert support.run_pytest(project.root, *extra)[0] == 4
    code, out, err = issue.run("tdd-red", "--issue", issue.slug, "--loop", "outer",
                               "--scenario", "TRC-1", "--", *support.PYTEST, *extra)
    assert code == 2, out + err
    assert _records(issue) == {}
    message = support.refusal(err)
    assert "a setup error, not a red" in message, message
    assert quoted in message, message


# --- `TRC-C4` ------------------------------------------------------------------------------

def test_trc_c4(tmp_path):
    """An import error is still not a red for the inner loop."""
    _, issue = _at_refine(tmp_path, conftest="fixture import")
    code, out, err = issue.run("tdd-red", "--issue", issue.slug, "--loop", "inner",
                               "--scenario", "TRC-1", "--", *support.PYTEST)
    recorded = json.loads((support.FIXTURES / "compass-8.0.4" / "inner-setup-error.json")
                          .read_text(encoding="utf-8"))
    assert {"exit": code, "message": support.refusal(err)} == recorded, out + err
    assert _records(issue) == {}


# --- `TRC-C6` ------------------------------------------------------------------------------

def _draft_documents(project, issue):
    folder = f"docs/compass/{support.CREATED}-{issue.slug}"
    (project.root / folder).mkdir(parents=True, exist_ok=True)
    for kind in ("requirements-review", "acceptance-criteria"):
        rel = f"{folder}/{kind}.md"
        (project.root / rel).write_text(f"# {kind}\n", encoding="utf-8")
        issue.must("issue", "artifact", "set", kind, "--status", "draft", "--path", rel,
                   "--issue", issue.slug)


def _statuses(issue):
    return {a["kind"]: a.get("status") for a in issue.manifest().get("artifacts") or []
            if a.get("kind") in ("acceptance-criteria", "requirements-review")}


def test_trc_c6(tmp_path):
    """The stage 1 red at refine moves no document and unlocks no code."""
    project, issue = _at_refine(tmp_path)
    _draft_documents(project, issue)
    (project.root / ".compass" / "current-task").write_text(issue.slug + "\n",
                                                            encoding="utf-8")
    assert _statuses(issue) == {"acceptance-criteria": "draft",
                                "requirements-review": "draft"}
    before = _hook(project)
    assert before[0] == 2, before
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 0, out + err
    assert _statuses(issue) == {"acceptance-criteria": "draft",
                                "requirements-review": "draft"}
    assert not (issue.dir / ".red").exists()
    assert _records(issue)["red-TRC-1.outer.json"]["before_implement"] is True
    assert _hook(project) == before


def test_trc_c6_the_issue_still_reads_as_not_started(tmp_path):
    """A stage 1 red is not the start of implement: `compass next` keeps the stage."""
    _, issue = _at_refine(tmp_path)
    issue.approach_record()
    before = issue.must("next", "--issue", issue.slug)
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 0, out + err
    assert issue.must("next", "--issue", issue.slug) == before


@pytest.mark.parametrize("approach, registered", [
    ("quick-fix", None), ("hotfix", None), ("regular", "technical-design")])
def test_trc_c6_an_outer_red_after_refine_writes_the_marker(tmp_path, approach, registered):
    """Where refine is collapsed, or plan has registered its design, the outer-loop
    red is the first record of implement, as before (Q7)."""
    project, issue = _at_refine(tmp_path, approach=approach)
    if registered:
        rel = f"docs/compass/{support.CREATED}-{issue.slug}/{registered}.md"
        (project.root / rel).parent.mkdir(parents=True, exist_ok=True)
        (project.root / rel).write_text("# design\n", encoding="utf-8")
        issue.must("issue", "artifact", "set", registered, "--status", "draft",
                   "--path", rel, "--issue", issue.slug)
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 0, out + err
    assert (issue.dir / ".red").exists()
    assert "before_implement" not in _records(issue)["red-TRC-1.outer.json"]


# --- `TRC-C7` ------------------------------------------------------------------------------

def test_trc_c7(tmp_path):
    """A driver imported at module level in conftest.py is refused with the fix."""
    project, issue = _at_refine(tmp_path, conftest="module import")
    code, report, _ = support.run_pytest(project.root)
    assert (code, report) == (4, None)
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 2, out + err
    assert _records(issue) == {}
    message = support.refusal(err)
    assert "import the driver inside the driver-factory fixture" in message, message
    assert "'shop.driver'" in message, message


# --- `TRC-C8` ------------------------------------------------------------------------------

def test_trc_c8(tmp_path):
    """A setup error for a module outside the project is not a red."""
    project, issue = _at_refine(tmp_path, conftest="third-party import")
    code, report, _ = support.run_pytest(project.root)
    assert code == 1
    assert "failed on setup" in report and "orders_vendor_sdk" in report
    code, out, err = _red(issue, "--scenario", "TRC-1")
    assert code == 2, out + err
    assert _records(issue) == {}
    message = support.refusal(err)
    assert "'orders_vendor_sdk' is not a module of this project" in message, message


# --- one run, several scenarios (plan decision Q14) ---------------------------------------

def test_one_run_binds_the_red_to_every_scenario(tmp_path):
    """`--every-scenario` writes one record per scenario from one run."""
    _, issue = _at_refine(tmp_path, scenarios=("TRC-1", "TRC-2"))
    code, out, err = _red(issue, "--every-scenario")
    assert code == 0, out + err
    records = _records(issue)
    assert sorted(records) == ["red-TRC-1.outer.json", "red-TRC-2.outer.json"]
    one, two = records["red-TRC-1.outer.json"], records["red-TRC-2.outer.json"]
    assert one["run_id"] == two["run_id"]
    assert one["scenarios_in_run"] == two["scenarios_in_run"] == ["TRC-1", "TRC-2"]
    assert (one["scenario"], two["scenario"]) == ("TRC-1", "TRC-2")


def test_repeated_scenario_flags_bind_the_same_run(tmp_path):
    _, issue = _at_refine(tmp_path, scenarios=("TRC-1", "TRC-2"))
    code, out, err = _red(issue, "--scenario", "TRC-1", "--scenario", "TRC-2")
    assert code == 0, out + err
    assert sorted(_records(issue)) == ["red-TRC-1.outer.json", "red-TRC-2.outer.json"]


def test_a_scenario_with_no_failed_test_in_the_run_is_refused(tmp_path):
    project, issue = _at_refine(tmp_path, scenarios=("TRC-1",))
    issue.must("scenario", "add", "TRC-2", "--issue", issue.slug, "--intent", "INT-1",
               "--title", "Cancel an order", "--test",
               "tests/acceptance/test_cancel.py::test_cancel_order")
    code, out, err = _red(issue, "--every-scenario")
    assert code == 2, out + err
    assert "TRC-2" in err and "tests/acceptance/test_cancel.py::test_cancel_order" in err
    assert _records(issue) == {}


def test_several_scenarios_need_the_outer_loop(tmp_path):
    _, issue = _at_refine(tmp_path, scenarios=("TRC-1", "TRC-2"))
    code, out, err = issue.run("tdd-red", "--issue", issue.slug, "--loop", "inner",
                               "--scenario", "TRC-1", "--scenario", "TRC-2",
                               "--", *support.PYTEST)
    assert code == 2, out + err
    assert "--loop outer" in err
    assert _records(issue) == {}
