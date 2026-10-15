"""CX-12: native metadata smoke, without a model turn or real user configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self, process):
        self.process = process
        self.buffer = b""

    def call(self, number, method, params):
        self.process.stdin.write(json.dumps(dict(id=number, method=method, params=params)).encode() + b"\n")
        self.process.stdin.flush()
        selector = selectors.DefaultSelector()
        selector.register(self.process.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + 20
        try:
            while time.monotonic() < deadline:
                if b"\n" not in self.buffer:
                    if not selector.select(timeout=1):
                        continue
                    chunk = os.read(self.process.stdout.fileno(), 65536)
                    assert chunk, "Codex app server exited before replying"
                    self.buffer += chunk
                while b"\n" in self.buffer:
                    line, self.buffer = self.buffer.split(b"\n", 1)
                    message = json.loads(line)
                    if message.get("id") == number:
                        assert "error" not in message, message
                        return message["result"]
            pytest.fail(f"Codex {method} did not reply within 20 seconds")
        finally:
            selector.close()


@pytest.mark.skipif(shutil.which("codex") is None, reason="native Codex CLI is not installed")
def test_native_install_matches_usage_and_preserves_hook_trust(tmp_path):
    project, home = tmp_path / "project", tmp_path / "codex-home"
    project.mkdir()
    home.mkdir()
    result = subprocess.run([sys.executable, str(ROOT / "adapters/codex/install.py"),
                             "--project", str(project)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    # Only this test's project is trusted. Hooks must remain separately untrusted.
    (home / "config.toml").write_text(
        f"[projects.{json.dumps(str(project.resolve()))}]\ntrust_level = \"trusted\"\n")
    env = dict(os.environ, CODEX_HOME=str(home))
    with (tmp_path / "server.log").open("wb") as log:
        process = subprocess.Popen(["codex", "--no-daemon", "app-server"], cwd=project,
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
        try:
            client = Client(process)
            client.call(1, "initialize", {"clientInfo": {"name": "compass-smoke", "version": "1"},
                                          "capabilities": {"experimentalApi": True}})
            process.stdin.write(b'{"method":"initialized"}\n')
            process.stdin.flush()
            result = client.call(2, "skills/list", {"cwds": [str(project)], "forceReload": True})
            skills = [s for entry in result["data"] for s in entry["skills"]
                      if Path(s["path"]).resolve() == ROOT / "adapters/codex/skills/compass/SKILL.md"]
            assert len(skills) == 1 and skills[0]["enabled"]
            guide = (ROOT / "docs/codex.md").read_text()
            advertised = re.search(r"invoke `\$([\w:-]+) assess", guide).group(1)
            assert advertised == skills[0]["name"], (advertised, skills[0]["name"])
            result = client.call(3, "hooks/list", {"cwds": [str(project)]})
            hooks = [h for entry in result["data"] for h in entry["hooks"]]
            assert {h["eventName"] for h in hooks} == {"preToolUse", "postToolUse", "sessionStart", "stop"}
            assert all(h["trustStatus"] == "untrusted" and not h["isManaged"] for h in hooks)
            assert all("adapters/codex/runtime.py" in h["command"] for h in hooks)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
