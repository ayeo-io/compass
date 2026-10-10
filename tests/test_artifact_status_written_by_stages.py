"""Artifact status is written by the stages and by a person's approval (issue
`artifact-status-written-by-stages`, group A, ASW-1 to ASW-15).

Each test builds a scratch git repository with `compass init` and
`compass approach evaluate --write`, then drives `cli/compass` the way a person
or an agent session does. The ship refusal and the end-to-end run are in
`test_ship_commit_refuses_unapproved.py`.

Scenario ids: `ASW-1` to `ASW-15`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))

from artifact_status_support import (DOCS, add_evidence, HUMAN_DESIGN, ROOT, SLUG, add_entry,  # noqa: E402
                                     approve, edit, entries, git, manifest, manifest_file,
                                     project, register, run, statuses)

BY_SET = "compass issue artifact set"


def _brief(root):
    path = root / "brief.md"
    path.write_text("# brief\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "brief")
    return path


def _subtask_add(root):
    _brief(root)
    return run(root, "issue", "subtask", "add", "subtask-1", "--brief", "brief.md",
               "--model", "m", "--budget", "1", "--issue", SLUG)


def _red(root):
    return run(root, "tdd-red", "--issue", SLUG, "--", "sh", "-c", "echo FAILED; exit 1")


def _digest(root, kind):
    data = (root / DOCS / f"{kind}.md").read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()


# --- ASW-1 ---------------------------------------------------------------------

def _staged(root):
    add_entry(root, "delivery-approach", path=False)
    assert register(root, "delivery-approach")[0] == 0
    assert register(root, "acceptance-criteria")[0] == 0


def test_asw_1_stage_exit_approves_document_without_human_check(tmp_path):
    root = project(tmp_path / "a")
    _staged(root)
    assert register(root, "technical-design")[0] == 0
    found = entries(root)
    for kind in ("delivery-approach", "acceptance-criteria"):
        assert found[kind]["status"] == "approved", kind
        assert found[kind]["approved_by"] == BY_SET, kind
        assert found[kind]["approved_at"], kind
    assert found["technical-design"]["status"] == "draft"
    assert "approved_by" not in found["technical-design"]
    first = statuses(root)

    other = project(tmp_path / "b")
    _staged(other)
    code, out, err = _subtask_add(other)
    assert code == 0, out + err
    assert register(other, "technical-design")[0] == 0
    second = statuses(other)
    for kind in ("delivery-approach", "acceptance-criteria", "technical-design"):
        assert second[kind] == first[kind], kind


# --- ASW-2 ---------------------------------------------------------------------

def test_asw_2_stage_exit_moves_human_check_document_to_awaiting_approval(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN)
    assert register(root, "technical-design")[0] == 0
    assert entries(root)["technical-design"]["status"] == "draft"
    code, out, err = _red(root)
    assert code == 0, out + err
    found = entries(root)["technical-design"]
    assert found["status"] == "awaiting-approval"
    assert "approved_by" not in found and "approved_at" not in found


# --- ASW-3 ---------------------------------------------------------------------

def test_asw_3_verify_gate_pass_approves_verification_report(tmp_path):
    root = project(tmp_path)
    assert register(root, "verification-report")[0] == 0
    add_evidence(root, "EV-1")
    code, out, err = run(root, "gate", "pass", "verify.correctness", "--evidence", "EV-1",
                         "--issue", SLUG)
    assert code == 0, out + err
    found = entries(root)["verification-report"]
    assert found["status"] == "approved"
    assert found["approved_by"] == "compass gate pass"


# --- ASW-5 ---------------------------------------------------------------------

def test_asw_5_every_artifact_kind_names_its_stage(tmp_path):
    from compass_pkg.core import load_yaml
    shipped = load_yaml(str(ROOT / "governance" / "presets" / "default" / "artifacts.yml"))
    stages = load_yaml(str(ROOT / "governance" / "presets" / "default" / "stages.yml"))
    for kind, body in shipped["artifacts"].items():
        assert body.get("stage") in stages["stages"], kind
    assert {k: b["stage"] for k, b in shipped["artifacts"].items()} == {
        "delivery-approach": "assess", "intent": "assess",
        "acceptance-criteria": "define", "ui-contract": "define",
        "requirements-review": "refine", "technical-design": "plan",
        "threat-model": "plan", "rollback-plan": "plan",
        "distribution-map": "breakdown", "verification-report": "verify",
        "launch-readiness": "verify"}

    root = project(tmp_path / "ok")
    assert run(root, "policy", "lint")[0] == 0

    bad = project(tmp_path / "bad", compass_yml={
        "schema": 1, "owner": "jed72",
        "artifacts": {"technical-design": {"set": {"stage": "deploy"}}}}, evaluate=False)
    code, out, err = run(bad, "policy", "lint")
    assert code != 0 and "technical-design" in out + err and "deploy" in out + err

    plain = project(tmp_path / "plain", compass_yml={
        "schema": 1, "owner": "jed72", "artifacts": {"runbook": {"file": "runbook.md"}}})
    assert run(plain, "policy", "lint")[0] == 0
    add_entry(plain, "runbook")
    add_evidence(plain, "EV-1")
    assert run(plain, "gate", "pass", "verify.correctness", "--evidence", "EV-1",
               "--issue", SLUG)[0] == 0
    assert entries(plain)["runbook"]["status"] == "draft"


# --- ASW-6 ---------------------------------------------------------------------

def _awaiting(root):
    assert register(root, "technical-design")[0] == 0
    assert _red(root)[0] == 0
    assert entries(root)["technical-design"]["status"] == "awaiting-approval"


def test_asw_6_listed_approver_approves_artifact(tmp_path):
    from compass_pkg import approval_records
    root = project(tmp_path / "a", compass_yml=HUMAN_DESIGN)
    _awaiting(root)
    code, out, err = approve(root, "--artifact", "technical-design", scope="design review")
    assert code == 0, out + err
    found = entries(root)["technical-design"]
    assert (found["status"], found["approved_by"]) == ("approved", "jed72")
    assert found["approved_at"]
    records = [e for e in manifest(root)["evidence"] if e.get("type") == "artifact-approval"]
    assert len(records) == 1
    assert (records[0]["artifact"], records[0]["check"]) == ("technical-design", "design-review")
    assert not [e for e in manifest(root)["evidence"] if e.get("type") == "human-approval"]
    assert records[0]["timestamp"] == found["approved_at"]
    verdict, _ = approval_records.judge(
        "design-review", {"approvers": ["jed72"]}, manifest(root),
        str(root / ".compass" / "work" / SLUG))
    assert verdict == "pass"

    # An artifact whose human check lists no approvers takes any person, not `agent`.
    open_layer = {"schema": 1, "owner": "jed72", "checks": {"design-review": {
        "statement": "A person reviewed the design.", "kind": "human",
        "severity": "blocking", "on_skipped": "not-applicable"}},
        "artifacts": {"technical-design": {"set": {"checks": ["design-review"]}}}}
    anyone = project(tmp_path / "b", compass_yml=open_layer)
    _awaiting(anyone)
    code, out, err = approve(anyone, "--artifact", "technical-design", approver="agent")
    assert code == 2 and entries(anyone)["technical-design"]["status"] == "awaiting-approval"
    assert approve(anyone, "--artifact", "technical-design", approver="alex")[0] == 0
    assert entries(anyone)["technical-design"]["approved_by"] == "alex"


def test_asw_6_an_artifact_approval_never_clears_the_sign_off_guardrail(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN, assessment={"labels": ["auth"]})
    _awaiting(root)
    assert approve(root, "--artifact", "technical-design")[0] == 0
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    rows = [r for r in json.loads(out)["checks"] if r["name"] == "human-approval-present"]
    assert rows and rows[0]["status"] == "fail", out


# --- ASW-7 ---------------------------------------------------------------------

def test_asw_7_receipt_and_dashboard_show_approver_and_time(tmp_path):
    root = project(tmp_path)
    add_entry(root, "technical-design", status="approved", approved_by="jed72",
              approved_at="2026-10-10T12:00:00Z")
    add_entry(root, "acceptance-criteria", status="approved", approved_by=BY_SET,
              approved_at="2026-10-10T11:00:00Z")
    code, out, err = run(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, out + err
    docs = [ln for ln in out.splitlines() if "technical-design" in ln or "acceptance-criteria" in ln]
    text = "\n".join(docs)
    for needle in ("approved", "jed72", "2026-10-10T12:00:00Z", BY_SET, "2026-10-10T11:00:00Z"):
        assert needle in text, (needle, out)
    assert "Documents" in out
    code, out, err = run(root, "issue", "dashboard", "render", "--issue", SLUG)
    assert code == 0, out + err
    page = (root / ".compass" / "work" / SLUG / "README.md").read_text()
    assert "Approved by" in page and "Approved at" in page
    rows = [ln for ln in page.splitlines() if ln.startswith("| technical-design")
            or ln.startswith("| acceptance-criteria")]
    joined = "\n".join(rows)
    for needle in ("jed72", "2026-10-10T12:00:00Z", BY_SET, "2026-10-10T11:00:00Z"):
        assert needle in joined, (needle, page)


# --- ASW-8 to ASW-10 -----------------------------------------------------------

def test_asw_8_approve_refused_when_not_awaiting_approval(tmp_path):
    root = project(tmp_path)
    assert register(root, "acceptance-criteria")[0] == 0
    before = manifest_file(root).read_bytes()
    code, out, err = approve(root, "--artifact", "acceptance-criteria")
    assert code == 2
    assert "acceptance-criteria" in out + err and "draft" in out + err
    assert manifest_file(root).read_bytes() == before


def test_asw_9_approve_refused_for_unlisted_approver(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN)
    _awaiting(root)
    before = manifest_file(root).read_bytes()
    code, out, err = approve(root, "--artifact", "technical-design", approver="alex")
    assert code == 2 and "jed72" in out + err
    assert manifest_file(root).read_bytes() == before
    assert entries(root)["technical-design"]["status"] == "awaiting-approval"


def test_asw_10_artifact_set_cannot_approve_human_check_document(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN)
    _awaiting(root)
    before = manifest_file(root).read_bytes()
    code, out, err = run(root, "issue", "artifact", "set", "technical-design", "--status",
                         "approved", "--issue", SLUG)
    assert code == 2
    assert "compass evidence approve --artifact technical-design" in out + err
    assert manifest_file(root).read_bytes() == before
    # With no human check the same call stays allowed and names itself.
    plain = project(tmp_path / "plain")
    assert register(plain, "technical-design", "approved")[0] == 0
    assert entries(plain)["technical-design"]["approved_by"] == BY_SET


# --- ASW-11, ASW-12 ------------------------------------------------------------

def test_asw_11_rewrite_after_approval_moves_back_to_draft(tmp_path):
    root = project(tmp_path)
    assert register(root, "acceptance-criteria", "approved")[0] == 0
    found = entries(root)["acceptance-criteria"]
    assert found["status"] == "approved" and found["digest"] == _digest(root, "acceptance-criteria")
    old = found["digest"]
    (root / DOCS / "acceptance-criteria.md").write_text("# acceptance-criteria\n\nSecond.\n")
    assert register(root, "acceptance-criteria", "approved")[0] == 0
    found = entries(root)["acceptance-criteria"]
    assert found["status"] == "draft"
    assert "approved_by" not in found and "approved_at" not in found
    assert found["digest"] == _digest(root, "acceptance-criteria") != old
    assert "changed after it was approved" in found["reason"]
    assert BY_SET in found["reason"] and old[7:19] in found["reason"]


def test_asw_12_unchanged_registration_keeps_approved(tmp_path):
    root = project(tmp_path)
    assert register(root, "acceptance-criteria")[0] == 0
    body = manifest(root)
    entry = next(a for a in body["artifacts"] if a["kind"] == "acceptance-criteria")
    entry.update(status="approved", approved_by="jed72", approved_at="2026-10-10T12:00:00Z")
    (manifest_file(root)).write_text(yaml.safe_dump(body, sort_keys=False))
    assert entry["digest"] == _digest(root, "acceptance-criteria")
    assert register(root, "acceptance-criteria", "draft")[0] == 0
    found = entries(root)["acceptance-criteria"]
    assert (found["status"], found["approved_by"], found["approved_at"]) == (
        "approved", "jed72", "2026-10-10T12:00:00Z")


# --- ASW-13 --------------------------------------------------------------------

def test_asw_13_digest_recorded_without_capability_refusals_off(tmp_path):
    layer = {"schema": 1, "owner": "jed72", "artifacts": {
        "technical-design": {"set": {"depends_on": ["acceptance-criteria"]}}}}
    root = project(tmp_path, compass_yml=layer)
    assert register(root, "acceptance-criteria")[0] == 0
    assert register(root, "technical-design")[0] == 0
    found = entries(root)["technical-design"]
    assert found["digest"] == _digest(root, "technical-design")
    assert set(found["upstream"]) == {"acceptance-criteria"}
    (root / DOCS / "acceptance-criteria.md").write_text("# changed\n")
    code, out, err = run(root, "next", "--issue", SLUG)
    assert "stale" not in (out + err).lower()
    code, out, err = run(root, "check", "--issue", SLUG)
    assert "artifact-freshness" not in out + err and "stale" not in (out + err).lower()


# --- ASW-14 --------------------------------------------------------------------

OLD_DECISION = "governance/decisions/2026-10-05-artifact-freshness-stays-opt-in.md"
PINNED_OLD = "1fe4deb66ce1f3fad90befd9b779ab6a170000729847ba770d82ca3f1867dd3e"


def test_asw_14_new_decision_entry_amends_freshness_recording(tmp_path):
    new = ROOT / "governance" / "decisions" / "2026-10-10-artifact-freshness-records-digests-always.md"
    text = new.read_text(encoding="utf-8")
    assert "artifact-freshness-stays-opt-in" in text
    low = text.lower()
    assert "digest" in low and "always" in low
    assert "stale-document refusals stay" in low or "refusals stay" in low
    assert "opt-in" in low
    assert "jed72" in text and "2026-10-10" in text
    old = ROOT / OLD_DECISION
    assert hashlib.sha256(old.read_bytes()).hexdigest() == PINNED_OLD


# --- ASW-15 --------------------------------------------------------------------

def test_asw_15_reassess_marks_unregistered_document_superseded(tmp_path):
    root = project(tmp_path, assessment={"risk": "cross-cutting", "familiarity": "greenfield",
                                         "size": "large"})
    assert manifest(root)["delivery_approach"] == "full"
    add_entry(root, "requirements-review", status="approved", approved_by="jed72",
              approved_at="2026-10-10T12:00:00Z")
    add_entry(root, "technical-design", status="approved", approved_by=BY_SET,
              approved_at="2026-10-10T12:00:00Z")
    add_entry(root, "intent", path=False)
    edit(root, assessment={"risk": "contained", "familiarity": "brownfield-mapped",
                           "size": "medium", "goal": "delivery", "role": "engineer",
                           "labels": []})
    code, out, err = run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                         "--reason", "smaller than thought")
    assert code == 0, out + err
    assert manifest(root)["delivery_approach"] == "regular"
    found = entries(root)
    review = found["requirements-review"]
    assert review["status"] == "superseded"
    assert review["path"] == f"{DOCS}/requirements-review.md"
    assert "re-assessment" in review["reason"] and "full to regular" in review["reason"]
    assert "approved_by" not in review and "approved_at" not in review
    assert found["technical-design"]["status"] == "approved"
    assert found["technical-design"]["approved_by"] == BY_SET
    assert "intent" not in found
