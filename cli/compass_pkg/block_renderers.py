# compass_pkg.block_renderers - the text of each rendered block, from a snapshot
"""Pure renderers for the rendered block kinds (ADR-051).

A renderer takes a `RenderInputs` snapshot of the records and the project-
relative path of the document it renders into, and returns a `Part`: the lines
of the block and whether they depend on this issue's own records (`own`) or on
other issues or the project (`cross`). It reads no clock and no git
configuration, so the same records give the same text on every machine and a
second render changes no byte. `render_inputs.gather` is the only function
that touches the disk before the renderers run.

Every line copied from a record goes through `rendered_blocks.field`,
`cell` or `neutralise`, so recorded text cannot be read as a marker.
They are called through the module, so a test can replace one.

This module renders the kinds every document shares (`coverage`, `gates`, `dod`, `dor`,
`artifacts`, `evidence`, `follow-ups`, `decisions-taken`) and the verification note. The
page kinds are in `issue_page`, the index in `project_index`; `RENDERERS` holds all of
them. A kind in `rendered_blocks.KINDS` with no entry in `RENDERERS` is left as it is.
"""
# DEPENDENCY: standard library (os); compass_pkg.render_inputs, item_records,
# rendered_blocks, issue_page, project_index.
from __future__ import annotations

from compass_pkg import item_records
from compass_pkg import rendered_blocks as rb
from compass_pkg.render_inputs import (CROSS, OWN, Part, RenderInputs, code as _code,  # noqa: F401
                                       gather, link as _link, link_target as _link_target,
                                       shown_path as _shown_path)


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
        rows = item_records.items(inputs.task, None, inputs.get_view(), which)
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
        item_records.MET_CARRIED: "met, " + ids + " resolved",
        item_records.PAGE_TICK: "ticked on the page before 7.0.0 (%s)" % ids,
        item_records.CARRIED: "carried to ship, " + ids,
        item_records.OPEN: "open",
    }[item.state]


def artifacts(inputs, doc_rel):
    rows = [a for a in inputs.list_of("artifacts") if a.get("status") != "omitted"]
    if not rows:
        return Part(OWN, ["No documents registered yet."])
    approved = sum(1 for a in rows if a.get("status") == "approved")
    lines = ["Documents: %d registered, %d approved" % (len(rows), approved), "",
             "| Document | Status | Approved by | Why it exists |", "|---|---|---|---|"]
    for a in rows:
        name = str(a.get("kind", "?"))
        if isinstance(a.get("round"), int):
            # One row per round of a kind that repeats, each named by its own entry id.
            name += ", round %d (%s)" % (a["round"], a.get("id", "?"))
        kind = rb.cell(name)
        target = _link_target(inputs, a["path"]) if a.get("path") else None
        written = target in inputs.present
        shown = (_link(inputs, a["path"], doc_rel, name) if written else None) \
            or kind
        # A name or meaning the catalogue gives the document is shown when the entry holds it.
        for key, word in (("traditional_name", "traditional name"), ("stands_for", "stands for")):
            if a.get(key):
                shown += ", %s: %s" % (word, rb.cell(a[key]))
        status = a.get("status", "?") if written else "not written yet"
        by = a.get("approved_by") if written and a.get("status") == "approved" else None
        lines.append("| %s | %s | %s | %s |" % (
            shown, rb.cell(status), rb.cell(by) if by else "-", rb.cell(a.get("reason") or "")))
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


#: A quick fix has one scenario; the note stays one screen however many it has.
NOTE_SCENARIOS = 6


def verification_note(inputs, doc_rel):
    scenarios = inputs.list_of("scenarios")
    lines = []
    if scenarios:
        lines += ["| Scenario | Test | Red | Green |", "|---|---|---|---|"]
        for s in scenarios[:NOTE_SCENARIOS]:
            sid = str(s.get("id", "?"))
            green = inputs.records.get(("green", sid)) or inputs.records.get(("acceptance", sid))
            red = inputs.records.get(("red", sid))
            tests = ", ".join(_code(x) for x in s.get("tests") or []) or "-"
            lines.append("| %s | %s | %s | %s |" % (
                rb.cell("%s - %s" % (sid, s.get("title", ""))), tests,
                _code(red) if red else "-", _code(green) if green else "-"))
        if len(scenarios) > NOTE_SCENARIOS:
            lines.append("and %d more scenarios" % (len(scenarios) - NOTE_SCENARIOS))
    else:
        lines.append("No scenario recorded.")
    gate_rows = inputs.list_of("gates")
    if gate_rows:
        lines += ["", "Gates:"]
        lines += ["- %s: %s" % (_code(g.get("id", "?")), rb.field(g.get("status", "?")))
                  for g in gate_rows]
    changed = [c.get("path") for c in inputs.list_of("changed_files")
               if c.get("path") and not str(c["path"]).startswith("docs/compass/")]
    if changed:
        lines += ["", "Changed files:"]
        lines += ["- %s" % _code(p) for p in changed[:12]]
        if len(changed) > 12:
            lines.append("- and %d more" % (len(changed) - 12))
    release = inputs.task.get("release_note")
    if release and not isinstance(release, (dict, list)):
        lines += ["", "Release: %s" % rb.field(release)]
    return Part(OWN, lines)


#: Kind to renderer. A new kind is one entry here (or in the module that owns it) and one
#: name in `rendered_blocks.KINDS`.
RENDERERS = {
    "coverage": coverage,
    "gates": gates,
    "dod": _exit_list("dod"),
    "dor": _exit_list("dor"),
    "artifacts": artifacts,
    "evidence": evidence,
    "follow-ups": follow_ups,
    "decisions-taken": decisions_taken,
    "verification-note": verification_note,
}


def _add_modules():
    from compass_pkg import issue_page, project_index
    RENDERERS.update(issue_page.RENDERERS)
    RENDERERS.update(project_index.RENDERERS)


_add_modules()


def issue_page_text(slug):
    """The issue page as it is first created: a title and the page's blocks, in order.
    The blocks are filled by the render that creates the page."""
    from compass_pkg.issue_page import PAGE_KINDS
    parts = ["# %s\n" % rb.field(slug)]
    for kind in PAGE_KINDS:
        parts.append("\n%s\n%s\n" % (rb.OPENING.format(kind=kind), rb.CLOSING))
    return "".join(parts)


NOTE_TITLE = "# Verification note - %s\n"


def verification_note_text(slug):
    """The verification note as `quick-fix finish` first creates it: a title and its one block."""
    return "%s\n%s\n%s\n" % (NOTE_TITLE % rb.field(slug),
                                rb.OPENING.format(kind="verification-note"), rb.CLOSING)
