# compass_pkg.migrate_blocks - what `compass issue migrate` adds for rendered blocks
"""The additions 7.0.0 makes to an issue written before rendered blocks.

Migration only adds lines and records. It never rewrites an archived table and
never changes a line of a document (ADR-020, through ADR-051):

- an empty `dod` marker pair after the Definition of Done section of the
  verification report, with the registry digests that name the report re-stamped
  so the report keeps its status;
- the records the report's boxes held: `meets` on the evidence a tag names,
  `defers` on the follow-up a tag names, and a `page_ticks` entry for each ticked
  box (a page tick never counts as a person's approval);
- an empty verification note for each quick fix closed as completed.

A tag that names an id the manifest does not hold, or evidence of a type the
Definition of Done does not accept, writes no record. The item stays open and the
migration reports the issue, the item and the id. A report with no Definition of
Done heading gets no marker and no record, and is reported.

`run` computes the change and, unless `would`, writes it. The dry run and the
apply share it, so the dry run cannot promise more or less than the apply does.
Only this module reads the tags on a page; the rest of Compass reads records.
"""
# DEPENDENCY: standard library (copy, os, re); yaml; compass_pkg.core,
# compass_pkg.doc_sections, compass_pkg.item_records, compass_pkg.rendered_blocks,
# compass_pkg.status_words and, lazily, compass_pkg.migrate, compass_pkg.checks,
# compass_pkg.effective, compass_pkg.impl_versions.
from __future__ import annotations

import os
import re

from compass_pkg import doc_sections, item_records, rendered_blocks as rb, status_words
from compass_pkg.core import (FOUND, REFUSED, canonical_shape, docs_dir, resolve_artifact,
                              unregistered_document)
from compass_pkg.stable_ids import APPROACH_QUICK_FIX

REPORT = "verification-report"
NOTE = "verification-note"
HEADING = doc_sections.list_heading("verify", "exit")
PAIR = ("dod",)

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
        return effective.view_or_legacy(task_dir)
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
    by_statement = {doc_sections.normal(statement): check for check, statement in listed}
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


def _insert_pair(text, end):
    """The text with an empty `dod` pair before line `end` (a line index of `text.split`),
    or None when the result would not parse as that block."""
    eol = rb.line_ending(text)
    lines = rb.split_lines(text)
    at = min(end, len(lines))
    pair = [rb.OPENING.format(kind="dod") + eol, rb.CLOSING + eol]
    if at and not lines[at - 1].endswith("\n"):
        lines[at - 1] += eol
    new = "".join(lines[:at] + pair + lines[at:])
    try:
        parsed = rb.parse(new)
    except rb.MarkerError:
        return None
    return new if [b.kind for b in parsed.blocks].count("dod") == 1 else None


