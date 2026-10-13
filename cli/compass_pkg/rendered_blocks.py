# compass_pkg.rendered_blocks - the marker grammar, the mask and the one write path
"""The leaf module that owns rendered blocks (ADR-051).

A rendered block is the region between `<!-- compass:render <kind> -->` and
`<!-- /compass:render -->` in a person's document. The CLI rewrites what is
between the markers and nothing else. This module holds the four things that
make that safe, so no other module restates them:

- `parse`: finds the blocks of a text, or refuses a malformed marker with the
  line it is on;
- `masked_text` and `masked_digest`: a text with the lines inside every block
  removed. Every digest of a document and every reader of its text goes through
  them, so a render never changes what a person has approved or what a check
  reads as a statement;
- `neutralise`, `cell`, `field`: text copied from a record or a document is
  made harmless before it is written, so it cannot be read as a marker, a code
  fence, an HTML comment or a git conflict marker;
- `splice` and `write_rendered`: the only code that builds and writes a
  rendered document. It proves two things before it writes: the text outside
  the markers is unchanged, and a parse of the new text gives exactly the
  blocks that were meant.

It imports nothing from Compass except `atomic_io`, so any module can use it.
The grammar and its limits are in `architecture/decisions/ADR-051-*.md`.
"""
# DEPENDENCY: standard library (dataclasses, hashlib, os, re); compass_pkg.atomic_io.
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass

from compass_pkg import atomic_io

#: The block kinds. The first eight are the kinds of documents the templates carry; the rest belong to the
#: issue page, the verification note, the project index and the delivery approach's readiness line. Any other name in an
#: opening marker is a malformed marker.
KINDS = ("coverage", "gates", "dod", "dor", "artifacts", "evidence", "follow-ups",
         "decisions-taken", "header", "ask", "decision-required", "acceptance", "related",
         "decisions", "traceability", "deliberately-omitted", "verification-note", "index",
         "assessment", "policy-rules", "stage-weights", "gate-set", "plan-exit", "breakdown-exit",
         "readiness")

#: The prefix of the temporary files the render writes, so a killed render's
#: leftover can be told from a person's file.
TEMP_PREFIX = ".compass-render-"

OPENING = "<!-- compass:render {kind} -->"
CLOSING = "<!-- /compass:render -->"

_OPEN = re.compile(r"^<!-- compass:render ([A-Za-z0-9-]+) -->$")
#: Anything that starts like a marker. A line that does and is not exactly a
#: marker is malformed, whatever its spacing.
_LOOKS_LIKE = re.compile(r"^<!--\s*/?\s*compass:render")
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})(.*)$")
_CONFLICT = ("<<<<<<<", "=======", ">>>>>>>", "|||||||")


class MarkerError(ValueError):
    """A marker that does not parse. `line` is 1-based; `fault` says what is wrong."""

    def __init__(self, path, line, fault):
        super().__init__(f"{path}:{line}: {fault}")
        self.path, self.line, self.fault = path, line, fault


class PostConditionError(ValueError):
    """The engine refused a write: its own output failed a post-condition."""


class ChangedDuringRender(ValueError):
    """The file changed between the read and the replace."""


@dataclass(frozen=True)
class Block:
    """A block: `lines[start]` is the opening marker, `lines[end]` the closing
    one, and `lines[start + 1:end]` the interior."""
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Parsed:
    lines: list
    blocks: list
    eol: str


def line_ending(text):
    """The file's own line ending: the first one it holds, LF when it holds none."""
    at = text.find("\n")
    return "\r\n" if at > 0 and text[at - 1] == "\r" else "\n"


def split_lines(text):
    """The lines of `text` with their endings kept. Only LF ends a line, so the
    pieces join back to the text byte for byte."""
    lines = text.split("\n")
    out = [line + "\n" for line in lines[:-1]]
    if lines[-1]:
        out.append(lines[-1])
    return out


def _comment_state(line, inside):
    """Whether a multi-line HTML comment is still open after `line`, given
    whether it was open before it."""
    position = 0
    while position < len(line):
        if inside:
            end = line.find("-->", position)
            if end < 0:
                return True
            position, inside = end + 3, False
        else:
            start = line.find("<!--", position)
            if start < 0:
                return False
            position, inside = start + 4, True
    return inside


