"""The tighten-only settings of `compass.yml` only add (`compass_pkg.tighten`).

ADR-094 keeps five settings that can change what an issue owes, and each can
only make it owe more: `signoff_labels`, `require_evidence`, `agent_review:
on`, `project_checks` and `capabilities: {entry-exit-evaluation: true}`.
`tighten.apply` adds them to a resolved configuration. These tests pin what
each adds and check the rule of plan section 3.3: on every point of the
contract 1 grid (1,200 assessments) under every subset of the four `G5` labels
and one label a setting adds (32 subsets), each setting alone and all five
together owe at least what the bare configuration owes. The gates and checks
after are a superset of those before, no severity or skip verdict is lower, a
gate that applied still applies, and the evidence tokens and gates of
`evidence_required` are a superset.

Each test runs on two bare configurations: the check set
(`check_set.resolved()`) and the live default resolved for a project with no
`compass.yml`, which `tests/test_check_set.py` shows are the same rules.
"""
from __future__ import annotations

import copy
import re

import pytest

import compat_baseline as cb
from compass_pkg import catalogue_spec as spec
from compass_pkg import check_set, effective, settings_lint, tighten
from compass_pkg import evidence_required as er
from compass_pkg.core import CompassError, reading_matches
from compass_pkg.routing import RoutingConflict

NEW_LABEL = "billing"
PROJECT_CHECK = {"id": "arch-fitness", "name": "Architecture fitness",
                 "command": "python3 scripts/arch.py", "stage": "build",
                 "when": {"risk": ["critical"]}}
EACH = {
    "signoff_labels": {"signoff_labels": [NEW_LABEL]},
    "require_evidence": {"require_evidence": [
        {"when": {"risk": ["cross-cutting", "critical"]}, "add": ["reproduce-first"]},
        {"add": ["architecture"]},
        {"when": {"labels_any": [NEW_LABEL]}, "add": ["human-approval"]}]},
    "agent_review": {"agent_review": True},
    "project_checks": {"project_checks": [PROJECT_CHECK]},
    "capabilities": {"capabilities": {"entry-exit-evaluation": True}},
}
ALL = {key: value for one in EACH.values() for key, value in one.items()}


@pytest.fixture(scope="module", params=["check-set", "live-default"])
def base(request, tmp_path_factory):
    """The bare configuration: the check set, and the live default resolved for a
    project with no `compass.yml`, which step 2's parity test shows are equal."""
    if request.param == "check-set":
        return check_set.resolved()
    return effective.resolve_live(str(tmp_path_factory.mktemp("bare-project"))).resolved


def _agent_review_block():
    return check_set.load()["optional"]["agent_review"]


def _policy(resolved):
    view = effective.EffectiveView("live", None, None, resolved, {}, {})
    return tighten.with_settings(view.evaluator_policy(), resolved)


def _assess(**over):
    out = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
           "goal": "delivery", "urgency": "none", "labels": []}
    out.update(over)
    return out


# --- what each setting adds ------------------------------------------------------

def test_the_five_settings_are_the_tighten_keys():
    assert spec.TIGHTEN_KEYS == tuple(EACH)
    assert set(spec.TIGHTEN_KEYS) - {"capabilities"} <= set(spec.SETTINGS_KEYS)


def test_no_settings_change_nothing_and_the_base_is_not_changed(base):
    before = copy.deepcopy(base)
    assert tighten.apply(base, {}) == base
    tighten.apply(base, ALL)
    assert base == before
    assert tighten.evaluator_settings(base) == {}


def test_signoff_labels_join_the_g5_labels(base):
    out = tighten.apply(base, EACH["signoff_labels"])
    assert out["gates"]["G5"]["when"]["labels_any"] == list(er.G5_LABELS) + [NEW_LABEL]
    again = tighten.apply(base, {"signoff_labels": ["auth", NEW_LABEL, NEW_LABEL]})
    assert again["gates"]["G5"]["when"]["labels_any"] == list(er.G5_LABELS) + [NEW_LABEL]
    assert tighten.evaluator_settings(out) == {"signoff_labels": [NEW_LABEL]}


