"""The status line survives a plugin upgrade, and init offers to set it up:
GitHub issue #247.

The session-start hook keeps a launcher at `${CLAUDE_PLUGIN_DATA}/
compass-statusline`, a path that does not change between versions, pointing
at the current plugin root. `scripts/statusline-setup.py` shows the change to
a settings file and writes it only with `--apply`.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SETUP = ROOT / "scripts" / "statusline-setup.py"


def _plugin_root(tmp_path: Path, name: str) -> Path:
    """A copy of the parts of the plugin the session-start hook uses."""
    root = tmp_path / name
    for rel in ("hooks", "scripts/lib", "bin"):
        shutil.copytree(ROOT / rel, root / rel)
    shutil.copy(ROOT / "compass-contract.md", root / "compass-contract.md")
    return root


def _session(plugin_root: Path, project: Path, data: Path | None):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR")}
    if data is not None:
        env["CLAUDE_PLUGIN_DATA"] = str(data)
    return subprocess.run(["bash", str(plugin_root / "hooks" / "session-start.sh")],
                          input="{}", cwd=project, env=env, capture_output=True,
                          text=True, timeout=60)


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    (p / ".compass" / "work").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True)
    return p


def test_a_session_start_writes_the_launcher(tmp_path, project):
    """SL-A."""
    plugin = _plugin_root(tmp_path, "v1")
    data = tmp_path / "data"
    data.mkdir()
    assert _session(plugin, project, data).returncode == 0
    launcher = data / "compass-statusline"
    assert launcher.is_file() and os.access(launcher, os.X_OK)
    assert str(plugin / "bin" / "compass-statusline") in launcher.read_text()


def test_the_launcher_passes_stdin_to_the_target(tmp_path, project):
    """SL-A: a stand-in target echoes what it reads."""
    plugin = _plugin_root(tmp_path, "v1")
    target = plugin / "bin" / "compass-statusline"
    target.write_text("#!/bin/sh\ncat\n")
    target.chmod(0o755)
    data = tmp_path / "data"
    data.mkdir()
    _session(plugin, project, data)
    r = subprocess.run([str(data / "compass-statusline")], input="hello",
                       capture_output=True, text=True)
    assert r.stdout == "hello"


def test_an_upgrade_rewrites_the_launcher_and_a_repeat_does_not(tmp_path, project):
    """SL-B."""
    data = tmp_path / "data"
    data.mkdir()
    v1, v2 = _plugin_root(tmp_path, "v1"), _plugin_root(tmp_path, "v2")
    launcher = data / "compass-statusline"
    _session(v1, project, data)
    first = launcher.stat().st_mtime_ns
    os.utime(launcher, ns=(first - 10**9, first - 10**9))
    before = launcher.stat().st_mtime_ns
    _session(v1, project, data)
    assert launcher.stat().st_mtime_ns == before, "same root: left unchanged"
    _session(v2, project, data)
    assert str(v2 / "bin") in launcher.read_text()
    assert str(v1 / "bin") not in launcher.read_text()


@pytest.mark.parametrize("make_data", ["unset", "read-only"])
def test_no_usable_data_folder_changes_nothing(tmp_path, project, make_data):
    """SL-C."""
    plugin = _plugin_root(tmp_path, "v1")
    good = tmp_path / "good-data"
    good.mkdir()
    # The baseline is a run that writes the launcher, so an unset or unusable
    # folder must give exactly the output a working one does.
    baseline = _session(plugin, project, good)
    assert "Compass operating contract" in baseline.stdout
    data = None
    if make_data == "read-only":
        data = tmp_path / "data"
        data.mkdir()
        data.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        r = _session(plugin, project, data)
    finally:
        if data is not None:
            data.chmod(0o755)
    assert (r.returncode, r.stdout, r.stderr) == (baseline.returncode, baseline.stdout,
                                                   baseline.stderr)


def test_the_model_sees_the_same_output(tmp_path, project):
    """SL-C: writing the launcher adds nothing to the session's context."""
    plugin = _plugin_root(tmp_path, "v1")
    data = tmp_path / "data"
    data.mkdir()
    assert _session(plugin, project, data).stdout == _session(plugin, project, None).stdout


