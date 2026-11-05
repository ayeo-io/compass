"""The issue's own `config:` layer reaches the evaluator.

`compass approach evaluate` computes the stages, gates, checkpoints, subtask
ceiling and approach from the configuration the issue runs against and from
the issue's own layer (the approach it names, the stage modes it sets and the
subtask ceiling it sets), as `obligations` does for the classifier. Scenario
ids `IL-1` to `IL-6` (issue `issue-layer-reaches-evaluator`). Each test name
starts with its scenario id.

On the four-stage path (ADR-092) assess writes the evidence a change owes, and
no approach, stage mode or subtask ceiling (decisions 1, 3 and 11). So each test
checks two things: what the write commits on the path, and that the issue's
layer the commit stores (`EffectiveView.evaluator_issue`) still reaches the
evaluator, judged on the 8.0.4 governance copy, the last release that routed
approaches.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import configure_fixtures as fx  # noqa: E402

LAYERED = {"schema": 1}
#: The keys only an issue assessed before the path holds.
LEGACY_ONLY = ("stages", "subtask_ceiling", "max_worktrees", "orchestration")


def _evaluate(root, *extra):
    return fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--json", *extra)


def _reassess_with(tmp_path, *flags):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, *flags)
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    return root, task_dir


def _layer(task_dir):
    """The issue's layer the configuration in force hands the evaluator: the
    stored generation's, or the live view's for an issue with none."""
    from compass_pkg import effective
    view = effective.view_or_legacy(str(task_dir))
    # A project with no `compass.yml` has no view, and so no issue layer.
    return view.evaluator_issue() if view is not None else None


def _route_8_0_4(task_dir=None, issue=None, **readings):
    """The 8.0.4 evaluator's result for the issue's assessment, with the layer
    of `task_dir` (or `issue`) as its own layer."""
    import compat_baseline as cb
    from compass_pkg import routing
    assessment = dict(fx.MANIFEST["assessment"], size="medium", **readings)
    if task_dir is not None:
        issue = _layer(task_dir)
    return routing.evaluate_route(assessment, routing.prepare_policy(cb.policy_8_0_4()),
                                  issue=issue)


def _on_the_path(body):
    assert body["delivery_approach"] == "delivery", body
    assert body["evidence_required"], body
    for key in LEGACY_ONLY:
        assert key not in body, key


# --- IL-1: a stage mode in the issue's layer changes the computed stages -------------------

def test_il_1_an_issue_stage_mode_changes_the_stages_the_write_commits(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    first = fx.manifest_of(task_dir)
    _on_the_path(first)
    assert _route_8_0_4(task_dir)["stages"]["refine"] == "lightweight"
    code, out, err = fx.configure(root, "--mode", "refine=thorough")
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2
    # A stage mode changes no evidence on the path (ADR-092 decision 1).
    _on_the_path(body)
    assert body["evidence_required"] == first["evidence_required"]
    result = _route_8_0_4(task_dir)
    assert result["stages"]["refine"] == "thorough"
    assert result["delivery_approach"] == "regular"


def test_il_1_a_stored_overlay_is_read_again_by_a_later_evaluation(tmp_path):
    """The generation holds the overlay's effect, so a read-only evaluation
    after the commit still computes the issue's mode."""
    root, task_dir = _reassess_with(tmp_path, "--mode", "refine=thorough")
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    shown = json.loads(out)
    assert shown["evidence_required"] == fx.manifest_of(task_dir)["evidence_required"]
    assert "stages" not in shown, shown
    assert _layer(task_dir)["stage_modes"] == {"refine": "thorough"}
    assert _route_8_0_4(task_dir)["stages"]["refine"] == "thorough"


def test_il_1_an_issue_with_no_layer_computes_what_the_project_gives(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    _on_the_path(json.loads(out))
    assert _layer(task_dir) is None
    assert _route_8_0_4(task_dir)["stages"]["refine"] == "lightweight"


# --- IL-2: the issue's subtask ceiling reaches the evaluator -------------------------------

def test_il_2_an_issue_ceiling_lowers_the_subtask_ceiling(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    _on_the_path(fx.manifest_of(task_dir))
    assert _route_8_0_4(task_dir)["subtask_ceiling"] == 2
    code, out, err = fx.configure(root, "--ceiling", "subtask_ceiling=1")
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    # The path writes no ceiling (ADR-092 decision 11); the committed layer
    # still hands it to the evaluator.
    _on_the_path(fx.manifest_of(task_dir))
    assert _layer(task_dir)["subtask_ceiling"] == 1
    assert _route_8_0_4(task_dir)["subtask_ceiling"] == 1
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert "subtask_ceiling" not in json.loads(out)


# --- IL-3: the issue's approach is the candidate, and a lock refuses a loosening -------------

def test_il_3_an_issue_approach_is_the_candidate_of_a_read_only_evaluation(tmp_path):
    """A layer is read here and not linted: the commit is where a lock refuses."""
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED,
                                manifest=dict(fx.MANIFEST, config={"approach": "full"}))
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    # On the path the issue's approach selects no evidence (ADR-092 decision 3).
    _on_the_path(json.loads(out))
    assert not (task_dir / "generations").exists()
    assert _layer(task_dir) == {"approach": "full"}
    assert _route_8_0_4(task_dir)["delivery_approach"] == "full"


def test_il_3_a_lock_refuses_the_commit_of_an_issue_approach(tmp_path):
    """A spike issue that names `full` loses `spike.conclude` at its own
    assessment (the lock that protects exactly this case). A delivery issue
    that names `full` is not a lock case: it is incomparable on the subtask
    ceiling, which `test_issue_layer_at_its_point.py` pins."""
    body = dict(fx.MANIFEST, config={"approach": "full"})
    body["assessment"] = dict(fx.MANIFEST["assessment"], goal="exploration")
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED, manifest=body)
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--write")
    assert code != 0
    assert "does not pass the lint" in err and "K-LOCK-REFUSED" in err
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_il_3_a_floor_still_raises_the_issue_approach(tmp_path):
    """The floors apply after the issue's choice: an issue cannot name an
    approach below one a floor demands."""
    body = dict(fx.MANIFEST, config={"approach": "quick-fix"})
    body["assessment"] = dict(fx.MANIFEST["assessment"], risk="critical")
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED, manifest=body)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    _on_the_path(json.loads(out))
    assert _layer(task_dir) == {"approach": "quick-fix"}
    assert _route_8_0_4(task_dir, risk="critical")["delivery_approach"] != "quick-fix"


