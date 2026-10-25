# compass_pkg.header_block - the `document-header` rendered block
"""The block that opens every catalogue document written from a template.

Six lines, each read from a record and none from the file system or the clock, so
the same records give the same bytes on every render:

- the issue and its delivery approach, from the manifest;
- the kind's stage and owner, from the catalogue;
- the document's status, from the artifact registry;
- the date: the day of `approved_at` when the document is approved, else the
  manifest's `created`. A later render on another day changes nothing;
- Reads: the registered documents of kinds whose stage comes before this kind's
  stage, ordered by stage and then file name. A document is listed because its
  registry entry holds a path, never because its file exists, so deleting a file
  with no record changed leaves the block as it is;
- the kind's audience, from the catalogue, on one line.

Status and Date are separate lines, so an approval changes exactly two lines.
`placeholder_lines` gives the lines `compass issue template show` prints inside the
block, where no issue's records are read.
"""
# DEPENDENCY: compass_pkg.render_inputs, rendered_blocks, artifact_kinds, stable_ids, core
# (display_shape); block_renderers registers RENDERERS through _add_modules.
from __future__ import annotations

import posixpath

from compass_pkg import artifact_kinds
from compass_pkg import rendered_blocks as rb
from compass_pkg.core import display_shape
from compass_pkg.render_inputs import OWN, Part, code, link, link_target
from compass_pkg.stable_ids import STAGE_IDS

#: Registry states whose document no longer stands for its kind, so no header lists it.
_NOT_READ = ("superseded", "omitted")


def _flat(text):
    return " ".join(str(text or "").split())


def _lines(issue, approach, stage, owner, status, date, reads, audience):
    return [
        "> **Issue:** %s · **Approach:** %s" % (issue, approach),
        "> **Stage:** %s · **Owner:** %s" % (stage, owner),
        "> **Status:** %s" % status,
        "> **Date:** %s" % date,
        "> **Reads:** %s" % reads,
        "> **Audience:** %s" % audience,
    ]


def placeholder_lines(entry, slug=None):
    """The block's lines for `template show`: the kind's real stage, owner and audience
    from its catalogue `entry`, the issue's slug when one is named, and a placeholder for
    each fact only an issue's records give."""
    entry = entry or {}
    return _lines(slug or "{{ISSUE_SLUG}}", "{{APPROACH}}", _flat(entry.get("stage")),
                  _flat(entry.get("owner")), "{{STATUS}}", "{{DATE}}", "{{READS}}",
                  _flat(entry.get("audience")))


def _rank(stage):
    return STAGE_IDS.index(stage) if stage in STAGE_IDS else None


def _own_entry(inputs, doc_rel, catalogue):
    """The registry entry and kind of the document at `doc_rel`: the entry whose path
    names it, else no entry and the catalogue kind whose file name it has."""
    for entry in inputs.list_of("artifacts"):
        if entry.get("path") and link_target(inputs, entry["path"]) == doc_rel:
            return entry, entry.get("kind")
    name = posixpath.basename(doc_rel)
    for kind, body in catalogue.items():
        if isinstance(body, dict) and body.get("file") == name:
            return {}, kind
    return {}, None


def _reads(inputs, doc_rel, here, catalogue):
    found = set()
    for entry in inputs.list_of("artifacts"):
        path = entry.get("path")
        if not path or entry.get("status") in _NOT_READ:
            continue
        target = link_target(inputs, path)
        body = catalogue.get(entry.get("kind"))
        rank = _rank(_flat((body if isinstance(body, dict) else {}).get("stage")))
        if target is None or target == doc_rel or rank is None or rank >= here:
            continue
        found.add((rank, posixpath.basename(target), str(path)))
    shown = [link(inputs, path, doc_rel, name) or code(name) for _, name, path in sorted(found)]
    return ", ".join(shown) or "none"


def document_header(inputs, doc_rel):
    catalogue = artifact_kinds.catalogue(inputs.get_view())
    entry, kind = _own_entry(inputs, doc_rel, catalogue)
    body = catalogue.get(kind) if kind else None
    body = body if isinstance(body, dict) else {}
    task = inputs.task
    status = _flat(entry.get("status")) or "not registered"
    approved = str(entry.get("approved_at") or "")
    date = approved[:10] if status == "approved" and approved else str(task.get("created") or "")
    stage = _flat(body.get("stage"))
    here = _rank(stage)
    approach = display_shape(task.get("delivery_approach"))
    return Part(OWN, _lines(
        rb.field(inputs.slug), rb.field(approach or "not assessed"),
        rb.field(stage or "not in the catalog"),
        rb.field(_flat(body.get("owner")) or "not in the catalog"),
        rb.field(status), rb.field(date or "not recorded"),
        _reads(inputs, doc_rel, here, catalogue) if here is not None else "none",
        rb.field(_flat(body.get("audience")) or "not in the catalog")))


RENDERERS = {"document-header": document_header}
