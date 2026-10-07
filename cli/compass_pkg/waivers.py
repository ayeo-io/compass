# compass_pkg.waivers - who may depart from a parent, and whether the approval holds
"""Waivers (ADR-039): who may depart from a parent, and whether the approval holds.

A waiver sits in the catalogue entry it excuses and writes `reason` and
`approved_by`, plus `approved_on` in the project file. The CLI derives the
rest and never reads a written value for it: the fields from the entry's
operation, the scope from the layer, and the covered revision from the pin
(project) or the issue's generation (issue). There is no approvals file and no
`covers` field.

The module is pure. It takes layer documents, resolved configurations and an
evidence registry as data, reads no file, writes none, and no command calls it
yet. The later lint, update and reassess steps call `check`, `describe`,
`recheck` and `attribute`. The CLI checks that a name is in a list and that a
date is not in the future; it never authenticates the person.
"""
# DEPENDENCY: standard library (copy, datetime, collections);
# compass_pkg.catalogue_spec, compass_pkg.classify (the classify function)
# and compass_pkg.core (CompassError, only). Nothing imports this module yet.
from __future__ import annotations

import copy
import datetime
from collections import namedtuple

from compass_pkg import catalogue_spec as spec
from compass_pkg.classify import classify as _classify
from compass_pkg.core import CompassError

OPERATIONS = ("set", "replace", "remove")
LEGACY = "LEGACY"
UNAPPROVED = "UNAPPROVED"
# What a waiver writes. `covers` is not here on purpose: the covered revision
# is derived, so a written one is a fault.
WRITTEN = {"project": ("reason", "approved_by", "approved_on"),
           "issue": ("reason", "approved_by")}

WHOLE_ENTRY = "(entry)"
REFUSED = ("loosening", "incomparable")   # the classes that need an excuse

Waiver = namedtuple("Waiver", "id scope catalogue entry operation fields body")
Finding = namedtuple("Finding", "code level waiver_id message")
Invalidation = namedtuple("Invalidation", "waiver_id entry field old new project reason")
Attribution = namedtuple("Attribution", "result residual excused refusal unneeded")


def _fault(code, waiver_id, message, level="error"):
    return Finding(code, level, waiver_id, message)


def _fields_of(catalogue, operation, entry):
    """The fields the entry's operation changes."""
    if operation == "set":
        changes = entry.get("set")
        # `locked` is a lock's, and a waiver never excuses a lock refusal.
        return tuple(k for k in changes if k != "locked") \
            if isinstance(changes, dict) else ()
    if operation == "replace":
        return tuple(k for k in entry
                     if k in spec.FIELDS[catalogue] and k != "locked")
    return (WHOLE_ENTRY,)


def find(layer_doc, scope):
    """`(waivers, faults)` for every entry of a layer document that holds a
    `waiver`. The scope is the layer's: `project` or `issue`."""
    found, faults = [], []
    for catalogue in spec.CATALOGUES:
        entries = layer_doc.get(catalogue)
        if not isinstance(entries, dict):
            continue
        for entry_id, entry in entries.items():
            if not isinstance(entry, dict) or "waiver" not in entry:
                continue
            waiver_id = f"{scope}:{catalogue}.{entry_id}"
            held = [op for op in OPERATIONS if op in entry]
            if len(held) != 1:
                faults.append(_fault(
                    "W-NO-OPERATION", waiver_id,
                    "a waiver sits in an entry that has set, replace or remove "
                    "(one of them)"))
                continue
            found.append(Waiver(waiver_id, scope, catalogue, entry_id, held[0],
                                _fields_of(catalogue, held[0], entry),
                                entry["waiver"]))
    return found, faults


