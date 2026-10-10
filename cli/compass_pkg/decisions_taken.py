# compass_pkg.decisions_taken - decisions an agent took for the person
"""A requirement decision an agent took is shown to the person at a checkpoint.

The manifest's `decisions_taken` holds one entry per decision:

    id, question, resolution, by (an agent), stage, status, reason

`status` is `open`, `confirmed` or `reopened`. `reason` is written only by a
reopen and never removed, so `compass retro --decisions` can tell a decision
that was changed from one that was confirmed as taken.

This module owns:

- the ledger reader and `compass issue decision add` (`--from-ledger` or by
  hand);
- `compass issue decision set`, which reopens a decision and needs a terminal;
- `waiting`, which `compass next` calls to decide whether the issue waits at a
  checkpoint;
- `approve_set`, the `--decisions` form of `compass evidence approve`;
- `report`, which `compass retro --decisions` prints.

Only `approve_set` writes `confirmed`, as one `artifact-approval` record for
the whole set. The record is never a `human-approval` record, so the sign-off
of guardrail `G5` cannot be met by it. Owning decision:
`architecture/decisions/ADR-050-*.md`.
"""
# DEPENDENCY: standard library (os, re, json); compass_pkg.core, terminal,
# approval_records, stable_ids. next_cmd and approve_cmd are imported inside
# the functions that need them, because both import this module.
from __future__ import annotations

import json
import os
import re

from compass_pkg.core import (CompassError, issue_arg, load_manifest, now_iso,
                              resolve_issue_dir, save_manifest)
from compass_pkg.stable_ids import STAGE_IDS
from compass_pkg.terminal import say

OPEN, CONFIRMED, REOPENED = "open", "confirmed", "reopened"
LEDGER_REASON = "the resolution changed in the ledger"
#: Agents that always count, whether or not the plugin's `agents/` folder is found.
BASE_AGENTS = ("builder", "spec-author", "planner")
SCOPE = "requirement decisions"

_ID = r"[A-Z][A-Z0-9]*-?\d+"
_HEADING = re.compile(r"^###\s+(%s)\s+-\s+(.*?)\s*$" % _ID)
_BULLET = re.compile(r"^(\s*)[-*]\s+")
_LABEL = re.compile(
    r"^(\s*)[-*]\s+\*\*(Question|Resolution|Decided by)(?:\s*\([^)]*\))?\s*:?\*\*\s*:?\s*(.*)$")


def agent_names():
    """The names a ledger's "Decided by" can use: the three that always count
    and every stem in the plugin's `agents/` folder."""
    names = set(BASE_AGENTS)
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "agents")
    try:
        names.update(os.path.splitext(n)[0] for n in os.listdir(folder) if n.endswith(".md"))
    except OSError:
        pass
    return sorted(names, key=lambda n: (-len(n), n))


def _squash(text):
    return " ".join(str(text or "").split())


def agent_in(decided_by):
    """The agent a "Decided by" text names, or None. Case is ignored, so is a
    leading "the", and so is any text after the name."""
    text = _squash(decided_by).lower()
    if text.startswith("the "):
        text = text[4:]
    for name in agent_names():
        if re.match(re.escape(name) + r"(?![\w-])", text):
            return name
    return None


def parse_ledger(text):
    """Every `### <id> - <title>` block of a requirements review as
    `{id, question, resolution, decided_by}`. A bullet runs until the next
    bullet at the same or a shallower indent; a label may carry a
    parenthesis, as in "Resolution (working answer, ...)"."""
    blocks, current = [], None
    for line in text.splitlines():
        heading = _HEADING.match(line)
        if heading:
            current = {"id": heading.group(1), "lines": []}
            blocks.append(current)
        elif line.startswith("#"):
            current = None
        elif current is not None:
            current["lines"].append(line)
    out = []
    for block in blocks:
        found, label, indent = {}, None, 0
        for line in block["lines"]:
            bullet = _BULLET.match(line)
            labelled = _LABEL.match(line)
            if labelled:
                label, indent = labelled.group(2), len(labelled.group(1))
                found[label] = labelled.group(3)
            elif bullet and len(bullet.group(1)) <= indent:
                label = None
            elif label:
                found[label] += " " + line
        out.append({"id": block["id"], "question": _squash(found.get("Question")),
                    "resolution": _squash(found.get("Resolution")),
                    "decided_by": _squash(found.get("Decided by"))})
    return out


