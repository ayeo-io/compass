"""Role is no longer an assessment dimension (ayeo-io/compass-delivery-record#149).

The two blocking role rules became artifact rules keyed on the documents the
CLI finds on disk, the full approach stopped building in the claims gate, and
6.x records and configurations keep working. ADR-070 records the decision;
docs/upgrade-7-0-0.md tells an adopter what changes. 9.0.0 deletes the role
flags (ADR-098), so the tests of those calls check the refusal. Since 9.0.0 no
command reads the documents on disk (ADR-091), so the tests of that reading
moved to tests/test_removed_parts_9_0_0_documents.py, inverted.

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

from compass_pkg import obligations, word_map  # noqa: E402
from compass_pkg import catalogue_spec  # noqa: E402
from compass_pkg.routing import evaluate_route  # noqa: E402

#: The shipped default: the check set since 9.0.0 (ADR-094).
PRESET = None
# The live default declares no document, approach map or artifact rule since 9.0.0
# (ADR-091). The 7.0.0 preset is frozen with them, and a stored generation still
# reads them, so the tests of the artifact rules read that preset.
FROZEN = ROOT / "tests" / "fixtures" / "presets" / "default@7"
NOT_READ = "role is no longer an assessment dimension"


def _shipped_policy():
    from check_set_files import view as shipped_view
    return shipped_view("routing-policy.yml")


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _preset_config(folder=PRESET):
    """The catalogues of the check set, or of the frozen preset in `folder`, read
    through the retired-word tables as a stored generation is read."""
    if folder is None:
        from compass_pkg import check_set
        resolved = check_set.resolved()
        return {name: resolved[name] for name in catalogue_spec.CATALOGUES if resolved.get(name)}
    config = {}
    for name in catalogue_spec.CATALOGUES:
        part = _load(folder / f"{name}.yml")
        if part.get(name):
            config[name] = part[name]
    return word_map.map_layer(config)[0]


def _policy(folder=PRESET):
    return obligations.policy_adapter(_preset_config(folder))


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


# --- group A: the shipped vocabulary and the evaluator ----------------------------

def test_trc_a1_the_shipped_default_declares_no_role_dimension():
    dims = _preset_config()["dimensions"]
    assert "role" not in dims
    assert list(dims) == ["risk", "familiarity", "size", "goal", "urgency", "labels"]
    view = _shipped_policy()
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
    rules = _preset_config()["rules"]
    assert all(s.get("kind") != "role-rules" for s in rules.values())
    assert "role_rules" not in rules and "role_defaults" not in rules
    view = _shipped_policy()
    assert not view["routing_guardrails"].get("role_rules")
    assert not view["routing_strategies"].get("role_defaults")
    for document in (rules, view):
        for when in _whens(document):
            assert "role" not in json.dumps(when), when
    for bias in view["routing_strategies"]["biases"]:
        assert "role" not in bias.lower(), bias


def test_trc_a3_the_full_approach_no_longer_builds_in_the_claims_gate():
    # The shipped default routes no 8.x approach since 9.0.0 (ADR-092), so the full
    # approach is read on the frozen 7.0.0 preset and the 8.0.4 governance copy.
    import compat_baseline as cb
    for policy in (_policy(FROZEN), cb.policy_8_0_4()):
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


#: The documents each approach gained after the fixture below was recorded.
ADDED_AFTER_ROLE_REMOVAL = {"regular": ("requirements-review",), "hotfix": ("bug-report",)}


def _six_policy():
    """The routing policy view as it stood before role was removed: the last
    6.x shape, with the role dimension and the role rules."""
    return _load(ROOT / "tests" / "fixtures" / "routing-policy-before-role-removal.yml")


def test_trc_a4_an_assessment_without_a_role_routes_as_an_engineers_did():
    # The shipped default routes no 8.x approach since 9.0.0 (ADR-092), so the
    # approaches are read on the 8.0.4 governance copy, the last release that
    # routed them; the live view routes no document either.
    import compat_baseline as cb
    before, now = _six_policy(), cb.policy_8_0_4()
    for approach, case in REFERENCE.items():
        old = evaluate_route(dict(case, role="engineer"), before)
        new = evaluate_route(dict(case), now)
        assert new["delivery_approach"] == old["delivery_approach"] == approach
        assert new["stages"] == old["stages"], approach
        # 9.0.0 owes no document (ADR-091), so the documents are compared on the
        # frozen 7.0.0 preset. Documents a later 7.0.0 change added to the approach
        # (ADR-072) are not part of the role removal, so they are left out.
        assert evaluate_route(dict(case), _shipped_policy())["artifacts"] == [], approach
        seven = evaluate_route(dict(case), _policy(FROZEN))
        added = ADDED_AFTER_ROLE_REMOVAL.get(approach, ())
        assert [a for a in seven["artifacts"] if a["kind"] not in added] \
            == old["artifacts"], approach
        expected = [g for g in old["gates"]
                    if not (approach == "full" and g == "verify.claims")]
        assert new["gates"] == expected, approach


def test_trc_a5_the_board_and_flow_show_no_role():
    # 9.0.0 removed the board page (ADR-093); the text board and --json remain.
    from compass_pkg import flow
    assert "role" not in flow._ASSESSMENT_DIMENSIONS


# --- group B: the artifact rules -------------------------------------------------

def test_trc_b1_a_positioning_document_brings_the_claims_gate_and_the_ship_block():
    result = evaluate_route(_assess(artifacts=["positioning"]), _policy(FROZEN))
    assert result["delivery_approach"] == "regular"
    assert "RP-ART-001" in _fired(result)
    assert "verify.claims" in result["gates"]
    assert _blocks(result)["ship"] == (
        "every claim in positioning.md traces to a passing scenario")
    # The live default and its view hold no artifact rule since 9.0.0 (ADR-091).
    for policy in (_policy(), _shipped_policy()):
        live = evaluate_route(_assess(artifacts=["positioning"]), policy)
        assert "verify.claims" not in live["gates"] and "RP-ART-001" not in _fired(live)


def test_trc_b2_an_intent_document_brings_the_plan_block():
    result = evaluate_route(_assess(artifacts=["intent"]), _policy(FROZEN))
    assert "RP-ART-002" in _fired(result)
    assert _blocks(result)["plan"] == (
        "the spec has been checked against intent.md for intent fidelity")
    plain = evaluate_route(_assess(), _policy(FROZEN))
    assert result["gates"] == plain["gates"]


def test_trc_b3_neither_rule_fires_without_its_document():
    # The quick fix is an 8.x approach, read on the frozen 7.0.0 preset (ADR-092).
    result = evaluate_route(_assess(size="small", risk="trivial"), _policy(FROZEN))
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
    result = evaluate_route(_assess(role="product-owner"), _shipped_policy())
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
    import legacy_copy
    policy_text, guardrails_text = _six_0_1_texts()
    stored = legacy_copy.adapt(yaml.safe_load(policy_text),
                                  yaml.safe_load(guardrails_text))
    owed = evaluate_route(_assess(role="product-owner"), obligations.policy_adapter(stored))
    assert "plan" in _blocks(owed)


def test_trc_c3_a_role_justification_is_refused_from_9_0_0(tmp_path):
    """9.0.0 deletes the role flags (ADR-098): `--justify role=` gets the
    refusal of any dimension that needs no justification, and nothing is written."""
    root, _ = _project(tmp_path)
    before = (root / ".compass/work/t/manifest.yml").read_bytes()
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          *ALL_REASONS, "--justify", "role=an engineer")
    assert code != 0, out + err
    assert "--justify names role, which is not a dimension that needs one" in err, err
    assert NOT_READ not in err
    assert (root / ".compass/work/t/manifest.yml").read_bytes() == before


def test_trc_c4_a_quick_fix_given_a_role_is_refused_from_9_0_0(tmp_path):
    """9.0.0 deletes `quick-fix start --role` (ADR-098): argparse refuses it as
    an unknown flag, and no issue is written."""
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
    assert code == 2, out + err
    assert "unrecognized arguments: --role" in err, err
    assert not (root / ".compass/work/qf").exists()


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


# The two governance files v6.0.1 shipped, as members of the frozen archive
# `governance/shipped-releases.tar.xz`. A member is named by the file's version
# and the first 12 characters of its content digest.
SIX_0_1_MEMBERS = ("routing-policy/2.20.0-f5a495aa015e.yml",
                   "guardrails/1.26.0-1f7c189f989d.yml")


def _six_0_1_texts():
    import tarfile
    with tarfile.open(ROOT / "governance" / "shipped-releases.tar.xz", "r:xz") as archive:
        return tuple(archive.extractfile(name).read().decode("utf-8")
                     for name in SIX_0_1_MEMBERS)


def _copied_governance(root, edit=None):
    policy, guardrails = _six_0_1_texts()
    gov = root / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    if edit:
        policy = edit(policy)
    (gov / "routing-policy.yml").write_text(policy, encoding="utf-8")
    (gov / "guardrails.yml").write_text(guardrails, encoding="utf-8")
    (root / ".compass").mkdir(exist_ok=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n",
                                                 encoding="utf-8")


def test_trc_c8_a_project_rule_that_reads_role_is_refused(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    # Since 9.0.0 a project adds a rule with the tighten-only setting
    # `require_evidence` (ADR-094); its `when:` reads the assessment only.
    (root / "compass.yml").write_text(
        "schema: 1\nrequire_evidence:\n  - when: {role: designer}\n"
        "    add: [architecture]\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert code == 1, out + err
    assert "L-SETTING-INVALID [project] require_evidence[0].when.role" in out, out + err
    assert "labels" in out, out


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


# --- group D: the perspectives ---------------------------------------------------

def test_trc_d1_a_document_can_still_name_a_perspective_as_its_owner(tmp_path):
    artifacts = _load(FROZEN / "artifacts.yml")["artifacts"]
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


DOCS = ("docs/routing-deep-dive.md", "README.md",
        "templates/manifest.yml")


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


def test_trc_c8_a_check_that_reads_documents_is_refused(tmp_path):
    """Only a rule's evaluation reads the documents on disk; `compass check` does
    not, so a check or gate condition on `artifacts_any` would never match there."""
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    # Since 9.0.0 a project adds a check with the tighten-only setting
    # `project_checks` (ADR-094).
    (root / "compass.yml").write_text(
        "schema: 1\nproject_checks:\n  - {id: notes, name: Notes, command: 'true', "
        "stage: ship, when: {artifacts_any: [positioning]}}\n", encoding="utf-8")
    code, out, err = _run(root, "policy", "lint")
    assert code == 1, out + err
    assert "L-SETTING-INVALID [project] project_checks[0].when.artifacts_any" in out, (
        out + err)


def _old_evaluator(root, slug="t"):
    """What the 8.x evaluator gives for the issue over the configuration the CLI
    reads for it: its stored generation, else the check set now. On the
    four-stage path (ADR-092) the CLI shows the evidence owed, so the approach
    and its role rules are read here."""
    from compass_pkg import effective
    from compass_pkg.core import load_yaml, normalize_spine
    task_dir = Path(root) / ".compass" / "work" / slug
    task = normalize_spine(load_yaml(str(task_dir / "manifest.yml")))
    view = effective.effective_for(str(task_dir))
    return evaluate_route(task["assessment"], view.evaluator_policy())


def _path_view(root, slug="t"):
    """`compass approach evaluate --json` for the issue, on the path."""
    code, out, err = _run(root, "approach", "evaluate", "--issue", slug, "--json")
    assert code == 0, out + err
    result = json.loads(out)
    assert result["delivery_approach"] == "delivery" and result["evidence_required"], result
    return result, err


def test_trc_c2_copied_6x_governance_is_refused_from_9_0_0(tmp_path):
    """A project still on copied 6.x governance is refused: 9.0.0 reads no copy
    (ADR-098), so its role rules are never dropped without a word."""
    root, _ = _project(tmp_path, assessment=_assess(role="product-owner"),
                       compass_yml=False)
    _copied_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--json")
    assert code == 2 and "[governance-copy-removed]" in err, out + err


# An issue that Compass 6.0.1 assessed with `role: product-owner` and committed
# as generation 1, under a `compass.yml` that extends compass:default@6. Its
# `versions.yml` names cli 6.0.1. Packed, so the prose scans do not read the
# 6.0.1 wording as this tree's.
GENERATION_6_0_1 = ROOT / "tests" / "fixtures" / "v6.0.1-generation.tgz"


def _six_generation_project(tmp_path):
    import tarfile
    root = tmp_path / "proj"
    root.mkdir()
    with tarfile.open(GENERATION_6_0_1) as tar:
        tar.extractall(root)
    return root


def test_trc_c2_a_stored_6x_generation_keeps_its_role_rules_through_the_cli(tmp_path):
    """Through `compass approach evaluate`: an issue whose stored generation was
    committed by 6.0.1 keeps its role rules until it is re-assessed, and the
    re-assessment commits a generation on the 7.0.0 default without them."""
    root = _six_generation_project(tmp_path)
    task_dir = root / ".compass" / "work" / "t"
    versions = _load(task_dir / "generations" / "1" / "versions.yml")
    assert versions["cli"] == "6.0.1"
    assert _load(task_dir / "manifest.yml")["generation"] == 1

    _, err = _path_view(root)
    result = _old_evaluator(root)
    assert _fired(result) == ["RP-ROLE-002"]
    assert [b["phase"] for b in result["blocked_phases"]] == ["plan"]
    # The generation in force declares `role`, so the recorded role is read.
    assert NOT_READ not in err, err

    # The stored generation holds the other role rule too.
    data = _load(task_dir / "manifest.yml")
    data["assessment"]["role"] = "product-marketer"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False),
                                           encoding="utf-8")
    _path_view(root)
    result = _old_evaluator(root)
    assert _fired(result) == ["RP-ROLE-001"]
    assert "verify.claims" in result["gates"]
    assert _load(task_dir / "manifest.yml")["generation"] == 1

    code, out, err = _run(root, "approach", "evaluate", "--issue", "t", "--write",
                          "--reason", "upgraded to 7.0.0")
    assert code == 0, out + err
    assert NOT_READ in err and "assessment.role" in err, err
    data = _load(task_dir / "manifest.yml")
    assert data["generation"] == 2
    assert data["evidence_required"] and "stages" not in data, data
    assert not [f for f in data.get("policy_rules_fired") or []
                if f["id"].startswith("RP-ROLE")]
    assert "verify.claims" not in [g["id"] for g in data["gates"]]
    stored = {n: _load(task_dir / "generations" / str(n) / "resolved.yml") for n in (1, 2)}
    assert "role_rules" in stored[1]["rules"] and "role" in stored[1]["dimensions"]
    assert "role_rules" not in stored[2]["rules"] and "role" not in stored[2]["dimensions"]


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
