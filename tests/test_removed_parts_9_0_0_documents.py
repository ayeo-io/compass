"""What 9.0.0 removed with the required documents, and how an old record or call reads.

ADR-091 keeps one issue document, the acceptance criteria, and removes the
verbs, checks and settings that wrote or checked the others. A command line,
a project file or a stored record can still name one of them:

- a removed verb fails to parse, and the error names the removal with ADR-091;
- a removed `compass.yml` key or capability is read as before and
  `compass policy lint` names it;
- a stored generation that lists a removed check reports it as nothing to
  check, so no archived issue goes from pass to fail.

Issue: ayeo-io/compass-delivery#353 [Remove every required document except
the acceptance criteria].
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
from check_set_files import shipped  # noqa: E402
CLI = ROOT / "cli" / "compass"
# The 8.x presets, kept as test data (VD-055).
PRESETS = ROOT / "tests" / "fixtures" / "presets"
sys.path.insert(0, str(ROOT / "cli"))


def _run(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def _lint_project(layer):
    """The settings lint of a `compass.yml` that holds `layer`, as a report with
    `findings` and `errors`. 8.x linted it as a layer over the shipped parent;
    the removed settings are named the same way since ADR-094."""
    from types import SimpleNamespace
    from compass_pkg import check_set, settings_lint
    found = settings_lint.lint({"schema": 1, **layer}, check_set.resolved())
    return SimpleNamespace(findings=found, errors=[f for f in found if f.level == "error"])


# --- each removed part names its own decision record ------------------------------

def test_compass_analyze_names_its_removal_with_adr_091(tmp_path):
    proc = _run(["analyze", "--issue", "demo"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass analyze' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr
    assert "compass check runs the guardrails" in proc.stderr, proc.stderr
    assert "ADR-090" not in proc.stderr, proc.stderr


def test_compass_issue_receipt_names_its_removal_with_adr_091(tmp_path):
    proc = _run(["issue", "receipt", "--issue", "demo"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass issue receipt' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr
    assert ("compass approach show lists the issue's gates and compass check judges its "
            "evidence") in proc.stderr, proc.stderr


def test_a_verb_removed_with_the_stage_agents_still_names_adr_090():
    from compass_pkg import removed_parts
    line = removed_parts.line_for(["run", "demo"])
    assert "(ADR-090): Compass runs each issue in one session" in line, line


def test_a_removed_capability_turned_on_is_named_by_lint(monkeypatch):
    from compass_pkg import removed_parts
    monkeypatch.setitem(removed_parts.CAPABILITIES, "artifact-freshness",
                        ("whether a change to a document marks others stale", "ADR-091"))
    report = _lint_project({"capabilities": {"artifact-freshness": True}})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning"
    assert found[0].path == "capabilities.artifact-freshness"
    assert "removed in 9.0.0" in found[0].message and "ADR-091" in found[0].message


def test_a_removed_capability_left_off_gets_no_finding(monkeypatch):
    from compass_pkg import removed_parts
    monkeypatch.setitem(removed_parts.CAPABILITIES, "artifact-freshness",
                        ("whether a change to a document marks others stale", "ADR-091"))
    report = _lint_project({"capabilities": {"artifact-freshness": False}})
    assert not [f for f in report.findings if f.code == "L-SETTING-REMOVED"]


# --- consistency-check-passes, the check of compass analyze -------------------------

def test_consistency_check_passes_is_removed_with_no_replacement():
    from compass_pkg.check_registry import REGISTRY, REMOVED
    removed = REMOVED["consistency-check-passes"]
    assert "consistency-check-passes" not in REGISTRY
    assert removed.removed_in == "9.0.0" and removed.replaced_by is None
    assert removed.detail.startswith("nothing to check")
    assert "runs in its place" not in removed.detail


def test_a_stored_generation_that_lists_consistency_check_passes_gains_nothing():
    from compass_pkg.check_cmd import _with_replacements
    names = ["gate-evidence-present", "consistency-check-passes"]
    assert _with_replacements(names, {}) == names


def test_the_live_default_has_no_verify_analyze_gate_or_rule():
    gates = shipped("gates.yml")["gates"]
    assert "verify.analyze" not in gates
    rules = str(shipped("rules.yml"))
    assert "verify.analyze" not in rules
    assert "RP-REQUIRE-001" not in rules and "RP-REQUIRE-002" not in rules
    checks = shipped("checks.yml")["checks"]
    assert "consistency-check-passes" not in checks
    # An old manifest can still hold consistency-check evidence, so the type stays.
    types = shipped("evidence-types.yml")
    assert "consistency-check" in types["evidence_types"]


def test_the_retired_spelling_of_consistency_check_passes_reads_as_removed():
    # A guardrails.yml written before ADR-023 names this check by its old spelling.
    from compass_pkg.check_cmd import _removed_entry
    removed = _removed_entry("coherence-check-passes", "coherence-check-passes")
    assert removed is not None and removed.replaced_by is None
    assert _removed_entry("suite-passed", "suite-passed") is None


# --- verify.analyze, the gate of compass analyze ------------------------------------
#
# A frozen preset (default@6, default@7), a stored generation and copied 5.6.0 governance
# still hold `RP-REQUIRE-001` and `RP-REQUIRE-002`, which add `verify.analyze`. Nothing can
# clear that gate now, so routing leaves it out, and a rule whose only effect was to add
# it does not fire.

G5_LABEL = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
            "goal": "delivery", "labels": ["auth"]}
CRITICAL = {"risk": "critical", "familiarity": "brownfield-mapped", "size": "medium",
            "goal": "delivery", "labels": []}


def _default_6_policy():
    """The frozen `default@6` preset, in the evaluator's form: its catalogues
    read through the retired-word tables, as a stored generation is read."""
    from compass_pkg import catalogue_spec, word_map
    from compass_pkg.obligations import policy_adapter
    folder = ROOT / "tests" / "fixtures" / "presets" / "default@6"
    config = word_map.map_layer({
        name: (yaml.safe_load((folder / f"{name}.yml").read_text(encoding="utf-8"))
               or {}).get(name) or {}
        for name in catalogue_spec.CATALOGUES})[0]
    return policy_adapter(config)


def _route_on_default_6(assessment):
    from compass_pkg.routing import evaluate_route
    return evaluate_route(dict(assessment), _default_6_policy())


@pytest.mark.parametrize("assessment,kept", [(G5_LABEL, "RP-REQUIRE-004"),
                                             (CRITICAL, "RP-REQUIRE-003")],
                         ids=["auth-label", "risk-critical"])
def test_an_issue_routed_on_default_6_gets_no_verify_analyze(assessment, kept):
    result = _route_on_default_6(assessment)
    fired = [f["id"] for f in result["policy_rules_fired"]]
    assert "verify.analyze" not in result["gates"], result["gates"]
    assert "RP-REQUIRE-001" not in fired and "RP-REQUIRE-002" not in fired, fired
    # The rules beside them still fire and still add their own gates.
    assert kept in fired, fired
    assert "verify.architecture" in result["gates"], result["gates"]


def test_a_rule_that_adds_a_removed_gate_and_does_more_still_fires():
    from compass_pkg.routing import evaluate_route
    policy = _default_6_policy()
    for floor in policy["routing_guardrails"]["floors"]:
        if floor.get("id") == "RP-REQUIRE-002":
            floor["require_skill"] = "threat-modeling"
    result = evaluate_route(dict(G5_LABEL), policy)
    fired = {f["id"]: f["changed"] for f in result["policy_rules_fired"]}
    assert fired["RP-REQUIRE-002"] == ["skill 'threat-modeling' required"], fired
    assert "verify.analyze" not in result["gates"]


def _issue_with_the_5_6_0_governance(tmp_path, labels=("auth",)):
    sys.path.insert(0, str(ROOT / "tests"))
    import compat_baseline
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "demo"
    task_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    compat_baseline.add_governance_copy(root)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "demo", "created": "2026-11-04",
        "assessment": dict(G5_LABEL, labels=list(labels))}, sort_keys=False),
        encoding="utf-8")
    return root, task_dir


def test_approach_evaluate_writes_no_verify_analyze_from_copied_governance(tmp_path):
    root, task_dir = _issue_with_the_5_6_0_governance(tmp_path)
    proc = _run(["approach", "evaluate", "--issue", "demo", "--write", "--verbose",
                 *[f"--justify={d}=test" for d in ("risk", "familiarity", "size", "goal")]],
                root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "verify.analyze" not in proc.stdout, proc.stdout
    assert "RP-REQUIRE-002" not in proc.stdout, proc.stdout
    body = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    gates = [g["id"] for g in body["gates"]]
    fired = [f["id"] for f in body["policy_rules_fired"]]
    assert "verify.analyze" not in gates and "verify.architecture" in gates, gates
    assert "RP-REQUIRE-002" not in fired and "RP-REQUIRE-004" in fired, fired
    # On the four-stage path (ADR-092) the architecture review is owed evidence.
    assert "architecture" in body["evidence_required"], body["evidence_required"]


# A manifest written before 9.0.0 can still list `verify.analyze` as pending. It is not
# rewritten; it owes nothing, so it does not keep the issue from landing.

def _gates(pending_analyze=True):
    gates = [{"id": "verify.correctness", "status": "pass", "evidence": []}]
    if pending_analyze:
        gates.append({"id": "verify.analyze", "status": "pending", "evidence": []})
    return gates


def test_ship_commit_marks_done_over_a_stored_pending_verify_analyze(cli_path, tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _completed, _git, _init_repo, _open_issue
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "old-issue")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    body["gates"] = _gates()
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    _git(repo, "add", "--", ".compass/work/old-issue/manifest.yml")
    proc = subprocess.run([sys.executable, str(cli_path), "ship-commit", "-m", "land",
                           "--issue", "old-issue"], cwd=repo, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "NOT marked done" not in proc.stdout, proc.stdout
    body = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert _completed(body), body
    # The stored gate is kept as it was: an archived record is not rewritten.
    assert {"id": "verify.analyze", "status": "pending", "evidence": []} in body["gates"]


def test_ship_commit_still_refuses_over_another_pending_gate(cli_path, tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _git, _init_repo, _open_issue
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "old-issue")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    body["gates"] = _gates() + [{"id": "verify.regression", "status": "pending",
                                 "evidence": []}]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    _git(repo, "add", "--", ".compass/work/old-issue/manifest.yml")
    proc = subprocess.run([sys.executable, str(cli_path), "ship-commit", "-m", "land",
                           "--issue", "old-issue"], cwd=repo, capture_output=True,
                          text=True, timeout=60)
    assert "NOT marked done: 1 gate(s) have not passed (verify.regression)" in proc.stdout, \
        proc.stdout


def test_status_set_completes_over_a_stored_pending_verify_analyze(tmp_path):
    from compass_pkg import status_cmd
    task = {"issue": "old-issue", "gates": _gates()}
    assert status_cmd._unmet_gates(task) == []
    task["gates"].append({"id": "verify.regression", "status": "pending"})
    assert status_cmd._unmet_gates(task) == ["verify.regression"]


# --- the living spec ----------------------------------------------------------------
#
# 9.0.0 derives no living spec. An older branch or tag can still hold the file,
# and a project's compass.yml can still hold `living_spec`.

def test_compass_spec_sync_names_its_removal_with_adr_091(tmp_path):
    proc = _run(["spec", "sync"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass spec sync' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr
    assert "Compass needs only the acceptance criteria" in proc.stderr, proc.stderr


def test_the_private_spec_derivation_names_its_removal_with_adr_091(tmp_path):
    proc = _run(["_derive-system-spec", "--internal"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass _derive-system-spec' was removed in 9.0.0 (ADR-091)" in proc.stderr, \
        proc.stderr


@pytest.mark.parametrize("value", ["land", "refresh"])
def test_the_living_spec_setting_is_read_and_lint_names_it(value):
    report = _lint_project({"living_spec": value})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning" and found[0].path == "living_spec"
    assert "removed in 9.0.0" in found[0].message and "ADR-091" in found[0].message
    assert not [f for f in report.findings if f.level == "error"], report.findings


def test_a_project_that_sets_living_spec_still_reads_its_settings(tmp_path):
    from compass_pkg import project_settings
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text("schema: 1\nowner: someone\nliving_spec: refresh\n",
                                          encoding="utf-8")
    assert project_settings.settings(str(tmp_path)).get("owner") == "someone"


def test_ship_commit_lands_an_issue_and_writes_no_living_spec(cli_path, tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _completed, _git, _init_repo, _open_issue
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "lands-alone")
    before = _git(repo, "rev-parse", "HEAD").stdout.strip()
    proc = subprocess.run([sys.executable, str(cli_path), "ship-commit", "-m", "land it",
                           "--issue", "lands-alone"], cwd=repo, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _completed(yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8")))
    assert not (repo / "docs" / "system-spec.md").exists()
    assert not (repo / "docs" / "system-spec-archive.md").exists()
    subjects = _git(repo, "log", "--format=%s", f"{before}..HEAD").stdout.split("\n")
    assert [s for s in subjects if s] == ["land it"], subjects
    assert "living spec" not in proc.stdout, proc.stdout


# --- artifact freshness ---------------------------------------------------------------
#
# 9.0.0 reads no capability `artifact-freshness`. A frozen preset and a stored generation
# still declare it, so it stays valid; a project that turns it on is told it is removed.

def test_artifact_freshness_turned_on_is_named_by_lint():
    report = _lint_project({"capabilities": {"artifact-freshness": True}})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert len(found) == 1, [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning"
    assert found[0].path == "capabilities.artifact-freshness"
    assert "removed in 9.0.0" in found[0].message and "ADR-091" in found[0].message
    assert not [f for f in report.findings if f.level == "error"], report.findings


def test_artifact_freshness_left_off_gets_no_finding():
    report = _lint_project({"capabilities": {"artifact-freshness": False}})
    assert not [f for f in report.findings if f.code == "L-SETTING-REMOVED"]


def test_the_live_default_declares_no_artifact_freshness():
    preset = shipped("preset.yml")
    assert "artifact-freshness" not in (preset.get("capabilities") or {}), preset
    # An 8.x preset declares it, as a stored generation does, so the catalogue
    # keeps the name valid.
    from compass_pkg import catalogue_spec
    assert "artifact-freshness" in catalogue_spec.CAPABILITIES
    for frozen in ("default@6", "default@7"):
        old = yaml.safe_load((PRESETS / frozen / "preset.yml").read_text(encoding="utf-8"))
        assert "artifact-freshness" in old["capabilities"], frozen


def test_check_runs_no_freshness_pass_with_artifact_freshness_on(tmp_path):
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "demo"
    task_dir.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / "compass.yml").write_text(
        "schema: 1\ncapabilities:\n  artifact-freshness: true\n",
        encoding="utf-8")
    spec = root / "docs" / "compass" / "2026-11-04-demo" / "acceptance-criteria.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("# Acceptance criteria\n", encoding="utf-8")
    # A document whose recorded upstream digest no longer matches: stale, had the pass run.
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "demo", "created": "2026-11-04",
        "delivery_approach": "regular", "gates": [],
        "artifacts": [{"kind": "technical-design", "status": "draft",
                       "upstream": {"acceptance-criteria": "0" * 64}}]},
        sort_keys=False), encoding="utf-8")
    proc = _run(["check", "--issue", "demo", "--json"], root)
    # The run judges the issue: every other guardrail still reports.
    assert "scenarios-have-tests" in proc.stdout, proc.stdout + proc.stderr
    assert "artifact-freshness" not in proc.stdout, proc.stdout
    assert "freshness" not in proc.stdout, proc.stdout
    assert "Traceback" not in proc.stderr, proc.stderr


# --- rendered blocks, the issue page and the project index ---------------------------
#
# 9.0.0 renders nothing (ADR-091). No command writes an issue page, a project index or
# a block, and a stored generation that lists the check of the blocks gains nothing.

def test_compass_issue_render_names_its_removal_with_adr_091(tmp_path):
    proc = _run(["issue", "render", "--all"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass issue render' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr


def test_compass_plan_lint_names_its_removal_with_adr_091(tmp_path):
    """`compass plan lint` scanned the technical design, which 9.0.0 no longer writes."""
    proc = _run(["plan", "lint", "--issue", "demo"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass plan lint' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr
    assert "no technical design is written" in proc.stderr, proc.stderr

def test_compass_issue_template_show_names_its_removal_with_adr_091(tmp_path):
    """`compass issue template show` printed the skeleton of a document kind; 9.0.0
    keeps one document, whose template is `templates/acceptance-criteria.md`."""
    proc = _run(["issue", "template", "show", "acceptance-criteria"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "'compass issue template show' was removed in 9.0.0 (ADR-091)" in proc.stderr, \
        proc.stderr
    assert "templates/acceptance-criteria.md" in proc.stderr, proc.stderr


def test_a_landing_reads_no_technical_design():
    """A landing refused a project-scoped design decision with no decision record
    (ADR-072). 9.0.0 writes no technical design, so no landing refusal reads one and
    the refusal code is gone."""
    from compass_pkg import manifest, refusals
    names = {fn.__module__ for fn in manifest.LANDING_REFUSALS}
    assert "compass_pkg.decision_scope" not in names, names
    assert "project-decision-unrecorded" not in refusals.codes()

def test_rendered_blocks_current_is_removed_with_no_replacement():
    from compass_pkg.check_registry import REGISTRY, REMOVED
    removed = REMOVED["rendered-blocks-current"]
    assert "rendered-blocks-current" not in REGISTRY
    assert removed.removed_in == "9.0.0" and removed.replaced_by is None
    assert "runs in its place" not in removed.detail


def test_dashboard_current_names_no_replacement_once_its_replacement_is_removed():
    from compass_pkg.check_registry import REMOVED
    removed = REMOVED["dashboard-current"]
    assert removed.removed_in == "7.0.0" and removed.replaced_by is None
    assert "rendered-blocks-current" not in removed.detail


def test_a_stored_generation_that_lists_rendered_blocks_current_gains_nothing():
    from compass_pkg.check_cmd import _with_replacements
    names = ["gate-evidence-present", "rendered-blocks-current", "dashboard-current"]
    assert _with_replacements(names, {}) == names


def test_the_live_default_has_no_rendered_blocks_check():
    checks = shipped("checks.yml")["checks"]
    assert "rendered-blocks-current" not in checks
    gates = shipped("gates.yml")["gates"]
    assert "rendered-blocks-current" not in gates["G4"]["checks"]


@pytest.mark.parametrize("value", [True, False])
def test_the_github_page_switch_is_read_and_lint_names_it_when_on(value):
    report = _lint_project({"github_labels": {"domain": True, "page": value}})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    # The whole key went with the label sync (ADR-093). Lint names it once: by the
    # page switch when that is on, so the ADR-091 note stays, and by the key otherwise.
    if value:
        assert len(found) == 1 and found[0].path == "github_labels.page", found
        assert "ADR-091" in found[0].message
    else:
        assert len(found) == 1 and found[0].path == "github_labels", found
        assert "ADR-093" in found[0].message
    assert not [f for f in report.findings if f.level == "error"], report.findings


def test_ship_commit_writes_no_issue_page_and_no_project_index(cli_path, tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _completed, _init_repo, _open_issue
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "no-page")
    proc = subprocess.run([sys.executable, str(cli_path), "ship-commit", "-m", "land it",
                           "--issue", "no-page"], cwd=repo, capture_output=True,
                          text=True, timeout=60)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _completed(yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8")))
    docs = repo / "docs" / "compass"
    assert not (docs / "README.md").exists()
    assert not list(docs.glob("*/README.md")) if docs.is_dir() else True


def test_compass_next_reads_the_approach_from_the_manifest(tmp_path):
    """9.0.0 writes no delivery-approach.md (ADR-091): the manifest holds the decision, so
    `compass next` answers for an assessed issue that has no such file, and still refuses
    an issue whose manifest records no approach."""
    sys.path.insert(0, str(ROOT / "tests"))
    from acceptance.atdd_strategy import support
    project = support.Project(tmp_path / "repo")
    issue = project.issue("orders")
    assert issue.assess()[0] == 0
    assert not list((project.root / "docs").rglob("delivery-approach.md"))
    code, out, err = issue.run("next", "--issue", "orders")
    assert code == 0, out + err
    body = issue.manifest()
    body.pop("delivery_approach")
    issue.write_manifest(body)
    code, out, err = issue.run("next", "--issue", "orders")
    assert code != 0 and "assess" in err, out + err


def test_a_hint_to_a_removed_verb_says_the_replacement_went_too():
    """`issue dashboard` became `issue render` at 7.0.0, and 9.0.0 removes that too
    (ADR-091), so the hint names both removals rather than a verb that does not exist."""
    from compass_pkg.aliases import hint_for
    line = hint_for(["issue", "dashboard", "render"])
    assert "'issue dashboard' is now 'issue render'" in line, line
    assert "removed in 9.0.0 (ADR-091)" in line, line
    # `issue github sync` went with the label sync (ADR-093).
    assert hint_for(["issue", "labels", "sync"]) == (
        "'issue labels sync' is now 'issue github sync', which was removed in 9.0.0 (ADR-093).")


# --- the checks that read a removed document ------------------------------------------
#
# 9.0.0 removes four checks with the documents they read (ADR-091). A frozen preset
# still declares them, so an issue assessed on one reports each as nothing to check.

DOCUMENT_CHECKS = ("artifacts-approved", "design-within-word-ceiling", "contracts-declared",
                   "borrowed-documents-answered")


@pytest.mark.parametrize("check", DOCUMENT_CHECKS)
def test_a_document_check_is_removed_with_no_replacement(check):
    from compass_pkg.check_registry import REGISTRY, REMOVED
    assert check not in REGISTRY
    assert REMOVED[check].removed_in == "9.0.0" and REMOVED[check].replaced_by is None


def test_the_live_default_declares_no_document_check():
    checks = shipped("checks.yml")["checks"]
    gates = shipped("gates.yml")["gates"]
    for check in DOCUMENT_CHECKS:
        assert check not in checks, check
        assert check not in gates["G4"]["checks"], check


def test_a_stored_configuration_that_declares_a_removed_outside_check_reports_nothing():
    """A stored generation of an archived issue still declares the removed checks that sit
    in no gate, so `compass check` keeps their row and reports nothing to check."""
    from compass_pkg import outside_gate
    from compass_pkg.check_cmd import _removed_fn
    from compass_pkg.check_results import NOTHING_TO_CHECK
    for check in ("artifacts-approved", "design-within-word-ceiling", "contracts-declared"):
        assert check in outside_gate.CHECKS, check
        passed, detail = _removed_fn(check)({}, ".")
        assert passed is NOTHING_TO_CHECK and "removed in 9.0.0" in detail, detail


# --- the spike decision ---------------------------------------------------------------
#
# 9.0.0 removes `compass issue artifact set`, which wrote the spike's decision (ADR-091).
# `compass evidence add --type spike-conclusion --decision` writes it now, so
# `spike-conclusion-present` keeps a writer.

def _spike(tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from acceptance.atdd_strategy import support
    project = support.Project(tmp_path / "repo")
    issue = support.spike_issue(project)
    (issue.dir / "evidence").mkdir(exist_ok=True)
    (issue.dir / "evidence" / "spike.md").write_text("# What we learned\n", encoding="utf-8")
    return issue


def test_evidence_add_records_the_spike_decision(tmp_path):
    issue = _spike(tmp_path)
    code, out, err = issue.run("evidence", "add", "EV-SPIKE", "--issue", issue.slug,
                               "--type", "spike-conclusion", "--path", "evidence/spike.md",
                               "--decision", "graduate-to-delivery", "--next-issue", "the-feature")
    assert code == 0, out + err
    record = next(e for e in issue.manifest()["evidence"] if e["id"] == "EV-SPIKE")
    assert record["decision"] == "graduate-to-delivery" and record["next_task"] == "the-feature"
    from compass_pkg.checks import _check_spike_conclusion_present
    assert _check_spike_conclusion_present(issue.manifest(), str(issue.dir))[0] is True


@pytest.mark.parametrize("extra, words", [
    (["--decision", "graduate-to-delivery"], "--next-issue"),
    (["--decision", "keep"], "discard"),
    (["--next-issue", "x"], "--decision"),
])
def test_evidence_add_refuses_a_spike_decision_that_cannot_close_it(tmp_path, extra, words):
    issue = _spike(tmp_path)
    before = (issue.dir / "manifest.yml").read_bytes()
    code, out, err = issue.run("evidence", "add", "EV-SPIKE", "--issue", issue.slug,
                               "--type", "spike-conclusion", "--path", "evidence/spike.md", *extra)
    assert code == 2 and words in err, out + err
    assert (issue.dir / "manifest.yml").read_bytes() == before


def test_a_decision_on_another_evidence_type_is_refused(tmp_path):
    issue = _spike(tmp_path)
    code, out, err = issue.run("evidence", "add", "EV-N", "--issue", issue.slug,
                               "--type", "artifact", "--path", "evidence/spike.md",
                               "--decision", "discard")
    assert code == 2 and "spike-conclusion" in err, out + err


# --- document registration and status ---------------------------------------------------
#
# 9.0.0 registers no document and gives none a status (ADR-091): the verbs that set and
# read one are removed, routing writes no `artifacts:` list, and no stage record moves a
# document on. A manifest an older release wrote keeps its list as it is.

@pytest.mark.parametrize("argv, name", [
    (["issue", "artifact", "set", "technical-design", "--status", "draft"],
     "compass issue artifact set"),
    (["issue", "artifact-path", "delivery-approach"], "compass issue artifact-path"),
    (["evidence", "approve", "--artifact", "technical-design", "--approver", "jed"],
     "compass evidence approve --artifact"),
    (["evidence", "request", "--artifact", "technical-design"],
     "compass evidence request --artifact"),
])
def test_a_document_status_verb_names_its_removal_with_adr_091(tmp_path, argv, name):
    proc = _run([*argv, "--issue", "demo"], tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert f"'{name}' was removed in 9.0.0 (ADR-091)" in proc.stderr, proc.stderr


def _assessed(tmp_path, approach="regular"):
    """An issue assessed on the four-stage path (ADR-092)."""
    sys.path.insert(0, str(ROOT / "tests"))
    from acceptance.atdd_strategy import support
    project = support.Project(tmp_path / "repo")
    issue = project.issue("orders", approach=approach)
    code, out, err = issue.assess()
    assert code == 0, out + err
    assert issue.manifest()["evidence_required"], issue.manifest()
    return issue


#: A registry an older release wrote: one document approved, one still a draft.
OLD_REGISTRY = [
    {"id": "ART-SPEC", "kind": "acceptance-criteria", "status": "approved",
     "depth": "lightweight", "path": "docs/compass/2026-10-01-orders/acceptance-criteria.md",
     "approved_by": "jed72", "approved_at": "2026-10-02T09:00:00Z"},
    {"id": "ART-DESIGN", "kind": "technical-design", "status": "draft",
     "depth": "lightweight", "path": "docs/compass/2026-10-01-orders/technical-design.md"},
]


def test_approach_evaluate_writes_no_document_registry(tmp_path):
    issue = _assessed(tmp_path)
    assert "artifacts" not in issue.manifest(), issue.manifest().get("artifacts")


def test_a_reassessment_keeps_an_older_registry_as_it_is(tmp_path):
    issue = _assessed(tmp_path)
    body = issue.manifest()
    body["artifacts"] = [dict(entry) for entry in OLD_REGISTRY]
    issue.write_manifest(body)
    code, out, err = issue.run("approach", "evaluate", "--issue", issue.slug, "--write",
                               "--reason", "the size changed",
                               "--justify", "size=Test fixture: the size was judged.")
    assert code == 0, out + err
    assert issue.manifest()["artifacts"] == OLD_REGISTRY


def test_a_stage_record_moves_no_document_on(tmp_path):
    issue = _assessed(tmp_path)
    body = issue.manifest()
    body["artifacts"] = [dict(entry) for entry in OLD_REGISTRY]
    issue.write_manifest(body)
    code, out, err = issue.run("tdd-red", "--issue", issue.slug, "--", "sh", "-c",
                               "echo 'test_one FAILED'; exit 1")
    assert code == 0, out + err
    assert issue.manifest()["artifacts"] == OLD_REGISTRY
    assert "moved" not in out, out


# --- the Definition of Ready and Done with no catalogue -----------------------------------
#
# Before 9.0.0 an approach owed the Definition of Ready when its `artifacts:` map listed the
# requirements review, and the Definition of Done when it listed the verification report.
# 9.0.0 drops the map (ADR-091): the Definition of Ready applies where the refine stage is
# lightweight or thorough, and the Definition of Done where `verify` is thorough. A stored
# configuration that still declares the map is read as before.

def _live_approaches():
    return shipped("approaches.yml")["approaches"]


def test_the_stage_modes_owe_the_lists_the_live_approaches_owed():
    from compass_pkg import stage_lists
    for name, approach in _live_approaches().items():
        listed = set(approach.get("artifacts") or {}) & set(stage_lists.CHECKLIST_DOCUMENTS.values())
        if "artifacts" not in approach:
            continue
        assert stage_lists.owed_by_stages(approach["stages"]) == listed, name


@pytest.mark.parametrize("modes, owed", [
    ({"refine": "lightweight", "verify": "thorough"}, {"requirements-review", "verification-report"}),
    ({"refine": "thorough", "verify": "thorough"}, {"requirements-review", "verification-report"}),
    ({"refine": "collapsed", "verify": "thorough"}, {"verification-report"}),
    ({"refine": "collapsed", "verify": "lightweight"}, set()),
    ({"refine": "skipped", "verify": "conclude"}, set()),
    # A manifest written before the depth words were renamed stores the old words.
    ({"refine": "light", "verify": "full"}, {"requirements-review", "verification-report"}),
    ({"refine": "full", "verify": "light"}, {"requirements-review"}),
])
def test_an_approach_with_no_catalogue_owes_the_lists_by_its_stages(modes, owed):
    from compass_pkg import stage_lists
    assert stage_lists.owes("regular", {"stages": {}}, modes) == ("regular", owed)


def test_a_stored_approach_that_declares_the_map_is_read_as_before():
    from compass_pkg import stage_lists
    approach = {"artifacts": {"verification-report": "thorough"}}
    modes = {"refine": "lightweight", "verify": "thorough"}
    assert stage_lists.owes("hotfix", approach, modes) == ("hotfix", {"verification-report"})


# --- documents on disk are not read ----------------------------------------------
# An artifact rule (`when: {artifacts_any: [...]}`) fired on a document found on disk
# (ADR-070). 9.0.0 checks one document, so no command reads which documents an issue
# has: a positioning.md brings no gate, and a landing refuses nothing for it.

def _positioned_issue(tmp_path):
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nautonomy: balanced\n", encoding="utf-8")
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "3.0", "issue": "t", "created": "2026-10-16",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "medium", "goal": "delivery", "urgency": "none",
                       "labels": []}}, sort_keys=False),
        encoding="utf-8")
    doc = root / "docs" / "compass" / "2026-10-16-t" / "positioning.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# positioning\n", encoding="utf-8")
    return root, task_dir


def test_a_document_on_disk_brings_no_gate(tmp_path):
    import json
    root, _ = _positioned_issue(tmp_path)
    proc = _run(["approach", "evaluate", "--issue", "t", "--json"], root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    result = json.loads(proc.stdout)
    assert "verify.claims" not in result["gates"], result["gates"]
    assert "RP-ART-001" not in [f["id"] for f in result["policy_rules_fired"]]


def test_the_documents_on_disk_are_not_a_reading():
    import importlib
    with pytest.raises(ImportError):
        importlib.import_module("compass_pkg.documents_present")


def test_a_landing_refuses_nothing_for_a_document_on_disk():
    from compass_pkg import manifest, refusals
    names = {fn.__module__ for fn in manifest.LANDING_REFUSALS}
    assert "compass_pkg.documents_present" not in names, names
    assert "artifact-rule-not-applied" not in refusals.codes()


# --- the live default declares no artifact catalogue -----------------------------

def test_the_live_default_declares_no_artifact_catalogue():
    catalogue = shipped("artifacts.yml")
    assert catalogue["artifacts"] == {}, sorted(catalogue["artifacts"])
    for name, approach in _live_approaches().items():
        assert "artifacts" not in approach, name
    rules = shipped("rules.yml")["rules"]
    assert "artifact_rules" not in rules
    found = [rid for rule_set in rules.values() for rid, rule in rule_set["rules"].items()
             if "add_artifact" in (rule.get("then") or {})]
    assert found == [], found


def test_the_generated_views_hold_no_artifact_rule_or_map():
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text(
        encoding="utf-8"))
    assert "artifact_rules" not in policy["routing_guardrails"]
    for name, shape in policy["route_shapes"].items():
        assert "artifacts" not in shape, name


def test_a_project_artifacts_key_is_named_by_lint():
    report = _lint_project({"artifacts": {"runbook": {"file": "runbook.md"}}})
    found = [f for f in report.findings if f.code == "L-SETTING-REMOVED"]
    assert [f.path for f in found] == ["artifacts"], [(f.code, f.path) for f in report.findings]
    assert found[0].level == "warning"
    assert "removed in 9.0.0" in found[0].message and "ADR-091" in found[0].message


def test_a_stored_entry_is_filled_from_the_last_shipped_catalogue():
    from compass_pkg import artifact_kinds
    assert "acceptance-criteria" in artifact_kinds.shipped()


class _View:
    def __init__(self, config):
        self.config = config


@pytest.mark.parametrize("catalogue", [{}, None])
def test_the_spec_section_is_listed_by_the_last_shipped_catalogue(monkeypatch, catalogue):
    """A generation stored on the live default declares no catalogue, so the
    Non-functional requirements section is read from the last shipped one, and
    nfr-rows-resolved still judges the spec."""
    from compass_pkg import effective, section_checks
    config = {} if catalogue is None else {"artifacts": catalogue}
    monkeypatch.setattr(effective, "view_or_legacy", lambda task_dir: _View(config))
    for depth in ("thorough", "lightweight"):
        assert section_checks._listed("t", "acceptance-criteria", depth,
                                      section_checks.NFR_HEADING), depth


def test_a_catalogue_that_declares_the_spec_is_still_read_by_its_own_entry(monkeypatch):
    from compass_pkg import effective, section_checks
    own = {"artifacts": {"acceptance-criteria": {"file": "acceptance-criteria.md",
                                                 "sections": {"thorough": ["Summary"]}}}}
    monkeypatch.setattr(effective, "view_or_legacy", lambda task_dir: _View(own))
    assert not section_checks._listed("t", "acceptance-criteria", "thorough",
                                      section_checks.NFR_HEADING)


