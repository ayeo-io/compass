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
not due is still reported, but `compass check` counts only due rows.

How a check is judged:

- `human`: a record in the manifest, read by `item_records`: evidence that meets
  the check (`--meets`), a person's approval (`compass evidence approve
  --check`), or a follow-up that defers it (`--defers`; on a path issue only one
  that links to a GitHub issue with `--github`). A tick on a page counts
  for nothing; the page is never read. A check that lists `approvers:` needs a
  current approval by one of them, which `compass_pkg.approval_records` judges,
  and a deferral does not excuse it. A check whose document the routed approach
  owes no copy of is nothing-to-check, and so is one whose document is recorded
  as deliberately omitted (skipped).
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

A path issue (ADR-092). It runs assess, specify, build and ship and has no
stage modes, so no list of it is skipped. Its lists are the configuration's
lists of those four stages. A configuration that still declares the legacy
stages has its lists moved onto the path (`path_lists`): each legacy stage's
lists go to the path stage that shows it, except the `verify` exit list, the
Definition of Done, which is the build exit list. A path issue owes no
Definition of Ready, so no `dor-*` check is listed for it. It owes the
Definition of Done only when `evidence_required` lists `definition-of-done`.
An issue assessed before 9.0.0 keeps its legacy lists exactly.
"""
# DEPENDENCY: standard library (dataclasses, os); compass_pkg.check_registry,
# compass_pkg.check_results, compass_pkg.core, compass_pkg.item_records,
# compass_pkg.next_cmd, compass_pkg.path_readers, compass_pkg.path_stages,
# compass_pkg.review_records, compass_pkg.word_map.
# It reads configuration through an EffectiveView and does not import
# compass_pkg.obligations, which only classify, effective and replay may import.
from __future__ import annotations

import os
from dataclasses import dataclass

from compass_pkg import item_records, review_records
from compass_pkg.check_registry import CHECK_FNS
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import FOUND, OMITTED, resolve_artifact, unregistered_document
from compass_pkg.path_readers import READY_PREFIX
from compass_pkg.path_readers import owes as path_owes
from compass_pkg.path_stages import is_path_issue, path_stage_of, stages_of
from compass_pkg.stable_ids import (APPROACH_DELIVERY, DEPTH_LIGHTWEIGHT, DEPTH_THOROUGH,
                                    PATH_STAGE_IDS, STAGE_BUILD, STAGE_REFINE, STAGE_VERIFY)

CAPABILITY = "entry-exit-evaluation"
SIDES = ("entry", "exit")
#: The modes that mean a stage did not run as a stage. `compass next` passes
#: over the same two.
SKIPPED_MODES = ("skipped", "collapsed")

#: The document kind that holds the ticks of each side's lists.
CHECKLIST_DOCUMENTS = {"entry": "requirements-review", "exit": "verification-report"}

#: What a skipped check returns, by its `on_skipped`.
SKIPPED_STATUS = {"pass": "pass", "not-applicable": "nothing-to-check", "fail": "fail"}



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
    """Where the checklist documents of one evaluation stand, read once each."""

    def __init__(self, task_dir):
        self.task_dir = task_dir
        self._cache = {}

    def state(self, side):
        """`found`, `omitted` or `absent` for the document of a side's lists."""
        if side not in self._cache:
            self._cache[side] = _document(self.task_dir, CHECKLIST_DOCUMENTS[side])[0]
        return self._cache[side]


def _tick(check_id, check, stage, side, documents, task, owes):
    """`(status, detail)` of a human check, or None when its document is
    recorded as omitted (the check is skipped). `owes` is `(approach, kinds)`,
    the checklist documents the approach owes (`owes`), or None when the
    approach is not known. The records of the manifest decide; the
    document is not read."""
    state = documents.state(side)
    if state == "omitted":
        return None
    kind = CHECKLIST_DOCUMENTS[side]
    if state == "absent" and owes is not None and kind not in owes[1]:
        return "nothing-to-check", f"{owes[0]} owes no {kind}"
    if check.get("approvers"):
        # A deferral or evidence is not an approval, so neither excuses a check
        # that names who may approve.
        from compass_pkg import approval_records
        return approval_records.judge(check_id, check, task, documents.task_dir)
    recorded, ids = item_records.state_of(task, check_id, item_records.accepted_types())
    if recorded == item_records.OPEN:
        return "fail", f"not recorded: {item_records.open_hint(check_id, task)}"
    shown = ", ".join(ids)
    return "pass", {
        item_records.MET_EVIDENCE: f"met by {shown}",
        item_records.TICKED: f"ticked by {shown}",
        item_records.CARRIED: f"carried to ship, {shown}",
        item_records.MET_CARRIED: f"met, {shown} resolved",
        item_records.PAGE_TICK: f"ticked on the page before 7.0.0 ({shown})",
        item_records.LINKED: f"carried to a GitHub issue, {shown}",
    }[recorded]


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
    current stage no list knows, has reached them all. A path issue's stages are
    the path's, and a legacy stage name for its current stage reads as the path
    stage that shows it."""
    from compass_pkg import status_words
    from compass_pkg.next_cmd import _current_phase_from_task
    path = is_path_issue(task)
    order = list(stages_of(task)) if path else list(view.stage_order())
    if status_words.is_closed(task):
        return order, len(order)
    current = _current_phase_from_task(task, task_dir)
    if path:
        current = path_stage_of(current)
    return order, (order.index(current) if current in order else len(order))


def path_lists(stages):
    """`{path stage: {side: [check ids]}}` of a path issue, from a configuration's
    `stages` map. A configuration that declares a `verify` stage is a legacy one:
    each of its lists goes to the path stage that shows the stage, and the `verify`
    exit list (the Definition of Done) goes to build's exit. Any other
    configuration is read at the path stages as it stands. No `dor-*` check is
    kept: a path issue has no Definition of Ready."""
    stages = stages if isinstance(stages, dict) else {}
    out = {stage: {side: [] for side in SIDES} for stage in PATH_STAGE_IDS}
    if STAGE_VERIFY in stages:
        ordered = sorted(stages.items(), key=lambda item: (item[1] or {}).get("order", 0)
                         if isinstance(item[1], dict) else 0)
        moves = []
        for stage, body in ordered:
            for side in SIDES:
                target = (STAGE_BUILD if (stage, side) == (STAGE_VERIFY, "exit")
                          else path_stage_of(stage))
                moves.append((target, side, body))
    else:
        moves = [(stage, side, stages.get(stage)) for stage in PATH_STAGE_IDS
                 for side in SIDES]
    for target, side, body in moves:
        if target not in out or not isinstance(body, dict):
            continue
        kept = out[target][side]
        for check_id in body.get(side) or []:
            if not str(check_id).startswith(READY_PREFIX) and check_id not in kept:
                kept.append(check_id)
    return out


#: The stage modes that owe each checklist document when an approach declares no
#: `artifacts:` map (ADR-091): the same approaches as the shipped maps before 9.0.0.
_OWING_MODES = {"requirements-review": (STAGE_REFINE, (DEPTH_LIGHTWEIGHT, DEPTH_THOROUGH)),
                "verification-report": (STAGE_VERIFY, (DEPTH_THOROUGH,))}


def owed_by_stages(modes):
    """The checklist documents an issue's stage modes owe: the requirements review (the
    Definition of Ready) where refine is lightweight or thorough, the verification report
    (the Definition of Done) where the `verify` stage is thorough. A mode stored in a
    retired word (`light`, `full`), as a manifest written before the rename holds, is
    read as its current word."""
    from compass_pkg import word_map
    modes = modes if isinstance(modes, dict) else {}
    renamed = word_map.tables().get("stage_mode") or {}
    return {kind for kind, (stage, owing) in _OWING_MODES.items()
            if renamed.get(modes.get(stage), modes.get(stage)) in owing}


def owes(approach_name, approach, modes):
    """`(approach, kinds)`: the checklist documents the approach owes. A configuration that
    declares the approach's `artifacts:` map, as a stored generation
    does, is read as before; one with no map owes by the issue's stage modes, or the
    approach's own when the issue records none."""
    if "artifacts" in approach:
        return approach_name, set(approach.get("artifacts") or {})
    return approach_name, owed_by_stages(modes or approach.get("stages"))


def evaluate(view, task, task_dir, run=True):
    """The rows of every list of the issue, in stage order, entry before exit.
    An empty list for an issue read without a configuration. A check that
    says `requires: [entry-exit-evaluation]` (the shipped Definition of Ready
    and Done) is active only where the capability is on; a check a project adds
    runs whatever the capability. With `run` false a deterministic check is not
    run and its row is `pending`, so a reader of the record never re-runs a
    check."""
    if view is None:
        return []
    config = view.config
    approach_name = task.get("delivery_approach")
    approach = (config.get("approaches") or {}).get(approach_name)
    checks = config.get("checks") or {}
    stages = config.get("stages") or {}
    modes = task.get("stages") if isinstance(task.get("stages"), dict) else {}
    # An issue assessed before 9.0.0 names an approach the shipped default no longer
    # declares (ADR-092); it owes by its own stage modes, as it did before.
    if approach is None and modes and not is_path_issue(task):
        approach = {}
    owes_now = None if approach is None else owes(approach_name, approach, modes)
    if is_path_issue(task):
        # A path issue has no modes and no approach in the catalogue: what it owes is
        # its `evidence_required`, and its lists are moved onto the path stages.
        stages, modes = path_lists(stages), {}
        owes_now = (f"this {APPROACH_DELIVERY} issue",
                    {"verification-report"} if path_owes(task, "definition-of-done")
                    else set())
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
                    documents, due, run, owes_now)
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
