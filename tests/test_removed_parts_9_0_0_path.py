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
from types import SimpleNamespace

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


# --- the merge -------------------------------------------------------------------------

def _resolved_parent(folder=None):
    """The resolved shipped default, or with `folder` the frozen preset of that name."""
    from compass_pkg import merge, policy_lint
    parent = _parent() if folder is None else policy_lint.load_parent(
        directory=ROOT / "governance" / "presets" / folder)[0]
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
    # The shipped default no longer declares these parts (ADR-092); a frozen preset
    # does, and a parent or an issue layer over it still changes them.
    from compass_pkg import merge
    base = _resolved_parent("default@7")
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
    view = effective.view_or_legacy(start=str(root))
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


# --- an issue layer that sets a legacy stage (ADR-092 decision 10) ----------------------

def test_an_issue_layer_drops_a_legacy_stage_the_shipped_default_does_not_hold():
    from compass_pkg import merge, policy_lint
    from compass_pkg.layers import Layer
    base = _resolved_parent()
    doc = {"stages": {"define": {"set": {"mode": "collapsed"}},
                      "ship": {"set": {"mode": "thorough"}}}}
    config, _ = merge.apply(base, doc, "issue", "issue")
    assert "define" not in config["stages"]
    assert config["stages"]["ship"]["mode"] == "thorough"
    only = {"stages": {"define": {"set": {"mode": "collapsed"}}}}
    report = policy_lint.lint_chain(_parent(), None, Layer("issue", "issue", only, "d"))
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert [(f.layer, f.path) for f in found] == [("issue", "stages.define")], found
    assert not report.errors, report.errors


def test_an_old_issue_keeps_a_legacy_stage_its_configuration_holds():
    from compass_pkg import merge
    base = _resolved_parent("default@7")
    config, _ = merge.apply(base, {"stages": {"define": {"set": {"mode": "collapsed"}}}},
                            "issue", "issue")
    assert config["stages"]["define"]["mode"] == "collapsed"


# --- a reference to a legacy stage in a project or copied layer --------------------------

def _lint_findings(project_doc):
    from compass_pkg import policy_lint
    from compass_pkg.layers import Layer
    report = policy_lint.lint_chain(_parent(), Layer("project", "project",
                                                     {"schema": 1, **project_doc}, "d"))
    return report


def test_a_project_gate_at_a_legacy_stage_is_read_at_its_path_stage():
    from compass_pkg import merge
    doc = {"schema": 1, "gates": {"project.review": {
        "kind": "review", "stage": "verify", "accepts": ["test-run"]}}}
    config, _ = merge.apply(_resolved_parent(), doc, "project", "project")
    assert config["gates"]["project.review"]["stage"] == "ship"
    report = _lint_findings(doc)
    mapped = [f for f in report.findings if f.code == "L-STAGE-MAPPED"]
    assert [(f.path, f.level) for f in mapped] == [("gates.project.review.stage", "warning")]
    assert "verify" in mapped[0].message and "ship" in mapped[0].message
    assert not report.errors, report.errors


def test_a_copied_guardrail_checked_at_a_legacy_stage_is_read_at_its_path_stage():
    from compass_pkg import merge
    # A copy of the 9.0.0 files declares only the path stages, so a project
    # guardrail it checks at `verify` names a stage the copy does not hold.
    doc = {"stages": {"assess": {"order": 1, "modes": {"thorough": {"rank": 3}}},
                      "ship": {"order": 4, "modes": {"thorough": {"rank": 3}}}},
           "gates": {"PG-A": {"kind": "guardrail", "stage": "verify",
                              "applies_to": {"ships": True}, "checks": []}}}
    config, _ = merge.apply({}, doc, "parent", "legacy")
    assert config["gates"]["PG-A"]["stage"] == "ship"
    # A copy made before 9.0.0 declares its legacy stages and is read as it is.
    old = dict(doc, stages=dict(doc["stages"], verify={"order": 3, "modes": {}}))
    config, _ = merge.apply({}, old, "parent", "legacy")
    assert config["gates"]["PG-A"]["stage"] == "verify"


