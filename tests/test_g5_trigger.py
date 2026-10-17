"""`G5`'s trigger, read from a project that copied the framework's governance.

History. `G5` first applied only to the four labels `auth`, `payments`,
`personal-data` and `migrations`. A change that added backup and restore was
assessed at risk `critical` but carried none of them, so issue
`g5-trigger-matches-statement` (SCN-A1..F2) added a critical-risk arm. On
2026-10-12 jed72 decided to drop that arm again ("yes narrow guardrail 5"):
critical-risk code that carries none of the labels can be reverted at merge,
and CI and review gate it. The labels carry the irreversibility, so they are
the trigger (governance decision
`2026-10-12-guardrail-5-triggers-on-the-irreversible-labels`, issue
`g5-irreversible-labels`, GIL-4 and GIL-6). A project that wants the arm puts
it back in `compass.yml`.
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GUARDRAILS = ROOT / "governance" / "guardrails.yml"
CONTRACT = ROOT / "docs" / "safety-contract.md"

APPROVAL = {
    "id": "EV-APPROVE", "type": "human-approval", "path": "evidence/approval.md",
    "decision": "approved", "approver": "jed72", "role": "maintainer",
    "scope": "backup and restore paths", "timestamp": "2026-08-06T09:00:00Z",
}


def _project(tmp_path, *, blast="critical", touches=None, approval=False,
             status="active"):
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", root / "governance")
    (root / ".compass").mkdir()
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (root / ".compass" / "current-task").write_text("t\n")
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (task_dir / "delivery-approach.md").write_text("# Route\n")
    (task_dir / "evidence").mkdir()
    (task_dir / "evidence" / "green.json").write_text(
        '{"command": "pytest", "exit_code": 0, "passed": true}')
    (task_dir / "evidence" / "approval.md").write_text("# Approval\n")
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_thing.py").write_text("def test_thing():\n    pass\n")
    (root / "src" / "x.py").write_text("x = 1\n")

    evidence = [{"id": "EV-1", "type": "test-run", "path": "evidence/green.json"}]
    if approval:
        evidence.append(dict(APPROVAL))
    task = {
        "schema_version": "1.1", "task": "t", "created": "2026-08-06",
        "status": status,
        "assessment": {"risk": blast, "familiarity": "greenfield",
                     "size": "small", "goal": "delivery",
                     "urgency": "none", "role": "engineer",
                     "labels": touches or []},
        "delivery_approach": "standard", "topology": "solo", "policy_rules_fired": [],
        "stages": {}, "evidence": evidence,
        "gates": [{"id": "verify.correctness", "status": "pass",
                   "evidence": ["EV-1"]}],
        "scenarios": [{"id": "SCN-1", "title": "t", "intent": "INT-1",
                       "tests": ["tests/test_thing.py"]}],
        "changed_files": [{"path": "src/x.py", "scenarios": ["SCN-1"]}],
        "claims": [], "follow_ups": [], "reassessments": [], "friction": [],
    }
    if status == "landed":
        task["land_timestamp"] = "2026-08-06T00:00:00Z"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(task, sort_keys=False))
    return root


def _check(root):
    # The issue page is written by the render after a command; this fixture wrote the
    # manifest by hand, so render it as that step would.
    subprocess.run([sys.executable, str(CLI), "issue", "render", "--issue", "t"],
                   cwd=str(root), capture_output=True, text=True, timeout=60)
    return subprocess.run([sys.executable, str(CLI), "check", "--verbose", "--issue", "t"],
                          cwd=str(root), capture_output=True, text=True, timeout=60)


def _g5_line(out):
    for line in out.splitlines():
        if "G5" in line or "human-approval-present" in line:
            return line
    return ""


# ---------------------------------------------------------------------------
# Group A - the trigger is the four labels
# ---------------------------------------------------------------------------

def test_scn_a1_critical_blast_radius_alone_does_not_require_an_approval(tmp_path):
    root = _project(tmp_path, blast="critical", touches=["infra"])
    result = _check(root)
    combined = result.stdout + result.stderr
    assert "not applicable" in _g5_line(combined), (
        f"G5 applied to critical risk with no irreversible label:\n{combined}")
    assert "FAIL human-approval-present" not in combined, combined
    assert result.returncode == 0, combined


def test_scn_a2_a_recorded_approval_clears_g5(tmp_path):
    root = _project(tmp_path, blast="critical", touches=["migrations"], approval=True)
    result = _check(root)
    assert "FAIL human-approval-present" not in result.stdout, result.stdout
    assert result.returncode == 0, result.stdout


def test_scn_a3_the_domain_trigger_is_unchanged(tmp_path):
    root = _project(tmp_path, blast="contained", touches=["payments"])
    result = _check(root)
    assert "FAIL human-approval-present" in result.stdout, (
        f"the original domain trigger stopped working:\n{result.stdout}")


def test_scn_a4_neither_condition_still_skips_g5(tmp_path):
    root = _project(tmp_path, blast="contained", touches=["ci"])
    result = _check(root)
    assert "not applicable" in _g5_line(result.stdout), (
        f"G5 applied to a task it should not:\n{result.stdout}")
    assert result.returncode == 0, result.stdout


# ---------------------------------------------------------------------------
# Group B - the any_of evaluator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("readings,expected", [
    ({"risk": "critical", "labels": []}, True),
    ({"risk": "contained", "labels": ["payments"]}, True),
    ({"risk": "contained", "labels": ["ci"]}, False),
])
def test_scn_b1_b2_any_of_is_an_or(readings, expected):
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.core import reading_matches
    when = {"any_of": [{"touches_any": ["auth", "payments"]},
                       {"risk": "critical"}]}
    assert reading_matches(when, readings) is expected


def test_scn_b3_any_of_composes_with_siblings_as_an_and():
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.core import reading_matches
    when = {"any_of": [{"risk": "critical"}], "goal": "delivery"}
    assert reading_matches(when, {"risk": "critical",
                                  "goal": "delivery"}) is True
    assert reading_matches(when, {"risk": "critical",
                                  "intent": "exploration"}) is False


# ---------------------------------------------------------------------------
# Group C - history
# ---------------------------------------------------------------------------

def test_scn_c1_a_landed_task_is_reported_not_failed(tmp_path):
    """A landed issue cleared the gates in force when it landed. Re-failing it
    demands a checkpoint for a decision already taken, which nobody can act on
    (ADR-006, backward compatibility is non-negotiable)."""
    root = _project(tmp_path, blast="contained", touches=["payments"],
                    status="landed")
    result = _check(root)
    assert "FAIL human-approval-present" not in result.stdout, (
        f"re-failed a landed task under a widened trigger:\n{result.stdout}")
    assert "landed" in result.stdout, (
        f"the absent approval must still be said out loud:\n{result.stdout}")


# ---------------------------------------------------------------------------
# Failure modes - the published guarantee must match the mechanism
# ---------------------------------------------------------------------------

def test_scn_f1_the_safety_contract_names_the_four_labels_only():
    text = CONTRACT.read_text(encoding="utf-8")
    i = text.find("Human approvals are needed")
    assert i != -1, "guarantee 5 not found in docs/safety-contract.md"
    para = text[i:text.index("The evidence records", i)]
    for label in ("auth", "payments", "personal data", "migrations"):
        assert label in para, (label, para)
    assert "critical" not in para, (
        "the contract names critical risk as a trigger of guardrail 5, which "
        "the 2026-10-12 decision removed")


def test_scn_f2_guardrails_version_was_bumped():
    doc = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))
    version = str(doc.get("version", ""))
    assert version and version not in ("1.4.0", "1.32.0"), (
        f"guardrails.yml still reports version {version!r}; a rule change must "
        "bump it, or `compass policy lint` cannot tell projects their copy is "
        "stale")
