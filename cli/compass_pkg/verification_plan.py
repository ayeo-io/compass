# compass_pkg.verification_plan - the planned kind of test for each scenario
"""Reads the Verification plan table of a technical design.

The table's rows name a scenario group letter or scenario ids in the Group cell, and one
of five kinds in the Kind cell. `read` gives each scenario its planned kind:

- a row that names the scenario's id wins over a row that names its group;
- between rows of one precedence, the first row wins;
- a scenario no row covers reads "not planned";
- a word that is not one of the five kinds reads "unknown (<word>)".

A scenario's group comes from the spec: the letter of the `## Scenario group <L>` heading
above its `traceability id` line.

No check parses this table. The `coverage` block shows the kinds, so the plan reaches
`compass check` only as `rendered-blocks-current` staleness, and `compass issue lint`
prints a note for a row whose kind is unknown.
"""
# DEPENDENCY: standard library (dataclasses, re); compass_pkg.template_lists (same_heading
# and its section-number rule).
from __future__ import annotations

import re
from dataclasses import dataclass, field

from compass_pkg import template_lists

HEADING = "Verification plan"
KINDS = ("unit", "integration", "acceptance", "judged review", "manual")
NOT_PLANNED = "not planned"

_GROUP_HEADING = re.compile(r"^Scenario group\s+([A-Za-z0-9]+)\b")
_TRACE = re.compile(r"traceability id:\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")
_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_SEPARATOR = re.compile(r"^\|?\s*:?-{3,}")


@dataclass
class Row:
    #: The table's 1-based data row number, for the lint note.
    number: int
    group: str
    kind: str
    #: The tokens of the Group cell.
    names: list = field(default_factory=list)

    @property
    def known(self):
        return self.kind.lower() in KINDS


@dataclass
class Plan:
    rows: list
    #: `{scenario id: kind text}` for every scenario asked about.
    kinds: dict

    def unknown_rows(self):
        return [r for r in self.rows if not r.known]


def _plain_lines(text):
    """`(line, outside)` for each line: `outside` is False inside a code fence or an HTML
    comment, where a heading or a table is not one."""
    fenced = commented = False
    for line in text.split("\n"):
        stripped = line.strip()
        if not commented and stripped.startswith(("```", "~~~")):
            fenced = not fenced
            yield line, False
            continue
        if fenced:
            yield line, False
            continue
        if commented:
            if "-->" in line:
                commented = False
            yield line, False
            continue
        if stripped.startswith("<!--") and "-->" not in stripped[4:]:
            commented = True
            yield line, False
            continue
        yield line, True


def _section(text):
    """The lines of the Verification plan section that are outside fences and comments, or
    None when the text holds no such `## ` heading."""
    lines, inside = None, False
    for line, outside in _plain_lines(text):
        if outside and line.startswith("## "):
            if inside:
                break
            inside = template_lists.same_heading(line[3:].strip(), HEADING)
            if inside:
                lines = []
            continue
        if inside and outside:
            lines.append(line)
    return lines


def has_plan(design_text):
    """Whether the design holds a Verification plan heading."""
    return _section(design_text or "") is not None


def _cells(line):
    parts = _CELL_SPLIT.split(line.strip())
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return [p.strip().replace("\\|", "|") for p in parts]


def _rows(section):
    """The rows of the first table whose header holds Group and Kind."""
    lines = list(section)
    for at, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        header = [c.lower() for c in _cells(line)]
        if "group" not in header or "kind" not in header:
            continue
        if at + 1 >= len(lines) or not _SEPARATOR.match(lines[at + 1].strip()):
            continue
        g, k = header.index("group"), header.index("kind")
        rows = []
        for body in lines[at + 2:]:
            if not body.lstrip().startswith("|"):
                break
            cells = _cells(body)
            if len(cells) <= max(g, k):
                continue
            group, kind = cells[g], cells[k]
            # A row still holding the template's placeholder is not a plan yet.
            if "{{" in group or "{{" in kind:
                continue
            kind = " ".join(kind.strip("`").split())
            names = [n.strip().strip("`") for n in group.split(",") if n.strip().strip("`")]
            rows.append(Row(len(rows) + 1, group, kind, names))
        return rows
    return []


def spec_groups(spec_text):
    """`{scenario id: group letter}` from the spec's `## Scenario group <L>` headings. A
    scenario under any other `## ` heading has no group."""
    groups, current = {}, None
    for line, outside in _plain_lines(spec_text or ""):
        if outside and line.startswith("## "):
            words = template_lists._SECTION_NUMBER.sub("", line[3:].strip())
            found = _GROUP_HEADING.match(words)
            current = found.group(1) if found else None
            continue
        trace = _TRACE.search(line)
        if trace and current is not None:
            groups.setdefault(trace.group(1), current)
    return groups


def _kind_text(row):
    kind = row.kind.lower()
    return kind if kind in KINDS else "unknown (%s)" % row.kind


def read(design_text, spec_text, scenario_ids):
    """The `Plan` of the design, or None when it holds no Verification plan heading."""
    section = _section(design_text or "")
    if section is None:
        return None
    rows = _rows(section)
    groups = spec_groups(spec_text)
    ids = [str(s) for s in scenario_ids]
    known_ids = set(ids)
    by_id, by_group = {}, {}
    for row in rows:
        for name in row.names:
            if name in known_ids:
                by_id.setdefault(name, row)
            else:
                by_group.setdefault(name.upper(), row)
    kinds = {}
    for sid in ids:
        row = by_id.get(sid)
        if row is None and sid in groups:
            row = by_group.get(groups[sid].upper())
        kinds[sid] = _kind_text(row) if row is not None else NOT_PLANNED
    return Plan(rows, kinds)


def lint_notes(task, task_dir):
    """One line for each Verification plan row whose kind is not one of the five. A report
    beside the lint result: it never changes the exit code."""
    try:
        from compass_pkg import render_cmd, render_inputs
        inputs = render_inputs.gather(task, task_dir, render_cmd.project_of(task_dir))
        plan = read(inputs.doc_text("technical-design"), "", [])
    except Exception:                                       # noqa: BLE001 - a report must not fail the lint
        return []
    if plan is None:
        return []
    return ["technical-design.md: Verification plan row %d (%s) has the kind \"%s\", which is "
            "not one of %s or %s; the coverage block shows it as unknown."
            % (r.number, r.group, r.kind, ", ".join(KINDS[:-1]), KINDS[-1])
            for r in plan.unknown_rows()]
