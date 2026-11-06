"""Scenario group F of the four-layer acceptance strategy: the isolation proof
and the layering record, and the checks that need them at the verify stage.

`compass isolation record` runs the project's suite in parallel once, then
runs each scenario's declared tests twice, and writes an `isolation-proof`
record of the exit codes. `compass layering record` runs the project's own
layering test and writes a `layering` record. Only these commands write the
two types: `compass evidence add` refuses both. `isolation-proven` and
`layering-test-passed` read the records and never the project's test code
(ADR-086).

The specification is `acceptance-criteria.md` of the Compass issue
`atdd-strategy`. This file holds its scenarios of isolation and layering
(`TRC-F1` to `TRC-F14`), the candidate scenario (`TRC-H5`), the routing
scenarios (`TRC-A4`, `TRC-A7`, `TRC-A8`, `TRC-A10`, `TRC-A18` and `TRC-A20`)
and the end-to-end scenario (`TRC-X1`), for ayeo-io/compass-delivery#328.
Each test names the scenario it checks; `support.py` builds the projects.
`TRC-A16` was the retrospective's, which 9.0.0 removed (ADR-093).
"""
from __future__ import annotations

import ast
import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest
import yaml

from tests.acceptance.atdd_strategy import support
from tests.acceptance.atdd_strategy.support import ROOT

# `approval_support` holds the hook input a person's typed approval sends.
if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

ISOLATION = "isolation-proven"
LAYERING = "layering-test-passed"
PROOF = "evidence/isolation-proof.json"
LAYERS = "evidence/layering.json"
FAIL = "sh", "-c", "echo 'test_place_order FAILED'; exit 1"
PASS = "sh", "-c", "echo 'test_place_order PASSED'"
OK = "sh -c 'exit 0'"
REPEAT_OK = "sh -c 'exit 0' {tests}"
LAYERING_OK = ("--test-path", "tests/acceptance/test_layering.py", "--", "sh", "-c", "exit 0")
EXAMPLE = ROOT / "examples" / "atdd-adapters" / "python"
PYTEST = f"{sys.executable} -m pytest -p xdist.plugin -p no:cacheprovider"
#: Every piece of support code, named at a path the stage 1 suite writes, so the
#: advisory support-code check has nothing to report.
SUPPORT_PATHS = {"alias_helper": "tests/acceptance/conftest.py",
                 "driver_factory": "tests/acceptance/conftest.py",
                 "dsl_root": "tests/acceptance", "layering_test": "tests/acceptance"}


def _project(tmp_path, **settings):
    project = support.Project(tmp_path / "repo")
    support.stage_one_suite(project.root)
    project.setting(None, project={"acceptance_support": SUPPORT_PATHS}, **settings)
    return project


def _issue(project, slug="orders", approach="regular", scenarios=None, named=support.NAMED,
           expected=None, outer=True):
    """An issue with each scenario declaring its tests, and, with `outer`, an
    outer-loop red and an outer-loop green that name a candidate and a client."""
    issue = project.issue(slug, approach=approach)
    code, out, err = issue.assess(expected=expected)
    assert code == 0, out + err
    for scenario, tests in (scenarios or {"TRC-1": (support.SPEC_TEST,)}).items():
        argv = ["scenario", "add", scenario, "--issue", slug, "--intent", "INT-1",
                "--title", "Place an order"]
        for test in tests:
            argv += ["--test", test]
        issue.must(*argv)
    if outer:
        issue.must("tdd-red", "--issue", slug, "--loop", "outer", "--every-scenario",
                   "--", *FAIL)
        issue.must("tdd-green", "--issue", slug, "--loop", "outer", "--every-scenario",
                   *named, "--", *PASS)
    return issue


def _isolation(issue, parallel=OK, repeat=REPEAT_OK, named=support.NAMED):
    return issue.run("isolation", "record", "--issue", issue.slug, *named,
                     "--parallel", parallel, "--repeat", repeat)


def _must_isolation(issue, **kw):
    code, out, err = _isolation(issue, **kw)
    assert code == 0, out + err
    return out


def _layering(issue, *argv):
    return issue.run("layering", "record", "--issue", issue.slug, *(argv or LAYERING_OK))


def _must_layering(issue, *argv):
    code, out, err = _layering(issue, *argv)
    assert code == 0, out + err
    return out


def _record(issue, rel):
    return json.loads((issue.dir / rel).read_text(encoding="utf-8"))


def _rewrite(issue, rel, change):
    """Rewrite a record after `change(record)`, and stamp it again, so its identity
    covers what it holds and only the change is under test."""
    from compass_pkg.tdd import _stamp_identity
    record = _record(issue, rel)
    change(record)
    record_id, digest = _stamp_identity(record)
    (issue.dir / rel).write_text(json.dumps(record, indent=2), encoding="utf-8")
    body = issue.manifest()
    for entry in body.get("evidence") or []:
        if entry.get("path") == rel:
            entry["record_id"], entry["content_digest"] = record_id, digest
    issue.write_manifest(body)


def _rendered_check(issue):
    """`compass check`, whose only findings are the records'. Before 9.0.0 the issue
    page was rendered first; 9.0.0 renders nothing (ADR-091)."""
    return issue.check()


