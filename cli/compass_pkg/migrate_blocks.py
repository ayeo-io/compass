# compass_pkg.migrate_blocks - what `compass issue migrate` adds for rendered blocks
"""The records 7.0.0 adds to an issue written before rendered blocks.

Migration only adds records. It never rewrites an archived table and never
changes a line of a document (ADR-020, through ADR-051). It writes the records
the verification report's boxes held: `meets` on the evidence a tag names,
`defers` on the follow-up a tag names, and a `page_ticks` entry for each ticked
box (a page tick never counts as a person's approval).

Before 9.0.0 it also added an empty `dod` marker pair to the report and an empty
verification note to each completed quick fix. 9.0.0 renders no block and writes
no note (ADR-091), so the documents are left as they are.

A tag that names an id the manifest does not hold, or evidence of a type the
Definition of Done does not accept, writes no record. The item stays open and the
migration reports the issue, the item and the id. A report with no Definition of
Done heading gets no record, and is reported.

`run` computes the change and, unless `would`, writes it. The dry run and the
apply share it, so the dry run cannot promise more or less than the apply does.
Only this module reads the tags on a page; the rest of Compass reads records.
"""
# DEPENDENCY: standard library (copy, os, re); yaml; compass_pkg.core,
# compass_pkg.doc_sections, compass_pkg.item_records,
# compass_pkg.status_words and, lazily, compass_pkg.migrate, compass_pkg.checks,
# compass_pkg.effective, compass_pkg.impl_versions.
from __future__ import annotations

import os
import re

from compass_pkg import doc_sections, item_records, status_words
from compass_pkg.core import (FOUND, REFUSED, resolve_artifact,
                              unregistered_document)

REPORT = "verification-report"
HEADING = doc_sections.list_heading("verify", "exit")
#: Earlier statements of a Definition of Done item, as a report written before 7.0.0 holds
#: them. Those reports cite the report's sections by number; the shipped statements now name
#: them (ADR-064). A box is matched by its words before its place, so without these a report
#: with fewer boxes than the list would leave its items open.
FORMER_STATEMENTS = {
    "dod-every-scenario-passes": (
        "Every scenario passes - §1 is all PASS; the spec, read as the acceptance suite, "
        "is green.",),
    "dod-suite-green": ("TDD suite green - §2 links the record of the full suite passing.",),
    "dod-coverage-floor": (
        "Coverage meets the \"Tested before it lands\" guardrail's floor (`G1`) - evidence "
        "in §2.",),
}

_ITEM = re.compile(r"^\s*-\s+\[([ xX])\]\s*(.*)")
_EVIDENCE_TAG = re.compile(r"\(evidence:\s*(EV-[^)]+)\)")
# Both id spellings and both tag words: archived reports use an older tag word and the
# `BF-` id prefix.
_FOLLOW_UP_TAG = re.compile(r"\((?:follow-up|backfill):\s*((?:FU|BF)-[^)]+)\)")


def _tense(would, base, past):
    return ("would " + base) if would else past


def _plural(count, word):
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


class Outcome:
    """`notes` are changes (written, or to be written on a dry run). `problems` are items
    that stay open or documents that were not read; they are reported on every run."""

    def __init__(self):
        self.notes = []
        self.problems = []


def _view(task_dir):
    from compass_pkg import effective
    try:
        return effective.effective_for(task_dir)
    except Exception:                                    # noqa: BLE001
        # A configuration that cannot be read is judged by the shipped lists, as a reader
        # does for an issue with none.
        return None


def _report_path(task_dir, project):
    """`(path, why)`: the report to edit, or None and the reason it must not be edited. A path
    from the registry is checked as a note's is, before the report is read or written; the
    flat copy beside the manifest is also allowed, since it sits in the issue's own folder."""
    state, path, _ = resolve_artifact(task_dir, REPORT)
    if state == REFUSED:
        return None, "its registered path resolves outside the project"
    if state != FOUND:
        path = unregistered_document(task_dir, REPORT + ".md")
    if not path:
        return None, None
    rel = os.path.relpath(os.path.abspath(path), project).replace(os.sep, "/")
    why = _unsafe_path(task_dir, rel, project, allow_work=True)
    return (None, why) if why else (path, None)


