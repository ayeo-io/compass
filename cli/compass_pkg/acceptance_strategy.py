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
about scope. The one exception is the advisory check
`acceptance-applicability-agrees`: it compares the stored line with what the
records say, so it calls `records_say` and repeats the off and suspended
branches itself. It must tell a changed project setting, an off or suspended
issue and a line that disagrees with the records apart, each with its own
message, and `in_scope` gives only one answer for all of them. The module also holds the setting reader, the line the
delivery-approach record shows, the advisory check
`acceptance-applicability-agrees` and the waiver notices `compass check` prints.

Compass reads records here, never project code.
"""
# DEPENDENCY: standard library (json, os); compass_pkg.check_results,
# core, project_settings and red_first, and inside functions compass_pkg.layers, parents,
# next_cmd and next_step. It imports no command
# module and no check module at load time, so a check module can import it.
from __future__ import annotations

import json
import os

from compass_pkg import project_settings
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError, load_yaml
from compass_pkg.red_first import ACCEPTANCE_KINDS, is_record_name, load_record

#: The settings key and the manifest key.
KEY = "acceptance_strategy"
STATES = ("on", "off")

#: The advisory check this module implements, and every check of the strategy.
#: Later items add the checks this CLI does not ship yet; a configuration that does not
#: declare one does not run it.
CHECK = "acceptance-applicability-agrees"
CHECKS = (CHECK, "outer-loop-recorded", "outer-loop-attempts-recorded",
          "isolation-proven", "layering-test-passed", "acceptance-support-present")

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

#: The loops a red or green record can belong to: the outer acceptance loop, driven
#: through a client interface, and the inner unit loop. `compass tdd-red` and
#: `compass tdd-green` take one with `--loop`, default inner (ADR-080).
LOOPS = ("outer", "inner")

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


def line(task, task_dir=None):
    """The applicability line of the delivery-approach record. With the issue
    folder it gives the pin reason for a pinned project, as `notice` does."""
    held = stored(task)
    if held is None:
        pinned = pinned_below(_project_root(task_dir)) if task_dir else None
        if pinned:
            return f"The {NAME} does not apply: the project extends {pinned}, before the strategy."
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


def loop_of(record):
    """`outer` or `inner`: the loop a red or green record belongs to. Only a record
    that says `outer` is outer. A record with no `loop` field was written before the
    field existed, and reads as inner, so it stays valid (ADR-006, ADR-080)."""
    return "outer" if (record or {}).get("loop") == "outer" else "inner"


def stage_one(task, loop):
    """True when a red ends stage 1 and is written before implement (ADR-081): the
    outer loop, on an approach whose `stages` run refine, before plan is handed off
    and with no technical design, distribution map or subtask registered. 9.0.0
    registers no document (ADR-091), so plan's hand-off is what ends stage 1; an
    issue made before then keeps the registered documents. Quick fix and hotfix
    collapse refine, so their outer-loop red is the first record of implement.

    On a path issue (ADR-092) stage 1 ends at specify: an outer-loop red is stage
    1's while specify is not done (`next_step.specify_done`), and build's after."""
    from compass_pkg import next_cmd, next_step
    from compass_pkg.path_stages import is_path_issue
    from compass_pkg.stable_ids import STAGE_PLAN, STAGE_REFINE
    if is_path_issue(task):
        return loop == "outer" and not next_step.specify_done(task)
    stages = (task or {}).get("stages")
    weight = stages.get(STAGE_REFINE) if isinstance(stages, dict) else None
    if loop != "outer" or not isinstance(weight, str) \
            or weight.strip().lower() in next_cmd._SKIPPED_WEIGHTS:
        return False
    return not (next_cmd._handed_off(task, STAGE_PLAN)
                or next_cmd._registered(task, "technical-design")
                or next_cmd._registered(task, "distribution-map")
                or next_cmd._entries(task, "subtasks"))


def red_records(task_dir):
    """`[(name, record)]` of each red record holding a failed run, signed or not,
    bound or unbound, in name order."""
    out = []
    for name in _evidence_names(task_dir):
        if is_record_name("red", name):
            record = load_record(os.path.join(task_dir, "evidence", name))
            code = record.get("exit_code")
            if record.get("passed") is False and isinstance(code, int) \
                    and not isinstance(code, bool) and code != 0:
                out.append((name, record))
    return out


def has_red(task_dir):
    """True when a red record holding a failed run is on record, signed or not."""
    return bool(red_records(task_dir))


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
    refactor with no red takes it out (decision record
    `governance/decisions/2026-10-29-a-strategy-can-carry-checks-a-step-off-makes-advisory.md`)."""
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


def waiver_lines(task, view):
    """A notice for each issue waiver of one of the strategy's checks in the issue's
    `config:`: the check, the reason and whether it is approved. An approved waiver
    is one the issue's generation (`view`) holds, which passed the lint that
    committed it (ADR-039); any other leaves the check as it was."""
    held = (((task or {}).get("config") or {}).get("checks") or {})
    committed = ((getattr(view, "provenance", None) or {}).get("waivers") or {}) \
        if view is not None else {}
    approved = {str(r.get("entry")) for r in committed.values()
                if isinstance(r, dict) and r.get("scope") == "issue"}
    lines = []
    for check in CHECKS:
        waiver = (held.get(check) or {}).get("waiver") if isinstance(held.get(check), dict) \
            else None
        if not isinstance(waiver, dict):
            continue
        state = ("approved" if f"checks.{check}" in approved else
                 f"not approved, so {check} keeps its severity; run `compass policy lint "
                 f"--issue {(task or {}).get('issue')}` to see why")
        lines.append(f"waiver of {check}: {waiver.get('reason') or 'no reason recorded'}"
                     f" - {state}")
    return lines
