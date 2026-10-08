"""A project with both `compass.yml` and `.compass/config.yml` never loses a
guard silently (ADR-043 amendment).

`compass.yml` is Compass's file when it has a top-level `schema:` key, or when
it is the only settings file. A recognised `compass.yml` beside an old file
that still holds settings keys is refused as `settings-conflict`. A
`compass.yml` without `schema:` beside an old file is ignored with a warning,
and the old file keeps guarding.

Each hook test runs a copy of the hook made by `compat_hook.install`, in a
project built for the case, so no run reads or writes this repository.

Scenario ids: BS-1 to BS-7, in the acceptance criteria of the issue
`both-settings-files-present`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import compat_hook as ch
from settings_helpers import GLOBS, OTHER_GLOBS, STATE, hook_edit, make_project

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import core, governance, project_settings, record  # noqa: E402
from compass_pkg import tdd  # noqa: E402

# Looked up by name so a reader without these yet fails a test by assertion,
# not by an attribute error.
SettingsConflict = getattr(project_settings, "SettingsConflict", ())
CompassError = project_settings.CompassError

SCHEMA = "schema: 1\nadoption: enforced\n"
# One line: the keys, why they guard nothing, and the fix. It names no command
# that does not exist yet.
CONFLICT = ("settings-conflict: .compass/config.yml sets {keys}, but compass.yml "
            "is read, so those keys guard nothing. Move them into compass.yml "
            "(write mode as adoption) and delete them from .compass/config.yml, "
            "then retry.")


@pytest.fixture
def box():
    """A copy of the framework and a scratch directory for projects."""
    base = Path(tempfile.mkdtemp(prefix="bsk-"))
    framework = ch.install(base / "framework")
    yield framework, base
    shutil.rmtree(base, ignore_errors=True)


@pytest.fixture(autouse=True)
def fresh_warnings():
    """The warning is once per command, so each test starts a new command."""
    getattr(project_settings, "WARNED", set()).clear()


def _project(tmp_path, compass_yml=None, old=None):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    if compass_yml is not None:
        (root / "compass.yml").write_text(compass_yml)
    if old is not None:
        (root / ".compass" / "config.yml").write_text(old)
    return str(root)


# BS-1: a recognised compass.yml and settings left in the old file are refused.

def test_bs1_the_hook_refuses_with_settings_conflict(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA,
                           old="mode: enforced\n" + GLOBS)
    code_exit, code, err = hook_edit(framework, base, project,
                                     "packaging/build.cfg")
    assert (code_exit, code) == (2, "settings-conflict"), err
    text = " ".join(err.split())
    assert "mode, enforcement" in text and ".compass/config.yml" in text
    assert "compass.yml" in text and "compass policy migrate" not in text


def test_bs1_the_hook_and_the_cli_say_the_same_thing(box, tmp_path):
    framework, base = box
    old = "mode: enforced\n" + GLOBS
    project = make_project(base, compass_yml=SCHEMA, old=old)
    _exit, _code, err = hook_edit(framework, base, project, "packaging/a.cfg")
    root = _project(tmp_path, SCHEMA, old)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    body = str(caught.value).removeprefix("settings-conflict: ")
    # The hook's three-line shape puts "Fix:" and the code around the same words.
    hook_text = " ".join(err.split()).replace("Fix: ", "").replace(
        " [settings-conflict]", "")
    assert body in hook_text


def test_bs1_the_hook_refusal_stays_under_sixty_words_with_many_keys(box):
    framework, base = box
    old = "".join(f"{k}: {{}}\n" for k in (
        "mode", "autonomy", "allow_project_commands", "enforcement", "record",
        "project", "prices", "multiagent"))
    project = make_project(base, compass_yml=SCHEMA, old=old)
    _exit, code, err = hook_edit(framework, base, project, "packaging/a.cfg")
    assert code == "settings-conflict", err
    assert "and 3 more" in err
    assert len(err.split()) < 60, (len(err.split()), err)


# The old file is read for more than the keys the catalogue lists: the two
# below, and the three that the multiagent scripts find at any depth.
EXTRA_KEYS = [
    ("governance_drift: strict\n", "governance_drift"),
    ("worktree_root: ../wt\n", "worktree_root"),
    ("max_worktrees: 3\n", "max_worktrees"),
    ("test_command: make test\n", "test_command"),
    ("swarm:\n  worktree_root: ../wt\n", "worktree_root"),
    ("legacy:\n  deep:\n    test_command: make test\n", "test_command"),
]


@pytest.mark.parametrize("old,key", EXTRA_KEYS, ids=[k for _o, k in EXTRA_KEYS])
def test_bs1_a_key_the_old_file_is_read_for_is_a_conflict(tmp_path, old, key):
    root = _project(tmp_path, SCHEMA, "initialised: {by: x}\n" + old)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert isinstance(caught.value, SettingsConflict)
    assert caught.value.keys == [key]


def test_bs1_the_hook_refuses_for_governance_drift(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA,
                           old="governance_drift: strict\n")
    code_exit, code, err = hook_edit(framework, base, project, "packaging/a.cfg")
    assert (code_exit, code) == (2, "settings-conflict"), err
    assert "governance_drift" in err


def test_bs1_keys_under_multiagent_and_project_count_once(tmp_path):
    old = ("multiagent:\n  worktree_root: ../wt\n  max_worktrees: 3\n"
           "project:\n  test_command: make test\n")
    root = _project(tmp_path, SCHEMA, old)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert caught.value.keys == ["multiagent", "project"]


def test_bs1_a_key_listed_twice_is_counted_once(tmp_path, monkeypatch):
    monkeypatch.setattr(project_settings, "SETTINGS_KEYS",
                        project_settings.SETTINGS_KEYS + ("governance_drift",))
    root = _project(tmp_path, SCHEMA, "governance_drift: strict\n")
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert caught.value.keys == ["governance_drift"]


def test_bs1_the_reader_raises_the_one_line_text(tmp_path):
    root = _project(tmp_path, SCHEMA, "mode: enforced\n" + GLOBS)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert isinstance(caught.value, SettingsConflict)
    assert str(caught.value) == CONFLICT.format(keys="mode, enforcement")
    assert caught.value.keys == ["mode", "enforcement"]


# BS-2: a compass.yml with no schema is ignored beside an old file.

def test_bs2_the_old_file_is_read_and_a_warning_is_given_once(tmp_path, capsys):
    root = _project(tmp_path, "adoption: advisory\n" + OTHER_GLOBS,
                    "mode: enforced\n" + GLOBS)
    for _ in range(2):
        data = project_settings.settings(root)
    assert data["enforcement"] == {"code_globs": ["packaging/**"]}
    assert data["adoption"] == "enforced"
    err = capsys.readouterr().err
    assert err.count("warning:") == 1, err
    assert err.strip().endswith(
        "Add `schema:` to compass.yml if it is Compass's file.")
    assert ".compass/config.yml and compass.yml both exist" in err


def test_bs2_the_hook_guards_as_it_did_with_the_old_file_alone(box):
    framework, base = box
    project = make_project(base, compass_yml="adoption: advisory\n" + OTHER_GLOBS,
                           old="mode: enforced\n" + GLOBS)
    assert hook_edit(framework, base, project, "packaging/a.cfg")[:2] == \
        (2, "no-red-on-record")
    allowed = hook_edit(framework, base, project, "other/a.cfg")
    assert allowed[0] == 0, allowed
    assert "warning:" in allowed[2]


# BS-3: a recognised compass.yml and an old file with no settings key.

@pytest.mark.parametrize("old", [
    STATE + "records_signed_since: '2026-09-24'\n",
    "version: 1.0.0\nartifacts:\n  work_dir: .compass/work\n",
    "adoption: advisory\n",
])
def test_bs3_the_old_file_without_settings_keys_is_not_a_conflict(
        tmp_path, capsys, old):
    root = _project(tmp_path, SCHEMA + GLOBS, old)
    assert project_settings.settings(root)["enforcement"] == \
        {"code_globs": ["packaging/**"]}
    assert capsys.readouterr().err == ""


def test_bs3_the_hook_reads_compass_yml(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA + GLOBS, old=STATE)
    assert hook_edit(framework, base, project, "packaging/a.cfg")[:2] == \
        (2, "no-red-on-record")


# BS-4: a lone compass.yml is read, marker or not.

@pytest.mark.parametrize("text", ["adoption: advisory\n" + GLOBS,
                                  "schema: 1\nadoption: advisory\n" + GLOBS])
def test_bs4_a_lone_compass_yml_is_read(tmp_path, capsys, text):
    root = _project(tmp_path, text)
    assert project_settings.settings(root)["enforcement"] == \
        {"code_globs": ["packaging/**"]}
    assert capsys.readouterr().err == ""


def test_bs4_the_hook_reads_a_lone_compass_yml_without_a_marker(box):
    framework, base = box
    project = make_project(base, compass_yml="adoption: enforced\n" + GLOBS)
    assert hook_edit(framework, base, project, "packaging/a.cfg")[:2] == \
        (2, "no-red-on-record")


# BS-5: a file the reader cannot parse is refused, naming that file.

def test_bs5_a_broken_old_file_is_refused_naming_it(tmp_path):
    root = _project(tmp_path, SCHEMA, "enforcement: [unclosed\n")
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert not isinstance(caught.value, SettingsConflict)
    assert ".compass/config.yml" in str(caught.value)
    assert getattr(caught.value, "file", None) == os.path.join(
        ".compass", "config.yml")
    assert "settings-conflict" not in str(caught.value)


def test_bs5_a_broken_compass_yml_is_refused_naming_it(tmp_path):
    root = _project(tmp_path, "schema: 1\nenforcement: [unclosed\n",
                    "mode: enforced\n" + GLOBS)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert "compass.yml" in str(caught.value)
    assert ".compass/config.yml" not in str(caught.value)


def test_bs5_a_compass_yml_that_is_not_a_mapping_is_refused_naming_it(tmp_path):
    root = _project(tmp_path, "- a\n", "mode: enforced\n" + GLOBS)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert not isinstance(caught.value, SettingsConflict)
    assert "compass.yml" in str(caught.value)
    assert ".compass/config.yml" not in str(caught.value)


@pytest.mark.parametrize("compass_yml", [
    "- a\n",                                   # not a mapping
    "enforcement: [unclosed\n",                # cannot be parsed, no schema
])
def test_bs5_the_hook_names_a_compass_yml_it_cannot_use_beside_an_old_file(
        box, compass_yml):
    framework, base = box
    project = make_project(base, compass_yml=compass_yml,
                           old="mode: enforced\n" + GLOBS)
    code_exit, code, err = hook_edit(framework, base, project, "packaging/a.cfg")
    assert (code_exit, code) == (2, "config-invalid"), err
    assert "'compass.yml' could not be read" in err


def test_bs5_an_invalid_value_in_a_compass_yml_without_schema_is_ignored(box):
    """It is not Compass's file, so its values are not judged: the old file
    guards, and the warning says why compass.yml is ignored."""
    framework, base = box
    project = make_project(base, compass_yml="enforcement:\n  code_globs: '*'\n",
                           old="mode: enforced\n" + GLOBS)
    assert hook_edit(framework, base, project, "packaging/a.cfg")[:2] == \
        (2, "no-red-on-record")
    allowed = hook_edit(framework, base, project, "docker-compose.yml")
    assert allowed[0] == 0, allowed
    assert "warning:" in allowed[2]


def test_bs5_the_hook_names_the_broken_file(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA,
                           old="enforcement: [unclosed\n")
    code_exit, code, err = hook_edit(framework, base, project, "packaging/a.cfg")
    assert (code_exit, code) == (2, "config-invalid"), err
    assert "'.compass/config.yml' could not be read" in err


# BS-6: the key list.

def test_bs6_five_keys_in_file_order_then_the_rest(tmp_path):
    old = ("mode: enforced\nautonomy: balanced\nallow_project_commands: false\n"
           "enforcement: {}\nrecord: {}\nproject: {}\nprices: {}\n")
    root = _project(tmp_path, SCHEMA, old)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert isinstance(caught.value, SettingsConflict)
    assert str(caught.value) == CONFLICT.format(
        keys="mode, autonomy, allow_project_commands, enforcement, record "
             "and 2 more")


def test_bs6_the_warning_has_the_same_shape(tmp_path, capsys):
    root = _project(tmp_path, "adoption: enforced\n", "mode: enforced\n")
    project_settings.settings(root)
    assert capsys.readouterr().err.strip() == (
        "warning: .compass/config.yml and compass.yml both exist and "
        "compass.yml has no `schema:`, so the old file is read and compass.yml "
        "is not. Add `schema:` to compass.yml if it is Compass's file.")


# BS-7: a conflict is never read as defaults.

def test_bs7_compass_check_fails_with_the_conflict(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA, old="mode: enforced\n" + GLOBS)
    # The framework copy ships no governance/, which `check` looks for first.
    shutil.copytree(ROOT / "governance", Path(project) / "governance")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", COMPASS_ISSUE=ch.SLUG)
    result = subprocess.run([sys.executable, str(framework / "cli" / "compass"),
                             "check"], cwd=project, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode != 0
    assert "settings-conflict" in result.stdout + result.stderr


def test_bs7_a_missing_preset_is_an_error_naming_the_file_not_a_traceback(box):
    framework, base = box
    project = make_project(base, compass_yml=SCHEMA)
    shutil.copytree(ROOT / "governance", Path(project) / "governance")
    # The framework copy ships no preset, and this issue needs the effective view.
    assert not (framework / "governance" / "presets").exists()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", COMPASS_ISSUE=ch.SLUG)
    result = subprocess.run([sys.executable, str(framework / "cli" / "compass"),
                             "check"], cwd=project, env=env,
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "preset.yml" in result.stderr, result.stderr


@pytest.mark.parametrize("reader", [
    lambda root: core.load_mode(),
    lambda root: tdd._read_config(root),
    lambda root: governance._drift_is_strict(),
    lambda root: record.settings(root),
    lambda root: core.load_autonomy(),
])
def test_bs7_no_reader_turns_a_conflict_into_defaults(tmp_path, monkeypatch,
                                                      reader):
    root = _project(tmp_path, SCHEMA, "mode: advisory\n" + GLOBS)
    monkeypatch.chdir(root)
    with pytest.raises(CompassError) as caught:
        reader(root)
    assert "settings-conflict" in str(caught.value)


def test_bs7_lenient_still_answers_for_a_file_it_cannot_read(tmp_path):
    root = _project(tmp_path, "adoption: [unclosed\n")
    lenient = getattr(project_settings, "lenient", project_settings.settings)
    assert lenient(root) == {}


def _usage_in(tmp_path, old):
    """What `_record_usage` writes into a manifest when the project's old
    settings file is `old`."""
    from compass_pkg import quick_fix_cmd
    root = tmp_path / "qf"
    task = root / ".compass" / "work" / "x"
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text("issue: x\n")
    (root / ".compass" / "config.yml").write_text(old)
    quick_fix_cmd._record_usage(str(task), "2026-10-07T00:00:00+00:00")
    return core.load_yaml(str(task / "manifest.yml")).get("usage")


def test_bs7_an_unparseable_settings_file_still_records_usage_as_unreadable(
        tmp_path):
    usage = _usage_in(tmp_path, "prices: [unclosed\n")
    assert usage["recorded"] is False and usage["reason"] == "unreadable"


def test_bs7_the_usage_record_does_not_hide_a_conflict(tmp_path):
    root = tmp_path / "qf2"
    task = root / ".compass" / "work" / "x"
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text("issue: x\n")
    (root / ".compass" / "config.yml").write_text("prices: {}\n")
    (root / "compass.yml").write_text(SCHEMA)
    from compass_pkg import quick_fix_cmd
    with pytest.raises(CompassError) as caught:
        quick_fix_cmd._record_usage(str(task), "2026-10-07T00:00:00+00:00")
    assert "settings-conflict" in str(caught.value)


def test_bs1_a_script_key_under_two_headings_is_named_once(tmp_path):
    old = ("legacy:\n  worktree_root: ../a\nswarm:\n  worktree_root: ../b\n")
    root = _project(tmp_path, SCHEMA, old)
    with pytest.raises(CompassError) as caught:
        project_settings.settings(root)
    assert caught.value.keys == ["worktree_root"]
