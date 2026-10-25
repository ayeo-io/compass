# compass_pkg.lifecycle - the state of an issue, read from its records
"""`state_of(manifest, task_dir)` names the state of one issue.

Only two states are stored (`backlog`, a hold a person set, and `done`). The
others are read from the records, because no command marks the start of plan
or of review, and a stored state would need a writer at every place a record is
written.

The second part of this module derives the block a `depends_on` entry causes
(ADR-062). Every reader of a dependency - `compass next`, the pre-tool hook,
lint, the board, `compass flow --json`, the issue page and `ship-commit` -
judges it here, so no two of them can disagree. A reader passes the function
that reads another issue: the readers that decide a refusal pass
`checkout_reader`, which reads this checkout uncached; the readers that only
advise pass `mapping_reader` over the manifests they already parsed.
"""
# DEPENDENCY: compass_pkg.next_cmd (the record readers it already has),
# compass_pkg.status_words, core.load_manifest and issue_layout.is_one_segment.
# `core` never imports this module.
from __future__ import annotations

import os
from dataclasses import dataclass

from compass_pkg import next_cmd, status_words
from compass_pkg.core import load_manifest, manifest_path
from compass_pkg.issue_layout import is_one_segment
from compass_pkg.stable_ids import (
    STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IDS, STAGE_IMPLEMENT, STAGE_PLAN,
    STAGE_REFINE, STAGE_SHIP, STAGE_VERIFY)


def _define_finished(manifest):
    return (next_cmd._registered(manifest, "acceptance-criteria")
            or bool(next_cmd._entries(manifest, "scenarios")))


def _refine_finished(manifest, task_dir):
    stages = manifest.get("stages")
    weight = stages.get(STAGE_REFINE) if isinstance(stages, dict) else None
    if isinstance(weight, str) and weight.strip().lower() in next_cmd._SKIPPED_WEIGHTS:
        return True
    return (next_cmd._registered(manifest, "requirements-review")
            or (not next_cmd._earned(manifest, "requirements-review")
                and next_cmd._review_written(task_dir)))


def _work_started(manifest, task_dir):
    return (next_cmd._registered(manifest, "technical-design")
            or next_cmd._registered(manifest, "distribution-map")
            or bool(next_cmd._entries(manifest, "subtasks"))
            or next_cmd._testing_started(manifest, task_dir))


def _review_started(manifest):
    """An issue is in review once a gate left `pending` or a verification report
    is registered with a path (the architect's ruling, recorded in ADR-045).
    Manifest only, no disk read."""
    gates = next_cmd._entries(manifest, "gates")
    if any((g.get("status") or "pending") != "pending" for g in gates):
        return True
    return any(a.get("kind") == "verification-report" and a.get("path")
               for a in next_cmd._entries(manifest, "artifacts"))


_STATE_OF_STAGE = {STAGE_ASSESS: "backlog", STAGE_DEFINE: "backlog",
                   STAGE_REFINE: "backlog", STAGE_PLAN: "in-progress",
                   STAGE_BREAKDOWN: "in-progress", STAGE_IMPLEMENT: "in-progress",
                   STAGE_VERIFY: "in-review", STAGE_SHIP: "in-review"}


def _state_of_named_stage(manifest):
    """A top-level `current_phase` key wins over the records, as in
    `compass next`. A name no stage has says nothing."""
    named = manifest.get("current_phase")
    if isinstance(named, str):
        return _STATE_OF_STAGE.get(named.strip().lower())
    return None


#: The states in which the blocked flag counts: work is under way or in review.
BLOCKABLE_STATES = ("in-progress", "in-review")


def blocked_flag(manifest, task_dir):
    """The `blocked` mapping (`reason` and `at`) while the state allows it,
    else None. A flag left on a held, ready or closed issue is ignored."""
    flag = manifest.get("blocked") if isinstance(manifest, dict) else None
    if not isinstance(flag, dict):
        return None
    return flag if state_of(manifest, task_dir) in BLOCKABLE_STATES else None


