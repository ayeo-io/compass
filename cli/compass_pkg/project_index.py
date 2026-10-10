# compass_pkg.project_index - the block of the project index
"""The `index` block of the README.md directly in `docs/compass` (RS-13, ADR-051).

One table for each state of an issue, in the order a reader looks for work: Backlog,
Ready, In progress, In review, Done in the last 30 days, Closed. Each readable issue is
in exactly one table, as its slug linked to its issue page by a relative path. An
issue whose manifest cannot be read is listed by slug under Unreadable, and the
Markdown files a person put directly in `docs/compass/` are listed under Other
documents.

The window of the "Done in the last 30 days" table ends at the newest completion
the project holds, not at today, so the index is the same on every day the records
are the same (DCJ-55). The block reads no clock.

Every line of this block depends on the whole project, so it is a `cross` block: a
stale row is an advisory failure of `rendered-blocks-current` for that issue, and no
issue's blocking verdict depends on it.
"""
# DEPENDENCY: standard library (datetime); compass_pkg.render_inputs, rendered_blocks,
# issue_detail, status_words.
from __future__ import annotations

import datetime

from compass_pkg import rendered_blocks as rb
from compass_pkg import status_words
from compass_pkg.render_inputs import CROSS, Part, md_link, relative_to

#: The file the block is written into, relative to the project.
INDEX_REL = "docs/compass/README.md"
WINDOW_DAYS = 30

OPEN_SECTIONS = (("backlog", "Backlog"), ("ready", "Ready"), ("in-progress", "In progress"),
                 ("in-review", "In review"))
DONE_SECTION, CLOSED_SECTION = "Done in the last 30 days", "Closed"
INDEX_TITLE = "# Issues\n"


def index_text():
    """The index file as it is first created: a title and its one block."""
    return "%s\n%s\n%s\n" % (INDEX_TITLE, rb.OPENING.format(kind="index"), rb.CLOSING)


def _completed(task):
    """The date an issue was completed, or None."""
    text = str(task.get("land_timestamp") or "").strip()[:10]
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def newest_completion(scan):
    """The latest completion date among the project's completed issues, or None."""
    dates = [_completed(task) for task in scan.manifests.values()
             if status_words.is_completed(task)]
    dates = [d for d in dates if d]
    return max(dates) if dates else None


def _release(task):
    value = task.get("release_note")
    return rb.cell(value) if value and not isinstance(value, (dict, list)) else "-"


def _row(scan, slug, columns):
    task, facts = scan.manifests[slug], scan.detail(slug)
    link = md_link(slug, relative_to(scan.page_rel(slug), INDEX_REL))
    values = {"approach": rb.cell(facts.approach), "stage": rb.cell(facts.stage or "-"),
              "gates": facts.gates, "release": _release(task),
              "reason": rb.cell(status_words.close_reason(task) or "not recorded"),
              "completed": str(_completed(task) or "-")}
    return "| %s | %s |" % (link, " | ".join(values[c] for c in columns))


_HEADS = {"open": (("approach", "Approach"), ("stage", "Stage"), ("gates", "Gates"),
                   ("release", "Release")),
          "done": (("approach", "Approach"), ("completed", "Completed"), ("release", "Release")),
          "closed": (("approach", "Approach"), ("reason", "Reason"), ("completed", "Completed"),
                     ("release", "Release"))}


def _table(scan, title, slugs, shape):
    columns = [c for c, _ in _HEADS[shape]]
    lines = ["### %s (%d)" % (title, len(slugs)), ""]
    if not slugs:
        return lines + ["None", ""]
    lines += ["| Issue | %s |" % " | ".join(h for _, h in _HEADS[shape]),
              "|---|%s" % ("---|" * len(columns))]
    lines += [_row(scan, slug, columns) for slug in slugs]
    return lines + [""]


def sections(scan):
    """`{title: [slugs]}` of the readable issues, each in exactly one table."""
    newest = newest_completion(scan)
    out = {title: [] for _, title in OPEN_SECTIONS}
    out[DONE_SECTION], out[CLOSED_SECTION] = [], []
    for slug in sorted(scan.manifests):
        state = scan.detail(slug).state
        if state == "done":
            task = scan.manifests[slug]
            when = _completed(task)
            recent = (status_words.is_completed(task) and when and newest
                      and (newest - when).days < WINDOW_DAYS)
            out[DONE_SECTION if recent else CLOSED_SECTION].append(slug)
        else:
            title = dict(OPEN_SECTIONS).get(state)
            out[title or "Backlog"].append(slug)
    out[DONE_SECTION].sort(key=lambda s: (str(_completed(scan.manifests[s])), s), reverse=True)
    return out


def index(inputs, doc_rel):
    scan = inputs.scan
    if scan is None:
        return Part(CROSS, ["No issues were read."])
    found = sections(scan)
    lines = ["Issues: %d%s" % (len(scan.manifests) + len(scan.unreadable),
                               ", %d unreadable" % len(scan.unreadable) if scan.unreadable else ""),
             ""]
    for _, title in OPEN_SECTIONS:
        lines += _table(scan, title, found[title], "open")
    lines += _table(scan, DONE_SECTION, found[DONE_SECTION], "done")
    lines += _table(scan, CLOSED_SECTION, found[CLOSED_SECTION], "closed")
    if scan.unreadable:
        lines += ["### Unreadable", ""]
        lines += ["- %s - %s" % (rb.field(slug), rb.field(why))
                  for slug, why in sorted(scan.unreadable.items())] + [""]
    if scan.flat_documents:
        lines += ["### Other documents", ""]
        lines += ["- %s" % md_link(name, relative_to("docs/compass/" + name, doc_rel))
                  for name in scan.flat_documents] + [""]
    while lines and not lines[-1].strip():
        lines.pop()
    return Part(CROSS, lines)


def row_lines(lines, slug):
    """The lines of an index block that begin the row of `slug`."""
    prefix = "| [%s](" % slug.replace("[", "\\[").replace("]", "\\]")
    return [x for x in lines if x.startswith(prefix)]


RENDERERS = {"index": index}
