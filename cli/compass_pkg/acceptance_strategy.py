# compass_pkg.acceptance_strategy - whether the four-layer acceptance strategy applies
"""The one place that decides whether strategy `S17`, the four-layer acceptance
strategy, applies to an issue. The rule is the stored-applicability decision of
the issue `atdd-strategy`, made at its plan stage.

Assess stores what it expects in the manifest's `acceptance_strategy` block:
the project setting, the routing of the issue's approach and the acceptance
kind it expects. `compass check` then decides from the records: an issue is in
scope unless it holds an acceptance of kind `validation` or `refactor` and no
red record. An issue with no block was assessed before the strategy shipped,
so the strategy never applies to it (ADR-006).

Every check of the strategy calls `in_scope`, so two checks cannot disagree
about scope. The module also holds the setting reader, the line the
delivery-approach record shows, the advisory check
`acceptance-applicability-agrees` and `compass retro --acceptance`.

Compass reads records here, never project code.
"""
# DEPENDENCY: standard library (json, os); compass_pkg.check_results, core,
# project_settings and red_first, and inside functions compass_pkg.layers,
# effective and status_words. It imports no command
# module and no check module at load time, so a check module can import it.
from __future__ import annotations

import json
import os

from compass_pkg import project_settings
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError, load_yaml, manifest_path
from compass_pkg.red_first import ACCEPTANCE_KINDS, load_record

#: The settings key and the manifest key.
KEY = "acceptance_strategy"
STATES = ("on", "off")

#: The advisory check this module implements, and every check of the strategy.
#: The other four are added by later items; a configuration that does not
#: declare one does not run it.
CHECK = "acceptance-applicability-agrees"
CHECKS = (CHECK, "outer-loop-recorded", "outer-loop-attempts-recorded",
          "isolation-proven", "layering-test-passed")

#: The routing of each approach, as the preset's `approaches.<id>.acceptance_strategy`
#: names it, and the words the delivery-approach record shows for it.
ROUTINGS = {
    "on": "on",
    "existing-dsl": "existing DSL only",
    "existing-dsl-isolation": "existing DSL only, isolation proof required",
    "suspended": "suspended, as strategy `S2`",
}

#: What `compass approach evaluate --expected-acceptance` takes: `none` for a
#: change with client-observable behavior.
EXPECTED = ("none",) + ACCEPTANCE_KINDS

NAME = "four-layer acceptance strategy (`S17`)"
BEHAVIOR = "client-observable behavior"
SPIKE_WHY = "a spike ships nothing"
OLDER = "this issue was assessed before the strategy shipped"
NOTICE = f"{NAME}: does not apply - {OLDER}"
REASSESS = "compass approach evaluate --write --reason \"...\""


# --- the project setting -------------------------------------------------------------------

def setting(project_root):
    """`(state, reason)` of the project's `acceptance_strategy` setting, read from
    `compass.yml`, or `.compass/config.yml` in a project without one. Missing
    means on. `off` needs a reason that is not blank. Any other value raises
    `CompassError`, which the CLI reports with exit 2, as `core.load_autonomy`
    refuses an unknown `autonomy:`: a typo must not turn the strategy off, or
    on, without a word."""
    held = project_settings.lenient(project_root)
    # Only a missing key means on: a key with no value is refused, as the lint
    # refuses it. A project pinned before the strategy never reads the setting.
    if KEY not in held or pinned_below(project_root):
        return "on", None
    value = held[KEY]
    state = _state(value.get("state")) if isinstance(value, dict) else None
    reason = value.get("reason") if isinstance(value, dict) else None
    reason = reason.strip() if isinstance(reason, str) else None
    extra = sorted(set(value) - {"state", "reason"}) if isinstance(value, dict) else []
    if state in STATES and not extra and (state == "on" or reason):
        return state, reason or None
    where = project_settings.settings_file(project_root)
    raise CompassError(
        f"`{KEY}: {json.dumps(value, default=str)}` in {where} is not a setting; use "
        f"`{KEY}: {{state: on}}` or `{KEY}: {{state: off, reason: <why>}}`. The "
        f"state is on or off, and off needs a reason that is not blank (on if the "
        f"key is left out).")


