"""Role is no longer an assessment dimension (ayeo-io/compass-delivery-record#149).

The two blocking role rules became artifact rules keyed on the documents the
CLI finds on disk, the full approach stopped building in the claims gate, and
6.x records, configurations and CLI calls keep working. ADR-070 records the
decision; docs/upgrade-7-0-0.md tells an adopter what changes.

Each test is named by the scenario of the issue `remove-role-from-assessment`
that it checks, in the order of that issue's acceptance criteria.
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import classify, merge, obligations  # noqa: E402
from compass_pkg import catalogue_spec  # noqa: E402
from compass_pkg.routing import evaluate_route  # noqa: E402

PRESET = ROOT / "governance" / "presets" / "default"
VIEW = ROOT / "governance" / "routing-policy.yml"
NOT_READ = "role is no longer an assessment dimension"


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _preset_config():
    parts = []
    for name in catalogue_spec.CATALOGUES:
        part = _load(PRESET / f"{name}.yml")
        parts.append({k: v for k, v in part.items() if k != "schema"})
    config, _ = merge.apply({}, {"schema": 1, **merge.combine(parts)}, "parent", "default")
    return config


def _policy():
    return obligations.policy_adapter(_preset_config())


def _assess(**kw):
    base = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
            "goal": "delivery", "urgency": "none", "labels": []}
    base.update(kw)
    return base


def _fired(result):
    return [f["id"] for f in result["policy_rules_fired"]]


def _blocks(result):
    return {b["phase"]: b["until"] for b in result["blocked_phases"]}


def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "COMPASS_RENDER_AFTER": "0"}


def _run(root, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=root, env=_env(root),
                       capture_output=True, text=True, timeout=120,
                       stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout, r.stderr


ALL_REASONS = ["--justify", "risk=r", "--justify", "familiarity=f", "--justify", "size=s",
               "--justify", "goal=g", "--justify", "urgency=u"]


def _project(tmp_path, slug="t", assessment=None, compass_yml=True):
    root = tmp_path / "proj"
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    if compass_yml:
        (root / "compass.yml").write_text(
            "schema: 1\nextends: compass:default@6\nautonomy: balanced\n", encoding="utf-8")
    manifest = {"schema_version": "3.0", "issue": slug, "created": "2026-10-16",
                "assessment": assessment or _assess()}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    return root, task_dir


def _write_doc(root, slug, kind, register=True, exists=True):
    """Put a document of `kind` at its home and register it, as the role entry
    points do."""
    rel = f"docs/compass/2026-10-16-{slug}/{kind}.md"
    if exists:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"# {kind}\n", encoding="utf-8")
    if register:
        path = root / ".compass" / "work" / slug / "manifest.yml"
        data = _load(path)
        data.setdefault("artifacts", []).append(
            {"id": "ART-" + kind.upper(), "kind": kind, "status": "draft", "path": rel})
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return rel


# --- group A: the shipped vocabulary and the evaluator ----------------------------

def test_trc_a1_the_shipped_default_declares_no_role_dimension():
    dims = _load(PRESET / "dimensions.yml")["dimensions"]
    assert "role" not in dims
    assert list(dims) == ["risk", "familiarity", "size", "goal", "urgency", "labels"]
    view = _load(VIEW)
    assert "role" not in view["assessment_vocabulary"]
    assert "role" not in _policy()["assessment_vocabulary"]


def _whens(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "when" and isinstance(value, dict):
                yield value
            yield from _whens(value)
    elif isinstance(node, list):
        for item in node:
            yield from _whens(item)


def test_trc_a2_the_shipped_rules_hold_no_role_rule_default_or_bias():
    rules = _load(PRESET / "rules.yml")["rules"]
    assert all(s.get("kind") != "role-rules" for s in rules.values())
    assert "role_rules" not in rules and "role_defaults" not in rules
    view = _load(VIEW)
    assert "role_rules" not in view["routing_guardrails"]
    assert "role_defaults" not in view["routing_strategies"]
    for document in (rules, view):
        for when in _whens(document):
            assert "role" not in json.dumps(when), when
    for bias in view["routing_strategies"]["biases"]:
        assert "role" not in bias.lower(), bias


def test_trc_a3_the_full_approach_no_longer_builds_in_the_claims_gate():
    for policy in (_policy(), _load(VIEW)):
        result = evaluate_route(_assess(size="large"), policy)
        assert result["delivery_approach"] == "full"
        assert "verify.claims" not in result["gates"]


# What the default gave each assessment with role engineer before the removal.
REFERENCE = {
    "spike": _assess(goal="exploration", size="small", risk="trivial"),
    "quick-fix": _assess(size="small", risk="trivial"),
    "regular": _assess(),
    "hotfix": _assess(size="small", urgency="live-defect"),
    "full": _assess(size="large"),
}


def _six_policy():
    """The routing policy view as it stood before role was removed: the last
    6.x shape, with the role dimension and the role rules."""
    return _load(ROOT / "tests" / "fixtures" / "routing-policy-before-role-removal.yml")


def test_trc_a4_an_assessment_without_a_role_routes_as_an_engineers_did():
    before, now = _six_policy(), _load(VIEW)
    for approach, case in REFERENCE.items():
        old = evaluate_route(dict(case, role="engineer"), before)
        new = evaluate_route(dict(case), now)
        assert new["delivery_approach"] == old["delivery_approach"] == approach
        assert new["stages"] == old["stages"], approach
        assert new["artifacts"] == old["artifacts"], approach
        expected = [g for g in old["gates"]
                    if not (approach == "full" and g == "verify.claims")]
        assert new["gates"] == expected, approach


def test_trc_a5_the_board_and_flow_show_no_role():
    from compass_pkg import board_page, flow
    assert "role" not in board_page._DIMENSIONS
    assert "role" not in flow._ASSESSMENT_DIMENSIONS


def test_trc_a5_the_receipt_goal_line_names_no_role(tmp_path):
    root, task_dir = _project(tmp_path, assessment=_assess(role="product-owner"))
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS)
    assert code == 0, err
    code, out, err = _run(root, "issue", "receipt", "--issue", "t")
    assert code == 0, err
    goal = [line for line in out.splitlines() if line.strip().startswith("goal")]
    assert goal and "product-owner" not in goal[0] and "role" not in goal[0], out


# --- group B: the artifact rules -------------------------------------------------

def test_trc_b1_a_positioning_document_brings_the_claims_gate_and_the_ship_block():
    result = evaluate_route(_assess(artifacts=["positioning"]), _policy())
    assert result["delivery_approach"] == "regular"
    assert "RP-ART-001" in _fired(result)
    assert "verify.claims" in result["gates"]
    assert _blocks(result)["ship"] == (
        "every claim in positioning.md traces to a passing scenario")
    view = evaluate_route(_assess(artifacts=["positioning"]), _load(VIEW))
    assert "verify.claims" in view["gates"] and "RP-ART-001" in _fired(view)


def test_trc_b2_an_intent_document_brings_the_plan_block():
    result = evaluate_route(_assess(artifacts=["intent"]), _policy())
    assert "RP-ART-002" in _fired(result)
    assert _blocks(result)["plan"] == (
        "the spec has been checked against intent.md for intent fidelity")
    plain = evaluate_route(_assess(), _policy())
    assert result["gates"] == plain["gates"]


def test_trc_b3_neither_rule_fires_without_its_document():
    result = evaluate_route(_assess(size="small", risk="trivial"), _policy())
    assert result["delivery_approach"] == "quick-fix"
    assert not {"RP-ART-001", "RP-ART-002"} & set(_fired(result))
    assert result["gates"] == ["verify.correctness", "verify.governance",
                               "verify.traceability"]
    assert not result["blocked_phases"]


def test_trc_b4_a_spike_with_a_positioning_document_carries_only_its_own_gate():
    result = evaluate_route(_assess(goal="exploration", size="small", risk="trivial",
                                    artifacts=["positioning"]), _policy())
    assert result["delivery_approach"] == "spike"
    assert result["gates"] == ["spike.conclude"]


def test_trc_b5_presence_is_read_from_the_issues_documents(tmp_path):
    root, _ = _project(tmp_path / "a", slug="a")
    _write_doc(root, "a", "positioning")
    code, _, err = _run(root, "approach", "evaluate", "--issue", "a", "--write",
                        *ALL_REASONS)
    assert code == 0, err
    data = _load(root / ".compass/work/a/manifest.yml")
    assert "verify.claims" in [g["id"] for g in data["gates"]]
    assert set(data["assessment"]) == set(_assess())

    root, _ = _project(tmp_path / "b", slug="b")
    _write_doc(root, "b", "positioning", exists=False)
    code, _, err = _run(root, "approach", "evaluate", "--issue", "b", "--write",
                        *ALL_REASONS)
    assert code == 0, err
    data = _load(root / ".compass/work/b/manifest.yml")
    assert "verify.claims" not in [g["id"] for g in data["gates"]]
    assert set(data["assessment"]) == set(_assess())


def test_trc_b5_an_unregistered_document_at_its_home_counts(tmp_path):
    root, _ = _project(tmp_path, slug="c")
    _write_doc(root, "c", "positioning", register=False)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "c", "--json")
    assert code == 0, err
    assert "verify.claims" in json.loads(out)["gates"]


def test_trc_b6_the_classifier_sees_the_artifact_rules():
    parent = _preset_config()
    child = _without_rule(parent, "RP-ART-001")
    shown = classify.classify(parent, child)
    assert shown.result == "loosening", shown.reason
    point = shown.first_looser
    assert "positioning" in (point.assessment.get("artifacts") or []), point.assessment
    assert "positioning" in shown.to_json()["grid"]["artifacts"]


def _without_rule(config, rule_id):
    out = copy.deepcopy(config)
    for rule_set in out["rules"].values():
        rule_set.get("rules", {}).pop(rule_id, None)
    return out


# --- group C: upgrading from 6.x -------------------------------------------------

def test_trc_c1_a_manifest_that_records_a_role_evaluates_on_the_new_default(tmp_path):
    root, _ = _project(tmp_path, assessment=_assess(role="product-owner"))
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS)
    assert code == 0, err
    data = _load(root / ".compass/work/t/manifest.yml")
    assert not [f for f in data.get("policy_rules_fired") or []
                if f["id"].startswith("RP-ROLE")]
    assert "role" not in (data.get("justifications") or {})
    result = evaluate_route(_assess(role="product-owner"), _load(VIEW))
    assert not result["blocked_phases"]


def test_trc_c2_a_stored_6x_configuration_keeps_its_role_rules():
    six = _six_policy()
    result = evaluate_route(_assess(role="product-owner"), six)
    assert "RP-ROLE-002" in _fired(result)
    assert "plan" in _blocks(result)
    marketer = evaluate_route(_assess(role="product-marketer"), six)
    assert "verify.claims" in marketer["gates"]
    # A stored generation is a resolved configuration in catalogue form, which
    # holds the 6.x `role-rules` set.
    from compass_pkg import legacy_adapter, shipped_releases
    policy_text, guardrails_text = shipped_releases.texts("v6.0.1")
    stored = legacy_adapter.adapt(yaml.safe_load(policy_text),
                                  yaml.safe_load(guardrails_text))
    owed = obligations.obligations(stored, _assess(role="product-owner"))
    assert "plan" in owed.blocked_stages


def test_trc_c3_a_role_justification_is_accepted_and_not_recorded(tmp_path):
    root, _ = _project(tmp_path)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS, "--justify", "role=an engineer")
    assert code == 0, err
    assert NOT_READ in err and "7.0.0" in err
    data = _load(root / ".compass/work/t/manifest.yml")
    assert "role" not in data["justifications"]


def test_trc_c4_a_quick_fix_given_a_role_is_accepted_and_records_none(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nautonomy: balanced\n", encoding="utf-8")
    code, out, err = _run(root, "quick-fix", "start", "qf",
                          "--risk", "trivial - a typo", "--familiarity",
                          "brownfield-mapped - known", "--size", "atomic - one line",
                          "--role", "engineer - I am one",
                          "--intent", "The typo is gone",
                          "--scenario", "Given the page When it loads Then the word is spelt right",
                          "--test", "tests/test_x.py::test_y")
    assert code == 0, out + err
    assert NOT_READ in err
    data = _load(root / ".compass/work/qf/manifest.yml")
    assert "role" not in data["assessment"]
    assert "role" not in (data.get("justifications") or {})


def test_trc_c5_issue_migrate_reports_a_recorded_role_as_no_longer_read(tmp_path):
    root, task_dir = _project(tmp_path, assessment=_assess(role="designer"),
                              compass_yml=False)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    code, out, err = _run(root, "issue", "migrate")
    assert code == 0, out + err
    assert "no longer read" in out and "assessment.role" in out, out
    code, out, err = _run(root, "issue", "migrate", "--apply", "--i-have-a-copy")
    assert code == 0, out + err
    assert "assessment.role" in out, out
    assert _load(task_dir / "manifest.yml")["assessment"]["role"] == "designer"


def _copied_governance(root, edit=None):
    from compass_pkg import shipped_releases
    policy, guardrails = shipped_releases.texts("v6.0.1")
    gov = root / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    if edit:
        policy = edit(policy)
    (gov / "routing-policy.yml").write_text(policy, encoding="utf-8")
    (gov / "guardrails.yml").write_text(guardrails, encoding="utf-8")
    (root / ".compass").mkdir(exist_ok=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n",
                                                 encoding="utf-8")


def test_trc_c6_policy_migrate_drops_unedited_role_rules_without_a_waiver(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _copied_governance(root)
    code, out, err = _run(root, "policy", "migrate", "--json")
    assert code == 0, out + err
    report = json.loads(out)
    assert report["result"] == "ready", report
    text = json.dumps(report.get("compass_yml") or report)
    assert "role" not in json.dumps(report.get("overlay") or {}), report.get("overlay")
    assert "RP-ROLE" not in json.dumps(report.get("waivers") or {})
    assert "RP-ROLE" not in text or "retired" in text


def test_trc_c7_policy_migrate_names_the_replacement_of_an_edited_role_rule(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _copied_governance(root, edit=lambda text: text.replace(
        "A launch claim with no backing scenario must not ship.",
        "A launch claim with no backing scenario must never ship."))
    code, out, err = _run(root, "policy", "migrate")
    assert code == 1, out + err
    assert "RP-ROLE-001" in out + err and "RP-ART-001" in out + err, out + err
    assert "7.0.0" in out + err


def test_trc_c8_a_project_rule_that_reads_role_is_refused(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nrules:\n  extra:\n    kind: floors\n"
        "    hit: {force_minimum_approach: max}\n    rules:\n      X-1:\n"
        "        order: 1\n        when: {role: designer}\n"
        "        then: {force_minimum_approach: full}\n        rationale: probe\n",
        encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert code == 1, out + err
    assert "M-WHEN-RETIRED" in out + err
    assert "artifacts_any" in out + err and "label" in out + err


def test_trc_c8_a_project_that_declares_its_own_role_dimension_may_read_it(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\ndimensions:\n  role:\n    type: enum\n"
        "    values: [engineer, designer]\nrules:\n  extra:\n    kind: floors\n"
        "    hit: {force_minimum_approach: max}\n    rules:\n      X-1:\n"
        "        order: 1\n        when: {role: designer}\n"
        "        then: {force_minimum_approach: full}\n        rationale: probe\n",
        encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert "M-WHEN-RETIRED" not in out + err, out + err


def test_trc_c9_a_preset_fixture_that_records_a_role_is_read_without_it(tmp_path):
    root = tmp_path / "preset"
    (root / "compass-fixtures").mkdir(parents=True)
    (root / "compass.yml").write_text("schema: 1\nextends: compass:default@6\n",
                                      encoding="utf-8")
    (root / "compass-fixtures" / "one.yml").write_text(
        "name: one\nassessment:\n  risk: contained\n  familiarity: brownfield-mapped\n"
        "  size: medium\n  goal: delivery\n  role: engineer\n  labels: []\n"
        "expect:\n  approach: regular\n", encoding="utf-8")
    code, out, err = _run(root, "preset", "test", str(root), "--offline")
    assert code == 0, out + err
    assert "role" in out + err and "ignored" in out + err


def test_trc_c7_the_retired_rules_table_names_each_replacement():
    sidecar = _load(ROOT / "governance" / "legacy-views.yml")
    table = sidecar["routing_policy"]["retired_rules"]
    assert table["RP-ROLE-001"]["replaced_by"] == "RP-ART-001"
    assert table["RP-ROLE-002"]["replaced_by"] == "RP-ART-002"
    assert table["RP-SROLE-001"]["replaced_by"] is None
    from compass_pkg import retired
    assert retired.RULES == {k: v["replaced_by"] for k, v in table.items()}


# --- group D: the perspectives ---------------------------------------------------

def test_trc_d1_a_document_can_still_name_a_perspective_as_its_owner(tmp_path):
    artifacts = _load(PRESET / "artifacts.yml")["artifacts"]
    assert artifacts["ui-contract"]["owner"] == "designer"
    assert artifacts["intent"]["owner"] == "product-owner"
    assert artifacts["positioning"]["owner"] == "product-marketer"
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text("schema: 1\nextends: compass:default@6\n",
                                      encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert code == 0, out + err
    assert "owner" not in out + err


DOCS = ("docs/routing-deep-dive.md", "docs/roles-guide.md", "README.md",
        "templates/manifest.yml", "templates/intent.md")


def test_trc_d2_the_documents_and_templates_describe_role_as_a_perspective():
    for rel in DOCS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "Goal and role" not in text, rel
        assert "goal & role" not in text.lower(), rel
        for phrase in ("A role changes the issue's assessment",
                       "role_rules", "role rule", "role-rules"):
            assert phrase not in text, (rel, phrase)
    manifest = (ROOT / "templates" / "manifest.yml").read_text(encoding="utf-8")
    block = manifest.split("assessment:", 1)[1].split("\n\n", 1)[0]
    assert "role:" not in block


def test_trc_b6_an_issue_layer_is_judged_at_a_point_with_its_documents(tmp_path):
    """An issue's own `config:` layer is classified at the issue's assessment. That
    point carries the documents on disk, so a layer that drops RP-ART-001 from a
    positioned issue is a loosening, as dropping RP-ROLE-001 from a marketer was."""
    from compass_pkg import policy_lint
    root, task_dir = _project(tmp_path)
    _write_doc(root, "t", "positioning")
    manifest = _load(task_dir / "manifest.yml")
    loaded = policy_lint.load_layers(root, manifest=manifest, task_dir=str(task_dir))
    assert loaded.assessment["artifacts"] == ["positioning"]
    assert "artifacts" not in _load(task_dir / "manifest.yml")["assessment"]
    parent = _preset_config()
    child = _without_rule(parent, "RP-ART-001")
    assert classify.classify(parent, child, at=loaded.assessment).result == "loosening"
    plain = dict(loaded.assessment, artifacts=[])
    assert classify.classify(parent, child, at=plain).result == "equivalent"


def test_trc_b6_policy_diff_replays_an_issue_with_its_documents(tmp_path):
    """`compass policy diff` replays an archived or open issue at the point its
    evaluation would read: with the documents on disk that either side names."""
    from types import SimpleNamespace

    from compass_pkg import replay
    root, task_dir = _project(tmp_path)
    _write_doc(root, "t", "positioning")
    (issue,) = replay.read_archive(root)
    side = SimpleNamespace(config=_preset_config())
    point = replay._point_of(issue, side, side)
    assert point["artifacts"] == ["positioning"]
    assert "documents positioning" in replay._where({"assessment": point, "represents": {}})


def test_trc_c8_a_check_that_reads_documents_is_refused(tmp_path):
    """Only a rule's evaluation reads the documents on disk; `compass check` does
    not, so a check or gate condition on `artifacts_any` would never match there."""
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(
        "schema: 1\nextends: compass:default@6\nchecks:\n  backfills-paid:\n"
        "    set:\n      when: {artifacts_any: [positioning]}\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert code == 1, out + err
    assert "M-WHEN-DOCUMENTS" in out + err


def test_trc_c2_copied_6x_governance_keeps_its_role_rules_through_the_cli(tmp_path):
    """Through `compass approach evaluate`: a project still on copied 6.x
    governance routes a product owner's issue with RP-ROLE-002, as before."""
    root, _ = _project(tmp_path, assessment=_assess(role="product-owner"),
                       compass_yml=False)
    _copied_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--json")
    assert code == 0, out + err
    result = json.loads(out)
    assert "RP-ROLE-002" in [f["id"] for f in result["policy_rules_fired"]]
    assert [b["phase"] for b in result["blocked_phases"]] == ["plan"]


