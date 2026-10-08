# compass_pkg.template_lists - render the checklists of the document templates
"""Render a template's stage-list checklists from an issue's configuration.

Two templates hold checklists that are the stage lists: the requirements
review holds the entry lists and the verification report holds the exit lists
(`stage_lists.CHECKLIST_DOCUMENTS`). The shipped plan entry list is worded in
the first as `Definition of Ready` and the shipped `verify` exit list in the
second as `Definition of Done`. This module makes the template follow the
list, so a project that changes a list gets a template that matches it.

For each list the rendered section holds one box for each `human` check the
list names, in the listed order:

- a check whose statement the template already words keeps the template's own
  lines, so the shipped default renders the template file byte for byte;
- any other check gets a generated line: `- [ ] <statement>`, and for an exit
  list `- [ ] (evidence: {{EV-id}}) <statement>`, so the box can be deferred
  with a typed tag;
- a template box no list names is left out.

A list on a stage other than the two named ones renders as its own section,
headed `stage_lists.list_heading(stage, side)`, before the `Next stage:` line.
A list that names no `human` check adds no section. A check of another kind
evaluates itself and has no box to tick, so it does not render. The render
does not read `requires` or `when`: the document lists what the configuration
lists, and evaluation decides what is owed.

A template of any other kind, and an issue read without a configuration,
render as the file.
"""
# DEPENDENCY: standard library (re); compass_pkg.doc_sections,
# compass_pkg.stage_lists. It reads configuration through an EffectiveView.
from __future__ import annotations

import re

from compass_pkg.doc_sections import comment_mask, list_heading, normal, section
from compass_pkg.stage_lists import CHECKLIST_DOCUMENTS

#: Written before a generated exit-list line, so the box can be deferred.
EVIDENCE_PREFIX = "(evidence: {{EV-id}}) "

_ITEM_START = re.compile(r"^- \[[ xX]\] ")
_SIDE_OF = {kind: side for side, kind in CHECKLIST_DOCUMENTS.items()}


def kinds():
    """The document kinds whose checklists render from the lists."""
    return tuple(sorted(_SIDE_OF))


def _blocks(lines, mask, start, end):
    """The boxes in `lines[start:end]` as `(first, last_exclusive, statement)`.
    A box is an item line and the indented lines that continue it."""
    found, index = [], start
    while index < end:
        if mask[index] or not _ITEM_START.match(lines[index]):
            index += 1
            continue
        first, text = index, _ITEM_START.sub("", lines[index])
        index += 1
        while (index < end and not mask[index] and lines[index].startswith(" ")
               and lines[index].strip()):
            text += " " + lines[index].strip()
            index += 1
        found.append((first, index, normal(text)))
    return found


def _generated(statement, side):
    prefix = EVIDENCE_PREFIX if side == "exit" else ""
    return f"- [ ] {prefix}{' '.join(statement.split())}"


def _items(lines, blocks, statements, side):
    """The lines of the section's boxes: the template's own for a statement it
    words, a generated line for any other."""
    unused = list(blocks)
    out = []
    for statement in statements:
        wanted = normal(statement)
        match = next((b for b in unused if b[2] == wanted), None)
        if match is None:
            out.append(_generated(statement, side))
        else:
            unused.remove(match)
            out.extend(lines[match[0]:match[1]])
    return out


def _statements(config, stage, side):
    """The statements of the `human` checks the list names, in order. A check
    the list names more than once gives one statement."""
    checks = config.get("checks") or {}
    named = ((config.get("stages") or {}).get(stage) or {}).get(side) or []
    out = []
    for check_id in dict.fromkeys(named):
        check = checks.get(check_id)
        if isinstance(check, dict) and check.get("kind") == "human" and check.get("statement"):
            out.append(check["statement"])
    return out


def render(text, view, kind):
    """`text`, the template of `kind`, with its checklists rendered from
    `view`. The same text when `view` is None or `kind` holds no lists."""
    side = _SIDE_OF.get(kind)
    if view is None or side is None:
        return text
    config = view.config
    lines = text.split("\n")
    added = []
    for stage in view.stage_order():
        statements = _statements(config, stage, side)
        heading = list_heading(stage, side)
        mask = comment_mask(lines)
        body = section(lines, mask, heading)
        if body is None:
            if statements:
                added.append([f"### {heading}", ""]
                             + _items(lines, [], statements, side) + [""])
            continue
        blocks = _blocks(lines, mask, *body)
        items = _items(lines, blocks, statements, side)
        if blocks:
            first, last = blocks[0][0], blocks[-1][1]
            lines = lines[:first] + items + lines[last:]
        elif items:
            lines = lines[:body[1]] + items + [""] + lines[body[1]:]
    if added:
        mask = comment_mask(lines)
        at = next((i for i, line in enumerate(lines)
                   if not mask[i] and line.startswith("Next stage:")), None)
        extra = [line for new in added for line in new]
        if at is None:
            while lines and lines[-1] == "":
                lines.pop()
            lines = lines + [""] + extra
        else:
            lines = lines[:at] + extra + lines[at:]
    return "\n".join(lines)


def cmd_issue_template(args):
    """`compass issue template <kind> [--issue SLUG] [--json]`. Prints the
    template of `kind` with its checklists rendered from the issue's
    configuration. The text is the whole output, so a caller can write it to
    the document. With `--json` the output is one object:

        {"kind": "<kind>", "issue": "<slug>" or null,
         "source": "generation" | "live" | "none", "text": "<the document>"}

    `source` says where the lists came from: the issue's stored generation, the
    live project configuration, or "none" when no configuration is read and the
    template is the file as it is."""
    import json
    import os
    import sys

    from compass_pkg import effective, terminal
    from compass_pkg.core import FRAMEWORK_ROOT, CompassError, resolve_issue_dir

    directory = os.path.join(FRAMEWORK_ROOT, "templates")
    available = sorted(name[:-3] for name in os.listdir(directory) if name.endswith(".md"))
    kind = args.kind
    if kind not in available:
        raise CompassError(
            f"compass issue template: no template '{kind}'. The templates are: "
            f"{', '.join(available)}.")
    slug = getattr(args, "task", None)
    try:
        task_dir = resolve_issue_dir(slug)
    except CompassError:
        if slug:
            raise
        task_dir = None
    with open(os.path.join(directory, kind + ".md"), encoding="utf-8") as fh:
        text = fh.read()
    view = effective.view_or_legacy(task_dir)
    rendered = render(text, view, kind)
    if terminal.resolve_mode(args) == "json":
        print(json.dumps({"kind": kind,
                          "issue": os.path.basename(os.path.normpath(task_dir)) if task_dir else None,
                          "source": view.source if view is not None else "none",
                          "text": rendered}, indent=2))
        terminal.mark_handled()
        return 0
    sys.stdout.write(rendered)
    return 0
