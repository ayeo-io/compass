"""The lock check classifies only the facts a locked entry's footprint reads.

The first lock check counted every named label in the layer towards the cap of
eight, so a layer that named a ninth label in an advisory rule was refused even
when no locked entry could read it. The scan now keeps a label only where it
can reach a fact a lock protects. A projection is only safe if it gives the
refusals the full scan gives, so `scan="full"` stays as the reference and
these tests compare the two.

Scenario ids: `CS-4` to `CS-6` (issue `classifier-speed`).
"""
from __future__ import annotations

import copy
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

NINE = [f"label-{i}" for i in range(9)]


def _locks():
    from compass_pkg import locks
    return locks


def _fixtures():
    import classifier_fixtures
    return classifier_fixtures


def _held(*ids, hard=()):
    locks = _locks()
    held = {i: locks.Lock(True, "default") for i in ids}
    held.update({i: locks.Lock("hard", "default") for i in hard})
    return held


def _has_scan_mode():
    return "scan" in inspect.signature(_locks().enforce).parameters


def _enforce(held, before, after, scan=None, **kwargs):
    assert _has_scan_mode(), "locks.enforce has no `scan` argument"
    if scan is not None:
        kwargs["scan"] = scan
    return _locks().enforce(held, before, after, **kwargs)


# A configuration with two locked entries (the check `tests-pass` and the gate
# `verify.correctness`) and the unlocked ones around them.
LOCKED = ("checks.tests-pass", "gates.verify.correctness", "checks.solo",
          "gates.verify.solo")


def _before():
    """The base fixture plus a locked check and a locked gate that nothing lists
    and that list nothing, so their own conditions are the only way a label
    reaches them."""
    config = _fixtures().base()
    config["checks"]["solo"] = _fixtures().check()
    config["gates"]["verify.solo"] = {
        "kind": "guardrail", "stage": "verify", "applies_to": {"ships": True},
        "checks": [], "accepts": ["test-run"]}
    return config


def _advisory(names):
    return {"kind": "advisory", "hit": {}, "rules": {
        "A-1": {"order": 1, "when": {"labels_any": names},
                "then": {"strategy": "regression-baseline"}}}}


def _ceiling(names):
    return {"kind": "ceilings", "hit": {"limit": "min"}, "rules": {
        "C-1": {"order": 1, "when": {"labels_any": names},
                "then": {"ceiling": "run_cycles", "limit": 3}}}}


def _extra_check(names):
    return _fixtures().check(when={"labels_any": names})


def _extra_gate(names, checks=("no-secrets",)):
    return {"kind": "guardrail", "stage": "verify", "applies_to": {"ships": True},
            "checks": list(checks), "accepts": ["test-run"],
            "when": {"labels_any": names}}


def _a_rule_set_no_footprint_fact_reads(c, names=NINE):
    c["rules"]["advice"] = _advisory(names)


def _a_ceiling_rule_set(c, names=NINE):
    c["rules"]["limits"] = _ceiling(names)


def _an_unlocked_check_no_list_names(c, names=NINE):
    c["checks"]["extra"] = _extra_check(names)


def _an_unlocked_gate_that_holds_no_locked_check(c, names=NINE):
    c["gates"]["verify.extra"] = _extra_gate(names)


def _an_unlocked_check_only_an_unlocked_gate_lists(c, names=NINE):
    c["checks"]["extra"] = _extra_check(names)
    c["gates"]["verify.security"]["checks"] = ["no-secrets", "extra"]


def _a_floor_reads_nine_labels(c, names=NINE):
    c["rules"]["floors"]["rules"]["F-MANY"] = {
        "order": 9, "when": {"labels_any": names},
        "then": {"force_minimum_approach": "regular"}}


def _an_unlocked_check_a_locked_gate_lists(c, names=NINE):
    c["checks"]["extra"] = _extra_check(names)
    c["gates"]["verify.correctness"]["checks"] = ["tests-pass", "extra"]


