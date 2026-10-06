"""The pre-tool hook and the two multiagent scripts read project settings
through the one settings reader, so `compass.yml` is honoured and a project
with only `.compass/config.yml` is decided as before (ADR-043).

Each test runs a copy of the hook or the scripts made by `compat_hook.install`,
in a project built for the case, so no run reads or writes this repository.

Scenario ids: SH-1 to SH-3, SH-9 and SH-10, in the acceptance criteria of the
issue `settings-reader-hook`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import compat_hook as ch
from settings_helpers import (GLOBS, OTHER_GLOBS, SETTINGS, STATE, hook_edit,
                              make_project, make_repo, run_script)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import project_settings  # noqa: E402


@pytest.fixture
def box():
    """A copy of the framework and a scratch directory for projects."""
    base = Path(tempfile.mkdtemp(prefix="shk-"))
    framework = ch.install(base / "framework")
    yield framework, base
    shutil.rmtree(base, ignore_errors=True)


# SH-1: enforcement.code_globs comes from compass.yml, else the old file.

@pytest.mark.parametrize("where", ["compass", "old"])
def test_sh1_a_glob_guards_its_path_from_either_file(box, where):
    framework, base = box
    kwargs = {"compass_yml": "adoption: enforced\n" + GLOBS} if where == \
        "compass" else {"old": "mode: enforced\n" + GLOBS}
    project = make_project(base, **kwargs)
    assert hook_edit(framework, base, project, "packaging/build.cfg")[:2] == \
        (2, "no-red-on-record")
    assert hook_edit(framework, base, project, "docker-compose.yml")[0] == 0


def test_sh1_compass_yml_wins_when_both_files_exist(box):
    framework, base = box
    project = make_project(base, compass_yml=GLOBS, old=OTHER_GLOBS)
    assert hook_edit(framework, base, project, "packaging/build.cfg")[0] == 2
    assert hook_edit(framework, base, project, "other/build.cfg")[0] == 0


def test_sh1_no_settings_file_leaves_an_unlisted_path_alone(box):
    framework, base = box
    project = make_project(base)
    assert hook_edit(framework, base, project, "packaging/build.cfg")[0] == 0


def test_sh1_the_matched_rule_names_the_file_it_read(box):
    framework, base = box
    for kwargs, name in (({"compass_yml": GLOBS}, "in compass.yml"),
                         ({"old": GLOBS}, "in .compass/config.yml")):
        project = make_project(base, **kwargs)
        _exit, _code, err = hook_edit(framework, base, project,
                                      "packaging/a.cfg")
        assert name in " ".join(err.split()), err


@pytest.mark.parametrize("body", [
    "enforcement: [unclosed\n",
    "enforcement:\n  code_globs: '*'\n",
    "enforcement:\n  code_globs: ['a/**']\nenforcement: {}\n",
])
def test_sh1_a_compass_yml_the_hook_cannot_read_blocks_and_names_it(box, body):
    framework, base = box
    project = make_project(base, compass_yml=body, old=GLOBS)
    exit_code, code, err = hook_edit(framework, base, project,
                                     "docker-compose.yml")
    assert (exit_code, code) == (2, "config-invalid"), err
    text = " ".join(err.split())
    assert "compass.yml" in text and ".compass/config.yml" not in text, text


def test_sh1_an_old_file_the_hook_cannot_read_still_names_the_old_file(box):
    framework, base = box
    project = make_project(base, old="enforcement: [unclosed\n")
    exit_code, code, err = hook_edit(framework, base, project,
                                     "docker-compose.yml")
    assert (exit_code, code) == (2, "config-invalid"), err
    assert "fix .compass/config.yml and retry" in " ".join(err.split())


@pytest.mark.parametrize("body", ["enforcement: [unclosed\n",
                                  "enforcement:\n  code_globs: '*'\n"])
def test_sh1_the_refusal_says_the_file_could_not_be_read_once(box, body):
    """The `Why` line names the file once and gives the reader's reason, not a
    second sentence that names the file again."""
    framework, base = box
    project = make_project(base, compass_yml=body)
    _e, _c, err = hook_edit(framework, base, project, "docker-compose.yml")
    text = " ".join(err.split())
    assert text.count("could not be read") == 1, text
    assert "could not read enforcement.code_globs" not in text, text


# SH-2: the first refusal says who initialised the project.

def _refusal(box, **kwargs):
    framework, base = box
    project = make_project(base, issue=False, work=False, **kwargs)
    return hook_edit(framework, base, project, "src/app.py")


@pytest.mark.parametrize("where", ["state", "old"])
def test_sh2_the_refusal_says_who_initialised_the_project(box, where):
    kwargs = {"state": STATE} if where == "state" else {"old": STATE}
    exit_code, _code, err = _refusal(box, **kwargs)
    assert exit_code == 2
    assert "initialised by compass init on 2026-09-05" in err, err


def test_sh2_the_state_file_wins_over_the_old_file(box):
    _e, _c, err = _refusal(box, state=STATE,
                           old=STATE.replace("compass init", "an old init"))
    assert "initialised by compass init" in err, err


@pytest.mark.parametrize("body", [None, "initialised: [broken\n",
                                  "initialised: just-text\n", "other: 1\n"])
def test_sh2_a_missing_or_broken_record_adds_nothing(box, body):
    exit_code, code, err = _refusal(box, state=body)
    assert (exit_code, code) == (2, "not-initialised"), err
    assert "initialised by" not in err, err


# SH-3: the scripts read the worktree root, cap and test command.

def _output(result):
    return result.stdout + result.stderr


@pytest.mark.parametrize("where", ["compass", "old"])
def test_sh3_multiagent_reads_root_and_cap_from_either_file(box, where):
    framework, base = box
    repo = make_repo(base, **{where: SETTINGS % (where, 3, where)})
    text = _output(run_script(framework, repo, "multiagent.sh", "--dry-run"))
    assert f"wt-{where}" in text and "config max 3" in text, text


def test_sh3_an_older_heading_and_top_level_keys_still_read_from_the_old_file(box):
    framework, base = box
    for body, root in (
            ("swarm:\n  worktree_root: ../wt-heading\n  max_worktrees: 2\n",
             "wt-heading"),
            ("worktree_root: ../wt-flat\nmax_worktrees: 2\n", "wt-flat")):
        repo = make_repo(base, old="mode: enforced\n" + body)
        text = _output(run_script(framework, repo, "multiagent.sh",
                                  "--dry-run"))
        assert "config max 2" in text, text
        assert root in text, text


def test_sh3_compass_yml_wins_when_both_files_exist(box):
    framework, base = box
    repo = make_repo(base, compass=SETTINGS % ("new", 3, "new"),
                     old=SETTINGS % ("old", 5, "old"))
    text = _output(run_script(framework, repo, "multiagent.sh", "--dry-run"))
    assert "wt-new" in text and "config max 3" in text, text
    assert "wt-old" not in text
    text = _output(run_script(framework, repo, "integrate.sh"))
    assert "test command:  run-new" in text, text


def test_sh3_a_project_with_no_settings_uses_the_defaults(box):
    framework, base = box
    repo = make_repo(base)
    text = _output(run_script(framework, repo, "multiagent.sh", "--dry-run"))
    assert ".compass-worktrees" in text and "config max 6" in text, text


@pytest.mark.parametrize("where", ["compass", "old"])
def test_sh3_integrate_reads_the_test_command_from_either_file(box, where):
    framework, base = box
    repo = make_repo(base, **{where: SETTINGS % (where, 3, where)})
    out = run_script(framework, repo, "integrate.sh")
    assert f"test command:  run-{where}" in _output(out), out.stdout


def test_sh3_scalar_stops_on_a_recursive_alias(tmp_path):
    """A settings file can anchor a mapping inside itself. The lookup must end
    and report the key as missing, not recurse until Python gives up."""
    (tmp_path / ".compass").mkdir()
    (tmp_path / ".compass" / "config.yml").write_text("a: &x {b: *x}\n")
    try:
        value = project_settings.scalar(str(tmp_path), "worktree_root")
    except RecursionError:
        value = "recursed"
    assert value == ""


# SH-9: compass.yml is read at the documented paths only; an unreadable file
# stops the scripts.

DECOYS = ("checks:\n  x:\n    params:\n      test_command: wrong\n"
          "      max_worktrees: 99\n      worktree_root: ../wrong\n"
          "max_worktrees: 98\nworktree_root: ../wrong\ntest_command: wrong\n")
DOCUMENTED = ("project:\n  test_command: right\n"
              "multiagent:\n  worktree_root: ../wt-right\n  max_worktrees: 2\n")


def test_sh9_compass_yml_is_read_at_the_documented_paths_only(tmp_path):
    (tmp_path / "compass.yml").write_text(DECOYS + DOCUMENTED)
    root = str(tmp_path)
    assert project_settings.scalar(root, "test_command") == "right"
    assert project_settings.scalar(root, "worktree_root") == "../wt-right"
    assert project_settings.scalar(root, "max_worktrees") == "2"
    assert project_settings.scalar(root, "name") == ""


def test_sh9_a_key_outside_its_documented_path_is_not_read_from_compass_yml(
        tmp_path):
    (tmp_path / "compass.yml").write_text(DECOYS)
    for key in ("test_command", "worktree_root", "max_worktrees"):
        assert project_settings.scalar(str(tmp_path), key) == "", key


def test_sh9_the_scripts_ignore_a_decoy_key_in_compass_yml(box):
    framework, base = box
    repo = make_repo(base, compass=DECOYS + DOCUMENTED)
    text = _output(run_script(framework, repo, "multiagent.sh", "--dry-run"))
    assert "config max 2" in text and "wt-right" in text, text
    assert "wrong" not in text, text
    text = _output(run_script(framework, repo, "integrate.sh"))
    assert "test command:  right" in text, text


@pytest.mark.parametrize("where", ["compass", "old"])
@pytest.mark.parametrize("script,args", [("multiagent.sh", ("--dry-run",)),
                                         ("integrate.sh", ())])
def test_sh9_a_settings_file_that_cannot_be_read_stops_the_script(
        box, where, script, args):
    framework, base = box
    repo = make_repo(base, **{where: "multiagent: [unclosed\n"})
    out = run_script(framework, repo, script, *args)
    name = "compass.yml" if where == "compass" else "config.yml"
    assert out.returncode == 1, _output(out)
    assert name in out.stderr, out.stderr
    assert "config max" not in out.stdout and "test command" not in out.stdout


# SH-10: the hook starts Python for the globs only when a settings file exists.

FAKE = """#!/usr/bin/env bash
# Fails only for the reader whose script holds $FAKE_FAIL_ON.
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  if [ -n "${FAKE_FAIL_ON:-}" ] && printf '%s' "$body" | grep -qF -- "$FAKE_FAIL_ON"; then
    echo "fake python3: failing on purpose" >&2
    exit 1
  fi
  printf '%s\\n' "$body" | REALPY "$@"
  exit $?
