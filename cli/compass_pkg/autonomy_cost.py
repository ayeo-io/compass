# compass_pkg.autonomy_cost - the autonomy ratio, the bands and the cost per change
"""Figures derived from what `checkpoint_outcomes` and `usage` record.

Nothing here is stored. The retro (`compass retro --impact`) and
`compass issue diagnose` call these functions on every read, so both give the
same number for the same issue. The definitions are in `docs/autonomy-and-cost.md`.

- A shipped issue is *measurable* when it is judged (it holds the
  `checkpoint_outcomes` key), lists checkpoints as a list and holds an outcome
  for each one listed. It is *autonomous* when it is measurable and
  no outcome is `waited`.
- The three *bands* count unlike things, so each carries its unit: human
  judgement counts checkpoints a person answered and human checks they
  approved; guardrailed counts gates that passed with a typed evidence record;
  autonomous counts stages the route ran that no person answered and no passed
  gate belongs to.
- An issue has *complete usage* when its cost is a number that no other issue
  shares. The cost per change is the median of those, so an issue whose cost is
  unknown is counted as unmeasured and never as zero.

A figure below its floor is withheld: its value is `None` and it carries a
reason, never a zero.
"""
# DEPENDENCY: standard library (math); compass_pkg.status_words,
# checkpoint_outcomes, approval_records, effective, decisions_taken. The
# floors are read from compass_pkg.calibration when a row is built, because
# that module imports this one.
from __future__ import annotations

import math

from compass_pkg import approval_records, checkpoint_outcomes, status_words
from compass_pkg.stable_ids import STAGE_IDS

#: What each band counts, shown beside its number so no reader adds unlike things.
UNITS = {"human_judgement": "checkpoints and human checks",
         "guardrailed": "gates", "autonomous": "stages"}


def _median(values):
    values = sorted(values)
    if not values:
        return None
    mid = len(values) // 2
    return float(values[mid]) if len(values) % 2 else (values[mid - 1] + values[mid]) / 2.0


