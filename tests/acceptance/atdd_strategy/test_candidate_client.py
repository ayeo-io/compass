"""Scenario group H of the four-layer acceptance strategy: the candidate and the
client on outer-loop green records.

`compass tdd-green --loop outer` takes `--candidate <build id>|local` and
`--client api|web|cli`. The green record then names `candidate`,
`candidate_kind` (`deployed`, or `local` for the tree id already on the record)
and `client`. On an issue the strategy applies to, an outer-loop green that
lacks either is refused when it is written and when it is registered with
`compass evidence add`, and `outer-loop-recorded` fails one that reached the
registry another way. `compass retro --acceptance` reports the clients per
issue and the deployed and local candidates apart (ADR-085).

The specification is `acceptance-criteria.md` of the Compass issue
`atdd-strategy`, scenarios `TRC-H1` to `TRC-H4`, `TRC-H6` and `TRC-H7`
(ayeo-io/compass-delivery#326). `TRC-H5` belongs to the isolation proof. The
one-run green for several scenarios is decision 8 of ADR-085.
Each test names the scenario it checks; `support.py` builds the projects.
"""
from __future__ import annotations

import json
import sys

import pytest

from tests.acceptance.atdd_strategy import support

CHECK = "outer-loop-recorded"
FAIL = "sh", "-c", "echo 'test_place_order FAILED'; exit 1"
PASS = "sh", "-c", "echo 'test_place_order PASSED'"
GREEN = "evidence/green-TRC-1.outer.json"
ACCEPTED = "api, web, cli"


def _issue(project, slug="orders", scenarios=("TRC-1",)):
    """A regular issue in scope, with an outer-loop red for each scenario."""
    issue = project.issue(slug)
    code, out, err = issue.assess()
    assert code == 0, out + err
    for scenario in scenarios:
        issue.must("scenario", "add", scenario, "--issue", slug, "--intent", "INT-1",
                   "--title", "Place an order", "--test", support.SPEC_TEST)
        issue.must("tdd-red", "--issue", slug, "--loop", "outer", "--scenario", scenario,
                   "--", *FAIL)
    return issue


def _project(tmp_path):
    project = support.Project(tmp_path / "repo")
    support.stage_one_suite(project.root)
    return project


def _green(issue, *named, scenario="TRC-1"):
    argv = ["tdd-green", "--issue", issue.slug, "--loop", "outer"]
    if scenario:
        argv += ["--scenario", scenario]
    return issue.run(*argv, *named, "--", *PASS)


def _must_green(issue, *named, scenario="TRC-1"):
    code, out, err = _green(issue, *named, scenario=scenario)
    assert code == 0, out + err
    return out


def _record(issue, rel=GREEN):
    return json.loads((issue.dir / rel).read_text(encoding="utf-8"))


def _row(issue, name=CHECK):
    code, document = issue.check()
    rows = [c for c in document["checks"] if c["name"] == name]
    assert len(rows) == 1, (name, document)
    return code, rows[0]


# --- `TRC-H1` ------------------------------------------------------------------------------

def test_trc_h1(tmp_path):
    """Green through the client."""
    issue = _issue(_project(tmp_path))
    _must_green(issue, "--candidate", "build-417", "--client", "api")
    record = _record(issue)
    assert (record["candidate"], record["candidate_kind"], record["client"], record["loop"]) \
        == ("build-417", "deployed", "api", "outer"), record
    _, row = _row(issue)
    assert row["status"] == "pass", row


# --- `TRC-H2` ------------------------------------------------------------------------------

def test_trc_h2(tmp_path):
    """A local build is named by its tree id."""
    issue = _issue(_project(tmp_path))
    _must_green(issue, "--candidate", "local", "--client", "cli")
    record = _record(issue)
    assert record["tree_id"], record
    assert (record["candidate"], record["candidate_kind"]) == (record["tree_id"], "local"), record
    _, row = _row(issue)
    assert row["status"] == "pass", row


# --- `TRC-H3` ------------------------------------------------------------------------------

