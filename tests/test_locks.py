"""Locks, unlocks and conformance (ADR-039).

A lock lets a lower layer tighten an entry and refuses a change that loosens it
or cannot be compared. The comparison is the classifier's, projected to the
footprint of the locked entries. Small configurations (`classifier_fixtures`)
carry most tests, so a test that scans the grid takes a fraction of a second;
a few tests enforce the locks against the shipped preset.

Scenario ids: `LK-1` to `LK-9` (issue `locks`).
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

MODULE = ROOT / "cli" / "compass_pkg" / "locks.py"


# --- LK-9: the module's declarations ----------------------------------------------

def test_lk_9_the_module_declares_its_dependencies():
    assert MODULE.is_file(), "cli/compass_pkg/locks.py does not exist"
    text = MODULE.read_text(encoding="utf-8")
    header = text.split("from __future__", 1)[0]
    assert "# DEPENDENCY:" in header
    assert "compass_pkg.classify" in header
    assert "compass_pkg.merge" in header


# --- helpers ---------------------------------------------------------------------

def _api():
    from compass_pkg import locks
    return locks


def _fixtures():
    import classifier_fixtures
    return classifier_fixtures


def _layer(doc, kind="project", name=None):
    from compass_pkg.layers import Layer
    doc = doc if kind == "issue" else {"schema": 1, **doc}
    return Layer(name or kind, kind, doc, "digest")


def _preset_doc():
    """The committed preset as one layer document, with `locked` markers."""
    import yaml
    from compass_pkg import catalogue_spec
    doc = {"schema": 1}
    directory = ROOT / "governance" / "presets" / "default"
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))
        doc[name] = part[name]
    return doc


def _waiver(approver="owner-1", reason="A recorded reason."):
    return {"reason": reason, "approved_by": approver, "approved_on": "2026-10-01"}


# --- LK-1: reading the locks ------------------------------------------------------

def test_lk_1_a_lock_on_an_entry_or_in_its_set_is_declared():
    locks = _api()
    doc = {"checks": {"a": {"locked": True}, "b": {"set": {"locked": "hard"}},
                      "c": {"set": {"severity": "advisory"}}},
           "stages": {"verify": {"locked": True}},
           "approaches": {"spike": {"locked": True}},
           "rules": {"immovable_gates": {"locked": True}}}
    assert locks.declared_locks(doc) == {
        "checks.a": True, "checks.b": "hard", "stages.verify": True,
        "approaches.spike": True, "rules.immovable_gates": True}


def test_lk_1_a_value_that_is_not_a_lock_level_is_not_a_lock():
    locks = _api()
    doc = {"checks": {"a": {"locked": False}, "b": {"locked": "soft"},
                      "c": {"locked": 1}}}
    assert locks.declared_locks(doc) == {}


def test_lk_1_the_higher_level_wins_and_the_declaring_layer_is_named():
    locks = _api()
    parent = _layer({"checks": {"a": {"locked": True}, "b": {"locked": "hard"}}},
                    "parent", "base")
    project = _layer({"checks": {"a": {"locked": "hard"}, "b": {"locked": True},
                                 "c": {"locked": True}}}, "project")
    held = locks.lock_set([parent, project])
    assert {k: v.level for k, v in held.items()} == {
        "checks.a": "hard", "checks.b": "hard", "checks.c": True}
    assert held["checks.a"].layer == "project"
    assert held["checks.b"].layer == "base"
    assert held["checks.c"].layer == "project"


def test_lk_1_a_valid_project_unlock_lifts_a_true_lock_and_not_a_hard_one():
    locks = _api()
    parent = _layer({"checks": {"a": {"locked": True}, "b": {"locked": "hard"},
                                "c": {"locked": True}}}, "parent", "base")
    project = _layer({"owner": "owner-1", "checks": {
        "a": {"unlock": True, "waiver": _waiver()},
        "b": {"unlock": True, "waiver": _waiver()},
        "c": {"unlock": True, "waiver": _waiver("someone-else")}}})
    assert set(locks.lock_set([parent, project])) == {"checks.b", "checks.c"}


def test_lk_1_a_lock_the_project_itself_declares_survives_its_own_layer():
    locks = _api()
    project = _layer({"owner": "owner-1",
                      "checks": {"mine": {"locked": True}}})
    assert set(locks.lock_set([project])) == {"checks.mine"}


def _expected_shipped_locks():
    """ADR-039's table, written out: the gates and the checks in their sets."""
    import yaml
    gates = yaml.safe_load((ROOT / "governance" / "presets" / "default"
                            / "gates.yml").read_text(encoding="utf-8"))["gates"]
    expected = {"stages.assess": True, "stages.verify": True, "stages.ship": True,
                "approaches.spike": True, "rules.immovable_gates": True,
                "gates.verify.correctness": True, "gates.verify.governance": True,
                "gates.verify.traceability": True, "gates.spike.conclude": True,
                "gates.G5": "hard", "checks.human-approval-present": "hard"}
    for gate in ("G1", "G2", "G3", "G4", "S1", "S2"):
        expected[f"gates.{gate}"] = True
        for check in gates[gate]["checks"]:
            expected[f"checks.{check}"] = True
    return expected


def test_lk_1_the_shipped_preset_gives_exactly_the_adr_lock_set():
    locks = _api()
    held = locks.lock_set([_layer(_preset_doc(), "parent", "default")])
    assert {k: v.level for k, v in held.items()} == _expected_shipped_locks()
    assert all(v.layer == "default" for v in held.values())


def test_lk_1_the_preset_summary_agrees_with_the_locks_it_declares():
    import yaml
    locks = _api()
    summary = yaml.safe_load((ROOT / "governance" / "presets" / "default"
                              / "preset.yml").read_text(encoding="utf-8"))["locks"]
    held = {k: v.level for k, v in
            locks.lock_set([_layer(_preset_doc(), "parent", "default")]).items()}
    assert sorted(summary["hard"]) == sorted(k for k, v in held.items() if v == "hard")
    assert sorted(summary["locked"]) == sorted(k for k, v in held.items() if v is True)
    assert "gates.G5" in summary["hard"] and "checks.human-approval-present" in summary["hard"]


# --- LK-2: the footprint ----------------------------------------------------------

def _held(*ids, hard=()):
    locks = _api()
    held = {i: locks.Lock(True, "default") for i in ids}
    held.update({i: locks.Lock("hard", "default") for i in hard})
    return held


def _guarded():
    """The small base configuration with two stage lists, a gate carrying a
    check, a rule set of immovable gates and a spike approach."""
    config = _fixtures().base()
    config["checks"]["tests-pass"]["on_skipped"] = "fail"
    config["stages"]["implement"]["exit"] = ["tests-pass"]
    config["gates"]["verify.correctness"]["locked"] = True
    config["rules"]["immovable_gates"] = {
        "kind": "immovable-gates", "hit": {"gate": "collect"},
        "rules": {
            "RULE-1": {"order": 1, "then": {"gate": "verify.correctness"}},
            "RULE-2": {"order": 2, "then": {"require_artifact": "intent"}},
            "RULE-3": {"order": 3, "then": {"block_phase": "verify"}},
            "RULE-4": {"order": 4, "then": {"require_skill": "evidence-gates"}},
            "RULE-5": {"order": 5, "when": {"risk": "critical"},
                    "then": {"force_minimum_approach": "full"}},
        }}
    config["approaches"]["spike"] = {
        "weight": 0, "ships": False,
        "stages": {"define": "light", "implement": "full", "verify": "full"},
        "gates": [], "artifacts": {}, "subtask_ceiling": 1, "checkpoints": {}}
    return config