def _state(value):
    """`on` or `off` from a written state. YAML 1.1, which the loader follows, reads
    an unquoted `on` and `off` as true and false, so those read as the words."""
    if value is True:
        return "on"
    if value is False:
        return "off"
    return value


def problem(value):
    """The fault in a settings value as text, or None. `compass policy lint`
    reports it for `compass.yml`."""
    if not isinstance(value, dict):
        return "expected a mapping with `state` (on or off) and, for off, a `reason`"
    extra = sorted(set(value) - {"state", "reason"})
    if extra:
        return f"{', '.join(extra)}: not a key; it holds state and reason"
    state = _state(value.get("state"))
    if state not in STATES:
        return f"state: {value.get('state')!r} is not on or off"
    reason = value.get("reason")
    if state == "off" and not (isinstance(reason, str) and reason.strip()):
        return "state off needs a reason that is not blank"
    return None


# --- routing and the stored block -----------------------------------------------------------

def approach_routing(resolved, approach):
    """The routing of `approach` in a resolved configuration. An approach that
    names none reads `on` when it ships and `suspended` when it does not."""
    body = ((resolved or {}).get("approaches") or {}).get(approach) or {}
    named = body.get(KEY)
    if named in ROUTINGS:
        return named
    return "on" if body.get("ships", True) is not False else "suspended"


#: The first major of the shipped default that carries the strategy.
FIRST_MAJOR = 8


def pinned_below(project_root):
    """The `extends:` value when the project's `compass.yml` pins the shipped
    default at a major before `FIRST_MAJOR`, else None. Resolution always reads
    the live preset, whatever major `extends:` names, so the pin is what keeps
    a project on @6 or @7 out of the strategy (decided by jed72, 2026-10-30). A
    project with no `compass.yml`, no `extends:` or a git parent names no
    shipped major and runs on the live default, so it is not pinned below."""
    from compass_pkg import layers, parents
    if not project_settings.compass_yml_counts(project_root):
        return None
    try:
        doc = load_yaml(os.path.join(project_root, layers.PROJECT_FILE))
        value = parents.extends_value((doc or {}).get("extends"))
        name, major = layers.parse_extends(value)
    except (CompassError, AttributeError, TypeError, ValueError):
        return None
    return value if name == "default" and major < FIRST_MAJOR else None


def suspended_findings(resolved):
    """`[(path, message)]` for each approach that ships and sets the routing
    `suspended`. `compass policy lint` refuses them: that would turn the strategy
    off with no recorded reason, and the settings key is the one way to turn it
    off (decided by jed72, 2026-10-30). The spike, which ships nothing, keeps
    `suspended`."""
    out = []
    for approach, body in sorted(((resolved or {}).get("approaches") or {}).items()):
        if (isinstance(body, dict) and body.get(KEY) == "suspended"
                and body.get("ships", True) is not False):
            out.append((f"approaches.{approach}.{KEY}",
                        f"the {approach} approach ships, so it cannot suspend the "
                        f"four-layer acceptance strategy; turn the strategy off for the "
                        f"project with the settings key `{KEY}: {{state: off, reason: <why>}}`"))
    return out


def notice(task_dir):
    """The notice `compass check` gives an issue with no stored block."""
    pinned = pinned_below(_project_root(task_dir))
    if pinned:
        return f"{NAME}: does not apply - the project extends {pinned}, before the strategy"
    return NOTICE


def declared(resolved):
    """True when a resolved configuration declares the strategy's check, which
    is how an issue's stored generation says the strategy shipped for it."""
    return CHECK in ((resolved or {}).get("checks") or {})


def block(project_root, resolved, approach, expected):
    """The block `compass approach evaluate --write` stores for an issue."""
    state, reason = setting(project_root)
    routing = approach_routing(resolved, approach)
    expected = expected or "none"
    if state == "off":
        applies, why = False, reason
    elif routing == "suspended":
        # A project can route an approach that ships `suspended` too; only the
        # spike's reason is that it ships nothing.
        ships = (((resolved or {}).get("approaches") or {}).get(approach) or {}).get(
            "ships", True) is not False
        applies, why = False, (f"suspended on the {approach} approach by the project" if ships
                               else SPIKE_WHY)
    elif expected in ACCEPTANCE_KINDS:
        applies, why = False, f"acceptance of kind {expected}"
    else:
        applies, why = True, BEHAVIOR
    out = {"state": state}
    if reason:
        out["reason"] = reason
    out.update({"routing": routing, "expected_acceptance": expected,
                "applies": applies, "why": why})
    return out