def _row(document, name):
    rows = [c for c in document["checks"] if c["name"] == name]
    assert len(rows) == 1, (name, document["checks"])
    return rows[0]


def _commit(project, message="change"):
    support.git(project.root, "add", "-A", ":!.compass", ":!compass.yml")
    support.git(project.root, "commit", "-q", "-m", message)


# --- `TRC-F1` ------------------------------------------------------------------------------

def test_trc_f1(tmp_path):
    """An isolation proof is recorded from a parallel run and a repeat run."""
    issue = _issue(_project(tmp_path), scenarios={
        "TRC-1": (support.SPEC_TEST,),
        "TRC-2": (support.SPEC + "::test_cancel_order", support.SPEC + "::test_refund")})
    calls = issue.project.root / "calls.txt"
    out = _must_isolation(
        issue, parallel=f"sh -c 'echo parallel >> {calls}'",
        repeat=f"sh -c 'echo \"$*\" >> {calls}' repeat {{tests}}")
    record = _record(issue, PROOF)
    assert record["type"] == "isolation-proof"
    assert record["parallel"]["exit_code"] == 0, record
    assert record["parallel"]["argv"] == ["sh", "-c", f"echo parallel >> {calls}"]
    assert [(r["scenario"], r["tests"], r["runs"], r["same"]) for r in record["repeat"]] == [
        ("TRC-1", [support.SPEC_TEST], [0, 0], True),
        ("TRC-2", [support.SPEC + "::test_cancel_order", support.SPEC + "::test_refund"],
         [0, 0], True)]
    assert (record["candidate"], record["candidate_kind"], record["client"]) \
        == ("build-417", "deployed", "api"), record
    assert record["tree_id"] and record["timestamp"], record
    # One parallel run, then each scenario's declared tests twice, with no shell.
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "parallel", support.SPEC_TEST, support.SPEC_TEST,
        f"{support.SPEC}::test_cancel_order {support.SPEC}::test_refund",
        f"{support.SPEC}::test_cancel_order {support.SPEC}::test_refund"]
    entry = next(e for e in issue.manifest()["evidence"] if e["type"] == "isolation-proof")
    assert entry["path"] == PROOF and entry["record_id"] == record["record_id"], entry
    assert "isolation-proof" in out


@pytest.mark.parametrize("change, refusal", [
    ({"repeat": "sh -c 'exit 0'"}, "{tests}"),
    ({"named": ("--candidate", "build-417")}, "names no client"),
    ({"named": ("--candidate", "build-417", "--client", "smoke")}, "api, web, cli"),
])
def test_trc_f1_refusals(tmp_path, change, refusal):
    """The command refuses a repeat command with no `{tests}`, and a missing or
    unknown client, and writes nothing."""
    issue = _issue(_project(tmp_path))
    code, out, err = _isolation(issue, **change)
    assert code == 2, out + err
    assert refusal in err, err
    assert not (issue.dir / PROOF).exists()


def test_trc_f1_no_declared_test(tmp_path):
    """An issue whose scenarios declare no test has nothing to run twice."""
    issue = _issue(_project(tmp_path), outer=False, scenarios={"TRC-1": ()})
    code, out, err = _isolation(issue)
    assert code == 2, out + err
    assert "declares no test" in err, err
    assert not (issue.dir / PROOF).exists()


# --- `TRC-F2` and `TRC-F7`: a missing record -----------------------------------------------

def test_trc_f2(tmp_path):
    """Isolation is proven, not asserted."""
    issue = _issue(_project(tmp_path))
    _must_layering(issue)
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION)
    assert row["status"] == "fail", row
    assert "no isolation-proof record" in row["detail"], row
    assert "compass isolation record" in row["detail"], row
    assert _row(document, LAYERING)["status"] == "pass"


def test_trc_f7(tmp_path):
    """The verify stage without a layering record fails."""
    issue = _issue(_project(tmp_path))
    _must_isolation(issue)
    code, document = issue.check()
    assert code == 1
    row = _row(document, LAYERING)
    assert row["status"] == "fail", row
    assert "no layering record" in row["detail"], row
    assert "compass layering record" in row["detail"], row
    assert _row(document, ISOLATION)["status"] == "pass"


# --- `TRC-F3` and `TRC-F4`: a proof that fails ----------------------------------------------

#: A scenario that signs up with a fixed email address in the store `$STORE`, and
#: fails when the address is taken.
FIXED_EMAIL = ("import os\nfrom pathlib import Path\n\n\n"
               "def test_sign_up():\n"
               "    store = Path(os.environ['STORE'])\n"
               "    store.mkdir(exist_ok=True)\n"
               "    account = store / 'ann@example.com'\n"
               "    assert not account.exists(), 'ann@example.com is taken'\n"
               "    account.touch()\n")
#: Two scenarios that each hold one lock file for two seconds: in order they pass,
#: and on two workers the second finds the lock taken.
SHARED_LOCK = ("import os\nimport time\n\n\n"
               "def _hold():\n"
               "    fd = os.open('suite.lock', os.O_CREAT | os.O_EXCL)\n"
               "    time.sleep(2)\n"
               "    os.close(fd)\n"
               "    os.remove('suite.lock')\n\n\n"
               "def test_archive():\n    _hold()\n\n\n"
               "def test_restore():\n    _hold()\n")