def _number(value):
    """True for a finite number that is not a boolean."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _dicts(value):
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def shipped(task) -> bool:
    return status_words.is_completed(task)


def measurable(task) -> bool:
    """A shipped judged issue that lists `checkpoints:` as a list and holds an
    outcome for every checkpoint it lists. An issue that is not judged holds no
    record of its hand-offs, so an empty `checkpoints:` list there says no
    hand-off was listed, not that no person answered one."""
    if not shipped(task) or not checkpoint_outcomes.judged(task):
        return False
    if not isinstance(task.get(checkpoint_outcomes.KEY), list):
        return False
    if not isinstance(task.get("checkpoints"), list):
        return False
    have = checkpoint_outcomes.outcomes(task)
    return all(stage in have for stage in checkpoint_outcomes.listed(task))


def autonomous(task) -> bool:
    """A measurable issue with no `waited` outcome."""
    return measurable(task) and not any(
        entry.get("outcome") == checkpoint_outcomes.WAITED
        for entry in checkpoint_outcomes.outcomes(task).values())


def _human_checks(view):
    """The human checks that name approvers, in stage lists and on documents."""
    config = view.config
    checks = config.get("checks") or {}
    ids = set()
    for body in (config.get("stages") or {}).values():
        for side in ("entry", "exit"):
            ids.update(str(one) for one in (body or {}).get(side) or [])
    for body in (config.get("artifacts") or {}).values():
        ids.update(str(one) for one in (body or {}).get("checks") or [])
    return {one: checks[one] for one in sorted(ids)
            if isinstance(checks.get(one), dict) and checks[one].get("kind") == "human"
            and checks[one].get("approvers")}


def human_checks_passed(view, task, task_dir) -> int:
    """How many human checks have a current approval that `approval_records.judge`
    passes. An issue read without a configuration has no human checks."""
    if view is None:
        return 0
    return sum(1 for one, check in _human_checks(view).items()
               if approval_records.judge(one, check, task, task_dir)[0] == "pass")


def _holds_approval(task) -> bool:
    """True when the manifest holds an approved record a human check could read."""
    return any(e.get("type") in ("human-approval", approval_records.ARTIFACT_APPROVAL)
               and e.get("check") and e.get("decision") == approval_records.APPROVED
               for e in _dicts(task.get("evidence")))


def _guardrailed(task) -> int:
    typed = {e.get("id") for e in _dicts(task.get("evidence")) if e.get("id") and e.get("type")}
    return sum(1 for gate in _dicts(task.get("gates"))
               if gate.get("status") == "pass"
               and any(one in typed for one in gate.get("evidence") or []
                       if isinstance(one, str)))


def _autonomous_stages(task) -> int:
    waited = {stage for stage, entry in checkpoint_outcomes.outcomes(task).items()
              if entry.get("outcome") == checkpoint_outcomes.WAITED}
    gated = {str(gate.get("id")).split(".")[0] for gate in _dicts(task.get("gates"))
             if gate.get("status") == "pass"}
    return sum(1 for stage in STAGE_IDS
               if checkpoint_outcomes.stage_runs(task, stage)
               and stage not in waited and stage not in gated)


def bands(task, task_dir) -> dict | None:
    """The issue's `{human_judgement, guardrailed, autonomous}` counts, or None
    when its configuration cannot be read. Each count has its unit in `UNITS`."""
    from compass_pkg import effective
    human = 0
    # A human check passes only with an approved record that names it, so an
    # issue that holds none has nothing to count and its configuration is not
    # read. Reading it for every issue made the retro several times slower.
    if _holds_approval(task):
        try:
            view = effective.view_or_legacy(task_dir, manifest=task)
            human = human_checks_passed(view, task, task_dir)
        except Exception:                              # noqa: BLE001 - an unreadable configuration
            return None
    waited = sum(1 for entry in checkpoint_outcomes.outcomes(task).values()
                 if entry.get("outcome") == checkpoint_outcomes.WAITED)
    return {"human_judgement": waited + human, "guardrailed": _guardrailed(task),
            "autonomous": _autonomous_stages(task)}


def complete_cost(task) -> float | None:
    """The issue's cost in dollars, or None when its usage is not complete.

    Complete usage has `recorded` not false, a numeric `total.cost_usd` and no
    stage marked shared. A quick fix's block has no total: every measured stage
    needs a numeric `cost_usd`, none may be shared, and the cost is their sum."""
    usage = task.get("usage")
    if not isinstance(usage, dict) or usage.get("recorded") is False:
        return None
    stages = [s for s in (usage.get("stages") or {}).values() if isinstance(s, dict)]
    shared = [usage.get("total"), usage.get("unattributed")] + stages
    if any(isinstance(b, dict) and b.get("shared") for b in shared):
        return None
    total = usage.get("total")
    if isinstance(total, dict):
        return round(float(total["cost_usd"]), 6) if _number(total.get("cost_usd")) else None
    measured = [s for s in stages if s.get("measured") is not False]
    if not measured or not all(_number(s.get("cost_usd")) for s in measured):
        return None
    return round(sum(float(s["cost_usd"]) for s in measured), 6)


def _withheld(count, floor, what):
    return None if count >= floor else "%d %s; %d required" % (count, what, floor)


def _row(value, issues, not_measurable, withheld, **more):
    return {"value": None if withheld else value, "issues": issues,
            "not_measurable": not_measurable, "withheld": withheld, **more}


def ratio_row(tasks, floor) -> dict:
    ships = [d for _, d in tasks if shipped(d)]
    found = [d for d in ships if measurable(d)]
    withheld = _withheld(len(found), floor, "measurable shipped issue(s)")
    value = round(100.0 * sum(1 for d in found if autonomous(d)) / len(found), 1) if found else None
    return _row(value, len(found), len(ships) - len(found), withheld)


def band_row(tasks, work_root, floor) -> dict:
    import os
    ships = [(s, d) for s, d in tasks if shipped(d)]
    sums, counted = dict.fromkeys(UNITS, 0), 0
    for slug, d in ships:
        if not measurable(d):
            continue
        one = bands(d, os.path.join(work_root, slug))
        if one is None:
            continue
        counted += 1
        for key in sums:
            sums[key] += one[key]
    withheld = _withheld(counted, floor, "measurable shipped issue(s) with bands")
    return _row(dict(sums, units=dict(UNITS)), counted, len(ships) - counted, withheld)


def cost_row(tasks, floor, group_floor) -> dict:
    ships = [d for _, d in tasks if shipped(d)]
    by_approach, measured = {}, 0
    for d in ships:
        cost = complete_cost(d)
        if cost is None:
            continue
        measured += 1
        by_approach.setdefault(d.get("delivery_approach") or "?", []).append((cost, d))
    withheld = _withheld(measured, floor, "shipped issue(s) with complete usage")
    value = {}
    for approach, group in sorted(by_approach.items()):
        per = [cost / len(d["scenarios"]) for cost, d in group
               if isinstance(d.get("scenarios"), list) and d["scenarios"]]
        small = len(group) < group_floor
        # The per-scenario figure has its own floor: it rests on the issues with scenarios.
        thin = len(per) < group_floor
        value[approach] = {
            "issues": len(group),
            "median_usd": None if small else round(_median([c for c, _ in group]), 6),
            "median_per_scenario_usd": (None if small or thin
                                        else round(_median(per), 6)),
            "per_scenario_issues": len(per), "without_scenarios": len(group) - len(per),
            "withheld": ("%d issue(s); %d required" % (len(group), group_floor)) if small else None,
            "per_scenario_withheld": (
                "%d issue(s) with scenarios; %d required" % (len(per), group_floor)
                if thin and not small else None)}
    return _row(value, measured, len(ships) - measured, withheld)


def decisions_row(work_root, floor, issues=None) -> dict:
    """`issues` is `[(slug, manifest)]` already read; without it the report
    reads `work_root` itself."""
    from compass_pkg import decisions_taken
    found = decisions_taken.report(work_root, issues)
    withheld = _withheld(found["issues"], floor, "issue(s) hold decisions")
    value = {key: found[key] for key in ("confirmed", "changed", "never_confirmed", "total",
                                         "open_in_flight")}
    value["share"] = dict(found["share"])
    return _row(value, found["issues"], 0, withheld)


def impact_rows(issues, work_root) -> dict:
    """The four row objects of `compass retro --impact`. `issues` is
    `[(slug, manifest)]`; `work_root` holds each issue's folder."""
    from compass_pkg import calibration
    floor, group = calibration.IMPACT_SAMPLE_FLOOR, calibration.IMPACT_GROUP_FLOOR
    issues = [(slug, d) for slug, d in issues if isinstance(d, dict)]
    return {"autonomy_ratio": ratio_row(issues, floor),
            "band_split": band_row(issues, work_root, floor),
            "cost_per_change": cost_row(issues, floor, group),
            "decisions_confirmed": decisions_row(work_root, floor, issues)}


