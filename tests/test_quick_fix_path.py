"""`compass quick-fix start` and `finish` on the four-stage path (ADR-092).

With the path writer on (the `path_writer` fixture), `start` serves every size:
it writes the path manifest and `acceptance-criteria.md` with the one scenario
and the intent, and no devlog. It takes the hotfix setting as `--urgency`.
`finish` works on any delivery issue on the path. It passes the three immovable
gates, as before, and refuses with exit 1 while other evidence is owed, with one
`next:` line for each owed item.

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations

import json

from test_quick_fix_verbs import (  # noqa: F401  (`repo` is a fixture)
    GREET_CMD, NAMED, RELEASE_NOTE, _base_greeting, _git, _manifest, _run,
    _write_greeting, repo)

SLUG = "greet-path"
STANDARD = ["scenarios", "red-before-green", "suite-green", "correctness", "governance",
            "traceability", "regression", "security", "clarity", "outer-loop", "isolation",
            "layering", "definition-of-done"]
INTENT = "A greeting says hello to the person it names."
SCENARIO = ("Given the greeting template, when it is read, then it says "
            "'Hello, %s!'.")
TEST_ID = "tests/test_greeting.py::test_greeting_says_hello"


def _start(root, slug=SLUG, size="atomic - one file, one obvious change", *extra):
    return _run(root, "quick-fix", "start", slug,
                "--risk", "trivial - a one-line text change",
                "--familiarity", "brownfield-mapped - the file and its test already exist",
                "--size", size, "--intent", INTENT, "--scenario", SCENARIO,
                "--test", TEST_ID, *extra)


def _red(root, slug=SLUG, *extra):
    red = _run(root, "tdd-red", "--issue", slug, "--scenario", "TRC-001", *extra,
               *GREET_CMD)
    assert red.returncode == 0, red.stdout + red.stderr
    return red


def _finish(root, slug=SLUG, *extra):
    return _run(root, "quick-fix", "finish", "--issue", slug, "-m", "Say hello properly",
                *RELEASE_NOTE, *NAMED, *extra, *GREET_CMD)


def _next_lines(result):
    return [ln for ln in result.stdout.splitlines() if ln.startswith("next: ")]


# --- start ---------------------------------------------------------------------------

def test_start_records_a_medium_change_on_the_path(repo, path_writer):
    result = _start(repo, SLUG, "medium - several files and a design choice")
    assert result.returncode == 0, result.stdout + result.stderr

    manifest = _manifest(repo, SLUG)
    assert manifest["delivery_approach"] == "delivery"
    assert manifest["evidence_required"] == STANDARD
    assert "stages" not in manifest and "subtask_ceiling" not in manifest
    assert [s["id"] for s in manifest["scenarios"]] == ["TRC-001"]
    assert (repo / ".compass" / "current-task").read_text().strip() == SLUG

    # The acceptance criteria hold the intent and the one scenario; no devlog.
    work = repo / ".compass" / "work" / SLUG
    assert not (work / "devlog.md").exists()
    specs = list((repo / "docs" / "compass").glob(f"*-{SLUG}/acceptance-criteria.md"))
    assert len(specs) == 1, specs
    spec = specs[0].read_text()
    assert f"INT-1 | quick-fix start | {INTENT}" in spec
    assert "traceability id: TRC-001" in spec and "serves: INT-1" in spec
    assert "Given the greeting template" in spec
    assert "## Non-functional requirements" in spec
    assert "{{" not in spec

    lines = result.stdout.splitlines()
    assert lines[-1] == ("next: compass tdd-red --loop outer --scenario TRC-001 "
                         "-- <acceptance test command>")


def test_start_takes_the_hotfix_setting_as_urgency(repo, path_writer):
    result = _start(repo, SLUG, "small - one file",
                    "--urgency", "live-defect - the greeting is wrong in production")
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = _manifest(repo, SLUG)
    assert manifest["assessment"]["urgency"] == "live-defect"
    assert manifest["justifications"]["urgency"] == "the greeting is wrong in production"
    assert "reproduce-first" in manifest["evidence_required"]


def test_start_refuses_an_urgency_with_no_reason(repo, path_writer):
    result = _start(repo, SLUG, "small - one file", "--urgency", "live-defect")
    assert result.returncode != 0
    assert "--urgency needs a reason" in result.stdout + result.stderr
    assert not (repo / ".compass" / "work" / SLUG).exists()


def test_with_the_switch_off_start_still_refuses_heavier_work(repo, monkeypatch):
    monkeypatch.delenv("COMPASS_PATH_WRITER", raising=False)
    result = _start(repo, SLUG, "medium - several files and a design choice")
    assert result.returncode == 1
    assert _manifest(repo, SLUG)["delivery_approach"] == "regular"


# --- finish --------------------------------------------------------------------------

def test_finish_refuses_while_a_medium_change_owes_evidence(repo, path_writer):
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")

    finish = _finish(repo)
    assert finish.returncode == 1, finish.stdout + finish.stderr
    owed = _next_lines(finish)
    assert owed, finish.stdout
    for gate in ("verify.regression", "verify.security", "verify.clarity"):
        assert f"next: compass gate pass {gate} --evidence <EV-id>" in owed
    assert any(line.startswith("next: compass isolation record") for line in owed)
    assert "next: compass layering record -- <layering test command>" in owed
    assert any("--meets dod-" in line for line in owed)
    # Nothing was written: no gate passed, no green, no commit.
    manifest = _manifest(repo, SLUG)
    assert all(g["status"] == "pending" for g in manifest["gates"])
    assert not [e for e in manifest.get("evidence") or [] if e.get("type") == "test-run"]
    assert _git(repo, "rev-parse", "HEAD") == head


def test_finish_json_names_the_owed_commands(repo, path_writer):
    _base_greeting(repo)
    assert _start(repo, SLUG, "medium - several files and a design choice").returncode == 0
    _red(repo, SLUG, "--loop", "outer")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Say hello",
                  *RELEASE_NOTE, *NAMED, "--json", *GREET_CMD)
    assert finish.returncode == 1
    doc = json.loads(finish.stdout)
    assert "compass gate pass verify.clarity --evidence <EV-id>" in doc["owed"]


def test_finish_refuses_until_the_outer_loop_red_then_ships(repo, path_writer):
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo, SLUG, "--loop", "inner")

    refused = _finish(repo)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert _next_lines(refused) == [
        "next: compass tdd-red --loop outer --scenario TRC-001 "
        "-- <acceptance test command>"]

    _red(repo, SLUG, "--loop", "outer")
    _write_greeting(repo, "Hello, %s!")
    head = _git(repo, "rev-parse", "HEAD")
    shipped = _finish(repo)
    assert shipped.returncode == 0, shipped.stdout + shipped.stderr
    assert _git(repo, "rev-parse", "HEAD") != head

    manifest = _manifest(repo, SLUG)
    assert manifest["status"] == "done"
    assert {g["id"]: g["status"] for g in manifest["gates"]} == {
        "verify.correctness": "pass", "verify.governance": "pass",
        "verify.traceability": "pass"}
    assert not (repo / ".compass" / "work" / SLUG / "devlog.md").exists()
    # The issue is closed, so no command comes next.
    assert not _next_lines(shipped)


def test_finish_no_commit_ends_with_the_next_command(repo, path_writer):
    _base_greeting(repo)
    assert _start(repo).returncode == 0
    _red(repo)
    _write_greeting(repo, "Hello, %s!")
    finish = _finish(repo, SLUG, "--no-commit")
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert finish.stdout.splitlines()[-1].startswith("next: ")