def test_a_signoff_label_owes_what_a_shipped_g5_label_owes(base):
    policy = _policy(tighten.apply(base, EACH["signoff_labels"]))
    shipped = er.evaluate(_assess(size="atomic", risk="trivial", labels=["auth"]), policy)
    added = er.evaluate(_assess(size="atomic", risk="trivial", labels=[NEW_LABEL]), policy)
    assert added["evidence_required"] == shipped["evidence_required"]
    assert {"human-approval", "scenario-approval"} <= set(added["evidence_required"])
    assert added["rules_fired"] == shipped["rules_fired"]
    bare = er.evaluate(_assess(size="atomic", risk="trivial", labels=[NEW_LABEL]),
                       _policy(base))
    assert "human-approval" not in bare["evidence_required"]


def test_a_spike_on_a_signoff_label_is_refused_as_on_a_shipped_one(base):
    policy = _policy(tighten.apply(base, EACH["signoff_labels"]))
    with pytest.raises(RoutingConflict):
        er.evaluate(_assess(goal="exploration", labels=[NEW_LABEL]), policy)
    assert er.evaluate(_assess(goal="exploration", labels=[NEW_LABEL]),
                       _policy(base))["delivery_approach"] == "spike"


def test_require_evidence_adds_its_tokens_under_a_rule_id(base):
    out = tighten.apply(base, EACH["require_evidence"])
    assert [r["id"] for r in out["require_evidence"]] == [
        "RP-SETTING-1", "RP-SETTING-2", "RP-SETTING-3"]
    assert out["require_evidence"][1]["when"] == {}
    result = er.evaluate(_assess(risk="cross-cutting"), _policy(out))
    assert {"reproduce-first", "architecture"} <= set(result["evidence_required"])
    assert result["rules_fired"][-2:] == ["RP-SETTING-1", "RP-SETTING-2"]
    # Applied again, the rules keep counting, so no id is taken twice.
    twice = tighten.apply(out, {"require_evidence": [{"add": ["security"]}]})
    assert twice["require_evidence"][-1]["id"] == "RP-SETTING-4"


def test_require_evidence_does_not_reach_a_spike(base):
    policy = _policy(tighten.apply(base, EACH["require_evidence"]))
    result = er.evaluate(_assess(goal="exploration"), policy)
    assert result["evidence_required"] == [] and result["gates"] == ["spike.conclude"]


def test_agent_review_on_adds_the_advisory_judged_check_at_ship(base):
    for value in (True, "on"):
        out = tighten.apply(base, {"agent_review": value})
        assert out["checks"]["agent-review"] == _agent_review_block()["checks"]["agent-review"]
        assert out["checks"]["agent-review"]["severity"] == "advisory"
        assert out["stages"]["ship"]["entry"] == ["agent-review"]
    for value in (False, "off"):
        assert tighten.apply(base, {"agent_review": value}) == base


def test_agent_review_on_keeps_a_check_the_base_already_holds(base):
    held = copy.deepcopy(base)
    held["checks"]["agent-review"] = dict(_agent_review_block()["checks"]["agent-review"],
                                          statement="kept")
    out = tighten.apply(held, {"agent_review": "on"})
    assert out["checks"]["agent-review"]["statement"] == "kept"
    assert out["stages"]["ship"]["entry"] == ["agent-review"]


def test_a_project_check_adds_a_command_check_and_its_guardrail(base):
    out = tighten.apply(base, EACH["project_checks"])
    check = out["checks"]["arch-fitness"]
    assert check["impl"] == "command-passes" and check["severity"] == "blocking"
    assert check["params"] == {"command": PROJECT_CHECK["command"]}
    gate = out["gates"]["arch-fitness"]
    assert gate["kind"] == "guardrail" and gate["stage"] == "build"
    assert gate["checks"] == ["arch-fitness"] and gate["when"] == {"risk": ["critical"]}
    view = effective.EffectiveView("live", None, None, out, {}, {})
    assert view.command_checks() == [{"id": "arch-fitness", "name": "Architecture fitness",
                                      "checks": ["command-passes"],
                                      "params": {"command": PROJECT_CHECK["command"]}}]


