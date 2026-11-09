"""A project file that still sets the approaches, a legacy stage, the caps rules or a
Definition of Ready check keeps working (ADR-092).

9.0.0 runs every new delivery issue on one four-stage path. The live default stops
declaring the five approaches, the six legacy stages `define` to `verify` that the path
does not keep, the caps rule set and the seven `dor-*` checks. A project `compass.yml`
written before 9.0.0 can still set them; since ADR-094 a catalogue key in `compass.yml`
is a removed setting and is not read at all, and `compass policy lint` names it with
`L-SETTING-REMOVED`. The cases of the merge, the layered lint, the issue layer and
git parents went with them in 9.0.0 (ADR-094).

A frozen preset (`default@6`, `default@7`) and a stored generation are not project
layers: they keep their approaches, stages, caps and lists. A project's own copy of
the governance files is read with a gate at a legacy stage at its path stage.

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

import test_checkpoint_outcomes as projects  # noqa: E402

LEGACY_STAGES = ("define", "refine", "plan", "breakdown", "implement", "verify")
READY_CHECKS = ("dor-summary-filled", "dor-problem-traces-up", "dor-behavior-is-gwt",
                "dor-traceability-ids", "dor-affected-surface-named",
                "dor-no-open-questions", "dor-approach-still-fits")


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


# --- compass policy lint -------------------------------------------------------------


# The settings lint names a removed catalog once, by its key, not once per entry
# (ADR-094).
@pytest.mark.parametrize("body,key", [
    ("approaches: 5\n", "approaches"),
    ("stages:\n  plan: {modes: 7}\n", "stages"),
    ("rules:\n  caps: {kind: not-a-kind}\n", "rules"),
    ("checks:\n  dor-no-open-questions: {kind: not-a-kind}\n", "checks"),
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


# --- the frozen presets -----------------------------------------------------------------


@pytest.mark.parametrize("frozen", ["default@6", "default@7"])
def test_a_frozen_preset_still_loads_with_its_approaches_and_stages(frozen):
    import yaml
    from compass_pkg import catalogue_spec, word_map
    folder = ROOT / "tests" / "fixtures" / "presets" / frozen
    # Read through the retired-word tables, as a stored generation is read.
    config = word_map.map_layer({
        name: (yaml.safe_load((folder / f"{name}.yml").read_text(encoding="utf-8"))
               or {}).get(name) or {}
        for name in catalogue_spec.CATALOGUES})[0]
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
    # The settings lint names each removed catalog once, by its key (ADR-094).
    for key in ("approaches", "stages", "rules", "checks"):
        assert f"L-SETTING-REMOVED [project] {key}:" in out, (key, out)


@pytest.mark.parametrize("frozen", ["compass:default@6", "compass:default@7"])
def test_a_project_pinned_to_a_frozen_major_resolves_the_path_approaches(tmp_path, frozen):
    """Resolution reads only the live preset, whatever major `extends:` names (the
    owner's decision of 2026-10-30), and ADR-092 rejects a pinned frozen preset
    keeping its approaches. So such a project resolves the path, and its issues
    still check."""
    from compass_pkg import effective
    root = projects.project(tmp_path, compass_yml=dict(projects.BALANCED, extends=frozen))
    view = effective.effective_for(start=str(root))
    assert set(view.config["approaches"]) == {"delivery", "spike"}, frozen
    assert list(view.stage_order()) == ["assess", "specify", "build", "ship"], frozen
    done = projects.run(root, "check", "--issue", projects.SLUG)
    assert done.returncode in (0, 1), done.stdout + done.stderr
    assert "M-" not in done.stdout + done.stderr, done.stdout + done.stderr


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


# --- a reference to a legacy stage in a governance copy -----------------------------------


def test_a_copied_guardrail_checked_at_a_legacy_stage_is_read_at_its_path_stage():
    import legacy_copy
    # A copy of the 9.0.0 files declares only the path stages, so a project
    # guardrail it checks at `verify` names a stage the copy does not hold.
    doc = {"stages": {"assess": {"order": 1, "modes": {"thorough": {"rank": 3}}},
                      "ship": {"order": 4, "modes": {"thorough": {"rank": 3}}}},
           "gates": {"PG-A": {"kind": "guardrail", "stage": "verify",
                              "applies_to": {"ships": True}, "checks": []}}}
    config, _ = legacy_copy._legacy_config(doc)
    assert config["gates"]["PG-A"]["stage"] == "ship"
    # A copy made before 9.0.0 declares its legacy stages and is read as it is.
    old = dict(doc, stages=dict(doc["stages"], verify={"order": 3, "modes": {}}))
    config, _ = legacy_copy._legacy_config(old)
    assert config["gates"]["PG-A"]["stage"] == "verify"


