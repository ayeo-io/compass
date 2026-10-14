# compass_pkg.dependencies_block - the `dependencies` rendered block
"""The block that lists an issue's `depends_on` entries in the design's Risks and dependencies.

Each entry is one line, `- <slug> - <reason> - until <until> - <word>`. The word is the one
the board panel shows for the entry - `met`, `waiting`, `not found` or `unreadable` - and
comes from the same `lifecycle.judge` result through the panel's own function, so the two
cannot disagree (ADR-062). An entry that is not the documented shape is listed with the
line `compass issue lint` prints for it. An issue with no `depends_on` reads `None`.

The block reads other issues' manifests from the project scan, as the issue page does
(ADR-062 decision 7), so it is a `cross` part: `rendered-blocks-current` reports a stale
block as an advisory failure, and a dependency's change never blocks this issue's check.
"""
# DEPENDENCY: compass_pkg.render_inputs, lifecycle, board_page (the panel's word),
# issue_page (the reader over the scan), rendered_blocks; block_renderers registers
# RENDERERS through _add_modules.
from __future__ import annotations

from compass_pkg import lifecycle
from compass_pkg import rendered_blocks as rb
from compass_pkg.render_inputs import CROSS, Part

NONE = "None"
#: The word for an entry when no other issue was read, so nothing could be judged.
NOT_JUDGED = "not judged"


def dependencies(inputs, doc_rel):
    from compass_pkg import board_page, issue_page

    good, faults = lifecycle.entries(inputs.task)
    if not good and not faults:
        return Part(CROSS, [NONE])
    read = issue_page._reader(inputs.scan)
    lines = []
    if read is None:
        for entry in good:
            lines.append(_line(entry["issue"], entry["reason"], entry["until"], NOT_JUDGED))
    else:
        unreadable = set(inputs.scan.unreadable)
        for dep in lifecycle.judge(inputs.task, inputs.slug, read):
            lines.append(_line(dep.issue, dep.reason, dep.until,
                               board_page._dependency_word(dep.row(), unreadable)))
    lines += ["- " + rb.field(fault) for fault in faults]
    return Part(CROSS, lines)


def _line(issue, reason, until, word):
    return "- %s - %s - until %s - %s" % (rb.field(issue), rb.field(reason), rb.field(until),
                                          word)


RENDERERS = {"dependencies": dependencies}
