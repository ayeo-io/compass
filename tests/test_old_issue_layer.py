"""An issue keeps the issue layer its stored generation holds; a new `config:`
is not read.

9.0.0 has no issue layer (ADR-094). An 8.x issue whose stored generation was
committed with one keeps it: `compass check` and a read-only `compass approach
evaluate` read the generation, and `EffectiveView.evaluator_issue` hands the
layer's stage modes, approach and ceilings to the evaluator. A manifest's
`config:` changes nothing else: assess does not read it, and `compass issue
lint` warns about it.

Most cases moved from `test_issue_layer_evaluator.py` (scenario ids `IL-1` to
`IL-6`) and `test_waived_stage_on_floor.py` (`WSM-4`), which went with `compass
issue configure`. A stage mode of a legacy stage or an 8.x approach is resolved
in process over the 8.0.4 governance copy (`_view_8_0_4`), as an old issue's
stored generation resolves it.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import reassess_fixtures as fx  # noqa: E402

LAYERED = {"schema": 1}
#: The keys only an issue assessed before the path holds.
LEGACY_ONLY = ("stages", "subtask_ceiling", "max_worktrees", "orchestration")
#: The issue layer an 8.x issue committed: ship's mode in the old word `full`,
#: which the generation stores as `thorough`, and a subtask ceiling.
OVERLAY = {"stages": {"ship": {"set": {"mode": "full"}}},
           "ceilings": {"subtask_ceiling": 1}}
HEADER_KEYS = ("schema", "issue", "generation")


def _evaluate(root, *extra):
    return fx.run(root, "approach", "evaluate", "--issue", fx.SLUG, "--json", *extra)


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


def _view_8_0_4(tmp_path, issue_doc, project_doc=None):
    """The view of an issue whose layer is `issue_doc`, resolved over the 8.0.4
    governance copy, as an 8.x generation stored it: the copy's configuration
    with each stage mode the layer sets written into its stage, and the
    layer's approach and ceilings beside it. `project_doc` held no catalogue in
    8.x either, so it adds nothing. 8.x merged the layers; 9.0.0 has no merge
    (ADR-094), so the stored shape is built here."""
    import compat_baseline as cb
    from compass_pkg import effective, word_map
    copy_root = tmp_path / "copy-8-0-4"
    (copy_root / ".compass").mkdir(parents=True, exist_ok=True)
    cb.add_governance_copy(copy_root, source=cb.GOVERNANCE_8_0_4)
    resolved = effective.legacy_resolved(str(copy_root))
    issue = word_map.map_layer(copy.deepcopy(issue_doc))[0]
    for stage, entry in (issue.get("stages") or {}).items():
        resolved["stages"][stage]["mode"] = entry["set"]["mode"]
    resolved.update({key: issue_doc[key] for key in ("approach", "ceilings") if key in issue_doc})
    return effective.EffectiveView("live", None, None, resolved, {}), None


def _on_the_path(body):
    assert body["delivery_approach"] == "delivery", body
    assert body["evidence_required"], body
    for key in LEGACY_ONLY:
        assert key not in body, key


def _old_issue(tmp_path):
    """An issue at generation 2, which an 8.x reassess committed with the issue
    layer `OVERLAY`: the manifest holds it as `config:`, and the generation
    holds its effect and its digest. Written through the store, as 8.x wrote it."""
    from compass_pkg import generation
    from compass_pkg.atomic_io import digest
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    stored = generation.load(str(task_dir), 1)
    body = {name: {k: v for k, v in stored[name].items() if k not in HEADER_KEYS}
            for name in ("resolved", "provenance", "versions")}
    resolved = copy.deepcopy(body["resolved"])
    resolved["stages"]["ship"]["mode"] = "thorough"
    resolved["ceilings"] = dict(OVERLAY["ceilings"])
    versions = dict(body["versions"], issue_overlay_digest=digest(OVERLAY))
    manifest = fx.manifest_of(task_dir)
    manifest["config"] = copy.deepcopy(OVERLAY)
    generation.commit(str(task_dir), generation.Resolution(
        resolved=resolved, provenance=body["provenance"], versions=versions), manifest)
    assert fx.manifest_of(task_dir)["generation"] == 2
    return root, task_dir


# --- an 8.x issue reads the layer its generation stored ------------------------------------

def test_il_1_a_stored_overlay_is_read_again_by_a_later_evaluation(tmp_path):
    """The generation holds the overlay's effect, so a read-only evaluation
    still computes the issue's mode and ceiling."""
    root, task_dir = _old_issue(tmp_path)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    shown = json.loads(out)
    assert shown["evidence_required"] == fx.manifest_of(task_dir)["evidence_required"]
    assert "stages" not in shown and "subtask_ceiling" not in shown, shown
    assert _layer(task_dir) == {"stage_modes": {"ship": "thorough"}, "subtask_ceiling": 1}
    result = _route_8_0_4(task_dir)
    assert result["stages"]["ship"] == "thorough"
    assert result["subtask_ceiling"] == 1


