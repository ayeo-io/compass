"""Scenario group I of the four-layer acceptance strategy: readiness names the
support code a project has not built, and the missing code blocks nothing.

The specification is `acceptance-criteria.md` of the Compass issue
`support-code-readiness` (ayeo-io/compass-delivery#329). Each test names the
scenario it checks; `support.py` builds the projects.

The project names each piece of support code in `project.acceptance_support`.
Readiness tests only that each named path exists; it reads no project code.
"""
from __future__ import annotations

import json
import re
import sys

import pytest
import yaml

from tests.acceptance.atdd_strategy import support
from tests.acceptance.atdd_strategy.support import ROOT

CHECK = "acceptance-support-present"

#: Each piece of support code: its settings key, the name readiness prints and
#: where the Python reference example keeps it.
PIECES = {
    "alias_helper": ("alias helper", "tests/acceptance/alias.py"),
    "driver_factory": ("driver factory", "conftest.py"),
    "dsl_root": ("DSL root", "tests/acceptance/dsl.py"),
    "layering_test": ("layering test", "tests/acceptance/test_layering.py"),
}
ALL = tuple(PIECES)


def _project(tmp_path, present, named=ALL, name="repo"):
    """A project whose settings name each piece in `named`, and whose files hold
    each piece in `present`. A piece named but not present names a path that
    does not exist."""
    project = support.Project(tmp_path / name)
    for key in present:
        path = project.root / PIECES[key][1]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# support code\n", encoding="utf-8")
    project.setting(None, project={
        "acceptance_support": {key: PIECES[key][1] for key in named}})
    return project


def _readiness(project):
    code, out, err = project.run("readiness", "--json")
    assert code == 0, out + err
    return json.loads(out)


def _status(document):
    """What readiness decides about the project: each signal, the score and the floor."""
    return {"signals": [(s["id"], s["result"]) for s in document["signals"]],
            "score": document["score"], "floor_met": document["floor_met"],
            "below_floor": document["below_floor"]}


def _support_lines(text):
    """`{piece name: line}` of the support-code block of `compass readiness`."""
    names = [name for name, _ in PIECES.values()]
    lines = {}
    for line in text.splitlines():
        for name in names:
            if re.match(rf"\s+{re.escape(name)}\s+(present|missing)\b", line):
                lines[name] = line
    return lines


# --- `TRC-I1` ------------------------------------------------------------------------------

@pytest.mark.parametrize("present, missing", [
    ((), ALL),
    (("alias_helper", "dsl_root"), ("driver_factory", "layering_test")),
    (ALL, ()),
])
def test_trc_i1(tmp_path, present, missing):
    """Readiness names the missing support code."""
    project = _project(tmp_path, present)
    document = _readiness(project)
    pieces = {p["key"]: p for p in document["support_code"]["pieces"]}
    assert sorted(k for k, p in pieces.items() if p["result"] == "missing") == sorted(missing)
    assert document["support_code"]["missing"] == [PIECES[k][0] for k in ALL if k in missing]

    code, out, err = project.run("readiness")
    assert code == 0, out + err
    lines = _support_lines(out)
    assert set(lines) == {name for name, _ in PIECES.values()}, out
    for key, (name, path) in PIECES.items():
        state = "missing" if key in missing else "present"
        assert re.match(rf"\s+{re.escape(name)}\s+{state}\b", lines[name]), lines[name]
        assert path in lines[name], lines[name]

    complete = _readiness(_project(tmp_path, ALL, name="complete"))
    assert _status(document) == _status(complete)


def test_trc_i1_a_piece_with_no_setting_is_missing(tmp_path):
    """A piece the settings do not name is missing, and the line names the setting
    to add (`TRC-I1`)."""
    project = _project(tmp_path, ALL, named=("driver_factory", "dsl_root", "layering_test"))
    document = _readiness(project)
    assert document["support_code"]["missing"] == ["alias helper"]
    out = project.run("readiness")[1]
    line = _support_lines(out)["alias helper"]
    assert "missing" in line and "project.acceptance_support.alias_helper" in line, line
    assert "compass.yml" in line, line


def test_trc_i1_a_path_outside_the_project_is_missing(tmp_path):
    """Readiness tests only paths inside the project root, so a path that leaves
    it is missing even when it exists (`TRC-I1`)."""
    project = _project(tmp_path, ALL)
    (tmp_path / "outside.py").write_text("# elsewhere\n", encoding="utf-8")
    settings = yaml.safe_load((project.root / "compass.yml").read_text(encoding="utf-8"))
    settings["project"]["acceptance_support"]["alias_helper"] = "../outside.py"
    (project.root / "compass.yml").write_text(yaml.safe_dump(settings), encoding="utf-8")
    document = _readiness(project)
    assert document["support_code"]["missing"] == ["alias helper"]
    piece = document["support_code"]["pieces"][0]
    assert "outside the project root" in piece["reason"], piece


@pytest.mark.parametrize("value", ["tests/acceptance", {"alias_helper": ["a.py"]}])
def test_trc_i1_a_setting_that_is_not_paths_is_refused(tmp_path, value):
    """A setting readiness cannot read is refused with exit 2 before any command
    runs, so a typo does not report every piece as missing (`TRC-I1`)."""
    project = support.Project(tmp_path / "repo")
    project.setting(None, project={"acceptance_support": value})
    code, out, err = project.run("readiness")
    assert code == 2, out + err
    assert "project.acceptance_support" in err, err
    assert not (project.root / ".compass" / "readiness.yml").exists()


