"""What a person reads at a terminal: the route as a rail, and a line fitted
to the terminal's width.

`compass next` opens with the route's stages in a row - done, current,
pending, skipped by policy - when a person runs it. The model must see no
change, so the rail is drawn only when stdout is a terminal and `CLAUDECODE`
is unset: Claude Code runs commands with neither a terminal nor that
variable unset. Everything else gets the verb's plain output, byte for byte.

The status line (`bin/compass-statusline`) fits its line with `fit`, so
width fitting lives in one place.

Standard library only, so any entry point can use it without the YAML
dependency or the full CLI.
"""
from __future__ import annotations

import os
import re
import shutil

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
    if choice == "always":
        return "color"
    try:
        terminal = out.isatty()
    except (AttributeError, ValueError):
        terminal = False
    if not terminal:
        return None
    if choice == "never":
        return "ascii"
    # NO_COLOR counts when present and not empty (no-color.org).
    if env.get("NO_COLOR"):
        return "unicode"
    return "color"


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


def header(fields: list, style: str, width: int | None = None) -> str:
    """The line above the rail, fitted to the terminal like the rail."""
    if width is None:
        width = shutil.get_terminal_size((80, 24)).columns
    glyphs = GLYPHS["ascii" if style == "ascii" else "unicode"]
    return fit([f for f in fields if f], width, glyphs["join"], glyphs["cut"])