def _an_unlocked_gate_that_holds_the_locked_check(c, names=NINE):
    c["gates"]["G1"]["when"] = {"labels_any": names}


def _the_locked_checks_own_when(c, names=NINE):
    c["checks"]["tests-pass"]["when"] = {"labels_any": names}


def _a_locked_check_nothing_lists(c, names=NINE):
    c["checks"]["solo"]["when"] = {"labels_any": names}


def _a_locked_gate_that_holds_no_check(c, names=NINE):
    c["gates"]["verify.solo"]["when"] = {"labels_any": names}


NOT_READ = {
    "an advisory rule set": _a_rule_set_no_footprint_fact_reads,
    "a ceiling rule set": _a_ceiling_rule_set,
    "an unlocked check no list names": _an_unlocked_check_no_list_names,
    "an unlocked gate that holds no locked check":
        _an_unlocked_gate_that_holds_no_locked_check,
    "an unlocked check only an unlocked gate lists":
        _an_unlocked_check_only_an_unlocked_gate_lists,
}

READ = {
    "a floor": _a_floor_reads_nine_labels,
    "an unlocked check a locked gate lists": _an_unlocked_check_a_locked_gate_lists,
    "an unlocked gate that holds the locked check":
        _an_unlocked_gate_that_holds_the_locked_check,
    "the locked check's own when": _the_locked_checks_own_when,
    "a locked check nothing lists": _a_locked_check_nothing_lists,
    "a locked gate that holds no check": _a_locked_gate_that_holds_no_check,
}


def _grid_refusals(result):
    return [r for r in result.refusals if r.field == "grid"]


# --- CS-4: only the label sites a footprint can read are counted ----------------------

@pytest.mark.parametrize("name", sorted(NOT_READ))
def test_cs_4_nine_labels_no_locked_entry_reads_are_not_counted(name):
    after = _before()
    NOT_READ[name](after)
    result = _enforce(_held(*LOCKED), _before(), after, early_exit=False)
    assert result.ok, [r.message for r in result.refusals]
    full = _enforce(_held(*LOCKED), _before(), after, scan="full", early_exit=False)
    assert _grid_refusals(full), "the full scan counts them, so only the count changed"


@pytest.mark.parametrize("name", sorted(READ))
def test_cs_4_nine_labels_a_locked_entry_can_read_are_still_refused(name):
    after = _before()
    READ[name](after)
    result = _enforce(_held(*LOCKED), _before(), after, early_exit=False)
    refusal = _grid_refusals(result)
    assert refusal, f"{name}: nine labels a locked entry reads were not refused"
    assert refusal[0].outcome == "incomparable"


def test_cs_4_a_label_a_footprint_cannot_read_adds_no_points():
    """Three labels in an advisory rule beside the one a floor reads: the
    footprint scan visits the points of one label, the full scan of four."""
    after = _before()
    after["rules"]["advice"] = _advisory(["x", "y", "z"])
    footprint = _enforce(_held(*LOCKED), _before(), after, early_exit=False)
    full = _enforce(_held(*LOCKED), _before(), after, scan="full", early_exit=False)
    assert footprint.ok and full.ok
    assert footprint.evaluated * 8 == full.evaluated > 0


def test_cs_4_the_scan_modes_are_footprint_and_full_and_nothing_else():
    from compass_pkg.core import CompassError
    assert _has_scan_mode(), "locks.enforce has no `scan` argument"
    with pytest.raises(CompassError, match="scan"):
        _locks().enforce(_held(*LOCKED), _before(), _before(), scan="sampled")
    with pytest.raises(CompassError, match="scan"):
        _locks().enforce_chain([], scan="sampled")
    assert inspect.signature(_locks().enforce).parameters["scan"].default == "footprint"
    assert inspect.signature(_locks().enforce_chain).parameters["scan"].default == "footprint"