def test_a_missing_target_prints_nothing(tmp_path, project):
    """SL-D."""
    plugin = _plugin_root(tmp_path, "v1")
    data = tmp_path / "data"
    data.mkdir()
    _session(plugin, project, data)
    shutil.rmtree(plugin)
    r = subprocess.run([str(data / "compass-statusline")], input="{}",
                       capture_output=True, text=True)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


# --- the setup helper ---------------------------------------------------------

def _setup(settings: Path, launcher: Path, *extra):
    return subprocess.run([sys.executable, str(SETUP), "--settings", str(settings),
                           "--launcher", str(launcher), *extra],
                          capture_output=True, text=True)


def test_no_entry_shows_the_diff_then_writes_on_apply(tmp_path):
    """SL-E."""
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"theme": "dark"}))
    launcher = tmp_path / "compass-statusline"
    r = _setup(settings, launcher)
    assert r.returncode == 0 and str(launcher) in r.stdout and "+" in r.stdout
    assert json.loads(settings.read_text()) == {"theme": "dark"}, "no write without --apply"
    r = _setup(settings, launcher, "--apply")
    assert r.returncode == 0
    data = json.loads(settings.read_text())
    assert data["statusLine"] == {"type": "command", "command": str(launcher)}
    assert data["theme"] == "dark"


def test_a_missing_settings_file_is_created_only_on_apply(tmp_path):
    """SL-E."""
    settings = tmp_path / "new" / "settings.json"
    launcher = tmp_path / "compass-statusline"
    assert _setup(settings, launcher).returncode == 0
    assert not settings.exists()
    assert _setup(settings, launcher, "--apply").returncode == 0
    assert json.loads(settings.read_text())["statusLine"]["command"] == str(launcher)


@pytest.mark.parametrize("apply", [False, True])
def test_another_status_line_is_left_byte_identical(tmp_path, apply):
    """SL-F."""
    settings = tmp_path / "settings.json"
    raw = '{\n  "statusLine": {"type": "command", "command": "~/bin/my-line"}\n}\n'
    settings.write_text(raw)
    r = _setup(settings, tmp_path / "compass-statusline", *(["--apply"] if apply else []))
    assert r.returncode == 0
    assert settings.read_text() == raw
    assert "combine" in r.stdout


def test_a_versioned_compass_path_is_replaced_only_on_apply(tmp_path):
    """SL-G."""
    settings = tmp_path / "settings.json"
    old = "/home/u/.claude/plugins/cache/compass/compass/5.1.0/bin/compass-statusline"
    settings.write_text(json.dumps({"statusLine": {"type": "command", "command": old}}))
    launcher = tmp_path / "compass-statusline"
    r = _setup(settings, launcher)
    assert old in r.stdout and str(launcher) in r.stdout
    assert json.loads(settings.read_text())["statusLine"]["command"] == old
    _setup(settings, launcher, "--apply")
    assert json.loads(settings.read_text())["statusLine"]["command"] == str(launcher)


def test_the_launcher_already_set_is_left_alone(tmp_path):
    settings = tmp_path / "settings.json"
    launcher = tmp_path / "compass-statusline"
    raw = json.dumps({"statusLine": {"type": "command", "command": str(launcher)}})
    settings.write_text(raw)
    r = _setup(settings, launcher, "--apply")
    assert r.returncode == 0 and "already" in r.stdout
    assert settings.read_text() == raw


# --- the documents ------------------------------------------------------------

def test_init_and_quickstart_name_the_launcher():
    """SL-H."""
    init = (ROOT / "commands" / "init.md").read_text(encoding="utf-8")
    assert "scripts/statusline-setup.py" in init
    assert "even when step 1 stops" in init
    assert "--apply" in init and "yes" in init
    quick = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
    assert "compass-statusline" in quick and "plugins/data" in quick
    assert "after each upgrade" not in quick and "after every upgrade" not in quick


# --- review round 1 ------------------------------------------------------------

def _launcher_for(data: Path, root: Path) -> Path:
    data.mkdir(parents=True)
    launcher = data / "compass-statusline"
    launcher.write_text(f"#!/usr/bin/env bash\ntarget={root}/bin/compass-statusline\n"
                        "[ -x \"$target\" ] || exit 0\nexec \"$target\"\n")
    launcher.chmod(0o755)
    return launcher


