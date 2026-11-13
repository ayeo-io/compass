"""The record mode, the `record.commit` setting and the ignore files (#356).

`record_mode.mode` decides whether an issue's folder is committed with its
code or kept out of the project's git history. `compass init` writes
`.compass/work/.gitignore` in every project, and the per-machine lines of
`.compass/.gitignore` in committed mode only. Nothing here stages a file:
`ship-commit` does that in committed mode.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from compass_pkg import init_cmd, record, record_mode, session_lease, settings_lint
from compass_pkg.core import CompassError

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                          text=True, check=True).stdout


def _project(tmp_path, record_block=None, git=True):
    root = (tmp_path / "project").resolve()
    root.mkdir()
    if git:
        _git(root, "init", "-q")
    if record_block is not None:
        text = "schema: 1\nrecord:\n" + "".join(
            f"  {key}: {json.dumps(value)}\n" for key, value in record_block.items())
        (root / "compass.yml").write_text(text, encoding="utf-8")
    return root


# --- the mode, one row of the table at a time -----------------------------------------

def test_record_commit_false_keeps_the_record_out(tmp_path):
    root = _project(tmp_path, {"commit": False})
    assert record_mode.mode(str(root)) == ("kept-out", "record.commit is false")


def test_record_commit_true_commits_the_record_even_with_a_remote(tmp_path):
    root = _project(tmp_path, {"commit": True, "remote": "https://example.org/r.git",
                               "paths": [".compass/work"]})
    assert record_mode.mode(str(root)) == ("committed", None)


def test_a_remote_without_record_commit_keeps_the_record_out(tmp_path):
    root = _project(tmp_path, {"remote": "https://example.org/r.git",
                               "paths": [".compass/work"]})
    assert record_mode.mode(str(root)) == (
        "kept-out", "the record is synced to https://example.org/r.git; "
                    "set record.commit to choose")


def test_neither_setting_commits_the_record(tmp_path):
    root = _project(tmp_path)
    found = record_mode.mode(str(root), str(root / ".compass" / "work" / "fix-a"))
    assert found.mode == record_mode.COMMITTED and found.reason is None


def test_an_ignored_issue_folder_is_kept_out_and_names_the_rule(tmp_path):
    """The project's own ignore rule wins: nothing is force-added and the
    landing is not refused, and the reason names the rule."""
    root = _project(tmp_path, {"commit": True})
    (root / ".gitignore").write_text("node_modules/\n/.compass/work/\n", encoding="utf-8")
    found = record_mode.mode(str(root), str(root / ".compass" / "work" / "fix-a"))
    assert found == ("kept-out",
                     ".compass/work/fix-a is ignored by .gitignore:2:/.compass/work/")


def test_outside_a_git_work_tree_the_record_is_kept_out(tmp_path):
    root = _project(tmp_path, git=False)
    assert record_mode.mode(str(root)) == ("kept-out", "not a git repository")


@pytest.mark.parametrize("value", ["no", 0, "false"])
def test_a_record_commit_that_is_not_a_boolean_is_refused(tmp_path, value):
    root = _project(tmp_path, {"commit": value})
    with pytest.raises(CompassError, match="must be true or false"):
        record_mode.mode(str(root))


def test_this_repository_keeps_its_record_out_because_it_names_a_remote():
    """VD-031: this repository names `record.remote` and no `record.commit`,
    so it stays kept out with no edit of its `compass.yml`. The file is read,
    never written."""
    path = ROOT / "compass.yml"
    before = path.read_bytes()
    found = record_mode.mode(str(ROOT))
    assert path.read_bytes() == before
    assert found == ("kept-out", "the record is synced to "
                                 "https://github.com/ayeo-io/compass-delivery.git; "
                                 "set record.commit to choose")


# --- the setting -------------------------------------------------------------------------

def test_record_settings_accepts_record_commit_alone(tmp_path):
    root = _project(tmp_path, {"commit": False})
    assert record.settings(str(root)) is None
    assert "no record is configured" in record.sync(str(root))


def test_record_settings_still_needs_paths_with_a_remote(tmp_path):
    root = _project(tmp_path, {"commit": True, "remote": "https://example.org/r.git"})
    with pytest.raises(CompassError, match="needs a `remote:`"):
        record.settings(str(root))


def test_the_lint_and_the_schema_accept_a_boolean_record_commit():
    assert settings_lint.lint({"record": {"commit": False}}) == []
    assert settings_lint.lint({"record": {"commit": True,
                                          "remote": "https://example.org/r.git",
                                          "paths": [".compass/work"]}}) == []
    node = settings_lint.schema()["properties"]["record"]["properties"]["commit"]
    assert node["type"] == "boolean"
    committed = json.loads((ROOT / "schemas" / "compass.schema.json").read_text())
    assert committed["properties"]["record"]["properties"]["commit"] == node


# --- the ignore files --------------------------------------------------------------------

def _lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_init_writes_the_work_ignore_file_once(tmp_path):
    root = _project(tmp_path)
    init_cmd.ensure_initialised(str(root))
    path = root / ".compass" / "work" / ".gitignore"
    first = path.read_text(encoding="utf-8")
    assert _lines(path) == [*record_mode.WORK_IGNORE_HEADER, *record_mode.WORK_IGNORE_LINES]
    changed = []
    init_cmd.ensure_initialised(str(root), changed=changed)
    assert changed == []
    assert path.read_text(encoding="utf-8") == first


def test_init_keeps_the_persons_lines_and_adds_only_the_missing_ones(tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work"
    work.mkdir(parents=True)
    held = ["# mine", "*/scratch/", "*/generations/"]
    (work / ".gitignore").write_text("\n".join(held) + "\n", encoding="utf-8")
    changed = []
    init_cmd.ensure_initialised(str(root), changed=changed)
    lines = _lines(work / ".gitignore")
    assert lines[:3] == held
    assert lines.count("*/generations/") == 1
    for line in record_mode.WORK_IGNORE_LINES:
        assert line in lines, line
    assert str(work / ".gitignore") in changed


def test_init_writes_the_work_ignore_file_in_a_kept_out_project(tmp_path):
    root = _project(tmp_path, {"commit": False})
    init_cmd.ensure_initialised(str(root))
    assert (root / ".compass" / "work" / ".gitignore").is_file()
    assert not (root / ".compass" / ".gitignore").exists()


def test_init_adds_the_per_machine_lines_only_in_committed_mode(tmp_path):
    root = _project(tmp_path)
    compass = root / ".compass"
    compass.mkdir()
    (compass / ".gitignore").write_text("sessions.json\n.sessions.lock\n", encoding="utf-8")
    init_cmd.ensure_initialised(str(root))
    lines = _lines(compass / ".gitignore")
    assert lines[:2] == ["sessions.json", ".sessions.lock"]
    for line in record_mode.COMPASS_IGNORE_LINES:
        assert line in lines, line
    before = (compass / ".gitignore").read_text(encoding="utf-8")
    init_cmd.ensure_initialised(str(root))
    assert (compass / ".gitignore").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("record_block, git", [
    ({"remote": "https://example.org/r.git", "paths": [".compass/work"]}, True),
    ({"commit": False}, True),
    (None, False),
])
def test_init_leaves_the_compass_ignore_file_alone_when_kept_out(tmp_path, record_block, git):
    """A kept-out project can track `.compass/.gitignore`; it must not change."""
    root = _project(tmp_path, record_block, git=git)
    compass = root / ".compass"
    compass.mkdir()
    (compass / ".gitignore").write_text("sessions.json\n", encoding="utf-8")
    init_cmd.ensure_initialised(str(root))
    assert (compass / ".gitignore").read_text(encoding="utf-8") == "sessions.json\n"


def test_init_with_unreadable_settings_still_writes_the_work_ignore_file(tmp_path):
    root = _project(tmp_path, {"commit": "maybe"})
    init_cmd.ensure_initialised(str(root))
    assert (root / ".compass" / "work" / ".gitignore").is_file()
    assert not (root / ".compass" / ".gitignore").exists()


def test_the_session_table_shares_the_append_helper(tmp_path):
    compass = tmp_path / ".compass"
    compass.mkdir()
    (compass / ".gitignore").write_text("delegations/\n", encoding="utf-8")
    session_lease._ignore(str(compass))
    session_lease._ignore(str(compass))
    assert _lines(compass / ".gitignore") == ["delegations/", "", "sessions.json",
                                               ".sessions.lock"]


def test_git_add_of_an_issue_folder_skips_each_listed_file(tmp_path):
    """In a real repository, `git add` of the folder stages the record and
    none of the per-checkout files."""
    root = _project(tmp_path)
    init_cmd.ensure_initialised(str(root))
    issue = root / ".compass" / "work" / "fix-a"
    kept = ["manifest.yml", "devlog.md", ".spike", "evidence/red-1.json",
            "approval-requests/closed/1.yml"]
    skipped = ["generations/1/resolved.yml", ".render.lock", ".generation.lock",
               ".manifest.lock", ".approval.lock", ".red", ".acceptance",
               "start-state.json", "evidence/.tdd-state.json",
               "approval-requests/pending/2.yml"]
    for rel in kept + skipped:
        (issue / rel).parent.mkdir(parents=True, exist_ok=True)
        (issue / rel).write_text("x\n", encoding="utf-8")
    _git(root, "add", "--", ".compass/work/.gitignore", ".compass/work/fix-a")
    staged = set(_git(root, "diff", "--cached", "--name-only").splitlines())
    assert staged == {".compass/work/.gitignore",
                      *(f".compass/work/fix-a/{rel}" for rel in kept)}


def test_the_init_verb_names_the_ignore_files_it_wrote(tmp_path):
    root = _project(tmp_path)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    first = subprocess.run([sys.executable, str(CLI), "init"], cwd=str(root), env=env,
                           capture_output=True, text=True, timeout=120)
    assert first.returncode == 0, first.stderr
    assert ".compass/work/.gitignore" in first.stdout, first.stdout
    second = subprocess.run([sys.executable, str(CLI), "init"], cwd=str(root), env=env,
                            capture_output=True, text=True, timeout=120)
    assert "nothing changed" in second.stdout, second.stdout