def _boxes(lines, start, end):
    """`[(ticked, text)]` of the boxes in `lines[start:end]` outside comments. A continuation
    line is an indented line after a box."""
    mask = doc_sections.comment_mask(lines)
    shown = doc_sections.visible(lines)
    boxes = []
    for index in range(start, end):
        if mask[index]:
            continue
        line = shown[index].rstrip("\r")
        found = _ITEM.match(line)
        if found:
            boxes.append([found.group(1).lower() == "x", found.group(2)])
        elif boxes and line.startswith(" ") and line.strip():
            boxes[-1][1] += " " + line.strip()
    return [(ticked, text) for ticked, text in boxes]


def _map_boxes(boxes, listed):
    """`[check id or None]` for each box: the item whose statement the box reads, else the
    item at the box's place when the report has as many boxes as the list has items."""
    by_statement = {doc_sections.normal(old): check for check, _ in listed
                    for old in FORMER_STATEMENTS.get(check, ())}
    by_statement.update((doc_sections.normal(statement), check) for check, statement in listed)
    found, taken = [], set()
    for ticked, text in boxes:
        check = by_statement.get(doc_sections.normal(text))
        found.append(check if check not in taken else None)
        taken.add(check)
    if len(boxes) == len(listed):
        for index, check in enumerate(found):
            place = listed[index][0]
            if check is None and place not in taken:
                found[index] = place
                taken.add(place)
    return found


def _records(slug, data, boxes, checks, source, out):
    """Write the item records the boxes hold into `data`; returns how many were new."""
    from compass_pkg.checks import _DOD_ACCEPTED_EVIDENCE_TYPES
    evidence = {e.get("id"): e for e in data.get("evidence") or [] if isinstance(e, dict)}
    follow_ups = {f.get("id"): f for f in data.get("follow_ups") or [] if isinstance(f, dict)}
    ticks = data.setdefault("page_ticks", [])
    made = {"meets": 0, "defers": 0, "page ticks": 0}
    for (ticked, text), check in zip(boxes, checks):
        if check is None:
            out.problems.append("%s: a box of the Definition of Done reads no item of the list, "
                                "so nothing is recorded for it: %s" % (slug, " ".join(text.split())[:80]))
            continue
        tagged = _EVIDENCE_TAG.search(text)
        if tagged:
            ev_id = tagged.group(1).strip()
            entry = evidence.get(ev_id)
            if entry is None:
                out.problems.append("%s: %s: the tag names evidence %s, which the manifest does "
                                    "not hold. Nothing is recorded for it%s." % (
                                        slug, check, ev_id, "" if ticked else ", so the item stays open"))
            elif entry.get("type") not in _DOD_ACCEPTED_EVIDENCE_TYPES:
                out.problems.append("%s: %s: the tag names evidence %s of type %s, which the "
                                    "Definition of Done does not accept. Nothing is recorded "
                                    "for it%s." % (slug, check, ev_id, entry.get("type"),
                                                   "" if ticked else ", so the item stays open"))
            elif check not in (entry.get("meets") or []):
                entry["meets"] = list(entry.get("meets") or []) + [check]
                made["meets"] += 1
        carried = _FOLLOW_UP_TAG.search(text)
        if carried:
            fu_id = carried.group(1).strip()
            entry = follow_ups.get(fu_id)
            if entry is None:
                out.problems.append("%s: %s: the tag names follow-up %s, which the manifest "
                                    "does not hold. Nothing is recorded for it%s." % (
                                        slug, check, fu_id, "" if ticked else ", so the item stays open"))
            elif entry.get("status") not in ("outstanding", "resolved"):
                out.problems.append("%s: %s: follow-up %s has the status %s, which carries no "
                                    "item. Nothing is recorded for it." % (
                                        slug, check, fu_id, entry.get("status")))
            elif entry.get("defers") not in (None, "", check):
                out.problems.append("%s: %s: follow-up %s already defers %s and a follow-up "
                                    "defers one item. Nothing is recorded for it%s." % (
                                        slug, check, fu_id, entry.get("defers"),
                                        "" if ticked else ", so the item stays open"))
            elif entry.get("defers") != check:
                entry["defers"] = check
                made["defers"] += 1
        if ticked and not any(isinstance(t, dict) and t.get("check") == check
                              and t.get("source") == source for t in ticks):
            ticks.append({"check": check, "source": source})
            made["page ticks"] += 1
    if not ticks:
        data.pop("page_ticks")
    return made


