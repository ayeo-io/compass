"""A root sandbox has a sanctioned, contained way to run the compass condition.

Since D89 a compass run as root is refused unless the plugin copy is on a
read-only mount or `--allow-root` is given. The weekly routine runs only as
root, so it could not measure the compass condition, and once used
`--allow-root` to get through. `--session-user` runs each session as an
unprivileged user instead, and `--allow-root` is refused where `CI` or
`COMPASS_UNATTENDED` says nobody is at the terminal (PRD 14 amendment).

Scenario ids: HR-A to HR-F (issue `harness-root-sanctioned-path`).
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))
sys.path.insert(0, str(ROOT / "cli"))

import harness  # noqa: E402
from compass_pkg import host_launch  # noqa: E402
from test_eval_harness import (  # noqa: E402,F401
    _configure_fake_claude, fake_claude, plugin_source_dir, scenario_dir)


class _User:
    def __init__(self, name, uid, gid, home):
        self.pw_name, self.pw_uid, self.pw_gid, self.pw_dir = name, uid, gid, home


def _lookup(users):
    def lookup(name):
        if name not in users:
            raise KeyError(name)
        return users[name]
    return lookup


SESSION = _User("evaluser", 1500, 1500, "/home/evaluser")
ROOT_USER = _User("root", 0, 0, "/root")
USERS = _lookup({"evaluser": SESSION, "root": ROOT_USER})


def _refusal(**kw):
    base = dict(allow_root=False, euid=0, session_user=None, env={},
                lookup=USERS)
    base.update(kw)
    return harness._root_refusal("compass", None, **base)


# --- HR-B: no sanctioned path is refused, naming the sanctioned paths first --

def test_hr_b_a_root_run_with_no_path_is_refused_naming_the_paths_in_order():
    problem = _refusal()
    assert problem
    assert problem.index("--session-user") < problem.index("--allow-root")
    assert problem.index("read-only mount") < problem.index("--allow-root")
    assert "person" in problem[problem.index("--allow-root"):]


# --- HR-C: --allow-root is a person's decision -------------------------------

@pytest.mark.parametrize("env", [{"CI": "true"}, {"COMPASS_UNATTENDED": "1"}])
def test_hr_c_allow_root_is_refused_when_nobody_is_at_the_terminal(env):
    problem = _refusal(allow_root=True, env=env)
    assert problem and "--allow-root" in problem and "scheduled" in problem


def test_hr_c_allow_root_still_works_for_a_person():
    assert _refusal(allow_root=True, env={}) is None


# --- HR-D and HR-E: a session user must be real, unprivileged and needed ---

def test_hr_d_a_session_user_that_is_root_is_refused():
    problem = _refusal(session_user="root")
    assert problem and "root" in problem


def test_hr_d_an_unknown_session_user_is_refused():
    problem = _refusal(session_user="nobody-here")
    assert problem and "nobody-here" in problem


def test_hr_e_a_session_user_without_root_is_refused():
    problem = _refusal(session_user="evaluser", euid=501)
    assert problem and "root" in problem


def test_hr_a_a_valid_session_user_is_a_sanctioned_path():
    assert _refusal(session_user="evaluser") is None


# --- HR-A: the session runs as the user, with its own home and folder -------

def test_hr_a_the_launcher_starts_the_session_as_the_user(monkeypatch, tmp_path):
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(host_launch.subprocess, "run", fake_run)
    host_launch.launch_claude("claude", "hi", [], tmp_path, {}, user=(1500, 1500))
    assert seen["user"] == 1500 and seen["group"] == 1500


def test_hr_a_the_launcher_without_a_user_is_unchanged(monkeypatch, tmp_path):
    seen = {}

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(host_launch.subprocess, "run", fake_run)
    host_launch.launch_claude("claude", "hi", [], tmp_path, {})
    assert "user" not in seen and "group" not in seen


def test_hr_a_the_session_gets_the_users_home_not_roots(monkeypatch):
    monkeypatch.setenv("HOME", "/root")
    monkeypatch.setenv("TMPDIR", "/root/tmp")
    env = harness._build_child_env("compass", None,
                                   session_user=harness.SessionUser.of(SESSION))
    assert env["HOME"] == "/home/evaluser" and env["USER"] == "evaluser"
    assert "TMPDIR" not in env


def test_hr_a_the_read_only_copies_open_for_reading_only(tmp_path):
    copy = tmp_path / "copy"
    (copy / "bin").mkdir(parents=True)
    (copy / "bin" / "tool").write_text("x")
    os.chmod(copy, 0o700)
    harness._open_for_session_user(copy)
    for path in (copy, copy / "bin"):
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode & stat.S_IROTH and mode & stat.S_IXOTH, oct(mode)
        assert not mode & (stat.S_IWGRP | stat.S_IWOTH), oct(mode)


def test_hr_a_a_root_run_with_a_session_user_records_the_session_uid(
        tmp_path, scenario_dir, fake_claude, plugin_source_dir, monkeypatch):
    # Root and the session user are both played by the user running the
    # tests: the run takes the root path, and every session starts as
    # "evaluser", whose uid is the test user's own, so no real privilege
    # change is needed for the run to complete.
    me = _User("evaluser", os.getuid(), os.getgid(), str(Path.home()))
    monkeypatch.setattr(harness, "_euid", lambda: 0)
    monkeypatch.setattr(harness, "_lookup_user", _lookup({"evaluser": me}))
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("COMPASS_UNATTENDED", raising=False)
    log_path, out_dir = tmp_path / "log.jsonl", tmp_path / "out"
    _configure_fake_claude(fake_claude, log_path, None)
    code = harness.main(["--scenario", str(scenario_dir), "--condition", "compass",
                         "--claude", str(fake_claude), "--out", str(out_dir),
                         "--plugin-source", str(plugin_source_dir),
                         "--session-user", "evaluser"])
    assert code == 0
    record = json.loads(next(out_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["session_uid"] == os.getuid()
    assert record["contained"] is True


# --- HR-F: no session user, no change ----------------------------------------

def test_hr_f_without_a_session_user_the_session_uid_is_the_harness_uid(
        tmp_path, scenario_dir, fake_claude, plugin_source_dir):
    log_path, out_dir = tmp_path / "log.jsonl", tmp_path / "out"
    _configure_fake_claude(fake_claude, log_path, None)
    code = harness.main(["--scenario", str(scenario_dir), "--condition", "bare",
                         "--claude", str(fake_claude), "--out", str(out_dir),
                         "--plugin-source", str(plugin_source_dir)])
    assert code == 0
    record = json.loads(next(out_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert record["session_uid"] == os.geteuid() == record["uid"]