def test_trc_i1_an_opted_out_project_gets_no_support_code_block(tmp_path):
    """A project that turned the strategy off is told the block is not reported
    (`TRC-I1`)."""
    project = support.Project(tmp_path / "repo")
    project.setting({"state": "off", "reason": "no client interface yet"})
    document = _readiness(project)
    assert document["support_code"] is None
    out = project.run("readiness")[1]
    assert not _support_lines(out), out
    assert "four-layer acceptance strategy is off" in out, out


# --- `TRC-I2` ------------------------------------------------------------------------------

def _claim_limit():
    """The claim limit as `governance/guardrails.yml` states it, in the description
    of the check that reports it."""
    rules = yaml.safe_load((ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8"))
    description = " ".join(rules["checks"][CHECK]["description"].split())
    found = re.search(r"Claim limit: (.*?\.)", description)
    assert found, description
    return found.group(1)


def _quick_fix(project):
    """The first in-scope issue of `project`: a quick fix, its test committed and failing."""
    root = project.root
    (root / "data").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi\n", encoding="utf-8")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_greeting.py").write_text(
        "import pathlib\n\n\ndef test_greeting():\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
        "    assert p.read_text().strip() == 'Hello'\n", encoding="utf-8")
    support.git(root, "add", "-A")
    support.git(root, "commit", "-q", "-m", "greeting and support code")
    issue = support.Issue(project, "greet")
    issue.must("quick-fix", "start", "greet", "--risk", "trivial - a text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one line", "--intent", "The greeting says Hello.",
               "--scenario", "Given the greeting, when it is read, then it says Hello.",
               "--test", "tests/test_greeting.py::test_greeting")
    return issue


def test_trc_i2(tmp_path):
    """Readiness reports and does not block."""
    project = _project(tmp_path, ("driver_factory", "dsl_root", "layering_test"))
    issue = _quick_fix(project)
    assert issue.manifest()["acceptance_strategy"]["applies"] is True

    # The issue passes every gate, and its next stage is ship.
    command = ["--", sys.executable, "-m", "pytest", "-q", "tests/test_greeting.py::test_greeting"]
    issue.must("tdd-red", "--issue", "greet", "--scenario", "TRC-001", *command)
    (project.root / "data" / "greeting.txt").write_text("Hello\n", encoding="utf-8")
    issue.must("quick-fix", "finish", "--issue", "greet", "--no-commit", "-m", "Say Hello",
               "--release-note", "The greeting says Hello.", *command)
    gates = issue.manifest().get("gates") or []
    assert gates and all(g.get("status") == "pass" for g in gates), gates
    assert issue.must("next", "--issue", "greet").startswith("Ship"), "the next stage is ship"

    code, document = issue.check()
    row = [c for c in document["checks"] if c["name"] == CHECK]
    assert len(row) == 1, document["checks"]
    assert row[0]["status"] == "advisory", row
    assert "alias helper" in row[0]["detail"], row
    assert _claim_limit() in " ".join(row[0]["detail"].split()), row
    # The advice alone does not make compass check exit 1.
    assert support.findings(document) == [(CHECK, "advisory")], document["checks"]
    assert code == 0, document


def _assessed_with_green(tmp_path, present):
    """An in-scope regular issue with an outer-loop red and green on record."""
    project = _project(tmp_path, present)
    issue = project.issue("change")
    code, out, err = issue.assess()
    assert code == 0, out + err
    issue.must("tdd-red", "--issue", "change", "--loop", "outer", "--", "sh", "-c",
               "echo 'test_one FAILED'; exit 1")
    issue.must("tdd-green", "--issue", "change", "--loop", "outer", "--", "sh", "-c",
               "echo 'test_one PASSED'")
    return issue


def _support_row(issue):
    code, document = issue.check()
    row = [c for c in document["checks"] if c["name"] == CHECK]
    assert len(row) == 1, document["checks"]
    return row[0]


def test_trc_i2_all_four_pieces_pass_the_check(tmp_path):
    """With every piece named and present the check passes, so the advice in
    `test_trc_i2` comes from the missing alias helper alone (`TRC-I2`)."""
    row = _support_row(_assessed_with_green(tmp_path, ALL))
    assert row["status"] == "pass", row


def test_trc_i2_an_issue_with_no_green_is_not_judged(tmp_path):
    """The claim limit is about what a green lets the issue claim, so an issue
    with no green on record has nothing to check yet (`TRC-I2`)."""
    project = _project(tmp_path, ())
    issue = project.issue("change")
    code, out, err = issue.assess()
    assert code == 0, out + err
    row = _support_row(issue)
    assert row["status"] == "nothing-to-check", row
    assert "no green" in row["detail"], row


def test_trc_i2_the_advice_stays_advice_without_a_generation(tmp_path):
    """An issue judged by the governance files, with no stored generation, still
    reports the missing support code as advice, not as a failure (`TRC-I2`)."""
    issue = _assessed_with_green(tmp_path, ())
    body = issue.manifest()
    del body["generation"]
    issue.write_manifest(body)
    # With no compass.yml the issue is judged by governance/guardrails.yml, which
    # holds no severity; the settings move to the old file.
    root = issue.project.root
    settings = yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    (root / "compass.yml").unlink()
    (root / ".compass" / "config.yml").write_text(
        yaml.safe_dump({"project": settings["project"]}), encoding="utf-8")
    row = _support_row(issue)
    assert row["status"] == "advisory", row
