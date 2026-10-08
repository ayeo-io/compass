"""The classifier meets its speed targets without changing a verdict (issue `classifier-speed`).

A speed change sits in a guard: a wrong "equivalent" lets a loosening through.
So these tests hold the measures to counters, not clocks. A wall-clock bound
fails when the machine is busy and passes when it is not, so it cannot tell a
slow scan from a busy computer. The targets are read from the benchmark's own
output (`scripts/bench-classifier.py`, wall-clock and CPU seconds), which the
issue records as command-output evidence.

Scenario ids: `CS-1` to `CS-3` and `CS-7` (issue `classifier-speed`).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))


def _fixtures():
    import classifier_fixtures
    return classifier_fixtures


ASSESSMENT = {"risk": "cross-cutting", "familiarity": "brownfield-mapped",
              "size": "medium", "goal": "delivery", "role": "engineer",
              "labels": ["auth"]}


@pytest.fixture(scope="module")
def policy():
    from compass_pkg import obligations
    return obligations.policy_adapter(_fixtures().preset())


# --- CS-1: the evaluator does not copy the policy ----------------------------------

class _CopyLog:
    """Every top-level `copy.deepcopy` call and the length of what it copied.
    The copier calls itself for each part, so only the outermost call counts."""

    def __init__(self, monkeypatch):
        self.sizes = []
        self.depth = 0
        real = copy.deepcopy

        def counting(value, memo=None, *rest):
            if self.depth == 0:
                self.sizes.append(len(repr(value)))
            self.depth += 1
            try:
                return real(value, memo, *rest)
            finally:
                self.depth -= 1

        monkeypatch.setattr(copy, "deepcopy", counting)


def test_cs_1_routing_an_assessment_copies_nothing_the_size_of_the_policy(
        monkeypatch, policy):
    from compass_pkg.routing import evaluate_route
    log = _CopyLog(monkeypatch)
    evaluate_route(copy.deepcopy(ASSESSMENT), policy, autonomy="balanced")
    log.sizes.pop(0)                      # the assessment copy this test made
    assert len(repr(policy)) > 5000, "the policy is the shipped one"
    assert max(log.sizes, default=0) < 1000, (
        f"the evaluator deep-copied {max(log.sizes)} characters; "
        f"the policy is {len(repr(policy))}")


def test_cs_1_one_obligations_call_copies_only_what_it_changes(monkeypatch):
    from compass_pkg import obligations
    config = _fixtures().preset()
    log = _CopyLog(monkeypatch)
    got = obligations.obligations(config, copy.deepcopy(ASSESSMENT))
    log.sizes.pop(0)
    assert not isinstance(got, obligations.Refused)
    assert max(log.sizes, default=0) < 1000, log.sizes[-3:]


def _old_names(policy):
    """The same policy as a project would have copied it before the routes were
    renamed: `regular` is `standard`, `full` is `expedition`, and the shapes,
    floors and checkpoints say so."""
    out = copy.deepcopy(policy)
    rename = {"regular": "standard", "full": "expedition", "quick-fix": "express"}
    out["route_shapes"] = {rename.get(k, k): v for k, v in out["route_shapes"].items()}
    strategies = out["routing_strategies"]
    for shape in strategies["default_shapes"]:
        shape["lean_toward"] = rename.get(shape["lean_toward"], shape["lean_toward"])
    if "default_route" in strategies:
        strategies["default_route"] = rename.get(strategies["default_route"],
                                                  strategies["default_route"])
    for group in out["routing_guardrails"].values():
        for rule in group:
            for key in ("force_minimum_route", "forbid_route"):
                if key in rule:
                    rule[key] = rename.get(rule[key], rule[key])
    table = out.get("autonomy_checkpoints") or {}
    out["autonomy_checkpoints"] = {
        level: {rename.get(k, k): v for k, v in row.items()}
        for level, row in table.items()}
    return out


def test_cs_1_the_policy_the_evaluator_is_given_is_left_as_it_was(policy):
    from compass_pkg.routing import evaluate_route
    old = _old_names(policy)
    assert old != policy, "the old spelling must differ, or this proves nothing"
    before = copy.deepcopy(old)
    got = evaluate_route(copy.deepcopy(ASSESSMENT), old, autonomy="balanced")
    assert old == before
    assert got["renamed_routes"], "the old names were read as the current ones"


def test_cs_1_old_route_names_give_the_result_the_current_names_give(policy):
    """The result of an older policy is the current one's, except for the list
    of names it renamed."""
    from compass_pkg.routing import canonical_routes, evaluate_route
    old = _old_names(policy)
    routes = set()
    for labels in ([], ["auth"], ["migrations"], ["auth", "payments"]):
        for risk in ("trivial", "contained", "cross-cutting", "critical"):
            for size in ("atomic", "small", "medium", "large"):
                for autonomy in ("controlled", "balanced", "autonomous"):
                    assessment = {**ASSESSMENT, "risk": risk, "size": size,
                                  "labels": labels}
                    a = evaluate_route(copy.deepcopy(assessment), old, autonomy=autonomy)
                    b = evaluate_route(copy.deepcopy(assessment),
                                       canonical_routes(old)[0], autonomy=autonomy)
                    routes.add(a["candidate_via"])
                    a.pop("renamed_routes"), b.pop("renamed_routes")
                    assert a == b, (labels, risk, size, autonomy)
    assert any("no shape matched" in via for via in routes), (
        "some assessment must fall to the default route, which is renamed too")


def test_cs_1_two_names_for_one_route_are_still_refused(policy):
    from compass_pkg.core import CompassError
    from compass_pkg.routing import evaluate_route
    bad = copy.deepcopy(policy)
    bad["route_shapes"]["standard"] = copy.deepcopy(bad["route_shapes"]["regular"])
    with pytest.raises(CompassError, match="names route 'regular' twice"):
        evaluate_route(copy.deepcopy(ASSESSMENT), bad)


# --- CS-1: what one classification repeats, it does once -----------------------------

def _counting(monkeypatch, module, name):
    """Replace `module.name` with a function that counts its calls."""
    real = getattr(module, name)
    counter = {"calls": 0}

    def counted(*args, **kwargs):
        counter["calls"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return counter


def test_cs_1_a_classification_adapts_each_configuration_once(monkeypatch):
    """The policy a configuration gives the evaluator does not depend on the
    assessment, so the grid builds it once for each side, not once for each
    point."""
    from compass_pkg import classify, obligations, routing
    adapted = _counting(monkeypatch, obligations, "policy_adapter")
    viewed = _counting(monkeypatch, routing, "canonical_view")
    parent, child = _bench().pair(4)
    got = classify.classify(parent, child)
    assert got.grid.points == 4608
    assert adapted["calls"] == 2, adapted
    assert viewed["calls"] == 2, viewed


def test_cs_1_the_evaluator_runs_once_for_an_assessment_not_once_for_each_autonomy(
        monkeypatch):
    """Only the checkpoints depend on the autonomy, so the other autonomy
    values are read from the one result."""
    from compass_pkg import obligations
    ran = _counting(monkeypatch, obligations, "evaluate_route")
    got = obligations.obligations(_fixtures().preset(), copy.deepcopy(ASSESSMENT))
    assert not isinstance(got, obligations.Refused)
    assert len(got.checkpoints) == len(obligations.AUTONOMY) > 1
    assert ran["calls"] == 1, ran


def test_cs_1_each_autonomy_gets_the_checkpoints_the_evaluator_gives_it():
    from compass_pkg import obligations
    from compass_pkg.routing import evaluate_route
    config = _fixtures().preset()
    policy = obligations.policy_adapter(config)
    seen = set()
    for risk in ("trivial", "contained", "cross-cutting", "critical"):
        for size in ("atomic", "medium", "product"):
            for labels in ([], ["auth"], ["migrations"]):
                assessment = {**ASSESSMENT, "risk": risk, "size": size, "labels": labels}
                got = obligations.obligations(config, copy.deepcopy(assessment))
                if isinstance(got, obligations.Refused):
                    continue
                for autonomy in obligations.AUTONOMY:
                    expected = evaluate_route(copy.deepcopy(assessment), policy,
                                              autonomy=autonomy)["checkpoints"]
                    assert list(got.checkpoints[autonomy]) == expected, (
                        risk, size, labels, autonomy)
                    seen.add(tuple(expected))
    assert len(seen) > 1, "the assessments must give different checkpoints"


def test_cs_1_a_preparation_changes_no_obligation():
    from compass_pkg import obligations
    assert hasattr(obligations, "Preparation"), "obligations.Preparation does not exist"
    config = _fixtures().preset()
    preparation = obligations.Preparation()
    for labels in ([], ["auth"], ["migrations", "payments"]):
        for risk in ("contained", "critical"):
            assessment = {**ASSESSMENT, "risk": risk, "labels": labels}
            plain = obligations.obligations(config, copy.deepcopy(assessment))
            again = obligations.obligations(config, copy.deepcopy(assessment),
                                            preparation=preparation)
            assert again == plain


def test_cs_1_a_preparation_meant_for_other_inputs_is_not_reused():
    """It is keyed to the configuration and issue it was made from. Another
    configuration builds it again, so a preparation cannot answer for a
    configuration that changed."""
    from compass_pkg import obligations
    assert hasattr(obligations, "Preparation"), "obligations.Preparation does not exist"
    config = _fixtures().preset()
    other = copy.deepcopy(config)
    del other["rules"]["floors"]["rules"]["RP-FLOOR-003"]   # the label floor
    assessment = {**ASSESSMENT, "risk": "contained", "size": "small", "labels": ["auth"]}
    preparation = obligations.Preparation()
    first = obligations.obligations(config, copy.deepcopy(assessment),
                                    preparation=preparation)
    second = obligations.obligations(other, copy.deepcopy(assessment),
                                     preparation=preparation)
    assert second == obligations.obligations(other, copy.deepcopy(assessment))
    assert second != first, "the two configurations must route differently here"


def test_cs_1_equal_facts_are_not_compared_field_by_field(monkeypatch):
    """Where the two sides owe the same, the comparison has nothing to report,
    so it does not walk the fields."""
    from compass_pkg import classify
    compared = _counting(monkeypatch, classify, "_compare")
    parent, child = _bench().pair(4)
    got = classify.classify(parent, child)
    assert got.result == "equivalent" and got.grid.points == 4608
    assert compared["calls"] == 0, compared


def test_cs_1_a_point_that_differs_is_still_compared_field_by_field():
    from compass_pkg import classify
    fixtures = _fixtures()
    parent, child = fixtures.base(), fixtures.base()
    child["gates"]["verify.correctness"]["checks"] = ["tests-pass", "no-secrets"]
    got = classify.classify(parent, child)
    assert got.result == "tightening" and got.counts["tighter"] == got.grid.points


# --- CS-3: the benchmark pair keeps its verdict, and the benchmark prints CPU time ---

BENCH = ROOT / "scripts" / "bench-classifier.py"


def _bench():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bench_classifier_speed", BENCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cs_3_the_benchmark_pair_at_four_labels_keeps_its_grid_verdict_and_counts(
        monkeypatch):
    from compass_pkg import classify, obligations
    calls = []
    real = obligations.obligations
    monkeypatch.setattr(obligations, "obligations",
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    parent, child = _bench().pair(4)
    got = classify.classify(parent, child)
    assert (got.result, got.scan, got.complete) == ("equivalent", "full", True)
    assert got.grid.points == 4608 and got.grid.raw_points == 51840
    assert got.grid.label_count == 4
    assert got.counts == {"equal": 4608, "tighter": 0, "looser": 0, "mixed": 0}
    assert len(calls) == 2 * 4608, "the evaluator runs once for each side at each point"


def test_cs_3_the_benchmark_records_cpu_seconds_beside_the_clock():
    bench = _bench()
    row = bench.measure(_fixtures().base(), _fixtures().with_labels(_fixtures().base(), "ci"),
                        exhaustive=False)
    assert "cpu_seconds" in row, "the row has no CPU figure"
    assert 0 < row["cpu_seconds"] <= row["seconds"] * 1.5
    line = bench.format_row(row)
    assert "cpu" in line and f"{row['cpu_seconds']:.1f}" in line
    assert "grouped" in line and f"{row['points']:,}" in line


# --- CS-2: a stored classification is reused when nothing it depends on moved ------

def _classify_api():
    from compass_pkg import classify
    return classify


def _stored():
    """The function that returns a stored classification, or fails the test
    with the reason (a missing function is a failed assertion, not an error)."""
    classify = _classify_api()
    assert hasattr(classify, "classify_stored"), "classify.classify_stored does not exist"
    return classify.classify_stored


def _pair_with_one_more_check():
    parent = _fixtures().base()
    child = _fixtures().base()
    child["gates"]["verify.correctness"]["checks"] = ["tests-pass", "no-secrets"]
    return parent, child


class _EvaluatorCalls:
    def __init__(self, monkeypatch):
        from compass_pkg import obligations
        self.count = 0
        real = obligations.obligations

        def counting(*args, **kwargs):
            self.count += 1
            return real(*args, **kwargs)

        monkeypatch.setattr(obligations, "obligations", counting)


def test_cs_2_the_same_two_configurations_are_classified_once(monkeypatch):
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    first = stored(store, parent, child)
    scanned = calls.count
    assert scanned > 0 and first.result == "tightening" and len(store) == 1
    second = stored(store, copy.deepcopy(parent), copy.deepcopy(child))
    assert calls.count == scanned, "an unchanged layer was scanned again"
    assert second.to_json() == first.to_json()
    assert len(store) == 1


def test_cs_2_a_stored_result_carries_the_names_of_the_call_that_asked(monkeypatch):
    stored = _stored()
    store = {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child, parent_name="default", child_name="project")
    again = stored(store, parent, child, parent_name="project", child_name="issue")
    assert (again.parent_name, again.child_name) == ("project", "issue")
    assert again.to_json()["parent"] == "project"


@pytest.mark.parametrize("change", [
    "child config", "parent config", "child capabilities", "parent capabilities",
    "child issue", "directions", "exhaustive", "early exit"])
def test_cs_2_anything_the_verdict_depends_on_makes_a_new_scan(monkeypatch, change):
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    seen = calls.count
    kwargs = {}
    if change == "child config":
        child["checks"]["no-secrets"]["severity"] = "advisory"
    elif change == "parent config":
        parent["checks"]["no-secrets"]["severity"] = "advisory"
    elif change == "child capabilities":
        kwargs["child_capabilities"] = ("artifact-freshness",)
    elif change == "parent capabilities":
        kwargs["parent_capabilities"] = ("artifact-freshness",)
    elif change == "child issue":
        kwargs["child_issue"] = {"ceilings": {"subtask_ceiling": 1}}
    elif change == "directions":
        kwargs["directions"] = {"rules.ceilings.review_rounds": "lower"}
    elif change == "exhaustive":
        kwargs["exhaustive"] = True
    elif change == "early exit":
        kwargs["early_exit"] = True
    stored(store, parent, child, **kwargs)
    assert calls.count > seen, f"a change of {change} was served from the store"
    assert len(store) == 2


def test_cs_2_a_new_classifier_version_makes_a_new_scan(monkeypatch):
    stored = _stored()
    classify = _classify_api()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    seen = calls.count
    monkeypatch.setattr(classify, "CLASSIFIER_VERSION", classify.CLASSIFIER_VERSION + 1)
    stored(store, parent, child)
    assert calls.count > seen and len(store) == 2


@pytest.mark.parametrize("table", ["OBLIGATION_FIELDS", "CEILING_DIRECTIONS"])
def test_cs_2_a_changed_rule_table_makes_a_new_scan(monkeypatch, table):
    """The tables the comparison reads are part of the key, so a rule change
    cannot be served a result the old rule gave."""
    stored = _stored()
    classify = _classify_api()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    seen = calls.count
    changed = dict(getattr(classify, table))
    changed["a.new.field"] = "lower" if table == "CEILING_DIRECTIONS" else "identity"
    monkeypatch.setattr(classify, table, changed)
    stored(store, parent, child)
    assert calls.count > seen and len(store) == 2


def test_cs_2_a_changed_check_registry_makes_a_new_scan(monkeypatch):
    from compass_pkg import check_registry
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    seen = calls.count
    import dataclasses
    registry = dict(check_registry.REGISTRY)
    name, entry = next(iter(registry.items()))
    registry[name] = dataclasses.replace(entry, tighter={**entry.tighter, "a-param": "lower"})
    monkeypatch.setattr(check_registry, "REGISTRY", registry)
    stored(store, parent, child)
    assert calls.count > seen and len(store) == 2


def test_cs_2_a_stored_result_gives_back_the_json_it_was_made_from():
    classify = _classify_api()
    assert hasattr(classify.Classification, "from_json"), "Classification.from_json is missing"
    fixtures = _fixtures()
    tight, loose = _pair_with_one_more_check()
    cases = [
        (tight, loose),
        (loose, tight),                                       # loosening
        (fixtures.base(), fixtures.base()),                   # identical
        (fixtures.base(), fixtures.with_labels(fixtures.base(), "a", "b")),
        (fixtures.with_labels(fixtures.base(), *"abcdefghi"),  # past the cap
         fixtures.with_labels(fixtures.base(), *"abcdefghij")),
    ]
    seen = set()
    for parent, child in cases:
        got = classify.classify(parent, child, parent_name="p", child_name="c")
        doc = got.to_json()
        seen.add(doc["scan"])
        loaded = classify.Classification.from_json(json.loads(json.dumps(doc)))
        assert loaded.to_json() == doc
        assert classify.json_shape_errors(loaded.to_json()) == []
    assert {"full", "identical", "cap"} <= seen


def test_cs_2_every_verdict_survives_a_store():
    classify = _classify_api()
    stored = _stored()
    fixtures = _fixtures()
    tight, loose = _pair_with_one_more_check()
    mixed = fixtures.with_spike(fixtures.base())
    store = {}
    seen = set()
    for parent, child in ((tight, loose), (loose, tight), (fixtures.base(), mixed),
                          (fixtures.base(), fixtures.with_labels(fixtures.base(), "a"))):
        first = stored(store, parent, child)
        again = stored(store, parent, child)
        assert again.to_json() == first.to_json() == classify.classify(
            parent, child).to_json()
        seen.add(first.result)
    assert {"equivalent", "tightening", "loosening", "incomparable"} <= seen


def test_cs_2_a_stored_entry_that_is_not_a_classification_is_scanned_again(monkeypatch):
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    (key,) = store
    store[key] = {"schema": 1, "result": "equivalent"}        # damaged or old
    seen = calls.count
    got = stored(store, parent, child)
    assert calls.count > seen and got.result == "tightening"
    assert store[key]["result"] == "tightening"


@pytest.mark.parametrize("damage", [
    "equivalent with tighter points", "looser count without a first looser point",
    "counts that do not add up to the points evaluated", "a cap result that is equivalent",
    "tightening that has looser points"])
def test_cs_2_a_stored_entry_whose_fields_contradict_each_other_is_scanned_again(
        monkeypatch, damage):
    """The shape of the document is right, and its parts disagree, so it was not
    written by `to_json` and its verdict cannot be trusted."""
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child)
    (key,) = store
    doc = copy.deepcopy(store[key])
    assert doc["result"] == "tightening" and doc["counts"]["tighter"] > 0
    if damage == "equivalent with tighter points":
        doc["result"] = "equivalent"
    elif damage == "looser count without a first looser point":
        doc["counts"]["looser"] = 1
        doc["counts"]["tighter"] -= 1
    elif damage == "counts that do not add up to the points evaluated":
        doc["counts"]["tighter"] -= 1
    elif damage == "a cap result that is equivalent":
        doc["scan"], doc["result"] = "cap", "equivalent"
    else:
        doc["counts"]["looser"] = 1
        doc["counts"]["tighter"] -= 1
        doc["first_looser"] = doc["first_tighter"]
    store[key] = doc
    seen = calls.count
    got = stored(store, parent, child)
    assert calls.count > seen, "a contradictory entry was served"
    assert got.result == "tightening" and store[key]["result"] == "tightening"
    assert store[key] != doc


def test_cs_2_a_caller_function_for_a_direction_is_never_stored(monkeypatch):
    """A function cannot be keyed, so a scan that uses one is not served from a
    store and writes nothing to it."""
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    parent, child = _pair_with_one_more_check()
    stored(store, parent, child, tighter=lambda impl, param: "none")
    assert store == {}
    seen = calls.count
    stored(store, parent, child, tighter=lambda impl, param: "none")
    assert calls.count == 2 * seen


def test_cs_2_identical_configurations_need_no_scan_and_no_entry(monkeypatch):
    stored = _stored()
    calls, store = _EvaluatorCalls(monkeypatch), {}
    base = _fixtures().base()
    got = stored(store, base, copy.deepcopy(base))
    assert got.result == "equivalent" and got.scan == "identical"
    assert calls.count == 0 and store == {}


# What decides a verdict, as one digest. A change to any of it
# can change what a stored result should say, so this pin fails until the
# author has looked at `classify.CLASSIFIER_VERSION`: raise it when a verdict
# can change, and only then record the new digest here. A change that moves no
# verdict (a rename, a faster way to the same answer) keeps the version.
# Re-pinned for `compare_at`, the single-assessment comparison `issue configure`
# previews with, and for `grid_at` and the `at=` argument of `classify`, the
# one-point grid an issue's own layer is judged on (ADR-037, 2026-10-08).
# Neither decides a verdict: a call without `at` runs the same code over the
# same grid. Merged with the entry and exit lists' `ships` reading, which
# raised the version to 2.
# Re-pinned for the rename of the depth words and the size `standard`
# (issue `vocabulary-and-cli-renames`): the evaluator reads a policy written in
# the old words as the new ones (`word_map.map_policy`) and lifts to `thorough`.
# No verdict moves: the 5.6.0 routing baseline and the classifications of layers
# in the old words give the same results (`test_size_medium.py`,
# `test_old_words_read.py`), so the version stays 2.
VERDICT_SOURCE_PIN = "fbe4e2b088645ce6"


def _verdict_source_digest():
    """The whole source of the modules that decide a verdict and of the pieces
    of `routing` and `core` the evaluator path runs, with the tables they read.
    Any edit to any of it, a comment included, changes the digest."""
    import hashlib
    import inspect
    from compass_pkg import classify, core, obligations, routing
    from compass_pkg import policy
    text = [inspect.getsource(classify), inspect.getsource(obligations)]
    text += [inspect.getsource(getattr(routing, name)) for name in (
        "evaluate_route", "canonical_routes", "canonical_view", "prepare_policy",
        "route_checkpoints", "PreparedPolicy", "_below_thorough")]
    text += [inspect.getsource(getattr(core, name)) for name in (
        "reading_matches", "shape_stages", "canonical_shape", "_stage_key_renames")]
    text += [inspect.getsource(policy.checkpoint_table_errors)]
    tables = {"hit": obligations.BUILT_IN_HIT, "statement": obligations.STATEMENT_KINDS,
              "stages": policy.CHECKPOINT_STAGES, "widest": classify.WIDEST_WHEN_EMPTY,
              "default_hit": obligations.DEFAULT_HIT,
              "approaches": obligations.EVALUATOR_APPROACHES}
    text.append(repr(sorted(tables.items())))
    return hashlib.sha256("\n".join(text).encode("utf-8")).hexdigest()[:16]


def test_cs_2_the_functions_that_decide_a_verdict_are_pinned_to_the_version():
    classify = _classify_api()
    assert hasattr(classify, "CLASSIFIER_VERSION"), "classify.CLASSIFIER_VERSION is missing"
    assert VERDICT_SOURCE_PIN == _verdict_source_digest(), (
        f"a function that decides a verdict changed. Raise "
        f"classify.CLASSIFIER_VERSION (now {classify.CLASSIFIER_VERSION}) if a "
        f"verdict can differ, then set VERDICT_SOURCE_PIN to "
        f"'{_verdict_source_digest()}'")


# --- CS-7: a public scan with a callback for each point ------------------------------

def _scan_api():
    classify = _classify_api()
    assert hasattr(classify, "scan"), "classify.scan does not exist"
    return classify


def _small_pair():
    fixtures = _fixtures()
    parent = fixtures.with_labels(fixtures.base(), "a", "b")
    child = copy.deepcopy(parent)
    child["gates"]["verify.correctness"]["checks"] = ["tests-pass", "no-secrets"]
    return parent, child


def test_cs_7_the_scan_calls_back_for_each_point_in_grid_order():
    classify = _scan_api()
    parent, child = _small_pair()
    grid = classify.build_grid(parent, child)
    seen = []
    done = classify.scan(parent, child, grid,
                         on_point=lambda point, run: seen.append(point.assessment))
    assert done == len(seen) == grid.points
    expected = [{**{name: cls.values[0] for (name, _), cls in zip(grid.dimensions, classes)
                    if cls.values[0] is not None}, "labels": list(subset)}
                for classes in __import__("itertools").product(
                    *[cs for _, cs in grid.dimensions])
                for subset in grid.label_subsets()]
    assert seen == expected


def test_cs_7_a_callback_that_answers_yes_stops_the_scan():
    classify = _scan_api()
    parent, child = _small_pair()
    grid = classify.build_grid(parent, child)
    seen = []
    done = classify.scan(parent, child, grid,
                         on_point=lambda point, run: seen.append(1) or len(seen) == 3)
    assert done == 3 and len(seen) == 3


def test_cs_7_a_callback_sees_each_points_changes_and_the_comparison_context():
    classify = _scan_api()
    parent, child = _small_pair()
    grid = classify.build_grid(parent, child)
    outcomes = []

    def record(point, run):
        outcomes.append(point.outcome)
        assert run.ctx.configs == (parent, child)

    classify.scan(parent, child, grid, on_point=record)
    assert set(outcomes) == {"tighter"}


def test_cs_7_the_scan_hands_the_callback_the_obligations_of_either_side_once(monkeypatch):
    from compass_pkg import obligations
    classify = _scan_api()
    parent, child = _small_pair()
    grid = classify.build_grid(parent, child)
    ran = _counting(monkeypatch, obligations, "obligations")
    again = []

    def ask(point, run):
        again.append(run.obligations(0, point.assessment))
        return True

    classify.scan(parent, child, grid, on_point=ask)
    assert ran["calls"] == 2, "the parent was evaluated again for the callback"
    assert not isinstance(again[0], classify.Refused)


def test_cs_7_classify_runs_through_the_public_scan(monkeypatch):
    classify = _scan_api()
    ran = _counting(monkeypatch, classify, "scan")
    parent, child = _small_pair()
    got = classify.classify(parent, child)
    assert ran["calls"] == 1 and got.result == "tightening"


def test_cs_7_the_two_helpers_the_lock_check_borrowed_are_public():
    classify = _scan_api()
    assert classify.where({"risk": "critical", "labels": ["a", "b"]}) == \
        "risk critical, labels a, b"
    assert classify.where({"risk": "critical"}) == "risk critical, labels none"
    assert classify.plain({"b": {3, 1}, "a": ("x",)}) == {"a": ["x"], "b": [1, 3]}


def test_cs_7_the_lock_module_reads_no_private_name_of_the_classifier():
    import ast
    text = (ROOT / "cli" / "compass_pkg" / "locks.py").read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "compass_pkg.classify":
            assert [a.name for a in node.names if a.name.startswith("_")] == []
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                and node.value.id == "classify"):
            assert not node.attr.startswith("_"), node.attr
            assert node.attr != "obligations", "locks reach the evaluator through classify"
    header = text.split("from __future__", 1)[0]
    for name in ("_Run", "_evaluate", "_where", "_plain"):
        assert name not in header, f"the header still names {name}"
