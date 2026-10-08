"""The issue's own `config:` layer reaches the evaluator.

`compass approach evaluate` computes the stages, gates, checkpoints, subtask
ceiling and approach from the configuration the issue runs against and from
the issue's own layer (the approach it names, the stage modes it sets and the
subtask ceiling it sets), as `obligations` does for the classifier. Scenario
ids `IL-1` to `IL-6` (issue `issue-layer-reaches-evaluator`). Each test name
starts with its scenario id.
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


def _evaluate(root, *extra):
    return fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--json", *extra)


def _reassess_with(tmp_path, *flags):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, *flags)
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    return root, task_dir


# --- IL-1: a stage mode in the issue's layer changes the computed stages -------------------

def test_il_1_an_issue_stage_mode_changes_the_stages_the_write_commits(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    assert fx.manifest_of(task_dir)["stages"]["refine"] == "light"
    code, out, err = fx.configure(root, "--mode", "refine=full")
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2
    assert body["stages"]["refine"] == "full"
    assert body["delivery_approach"] == "regular"


def test_il_1_a_stored_overlay_is_read_again_by_a_later_evaluation(tmp_path):
    """The generation holds the overlay's effect, so a read-only evaluation
    after the commit still computes the issue's mode."""
    root, task_dir = _reassess_with(tmp_path, "--mode", "refine=full")
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert json.loads(out)["stages"]["refine"] == "full"


def test_il_1_an_issue_with_no_layer_computes_what_the_project_gives(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert json.loads(out)["stages"]["refine"] == "light"


# --- IL-2: the issue's subtask ceiling reaches the evaluator -------------------------------

def test_il_2_an_issue_ceiling_lowers_the_subtask_ceiling(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    assert fx.manifest_of(task_dir)["subtask_ceiling"] == 2
    code, out, err = fx.configure(root, "--ceiling", "subtask_ceiling=1")
    assert code == 0, out + err
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["subtask_ceiling"] == 1
    code, out, err = _evaluate(root)
    assert json.loads(out)["subtask_ceiling"] == 1


# --- IL-3: the issue's approach is the candidate, and a lock refuses a loosening -------------

def test_il_3_an_issue_approach_is_the_candidate_of_a_read_only_evaluation(tmp_path):
    """A layer is read here and not linted: the commit is where a lock refuses."""
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED,
                                manifest=dict(fx.MANIFEST, config={"approach": "full"}))
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    assert json.loads(out)["delivery_approach"] == "full"
    assert not (task_dir / "generations").exists()


def test_il_3_a_lock_refuses_the_commit_of_an_issue_approach(tmp_path):
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED,
                                manifest=dict(fx.MANIFEST, config={"approach": "full"}))
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
    assert json.loads(out)["delivery_approach"] != "quick-fix"


def test_il_3_a_loosening_the_policy_does_not_allow_is_refused_with_the_lint_message(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, "--mode", "define=collapsed")
    assert code == 1, out + err
    code, out, err = fx.reassess(root)
    assert code != 0
    assert "C-INCOMPARABLE" in err or "does not pass the lint" in err
    assert fx.manifest_of(task_dir)["generation"] == 1
    assert fx.manifest_of(task_dir)["stages"]["define"] == "full"


# --- IL-4: the preview shows what the reassess commits -------------------------------------

def test_il_4_the_preview_and_the_reassess_agree(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = fx.configure(root, "--mode", "refine=full", "--ceiling",
                                  "subtask_ceiling=1", "--json")
    assert code == 0, out + err
    shown = json.loads(out)["assessment"]
    assert shown["approach"]["after"] == "regular"
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["delivery_approach"] == shown["approach"]["after"]
    by_field = {(c["field"], c["key"]): c["after"] for c in shown["changes"]}
    assert by_field[("approaches.stages", "refine")] == body["stages"]["refine"]
    assert by_field[("approaches.subtask_ceiling", None)] == body["subtask_ceiling"]


# --- IL-5: nothing changes without a layer or without a compass.yml -------------------------

def test_il_5_a_project_with_no_compass_yml_computes_as_before(tmp_path):
    root, task_dir = fx.project(tmp_path)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    result = json.loads(out)
    assert result["stages"]["refine"] == "light"
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
    assert "'feature' (regular)" in before and "'feature' (regular)" in after
    notes = [line for line in after.splitlines() if "is not committed yet" in line]
    assert len(notes) == 1
    assert [line for line in after.splitlines() if line not in notes] == before.splitlines()


def test_il_6_check_reads_the_stage_modes_the_write_committed(tmp_path):
    root, task_dir = _reassess_with(tmp_path, "--mode", "refine=full")
    code, out, err = fx.run(root, "check", "--issue", fx.SLUG)
    assert "generation 2" in out
    assert fx.manifest_of(task_dir)["stages"]["refine"] == "full"
