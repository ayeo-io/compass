# compass_pkg.block_renderers - the text of each rendered block, from a snapshot
"""Pure renderers for the rendered block kinds (ADR-051).

A renderer takes a `RenderInputs` snapshot of the records and the project-
relative path of the document it renders into, and returns a `Part`: the lines
of the block and whether they depend on this issue's own records (`own`) or on
other issues or the project (`cross`). It reads no file, no clock and no git
configuration, so the same records give the same text on every machine and a
second render changes no byte (DCJ-3). `gather` is the only function here that
touches the disk, and it does so once, before any renderer runs.

Every line copied from a record goes through `rendered_blocks.field`,
`cell` or `neutralise`, so recorded text cannot be read as a marker (DCJ-68).
They are called through the module, so a test can replace one.

The kinds this module renders are the eight of RS-1. A kind in
`rendered_blocks.KINDS` with no entry in `RENDERERS` is left as it is.
"""
# DEPENDENCY: standard library (dataclasses, glob, json, os); compass_pkg.rendered_blocks,
# compass_pkg.item_records, compass_pkg.issue_layout.
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field

from compass_pkg import item_records
from compass_pkg import rendered_blocks as rb
from compass_pkg.issue_layout import DOCS_ROOT

OWN, CROSS = "own", "cross"


@dataclass(frozen=True)
class Part:
    """The lines of one block. `scope` is `own` when they depend only on this
    issue's records and `cross` when they depend on another issue or the project."""
    scope: str
    lines: list


@dataclass
class RenderInputs:
    """A snapshot of everything the renderers read."""
    task: dict
    slug: str
    #: The project-relative directory of the issue's work folder.
    work_rel: str
    view: object = None
    #: `{(kind, scenario): file name}` for the red, green and acceptance records.
    records: dict = field(default_factory=dict)
    unbound: list = field(default_factory=list)

    def list_of(self, key):
        value = self.task.get(key)
        return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []


def gather(task, task_dir, project_root, view=None):
    """The snapshot for one issue: the manifest as loaded, the record files in the
    issue's `evidence/` folder, and the configuration view (None when the issue
    is read without one)."""
    records, unbound = _records(task_dir)
    work_rel = os.path.relpath(os.path.abspath(task_dir), project_root).replace(os.sep, "/")
    return RenderInputs(task=task, slug=os.path.basename(os.path.normpath(task_dir)),
                        work_rel=work_rel, view=view, records=records, unbound=unbound)


def _records(task_dir):
    out, unbound = {}, []
    for path in sorted(glob.glob(os.path.join(task_dir, "evidence", "*.json"))):
        name = os.path.basename(path)
        kind = next((k for k in ("red", "green", "acceptance")
                     if name == f"{k}.json" or name.startswith(f"{k}-")), None)
        if kind is None or name == "acceptance-baseline.json":
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        scenario = (data.get("scenario") if isinstance(data, dict) else None) \
            or name[len(kind) + 1:-5]
        if scenario:
            out.setdefault((kind, str(scenario)), name)
        else:
            unbound.append(name)
    return out, unbound


# --- helpers ---------------------------------------------------------------

def _code(text):
    """Text as inline code: neutralised, and a backtick written as an
    apostrophe so it cannot end the span."""
    return "`%s`" % rb.field(text).replace("`", "'")


def _link_target(inputs, path):
    """The project-relative path a manifest path names, or None when it
    leaves the project. A path under `docs/` or `.compass/` is measured from the
    project root; any other is measured from the issue's work folder, as the
    evidence registry's paths are."""
    path = str(path or "").replace("\\", "/")
    if not path or os.path.isabs(path):
        return None
    if not path.startswith(("docs/", ".compass/")):
        path = inputs.work_rel + "/" + path
    norm = os.path.normpath(path).replace(os.sep, "/")
    return None if norm.startswith("..") else norm