def test_the_helper_picks_the_launcher_for_its_own_root(tmp_path):
    """Not the newest file: the hook rewrites a launcher only when it changes."""
    home = tmp_path / "home"
    # The right launcher sorts second, so taking the first or the newest fails.
    mine = _launcher_for(home / ".claude/plugins/data/compass-inline", ROOT)
    other = _launcher_for(home / ".claude/plugins/data/compass-compass", tmp_path / "elsewhere")
    os.utime(mine, (1, 1))
    settings = tmp_path / "settings.json"
    env = dict(os.environ, HOME=str(home))
    r = subprocess.run([sys.executable, str(SETUP), "--settings", str(settings)],
                       env=env, capture_output=True, text=True)
    assert "compass-inline" in r.stdout and "compass-compass" not in r.stdout, r.stdout


def test_a_plugin_root_reached_through_a_symlink_is_found(tmp_path):
    real = tmp_path / "realplug"
    (real / "scripts").mkdir(parents=True)
    shutil.copy(SETUP, real / "scripts" / "statusline-setup.py")
    link = tmp_path / "linkplug"
    link.symlink_to(real)
    home = tmp_path / "home"
    _launcher_for(home / ".claude/plugins/data/compass-compass", link)
    env = dict(os.environ, HOME=str(home))
    r = subprocess.run([sys.executable, str(link / "scripts" / "statusline-setup.py"),
                        "--settings", str(tmp_path / "settings.json")],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0 and "compass-compass" in r.stdout, r.stdout


def test_the_documented_tilde_entry_counts_as_the_launcher(tmp_path):
    home = tmp_path / "home"
    launcher = _launcher_for(home / ".claude/plugins/data/compass-compass", ROOT)
    settings = tmp_path / "settings.json"
    raw = json.dumps({"statusLine": {"type": "command",
                                     "command": "~/.claude/plugins/data/compass-compass/compass-statusline"}})
    settings.write_text(raw)
    env = dict(os.environ, HOME=str(home))
    r = subprocess.run([sys.executable, str(SETUP), "--settings", str(settings),
                        "--launcher", str(launcher), "--apply"], env=env,
                       capture_output=True, text=True)
    assert "already runs the Compass" in r.stdout, r.stdout
    assert "not Compass" not in r.stdout and settings.read_text() == raw


def test_apply_keeps_a_symlink_and_the_file_mode(tmp_path):
    real = tmp_path / "real-settings.json"
    real.write_text(json.dumps({"env": {"TOKEN": "x"}}))
    real.chmod(0o600)
    link = tmp_path / "settings.json"
    link.symlink_to(real)
    _setup(link, tmp_path / "compass-statusline", "--apply")
    assert link.is_symlink()
    assert json.loads(real.read_text())["statusLine"]["type"] == "command"
    assert stat.S_IMODE(real.stat().st_mode) == 0o600


def test_replacing_a_versioned_entry_keeps_its_other_keys(tmp_path):
    settings = tmp_path / "settings.json"
    old = "/h/.claude/plugins/cache/compass/compass/5.1.0/bin/compass-statusline"
    settings.write_text(json.dumps({"statusLine": {"type": "command", "command": old,
                                                   "padding": 2}}))
    _setup(settings, tmp_path / "compass-statusline", "--apply")
    assert json.loads(settings.read_text())["statusLine"]["padding"] == 2


def test_invalid_json_is_refused_without_a_traceback(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{ // a comment\n}")
    r = _setup(settings, tmp_path / "compass-statusline", "--apply")
    assert r.returncode != 0 and "Traceback" not in r.stderr
    assert settings.read_text() == "{ // a comment\n}"


def test_init_names_the_helper_by_the_plugin_root():
    init = (ROOT / "commands" / "init.md").read_text(encoding="utf-8")
    assert "${CLAUDE_PLUGIN_ROOT}/scripts/statusline-setup.py" in init
    assert "<compass>" not in init


def test_the_quickstart_drops_the_old_upgrade_advice():
    quick = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
    assert "when you upgrade" not in quick
