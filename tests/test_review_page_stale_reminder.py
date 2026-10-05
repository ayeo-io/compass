"""A verb that leaves an issue's review page stale says so, in one line.

Six verbs write an issue's manifest, and the review page is generated from
it. None of them regenerates the page, so after each one the page can stop
matching its source, and only `compass check` used to say so - often well
after the moment of acting. The decision of 5 October 2026
(`governance/decisions/2026-10-05-remind-when-the-review-page-goes-stale.md`)
is to remind, not regenerate: regenerating would leave the dashboard-current
check able to catch only a hand-edited page.

So each verb prints one line naming `compass issue dashboard` when the page
it leaves behind no longer matches the manifest, and nothing when there is
no page or the page still matches.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
SLUG = "greeting-fix"
REMINDER = "compass issue dashboard"


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    started = _run(
        root, "quick-fix", "start", SLUG,
        "--risk", "trivial - a one-line text change",
        "--familiarity", "brownfield-mapped - the file and its test exist",
        "--size", "atomic - one file, one obvious change",
        "--intent", "The greeting says hello.",
        "--scenario", "Given the greeting, when it is read, then it says hello.",
        "--scenario-id", "TRC-001",
        "--test", "tests/test_greeting.py::test_greeting_says_hello")
    assert started.returncode == 0, started.stdout + started.stderr
    return root


def _work(root):
    return root / ".compass" / "work" / SLUG


def _with_a_current_page(root):
    made = _run(root, "issue", "dashboard", "--issue", SLUG)
    assert made.returncode == 0, made.stdout + made.stderr
    assert (_work(root) / "README.md").is_file()


def _reminders(result):
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.count(REMINDER)


def _evidence_file(root):
    path = _work(root) / "evidence" / "note.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("checked by hand\n")
    return "evidence/note.txt"


VERBS = {
    "evidence add": lambda root: _run(
        root, "evidence", "add", "--issue", SLUG, "--type", "command-output",
        "--path", _evidence_file(root), "EV-NOTE"),
    "issue set-status": lambda root: _run(
        root, "issue", "set-status", "parked", "--reason", "waiting",
        "--issue", SLUG),
    "issue artifact": lambda root: _run(
        root, "issue", "artifact", "delivery-approach", "--status",
        "approved", "--issue", SLUG),
}


@pytest.mark.parametrize("verb", sorted(VERBS))
def test_a_verb_that_leaves_the_page_stale_says_so_once(repo, verb):
    _with_a_current_page(repo)
    assert _reminders(VERBS[verb](repo)) == 1


@pytest.mark.parametrize("verb", sorted(VERBS))
def test_a_verb_on_an_issue_with_no_page_says_nothing_about_it(repo, verb):
    assert not (_work(repo) / "README.md").exists()
    assert _reminders(VERBS[verb](repo)) == 0


def _changed_file_add(root):
    return _run(root, "changed-file", "add", "README.md", "--scenario",
                "TRC-001", "--issue", SLUG)


def test_changed_file_add_is_silent_while_the_page_still_matches(repo):
    # The page does not show changed files, so tracing one leaves it current.
    _with_a_current_page(repo)
    assert _reminders(_changed_file_add(repo)) == 0


def test_changed_file_add_reminds_when_the_page_no_longer_matches(repo):
    _with_a_current_page(repo)
    page = _work(repo) / "README.md"
    page.write_text(page.read_text() + "\nedited after generation\n")
    assert _reminders(_changed_file_add(repo)) == 1


def test_gate_pass_that_leaves_the_page_stale_says_so_once(repo):
    VERBS["evidence add"](repo)
    _with_a_current_page(repo)
    result = _run(repo, "gate", "pass", "verify.governance", "--evidence",
                  "EV-NOTE", "--issue", SLUG)
    assert _reminders(result) == 1


def test_approach_evaluate_write_that_leaves_the_page_stale_says_so_once(repo):
    _with_a_current_page(repo)
    path = _work(repo) / "manifest.yml"
    manifest = yaml.safe_load(path.read_text())
    manifest["assessment"]["size"] = "standard"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    result = _run(repo, "approach", "evaluate", "--issue", SLUG, "--write",
                  "--reason", "the change is bigger than one file")
    assert _reminders(result) == 1


def test_the_reminder_is_silent_while_the_page_still_matches(repo):
    from compass_pkg.dashboard import stale_page_reminder
    _with_a_current_page(repo)
    assert stale_page_reminder(str(_work(repo))) is None
    (_work(repo) / "README.md").unlink()
    assert stale_page_reminder(str(_work(repo))) is None