def _suite(project, name, body):
    path = project.root / "tests" / "acceptance" / name
    path.write_text(body, encoding="utf-8")
    (project.root / "tests" / "acceptance" / "conftest.py").write_text("", encoding="utf-8")
    (project.root / ".gitignore").write_text("store-*/\nsuite.lock\n", encoding="utf-8")
    _commit(project, "the suite")
    return f"tests/acceptance/{name}"


def test_trc_f3(tmp_path):
    """A scenario that gives a different result on its second run fails the proof."""
    project = _project(tmp_path)
    spec = _suite(project, "test_accounts.py", FIXED_EMAIL)
    issue = _issue(project, scenarios={"TRC-1": (f"{spec}::test_sign_up",)})
    # Each command has its own store, as each run of the example makes a new one.
    _must_isolation(issue, parallel=f"env STORE=store-parallel {PYTEST} -n 2 {spec}",
                    repeat=f"env STORE=store-repeat {PYTEST} {{tests}}")
    record = _record(issue, PROOF)
    assert record["parallel"]["exit_code"] == 0, record
    (entry,) = record["repeat"]
    assert entry["runs"][0] == 0 and entry["runs"][1] != 0, entry
    assert entry["same"] is False
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION)
    assert row["status"] == "fail", row
    assert "TRC-1" in row["detail"] and "second run failed" in row["detail"], row


def test_trc_f4(tmp_path):
    """A suite that fails in parallel fails the proof."""
    project = _project(tmp_path)
    spec = _suite(project, "test_todos.py", SHARED_LOCK)
    issue = _issue(project, scenarios={"TRC-1": (f"{spec}::test_archive",),
                                       "TRC-2": (f"{spec}::test_restore",)})
    in_order = support.subprocess.run([*PYTEST.split(), spec], cwd=project.root,
                                      env=support.env(project.root), capture_output=True)
    assert in_order.returncode == 0, in_order.stdout
    _must_isolation(issue, parallel=f"{PYTEST} -n 2 {spec}", repeat=f"{PYTEST} {{tests}}")
    record = _record(issue, PROOF)
    assert record["parallel"]["exit_code"] != 0, record
    assert all(r["runs"] == [0, 0] for r in record["repeat"]), record
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION)
    assert row["status"] == "fail", row
    assert PROOF in row["detail"] and "the parallel run failed" in row["detail"], row


# --- `TRC-F5`, `TRC-F11` and `TRC-F12`: a layering record that passes ------------------------

def test_trc_f5(tmp_path):
    """A passing layering record meets the requirement."""
    issue = _issue(_project(tmp_path))
    _must_isolation(issue)
    _must_layering(issue)
    record = _record(issue, LAYERS)
    assert (record["type"], record["command"], record["exit_code"], record["passed"]) \
        == ("layering", "sh -c exit 0", 0, True), record
    code, document = issue.check()
    row = _row(document, LAYERING)
    assert row["status"] == "pass", row
    assert support.strategy_findings(document) == [], document["checks"]


def test_trc_f11(tmp_path):
    """A layering test in any language meets the requirement."""
    project = _project(tmp_path)
    script = project.root / "tests" / "acceptance" / "check_layers.sh"
    script.write_text("#!/bin/sh\necho 'every layer calls only the layer below it'\nexit 0\n",
                      encoding="utf-8")
    script.chmod(0o755)
    _commit(project, "the layering script")
    issue = _issue(project)
    _must_isolation(issue)
    _must_layering(issue, "--test-path", "tests/acceptance/check_layers.sh", "--",
                   "tests/acceptance/check_layers.sh")
    record = _record(issue, LAYERS)
    assert record["tests_ran"] is None, record
    code, document = _rendered_check(issue)
    assert _row(document, LAYERING)["status"] == "pass"
    assert code == 0, support.findings(document)


LAYERING_TEST = "def test_each_layer_calls_only_the_layer_below():\n    assert True\n"


@pytest.mark.parametrize("given", ["flags", "settings"])
def test_trc_f12(tmp_path, given):
    """The layering record names the test that ran. The command and the path can
    come from the project's settings."""
    layering_test = "tests/acceptance/test_layering.py"
    command = f"{sys.executable} -m pytest -q -p no:cacheprovider {layering_test}"
    settings = {}
    if given == "settings":
        settings = {"project": {"layering_command": command, "acceptance_support":
                                dict(SUPPORT_PATHS, layering_test=layering_test)}}
    project = _project(tmp_path)
    project.setting(None, **(settings or {"project": {"acceptance_support": SUPPORT_PATHS}}))
    (project.root / layering_test).write_text(LAYERING_TEST, encoding="utf-8")
    _commit(project, "the layering test")
    issue = _issue(project)
    argv = () if given == "settings" else ("--test-path", layering_test, "--",
                                           *command.split())
    issue.must("layering", "record", "--issue", issue.slug, *argv)
    record = _record(issue, LAYERS)
    assert record["command"] == command
    assert record["test_path"] == layering_test
    assert (record["exit_code"], record["tests_ran"]) == (0, 1), record
    assert record["tree_id"] and record["timestamp"], record


