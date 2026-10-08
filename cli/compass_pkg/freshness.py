# compass_pkg.freshness - which documents of an issue are stale, behind a capability
"""Record the digest of a document when it is written, and say when it is stale.

With the capability `artifact-freshness` on, `compass issue artifact` stamps
the registry entry of a document with `digest` (its own file) and `upstream`
(the digest of each artifact it `depends_on`, as the artifact catalogue
declares). Nothing else writes either field.

Staleness is computed, never stored. A document is stale when:

- an artifact it depends on has other bytes now than the one recorded, is
  missing now, or was missing when the document was written and is there now;
- or an artifact it depends on has a file that cannot be read now;
- or an artifact it depends on is stale itself, so staleness passes down the
  graph, through tracked documents only;
- or its own `upstream` record is not a map, which fails closed.

A document with no `upstream` record is not tracked, so a project that turns
the capability on has nothing stale until its documents are written again.
A presence check never writes a record, so it never clears staleness: only
writing the document again, against the upstream as it is now, does.

Where staleness blocks:

- `compass ship-commit` refuses to land while any tracked document is stale;
- a stage that consumes a document (`CONSUMES`) refuses entry while it is
  stale: `compass check` fails once the issue has reached the stage, and
  `compass next` names the document.

With the capability off, or for an issue read without a configuration, every
function here returns nothing and no reader changes. The digest is the one
`review_records` uses for the inputs of a judged check.
"""
# DEPENDENCY: standard library (dataclasses); compass_pkg.review_records and
# compass_pkg.stage_lists, which read a file's digest and the stage the issue
# has reached.
from __future__ import annotations

from dataclasses import dataclass

from compass_pkg import review_records, stage_lists
from compass_pkg.stable_ids import STAGE_IMPLEMENT, STAGE_SHIP

CAPABILITY = "artifact-freshness"

#: The documents a stage builds from. Entry to the stage is refused while one
#: is stale. Every document blocks land, whether or not a stage consumes it.
CONSUMES = {STAGE_IMPLEMENT: ("acceptance-criteria", "technical-design")}

#: The stage whose reaching makes a document that no stage consumes block.
LAND_STAGE = STAGE_SHIP

#: The label `compass check --json` gives the rows of this pass.
GUARDRAIL = "artifact-freshness"


def enabled(view):
    return view is not None and bool(view.capabilities.get(CAPABILITY))


def graph(view):
    """`{artifact id: [ids it depends on]}` from the artifact catalogue."""
    found = {}
    for artifact_id, body in ((view.config.get("artifacts") or {}).items()):
        if isinstance(body, dict) and isinstance(body.get("depends_on") or [], list):
            found[artifact_id] = [str(one) for one in (body.get("depends_on") or [])]
    return found


#: What `_digest` gives for a file that exists and cannot be read. It is not a
#: digest, so it never equals a recorded one: the reader reports the document as
#: stale instead of failing.
UNREADABLE = "unreadable"


def _digest(task, task_dir, artifact_id):
    try:
        return review_records.file_digest(
            review_records.input_path(task, task_dir, artifact_id))
    except OSError:
        return UNREADABLE


def unreadable(view, task, task_dir, kind):
    """The ids among `kind` and the artifacts it depends on whose file exists
    and cannot be read. Empty when the capability is off. `compass issue
    artifact` refuses to record a document while any is unreadable."""
    if not enabled(view):
        return []
    return [one for one in [kind, *(graph(view).get(kind) or [])]
            if _digest(task, task_dir, one) == UNREADABLE]


def stamp(view, task, task_dir, entry):
    """Record the digests on a registry entry, as the document is written.
    Returns True when the entry changed.

    An entry whose file has the bytes the record holds, and that already
    holds an `upstream` record, is left alone: registering a document again
    without changing it must not refresh its upstream, or any registration
    would clear staleness."""
    if not enabled(view):
        return False
    kind = entry.get("kind")
    own = _digest(task, task_dir, kind)
    if own is None:
        return False
    deps = graph(view).get(kind) or []
    if entry.get("digest") == own and ("upstream" in entry or not deps):
        return False
    entry["digest"] = own
    if deps:
        entry["upstream"] = {one: found for one in deps
                             if (found := _digest(task, task_dir, one)) is not None}
    else:
        entry.pop("upstream", None)
    return True


