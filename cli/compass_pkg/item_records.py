# compass_pkg.item_records - which Definition of Done and Ready items the records meet
"""Read the manifest records that meet an exit-list or entry-list item.

The Definition of Done is the issue's configured build exit list, or the
`verify` exit list of a configuration that still declares the legacy stages,
and the Definition of Ready its `plan` entry list. The `plan` and `breakdown`
exit lists are read the same way, whatever capability says they are
evaluated (the page that shows them is not the evaluator). A path issue
(ADR-092) has only the Definition of Done (`lists_of`). An item is a check
id in one of those lists. One of four records meets it, and a command writes
each:

- **met by evidence**: an `evidence` entry of an accepted type with
  `meets: [<check>]`;
- **ticked by a person**: the newest `human-approval` record for the check is
  `approved`;
- **carried to a follow-up**: a follow-up with `defers: <check>`. On a path
  issue (ADR-092) it meets the item only when it links to a GitHub issue
  (`github: {repo, number}`), outstanding or resolved, because the linked issue
  tracks the work (ADR-093). On an issue assessed before 9.0.0 it carries the
  item to ship while it is outstanding, and meets it once it is resolved;
- **ticked on the page before 7.0.0**: an entry of `page_ticks`, written only by
  `compass issue migrate`.

An item with none of these is open. Only this reader counts a page tick; the
approval check never does.

This module reads records. It imports no command module and no renderer, so the
renderers, the stage lists and `dod-evidence-typed` can all use it.
"""
# DEPENDENCY: standard library (dataclasses); compass_pkg.path_stages,
# compass_pkg.stable_ids. The accepted
# evidence types are read from compass_pkg.checks inside `items`, because checks
# imports the masking module and this one is imported by the renderers. The
# GitHub target pattern is read from compass_pkg.issue_link inside `linked_issue`
# for the same reason.
from __future__ import annotations

from dataclasses import dataclass

from compass_pkg.path_stages import is_path_issue
from compass_pkg.stable_ids import STAGE_BREAKDOWN, STAGE_BUILD, STAGE_PLAN, STAGE_VERIFY

#: The lists: `dod` is the build exit list (the `verify` exit list of a legacy
#: configuration, `_list_of`), `dor` the `plan` entry list.
LISTS = {"dod": (STAGE_BUILD, "exit"), "dor": (STAGE_PLAN, "entry"),
         "plan-exit": (STAGE_PLAN, "exit"), "breakdown-exit": (STAGE_BREAKDOWN, "exit")}
TITLES = {"dod": "Definition of Done", "dor": "Definition of Ready",
          "plan-exit": "Plan exit checks", "breakdown-exit": "Breakdown exit checks"}
#: What a block says when its list is empty. The two stage exit lists are empty in the
#: shipped default; the Definition of Done and Ready keep one sentence.
EMPTY = {"plan-exit": "No exit checks are configured for the plan stage.",
         "breakdown-exit": "No exit checks are configured for the breakdown stage."}

MET_EVIDENCE, TICKED, CARRIED, MET_CARRIED, PAGE_TICK, LINKED, OPEN = (
    "met-evidence", "ticked", "carried", "met-carried", "page-tick", "linked", "open")
#: The states that count as met. `LINKED` is a path issue's follow-up that names a
#: GitHub issue.
MET = (MET_EVIDENCE, TICKED, MET_CARRIED, PAGE_TICK, LINKED)


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
    config = view.config if view is not None else _shipped_default()
    stages = config.get("stages") or {}
    stage, side = _list_of(stages, which)
    named = (stages.get(stage) or {}).get(side) or []
    checks = config.get("checks") or {}
    out = []
    for check_id in dict.fromkeys(named):
        check = checks.get(check_id)
        statement = check.get("statement") if isinstance(check, dict) else None
        out.append((str(check_id), " ".join(str(statement or check_id).split())))
    return out