def test_trc_f12_no_command(tmp_path):
    """With no command and no `project.layering_command` the command refuses."""
    issue = _issue(_project(tmp_path))
    code, out, err = _layering(issue, "--test-path", "tests/acceptance/test_layering.py")
    assert code == 2, out + err
    assert "project.layering_command" in err, err
    assert not (issue.dir / LAYERS).exists()


# --- `TRC-F6`: the project owns the layer rules -----------------------------------------------

def _example(project):
    """The Python reference example, copied into the project root and committed."""
    shutil.copytree(EXAMPLE, project.root, dirs_exist_ok=True, ignore=shutil.ignore_patterns(
        "__pycache__", "*.pyc", ".pytest_cache"))
    _commit(project, "the reference example")


def _unreadable(folder):
    """Make every file under `folder` unreadable; return a function that undoes it."""
    changed = []
    for path in folder.rglob("*"):
        if path.is_file():
            changed.append((path, path.stat().st_mode))
            path.chmod(0)
    return lambda: [p.chmod(stat.S_IMODE(m)) for p, m in changed]


def _outcome(code, document):
    return code, [(c["name"], c["status"]) for c in document["checks"]
                  if c["name"] in support.STRATEGY_CHECKS]


def test_trc_f6(tmp_path):
    """The project owns the layer rules."""
    project = support.Project(tmp_path / "repo")
    _example(project)
    dsl = project.root / "tests" / "acceptance" / "dsl.py"
    text = dsl.read_text(encoding="utf-8")
    dsl.write_text(text.replace(
        "    def archive(self, name):\n",
        "    def archive(self, name):\n        assert name, 'a todo has a name'\n"),
        encoding="utf-8")
    _commit(project, "an assert in the DSL")
    issue = _issue(project, scenarios={"TRC-1": (
        "tests/acceptance/test_todos.py::test_a_completed_todo_can_be_archived",)})
    _must_isolation(issue)
    _must_layering(issue, "--test-path", "tests/acceptance/test_layering.py", "--",
                   *PYTEST.split(), "tests/acceptance/test_layering.py")
    record = _record(issue, LAYERS)
    assert record["exit_code"] != 0 and record["passed"] is False, record
    assert "the DSL makes no check" in record["log_excerpt"], record["log_excerpt"]
    code, document = issue.check()
    assert code == 1
    row = _row(document, LAYERING)
    assert row["status"] == "fail" and LAYERS in row["detail"], row
    before = _outcome(code, document)
    restore = _unreadable(project.root / "tests" / "acceptance")
    try:
        assert not os.access(dsl, os.R_OK) or os.geteuid() == 0
        after = _outcome(*issue.check())
    finally:
        restore()
    assert after == before


# --- `TRC-F8`: an empty or malformed record ---------------------------------------------------

def _no_repeat_result(record):
    for entry in record["repeat"]:
        entry.pop("runs")


@pytest.mark.parametrize("kind, fault, reason", [
    ("isolation-proof", "is not valid JSON", "could not be read"),
    ("isolation-proof", "has no result for the repeat run", "a field is missing"),
    ("layering", "is not valid JSON", "could not be read"),
    ("layering", "shows that 0 tests ran", "no test ran"),
])
def test_trc_f8(tmp_path, kind, fault, reason):
    """An empty or malformed strategy record fails, not passes."""
    project = _project(tmp_path)
    (project.root / "tests" / "acceptance" / "test_empty.py").write_text(
        "# no test here\n", encoding="utf-8")
    _commit(project, "an empty test file")
    issue = _issue(project)
    _must_isolation(issue)
    if fault == "shows that 0 tests ran":
        _must_layering(issue, "--", sys.executable, "-m", "pytest", "-q", "-p",
                       "no:cacheprovider", "tests/acceptance/test_empty.py")
        assert _record(issue, LAYERS)["tests_ran"] == 0
    else:
        _must_layering(issue)
    rel = PROOF if kind == "isolation-proof" else LAYERS
    if fault == "is not valid JSON":
        (issue.dir / rel).write_text("{ not json", encoding="utf-8")
    elif fault == "has no result for the repeat run":
        _rewrite(issue, rel, _no_repeat_result)
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION if kind == "isolation-proof" else LAYERING)
    assert row["status"] == "fail", row
    assert rel in row["detail"] and reason in row["detail"], row


def test_trc_f8_a_layering_test_that_only_skips(tmp_path):
    """A layering test whose every test is skipped exits 0, and no test ran."""
    project = _project(tmp_path)
    (project.root / "tests" / "acceptance" / "test_skipped.py").write_text(
        "import pytest\n\n\n@pytest.mark.skip(reason='not written yet')\n"
        "def test_layers():\n    pass\n", encoding="utf-8")
    _commit(project, "a layering test that skips")
    issue = _issue(project)
    _must_isolation(issue)
    _must_layering(issue, "--", sys.executable, "-m", "pytest", "-q", "-p",
                   "no:cacheprovider", "tests/acceptance/test_skipped.py")
    record = _record(issue, LAYERS)
    assert (record["exit_code"], record["tests_ran"], record["passed"]) == (0, 0, False), record
    code, document = issue.check()
    assert code == 1
    row = _row(document, LAYERING)
    assert row["status"] == "fail" and "no test ran" in row["detail"], row


