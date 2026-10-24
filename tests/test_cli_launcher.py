"""The `compass` command works in a person's own terminal after a plugin install.

Claude Code adds the plugin's `bin/` to the PATH of the commands it runs, not
to the person's shell, and the plugin's own folder names its version. So the
session-start hook keeps a launcher at `${CLAUDE_PLUGIN_DATA}/compass`, a path
that does not change between versions, and every message that sends the
person to their terminal names that launcher
(ayeo-io/compass-delivery-record#300).

Scenario `TRC-001` in compass-cli-on-path/acceptance-criteria.md.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import approval_requests, launcher  # noqa: E402


def _plugin_root(tmp_path: Path, version: str) -> Path:
    """A copy of the plugin laid out as Claude Code installs it, under
    `plugins/cache/<marketplace>/<plugin>/<version>`."""
    root = tmp_path / "config" / "plugins" / "cache" / "compass" / "compass" / version
    for rel in ("hooks", "scripts/lib", "bin", "cli"):
        shutil.copytree(ROOT / rel, root / rel)
    shutil.copy(ROOT / "compass-contract.md", root / "compass-contract.md")
    return root


def _data(tmp_path: Path) -> Path:
    data = tmp_path / "config" / "plugins" / "data" / "compass-compass"
    data.mkdir(parents=True, exist_ok=True)
    return data


def _session(plugin_root: Path, project: Path, data: Path):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PLUGIN_DATA", "CLAUDE_PROJECT_DIR")}
    env["CLAUDE_PLUGIN_DATA"] = str(data)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(["bash", str(plugin_root / "hooks" / "session-start.sh")],
                          input="{}", cwd=project, env=env, capture_output=True,
                          text=True, timeout=60)


@pytest.fixture
def project(tmp_path):
    p = tmp_path / "proj"
    (p / ".compass" / "work").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=p, check=True)
    return p


def _clean_env() -> dict:
    return {k: v for k, v in os.environ.items()
            if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA")}


def test_a_session_start_writes_a_compass_launcher_that_runs_the_cli(tmp_path, project):
    """Scenario `TRC-001`: the launcher runs the installed CLI with its
    arguments, from a shell that has none of the plugin's variables."""
    plugin = _plugin_root(tmp_path, "1.0.0")
    data = _data(tmp_path)
    assert _session(plugin, project, data).returncode == 0

    command = data / "compass"
    assert command.is_file() and os.access(command, os.X_OK)
    ran = subprocess.run([str(command), "--version"], capture_output=True, text=True,
                         env=_clean_env(), timeout=60)
    direct = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "--version"],
                            capture_output=True, text=True, timeout=60)
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout.split()[:2] == direct.stdout.split()[:2]
    # --version names the copy it ran, wrapped to the terminal width.
    assert str(plugin.resolve() / "cli") in "".join(ran.stdout.split()), (
        "the launcher ran another copy")


def test_an_upgrade_points_the_launcher_at_the_new_version(tmp_path, project):
    """Scenario `TRC-001`: the path the person typed keeps working after an
    upgrade, because the next session start rewrites the launcher."""
    data = _data(tmp_path)
    old = _plugin_root(tmp_path, "1.0.0")
    _session(old, project, data)
    new = _plugin_root(tmp_path, "1.1.0")
    _session(new, project, data)
    shutil.rmtree(old)

    text = (data / "compass").read_text(encoding="utf-8")
    assert str(new / "bin" / "compass") in text
    assert str(old) not in text
    ran = subprocess.run([str(data / "compass"), "--version"], capture_output=True,
                         text=True, env=_clean_env(), timeout=60)
    assert ran.returncode == 0, ran.stderr


def test_a_launcher_whose_plugin_is_gone_says_so(tmp_path, project):
    """Scenario `TRC-001`: a launcher left behind by an uninstall fails with a
    message, not silently, because a person typed it and waits for a result."""
    plugin = _plugin_root(tmp_path, "1.0.0")
    data = _data(tmp_path)
    _session(plugin, project, data)
    shutil.rmtree(plugin)

    ran = subprocess.run([str(data / "compass"), "--version"], capture_output=True,
                         text=True, env=_clean_env(), timeout=60)
    assert ran.returncode != 0
    assert "Claude Code session" in ran.stderr


def test_a_plugin_install_names_the_launcher_and_how_to_add_it_to_path(tmp_path):
    """Scenario `TRC-001`: the word a person types is the launcher's full
    path, with a line that says which folder to add to PATH."""
    plugin = _plugin_root(tmp_path, "1.0.0")
    data = _data(tmp_path)
    (data / "compass").write_text("#!/bin/sh\n", encoding="utf-8")
    (data / "compass").chmod(0o755)

    word, hint = launcher.terminal_command(plugin, path="/usr/bin:/bin")
    assert word == str(data / "compass")
    assert str(data) in hint and "PATH" in hint


def test_the_plain_word_is_used_when_the_launcher_folder_is_on_path(tmp_path):
    """Scenario `TRC-001`: a person who added the folder types `compass`."""
    plugin = _plugin_root(tmp_path, "1.0.0")
    data = _data(tmp_path)
    (data / "compass").write_text("#!/bin/sh\n", encoding="utf-8")
    (data / "compass").chmod(0o755)

    assert launcher.terminal_command(plugin, path=f"/usr/bin:{data}") == ("compass", "")


def test_an_install_from_source_keeps_the_plain_word(tmp_path):
    """Scenario `TRC-001`: a clone has no plugin data folder, so there is no
    launcher to name; the quickstart says how to put its `bin/` on PATH."""
    assert launcher.terminal_command(ROOT, path="/usr/bin") == ("compass", "")


def test_the_terminal_approval_command_names_the_launcher(monkeypatch):
    """Scenario `TRC-001`: the command printed for the person's terminal
    starts with the word they can run."""
    monkeypatch.setattr(launcher, "terminal_command",
                        lambda *a, **k: ("/x/data/compass", "add /x/data to PATH"))
    request = {"form": "guardrail", "value": "G5", "issue": "demo", "scope": ""}
    command = approval_requests._terminal_command(request)
    assert command.startswith("/x/data/compass evidence approve ")


@pytest.mark.parametrize("words", [
    ["evidence", "approve", "--check", "dod-suite-green", "--approver", "a", "--role", "qa"],
    ["issue", "decision", "set", "Q1", "--status", "reopened", "--reason", "r"],
])
def test_a_refusal_that_sends_the_person_to_a_terminal_names_the_command(words):
    """Scenario `TRC-001`: an agent that runs a person-only command is told
    what the person types, in words the agent can pass on."""
    word, _ = launcher.terminal_command()
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *words],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       timeout=60)
    assert r.returncode != 0
    assert f"`{word} {words[0]} {words[1]}" in r.stderr, r.stderr


def test_the_quickstart_limits_the_path_entry_to_claude_code():
    """Scenario `TRC-001`: the quickstart said the plugin puts `compass` on
    your PATH, with no limit, and named no way to run it in a terminal."""
    text = " ".join((ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8").split())
    assert "puts the `compass` CLI on your PATH." not in text
    assert "inside Claude Code" in text
    assert "plugins/data/compass-compass" in text
