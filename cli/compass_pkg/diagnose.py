#!/usr/bin/env python3
# =============================================================================
# compass_pkg.diagnose - `compass issue diagnose`
# =============================================================================
#
# Explains one run from its issue's own records, after the session is gone.
# compass retro, the friction log and compass rework-scan look across issues;
# this looks at one: each stage against the record that shows it ran, a
# timeline of the dated records, the deviations, and the questions only a
# transcript could answer. It reads and never writes.
#
# A stage's weight in the manifest is the plan, not proof the stage ran, so a
# missing record is a deviation only where the plan says a record must exist:
# a solo run writes no subtasks, a spike records no red, and an issue that has
# not landed has not reached its later stages.
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/, through core.load_yaml.
# =============================================================================

import glob
import json
import os

from compass_pkg.stable_ids import (
    APPROACH_SPIKE, STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IDS, STAGE_IMPLEMENT, STAGE_PLAN,
    STAGE_REFINE, STAGE_SHIP, STAGE_VERIFY)
from compass_pkg.core import (artifact_path, load_yaml, manifest_path,
                              resolve_issue_dir, unregistered_document)
from compass_pkg.interruptions import LOG_NAME

_NOT_RUN = {"skipped", "collapsed", "none", ""}
_ORDER = STAGE_IDS
_KINDS = ("red", "green", "acceptance")

CANNOT_SHOW = (
    "what a hook refusal or a failed check said: .compass/interruptions.log keeps only its time and kind",
    "what was said in the session, and why a step was taken: that needs the transcript",
    "how long anything took between records, and time spent with no record",
    "when a gate was passed: the manifest does not date gate passes",
    "when a review ran: a review round is dated when it was recorded, which can be later",
    "token use outside the subtasks that record a cost",
)


def _rel(root, path):
    return os.path.relpath(path, root) if path else ""


def _list(value):
    return value if isinstance(value, list) else []


def _dicts(value):
    return [v for v in _list(value) if isinstance(v, dict)]


def _records(task_dir):
    """[(kind, scenario, timestamp, command, path)] for every red, green and
    acceptance record, bound to a scenario (`red-A.json`) or not (`red.json`)."""
    out = []
    for path in sorted(glob.glob(os.path.join(task_dir, "evidence", "*.json"))):
        name = os.path.basename(path)[:-5]
        kind = next((k for k in _KINDS if name == k or name.startswith(k + "-")), None)
        if kind is None:
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        scenario = str(data.get("scenario") or name[len(kind) + 1:] or "")
        command = data.get("command") or " ".join(str(a) for a in _list(data.get("argv")))
        out.append((kind, scenario, str(data.get("timestamp") or ""), str(command or ""), path))
    return out


def _doc(task_dir, name):
    path = artifact_path(task_dir, name)
    if os.path.isfile(path):
        return path
    return unregistered_document(task_dir, name)


def _interruptions(root, slug):
    """[(timestamp, kind)] for this issue from .compass/interruptions.log."""
    path = os.path.join(root, ".compass", LOG_NAME)
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) == 3 and parts[1] == slug:
                    out.append((parts[0], parts[2]))
    except OSError:
        pass
    return out


def _landed_by_items(m):
    """`landed_by` as a list: older manifests hold a list of mappings, each
    naming a `commit`, an `issue` or an `id`; some hold one mapping or text."""
    by = m.get("landed_by")
    return by if isinstance(by, list) else [by] if by else []


def _landed_as(m):
    if m.get("land_commit"):
        return str(m["land_commit"])
    names = []
    for item in _landed_by_items(m):
        if isinstance(item, dict):
            item = item.get("commit") or item.get("issue") or item.get("id") or ""
        if item:
            names.append(str(item))
    return ", ".join(names)


def _landed_through(m):
    """The issues this one landed through, when `landed_by` names any."""
    if m.get("land_commit"):
        return ""
    return ", ".join(str(i["issue"]) for i in _landed_by_items(m)
                     if isinstance(i, dict) and i.get("issue"))


def _omitted(m):
    """{artifact kind: reason} for documents the manifest records as omitted."""
    return {str(a.get("kind")): str(a.get("reason") or "no reason recorded")
            for a in _dicts(m.get("artifacts")) if a.get("status") == "omitted"}