def test_lk_2_a_locked_check_covers_its_fields_and_its_places():
    locks = _api()
    fp = locks.footprint(_held("checks.tests-pass"), _guarded())
    assert fp.checks == {"tests-pass"}
    facts = fp.facts("checks.tests-pass")
    for field in ("checks.kind", "checks.impl", "checks.params", "checks.accepts",
                  "checks.reviewers", "checks.approvers", "checks.inputs",
                  "checks.severity", "checks.on_skipped", "checks.statement",
                  "stages.entry", "stages.exit", "gates.checks"):
        assert field in facts, field


def test_lk_2_a_locked_gate_covers_its_checks_types_stage_and_membership():
    locks = _api()
    fp = locks.footprint(_held("gates.G1"), _guarded())
    assert fp.gates == {"G1"}
    assert set(fp.facts("gates.G1")) == {"gates.checks", "gates.accepts",
                                         "gates.stage", "approaches.gates"}


def test_lk_2_a_locked_stage_covers_existence_order_and_its_lists():
    locks = _api()
    fp = locks.footprint(_held("stages.verify"), _guarded())
    assert fp.stages == {"verify"}
    assert set(fp.facts("stages.verify")) == {
        "existence", "stages.order", "stages.entry", "stages.exit",
        "approaches.stages"}


def test_lk_2_a_locked_approach_covers_existence_and_ships():
    locks = _api()
    fp = locks.footprint(_held("approaches.spike"), _guarded())
    assert fp.approaches == {"spike"}
    assert set(fp.facts("approaches.spike")) == {"existence", "approaches.ships"}


def test_lk_2_a_locked_rule_set_covers_each_effect_it_has():
    locks = _api()
    fp = locks.footprint(_held("rules.immovable_gates"), _guarded())
    assert fp.rule_gates == {"verify.correctness"}
    assert fp.rule_artifacts == {"intent"}
    assert fp.rule_blocks == {"verify"}
    assert fp.rule_skills == {"evidence-gates"}
    # An effect no obligation fact carries is protected as one value, with its `when`.
    assert fp.rule_identity == {
        ("immovable_gates", "RULE-5"): {"when": {"risk": "critical"},
                                     "then": {"force_minimum_approach": "full"}}}
    assert "evaluation.required_artifacts" in fp.facts("rules.immovable_gates")
    assert "rules.immovable_gates.RULE-5" in fp.facts("rules.immovable_gates")


def test_lk_2_an_entry_that_is_not_locked_adds_nothing():
    locks = _api()
    fp = locks.footprint(_held("checks.tests-pass"), _guarded())
    assert "no-secrets" not in fp.checks
    assert fp.gates == fp.stages == fp.approaches == set()
    assert fp.rule_gates == set() and fp.rule_identity == {}
    assert fp.facts("checks.no-secrets") == ()


def test_lk_2_a_lock_on_an_entry_the_configuration_lacks_is_listed_apart():
    locks = _api()
    fp = locks.footprint(_held("checks.gone", "stages.nowhere"), _guarded())
    assert fp.checks == set() and fp.stages == set()
    assert fp.absent == ("checks.gone", "stages.nowhere")


# --- LK-3: a lock on a check -----------------------------------------------------

def _before():
    """The configuration the lock is declared in: `tests-pass` is a human check
    that sits in a stage list and in two gates, and every compared field of it
    has a value."""
    config = _fixtures().base()
    config["checks"]["tests-pass"].update(
        kind="human", statement="A person ran the suite.", on_skipped="not-applicable",
        accepts=["test-run", "manual-review"], reviewers=["alice"],
        approvers=["alice"], params={"files": 5})
    config["stages"]["implement"]["exit"] = ["tests-pass"]
    return config


def _child(edit):
    config = _before()
    edit(config)
    return config


def _enforce(after, locks=("checks.tests-pass",), before=None, **kwargs):
    return _api().enforce(_held(*locks), before or _before(), after, **kwargs)


def _remove_the_stage(c):
    del c["stages"]["implement"]
    for approach in c["approaches"].values():
        approach["stages"].pop("implement")


def _change_when(c):
    c["checks"]["tests-pass"]["when"] = {"risk": "critical"}


def _detach_from_the_gates(c):
    c["gates"]["verify.correctness"]["checks"] = []
    c["gates"]["G1"]["checks"] = []


def _skip_passes(c):
    c["checks"]["tests-pass"]["on_skipped"] = "pass"


def _widen_accepts(c):
    c["checks"]["tests-pass"]["accepts"].append("attestation")


def _widen_reviewers(c):
    c["checks"]["tests-pass"]["reviewers"].append("bob")


def _drop_approvers(c):
    del c["checks"]["tests-pass"]["approvers"]


def _change_params(c):
    c["checks"]["tests-pass"]["params"] = {"files": 9}


def _change_statement(c):
    c["checks"]["tests-pass"]["statement"] = "Nobody needs to run the suite."


INDIRECT_ROUTES = {
    "remove-the-stage-that-carries-it": (_remove_the_stage, {"stages.exit"}),
    "change-its-when": (_change_when, {"stages.exit", "gates.checks"}),
    "detach-it-from-its-gates": (_detach_from_the_gates, {"gates.checks"}),
    "on-skipped-pass": (_skip_passes, {"checks.on_skipped"}),
    "widen-accepts": (_widen_accepts, {"checks.accepts"}),
    "widen-reviewers": (_widen_reviewers, {"checks.reviewers"}),
    "drop-approvers": (_drop_approvers, {"checks.approvers"}),
    "change-params": (_change_params, {"checks.params"}),
    "change-the-statement": (_change_statement, {"checks.statement"}),
}


@pytest.mark.parametrize("route", sorted(INDIRECT_ROUTES))
def test_lk_3_each_indirect_route_is_refused_and_names_the_check(route):
    edit, fields = INDIRECT_ROUTES[route]
    result = _enforce(_child(edit), early_exit=False)
    assert not result.ok
    assert {r.entry for r in result.refusals} == {"checks.tests-pass"}
    assert {r.field for r in result.refusals} <= fields
    assert {r.outcome for r in result.refusals} <= {"looser", "incomparable"}


def test_lk_3_the_indirect_routes_are_the_nine_the_design_lists():
    assert len(INDIRECT_ROUTES) == 9


def _tighten_on_skipped(c):
    c["checks"]["tests-pass"]["on_skipped"] = "fail"


def _narrow_accepts(c):
    c["checks"]["tests-pass"]["accepts"].remove("manual-review")


def _add_to_another_stage(c):
    c["stages"]["verify"]["entry"] = ["tests-pass"]


def _add_an_unlocked_check_beside_it(c):
    c["gates"]["verify.correctness"]["checks"].append("no-secrets")
    c["stages"]["implement"]["exit"].append("no-secrets")