def _restamp(data, old_digest, new_digest):
    """Move the digests the registry recorded for the report from the old masked digest to
    the new one: the report's own and the `upstream` of any document that names it. A digest
    that was already stale is left stale. Returns how many were moved."""
    moved = 0
    for entry in data.get("artifacts") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") == REPORT and entry.get("digest") == old_digest:
            entry["digest"] = new_digest
            moved += 1
        upstream = entry.get("upstream")
        if isinstance(upstream, dict) and upstream.get(REPORT) == old_digest:
            upstream[REPORT] = new_digest
            moved += 1
    return moved


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
    """Insert the pair and write the records. Returns `(manifest changed, edit)` where `edit`
    is `(path, new text, old digest)` for the report or None."""
    slug = os.path.basename(os.path.normpath(task_dir))
    path, why = _report_path(task_dir, project)
    if why:
        out.problems.append("%s: the verification-report is not edited: %s." % (slug, why))
    if not path:
        return False, None
    try:
        with open(path, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        out.problems.append("%s: %s could not be read as UTF-8, so it was left as it was."
                            % (slug, os.path.basename(path)))
        return False, None
    try:
        parsed = rb.parse(text, path)
    except rb.MarkerError as exc:
        out.problems.append("%s: %s has a render marker that does not parse (%s), so it was left "
                            "as it was." % (slug, os.path.basename(path), exc))
        return False, None
    lines = text.split("\n")
    mask = doc_sections.comment_mask(lines)
    found = doc_sections.section(lines, mask, HEADING)
    if found is None:
        out.problems.append("%s: %s has no \"%s\" heading, so it gets no marker and no record."
                            % (slug, os.path.basename(path), HEADING))
        return False, None
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
    edit = None
    if not any(b.kind == "dod" for b in parsed.blocks):
        new = _insert_pair(text, end)
        if new is None:
            out.problems.append("%s: %s cannot hold a dod marker pair after its Definition of "
                                "Done section, so none was added." % (slug, os.path.basename(path)))
        else:
            edit = (path, new, rb.masked_digest(path))
            out.notes.append("%s 1 dod marker pair in %s" % (
                _tense(would, "insert", "inserted"), source))
            if any(isinstance(a, dict) and a.get("kind") == REPORT and a.get("digest")
                   for a in data.get("artifacts") or []):
                out.notes.append("%s the registry digest of %s" % (
                    _tense(would, "re-stamp", "re-stamped"), REPORT))
    return bool(total), edit


def _unsafe_path(task_dir, rel, project, allow_work=False):
    """Why a path from a manifest cannot be written, or None (the render's rule)."""
    from compass_pkg import render_cmd
    return render_cmd.unsafe_document_path(task_dir, rel, project, allow_work)


def _verification_note(task_dir, data, project, would, out):
    """An empty note for a quick fix closed as completed. Returns whether `data` changed."""
    if not status_words.is_completed(data) \
            or canonical_shape(data.get("delivery_approach")) != APPROACH_QUICK_FIX:
        return False
    from compass_pkg.block_renderers import verification_note_text
    slug = os.path.basename(os.path.normpath(task_dir))
    entry = next((a for a in data.get("artifacts") or []
                  if isinstance(a, dict) and a.get("kind") == NOTE), None)
    rel = str((entry or {}).get("path") or "") or docs_dir(task_dir).rstrip("/") + "/" + NOTE + ".md"
    path = os.path.join(project, *rel.split("/"))
    why = _unsafe_path(task_dir, rel, project)
    if why:
        # A registered path comes from a manifest, so it is checked as the render checks one
        # before anything is created or written.
        out.problems.append("%s: the verification note at %s is not written: %s." % (slug, rel, why))
        return False
    if os.path.isfile(path) and entry is not None:
        return False
    out.notes.append("%s 1 verification note (%s)" % (_tense(would, "write", "wrote"), rel))
    # Registered before the dry run returns: the dry run's copy of the manifest then
    # holds the entry the apply adds, and the status step counts it as the apply does.
    if entry is None:
        data.setdefault("artifacts", []).append({
            "id": "ART-VERIFICATION_NOTE", "kind": NOTE, "status": "draft",
            "depth": "lightweight", "path": rel,
            "reason": "One screen of what was checked, for a reader (written by migration)"})
    if would:
        return True
    if not os.path.isfile(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(verification_note_text(slug))
    return entry is None


def register_planned(task_dir, data):
    """Add to the dry run's in-memory manifest `data` the registry entries `run` adds in
    the apply. The notes are discarded: `run` prints them from the disk."""
    from compass_pkg import migrate as base
    _verification_note(task_dir, data, base._project_root(task_dir), True, Outcome())


def run(task_dir, would, out=None):
    """Add the markers, records and notes of one issue; returns the `Outcome`."""
    from compass_pkg import migrate as base
    out = out or Outcome()
    path, loaded = base._read_manifest(task_dir)
    if not isinstance(loaded, dict):
        return out
    data = loaded
    project = base._project_root(task_dir)
    changed_records, edit = _definition_of_done(task_dir, data, project, would, out)
    noted = _verification_note(task_dir, data, project, would, out)
    if would:
        return out
    if edit is not None:
        report_path, new_text, old_digest = edit
        new_digest = "sha256:" + _hex(rb.masked_text(new_text))
        if _restamp(data, old_digest, new_digest):
            changed_records = True
    if changed_records or noted:
        base._write_manifest(path, data)
    if edit is not None:
        report_path, new_text, _ = edit
        rb.write_rendered(report_path, new_text, rb.file_digest(report_path))
    return out


def _hex(masked):
    import hashlib
    return hashlib.sha256(masked.encode("utf-8")).hexdigest()


def pin_stale_generation(task_dir, would, out):
    """Pin the stored generation of an issue whose generation records an implementation major
    the CLI no longer has, through the `--config` path (ADR-051). An issue whose generation
    records only majors the CLI has is not touched."""
    from compass_pkg import effective, impl_versions
    from compass_pkg.core import load_manifest
    try:
        data, _ = load_manifest(task_dir)
        stale = sorted(impl_versions.refusals(task_dir, data).checks)
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
