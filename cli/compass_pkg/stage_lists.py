# compass_pkg.stage_lists - evaluate each stage's entry and exit lists
"""Run the stage lists of an issue's configuration.

A stage can list checks it needs before work in it starts (`entry`) and before
it is left (`exit`). `evaluate` reads those lists from the issue's effective
view and gives each active check a row. The shipped Definition of Ready and
Done checks say `requires: [entry-exit-evaluation]`, so they are active only
where that capability is on. A check a project adds runs whatever the
capability, unless it asks for it with `requires`. An issue read without a
configuration has no rows.

Which list is due. `compass next` names the current stage. The entry list of a
stage is due once the stage is current or behind the issue, and its exit list
once the stage is behind it. A landed issue has every list due. A list that is
not due is still reported, so the receipt can show it, but `compass check`
counts only due rows.

How a check is judged:

- `human`: a tick, a checked box in a checklist document of the issue. The
  document is the requirements review for an entry list and the verification
  report for an exit list. The box is the one whose text equals the check's
  statement, under the heading of its list (`list_heading`): `Definition of
  Ready` for the plan entry list, `Definition of Done` for the `verify` exit
  list and `<Stage> <side> list` for any other.
  An unchecked box that carries a typed tag (`(evidence: ...)` or
  `(follow-up: ...)`) that resolves counts as deferred and passes. The tag is
  resolved by `checks.dod_tag_problems`, the code `dod-evidence-typed` uses.
  A check that lists `approvers:` also needs a current approval by one of
  them, which `compass_pkg.approval_records` judges.
  A missing document is not a failure when the routed approach lists no such
  document among its artifacts: the row is nothing-to-check.
- `deterministic`: the registered implementation runs.
- `judged`: a review record. `review_records.judge` reads the newest record
  of a listed reviewer and passes it only while the record says pass and
  matches the check's inputs, definition, issue and generation.
- `evidence`: not evaluated by this version. A blocking one fails, so a
  configuration cannot pass by naming a check nothing reads.

When a list is skipped. The stage that produces a human check's document is
skipped or collapsed (the stage before the listed one for an entry list, the
listed stage for an exit list), or the document is recorded as deliberately
omitted. A deterministic check is skipped when its listed stage is skipped or
collapsed. A skipped check gives the verdict its `on_skipped` names and does
not run.

An advisory check, by `severity` or by a `blocking_when` that does not match
the assessment, reports a failure as a pass that says so.
"""
# DEPENDENCY: standard library (dataclasses, os, re); compass_pkg.check_registry,
# compass_pkg.check_results, compass_pkg.core, compass_pkg.doc_sections,
# compass_pkg.next_cmd, compass_pkg.review_records.
# It reads configuration through an EffectiveView and does not import
# compass_pkg.obligations, which only classify, effective and replay may import.
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from compass_pkg import review_records
from compass_pkg.check_registry import CHECK_FNS
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import FOUND, OMITTED, resolve_artifact, unregistered_document
from compass_pkg.doc_sections import comment_mask, list_heading, normal, section, visible

CAPABILITY = "entry-exit-evaluation"
SIDES = ("entry", "exit")
#: The modes that mean a stage did not run as a stage. `compass next` passes
#: over the same two.
SKIPPED_MODES = ("skipped", "collapsed")

#: The document kind that holds the ticks of each side's lists.
CHECKLIST_DOCUMENTS = {"entry": "requirements-review", "exit": "verification-report"}

#: What a skipped check returns, by its `on_skipped`.
SKIPPED_STATUS = {"pass": "pass", "not-applicable": "nothing-to-check", "fail": "fail"}

_ITEM = re.compile(r"^\s*-\s+\[([ xX])\]\s*(.*)")
_TAG_ANYWHERE = re.compile(r"\((?:evidence|follow-up):[^)]*\)")


@dataclass(frozen=True)
class Row:
    """One check of one list. `status` is `pass`, `fail`, `nothing-to-check`
    or `pending` (a check that is not due and does not read a document, so it
    has not run). `due` says whether `compass check` counts it."""
    stage: str
    side: str
    check: str
    status: str
    detail: str
    due: bool
    severity: str = "blocking"

    @property
    def label(self):
        return label(self.stage, self.side)


def label(stage, side):
    """The name `compass check --json` gives the rows of one list."""
    return f"stage:{stage}:{side}"