TIGHTENINGS = {
    "raise-on-skipped": _tighten_on_skipped,
    "narrow-accepts": _narrow_accepts,
    "add-it-to-another-stage": _add_to_another_stage,
    "add-an-unlocked-check-beside-it": _add_an_unlocked_check_beside_it,
    "no-change": lambda c: None,
}


@pytest.mark.parametrize("name", sorted(TIGHTENINGS))
def test_lk_3_a_change_that_only_tightens_is_allowed(name):
    result = _enforce(_child(TIGHTENINGS[name]))
    assert result.ok, [r.message for r in result.refusals]
    assert result.refusals == ()


def test_lk_3_a_refusal_names_the_entry_level_field_values_and_point():
    result = _enforce(_child(_skip_passes))
    refusal = result.refusals[0]
    assert refusal.entry == "checks.tests-pass"
    assert refusal.level is True
    assert refusal.field == "checks.on_skipped"
    assert refusal.key == "tests-pass"
    assert refusal.outcome == "looser"
    assert refusal.parent == "not-applicable" and refusal.child == "pass"
    assert "risk" in refusal.where and "labels" in refusal.where
    text = refusal.message
    for part in ("checks.tests-pass", "locked", "checks.on_skipped",
                 "not-applicable", "pass", refusal.where):
        assert part in text, part


def test_lk_3_the_lock_level_and_the_layer_that_declared_it_are_in_the_message():
    locks = _api()
    held = {"checks.tests-pass": locks.Lock("hard", "default")}
    result = locks.enforce(held, _before(), _child(_skip_passes))
    refusal = result.refusals[0]
    assert refusal.level == "hard"
    assert "hard" in refusal.message and "default" in refusal.message


def test_lk_3_a_change_to_a_gate_list_is_judged_by_the_locked_check_alone():
    """Removing an unlocked check from the gate is not a refusal."""
    def remove_unlocked(c):
        c["gates"]["verify.security"]["checks"] = []
    config = _before()
    assert _enforce(_child(remove_unlocked), before=config).ok


def test_lk_3_early_exit_stops_after_the_first_point_that_refuses():
    both = _child(lambda c: (_skip_passes(c), _widen_accepts(c)))
    many = _enforce(both, early_exit=False)
    assert {r.field for r in many.refusals} == {"checks.on_skipped", "checks.accepts"}
    one = _enforce(both)
    assert one.refusals and len({r.where for r in one.refusals}) == 1
    assert one.evaluated < many.evaluated


# --- LK-4: a lock on a gate, a stage, a rule set or an approach ------------------

def _guard_all():
    """`_before()` with a first stage, `verify` before `ship`, a rule set that adds a
    gate to every approach, a spike approach, and a lock on each of them. The
    returned locks are the ones the tests enforce."""
    config = _before()
    config["stages"]["ship"] = {"order": 4, "modes": {"light": {"rank": 2},
                                                      "full": {"rank": 3}}}
    config["stages"]["verify"]["exit"] = ["tests-pass"]
    for approach in config["approaches"].values():
        approach["stages"]["ship"] = "full"
    config["rules"]["immovable_gates"] = {
        "kind": "immovable-gates", "hit": {"gate": "collect"},
        "rules": {"RULE-1": {"order": 1, "then": {"gate": "verify.security"}},
                  "RULE-2": {"order": 2, "when": {"risk": "critical"},
                          "then": {"force_minimum_approach": "full"}}}}
    config["approaches"]["spike"] = {
        "weight": 0, "ships": False,
        "stages": {"define": "light", "implement": "full", "verify": "full",
                   "ship": "light"},
        "gates": [], "artifacts": {}, "subtask_ceiling": 1, "checkpoints": {}}
    return config


GUARDED = ("gates.G1", "stages.define", "stages.verify", "stages.ship",
           "rules.immovable_gates", "approaches.spike")


def _enforce_guard(edit, **kwargs):
    before = _guard_all()
    after = copy.deepcopy(before)
    edit(after)
    return _api().enforce(_held(*GUARDED), before, after, **kwargs)


def _remove_a_gate(c):
    del c["gates"]["G1"]


def _move_the_gate(c):
    c["gates"]["G1"]["stage"] = "implement"


def _widen_gate_accepts(c):
    c["gates"]["G1"]["accepts"].append("attestation")


def _drop_a_gate_check(c):
    c["gates"]["G1"]["checks"] = []


def _gate_stops_applying(c):
    c["gates"]["G1"]["applies_to"] = {"ships": False}


def _stage_leaves_an_approach(c):
    del c["approaches"]["regular"]["stages"]["verify"]


def _remove_a_stage(c):
    del c["stages"]["ship"]
    for approach in c["approaches"].values():
        approach["stages"].pop("ship")


def _verify_after_ship(c):
    c["stages"]["verify"]["order"] = 5


def _a_stage_before_the_first(c):
    c["stages"]["intake"] = {"order": 0, "modes": {"full": {"rank": 3}}}


def _empty_a_stage_exit(c):
    c["stages"]["verify"]["exit"] = []


def _drop_the_rule(c):
    del c["rules"]["immovable_gates"]["rules"]["RULE-1"]


def _point_the_rule_at_another_gate(c):
    c["rules"]["immovable_gates"]["rules"]["RULE-1"]["then"] = {
        "gate": "verify.correctness"}


def _change_an_unmapped_effect(c):
    c["rules"]["immovable_gates"]["rules"]["RULE-2"]["then"] = {
        "force_minimum_approach": "regular"}


def _ship_a_spike(c):
    c["approaches"]["spike"]["ships"] = True


def _remove_the_approach(c):
    del c["approaches"]["spike"]


