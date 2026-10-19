"""Group D of issue `hooks-stop-refusing-harmless-work`: when `/compass:approve`
cannot name an approver, its message names the real cause.

Scenarios: `TRC-020` to `TRC-028`. The new contract is
`approval_records.owner_and_cause(task_dir)`, which returns an `OwnerLookup`
(`owner`, `cause`, `detail`, `root`, `found_in`) with one of seven `CAUSE_*`
values. `project_owner` keeps returning the owner or None, and
`prompt_approval.resolve_approver` uses the cause only when
`COMPASS_APPROVER` names no one.

Red before the change: `TRC-020` to `TRC-025` and the contract test, because
every cause gives the one message "no approver can be named". Green before the
change, kept as regression guards: `TRC-026`, `TRC-027`, `TRC-028`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from approval_support import OWNER, event, project, task_dir  # noqa: E402

COMMANDS = ("approve", "reject", "delegate", "revoke")
NO_APPROVER = "no approver can be named"


def _plugin(tmp_path):
    """A plugin root whose command files set the flag the hook requires."""
    root = tmp_path / "plugin"
    (root / "commands").mkdir(parents=True, exist_ok=True)
    for name in COMMANDS:
        (root / "commands" / f"{name}.md").write_text(
            f"---\ndescription: {name}\ndisable-model-invocation: true\n---\n\nBody.\n",
            encoding="utf-8")
    return root


def _type_approve(root, plugin, env=None):
    """What the hook answers when the person types /compass:approve in `root`."""
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root), dict(env or {}), plugin_root=str(plugin))


def _write_yml(root, content):
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    (root / "compass.yml").write_bytes(data)


def _blocked(root, plugin):
    result = _type_approve(root, plugin)
    assert result.block, result
    return result.message


def _short(message):
    return len(message.split()) < 60


@pytest.fixture
def setup(tmp_path):
    return project(tmp_path), _plugin(tmp_path)


# --- the loader cannot read compass.yml, or owner is not text ---------------------------------

@pytest.mark.parametrize("content, reason", [
    ("owner: jed72\nnot_a_key: 1\n", "not_a_key: not a key a project layer can hold"),
    ("owner: jed72\n\tenforcement: x\n", "invalid YAML"),
    ("owner: a\nowner: b\n", "duplicate key 'owner'"),
    ("- a\n- b\n", "expected a mapping, found list"),
    (b"\xff\xfe", "can't decode byte 0xff"),
])
def test_trc_020_a_compass_yml_the_loader_cannot_read_is_named(setup, content, reason):
    root, plugin = setup
    _write_yml(root, content)
    message = _blocked(root, plugin)
    assert "compass.yml" in message and "cannot be read" in message, message
    assert reason in message, message
    assert NO_APPROVER not in message, message
    assert _short(message), message


@pytest.mark.parametrize("content, kind", [
    ("owner: 123\n", "a number"),
    ("owner: true\n", "a boolean"),
    ("owner:\n  - a\n", "a list"),
    ("owner:\n  name: a\n", "a mapping"),
])
def test_trc_021_an_owner_that_is_not_text_is_named(setup, content, kind):
    root, plugin = setup
    _write_yml(root, content)
    message = _blocked(root, plugin)
    assert f"owner in compass.yml is {kind}, not text" in message, message
    assert "quote" in message.lower(), message
    assert NO_APPROVER not in message, message
    assert _short(message), message


# --- the owner is somewhere the approver is not read from --------------------------------------

def test_trc_022_an_owner_found_only_in_config_yml_is_named(setup):
    root, plugin = setup
    _write_yml(root, "schema: 1\n")
    (root / ".compass" / "config.yml").write_text(f"owner: {OWNER}\n", encoding="utf-8")
    message = _blocked(root, plugin)
    assert "read from compass.yml only" in message, message
    assert "owner" in message and "COMPASS_APPROVER" in message, message
    assert NO_APPROVER not in message, message
    assert _short(message), message


def test_trc_023_a_compass_yml_above_the_compass_folder_is_named(tmp_path):
    template = project(tmp_path)
    git_root = (tmp_path / "gitroot").resolve()
    app = git_root / "app"
    app.mkdir(parents=True)
    (git_root / ".git").mkdir()
    shutil.copy(template / "compass.yml", git_root / "compass.yml")
    shutil.copytree(template / ".compass", app / ".compass")
    message = _blocked(app, _plugin(tmp_path))
    assert str(git_root) in message and str(app) in message, message
    assert "only from the folder that holds .compass" in message, message
    assert NO_APPROVER not in message, message
    assert _short(message), message


def _git(cwd, *args):
    env = dict(os.environ, HOME=str(cwd.parent), GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="n", GIT_AUTHOR_EMAIL="n@example.com",
               GIT_COMMITTER_NAME="n", GIT_COMMITTER_EMAIL="n@example.com")
    subprocess.run(["git", *args], cwd=str(cwd), env=env, check=True, capture_output=True)


def test_trc_024_a_compass_yml_missing_in_a_linked_worktree_is_named(tmp_path):
    template = project(tmp_path)
    main = (tmp_path / "main").resolve()
    main.mkdir()
    _git(main, "init", "-b", "main")
    _git(main, "commit", "--allow-empty", "-m", "x")
    worktree = (tmp_path / "wt").resolve()
    _git(main, "worktree", "add", str(worktree))
    assert (worktree / ".git").is_file()
    shutil.copytree(template / ".compass", worktree / ".compass")
    message = _blocked(worktree, _plugin(tmp_path))
    assert str(worktree) in message, message
    assert "worktree" in message and "tracked" in message, message
    assert "copy compass.yml" in message.lower() and "COMPASS_APPROVER" in message, message
    assert NO_APPROVER not in message, message
    assert _short(message), message


def test_trc_025_a_compass_yml_missing_outside_a_worktree_has_no_worktree_hint(tmp_path):
    template = project(tmp_path)
    folder = (tmp_path / "plain").resolve()
    folder.mkdir()
    (folder / ".git").mkdir()
    shutil.copytree(template / ".compass", folder / ".compass")
    message = _blocked(folder, _plugin(tmp_path))
    assert f"no compass.yml in {folder}" in message, message
    assert "worktree" not in message.lower(), message
    assert NO_APPROVER not in message, message
    assert _short(message), message


# --- the messages that must not change --------------------------------------------------------

def test_trc_026_a_compass_yml_with_no_owner_keeps_its_message(setup):
    root, plugin = setup
    _write_yml(root, "schema: 1\n")
    message = _blocked(root, plugin)
    assert NO_APPROVER in message, message
    assert "owner: <your id>" in message and "COMPASS_APPROVER" in message, message


def test_trc_027_a_named_approver_is_accepted_while_compass_yml_is_unreadable(setup):
    from compass_pkg import prompt_approval
    root, _ = setup
    _write_yml(root, "owner: jed72\nnot_a_key: 1\n")
    assert prompt_approval.resolve_approver(str(task_dir(root)), {"COMPASS_APPROVER": "ada"}) == (
        "ada", "approver", "environment")


@pytest.mark.parametrize("state, content", [
    ("missing", None),
    ("rejected by the loader", "owner: jed72\nnot_a_key: 1\n"),
    ("a YAML syntax error", "owner: jed72\n\tenforcement: x\n"),
    ("not UTF-8", b"\xff\xfe"),
    ("holding owner: 123", "owner: 123\n"),
])
def test_trc_028_other_readers_of_the_owner_still_get_nothing(setup, state, content):
    from compass_pkg import approval_records
    root, _ = setup
    if content is None:
        (root / "compass.yml").unlink()
    else:
        _write_yml(root, content)
    assert approval_records.project_owner(str(task_dir(root))) is None, state


# --- the contract of the new function ---------------------------------------------------------

def test_owner_and_cause_gives_the_owner_or_one_of_seven_causes(setup, tmp_path):
    from compass_pkg import approval_records as records
    assert (records.CAUSE_UNREADABLE, records.CAUSE_NOT_TEXT, records.CAUSE_CONFIG_ONLY,
            records.CAUSE_FILE_ABOVE, records.CAUSE_MISSING_IN_WORKTREE, records.CAUSE_MISSING,
            records.CAUSE_NO_OWNER) == (
        "unreadable", "owner-not-text", "owner-in-config-yml", "compass-yml-above",
        "compass-yml-missing-in-worktree", "compass-yml-missing", "no-owner")
    root, _ = setup
    found = records.owner_and_cause(str(task_dir(root)))
    assert (found.owner, found.cause) == (OWNER, None)
    _write_yml(root, "owner: 123\n")
    found = records.owner_and_cause(str(task_dir(root)))
    assert (found.owner, found.cause, found.detail) == (None, records.CAUSE_NOT_TEXT, "a number")
    _write_yml(root, "owner: true\n")
    assert records.owner_and_cause(str(task_dir(root))).detail == "a boolean"
    _write_yml(root, "schema: 1\n")
    assert records.owner_and_cause(str(task_dir(root))).cause == records.CAUSE_NO_OWNER
    (root / "compass.yml").unlink()
    assert records.owner_and_cause(str(task_dir(root))).cause == records.CAUSE_MISSING