@dataclass(frozen=True)
class Finding:
    """One tracked document. `blocks` names what a stale one stops (`entry to
    implement` or `land`); `blocking` says whether the issue has reached it."""
    artifact: str
    stale: bool
    reasons: tuple
    blocks: str
    blocking: bool
    recorded: tuple = ()

    @property
    def detail(self):
        if not self.stale:
            return "fresh - written against " + (", ".join(self.recorded) or "its upstream")
        text = f"stale - {'; '.join(self.reasons)}; blocks {self.blocks}"
        return text if self.blocking else text + " (not yet due)"


def _short(digest):
    return (digest or "")[:19]


def _moved(recorded, deps, task, task_dir):
    """One phrase for each artifact in `deps` whose digest is not the one recorded."""
    found = []
    for one in deps:
        before, after = recorded.get(one), _digest(task, task_dir, one)
        if before == after:
            continue
        if after == UNREADABLE:
            found.append(f"{one} cannot be read now")
        elif after is None:
            found.append(f"{one} is missing now")
        elif before is None:
            found.append(f"{one} was not recorded when this was written")
        else:
            found.append(f"{one} changed ({_short(before)} then {_short(after)})")
    return found


def _blocks(kind, order):
    """`(stage index, label)` of the first thing a stale `kind` stops."""
    consumers = [i for i, stage in enumerate(order) if kind in CONSUMES.get(stage, ())]
    if consumers:
        return consumers[0], f"entry to {order[consumers[0]]}"
    land = order.index(LAND_STAGE) if LAND_STAGE in order else len(order) - 1
    return max(land, 0), "land"


def evaluate(view, task, task_dir):
    """The findings for every tracked document, in catalogue order. Empty when
    the capability is off."""
    if not enabled(view):
        return []
    deps = graph(view)
    tracked = {}
    for entry in task.get("artifacts") or []:
        if (isinstance(entry, dict) and entry.get("kind") in deps and deps[entry["kind"]]
                and entry.get("status") != "omitted" and "upstream" in entry):
            tracked[entry["kind"]] = entry
    # An `upstream` record that is not a map cannot be compared, so the document
    # is stale: a document that fails to say what it was written against must
    # not land.
    reasons = {kind: (_moved(entry["upstream"], deps[kind], task, task_dir)
                      if isinstance(entry["upstream"], dict)
                      else ["upstream record is not a map"])
               for kind, entry in tracked.items()}
    stale = {kind for kind, found in reasons.items() if found}
    changed = True
    while changed:
        changed = False
        for kind in tracked:
            via = [one for one in deps[kind] if one in stale and one != kind]
            if via and kind not in stale:
                stale.add(kind)
                changed = True
    for kind in stale:
        reasons[kind] = reasons[kind] + [f"{one} is stale" for one in deps[kind]
                                         if one in stale and one != kind]
    order, reached = stage_lists.positions(view, task, task_dir)
    findings = []
    for kind in tracked:
        index, label = _blocks(kind, order)
        findings.append(Finding(kind, kind in stale, tuple(reasons[kind]), label,
                                reached >= index, tuple(sorted(tracked[kind]["upstream"]))
                                if isinstance(tracked[kind]["upstream"], dict) else ()))
    return findings


def stale_findings(findings):
    return [one for one in findings if one.stale]


def unmet_entry(findings, stage):
    """Phrases for the stale documents the stage `stage` consumes."""
    return [f"{one.artifact} is stale" for one in findings
            if one.stale and one.artifact in CONSUMES.get(stage, ())]


def refusal(findings):
    """The text `compass ship-commit` refuses with, or None when nothing is stale."""
    stale = stale_findings(findings)
    if not stale:
        return None
    lines = [f"compass ship-commit: refusing to land - {len(stale)} artifact(s) are stale:"]
    lines += [f"  {one.artifact}: {'; '.join(one.reasons)}" for one in stale]
    lines += ["", "Write each stale document again against the current upstream, then run",
              "`compass issue artifact <kind> --status <status>` to record it. A document",
              "whose file has not changed keeps its old record, so registering alone",
              "does not clear it."]
    return "\n".join(lines)
