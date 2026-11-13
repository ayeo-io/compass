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


#: A delivery issue owes no Definition of Done by default (ADR-099 decision 9); the
#: project's own `require_evidence` rule adds the token.
OPT_IN = {"schema": 1,
          "require_evidence": [{"when": {}, "add": ["definition-of-done"]}]}


def _issue(tmp_path, created, *, gates_pass, before_the_path=False, assessment=None,
           opt_in=False):
    """The issue, created on `created`. With `before_the_path`, its manifest holds
    the keys 8.x stored for its assessment in place of the path keys (ADR-092).
    With `opt_in`, the project asks for the Definition of Done."""
    root = base.project(tmp_path, assessment=assessment,
                        compass_yml=OPT_IN if opt_in else None)
    body = manifest(root)
    if before_the_path:
        from test_next_stage import assessed_before_the_path
        body.pop("evidence_required", None)
        old = assessed_before_the_path(body["assessment"])
        old.pop("evidence")
        body.update(old)
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
    row = _row(_issue(tmp_path, "2026-11-05", gates_pass=True, opt_in=True))
    assert row["status"] == "fail", row
    assert all(f"{item} is open" in row["detail"] for item in ITEMS), row


def test_a_new_issue_with_a_gate_still_to_pass_has_nothing_due(tmp_path):
    row = _row(_issue(tmp_path, "2026-11-05", gates_pass=False, opt_in=True))
    assert row["status"] == "nothing-to-check", row
    assert "gate" in row["detail"], row


def test_an_older_issue_with_no_report_keeps_its_verdict(tmp_path):
    row = _row(_issue(tmp_path, "2026-10-10", gates_pass=True, before_the_path=True))
    assert row["status"] == "nothing-to-check", row
    assert "verification report" in row["detail"], row


def test_a_new_issue_whose_verify_stage_is_not_thorough_has_no_definition_of_done(tmp_path):
    # The approaches that wrote a verification report before 9.0.0 hold the Definition of
    # Done: those whose verify stage is thorough (regular, hotfix, full). A quick fix's is
    # lightweight.
    root = _issue(tmp_path, "2026-11-05", gates_pass=True, before_the_path=True)
    body = manifest(root)
    body["stages"]["verify"] = "lightweight"
    write_manifest(root, body)
    row = _row(root)
    assert row["status"] == "nothing-to-check", row
    assert "verify" in row["detail"], row


def test_a_path_issue_that_owes_no_definition_of_done_has_none(tmp_path):
    # On the four-stage path the evidence list says what is owed (ADR-092): a
    # small, contained change owes no `definition-of-done`.
    root = _issue(tmp_path, "2026-11-05", gates_pass=True, assessment={"size": "small"})
    assert "definition-of-done" not in manifest(root)["evidence_required"]
    row = _row(root)
    assert row["status"] == "nothing-to-check", row
    assert "does not list definition-of-done" in row["detail"], row