def _hand_written_green(issue):
    """An outer-loop green with neither a candidate nor a client, written by hand."""
    from compass_pkg.tdd import _stamp_identity
    record = {"command": " ".join(PASS), "argv": list(PASS), "scenario": "TRC-1",
              "loop": "outer", "exit_code": 0, "passed": True, "attempts": 1,
              "timestamp": "2026-10-29T11:00:00Z"}
    _stamp_identity(record)
    path = issue.dir / GREEN
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


@pytest.mark.parametrize("named, how, missing", [
    ((), "written by compass tdd-green", "candidate and client"),
    (("--client", "api"), "written by compass tdd-green", "candidate"),
    (("--candidate", "build-417"), "written by compass tdd-green", "client"),
    ((), "registered with compass evidence add", "candidate and client"),
])
def test_trc_h3(tmp_path, named, how, missing):
    """No record without a candidate and a client."""
    issue = _issue(_project(tmp_path))
    if how.startswith("written"):
        code, out, err = _green(issue, *named)
        assert not (issue.dir / GREEN).exists()
    else:
        _hand_written_green(issue)
        code, out, err = issue.run("evidence", "add", "EV-H3", "--issue", issue.slug,
                                   "--type", "test-run", "--path", GREEN,
                                   "--scenario", "TRC-1")
        assert all(e.get("path") != GREEN for e in issue.manifest()["evidence"])
    assert code == 2, out + err
    assert f"names no {missing}" in err, err
    code, row = _row(issue)
    assert code == 1
    assert row["status"] == "fail", row


def test_trc_h3_a_record_that_reached_the_registry_another_way(tmp_path):
    """`outer-loop-recorded` fails an outer-loop green with no candidate or client that
    was registered by editing the manifest."""
    issue = _issue(_project(tmp_path))
    record = _hand_written_green(issue)
    body = issue.manifest()
    body["evidence"].append({"id": "EV-H3", "type": "test-run", "path": GREEN,
                             "scenario": "TRC-1", "record_id": record["record_id"],
                             "content_digest": record["content_digest"]})
    issue.write_manifest(body)
    code, row = _row(issue)
    assert code == 1
    assert row["status"] == "fail", row
    assert f"{GREEN} names no candidate and client" in row["detail"], row


def test_trc_h3_out_of_scope_needs_neither(tmp_path):
    """An issue the strategy does not apply to records an outer-loop green with neither."""
    project = _project(tmp_path)
    project.setting({"state": "off", "reason": "a CLI with no client"})
    issue = _issue(project)
    _must_green(issue)
    record = _record(issue)
    assert not {"candidate", "candidate_kind", "client"} & set(record), record


def test_trc_h3_an_inner_green_names_no_client(tmp_path):
    """A unit-test green that names a candidate or a client is refused, so a reader can
    tell it from an acceptance green."""
    issue = _issue(_project(tmp_path))
    code, out, err = issue.run("tdd-green", "--issue", issue.slug, "--loop", "inner",
                               "--scenario", "TRC-1", "--client", "api", "--", *PASS)
    assert code == 2, out + err
    assert "--loop outer" in err, err
    assert not (issue.dir / "evidence" / "green-TRC-1.json").exists()


# --- `TRC-H4` ------------------------------------------------------------------------------

def test_trc_h4(tmp_path):
    """An unknown client is refused."""
    issue = _issue(_project(tmp_path))
    code, out, err = _green(issue, "--candidate", "build-417", "--client", "smoke")
    assert code == 2, out + err
    assert not (issue.dir / GREEN).exists()
    assert "smoke" in err and ACCEPTED in err, err


# --- one run, several scenarios (ADR-085, decision 8) ----------------------------------------

@pytest.mark.parametrize("bind", [("--scenario", "TRC-1", "--scenario", "TRC-2"),
                                  ("--every-scenario",)])
