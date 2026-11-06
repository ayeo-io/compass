"""Local adapter conformance: actual kit entries, never native model turns.

9.0.0 ships one adapter, Claude Code. The cases that compared it with the
Codex adapter now check the Claude Code result alone; the Codex adapter stays
on 8.x (ayeo-io/compass-delivery#345, decision 5).
"""
from __future__ import annotations

import json
import hashlib
from copy import deepcopy

import pytest
import yaml

from adapter_conformance.runner import Adapter

pytestmark = pytest.mark.raw_justify


def test_adapter_entries_compose_the_same_policy(tmp_path):
    cases = [
        ("trivial", "atomic", "delivery", "", "delivery"),
        ("contained", "medium", "delivery", "", "delivery"),
        ("contained", "medium", "exploration", "", "spike"),
        ("contained", "medium", "delivery", "positioning", None),
    ]
    # A delivery assessment is on the four-stage path, whose one approach is
    # `delivery`; an exploration is still a spike (ADR-092).
    # The last column was a role before 7.0.0 and a document reading after it.
    # The shipped default declares no artifact rule since 9.0.0 (ADR-091
    # decision 3), so the reading adds no claims gate. #354, which removes the
    # role entry points, decides how claims are reviewed.
    for index, (risk, size, goal, documents, expected) in enumerate(cases):
        adapter = Adapter("claude-code", tmp_path / str(index))
        result = adapter.evaluate(risk=risk, familiarity="brownfield-mapped",
                                  size=size, goal=goal, artifacts=documents)
        assert adapter.calls[-1]["argv"][:len(adapter.entry)] == adapter.entry
        if expected:
            assert result["delivery_approach"] == expected
        if documents == "positioning":
            assert "verify.claims" not in result["gates"]


def test_quick_fix_and_local_handoff(tmp_path):
    # A second entry resumes the issue the first one started.
    started = Adapter("claude-code", tmp_path / "project")
    started.seed("quick-fix")
    started.start_quick_fix()
    started.red()
    manifest_path = started.issue_dir / "manifest.yml"
    before = manifest_path.read_bytes()
    evidence_before = {path.name: path.read_bytes()
                       for path in (started.issue_dir / "evidence").iterdir() if path.is_file()}
    resumed = Adapter("claude-code", started.project)
    assert manifest_path.read_bytes() == before
    assert {path.name: path.read_bytes()
            for path in (resumed.issue_dir / "evidence").iterdir() if path.is_file()} == evidence_before
    # The quick fix is on the four-stage path (ADR-092): after its red it is at Build.
    from compass_pkg import next_cmd
    from compass_pkg.core import normalize_spine
    assert next_cmd._current_phase_from_task(
        next_cmd._typed(normalize_spine(resumed.manifest())), str(resumed.issue_dir)) \
        == "build"
    assert "build" in resumed.cli("next", "--issue", started.slug).stdout.lower()
    resumed.fix("quick-fix")
    resumed.finish_quick_fix()
    result = resumed.manifest()
    assert result["delivery_approach"] == "delivery"
    assert all(gate["status"] == "pass" for gate in result["gates"])
    assert resumed.cli("check", "--issue", resumed.slug).returncode == 0
    red = json.loads((resumed.issue_dir / "evidence/red-CONF-1.outer.json").read_text())
    green = json.loads((resumed.issue_dir / "evidence/green-CONF-1.outer.json").read_text())
    assert red["exit_code"] != 0 and red["passed"] is False
    assert green["exit_code"] == 0 and green["passed"] is True
    assert red["record_id"] != green["record_id"]