# --- `TRC-F9`: an older tree ---------------------------------------------------------------

@pytest.mark.parametrize("kind", ["isolation-proof", "layering"])
def test_trc_f9(tmp_path, kind):
    """A strategy record made on an older tree does not count."""
    project = _project(tmp_path)
    issue = _issue(project)
    _must_isolation(issue)
    _must_layering(issue)
    rel = PROOF if kind == "isolation-proof" else LAYERS
    made_on = _record(issue, rel)["tree_id"]
    (project.root / "README.md").write_text("base, changed after the records\n",
                                            encoding="utf-8")
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION if kind == "isolation-proof" else LAYERING)
    assert row["status"] == "fail", row
    assert rel in row["detail"] and made_on[:12] in row["detail"], row
    assert "a different tree from the current one" in row["detail"], row


# --- `TRC-F10`: a written note --------------------------------------------------------------

@pytest.mark.parametrize("kind, claim", [("isolation-proof", "isolated"),
                                         ("layering", "layered")])
def test_trc_f10(tmp_path, kind, claim):
    """A written note cannot stand in for a strategy record."""
    issue = _issue(_project(tmp_path))
    if kind == "isolation-proof":
        _must_layering(issue)
    else:
        _must_isolation(issue)
    note = issue.dir / "evidence" / "suite-review.md"
    note.write_text(f"The acceptance suite is {claim}.\n", encoding="utf-8")
    issue.must("evidence", "add", "EV-NOTE", "--issue", issue.slug, "--type", "manual-review",
               "--path", "evidence/suite-review.md")
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION if kind == "isolation-proof" else LAYERING)
    assert row["status"] == "fail", row
    assert f"no {kind} record" in row["detail"], row


@pytest.mark.parametrize("kind, command", [("isolation-proof", "compass isolation record"),
                                           ("layering", "compass layering record")])
def test_trc_f10_evidence_add_refuses_the_types(tmp_path, kind, command):
    """`compass evidence add` refuses both types: only their commands write them."""
    issue = _issue(_project(tmp_path))
    (issue.dir / "evidence" / "hand-written.json").write_text(
        json.dumps({"passed": True, "exit_code": 0}), encoding="utf-8")
    code, out, err = issue.run("evidence", "add", "EV-HAND", "--issue", issue.slug, "--type",
                               kind, "--path", "evidence/hand-written.json")
    assert code == 2, out + err
    assert command in err, err
    assert all(e["id"] != "EV-HAND" for e in issue.manifest()["evidence"])


def _hand_written(issue, kind, how):
    """Register a record of `kind` that its command did not write: a file written by
    hand and added to the manifest, or the command's own record edited afterwards."""
    if how == "edited after it was written":
        rel = PROOF if kind == "isolation-proof" else LAYERS
        record = _record(issue, rel)
        if kind == "isolation-proof":
            record["parallel"]["exit_code"] = 0
        else:
            record["exit_code"] = 0
        (issue.dir / rel).write_text(json.dumps(record, indent=2), encoding="utf-8")
        return rel
    green = _record(issue, "evidence/green-TRC-1.outer.json")
    note = ({"type": kind, "parallel": {"exit_code": 0}, "candidate": green["candidate"],
             "client": "api", "repeat": [{"scenario": "TRC-1", "tests": [support.SPEC_TEST],
                                          "runs": [0, 0]}]}
            if kind == "isolation-proof" else
            {"type": kind, "command": "sh -c 'exit 0'", "exit_code": 0, "tests_ran": 1})
    (issue.dir / "evidence" / "my-note.json").write_text(json.dumps(note), encoding="utf-8")
    body = issue.manifest()
    body["evidence"] = [e for e in body["evidence"] if e.get("type") != kind]
    body["evidence"].append({"id": "EV-NOTE", "type": kind, "path": "evidence/my-note.json"})
    issue.write_manifest(body)
    return "evidence/my-note.json"


@pytest.mark.parametrize("kind, command", [("isolation-proof", "compass isolation record"),
                                           ("layering", "compass layering record")])
@pytest.mark.parametrize("how", ["written by hand and added to the manifest",
                                 "edited after it was written"])
def test_trc_f10_a_record_its_command_did_not_write(tmp_path, kind, command, how):
    """A record registered by editing the manifest, or edited after its command wrote
    it, does not count: its identity must match the registry entry."""
    issue = _issue(_project(tmp_path))
    if kind == "isolation-proof":
        _must_layering(issue)
        _must_isolation(issue, parallel="sh -c 'exit 1'")
    else:
        _must_isolation(issue)
        _must_layering(issue, "--", "sh", "-c", "exit 1")
    rel = _hand_written(issue, kind, how)
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION if kind == "isolation-proof" else LAYERING)
    assert row["status"] == "fail", row
    assert f"{rel} was not written by `{command}`" in row["detail"], row