def test_one_green_run_binds_several_scenarios(tmp_path, bind):
    """`--scenario` repeated, or `--every-scenario`, records one outer-loop green per
    scenario from one run, each with the same run id."""
    project = _project(tmp_path)
    issue = _issue(project, scenarios=("TRC-1", "TRC-2"))
    counter = project.root / "runs.txt"
    once = ("sh", "-c", f"echo run >> {counter}; echo 'test_place_order PASSED'")
    issue.must("tdd-green", "--issue", issue.slug, "--loop", "outer", *bind,
               "--candidate", "build-417", "--client", "api", "--", *once)
    assert counter.read_text(encoding="utf-8").count("run") == 1
    one = _record(issue, "evidence/green-TRC-1.outer.json")
    two = _record(issue, "evidence/green-TRC-2.outer.json")
    assert one["run_id"] == two["run_id"], (one, two)
    assert one["scenarios_in_run"] == two["scenarios_in_run"] == ["TRC-1", "TRC-2"]
    assert (one["scenario"], two["scenario"]) == ("TRC-1", "TRC-2")
    assert one["client"] == two["client"] == "api"
    paths = [e["path"] for e in issue.manifest()["evidence"]]
    assert "evidence/green-TRC-1.outer.json" in paths
    assert "evidence/green-TRC-2.outer.json" in paths


def test_several_scenarios_need_a_red_each_before_the_run(tmp_path):
    """A scenario of the run with no red is refused before the command runs."""
    project = _project(tmp_path)
    issue = _issue(project)
    issue.must("scenario", "add", "TRC-2", "--issue", issue.slug, "--intent", "INT-1",
               "--title", "Cancel an order", "--test", support.SPEC_TEST)
    counter = project.root / "runs.txt"
    once = ("sh", "-c", f"echo run >> {counter}")
    code, out, err = issue.run("tdd-green", "--issue", issue.slug, "--loop", "outer",
                               "--every-scenario", "--candidate", "build-417",
                               "--client", "api", "--", *once)
    assert code == 2, out + err
    assert "TRC-2" in err, err
    assert not counter.exists()
    assert not (issue.dir / GREEN).exists()


def test_several_scenarios_need_the_outer_loop(tmp_path):
    issue = _issue(_project(tmp_path), scenarios=("TRC-1", "TRC-2"))
    code, out, err = issue.run("tdd-green", "--issue", issue.slug, "--loop", "inner",
                               "--scenario", "TRC-1", "--scenario", "TRC-2", "--", *PASS)
    assert code == 2, out + err
    assert "--loop outer" in err, err


# --- `TRC-H6` and `TRC-H7` ------------------------------------------------------------------

def _closed_issue(project, slug, *greens):
    """A closed in-scope issue with one outer-loop green per `(candidate, client)`, each
    bound to its own scenario."""
    scenarios = tuple(f"TRC-{n}" for n in range(1, len(greens) + 1))
    issue = _issue(project, slug=slug, scenarios=scenarios)
    for scenario, (candidate, client) in zip(scenarios, greens):
        _must_green(issue, "--candidate", candidate, "--client", client, scenario=scenario)
    issue.close()
    return issue


def _retro(project, fmt=None):
    argv = ["retro", "--acceptance"] + (["--format", fmt] if fmt else [])
    code, out, err = project.run(*argv)
    assert code == 0, out + err
    return json.loads(out) if fmt == "json" else out


def test_trc_h6(tmp_path):
    """The retrospective reports the client per issue."""
    project = _project(tmp_path)
    _closed_issue(project, "orders", ("build-417", "api"))
    _closed_issue(project, "refunds", ("build-418", "api"), ("build-418", "cli"))
    out = _retro(project)
    assert "clients of orders: api" in out, out
    assert "clients of refunds: api, cli" in out, out
    document = _retro(project, "json")
    assert document["clients"] == {"orders": ["api"], "refunds": ["api", "cli"]}, document


def test_trc_h7(tmp_path):
    """The retrospective reports deployed and local candidates apart."""
    project = _project(tmp_path)
    _closed_issue(project, "orders", ("build-417", "api"))
    _closed_issue(project, "refunds", ("build-418", "web"))
    _closed_issue(project, "returns", ("local", "cli"))
    out = _retro(project)
    assert "in-scope issues with a deployed candidate: 2 of 3" in out, out
    assert "with a local candidate only: returns" in out, out
    document = _retro(project, "json")
    assert document["candidates"] == {"deployed": ["orders", "refunds"], "local": ["returns"],
                                      "none": []}, document


# --- `compass quick-fix finish` --------------------------------------------------------------