def test_git_environment_cannot_escape_project(tmp_path, monkeypatch):
    outside = Adapter("claude-code", tmp_path / "outside")
    outside.seed("quick-fix")
    assert outside.git("config", "maintenance.auto").stdout.strip() == "false"
    assert outside.git("config", "gc.auto").stdout.strip() == "0"
    before = {str(path.relative_to(outside.project)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in outside.project.rglob("*") if path.is_file()}
    supplied = {"GIT_DIR": str(outside.project / ".git"),
                "GIT_COMMON_DIR": str(outside.project / ".git"),
                "GIT_WORK_TREE": str(outside.project),
                "GIT_INDEX_FILE": str(outside.project / ".git/another-index"),
                "GIT_OBJECT_DIRECTORY": str(outside.project / ".git/objects")}
    for key, value in supplied.items():
        monkeypatch.setenv(key, value)
    isolated = Adapter("claude-code", tmp_path / "isolated")
    assert not set(supplied).intersection(isolated.env), "Git repository selection leaked"
    isolated.seed("quick-fix")
    assert (isolated.project / ".git").is_dir()
    after = {str(path.relative_to(outside.project)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in outside.project.rglob("*") if path.is_file()}
    assert after == before


def test_regular_feature_records(tmp_path):
    adapter = Adapter("claude-code", tmp_path / "claude-code")
    adapter.seed("feature")
    adapter.start_feature()
    adapter.red()
    adapter.fix("feature")
    adapter.green_feature()
    observation = adapter.observe()
    manifest = observation["manifest"]
    assert manifest["delivery_approach"] == "delivery"
    assert {gate["id"] for gate in manifest["gates"]} == {
        "verify.correctness", "verify.governance", "verify.traceability",
        "verify.regression", "verify.clarity", "verify.security"}
    # Routing writes no document list since 9.0.0 (ADR-091); `compass check`
    # in observe() reads the acceptance criteria at their fixed path.
    assert manifest["artifacts"] == []
    assert any(record["type"] == "test-run" and record["passed"]
               for record in observation["evidence"])


def test_semantic_changes_and_tampered_evidence_fail(tmp_path):
    from adapter_conformance.runner import compare

    adapter = Adapter("claude-code", tmp_path / "project")
    adapter.seed("quick-fix")
    adapter.start_quick_fix()
    adapter.red()
    adapter.fix("quick-fix")
    adapter.finish_quick_fix()
    manifest = adapter.manifest()
    manifest["evidence"].append({
        "id": "EV-SYNTHETIC-SCOPE", "type": "human-approval", "guardrail": "G5",
        "issue": adapter.slug, "generation": manifest["generation"],
        "approver": "synthetic fixture; no human signed", "role": "fixture",
        "decision": "approved", "scope": "synthetic subject-check input only",
        "timestamp": "2026-10-15T00:00:00Z", "synthetic": True})
    (adapter.issue_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    original = adapter.observe()
    approval = next(record for record in original["evidence"]
                    if record["type"] == "human-approval")
    assert approval["guardrail"] == "G5" and approval["synthetic"] is True
    compare(original, adapter.observe())

    changed_policy = deepcopy(original)
    changed_policy["policy"]["autonomy"] = "different-policy-value"
    with pytest.raises(AssertionError, match="policy"):
        compare(original, changed_policy)
    changed_gate = deepcopy(original)
    changed_gate["manifest"]["gates"][0]["status"] = "fail"
    with pytest.raises(AssertionError, match="gates"):
        compare(original, changed_gate)
    changed_subject = deepcopy(original)
    changed_approval = next(record for record in changed_subject["evidence"]
                            if record["type"] == "human-approval")
    changed_approval.pop("guardrail")
    changed_approval["check"] = "dod-reviewed"
    with pytest.raises(AssertionError, match="evidence"):
        compare(original, changed_subject)

    evidence = adapter.issue_dir / "evidence/green-CONF-1.outer.json"
    record = json.loads(evidence.read_text())
    record["exit_code"] = 23
    evidence.write_text(json.dumps(record))
    with pytest.raises(AssertionError, match="identity|suite-passed"):
        adapter.observe()


def test_hook_decisions(tmp_path):
    adapter = Adapter("claude-code", tmp_path / "claude-code")
    adapter.seed("quick-fix")
    for state, expected_exit in (("unassessed", 2), ("no-red", 2), ("red", 0)):
        if state == "no-red":
            adapter.start_quick_fix()
        elif state == "red":
            adapter.red()
        for action in ("file", "move", "shell"):
            decision = adapter.payload_decision(action)
            assert decision["exit_code"] == expected_exit, (state, action, decision)
            if expected_exit:
                assert decision["reason"]
    spike = Adapter("claude-code", tmp_path / "claude-code-spike")
    spike.seed("quick-fix")
    spike.start_spike()
    assert spike.payload_decision("file") == {"exit_code": 0, "reason": None}


def test_approval_scope_observations(tmp_path):
    # The cap observation ran the multiagent script, which 9.0.0 removed
    # (ADR-090); the approval observation stays.
    approval = Adapter("claude-code", tmp_path / "approval")
    approval.seed("quick-fix")
    approval.start_approval_fixture()
    subjects = [approval.approval_decision(subject)
                for subject in (None, "check", "guardrail")]
    assert [result["status"] for result in subjects] == ["fail", "fail", "pass"]
    assert all(result["synthetic"] for result in subjects)


def test_local_captures_cannot_claim_native_acceptance(tmp_path):
    adapter = Adapter("claude-code", tmp_path / "project")
    result = adapter.evaluate(risk="trivial", familiarity="brownfield-mapped",
                              size="atomic", goal="delivery", role="engineer")
    observed = {"evidence_class": "local", "delivery_approach": result["delivery_approach"],
                "gates": result["gates"]}
    # An assessment is evaluated on the four-stage path, whose one approach is
    # `delivery` (ADR-092).
    expected = {"evidence_class": "local", "delivery_approach": "delivery",
                "gates": ["verify.correctness", "verify.governance", "verify.traceability"]}
    capture = adapter.capture("route", observed, expected)
    assert capture["format_version"] == 1 and capture["evidence_class"] == "local"
    assert capture["result"]["status"] == "passed"
    assert capture["native"]["status"] == capture["independent"]["status"] == "unmeasured"
    assert capture["calls"] and capture["framework_revision"]
    assert json.loads(json.dumps(capture))["adapter"] == "claude-code"
    changed = deepcopy(observed)
    changed["delivery_approach"] = "regular"
    assert adapter.capture("route", changed, expected)["result"]["status"] == "failed"
    for case in ("cold-resume", "fresh-machine-install", "external-user-issue"):
        with pytest.raises(ValueError, match="local"):
            adapter.capture(case, observed, expected)