def stored(task):
    """The issue's stored block, or None for an issue assessed before the strategy."""
    value = (task or {}).get(KEY)
    return value if isinstance(value, dict) else None


def line(task):
    """The applicability line of the delivery-approach record."""
    held = stored(task)
    if held is None:
        return f"The {NAME} does not apply: {OLDER}."
    if held.get("state") == "off":
        status = "off for this project"
    else:
        status = "applies" if held.get("applies") else "does not apply"
    approach = task.get("delivery_approach") or "?"
    routing = ROUTINGS.get(held.get("routing"), held.get("routing"))
    return (f"Four-layer acceptance strategy (`S17`): {status} - {held.get('why')}. "
            f"Routing on the {approach} approach: {routing}.")


# --- scope from the records -----------------------------------------------------------------

def _evidence_names(task_dir):
    folder = os.path.join(task_dir, "evidence")
    if os.path.islink(folder):
        return []
    try:
        return sorted(os.listdir(folder))
    except OSError:
        return []


def has_red(task_dir):
    """True when a red record holding a failed run is on record, signed or not."""
    for name in _evidence_names(task_dir):
        if name == "red.json" or (name.startswith("red-") and name.endswith(".json")):
            record = load_record(os.path.join(task_dir, "evidence", name))
            code = record.get("exit_code")
            if record.get("passed") is False and isinstance(code, int) \
                    and not isinstance(code, bool) and code != 0:
                return True
    return False


def acceptance_kind(task, task_dir):
    """The kind of the issue's acceptance, from a registered record or the
    declared baseline, or None."""
    root = os.path.realpath(task_dir)
    for entry in (task or {}).get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        full = os.path.realpath(os.path.join(task_dir, entry.get("path") or ""))
        if os.path.commonpath([root, full]) != root:
            continue
        kind = load_record(full).get("kind")
        if kind in ACCEPTANCE_KINDS:
            return kind
    kind = load_record(os.path.join(task_dir, "evidence", "acceptance-baseline.json")).get("kind")
    return kind if kind in ACCEPTANCE_KINDS else None


def records_say(task, task_dir):
    """`(applies, why)` as the records decide it, apart from the setting: a red
    record puts the issue in scope; an acceptance of kind validation or
    refactor with no red takes it out (parent decision Q1)."""
    if has_red(task_dir):
        return True, "a red record is on record"
    kind = acceptance_kind(task, task_dir)
    if kind:
        return False, f"acceptance of kind {kind}, and no red record"
    return True, BEHAVIOR


def in_scope(task, task_dir):
    """`(applies, why)`: does the strategy apply to the issue now? Every check
    of the strategy asks this, and declines with `why` when it does not."""
    held = stored(task)
    if held is None:
        return False, OLDER
    if held.get("state") == "off":
        return False, f"the project turned the strategy off - {held.get('reason')}"
    if held.get("routing") == "suspended":
        return False, f"suspended on this approach - {held.get('why')}"
    return records_say(task, task_dir)


def _project_root(task_dir):
    from compass_pkg.layers import find_project_root
    return find_project_root(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))


def _check_applicability_agrees(task, task_dir):
    """The advisory check: the stored applicability agrees with the project
    setting and with what the records decide."""
    held = stored(task)
    if held is None:
        return NOTHING_TO_CHECK, f"not required: the strategy does not apply - {OLDER}"
    root = _project_root(task_dir)
    state, reason = setting(root)
    if state != held.get("state"):
        now = "still applies to this issue as assessed" if held.get("state") == "on" \
            else "still does not apply to this issue as assessed"
        where = project_settings.settings_file(root)
        return False, (f"the project setting changed since assess: {where} now turns "
                       f"the strategy {state}, and this issue was assessed with it "
                       f"{held.get('state')}. The strategy {now} until the issue is "
                       f"re-assessed; run `{REASSESS}`.")
    if state == "off":
        return NOTHING_TO_CHECK, (f"not required: the project turned the strategy off - "
                                  f"{held.get('reason')}")
    # A suspended routing takes the issue out of scope whatever the records hold,
    # as `in_scope` reads it, so there is no line to compare with them.
    if held.get("routing") == "suspended":
        return NOTHING_TO_CHECK, f"not required: the strategy is suspended - {held.get('why')}"
    applies, why = records_say(task, task_dir)
    if bool(held.get("applies")) != applies:
        said = "applies" if held.get("applies") else "does not apply"
        now = "applies" if applies else "does not apply"
        kind = "none" if applies else (acceptance_kind(task, task_dir) or "none")
        return False, (f"the delivery-approach record says the strategy {said} "
                       f"({held.get('why')}), but the records say it {now} ({why}). "
                       f"Re-assess with `compass approach evaluate --write "
                       f"--expected-acceptance {kind} --reason \"...\"`.")
    return True, (f"the applicability line agrees with the records: the strategy "
                  f"{'applies' if applies else 'does not apply'} ({why})")