# --- the text rows -------------------------------------------------------------------

def _unmeasurable(row, tail=""):
    return "unmeasurable - %s%s" % (row["withheld"], tail)


def _dollars(value):
    return "unmeasurable" if value is None else "$%.4f" % value


def render_rows(rows) -> list:
    """The lines the retro prints after its by-approach block."""
    out = []
    ratio = rows["autonomy_ratio"]
    left = " (%d shipped issue(s) not measurable)" % ratio["not_measurable"]
    if ratio["withheld"]:
        out.append("  autonomy      " + _unmeasurable(ratio, left))
    else:
        out.append("  autonomy      %.1f%% of %d measurable shipped issue(s) ran with no waited "
                   "checkpoint; %d shipped issue(s) not measurable"
                   % (ratio["value"], ratio["issues"], ratio["not_measurable"]))
    band = rows["band_split"]
    if band["withheld"]:
        out.append("  bands         " + _unmeasurable(
            band, " (%d shipped issue(s) not counted)" % band["not_measurable"]))
    else:
        v = band["value"]
        out.append("  bands         human judgement %d (%s), guardrailed %d (%s), autonomous %d "
                   "(%s); over %d issue(s)"
                   % (v["human_judgement"], UNITS["human_judgement"], v["guardrailed"],
                      UNITS["guardrailed"], v["autonomous"], UNITS["autonomous"],
                      band["issues"]))
    cost = rows["cost_per_change"]
    if cost["withheld"]:
        out.append("  cost          " + _unmeasurable(
            cost, " (%d shipped issue(s) unmeasured)" % cost["not_measurable"]))
    else:
        out.append("  cost          per delivery approach, over %d shipped issue(s) with "
                   "complete usage; %d shipped issue(s) unmeasured:"
                   % (cost["issues"], cost["not_measurable"]))
        for approach, g in cost["value"].items():
            if g["withheld"]:
                out.append("                %-10s n=%d  (under %d - not summarised)"
                           % (approach, g["issues"], _group_floor()))
                continue
            per_scenario = ("unmeasurable - %s" % g["per_scenario_withheld"]
                            if g.get("per_scenario_withheld")
                            else _dollars(g["median_per_scenario_usd"]))
            line = ("                %-10s n=%d  median %s  per scenario %s"
                    % (approach, g["issues"], _dollars(g["median_usd"]), per_scenario))
            if g["without_scenarios"]:
                line += "  (%d without scenarios left out)" % g["without_scenarios"]
            out.append(line)
    dec = rows["decisions_confirmed"]
    if dec["withheld"]:
        out.append("  decisions     " + _unmeasurable(dec))
    else:
        v = dec["value"]
        line = ("  decisions     %d%% confirmed (%d), %d%% changed (%d), %d%% never confirmed "
                "(%d), of %d decision(s) over %d issue(s)"
                % (v["share"]["confirmed"], v["confirmed"], v["share"]["changed"],
                   v["changed"], v["share"]["never_confirmed"], v["never_confirmed"],
                   v["total"], dec["issues"]))
        if v["open_in_flight"]:
            line += "; %d open on an issue in flight" % v["open_in_flight"]
        out.append(line)
    return out


def _group_floor():
    from compass_pkg import calibration
    return calibration.IMPACT_GROUP_FLOOR