def _date(value):
    """A date from a date or an ISO date string, or None."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _text(value):
    return isinstance(value, str) and value.strip() != ""


def check_shape(waiver, today):
    """Findings about what the waiver writes, before anyone is asked who
    approved it. `today` is a `datetime.date`."""
    body, wid, out = waiver.body, waiver.id, []
    if not isinstance(body, dict):
        return [_fault("W-SHAPE", wid, "a waiver is a mapping of reason and approved_by")]
    for key in body:
        if key not in WRITTEN[waiver.scope] and not (
                key == "approved_on" and waiver.scope == "issue"):
            note = (" The covered revision is derived and never written."
                    if key == "covers" else "")
            out.append(_fault("W-KEY-UNKNOWN", wid,
                              f"{key} is not a field of a {waiver.scope} waiver; it "
                              f"writes {', '.join(WRITTEN[waiver.scope])}.{note}"))
    if not _text(body.get("reason")):
        out.append(_fault("W-REASON", wid, "a waiver needs a reason"))
    approver = body.get("approved_by")
    if not _text(approver):
        out.append(_fault("W-APPROVED-BY", wid, "a waiver needs approved_by"))
    if approver == UNAPPROVED:
        out.append(_fault("W-UNAPPROVED", wid,
                          "approved_by is UNAPPROVED: nobody has approved this departure"))
    if waiver.scope == "issue":
        if approver == LEGACY:
            out.append(_fault("W-LEGACY-ISSUE", wid,
                              "LEGACY is a migration shape for project waivers; an "
                              "issue waiver names a human-approval record"))
        if "approved_on" in body:
            out.append(_fault("W-APPROVED-ON-ISSUE", wid,
                              "an issue waiver has no approved_on: the approval record "
                              "carries its own timestamp"))
        return out
    if approver == LEGACY:
        if "approved_on" in body:
            out.append(_fault("W-LEGACY-DATED", wid,
                              "a LEGACY waiver has no approved_on"))
        else:
            out.append(_fault("W-LEGACY", wid, "no approval recorded: migrated from a "
                              "waived entry", "warning"))
        return out
    if "approved_on" not in body or body["approved_on"] is None:
        if approver != UNAPPROVED:
            out.append(_fault("W-APPROVED-ON-MISSING", wid,
                              "a project waiver needs approved_on"))
        return out
    given = _date(body["approved_on"])
    if given is None:
        out.append(_fault("W-APPROVED-ON-FORM", wid,
                          "approved_on is not a date (write YYYY-MM-DD)"))
    elif given > today:
        out.append(_fault("W-APPROVED-ON-FUTURE", wid,
                          f"approved_on {given.isoformat()} is later than today "
                          f"({today.isoformat()})"))
    return out


def allowed_approvers(waiver, project, parent):
    """`(names, finding)`: who may approve this waiver, from the layer above
    the one it sits in (ADR-039). `project` and `parent` are layer documents
    or None. An issue waiver takes the project's `approvers.issue-waiver`, a
    project waiver the parent's `approvers.project-waiver`, and both fall back
    to the project's `owner`. No project `owner` fails, whatever lists exist."""
    wid = waiver.id
    owner = (project or {}).get("owner")
    if not _text(owner):
        return [], _fault("W-NO-OWNER", wid,
                          "no owner is declared in the project file, so nobody may "
                          "approve a waiver")
    kind, source = (("issue-waiver", project) if waiver.scope == "issue"
                    else ("project-waiver", parent))
    held = (source or {}).get("approvers")
    if held is not None and not isinstance(held, dict):
        return [], _fault("W-APPROVERS-SHAPE", wid,
                          "approvers is a mapping of approver kind to a list of names")
    listed = (held or {}).get(kind)
    if listed is None:
        return [owner], None
    if not isinstance(listed, list) or not all(_text(n) for n in listed):
        return [], _fault("W-APPROVERS-SHAPE", wid,
                          f"approvers.{kind} is a list of names")
    return list(listed), None


def check(waiver, *, today, project, parent, registry=(), described=None):
    """Findings in the design's order: shape, authority, approval. The check
    stops at the first stage that finds an error, so one fault is not
    reported again as a second. A warning does not stop it."""
    out = check_shape(waiver, today)
    if any(f.level == "error" for f in out):
        return out
    if waiver.scope == "project" and waiver.body.get("approved_by") == LEGACY:
        return out
    names, fault = allowed_approvers(waiver, project, parent)
    if fault:
        return out + [fault]
    if waiver.scope == "project":
        approver = waiver.body["approved_by"]
        if approver not in names:
            out.append(_fault("W-APPROVER-NOT-ALLOWED", waiver.id,
                              f"{approver} may not approve this waiver; "
                              f"{_names(names)}"))
        return out
    return out + check_approval(waiver, names, registry, described)


def _names(names):
    return ("the approvers are " + ", ".join(names)) if names else "no approver is named"