def _review_text(task_dir):
    """The requirements review, registered or not: the file `compass next`
    counts as refine's record."""
    from compass_pkg.core import artifact_path, unregistered_document
    name = "requirements-review.md"
    path = artifact_path(task_dir, name)
    if not os.path.isfile(path):
        path = unregistered_document(task_dir, name)
    if not path:
        raise CompassError(
            "compass issue decision add --from-ledger: this issue has no requirements "
            "review to read. Write it at refine first, or record one decision with "
            "`compass issue decision add <id> --question ... --resolution ... --by ... "
            "--stage ...`.")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def add_from_ledger(task, task_dir):
    """Reconcile `decisions_taken` with the requirements review, in place.
    Returns a line for each entry added or changed. The ledger id is the key.

    - a new id decided by an agent is added at stage refine, open;
    - a changed question is updated and the status kept;
    - a changed resolution is updated and the entry is reopened;
    - an id no longer decided by an agent, or no longer in the ledger, stays.
    """
    held = task.setdefault("decisions_taken", [])
    by_id = {e.get("id"): e for e in held if isinstance(e, dict)}
    notes = []
    for block in parse_ledger(_review_text(task_dir)):
        agent = agent_in(block["decided_by"])
        if agent is None or not block["question"] or not block["resolution"]:
            continue
        entry = by_id.get(block["id"])
        if entry is None:
            entry = {"id": block["id"], "question": block["question"],
                     "resolution": block["resolution"], "by": agent, "stage": "refine",
                     "status": OPEN}
            held.append(entry)
            by_id[block["id"]] = entry
            notes.append("added %s (%s)" % (block["id"], agent))
            continue
        changed = []
        if _squash(entry.get("question")) != block["question"]:
            entry["question"] = block["question"]
            changed.append("question")
        if _squash(entry.get("resolution")) != block["resolution"]:
            entry["resolution"] = block["resolution"]
            entry["status"], entry["reason"] = REOPENED, LEDGER_REASON
            changed.append("resolution, now reopened")
        if entry.get("by") != agent:
            entry["by"] = agent
            changed.append("decider")
        if changed:
            notes.append("updated %s: %s" % (block["id"], ", ".join(changed)))
    if not held:
        task.pop("decisions_taken")
    return notes


def cmd_decision_add(args):
    task_dir = resolve_issue_dir(args.task)
    task, path = load_manifest(task_dir)
    if args.from_ledger:
        if args.id:
            raise CompassError("compass issue decision add: give an id or --from-ledger, "
                               "not both.")
        notes = add_from_ledger(task, task_dir)
        if notes:
            save_manifest(task, path)
        return say(args, "compass issue decision add: %s." % (
                       "%d change(s) from the ledger" % len(notes) if notes
                       else "nothing to add from the ledger"),
                   detail=notes, changes=notes)
    missing = [flag for flag, value in (("an id", args.id), ("--question", args.question),
                                        ("--resolution", args.resolution), ("--by", args.by),
                                        ("--stage", args.stage)) if not value]
    if missing:
        raise CompassError("compass issue decision add: give %s, or use --from-ledger."
                           % ", ".join(missing))
    if agent_in(args.by) != _squash(args.by).lower():
        raise CompassError("compass issue decision add: --by must name an agent (%s), not "
                           "'%s'. A decision a person took needs no record here."
                           % (", ".join(sorted(agent_names())), args.by))
    if args.stage not in STAGE_IDS:
        raise CompassError("compass issue decision add: '%s' is not a stage; use one of %s."
                           % (args.stage, ", ".join(STAGE_IDS)))
    held = task.setdefault("decisions_taken", [])
    if any(isinstance(e, dict) and e.get("id") == args.id for e in held):
        raise CompassError("compass issue decision add: %s exists already. Change it with "
                           "`compass issue decision set`." % args.id)
    held.append({"id": args.id, "question": _squash(args.question),
                 "resolution": _squash(args.resolution), "by": _squash(args.by).lower(),
                 "stage": args.stage, "status": OPEN})
    save_manifest(task, path)
    return say(args, "compass issue decision add: recorded %s, taken by %s at %s."
               % (args.id, _squash(args.by).lower(), args.stage),
               detail=["entry : %s in manifest.yml decisions_taken" % args.id],
               decision_id=args.id)