def test_cs_4_a_label_in_the_issue_layer_is_read_by_the_same_rule():
    """The issue layer's own document is walked as the configurations are, so a
    rule it adds for a label no footprint reads is not counted either."""
    after = _before()
    after["rules"]["advice"] = _advisory(NINE)
    issue = {"rules": {"advice": {"kind": "advisory", "rules": {
        "A-1": {"order": 1, "when": {"labels_any": NINE},
                "then": {"strategy": "regression-baseline"}}}}}}
    result = _enforce(_held(*LOCKED), _before(), after, after_issue=issue,
                      early_exit=False)
    assert result.ok, [r.message for r in result.refusals]


# --- CS-6: the shipped policy, a ninth label and what the refusal says ------------------

def _preset_doc():
    import yaml
    from compass_pkg import catalogue_spec
    doc = {"schema": 1}
    directory = ROOT / "governance" / "presets" / "default"
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))
        doc[name] = part[name]
    return doc


def _chain(project):
    from compass_pkg.layers import Layer
    return [Layer("parent", "parent", _preset_doc(), "digest"),
            Layer("project", "project", {"schema": 1, **project}, "digest")]


ADVICE_NAMING_NINE = {"rules": {"advisory": {"set": {"rules": {"set": {"A-MANY": {
    "order": 90, "when": {"labels_any": NINE},
    "then": {"strategy": "regression-baseline"}}}}}}}}

FLOOR_NAMING_FIVE = {"rules": {"floors": {"set": {"rules": {"set": {"F-FIVE": {
    "order": 90, "when": {"labels_any": NINE[:5]},
    "then": {"force_minimum_approach": "regular"}}}}}}}}


def test_cs_6_the_shipped_policy_accepts_a_layer_with_nine_advisory_labels():
    assert "scan" in inspect.signature(_locks().enforce_chain).parameters
    result = _locks().enforce_chain(_chain(ADVICE_NAMING_NINE), early_exit=False)
    assert result.ok, [r.message for r in result.refusals]
    full =_locks().enforce_chain(_chain(ADVICE_NAMING_NINE), early_exit=False,
                                  scan="full")
    assert [r.field for r in full.refusals] == ["grid"]


def test_cs_6_the_shipped_policy_still_refuses_nine_labels_a_floor_reads():
    result = _locks().enforce_chain(_chain(FLOOR_NAMING_FIVE), early_exit=False)
    (refusal,) = [r for r in result.refusals if r.field == "grid"]
    text = refusal.message
    assert "9" in text and "label-0" in text and "auth" in text
    assert "name no more than eight labels" in text.lower()
    assert "hard lock" in text and "unlock" not in text.lower()   # the shipped set has one
    assert "locked entry" in text


def test_cs_6_with_only_true_locks_the_refusal_names_the_owner_approved_unlock():
    after = _before()
    _a_floor_reads_nine_labels(after)
    result = _enforce(_held(*LOCKED), _before(), after, early_exit=False)
    (refusal,) = _grid_refusals(result)
    assert "unlock" in refusal.message and "owner" in refusal.message
    assert "name no more than eight labels" in refusal.message.lower()


def test_cs_6_the_refusal_says_which_labels_are_counted_and_which_are_not():
    result = _locks().enforce_chain(_chain(FLOOR_NAMING_FIVE), early_exit=False)
    (refusal,) = [r for r in result.refusals if r.field == "grid"]
    text = " ".join(refusal.message.split())
    assert "only the labels a locked entry can read" in text
    assert "advisory" in text and "ceiling" in text


def test_cs_6_the_guardrails_doc_describes_the_footprint_scan():
    text = " ".join((ROOT / "governance" / "guardrails.md").read_text(
        encoding="utf-8").split())
    section = text.split("## Locks and conformance", 1)[1]
    for part in ("only the labels a locked entry can read",
                 "advisory, bias and ceiling rules",
                 "scan=\"full\"", "eight labels", "issue's `config:`"):
        assert part in section, part
    assert "until the footprint-only scan lands" not in section
    assert "counts labels across the whole layer" not in section


# --- CS-5: the footprint scan gives the full scan's refusals --------------------------

PROOF = {"compared": 0, "full_capped": 0, "differences": []}