def _quick_fix(tmp_path):
    """An in-scope quick fix, its test committed and failing, its outer-loop red recorded."""
    project = support.Project(tmp_path / "repo")
    root = project.root
    (root / "data").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi\n", encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests" / "test_greeting.py").write_text(
        "import pathlib\n\n\ndef test_greeting():\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
        "    assert p.read_text().strip() == 'Hello'\n", encoding="utf-8")
    support.git(root, "add", "data/greeting.txt", "tests/test_greeting.py")
    support.git(root, "commit", "-q", "-m", "greeting")
    issue = support.Issue(project, "greet")
    issue.must("quick-fix", "start", "greet", "--risk", "trivial - a text change",
               "--familiarity", "brownfield-mapped - the file and its test exist",
               "--size", "atomic - one line", "--intent", "The greeting says Hello.",
               "--scenario", "Given the greeting, when it is read, then it says Hello.",
               "--test", "tests/test_greeting.py::test_greeting")
    issue.must("tdd-red", "--issue", "greet", "--scenario", "TRC-001", "--", *QUICK_TEST)
    (root / "data" / "greeting.txt").write_text("Hello\n", encoding="utf-8")
    return project, issue


QUICK_TEST = (sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
              "tests/test_greeting.py::test_greeting")
FINISH = ("quick-fix", "finish", "--issue", "greet", "--no-commit", "-m", "Say Hello",
          "--release-note", "The greeting says Hello.")


def test_quick_fix_finish_names_the_candidate_and_client(tmp_path):
    """An in-scope quick fix records an outer-loop green, which names both."""
    _, issue = _quick_fix(tmp_path)
    issue.must(*FINISH, "--candidate", "local", "--client", "cli", "--", *QUICK_TEST)
    record = _record(issue, "evidence/green-TRC-001.outer.json")
    assert (record["candidate_kind"], record["client"]) == ("local", "cli"), record


def test_quick_fix_finish_refuses_before_it_writes(tmp_path):
    """With neither named, an in-scope quick fix is refused before anything is traced."""
    _, issue = _quick_fix(tmp_path)
    code, out, err = issue.run(*FINISH, "--", *QUICK_TEST)
    assert code == 2, out + err
    assert "names no candidate and client" in err, err
    assert "--candidate" in err and "--client" in err, err
    assert not issue.manifest().get("changed_files")
    assert not (issue.dir / "evidence" / "green-TRC-001.outer.json").exists()


def test_quick_fix_finish_does_not_reuse_an_inner_green(tmp_path):
    """A finish that records the outer loop does not take an inner-loop green on the same
    tree with the same command as its own: it records the outer-loop green."""
    _, issue = _quick_fix(tmp_path)
    issue.must("changed-file", "add", "data/greeting.txt", "--issue", "greet",
               "--scenario", "TRC-001")
    issue.must("tdd-green", "--issue", "greet", "--scenario", "TRC-001", "--loop", "inner",
               "--", *QUICK_TEST)
    issue.must(*FINISH, "--candidate", "local", "--client", "cli", "--", *QUICK_TEST)
    record = _record(issue, "evidence/green-TRC-001.outer.json")
    assert record["loop"] == "outer", record
    _, row = _row(issue)
    assert row["status"] == "pass", row


def test_quick_fix_finish_on_the_inner_loop_writes_neither(tmp_path):
    """`finish` chooses its loop, so it takes the two flags on the inner loop and does
    not write them: only an acceptance green names a candidate and a client. It still
    refuses an unknown client."""
    _, issue = _quick_fix(tmp_path)
    code, out, err = issue.run(*FINISH, "--loop", "inner", "--candidate", "local",
                               "--client", "smoke", "--", *QUICK_TEST)
    assert code == 2 and ACCEPTED in err, out + err
    # The finish records the inner-loop green, and then `compass check` refuses it: an
    # in-scope quick fix needs an outer-loop green.
    code, out, err = issue.run(*FINISH, "--loop", "inner", "--candidate", "local",
                               "--client", "cli", "--", *QUICK_TEST)
    assert code == 2 and "outer-loop-recorded" in out + err, out + err
    record = _record(issue, "evidence/green-TRC-001.json")
    assert record["loop"] == "inner", record
    assert not {"candidate", "candidate_kind", "client"} & set(record), record