def test_the_capability_is_switched_on_only_by_true(base):
    assert tighten.apply(base, EACH["capabilities"])["capabilities"] == {
        "entry-exit-evaluation": True}
    off = {"capabilities": {"entry-exit-evaluation": False}}
    assert tighten.apply(base, off) == base


@pytest.mark.parametrize("settings, path", [
    ({"signoff_labels": "billing"}, "signoff_labels"),
    ({"require_evidence": [{"add": ["nope"]}]}, "require_evidence[0].add"),
    ({"require_evidence": [{"add": ["security"], "remove": ["clarity"]}]},
     "require_evidence[0].remove"),
    ({"agent_review": "sometimes"}, "agent_review"),
    ({"project_checks": [dict(PROJECT_CHECK, id="G5")]}, "project_checks[0].id"),
    ({"project_checks": [dict(PROJECT_CHECK, severity="advisory")]},
     "project_checks[0].severity"),
    ({"capabilities": {"artifact-freshness-x": True}}, "capabilities.artifact-freshness-x"),
    ({"checks": {}}, "checks"),
])
def test_a_value_that_does_not_add_is_refused_before_anything_is_applied(base, settings, path):
    with pytest.raises(CompassError, match=re.escape(path)):
        tighten.apply(base, settings)


def test_agent_review_needs_the_optional_block_of_the_check_set(base):
    doc = check_set.load()
    doc["optional"] = {}
    with pytest.raises(CompassError, match="no optional agent review"):
        tighten.apply(base, {"agent_review": "on"}, check_set_doc=doc)


def test_settings_of_keeps_only_the_tighten_keys():
    doc = dict(ALL, schema=1, autonomy="balanced", checks={})
    assert tighten.settings_of(doc) == ALL
    assert tighten.settings_of(None) == {}


# --- only adds, on the whole grid ------------------------------------------------

_SEVERITY = {s: i for i, s in enumerate(spec.SEVERITIES)}
_ON_SKIPPED = {s: i for i, s in enumerate(spec.ON_SKIPPED)}


def _points():
    header, rows = cb.load_routing()
    grid = [row["assessment"] for row in rows if row["kind"] == "grid"]
    subsets = list(cb.label_subsets(list(header["labels"]) + [NEW_LABEL]))
    assert len(grid) == 1200 and len(subsets) == 32
    for assessment in grid:
        readings = {k: v for k, v in assessment.items() if k != "role"}
        readings["size"] = cb.SIZE_NOW.get(readings["size"], readings["size"])
        for labels in subsets:
            yield dict(readings, labels=labels)