def refusal_key(refusal):
    return (refusal.entry, refusal.level, refusal.field, refusal.key, refusal.outcome,
            repr(refusal.parent), repr(refusal.child), refusal.where, refusal.layer)


def compare_scans(call, **kwargs):
    """Run `call(scan=..., early_exit=False, **kwargs)` with the full scan and
    with the footprint scan and compare what each refuses. A case the full scan
    cannot run (more than eight labels in the layer) has nothing to compare, so
    it is counted apart. Returns the pair of results."""
    assert _has_scan_mode(), "locks.enforce has no `scan` argument"
    assert "scan" in inspect.signature(_locks().enforce_chain).parameters
    full = call(scan="full", early_exit=False, **kwargs)
    footprint = call(scan="footprint", early_exit=False, **kwargs)
    if _grid_refusals(full):
        PROOF["full_capped"] += 1
        return full, footprint
    PROOF["compared"] += 1
    a = sorted(refusal_key(r) for r in full.refusals)
    b = sorted(refusal_key(r) for r in footprint.refusals)
    if a != b:
        PROOF["differences"].append((a, b))
    return full, footprint


def test_cs_5_both_scans_agree_on_the_small_cases_written_here():
    cases = {**NOT_READ, **READ}
    before = PROOF["compared"]
    for name, edit in cases.items():
        after = _before()
        edit(after, NINE[:3])               # few enough labels for the full scan to run
        full, footprint = compare_scans(
            lambda **kw: _enforce(_held(*LOCKED), _before(), after, **kw))
        assert not _grid_refusals(full), name
    for edit in (_loosen_where_a_label_shows, lambda c: None):
        after = _before()
        edit(after)
        compare_scans(lambda **kw: _enforce(_held(*LOCKED), _before(), after, **kw))
    assert PROOF["compared"] - before == len(cases) + 2
    assert PROOF["differences"] == []


def _loosen_where_a_label_shows(c):
    """The parent's floor lifts `auth` work to `full`. The child drops it, and
    a gate that only `full` carries stops applying there: the loosening shows
    at the points that name `auth` and nowhere else."""
    del c["rules"]["floors"]["rules"]["F-1"]


def _auth_gate_before():
    config = _fixtures().base()
    config["gates"]["verify.security"]["checks"] = ["no-secrets"]
    return config


def test_cs_5_a_loosening_only_a_label_shows_is_found_by_both_scans():
    before = _auth_gate_before()
    after = copy.deepcopy(before)
    _loosen_where_a_label_shows(after)
    held = _held("gates.verify.security")
    full, footprint = compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert full.refusals and [r.where for r in full.refusals] == \
        [r.where for r in footprint.refusals]
    assert all("auth" in r.where for r in footprint.refusals)
    assert PROOF["differences"] == []


def test_cs_5_a_projection_that_drops_a_label_a_floor_reads_is_caught(monkeypatch):
    """The comparison has to be able to fail: with floors treated as sites no
    footprint reads, the loosening above is missed and the refusals differ."""
    locks = _locks()
    assert hasattr(locks, "IRRELEVANT_RULE_KINDS"), "locks.IRRELEVANT_RULE_KINDS is missing"
    monkeypatch.setattr(locks, "IRRELEVANT_RULE_KINDS",
                        (*locks.IRRELEVANT_RULE_KINDS, "floors"))
    before = _auth_gate_before()
    after = copy.deepcopy(before)
    _loosen_where_a_label_shows(after)
    held = _held("gates.verify.security")
    saved = list(PROOF["differences"])
    compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert len(PROOF["differences"]) == len(saved) + 1, "the wrong projection was not caught"
    PROOF["differences"][:] = saved


# Cases where a loosening shows only at the points that name one label. Each one
# needs a different part of the projection to keep that label, so each is a case
# a wrong projection would miss.

