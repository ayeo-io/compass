"""A validation acceptance must be declared before the change.

An acceptance stands in for a red, so it is declared first. Nothing checked
that for a validation on a quick fix: edit the file, then declare, then
finish, and all three gates passed. `acceptance start --kind validation` now
lists the files changed since `quick-fix start`, against the commit at start
so a staged change counts, and refuses when there are any.

Scenario id: LV-1 (issue `late-validation-acceptance`).
"""
from __future__ import annotations

from test_quick_fix_verbs import _git, _manifest, _run, _start, repo  # noqa: F401

SLUG = "tidy-conf"
VALIDATE = ["--", "python3", "-c", "import configparser; configparser.ConfigParser().read('app.ini')"]
TEST = ["--", "python3", "-c", "pass"]


def _setup(repo, dirty=None):
    (repo / "app.ini").write_text("[a]\nx = 1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "conf")
    if dirty:
        (repo / dirty).write_text("someone else's work\n")
    started = _start(repo, SLUG, test="tests/test_conf.py::test_conf")
    assert started.returncode == 0, started.stderr


def _declare(repo):
    return _run(repo, "acceptance", "start", "--kind", "validation", "--issue", SLUG, *VALIDATE)


def test_lv_1_a_validation_declared_after_the_change_is_refused(repo):
    _setup(repo)
    (repo / "app.ini").write_text("[a]\nx = 2\n")
    declared = _declare(repo)
    assert declared.returncode != 0, declared.stdout
    assert "app.ini" in declared.stderr, declared.stderr


def test_lv_1_a_staged_change_before_declaring_is_refused(repo):
    _setup(repo)
    (repo / "app.ini").write_text("[a]\nx = 2\n")
    _git(repo, "add", "app.ini")
    declared = _declare(repo)
    assert declared.returncode != 0, declared.stdout
    assert "app.ini" in declared.stderr, declared.stderr


def test_lv_1_declared_first_a_staged_change_records_and_finishes(repo):
    _setup(repo)
    assert _declare(repo).returncode == 0
    (repo / "app.ini").write_text("[a]\nx = 2\n")
    _git(repo, "add", "app.ini")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Raise x",
                  "--no-commit", *VALIDATE)
    assert finish.returncode == 0, finish.stdout + finish.stderr


def test_lv_1_a_file_dirty_before_quick_fix_start_does_not_count(repo):
    _setup(repo, dirty="notes.txt")
    declared = _declare(repo)
    assert declared.returncode == 0, declared.stderr


def test_lv_1_a_refactor_may_write_its_characterisation_test_first(repo):
    _setup(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_conf.py").write_text("def test_conf():\n    assert True\n")
    declared = _run(repo, "acceptance", "start", "--kind", "refactor", "--issue", SLUG,
                    "--", "python3", "-m", "pytest", "-q", "tests/test_conf.py")
    assert declared.returncode == 0, declared.stderr


def test_lv_1_someone_elses_commit_after_start_does_not_block(repo):
    # A pull or a parallel session's commit is not this fix's change, and
    # an issue that cannot be restarted must not be stuck behind it.
    _setup(repo)
    (repo / "other.py").write_text("x = 1\n")
    _git(repo, "add", "other.py")
    _git(repo, "commit", "-q", "-m", "someone else")
    declared = _declare(repo)
    assert declared.returncode == 0, declared.stderr


def test_lv_1_declared_first_a_git_mv_records_and_finishes(repo):
    _setup(repo)
    assert _declare(repo).returncode == 0
    _git(repo, "mv", "README.md", "README.txt")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Rename",
                  "--no-commit", *VALIDATE)
    assert finish.returncode == 0, finish.stdout + finish.stderr


def test_lv_1_a_git_mv_before_declaring_is_refused(repo):
    _setup(repo)
    _git(repo, "mv", "README.md", "README.txt")
    declared = _declare(repo)
    assert declared.returncode != 0
    assert "README" in declared.stderr, declared.stderr


def test_lv_1_declared_first_an_ignored_path_change_finishes(repo):
    (repo / ".gitignore").write_text(".env\n")
    _setup(repo)
    assert _declare(repo).returncode == 0
    (repo / ".env").write_text("X=1\n")
    (repo / "app.ini").write_text("[a]\nx = 2\n")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG, "-m", "Env",
                  "--no-commit", *VALIDATE)
    assert finish.returncode == 0, finish.stdout + finish.stderr


def test_lv_1_a_validator_output_file_must_be_cleared_before_declaring(repo):
    # Pinned, not hidden: an untracked output file is indistinguishable
    # from a change, so the refusal names it and the docs say to delete or
    # ignore it first.
    _setup(repo)
    (repo / "junit.xml").write_text("<testsuite/>\n")
    declared = _declare(repo)
    assert declared.returncode != 0
    assert "junit.xml" in declared.stderr, declared.stderr