def _list_of(stages, which):
    """`(stage, side)` of the list `which` in a configuration's `stages` map. A
    configuration that declares a `verify` stage, as every one before 9.0.0 and
    every stored generation does, holds its Definition of Done there."""
    if which == "dod" and STAGE_VERIFY in stages:
        return STAGE_VERIFY, "exit"
    return LISTS[which]


def lists_of(task):
    """The keys of `LISTS` an issue has. A path issue owes no Definition of Ready
    and runs no plan or breakdown stage, so it has only the Definition of Done."""
    return ("dod",) if is_path_issue(task) else tuple(LISTS)


def _shipped_default():
    """The `stages` and `checks` catalogues of the check set (ADR-094)."""
    from compass_pkg import check_set
    loaded = check_set.load()
    return {"stages": loaded.get("stages"), "checks": loaded.get("checks")}


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
    if is_path_issue(task):
        # The one follow-up rule of a path issue (ADR-093): only a follow-up that
        # links to a GitHub issue meets the item, whatever its status.
        linked = tuple(str(f.get("id")) for f in _dicts(task.get("follow_ups"))
                       if f.get("defers") == check_id and linked_issue(f) is not None)
        return (LINKED, linked) if linked else (OPEN, ())
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


def linked_issue(follow_up):
    """`(repo, number)` of the GitHub issue a follow-up links to, or None. The
    value must be one `compass issue link set` would accept, so a field edited by
    hand into another shape links nothing."""
    from compass_pkg.issue_link import parse_target
    value = follow_up.get("github") if isinstance(follow_up, dict) else None
    if not isinstance(value, dict):
        return None
    repo, number = value.get("repo"), value.get("number")
    if not isinstance(repo, str) or not isinstance(number, int) or isinstance(number, bool):
        return None
    return (repo, number) if parse_target("%s#%d" % (repo, number)) == (repo, number) else None


def items(task, task_dir, view, which):
    """The `Item` of each check in the list `which` (a key of `LISTS`)."""
    accepted = accepted_types()
    out = []
    for check_id, statement in listed_checks(view, which):
        state, records = state_of(task, check_id, accepted)
        out.append(Item(check_id, statement, state, records))
    return out


# --- what the commands that record an item check -------------------------------

def unlisted_problem(view, check_id, command, task=None):
    """Why `command` cannot record `check_id`, or None when the issue lists it. The
    message names the check and lists the items the issue does list. With the
    issue's manifest, only its own lists count (`lists_of`)."""
    lists = {which: [c for c, _ in listed_checks(view, which)]
             for which in (lists_of(task) if task is not None else LISTS)}
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


#: The command a path issue's open item names when it is carried to a follow-up.
LINKED_FOLLOW_UP = ('`compass follow-up add FU-<id> --defers %s --github owner/repo#N '
                    '--summary "..."`')


def open_hint(check_id, task=None):
    """What a reader does to record an item that has no record. On a path issue a
    follow-up meets the item only with `--github`, and a follow-up that defers it
    without a link is named, so the reader knows why it does not count."""
    if task is not None and is_path_issue(task):
        unlinked = [str(f.get("id")) for f in _dicts(task.get("follow_ups"))
                    if f.get("defers") == check_id and linked_issue(f) is None]
        note = ("; follow-up %s defers it but links to no GitHub issue, so it meets "
                "nothing" % ", ".join(unlinked)) if unlinked else ""
        return ("record it with `compass evidence add ... --meets %s` or "
                "`compass gate pass ... --meets %s`, " % (check_id, check_id)
                + LINKED_FOLLOW_UP % check_id
                + ", or a person's `compass evidence approve --check %s`%s" % (check_id, note))
    return ("record it with `compass evidence add ... --meets %s` or "
            "`compass gate pass ... --meets %s`, `compass follow-up add ... --defers %s`, "
            "or a person's `compass evidence approve --check %s`"
            % (check_id, check_id, check_id, check_id))