def status_errors(manifest, raw, task_dir):
    """What `issue lint` reports about the status keys. `manifest` is the
    loaded issue, `raw` the parsed file as it is on disk (a status word that
    was mapped on load shows only there)."""
    errors = []
    reason = status_words.close_reason(manifest)
    if status_words.is_closed(manifest) and reason is None:
        errors.append(
            "`status: done` has no `close_reason`; give one of "
            + ", ".join(status_words.CLOSE_REASONS))
    words = status_words._RETIRED_CLOSE_REASON
    if isinstance(raw, dict) and raw.get("status") in words:
        old, given = raw["status"], raw.get("close_reason")
        stood_for = words[old]
        fits = given in (None, stood_for) or (
            stood_for == status_words.NOT_PLANNED and given == status_words.DUPLICATE)
        if not fits:
            errors.append(
                f"`status: {old}` contradicts `close_reason: {given}`; the "
                f"close reason is used, so change or remove one of them")
    if manifest.get("duplicate_of") and reason != status_words.DUPLICATE:
        errors.append("`duplicate_of` is set but the close reason is not duplicate")
    if status_words.has_blocked_key(manifest) and blocked_flag(manifest, task_dir) is None:
        errors.append(
            f"`blocked` is set on an issue that is {state_of(manifest, task_dir)}; "
            "only an in-progress or in-review issue can be blocked, and readers "
            "ignore the flag")
    return errors


def state_of(manifest, task_dir):
    if status_words.is_closed(manifest):
        return "done"
    if status_words.is_held(manifest):
        return "backlog"
    if _review_started(manifest):
        return "in-review"
    named = _state_of_named_stage(manifest)
    if named:
        return named
    if _work_started(manifest, task_dir):
        return "in-progress"
    if _define_finished(manifest) and _refine_finished(manifest, task_dir):
        return "ready"
    return "backlog"


# --- dependencies between issues (ADR-062) --------------------------------------

#: The values `until` takes, in the order every message lists them: the two
#: workflow states, then each stage after assess. A manifest always reaches
#: assess, so it is not a value.
UNTIL_STATES = ("done", "in-review")
UNTIL_STAGES = tuple(STAGE_IDS[1:])
UNTIL_VALUES = UNTIL_STATES + UNTIL_STAGES
DEFAULT_UNTIL = "done"
#: The keys of one `depends_on` entry, in the order the writer puts them.
ENTRY_KEYS = ("issue", "reason", "until")

#: Why a dependency could not be judged. None of them counts as unmet.
NOT_FOUND = "not found"
UNREADABLE = "unreadable"
UNKNOWN_UNTIL = "unknown until"
CYCLE = "cycle"

SHAPE_TEXT = "{issue, reason, until}"


class Unread(Exception):
    """A reader could not give the manifest of a slug. `why` is NOT_FOUND or
    UNREADABLE; `cause` says what went wrong, for lint."""

    def __init__(self, why, cause=""):
        super().__init__(why)
        self.why = why
        self.cause = cause


def checkout_reader(work_root):
    """A reader of this checkout's `.compass/work/<slug>/`, through
    `load_manifest` and never the parse cache: the readers that decide a
    refusal use it (ADR-052). It runs no git command and reads no other tree."""
    def read(slug):
        if not is_one_segment(slug):
            raise Unread(NOT_FOUND)
        task_dir = os.path.join(work_root, slug)
        if not os.path.isfile(manifest_path(task_dir)):
            raise Unread(NOT_FOUND)
        try:
            manifest, _path = load_manifest(task_dir)
        except Exception as exc:                            # noqa: BLE001 - any fault is unreadable
            raise Unread(UNREADABLE, _cause(exc)) from None
        if not isinstance(manifest, dict):
            raise Unread(UNREADABLE, "not a mapping")
        return manifest, task_dir
    return read


def mapping_reader(found):
    """A reader over manifests a caller already parsed. `found` maps a slug to
    `(manifest, task_dir)`, or to the text of why it could not be read. A slug
    it does not hold has no manifest."""
    def read(slug):
        hit = found.get(slug)
        if hit is None:
            raise Unread(NOT_FOUND)
        if isinstance(hit, str):
            raise Unread(UNREADABLE, hit)
        return hit
    return read


def _cause(exc):
    text = str(exc).strip().splitlines()
    return "%s: %s" % (type(exc).__name__, text[0]) if text else type(exc).__name__


