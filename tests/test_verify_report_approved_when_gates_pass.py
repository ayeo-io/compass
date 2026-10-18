"""A `verify` document is approved only once every `verify` gate has passed
(issue `verify-report-approved-when-gates-pass`, VRA-1 to VRA-12).

Each test builds a scratch git repository with `compass init` and
`compass approach evaluate --write`, then drives `cli/compass` the way a person
or an agent session does.

Scenario ids: `VRA-1` to `VRA-12`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))

from artifact_status_support import (ROOT, SLUG, add_entry, add_evidence, edit,  # noqa: E402
                                     entries, manifest, manifest_file, project, register, run)

BY_SET = "compass issue artifact set"
BY_GATE = "compass gate pass"

#: The seven `verify` gates of a regular issue and the evidence type each takes.
GATES = {"verify.correctness": "test-run", "verify.governance": "command-output",
         "verify.traceability": "command-output", "verify.regression": "test-run",
         "verify.clarity": "artifact", "verify.security": "command-output",
         "verify.architecture": "command-output"}

#: A project layer that gives the verification report a human check.
HUMAN_REPORT = {
    "schema": 1, "owner": "jed72",
    "checks": {"report-review": {
        "statement": "A person reviewed the report.", "kind": "human",
        "severity": "blocking", "on_skipped": "not-applicable",
        "approvers": ["jed72"]}},
    "artifacts": {"verification-report": {"set": {"checks": ["report-review"]}}},
}


def _pending(root):
    body = manifest(root)
    # A fixture issue holds six `verify` gates; routing adds the seventh to a real
    # one, so the fixture adds it to match.
    if not any(g["id"] == "verify.architecture" for g in body["gates"]):
        body["gates"].append({"id": "verify.architecture"})
    for gate in body["gates"]:
        gate["status"] = "pending"
        gate["evidence"] = []
    edit(root, gates=body["gates"])


def _pass(root, gate):
    number = len(manifest(root).get("evidence") or []) + 1
    evidence_id = f"EV-V{number}"
    add_evidence(root, evidence_id, GATES[gate])
    code, out, err = run(root, "gate", "pass", gate, "--evidence", evidence_id,
                         "--issue", SLUG)
    assert code == 0, out + err
    return out + err


def _fresh(tmp_path, compass_yml=None, report=True):
    root = project(tmp_path, compass_yml=compass_yml)
    _pending(root)
    if report:
        assert register(root, "verification-report")[0] == 0
    return root


def _report(root):
    return entries(root)["verification-report"]


def _plain(entry):
    return "approved_by" not in entry and "approved_at" not in entry


# --- VRA-1 ---------------------------------------------------------------------

def test_vra_1_one_verify_gate_pass_leaves_the_report_a_draft(tmp_path):
    root = _fresh(tmp_path)
    assert len(GATES) == len([g for g in manifest(root)["gates"] if g["id"] in GATES])
    out = _pass(root, "verify.correctness")
    assert _report(root)["status"] == "draft" and _plain(_report(root))
    assert "verification-report" not in out


# --- VRA-2 ---------------------------------------------------------------------

def test_vra_2_the_last_verify_gate_pass_approves_the_report(tmp_path):
    root = _fresh(tmp_path)
    _pass(root, "verify.correctness")
    others = [g for g in GATES if g != "verify.correctness"]
    for gate in others[:-1]:
        _pass(root, gate)
        assert _report(root)["status"] == "draft", gate
    out = _pass(root, others[-1])
    found = _report(root)
    assert found["status"] == "approved"
    assert found["approved_by"] == BY_GATE and found["approved_at"]
    assert "verification-report -> approved" in out
    code, out, err = run(root, "check", "--issue", SLUG)
    line = next((ln for ln in (out + err).splitlines() if "artifacts-approved" in ln), "")
    assert "verification-report" not in line, out + err


# --- VRA-3 ---------------------------------------------------------------------

def test_vra_3_the_order_of_gate_passes_does_not_matter(tmp_path):
    root = _fresh(tmp_path)
    order = ["verify.architecture"] + [g for g in GATES if g not in (
        "verify.architecture", "verify.correctness")] + ["verify.correctness"]
    for gate in order[:-1]:
        _pass(root, gate)
        assert _report(root)["status"] == "draft", gate
    _pass(root, order[-1])
    assert _report(root)["status"] == "approved"


# --- VRA-4 ---------------------------------------------------------------------

def test_vra_4_earlier_stage_documents_move_on_the_first_pass(tmp_path):
    root = _fresh(tmp_path)
    for kind in ("technical-design", "distribution-map"):
        add_entry(root, kind)
    _pass(root, "verify.correctness")
    found = entries(root)
    for kind in ("technical-design", "distribution-map"):
        assert found[kind]["status"] == "approved", kind
        assert found[kind]["approved_by"] == BY_GATE, kind
    assert found["verification-report"]["status"] == "draft"


# --- VRA-5 ---------------------------------------------------------------------

def test_vra_5_a_human_check_document_waits_for_the_last_gate(tmp_path):
    root = _fresh(tmp_path, compass_yml=HUMAN_REPORT)
    names = list(GATES)
    for gate in names[:-1]:
        _pass(root, gate)
        assert _report(root)["status"] == "draft", gate
    _pass(root, names[-1])
    found = _report(root)
    assert found["status"] == "awaiting-approval" and "approved_by" not in found


# --- VRA-6 ---------------------------------------------------------------------

def test_vra_6_gates_of_other_stages_do_not_hold_it(tmp_path):
    root = _fresh(tmp_path)
    body = manifest(root)
    body["gates"].append({"id": "G5", "status": "pending", "evidence": []})
    edit(root, gates=body["gates"])
    for gate in GATES:
        _pass(root, gate)
    assert [g["status"] for g in manifest(root)["gates"] if g["id"] == "G5"] == ["pending"]
    assert _report(root)["status"] == "approved"


# --- VRA-7 ---------------------------------------------------------------------

@pytest.mark.parametrize("kind, more", [
    ("verification-note", {}), ("launch-readiness", {}),
    ("review", {"round": 1, "id": "ART-REVIEW-1"})])
def test_vra_7_every_verify_stage_kind_follows_the_rule(tmp_path, kind, more):
    root = _fresh(tmp_path, report=False)
    add_entry(root, kind, **more)
    names = list(GATES)
    for gate in names[:-1]:
        _pass(root, gate)
    found = next(a for a in manifest(root)["artifacts"] if a["kind"] == kind)
    assert found["status"] == "draft"
    _pass(root, names[-1])
    found = next(a for a in manifest(root)["artifacts"] if a["kind"] == kind)
    assert found["status"] == "approved" and found["approved_by"] == BY_GATE


# --- VRA-8 ---------------------------------------------------------------------

def test_vra_8_registering_after_every_gate_passed_approves_it(tmp_path):
    root = _fresh(tmp_path, report=False)
    for gate in GATES:
        _pass(root, gate)
    assert not _report(root).get("path")
    assert register(root, "verification-report")[0] == 0
    found = _report(root)
    assert found["status"] == "approved" and found["approved_by"] == BY_SET


# --- VRA-9 ---------------------------------------------------------------------

def test_vra_9_registering_after_some_gates_passed_leaves_a_draft(tmp_path):
    root = _fresh(tmp_path, report=False)
    names = list(GATES)
    for gate in names[:3]:
        _pass(root, gate)
    assert register(root, "verification-report")[0] == 0
    assert _report(root)["status"] == "draft" and "approved_by" not in _report(root)
    for gate in names[3:]:
        _pass(root, gate)
    found = _report(root)
    assert found["status"] == "approved" and found["approved_by"] == BY_GATE


# --- VRA-10 --------------------------------------------------------------------

def test_vra_10_documents_the_old_rule_approved_keep_their_status(tmp_path):
    root = _fresh(tmp_path)
    names = list(GATES)
    for gate in names[:5]:
        _pass(root, gate)
    body = manifest(root)
    for entry in body["artifacts"]:
        if entry["kind"] == "verification-report":
            entry.update(status="approved", approved_by=BY_GATE,
                         approved_at="2026-10-01T00:00:00Z")
    edit(root, artifacts=body["artifacts"])
    add_entry(root, "technical-design", status="approved", approved_by=BY_SET,
              approved_at="2026-10-01T00:00:00Z")
    before = manifest_file(root).read_bytes()
    for argv in (("check", "--issue", SLUG), ("issue", "lint", "--issue", SLUG),
                 ("next", "--issue", SLUG)):
        run(root, *argv)
    assert _report(root)["status"] == "approved"
    assert manifest_file(root).read_bytes() == before
    # A later `verify` gate pass does not rewrite an entry that is already approved.
    kept = {k: dict(a) for k, a in entries(root).items()}
    _pass(root, names[5])
    assert {k: a for k, a in entries(root).items()} == kept


# --- VRA-11 --------------------------------------------------------------------

AMENDMENT = "## Amendment, 14 October 2026"
ADR = ROOT / "architecture" / "decisions" / (
    "ADR-050-artifact-status-is-written-by-stage-exits-and-by-a-persons-approval.md")
DECISION = ROOT / "governance" / "decisions" / (
    "2026-10-14-a-verification-document-waits-for-its-last-gate.md")


def test_vra_11_the_changed_rule_is_recorded_and_documented():
    adr = ADR.read_text(encoding="utf-8")
    assert AMENDMENT in adr
    above, amendment = adr.split(AMENDMENT, 1)
    assert above.rstrip().endswith("`2026-10-10-artifact-freshness-records-digests-always`: "
                                   "the recording half of artifact freshness.")
    assert "every `verify` gate" in amendment and "draft" in amendment
    status = (ROOT / "cli" / "compass_pkg" / "artifact_status.py").read_text(encoding="utf-8")
    command = (ROOT / "cli" / "compass_pkg" / "artifact_cmd.py").read_text(encoding="utf-8")
    verify = (ROOT / "commands" / "verify.md").read_text(encoding="utf-8")
    for text in (status, command, verify):
        assert "every `verify` gate" in text
    assert "verify_record_exists" not in status + command
    assert "registering the report also approves it" not in verify
    decision = DECISION.read_text(encoding="utf-8")
    assert "ADR-050" in decision and "every `verify` gate" in decision


# --- VRA-12 --------------------------------------------------------------------

@pytest.mark.parametrize("gates", [
    [],
    [{"id": "G2", "status": "pass"}],
    [{"id": "unknown-gate", "status": "pass"}],
], ids=["empty", "other-stage", "unknown"])
def test_vra_12_no_verify_gate_leaves_report_draft(tmp_path, gates):
    """A passed gate counts only when the catalogue places it in verify."""
    root = _fresh(tmp_path, report=False)
    edit(root, gates=gates)
    assert register(root, "verification-report")[0] == 0
    assert _report(root)["status"] == "draft" and _plain(_report(root))
