"""The evaluator adapter and the issue-layer evaluation order.

`obligations.policy_adapter` turns the catalogues of a resolved configuration
into the input `evaluate_route` takes. These tests replay it against the
routing grid of the compatibility baseline and the archive sample's recorded
verdicts. A replay that cannot fail proves nothing, so each one is run over a
planted fault as well.

The cases of the obligations function and the facts the classifier compared
went with the classifier in 9.0.0 (ADR-094). These moved from the tests of
the obligations function.

Scenario ids: `OB-1`, `OB-2`, `OB-3`, `OB-4`, `OB-5` and `OB-8` (issue
`obligations`).
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg.core import CompassError  # noqa: E402
from compass_pkg.routing import evaluate_route  # noqa: E402

READINGS = {"risk": "contained", "familiarity": "greenfield", "size": "small",
            "labels": []}


def _policy(stages, floors=None, ranks=None, extra_shapes=None):
    """The smallest legacy-shaped policy the evaluator accepts: one approach
    and the floors given."""
    policy = {
        "routing_strategies": {"default_route": "regular"},
        "routing_guardrails": {"floors": floors or []},
        "route_shapes": {"regular": {"weight": 2, "stages": stages, "gates": [],
                                     "artifacts": {}, "subtask_ceiling": 1}},
    }
    policy["route_shapes"].update(extra_shapes or {})
    if ranks is not None:
        policy["stage_mode_ranks"] = ranks
    return policy


def _floor(*stages):
    return [{"id": "F-1", "when": {"risk": "contained"}, "never_skip": list(stages)}]


# --- OB-2: the evaluator lifts by rank when it is given ranks --------------------

RANKS = {"refine": {"skipped": 0, "collapsed": 1, "lightweight": 2, "thorough": 3,
                    "exhaustive": 4, "draft": 0},
         "implement": {"thorough": 3}}


def test_ob_2_a_floor_lifts_a_mode_whose_rank_is_below_thorough():
    policy = _policy({"refine": "draft", "implement": "thorough"}, _floor("refine"),
                     RANKS)
    # `draft` is not in the fixed set, so only the rank can lift it.
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "thorough"


def test_ob_2_a_floor_leaves_a_mode_of_rank_thorough_or_above_alone():
    for mode in ("thorough", "exhaustive"):
        policy = _policy({"refine": mode, "implement": "thorough"}, _floor("refine"),
                         RANKS)
        assert evaluate_route(READINGS, policy)["stages"]["refine"] == mode


def test_ob_2_a_floor_leaves_a_mode_with_no_rank_alone():
    policy = _policy({"refine": "expedited", "implement": "thorough"}, _floor("refine"),
                     RANKS)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "expedited"


def test_ob_2_a_stage_the_floor_does_not_name_is_not_lifted():
    policy = _policy({"refine": "draft", "implement": "thorough"}, _floor("implement"),
                     RANKS)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "draft"


def test_ob_2_a_policy_with_no_ranks_lifts_exactly_the_fixed_set():
    for mode, lifted in (("collapsed", True), ("skipped", True), ("lightweight", True),
                         ("thorough", False), ("draft", False), ("expedited", False)):
        policy = _policy({"refine": mode}, _floor("refine"))
        got = evaluate_route(READINGS, policy)["stages"]["refine"]
        assert got == ("thorough" if lifted else mode), mode


def test_ob_2_a_policy_copied_before_the_rename_lifts_the_same_set():
    """A copied policy that still says `light` and `full` routes as it did, once
    the copy reader maps its words. Since 9.0.0 only `tests/legacy_copy.py` reads
    a copied policy (ADR-098), so the mapping runs there, not in `evaluate_route`."""
    from legacy_copy import map_policy
    for mode in ("light", "full"):      # `light` is lifted; `full` is already there
        policy = map_policy(_policy({"refine": mode}, _floor("refine")))
        assert evaluate_route(READINGS, policy)["stages"]["refine"] == "thorough", mode
    ranked = map_policy(_policy(
        {"refine": "draft", "implement": "full"}, _floor("refine"),
        {"refine": {"light": 2, "full": 3, "draft": 0}, "implement": {"full": 3}}))
    assert evaluate_route(READINGS, ranked)["stages"]["refine"] == "thorough"


def test_ob_2_a_stage_with_no_thorough_rank_is_not_lifted_by_rank():
    # Without a rank for `thorough` there is nothing to be below.
    policy = _policy({"refine": "draft"}, _floor("refine"),
                     {"refine": {"draft": 0}})
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "draft"


# --- the shipped preset as a resolved configuration ------------------------------

def _preset_config(folder="default"):
    """The catalogues of the committed preset files, as a stored generation
    holds them: each file adds its own catalogue, so nothing merges."""
    import yaml
    from compass_pkg import catalogue_spec
    preset = ROOT / "tests" / "fixtures" / "presets" / folder
    config = {}
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((preset / f"{name}.yml").read_text(encoding="utf-8"))
        if part.get(name):
            config[name] = part[name]
    return config


@pytest.fixture(scope="module")
def preset_config():
    """The shipped default: the check set since 9.0.0 (ADR-094), which replaced
    the live preset."""
    from compass_pkg import catalogue_spec, check_set
    resolved = check_set.resolved()
    return {name: resolved[name] for name in catalogue_spec.CATALOGUES if resolved.get(name)}


@pytest.fixture(scope="module")
def frozen_config():
    """The frozen 7.0.0 preset. The live default declares no document since 9.0.0
    (ADR-091) and no approach but the spike and the path (ADR-092); a stored
    generation still declares its catalogue, approach maps, stages, floors and
    document rules, so the facts they give, and the replay of the 8.x routing
    baseline, are read from this preset."""
    return _preset_config("default@7")


def _respelled(result):
    """A routing result with the two values the catalogues spell differently
    written their way: a document is its id (no `.md`), and a stage is its
    current name. The legacy files keep the older spelling (`intent.md`,
    `land`)."""
    from compass_pkg import core
    renames = core._stage_key_renames()
    out = copy.deepcopy(result)
    if "required_artifacts" in out:
        out["required_artifacts"] = [a[:-3] if a.endswith(".md") else a
                                     for a in out["required_artifacts"]]
    for blocked in out.get("blocked_phases") or []:
        blocked["phase"] = renames.get(blocked["phase"], blocked["phase"])
    return out


def _replay(adapted, header, rows, first_only=False):
    """Where the adapted policy routes differently from the baseline, in the
    catalogues' spelling. Grid and archive rows compare with the recorded
    result. A label row records only a digest of the legacy spelling, so it
    compares with the 8.0.4 governance copy through the same respelling. That
    copy routes as the baseline (contract 1) and, unlike the live default, keeps
    the delivery approaches that 9.0.0 replaces (ADR-092)."""
    from compat_baseline import compact, digest, label_subsets, policy_8_0_4
    found, today = [], None
    for row in rows:
        if row["kind"] in ("grid", "archive"):
            if compact(row["assessment"], adapted) != _respelled(row["result"]):
                found.append(f"{row['kind']} {row['assessment']}")
        elif row["kind"] == "label-digests":
            today = today or policy_8_0_4()
            for subset in label_subsets(header["labels"]):
                readings = dict(row["assessment"], labels=subset)
                if (digest(_respelled(compact(readings, adapted)))
                        != digest(_respelled(compact(readings, today)))):
                    found.append(f"labels {subset} on {row['assessment']}")
                    break
        if found and first_only:
            break
    return found


@pytest.fixture(scope="module")
def baseline():
    from compat_baseline import load_routing
    return load_routing()


def _differences_between(today, adapted, assessments, first_only=False):
    """Where two policies route differently over the same assessments."""
    from compat_baseline import compact
    found = []
    for readings in assessments:
        a, b = compact(readings, today), compact(readings, adapted)
        if a != b:
            found.append((readings, a, b))
            if first_only:
                break
    return found


# --- OB-1: the adapted preset routes the compatibility grid as today's policy ----

def test_ob_1_the_adapted_preset_routes_the_whole_baseline_as_before(frozen_config,
                                                                    baseline):
    from compass_pkg import obligations
    header, rows = baseline
    adapted = obligations.policy_adapter(frozen_config)
    differences = _replay(adapted, header, rows)
    assert differences == [], "\n".join(differences[:10])


def test_ob_1_the_only_spelling_the_replay_changes_is_the_two_the_catalogues_respell(
        frozen_config, baseline):
    """Without the respelling, the adapted preset differs from the baseline in
    `required_artifacts` and `blocked_phases` and in nothing else, and each
    differing value is the baseline's value in the catalogues' spelling."""
    from compass_pkg import obligations
    from compat_baseline import compact
    _, rows = baseline
    adapted = obligations.policy_adapter(frozen_config)
    fields = set()
    for row in rows:
        if row["kind"] not in ("grid", "archive"):
            continue
        now = compact(row["assessment"], adapted)
        old = row["result"]
        for key in set(now) | set(old):
            if now.get(key) != old.get(key):
                fields.add(key)
        assert now == _respelled(old), row["assessment"]
    assert fields == {"required_artifacts", "blocked_phases"}


def test_ob_1_a_gate_dropped_from_the_preset_breaks_the_replay(frozen_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(frozen_config)
    regular = config["approaches"]["regular"]
    regular["gates"] = [g for g in regular["gates"] if g != "verify.regression"]
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows, first_only=True), \
        "a dropped gate went unseen"


def test_ob_1_a_floor_dropped_from_the_preset_breaks_the_replay(frozen_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(frozen_config)
    del config["rules"]["floors"]["rules"]["RP-FLOOR-001"]
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows, first_only=True)


def test_ob_1_a_change_only_a_label_reaches_breaks_the_replay(frozen_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(frozen_config)
    config["rules"]["floors"]["rules"]["RP-FLOOR-003"]["when"] = {
        "labels_any": ["nothing-matches"]}
    adapted = obligations.policy_adapter(config)
    # No grid row carries a label, so only the label rows can see it.
    assert [d for d in _replay(adapted, header, rows, first_only=True)
            if d.startswith("labels")]


def test_ob_1_the_generated_fallback_shape_goes_back_to_the_default_route(frozen_config):
    strategies = _api("policy_adapter")(frozen_config)["routing_strategies"]
    assert strategies["default_route"] == "regular"
    assert "RP-SHAPE-FALLBACK" not in [r["id"] for r in strategies["default_shapes"]]
    assert [r["id"] for r in strategies["default_shapes"]] == [
        f"RP-SHAPE-00{i}" for i in range(1, 6)]


def test_ob_1_the_ranks_reach_the_evaluator(frozen_config):
    from compass_pkg import obligations
    ranks = obligations.policy_adapter(frozen_config)["stage_mode_ranks"]
    assert ranks["ship"] == {"lightweight": 2, "thorough": 3, "thorough-with-follow-up": 4}
    assert "reproduce-first" not in ranks["define"]
    assert ranks["define"]["thorough"] == 3


def test_ob_1_a_planted_rank_on_a_mode_a_floor_reaches_breaks_the_replay(
        frozen_config, baseline):
    from compass_pkg import obligations
    header, rows = baseline
    config = copy.deepcopy(frozen_config)
    # `reproduce-first` carries no rank, and floor RP-FLOOR-002 names `define`.
    config["stages"]["define"]["modes"]["reproduce-first"] = {"rank": 2}
    adapted = obligations.policy_adapter(config)
    assert _replay(adapted, header, rows), \
        "a planted rank on a lifted stage went unseen"


def test_ob_1_a_planted_rank_on_expedited_is_seen_when_a_floor_names_implement(
        frozen_config):
    """The baseline's policy has no floor on `implement`, so a rank on `expedited`
    cannot show in the baseline. With one such floor added to both paths, it
    does. The policy is the 8.0.4 governance copy, which routes as the baseline
    and keeps the delivery approaches that 9.0.0 replaces (ADR-092)."""
    from compass_pkg import obligations
    from compat_baseline import policy_8_0_4
    today = policy_8_0_4()
    today["routing_guardrails"]["floors"].append(
        {"id": "RP-PLANT", "when": {"urgency": "live-defect"},
         "require_phase": "implement"})
    config = copy.deepcopy(frozen_config)
    config["rules"]["floors"]["rules"]["RP-PLANT"] = {
        "order": 99, "when": {"urgency": "live-defect"},
        "then": {"require_phase": "implement"}}
    config["rules"]["floors"]["hit"]["require_phase"] = "collect"
    hotfixes = [{"risk": "contained", "familiarity": "greenfield", "size": "small",
                 "goal": "delivery", "urgency": "live-defect", "role": "engineer",
                 "labels": []}]
    assert _differences_between(today, obligations.policy_adapter(config),
                                hotfixes) == []
    config["stages"]["implement"]["modes"]["expedited"] = {"rank": 2}
    assert _differences_between(today, obligations.policy_adapter(config),
                                hotfixes, first_only=True), \
        "a planted rank on expedited went unseen"


# --- helpers ---------------------------------------------------------------------

def _api(name):
    from compass_pkg import obligations
    assert hasattr(obligations, name), f"obligations.{name} is not defined yet"
    return getattr(obligations, name)


def _assessment(**kw):
    base = {"risk": "contained", "familiarity": "brownfield-mapped",
            "size": "medium", "goal": "delivery", "urgency": "none",
            "labels": []}
    base.update(kw)
    return base


def test_ob_3_the_replays_spelling_follows_cores_tables_and_the_adapters_rule(
        monkeypatch):
    import legacy_copy as legacy_adapter
    from compass_pkg import core
    table = core._stage_key_renames()
    assert table, "core holds no retired stage name"
    for old, new in table.items():
        assert _respelled({"blocked_phases": [{"phase": old}]})[
            "blocked_phases"][0]["phase"] == new
    # A name added to core's table is read through at once: the replay holds no copy.
    monkeypatch.setattr(core, "_stage_key_renames",
                        lambda: dict(table, **{"zz-retired": "zz-current"}))
    assert _respelled({"blocked_phases": [{"phase": "zz-retired"}]})[
        "blocked_phases"][0]["phase"] == "zz-current"
    for name in ("intent.md", "intent", "a.md.md", "md", ""):
        assert _respelled({"required_artifacts": [name]})["required_artifacts"][0] \
            == legacy_adapter._artifact_id(name)


# --- OB-5: the issue layer ---------------------------------------------------------


def test_ob_5_the_evaluator_applies_a_waived_stage_on_a_replaced_approach():
    # The copy reader maps the older words before the evaluator runs (ADR-098).
    from legacy_copy import map_policy
    policy = map_policy(_policy({"refine": "light", "implement": "full"}))
    policy["route_shapes"]["full"] = dict(policy["route_shapes"]["regular"], weight=9)
    policy["routing_guardrails"]["floors"].append(
        {"id": "F-UP", "when": {"risk": "contained"}, "force_minimum_route": "full"})
    out = evaluate_route(READINGS, policy, issue={
        "stage_modes": {"implement": "expedited", "refine": "lighter"},
        "waived_stages": ["implement"]})
    assert out["delivery_approach"] == "full"
    # `light` is the older spelling, read as `lightweight`.
    assert out["stages"] == {"refine": "lightweight", "implement": "expedited"}
    assert out["issue_overrides"] == {"applied": {"implement": "expedited"},
                                      "ignored": {"refine": "lighter"}}


def test_ob_5_the_evaluator_lowers_a_subtask_ceiling_for_an_issue_and_never_raises_it():
    policy = _policy({"refine": "light"})
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 5}
                          )["subtask_ceiling"] == 1
    policy["route_shapes"]["regular"]["subtask_ceiling"] = 3
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 2}
                          )["subtask_ceiling"] == 2
    policy["route_shapes"]["regular"]["subtask_ceiling"] = None
    assert evaluate_route(READINGS, policy, issue={"subtask_ceiling": 2}
                          )["subtask_ceiling"] == 2


def _fault(call):
    """The message of the `CompassError` the call raises. Any other outcome,
    including another kind of error, fails the test."""
    try:
        call()
    except Exception as exc:                     # noqa: BLE001
        assert isinstance(exc, CompassError), f"{type(exc).__name__}: {exc}"
        return str(exc)
    raise AssertionError("no error was raised")


def test_ob_5_a_mode_ranked_equal_to_thorough_is_not_lifted():
    ranks = {"refine": {"thorough": 3, "equal": 3, "lightweight": 2}}
    policy = _policy({"refine": "equal"}, _floor("refine"), ranks)
    assert evaluate_route(READINGS, policy)["stages"]["refine"] == "equal"


def test_ob_5_the_evaluator_reports_what_it_applied_and_ignored():
    policy = _policy({"refine": "light", "implement": "full"}, _floor("refine"))
    out = evaluate_route(READINGS, policy, issue={
        "stage_modes": {"implement": "expedited", "ship": "light"}})
    assert out["stages"]["implement"] == "expedited"
    assert out["issue_overrides"] == {"applied": {"implement": "expedited"},
                                      "ignored": {"ship": "light"}}
    # A call with no issue input has no such key, as before.
    assert "issue_overrides" not in evaluate_route(READINGS, policy)



# --- OB-8: nothing else changes -----------------------------------------------------

EVALUATOR_KEYS = {
    "renamed_routes", "candidate_route", "candidate_via", "delivery_approach",
    "policy_rules_fired", "stages", "gates", "artifacts", "subtask_ceiling",
    "required_artifacts", "required_skills", "blocked_phases", "max_worktrees",
    "applicable_strategies", "checkpoints"}


def test_ob_8_the_evaluator_called_as_before_returns_the_same_keys():
    from compat_baseline import shipped_policy
    out = evaluate_route(_assessment(), shipped_policy())
    assert set(out) == EVALUATOR_KEYS
    assert set(evaluate_route(_assessment(), shipped_policy(), "controlled")) \
        == EVALUATOR_KEYS


def test_ob_8_an_empty_issue_input_is_no_issue_input():
    from compat_baseline import shipped_policy
    assert evaluate_route(_assessment(), shipped_policy(), issue={}) \
        == evaluate_route(_assessment(), shipped_policy())


def test_ob_8_the_command_answers_as_before():
    """The 8.x evaluator, called as `approach evaluate --assessment` called it
    with no issue, gives the same approach and no issue key. The command now
    prints the path for a delivery assessment (ADR-092); its twin follows."""
    # The 8.0.4 governance copy keeps the 8.x approaches; the shipped default
    # routes every delivery assessment to the path since 9.0.0 (ADR-092).
    from compat_baseline import policy_8_0_4
    answer = evaluate_route({"risk": "trivial", "familiarity": "greenfield",
                             "size": "small"}, policy_8_0_4())
    assert answer["delivery_approach"] == "quick-fix"
    assert "issue_overrides" not in answer


def test_ob_8_the_command_answers_on_the_path(tmp_path):
    import json
    import subprocess
    out = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "approach", "evaluate",
         "--json", "--assessment", "risk=trivial", "--assessment",
         "familiarity=greenfield", "--assessment", "size=small"],
        cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    answer = json.loads(out.stdout)
    assert answer["delivery_approach"] == "delivery"
    assert answer["evidence_required"]
    assert "issue_overrides" not in answer


def _obligations_importers(paths):
    """The files among `paths` that import `obligations` in any form: `from
    compass_pkg import obligations`, with other names or in a parenthesised list,
    `from compass_pkg.obligations import x`, and `import compass_pkg.obligations`."""
    import ast
    found = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.ImportFrom):
                if node.module == "compass_pkg":
                    names = [a.name for a in node.names]
                elif node.module == "compass_pkg.obligations":
                    names = ["obligations"]
            elif isinstance(node, ast.Import):
                names = [a.name.rsplit(".", 1)[-1] for a in node.names
                         if a.name.startswith("compass_pkg.")]
            if "obligations" in names:
                found.append(path)
                break
    return found


def test_ob_8_only_effective_reads_the_new_path():
    """Amended 2026-10-07 (ADR-037): `effective` may import `obligations`; the
    readers go through the effective view. The classifier and the replay (policy
    diff) also imported it until 9.0.0 removed them (ADR-094)."""
    paths = [p for p in sorted((ROOT / "cli").rglob("*.py"))
             if p.name != "obligations.py" and "vendor" not in p.parts]
    users = [str(p.relative_to(ROOT)) for p in _obligations_importers(paths)]
    assert users == ["cli/compass_pkg/effective.py"]
    assert "obligations" not in (ROOT / "cli" / "compass").read_text(encoding="utf-8")


def test_ob_8_the_import_rule_sees_every_import_form(tmp_path):
    forms = {
        "a.py": "from compass_pkg import obligations\n",
        "b.py": "from compass_pkg import (\n    layers,\n    obligations,\n)\n",
        "c.py": "import compass_pkg.obligations as o\n",
        "d.py": "def f():\n    from compass_pkg.obligations import obligations\n",
    }
    for name, text in forms.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    (tmp_path / "e.py").write_text("from compass_pkg import layers\n", encoding="utf-8")
    seen = sorted(p.name for p in _obligations_importers(sorted(tmp_path.glob("*.py"))))
    assert seen == ["a.py", "b.py", "c.py", "d.py"]


def test_ob_8_a_second_importer_fails_the_rule(tmp_path):
    planted = tmp_path / "reader.py"
    planted.write_text("from compass_pkg import (\n    obligations,\n)\n", encoding="utf-8")
    paths = [p for p in sorted((ROOT / "cli").rglob("*.py"))
             if p.name != "obligations.py" and "vendor" not in p.parts] + [planted]
    users = [p.name for p in _obligations_importers(paths)]
    assert users != ["effective.py"]
    assert users[-1] == "reader.py"


def test_ob_8_the_effect_names_are_the_inverse_of_the_adapters():
    import legacy_copy as legacy_adapter
    from compass_pkg import obligations
    assert obligations._LEGACY_EFFECT == {
        new: old for old, new in legacy_adapter.RENAMED_EFFECTS.items()}


def test_ob_8_the_module_declares_its_dependencies_and_stays_small():
    path = ROOT / "cli" / "compass_pkg" / "obligations.py"
    text = path.read_text(encoding="utf-8")
    assert "# DEPENDENCY:" in text
    # The design's target was 600; the readiness fact (one function and its
    # table rows) takes the cap to 620, and the word-limit fact (one field and
    # its row) to 625, the model-tier block (one import, one call and the
    # dependency line) to 630, the waived stages of the issue layer to 634, and
    # the `delivery` approach of the path (ADR-092) to 636. The classifier's facts
    # went in 9.0.0 (ADR-094), which leaves the adapter and the issue input.
    assert len(text.splitlines()) < 637
    core = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8")
    assert len(core.splitlines()) <= 1200


def test_ob_4_the_evaluators_two_conflicts_are_the_ones_that_refuse():
    from compass_pkg import routing
    conflict = getattr(routing, "RoutingConflict", None)
    assert conflict is not None and issubclass(conflict, CompassError)


def test_ob_8_the_owning_docs_name_the_module_and_the_evaluator_input():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    rows = [line for line in readme.splitlines()
            if line.startswith("|") and "cli/compass_pkg/obligations.py" in line]
    assert len(rows) == 1, "docs/README.md needs one owning-doc row for obligations.py"
    owner = rows[0].split("|")[2].strip().strip("`")
    assert (ROOT / owner).is_file(), owner
    policy = (ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8")
    for word in ("cli/compass_pkg/obligations.py", "stage_mode_ranks", "RoutingConflict"):
        assert word in policy, f"routing-policy.md does not mention {word}"


# --- the evaluator reads the configuration's orders; guards for what it cannot read ---

def _reordered(config):
    """`size` reordered, with a floor that reads it through `at_least`."""
    config = copy.deepcopy(config)
    config["dimensions"]["size"]["values"] = ["atomic", "small", "large", "medium",
                                              "product"]
    config["rules"]["floors"]["rules"]["RP-PLANT-ORDER"] = {
        "order": 90, "when": {"size": {"at_least": "large"}},
        "then": {"force_minimum_approach": "full"}}
    return config


def test_ob_1_the_shipped_orders_are_what_the_evaluator_assumed(preset_config):
    from compass_pkg.catalogue_spec import SHIPPED_ORDERS
    adapted = _api("policy_adapter")(preset_config)
    assert {k: tuple(v) for k, v in adapted["dimension_orders"].items()} \
        == dict(SHIPPED_ORDERS)


def test_ob_1_the_built_in_hit_policies_are_the_adapters(preset_config):
    import legacy_copy as legacy_adapter
    built_in = _api("BUILT_IN_HIT")
    assert built_in == legacy_adapter.EFFECT_HITS
    assert _api("DEFAULT_HIT") == "collect"
    for rule_set in preset_config["rules"].values():
        for effect, declared in rule_set["hit"].items():
            assert declared == built_in.get(effect, "collect"), effect


def test_ob_1_the_five_approaches_are_the_ones_the_policy_ships(preset_config, frozen_config):
    # The evaluator knows the shipped default's two approaches (ADR-092) and the
    # five of the 8.x presets, which a frozen preset or stored generation declares.
    assert set(_api("EVALUATOR_APPROACHES")) == \
        set(preset_config["approaches"]) | set(frozen_config["approaches"])
    assert set(preset_config["approaches"]) == {"spike", "delivery"}


def test_ob_8_no_planning_id_that_a_reader_cannot_open_is_cited():
    """The shipped files of this increment cite decisions and ADRs a reader can
    open, never an id from a planning document that is not in the repository."""
    import re
    private = re.compile(r"(?<![A-Za-z0-9-])(D-\d+|CF-\d+|X-\d+|Q-\d+|PC-\d+|R-7|S1\.\d+)\b")
    for rel in ("cli/compass_pkg/obligations.py", "cli/compass_pkg/routing.py",
                "governance/routing-policy.md", "tests/test_policy_adapter.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        # The pattern itself is the one line allowed to spell the ids.
        found = [m.group(0) for line in text.splitlines()
                 if "private = re.compile" not in line
                 for m in private.finditer(line)]
        assert found == [], (rel, found)
    cited = re.findall(r"governance/decisions/[\w.-]+\.md",
                       (ROOT / "cli/compass_pkg/routing.py").read_text(encoding="utf-8"))
    assert cited, "routing.py names no decision for the issue layer's order"
    for path in cited:
        assert (ROOT / path).is_file(), path


def test_ob_8_the_routing_policy_records_what_the_replays_showed():
    policy = (ROOT / "governance" / "routing-policy.md").read_text(encoding="utf-8")
    for word in ("dimension_orders", "hit policy", "reproduce-first", "expedited",
                 "tests/test_policy_adapter.py"):
        assert word in policy, f"routing-policy.md does not mention {word}"
