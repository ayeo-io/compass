"""The word a person types to run this CLI in their own terminal.

Claude Code adds the plugin's `bin/` to the PATH of the commands it runs, not
to the person's shell, and the plugin's folder names its version. So the
session-start hook keeps a launcher at `<config>/plugins/data/
<plugin>-<marketplace>/compass`, which does not move between versions. The Bash tool does not
pass `CLAUDE_PLUGIN_DATA` on, so the folder is worked out from where this CLI
is installed: `<config>/plugins/cache/<marketplace>/<plugin>/<version>/`.
"""
from __future__ import annotations

import os
import re
import shlex
import sys
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


# A person-only command written as plain `compass`, which a person's own
# terminal does not have for a plugin install. Not when `compass` is the end
# of a path, so a launcher path already in the text is left alone. Not a
# verb label (`compass issue decision set: ...`) and not a delegated approval,
# which an agent runs inside Claude Code, where `compass` resolves.
_PERSON_ONLY = re.compile(
    r"(?<![\w/.'-])compass (?=(?:evidence approve|issue decision set)\b(?!:)"
    r"(?![^\n`]*--delegated))")


def name_commands(text: str, word: str) -> str:
    """`text` with each person-only command starting with `word`."""
    return _PERSON_ONLY.sub(word + " ", text)


class _Naming:
    """Standard output or error, naming the launcher in what it writes."""

    def __init__(self, stream, word):
        self._stream, self._word = stream, word

    def write(self, text):
        return self._stream.write(name_commands(text, self._word))

    def __getattr__(self, name):
        return getattr(self._stream, name)


def name_commands_in_output() -> None:
    """Make every message the CLI prints name the launcher, so no message
    can send a person to a terminal with a word that terminal lacks. Does
    nothing where `compass` is the right word."""
    word, _ = terminal_command()
    if word == "compass" or isinstance(sys.stdout, _Naming):
        return
    sys.stdout = _Naming(sys.stdout, word)
    sys.stderr = _Naming(sys.stderr, word)