# --- the retrospective -----------------------------------------------------------------------

def _closed(task):
    """Landed, or closed as completed. An issue closed as not planned or as a
    duplicate delivered nothing, so the measures leave it out."""
    from compass_pkg import status_words
    return bool(task.get("land_timestamp")) or status_words.is_completed(task)


def step_off(task, task_dir):
    """The reason of an approved issue waiver of one of the strategy's checks in
    the issue's stored generation, or None. A waiver the generation holds passed
    the lint that commits it, so its approval was checked then (ADR-039)."""
    from compass_pkg import effective
    try:
        view = effective.effective_for(task_dir, task)
    except CompassError:
        return None
    records = ((view.provenance or {}).get("waivers") or {}) if view is not None else {}
    for record in records.values():
        if not isinstance(record, dict) or record.get("scope") != "issue":
            continue
        entry = str(record.get("entry") or "")
        if entry.startswith("checks.") and entry[len("checks."):] in CHECKS:
            body = (((task.get("config") or {}).get("checks") or {})
                    .get(entry[len("checks."):]) or {}).get("waiver") or {}
            return record.get("reason") or body.get("reason") or "no reason recorded"
    return None


def report(work):
    """The retrospective over every closed issue under `work` that was assessed
    with the strategy."""
    out = {"measured": [], "out_of_scope": [], "off": [], "stepped_off": []}
    names = sorted(os.listdir(work)) if os.path.isdir(work) else []
    for slug in names:
        task_dir = os.path.join(work, slug)
        path = manifest_path(task_dir)
        if not os.path.isfile(path):
            continue
        try:
            task = load_yaml(path)
        except CompassError:
            continue
        if not isinstance(task, dict) or stored(task) is None or not _closed(task):
            continue
        if stored(task).get("state") == "off":
            out["off"].append(slug)
            continue
        applies, _ = in_scope(task, task_dir)
        if not applies:
            out["out_of_scope"].append(slug)
            continue
        reason = step_off(task, task_dir)
        if reason:
            out["stepped_off"].append({"issue": slug, "reason": reason})
            continue
        out["measured"].append(slug)
    return out


def cmd_retro_acceptance(args):
    """`compass retro --acceptance`: the strategy's measures, with an opted-out
    project and each issue that stepped off reported apart. Exit 0."""
    from compass_pkg.core import find_compass_dir
    compass_dir = find_compass_dir()
    root = os.path.dirname(compass_dir)
    state, reason = setting(root)
    out = report(os.path.join(compass_dir, "work"))
    out = {"opted_out": {"reason": reason} if state == "off" else None, **out}
    if getattr(args, "format", "markdown") == "json":
        print(json.dumps(out, indent=2))
        return 0
    lines = [f"compass retro --acceptance: the {NAME}"]
    if state == "off":
        lines.append(f"  This project has opted out of the four-layer acceptance strategy: "
                     f"{reason}")
    lines.append(f"  closed in-scope issues counted in the measures: {len(out['measured'])}"
                 + (f" ({', '.join(out['measured'])})" if out["measured"] else ""))
    if out["off"]:
        lines.append(f"  not counted, assessed while the strategy was off: "
                     f"{', '.join(out['off'])}")
    if out["out_of_scope"]:
        lines.append(f"  not counted, out of scope: {', '.join(out['out_of_scope'])}")
    for item in out["stepped_off"]:
        lines.append(f"  not counted, stepped off through an approved waiver: "
                     f"{item['issue']} - {item['reason']}")
    print("\n".join(lines))
    return 0