def _role_rule_gate_pair():
    """A role rule adds the locked gate `verify.security` where `x` is named. The
    child removes the rule."""
    before = _fixtures().base()
    before["rules"]["roles"] = {"kind": "role-rules", "rules": {
        "R-1": {"order": 1, "when": {"labels_any": ["x"]},
                "then": {"gate": "verify.security"}}}}
    after = copy.deepcopy(before)
    del after["rules"]["roles"]["rules"]["R-1"]
    return before, after, _held("gates.verify.security")


def _check_in_a_locked_gate_pair():
    """The unlocked check `extra` is active where `x` is named and sits in the
    locked gate. The child takes it off the gate."""
    before = _fixtures().base()
    before["checks"]["extra"] = _extra_check(["x"])
    before["gates"]["verify.correctness"]["checks"] = ["tests-pass", "extra"]
    after = copy.deepcopy(before)
    after["gates"]["verify.correctness"]["checks"] = ["tests-pass"]
    return before, after, _held("gates.verify.correctness")


def _gate_that_holds_a_locked_check_pair():
    """The unlocked gate `G1` is in force where `x` is named and holds the locked
    check. The child empties it."""
    before = _fixtures().base()
    before["gates"]["G1"]["when"] = {"labels_any": ["x"]}
    after = copy.deepcopy(before)
    after["gates"]["G1"]["checks"] = []
    return before, after, _held("checks.tests-pass")


LABEL_ONLY = {
    "a floor lifts the approach where a label is named": lambda: _floor_pair(),
    "a shape picks the approach where a label is named": lambda: _shape_pair(),
    "a cap names a label": lambda: _cap_pair(),
    "a role rule adds a locked gate where a label is named": _role_rule_gate_pair,
    "an unlocked check in a locked gate is active where a label is named":
        _check_in_a_locked_gate_pair,
    "an unlocked gate holding a locked check is in force where a label is named":
        _gate_that_holds_a_locked_check_pair,
}


@pytest.mark.parametrize("name", sorted(LABEL_ONLY))
def test_cs_5_a_loosening_only_one_label_shows_is_found_by_both_scans(name):
    before, after, held = LABEL_ONLY[name]()
    full, footprint = compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert full.refusals, "the case must loosen a locked entry"
    assert all(any(label in r.where.split("labels")[-1].replace(",", " ").split()
                   for label in ("x", "y", "auth")) for r in full.refusals), [
        r.where for r in full.refusals]
    assert [r.where for r in footprint.refusals] == [r.where for r in full.refusals]
    assert PROOF["differences"] == []


@pytest.mark.parametrize("kind", ["floors", "role-rules", "shapes", "caps"])
def test_cs_5_dropping_the_labels_of_a_rule_set_that_decides_the_route_is_caught(
        monkeypatch, kind):
    """The rule sets whose labels the projection must keep: each is proved by a
    case in which making that kind irrelevant changes a refusal."""
    locks = _locks()
    before, after, held = {
        "floors": _floor_pair, "role-rules": _role_rule_gate_pair,
        "shapes": _shape_pair, "caps": _cap_pair}[kind]()
    saved = list(PROOF["differences"])
    monkeypatch.setattr(locks, "IRRELEVANT_RULE_KINDS", (*locks.IRRELEVANT_RULE_KINDS, kind))
    compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert len(PROOF["differences"]) == len(saved) + 1, f"{kind} was dropped unseen"
    PROOF["differences"][:] = saved


def _floor_pair():
    before = _auth_gate_before()
    after = copy.deepcopy(before)
    _loosen_where_a_label_shows(after)
    return before, after, _held("gates.verify.security")


def _shape_pair():
    """A shape leans to `full` where `x` is named, and the child drops it."""
    before = _fixtures().base()
    before["rules"]["default_shapes"]["rules"]["S-X"] = {
        "order": 0, "when": {"labels_any": ["x"]}, "then": {"lean_toward": "full"}}
    after = copy.deepcopy(before)
    del after["rules"]["default_shapes"]["rules"]["S-X"]
    return before, after, _held("gates.verify.security")