def _definition_of_done(task_dir, data, project, would, out):
    """Write the records the report's boxes hold. Returns whether `data` changed. Since
    9.0.0 the report is left as it is: no block is rendered into it (ADR-091)."""
    slug = os.path.basename(os.path.normpath(task_dir))
    path, why = _report_path(task_dir, project)
    if why:
        out.problems.append("%s: the verification-report is not edited: %s." % (slug, why))
    if not path:
        return False
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        out.problems.append("%s: %s could not be read as UTF-8, so it was left as it was."
                            % (slug, os.path.basename(path)))
        return False
    lines = text.split("\n")
    mask = doc_sections.comment_mask(lines)
    found = doc_sections.section(lines, mask, HEADING)
    if found is None:
        out.problems.append("%s: %s has no \"%s\" heading, so it gets no record."
                            % (slug, os.path.basename(path), HEADING))
        return False
    start, end = found
    boxes = _boxes(lines, start, end)
    listed = item_records.listed_checks(_view(task_dir), "dod")
    checks = _map_boxes(boxes, listed)
    source = os.path.relpath(path, project).replace(os.sep, "/")
    made = _records(slug, data, boxes, checks, source, out)
    total = sum(made.values())
    if total:
        parts = ", ".join("%d %s" % (n, word) for word, n in made.items() if n)
        out.notes.append("%s %s (%s)" % (_tense(would, "write", "wrote"),
                                         _plural(total, "item record"), parts))
    return bool(total)


def _unsafe_path(task_dir, rel, project, allow_work=False):
    """Why a path from a manifest cannot be written, or None (the render's rule)."""
    from compass_pkg import doc_paths
    return doc_paths.unsafe_document_path(task_dir, rel, project, allow_work)


def run(task_dir, would, out=None):
    """Add the markers, records and notes of one issue; returns the `Outcome`."""
    from compass_pkg import migrate as base
    out = out or Outcome()
    path, loaded = base._read_manifest(task_dir)
    if not isinstance(loaded, dict):
        return out
    data = loaded
    project = base._project_root(task_dir)
    changed_records = _definition_of_done(task_dir, data, project, would, out)
    if would:
        return out
    if changed_records:
        base._write_manifest(path, data)
    return out


def pin_stale_generation(task_dir, would, out):
    """Pin the stored generation of an issue whose generation records an implementation major
    the CLI no longer has, through the `--config` path (ADR-051). An issue whose generation
    records only majors the CLI has is not touched."""
    from compass_pkg import effective, impl_versions
    from compass_pkg.core import load_manifest
    try:
        data, _ = load_manifest(task_dir)
        stale = sorted(impl_versions.refusals(task_dir, data).checks)
    except effective.MajorRefusal:
        # Pinning across a resolver or schema major is the repair's call, one issue at a
        # time, so the migrate names it and goes on. A closed issue keeps the generation it
        # closed under and `migrate --config` refuses it, so a note naming that fix would
        # send the person in a circle.
        if status_words.is_closed(data):
            return
        slug = os.path.basename(os.path.normpath(task_dir))
        out.notes.append("%s: its generation was built by another resolver or schema major, "
                         "so it was not pinned; run `%s --issue %s`"
                         % (slug, effective.FIX_MAJOR, slug))
        return
    except Exception:                                    # noqa: BLE001
        return
    if not stale:
        return
    held = effective.generation.number(data)
    target = (held or 0) + 1
    others = effective.generation.unwritten_files(task_dir, target)
    if others:
        # The pin's commit would refuse this folder rather than delete files it did not
        # write, which the copy check never judged. Asked here, so the dry run and the
        # apply report the same open item and the rest of the issue is still migrated.
        out.problems.append(
            "%s: generation %s %s pinned to the installed versions, because "
            "generations/%s/ holds %s, which a generation commit does not write and will "
            "not delete. %s, then re-run the migrate" % (
                os.path.basename(os.path.normpath(task_dir)), held,
                _tense(would, "not be", "was not"), target, ", ".join(others),
                effective.generation.unwritten_advice(task_dir, target, others)))
        return
    out.notes.append("%s generation %s to the installed versions, because it records a major of "
                     "%s that this CLI lacks" % (_tense(would, "pin", "pinned"), held,
                                                 ", ".join(stale)))
    if not would:
        effective.migrate_generation(task_dir, closed_ok=True)