def parse(text, path="<text>"):
    """The blocks of `text`. Raises `MarkerError` for a marker that is not well
    formed. A marker counts only on a line by itself, outside a fenced code
    block and outside a multi-line HTML comment; inside a block, only the
    closing marker and a stray marker matter."""
    lines = split_lines(text)
    blocks, open_block = [], None
    fence, in_comment = None, False
    for index, raw in enumerate(lines):
        line = raw.strip()
        number = index + 1
        if open_block is not None:
            if line == CLOSING:
                blocks.append(Block(open_block[0], open_block[1], index))
                open_block = None
            elif _OPEN.match(line):
                if _OPEN.match(line).group(1) not in KINDS:
                    raise MarkerError(path, number, _unknown(line))
                raise MarkerError(
                    path, number, f"an opening marker inside the open block that starts at "
                    f"line {open_block[1] + 1}")
            elif _LOOKS_LIKE.match(line):
                raise MarkerError(path, number, "a malformed marker inside an open block")
            continue
        if fence is not None:
            closing = re.match(r"^([`~]{3,})\s*$", line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence):
                fence = None
            continue
        if in_comment:
            in_comment = _comment_state(line, True)
            continue
        opened = _FENCE_OPEN.match(line)
        if opened and not (opened.group(1)[0] == "`" and "`" in opened.group(2)):
            fence = opened.group(1)
            continue
        if line == CLOSING:
            raise MarkerError(path, number, "a closing marker with no opening marker")
        found = _OPEN.match(line)
        if found:
            if found.group(1) not in KINDS:
                raise MarkerError(path, number, _unknown(line))
            open_block = (found.group(1), index)
            continue
        if _LOOKS_LIKE.match(line):
            raise MarkerError(
                path, number,
                "a malformed marker (a marker is exactly "
                "`<!-- compass:render KIND -->` or `<!-- /compass:render -->` on its own line)")
        in_comment = _comment_state(line, False)
    if open_block is not None:
        raise MarkerError(path, open_block[1] + 1,
                          f"an opening marker for {open_block[0]} with no closing marker")
    return Parsed(lines, blocks, line_ending(text))


def _unknown(line):
    name = _OPEN.match(line).group(1)
    return (f"an opening marker naming the unknown kind \"{name}\" "
            f"(the kinds are {', '.join(KINDS)})")


def masked_text(text, keep_lines=False):
    """`text` with the lines inside every block removed and the marker lines
    kept. With `keep_lines`, each removed line is replaced by an empty line, so
    a line number in the result is a line number in `text`.

    A text with no block is returned byte for byte, so a digest recorded before
    blocks existed does not change. A text whose markers do not parse is
    returned whole: it never raises, because a reader or a digest must not fail
    on a document a person is still mending."""
    if "compass:render" not in text:
        return text
    try:
        parsed = parse(text)
    except MarkerError:
        return text
    if not parsed.blocks:
        return text
    skip = {}
    for block in parsed.blocks:
        for index in range(block.start + 1, block.end):
            skip[index] = True
    eol = parsed.eol
    out = []
    for index, raw in enumerate(parsed.lines):
        if index in skip:
            if keep_lines:
                out.append(eol)
            continue
        out.append(raw)
    return "".join(out)


def read_masked(path, keep_lines=False):
    """The masked text of the file at `path`, read as UTF-8 with the line
    endings a reader sees (`\\r\\n` as `\\n`), as `open(path).read()` gives."""
    with open(path, encoding="utf-8") as fh:
        return masked_text(fh.read(), keep_lines=keep_lines)


def masked_digest(path):
    """`sha256:` and the hex digest of the file's masked bytes, `None` when the
    file is absent. A file that is not UTF-8 is digested whole."""
    if not path or not os.path.isfile(path):
        return None
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        data = masked_text(raw.decode("utf-8")).encode("utf-8")
    except UnicodeDecodeError:
        data = raw
    return "sha256:" + hashlib.sha256(data).hexdigest()


# --- text copied into a block ----------------------------------------------

def neutralise(line):
    """`line` made safe to write inside a block. A comment opener or closer is
    written as an entity, and a line that would open a code fence or read as a
    git conflict marker gets a backslash before its first character, which
    CommonMark shows as the character itself."""
    line = line.replace("<!--", "&lt;!--").replace("-->", "--&gt;")
    stripped = line.lstrip()
    if stripped.startswith(("```", "~~~") + _CONFLICT):
        lead = len(line) - len(stripped)
        line = line[:lead] + "\\" + stripped
    return line


def field(text):
    """A one-line field: line breaks become spaces, then the text is neutralised."""
    return neutralise(" ".join(str(text if text is not None else "").split()))


def cell(text):
    """A table cell: a field with each `|` escaped."""
    return field(text).replace("|", "\\|")


