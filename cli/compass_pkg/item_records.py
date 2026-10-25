# compass_pkg.item_records - which Definition of Done and Ready items the records meet
"""Read the manifest records that meet an exit-list or entry-list item.

The Definition of Done is the issue's configured `verify` exit list and the
Definition of Ready its `plan` entry list. The `plan` and `breakdown` exit lists are
read the same way, whatever capability says they are
evaluated (the page that shows them is not the evaluator). An item is a check
id in one of those lists. One of four records meets it, and a command writes
each:

- **met by evidence**: an `evidence` entry of an accepted type with
  `meets: [<check>]`;
- **ticked by a person**: the newest `human-approval` record for the check is
  `approved`;
- **carried to a follow-up**: a follow-up with `defers: <check>`; it is met once
  it is resolved;
- **ticked on the page before 7.0.0**: an entry of `page_ticks`, written only by
  `compass issue migrate`.

An item with none of these is open. Only this reader counts a page tick; the
approval check never does.

This module reads records. It imports no command module and no renderer, so the
renderers, the stage lists and `dod-evidence-typed` can all use it.
"""
# DEPENDENCY: standard library (dataclasses); compass_pkg.stable_ids. The accepted
# evidence types are read from compass_pkg.checks inside `items`, because checks
# imports the masking module and this one is imported by the renderers.
from __future__ import annotations

from dataclasses import dataclass

from compass_pkg.stable_ids import STAGE_BREAKDOWN, STAGE_PLAN, STAGE_VERIFY

#: The two lists: `dod` is the `verify` exit list, `dor` the `plan` entry list.
LISTS = {"dod": (STAGE_VERIFY, "exit"), "dor": (STAGE_PLAN, "entry"),
         "plan-exit": (STAGE_PLAN, "exit"), "breakdown-exit": (STAGE_BREAKDOWN, "exit")}
TITLES = {"dod": "Definition of Done", "dor": "Definition of Ready",
          "plan-exit": "Plan exit checks", "breakdown-exit": "Breakdown exit checks"}
#: What a block says when its list is empty. The two stage exit lists are empty in the
#: shipped default; the Definition of Done and Ready keep one sentence.
EMPTY = {"plan-exit": "No exit checks are configured for the plan stage.",
         "breakdown-exit": "No exit checks are configured for the breakdown stage."}

MET_EVIDENCE, TICKED, CARRIED, MET_CARRIED, PAGE_TICK, OPEN = (
    "met-evidence", "ticked", "carried", "met-carried", "page-tick", "open")
#: The states that count as met.
MET = (MET_EVIDENCE, TICKED, MET_CARRIED, PAGE_TICK)


@dataclass(frozen=True)
class Item:
    check: str
    statement: str
    state: str
    #: The ids of the records that meet it: evidence ids, follow-up ids, the
    #: approver, or the document a page tick was read from.
    records: tuple = ()


def listed_checks(view, which):
    """`[(check id, statement)]` of the configured list, in order. An issue read
    without a configuration (a project with no `compass.yml`, an issue with no
    generation) is judged by the shipped default's lists, so the guardrail does not
    go quiet on it."""
    stage, side = LISTS[which]
    config = view.config if view is not None else _shipped_default()
    named = ((config.get("stages") or {}).get(stage) or {}).get(side) or []
    checks = config.get("checks") or {}
    out = []
    for check_id in dict.fromkeys(named):
        check = checks.get(check_id)
        statement = check.get("statement") if isinstance(check, dict) else None
        out.append((str(check_id), " ".join(str(statement or check_id).split())))
    return out


def _shipped_default():
    """The `stages` and `checks` catalogues of the shipped default preset."""
    import os

    from compass_pkg.core import FRAMEWORK_ROOT, load_yaml
    folder = os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default")
    return {"stages": (load_yaml(os.path.join(folder, "stages.yml")) or {}).get("stages"),
            "checks": (load_yaml(os.path.join(folder, "checks.yml")) or {}).get("checks")}


def _dicts(value):
    return [e for e in value or [] if isinstance(e, dict)]


def accepted_types():
    from compass_pkg.checks import _DOD_ACCEPTED_EVIDENCE_TYPES
    return _DOD_ACCEPTED_EVIDENCE_TYPES


def state_of(task, check_id, accepted):
    """`(state, record ids)` of one check."""
    ids = tuple(str(e.get("id")) for e in _dicts(task.get("evidence"))
                if check_id in (e.get("meets") or []) and e.get("type") in accepted)
    if ids:
        return MET_EVIDENCE, ids
    claims = [e for e in _dicts(task.get("evidence"))
              if e.get("type") == "human-approval" and e.get("check") == check_id
              and e.get("decision") in ("approved", "rejected")]
    if claims and claims[-1].get("decision") == "approved":
        return TICKED, (str(claims[-1].get("approver") or "a person"),)
    deferred = [f for f in _dicts(task.get("follow_ups")) if f.get("defers") == check_id]
    resolved = tuple(str(f.get("id")) for f in deferred if f.get("status") == "resolved")
    if resolved:
        return MET_CARRIED, resolved
    for tick in _dicts(task.get("page_ticks")):
        if tick.get("check") == check_id:
            return PAGE_TICK, (str(tick.get("source") or "a document"),)
    if deferred:
        return CARRIED, tuple(str(f.get("id")) for f in deferred)
    return OPEN, ()


def items(task, task_dir, view, which):
    """The `Item` of each check in the list `which` (a key of `LISTS`)."""
    accepted = accepted_types()
    out = []
    for check_id, statement in listed_checks(view, which):
        state, records = state_of(task, check_id, accepted)
        out.append(Item(check_id, statement, state, records))
    return out


# --- what the commands that record an item check -------------------------------

def unlisted_problem(view, check_id, command):
    """Why `command` cannot record `check_id`, or None when the issue lists it. The
    message names the check and lists the items the issue does list."""
    lists = {which: [c for c, _ in listed_checks(view, which)] for which in LISTS}
    if any(check_id in ids for ids in lists.values()):
        return None
    shown = "; ".join("%s: %s" % (TITLES[w], ", ".join(ids) or "no item")
                      for w, ids in lists.items() if ids or w in ("dod", "dor"))
    return ("%s: '%s' is not an item of this issue's Definition of Done or Ready, or of a "
            "stage exit list. The issue lists - %s." % (command, check_id, shown))


def evidence_type_problem(evidence_type, command):
    """Why evidence of this type cannot meet an item, or None."""
    accepted = accepted_types()
    if evidence_type in accepted:
        return None
    return ("%s: evidence of type '%s' cannot meet an item. The accepted types are %s."
            % (command, evidence_type, ", ".join(sorted(accepted))))


def open_hint(check_id):
    """What a reader does to record an item that has no record."""
    return ("record it with `compass evidence add ... --meets %s` or "
            "`compass gate pass ... --meets %s`, `compass follow-up add ... --defers %s`, "
            "or a person's `compass evidence approve --check %s`"
            % (check_id, check_id, check_id, check_id))