def test_a_project_that_restates_the_removed_require_phase_gets_a_warning():
    from compass_pkg import merge
    floor = {"order": 1, "when": {"familiarity": "brownfield-unmapped"},
             "then": {"require_phase": "define", "require_skill": "behavior-mapping"},
             "rationale": "The project restates the floor."}
    doc = {"schema": 1, "rules": {"floors": {"set": {"rules": {"set": {"RP-FLOOR-002": floor}}}}}}
    config, _ = merge.apply(_resolved_parent(), doc, "project", "project")
    then = config["rules"]["floors"]["rules"]["RP-FLOOR-002"]["then"]
    assert then == {"require_skill": "behavior-mapping"}
    report = _lint_findings(doc)
    codes = [(f.code, f.path) for f in report.findings]
    assert ("L-SETTING-REMOVED", "rules.floors.rules.RP-FLOOR-002.then.require_phase") in codes
    assert "M-HIT-MISSING" not in [c for c, _ in codes], codes


@pytest.mark.parametrize("major, warned", [("6", True), ("7", True), ("8", False)])
def test_lint_warns_that_a_frozen_major_is_not_loaded(major, warned):
    report = _lint_findings({"extends": f"compass:default@{major}"})
    found = [f for f in report.findings if f.code == "L-EXTENDS-FROZEN-MAJOR"]
    assert bool(found) == warned, report.findings
    if warned:
        assert found[0].level == "warning"
        assert "not loaded" in found[0].message and "compass:default@8" in found[0].message


def test_an_issue_layer_drops_an_approach_the_shipped_default_does_not_declare():
    from compass_pkg import merge, policy_lint
    from compass_pkg.layers import Layer
    config, _ = merge.apply(_resolved_parent(), {"approach": "full"}, "issue", "issue")
    assert "approach" not in config
    assessment = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
                  "goal": "delivery", "urgency": "none", "labels": []}
    report = policy_lint.lint_chain(_parent(), None,
                                    Layer("issue", "issue", {"approach": "full"}, "d"),
                                    assessment=assessment)
    found = [(f.code, f.layer, f.path) for f in report.findings
             if f.code == "L-SETTING-REMOVED"]
    assert found == [("L-SETTING-REMOVED", "issue", "approach")], report.findings
    assert not report.errors, report.errors


def test_an_old_issue_keeps_an_approach_its_configuration_declares():
    from compass_pkg import removed_parts
    held = _resolved_parent("default@7")
    assert removed_parts.unheld_stages({"approach": "full"}, held) == []
    assert removed_parts.without_unheld_stages({"approach": "full"}, held) == {"approach": "full"}
    # A name that is no approach at all is the layer's own fault and is not left out.
    assert removed_parts.unheld_stages({"approach": "nonesuch"}, _resolved_parent()) == []


# --- a git parent ----------------------------------------------------------------------

def test_the_shipped_preset_is_not_read_as_a_git_parent():
    """Only a project layer and a git parent drop what 9.0.0 removed; the shipped
    preset and a frozen preset keep their catalogue."""
    from compass_pkg import parents, removed_parts
    assert removed_parts.drops_removed("project", "project")
    assert removed_parts.drops_removed("parent", "github:acme/team@1.0.0#abcdef0")
    assert parents.ref_label(parents.GitSpec("acme", "team", "1.0.0", "a" * 40)) \
        .startswith(removed_parts.GIT_PARENT_SCHEME)
    for name in ("default", "default@7", "legacy", "preset", "parent"):
        assert not removed_parts.drops_removed("parent", name), name
    assert not removed_parts.drops_removed("issue", "issue")


# --- a lock on a removed key -----------------------------------------------------------

#: Locks on removed keys: a whole legacy stage, and the `delivery` approach, which the
#: live default still declares but a project or git parent can no longer change.
REMOVED_LOCKS = {"stages": {"verify": {"locked": "hard"}},
                 "approaches": {"delivery": {"set": {"locked": "hard"}}}}


@pytest.mark.parametrize("kind,name", [("project", "project"),
                                       ("parent", "github:acme/team@1.0.0#abcdef0")])