def hygiene_problem(line):
    """Why a rendered line is not safe, or `None`. A rendered line holds no
    comment opener or closer, does not open a fence and is not a conflict
    marker; a line that did would change how the rest of the document reads."""
    if "<!--" in line or "-->" in line:
        return "holds an HTML comment opener or closer"
    stripped = line.strip()
    if stripped.startswith(("```", "~~~")):
        return "opens a code fence"
    if stripped.startswith(_CONFLICT):
        return "reads as a git conflict marker"
    return None


#: The one fence a rendered body may hold: a Mermaid chart, opened and closed by these exact
#: lines. A chart line is neutralised like any other, so no line inside can close it early.
CHART_OPEN, CHART_CLOSE = "```mermaid", "```"


def body_problem(lines):
    """`(line, why)` for the first unsafe line of a rendered body, or None. The lines
    follow `hygiene_problem`, except that one balanced Mermaid fence is allowed: the
    chart of the traceability block."""
    in_chart = False
    for line in lines:
        if in_chart and line == CHART_CLOSE:
            in_chart = False
            continue
        if not in_chart and line == CHART_OPEN:
            in_chart = True
            continue
        problem = hygiene_problem(line)
        if problem:
            return line, problem
    if in_chart:
        return CHART_OPEN, "opens a code fence that is never closed"
    return None


# --- building and writing a rendered document ------------------------------

def splice(parsed, bodies):
    """The text of `parsed` with the interior of each block in `bodies`
    replaced. `bodies` maps a block's index in `parsed.blocks` to its interior
    lines (without line endings). This is the one place a rendered document is
    assembled."""
    eol = parsed.eol
    out, cursor = [], 0
    for index, block in enumerate(parsed.blocks):
        if index not in bodies:
            continue
        out.extend(parsed.lines[cursor:block.start + 1])
        out.extend(line + eol for line in bodies[index])
        cursor = block.end
    out.extend(parsed.lines[cursor:])
    return "".join(out)


def build(path, text, bodies):
    """`new_text` for `text` with `bodies` spliced in, after the two
    post-conditions hold:

    - the masked text of the result equals the masked text of `text`, so
      nothing outside the markers changed;
    - a parse of the result gives exactly the blocks meant: the same kinds in
      the same order, the new interior in the blocks that were rendered, the old
      interior in the rest, and no rendered line that could be read as markup.

    Raises `PostConditionError` otherwise; nothing has been written."""
    parsed = parse(text, path)
    for index, lines in bodies.items():
        found = body_problem(lines)
        if found:
            line, problem = found
            raise PostConditionError(
                f"{path}: a rendered line in the {parsed.blocks[index].kind} block "
                f"{problem}: {line[:80]!r}. The render wrote nothing.")
    new_text = splice(parsed, bodies)
    if masked_text(new_text) != masked_text(text):
        raise PostConditionError(
            f"{path}: the render would change text outside the markers (post-condition: "
            f"the masked text must be unchanged). It wrote nothing.")
    again = parse(new_text, path)
    meant = []
    for index, block in enumerate(parsed.blocks):
        interior = ([line + parsed.eol for line in bodies[index]] if index in bodies
                    else parsed.lines[block.start + 1:block.end])
        meant.append((block.kind, "".join(interior)))
    got = [(b.kind, "".join(again.lines[b.start + 1:b.end])) for b in again.blocks]
    if got != meant:
        raise PostConditionError(
            f"{path}: a parse of the rendered text does not give the blocks that were "
            f"meant (post-condition). It wrote nothing.")
    return new_text


def file_digest(path):
    """`sha256:` and the hex digest of the file's bytes, `None` when absent."""
    try:
        with open(path, "rb") as fh:
            return "sha256:" + hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None


def write_rendered(path, new_text, read_digest, *, before_replace=None):
    """Replace `path` with `new_text` unless it changed since it was read.

    `read_digest` is `file_digest` of the bytes the render read, `None` for a
    file that did not exist. The check runs after the temporary file is written
    and just before the rename; a file that moved since the read is left as it
    is and `ChangedDuringRender` is raised."""

    def guard(tmp):
        if before_replace is not None:
            before_replace(tmp)
        if file_digest(path) != read_digest:
            raise ChangedDuringRender(
                f"{path} changed during the render. It was not replaced, so the change "
                f"is kept. Run the command again.")

    atomic_io.atomic_write_text(path, new_text, newline="", temp_prefix=TEMP_PREFIX,
                                before_replace=guard)


def remove_stale_temporaries(folder):
    """Delete the temporary files a killed render left in `folder`. The caller
    holds the issue's lock, so no other render is writing one."""
    removed = []
    try:
        names = os.listdir(folder)
    except OSError:
        return removed
    for name in names:
        if name.startswith(TEMP_PREFIX):
            try:
                os.unlink(os.path.join(folder, name))
                removed.append(name)
            except OSError:
                pass
    return removed