def cmd_decision_set(args):
    from compass_pkg.approve_cmd import _terminal_attached
    if not _terminal_attached():
        raise CompassError("compass issue decision set: this needs a terminal on standard "
                           "input. Changing a decision is a person's act, so run the "
                           "command yourself in a terminal.")
    if args.status != REOPENED:
        raise CompassError("compass issue decision set: only --status reopened is accepted. "
                           "A decision becomes confirmed through `compass evidence approve "
                           "--decisions`.")
    reason = _squash(args.reason)
    if not reason:
        raise CompassError("compass issue decision set: --reason must say why the decision "
                           "is reopened.")
    task_dir = resolve_issue_dir(args.task)
    task, path = load_manifest(task_dir)
    entry = next((e for e in task.get("decisions_taken") or []
                  if isinstance(e, dict) and e.get("id") == args.id), None)
    if entry is None:
        raise CompassError("compass issue decision set: this issue records no decision %s."
                           % args.id)
    entry["status"], entry["reason"] = REOPENED, reason
    save_manifest(task, path)
    return say(args, "compass issue decision set: %s reopened." % args.id,
               detail=["reason : %s" % reason], decision_id=args.id, status=REOPENED)


# --- the checkpoint wait ----------------------------------------------------------

def _rank(stage):
    return STAGE_IDS.index(stage) if stage in STAGE_IDS else 0


def unconfirmed(task):
    """The decisions a person has not confirmed: open and reopened ones."""
    return [e for e in task.get("decisions_taken") or []
            if isinstance(e, dict) and e.get("status") != CONFIRMED]


def waiting(task, done_stages):
    """`(stage, entries)` when the issue is at a checkpoint, else `(None, [])`.

    The issue is at the checkpoint of stage S when the records show S done, S
    is in the manifest's `checkpoints:`, and a decision taken at S or earlier
    is not confirmed. The latest such stage is reported. `entries` are the
    unconfirmed decisions taken at that stage or earlier."""
    checkpoints = task.get("checkpoints")
    checkpoints = [s for s in checkpoints if s in STAGE_IDS] if isinstance(checkpoints, list) else []
    pending = unconfirmed(task)
    for stage in reversed(STAGE_IDS):
        if stage in checkpoints and stage in done_stages:
            here = [e for e in pending if _rank(e.get("stage")) <= _rank(stage)]
            if here:
                return stage, here
    return None, []


def listing(entries):
    """The lines that show each decision to the person."""
    lines = []
    for e in entries:
        mark = e.get("status") or OPEN
        if e.get("reason") and mark == REOPENED:
            mark += ": " + _squash(e["reason"])
        lines.append("  %s [%s] taken by %s at %s: %s" % (
            e.get("id"), mark, e.get("by"), e.get("stage"), _squash(e.get("question"))))
        lines.append("    Resolution: %s" % _squash(e.get("resolution")))
    return lines