def _items(path, heading):
    """`[(ticked, normalised text, text)]` for the checkbox items under
    `heading` of the document at `path`, or None when the document has no such
    heading. A continuation line is an indented line after an item. The section
    is read by `doc_sections`, as the renderer and the tag rule read it."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().split("\n")
    mask = comment_mask(lines)
    body = section(lines, mask, heading)
    if body is None:
        return None
    shown = visible(lines)
    items = []
    for index in range(*body):
        line = shown[index]
        if mask[index]:
            continue
        found = _ITEM.match(line)
        if found:
            items.append([found.group(1).lower() == "x", found.group(2)])
        elif items and line.startswith(" ") and line.strip():
            items[-1][1] += " " + line.strip()
    return [(t, normal(s), s) for t, s in items]


def _document(task_dir, kind):
    """`(state, path, name)`: `found` with the path, `omitted`, or `absent`."""
    state, path, _ = resolve_artifact(task_dir, kind)
    if state == FOUND:
        return "found", path
    if state == OMITTED:
        return "omitted", None
    elsewhere = unregistered_document(task_dir, kind + ".md")
    return ("found", elsewhere) if elsewhere else ("absent", None)


class _Documents:
    """The checklists of one evaluation, read once each."""

    def __init__(self, task_dir):
        self.task_dir = task_dir
        self._cache = {}

    def get(self, stage, side):
        if (stage, side) not in self._cache:
            kind = CHECKLIST_DOCUMENTS[side]
            heading = list_heading(stage, side)
            state, path = _document(self.task_dir, kind)
            items = _items(path, heading) if state == "found" else None
            self._cache[(stage, side)] = (state, path, kind + ".md", heading, items)
        return self._cache[(stage, side)]


def _tick(check_id, check, stage, side, documents, task, owes):
    """`(status, detail)` of a human check, or None when its document is
    recorded as omitted (the check is skipped). `owes` is `(approach, kinds)`,
    the document kinds the routed approach lists among its artifacts, or None
    when the approach is not known."""
    state, path, name, heading, items = documents.get(stage, side)
    if state == "omitted":
        return None
    kind = CHECKLIST_DOCUMENTS[side]
    if state == "absent":
        if owes is not None and kind not in owes[1]:
            return "nothing-to-check", f"{owes[0]} owes no {kind}"
        return "fail", f"{name} not found; its '{heading}' section holds the tick"
    wanted = normal(check.get("statement") or "")
    matches = [(ticked, raw) for ticked, text, raw in (items or []) if text == wanted]
    if not matches:
        return "fail", (f"no checklist item with this statement under '{heading}' "
                        f"in {name}")
    if any(ticked for ticked, _ in matches):
        if check.get("approvers"):
            from compass_pkg import approval_records
            return approval_records.judge(check_id, check, task, documents.task_dir)
        return "pass", f"ticked in {name}"
    from compass_pkg.checks import dod_tag_problems
    registry = {e.get("id"): e for e in (task.get("evidence") or [])
                if isinstance(e, dict) and e.get("id")}
    follow_ups = {f.get("id"): f for f in (task.get("follow_ups") or [])
                  if isinstance(f, dict) and f.get("id")}
    problems = []
    for _, raw in matches:
        found = dod_tag_problems(raw, registry, follow_ups)
        if found is None:
            continue
        if not found:
            shown = _TAG_ANYWHERE.search(raw)
            tag = shown.group(0) if shown else "a typed tag"
            if check.get("approvers"):
                # A deferral is not an approval, so it cannot excuse a check
                # that names who may approve.
                from compass_pkg import approval_records
                status, detail = approval_records.judge(check_id, check, task,
                                                        documents.task_dir)
                if status == "fail":
                    return status, (f"{detail} (deferred with {tag}; a deferral does "
                                    f"not excuse approvers)")
                return status, f"{detail}; deferred with {tag}"
            return "pass", f"deferred with {tag}"
        problems += found
    if problems:
        return "fail", "; ".join(problems)
    return "fail", f"not ticked in {name} under '{heading}'"


def _implementation(check, task, task_dir):
    fn = CHECK_FNS.get(check.get("impl"))
    if fn is None:
        return "fail", f"no implementation '{check.get('impl')}' is registered"
    try:
        passed, detail = fn(task, task_dir)
    except Exception as exc:                           # noqa: BLE001
        return "fail", f"check errored: {exc}"
    if passed is NOTHING_TO_CHECK:
        return "nothing-to-check", detail
    return ("pass" if passed else "fail"), detail


def _skipped(check):
    value = check.get("on_skipped")
    return SKIPPED_STATUS.get(value, "fail")


def _active(view, check, reading, capabilities):
    return (view.matches(check.get("when"), reading)
            and set(check.get("requires") or ()) <= capabilities)


def _severity(view, check, reading):
    blocking_when = check.get("blocking_when")
    if check.get("severity", "blocking") != "blocking":
        return "advisory"
    if blocking_when and not view.matches(blocking_when, reading):
        return "advisory"
    return "blocking"


def positions(view, task, task_dir):
    """`(order, reached)`: the stage names in order, and how many stages the
    issue has reached (the index of the current stage). A closed issue, or a
    current stage no list knows, has reached them all."""
    from compass_pkg import status_words
    from compass_pkg.next_cmd import _current_phase_from_task
    order = list(view.stage_order())
    if status_words.is_closed(task):
        return order, len(order)
    current = _current_phase_from_task(task, task_dir)
    return order, (order.index(current) if current in order else len(order))


def evaluate(view, task, task_dir, run=True):
    """The rows of every list of the issue, in stage order, entry before exit.
    An empty list for an issue read without a configuration. A check that
    says `requires: [entry-exit-evaluation]` (the shipped Definition of Ready
    and Done) is active only where the capability is on; a check a project adds
    runs whatever the capability. With `run` false a deterministic check is not
    run and its row is `pending`: the receipt reads the record and never
    re-runs a check."""
    if view is None:
        return []
    config = view.config
    approach_name = task.get("delivery_approach")
    approach = (config.get("approaches") or {}).get(approach_name)
    owes = (None if approach is None
            else (approach_name, set(approach.get("artifacts") or {})))
    checks = config.get("checks") or {}
    stages = config.get("stages") or {}
    modes = task.get("stages") if isinstance(task.get("stages"), dict) else {}
    reading = view.listing_assessment(task.get("assessment") or {},
                                      task.get("delivery_approach"))
    capabilities = {name for name, on in view.capabilities.items() if on}
    order, reached = positions(view, task, task_dir)
    documents = _Documents(task_dir)
    rows = []
    for index, stage in enumerate(order):
        body = stages.get(stage) or {}
        for side in SIDES:
            due = index <= reached if side == "entry" else index < reached
            if side == "entry":
                producer = order[index - 1] if index else stage
            else:
                producer = stage
            for check_id in body.get(side) or []:
                check = checks.get(check_id)
                if not isinstance(check, dict):
                    rows.append(Row(stage, side, check_id, "fail",
                                    "the check is not defined in the configuration",
                                    due))
                    continue
                if not _active(view, check, reading, capabilities):
                    continue
                severity = _severity(view, check, reading)
                kind = check.get("kind")
                status, detail, settled = _outcome(
                    check_id, check, kind, side, stage, producer, modes, task, task_dir,
                    documents, due, run, owes)
                if status != "pending":
                    status, detail = _apply(view, check, status, detail, settled, reading)
                rows.append(Row(stage, side, check_id, status, detail, due, severity))
    return rows


def _apply(view, check, status, detail, settled, reading):
    """Give an outcome the verdict `compass check` gives a gate check: its
    `on_skipped` decides a result of nothing to check, and its effective
    severity turns a failure into an advisory one. Both come from
    `check_cmd._judge`, so a check id has one verdict whoever runs it. An
    outcome that is already settled (a skipped stage has had its `on_skipped`
    applied, and a route that owes no document is not a skip) does not get
    `on_skipped` a second time."""
    from compass_pkg.check_cmd import ADVISORY_FAILURE, _judge as judge
    declared = {k: v for k, v in check.items() if k != "on_skipped"} if settled else check
    passed, detail = judge(_PASSED[status], detail, declared, view.matches, reading)
    if passed is ADVISORY_FAILURE:
        return "advisory", detail
    if passed is NOTHING_TO_CHECK:
        return "nothing-to-check", detail
    return ("pass" if passed else "fail"), detail


_PASSED = {"pass": True, "fail": False, "nothing-to-check": NOTHING_TO_CHECK}


def _outcome(check_id, check, kind, side, stage, producer, modes, task, task_dir, documents,
             due, run, owes):
    """`(status, detail, settled)` for one active check, before its severity
    and `on_skipped` are applied. `settled` is true when the status already
    follows from `on_skipped` or from the route owing no document."""
    source = producer if kind == "human" else stage
    mode = modes.get(source)
    if mode in SKIPPED_MODES:
        return (_skipped(check),
                f"{source} is {mode}; on_skipped is {check.get('on_skipped')}", True)
    if kind == "human":
        ticked = _tick(check_id, check, stage, side, documents, task, owes)
        if ticked is None:
            return (_skipped(check), f"{CHECKLIST_DOCUMENTS[side]} is recorded as omitted; "
                                     f"on_skipped is {check.get('on_skipped')}", True)
        # The one nothing-to-check a tick gives is a route that owes no document.
        return (*ticked, ticked[0] == "nothing-to-check")
    if not due:
        return ("pending", f"runs when {'work in' if side == 'entry' else 'leaving'} "
                           f"{stage} is due", False)
    if kind == "deterministic":
        if not run:
            return "pending", "not run here; `compass check` runs it", False
        return (*_implementation(check, task, task_dir), False)
    if kind == "judged":
        return (*review_records.judge(check_id, check, task, task_dir), False)
    return "fail", (f"a check of kind '{kind}' is not evaluated by this version of "
                    f"compass, so it cannot pass"), False


def due_rows(rows):
    return [row for row in rows if row.due]


def unmet_entry(rows, stage):
    """The ids of the failing due entry checks of `stage`, in list order."""
    return [row.check for row in rows
            if row.due and row.side == "entry" and row.stage == stage
            and row.status == "fail"]