fi
exec REALPY "$@"
"""


def _hook_with_failing_globs_reader(framework, base, project):
    fake_bin = base / "fakebin"
    fake_bin.mkdir(exist_ok=True)
    fake = fake_bin / "python3"
    fake.write_text(FAKE.replace("REALPY", sys.executable))
    fake.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project),
           "PATH": f"{fake_bin}:{os.environ['PATH']}",
           "FAKE_FAIL_ON": "fnmatch.fnmatch(path, g)"}
    event = json.dumps({"tool_name": "Edit", "tool_input": {
        "file_path": str(project / "docker-compose.yml")}})
    return subprocess.run(["bash", str(framework / "hooks" / "pre-tool.sh")],
                          input=event, capture_output=True, text=True,
                          timeout=120, env=env).returncode


def test_sh10_a_project_with_no_settings_file_starts_no_python_for_the_globs(box):
    framework, base = box
    assert _hook_with_failing_globs_reader(
        framework, base, make_project(base)) == 0


@pytest.mark.parametrize("kwargs", [{"compass_yml": GLOBS}, {"old": GLOBS}])
def test_sh10_a_project_with_a_settings_file_does_start_it(box, kwargs):
    """The control: the same fake reader refuses once a settings file exists,
    so the allow above is because Python did not start."""
    framework, base = box
    assert _hook_with_failing_globs_reader(
        framework, base, make_project(base, **kwargs)) == 2
