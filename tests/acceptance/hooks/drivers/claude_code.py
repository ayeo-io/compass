"""The hook as Claude Code runs it: `hooks/pre-tool.sh` with the tool call's
JSON on standard input, read back as the exit code and standard error."""
from __future__ import annotations

from tests.acceptance.hooks.drivers.base import HookDriverBase


class ClaudeCodeDriver(HookDriverBase):

    def _hook(self, tool, tool_input):
        return self._run(["bash", str(self.install / "hooks" / "pre-tool.sh")],
                         {"tool_name": tool, "tool_input": tool_input,
                          "cwd": str(self.project)})

    def _send_edit(self, path):
        return self._hook("Edit", {"file_path": path})

    def _send_read(self, path):
        return self._hook("Read", {"file_path": path})

    def _send_shell(self, command):
        return self._hook("Bash", {"command": command})
