"""A project file that still sets the approaches, a legacy stage, the caps rules or a
Definition of Ready check keeps working (ADR-092).

9.0.0 runs every new delivery issue on one four-stage path. The live default stops
declaring the five approaches, the six legacy stages `define` to `verify` that the path
does not keep, the caps rule set and the seven `dor-*` checks. A project `compass.yml`
written before 9.0.0 can still set them. If the merge read them, a `set:` on a stage the
parent no longer holds would refuse the project file and every command would stop. So
the merge leaves each one out of a project layer, and `compass policy lint` names it with
`L-SETTING-REMOVED`, the pattern ADR-091 set for `artifacts`.

A frozen preset (`default@6`, `default@7`) and a stored generation are not project
layers: they keep their approaches, stages, caps and lists, and still load.

Issue: ayeo-io/compass-delivery#351.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

import test_checkpoint_outcomes as projects  # noqa: E402

LEGACY_STAGES = ("define", "refine", "plan", "breakdown", "implement", "verify")
READY_CHECKS = ("dor-summary-filled", "dor-problem-traces-up", "dor-behavior-is-gwt",
                "dor-traceability-ids", "dor-affected-surface-named",
                "dor-no-open-questions", "dor-approach-still-fits")

#: Each project change and the removed key `compass policy lint` names for it.
CHANGES = [
    ({"approaches": {"regular": {"set": {"gates": ["verify.correctness"]}}}}, "approaches"),
    ({"stages": {"plan": {"set": {"mode": "thorough"}}}}, "stages.plan"),
    ({"stages": {"refine": {"remove": True}}}, "stages.refine"),
    ({"rules": {"caps": {"remove": True}}}, "rules.caps"),
    ({"checks": {"dor-no-open-questions": {"set": {"severity": "advisory"}}}},
     "checks.dor-no-open-questions"),
    ({"gates": {"verify.regression": {"set": {"checks": ["dor-behavior-is-gwt"]}}}},
     "checks.dor-behavior-is-gwt"),
]


def _parent():
    from compass_pkg import policy_lint
    return policy_lint.load_parent()[0]


def _lint_project(doc):
    from compass_pkg import policy_lint
    from compass_pkg.layers import Layer
    project = Layer("project", "project", {"schema": 1, **doc}, "d")
    return policy_lint.lint_chain(_parent(), project)


# --- the removed keys ---------------------------------------------------------------

def test_each_removed_key_names_adr_092():
    from compass_pkg import removed_parts
    keys = ["approaches", "rules.caps"] + [f"stages.{s}" for s in LEGACY_STAGES] + [
        f"checks.{c}" for c in READY_CHECKS]
    for key in keys:
        assert key in removed_parts.SETTINGS, key
        assert removed_parts.SETTINGS[key][1] == "ADR-092", key
    assert "ADR-092" in removed_parts.REASONS
    # The path keeps `assess` and `ship`, so a project can still change them.
    assert "stages.assess" not in removed_parts.SETTINGS
    assert "stages.ship" not in removed_parts.SETTINGS


def test_every_field_that_lists_checks_drops_a_removed_check():
    """A field the merge reads as a list of check ids that `without_removed` did not
    filter would keep a removed id, and the merge would refuse it as unknown."""
    from compass_pkg import merge, removed_parts
    lists = {(catalogue, field) for catalogue, field, target, kind in merge.REFERENCES
             if target == "checks" and kind == "list" and catalogue not in removed_parts.SETTINGS}
    held = {(catalogue, field) for catalogue, fields in removed_parts.CHECK_LIST_FIELDS.items()
            for field in fields}
    assert lists == held


# --- compass policy lint -------------------------------------------------------------

@pytest.mark.parametrize("doc,key", CHANGES, ids=[k for _, k in CHANGES])
def test_lint_names_each_removed_key_once_as_a_warning(doc, key):
    report = _lint_project(doc)
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert [f.path for f in found] == [key], [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning"
    assert "removed in 9.0.0" in found[0].message and "ADR-092" in found[0].message
    assert not [f for f in report.findings if f.level == "error"], [
        (f.code, f.path, f.message) for f in report.findings if f.level == "error"]


def test_a_project_that_changes_only_kept_parts_gets_no_removal_finding():
    report = _lint_project({"stages": {"ship": {"set": {"locked": True}}},
                            "rules": {"loop_ceilings": {"set": {"hit": {"limit": "min"}}}}})
    assert not [f for f in report.findings if f.code == "L-SETTING-REMOVED"]


def test_lint_does_not_judge_the_impl_of_a_removed_check():
    report = _lint_project({"checks": {"dor-no-open-questions": {"set": {"impl": "nonesuch"}}}})
    assert [f.code for f in report.findings] == ["L-SETTING-REMOVED"], report.findings


@pytest.mark.parametrize("body,key", [
    ("approaches: 5\n", "approaches"),
    ("stages:\n  plan: {modes: 7}\n", "stages.plan"),
    ("rules:\n  caps: {kind: not-a-kind}\n", "rules.caps"),
    ("checks:\n  dor-no-open-questions: {kind: not-a-kind}\n", "checks.dor-no-open-questions"),
])
def test_a_removed_key_with_a_bad_value_gives_only_the_removed_warning(tmp_path, body, key):
    """Nothing reads a removed key, so a value the old schema refused must not make the
    project file invalid (the #353 rule for removed settings)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    env = projects.env(tmp_path)
    subprocess.run([sys.executable, str(CLI), "init"], cwd=tmp_path, env=env,
                   capture_output=True, text=True)
    (tmp_path / "compass.yml").write_text("schema: 1\nowner: jed\n" + body, encoding="utf-8")
    result = subprocess.run([sys.executable, str(CLI), "policy", "lint"], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    out = result.stdout + result.stderr
    assert result.returncode == 0, out
    assert "L-SCHEMA" not in out, out
    assert f"L-SETTING-REMOVED [project] {key}" in out, out


# --- the merge -------------------------------------------------------------------------

def _resolved_parent():
    from compass_pkg import merge
    parent = _parent()
    return merge.apply({}, parent.doc, "parent", "default")[0]


@pytest.mark.parametrize("doc,key", CHANGES, ids=[k for _, k in CHANGES])
def test_the_merge_leaves_a_removed_key_out_of_a_project_layer(doc, key):
    from compass_pkg import merge
    base = _resolved_parent()
    config, provenance = merge.apply(base, {"schema": 1, **doc}, "project", "project")
    assert config == base, key
    assert not [p for p, step in provenance.items() if step.get("layer") == "project"], key


def test_a_kept_reference_beside_a_removed_one_is_still_merged():
    from compass_pkg import merge
    base = _resolved_parent()
    doc = {"schema": 1, "gates": {
        "verify.regression": {"set": {"checks": {"add": ["dor-no-open-questions",
                                                         "backfills-paid"]}}},
        "project.review": {"kind": "review", "stage": "ship", "accepts": ["test-run"],
                           "checks": ["dor-traceability-ids", "backfills-paid"]}}}
    config, _ = merge.apply(base, doc, "project", "project")
    assert config["gates"]["verify.regression"]["checks"] == ["backfills-paid"]
    assert config["gates"]["project.review"]["checks"] == ["backfills-paid"]


def test_a_parent_or_issue_layer_still_merges_the_removed_parts():
    from compass_pkg import merge
    base = _resolved_parent()
    parent = {"approaches": {"regular": {"set": {"gates": ["verify.correctness"]}}},
              "rules": {"caps": {"remove": True}}}
    config, _ = merge.apply(base, parent, "parent", "parent")
    assert config["approaches"]["regular"]["gates"] == ["verify.correctness"]
    assert "caps" not in config["rules"]
    config, _ = merge.apply(base, {"stages": {"plan": {"set": {"mode": "thorough"}}}},
                            "issue", "issue")
    assert config["stages"]["plan"]["mode"] == "thorough"


@pytest.mark.parametrize("frozen", ["default@6", "default@7"])
def test_a_frozen_preset_still_loads_with_its_approaches_and_stages(frozen):
    from compass_pkg import merge, policy_lint
    parent, _ = policy_lint.load_parent(directory=ROOT / "governance" / "presets" / frozen)
    config, _ = merge.apply({}, parent.doc, "parent", frozen)
    assert {"quick-fix", "regular", "full"} <= set(config["approaches"]), frozen
    assert {"plan", "refine", "breakdown"} <= set(config["stages"]), frozen
    assert "caps" in config["rules"], frozen
    assert set(READY_CHECKS) <= set(config["checks"]), frozen


# --- the commands still run ------------------------------------------------------------

OLD_PROJECT_FILE = dict(projects.BALANCED, **{
    "approaches": {"regular": {"set": {"gates": ["verify.correctness"]}}},
    "stages": {"plan": {"set": {"mode": "thorough"}}},
    "rules": {"caps": {"remove": True}},
    "checks": {"dor-no-open-questions": {"set": {"severity": "advisory"}}},
})


def test_evaluate_write_and_check_run_on_an_old_project_file(tmp_path):
    root = projects.project(tmp_path, compass_yml=OLD_PROJECT_FILE)
    done = projects.run(root, "check", "--issue", projects.SLUG)
    out = done.stdout + done.stderr
    assert done.returncode in (0, 1), out
    assert "M-" not in out and "nothing can be resolved" not in out, out
    lint = projects.run(root, "policy", "lint")
    out = lint.stdout + lint.stderr
    assert lint.returncode == 0, out
    for key in ("approaches", "stages.plan", "rules.caps", "checks.dor-no-open-questions"):
        assert f"L-SETTING-REMOVED [project] {key}" in out, (key, out)


@pytest.mark.parametrize("frozen", ["compass:default@6", "compass:default@7"])
def test_a_project_on_a_frozen_preset_still_loads_its_approaches(tmp_path, frozen):
    from compass_pkg import effective
    root = projects.project(tmp_path, compass_yml=dict(projects.BALANCED, extends=frozen))
    view = effective.view_or_legacy(start=str(root))
    assert {"quick-fix", "regular", "full"} <= set(view.config["approaches"]), frozen
    assert "plan" in view.config["stages"], frozen
    done = projects.run(root, "check", "--issue", projects.SLUG)
    assert done.returncode in (0, 1), done.stdout + done.stderr


# --- checkpoints -----------------------------------------------------------------------

def test_a_checkpoint_table_may_name_the_path_stages():
    from compass_pkg import policy
    table = {"autonomy_checkpoints": {"balanced": {
        "regular": ["assess", "specify", "build", "ship", "define", "plan"]}}}
    assert policy.checkpoint_table_errors(table) == []
    bad = {"autonomy_checkpoints": {"balanced": {"regular": ["breakdown"]}}}
    assert policy.checkpoint_table_errors(bad), "breakdown is no checkpoint"


def test_an_old_issue_gets_no_path_checkpoint_from_the_table():
    from compass_pkg import routing

    class _Prepared:
        view = {"autonomy_checkpoints": {"balanced": {
            "regular": ["assess", "specify", "build", "ship", "define", "plan"]}}}

    stages = {"assess": "thorough", "define": "thorough", "refine": "lightweight",
              "plan": "thorough", "implement": "thorough", "verify": "thorough",
              "ship": "thorough"}
    assert routing.route_checkpoints(_Prepared(), stages, "regular", "balanced") == [
        "assess", "define", "plan"]
