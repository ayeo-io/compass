"""A waived stage mode holds on an approach a floor raised.

The `migrations` label brings RP-FLOOR-003, which raises the approach to
`full`, and `full` runs breakdown as multiagent. An issue whose `config:` sets
breakdown to skipped, with an issue waiver the owner approved, keeps the solo
build; the same entry without a valid approval is refused by the lint. Decision:
`governance/decisions/2026-10-17-a-waived-stage-mode-holds-on-a-floor-raised-approach.md`.

The shipped default has no breakdown stage, no approaches and no RP-FLOOR-003
since 9.0.0 (ADR-092), and a reassess over it leaves the issue's breakdown mode
out. An issue assessed before 9.0.0 keeps a configuration that holds them, so
the rule is tested over the 8.0.4 governance copy: the chain an old issue's
stored generation resolved, with the project's owner and the issue's layer.

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


def _parent(tmp_path):
    """The 8.0.4 governance copy in catalogue form, as a parent layer."""
    import compat_baseline as cb
    from compass_pkg import effective
    root = tmp_path / "copy"
    (root / ".compass").mkdir(parents=True)
    cb.add_governance_copy(root, source=cb.GOVERNANCE_8_0_4)
    return effective._legacy_parent(str(root))[0]


ISSUE_LAYER = {"stages": {"breakdown": {
    "set": {"mode": "skipped"},
    "waiver": {"reason": "Three small fixes in one module.", "approved_by": "EV-1"}}}}


def _lint(tmp_path, evidence):
    from compass_pkg import layers, policy_lint
    project_doc = {"schema": 1, "owner": "jed72"}
    project = layers.Layer("project", "project", project_doc,
                           layers.layer_digest(project_doc, "project"))
    issue = layers.Layer("issue", "issue", ISSUE_LAYER, layers.layer_digest(ISSUE_LAYER, "issue"))
    parent = _parent(tmp_path)
    assessment = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
                  "goal": "delivery", "urgency": "none", "labels": ["migrations"]}
    report = policy_lint.lint_chain(parent, project, issue, registry=evidence,
                                    assessment=assessment)
    return report, (parent, project, issue), assessment


def test_wsm_4_an_approved_waiver_records_the_lower_mode(tmp_path):
    from compass_pkg import merge, obligations
    from compass_pkg.routing import evaluate_route
    report, chain, assessment = _lint(tmp_path, [copy.deepcopy(APPROVAL)])
    assert not report.errors, report.errors
    config = merge.resolve(list(chain))[0]
    policy = obligations.policy_adapter(config)
    waived = evaluate_route(assessment, policy,
                            issue=obligations.issue_input(config, {}, ["breakdown"]))
    # RP-FLOOR-003 raises the approach, and the waived mode holds on it.
    assert waived["delivery_approach"] == "full"
    assert waived["stages"]["breakdown"] == "skipped"
    # The same mode without the waiver gives way to the approach the floor raised.
    plain = evaluate_route(assessment, policy, issue=obligations.issue_input(config, {}, []))
    assert plain["stages"]["breakdown"] == "multiagent"


@pytest.mark.parametrize("evidence, code", [
    ([], "W-APPROVAL-MISSING"),
    ([dict(APPROVAL, approver="someone-else")], "W-APPROVER-NOT-ALLOWED"),
], ids=["no-approval-record", "approver-not-allowed"])
def test_wsm_5_an_unapproved_waiver_is_refused(tmp_path, evidence, code):
    # Without a valid approval the lowered mode is a change the classifier cannot
    # order, and the waiver that would excuse it is named as the fault.
    report, _, _ = _lint(tmp_path, evidence)
    assert sorted(f.code for f in report.errors) == ["C-INCOMPARABLE", code], report.errors
