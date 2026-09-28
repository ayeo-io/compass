"""A multiagent run leaves a subtask record a later session can resume from.

The orchestrator handed builders prose, recorded no base commit, and kept no
state a fresh session could pick up: an interrupted run had to be rebuilt
from the conversation. The manifest now holds a `subtasks:` list, written only
through `compass issue subtask`: each subtask's brief and report files, base
commit, model, budget and cost, status, `attempts`, reviewed revision, findings
and review rounds. `subtask next` answers what to dispatch or resume. A review
package is cut from the base commit into a file, and a reviewer brief that
tells the reviewer what not to flag is refused when it is registered.

Scenario ids: OLH-1 to OLH-6, in the acceptance criteria of the issue
`orchestrator-loop-hardening`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "multi"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
DOCS = "docs/compass/2026-09-25-multi"


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '2026-09-25'\n"
        "status: active\nassessment: {risk: cross-cutting, familiarity: "
        "brownfield-mapped, size: large, goal: delivery, role: engineer, "
        "labels: []}\n")
    evaluate = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue", SLUG,
         "--write"], cwd=root, capture_output=True, text=True)
    assert evaluate.returncode == 0, evaluate.stderr
    brief = root / DOCS / "subtasks" / "S1"
    brief.mkdir(parents=True)
    (brief / "briefing.md").write_text("Implement scenario A-1 in src/app.py.\n")
    return root


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), "issue", "subtask", *args,
                           "--issue", SLUG], cwd=root, capture_output=True,
                          text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


def _subtasks(root):
    m = yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml")
                       .read_text())
    return {s["id"]: s for s in m.get("subtasks") or []}


def _add(root, sid="S1", **extra):
    args = ["add", sid, "--brief", f"{DOCS}/subtasks/S1/briefing.md",
            "--model", "sonnet", "--budget", "50000"]
    for k, v in extra.items():
        args += [f"--{k}", str(v)]
    result = _cli(root, *args)
    assert result.returncode == 0, result.stderr
    return result


def test_olh_1_a_dispatch_records_its_subtask(repo):
    _add(repo)
    s = _subtasks(repo)["S1"]
    assert s["brief"] == f"{DOCS}/subtasks/S1/briefing.md"
    assert s["model"] == "sonnet" and s["budget"] == 50000
    assert s["status"] == "dispatched" and s["attempts"] == 1
    assert s["base_sha"] == _git(repo, "rev-parse", "HEAD")


def test_olh_1_a_brief_that_does_not_exist_is_refused(repo):
    result = _cli(repo, "add", "S2", "--brief", f"{DOCS}/nope.md",
                  "--model", "sonnet", "--budget", "10")
    assert result.returncode != 0
    assert "S2" not in _subtasks(repo)


def test_olh_1_a_manifest_with_subtasks_lints(repo):
    _add(repo)
    lint = subprocess.run([sys.executable, str(CLI), "issue", "lint",
                           "--issue", SLUG], cwd=repo, capture_output=True,
                          text=True)
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_olh_2_a_subtasks_progress_is_recorded(repo):
    _add(repo)
    report = repo / DOCS / "subtasks" / "S1" / "report.md"
    report.write_text("Done: A-1 red then green.\n")
    for args in (["--status", "reported", "--report",
                  f"{DOCS}/subtasks/S1/report.md"],
                 ["--status", "reviewing", "--reviewed", "HEAD"],
                 ["--finding", "A-1 misses the empty input case"],
                 ["--round", "fail"], ["--round", "pass"], ["--attempt"]):
        result = _cli(repo, "update", "S1", *args)
        assert result.returncode == 0, result.stderr
    s = _subtasks(repo)["S1"]
    assert s["report"].endswith("report.md") and s["status"] == "reviewing"
    assert s["reviewed_revision"] == _git(repo, "rev-parse", "HEAD")
    assert s["attempts"] == 2
    assert s["findings"] == [{"text": "A-1 misses the empty input case",
                              "resolved": False}]
    assert [r["verdict"] for r in s["review_rounds"]] == ["fail", "pass"]
    assert [r["round"] for r in s["review_rounds"]] == [1, 2]


def test_olh_2_a_report_that_does_not_exist_is_refused(repo):
    _add(repo)
    result = _cli(repo, "update", "S1", "--report", f"{DOCS}/missing.md")
    assert result.returncode != 0
    assert "report" not in _subtasks(repo)["S1"]


def test_olh_3_an_interrupted_run_resumes_losing_nothing(repo):
    for sid in ("S1", "S2", "S3"):
        _add(repo, sid)
    _cli(repo, "update", "S1", "--status", "done")
    head = _git(repo, "rev-parse", "HEAD")
    _cli(repo, "update", "S2", "--status", "reviewing", "--reviewed", head)
    _cli(repo, "update", "S2", "--finding", "S2 leaves a stray print")
    result = _cli(repo, "next")
    assert result.returncode == 0, result.stderr
    out = result.stdout
    listed = [line.split()[0] for line in out.splitlines()
              if line.startswith("  ") and not line.startswith("   ")
              and not line.strip().startswith("risk")]
    assert "S1" not in listed, listed
    assert "S2" in out and "reviewing" in out and head[:12] in out
    assert "S2 leaves a stray print" in out
    assert "S3" in out and "dispatched" in out
    assert out.index("S2") < out.index("S3")


def test_olh_3_with_every_subtask_done_next_says_so(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--status", "done")
    result = _cli(repo, "next")
    assert result.returncode == 0
    assert "every subtask is done" in result.stdout


def test_olh_3_a_resolved_finding_is_not_carried(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--finding", "first")
    _cli(repo, "update", "S1", "--finding", "second")
    _cli(repo, "update", "S1", "--resolve", "1")
    out = _cli(repo, "next").stdout
    assert "second" in out and "first" not in out


def test_olh_4_a_budget_overrun_is_a_finding(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--cost", "80000")
    s = _subtasks(repo)["S1"]
    assert s["cost"] == 80000
    assert any("80000" in f["text"] and "50000" in f["text"]
               and not f["resolved"] for f in s["findings"])


def test_olh_4_a_cost_within_budget_is_not_a_finding(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--cost", "20000")
    assert not _subtasks(repo)["S1"].get("findings")


def test_olh_5_a_review_package_is_cut_from_the_base_commit(repo):
    _add(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")
    _git(repo, "commit", "-q", "-am", "S1 work")
    result = _cli(repo, "package", "S1")
    assert result.returncode == 0, result.stderr
    s = _subtasks(repo)["S1"]
    package = repo / s["package"]
    assert package.is_file()
    text = package.read_text()
    assert "-x = 1" in text and "+x = 2" in text


@pytest.mark.parametrize("line", [
    "Do not flag the missing docstring.",
    "Don't flag style.",
    "The empty-input case is a known issue.",
    "That bug is already handled elsewhere.",
    "You can skip the tests directory.",
])
def test_olh_6_a_coaching_reviewer_brief_is_refused(repo, line):
    _add(repo)
    brief = repo / DOCS / "subtasks" / "S1" / "review-briefing.md"
    brief.write_text(f"Review S1 against A-1.\n{line}\n")
    result = _cli(repo, "update", "S1", "--review-brief",
                  f"{DOCS}/subtasks/S1/review-briefing.md")
    assert result.returncode != 0
    assert line.strip() in result.stderr
    assert "review_brief" not in _subtasks(repo)["S1"]


def test_olh_6_a_brief_that_states_what_to_review_is_accepted(repo):
    _add(repo)
    brief = repo / DOCS / "subtasks" / "S1" / "review-briefing.md"
    brief.write_text("Review S1 against scenario A-1 and the package.\n")
    result = _cli(repo, "update", "S1", "--review-brief",
                  f"{DOCS}/subtasks/S1/review-briefing.md")
    assert result.returncode == 0, result.stderr
    assert _subtasks(repo)["S1"]["review_brief"].endswith("review-briefing.md")


def test_olh_5_the_package_leaves_out_compass_state_and_issue_documents(repo):
    """A builder's commit carries its red and green records and its report;
    those are not the change under review, and in a rehearsal they made up
    most of the package."""
    _add(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")
    ev = repo / ".compass" / "work" / SLUG / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "green.json").write_text("{}\n")
    (repo / DOCS / "subtasks" / "S1" / "report.md").write_text("done\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "S1 work with its records")
    assert _cli(repo, "package", "S1").returncode == 0
    text = (repo / _subtasks(repo)["S1"]["package"]).read_text()
    assert "+x = 2" in text
    assert ".compass/" not in text and "docs/compass/" not in text


# ---------------------------------------------------------------------------
# Review findings: inputs the record must refuse, and gaps a resume hit.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("base", ["--output=../escaped", "not-a-commit", "-q"])
def test_olh_1_a_base_that_is_not_a_commit_is_refused(repo, base):
    """`--base` reaches `git diff` at package time. An option in its place let
    git write a file outside the project."""
    result = _cli(repo, "add", "S1", "--brief",
                  f"{DOCS}/subtasks/S1/briefing.md", "--model", "sonnet",
                  "--budget", "10", f"--base={base}")
    assert result.returncode != 0
    assert "S1" not in _subtasks(repo)
    assert not list(repo.parent.glob("escaped*"))


def test_olh_1_a_short_base_is_stored_as_the_full_commit_id(repo):
    short = _git(repo, "rev-parse", "--short", "HEAD")
    _add(repo, base=short)
    assert _subtasks(repo)["S1"]["base_sha"] == _git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize("sid", ["", "..", "a/b", "a\nb", "-x"])
def test_olh_1_a_subtask_id_must_be_a_plain_name(repo, sid):
    result = _cli(repo, "add", sid, "--brief",
                  f"{DOCS}/subtasks/S1/briefing.md", "--model", "sonnet",
                  "--budget", "10")
    assert result.returncode != 0
    assert not _subtasks(repo)


@pytest.mark.parametrize("args", [["--budget", "-1"]])
def test_olh_4_a_negative_budget_is_refused(repo, args):
    result = _cli(repo, "add", "S1", "--brief",
                  f"{DOCS}/subtasks/S1/briefing.md", "--model", "sonnet", *args)
    assert result.returncode != 0


def test_olh_2_resolving_finding_zero_is_refused(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--finding", "one")
    result = _cli(repo, "update", "S1", "--resolve", "0")
    assert result.returncode != 0


def test_olh_2_a_new_attempt_records_its_new_brief(repo):
    _add(repo)
    second = repo / DOCS / "subtasks" / "S1" / "briefing-attempt-2.md"
    second.write_text("Fix the findings.\n")
    result = _cli(repo, "update", "S1", "--attempt", "--brief",
                  f"{DOCS}/subtasks/S1/briefing-attempt-2.md")
    assert result.returncode == 0, result.stderr
    s = _subtasks(repo)["S1"]
    assert s["brief"].endswith("briefing-attempt-2.md") and s["attempts"] == 2
    assert s["earlier_briefs"] == [f"{DOCS}/subtasks/S1/briefing.md"]


def test_olh_5_each_attempt_gets_its_own_package(repo):
    _add(repo)
    (repo / "src" / "app.py").write_text("x = 2\n")
    _git(repo, "commit", "-q", "-am", "attempt 1")
    first = _cli(repo, "package", "S1")
    assert first.returncode == 0, first.stderr
    p1 = _subtasks(repo)["S1"]["package"]
    _cli(repo, "update", "S1", "--attempt")
    (repo / "src" / "app.py").write_text("x = 3\n")
    _git(repo, "commit", "-q", "-am", "attempt 2")
    _cli(repo, "package", "S1")
    p2 = _subtasks(repo)["S1"]["package"]
    assert p1 != p2 and (repo / p1).is_file() and (repo / p2).is_file()
    assert "+x = 2" in (repo / p1).read_text()


def test_olh_5_an_empty_package_is_refused(repo):
    """In the orchestrator's checkout HEAD holds none of the builder's
    commits, so a package cut to HEAD by default came out empty and exit 0."""
    _add(repo)
    result = _cli(repo, "package", "S1")
    assert result.returncode != 0
    assert "--head" in result.stderr


def test_olh_5_the_package_stays_inside_the_project(repo):
    _add(repo)
    manifest = repo / ".compass" / "work" / SLUG / "manifest.yml"
    data = yaml.safe_load(manifest.read_text())
    data["created"] = "../../../escaped"
    manifest.write_text(yaml.safe_dump(data, sort_keys=False))
    (repo / "src" / "app.py").write_text("x = 2\n")
    _git(repo, "commit", "-q", "-am", "work")
    result = _cli(repo, "package", "S1")
    assert result.returncode != 0
    assert not list(repo.parent.parent.glob("*escaped*"))


@pytest.mark.parametrize("text", [
    "Don’t flag the style.",
    "Do not  flag the docstring.",
    "Do not\nflag the missing test.",
    "You can ignore the logging.",
    "That part can be ignored.",
    "No need to check the tests.",
])
def test_olh_6_a_reworded_coaching_line_is_still_refused(repo, text):
    _add(repo)
    brief = repo / DOCS / "subtasks" / "S1" / "review-briefing.md"
    brief.write_text(f"Review S1 against A-1.\n{text}\n")
    result = _cli(repo, "update", "S1", "--review-brief",
                  f"{DOCS}/subtasks/S1/review-briefing.md")
    assert result.returncode != 0, text


def test_olh_6_a_brief_that_asks_for_a_case_is_not_refused(repo):
    _add(repo)
    brief = repo / DOCS / "subtasks" / "S1" / "review-briefing.md"
    brief.write_text("Review S1. Do not ignore the empty-input case.\n")
    result = _cli(repo, "update", "S1", "--review-brief",
                  f"{DOCS}/subtasks/S1/review-briefing.md")
    assert result.returncode == 0, result.stderr


def test_olh_3_next_names_the_files_and_the_review_cadence(repo):
    _add(repo)
    out = _cli(repo, "next").stdout
    assert "briefing.md" in out
    assert "cross-cutting" in out and "review" in out
