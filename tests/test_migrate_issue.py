"""`compass migrate` moves each open, assessed 8.x issue onto the four-stage path (#359).

Step 2 of the #359 plan [Add compass migrate and the 9.0.0 upgrade guide]:

- an issue at define lands at specify, at implement at build, and at `verify` at
  ship only when each scenario has a red before its green; otherwise at build,
  with the scenario named;
- a spike keeps its approach; a closed, a path and a never-assessed issue are
  left as they are;
- `legacy:` holds each key the path writer drops and each 8.x record no path
  reader uses, and the acceptance-criteria entry still resolves;
- the dry run writes nothing; a missing request link is listed with the
  command, and `--request` with `--issue` records it in the same run;
- a project with copied governance and no `compass.yml`, and one that extends
  a git parent, are refused with exit 2.
"""
from __future__ import annotations

import json

import pytest

from migrate_9_helpers import (ASSESSMENT, SPIKE, fix, green, manifest, ok, old_issue,
                               project, red, run, scenario, snapshot, task_dir)

F = "tests/test_f.py"
G = "tests/test_g.py"
SPEC = ".compass/work/records/acceptance-criteria.md"


def _report(root, *args):
    done = run(root, "migrate", *args, "--json")
    return done.returncode, json.loads(done.stdout) if done.stdout.strip() else done.stderr


def _row(doc, slug):
    return next(r for r in doc["issues"] if r["issue"] == slug)


def _schema_errors(body):
    import jsonschema
    from migrate_9_helpers import ROOT
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    return sorted(e.message for e in jsonschema.Draft7Validator(schema).iter_errors(body))


@pytest.fixture
def root(tmp_path):
    return project(tmp_path)


def test_an_issue_at_define_lands_at_specify(root):
    old_issue(root, "at-define")
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    row = _row(doc, "at-define")
    assert (row["from"], row["to"]) == ("define", "specify")
    body = manifest(root, "at-define")
    assert "evidence_required" in body and "stages" not in body
    assert body["legacy"]["stages"] and "subtask_ceiling" in body["legacy"]
    assert not _schema_errors(body), _schema_errors(body)
    last = body["reassessments"][-1]
    assert last["reason"] == "compass migrate to 9.0.0"
    assert last["kind"] == "policy-correction"


def test_an_issue_at_implement_lands_at_build(root):
    old_issue(root, "at-implement", scenarios=[scenario("TRC-001", F)])
    red(root, "at-implement", "TRC-001", F)
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    row = _row(doc, "at-implement")
    assert (row["from"], row["to"]) == ("implement", "build")
    assert "held_back" not in row


def test_an_issue_at_verify_lands_at_ship_with_a_red_before_each_green(root):
    old_issue(root, "at-verify", scenarios=[scenario("TRC-001", F)])
    red(root, "at-verify", "TRC-001", F)
    fix(root)
    green(root, "at-verify", "TRC-001", F)
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    row = _row(doc, "at-verify")
    assert (row["from"], row["to"]) == ("verify", "ship")
    assert ok(root, "next", "--issue", "at-verify").stdout.startswith("Ship")


def test_an_issue_at_verify_with_a_green_and_no_red_lands_at_build_naming_it(root):
    old_issue(root, "no-red", scenarios=[scenario("TRC-001", F), scenario("TRC-002", G)])
    red(root, "no-red", "TRC-001", F)
    fix(root)
    green(root, "no-red", "TRC-001", F)
    # 8.x took a test run bound to a scenario as its green with no red before it.
    (task_dir(root, "no-red") / "g-run.json").write_text(json.dumps(
        {"command": "pytest tests/test_g.py", "exit_code": 0, "passed": True}))
    ok(root, "evidence", "add", "EV-9", "--issue", "no-red", "--type", "test-run",
       "--path", "g-run.json", "--scenario", "TRC-002")
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    row = _row(doc, "no-red")
    assert (row["from"], row["to"]) == ("verify", "build")
    assert row["held_back"] == "TRC-002 has no red"
    # The text view says the same, and migrate wrote no red to move it.
    assert not (task_dir(root, "no-red") / "evidence" / "red-TRC-002.json").exists()


def test_a_spike_keeps_its_approach_and_is_not_moved_twice(root):
    old_issue(root, "spike", assessment=SPIKE, orchestration="single")
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    body = manifest(root, "spike")
    assert body["delivery_approach"] == "spike"
    assert body["stages"] and "evidence_required" not in body
    assert body["legacy"] == {"subtask_ceiling": body["legacy"]["subtask_ceiling"],
                              "orchestration": "single"}
    code, doc = _report(root)
    assert code == 0
    assert _row(doc, "spike")["detail"] == "already moved by compass migrate"


def test_closed_path_and_never_assessed_issues_are_left_as_they_are(root):
    old_issue(root, "closed", status="done")
    ok(root, "quick-fix", "start", "on-path", "--risk", "trivial - one line",
       "--familiarity", "brownfield-mapped - known", "--size", "atomic - one line",
       "--intent", "f returns 2", "--scenario", "Given f, when called, then it returns 2.",
       "--scenario-id", "TRC-001", "--test", F)
    folder = task_dir(root, "never")
    folder.mkdir(parents=True)
    (folder / "manifest.yml").write_text("schema_version: '3.0'\nissue: never\n")
    before = snapshot(root / ".compass" / "work")
    code, doc = _report(root, "--apply")
    assert code == 0, doc
    details = {r["issue"]: (r["result"], r["detail"]) for r in doc["issues"]}
    assert details == {"closed": ("left", "closed"),
                       "on-path": ("left", "already on the four-stage path"),
                       "never": ("left", "never assessed")}
    assert snapshot(root / ".compass" / "work") == before


