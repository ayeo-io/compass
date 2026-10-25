# compass_pkg.model_tiers - the model tier of each seat, and the model and effort it maps to
"""The model tier, and the effort, each seat of an issue runs on.

A seat is a stage, or the reviewer in the verify stage (`review`). The routing
policy's `model_rules` give each seat a default tier (`default_tiers`) and
raise it when the assessment warrants it (`floors`). A floor can also raise a
seat's effort. A floor only raises: the highest tier, and the highest effort,
among the matching rules wins, as the routing floors raise an approach and
never lower it. `evaluate` computes the result the evaluator folds into the
manifest's `models:` key.

The manifest records the tier and a floor's effort, never a model name. The
project's `models` setting maps each tier to a model and, optionally, an
effort, when `compass approach show --model <seat>` or `--effort <seat>` runs,
so a changed name applies to every open issue at once. `inherit` means the
model the session runs on.
"""
# DEPENDENCY: compass_pkg.core (errors, manifests, project root), compass_pkg.stable_ids
# (the tier, effort and stage ids); the setting is
# read through compass_pkg.project_settings, imported where it is used.
from __future__ import annotations

import os
import sys

from compass_pkg.core import CompassError
from compass_pkg.stable_ids import (EFFORT_LEVELS, EFFORT_HIGH, EFFORT_LOW, EFFORT_MEDIUM,
                                    MODEL_TIERS, STAGE_ASSESS, STAGE_BREAKDOWN, STAGE_DEFINE,
                                    STAGE_IMPLEMENT, STAGE_PLAN, STAGE_REFINE, STAGE_SHIP,
                                    STAGE_VERIFY, TIER_FAST, TIER_STANDARD, TIER_STRONG)

#: The tiers, weakest first. A floor raises a seat to a later tier.
TIERS = MODEL_TIERS
#: The effort levels, lowest first, as Claude Code names them.
EFFORTS = EFFORT_LEVELS
#: The seats, in stage order. `review` is the reviewer in the verify stage.
REVIEW = "review"
SEATS = (STAGE_ASSESS, STAGE_DEFINE, STAGE_REFINE, STAGE_PLAN, STAGE_BREAKDOWN,
         STAGE_IMPLEMENT, STAGE_VERIFY, REVIEW, STAGE_SHIP)
#: The stage a seat belongs to, where it is not the seat's own name.
SEAT_STAGE = {REVIEW: STAGE_VERIFY}
#: The value of a tier's model that means the model the session runs on.
INHERIT = "inherit"
#: The shipped mapping of tiers (the `models` setting): a model and an effort each.
DEFAULT_MODELS = {TIER_STRONG: {"model": INHERIT, "effort": EFFORT_HIGH},
                  TIER_STANDARD: {"model": "sonnet", "effort": EFFORT_MEDIUM},
                  TIER_FAST: {"model": "haiku", "effort": EFFORT_LOW}}
#: Stage modes in which a stage does not run, so its seats get no tier.
NOT_RUN = ("collapsed", "skipped")


def _tier(value, rule_id):
    if value not in TIERS:
        raise CompassError(
            f"model rule {rule_id} names the tier {value!r}; a tier is one of "
            f"{', '.join(TIERS)}")
    return value


def _effort(value, where):
    if value not in EFFORTS:
        raise CompassError(
            f"{where} names the effort {value!r}; an effort is one of {', '.join(EFFORTS)}")
    return value


def _seat(value, rule_id):
    if value not in SEATS:
        raise CompassError(
            f"model rule {rule_id} names the seat {value!r}; a seat is one of "
            f"{', '.join(SEATS)}")
    return value


def higher(order, a, b):
    """The later of `a` and `b` in `order`; None counts as below everything."""
    if a is None or b is None:
        return b if a is None else a
    return a if order.index(a) >= order.index(b) else b


#: Which list of the evaluator's `model_rules` block a rule set's `kind` fills.
RULE_KINDS = {"model-tiers": "default_tiers", "model-floors": "floors"}


def policy_block(rules):
    """`{"model_rules": {default_tiers, floors}}` from a configuration's rule sets,
    in the shape the evaluator and `governance/routing-policy.yml` hold, or `{}`
    when no rule set is a model-tier kind."""
    blocks, found = {block: [] for block in RULE_KINDS.values()}, False
    for rule_set in rules.values():
        block = RULE_KINDS.get((rule_set or {}).get("kind"))
        if not block:
            continue
        found = True
        ordered = sorted(((rule_set.get("rules") or {}).items()),
                         key=lambda item: item[1].get("order", 0))
        for rule_id, rule in ordered:
            entry = {"id": rule_id}
            if "when" in rule:
                entry["when"] = rule["when"]
            entry.update(rule.get("then") or {})
            if "rationale" in rule:
                entry["rationale"] = rule["rationale"]
            blocks[block].append(entry)
    return {"model_rules": blocks} if found else {}


