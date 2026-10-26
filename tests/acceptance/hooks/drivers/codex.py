"""The hook as Codex runs it: the command `adapters/codex/install.py` writes,
`python3 <install>/adapters/codex/runtime.py hook`, run by a shell with the
machine's PATH, with Codex's own event on standard input. Codex edits files
with `apply_patch` and reads them with a shell command; it has no Read tool."""
from __future__ import annotations

from tests.acceptance.hooks.drivers.base import HookDriverBase


class CodexDriver(HookDriverBase):

    def _hook(self, tool, tool_input):
        runtime = self.install / "adapters" / "codex" / "runtime.py"
        return self._run(["/bin/sh", "-c", 'exec python3 "$0" hook', str(runtime)],
                         {"hook_event_name": "PreToolUse", "tool_name": tool,
                          "tool_input": tool_input, "cwd": str(self.project)})

    def _send_edit(self, path):
        relative = path[len(str(self.project)) + 1:]
        patch = (f"*** Begin Patch\n*** Update File: {relative}\n@@\n-x\n+y\n"
                 "*** End Patch")
        return self._hook("apply_patch", {"command": patch})

    def _send_read(self, path):
        return self._hook("exec_command", {"cmd": f"cat {path}"})

    def _send_shell(self, command):
        return self._hook("exec_command", {"cmd": command})
