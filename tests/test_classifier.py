"""The configuration classifier: compare two resolved configurations by what
each owes across the assessment grid (ADR-037).

Small configurations (`classifier_fixtures`) carry most tests so the full grid
can run beside the grouped one. A few tests classify the shipped preset.

Scenario ids: `CL-1` to `CL-7` (issue `classifier`).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

MODULE = ROOT / "cli" / "compass_pkg" / "classify.py"


# --- CL-7: the module's declarations ----------------------------------------------

def test_cl_7_the_module_declares_its_dependencies():
    assert MODULE.is_file(), "cli/compass_pkg/classify.py does not exist"
    text = MODULE.read_text(encoding="utf-8")
    header = text.split("from __future__", 1)[0]
    assert "# DEPENDENCY:" in header
    assert "compass_pkg.obligations" in header


# --- helpers ---------------------------------------------------------------------

def _api():
    from compass_pkg import classify
    return classify


def _base():
    import classifier_fixtures
    return classifier_fixtures.base()


def _labelled(config, *names):
    import classifier_fixtures
    return classifier_fixtures.with_labels(config, *names)


def _with_urgency(when):
    config = _base()
    config["dimensions"]["urgency"] = {"type": "enum", "values": ["normal", "live-defect"]}
    config["rules"]["floors"]["rules"]["F-U"] = {
        "order": 5, "when": when, "then": {"force_minimum_approach": "full"}}
    return config


@pytest.fixture(scope="module")
def preset_cache():
    return {}


def _classes(grid, name):
    return [c.values for dim, classes in grid.dimensions if dim == name
            for c in classes]


# --- CL-1: the grid ----------------------------------------------------------------

def test_cl_1_atoms_are_the_tests_of_a_condition():
    classify = _api()
    assert classify.atoms_of({"size": "large"}) == [("in", "size", ("large",))]
    assert classify.atoms_of({"risk": {"at_least": "critical"}}) == [
        ("at_least", "risk", "critical")]
    assert classify.atoms_of({"labels_any": ["b", "a"]}) == [
        ("labels_any", ("b", "a"))]
    nested = classify.atoms_of({"familiarity": "greenfield", "any_of": [
        {"size": ["small", "large"]}, {"labels_any": ["auth"]}]})
    assert nested == [("in", "familiarity", ("greenfield",)),
                      ("in", "size", ("small", "large")),
                      ("labels_any", ("auth",))]
    # An older key is read as the evaluator reads it.
    assert classify.atoms_of({"blast_radius": "critical"}) == [
        ("in", "risk", ("critical",))]


def test_cl_1_atoms_are_collected_from_every_place_a_condition_sits():
    classify = _api()
    config = _base()
    config["checks"]["tests-pass"]["when"] = {"risk": "critical"}
    config["checks"]["tests-pass"]["blocking_when"] = {"familiarity": "greenfield"}
    config["gates"]["G1"]["when"] = {"labels_any": ["payments"]}
    atoms = classify.collect_atoms(config)
    assert ("in", "risk", ("critical",)) in atoms
    assert ("in", "familiarity", ("greenfield",)) in atoms
    assert ("labels_any", ("payments",)) in atoms
    assert ("in", "size", ("large",)) in atoms          # a rule's `when`
    assert ("labels_any", ("auth",)) in atoms
    assert atoms == classify.collect_atoms(config)       # deterministic
    only_child = classify.collect_atoms(_base(), config)
    assert ("labels_any", ("payments",)) in only_child   # both are read


def test_cl_1_values_no_predicate_tells_apart_are_one_class():
    classify = _api()
    config = _base()
    grid = classify.build_grid(config, config)
    assert _classes(grid, "risk") == [("contained", "critical")]
    assert _classes(grid, "familiarity") == [("greenfield", "brownfield-unmapped")]
    assert _classes(grid, "size") == [("small",), ("large",)]
    assert grid.labels == ("auth",)
    assert grid.points == 1 * 1 * 2 * 2
    assert grid.raw_points == 2 * 2 * 2 * 2


def test_cl_1_the_exhaustive_grid_has_every_value_as_its_own_class():
    classify = _api()
    config = _base()
    grid = classify.build_grid(config, config, exhaustive=True)
    assert _classes(grid, "risk") == [("contained",), ("critical",)]
    assert grid.points == grid.raw_points == 16


def test_cl_1_a_value_only_the_child_has_and_a_predicate_reads_is_its_own_class():
    classify = _api()
    child = _base()
    child["dimensions"]["size"]["values"] = ["small", "large", "huge"]
    child["rules"]["default_shapes"]["rules"]["S-1"]["when"] = {
        "size": ["large", "huge"]}
    grid = classify.build_grid(_base(), child)
    assert _classes(grid, "size") == [("small",), ("large",), ("huge",)]
    kinds = {c.values: c.kind for dim, cs in grid.dimensions if dim == "size"
             for c in cs}
    assert kinds[("huge",)] == "one-side"
    assert kinds[("large",)] == "both" and kinds[("small",)] == "both"


def test_cl_1_a_value_only_one_side_has_and_no_predicate_reads_is_left_out():
    classify = _api()
    child = _base()
    child["dimensions"]["familiarity"]["values"].append("legacy")
    grid = classify.build_grid(_base(), child)
    assert _classes(grid, "familiarity") == [("greenfield", "brownfield-unmapped")]
    assert grid.raw_points == 2 * 3 * 2 * 2         # the raw count has it
    assert grid.points == 1 * 1 * 2 * 2


def test_cl_1_a_value_a_side_removed_is_read_the_same_way():
    classify = _api()
    child = _base()
    child["dimensions"]["familiarity"]["values"] = ["greenfield"]
    grid = classify.build_grid(_base(), child)
    assert _classes(grid, "familiarity") == [("greenfield",)]


def test_cl_1_an_at_least_atom_reads_each_sides_own_order():
    classify = _api()
    parent, child = _base(), _base()
    for config in (parent, child):
        config["checks"]["tests-pass"]["when"] = {"risk": {"at_least": "contained"}}
    child["dimensions"]["risk"]["values"] = ["critical", "contained"]  # reordered
    grid = classify.build_grid(parent, child)
    # Under the parent both values reach `contained`. Under the child `critical`
    # sits below it. Only the child's order tells the two apart.
    assert _classes(grid, "risk") == [("contained",), ("critical",)]


def test_cl_1_labels_are_the_names_a_predicate_reads_and_every_subset_is_a_point():
    classify = _api()
    config = _labelled(_base(), "payments", "ci")
    grid = classify.build_grid(config, config)
    assert grid.labels == ("auth", "ci", "payments")
    assert grid.label_subsets() == [
        (), ("auth",), ("ci",), ("payments",), ("auth", "ci"),
        ("auth", "payments"), ("ci", "payments"), ("auth", "ci", "payments")]
    assert grid.points == 1 * 1 * 2 * 8


def test_cl_1_eight_named_labels_are_a_grid_and_nine_are_not_sampled(monkeypatch):
    classify = _api()
    eight = _labelled(_base(), *[f"l{i}" for i in range(7)])   # plus `auth`
    grid = classify.build_grid(eight, eight)
    assert len(grid.labels) == 8 and grid.points == 2 * 256

    nine = _labelled(_base(), *[f"l{i}" for i in range(8)])
    from compass_pkg import obligations

    def refuse(*args, **kwargs):
        raise AssertionError("the cap must stop the scan before any evaluation")
    monkeypatch.setattr(obligations, "obligations", refuse)
    changed = _labelled(_base(), *[f"l{i}" for i in range(8)])
    changed["checks"]["tests-pass"]["severity"] = "advisory"
    got = classify.classify(nine, changed)
    assert got.result == "incomparable"
    assert "9" in got.reason and "eight" in got.reason
    assert got.grid.label_count == 9 and got.grid.points == 0
    # Both sides' labels count towards the cap.
    four = _labelled(_base(), "a", "b", "c")                    # four names
    other = _labelled(_base(), "d", "e", "f", "g", "h")         # six names
    both = classify.classify(four, other)
    assert both.result == "incomparable" and both.grid.label_count == 9


def test_cl_1_identical_configurations_are_equivalent_even_past_the_cap(monkeypatch):
    classify = _api()
    nine = _labelled(_base(), *[f"l{i}" for i in range(8)])
    got = classify.classify(nine, _labelled(_base(), *[f"l{i}" for i in range(8)]))
    assert got.result == "equivalent" and got.grid.evaluated == 0


def test_cl_1_the_shipped_policy_has_the_grid_the_decision_records():
    classify = _api()
    import classifier_fixtures
    config = classifier_fixtures.preset()
    grid = classify.build_grid(config, config)
    assert grid.labels == ("auth", "migrations", "payments", "personal-data")
    assert grid.closed_points == 288
    assert grid.points == 4608
    assert grid.raw_points == 51840          # 3,240 assessments with each optional one omitted too


# --- CL-2: points combine into a verdict -------------------------------------------

def _classify(parent, child, **kw):
    return _api().classify(parent, child, **kw)


def _gate_checks(config, gate, checks):
    config["gates"][gate]["checks"] = list(checks)
    return config


def test_cl_2_a_rule_that_changes_nothing_is_equivalent():
    # A new floor asks for at least `regular`; another rule already asks for
    # more wherever it matters, and nothing asks for less.
    child = _base()
    child["rules"]["floors"]["rules"]["F-2"] = {
        "order": 2, "when": {"risk": "critical"},
        "then": {"force_minimum_approach": "regular"}}
    got = _classify(_base(), child)
    assert got.result == "equivalent", got.reason
    assert got.counts["equal"] == got.grid.evaluated > 0
    assert got.counts["tighter"] == got.counts["looser"] == got.counts["mixed"] == 0


def test_cl_2_an_added_check_on_a_gate_is_tightening():
    child = _base()
    child["checks"]["extra"] = {**child["checks"]["tests-pass"]}
    _gate_checks(child, "verify.correctness", ["tests-pass", "extra"])
    got = _classify(_base(), child)
    assert got.result == "tightening", got.reason
    assert got.counts["looser"] == got.counts["mixed"] == 0 and got.counts["tighter"] > 0


def test_cl_2_a_check_taken_off_a_gate_is_loosening():
    child = _gate_checks(_base(), "verify.correctness", [])
    got = _classify(_base(), child)
    assert got.result == "loosening", got.reason
    assert got.counts["tighter"] == got.counts["mixed"] == 0 and got.counts["looser"] > 0


def test_cl_2_a_less_strict_point_and_a_stricter_one_are_incomparable():
    child = _gate_checks(_base(), "verify.correctness", [])
    child["checks"]["extra"] = {**child["checks"]["tests-pass"]}
    child["rules"]["floors"]["rules"]["F-1"]["when"] = {"labels_any": ["auth"]}
    child["gates"]["verify.security"]["checks"] = ["no-secrets", "extra"]
    got = _classify(_base(), child)
    # Large work owes one more check on the security gate and one fewer on the
    # correctness gate, whatever the set of checks, so no point is only one.
    assert got.result == "incomparable", got.reason
    assert got.first_mixed is not None


def test_cl_2_a_heavier_approach_that_owes_fewer_checks_is_incomparable():
    child = _base()
    child["gates"]["verify.audit"] = {"kind": "review", "checks": ["no-secrets"],
                                      "accepts": ["test-run"]}
    child["approaches"]["full"]["gates"] = ["verify.security", "verify.audit"]
    got = _classify(_base(), child)
    assert got.result == "incomparable", got.reason
    point = got.first_mixed
    # Where `full` is chosen: large work, or the label floor.
    assert point.assessment["size"] == "large" or "auth" in point.assessment["labels"]
    assert point.assessment["labels"] == [] or "auth" in point.assessment["labels"]
    fields = {change.field for change in point.changes}
    assert "approaches.gates" in fields


def _pair_only_shapes(first, second):
    config = _base()
    config["rules"]["floors"]["rules"].pop("F-1")
    shapes = config["rules"]["default_shapes"]["rules"]
    shapes.clear()
    shapes.update({
        first[0]: {"order": 1, "when": {"labels_any": [first[1]]},
                   "then": {"lean_toward": first[2]}},
        second[0]: {"order": 2, "when": {"labels_any": [second[1]]},
                    "then": {"lean_toward": second[2]}},
        "S-FALLBACK": {"order": 3, "when": {}, "then": {"lean_toward": "regular"}}})
    return _labelled(config, "ci")


def test_cl_2_a_loosening_that_only_two_labels_together_show_is_found():
    parent = _pair_only_shapes(("A", "payments", "full"), ("B", "auth", "regular"))
    child = _pair_only_shapes(("B", "auth", "regular"), ("A", "payments", "full"))
    got = _classify(parent, child)
    assert got.result == "loosening", got.reason
    assert got.first_looser.assessment["labels"] == ["auth", "payments"]
    # The three singles and the empty set are equal; two subsets hold both.
    assert got.counts["looser"] == 2 and got.counts["equal"] == 6
    # No sample of "each label alone and all together" could be sure of that.


def test_cl_2_two_identical_refusals_are_equal_and_a_new_refusal_is_not():
    import classifier_fixtures
    only = {"risk": "critical", "labels_any": ["auth"]}
    parent = classifier_fixtures.with_spike(_base(), only)
    # The same refusals on both sides, and one change elsewhere.
    child = classifier_fixtures.with_spike(
        _gate_checks(_base(), "verify.correctness", []), only)
    got = _classify(parent, child)
    assert got.result == "loosening", got.reason          # the refusals are equal
    assert got.counts["mixed"] == 0
    # The child no longer refuses where the parent does.
    # The same points refused for another reason is not the same outcome.
    renamed = classifier_fixtures.with_spike(_base(), only)
    renamed["rules"]["floors"]["rules"]["F-9"] = renamed["rules"]["floors"]["rules"].pop("F-1")
    got = _classify(parent, renamed)
    assert got.result == "incomparable", got.reason
    assert {c.field for c in got.first_mixed.changes} == {"evaluation.refused"}
    got = _classify(parent, _base())
    assert got.result == "incomparable", got.reason
    assert {c.field for c in got.first_mixed.changes} == {"evaluation.refused"}
    assert got.first_mixed.assessment["risk"] == "critical"
    assert got.first_mixed.assessment["labels"] == ["auth"]
    assert got.counts["mixed"] > 0 and got.counts["looser"] == got.counts["tighter"] == 0


# --- CL-3: each field compares by the kind the field table gives it -----------------

def _verdict(child, parent=None, **kw):
    return _classify(parent if parent is not None else _base(), child, **kw).result


def _edit(path_value_pairs, config=None):
    """A copy of the base with each `("a", "b", "c"), value` pair set."""
    config = config if config is not None else _base()
    for path, value in path_value_pairs:
        node = config
        for step in path[:-1]:
            node = node[step]
        node[path[-1]] = value
    return config


SEVERITY = ("checks", "tests-pass", "severity")
ON_SKIPPED = ("checks", "tests-pass", "on_skipped")


def test_cl_3_ordered_fields_compare_by_their_declared_order():
    assert _verdict(_edit([(SEVERITY, "advisory")])) == "loosening"
    assert _verdict(_edit([(SEVERITY, "blocking")]),
                    _edit([(SEVERITY, "advisory")])) == "tightening"
    assert _verdict(_edit([(ON_SKIPPED, "pass")])) == "loosening"
    assert _verdict(_edit([(ON_SKIPPED, "not-applicable")])) == "loosening"
    assert _verdict(_edit([(ON_SKIPPED, "fail")]),
                    _edit([(ON_SKIPPED, "pass")])) == "tightening"
    # A value outside the declared order cannot be placed.
    assert _verdict(_edit([(SEVERITY, "fatal")])) == "incomparable"


def test_cl_3_a_stage_mode_compares_by_rank_and_an_unranked_mode_is_incomparable():
    mode = lambda m: [(("approaches", "regular", "stages", "implement"), m)]
    assert _verdict(_edit(mode("light"))) == "loosening"
    assert _verdict(_edit(mode("full")), _edit(mode("light"))) == "tightening"
    assert _verdict(_edit(mode("reproduce-first"))) == "incomparable"
    assert _verdict(_edit(mode("full")), _edit(mode("reproduce-first"))) == "incomparable"
    assert _verdict(_edit(mode("reproduce-first")),
                    _edit(mode("reproduce-first"))) == "equivalent"
    # Two names that share a rank are not told apart by it.
    sibling = lambda m: _edit(mode(m), _edit(
        [(("stages", "implement", "modes", "thorough"), {"rank": 3})]))
    assert _verdict(sibling("thorough"), sibling("full")) == "incomparable"


def test_cl_3_a_stage_one_side_lacks_compares_by_existence():
    child = _base()
    del child["approaches"]["regular"]["stages"]["verify"]
    assert _verdict(child) == "loosening"
    assert _verdict(_base(), child) == "tightening"


def test_cl_3_artifacts_owed_are_a_set_and_their_depth_is_ordered():
    light = _edit([(("approaches", "regular", "artifacts"),
                    {"acceptance-criteria": "light"})])
    full = _edit([(("approaches", "regular", "artifacts"),
                   {"acceptance-criteria": "full"})])
    both = _edit([(("approaches", "regular", "artifacts"),
                   {"acceptance-criteria": "light", "technical-design": "light"})])
    assert _verdict(full, light) == "tightening"
    assert _verdict(light, full) == "loosening"
    assert _verdict(both, light) == "tightening"
    assert _verdict(light, both) == "loosening"
    assert _verdict(light, _base()) == "tightening"


def test_cl_3_a_way_set_is_stricter_when_it_is_smaller():
    accepts = ("checks", "tests-pass", "accepts")
    narrow = _edit([(accepts, ["test-run"])])
    wide = _edit([(accepts, ["test-run", "manual-review"])])
    assert _verdict(wide, narrow) == "loosening"          # a widened `accepts`
    assert _verdict(narrow, wide) == "tightening"
    assert _verdict(_edit([(accepts, ["claim-review"])]), narrow) == "incomparable"
    gate = ("gates", "verify.correctness", "accepts")
    assert _verdict(_edit([(gate, ["test-run", "artifact"])])) == "loosening"
    assert _verdict(_edit([(gate, [])])) == "tightening"


def test_cl_3_an_absent_reviewers_or_approvers_list_is_the_widest():
    for name in ("reviewers", "approvers"):
        path = ("checks", "tests-pass", name)
        listed = _edit([(path, ["lead"])])
        assert _verdict(_base(), listed) == "loosening", name
        assert _verdict(listed, _base()) == "tightening", name
        assert _verdict(_edit([(path, ["lead", "peer"])]), listed) == "loosening"
        assert _verdict(_edit([(path, ["peer"])]), listed) == "incomparable"


def test_cl_3_a_ceiling_the_table_gives_no_direction_is_incomparable_on_any_change():
    from compass_pkg import catalogue_spec
    for name in ("builder_attempts", "review_rounds", "replans", "repeated_error"):
        assert catalogue_spec.CEILING_DIRECTIONS[f"rules.ceilings.{name}"] == "none"
        assert _verdict(_ceiling_rule(3, name), _ceiling_rule(2, name)) == "incomparable"
        assert _verdict(_ceiling_rule(2, name), _ceiling_rule(3, name)) == "incomparable"
        assert _verdict(_ceiling_rule(3, name)) == "incomparable"
    one = _edit([(("approaches", "regular", "subtask_ceiling"), 1)])
    assert _verdict(one, directions={"approaches.subtask_ceiling": "none"}) == "incomparable"


def test_cl_3_a_ceiling_compares_in_the_direction_its_registry_declares():
    ceiling = ("approaches", "regular", "subtask_ceiling")
    lower, higher = _edit([(ceiling, 1)]), _edit([(ceiling, 3)])
    down = {"approaches.subtask_ceiling": "lower"}
    up = {"approaches.subtask_ceiling": "higher"}
    assert _verdict(lower, directions=down) == "tightening"
    assert _verdict(higher, directions=down) == "loosening"
    assert _verdict(lower, directions=up) == "loosening"
    assert _verdict(higher, directions=up) == "tightening"
    # No ceiling at all is the unbounded one.
    unbounded = _edit([(ceiling, None)])
    assert _verdict(unbounded, directions=down) == "loosening"
    assert _verdict(unbounded, directions=up) == "tightening"


def _ceiling_rule(limit, name="review_rounds"):
    config = _base()
    config["rules"]["caps"] = {"kind": "ceilings", "hit": {"limit": "min"}, "rules": {
        "C-1": {"order": 1, "when": {}, "then": {"ceiling": name, "limit": limit}}}}
    return config


def _worktree_cap(limit):
    config = _base()
    config["rules"]["worktree-caps"] = {
        "kind": "caps", "hit": {"max_worktrees": "min"}, "rules": {
            "W-1": {"order": 1, "when": {}, "then": {"max_worktrees": limit}}}}
    return config


def test_cl_3_a_loop_ceiling_compares_by_name():
    assert _verdict(_ceiling_rule(3)) == "incomparable"
    assert _verdict(_ceiling_rule(3), directions={"rules.ceilings": "lower"}) == "tightening"
    assert _verdict(_ceiling_rule(5), _ceiling_rule(3),
                    directions={"rules.ceilings.review_rounds": "lower"}) == "loosening"


def test_cl_3_a_check_parameter_is_a_ceiling_whose_direction_the_registry_declares():
    def with_params(**params):
        config = _base()
        config["checks"]["tests-pass"].update(impl="command-passes", params=params)
        return config
    assert _verdict(with_params(command="b"), with_params(command="a")) == "incomparable"
    assert _verdict(with_params(timeout_seconds=30),
                    with_params(timeout_seconds=60)) == "incomparable"   # `none`
    assert _verdict(with_params(timeout_seconds=30), with_params(timeout_seconds=60),
                    directions={"checks.params.command-passes.timeout_seconds": "lower"}
                    ) == "tightening"
    assert _verdict(with_params(timeout_seconds=30), with_params(timeout_seconds=60),
                    directions={"checks.params.command-passes.timeout_seconds": "higher"}
                    ) == "loosening"
    assert _verdict(with_params(timeout_seconds=60),
                    with_params(timeout_seconds=60)) == "equivalent"


def test_cl_3_kind_and_impl_never_compare_and_a_statement_counts_for_human_and_judged():
    assert _verdict(_edit([(("checks", "tests-pass", "impl"), "no-trusted-rerun")])
                    ) == "incomparable"
    assert _verdict(_edit([(("checks", "tests-pass", "kind"), "evidence")])
                    ) == "incomparable"
    text = ("checks", "tests-pass", "statement")
    assert _verdict(_edit([(text, "Another sentence.")])) == "equivalent"   # deterministic
    for kind in ("human", "judged"):
        parent = _edit([(("checks", "tests-pass", "kind"), kind)])
        child = _edit([(("checks", "tests-pass", "kind"), kind), (text, "Changed.")])
        assert _verdict(child, parent) == "incomparable", kind


def test_cl_3_a_check_that_keeps_its_id_compares_by_its_definition():
    child = _edit([(("checks", "tests-pass", "accepts"), ["test-run", "artifact"])])
    got = _classify(_base(), child)
    assert got.result == "loosening"
    assert {c.field for c in got.first_looser.changes} == {"checks.accepts"}
    assert got.first_looser.changes[0].key == "tests-pass"


def test_cl_3_a_delivery_approachs_weight_is_never_read():
    child = _edit([(("approaches", "regular", "weight"), 3),
                   (("approaches", "full", "weight"), 9)])
    assert _verdict(child) == "equivalent"


def test_cl_3_a_field_the_table_omits_is_not_compared_and_the_table_drives_the_rule(
        monkeypatch):
    from compass_pkg import catalogue_spec
    loosened = _edit([(SEVERITY, "advisory")])
    monkeypatch.setitem(catalogue_spec.OBLIGATION_FIELDS, "checks.severity", "identity")
    assert _verdict(_edit([(SEVERITY, "blocking")]), loosened) == "incomparable"
    monkeypatch.delitem(catalogue_spec.OBLIGATION_FIELDS, "checks.severity")
    assert _verdict(loosened) == "equivalent"


def test_cl_3_every_field_the_classifier_emits_is_a_key_of_the_table():
    from compass_pkg import catalogue_spec
    child = _edit([(SEVERITY, "advisory"), (ON_SKIPPED, "pass"),
                   (("approaches", "regular", "stages", "implement"), "light"),
                   (("approaches", "regular", "subtask_ceiling"), 1),
                   (("checks", "tests-pass", "accepts"), ["x"])])
    got = _classify(_base(), child)
    fields = {c.field for c in got.first_mixed.changes}
    assert fields and fields <= set(catalogue_spec.OBLIGATION_FIELDS)
    # The one that is not a field of the table is the two named by the design.
    assert _api().NO_FIELD == ("evaluation.refused", "dimensions.values")


def test_cl_3_adding_a_plan_exit_check_to_the_shipped_preset_is_tightening(preset_cache):
    import classifier_fixtures
    parent = classifier_fixtures.preset()
    child = classifier_fixtures.layer(parent, {
        "checks": {"docs-read": {"statement": "x", "kind": "deterministic",
                                 "impl": "suite-passed", "severity": "blocking",
                                 "on_skipped": "fail"}},
        "stages": {"plan": {"set": {"exit": ["docs-read"]}}}})
    got = _classify(parent, child, cache=preset_cache)
    assert got.result == "tightening", got.reason
    assert got.grid.points == 4608 and got.grid.evaluated == 4608
    # A second run against the same parent reads the parent's scan.
    assert len([k for k in preset_cache]) >= 4608


# --- CL-4: the first difference, and early exit ------------------------------------

def _widened_gate():
    return _edit([(("gates", "verify.correctness", "accepts"),
                   ["test-run", "artifact"])])


def test_cl_4_the_first_looser_point_names_its_field_parent_value_and_new_value():
    got = _classify(_base(), _widened_gate())
    point = got.first_looser
    assert point.outcome == "looser"
    change = point.changes[0]
    assert (change.fact, change.field, change.key) == (
        "gate_accepts", "gates.accepts", "verify.correctness")
    assert change.parent == ("test-run",)
    assert change.child == ("artifact", "test-run")
    assert change.outcome == "looser"
    assert "gates.accepts" in point.summary and "verify.correctness" in point.summary
    assert '["test-run"]' in point.summary and '["artifact", "test-run"]' in point.summary
    assert got.reason == point.summary


def test_cl_4_the_first_point_is_the_first_in_catalogue_order_and_says_what_it_stands_for():
    point = _classify(_base(), _widened_gate()).first_looser
    assert list(point.assessment) == ["risk", "familiarity", "size", "labels"]
    assert point.assessment == {"risk": "contained", "familiarity": "greenfield",
                                "size": "small", "labels": []}
    assert point.represents == {"risk": ["contained", "critical"],
                                "familiarity": ["greenfield", "brownfield-unmapped"],
                                "size": ["small"]}


def test_cl_4_the_output_reports_the_counts_of_points():
    got = _classify(_base(), _widened_gate())
    assert got.grid.points == 4 and got.grid.raw_points == 16
    assert got.grid.evaluated == 4 and got.complete is True
    assert sum(got.counts.values()) == 4


def _split():
    """Looser at small work (the regular approach owes nothing) and stricter at
    large work (the full approach owes one more gate), never both at a point."""
    child = _base()
    child["approaches"]["regular"]["gates"] = []
    child["gates"]["verify.audit"] = {"kind": "review", "checks": ["no-secrets"],
                                      "accepts": ["test-run"]}
    child["approaches"]["full"]["gates"].append("verify.audit")
    child["rules"]["floors"]["rules"].pop("F-1")
    parent = _base()
    parent["rules"]["floors"]["rules"].pop("F-1")
    # A label no rule uses to change what is owed gives the grid four points.
    return _labelled(parent, "ci"), _labelled(child, "ci")


def test_cl_4_an_incomparable_verdict_names_a_looser_point_and_a_stricter_one():
    parent, child = _split()
    got = _classify(parent, child)
    assert got.result == "incomparable"
    assert got.first_mixed is None
    assert got.first_looser.assessment["size"] == "small"
    assert got.first_tighter.assessment["size"] == "large"
    assert got.first_looser.summary in got.reason
    assert got.first_tighter.summary in got.reason


def test_cl_4_early_exit_stops_when_the_verdict_is_final_and_says_so():
    parent, child = _split()
    full = _classify(parent, child)
    quick = _classify(parent, child, early_exit=True)
    assert quick.result == full.result == "incomparable"
    assert quick.complete is False and quick.grid.evaluated < quick.grid.points
    assert quick.first_looser == full.first_looser
    assert quick.first_tighter == full.first_tighter
    assert full.complete is True and full.grid.evaluated == full.grid.points


def test_cl_4_early_exit_stops_at_the_first_mixed_point():
    got = _classify(_base(), _edit([(("checks", "tests-pass", "impl"), "no-trusted-rerun")]),
                    early_exit=True)
    assert got.result == "incomparable" and got.grid.evaluated == 1
    assert got.complete is False


def test_cl_4_early_exit_does_not_stop_while_the_verdict_could_still_change():
    got = _classify(_base(), _widened_gate(), early_exit=True)
    assert got.result == "loosening" and got.complete is True
    assert got.grid.evaluated == got.grid.points


def test_cl_4_the_same_input_gives_the_same_report():
    parent, child = _split()
    first, second = _classify(parent, child), _classify(parent, child)
    assert first == second


def test_cl_4_a_shared_cache_serves_the_parents_scan_to_every_child(monkeypatch):
    from compass_pkg import obligations
    calls = []
    real = obligations.obligations
    monkeypatch.setattr(obligations, "obligations",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    cache = {}
    first = _classify(_base(), _widened_gate(), cache=cache)
    assert len(calls) == 2 * first.grid.evaluated
    calls.clear()
    other = _classify(_base(), _edit([(SEVERITY, "advisory")]), cache=cache)
    assert len(calls) == other.grid.evaluated          # only the new child's points


# --- CL-5: the grouped grid is exact, and the atoms cover every read ----------------

def _pairs():
    """Every classifier fixture: pairs of configurations with the keyword
    arguments to classify them under."""
    import classifier_fixtures
    pairs = {}

    def add(name, parent, child, **kw):
        pairs[name] = (parent, child, kw)

    noop = _base()
    noop["rules"]["floors"]["rules"]["F-2"] = {
        "order": 2, "when": {"risk": "critical"},
        "then": {"force_minimum_approach": "regular"}}
    add("no-effect", _base(), noop)
    extra = _base()
    extra["checks"]["extra"] = {**extra["checks"]["tests-pass"]}
    _gate_checks(extra, "verify.correctness", ["tests-pass", "extra"])
    add("tightening", _base(), extra)
    add("loosening", _base(), _gate_checks(_base(), "verify.correctness", []))
    add("widened-accepts", _base(), _widened_gate())
    add("impl-change", _base(), _edit([(("checks", "tests-pass", "impl"),
                                        "no-trusted-rerun")]))
    parent, child = _split()
    add("split", parent, child)
    audit = _base()
    audit["gates"]["verify.audit"] = {"kind": "review", "checks": ["no-secrets"],
                                      "accepts": ["test-run"]}
    audit["approaches"]["full"]["gates"] = ["verify.security", "verify.audit"]
    add("heavier-owes-fewer", _base(), audit)
    add("two-labels", _pair_only_shapes(("A", "payments", "full"), ("B", "auth", "regular")),
        _pair_only_shapes(("B", "auth", "regular"), ("A", "payments", "full")))
    only = {"risk": "critical", "labels_any": ["auth"]}
    add("refusal-both", classifier_fixtures.with_spike(_base(), only),
        classifier_fixtures.with_spike(_gate_checks(_base(), "verify.correctness", []), only))
    add("refusal-one", classifier_fixtures.with_spike(_base(), only), _base())
    huge = _base()
    huge["dimensions"]["size"]["values"] = ["small", "large", "huge"]
    huge["rules"]["default_shapes"]["rules"]["S-1"]["when"] = {"size": ["large", "huge"]}
    add("union-read", _base(), huge)
    unread = _base()
    unread["dimensions"]["familiarity"]["values"].append("legacy")
    add("union-unread", _base(), unread)
    shorter = _base()
    shorter["dimensions"]["familiarity"]["values"] = ["greenfield"]
    add("union-removed", _base(), shorter)
    for config in (_base(), _base()):
        config["checks"]["tests-pass"]["when"] = {"risk": {"at_least": "critical"}}
    reordered_p, reordered_c = _base(), _base()
    for config in (reordered_p, reordered_c):
        config["checks"]["tests-pass"]["when"] = {"risk": {"at_least": "critical"}}
    reordered_c["dimensions"]["risk"]["values"] = ["critical", "contained"]
    add("reordered", reordered_p, reordered_c)
    missing = _base()
    del missing["approaches"]["regular"]["stages"]["verify"]
    add("stage-removed", _base(), missing)
    add("severity", _base(), _edit([(SEVERITY, "advisory")]))
    add("capability", _base(), _base(),
        child_capabilities=("entry-exit-evaluation",))
    required = _base()
    required["checks"]["needs"] = {**required["checks"]["tests-pass"],
                                   "requires": ["entry-exit-evaluation"]}
    required["stages"]["verify"]["entry"] = ["needs"]
    add("capability-on", required, required, child_capabilities=("entry-exit-evaluation",))
    predicates = _base()
    predicates["checks"]["tests-pass"]["when"] = {"any_of": [
        {"risk": "critical"}, {"labels_any": ["ci"]}]}
    predicates["checks"]["tests-pass"]["blocking_when"] = {"familiarity": "greenfield"}
    add("predicates", predicates, _edit([(SEVERITY, "advisory")], copy.deepcopy(predicates)))
    add("absent-optional", _with_urgency({}),
        _with_urgency({"urgency": ["normal", "live-defect"]}))
    add("absent-read", _with_urgency({"urgency": "live-defect"}),
        _with_urgency({"urgency": ["live-defect", "normal"]}))
    add("labels-three", _labelled(_base(), "payments", "ci"),
        _labelled(_gate_checks(_base(), "verify.correctness", []), "payments", "ci"))
    return pairs


def _signature(point):
    return None if point is None else (
        tuple(point.assessment.items()), point.outcome, point.changes, point.summary)


@pytest.mark.parametrize("name", sorted(_pairs()))
def test_cl_5_the_grouped_grid_gives_the_full_grids_verdict_and_first_differences(name):
    parent, child, kw = _pairs()[name]
    grouped = _classify(parent, child, **kw)
    full = _classify(parent, child, exhaustive=True, **kw)
    assert full.exhaustive is True and grouped.exhaustive is False
    assert grouped.result == full.result, name
    for slot in ("first_looser", "first_tighter", "first_mixed"):
        assert _signature(getattr(grouped, slot)) == _signature(getattr(full, slot)), \
            (name, slot)
    assert grouped.grid.points <= full.grid.points <= grouped.grid.raw_points
    # Each outcome exists in the grouped scan exactly where it exists in the full.
    for outcome, count in full.counts.items():
        assert (count > 0) == (grouped.counts[outcome] > 0), (name, outcome)


def test_cl_5_the_fixtures_cover_every_verdict_and_both_grids_differ_in_size():
    verdicts = {_classify(p, c, **kw).result for p, c, kw in _pairs().values()}
    assert verdicts == {"equivalent", "tightening", "loosening", "incomparable"}
    parent, child, kw = _pairs()["labels-three"]
    assert (_classify(parent, child).grid.points
            < _classify(parent, child, exhaustive=True).grid.points)


def _reference_atoms(when):
    """The atoms of a condition, read again without the classifier's code, so a
    fault in `atoms_of` cannot hide in both sides of the comparison."""
    out = []
    for key, val in (when or {}).items():
        if key == "any_of":
            for clause in val:
                out.extend(_reference_atoms(clause))
        elif key == "labels_any":
            out.append(("labels_any", tuple(val)))
        elif isinstance(val, dict):
            out.append(("at_least", key, val["at_least"]))
        else:
            out.append(("in", key, tuple(val if isinstance(val, list) else [val])))
    return out


class _ReadLog(dict):
    """An assessment that records the keys read from it."""
    reads = []

    def get(self, key, default=None):
        _ReadLog.reads.append(key)
        return super().get(key, default)

    def __getitem__(self, key):
        _ReadLog.reads.append(key)
        return super().__getitem__(key)

    def __contains__(self, key):
        _ReadLog.reads.append(key)
        return super().__contains__(key)


@pytest.mark.parametrize("name", sorted(_pairs()))
def test_cl_5_every_condition_the_evaluator_reads_is_covered_by_the_atoms(
        name, monkeypatch):
    from compass_pkg import obligations, routing
    classify = _api()
    parent, child, kw = _pairs()[name]
    covered = set(classify.collect_atoms(parent, child))
    keys = {atom[1] for atom in covered if atom[0] != "labels_any"} | {"labels"}
    keys |= {dim for config in (parent, child) for dim in config["dimensions"]}
    # The vocabulary check asks for these six names whether or not a
    # configuration declares them; a name nobody declares is never in a point.
    keys |= {"risk", "familiarity", "size", "goal", "urgency", "role"}
    seen = []
    real = obligations.reading_matches

    def recording(when, assessment, orders=None):
        seen.append(when)
        return real(when, assessment, orders)

    monkeypatch.setattr(obligations, "reading_matches", recording)
    monkeypatch.setattr(routing, "reading_matches", recording)
    real_obligations = obligations.obligations

    def logged(config, assessment, **kwargs):
        return real_obligations(config, _ReadLog(assessment), **kwargs)

    monkeypatch.setattr(obligations, "obligations", logged)
    _ReadLog.reads.clear()
    _classify(parent, child, exhaustive=True, **kw)
    assert seen, "the evaluator read no condition"
    for when in seen:
        missing = [atom for atom in _reference_atoms(when) if atom not in covered]
        assert missing == [], (name, when, missing)
    assert set(_ReadLog.reads) <= keys, set(_ReadLog.reads) - keys


# --- CL-6: the verdict is complete, stable JSON -------------------------------------

import json  # noqa: E402

TOP_KEYS = ["schema", "result", "reason", "scan", "parent", "child", "exhaustive",
            "complete", "grid", "counts", "first_looser", "first_tighter", "first_mixed"]
GRID_KEYS = ["labels", "label_count", "label_cap", "points", "raw_points", "evaluated"]
COUNT_KEYS = ["equal", "tighter", "looser", "mixed"]
POINT_KEYS = ["assessment", "represents", "outcome", "summary", "changes"]
CHANGE_KEYS = ["fact", "field", "key", "outcome", "parent", "child"]
EXAMPLE = ROOT / "tests" / "fixtures" / "classifier-json-example.json"


def _documents():
    """The JSON of every fixture, and of the cap and identical shortcuts."""
    docs = {name: _classify(p, c, **kw).to_json() for name, (p, c, kw) in _pairs().items()}
    nine = _labelled(_base(), *[f"l{i}" for i in range(8)])
    other = _labelled(_base(), *[f"l{i}" for i in range(8)])
    other["checks"]["tests-pass"]["severity"] = "advisory"
    docs["cap"] = _classify(nine, other).to_json()
    docs["identical"] = _classify(_base(), _base()).to_json()
    return docs


def test_cl_6_every_verdict_has_every_field_in_the_same_order():
    for name, doc in _documents().items():
        assert list(doc) == TOP_KEYS, name
        assert list(doc["grid"]) == GRID_KEYS, name
        assert list(doc["counts"]) == COUNT_KEYS, name
        for slot in ("first_looser", "first_tighter", "first_mixed"):
            point = doc[slot]
            if point is None:
                continue
            assert list(point) == POINT_KEYS, (name, slot)
            for change in point["changes"]:
                assert list(change) == CHANGE_KEYS, (name, slot)


def test_cl_6_the_four_verdicts_and_their_points_are_all_present_in_the_fixtures():
    docs = _documents().values()
    assert {d["result"] for d in docs} == {"equivalent", "tightening", "loosening",
                                           "incomparable"}
    for slot in ("first_looser", "first_tighter", "first_mixed"):
        assert any(d[slot] is not None for d in docs), slot
        assert any(d[slot] is None for d in docs), slot
    assert all(d["exhaustive"] is False for d in docs)


def test_cl_6_the_document_is_plain_json_and_the_same_every_time():
    for name, doc in _documents().items():
        assert json.loads(json.dumps(doc)) == doc, name
        assert json.dumps(_documents()[name]) == json.dumps(doc), name


def test_cl_6_the_cap_and_a_shortcut_still_carry_every_field():
    docs = _documents()
    cap = docs["cap"]
    assert cap["result"] == "incomparable" and cap["grid"]["label_count"] == 9
    assert cap["grid"]["points"] == cap["grid"]["raw_points"] == cap["grid"]["evaluated"] == 0
    assert cap["grid"]["label_cap"] == 8 and len(cap["grid"]["labels"]) == 9
    assert cap["counts"] == dict.fromkeys(COUNT_KEYS, 0)
    assert docs["identical"]["result"] == "equivalent"
    assert docs["identical"]["grid"]["evaluated"] == 0


def test_cl_6_the_shape_is_pinned_by_a_documented_example():
    got = _classify(_base(), _widened_gate(), parent_name="default@6",
                    child_name="project").to_json()
    want = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert got == want
    # The order of the keys is part of the shape.
    assert json.dumps(got) == json.dumps(want)
    assert _api().JSON_SCHEMA_VERSION == want["schema"] == 1


def test_cl_6_a_change_to_the_shape_fails_the_pin():
    classify = _api()
    doc = _classify(_base(), _widened_gate()).to_json()
    assert classify.json_shape_errors(doc) == []
    broken = dict(doc)
    del broken["first_mixed"]
    assert classify.json_shape_errors(broken)
    renamed = {("verdict" if k == "result" else k): v for k, v in doc.items()}
    assert classify.json_shape_errors(renamed)
    retyped = dict(doc, complete="yes")
    assert classify.json_shape_errors(retyped)
    bad_enum = dict(doc, result="looser")
    assert classify.json_shape_errors(bad_enum)
    deeper = json.loads(json.dumps(doc))
    deeper["first_looser"]["changes"][0].pop("key")
    assert classify.json_shape_errors(deeper)
    for name, good in _documents().items():
        assert classify.json_shape_errors(good) == [], name


# --- CL-7: the benchmark, the declarations and the docs -----------------------------

BENCH = ROOT / "scripts" / "bench-classifier.py"


def _bench():
    import importlib.util
    assert BENCH.is_file(), "scripts/bench-classifier.py does not exist"
    spec = importlib.util.spec_from_file_location("bench_classifier", BENCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cl_7_the_benchmark_builds_the_pair_at_each_label_count():
    bench = _bench()
    assert tuple(bench.DEFAULT_LABELS) == (4, 8)
    classify = _api()
    for count in (4, 8):
        parent, child = bench.pair(count)
        assert len(classify.build_grid(parent, child).labels) == count
        assert parent != child                # a real scan, never the shortcut


def test_cl_7_the_benchmark_times_a_grouped_and_a_full_scan_and_prints_numbers():
    bench = _bench()
    grouped = bench.measure(_base(), _labelled(_base(), "ci"), exhaustive=False)
    full = bench.measure(_base(), _labelled(_base(), "ci"), exhaustive=True)
    assert grouped["mode"] == "grouped" and full["mode"] == "full"
    assert grouped["points"] < full["points"]
    assert grouped["evaluations"] == 2 * grouped["points"]
    assert grouped["seconds"] > 0 and full["seconds"] > 0
    line = bench.format_row(grouped)
    assert "grouped" in line and f"{grouped['points']:,}" in line and "s" in line


def test_cl_7_only_the_classifier_and_the_replay_import_the_obligations_module():
    import re
    pattern = re.compile(r"^\s*(from compass_pkg(\.obligations)? import .*|"
                         r"import compass_pkg\.obligations)", re.M)
    users = []
    for path in sorted((ROOT / "cli").rglob("*.py")):
        if path.name == "obligations.py" or "vendor" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if any("obligations" in m.group(0) for m in pattern.finditer(text)):
            users.append(path.name)
    # Amended 2026-10-07 (ADR-037): `effective` may import it too.
    assert users == ["classify.py", "effective.py"]


def test_cl_7_the_entry_script_and_the_aggregate_do_not_name_the_classifier():
    for name in ("cli/compass", "cli/compass_pkg/_all.py"):
        assert "classify" not in (ROOT / name).read_text(encoding="utf-8"), name
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200


def test_cl_7_the_doc_describes_what_exists_and_its_example_is_possible():
    import re
    text = (ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8")
    assert "in the CLI" not in text and "`--exhaustive`" not in text
    assert "argument" in text and "`exhaustive=True`" in text
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    assert blocks, "routing-policy.md has no JSON example of the classification"
    for block in blocks:
        doc = json.loads(block)
        assert _api().json_shape_errors(doc) == []
        assert (doc["result"] == "loosening") == (doc["counts"]["looser"] > 0
                                                  and doc["first_looser"] is not None
                                                  and doc["counts"]["tighter"] == 0)
        assert doc["grid"]["evaluated"] == sum(doc["counts"].values())
    assert "no direction unless" not in text
    assert "CEILING_DIRECTIONS" in text


def test_cl_7_the_classifier_reads_no_private_name_of_another_module():
    import ast
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module.startswith("compass_pkg"):
            private = [a.name for a in node.names if a.name.startswith("_")]
            assert private == [], (node.module, private)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "obligations":
            assert not node.attr.startswith("_"), node.attr


def test_cl_7_adr_037_records_where_a_ceiling_declares_its_direction():
    text = (ROOT / "architecture" / "decisions"
            / "ADR-037-configuration-changes-are-classified-by-effect.md").read_text(
        encoding="utf-8")
    assert "## Amendment" in text and "CEILING_DIRECTIONS" in text
    assert "maintainer" in text.split("## Amendment", 1)[1]
    assert "as its registry entry declares" not in text


def test_cl_7_the_owning_doc_names_the_module_the_benchmark_and_the_json():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    rows = [line for line in readme.splitlines()
            if line.startswith("|") and "cli/compass_pkg/classify.py" in line]
    assert len(rows) == 1, "docs/README.md needs one owning-doc row for classify.py"
    assert "scripts/bench-classifier.py" in rows[0]
    owner = rows[0].split("|")[2].strip().strip("`")
    assert (ROOT / owner).is_file(), owner
    text = (ROOT / owner).read_text(encoding="utf-8")
    for word in ("cli/compass_pkg/classify.py", "Classification.to_json()",
                 "tests/fixtures/classifier-json-example.json", "first_looser",
                 "schema", "scripts/bench-classifier.py", "tightening", "loosening",
                 "scan", "early-exit", "parent_name"):
        assert word in text, f"{owner} does not mention {word}"


# --- CL-1: an optional dimension may be left out of an assessment -------------------

def test_cl_1_an_assessment_that_omits_an_optional_dimension_is_a_point():
    # The parent forces `full` for every assessment. The child forces it only
    # when urgency is given, so the two differ where urgency is omitted.
    parent = _with_urgency({})
    child = _with_urgency({"urgency": ["normal", "live-defect"]})
    for exhaustive in (False, True):
        got = _classify(parent, child, exhaustive=exhaustive)
        assert got.result != "equivalent", exhaustive
        assert got.result == "loosening", got.reason
        assert "urgency" not in got.first_looser.assessment
        assert got.first_looser.represents["urgency"] == [None]


def test_cl_1_a_required_dimension_has_no_absent_class_and_the_unread_class_takes_it():
    classify = _api()
    config = _with_urgency({"urgency": "live-defect"})
    grid = classify.build_grid(config, config)
    # `normal` is read by no predicate, so omitting urgency behaves as it does.
    assert _classes(grid, "urgency") == [("normal", None), ("live-defect",)]
    assert None not in sum(_classes(grid, "risk"), ())
    exhaustive = classify.build_grid(config, config, exhaustive=True)
    assert _classes(exhaustive, "urgency") == [("normal",), ("live-defect",), (None,)]
    assert grid.raw_points == exhaustive.raw_points == 2 * 2 * 2 * 3 * 2


# --- CL-3: the ceilings whose direction the field table declares ---------------------

def test_cl_3_the_subtask_ceiling_is_stricter_when_lower_and_no_ceiling_is_the_loosest():
    ceiling = ("approaches", "regular", "subtask_ceiling")
    at = lambda n: _edit([(ceiling, n)])
    assert _verdict(at(1), at(2)) == "tightening"
    assert _verdict(at(2), at(1)) == "loosening"
    assert _verdict(at(None), at(1)) == "loosening"
    assert _verdict(at(1), at(None)) == "tightening"
    assert _verdict(at(2), at(None)) == "tightening"


def test_cl_3_the_worktree_cap_is_stricter_when_lower():
    assert _verdict(_worktree_cap(1), _worktree_cap(2)) == "tightening"
    assert _verdict(_worktree_cap(2), _worktree_cap(1)) == "loosening"
    assert _verdict(_base(), _worktree_cap(1)) == "loosening"      # no cap is loosest


def test_cl_3_the_budget_ceilings_are_stricter_when_lower():
    for name in ("run_cost_usd", "run_minutes", "run_cycles"):
        assert _verdict(_ceiling_rule(10, name), _ceiling_rule(5, name)) == "loosening"
        assert _verdict(_ceiling_rule(5, name), _ceiling_rule(10, name)) == "tightening"
        assert _verdict(_base(), _ceiling_rule(5, name)) == "loosening", name   # removed
        assert _verdict(_ceiling_rule(5, name), _base()) == "tightening", name


def test_cl_3_every_shipped_ceiling_has_an_entry_and_every_entry_names_one():
    from compass_pkg import catalogue_spec, loop_ceilings
    table = catalogue_spec.CEILING_DIRECTIONS
    assert set(table.values()) <= {"higher", "lower", "none"}
    for name in loop_ceilings.CEILINGS:
        assert f"rules.ceilings.{name}" in table, name
    named = {k for k in table if k.startswith("rules.ceilings.")}
    assert named == {f"rules.ceilings.{n}" for n in loop_ceilings.CEILINGS}
    others = set(table) - named
    assert others == {"approaches.subtask_ceiling", "evaluation.max_worktrees"}
    for key in others:
        assert catalogue_spec.OBLIGATION_FIELDS[key] == "ceiling"
    assert catalogue_spec.OBLIGATION_FIELDS["rules.ceilings"] == "ceiling"


def test_cl_3_a_flipped_direction_in_the_table_changes_the_verdict(monkeypatch):
    from compass_pkg import catalogue_spec
    child, parent = _worktree_cap(1), _worktree_cap(2)
    assert _verdict(child, parent) == "tightening"
    # The cap also lowers the subtask ceiling, so both entries are flipped.
    for key in ("evaluation.max_worktrees", "approaches.subtask_ceiling"):
        monkeypatch.setitem(catalogue_spec.CEILING_DIRECTIONS, key, "higher")
    assert _verdict(child, parent) == "loosening"
    monkeypatch.setitem(catalogue_spec.CEILING_DIRECTIONS, "evaluation.max_worktrees",
                        "lower")
    assert _verdict(child, parent) == "incomparable"      # one flipped entry shows


def test_cl_3_a_ceiling_outside_the_table_is_incomparable_on_any_change(monkeypatch):
    from compass_pkg import catalogue_spec
    monkeypatch.delitem(catalogue_spec.CEILING_DIRECTIONS, "rules.ceilings.run_cost_usd")
    assert _verdict(_ceiling_rule(5, "run_cost_usd"),
                    _ceiling_rule(10, "run_cost_usd")) == "incomparable"


def test_cl_3_the_callers_directions_override_the_table():
    child, parent = _worktree_cap(1), _worktree_cap(2)
    both = {"evaluation.max_worktrees": "higher", "approaches.subtask_ceiling": "higher"}
    assert _verdict(child, parent, directions=both) == "loosening"
    assert _verdict(_ceiling_rule(3), _ceiling_rule(2),
                    directions={"rules.ceilings": "higher"}) == "tightening"


def _with_stage(config, mode="light"):
    config["stages"]["breakdown"] = {
        "order": 4, "modes": {"skipped": {"rank": 0}, "light": {"rank": 2}}}
    config["approaches"]["regular"]["stages"]["breakdown"] = mode
    return config


def test_cl_3_adding_a_stage_reads_tighter_and_removing_one_looser_even_when_skipped():
    for mode in ("light", "skipped"):
        added = _with_stage(_base(), mode)
        assert _verdict(added) == "tightening", mode
        assert _verdict(_base(), added) == "loosening", mode   # a recorded side effect


def test_cl_3_reordering_an_unlocked_stage_and_moving_a_gate_read_equivalent_here():
    # `stages.order` and `gates.stage` are the footprint of a lock; the locks
    # compare them. No fact the classifier reads changes with either.
    reordered = _base()
    reordered["stages"]["define"]["order"], reordered["stages"]["verify"]["order"] = 3, 1
    assert _verdict(reordered) == "equivalent"
    moved = _edit([(("gates", "G1", "stage"), "define")])
    assert _verdict(moved) == "equivalent"


def test_cl_3_a_check_renamed_with_an_identical_definition_is_incomparable():
    child = _base()
    child["checks"]["tests-pass-renamed"] = child["checks"].pop("tests-pass")
    for gate in child["gates"].values():
        gate["checks"] = ["tests-pass-renamed" if c == "tests-pass" else c
                          for c in gate["checks"]]
    got = _classify(_base(), child)
    assert got.result == "incomparable", got.reason
    assert {c.field for c in got.first_mixed.changes} == {"gates.checks"}


def test_cl_3_the_only_change_fields_outside_the_table_are_the_two_named():
    from compass_pkg import catalogue_spec
    classify = _api()
    assert classify.NO_FIELD == ("evaluation.refused", "dimensions.values")
    assert not set(classify.NO_FIELD) & set(catalogue_spec.OBLIGATION_FIELDS)
    seen = set()
    for p, c, kw in _pairs().values():
        got = _classify(p, c, **kw)
        for slot in (got.first_looser, got.first_tighter, got.first_mixed):
            seen |= {ch.field for ch in (slot.changes if slot else ())}
    assert seen - set(catalogue_spec.OBLIGATION_FIELDS) == set(classify.NO_FIELD)
    # `dimensions.values` appears only where a predicate reads a value one side lacks.
    huge = _base()
    huge["dimensions"]["size"]["values"] = ["small", "large", "huge"]
    huge["rules"]["default_shapes"]["rules"]["S-1"]["when"] = {"size": ["large", "huge"]}
    got = _classify(_base(), huge)
    assert {ch.field for ch in got.first_mixed.changes} == {"dimensions.values"}


# --- CL-6: what was compared, how it was scanned, and determinism ---------------------

def test_cl_6_the_document_says_how_it_was_scanned():
    parent, child = _split()
    scans = {
        "full": _classify(parent, child),
        "early-exit": _classify(parent, child, early_exit=True),
        "identical": _classify(_base(), _base()),
        "cap": _classify(_labelled(_base(), *[f"l{i}" for i in range(8)]),
                         _labelled(_gate_checks(_base(), "verify.correctness", []),
                                   *[f"l{i}" for i in range(8)])),
    }
    for scan, got in scans.items():
        assert got.to_json()["scan"] == scan
    assert scans["early-exit"].to_json()["complete"] is False
    assert scans["full"].to_json()["complete"] is True
    # Early exit that never gets the chance to stop is a full scan.
    assert _classify(_base(), _widened_gate(), early_exit=True).to_json()["scan"] == "full"
    assert _classify(_base(), _widened_gate(), exhaustive=True).to_json()["scan"] == "full"


def test_cl_6_the_caller_names_what_was_compared_and_the_default_is_null():
    doc = _classify(_base(), _widened_gate()).to_json()
    assert doc["parent"] is None and doc["child"] is None
    named = _classify(_base(), _widened_gate(), parent_name="default@6",
                      child_name="project").to_json()
    assert named["parent"] == "default@6" and named["child"] == "project"
    assert {k: v for k, v in named.items() if k not in ("parent", "child")} == \
        {k: v for k, v in doc.items() if k not in ("parent", "child")}


def test_cl_6_a_set_valued_change_is_a_sorted_list_whatever_the_hash_seed():
    child = _edit([(("approaches", "regular", "artifacts"),
                    {"technical-design": "light", "acceptance-criteria": "light",
                     "distribution-map": "light"})])
    doc = _classify(_base(), child).to_json()
    change = doc["first_tighter"]["changes"][0]
    assert (change["field"], change["parent"], change["child"]) == (
        "approaches.artifacts", [],
        ["acceptance-criteria", "distribution-map", "technical-design"])


_SEED_SCRIPT = """
import json, sys
sys.path.insert(0, {cli!r}); sys.path.insert(0, {tests!r})
import compass_pkg
import classifier_fixtures as fx
from compass_pkg import classify
base = fx.base()
child = fx.base()
child["approaches"]["regular"]["artifacts"] = {{
    "technical-design": "light", "acceptance-criteria": "light",
    "distribution-map": "light"}}
