"""A waived stage mode holds on an approach a floor raised, end to end.

The `migrations` label brings RP-FLOOR-003, which raises the approach to
`full`, and `full` runs breakdown as multiagent. An issue whose `config:` sets
breakdown to skipped, with an issue waiver the owner approved, keeps the solo
build; the same entry without a valid approval is refused by the lint at the
reassess, and nothing is written. Decision:
`governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`.

Scenario ids: `WSM-4` and `WSM-5` (issue `owner-reassess-overrides-label-floor`).
"""
from __future__ import annotations

import copy

import pytest

import configure_fixtures as cf

JUSTIFY = [arg for dim in ("risk", "familiarity", "size", "goal")
           for arg in ("--justify", f"{dim}=a reason")]

# The issue waiver's approval names the values `waivers.describe` derives. A
# stage entry holds no mode in the parent (modes live on each approach), so
# the derived `from` is null.
APPROVAL = {
    "id": "EV-1", "type": "human-approval", "decision": "approved",
    "approver": "jed72", "role": "owner", "scope": "waiver",
    "timestamp": "2026-10-17T09:00:00Z",
    "waiver": {"scope": "issue", "entry": "stages.breakdown",
               "fields": {"mode": {"from": None, "to": "skipped"}}}}


def _project(tmp_path, evidence):
    body = copy.deepcopy(cf.MANIFEST)
    body["assessment"]["labels"] = ["migrations"]
    body["config"] = {"stages": {"breakdown": {
        "set": {"mode": "skipped"},
        "waiver": {"reason": "Three small fixes in one module.", "approved_by": "EV-1"}}}}
    body["evidence"] = evidence
    return cf.project(tmp_path, compass_yml={"schema": 1, "owner": "jed72"}, manifest=body)


def test_wsm_4_an_approved_waiver_records_the_lower_mode(tmp_path):
    root, task_dir = _project(tmp_path, [copy.deepcopy(APPROVAL)])
    code, out, err = cf.reassess(root, *JUSTIFY)
    assert code == 0, out + err
    manifest = cf.manifest_of(task_dir)
    assert manifest["delivery_approach"] == "full"
    assert manifest["stages"]["breakdown"] == "skipped"
    gates = {g["id"] for g in manifest["gates"]}
    assert len(gates) == 8
    assert {"verify.analyze", "verify.architecture"} <= gates
    # A read of the stored generation gives the same mode: its provenance
    # keeps the waiver.
    code, out, err = cf.run(root, "approach", "evaluate", "--issue", cf.SLUG, "--json")
    assert code == 0, out + err
    assert '"breakdown": "skipped"' in out


@pytest.mark.parametrize("evidence", [
    [],
    [dict(APPROVAL, approver="someone-else")],
], ids=["no-approval-record", "approver-not-allowed"])
def test_wsm_5_an_unapproved_waiver_is_refused(tmp_path, evidence):
    root, task_dir = _project(tmp_path, evidence)
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = cf.reassess(root, *JUSTIFY)
    assert code != 0, out + err
    assert "does not pass the lint" in out + err
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == before
    assert not (task_dir / "generations").exists()
