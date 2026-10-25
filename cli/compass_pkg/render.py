"""What a person reads at a terminal: the route as a rail, and a line fitted
to the terminal's width.

`compass next` opens with the route's stages in a row - done, current,
pending, skipped by policy - when a person runs it. The model must see no
change, so the rail is drawn only when stdout is a terminal and `CLAUDECODE`
is unset: Claude Code runs commands without a terminal and with that
variable set. Everything else gets the verb's plain output, byte for byte.

The status line (`bin/compass-statusline`) fits its line with `fit` too, so
the rail, its header and the status line share one way of fitting a line.
`terminal.py` shortens the CLI's own output lines separately.

DEPENDENCY: standard library only (os, re, shutil, textwrap), so any entry
point can use it without the bundled PyYAML or the full CLI.
"""
from __future__ import annotations

import os
import re
import shutil
import textwrap

GLYPHS = {
    "unicode": {"done": "✓", "current": "●", "pending": "○", "skipped": "–",
                "sep": " → ", "join": " · ", "cut": "…"},
    "ascii": {"done": "[x]", "current": "[>]", "pending": "[ ]", "skipped": "[-]",
              "sep": " > ", "join": " - ", "cut": "..."},
}

# Colour per stage state: done green, current bold cyan, pending plain,
# skipped dim and struck through so it reads as "not on this route".
_COLOUR = {"done": "\x1b[32m", "current": "\x1b[1;36m", "pending": "",
           "skipped": "\x1b[2;9m"}
_RESET = "\x1b[0m"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def rail_style(out, mode: str = "summary", env=None) -> str | None:
    """How to draw the rail on `out`: "color", "unicode", "ascii", or
    None for the plain output.

    `CLAUDECODE` always means plain, whatever else is set, so a person's
    `COMPASS_COLOR=always` never reaches the model. Only the default human
    view gets a rail; `--json` and `--quiet` keep theirs.
    """
    env = os.environ if env is None else env
    if env.get("CLAUDECODE") or mode != "summary":
        return None
    choice = (env.get("COMPASS_COLOR") or "").strip().lower()
    # NO_COLOR counts when present and not empty (no-color.org), and it wins
    # over COMPASS_COLOR=always: that setting is about where the rail shows,
    # not whether it is coloured.
    no_color = bool(env.get("NO_COLOR"))
    if choice == "always":
        return "unicode" if no_color else "color"
    try:
        terminal = out.isatty()
    except (AttributeError, ValueError):
        terminal = False
    if not terminal:
        return None
    if choice == "never":
        return "ascii"
    return "unicode" if no_color else "color"


def stage_states(order, weights, current, finished, skipped_weights):
    """(stage key, state) for every stage in `order`.

    A stage whose weight is in `skipped_weights` is skipped, unless it is
    the current stage, which is always shown as current.
    """
    keys = list(order)
    if current is not None and current not in keys and not finished:
        # A stage outside the pipeline's order says nothing about which
        # stages came before it, so none is shown as done.
        at = 0
    else:
        at = keys.index(current) if current in keys else len(keys)
    out = []
    for i, key in enumerate(keys):
        weight = str((weights or {}).get(key) or "").strip().lower()
        if key == current and not finished:
            state = "current"
        elif weight in skipped_weights:
            state = "skipped"
        elif finished or i < at:
            state = "done"
        else:
            state = "pending"
        out.append((key, state))
    return out


def visible_width(text: str) -> int:
    return len(_ANSI.sub("", text))


def rail(items, style: str, width: int | None = None) -> list[str]:
    """The rail's lines for [(display name, state)], wrapped between stages
    so no line is wider than `width` (the terminal's, by default)."""
    if width is None:
        width = shutil.get_terminal_size((80, 24)).columns
    glyphs = GLYPHS["ascii" if style == "ascii" else "unicode"]
    sep = glyphs["sep"]
    lines, line = [], ""
    for name, state in items:
        token = f"{name} {glyphs[state]}"
        if style == "color" and _COLOUR[state]:
            token = f"{_COLOUR[state]}{token}{_RESET}"
        if not line:
            line = token
        elif visible_width(line) + len(sep) + visible_width(token) <= width:
            line += sep + token
        else:
            # The separator opens the next line, so the arrow still reads.
            lines.append(line)
            line = sep.lstrip() + token
    if line:
        lines.append(line)
    return lines


