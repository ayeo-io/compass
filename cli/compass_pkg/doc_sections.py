# compass_pkg.doc_sections - read the checklist sections of an issue's documents
"""One reader for the sections that hold a stage list's checklist.

Three readers use it, so a heading and a section mean one thing: the renderer
of the document templates (`template_lists`), the tick of a `human` check
(`stage_lists`) and the typed tag rule of `dod-evidence-typed` (`checks`).

A section starts at a heading and ends at the next heading or at a line that
starts `Next stage:`. A line inside an HTML comment is not part of any section:
the templates quote example boxes and example headings in comments.

Headings. The `plan` entry list sits under `Definition of Ready` and the
`verify` exit list under `Definition of Done`. Any other list sits under
`<Stage> <side> list`, for example `Implement exit list`.
"""
# DEPENDENCY: standard library (re); compass_pkg.catalogue_spec,
# compass_pkg.stable_ids. It imports nothing else, so any reader can use it.
from __future__ import annotations

import re

from compass_pkg import catalogue_spec
from compass_pkg.stable_ids import STAGE_PLAN, STAGE_VERIFY

#: The two lists the templates have always worded, each under its own heading.
NAMED_HEADINGS = {(STAGE_PLAN, "entry"): "Definition of Ready",
                  (STAGE_VERIFY, "exit"): "Definition of Done"}

_STAGE_ID = re.compile(catalogue_spec.ID_PATTERN)
_COMMENT_TOKEN = re.compile(r"<!--|-->")
_TAG = re.compile(r"^\((?:evidence|follow-up):[^)]*\)\s*")


def list_heading(stage, side):
    """The heading a stage's list sits under in its checklist document. The
    templates render from this and the ticks and the tag rule read from it, so
    a heading means one list."""
    return NAMED_HEADINGS.get((stage, side)) or f"{stage[:1].upper()}{stage[1:]} {side} list"


def is_exit_heading(heading):
    """Whether `heading` is the heading `list_heading` gives some stage's exit
    list. A stage id is whatever `catalogue_spec.ID_PATTERN` allows, so it can
    hold a dot."""
    if heading == NAMED_HEADINGS[(STAGE_VERIFY, "exit")]:
        return True
    suffix = " exit list"
    return heading.endswith(suffix) and bool(_STAGE_ID.match(heading[:-len(suffix)]))


def normal(text):
    """A box's text as a statement is compared: without a leading typed tag or
    emphasis marks, on one line."""
    return " ".join(_TAG.sub("", text).replace("**", "").replace("*", "").split())


def comment_mask(lines):
    """For each line, whether it is inside an HTML comment or opens one."""
    mask, inside = [], False
    for line in lines:
        mask.append(inside or "<!--" in line)
        for token in _COMMENT_TOKEN.findall(line):
            inside = token == "<!--"
    return mask


def heading_of(line):
    """The text of a heading line, else None."""
    return line.strip().lstrip("#").strip() if line.lstrip().startswith("#") else None


def sections(lines, mask, wanted):
    """`[(heading, start, end)]` for every section whose heading `wanted`
    accepts, in document order. The body is `lines[start:end]`."""
    found = []
    for index, line in enumerate(lines):
        heading = None if mask[index] else heading_of(line)
        if heading is None or not wanted(heading):
            continue
        end = len(lines)
        for later in range(index + 1, len(lines)):
            if not mask[later] and (heading_of(lines[later]) is not None
                                    or lines[later].startswith("Next stage:")):
                end = later
                break
        found.append((heading, index + 1, end))
    return found


def section(lines, mask, heading):
    """`(start, end)` of the first section headed `heading`, else None."""
    for _, start, end in sections(lines, mask, lambda h: h == heading):
        return start, end
    return None