def next_lines(task, done_stages):
    """`(first_line, more_lines)` for `compass next` when decisions are
    unconfirmed: the wait line replaces the stage line at a checkpoint, and
    the list follows. `first_line` is None when the issue is not waiting."""
    stage, entries = waiting(task, done_stages)
    if stage:
        head = "Waiting at the %s checkpoint: %d decision(s) to confirm" % (stage, len(entries))
        return head, listing(entries) + [
            "Confirm them all: compass evidence approve --decisions --approver <you> "
            "--role <role> --scope \"%s\"" % SCOPE,
            "Change one: compass issue decision set <id> --status reopened --reason \"<why>\""]
    entries = unconfirmed(task)
    if entries:
        return None, ["Decisions taken for you, not yet confirmed (%d):" % len(entries)] \
            + listing(entries)
    return None, []


# --- confirming the set -------------------------------------------------------------

def _approvers_in(node, found):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "approvers" and isinstance(value, list):
                found.extend(str(one) for one in value)
            else:
                _approvers_in(value, found)
    elif isinstance(node, list):
        for one in node:
            _approvers_in(one, found)


def project_approvers(task_dir):
    """`(listed, owner)`: every name in any `approvers:` list of the project
    file, and its `owner`. Both are empty when there is no project file."""
    from compass_pkg import approval_records, layers
    owner = approval_records.project_owner(task_dir)
    listed = []
    try:
        loaded = layers.load_project_layer(layers.find_project_root(task_dir))
    except Exception:                                      # noqa: BLE001
        loaded = None
    if loaded:
        _approvers_in(loaded[0].doc, listed)
    return listed, owner


def _may_confirm(task_dir, approver):
    from compass_pkg import approval_records
    listed, owner = project_approvers(task_dir)
    if listed:
        if approval_records.approver_listed(listed, approver, owner):
            return
        raise CompassError(
            "compass evidence approve: %s is not among the approvers this project declares "
            "(%s), so the confirmation would not count." % (approver, ", ".join(sorted(set(listed)))))
    if approval_records.approver_listed([approval_records.OWNER], approver, owner):
        return
    raise CompassError(
        "compass evidence approve: this project declares no approvers, so only its owner may "
        "confirm decisions taken for the person%s." % (
            " (%s)" % owner if owner else "; it declares no owner either, so add `owner:` or "
            "an `approvers:` list to compass.yml"))


def approve_set(args):
    """The `--decisions` form of `compass evidence approve`. The verb has
    already checked the terminal and the approver's name."""
    from compass_pkg import next_cmd
    if args.decision != "approved":
        raise CompassError("compass evidence approve: --decisions records a confirmation "
                           "only. To send a decision back, run `compass issue decision set "
                           "<id> --status reopened --reason \"<why>\"`.")
    task_dir = resolve_issue_dir(args.task)
    task, path = load_manifest(task_dir)
    _may_confirm(task_dir, args.approver)
    done = next_cmd._stages_on_record(next_cmd._typed(task), task_dir)
    stage, entries = waiting(task, done)
    if stage is None:
        entries = unconfirmed(task)
        stage = max((e.get("stage") for e in entries), key=_rank, default=None)
    if not entries:
        raise CompassError("compass evidence approve: this issue has no decision waiting to "
                           "be confirmed.")
    ids = [e["id"] for e in entries]
    stamp = now_iso().replace("+00:00", "Z")
    taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
    number = 1
    while "EV-APPROVAL-DECISIONS-%d" % number in taken:
        number += 1
    evidence_id = "EV-APPROVAL-DECISIONS-%d" % number
    record = {"id": evidence_id, "type": "artifact-approval", "decisions": ids, "stage": stage,
              "approver": args.approver, "role": args.role, "decision": args.decision,
              "timestamp": stamp}
    if args.scope:
        record["scope"] = args.scope
    record.update(issue=os.path.basename(os.path.normpath(task_dir)),
                  generation=task.get("generation"))
    task.setdefault("evidence", []).append(record)
    for entry in entries:
        entry["status"] = CONFIRMED
    save_manifest(task, path)
    return say(args, "compass evidence approve: %d decision(s) confirmed by %s, recorded as %s."
               % (len(ids), args.approver, evidence_id),
               detail=["decisions : %s" % ", ".join(ids),
                       "record    : %s in manifest.yml evidence" % evidence_id],
               decisions=ids, evidence_id=evidence_id, approver=args.approver, at=stamp)