def evaluate(model_rules, matches, stages):
    """`{seat: {tier, by[, effort, effort_by][, not_fired]}}` for the seats whose
    stage runs.

    `model_rules` is the policy's block (`default_tiers` and `floors`, each a
    list of rules with `id`, `seat`, an optional `when`, and a `tier`, an
    `effort` or both; a default rule needs a tier), `matches` answers whether a
    `when` holds for the assessment, and `stages` is the approach's stage
    modes. A policy with no block gives `{}`: the agents then run on their
    frontmatter model and effort."""
    if not isinstance(model_rules, dict):
        return {}
    seats, not_fired = {}, {}
    for block in ("default_tiers", "floors"):
        for rule in model_rules.get(block) or []:
            rid = rule.get("id", "?")
            seat = _seat(rule.get("seat"), rid)
            if block == "default_tiers" or "tier" in rule or "effort" not in rule:
                tier = _tier(rule.get("tier"), rid)
            else:
                tier = None
            effort = (_effort(rule["effort"], f"model rule {rid}")
                      if "effort" in rule else None)
            if not matches(rule.get("when")):
                if block == "floors":
                    not_fired.setdefault(seat, []).append(rid)
                continue
            held = seats.setdefault(seat, {})
            if tier is not None and higher(TIERS, held.get("tier"), tier) != held.get("tier"):
                held.update(tier=tier, by=rid)
            if effort is not None and \
                    higher(EFFORTS, held.get("effort"), effort) != held.get("effort"):
                held.update(effort=effort, effort_by=rid)
    out = {}
    for seat in SEATS:
        if not seats.get(seat, {}).get("tier"):
            continue
        mode = (stages or {}).get(SEAT_STAGE.get(seat, seat))
        if mode is None or mode in NOT_RUN:
            continue
        held = seats[seat]
        entry = {"tier": held["tier"], "by": held["by"]}
        if held.get("effort"):
            entry.update(effort=held["effort"], effort_by=held["effort_by"])
        if not_fired.get(seat):
            entry["not_fired"] = list(not_fired[seat])
        out[seat] = entry
    return out


def raised(tier):
    """The tier one step above `tier`; strong stays strong."""
    return TIERS[min(TIERS.index(tier) + 1, len(TIERS) - 1)]


def mapping(project_root):
    """The project's tiers as `{tier: {model, effort}}`: the shipped mapping
    with the `models` setting over it. A tier the setting gives as a bare
    string names a model and sets no effort. A setting that names another
    tier, or an effort outside the five levels, is refused."""
    from compass_pkg import project_settings
    given = project_settings.settings(project_root).get("models") or {}
    if not isinstance(given, dict):
        raise CompassError("the `models` setting must map a tier to a model name, "
                           f"for example `standard: sonnet`; the tiers are {', '.join(TIERS)}")
    unknown = sorted(str(k) for k in given if k not in TIERS)
    if unknown:
        raise CompassError(
            f"the `models` setting names {', '.join(unknown)}, which is not a tier; "
            f"the tiers are {', '.join(reversed(TIERS))}")
    out = {tier: dict(value) for tier, value in DEFAULT_MODELS.items()}
    for tier, value in given.items():
        if isinstance(value, str):
            value = {"model": value}
        if not isinstance(value, dict) or set(value) - {"model", "effort"} or \
                not isinstance(value.get("model"), str) or not value["model"].strip():
            raise CompassError(
                f"the `models` setting gives {tier} no model: write a model name, or "
                f"`{{model: <name>, effort: <level>}}`")
        effort = value.get("effort")
        if effort is not None:
            _effort(effort, f"the `models` setting for {tier}")
        out[tier] = {"model": value["model"].strip(), "effort": effort}
    return out


def resolve(tier, project_root):
    """The model name `tier` maps to in this project."""
    return mapping(project_root)[_tier(tier, "in the manifest")]["model"]


def resolve_effort(tier, floor_effort, project_root):
    """The effort a seat at `tier` runs at: the higher of its tier's effort
    and the effort a floor raised it to. None when neither sets one."""
    return higher(EFFORTS, mapping(project_root)[_tier(tier, "in the manifest")]["effort"],
                  floor_effort)


def project_root_of(task_dir):
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))


def seat_entry(task, seat):
    """The manifest's record for `seat` when it holds a known tier, or None. A
    recorded effort outside the five levels is refused, not ignored: ignoring
    it would leave the agent on its frontmatter with nothing said."""
    models = task.get("models") if isinstance(task, dict) else None
    entry = models.get(seat) if isinstance(models, dict) else None
    if not isinstance(entry, dict) or entry.get("tier") not in TIERS:
        return None
    if entry.get("effort") is not None:
        _effort(entry["effort"], f"the manifest's models.{seat}")
    return entry