def test_il_6_check_reads_the_generation_the_layer_was_committed_with(tmp_path):
    root, task_dir = _old_issue(tmp_path)
    code, out, err = fx.run(root, "check", "--issue", fx.SLUG)
    assert "generation 2" in out, out + err
    assert "config: differs" not in out
    _on_the_path(fx.manifest_of(task_dir))


def test_il_6_check_names_a_changed_config_and_judges_by_the_generation(tmp_path):
    root, task_dir = _old_issue(tmp_path)
    code, before, err = fx.run(root, "check", "--issue", fx.SLUG)
    fx.write_manifest(task_dir, config={"approach": "full"})
    code, after, err = fx.run(root, "check", "--issue", fx.SLUG)
    # The path's committed approach is `delivery` (ADR-092 decision 2).
    assert "'feature' (delivery)" in before and "'feature' (delivery)" in after
    notes = [line for line in after.splitlines() if "config: differs" in line]
    assert len(notes) == 1 and "ADR-094" in notes[0], notes
    assert [line for line in after.splitlines() if line not in notes] == before.splitlines()


def test_a_reassess_of_an_old_issue_commits_a_generation_without_the_layer(tmp_path):
    root, task_dir = _old_issue(tmp_path)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "committed generation 3" in out
    assert "RE-ASSESSMENT recorded (configuration)" not in out
    body = fx.manifest_of(task_dir)
    assert body["config"] == OVERLAY        # the manifest keeps the key as written
    assert [e["kind"] for e in body.get("reassessments") or ()] == ["unchanged"]
    assert fx.load(fx.gen(task_dir, 3) / "versions.yml")["issue_overlay_digest"] is None
    assert _layer(task_dir) is None


# --- a new issue's config: is not read -----------------------------------------------------

def test_a_new_issue_config_changes_nothing_the_evaluator_computes(tmp_path):
    plain_root, _ = fx.project(tmp_path / "plain", compass_yml=LAYERED)
    config = {"approach": "full", "autonomy": "controlled",
              "ceilings": {"subtask_ceiling": 1},
              "stages": {"ship": {"set": {"mode": "thorough"}}}}
    layered_root, task_dir = fx.project(tmp_path / "layered", compass_yml=LAYERED,
                                        manifest=dict(fx.MANIFEST, config=config))
    plain = json.loads(_evaluate(plain_root)[1])
    layered = json.loads(_evaluate(layered_root)[1])
    assert plain == layered
    _on_the_path(layered)
    assert _layer(task_dir) is None


def test_a_new_issue_config_is_not_committed(tmp_path):
    config = {"autonomy": "controlled", "stages": {"ship": {"set": {"mode": "thorough"}}}}
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED,
                                  manifest=dict(fx.MANIFEST, config=config))
    resolved = fx.load(fx.gen(task_dir, 1) / "resolved.yml")
    assert resolved["autonomy"] == "balanced"
    assert "mode" not in resolved["stages"]["ship"]
    assert fx.load(fx.gen(task_dir, 1) / "versions.yml")["issue_overlay_digest"] is None
    # A config: written after the commit is not a change a reassess commits.
    fx.write_manifest(task_dir, config={"autonomy": "autonomous"})
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out
    assert [e["kind"] for e in fx.manifest_of(task_dir)["reassessments"]] == ["unchanged"]