APPROVAL_FIELDS = ("approver", "role", "scope", "timestamp")


def _same_values(recorded, derived):
    """True when the record names the same fields, with the same parent and
    new value for each, as the derived waiver."""
    if not isinstance(recorded, dict) or set(recorded) != set(derived):
        return False
    return all(isinstance(recorded[f], dict) and {"from", "to"} <= set(recorded[f])
               and recorded[f].get("from") == derived[f].get("from")
               and recorded[f].get("to") == derived[f].get("to") for f in derived)


def check_approval(waiver, names, registry, described):
    """Findings about the `human-approval` record an issue waiver's
    `approved_by` names. The record must say who approved (an allowed name)
    and which entry and values it approved, so one approval cannot excuse a
    different waiver. The CLI checks the fields; it never authenticates the
    person (ADR-039)."""
    wid, ref = waiver.id, waiver.body.get("approved_by")
    record = next((r for r in registry if isinstance(r, dict) and r.get("id") == ref),
                  None)
    if record is None:
        return [_fault("W-APPROVAL-MISSING", wid,
                       f"{ref} is not a record in the issue's evidence")]
    if record.get("type") != "human-approval":
        return [_fault("W-APPROVAL-TYPE", wid,
                       f"{ref} is a {record.get('type')} record, not a human-approval")]
    if record.get("decision") != "approved":
        return [_fault("W-APPROVAL-DECISION", wid,
                       f"{ref} does not hold decision: approved")]
    missing = [k for k in APPROVAL_FIELDS if not record.get(k)]
    if missing:
        return [_fault("W-APPROVAL-FIELDS", wid,
                       f"{ref} is missing {', '.join(missing)}")]
    if record["approver"] not in names:
        return [_fault("W-APPROVER-NOT-ALLOWED", wid,
                       f"{record['approver']} may not approve this waiver; "
                       f"{_names(names)}")]
    if described is None or described.get("id") != wid:
        return [_fault("W-APPROVAL-UNCHECKED", wid,
                       "the waiver's values were not derived for this waiver, so the "
                       "record cannot be matched to it")]
    entry = f"{waiver.catalogue}.{waiver.entry}"
    named = record.get("waiver")
    if not (isinstance(named, dict) and named.get("scope") == "issue"
            and named.get("entry") == entry
            and _same_values(named.get("fields"), described.get("fields") or {})):
        return [_fault("W-APPROVAL-WAIVER", wid,
                       f"{ref} does not approve this waiver: it must name scope "
                       f"issue, entry {entry} and each waived field's from and to")]
    return []


def covered_revision(scope, extends=None, versions=None):
    """The revision an approval was given against, derived and never written.
    A project waiver covers the `extends:` pin: the string, or the `from` of
    its map form. An issue waiver covers the project revision recorded in the
    issue's generation (`versions['project']['digest']`). None when the
    source is not given."""
    if scope == "project":
        ref = extends.get("from") if isinstance(extends, dict) else extends
        return {"kind": "parent", "ref": ref} if _text(ref) else None
    digest = ((versions or {}).get("project") or {}).get("digest")
    return {"kind": "project-revision", "digest": digest} if _text(digest) else None


def _value(config, waiver, field):
    """One waived field's value in a resolved configuration, or None."""
    entry = ((config or {}).get(waiver.catalogue) or {}).get(waiver.entry)
    if field == WHOLE_ENTRY:
        return copy.deepcopy(entry)
    return copy.deepcopy(entry.get(field)) if isinstance(entry, dict) else None


def describe(waiver, parent_config, child_config, covered):
    """The record of a waiver that a generation keeps: the parent value
    (`from`) each waived field had when the approval was given, the value the
    layer sets (`to`) and the covered revision. A later re-check compares
    `from` with the parent it meets then. Nothing in it is copied from the
    configurations by reference."""
    record = {
        "id": waiver.id, "scope": waiver.scope,
        "entry": f"{waiver.catalogue}.{waiver.entry}", "operation": waiver.operation,
        "fields": {f: {"from": _value(parent_config, waiver, f),
                       "to": _value(child_config, waiver, f)} for f in waiver.fields},
        "approved_by": waiver.body.get("approved_by"),
    }
    given = waiver.body.get("approved_on")
    if waiver.scope == "project" and given is not None:
        day = _date(given)
        record["approved_on"] = day.isoformat() if day else given
    record["covered"] = copy.deepcopy(covered)
    return record