child["gates"]["verify.correctness"]["accepts"] = ["test-run", "artifact", "manual-review"]
sys.stdout.write(json.dumps(classify.classify(base, child).to_json()))
"""


def test_cl_6_the_json_is_the_same_bytes_under_different_hash_seeds():
    import os
    import subprocess
    script = _SEED_SCRIPT.format(cli=str(ROOT / "cli"), tests=str(ROOT / "tests"))
    outputs = {}
    for seed in ("0", "1", "12345", "99"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONDONTWRITEBYTECODE="1")
        done = subprocess.run([sys.executable, "-c", script], env=env,
                              capture_output=True, text=True, check=True)
        outputs[seed] = done.stdout
    assert len(set(outputs.values())) == 1, outputs.keys()
    assert json.loads(next(iter(outputs.values())))["result"] == "incomparable"


def test_cl_6_the_summary_names_the_looser_change_not_the_first_one():
    child = _base()
    child["gates"]["verify.audit"] = {"kind": "review", "checks": ["no-secrets"],
                                      "accepts": ["test-run"]}
    child["approaches"]["regular"]["gates"].append("verify.audit")      # tighter
    child["checks"]["tests-pass"]["severity"] = "advisory"              # looser, later
    got = _classify(_base(), child)
    point = got.first_mixed
    assert [c.outcome for c in point.changes][0] == "tighter"
    assert "checks.severity" in point.summary and "approaches.gates" not in point.summary
    assert "checks.severity" in got.reason


def test_cl_6_the_tightening_reason_is_pinned():
    extra = _base()
    extra["checks"]["extra"] = {**extra["checks"]["tests-pass"]}
    _gate_checks(extra, "verify.correctness", ["tests-pass", "extra"])
    got = _classify(_base(), extra)
    assert got.result == "tightening"
    assert got.reason == "4 of 4 points owe more and none owe less"
    assert _classify(_base(), _base(), parent_name="a").reason == \
        "the configurations are identical"
