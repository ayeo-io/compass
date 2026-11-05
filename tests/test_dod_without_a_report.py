"""`dod-evidence-typed` judges a 9.0.0 issue with no verification report (ADR-091).

9.0.0 writes no verification report, so an issue created on or after 2026-11-04 is
judged once every gate has passed, report or not. Before that, nothing is due. An older
issue keeps the rule it had: it is judged only once its report exists.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import json

import artifact_status_support as base
from artifact_status_support import SLUG, manifest, run, write_manifest

ITEMS = ["dod-every-scenario-passes", "dod-suite-green", "dod-coverage-floor",
         "dod-no-lint-errors", "dod-traceability-intact", "dod-living-docs-updated",
         "dod-follow-ups-settled"]


def _issue(tmp_path, created, *, gates_pass):
    root = base.project(tmp_path)
    body = manifest(root)
    body["created"] = created
    (root / "evidence.txt").write_text("x\n")
    body["evidence"] = [{"id": "EV-1", "type": "test-run", "path": "../../../evidence.txt"}]
    for gate in body["gates"]:
        gate["status"] = "pass" if gates_pass else "pending"
        gate["evidence"] = ["EV-1"] if gates_pass else []
    write_manifest(root, body)
    return root


def _row(root):
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    rows = [c for c in json.loads(out)["checks"] if c["name"] == "dod-evidence-typed"]
    assert rows, out + err
    return rows[0]


def test_a_new_issue_is_judged_once_every_gate_has_passed(tmp_path):
    row = _row(_issue(tmp_path, "2026-11-05", gates_pass=True))
    assert row["status"] == "fail", row
    assert all(f"{item} is open" in row["detail"] for item in ITEMS), row


def test_a_new_issue_with_a_gate_still_to_pass_has_nothing_due(tmp_path):
    row = _row(_issue(tmp_path, "2026-11-05", gates_pass=False))
    assert row["status"] == "nothing-to-check", row
    assert "gate" in row["detail"], row


def test_an_older_issue_with_no_report_keeps_its_verdict(tmp_path):
    row = _row(_issue(tmp_path, "2026-10-10", gates_pass=True))
    assert row["status"] == "nothing-to-check", row
    assert "verification report" in row["detail"], row


def test_a_new_issue_whose_verify_stage_is_not_thorough_has_no_definition_of_done(tmp_path):
    # The approaches that wrote a verification report before 9.0.0 hold the Definition of
    # Done: those whose verify stage is thorough (regular, hotfix, full). A quick fix's is
    # lightweight.
    root = _issue(tmp_path, "2026-11-05", gates_pass=True)
    body = manifest(root)
    body["stages"]["verify"] = "lightweight"
    write_manifest(root, body)
    row = _row(root)
    assert row["status"] == "nothing-to-check", row
    assert "verify" in row["detail"], row