def test_trc_f10_a_record_that_names_no_tree(tmp_path):
    """Where git can name the tree, a record with no tree id does not count."""
    issue = _issue(_project(tmp_path))
    _must_isolation(issue)
    _must_layering(issue)
    _rewrite(issue, LAYERS, lambda record: record.pop("tree_id"))
    code, document = issue.check()
    assert code == 1
    row = _row(document, LAYERING)
    assert row["status"] == "fail" and f"{LAYERS} names no tree" in row["detail"], row


# --- `TRC-F13`: no parser -------------------------------------------------------------------

#: The modules the four-layer acceptance strategy adds to `cli/compass_pkg/`.
STRATEGY_MODULES = ("acceptance_strategy.py", "candidate_client.py", "green_attempts.py",
                    "isolation.py", "layering.py", "outer_loop.py", "strategy_records.py",
                    "support_code.py")
#: Modules that parse source code. Compass reads records, never the project's code.
PARSERS = {"ast", "tokenize", "token", "lib2to3", "parser", "symtable", "pyclbr",
           "libcst", "parso", "astroid", "tree_sitter", "esprima", "pycparser", "javalang",
           "typed_ast"}


def parser_imports(paths):
    """`[(module, line, name)]` for each import of a parser in the files `paths`,
    by `import`, `from ... import`, `__import__` or `importlib.import_module`."""
    found = []
    for path in paths:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = [node.module]
            elif isinstance(node, ast.Call) and node.args \
                    and isinstance(node.args[0], ast.Constant) \
                    and isinstance(node.args[0].value, str) \
                    and getattr(node.func, "id", getattr(node.func, "attr", None)) \
                    in ("__import__", "import_module"):
                names = [node.args[0].value]
            found += [(Path(path).name, node.lineno, n) for n in names
                      if n.split(".")[0] in PARSERS]
    return found


@pytest.mark.parametrize("state, count", [("as shipped", 0),
                                          ('with a planted "import ast" in one', 1)])
def test_trc_f13(tmp_path, state, count):
    """The code the strategy adds parses no project code."""
    package = ROOT / "cli" / "compass_pkg"
    paths = [package / name for name in STRATEGY_MODULES]
    assert all(p.is_file() for p in paths), [p for p in paths if not p.is_file()]
    if state != "as shipped":
        copy = tmp_path / "isolation.py"
        text = (package / "isolation.py").read_text(encoding="utf-8")
        lines = text.splitlines()
        at = next(n for n, line in enumerate(lines) if line.startswith("import "))
        lines.insert(at, "import ast")
        copy.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths = [copy if p.name == "isolation.py" else p for p in paths]
        assert parser_imports(paths) == [("isolation.py", at + 1, "ast")]
    assert len(parser_imports(paths)) == count


# --- `TRC-F14`: a repeat run that leaves out a test -------------------------------------------

def test_trc_f14(tmp_path):
    """A repeat run that leaves out one of the issue's tests does not count."""
    archive, restore = support.SPEC + "::test_archive", support.SPEC + "::test_restore"
    issue = _issue(_project(tmp_path), scenarios={"TRC-1": (archive,), "TRC-2": (restore,)})
    _must_isolation(issue)
    _must_layering(issue)

    def only_archive(record):
        record["repeat"] = [r for r in record["repeat"] if r["tests"] == [archive]]
    _rewrite(issue, PROOF, only_archive)
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION)
    assert row["status"] == "fail", row
    assert f"{restore} was not run twice" in row["detail"], row
    assert f"{archive} was not run twice" not in row["detail"], row


# --- `TRC-H5`: another candidate ------------------------------------------------------------

def test_trc_h5(tmp_path):
    """An isolation proof made on another candidate does not count."""
    issue = _issue(_project(tmp_path), named=("--candidate", "build-418", "--client", "api"))
    _must_isolation(issue, named=("--candidate", "build-417", "--client", "api"))
    _must_layering(issue)
    code, document = issue.check()
    assert code == 1
    row = _row(document, ISOLATION)
    assert row["status"] == "fail", row
    assert "build-417" in row["detail"] and "build-418" in row["detail"], row


# --- `TRC-A4`: an out-of-scope issue ----------------------------------------------------------

def test_trc_a4(tmp_path):
    """Strategy evidence on an out-of-scope issue is listed and judges nothing."""
    project = _project(tmp_path)
    plain = _issue(project, slug="docs-plain", expected="validation", outer=False)
    plain.acceptance_start("validation")
    issue = _issue(project, slug="docs-validation", expected="validation", outer=False)
    issue.acceptance_start("validation")
    _must_isolation(issue, parallel="sh -c 'exit 1'")
    _must_layering(issue)
    code, document = issue.check()
    plain_code, _ = plain.check()
    assert code == plain_code
    for name, rel, result in ((ISOLATION, PROOF, "failed"), (LAYERING, LAYERS, "passed")):
        row = _row(document, name)
        assert row["status"] == "nothing-to-check", row
        assert "not required: the strategy does not apply" in row["detail"], row
        assert f"{rel} is on record: {result}" in row["detail"], row


# --- `TRC-A7` and `TRC-A8`: the routing of each approach ---------------------------------------