def _cap_pair():
    """A cap forbids `full` where `x` is named, which makes the evaluator refuse
    work the floor sends there. The child drops the cap, so the parent's refusal
    ends: the locked gate stops applying nowhere, but the refusal itself is the
    difference the lock reads."""
    before = _fixtures().base()
    before["rules"]["caps"] = {"kind": "caps", "rules": {
        "C-X": {"order": 1, "when": {"labels_any": ["x"]},
                "then": {"forbid_approach": "regular"}}}}
    after = copy.deepcopy(before)
    after["rules"]["caps"]["rules"]["C-X"]["when"] = {"labels_any": ["y"]}
    return before, after, _held("gates.verify.correctness")


def _dotted_check_pair():
    """The locked check `tests-pass` and an unlocked check whose id starts with
    `tests-pass.` on a gate that is in force. The child changes the unlocked
    check's `blocking_when`. A check id may hold a dot, so a change to the
    unlocked check is not a change to the locked one."""
    before = _fixtures().base()
    before["checks"]["tests-pass.strict"] = _fixtures().check(
        blocking_when={"risk": ["critical"]})
    before["gates"]["G1"]["checks"] = ["tests-pass", "tests-pass.strict"]
    after = copy.deepcopy(before)
    after["checks"]["tests-pass.strict"]["blocking_when"] = {"risk": ["contained"]}
    return before, after, _held("checks.tests-pass")


def test_cs_5_a_change_to_an_unlocked_check_whose_id_extends_a_locked_one_is_allowed():
    before, after, held = _dotted_check_pair()
    full, footprint = compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert full.ok and footprint.ok, [r.message for r in full.refusals]
    assert PROOF["differences"] == []


def test_cs_5_a_parameter_of_a_locked_check_is_still_pinned_to_it():
    """The prefix rule stays for parameter keys, which are `check.parameter`."""
    before = _fixtures().base()
    before["checks"]["tests-pass"]["params"] = {"files": 5}
    after = copy.deepcopy(before)
    after["checks"]["tests-pass"]["params"] = {"files": 9}
    held = _held("checks.tests-pass")
    full, footprint = compare_scans(lambda **kw: _enforce(held, before, after, **kw))
    assert [(r.entry, r.field) for r in footprint.refusals] == [
        ("checks.tests-pass", "checks.params")]
    assert PROOF["differences"] == []


# The routes tried against the shipped policy: each is one layer (or
# a short chain) on the shipped default, and each has a refusal or none to give.

def _preset():
    return _preset_doc()


def _layer(doc, kind="project", name=None):
    from compass_pkg.layers import Layer
    doc = doc if kind == "issue" else {"schema": 1, **doc}
    return Layer(name or kind, kind, doc, "digest")


WAIVER = {"reason": "A recorded reason.", "approved_by": "owner-1", "approved_on": "2026-10-01"}


def _p(doc):
    return [_layer(doc, "project")]


def _issue(doc):
    return [_layer({}, "project"), _layer(doc, "issue")]


def _without_lock(entry):
    return {k: v for k, v in entry.items() if k != "locked"}