# --- retro --------------------------------------------------------------------------

def report(work_root):
    """The counts behind `compass retro --decisions`. Reads each manifest
    directly; the parse cache of ADR-049 serves `flow.py` only."""
    from compass_pkg import status_words
    from compass_pkg.core import load_yaml, manifest_path, normalize_spine
    total = confirmed = changed = never = in_flight = issues = 0
    if os.path.isdir(work_root):
        for name in sorted(os.listdir(work_root)):
            path = manifest_path(os.path.join(work_root, name))
            if not os.path.isfile(path):
                continue
            try:
                data = load_yaml(path)
            except CompassError:
                continue
            if not isinstance(data, dict):
                continue
            entries = [e for e in data.get("decisions_taken") or [] if isinstance(e, dict)]
            if not entries:
                continue
            issues += 1
            closed = status_words.is_closed(normalize_spine(data))
            for e in entries:
                total += 1
                if e.get("reason"):
                    changed += 1
                elif e.get("status") == CONFIRMED:
                    confirmed += 1
                elif closed:
                    never += 1
                else:
                    in_flight += 1

    def share(n):
        return round(100 * n / total) if total else 0
    return {"total": total, "issues": issues, "confirmed": confirmed, "changed": changed,
            "never_confirmed": never, "open_in_flight": in_flight,
            "share": {"confirmed": share(confirmed), "changed": share(changed),
                      "never_confirmed": share(never)}}


def cmd_retro_decisions(args, work_root):
    data = report(work_root)
    if getattr(args, "format", "markdown") == "json":
        print(json.dumps(data, indent=2))
        return 0
    if not data["total"]:
        print("compass retro --decisions: no decisions taken for the person are recorded yet.")
        return 0
    s = data["share"]
    print("compass retro --decisions: %d agent decisions across %d issue(s)."
          % (data["total"], data["issues"]))
    print("  %d%% confirmed (%d): confirmed as the agent took them" % (s["confirmed"], data["confirmed"]))
    print("  %d%% changed (%d): reopened by a person or by a change in the ledger"
          % (s["changed"], data["changed"]))
    print("  %d%% never confirmed (%d): still open on a done issue"
          % (s["never_confirmed"], data["never_confirmed"]))
    if data["open_in_flight"]:
        print("  %d open on an issue in flight" % data["open_in_flight"])
    return 0


# --- registration ----------------------------------------------------------------------

def register(issue_subs):
    """Add the `decision` group to `compass issue`."""
    group = issue_subs.add_parser(
        "decision", help="decisions an agent took for the person")
    subs = group.add_subparsers(dest="decision_cmd", required=True)
    add = subs.add_parser("add", help="record a decision an agent took for the person")
    add.add_argument("id", nargs="?", help="the decision's id, such as D-1")
    add.add_argument("--from-ledger", action="store_true",
                     help="read the requirements review and record each entry an agent decided")
    add.add_argument("--question")
    add.add_argument("--resolution")
    add.add_argument("--by", help="the agent that took it")
    add.add_argument("--stage", help="the stage it was taken in")
    issue_arg(add)
    add.set_defaults(func=cmd_decision_add, output_kind="hand-off")
    st = subs.add_parser("set", help="reopen a decision taken for the person")
    st.add_argument("id")
    st.add_argument("--status", required=True)
    st.add_argument("--reason", required=True)
    issue_arg(st)
    st.set_defaults(func=cmd_decision_set, output_kind="hand-off")