def _link(inputs, path, doc_rel, text):
    """A relative Markdown link to `path`, shown as `text`, when the path is
    under `docs/compass/` (a folder a project commits); None otherwise. The work
    folder is untracked in many projects, so a link there would not resolve."""
    target = _link_target(inputs, path)
    safe = target is not None and all(c.isalnum() or c in "._-/" for c in target)
    if not (safe and target.startswith(DOCS_ROOT.replace(os.sep, "/") + "/")):
        return None
    relative = os.path.relpath(target, os.path.dirname(doc_rel) or ".").replace(os.sep, "/")
    return "[%s](%s)" % (rb.field(text).replace("[", "\\[").replace("]", "\\]"), relative)


def _shown_path(inputs, path, doc_rel):
    """A path as the block shows it: a link when `_link` gives one, else code."""
    return _link(inputs, path, doc_rel, path) or _code(path)


# --- the renderers ---------------------------------------------------------

def coverage(inputs, doc_rel):
    scenarios = inputs.list_of("scenarios")
    lines = []
    if not scenarios:
        lines.append("No scenarios recorded yet.")
    else:
        rows, passed = [], 0
        for s in scenarios:
            sid = str(s.get("id", "?"))
            red = inputs.records.get(("red", sid))
            green = inputs.records.get(("green", sid))
            accept = inputs.records.get(("acceptance", sid))
            if green or accept:
                result = "passed"
                passed += 1
            elif red:
                result = "failing test only"
            else:
                result = "no test record"
            tests = ", ".join(_code(t) for t in s.get("tests") or []) or "-"
            rows.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                rb.cell(sid), rb.cell(s.get("title", "")), tests,
                _code(red) if red else "-", _code(green) if green else "-",
                _code(accept) if accept else "-", result))
        lines += ["Coverage: %d of %d scenarios passed" % (passed, len(scenarios)), "",
                  "| Scenario | Title | Tests | Red | Green | Acceptance | Result |",
                  "|---|---|---|---|---|---|---|"] + rows
    modes = inputs.list_of("failure_modes_descoped")
    if modes:
        lines += ["", "De-scoped failure modes:"]
        lines += ["- %s - %s" % (rb.field(m.get("mode", "")),
                                 rb.field(m.get("reason") or "no reason recorded"))
                  for m in modes]
    return Part(OWN, lines)


def gates(inputs, doc_rel):
    rows = inputs.list_of("gates")
    if not rows:
        return Part(OWN, ["No gates recorded yet."])
    passed = sum(1 for g in rows if g.get("status") == "pass")
    lines = ["Gates: %d of %d pass" % (passed, len(rows)), ""]
    for g in rows:
        ids = ", ".join(str(e) for e in g.get("evidence") or []) or "no evidence"
        lines.append("- %s: %s - %s" % (_code(g.get("id", "?")),
                                        rb.field(g.get("status", "?")), rb.field(ids)))
    return Part(OWN, lines)


def _exit_list(which):
    def render(inputs, doc_rel):
        rows = item_records.items(inputs.task, None, inputs.view, which)
        title = item_records.TITLES[which]
        if not rows:
            return Part(OWN, ["No %s is configured for this issue." % title])
        met = [i for i in rows if i.state in item_records.MET]
        carried = [i for i in rows if i.state == item_records.CARRIED]
        opened = [i for i in rows if i.state == item_records.OPEN]
        head = "%s: %d of %d met" % (title, len(met), len(rows))
        if carried:
            ids = ", ".join(r for i in carried for r in i.records)
            head += ", %d carried to ship (%s)" % (len(carried), rb.field(ids))
        if opened:
            head += ", %d open" % len(opened)
        lines = [head, ""]
        for item in rows:
            lines.append("- %s - %s (%s)" % (_state_phrase(item), rb.field(item.statement),
                                             _code(item.check)))
        return Part(OWN, lines)
    return render


def _state_phrase(item):
    ids = rb.field(", ".join(item.records))
    return {
        item_records.MET_EVIDENCE: "met by " + ids,
        item_records.TICKED: "ticked by " + ids,
        item_records.MET_CARRIED: "met, carried to " + ids + " (resolved)",
        item_records.PAGE_TICK: "ticked on the page before 7.0.0 (%s)" % ids,
        item_records.CARRIED: "carried to " + ids,
        item_records.OPEN: "open",
    }[item.state]