def recheck(records, new_parent):
    """The waivers a moved revision invalidates. Each record is what
    `describe` made: the parent value of every waived field when the approval
    was given. One question is asked of each field: is the parent's value now
    different? A list or a whole entry compares as a whole. A change to any
    other field or entry invalidates nothing, so a parent patch that does not
    touch a waived field asks for no new approval. An entry the new parent
    does not define invalidates the waiver."""
    out = []
    for record in records:
        catalogue, entry_id = record["entry"].split(".", 1)
        held = ((new_parent or {}).get(catalogue) or {}).get(entry_id)
        if held is None:
            out.append(Invalidation(
                record["id"], record["entry"], None, None, None, None,
                f"{record['entry']}: the new parent no longer defines this entry, so "
                f"the waiver covers nothing"))
            continue
        for field, seen in record["fields"].items():
            now = copy.deepcopy(held if field == WHOLE_ENTRY else held.get(field))
            if now != seen["from"]:
                out.append(Invalidation(
                    record["id"], record["entry"], field, seen["from"], now, seen["to"],
                    f"{record['entry']}.{field}: the parent value changed from "
                    f"{seen['from']!r} to {now!r}; the project value is "
                    f"{seen['to']!r}"))
    return out


def _revert(child, parent, waivers):
    """The child with each waived entry put back to the parent's value: the
    residual configuration."""
    out = copy.deepcopy(child)
    for w in waivers:
        held = ((parent or {}).get(w.catalogue) or {}).get(w.entry)
        table = out.setdefault(w.catalogue, {})
        if held is None:
            table.pop(w.entry, None)
        else:
            table[w.entry] = copy.deepcopy(held)
    return out


def _apply_alone(base, child, waiver):
    """The residual with only this waiver's entry as the child wrote it. The
    design reverts the one entry and compares with the residual; with a single
    waiver those two are the same configuration, so this applies it instead."""
    out = copy.deepcopy(base)
    held = (child.get(waiver.catalogue) or {}).get(waiver.entry)
    table = out.setdefault(waiver.catalogue, {})
    if held is None:
        table.pop(waiver.entry, None)
    else:
        table[waiver.entry] = copy.deepcopy(held)
    return out


def _needed(parent, base, child, waiver, classify_kwargs):
    """True when the waiver's entry, alone, needs an excuse. An entry that
    cannot stand alone (a removed check a gate still lists) is judged needed:
    a false "unneeded" would drop an approval that something rests on."""
    try:
        alone = _classify(parent, _apply_alone(base, child, waiver), **classify_kwargs)
    except CompassError:
        return True
    return alone.result in REFUSED


def _refusal(classification):
    shown = classification.to_json()
    return {"result": shown["result"], "reason": shown["reason"],
            "point": shown["first_mixed"] or shown["first_looser"]}


def attribute(parent, child, waivers, **classify_kwargs):
    """Which loosening each waiver excuses. `parent` and `child` are resolved
    configurations (an issue layer is merged onto the project's first).
    `excused` is not lock-aware: the locks increment refuses a change to a
    locked entry before attribution, and a waiver never excuses that refusal.

    The residual layer is the child with every waived entry reverted to the
    parent's value. If it is `equivalent` or `tightening`, every loosening and
    every change that cannot be compared comes from a waived entry, and each is
    excused for the fields its operation changes. If it is `loosening` or
    `incomparable`, the layer is refused with the residual's first point:
    a waiver never excuses a change on another entry. An unwaived tightening
    that only offsets a waived loosening is seen apart from it, which can
    refuse and never excuses more than a waiver covers.

    A waiver is unneeded when its entry, applied alone to the residual,
    needs no excuse. That costs one more classification per waiver."""
    classify_kwargs.setdefault("early_exit", True)
    base = _revert(child, parent, waivers)
    residual = _classify(parent, base, **classify_kwargs)
    if residual.result in REFUSED:
        return Attribution("refused", residual, {}, _refusal(residual), [])
    excused = {w.id: list(w.fields) for w in waivers}
    unneeded = [w.id for w in waivers
                if not _needed(parent, base, child, w, classify_kwargs)]
    return Attribution("excused" if waivers else "accepted", residual, excused, None, unneeded)
