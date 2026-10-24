"""The word a person types to run this CLI in their own terminal.

Claude Code adds the plugin's `bin/` to the PATH of the commands it runs, not
to the person's shell, and the plugin's folder names its version. So the
session-start hook keeps a launcher at `<config>/plugins/data/<plugin>-<market
place>/compass`, which does not move between versions. The Bash tool does not
pass `CLAUDE_PLUGIN_DATA` on, so the folder is worked out from where this CLI
is installed: `<config>/plugins/cache/<marketplace>/<plugin>/<version>/`.
"""
from __future__ import annotations

import os
import shlex
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


def terminal_command(root: Path | None = None,
                     path: str | None = None) -> tuple[str, str]:
    """The command word, and a line saying which folder to add to PATH.

    The word is the launcher's full path for a plugin install whose launcher
    exists and whose folder is not on PATH. Otherwise it is `compass`, and
    the line is empty: an install from source has no plugin data folder, and
    `docs/quickstart.md` says how to put its `bin/` on PATH.
    """
    parts = (root or _ROOT).resolve().parts
    if len(parts) < 6 or parts[-5:-3] != ("plugins", "cache"):
        return "compass", ""
    marketplace, plugin = parts[-3], parts[-2]
    data = Path(*parts[:-4]) / "data" / f"{plugin}-{marketplace}"
    command = data / "compass"
    if not (command.is_file() and os.access(command, os.X_OK)):
        return "compass", ""
    entries = (os.environ.get("PATH", "") if path is None else path).split(os.pathsep)
    if str(data) in entries:
        return "compass", ""
    return (shlex.quote(str(command)),
            f"To type `compass` instead, add {data} to your PATH.")