def _shipped_routes():
    preset = _preset()
    g1 = preset["gates"]["G1"]["checks"]
    sp = preset["checks"]["suite-passed"]
    routes = {
        "remove a gate": _p({"gates": {"G1": {"remove": True}}}),
        "remove a check and detach it": _p({
            "checks": {"suite-passed": {"remove": True}},
            "gates": {"G1": {"set": {"checks": {"remove": ["suite-passed"]}}}}}),
        "replace a check by a weaker one": _p({
            "checks": {"suite-passed": {"remove": True},
                       "suite-passed-2": {**_without_lock(sp), "severity": "advisory"}},
            "gates": {"G1": {"set": {"checks": [
                c if c != "suite-passed" else "suite-passed-2" for c in g1]}}}}),
        "move a check out of its gate": _p({
            "gates": {"G1": {"set": {"checks": {"remove": ["suite-passed"]}}},
                      "verify.regression": {"set": {"checks": {"add": ["suite-passed"]}}}}}),
        "skipped check passes": _p({"checks": {"suite-passed": {
            "set": {"on_skipped": "pass"}}}}),
        "severity advisory": _p({"checks": {"suite-passed": {
            "set": {"severity": "advisory"}}}}),
        "accepts widened": _p({"checks": {"suite-passed": {
            "set": {"accepts": ["test-run", "note"]}}}}),
        "reviewers on a hard-locked check": _p({"checks": {"human-approval-present": {
            "set": {"reviewers": ["anyone"]}}}}),
        "approvers on a hard-locked check": _p({"checks": {"human-approval-present": {
            "set": {"approvers": ["anyone"]}}}}),
        "check when narrowed": _p({"checks": {"suite-passed": {
            "set": {"when": {"risk": "critical"}}}}}),
        "check blocking when": _p({"checks": {"suite-passed": {
            "set": {"blocking_when": {"risk": ["critical"]}}}}}),
        "check requires a capability": _p({"checks": {"suite-passed": {
            "set": {"requires": ["artifact-freshness"]}}}}),
        "check implementation changed": _p({"checks": {"suite-passed": {
            "set": {"impl": "command-passes"}}}}),
        "gate kind changed": _p({"gates": {"G1": {"set": {"kind": "review"}}}}),
        "gate when narrowed": _p({"gates": {"G1": {"set": {"when": {"risk": "critical"}}}}}),
        "hard gate when narrowed": _p({"gates": {"G5": {
            "set": {"when": {"risk": "critical"}}}}}),
        "gate applies_to flipped": _p({"gates": {"G1": {
            "set": {"applies_to": {"ships": False}}}}}),
        "gate stage moved": _p({"gates": {"G4": {"set": {"stage": "ship"}}}}),
        "gate accepts widened": _p({"gates": {"G1": {"set": {"accepts": ["note"]}}}}),
        "stage verify after ship": _p({"stages": {"verify": {"set": {"order": 9}}}}),
        "stage before assess": _p({"stages": {"intake": {
            "order": 0, "modes": {"full": {"rank": 3}}}}}),
        "remove stage ship": _p({"stages": {"ship": {"remove": True}}}),
        "spike ships": _p({"approaches": {"spike": {"set": {"ships": True}}}}),
        "remove the spike approach": _p({"approaches": {"spike": {"remove": True}}}),
        "immovable rule removed": _p({"rules": {"immovable_gates": {
            "set": {"rules": {"remove": ["RP-GATE-001"]}}}}}),
        "immovable hit changed": _p({"rules": {"immovable_gates": {
            "set": {"hit": {"gate": "first"}}}}}),
        "immovable kind changed": _p({"rules": {"immovable_gates": {
            "set": {"kind": "advisory"}}}}),
        "immovable set removed": _p({"rules": {"immovable_gates": {"remove": True}}}),
        "conclude gate emptied": _p({"gates": {"spike.conclude": {"set": {"checks": []}}}}),
        "issue loosens a check": _issue({"checks": {"suite-passed": {
            "set": {"on_skipped": "pass"}}}}),
        "issue empties a gate": _issue({"gates": {"G1": {"set": {"checks": []}}}}),
        "approach drops a stage": _p({"approaches": {"regular": {"set": {
            "stages": {"remove": ["verify"]}}}}}),
        "spike drops its gate": _p({"approaches": {"spike": {"set": {"gates": []}}}}),
        "critical leans to spike": _p({"rules": {"default_shapes": {"set": {"rules": {"set": {
            "RP-SHAPE-000": {"order": 0, "when": {"risk": "critical"},
                             "then": {"lean_toward": "spike"}}}}}}}}),
        "every assessment leans to spike": _p({"rules": {"default_shapes": {"set": {
            "rules": {"set": {"RP-SHAPE-000": {
                "order": 0, "when": {}, "then": {"lean_toward": "spike"}}}}}}}}),
        "a risk value dropped": _p({"dimensions": {"risk": {"set": {"values": [
            "trivial", "contained", "cross-cutting"]}}}}),
        "the label list closed": _p({"dimensions": {"labels": {"set": {
            "open": False, "common": []}}}}),
        "an issue drops a risk value": _issue({"dimensions": {"risk": {"set": {"values": [
            "trivial", "contained", "cross-cutting"]}}}}),
        "an approach loses its gates": _p({"approaches": {"regular": {"set": {"gates": []}}}}),
        "a check only an advisory rule names": _p({
            "checks": {"extra": {"statement": "x", "kind": "deterministic",
                                 "impl": "suite-passed", "severity": "advisory",
                                 "on_skipped": "pass",
                                 "when": {"labels_any": ["a", "b", "c", "d", "e"]}}}}),
        "a floor on a new label": _p({"rules": {"floors": {"set": {"rules": {"set": {
            "F-NEW": {"order": 90, "when": {"labels_any": ["a", "b"]},
                      "then": {"force_minimum_approach": "regular"}}}}}}}}),
        "a rule set for labels nothing reads": _p(ADVICE_NAMING_NINE),
        "a floor for five new labels": _p(FLOOR_NAMING_FIVE),
        "nothing": _p({}),
    }
    routes["unlock with an owner waiver, then loosen"] = [
        _layer({"owner": "owner-1"}, "project"),
        _layer({"checks": {"suite-passed": {
            "unlock": True, "waiver": WAIVER, "set": {"on_skipped": "pass"}}}}, "issue")]
    routes["a parent unlocks"] = [_layer({"owner": "owner-1", "checks": {
        "suite-passed": {"unlock": True, "waiver": WAIVER,
                         "set": {"on_skipped": "pass"}}}}, "parent", "other-parent")]
    routes["the owner unlocks a soft lock and loosens it"] = _p({
        "owner": "owner-1", "checks": {"suite-passed": {
            "unlock": True, "waiver": WAIVER, "set": {"on_skipped": "pass"}}}})
    routes["the owner unlocks a hard lock"] = _p({
        "owner": "owner-1", "gates": {"G5": {
            "unlock": True, "waiver": WAIVER, "set": {"checks": []}}}})
    return routes