INTENT_TEXT = ("# Intent\n\n## Problem\n\nx\n\n## Desired outcome\n\n- INT-1: x\n\n"
               "## Success signals\n\n- x\n\n## Non-goals\n\n- x\n")


def test_trc_b2_the_assess_flow_records_the_intent_block(tmp_path):
    """The assess procedure, step 3: evaluate without --write, draft and register
    the intent the approach owes, then write. The recorded rules hold RP-ART-002,
    and the intent keeps the depth the approach owes it."""
    root, task_dir = _project(tmp_path)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--json")
    assert code == 0, out + err
    owed = {a["kind"]: a["depth"] for a in json.loads(out)["artifacts"]}
    assert owed["intent"] == "lightweight"
    rel = "docs/compass/2026-10-16-t/intent.md"
    (root / rel).parent.mkdir(parents=True)
    (root / rel).write_text(INTENT_TEXT, encoding="utf-8")
    code, out, err = _run(root, "issue", "artifact", "set", "intent", "--issue", "t",
                          "--status", "draft", "--path", rel)
    assert code == 0, out + err
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS)
    assert code == 0, out + err
    data = _load(task_dir / "manifest.yml")
    assert "RP-ART-002" in [f["id"] for f in data["policy_rules_fired"]]
    intent = next(a for a in data["artifacts"] if a["kind"] == "intent")
    assert intent["depth"] == "lightweight" and intent["path"] == rel
    procedure = (ROOT / "approaches" / "assess-procedure.md").read_text(encoding="utf-8")
    step3 = procedure.split("3. **Compute the delivery approach", 1)[1].split("\n4. ", 1)[0]
    assert "without `--write`" in step3 and "before the write" in step3


