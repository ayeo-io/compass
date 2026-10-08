"""`compass scenario tests` replaces the tests a scenario declares.

Before this verb a scenario whose declared test id was wrong - after a test
was renamed for a good reason, say - could be fixed only by renaming the test
back or by editing manifest.yml by hand. The verb writes the manifest through
the writer the other scenario verbs use, and it accepts only a test id that
`declared-tests-resolve` would accept, because both call one resolver.

The issue is `scenario-tests-verb`, and it has one scenario.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

EXAMPLE = ROOT / "tests" / "fixtures" / "scenario-tests-json-example.json"
SLUG = "swap"
OLD = "tests/test_old.py::test_old_name"
NEW = "tests/test_new.py::test_new_name"


def _body(tests=(OLD,)):
    return {
        "task": SLUG,
        "created": "2026-10-08",
        "status": "active",
        "scenarios": [
            {"id": "SCN-1", "title": "the first case", "intent": "INT-1",
             "tests": list(tests)},
            {"id": "SCN-2", "title": "the second case", "intent": "INT-1",
             "tests": ["tests/test_other.py::test_other"]},
        ],
        "evidence": [],
        "gates": [{"id": "verify.correctness", "status": "pending",
                   "evidence": []}],
        "changed_files": [],
    }


@pytest.fixture
def issue(project, make_task):
    """An issue declaring a renamed test, with the renamed test on disk."""
    tests = project / "tests"
    tests.mkdir()
    (tests / "test_old.py").write_text("def test_old_name():\n    pass\n")
    (tests / "test_new.py").write_text("def test_new_name():\n    pass\n")
    (tests / "test_other.py").write_text("def test_other():\n    pass\n")
    return make_task(SLUG, _body())


def _tests(task_dir, sid="SCN-1"):
    data = yaml.safe_load((task_dir / "manifest.yml").read_text())
    return next(s for s in data["scenarios"] if s["id"] == sid)["tests"]


def test_the_verb_replaces_the_declared_tests(run_cli, issue):
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW,
                     "--reason", "test renamed")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _tests(issue) == [NEW]
    assert _tests(issue, "SCN-2") == ["tests/test_other.py::test_other"]


def test_the_verb_takes_several_tests_in_the_order_given(run_cli, issue):
    second = "tests/test_old.py::test_old_name"
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW,
                     "--test", second)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _tests(issue) == [NEW, second]


def test_an_unknown_scenario_is_refused_and_nothing_is_written(run_cli, issue):
    before = (issue / "manifest.yml").read_text()
    result = run_cli("scenario", "tests", "SCN-9", "--test", NEW)
    assert result.returncode == 2, result.stdout + result.stderr
    combined = result.stdout + result.stderr
    assert "SCN-9" in combined and "SCN-1" in combined, combined
    assert (issue / "manifest.yml").read_text() == before


def test_no_test_is_refused(run_cli, issue):
    before = (issue / "manifest.yml").read_text()
    result = run_cli("scenario", "tests", "SCN-1")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "--test" in result.stdout + result.stderr
    assert (issue / "manifest.yml").read_text() == before


@pytest.mark.parametrize("bad", [
    "tests/test_new.py::test_no_such_name",   # file exists, name does not
    "tests/test_missing.py::test_new_name",   # file does not exist
])
def test_a_test_that_does_not_resolve_is_refused(run_cli, issue, bad):
    before = (issue / "manifest.yml").read_text()
    result = run_cli("scenario", "tests", "SCN-1", "--test", bad)
    assert result.returncode == 2, result.stdout + result.stderr
    assert bad in result.stdout + result.stderr
    assert (issue / "manifest.yml").read_text() == before


def test_a_skipped_test_is_refused_as_the_check_refuses_it(run_cli, project,
                                                           issue):
    (project / "tests" / "test_new.py").write_text(
        "import pytest\n\n@pytest.mark.skip\ndef test_new_name():\n    pass\n")
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "skipped" in result.stdout + result.stderr


def test_the_verb_and_the_check_share_one_resolver(project, issue):
    """The verb accepts exactly the ids `declared-tests-resolve` accepts."""
    from compass_pkg import manifest, test_ids

    assert manifest._test_id_resolves is test_ids._test_id_resolves
    assert manifest._test_is_skipped is test_ids._test_is_skipped


def test_the_check_agrees_after_the_swap(run_cli, issue):
    """`declared-tests-resolve` fails on the stale id and passes after the
    verb, with correctness claimed."""
    path = issue / "manifest.yml"
    data = yaml.safe_load(path.read_text())
    data["scenarios"][0]["tests"] = ["tests/test_gone.py::test_old_name"]
    data["gates"][0]["status"] = "pass"
    path.write_text(yaml.safe_dump(data, sort_keys=False))

    def verdict():
        out = run_cli("check", "--issue", SLUG, "--json").stdout
        rows = json.loads(out)
        text = json.dumps(rows)
        return "do not resolve" in text

    assert verdict(), "the stale id should fail declared-tests-resolve"
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not verdict()


def test_the_devlog_line_names_the_old_and_new_tests_and_the_reason(run_cli,
                                                                    issue):
    (issue / "devlog.md").write_text("# Devlog - swap\n\n")
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW,
                     "--reason", "renamed to say what it checks")
    assert result.returncode == 0, result.stdout + result.stderr
    lines = (issue / "devlog.md").read_text().splitlines()
    entry = next(ln for ln in lines if "SCN-1" in ln)
    assert OLD in entry and NEW in entry, entry
    assert "renamed to say what it checks" in entry, entry
    assert entry.startswith("- 20"), entry


def test_no_devlog_is_created_when_the_issue_has_none(run_cli, issue):
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (issue / "devlog.md").exists()


def test_json_output_matches_the_pinned_fixture(run_cli, issue):
    result = run_cli("scenario", "tests", "SCN-1", "--test", NEW,
                     "--reason", "test renamed", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    got = json.loads(result.stdout)
    pinned = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert got == pinned
    assert list(got) == list(pinned)


def test_the_verb_is_in_the_help_and_the_readme():
    from compass_pkg.verb_help import VERB_DESCRIPTIONS

    assert "scenario tests" in VERB_DESCRIPTIONS
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "compass scenario tests" in readme


# --- a changed test list cannot keep a stale green -------------------------

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _git(root, *args):
    return subprocess.run([*GIT, *args], cwd=root, capture_output=True,
                          text=True, check=True).stdout.strip()


def _cli(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)})


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    # ship-commit runs its own `git commit`, which does not see the -c
    # identity in GIT; CI has no global identity to fall back on.
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("base\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "new.py").write_text("y = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    (root / "tests" / "test_b.py").write_text("def test_b():\n    pass\n")
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": SLUG, "created": "2026-10-08",
        "status": "active",
        "scenarios": [{"id": "S-1", "title": "a case", "intent": "INT-1",
                       "tests": ["tests/test_a.py::test_a"]}],
        "gates": [{"id": "verify.correctness", "status": "pass",
                   "evidence": []}],
        "changed_files": [{"path": "src/new.py", "scenarios": ["S-1"]}],
        "evidence": [],
    }, sort_keys=False))
    return root


def _green(root):
    result = _cli(root, "tdd-green", "--issue", SLUG, "--", sys.executable,
                  "-c", "pass")
    assert result.returncode == 0, result.stderr


def test_a_swap_to_a_test_in_another_file_needs_a_green_on_that_file(repo):
    """The green recorded before the swap tested the old test file. After the
    swap, ship-commit refuses and names the new test file; a new tdd-green
    covers it and the commit lands."""
    _green(repo)
    result = _cli(repo, "scenario", "tests", "S-1", "--issue", SLUG,
                  "--test", "tests/test_b.py::test_b")
    assert result.returncode == 0, result.stdout + result.stderr
    _git(repo, "add", "src/new.py", "tests/test_b.py")
    head = _git(repo, "rev-parse", "HEAD")

    refused = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")

    assert refused.returncode != 0, refused.stdout
    combined = refused.stdout + refused.stderr
    assert "tests/test_b.py" in combined and "tdd-green" in combined, combined
    assert _git(repo, "rev-parse", "HEAD") == head

    _green(repo)
    landed = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert landed.returncode == 0, landed.stdout + landed.stderr
    assert _git(repo, "rev-parse", "HEAD") != head
