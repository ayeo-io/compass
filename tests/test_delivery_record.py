"""The delivery record is synced to a second, private repository.

A project's issue records are kept out of its own git history, so they lived
on one machine. `compass record sync` copies the paths `.compass/config.yml`
names into the repository it names, with credentials redacted, and
`ship-commit` runs it after every landing. `compass record restore` brings
the record back into a fresh clone.

Scenario ids: DR-A to DR-E, in the acceptance criteria of the issue
`delivery-record`.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_ship_commit_derives import _init_repo, _open_issue, _run_ship_commit

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TOKEN = "sk-ant-api03-FAKEfakeFAKEfake0123456789abcdef"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True)


def _remote(tmp_path):
    remote = tmp_path / "record.git"
    # A default branch other than the record's `main`, as git gives where
    # init.defaultBranch is unset (CI): the record must still be found.
    subprocess.run(["git", "-c", "init.defaultBranch=master", "init", "-q",
                    "--bare", str(remote)], check=True)
    return remote


def _configure(project, remote, paths=(".compass/work", "docs/analysis")):
    cfg = project / ".compass" / "config.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"record:", f"  remote: {remote}", "  paths:"]
    lines += [f"    - {p}" for p in paths]
    existing = cfg.read_text() if cfg.exists() else ""
    cfg.write_text(existing + "\n".join(lines) + "\n")


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    root = tmp_path / "project"
    root.mkdir()
    _init_repo(root)
    (root / ".compass" / "work" / "one").mkdir(parents=True)
    (root / ".compass" / "work" / "one" / "manifest.yml").write_text("issue: one\n")
    (root / "docs" / "analysis").mkdir(parents=True)
    (root / "docs" / "analysis" / "plan.md").write_text(
        f"A private plan. Key {TOKEN} pasted by mistake.\n")
    return root


def _cli(cwd, *args):
    env = {**os.environ}
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, env=env, timeout=120)


def _record_files(remote, tmp_path, name="check"):
    clone = tmp_path / name
    subprocess.run(["git", "clone", "-q", "-b", "main", str(remote), str(clone)],
                   check=True)
    return clone


# --- DR-A: sync ---------------------------------------------------------------

def test_dr_a_sync_copies_redacts_commits_and_pushes(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    result = _cli(project, "record", "sync")
    assert result.returncode == 0, result.stdout + result.stderr
    clone = _record_files(remote, tmp_path)
    assert (clone / ".compass" / "work" / "one" / "manifest.yml").read_text() == "issue: one\n"
    plan = (clone / "docs" / "analysis" / "plan.md").read_text()
    assert TOKEN not in plan and "[REDACTED]" in plan
    head = _git(project, "rev-parse", "--short=12", "HEAD").stdout.strip()
    assert head in _git(clone, "log", "-1", "--format=%s").stdout


def test_dr_a_a_deleted_file_stays_unless_pruned_and_no_change_makes_no_commit(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    (project / "docs" / "analysis" / "plan.md").unlink()
    (project / "docs" / "analysis" / "other.md").write_text("kept\n")
    assert _cli(project, "record", "sync").returncode == 0
    clone = _record_files(remote, tmp_path, "kept")
    # A plain sync adds and updates; it never deletes from the record.
    assert (clone / "docs" / "analysis" / "plan.md").exists()
    assert _cli(project, "record", "sync", "--prune").returncode == 0
    clone = _record_files(remote, tmp_path)
    assert not (clone / "docs" / "analysis" / "plan.md").exists()
    commits = _git(clone, "rev-list", "--count", "HEAD").stdout.strip()
    again = _cli(project, "record", "sync")
    assert again.returncode == 0 and "nothing to sync" in again.stdout
    clone2 = _record_files(remote, tmp_path, "check2")
    assert _git(clone2, "rev-list", "--count", "HEAD").stdout.strip() == commits


# --- DR-B: no record configured ---------------------------------------------------

def test_dr_b_no_record_configured_is_a_no_op(project):
    result = _cli(project, "record", "sync")
    assert result.returncode == 0
    assert "no record" in result.stdout.lower()


# --- DR-C: ship syncs, and a failed sync fails ship ----------------------------------

def test_dr_c_ship_commit_syncs_the_record_after_landing(cli_path, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    remote = _remote(tmp_path)
    _configure(repo, remote, paths=(".compass/work",))
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "name the record")
    _open_issue(repo, "shipped")
    result = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", "shipped")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "record synced" in result.stdout
    clone = _record_files(remote, tmp_path)
    assert "status: landed" in (clone / ".compass" / "work" / "shipped" / "manifest.yml").read_text()


def test_dr_c_a_failed_sync_fails_ship_loudly(cli_path, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _configure(repo, tmp_path / "no-such-remote.git", paths=(".compass/work",))
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "name the record")
    _open_issue(repo, "shipped")
    result = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", "shipped")
    assert result.returncode != 0
    assert "landed" in result.stdout + result.stderr
    assert "compass record sync" in result.stdout + result.stderr


# --- DR-D: restore ---------------------------------------------------------------------

def test_dr_d_restore_brings_the_record_into_a_fresh_clone(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    _init_repo(fresh)
    _configure(fresh, remote)
    result = _cli(fresh, "record", "restore")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (fresh / ".compass" / "work" / "one" / "manifest.yml").is_file()
    assert "restored" in result.stdout


def test_dr_d_restore_refuses_to_overwrite_a_differing_file(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    (project / ".compass" / "work" / "one" / "manifest.yml").write_text("issue: changed\n")
    refused = _cli(project, "record", "restore")
    assert refused.returncode != 0 and "--force" in refused.stderr
    assert (project / ".compass" / "work" / "one" / "manifest.yml").read_text() == "issue: changed\n"
    forced = _cli(project, "record", "restore", "--force")
    assert forced.returncode == 0
    assert (project / ".compass" / "work" / "one" / "manifest.yml").read_text() == "issue: one\n"


# --- DR-E: the decision ------------------------------------------------------------------

def test_dr_e_the_decision_is_recorded():
    adr = next((ROOT / "architecture" / "decisions").glob("ADR-031-*.md"))
    text = adr.read_text()
    assert "compass record sync" in text and "restore" in text
    assert "private" in text


def test_dr_a_a_path_missing_from_this_checkout_is_kept_in_the_record(project, tmp_path):
    """A worktree has none of the ignored folders. Syncing from one must not
    wipe them from the record: a whole path that is absent is skipped."""
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    import shutil
    shutil.rmtree(project / "docs" / "analysis")
    (project / ".compass" / "work" / "two").mkdir()
    (project / ".compass" / "work" / "two" / "manifest.yml").write_text("issue: two\n")
    result = _cli(project, "record", "sync")
    assert result.returncode == 0, result.stderr
    assert "docs/analysis" in result.stdout and "not in this checkout" in result.stdout
    clone = _record_files(remote, tmp_path)
    assert (clone / "docs" / "analysis" / "plan.md").is_file()
    assert (clone / ".compass" / "work" / "two" / "manifest.yml").is_file()



# --- found in review ----------------------------------------------------------

def test_dr_a_a_partial_checkout_deletes_nothing(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    (project / ".compass" / "work" / "two").mkdir()
    (project / ".compass" / "work" / "two" / "manifest.yml").write_text("issue: two\n")
    assert _cli(project, "record", "sync").returncode == 0
    import shutil
    shutil.rmtree(project / ".compass" / "work" / "two")
    assert _cli(project, "record", "sync").returncode == 0
    clone = _record_files(remote, tmp_path)
    assert (clone / ".compass" / "work" / "two" / "manifest.yml").is_file()


def test_dr_a_a_full_sync_from_a_linked_worktree_is_refused(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    _git(project, "add", "-A")
    _git(project, "commit", "-q", "-m", "all")
    linked = tmp_path / "linked"
    assert _git(project, "worktree", "add", "-q", str(linked)).returncode == 0
    result = _cli(linked, "record", "sync")
    assert result.returncode != 0 and "worktree" in result.stderr


@pytest.mark.parametrize("bad", [".", ".git", ".git/hooks", " ../outside", "../x",
                                 "/etc", "./.git", "docs/../.git", "a/.git",
                                 "docs/..", ".Git", ".GIT", "./.gIt/hooks"])
def test_dr_a_a_path_outside_the_project_or_into_git_is_refused(project, tmp_path, bad):
    remote = _remote(tmp_path)
    _configure(project, remote, paths=(".compass/work", bad))
    result = _cli(project, "record", "sync")
    assert result.returncode != 0, result.stdout
    assert "path" in result.stderr


def test_dr_a_a_cached_clone_of_another_remote_is_replaced(project, tmp_path):
    first = _remote(tmp_path)
    _configure(project, first)
    assert _cli(project, "record", "sync").returncode == 0
    import hashlib, shutil
    cache = tmp_path / "cache" / "compass" / "record"
    clone = next(cache.iterdir())
    _git(clone, "remote", "set-url", "origin", str(tmp_path / "elsewhere.git"))
    (project / "docs" / "analysis" / "new.md").write_text("new\n")
    assert _cli(project, "record", "sync").returncode == 0
    check = _record_files(first, tmp_path)
    assert (check / "docs" / "analysis" / "new.md").is_file()


def test_dr_c_any_error_in_the_sync_still_says_the_commit_landed(cli_path, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    remote = _remote(tmp_path)
    _configure(repo, remote, paths=(".compass/work",))
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "name the record")
    task_dir = _open_issue(repo, "shipped")
    unreadable = task_dir / "evidence"
    unreadable.mkdir()
    (unreadable / "locked.json").write_text("{}")
    (unreadable / "locked.json").chmod(0)
    try:
        result = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", "shipped")
    finally:
        (unreadable / "locked.json").chmod(0o644)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "compass record sync" in result.stderr


def test_dr_c_ship_from_a_linked_worktree_syncs_only_the_issue(cli_path, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    remote = _remote(tmp_path)
    _configure(repo, remote, paths=(".compass/work", "docs/analysis"))
    (repo / "docs" / "analysis").mkdir(parents=True)
    (repo / "docs" / "analysis" / "plan.md").write_text("the plan\n")
    (repo / ".compass" / "work" / "older").mkdir(parents=True)
    (repo / ".compass" / "work" / "older" / "manifest.yml").write_text("issue: older\n")
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "name the record")
    assert _cli(repo, "record", "sync").returncode == 0
    linked = tmp_path / "linked"
    assert _git(repo, "worktree", "add", "-q", str(linked)).returncode == 0
    _open_issue(linked, "shipped")
    result = _run_ship_commit(cli_path, linked, "-m", "land it", "--issue", "shipped")
    assert result.returncode == 0, result.stdout + result.stderr
    clone = _record_files(remote, tmp_path)
    assert (clone / ".compass" / "work" / "shipped" / "manifest.yml").is_file()
    assert (clone / ".compass" / "work" / "older" / "manifest.yml").is_file()
    assert (clone / "docs" / "analysis" / "plan.md").is_file()



def test_dr_a_a_link_or_other_name_for_git_is_refused_by_identity(project, tmp_path):
    """The check compares the folder itself, not its spelling: a symlink
    named anything that leads to `.git` is refused too."""
    remote = _remote(tmp_path)
    (project / "gitlink").symlink_to(project / ".git")
    _configure(project, remote, paths=(".compass/work", "gitlink"))
    result = _cli(project, "record", "sync")
    assert result.returncode != 0 and "git" in result.stderr



def _plant_link_in_record(remote, tmp_path, rel, target):
    """Commit a symbolic link into the record repository, as someone with
    write access to it could."""
    work = tmp_path / "attacker"
    subprocess.run(["git", "clone", "-q", str(remote), str(work)], check=True)
    link = work / rel
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    _git(work, "add", "-A")
    _git(work, "-c", "user.name=x", "-c", "user.email=x@example.invalid",
         "commit", "-q", "-m", "plant")
    _git(work, "push", "-q", "origin", "HEAD:main")


def test_dr_a_a_record_holding_a_link_is_refused_by_sync_and_restore(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    assert _cli(project, "record", "sync").returncode == 0
    secret = tmp_path / "id_key"
    secret.write_text("PRIVATE KEY\n")
    _plant_link_in_record(remote, tmp_path, ".compass/work/x/key", str(secret))
    sync = _cli(project, "record", "sync")
    assert sync.returncode != 0 and "link" in sync.stderr
    restore = _cli(project, "record", "restore", "--force")
    assert restore.returncode != 0 and "link" in restore.stderr
    assert not (project / ".compass" / "work" / "x" / "key").exists()


def test_dr_a_a_nested_git_folder_or_file_is_not_copied(project, tmp_path):
    remote = _remote(tmp_path)
    _configure(project, remote)
    nested = project / ".compass" / "work" / "one" / ".GIT"
    nested.mkdir()
    (nested / "config").write_text("[remote]\n")
    # In another folder: on a file system that ignores case, `.git` and
    # `.GIT` side by side are one name.
    (project / ".compass" / "work" / "two").mkdir()
    (project / ".compass" / "work" / "two" / ".git").write_text("gitdir: x\n")
    assert _cli(project, "record", "sync").returncode == 0
    clone = _record_files(remote, tmp_path)
    assert not (clone / ".compass" / "work" / "one" / ".GIT").exists()
    assert not (clone / ".compass" / "work" / "two" / ".git").exists()


def test_dr_c_a_worktree_ship_syncs_only_configured_paths(cli_path, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    remote = _remote(tmp_path)
    _configure(repo, remote, paths=("docs/analysis",))
    (repo / "docs" / "analysis").mkdir(parents=True)
    (repo / "docs" / "analysis" / "plan.md").write_text("the plan\n")
    _git(repo, "add", ".compass/config.yml")
    _git(repo, "commit", "-q", "-m", "name the record")
    assert _cli(repo, "record", "sync").returncode == 0
    linked = tmp_path / "linked"
    assert _git(repo, "worktree", "add", "-q", str(linked)).returncode == 0
    _open_issue(linked, "shipped")
    result = _run_ship_commit(cli_path, linked, "-m", "land it", "--issue", "shipped")
    assert result.returncode == 0, result.stdout + result.stderr
    clone = _record_files(remote, tmp_path)
    assert not (clone / ".compass" / "work" / "shipped").exists()
    assert (clone / "docs" / "analysis" / "plan.md").is_file()