def test_trc_b7_ship_refuses_a_document_whose_rule_the_approach_does_not_hold(tmp_path):
    """A positioning.md written after the issue was assessed: its rule did not fire
    at the last evaluation, so the landing is refused until it is re-evaluated."""
    root, task_dir = _project(tmp_path)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS)
    assert code == 0, out + err
    _write_doc(root, "t", "positioning")
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import documents_present
    task = _load(task_dir / "manifest.yml")
    text = documents_present.landing_refusal(task, str(task_dir))
    assert text and "RP-ART-001" in text and "positioning.md" in text, text
    assert "compass approach evaluate --issue t --write" in text
    from compass_pkg import manifest
    assert documents_present.landing_refusal in manifest.LANDING_REFUSALS
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write")
    assert code == 0, out + err
    assert documents_present.landing_refusal(_load(task_dir / "manifest.yml"),
                                             str(task_dir)) is None


def test_trc_c1_a_recorded_role_is_named_as_ignored_on_evaluation(tmp_path):
    """Re-assessing a 6.x issue says on standard error that its recorded role
    is no longer read, so the change in routing is not silent."""
    root, _ = _project(tmp_path, assessment=_assess(role="product-owner"))
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t")
    assert code == 0, out + err
    assert NOT_READ in err and "assessment.role" in err, err
    root2, _ = _project(tmp_path / "b")
    code, out, err = _run(root2, "approach", "evaluate", "--issue", "t")
    assert NOT_READ not in err, err