def test_a_spike_issue_that_names_full_is_written_as_a_spike(tmp_path):
    body = dict(fx.MANIFEST, config={"approach": "full"})
    body["assessment"] = dict(fx.MANIFEST["assessment"], goal="exploration")
    root, task_dir = fx.project(tmp_path, compass_yml=LAYERED, manifest=body)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["delivery_approach"] == "spike"


def test_issue_lint_warns_on_a_config_nothing_reads(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED,
                                  manifest=dict(fx.MANIFEST, config={"autonomy": "controlled"}))
    code, out, err = fx.run(root, "issue", "lint", "--issue", fx.SLUG)
    assert code == 0, out + err
    assert "warning: config: is not read" in out and "ADR-094" in out, out


def test_issue_lint_does_not_warn_on_the_config_a_generation_was_committed_with(tmp_path):
    root, task_dir = _old_issue(tmp_path)
    code, out, err = fx.run(root, "issue", "lint", "--issue", fx.SLUG)
    assert code == 0, out + err
    assert "config: is not read" not in out, out
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    code, out, err = fx.run(root, "issue", "lint", "--issue", fx.SLUG)
    assert code == 0, out + err
    assert "warning: config: is not read" in out, out


# --- the evaluator reads an issue input over the 8.0.4 copy ---------------------------------

def test_il_1_an_issue_stage_mode_reaches_the_evaluator_over_the_8_0_4_copy(tmp_path):
    view, _ = _view_8_0_4(tmp_path, {"stages": {"refine": {"set": {"mode": "thorough"}}}})
    layer = view.evaluator_issue()
    assert layer["stage_modes"] == {"refine": "thorough"}
    assert _route_8_0_4(issue=None)["stages"]["refine"] == "lightweight"
    result = _route_8_0_4(issue=layer)
    assert result["stages"]["refine"] == "thorough"
    assert result["delivery_approach"] == "regular"


def test_il_1_an_issue_with_no_layer_computes_what_the_project_gives(tmp_path):
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED)
    code, out, err = _evaluate(root)
    assert code == 0, out + err
    _on_the_path(json.loads(out))
    assert _layer(task_dir) is None
    assert _route_8_0_4(task_dir)["stages"]["refine"] == "lightweight"


def test_il_3_an_issue_approach_is_the_candidate_over_the_8_0_4_copy(tmp_path):
    view, _ = _view_8_0_4(tmp_path, {"approach": "full"})
    assert view.evaluator_issue() == {"approach": "full"}
    assert _route_8_0_4(issue=view.evaluator_issue())["delivery_approach"] == "full"


def test_il_3_a_floor_still_raises_the_issue_approach(tmp_path):
    """The floors apply after the issue's choice: an issue cannot name an
    approach below one a floor demands."""
    view, _ = _view_8_0_4(tmp_path, {"approach": "quick-fix"})
    assert view.evaluator_issue() == {"approach": "quick-fix"}
    assert _route_8_0_4(issue=view.evaluator_issue())["delivery_approach"] == "quick-fix"
    raised = _route_8_0_4(issue=view.evaluator_issue(), risk="critical")
    assert raised["delivery_approach"] == "full", raised["delivery_approach"]


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


def test_wsm_4_a_waived_stage_mode_holds_on_an_approach_a_floor_raised(tmp_path):
    """The `migrations` label brings RP-FLOOR-003, which raises the approach to
    `full`, and `full` runs breakdown as multiagent. A stage an old issue's
    generation records as waived keeps its mode there (decision
    `2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach`)."""
    from compass_pkg import obligations
    from compass_pkg.routing import evaluate_route
    view, _ = _view_8_0_4(tmp_path, {"stages": {"breakdown": {"set": {"mode": "skipped"}}}},
                          project_doc={"schema": 1, "owner": "jed72"})
    config = view.resolved
    policy = obligations.policy_adapter(config)
    assessment = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
                  "goal": "delivery", "urgency": "none", "labels": ["migrations"]}
    waived = evaluate_route(assessment, policy,
                            issue=obligations.issue_input(config, {}, ["breakdown"]))
    assert waived["delivery_approach"] == "full"
    assert waived["stages"]["breakdown"] == "skipped"
    # The same mode without the waiver gives way to the approach the floor raised.
    plain = evaluate_route(assessment, policy, issue=obligations.issue_input(config, {}, []))
    assert plain["stages"]["breakdown"] == "multiagent"