def _stage_records(root, task_dir, m, records):
    """{stage: [what shows it ran]}; an empty list means no record."""
    shown = {s: [] for s in _ORDER}
    omitted = _omitted(m)
    mpath = _rel(root, manifest_path(task_dir))
    if m.get("assessment"):
        shown[STAGE_ASSESS].append(f"{mpath} (assessment)")
    approach = _doc(task_dir, "delivery-approach.md")
    if approach:
        shown[STAGE_ASSESS].append(_rel(root, approach))
    for stage, name in ((STAGE_DEFINE, "acceptance-criteria.md"),
                        (STAGE_REFINE, "requirements-review.md"),
                        (STAGE_PLAN, "technical-design.md"),
                        (STAGE_BREAKDOWN, "distribution-map.md")):
        path = _doc(task_dir, name)
        if path:
            shown[stage].append(_rel(root, path))
        elif name[:-3] in omitted:
            shown[stage].append(f"omitted: {omitted[name[:-3]]}")
    if _list(m.get("scenarios")):
        shown[STAGE_DEFINE].append(f"{mpath} (scenarios: {len(m['scenarios'])})")
    if _list(m.get("subtasks")):
        shown[STAGE_BREAKDOWN].append(f"{mpath} (subtasks: {len(m['subtasks'])})")
    shown[STAGE_IMPLEMENT] = [_rel(root, r[4]) for r in records]
    if any(g.get("status") == "pass" for g in _dicts(m.get("gates"))):
        shown[STAGE_VERIFY].append(f"{mpath} (gates)")
    review = os.path.join(task_dir, "evidence", "review.md")
    if os.path.isfile(review):
        shown[STAGE_VERIFY].append(_rel(root, review))
    landed_as = _landed_as(m)
    if landed_as or m.get("land_timestamp"):
        shown[STAGE_SHIP].append(f"{mpath} (landed {landed_as})" if landed_as else f"{mpath} (landed)")
    return shown


def _timeline(root, task_dir, m, records):
    mpath = _rel(root, manifest_path(task_dir))
    events = []
    for kind, scenario, when, _, path in records:
        if when:
            label = "acceptance declared" if kind == "acceptance" else kind
            events.append((when, f"{label} {scenario or '(unbound)'}", _rel(root, path)))
    for st in _dicts(m.get("subtasks")):
        if st.get("dispatched_at"):
            events.append((str(st["dispatched_at"]), f"{st.get('id')} dispatched", mpath))
        for rnd in _dicts(st.get("review_rounds")):
            if rnd.get("at"):
                events.append((str(rnd["at"]),
                               f"{st.get('id')} review round {rnd.get('round')}: {rnd.get('verdict')}",
                               mpath))
    for ra in _dicts(m.get("reassessments")):
        when = ra.get("at") or ra.get("date") or ra.get("timestamp")
        if when:
            src = ra.get("from_route") or ra.get("from") or "?"
            dst = ra.get("to_route") or ra.get("to") or "?"
            events.append((str(when), f"reassessed {src} -> {dst}", mpath))
    log = os.path.join(".compass", LOG_NAME)
    for when, kind in _interruptions(root, os.path.basename(os.path.normpath(task_dir))):
        what = "hook refused an edit" if kind == "hook_blocks" else "a check failed"
        events.append((when, what, log))
    landed_at = str(m.get("land_timestamp") or "")
    if landed_at:
        # Comparing text: both are ISO 8601 UTC, so a later time sorts later.
        events = [(w, f"{what} (after landing)" if w[:19] > landed_at[:19] else what, p)
                  for w, what, p in events]
        events.append((landed_at, f"landed {_landed_as(m)}".strip(), mpath))
    return sorted(events)