def _owed(readings, policy):
    try:
        out = er.evaluate(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return None     # refused: owes more than any result
    return set(out["evidence_required"]), set(out["gates"])


def _catalogue_lowerings(before, after):
    """What `after` owes less of than `before`, read from the catalogues."""
    out = []
    for catalogue in ("checks", "gates"):
        missing = set(before.get(catalogue) or {}) - set(after.get(catalogue) or {})
        out += [f"{catalogue}.{i} removed" for i in sorted(missing)]
    for check_id, check in (before.get("checks") or {}).items():
        now = (after.get("checks") or {}).get(check_id)
        if now is None:
            continue
        if _SEVERITY[now.get("severity", "blocking")] < _SEVERITY[check.get("severity",
                                                                              "blocking")]:
            out.append(f"checks.{check_id} severity lowered")
        if _ON_SKIPPED.get(now.get("on_skipped"), 0) < _ON_SKIPPED.get(check.get("on_skipped"), 0):
            out.append(f"checks.{check_id} on_skipped lowered")
        rest = {k: v for k, v in check.items() if k not in ("severity", "on_skipped")}
        if rest != {k: v for k, v in now.items() if k not in ("severity", "on_skipped")}:
            out.append(f"checks.{check_id} changed")
    for gate_id, gate in (before.get("gates") or {}).items():
        now = (after.get("gates") or {}).get(gate_id)
        if now is None:
            continue
        if not set(gate.get("checks") or ()) <= set(now.get("checks") or ()):
            out.append(f"gates.{gate_id} lost a check")
        for key in ("stage", "applies_to", "accepts", "kind"):
            if gate.get(key) != now.get(key):
                out.append(f"gates.{gate_id}.{key} changed")
    for stage_id, stage in (before.get("stages") or {}).items():
        now = (after.get("stages") or {}).get(stage_id) or {}
        for key in ("entry", "exit"):
            if not set(stage.get(key) or ()) <= set(now.get(key) or ()):
                out.append(f"stages.{stage_id}.{key} lost a check")
    for name, on in (before.get("capabilities") or {}).items():
        if on and not (after.get("capabilities") or {}).get(name):
            out.append(f"capabilities.{name} turned off")
    return out


def _grid_lowerings(before, after, first_only=False):
    """`(points, lowerings)`: each grid point where `after` owes less than
    `before`, as a gate that stops applying or evidence that is no longer owed."""
    policy_before, policy_after = _policy(before), _policy(after)
    gates = [(g, before["gates"][g].get("when"), (after["gates"].get(g) or {}).get("when"))
             for g in before.get("gates") or {}]
    out, points = [], 0
    for readings in _points():
        points += 1
        for gate_id, was, now in gates:
            if reading_matches(was, readings) and not reading_matches(now, readings):
                out.append(f"{readings}: gate {gate_id} no longer applies")
        owed_before, owed_after = _owed(readings, policy_before), _owed(readings, policy_after)
        if owed_after is not None and (owed_before is None or not (
                owed_before[0] <= owed_after[0] and owed_before[1] <= owed_after[1])):
            out.append(f"{readings}: before {owed_before}, after {owed_after}")
        if out and first_only:
            break
    return points, out


@pytest.mark.parametrize("name", list(EACH) + ["all"])
def test_each_setting_owes_at_least_what_the_bare_configuration_owes(base, name):
    """Plan section 3.3: every point of the grid owes at least what the bare
    configuration owes, and the catalogues only grow."""
    after = tighten.apply(base, ALL if name == "all" else EACH[name])
    assert _catalogue_lowerings(base, after) == []
    points, lowered = _grid_lowerings(base, after)
    assert points == 1200 * 32
    assert lowered == [], f"{len(lowered)} points owe less:\n" + "\n".join(lowered[:20])


def test_a_setting_adds_something_on_the_grid(base):
    """The comparison is not empty: `signoff_labels` and `require_evidence` each
    make some point owe more."""
    for name in ("signoff_labels", "require_evidence"):
        after = _policy(tighten.apply(base, EACH[name]))
        bare = _policy(base)
        assert any(_owed(r, bare) != _owed(r, after) for r in _points()), name


@pytest.mark.parametrize("plant", ["label", "severity", "stage-entry", "evidence"])
def test_the_only_adds_check_sees_a_planted_lowering(base, plant):
    """A planted change that owes less is reported: by the catalogue comparison
    for an entry, and by the grid for a gate or evidence."""
    after = copy.deepcopy(base)
    if plant == "label":
        after["gates"]["G5"]["when"]["labels_any"] = ["auth"]
        _, lowered = _grid_lowerings(base, after, first_only=True)
    elif plant == "severity":
        after["checks"]["suite-passed"]["severity"] = "advisory"
        lowered = _catalogue_lowerings(base, after)
    elif plant == "stage-entry":
        before = tighten.apply(base, EACH["agent_review"])
        lowered = _catalogue_lowerings(before, after)
    else:
        rich = tighten.apply(base, EACH["require_evidence"])
        _, lowered = _grid_lowerings(rich, after, first_only=True)
    assert lowered, f"the planted {plant} lowering went unseen"


def test_the_lint_and_apply_agree_on_what_they_refuse(base):
    """`apply` refuses exactly what the lint's value check refuses, so a file the
    lint passes always applies."""
    for name, settings in EACH.items():
        assert settings_lint.value_problems(settings, base) == [], name
        tighten.apply(base, settings)