def artifacts(inputs, doc_rel):
    rows = inputs.list_of("artifacts")
    if not rows:
        return Part(OWN, ["No documents registered yet."])
    approved = sum(1 for a in rows if a.get("status") == "approved")
    lines = ["Documents: %d registered, %d approved" % (len(rows), approved), "",
             "| Document | Status | Approved by | Why it exists |", "|---|---|---|---|"]
    for a in rows:
        kind = rb.cell(a.get("kind", "?"))
        shown = (_link(inputs, a["path"], doc_rel, a.get("kind", "?")) if a.get("path") else None) \
            or kind
        by = a.get("approved_by") if a.get("status") == "approved" else None
        lines.append("| %s | %s | %s | %s |" % (
            shown, rb.cell(a.get("status", "?")), rb.cell(by) if by else "-",
            rb.cell(a.get("reason") or "")))
    return Part(OWN, lines)


def evidence(inputs, doc_rel):
    rows = inputs.list_of("evidence")
    if not rows:
        return Part(OWN, ["No evidence recorded yet."])
    lines = ["Evidence is linked, not reproduced - open a record to read it.", ""]
    for e in rows:
        where = _shown_path(inputs, e["path"], doc_rel) if e.get("path") else "no path"
        lines.append("- %s (%s) - %s" % (_code(e.get("id", "?")),
                                         rb.field(e.get("type", "?")), where))
    return Part(OWN, lines)


def follow_ups(inputs, doc_rel):
    rows = inputs.list_of("follow_ups")
    if not rows:
        return Part(OWN, ["No follow-ups recorded."])
    lines = []
    for f in rows:
        line = "- %s (%s) %s" % (_code(f.get("id", "?")), rb.field(f.get("status", "?")),
                                 rb.field(f.get("summary", "")))
        if f.get("target_task"):
            line += " - target: %s" % _code(f["target_task"])
        if f.get("defers"):
            line += " - defers: %s" % _code(f["defers"])
        lines.append(line)
    return Part(OWN, lines)


def decisions_taken(inputs, doc_rel):
    taken = inputs.list_of("decisions_taken")
    again = inputs.list_of("reassessments")
    if not taken and not again:
        return Part(OWN, ["No decisions taken and no reassessments recorded."])
    lines = []
    if taken:
        confirmed = sum(1 for d in taken if d.get("status") == "confirmed")
        lines += ["Decisions taken for the person: %d, %d confirmed" % (len(taken), confirmed), ""]
        for d in taken:
            lines.append("- %s (%s) %s - %s - taken by %s at %s" % (
                _code(d.get("id", "?")), rb.field(d.get("status", "?")),
                rb.field(d.get("question", "")), rb.field(d.get("resolution", "")),
                rb.field(d.get("by", "?")), rb.field(d.get("stage", "?"))))
    if again:
        if lines:
            lines.append("")
        lines += ["Reassessments:", ""]
        for r in again:
            lines.append("- %s to %s (%s): %s" % (
                rb.field(r.get("from_route", "?")), rb.field(r.get("to_route", "?")),
                rb.field(r.get("kind", "judgement")), rb.field(r.get("reason", ""))))
    return Part(OWN, lines)


#: Kind to renderer. A new kind is one entry here and one name in `rendered_blocks.KINDS`.
RENDERERS = {
    "coverage": coverage,
    "gates": gates,
    "dod": _exit_list("dod"),
    "dor": _exit_list("dor"),
    "artifacts": artifacts,
    "evidence": evidence,
    "follow-ups": follow_ups,
    "decisions-taken": decisions_taken,
}

#: The blocks a new issue page holds until the page kinds are rendered.
PAGE_KINDS = ("artifacts", "follow-ups")


def issue_page_text(slug):
    """The issue page as it is first created: a title and the blocks of the kinds
    this module renders for it. The blocks are filled by the render that creates
    the page."""
    parts = ["# %s\n" % rb.field(slug)]
    for kind in PAGE_KINDS:
        parts.append("\n%s\n%s\n" % (rb.OPENING.format(kind=kind), rb.CLOSING))
    return "".join(parts)