def test_il_3_a_loosening_the_policy_does_not_allow_is_refused_with_the_lint_message(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, "--mode", "define=collapsed")
    assert code == 1, out + err
    code, out, err = fx.reassess(root)
    assert code != 0
    assert "C-INCOMPARABLE" in err or "does not pass the lint" in err
    assert fx.manifest_of(task_dir)["generation"] == 1
    # The path stores no stage modes (ADR-092 decision 1); the refused commit
    # left the stored layer, which still gives define its mode.
    _on_the_path(fx.manifest_of(task_dir))
    assert _layer(task_dir) is None
    assert _route_8_0_4(task_dir)["stages"]["define"] == "thorough"


# --- IL-4: the preview shows what the reassess commits -------------------------------------

def test_il_4_the_preview_and_the_reassess_agree(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, "--mode", "refine=thorough", "--ceiling",
                                  "subtask_ceiling=1", "--json")
    assert code == 0, out + err
    shown = json.loads(out)["assessment"]
    assert shown["approach"]["after"] == "delivery"
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["delivery_approach"] == shown["approach"]["after"]
    _on_the_path(body)
    # The path stores neither field (ADR-092 decisions 1 and 11), so the preview's
    # values are compared with what the committed layer gives the evaluator.
    result = _route_8_0_4(task_dir)
    by_field = {(c["field"], c["key"]): c["after"] for c in shown["changes"]}
    assert by_field[("approaches.stages", "refine")] == result["stages"]["refine"] == "thorough"
    assert by_field[("approaches.subtask_ceiling", None)] == result["subtask_ceiling"] == 1


# --- IL-5: nothing changes without a layer or without a compass.yml -------------------------

def test_il_5_a_project_with_no_compass_yml_computes_as_before(tmp_path):
    root, task_dir = fx.project(tmp_path)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    _on_the_path(json.loads(out))
    assert _layer(task_dir) is None
    result = _route_8_0_4(task_dir)
    assert result["stages"]["refine"] == "lightweight"
    assert result["subtask_ceiling"] == 2
    assert result["delivery_approach"] == "regular"


def test_il_5_a_layer_and_no_layer_agree_on_everything_the_layer_does_not_set(tmp_path):
    plain_root, _ = fx.project(tmp_path / "plain", compass_yml=LAYERED)
    layered_root, _ = fx.project(
        tmp_path / "layered", compass_yml=LAYERED,
        manifest=dict(fx.MANIFEST, config={"autonomy": "balanced"}))
    plain = json.loads(_evaluate(plain_root)[1])
    layered = json.loads(_evaluate(layered_root)[1])
    assert plain == layered


# --- IL-6: check judges by the committed result --------------------------------------------

def test_il_6_check_names_the_committed_approach_not_a_pending_edit(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, before, err = fx.run(root, "check", "--issue", fx.SLUG)
    fx.write_manifest(task_dir, config={"approach": "full"})
    code, after, err = fx.run(root, "check", "--issue", fx.SLUG)
    # The path's committed approach is `delivery` (ADR-092 decision 2).
    assert "'feature' (delivery)" in before and "'feature' (delivery)" in after
    notes = [line for line in after.splitlines() if "is not committed yet" in line]
    assert len(notes) == 1
    assert [line for line in after.splitlines() if line not in notes] == before.splitlines()


def test_il_6_check_reads_the_stage_modes_the_write_committed(tmp_path):
    root, task_dir = _reassess_with(tmp_path, "--mode", "refine=thorough")
    code, out, err = fx.run(root, "check", "--issue", fx.SLUG)
    assert "generation 2" in out
    _on_the_path(fx.manifest_of(task_dir))
    assert _layer(task_dir)["stage_modes"] == {"refine": "thorough"}
