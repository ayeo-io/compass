"""A human check can name approvers (issue `human-check-approvers`).

A `human` check is a ticked box. With `approvers:` the tick counts only when a
`human-approval` record for the check, by a listed approver, is current for
the issue and its generation. Without `approvers:` a tick is enough.

Scenario ids: `HA-1` to `HA-9`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_entry_exit_evaluation import (_by_check, _config_project, _rows,  # noqa: E402
                                        _view, _write_review)
from test_generation_store import SLUG, _manifest, _write_manifest  # noqa: E402

CHECK = "dor-summary-filled"


def _approver(*names):
    def mutate(resolved):
        resolved["checks"][CHECK]["approvers"] = list(names)
    return mutate


def _record(**changes):
    body = {"id": "EV-APPROVE-1", "type": "human-approval", "check": CHECK,
            "approver": "alice", "role": "owner", "scope": "the summary",
            "decision": "approved", "timestamp": "2026-10-08T09:00:00Z",
            "issue": SLUG, "generation": None}
    body.update(changes)
    return {k: v for k, v in body.items() if v is not None or k == "generation"}


def _row(tmp_path, monkeypatch, approvers, records=(), **manifest_changes):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)
    _write_manifest(task_dir, evidence=list(records), **manifest_changes)
    mutate = _approver(*approvers) if approvers is not None else None
    return _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))[CHECK]


def test_ha_1_a_human_check_without_approvers_passes_on_a_tick(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, None)
    assert row.status == "pass" and "ticked" in row.detail


def test_ha_2_with_approvers_a_tick_alone_fails_and_names_who_may_approve(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice", "bob"])
    assert row.status == "fail"
    assert "no approval record" in row.detail
    assert "alice" in row.detail and "bob" in row.detail


def test_ha_3_a_current_approval_by_a_listed_approver_passes(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice", "bob"], [_record()])
    assert row.status == "pass"
    assert "EV-APPROVE-1" in row.detail and "alice" in row.detail


def test_ha_4_an_approval_by_someone_not_listed_does_not_count(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["bob"], [_record(approver="alice")])
    assert row.status == "fail"
    assert "approver not listed" in row.detail
    assert "alice" in row.detail and "bob" in row.detail


def test_ha_4_a_listed_approvers_record_counts_beside_an_unlisted_one(tmp_path, monkeypatch):
    records = [_record(id="EV-APPROVE-1", approver="bob"),
               _record(id="EV-APPROVE-2", approver="mallory")]
    row = _row(tmp_path, monkeypatch, ["bob"], records)
    assert row.status == "pass" and "EV-APPROVE-1" in row.detail


def test_ha_4_the_agent_is_not_an_approver(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["agent"], [_record(approver="agent")])
    assert row.status == "fail" and "approver not listed" in row.detail


def test_ha_5_an_approval_written_for_another_issue_does_not_count(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(issue="another-issue")])
    assert row.status == "fail"
    assert "another-issue" in row.detail and SLUG in row.detail
    assert "alice" in row.detail


def test_ha_5_an_approval_with_no_issue_does_not_count(tmp_path, monkeypatch):
    record = _record()
    del record["issue"]
    row = _row(tmp_path, monkeypatch, ["alice"], [record])
    assert row.status == "fail" and "issue" in row.detail


def test_ha_6_an_approval_from_an_earlier_generation_does_not_count(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(generation=1)], generation=2)
    assert row.status == "fail"
    assert "generation" in row.detail and "alice" in row.detail


def test_ha_6_an_approval_of_the_current_generation_counts(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(generation=2)], generation=2)
    assert row.status == "pass"


def test_ha_7_an_approval_for_another_check_or_without_approval_does_not_count(
        tmp_path, monkeypatch):
    changes = ({"check": "dor-no-open-questions"}, {"decision": "rejected"},
               {"type": "manual-review"})
    for number, change in enumerate(changes):
        (tmp_path / str(number)).mkdir()
        row = _row(tmp_path / str(number), monkeypatch, ["alice"], [_record(**change)])
        assert row.status == "fail" and "no approval record" in row.detail, change


def test_ha_7_an_approval_missing_a_required_field_does_not_count(tmp_path, monkeypatch):
    record = _record()
    del record["timestamp"]
    row = _row(tmp_path, monkeypatch, ["alice"], [record])
    assert row.status == "fail" and "timestamp" in row.detail


def test_ha_8_an_approval_does_not_replace_the_tick(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir, ticked=[1, 2, 3, 4, 5, 6])
    _write_manifest(task_dir, evidence=[_record()])
    rows = _by_check(_rows(_view(root, monkeypatch, _approver("alice")), task_dir))
    assert rows[CHECK].status == "fail" and "not ticked" in rows[CHECK].detail


def test_ha_9_an_approval_binds_one_check_not_its_neighbours(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)
    _write_manifest(task_dir, evidence=[_record()])

    def mutate(resolved):
        _approver("alice")(resolved)
        resolved["checks"]["dor-no-open-questions"]["approvers"] = ["alice"]

    rows = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))
    assert rows[CHECK].status == "pass"
    assert rows["dor-no-open-questions"].status == "fail"
    assert "no approval record" in rows["dor-no-open-questions"].detail


def test_ha_9_the_manifest_is_not_changed_by_reading(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)
    _write_manifest(task_dir, evidence=[_record()])
    before = copy.deepcopy(_manifest(task_dir))
    _rows(_view(root, monkeypatch, _approver("alice")), task_dir)
    assert _manifest(task_dir) == before


def test_ha_10_the_stage_list_module_and_its_doc_say_approvers_are_read():
    from compass_pkg import stage_lists
    assert "approvers" in stage_lists.__doc__
    doc = (ROOT / "docs" / "entry-exit-evaluation.md").read_text(encoding="utf-8")
    assert "## Approvers on a human check" in doc
    assert "`approvers:` are not read" not in doc