def test_a_lock_on_a_removed_key_is_not_held(kind, name):
    """The merge leaves a removed key out and lint says it is not read, so its lock must
    not be held or shown as the layer's lock either."""
    from compass_pkg import locks, policy_effective
    from compass_pkg.layers import Layer
    layer = Layer(name, kind, {"schema": 1, **REMOVED_LOCKS}, "d")
    held = locks.lock_set([_parent(), layer])
    assert not [entry for entry, lock in held.items() if lock.layer == name], held
    # The shipped default does not lock the delivery approach, so nothing holds it.
    assert "approaches.delivery" not in held and "stages.verify" not in held, held
    chain = dict(project=layer) if kind == "project" else dict(
        project=None, git_parents=[SimpleNamespace(layer=layer, version="1.0.0")])
    rows = policy_effective.resolve_effective(_parent(), **chain).rows
    shown = {row.path: row.source for row in rows if row.path.endswith(".locked")}
    assert "stages.verify.locked" not in shown and "approaches.delivery.locked" not in shown, \
        shown
    assert shown["approaches.spike.locked"].startswith("default"), shown


# --- a project rule that forces an approach --------------------------------------------

def _floor(then, hit=None):
    """A project layer that adds the floors rule `RP-PROJ-001` with `then`."""
    change = {"rules": {"set": {"RP-PROJ-001": {
        "order": 9, "when": {"risk": ["critical"]}, "then": then,
        "rationale": "Critical work runs at least the regular approach."}}}}
    if hit is not None:
        change["hit"] = hit
    return {"rules": {"floors": {"set": change}}}


FLOORS_HIT = {"require_skill": "collect", "add_gate": "collect",
              "force_minimum_approach": "max"}


@pytest.mark.parametrize("hit", [None, FLOORS_HIT], ids=["no-hit", "8.x-hit"])
@pytest.mark.parametrize("approach", ["regular", "delivery"])
def test_a_project_rule_that_forces_an_approach_is_dropped_and_named(hit, approach):
    """ADR-092 decision 10: no configuration's approach is read for a new assessment, so
    a project floor that forces one is left out with a warning. It must not stop lint
    with an unknown approach, a missing hit policy, a refused lock or C-INCOMPARABLE."""
    from compass_pkg import merge
    doc = _floor({"force_minimum_approach": approach}, hit)
    base = _resolved_parent()
    config, provenance = merge.apply(base, {"schema": 1, **doc}, "project", "project")
    assert config == base
    # The rest of an 8.x hit map restates the shipped one, so only it is written.
    written = [p for p, step in provenance.items() if step.get("layer") == "project"]
    assert written == (["rules.floors.hit"] if hit else []), written
    report = _lint_project(doc)
    assert not [(f.code, f.path) for f in report.findings if f.level == "error"], [
        (f.code, f.path, f.message) for f in report.findings if f.level == "error"]
    removed = sorted(f.path for f in report.findings if f.code == "L-SETTING-REMOVED")
    expected = ["rules.floors.rules.RP-PROJ-001.then.force_minimum_approach"]
    if hit:
        expected = ["rules.floors.hit.force_minimum_approach"] + expected
    assert removed == expected, report.findings
    assert all("ADR-092" in f.message for f in report.findings
               if f.code == "L-SETTING-REMOVED")


def test_a_project_rule_keeps_its_other_effects_beside_a_dropped_approach():
    from compass_pkg import merge
    doc = _floor({"force_minimum_approach": "full", "add_gate": "verify.architecture"})
    config, _ = merge.apply(_resolved_parent(), {"schema": 1, **doc}, "project", "project")
    assert config["rules"]["floors"]["rules"]["RP-PROJ-001"]["then"] == {
        "add_gate": "verify.architecture"}
    report = _lint_project(doc)
    assert not report.errors, report.errors
    assert [f.path for f in report.findings if f.code == "L-SETTING-REMOVED"] == [
        "rules.floors.rules.RP-PROJ-001.then.force_minimum_approach"]


def test_a_new_project_rule_set_of_approach_floors_is_dropped_whole():
    from compass_pkg import merge
    doc = {"rules": {"team_floors": {"kind": "floors",
                                     "hit": {"force_minimum_approach": "max"},
                                     "rules": {"T-1": {"order": 1, "when": {},
                                                       "then": {"forbid_approach": "spike"}}}}}}
    base = _resolved_parent()
    config, _ = merge.apply(base, {"schema": 1, **doc}, "project", "project")
    assert config == base
    report = _lint_project(doc)
    assert not report.errors, report.errors