def seat_tier(task, seat):
    """The tier the manifest records for `seat`, or None."""
    entry = seat_entry(task, seat)
    return entry["tier"] if entry else None


def cmd_approach_show(args):
    """`compass approach show`: the three-line decision view, or with `--model
    SEAT` or `--effort SEAT` only the model name or the effort of that seat."""
    if getattr(args, "model", None) and getattr(args, "effort", None):
        raise CompassError("compass approach show: give --model or --effort, not both; "
                           "each prints one value")
    if getattr(args, "model", None) or getattr(args, "effort", None):
        return cmd_approach_model(args)
    from compass_pkg.routing import cmd_approach_summary
    return cmd_approach_summary(args)


# --- command: approach show --model / --effort ----------------------------------------------

def cmd_approach_model(args):
    """`compass approach show --model <seat>` prints the model name a stage command
    passes when it invokes the seat's agent; `--effort <seat>` prints the effort.
    Exit 1 when the issue records no tier for the seat, or, for `--effort`, when
    neither the tier nor a floor sets one: the agent's frontmatter applies."""
    from compass_pkg.core import load_manifest, resolve_issue_dir
    from compass_pkg.terminal import mark_handled
    mark_handled()
    flag, seat = ("--model", args.model) if getattr(args, "model", None) \
        else ("--effort", args.effort)
    what = flag[2:]
    if seat not in SEATS:
        raise CompassError(f"compass approach show {flag}: {seat!r} is not a seat; "
                           f"the seats are {', '.join(SEATS)}")
    task_dir = resolve_issue_dir(args.task)
    task, _ = load_manifest(task_dir)
    entry, root = seat_entry(task, seat), project_root_of(task_dir)
    value = None
    if entry is not None:
        value = (resolve(entry["tier"], root) if what == "model"
                 else resolve_effort(entry["tier"], entry.get("effort"), root))
    if value is None:
        why = (f"records no tier for {seat}" if entry is None
               else f"sets no effort for {seat}: its tier names none and no floor raised it")
        sys.stderr.write(
            f"compass approach show {flag}: {os.path.basename(os.path.normpath(task_dir))} "
            f"{why}. Leave `{what}` out when you invoke the agent, so its "
            f"frontmatter {what} applies.\n")
        return 1
    print(value)
    return 0


# --- command: retro --models ----------------------------------------------------------------

def _rows(work):
    """`{(tier, risk): [review rounds, ...]}` and the count of subtasks raised on
    a later try, from every manifest under `work`."""
    from compass_pkg.core import load_yaml, manifest_path
    groups, raised_count = {}, 0
    if not os.path.isdir(work):
        return groups, raised_count
    for slug in sorted(os.listdir(work)):
        path = manifest_path(os.path.join(work, slug))
        if not os.path.isfile(path):
            continue
        try:
            data = load_yaml(path)
        except CompassError:
            continue
        if not isinstance(data, dict):
            continue
        risk = str((data.get("assessment") or {}).get("risk") or "unknown")
        for sub in data.get("subtasks") or []:
            tiers = sub.get("tiers") if isinstance(sub, dict) else None
            if not isinstance(tiers, list) or not tiers or tiers[0] not in TIERS:
                continue
            rounds = sub.get("review_rounds")
            groups.setdefault((tiers[0], risk), []).append(
                len(rounds) if isinstance(rounds, list) else 0)
            if any(t != tiers[0] for t in tiers[1:]):
                raised_count += 1
    return groups, raised_count


def report(work):
    """The lines `compass retro --models` prints."""
    groups, raised_count = _rows(work)
    if not groups:
        return ["compass retro --models: no subtask records a tier. A subtask "
                "records one when `compass issue subtask add` dispatches it on an "
                "issue whose manifest has a `models:` key."]
    total = sum(len(v) for v in groups.values())
    lines = [f"compass retro --models: {total} subtask(s) record a dispatch tier",
             "",
             f"  {'tier':<9} {'risk':<14} {'subtasks':>8}  mean review rounds"]
    order = {t: i for i, t in enumerate(reversed(TIERS))}
    for (tier, risk), rounds in sorted(groups.items(),
                                       key=lambda kv: (order[kv[0][0]], kv[0][1])):
        lines.append(f"  {tier:<9} {risk:<14} {len(rounds):>8}  "
                     f"{sum(rounds) / len(rounds):.1f}")
    lines += ["", f"  raised on a later try: {raised_count}",
              "  The tier is the one the first try was dispatched on. A tier "
              "whose subtasks need more review rounds is the evidence for moving "
              "a floor."]
    return lines


def cmd_retro_models(args):
    from compass_pkg.core import find_compass_dir
    for line in report(os.path.join(find_compass_dir(), "work")):
        print(line)
    return 0
