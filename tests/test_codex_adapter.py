"""Codex adapter acceptance: CX-1 to CX-8, shared-source installation."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "adapters/codex/install.py"
RUNTIME = ROOT / "adapters/codex/runtime.py"


def install(project, *args):
    return subprocess.run([sys.executable, str(INSTALL), "--project", str(project), *args],
                          capture_output=True, text=True)


def test_project_install_preserves_user_files(tmp_path):
    project = tmp_path / "project with spaces"
    project.mkdir()
    agents = project / "AGENTS.md"
    agents.write_text("# My instructions\nKeep this text.\n")
    hooks = project / ".codex/hooks.json"
    hooks.parent.mkdir()
    original = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo user"}]}]}}
    hooks.write_text(json.dumps(original))
    first = install(project)
    assert first.returncode == 0, first.stderr
    assert "compass-contract.md" in agents.read_text()
    assert "Keep this text." in agents.read_text()
    skill = project / ".agents/skills/compass"
    assert skill.resolve() == ROOT / "adapters/codex/skills/compass"
    before = agents.read_bytes(), hooks.read_bytes()
    assert install(project).returncode == 0
    assert before == (agents.read_bytes(), hooks.read_bytes())
    assert install(project, "--uninstall").returncode == 0
    assert agents.read_text() == "# My instructions\nKeep this text.\n"
    assert json.loads(hooks.read_text()) == original
    assert not skill.exists()
    assert not (project / ".compass/codex-install.json").exists()


def test_install_collision_is_atomic(tmp_path):
    project = tmp_path / "collision"
    project.mkdir()
    agents = project / "AGENTS.md"
    agents.write_bytes(b"User instructions\r\nKeep CRLF.\r\n")
    skill = project / ".agents/skills/compass"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("User skill")
    before = agents.read_bytes()
    result = install(project)
    assert result.returncode == 2 and "overwrite" in result.stderr
    assert agents.read_bytes() == before
    assert not (project / ".codex").exists()
    (skill / "SKILL.md").unlink()
    skill.rmdir()
    assert install(project).returncode == 0
    assert before in agents.read_bytes()
    agents.write_bytes(agents.read_bytes() + b"\nMore user instructions.\n")
    hooks = project / ".codex/hooks.json"
    data = json.loads(hooks.read_text())
    data["hooks"]["Stop"][0]["hooks"][0]["command"] = "user changed this"
    hooks.write_text(json.dumps(data))
    before = agents.read_bytes(), hooks.read_bytes()
    assert install(project, "--uninstall").returncode == 2
    assert before == (agents.read_bytes(), hooks.read_bytes())
    # Existing empty user files also survive a complete install/uninstall.
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "AGENTS.md").touch()
    assert install(empty).returncode == 0
    assert install(empty, "--uninstall").returncode == 0
    assert (empty / "AGENTS.md").is_file()
    assert (empty / "AGENTS.md").read_bytes() == b""


def test_shared_entry_and_plugin():
    plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
    assert plugin["skills"] == "./adapters/codex/skills/"
    assert plugin["hooks"] == "./adapters/codex/hooks.json"
    assert (ROOT / plugin["skills"][2:] / "compass/SKILL.md").is_file()
    context = subprocess.run([sys.executable, str(RUNTIME), "context"],
                             capture_output=True, text=True)
    assert context.returncode == 0, context.stderr
    paths = json.loads(context.stdout)
    assert Path(paths["root"]) == ROOT
    for stage in ("assess", "define", "refine", "plan", "breakdown", "implement", "verify", "ship"):
        assert Path(paths["commands"][stage]) == ROOT / "commands" / (stage + ".md")
    for role in ("engineer", "product-owner", "designer", "product-marketer", "qa"):
        assert Path(paths["roles"][role]).is_file()
    hook_config = json.loads((ROOT / plugin["hooks"][2:]).read_text())
    assert set(hook_config["hooks"]) == {"SessionStart", "PreToolUse", "PostToolUse", "Stop"}
    assert all("runtime.py" in group["hooks"][0]["command"]
               for groups in hook_config["hooks"].values() for group in groups)


def hook(project, tool, command, event="PreToolUse", **extra):
    payload = {"cwd": str(project), "session_id": "codex-test", "hook_event_name": event,
               "tool_name": tool, "tool_input": {"command": command}, **extra}
    env = dict(os.environ)
    for name in ("COMPASS_ISSUE", "CLAUDE_PROJECT_DIR", "CLAUDE_PLUGIN_DATA"):
        env.pop(name, None)
    return subprocess.run([sys.executable, str(RUNTIME), "hook"], input=json.dumps(payload),
                          cwd=project, env=env, text=True, capture_output=True)


def opted_in(tmp_path):
    project = tmp_path / "project"
    (project / ".compass").mkdir(parents=True)
    (project / ".git").mkdir()
    return project


def patch(body):
    return "*** Begin Patch\n" + body + "\n*** End Patch"


def test_patch_targets_are_guarded(tmp_path):
    project = opted_in(tmp_path)
    for body in ("*** Add File: src/new.py\n+value = 1",
                 "*** Update File: src/existing.py\n@@\n-old\n+new",
                 "*** Delete File: src/old.py",
                 "*** Update File: tests/test_old.py\n*** Move to: src/new.py\n@@\n-old\n+new",
                 "*** Add File: tests/test_safe.py\n+pass\n*** Add File: src/new.py\n+value = 1"):
        result = hook(project, "apply_patch", patch(body))
        assert result.returncode == 2, (body, result.stdout, result.stderr)
        assert "[" in result.stderr or "Compass" in result.stderr or "compass" in result.stderr
    # A refusal is specific to a production target, not all patches.
    result = hook(project, "apply_patch", patch("*** Add File: tests/test_safe.py\n+pass"))
    assert result.returncode == 0, result.stderr


def test_shell_and_spike_use_shared_hook(tmp_path):
    project = opted_in(tmp_path)
    for tool, fields in (("Bash", {"command": "printf x > src/new.py"}),
                         ("exec_command", {"cmd": "printf x > src/new.py"})):
        result = hook(project, tool, "", tool_input=fields)
        assert result.returncode == 2, (tool, result.stderr)
    issue = project / ".compass/work/explore"
    issue.mkdir(parents=True)
    (issue / "manifest.yml").write_text(
        "schema_version: '3.0'\nissue: explore\ncreated: '2026-10-15'\n"
        "delivery_approach: spike\nassessment:\n  goal: exploration\n")
    (issue / ".spike").touch()
    (issue / "delivery-approach.md").write_text("Explore the isolated probe; no production code ships.\n")
    (project / ".compass/current-task").write_text("explore\n")
    result = hook(project, "apply_patch", patch("*** Add File: src/new.py\n+x = 1"))
    assert result.returncode == 0, result.stderr


def test_bootstrap_and_post_action(tmp_path):
    project = opted_in(tmp_path)
    start = hook(project, "", "", event="SessionStart", source="resume")
    assert start.returncode == 0, start.stderr
    context = json.loads(start.stdout)["hookSpecificOutput"]["additionalContext"]
    assert (ROOT / "compass-contract.md").read_text().strip() in context
    assert str(ROOT) in context
    assert "Codex" in context
    issue = project / ".compass/work/active"
    issue.mkdir(parents=True)
    (issue / "devlog.md").write_text("# Active issue\n")
    (project / ".compass/current-task").write_text("active\n")
    (project / "src").mkdir()
    (project / "src/one.py").write_text("one = 1\n")
    (project / "src/two.py").write_text("two = 2\n")
    result = hook(project, "apply_patch", patch(
        "*** Add File: src/one.py\n+one = 1\n*** Add File: src/two.py\n+two = 2"),
        event="PostToolUse")
    assert result.returncode == 0, result.stderr
    log = (issue / "devlog.md").read_text()
    assert "src/one.py" in log and "src/two.py" in log
    stop = hook(project, "", "", event="Stop")
    assert stop.returncode == 0
    assert not stop.stdout or isinstance(json.loads(stop.stdout), dict)


def test_bridge_failures_refuse(tmp_path, monkeypatch, capsys):
    project = opted_in(tmp_path)
    for command in ("", "*** Begin Patch\n*** End Patch", patch("*** Move to: src/a.py"),
                    patch("*** Add File: \n+x"), patch("*** Begin Patch\n*** Add File: x.py\n+x")):
        result = hook(project, "apply_patch", command)
        assert result.returncode == 2 and "refused" in result.stderr
    # A shell payload without a command must not become a silent allow.
    assert hook(project, "Bash", "", tool_input={}).returncode == 2
    import importlib.util
    spec = importlib.util.spec_from_file_location("codex_runtime_test", RUNTIME)
    runtime = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime)
    monkeypatch.setattr(runtime, "shared_hook", lambda *args: subprocess.CompletedProcess([], 1, "", ""))
    assert runtime.run_hook({"cwd": str(project), "hook_event_name": "PreToolUse",
                             "tool_name": "Bash", "tool_input": {"command": "true"}}) == 2
    assert "failed" in capsys.readouterr().err.lower()


def test_codex_contract_column():
    import yaml
    from tests.test_adapter_contract import contract_problems
    data = yaml.safe_load((ROOT / "schemas/adapter-contract.yml").read_text())
    assert "codex" in data["adapters"]
    assert contract_problems(ROOT) == []
    for row in data["capabilities"]:
        cell = row["codex"]
        if cell["status"] == "partial":
            assert cell.get("note"), row["capability"]
    assert data["capabilities"][4]["codex"]["status"] == "partial"


def test_user_append_after_no_final_newline(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("Keep")
    assert install(tmp_path).returncode == 0
    with agents.open("a") as stream:
        stream.write("More\n")
    assert install(tmp_path).returncode == 0  # update must also preserve the separator's owner
    assert install(tmp_path, "--uninstall").returncode == 0
    assert agents.read_text() == "KeepMore\n"