def fit(fields: list, width: int, sep: str, cut: str = "…") -> str:
    """Join `fields` with `sep`, dropping fields from the right until the line
    fits `width`; the first two always stay, and the second is cut last,
    ending in `cut`."""
    fields = list(fields)
    while len(sep.join(fields)) > width and len(fields) > 2:
        fields.pop()
    line = sep.join(fields)
    if len(line) > width and len(fields) == 2:
        room = width - len(fields[0]) - len(sep) - len(cut)
        fields[1] = fields[1][:max(room, 1)] + cut
        line = sep.join(fields)
    return line


def wrap(text: str, width: int | None = None) -> list[str]:
    """`text` broken at spaces into lines no wider than `width`. Used for the
    plain lines under the rail, which keep their words but not their line."""
    if width is None:
        width = shutil.get_terminal_size((80, 24)).columns
    return textwrap.wrap(text, max(width, 1), break_on_hyphens=False) or [""]


def header(fields: list, style: str, width: int | None = None) -> str:
    """The line above the rail, fitted to the terminal like the rail."""
    if width is None:
        width = shutil.get_terminal_size((80, 24)).columns
    glyphs = GLYPHS["ascii" if style == "ascii" else "unicode"]
    # The fields come from the manifest, which anyone can edit. A control
    # character in one could set the window title or clear the screen.
    fields = [_CONTROL.sub("", str(f)) for f in fields if f]
    return fit([f for f in fields if f], width, glyphs["join"], glyphs["cut"])


# --- paths ---------------------------------------------------------------------
# Every path the CLI prints is relative to the project root, `path:line` where
# the line is known, so a terminal or an IDE opens it with one click and the
# model reads it without a search (#291).


def relative_paths(text, root) -> str:
    """`text` with each absolute path under `root` made relative to it. The
    root itself is left absolute: "initialised Compass in <root>" must say
    where."""
    if not root or not isinstance(text, str):
        return text
    for base in sorted({os.path.abspath(root), os.path.realpath(root)}, key=len, reverse=True):
        if len(base) <= 1:
            continue          # the filesystem root would match everything
        # Only where the root starts a path - not inside a URL or a longer
        # path that merely contains it - and only with a name after it.
        pattern = r"(?<![\w./:~$-])" + re.escape(base + os.sep) + r"(?=[^\s`'\"])"
        text = re.sub(pattern, "", text)
    return text


# A colour or cursor sequence a terminal program writes: ESC, `[`, numbers
# and semicolons, then one letter. XML cannot hold ESC, so pytest's JUnit
# report writes it as the literal text `#x1B`; both forms are matched.
_ANSI_SEQUENCE = re.compile(r"(?:\x1b|#x1B)\[[0-9;?]*[A-Za-z]")


def strip_ansi(text):
    """`text` without terminal colour codes. With FORCE_COLOR set, pytest
    colours `E`, `PASSED`, `FAILED` and its summary counts even when its
    output is captured, so any match on those words reads the text through
    this first (#403)."""
    return _ANSI_SEQUENCE.sub("", text or "")


def fired_rule_line(rule, with_kind=True):
    """One fired policy rule as a line: its meaning first, then its id, and
    its kind when asked. Every screen that names a fired rule prints it
    through this, so the screens cannot drift apart again (#109)."""
    if not isinstance(rule, dict):
        return f"({rule})"
    rationale = str(rule.get("rationale") or "").rstrip().rstrip(".")
    code = rule.get("id", "?")
    if with_kind and rule.get("kind"):
        code = f"{code}, {rule['kind']}"
    return f"{rationale} ({code})" if rationale else f"({code})"