def test_legacy_holds_each_moved_key_and_the_criteria_entry_still_resolves(root):
    folder = old_issue(
        root, "records", orchestration="single", max_worktrees=2,
        subtasks=[{"id": "ST-1", "status": "done"}], models={"build": "large"},
        page_ticks={"dod": ["tests-pass"]}, readiness={"status": "measured", "score": 3},
        depends_on=[{"issue": "records-two", "until": "verify", "reason": "x"}],
        raised_by={"issue": "records-two", "found_at": "implement"},
        artifacts=[
            {"id": "AC-1", "kind": "acceptance-criteria", "path": SPEC,
             "reason": "the spec", "status": "approved", "revision": 2, "round": 1},
            {"id": "TD-1", "kind": "technical-design", "path": "design.md",
             "status": "draft"}])
    (folder / "acceptance-criteria.md").write_text("# Spec\n")
    old_issue(root, "records-two")
    before = manifest(root, "records")
    code, doc = _report(root, "--apply", "--issue", "records")
    assert code == 0, doc
    body = manifest(root, "records")
    legacy = body["legacy"]
    for key in ("stages", "subtask_ceiling", "orchestration", "max_worktrees", "subtasks",
                "models", "page_ticks", "readiness"):
        assert legacy[key] == before[key], key
        assert key not in body, key
    assert legacy["documents"] == [before["artifacts"][1]]
    assert legacy["artifact_status"] == {"AC-1": {"revision": 2, "round": 1}}
    # `status` stays: the schema needs it on every entry.
    assert body["artifacts"] == [{"id": "AC-1", "kind": "acceptance-criteria",
                                  "path": SPEC, "reason": "the spec",
                                  "status": "approved"}]
    assert legacy["stage_values"] == {"depends_on[0].until": "verify",
                                      "raised_by.found_at": "implement"}
    assert body["depends_on"][0]["until"] == "ship"
    assert body["raised_by"]["found_at"] == "build"
    assert not _schema_errors(body), _schema_errors(body)
    from compass_pkg.core import resolve_artifact
    found = resolve_artifact(str(folder), "acceptance-criteria")
    assert found[:2] == ("found", str(folder / "acceptance-criteria.md")), found
    assert "not there" not in str(found), found
    # Only the named issue was converted.
    assert "legacy" not in manifest(root, "records-two")


def test_the_dry_run_writes_nothing_and_exits_1(root):
    old_issue(root, "dry", scenarios=[scenario("TRC-001", F)])
    red(root, "dry", "TRC-001", F)
    before = snapshot(root / ".compass")
    done = run(root, "migrate")
    assert done.returncode == 1, done.stdout + done.stderr
    assert "would convert 1 issue(s) (1 at build)" in done.stdout
    assert "Dry run: nothing was written." in done.stdout
    assert snapshot(root / ".compass") == before


def test_a_missing_request_link_is_listed_with_the_command(root):
    old_issue(root, "asks")
    old_issue(root, "linked", github={"repo": "o/r", "number": 7})
    done = run(root, "migrate", "--apply")
    assert done.returncode == 0, done.stdout + done.stderr
    assert ("compass issue link set --issue asks --request <url> --requester <name>"
            in done.stdout)
    # A GitHub link gives the request link; the requester is still asked for.
    assert manifest(root, "linked")["request"]["link"] == "https://github.com/o/r/issues/7"
    assert "--issue linked --request" in done.stdout
    assert "2 issue(s) need a request link." in done.stdout


def test_request_and_requester_with_issue_record_it_in_the_same_run(root):
    old_issue(root, "asked")
    code, doc = _report(root, "--apply", "--issue", "asked", "--request", "o/r#9",
                        "--requester", "Dana Smith")
    assert code == 0, doc
    body = manifest(root, "asked")
    assert body["request"]["link"] == "https://github.com/o/r/issues/9"
    assert body["request"]["requester"] == "Dana Smith"
    assert body["github"] == {"repo": "o/r", "number": 9}
    assert _row(doc, "asked")["needs_request"] is False


def test_request_without_issue_is_refused(root):
    old_issue(root, "asked")
    done = run(root, "migrate", "--request", "o/r#9", "--requester", "Dana")
    assert done.returncode == 2
    assert "give --issue <slug> too" in done.stderr


def test_copied_governance_with_no_compass_yml_is_refused(root):
    import compat_baseline as cb
    cb.add_governance_copy(root, source=cb.GOVERNANCE_8_0_4)
    old_issue(root, "copy")
    before = snapshot(root / ".compass")
    done = run(root, "migrate", "--apply")
    assert done.returncode == 2, done.stdout + done.stderr
    assert "[governance-copy-removed]" in done.stderr
    assert snapshot(root / ".compass") == before


def test_a_git_parent_is_refused(root):
    (root / "compass.yml").write_text("extends: github:o/team-policy@v1\n")
    old_issue(root, "parent")
    done = run(root, "migrate")
    assert done.returncode == 2, done.stdout + done.stderr
    assert "[git-parent-removed]" in done.stderr
    assert "github:o/team-policy@v1" in done.stderr


def test_the_issue_still_resolves_under_compass_check(root):
    """The converted manifest is one `compass check` reads, as a path issue."""
    old_issue(root, "checked", scenarios=[scenario("TRC-001", F)], assessment=ASSESSMENT)
    ok(root, "migrate", "--apply")
    done = run(root, "check", "--issue", "checked", "--json")
    assert done.returncode in (0, 1), done.stdout + done.stderr
    assert "request-recorded" in done.stdout
