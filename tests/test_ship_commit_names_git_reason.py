"""`compass ship-commit` prints the reason git gave when the commit fails.

The error used to open with a guess ("a pre-commit hook may be aborting the
commit") and show git's own message only after it. With no author identity
set no hook exists, so the guess sent the reader to look for a problem that
is not there. The error now starts with git's own lines, says the land did
not happen, and names a pre-commit hook only when one is installed.
"""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

HOOK_GUESS = "pre-commit hook may be aborting"
SETUP_IDENTITY = {
    "GIT_AUTHOR_NAME": "Setup", "GIT_AUTHOR_EMAIL": "setup@example.com",
    "GIT_COMMITTER_NAME": "Setup", "GIT_COMMITTER_EMAIL": "setup@example.com",
}


def _git(cwd: Path, *args: str, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, env=env)


@pytest.fixture
def no_identity(tmp_path, monkeypatch):
    """Run the CLI where git can find no author name or email.

    HOME and the config files point at empty places, and the repository sets
    `user.useConfigOnly` so git cannot guess an identity from the host name
    either - a developer machine would otherwise pass for the wrong reason.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME",
                 "GIT_COMMITTER_EMAIL", "EMAIL"):
        monkeypatch.delenv(name, raising=False)


def _repo_with_staged_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, **SETUP_IDENTITY}
    _git(repo, "init", "-q", env=env)
    _git(repo, "config", "commit.gpgsign", "false", env=env)
    _git(repo, "config", "user.useConfigOnly", "true", env=env)
    (repo / "file.txt").write_text("hello\n")
    _git(repo, "add", "-A", env=env)
    _git(repo, "commit", "-q", "-m", "init", env=env)
    (repo / "file.txt").write_text("changed\n")
    _git(repo, "add", "-A", env=env)
    return repo


def _head(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_hook(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_no_identity_error_starts_with_gits_reason(run_cli, tmp_path,
                                                   no_identity):
    repo = _repo_with_staged_change(tmp_path)
    before = _head(repo)
    result = run_cli("ship-commit", "-m", "land it", cwd=repo)
    text = result.stdout + result.stderr
    assert result.returncode != 0, result
    assert _head(repo) == before
    assert "Author identity unknown" in text, text
    assert "Please tell me who you are" in text, text
    assert "HEAD did not advance" in text, text
    assert text.index("Author identity unknown") < text.index(
        "HEAD did not advance"), text
    assert HOOK_GUESS not in text, text
    assert "the land did NOT happen" in text, text


def test_a_failing_hook_still_gets_the_hook_suggestion(run_cli, tmp_path,
                                                       no_identity):
    repo = _repo_with_staged_change(tmp_path)
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@example.com")
    _write_hook(repo / ".git" / "hooks" / "pre-commit",
                "echo 'lint failed on file.txt' >&2\nexit 1\n")
    before = _head(repo)
    result = run_cli("ship-commit", "-m", "land it", cwd=repo)
    text = result.stdout + result.stderr
    assert result.returncode != 0, result
    assert _head(repo) == before
    assert "lint failed on file.txt" in text, text
    assert text.index("lint failed on file.txt") < text.index(
        "HEAD did not advance"), text
    assert HOOK_GUESS in text, text


def test_a_hook_in_the_configured_hooks_folder_counts(run_cli, tmp_path,
                                                      no_identity):
    repo = _repo_with_staged_change(tmp_path)
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "core.hooksPath", str(tmp_path / "shared-hooks"))
    _write_hook(tmp_path / "shared-hooks" / "pre-commit", "exit 1\n")
    result = run_cli("ship-commit", "-m", "land it", cwd=repo)
    assert result.returncode != 0, result
    assert HOOK_GUESS in result.stdout + result.stderr, result


def test_a_hook_file_that_cannot_run_is_not_blamed(run_cli, tmp_path,
                                                   no_identity):
    """git skips a hook that is not marked as runnable, so it cannot have
    aborted the commit."""
    repo = _repo_with_staged_change(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    _write_hook(hook, "exit 1\n")
    hook.chmod(0o644)
    result = run_cli("ship-commit", "-m", "land it", cwd=repo)
    text = result.stdout + result.stderr
    assert result.returncode != 0, result
    assert "Author identity unknown" in text, text
    assert HOOK_GUESS not in text, text