def test_trc_a7(tmp_path):
    """An in-scope quick fix needs an outer-loop green and nothing heavier."""
    issue = _issue(_project(tmp_path), approach="quick-fix")
    assert issue.manifest()["acceptance_strategy"]["routing"] == "existing-dsl"
    assert _record(issue, "evidence/green-TRC-1.outer.json")["attempts"] == 1
    code, document = issue.check()
    assert support.strategy_findings(document) == [], document["checks"]
    for name in (ISOLATION, LAYERING):
        row = _row(document, name)
        assert row["status"] == "nothing-to-check" and "existing DSL only" in row["detail"], row


def test_trc_a8(tmp_path):
    """An in-scope hotfix also needs the isolation proof."""
    issue = _issue(_project(tmp_path), approach="hotfix")
    assert issue.manifest()["acceptance_strategy"]["routing"] == "existing-dsl-isolation"
    code, document = issue.check()
    assert code == 1
    assert support.strategy_findings(document) == [(ISOLATION, "fail")], document["checks"]
    assert "no isolation-proof record" in _row(document, ISOLATION)["detail"]
    assert _row(document, LAYERING)["status"] == "nothing-to-check"


# --- `TRC-A10`: a spike that graduates --------------------------------------------------------

def test_trc_a10(tmp_path):
    """A spike that graduates gets the strategy in full."""
    project = _project(tmp_path)
    spike = project.issue("explore", approach="spike")
    assert spike.assess()[0] == 0
    body = spike.manifest()
    body["evidence"].append({"id": "EV-SPIKE", "type": "spike-conclusion",
                             "decision": "graduate-to-delivery", "next_task": "orders"})
    spike.write_manifest(body)
    issue = _issue(project, outer=False)
    assert issue.manifest()["acceptance_strategy"]["applies"] is True
    code, document = issue.check()
    assert code == 1
    for name in ("outer-loop-recorded", ISOLATION, LAYERING):
        assert _row(document, name)["status"] == "fail", _row(document, name)
    assert "no outer-loop green" in _row(document, "outer-loop-recorded")["detail"]


# --- `TRC-A18` and `TRC-A20`: a waiver makes the isolation check advisory ----------------------

OWNER = "jed72"
WAIVER_REASON = "the staging environment is down until 3 November"
ADVISORY = {"set": {"severity": "advisory"}}


def _approval(scope, entry):
    return {"id": "EV-W1", "type": "human-approval", "decision": "approved",
              "approver": OWNER, "role": "owner", "scope": "waiver",
              "timestamp": "2026-10-29T10:00:00Z",
              "waiver": {"scope": scope, "entry": entry,
                         "fields": {"severity": {"from": "blocking", "to": "advisory"}}}}


def test_trc_a18(tmp_path):
    """A project makes one of the strategy's checks advisory."""
    project = support.Project(tmp_path / "repo")
    support.stage_one_suite(project.root)
    project.setting(None, owner=OWNER,
                    project={"acceptance_support": SUPPORT_PATHS},
                    checks={ISOLATION: dict(ADVISORY, waiver={
                        "reason": WAIVER_REASON, "approved_by": OWNER,
                        "approved_on": "2026-10-29"})})
    code, out, err = project.run("policy", "lint")
    assert "K-LOCK-REFUSED" not in out + err, out + err
    issue = _issue(project)
    _must_layering(issue)
    code, out, err = issue.run("check", "--issue", issue.slug)
    assert "Conformance: non-conformant" not in out + err, out + err
    code, document = _rendered_check(issue)
    assert code == 0, support.findings(document)
    assert _row(document, ISOLATION)["status"] == "advisory"


def _waive(issue, check):
    """`compass waiver add` on one of the strategy's checks, with the reason."""
    issue.must("waiver", "add", "--check", check, "--reason", WAIVER_REASON,
               "--issue", issue.slug)


def _owner_approves(project, issue, waiver):
    """An agent asks with `compass evidence request --waiver`; the Stop hook shows
    the request, and the owner types `/compass:approve waiver <id>` in Claude Code."""
    from approval_support import event
    from compass_pkg import approval_requests, prompt_approval
    issue.must("evidence", "request", "--waiver", waiver, "--issue", issue.slug)
    approval_requests.stop_message(str(project.root / ".compass"),
                                   {"COMPASS_ISSUE": issue.slug})
    done = prompt_approval.handle(
        event(project.root, command="compass:approve", args=f"waiver {waiver}"),
        {}, plugin_root=str(ROOT))
    assert not done.block, done.message


def _statuses(document):
    return {name: _row(document, name)["status"] for name in (ISOLATION, LAYERING)}