@dataclass(frozen=True)
class Dependency:
    issue: str
    reason: str
    until: str
    #: The other issue's state word; None when it was not read.
    state: object = None
    #: Its stage as `compass next` names it, `done` when closed; None when not read.
    stage: object = None
    close_reason: object = None
    met: bool = False
    #: NOT_FOUND, UNREADABLE, UNKNOWN_UNTIL or CYCLE; None when it was judged.
    fault: object = None
    #: What went wrong reading it, for lint.
    cause: object = None

    @property
    def waits(self):
        """The wait as a reader shows it, or None when met or not judged."""
        if self.met or self.fault:
            return None
        if self.state == "done":
            return "waits for %s, which was closed as %s" % (
                self.issue, self.close_reason or "no close reason")
        return "waits for %s to reach %s" % (self.issue, self.until)

    @property
    def state_text(self):
        """The state as a reader sees it: `done (not-planned)` for a closed issue."""
        if self.state == "done" and self.close_reason:
            return "%s (%s)" % (self.state, self.close_reason)
        return self.state

    def row(self):
        """The `compass flow --json` entry: exactly these six keys."""
        return {"issue": self.issue, "reason": self.reason, "until": self.until,
                "state": self.state, "stage": self.stage, "met": self.met}


def _shape_faults(manifest):
    """`(well-formed entries, faults)`. A fault is `(name, hook phrase, lint
    line)`, where `name` is the dependency it concerns, as near as the entry
    says."""
    raw = manifest.get("depends_on") if isinstance(manifest, dict) else None
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [("depends_on", "which is not a list of %s entries" % SHAPE_TEXT,
                     "`depends_on` is not a list of %s entries" % SHAPE_TEXT)]
    good, faults, seen = [], [], set()
    for number, entry in enumerate(raw, 1):
        issue = entry.get("issue") if isinstance(entry, dict) else entry
        name = issue if isinstance(issue, str) and issue.strip() else "entry %d" % number
        if not _well_formed(entry):
            faults.append((name, "in an entry that is not the documented %s shape" % SHAPE_TEXT,
                           "`depends_on` entry %d is not the documented %s shape"
                           % (number, SHAPE_TEXT)))
            continue
        if issue in seen:
            faults.append((issue, "named twice",
                           "`depends_on` names %s twice; keep one entry per issue" % issue))
            continue
        seen.add(issue)
        good.append({"issue": issue, "reason": entry["reason"],
                     "until": entry.get("until", DEFAULT_UNTIL)})
    return good, faults


def _well_formed(entry):
    if not isinstance(entry, dict) or not set(entry) <= set(ENTRY_KEYS):
        return False
    issue, reason = entry.get("issue"), entry.get("reason")
    return (is_one_segment(issue) and isinstance(reason, str) and bool(reason.strip())
            and isinstance(entry.get("until", DEFAULT_UNTIL), str))


def entries(manifest):
    """`(entries, faults)`: the well-formed `depends_on` entries, each with its
    `until` filled in, and one lint line for each entry that is not."""
    good, faults = _shape_faults(manifest)
    return good, [lint for _name, _phrase, lint in faults]


def stage_of(manifest, task_dir, state):
    """`(stage, problem)`. A closed issue is at `done`; an issue with no delivery
    approach is at assess; every other issue is where `compass next` puts it."""
    if state == "done":
        return "done", None
    if state in ("backlog", "ready") and not manifest.get("delivery_approach"):
        return STAGE_ASSESS, None
    try:
        return next_cmd._current_phase_from_task(manifest, task_dir) or "done", None
    except Exception as exc:                                # noqa: BLE001
        return None, "the stage could not be read (%s)" % type(exc).__name__


def reached(until, state, stage, close_reason):
    """Whether an issue in `state` at `stage` has reached `until`. Only a close
    as completed counts as done, so an issue closed any other way meets nothing."""
    if state == "done":
        return close_reason == status_words.COMPLETED
    if until == "done":
        return False
    if until == "in-review":
        return state == "in-review"
    if stage == "done":
        return True
    return STAGE_IDS.index(stage) >= STAGE_IDS.index(until)