def _deviations(task_dir, m, stages, shown, records):
    out = []
    landed = str(m.get("status") or "") == "landed"
    spike = str(m.get("delivery_approach") or "") == APPROACH_SPIKE
    # An issue that has not landed has reached only as far as its last stage
    # with a record; a stage after that is not reached yet, not missing.
    # An omission recorded early says nothing about how far the work got.
    reached = max((i for i, s in enumerate(_ORDER)
                   if any(not r.startswith("omitted:") for r in shown[s])), default=-1)
    through = _landed_through(m)
    if through:
        out.append(f"landed through {through}: its records are in that issue, "
                   f"so this issue's own missing stages are not listed")
    for i, stage in enumerate(_ORDER if not through else ()):
        weight = stages.get(stage)
        if weight is None or str(weight) in _NOT_RUN or shown[stage]:
            continue
        if not landed and i >= reached:
            continue
        if stage == STAGE_BREAKDOWN:
            continue                    # a solo run writes no subtasks
        if stage == STAGE_IMPLEMENT and spike:
            continue                    # a spike records no red
        out.append(f"{stage} ran in the route ({weight}) but has no record")
    declared = any(r[0] == "acceptance" for r in records) or os.path.isfile(
        os.path.join(task_dir, "evidence", "acceptance-baseline.json"))
    reds = [r for r in records if r[0] == "red"]
    for kind, scenario, when, command, _ in records:
        if kind != "green":
            continue
        # Unbound records name no scenario, so they cannot be paired.
        own = [r for r in reds if scenario and r[1] == scenario]
        # Red-first is checked per issue, so a green whose scenario has no
        # red of its own is only a deviation when the issue has no red at all.
        if not own and not reds and not declared:
            out.append(f"scenario {scenario or '(unbound)'}: a green, and no red anywhere in the issue")
        for red in own:
            if red[2] and when and red[2] > when:
                source = ("the same command" if red[3] == command
                          else f"a different command ({red[3] or 'not recorded'})")
                out.append(f"scenario {scenario}: a red dated after its green, from {source}")
    for st in _dicts(m.get("subtasks")):
        for rnd in _dicts(st.get("review_rounds")):
            if str(rnd.get("verdict")).lower() == "fail":
                out.append(f"{st.get('id')} review round {rnd.get('round')} failed")
    if landed:
        for g in _dicts(m.get("gates")):
            if g.get("status") != "pass":
                out.append(f"gate {g.get('id')} is {g.get('status') or 'unset'}")
    return out


def cmd_issue_diagnose(args):
    task_dir = resolve_issue_dir(args.task)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))
    m = load_yaml(manifest_path(task_dir))
    if not isinstance(m, dict):
        m = {}
    stages = m.get("stages") if isinstance(m.get("stages"), dict) else {}
    records = _records(task_dir)
    shown = _stage_records(root, task_dir, m, records)

    lines = [f"compass issue diagnose: {m.get('issue') or os.path.basename(task_dir)}"
             f" ({m.get('delivery_approach') or 'no approach'}, {m.get('status') or 'no status'})",
             "", "Stages"]
    if not stages:
        lines.append("  the manifest records no stages")
    for stage in _ORDER if stages else ():
        weight = stages.get(stage)
        weight_text = str(weight) if weight not in (None, "") else "not set"
        if weight is None or str(weight) in _NOT_RUN:
            lines.append(f"  {stage:<10} {weight_text:<20} skipped by the route")
        else:
            lines.append(f"  {stage:<10} {weight_text:<20} "
                         + (", ".join(shown[stage]) if shown[stage] else "no record"))
    lines += ["", "Gates"]
    gates = _dicts(m.get("gates"))
    for g in gates:
        ev = ", ".join(str(e) for e in _list(g.get("evidence"))) or "no evidence"
        lines.append(f"  {str(g.get('id') or '(no id)'):<24} {str(g.get('status') or 'unset'):<8} {ev}")
    if not gates:
        lines.append("  none on record")
    costs = [(st.get("id"), st.get("cost")) for st in _dicts(m.get("subtasks"))
             if st.get("cost") is not None]
    if costs:
        lines += ["", "Recorded cost"]
        lines += [f"  {sid}: {cost} tokens" for sid, cost in costs]
    lines += ["", "Timeline"]
    events = _timeline(root, task_dir, m, records)
    lines += [f"  {when}  {what}  {path}" for when, what, path in events] or ["  no dated records"]
    lines += ["", "Deviations"]
    dev = _deviations(task_dir, m, stages, shown, records)
    lines += [f"  - {d}" for d in dev] or ["  None found in the records."]
    lines += ["", "The records cannot show"]
    lines += [f"  - {c}" for c in CANNOT_SHOW]
    print("\n".join(lines))
    return 0


def register(issue_subs, issue_arg):
    """Add `diagnose` to the `compass issue` group."""
    p = issue_subs.add_parser(
        "diagnose", help="explain one run from its issue's own records")
    issue_arg(p)
    p.set_defaults(func=cmd_issue_diagnose, output_kind="report")