def test_trc_a20(tmp_path):
    """One issue steps off the strategy with a recorded reason. 9.0.0 has no issue
    layer (ADR-094), so the step-off is one waiver per strategy check, each made
    with `compass waiver add` and approved by the project's owner. A check is
    excused only once its own waiver is approved."""
    project = _project(tmp_path, owner=OWNER)
    issue = _issue(project)
    issue.must("issue", "use", issue.slug)
    for name in (ISOLATION, LAYERING):
        _waive(issue, name)
    waivers = {w["check"]: w["id"] for w in issue.manifest()["waivers"]}
    assert set(waivers) == {ISOLATION, LAYERING}, waivers

    # Before any approval: both checks still fail, and a notice names the request.
    code, document = issue.check()
    assert code == 1, document if isinstance(document, str) else document["checks"]
    assert _statuses(document) == {ISOLATION: "fail", LAYERING: "fail"}, document["checks"]
    for waiver in waivers.values():
        assert any(waiver in n and f"compass evidence request --waiver {waiver}" in n
                   for n in document["notices"]), document["notices"]

    # One approval excuses its one check, and only that check.
    _owner_approves(project, issue, waivers[ISOLATION])
    code, document = issue.check()
    assert code == 1, document["checks"]
    assert _statuses(document) == {ISOLATION: "waived", LAYERING: "fail"}, document["checks"]

    # Both approved: the issue has stepped off the strategy, and check passes.
    _owner_approves(project, issue, waivers[LAYERING])
    code, document = issue.check()
    assert code == 0, support.findings(document)
    assert _statuses(document) == {ISOLATION: "waived", LAYERING: "waived"}
    assert document["waived"] == 2, document
    approvals = {e["waiver"]: e["id"] for e in issue.manifest()["evidence"]
                 if e.get("type") == "human-approval" and e.get("waiver")}
    for name, waiver in waivers.items():
        detail = _row(document, name)["detail"]
        for part in (waiver, WAIVER_REASON, OWNER, approvals[waiver]):
            assert part in detail, (part, detail)


@pytest.mark.parametrize("approval", ["approved by the project's owner", "with no approval"])
def test_trc_a20_a_config_waiver_is_not_read(tmp_path, approval):
    """A waiver written in one issue's `config:` is not read: 9.0.0 has no issue
    layer (ADR-094), so with or without an approval the checks keep their severity
    and the notice names the waiver as not approved."""
    project = _project(tmp_path, owner=OWNER)
    issue = _issue(project)
    body = issue.manifest()
    body["config"] = {"checks": {name: dict(ADVISORY, waiver={
        "reason": WAIVER_REASON, "approved_by": "EV-W1"}) for name in (ISOLATION, LAYERING)}}
    if approval.startswith("approved"):
        body["evidence"].append(_approval("issue", f"checks.{ISOLATION}"))
        body["evidence"].append(dict(_approval("issue", f"checks.{LAYERING}"), id="EV-W2"))
        body["config"]["checks"][LAYERING]["waiver"]["approved_by"] = "EV-W2"
    issue.write_manifest(body)
    code, out, err = issue.assess(reason="step off the strategy for one issue")
    assert code == 0, out + err
    code, document = _rendered_check(issue)
    assert code == 1, document if isinstance(document, str) else document["checks"]
    for name in (ISOLATION, LAYERING):
        assert _row(document, name)["status"] == "fail", _row(document, name)
    code, out, err = issue.run("check", "--issue", issue.slug)
    assert WAIVER_REASON in out, out + err
    assert "not approved" in out, out


# --- `TRC-X1`: every record ---------------------------------------------------------------------

def test_trc_x1(tmp_path):
    """An in-scope issue with every record passes the strategy's checks."""
    project = support.Project(tmp_path / "repo")
    _example(project)
    project.setting(None, project={"acceptance_support": {
        "alias_helper": "tests/acceptance/alias.py", "driver_factory": "conftest.py",
        "dsl_root": "tests/acceptance/dsl.py",
        "layering_test": "tests/acceptance/test_layering.py"}})
    test = "tests/acceptance/test_todos.py::test_a_completed_todo_can_be_archived"
    issue = _issue(project, slug="archive", scenarios={"TRC-1": (test,)}, outer=False)
    issue.must("tdd-red", "--issue", issue.slug, "--loop", "outer", "--scenario", "TRC-1",
               "--", *FAIL)
    named = ("--candidate", "local", "--client", "api")
    issue.must("tdd-green", "--issue", issue.slug, "--loop", "outer", "--scenario", "TRC-1",
               *named, "--", *PYTEST.split(), "--driver", "api", test)
    _must_isolation(issue, named=named,
                    parallel=f"{PYTEST} -n 2 --driver api tests/acceptance/test_todos.py",
                    repeat=f"{PYTEST} --driver api {{tests}}")
    _must_layering(issue, "--test-path", "tests/acceptance/test_layering.py", "--",
                   *PYTEST.split(), "tests/acceptance/test_layering.py")
    green = _record(issue, "evidence/green-TRC-1.outer.json")
    assert (green["client"], green["attempts"]) == ("api", 1), green
    proof = _record(issue, PROOF)
    assert proof["parallel"]["exit_code"] == 0 and proof["repeat"][0]["runs"] == [0, 0], proof
    assert proof["candidate"] == green["candidate"] == green["tree_id"]
    code, document = issue.check()
    assert support.strategy_findings(document) == [], document["checks"]
    for name in ("outer-loop-recorded", "outer-loop-attempts-recorded", ISOLATION, LAYERING,
                 "acceptance-support-present"):
        assert _row(document, name)["status"] == "pass", _row(document, name)