ROUTES = _shipped_routes()
ROUTE_OUTCOMES = {}


@pytest.mark.parametrize("name", sorted(ROUTES))
def test_cs_5_both_scans_agree_on_a_route_tried_against_the_shipped_policy(name):
    from compass_pkg.layers import Layer
    from compass_pkg.merge import MergeError
    chain = [Layer("parent", "parent", _preset_doc(), "digest"), *ROUTES[name]]
    cache = {}          # one cache for one case: the footprint scan reuses the full scan's
    try:
        full, footprint = compare_scans(
            lambda **kw: _locks().enforce_chain(chain, cache=cache, **kw))
    except MergeError:
        ROUTE_OUTCOMES[name] = "merge rejects it"      # no configuration to scan
        return
    ROUTE_OUTCOMES[name] = ("capped" if _grid_refusals(full)
                            else "refused" if full.refusals else "allowed")
    assert PROOF["differences"] == [], PROOF["differences"][:1]


def test_cs_5_the_routes_tried_cover_refusals_allowances_and_the_cap():
    """The counts are over every route test, so they are asserted only when this
    process ran them all (a parallel run spreads them over processes)."""
    from compass_pkg.layers import Layer
    from compass_pkg.merge import MergeError
    rejected = []
    for name, layers in ROUTES.items():
        try:
            from compass_pkg import merge
            config = {}
            for layer in [Layer("parent", "parent", _preset_doc(), "digest"), *layers]:
                config, _ = merge.apply(config, layer.doc, layer.kind, layer.name)
        except MergeError:
            rejected.append(name)
    assert len(ROUTES) >= 48 and len(rejected) <= 6, rejected
    if set(ROUTE_OUTCOMES) != set(ROUTES):
        pytest.skip("the route tests ran in other processes")
    seen = list(ROUTE_OUTCOMES.values())
    assert seen.count("refused") >= 30 and seen.count("allowed") >= 2, seen
    assert seen.count("capped") >= 3, seen