def _judge_one(entry, slug, read):
    issue, until = entry["issue"], entry["until"]
    base = dict(issue=issue, reason=entry["reason"], until=until)
    if until not in UNTIL_VALUES:
        return Dependency(fault=UNKNOWN_UNTIL, **base)
    try:
        manifest, task_dir = read(issue)
    except Unread as exc:
        return Dependency(fault=exc.why, cause=exc.cause or None, **base)
    try:
        state = state_of(manifest, task_dir)
        close = status_words.close_reason(manifest) if state == "done" else None
        stage, problem = stage_of(manifest, task_dir, state)
        if problem or (stage != "done" and stage not in STAGE_IDS):
            return Dependency(state=state, close_reason=close, fault=UNREADABLE,
                              cause=problem or "it names no stage", **base)
        found = dict(base, state=state, stage=stage, close_reason=close)
        # A dependency that waits for this issue in turn is a cycle. Counting
        # it as unmet would block both issues for ever, so it is a fault.
        if slug in {e["issue"] for e in entries(manifest)[0]}:
            return Dependency(fault=CYCLE, **found)
        return Dependency(met=reached(until, state, stage, close), **found)
    except Exception as exc:                                # noqa: BLE001 - a fault never blocks
        return Dependency(fault=UNREADABLE, cause=_cause(exc), **base)


def judge(manifest, slug, read):
    """Every well-formed entry of `manifest`, judged in order. `slug` is the
    waiting issue's own; `read` is the reader the caller chose. Reads each
    dependency once, and never a dependency's own dependencies."""
    return tuple(_judge_one(entry, slug, read) for entry in entries(manifest)[0])


def in_scope(manifest, task_dir, stage=None):
    """Whether a dependency can block the issue now: it is at implement and
    neither on hold nor done. A caller that already knows the stage passes it."""
    if status_words.is_closed(manifest) or status_words.is_held(manifest):
        return False
    if stage is None:
        stage, _problem = stage_of(manifest, task_dir, state_of(manifest, task_dir))
    return stage == STAGE_IMPLEMENT


def dependency_block(manifest, task_dir, deps, stage=None):
    """The waits of the unmet dependencies, joined with "; ", while the issue
    is in scope (`in_scope`); else None."""
    if not in_scope(manifest, task_dir, stage):
        return None
    waits = [d.waits for d in deps if d.waits]
    return "; ".join(waits) if waits else None


def blocked_text(stored, waits):
    """The blocked reason a reader shows: the stored flag's reason first, then
    the dependency block; None when neither is set."""
    parts = [p for p in (stored, waits) if p]
    return "; ".join(parts) if parts else None


_FAULT_PHRASE = {
    NOT_FOUND: "which has no manifest in this checkout",
    UNREADABLE: "whose manifest cannot be read",
}


def _hook_phrase(dependency, slug):
    if dependency.fault == UNKNOWN_UNTIL:
        return "with until '%s', which is not a value" % dependency.until
    if dependency.fault == CYCLE:
        return "which depends on '%s' in turn" % slug
    return _FAULT_PHRASE[dependency.fault]


def _warning(slug, name, phrase):
    return ("Compass: '%s' depends on '%s', %s; the edit is allowed. "
            "Run compass issue lint to see it." % (slug, name, phrase))


def hook_lines(task_dir):
    """What the pre-tool hook's dependency reader prints: `warn <text>` for
    each dependency it cannot judge, then at most one
    `wait<TAB>dependency<TAB>until<TAB>state<TAB>more` for the first unmet one.
    Tabs separate the fields because a state can hold a space.

    No lines when the issue's own manifest cannot be read, or the issue is out
    of scope. A fault only warns: the hook refuses on a positive read of an
    unmet dependency and on nothing else."""
    try:
        manifest, _path = load_manifest(task_dir)
    except Exception:                                       # noqa: BLE001 - unreadable: allow
        return []
    if not isinstance(manifest, dict) or not in_scope(manifest, task_dir):
        return []
    slug = os.path.basename(os.path.normpath(task_dir))
    _good, faults = _shape_faults(manifest)
    lines = ["warn " + _warning(slug, name, phrase) for name, phrase, _lint in faults]
    deps = judge(manifest, slug, checkout_reader(os.path.dirname(os.path.normpath(task_dir))))
    lines += ["warn " + _warning(slug, d.issue, _hook_phrase(d, slug)) for d in deps if d.fault]
    unmet = [d for d in deps if d.waits]
    if unmet:
        first = unmet[0]
        more = " (and %d more)" % (len(unmet) - 1) if len(unmet) > 1 else ""
        lines.append("\t".join(("wait", first.issue, first.until, first.state_text, more)))
    return lines