REFUSED = {
    "remove-a-gate": (_remove_a_gate, "gates.G1", "existence"),
    "move-a-gate-to-another-stage": (_move_the_gate, "gates.G1", "gates.stage"),
    "widen-a-gates-accepts": (_widen_gate_accepts, "gates.G1", "gates.accepts"),
    "drop-a-check-from-a-gate": (_drop_a_gate_check, "gates.G1", "gates.checks"),
    "a-gate-stops-applying": (_gate_stops_applying, "gates.G1", "approaches.gates"),
    "a-stage-leaves-an-approach": (_stage_leaves_an_approach, "stages.verify",
                                   "approaches.stages"),
    "remove-a-stage": (_remove_a_stage, "stages.ship", "existence"),
    "verify-after-ship": (_verify_after_ship, "stages.verify", "stages.order"),
    "a-stage-before-the-first": (_a_stage_before_the_first, "stages.define",
                                 "stages.order"),
    "empty-a-stage-exit": (_empty_a_stage_exit, "stages.verify", "stages.exit"),
    "drop-a-rule-that-adds-a-gate": (_drop_the_rule, "rules.immovable_gates",
                                     "approaches.gates"),
    "point-a-rule-at-another-gate": (_point_the_rule_at_another_gate,
                                     "rules.immovable_gates", "approaches.gates"),
    "change-an-effect-no-fact-carries": (_change_an_unmapped_effect,
                                         "rules.immovable_gates",
                                         "rules.immovable_gates.RULE-2"),
    "a-spike-that-ships": (_ship_a_spike, "approaches.spike", "approaches.ships"),
    "remove-the-spike": (_remove_the_approach, "approaches.spike", "existence"),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_lk_4_a_change_that_loosens_the_entry_is_refused(name):
    edit, entry, field = REFUSED[name]
    result = _enforce_guard(edit, early_exit=False)
    assert not result.ok
    assert (entry, field) in {(r.entry, r.field) for r in result.refusals}, \
        [(r.entry, r.field) for r in result.refusals]


def _add_a_stage_between(c):
    c["stages"]["ship"]["order"] = 6
    c["stages"]["review"] = {"order": 5, "modes": {"full": {"rank": 3}}}


def _add_a_check_to_a_gate(c):
    c["gates"]["G1"]["checks"].append("no-secrets")


def _narrow_gate_accepts(c):
    c["gates"]["G1"]["accepts"] = []


def _add_a_stage_after(c):
    c["stages"]["retro"] = {"order": 9, "modes": {"full": {"rank": 3}}}


def _add_a_gate_to_an_approach(c):
    c["approaches"]["regular"]["gates"].append("verify.security")


def _add_an_exit_check(c):
    c["stages"]["verify"]["exit"].append("no-secrets")


def _a_new_rule_beside_it(c):
    c["rules"]["immovable_gates"]["rules"]["RULE-3"] = {
        "order": 3, "then": {"gate": "verify.correctness"}}


def _renumber_all_stages(c):
    for body in c["stages"].values():
        body["order"] *= 10


ALLOWED = {
    "a-stage-between-verify-and-ship": _add_a_stage_between,
    "a-check-added-to-a-gate": _add_a_check_to_a_gate,
    "narrow-a-gates-accepts": _narrow_gate_accepts,
    "a-stage-after-the-last": _add_a_stage_after,
    "a-gate-added-to-an-approach": _add_a_gate_to_an_approach,
    "a-check-added-to-a-stage-exit": _add_an_exit_check,
    "a-rule-added-beside-the-locked-one": _a_new_rule_beside_it,
    "every-order-renumbered-in-step": _renumber_all_stages,
    "no-change": lambda c: None,
}


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_lk_4_a_change_that_only_adds_process_is_allowed(name):
    result = _enforce_guard(ALLOWED[name])
    assert result.ok, [r.message for r in result.refusals]


# --- LK-5: what a lock refuses whatever the layer says ---------------------------

def _parent_doc():
    """The small configuration as a parent layer that locks `tests-pass`
    (soft) and `human-approval` (hard)."""
    doc = _before()
    doc["checks"]["human-approval"] = {
        "statement": "A person approved.", "kind": "human", "impl": "human-approval-present",
        "severity": "blocking", "on_skipped": "fail", "locked": "hard"}
    doc["gates"]["G1"]["checks"].append("human-approval")
    doc["checks"]["tests-pass"]["locked"] = True
    return doc


def _chain(project, parent=None):
    return [_layer(parent or _parent_doc(), "parent", "base"), _layer(project)]


def _loosen_tests_pass():
    return {"owner": "owner-1", "checks": {"tests-pass": {
        "set": {"on_skipped": "pass"}, "waiver": _waiver()}}}


def test_lk_5_a_waiver_does_not_excuse_a_lock_refusal():
    result = _api().enforce_chain(_chain(_loosen_tests_pass()), early_exit=False)
    assert not result.ok
    refusal = result.refusals[0]
    assert (refusal.entry, refusal.field, refusal.layer) == (
        "checks.tests-pass", "checks.on_skipped", "project")
    assert "project" in refusal.message and "base" in refusal.message


def test_lk_5_a_hard_lock_is_refused_even_with_an_unlock_the_owner_approved():
    project = {"owner": "owner-1", "checks": {"human-approval": {
        "unlock": True, "set": {"on_skipped": "pass"}, "waiver": _waiver()}}}
    result = _api().enforce_chain(_chain(project), early_exit=False)
    fields = {(r.entry, r.field) for r in result.refusals}
    assert ("checks.human-approval", "unlock") in fields
    assert ("checks.human-approval", "checks.on_skipped") in fields
    unlock = next(r for r in result.refusals if r.field == "unlock")
    assert unlock.outcome == "refused" and "hard" in unlock.message


def test_lk_5_an_entry_that_is_not_locked_is_never_refused():
    project = {"checks": {"no-secrets": {"set": {"on_skipped": "pass"}},
                          "tests-pass": {"set": {"severity": "blocking"}}}}
    assert _api().enforce_chain(_chain(project)).ok


def test_lk_5_a_layer_that_changes_nothing_a_lock_covers_is_allowed():
    project = {"checks": {"extra": {
        "statement": "x", "kind": "deterministic", "impl": "suite-passed",
        "severity": "advisory", "on_skipped": "pass"}}}
    assert _api().enforce_chain(_chain(project)).ok


def test_lk_5_more_than_eight_named_labels_is_refused_with_the_count():
    names = [f"label-{i}" for i in range(9)]
    project = {"rules": {"floors": {"set": {"rules": {"set": {"F-MANY": {
        "order": 5, "when": {"labels_any": names},
        "then": {"force_minimum_approach": "regular"}}}}}}}}
    result = _api().enforce_chain(_chain(project))
    assert not result.ok
    refusal = result.refusals[0]
    assert refusal.field == "grid" and refusal.outcome == "incomparable"
    assert "10" in refusal.message and "eight" in refusal.message   # nine, and `auth`


def test_lk_5_a_configuration_the_evaluator_rejects_cannot_be_shown_to_hold():
    project = {"approaches": {"regular": {"set": {"ships": False}}}}
    result = _api().enforce_chain(_chain(project))
    assert not result.ok
    assert result.refusals[0].field == "evaluation"
    assert "evaluator" in result.refusals[0].message


def test_lk_5_a_lock_with_nothing_before_it_enforces_nothing():
    """The first layer has no layer above it, so no lock binds it."""
    only = [_layer(_parent_doc(), "parent", "base")]
    assert _api().enforce_chain(only).ok
    assert _api().enforce_chain([]).ok


# --- LK-6: unlocks ---------------------------------------------------------------

def _unlock_layer(kind="project", owner="owner-1", waiver="default", name=None):
    body = {"unlock": True, "set": {"on_skipped": "pass"}}
    if waiver == "default":
        body["waiver"] = _waiver()
    elif waiver is not None:
        body["waiver"] = waiver
    doc = {"checks": {"tests-pass": body}}
    if owner:
        doc["owner"] = owner
    return _layer(doc, kind, name)


def test_lk_6_an_unlock_from_the_project_with_the_owners_waiver_stands():
    locks = _api()
    found = locks.unlock_findings(_unlock_layer())
    assert [(f.entry, f.ok, f.reason) for f in found] == [("checks.tests-pass", True, "")]


UNLOCK_REFUSALS = {
    "an-issue-layer": (dict(kind="issue"), "only the project layer"),
    "a-parent-layer": (dict(kind="parent"), "only the project layer"),
    "no-owner-declared": (dict(owner=None), "no owner"),
    "no-waiver": (dict(waiver=None), "needs a waiver"),
    "no-reason": (dict(waiver={"approved_by": "owner-1", "approved_on": "2026-10-01"}),
                  "no reason"),
    "approved-by-someone-else": (dict(waiver=_waiver("alice")), "only the owner owner-1"),
    "approved-by-no-one": (dict(waiver={"reason": "r"}), "approved by no one"),
}


@pytest.mark.parametrize("name", sorted(UNLOCK_REFUSALS))
def test_lk_6_an_unlock_is_refused_and_says_why(name):
    locks = _api()
    arguments, words = UNLOCK_REFUSALS[name]
    found = locks.unlock_findings(_unlock_layer(**arguments))
    assert len(found) == 1 and not found[0].ok
    assert found[0].entry == "checks.tests-pass"
    assert words in found[0].reason, found[0].reason


def test_lk_6_a_hard_lock_and_an_entry_with_no_lock_refuse_an_unlock_when_the_lock_set_is_known():
    locks = _api()
    layer = _unlock_layer()
    hard = locks.unlock_findings(layer, {"checks.tests-pass": locks.Lock("hard", "base")})
    assert not hard[0].ok and "hard lock" in hard[0].reason
    none = locks.unlock_findings(layer, {})
    assert not none[0].ok and "not locked" in none[0].reason
    soft = locks.unlock_findings(layer, {"checks.tests-pass": locks.Lock(True, "base")})
    assert soft[0].ok


def test_lk_6_only_unlock_true_is_an_unlock():
    locks = _api()
    layer = _layer({"owner": "owner-1", "checks": {
        "tests-pass": {"unlock": False, "waiver": _waiver()}}})
    assert locks.unlock_findings(layer) == []


def test_lk_6_an_unlock_lifts_the_lock_for_the_project_and_the_issue_below_it():
    project = _unlock_layer().doc
    issue = {"checks": {"tests-pass": {"set": {"on_skipped": "pass"}}}}
    layers = [_layer(_parent_doc(), "parent", "base"), _layer(project),
              _layer(issue, "issue")]
    assert _api().enforce_chain(layers).ok


def test_lk_6_a_refused_unlock_leaves_the_entry_locked_and_is_itself_refused():
    project = _unlock_layer(waiver=_waiver("alice")).doc
    result = _api().enforce_chain(_chain(project), early_exit=False)
    fields = {(r.entry, r.field) for r in result.refusals}
    assert ("checks.tests-pass", "unlock") in fields
    assert ("checks.tests-pass", "checks.on_skipped") in fields


def test_lk_6_an_unlock_in_an_issue_or_a_parent_is_refused_by_name():
    locks = _api()
    base = _layer(_parent_doc(), "parent", "base")
    cases = {"issue": [base, _layer({}, "project"), _unlock_layer("issue", name="the-issue")],
             "parent": [base, _unlock_layer("parent", name="late-parent")]}
    for kind, layers in cases.items():
        result = locks.enforce_chain(layers, early_exit=False)
        refusals = [r for r in result.refusals if r.field == "unlock"]
        assert refusals, kind
        assert refusals[0].entry == "checks.tests-pass"
        assert "only the project layer" in refusals[0].message
        assert refusals[0].layer == layers[-1].name


# -- against the shipped preset

PRESET_CACHE = {}


def _preset_chain(project):
    return [_layer(_preset_doc(), "parent", "default"), _layer(project)]


def _enforce_preset(project, **kwargs):
    return _api().enforce_chain(_preset_chain(project), cache=PRESET_CACHE, **kwargs)


def test_lk_6_the_preset_allows_a_project_that_adds_a_check_to_a_locked_gate():
    project = {"checks": {"extra-check": {
        "statement": "An extra check.", "kind": "deterministic", "impl": "command-passes",
        "severity": "advisory", "on_skipped": "not-applicable"}},
        "gates": {"G1": {"set": {"checks": {"add": ["extra-check"]}}}}}
    result = _enforce_preset(project)
    assert result.ok, [r.message for r in result.refusals]
    assert result.evaluated > 1000


def test_lk_6_the_preset_refuses_a_hard_check_loosened_and_a_locked_gate_emptied():
    hard = _enforce_preset({"checks": {"human-approval-present": {
        "set": {"on_skipped": "pass"}}}})
    assert [(r.entry, r.field, r.level) for r in hard.refusals][:1] == [
        ("checks.human-approval-present", "checks.on_skipped", "hard")]
    emptied = _enforce_preset({"gates": {"G2": {"set": {"checks": []}}}})
    assert {(r.entry, r.field) for r in emptied.refusals} >= {("gates.G2", "gates.checks")}


def test_lk_6_the_preset_lets_the_owner_unlock_a_soft_lock_and_never_a_hard_one():
    soft = {"owner": "owner-1", "checks": {"suite-passed": {
        "unlock": True, "set": {"on_skipped": "not-applicable"}, "waiver": _waiver()}}}
    assert _enforce_preset(soft).ok
    hard = {"owner": "owner-1", "gates": {"G5": {
        "unlock": True, "set": {"checks": []}, "waiver": _waiver()}}}
    result = _enforce_preset(hard)
    assert ("gates.G5", "unlock") in {(r.entry, r.field) for r in result.refusals}


# --- LK-7: conformance -----------------------------------------------------------

def test_lk_7_a_project_with_no_unlock_is_conformant():
    locks = _api()
    layer = _layer({"owner": "owner-1", "checks": {"tests-pass": {"set": {"severity": "blocking"}}}})
    assert locks.conformance(layer) == locks.Conformance("conformant", (), ())


def test_lk_7_a_project_that_unlocks_an_entry_is_non_conformant_and_names_it():
    locks = _api()
    layer = _layer({"owner": "owner-1", "checks": {
        "tests-pass": {"unlock": True, "waiver": _waiver()},
        "no-secrets": {"unlock": True, "waiver": _waiver()}},
        "gates": {"G1": {"unlock": True, "waiver": _waiver()}}})
    found = locks.conformance(layer)
    assert found.status == "non-conformant"
    assert found.unlocked == ("checks.no-secrets", "checks.tests-pass", "gates.G1")
    assert found.refused == ()


def test_lk_7_a_refused_unlock_is_listed_with_its_reason_and_does_not_unlock():
    locks = _api()
    layer = _layer({"owner": "owner-1", "checks": {
        "tests-pass": {"unlock": True, "waiver": _waiver("alice")}}})
    found = locks.conformance(layer)
    assert found.status == "conformant" and found.unlocked == ()
    assert [entry for entry, _ in found.refused] == ["checks.tests-pass"]
    assert "only the owner owner-1" in found.refused[0][1]


def test_lk_7_a_hard_lock_makes_the_unlock_a_refusal_when_the_lock_set_is_known():
    locks = _api()
    layer = _layer({"owner": "owner-1", "gates": {"G5": {"unlock": True, "waiver": _waiver()}}})
    unknown = locks.conformance(layer)
    assert unknown.status == "non-conformant" and unknown.unlocked == ("gates.G5",)
    known = locks.conformance(layer, locks.lock_set(
        [_layer(_preset_doc(), "parent", "default")]))
    assert known.status == "conformant" and known.unlocked == ()
    assert "hard lock" in known.refused[0][1]


def test_lk_7_the_text_names_the_status_the_entries_and_each_refusal():
    locks = _api()
    non = locks.Conformance("non-conformant", ("checks.a", "gates.G1"), (("gates.G5", "a hard lock cannot be unlocked by anyone"),))
    lines = locks.conformance_text(non)
    assert lines[0].startswith("Conformance: non-conformant - this project unlocks")
    assert "checks.a, gates.G1" in lines[0]
    assert lines[1] == "Unlock refused for gates.G5: a hard lock cannot be unlocked by anyone"


def test_lk_7_a_conformant_project_with_nothing_refused_has_no_text():
    locks = _api()
    assert locks.conformance_text(locks.Conformance("conformant", (), ())) == []
    only = locks.Conformance("conformant", (), (("checks.a", "no owner"),))
    assert locks.conformance_text(only) == ["Unlock refused for checks.a: no owner"]


def test_lk_7_the_text_wraps_inside_the_width():
    locks = _api()
    many = tuple(f"checks.a-long-check-name-{i}" for i in range(12))
    lines = locks.conformance_text(locks.Conformance("non-conformant", many, ()), width=60)
    assert len(lines) > 2 and all(len(line) <= 60 for line in lines)
    assert all(line.startswith("  ") for line in lines[1:])
    assert all(name in " ".join(lines) for name in many)


# --- LK-8: check, the receipt and the summary report conformance -----------------

import json as _json
import subprocess
import textwrap

import yaml

CLI = ROOT / "cli" / "compass"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
MARKERS = ("Conformance:", "Unlock refused")

UNLOCK_FILE = textwrap.dedent("""\
    schema: 1
    owner: owner-1
    checks:
      suite-passed:
        unlock: true
        waiver: {reason: "The suite runs in another system.", approved_by: owner-1,
                 approved_on: 2026-10-01}
    """)


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    (root / ".compass").mkdir()
    started = _run(root, "quick-fix", "start", "greeting",
                   "--risk", "trivial - why", "--familiarity",
                   "brownfield-mapped - the file and its test exist",
                   "--size", "atomic - why", "--intent", "the greeting is right",
                   "--scenario", "Given the greeting, when read, then it says hello",
                   "--test", "tests/test_greeting.py")
    assert started.returncode == 0, started.stdout + started.stderr
    return root


COMMANDS = {"check": ("check",), "receipt": ("issue", "receipt"),
            "summary": ("approach", "summary")}


def _outputs(root):
    got = {}
    for name, args in COMMANDS.items():
        done = _run(root, *args)
        got[name] = (done.returncode, done.stdout)
    return got


def _without_conformance(text):
    """The lines that are not the report, with the blank line the receipt puts
    after it folded into the one before."""
    kept = [line for line in text.splitlines()
            if not any(mark in line for mark in MARKERS)]
    return [line for i, line in enumerate(kept) if line or not (i and not kept[i - 1])]


def test_lk_8_with_no_project_file_the_three_commands_print_no_conformance(project):
    for name, (code, out) in _outputs(project).items():
        assert not any(mark in out for mark in MARKERS), name


@pytest.mark.parametrize("content", [
    "checks: {}\n",                                           # not Compass's file: no schema
    "schema: 1\nowner: owner-1\n",                            # no unlock
    "schema: 1\nowner: owner-1\nchecks:\n  suite-passed:\n    set: {severity: blocking}\n",
    UNLOCK_FILE.replace("schema: 1\n", ""),                  # an unlock, but not Compass's file
], ids=["no-schema", "no-unlock", "a-change-with-no-unlock", "an-unlock-with-no-schema"])
def test_lk_8_a_project_file_that_unlocks_nothing_changes_nothing(project, content):
    before = _outputs(project)
    (project / "compass.yml").write_text(content)
    assert _outputs(project) == before


def test_lk_8_an_unlock_prints_the_line_on_every_run_of_the_three_commands(project):
    before = _outputs(project)
    (project / "compass.yml").write_text(UNLOCK_FILE)
    for _ in range(2):
        after = _outputs(project)
        for name in COMMANDS:
            code, out = after[name]
            assert code == before[name][0], name
            assert ("Conformance: non-conformant - this project unlocks framework "
                    "entries: checks.suite-passed") in out, name
            assert _without_conformance(out) == before[name][1].splitlines(), name


def test_lk_8_the_receipt_line_stays_inside_the_receipts_width_and_before_the_verdict(project):
    (project / "compass.yml").write_text(UNLOCK_FILE)
    lines = _run(project, "issue", "receipt").stdout.splitlines()
    assert max(len(line) for line in lines) <= 100
    assert lines[-1].startswith("Verdict:")
    assert any(line.startswith("Conformance:") for line in lines[:-2])


def test_lk_8_the_summary_prints_its_three_lines_and_then_the_conformance_line(project):
    (project / "compass.yml").write_text(UNLOCK_FILE)
    lines = _run(project, "approach", "summary").stdout.splitlines()
    assert lines[0].startswith("Approach:") and lines[1].startswith("Gates:")
    assert lines[2].startswith("Writes:") and lines[3].startswith("Conformance:")
    assert len(lines) == 4


def test_lk_8_check_lists_the_line_in_its_json_notices_and_on_a_spike(project):
    (project / "compass.yml").write_text(UNLOCK_FILE)
    document = _json.loads(_run(project, "check", "--json").stdout)
    assert any(n.startswith("Conformance: non-conformant") for n in document["notices"])
    manifest = project / ".compass" / "work" / "greeting" / "manifest.yml"
    body = yaml.safe_load(manifest.read_text())
    body["delivery_approach"] = "spike"
    manifest.write_text(yaml.safe_dump(body))
    spike = _run(project, "check")
    assert "Conformance: non-conformant" in spike.stdout, spike.stdout + spike.stderr


def test_lk_8_a_refused_unlock_is_reported_and_does_not_say_non_conformant(project):
    (project / "compass.yml").write_text(
        UNLOCK_FILE.replace("approved_by: owner-1", "approved_by: alice"))
    for name, (code, out) in _outputs(project).items():
        assert "Unlock refused for checks.suite-passed" in out, name
        assert "non-conformant" not in out, name


def test_lk_8_conformance_lines_never_raises_and_says_when_it_cannot_read(tmp_path):
    locks = _api()
    assert locks.conformance_lines(tmp_path) == []
    (tmp_path / "compass.yml").write_text("schema: 1\nschema: 2\n")
    lines = locks.conformance_lines(tmp_path)
    assert lines[0].startswith("Conformance: not checked")
    # The parser wraps a long temporary path across lines, so compare words.
    assert "duplicate key" in " ".join(" ".join(lines).split())
    (tmp_path / "compass.yml").write_text("- not a mapping\n")
    assert locks.conformance_lines(tmp_path) == []
    (tmp_path / "compass.yml").write_text(UNLOCK_FILE)
    assert locks.conformance_lines(tmp_path)[0].startswith("Conformance: non-conformant")


# --- LK-9: the repository around the module --------------------------------------

def _python_sources():
    for top in ("cli", "hooks", "scripts"):
        for path in sorted((ROOT / top).rglob("*")):
            parts = path.relative_to(ROOT).parts
            if path.is_file() and path.suffix in ("", ".py", ".sh") \
                    and "vendor" not in parts and "__pycache__" not in parts:
                try:
                    yield "/".join(parts), path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue


def test_lk_9_the_module_has_an_owning_doc_row_and_the_doc_describes_it():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    rows = [line for line in readme.splitlines() if "cli/compass_pkg/locks.py" in line]
    assert len(rows) == 1
    owner = rows[0].rsplit("`", 2)[-2]
    text = (ROOT / owner).read_text(encoding="utf-8")
    for word in ("unlock", "non-conformant", "locked: hard", "footprint"):
        assert word in text, f"{owner} does not mention {word}"


IMPORTS_LOCKS = re.compile(
    r"^\s*(from compass_pkg import [^\n]*\blocks\b|from compass_pkg\.locks import"
    r"|import compass_pkg\.locks)", re.M)


def test_lk_9_only_check_lint_the_receipt_and_the_summary_import_the_module():
    hits = [name for name, text in _python_sources()
            if name != "cli/compass_pkg/locks.py" and IMPORTS_LOCKS.search(text)]
    assert hits == ["cli/compass_pkg/check_cmd.py", "cli/compass_pkg/policy_lint.py",
                    "cli/compass_pkg/receipt.py", "cli/compass_pkg/routing.py"], hits


def test_lk_9_no_command_exposes_the_module_and_the_aggregate_does_not_name_it():
    assert "locks" not in (ROOT / "cli" / "compass_pkg" / "_all.py").read_text(encoding="utf-8")
    entry = (ROOT / "cli" / "compass").read_text(encoding="utf-8")
    assert "compass_pkg.locks" not in entry and "locks.enforce" not in entry


def test_lk_9_the_shipped_lock_set_is_written_once_in_the_preset_and_not_here():
    text = MODULE.read_text(encoding="utf-8")
    for literal in ("human-approval-present", "gates.G5", "spike.conclude",
                    "verify.correctness", "presets/default", "presets", "immovable_gates"):
        assert literal not in text, literal


def test_lk_9_core_stays_in_bounds_and_does_not_know_the_module():
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200
    assert "locks" not in core.replace("block", "").replace("unlock", "")


def test_lk_9_the_module_says_what_it_is_and_what_it_leaves_to_others():
    text = MODULE.read_text(encoding="utf-8")
    assert "stub" not in text.lower()
    top = text.split("from __future__", 1)[0]
    for word in ("ADR-039", "footprint", "waiver", "conformance"):
        assert word in top, word


def test_lk_4_a_stage_level_with_the_first_is_refused_and_named():
    def level(c):
        c["stages"]["intake"] = {"order": 1, "modes": {"full": {"rank": 3}}}
    result = _enforce_guard(level, early_exit=False)
    found = [r for r in result.refusals if r.field == "stages.order" and r.key == "intake"]
    assert [(r.parent, r.child) for r in found] == [("define first", "intake level with define")]
    before = _enforce_guard(_a_stage_before_the_first, early_exit=False)
    first = [r for r in before.refusals if r.key == "intake"]
    assert [(r.parent, r.child) for r in first] == [("define first", "intake before define")]


def test_lk_1_an_entry_a_layer_locks_and_unlocks_at_once_stays_locked():
    locks = _api()
    project = _layer({"owner": "owner-1", "checks": {
        "mine": {"locked": True, "unlock": True, "waiver": _waiver()}}})
    assert set(locks.lock_set([project])) == {"checks.mine"}


def test_lk_8_the_check_summary_shows_the_conformance_line_before_other_notices(tmp_path):
    """The summary shows three notices. Four earlier ones must not push the
    conformance line out of view."""
    import argparse
    import io
    from contextlib import redirect_stdout
    from compass_pkg import check_cmd
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "greeting"
    task_dir.mkdir(parents=True)
    (root / "compass.yml").write_text(UNLOCK_FILE)
    run = check_cmd._CheckRun(str(task_dir), {"delivery_approach": "quick-fix"}, "enforced")
    for number in range(4):
        run.line(f"  an earlier notice {number}")
    args = argparse.Namespace(json=False, no_count=True, evidence_out=None)
    out = io.StringIO()
    with redirect_stdout(out):
        check_cmd._emit_check(run, args)
    shown = out.getvalue().splitlines()
    assert any("Conformance: non-conformant" in line for line in shown), out.getvalue()
    where = [i for i, line in enumerate(shown) if "Conformance: non-conformant" in line]
    earlier = [i for i, line in enumerate(shown) if "earlier notice" in line]
    assert earlier and where[0] < earlier[0], out.getvalue()


# --- LK-5 (review): a change to a dimension's vocabulary ---------------------------

def _g5_gone(result):
    return {(r.entry, r.field) for r in result.refusals if r.entry.startswith("gates.G5")}


VOCABULARY_ROUTES = {
    "drop-a-risk-value": {"dimensions": {"risk": {"set": {"values": {"remove": ["critical"]}}}}},
    "rename-a-risk-value": {"dimensions": {"risk": {"set": {"values": {
        "add": ["severe"], "remove": ["critical"]}}}}},
    "close-the-label-list": {"dimensions": {"labels": {"set": {"open": False, "common": []}}}},
}


@pytest.mark.parametrize("name", sorted(VOCABULARY_ROUTES))
def test_lk_5_a_vocabulary_change_that_ends_a_locked_gate_is_refused(name):
    result = _enforce_preset(VOCABULARY_ROUTES[name])
    assert not result.ok
    assert any(r.entry == "gates.G5" and r.level == "hard" for r in result.refusals), \
        [(r.entry, r.field) for r in result.refusals]


@pytest.mark.parametrize("name", sorted(VOCABULARY_ROUTES))
def test_lk_5_an_owner_unlock_does_not_lift_the_hard_lock_on_a_vocabulary_change(name):
    project = dict(VOCABULARY_ROUTES[name], owner="owner-1", gates={"G5": {
        "unlock": True, "waiver": _waiver()}})
    result = _enforce_preset(project, early_exit=False)
    found = {(r.entry, r.field) for r in result.refusals}
    assert ("gates.G5", "unlock") in found
    assert any(entry == "gates.G5" and field != "unlock" for entry, field in found), found


def test_lk_5_a_vocabulary_change_no_locked_gate_depends_on_is_allowed():
    project = {"dimensions": {"familiarity": {"set": {"values": {"add": ["legacy-code"]}}}}}
    assert _enforce_preset(project).ok


# --- LK-4 (review): the rules of a locked rule set --------------------------------

def _also_listed(c):
    """Both approaches list the gate the locked rule adds, so the rule alone no
    longer decides whether the gate is in force."""
    c["approaches"]["regular"]["gates"].append("verify.security")


def _enforce_listed(edit):
    before = _guard_all()
    _also_listed(before)
    after = copy.deepcopy(before)
    edit(after)
    return _api().enforce(_held(*GUARDED), before, after, early_exit=False)


def test_lk_4_a_rule_removed_from_a_locked_set_is_refused_though_the_gate_is_listed_elsewhere():
    result = _enforce_listed(lambda c: c["rules"]["immovable_gates"]["rules"].pop("RULE-1"))
    assert ("rules.immovable_gates", "rules.immovable_gates.RULE-1") in {
        (r.entry, r.field) for r in result.refusals}


@pytest.mark.parametrize("field,value", [("kind", "advisory"), ("hit", {"gate": "first"})])
def test_lk_4_a_locked_sets_kind_or_hit_cannot_change(field, value):
    def edit(c):
        c["rules"]["immovable_gates"][field] = value
    result = _enforce_listed(edit)
    found = [r for r in result.refusals if r.field == f"rules.immovable_gates.{field}"]
    assert [(r.entry, r.outcome) for r in found] == [("rules.immovable_gates", "incomparable")]


def test_lk_4_a_rule_added_to_a_locked_set_is_allowed():
    def edit(c):
        c["rules"]["immovable_gates"]["rules"]["RULE-9"] = {
            "order": 9, "then": {"gate": "verify.correctness"}}
    assert _enforce_listed(edit).ok


# --- LK-6 and LK-7 (review): what an unlock needs, and what is reported -------------

def test_lk_6_a_reason_of_only_spaces_is_no_reason():
    locks = _api()
    layer = _unlock_layer(waiver=_waiver(reason="   "))
    found = locks.unlock_findings(layer)
    assert not found[0].ok and "no reason" in found[0].reason


def test_lk_6_an_issue_layers_locked_adds_no_lock():
    locks = _api()
    parent = _layer({"checks": {"a": {"locked": True}}}, "parent", "base")
    issue = _layer({"checks": {"b": {"locked": True}}}, "issue")
    assert set(locks.lock_set([parent, issue])) == {"checks.a"}


def _write_unlock(project, entry_block):
    (project / "compass.yml").write_text(
        "schema: 1\nowner: owner-1\n" + entry_block)


HARD_UNLOCK = textwrap.dedent("""\
    gates:
      G5:
        unlock: true
        waiver: {reason: "Needed.", approved_by: owner-1, approved_on: 2026-10-01}
    """)
MISSING_UNLOCK = HARD_UNLOCK.replace("gates:\n  G5:", "gates:\n  no-such-gate:")


@pytest.mark.parametrize("block,entry,words", [
    (HARD_UNLOCK, "gates.G5", "hard lock"),
    (MISSING_UNLOCK, "gates.no-such-gate", "not locked"),
], ids=["a-hard-lock", "an-entry-that-does-not-exist"])
def test_lk_7_the_commands_report_a_refused_unlock_not_a_non_conformant_project(
        project, block, entry, words):
    _write_unlock(project, block)
    for name, (code, out) in _outputs(project).items():
        assert f"Unlock refused for {entry}" in out and words in out, name
        assert "non-conformant" not in out, name


def test_lk_7_a_real_unlock_of_a_shipped_soft_lock_is_still_reported(project):
    (project / "compass.yml").write_text(UNLOCK_FILE)
    assert "non-conformant" in _run(project, "check").stdout


def test_lk_7_the_hard_set_is_read_from_the_preset_summary_not_written_in_the_module():
    from compass_pkg import legacy_views
    summary = legacy_views.preset_locks(str(ROOT))
    assert "gates.G5" in summary["hard"] and "stages.assess" in summary["locked"]


# --- LK-5 (review): what the refusal for the label cap and for a rejected configuration say

def _nine_labels():
    names = [f"label-{i}" for i in range(9)]
    return {"rules": {"floors": {"set": {"rules": {"set": {"F-MANY": {
        "order": 5, "when": {"labels_any": names},
        "then": {"force_minimum_approach": "regular"}}}}}}}}


def test_lk_5_the_label_cap_refusal_names_the_remedy_for_a_true_lock():
    parent = _parent_doc()
    del parent["checks"]["human-approval"]
    parent["gates"]["G1"]["checks"].remove("human-approval")
    result = _api().enforce_chain(_chain(_nine_labels(), parent))
    text = result.refusals[0].message
    assert "name no more than eight labels" in text.lower()
    assert "unlock" in text and "owner" in text


def test_lk_5_the_label_cap_refusal_for_a_hard_lock_names_no_unlock():
    parent = _parent_doc()
    parent["checks"]["tests-pass"]["locked"] = "hard"
    result = _api().enforce_chain(_chain(_nine_labels(), parent))
    text = result.refusals[0].message
    assert "name no more than eight labels" in text.lower()
    assert "unlock" not in text.lower() and "hard lock" in text


def test_lk_5_an_issue_below_a_nine_label_project_is_refused_too():
    layers = _chain(_nine_labels()) + [_layer({"autonomy": "controlled"}, "issue")]
    result = _api().enforce_chain(layers, early_exit=False)
    assert "issue" in {r.layer for r in result.refusals if r.field == "grid"}


def test_lk_5_a_rejected_configuration_says_an_unlock_cannot_help():
    project = {"approaches": {"regular": {"set": {"ships": False}}}}
    text = _api().enforce_chain(_chain(project)).refusals[0].message
    assert "An unlock cannot help" in text and "fix the configuration" in text


def test_lk_9_the_owning_doc_states_the_label_cap_the_unmapped_effects_and_the_approach_footprint():
    text = " ".join((ROOT / "governance" / "guardrails.md").read_text(encoding="utf-8").split())
    for part in ("across the whole layer", "fail-safe", "issue's `config:`",
                 "protects its `when` too", "its existence and its `ships` value",
                 "vocabulary", "A human signs off on the irreversible (`G5`)"):
        assert part in text, part
    section = text.split("## Locks and conformance", 1)[1]
    assert "(`G5`)" in section and section.index("signs off") < section.index("`G5` and")


def test_lk_9_the_header_names_every_private_classifier_name_the_module_uses():
    text = MODULE.read_text(encoding="utf-8")
    header = text.split("from __future__", 1)[0]
    used = sorted(set(re.findall(r"classify\.(_\w+)", text))
                  | set(re.findall(r"from compass_pkg\.classify import (_\w+)", text)))
    assert used, "the module uses no private name; drop this test"
    for name in used:
        assert name in header, name


def test_lk_5_a_child_that_refuses_an_assessment_the_parent_accepted_ends_the_locked_gate():
    before = _fixtures().with_spike(_before())
    before["approaches"]["spike"]["gates"] = ["verify.correctness"]
    del before["rules"]["floors"]["rules"]["F-1"]
    after = copy.deepcopy(before)
    after["rules"]["floors"]["rules"]["F-1"] = {
        "order": 1, "when": {"labels_any": ["auth"]},
        "then": {"force_minimum_approach": "full"}}
    result = _api().enforce(_held("gates.verify.correctness"), before, after,
                            early_exit=False)
    found = [r for r in result.refusals if r.field == "evaluation.refused"]
    assert [(r.entry, r.outcome) for r in found] == [("gates.verify.correctness", "looser")]
    assert "refused" in found[0].message


def test_lk_1_an_unlock_whose_waiver_is_dated_in_the_future_is_refused():
    locks = _api()
    parent = _layer({"checks": {"a": {"locked": True}}}, "parent", "base")
    future = _waiver()
    future["approved_on"] = "2999-01-01"
    project = _layer({"owner": "owner-1", "checks": {
        "a": {"unlock": True, "waiver": future}}})
    found = locks.unlock_findings(project, locks.lock_set([parent]))
    assert [f.ok for f in found] == [False]
    assert "later than today" in found[0].reason
    assert set(locks.lock_set([parent, project])) == {"checks.a"}
