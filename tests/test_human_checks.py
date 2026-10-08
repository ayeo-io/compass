"""A human check can name approvers (issue `human-check-approvers`).

A `human` check is a ticked box. With `approvers:` the tick counts only when a
`human-approval` record for the check, by a listed approver, is current for
the issue and its generation. Without `approvers:` a tick is enough.

The newest usable record by a listed approver decides, so a later rejection
withdraws an approval. A deferral tag does not excuse a check that lists
approvers. `compass evidence approve` records an approval from a terminal.

Scenario ids: `HA-1` to `HA-22`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import copy
import json
import os
import pty
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_entry_exit_evaluation import (DONE, _by_check, _config_project,  # noqa: E402
                                        _deferred_report, _rows, _view, _write_review)
from test_generation_store import (CLI, SLUG, _env, _evaluate_write, _manifest,  # noqa: E402
                                   _project, _run, _write_manifest)

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
    changes = ({"check": "dor-no-open-questions"}, {"decision": "pending"},
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


# --- HA-11: the newest usable record by a listed approver decides --------------------

def test_ha_11_a_later_rejection_by_a_listed_approver_withdraws_an_approval(
        tmp_path, monkeypatch):
    records = [_record(id="EV-APPROVE-1"),
               _record(id="EV-APPROVE-2", decision="rejected")]
    row = _row(tmp_path, monkeypatch, ["alice"], records)
    assert row.status == "fail"
    assert "approval withdrawn" in row.detail and "EV-APPROVE-2" in row.detail


def test_ha_11_a_later_approval_after_a_rejection_passes(tmp_path, monkeypatch):
    records = [_record(id="EV-APPROVE-1", decision="rejected"), _record(id="EV-APPROVE-2")]
    row = _row(tmp_path, monkeypatch, ["alice"], records)
    assert row.status == "pass" and "EV-APPROVE-2" in row.detail


def test_ha_11_a_rejection_by_someone_not_listed_withdraws_nothing(tmp_path, monkeypatch):
    records = [_record(id="EV-APPROVE-1"),
               _record(id="EV-APPROVE-2", approver="mallory", decision="rejected")]
    row = _row(tmp_path, monkeypatch, ["alice"], records)
    assert row.status == "pass" and "EV-APPROVE-1" in row.detail


def test_ha_11_a_rejection_alone_fails(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(decision="rejected")])
    assert row.status == "fail" and "approval withdrawn" in row.detail


# --- HA-12: a deferral does not excuse a check that lists approvers ------------------

DEFERRED = "dod-every-scenario-passes"
TAGS = [("(evidence: EV-T1)", {"evidence": [{"id": "EV-T1", "type": "test-run",
                                              "path": "e.json"}]}),
        ("(follow-up: FU-1)", {"follow_ups": [{"id": "FU-1", "status": "outstanding",
                                                "description": "d"}]})]


def _deferred_row(tmp_path, monkeypatch, tag, registry, approvers, records=()):
    root, task_dir = _config_project(tmp_path)
    registry = copy.deepcopy(registry)
    registry["evidence"] = registry.get("evidence", []) + list(records)
    _write_manifest(task_dir, current_phase="ship", **registry)
    _deferred_report(task_dir, tag)

    def mutate(resolved):
        if approvers:
            resolved["checks"][DEFERRED]["approvers"] = list(approvers)

    view = _view(root, monkeypatch, mutate)
    return _by_check(r for r in _rows(view, task_dir) if r.side == "exit")[DEFERRED]


@pytest.mark.parametrize("tag, registry", TAGS)
def test_ha_12_a_deferral_without_approvers_still_passes(tmp_path, monkeypatch, tag, registry):
    row = _deferred_row(tmp_path, monkeypatch, tag, registry, None)
    assert row.status == "pass" and row.detail.startswith("deferred with ")


@pytest.mark.parametrize("tag, registry", TAGS)
def test_ha_12_a_deferral_with_approvers_and_no_approval_fails(
        tmp_path, monkeypatch, tag, registry):
    row = _deferred_row(tmp_path, monkeypatch, tag, registry, ["alice"])
    assert row.status == "fail"
    assert "no approval record" in row.detail and "alice" in row.detail


@pytest.mark.parametrize("tag, registry", TAGS)
def test_ha_12_a_deferral_with_a_current_listed_approval_passes(
        tmp_path, monkeypatch, tag, registry):
    record = _record(check=DEFERRED)
    row = _deferred_row(tmp_path, monkeypatch, tag, registry, ["alice"], [record])
    assert row.status == "pass" and "EV-APPROVE-1" in row.detail


# --- HA-13: the owner entry names the project's owner ---------------------------------

def _owner_row(tmp_path, monkeypatch, owner, approver):
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)
    _write_manifest(task_dir, evidence=[_record(approver=approver)])
    if owner:
        path = root / "compass.yml"
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
        body["owner"] = owner
        path.write_text(yaml.safe_dump(body), encoding="utf-8")
    return _by_check(_rows(_view(root, monkeypatch, _approver("owner")), task_dir))[CHECK]


def test_ha_13_owner_means_the_project_owner(tmp_path, monkeypatch):
    row = _owner_row(tmp_path, monkeypatch, "jed72", "jed72")
    assert row.status == "pass" and "jed72" in row.detail


def test_ha_13_someone_other_than_the_owner_is_not_listed(tmp_path, monkeypatch):
    row = _owner_row(tmp_path, monkeypatch, "jed72", "alice")
    assert row.status == "fail" and "approver not listed" in row.detail
    assert "jed72" in row.detail


def test_ha_13_the_word_owner_is_not_a_person_when_the_project_has_none(tmp_path, monkeypatch):
    row = _owner_row(tmp_path, monkeypatch, None, "owner")
    assert row.status == "fail" and "approver not listed" in row.detail
    assert "no project owner" in row.detail


# --- HA-14: a record needs every field, and the detail shows what it read -------------

@pytest.mark.parametrize("field", ["approver", "role", "scope", "timestamp"])
def test_ha_14_a_record_missing_a_required_field_is_set_aside(tmp_path, monkeypatch, field):
    record = _record()
    del record[field]
    row = _row(tmp_path, monkeypatch, ["alice"], [record])
    assert row.status == "fail" and field in row.detail


def test_ha_14_the_detail_shows_values_with_repr_and_none_for_absent(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(approver="al; ice")])
    assert "'al; ice'" in row.detail
    record = _record()
    del record["issue"]
    (tmp_path / "second").mkdir()
    row = _row(tmp_path / "second", monkeypatch, ["alice"], [record])
    assert "issue none" in row.detail


def test_ha_14_the_detail_of_no_record_lists_what_a_record_holds(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"])
    for needle in ("check", "decision", "approver", "role", "scope", "timestamp",
                   "issue", "generation", "compass evidence approve"):
        assert needle in row.detail, needle


def test_ha_14_registry_entries_that_are_not_maps_are_skipped(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], ["junk", 5, None, _record()])
    assert row.status == "pass"


# --- HA-15: the generation is compared as written, and 0 is not absent -----------------

def test_ha_15_a_record_of_generation_zero_is_not_the_absent_generation(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(generation=0)])
    assert row.status == "fail" and "another generation" in row.detail
    assert "generation 0" in row.detail


def test_ha_15_a_record_with_no_generation_does_not_match_a_generation(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"], [_record(generation=None)], generation=1)
    assert row.status == "fail" and "generation none" in row.detail


# --- HA-16: the newest record explains the failure ---------------------------------------

def test_ha_16_the_newest_failing_record_gives_the_cause(tmp_path, monkeypatch):
    records = [_record(id="EV-APPROVE-1", approver="mallory"),
               _record(id="EV-APPROVE-2", issue="another-issue")]
    row = _row(tmp_path, monkeypatch, ["alice"], records)
    assert row.status == "fail"
    assert row.detail.startswith("approval is for another issue")
    assert "EV-APPROVE-2" in row.detail


# --- HA-17 to HA-24: `compass evidence approve` ---------------------------------------

SIGN_OFF = "sign-off"
STATEMENT = "The owner signs off the plan."
EXAMPLE = ROOT / "tests" / "fixtures" / "evidence-approve-example.json"
DOC = ROOT / "docs" / "entry-exit-evaluation.md"


def _cli_project(tmp_path):
    """A project with an owner, a human check that lists `owner` and `maria`,
    one that lists nobody, both in the `plan` entry list, and the box ticked."""
    human = {"kind": "human", "severity": "blocking", "on_skipped": "fail"}
    config = {"schema": 1, "owner": "jed72", "capabilities": {"entry-exit-evaluation": True},
              "checks": {SIGN_OFF: dict(human, statement=STATEMENT,
                                        approvers=["owner", "maria"]),
                         "open-check": dict(human, statement="Anyone may tick this.")},
              "stages": {"plan": {"set": {"entry": {"add": [SIGN_OFF, "open-check"]}}}}}
    root, task_dir = _project(tmp_path, compass_yml=config)
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="plan")
    (task_dir / "requirements-review.md").write_text(
        f"# R\n\n### Definition of Ready\n\n- [x] {STATEMENT}\n"
        f"- [x] Anyone may tick this.\n\nNext stage: x\n", encoding="utf-8")
    return root, task_dir


def _approve(root, *extra, check=SIGN_OFF, approver="jed72", role="owner",
             scope="the plan", terminal=True):
    """Run the verb. With `terminal` its stdin is a pseudo-terminal, as it is
    when a person types the command; without, stdin is empty, as in an agent
    session."""
    argv = [sys.executable, str(CLI), "evidence", "approve", "--check", check,
            "--issue", SLUG, "--approver", approver, "--role", role, "--scope", scope, *extra]
    master = slave = None
    if terminal:
        master, slave = pty.openpty()
    try:
        r = subprocess.run(argv, cwd=root, env=_env(root), capture_output=True, text=True,
                           stdin=slave if terminal else subprocess.DEVNULL, timeout=180)
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    return r.returncode, r.stdout, r.stderr


def _sign_off_row(root):
    out = _run(root, "check", "--issue", SLUG, "--json")[1]
    rows = [r for r in json.loads(out)["checks"] if r["name"] == SIGN_OFF]
    assert len(rows) == 1, out
    return rows[0]


def test_ha_17_the_verb_refuses_without_a_terminal_and_writes_nothing(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = _approve(root, terminal=False)
    assert code == 2 and "terminal" in out + err
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == before


def test_ha_17_the_verb_from_a_terminal_writes_a_record_that_clears_the_check(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    assert _sign_off_row(root)["status"] == "fail"
    code, out, err = _approve(root)
    assert code == 0, out + err
    entry = _manifest(task_dir)["evidence"][-1]
    assert entry["id"] == "EV-APPROVAL-sign-off-1" and entry["type"] == "human-approval"
    assert (entry["check"], entry["decision"], entry["approver"]) == (SIGN_OFF, "approved",
                                                                     "jed72")
    assert (entry["role"], entry["scope"], entry["issue"]) == ("owner", "the plan", SLUG)
    assert entry["generation"] == 1 and re.fullmatch(r"\d{4}-\d\d-\d\dT.*Z", entry["timestamp"])
    assert _sign_off_row(root)["status"] == "pass"


def test_ha_17_a_second_record_takes_the_next_number(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    assert _approve(root)[0] == 0 and _approve(root, approver="maria", role="lead")[0] == 0
    ids = [e["id"] for e in _manifest(task_dir)["evidence"]]
    assert ids[-2:] == ["EV-APPROVAL-sign-off-1", "EV-APPROVAL-sign-off-2"]


def test_ha_17_the_scope_is_written_with_its_whitespace_collapsed(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    assert _approve(root, scope="  the   plan \n section ")[0] == 0
    assert _manifest(task_dir)["evidence"][-1]["scope"] == "the plan section"


@pytest.mark.parametrize("change", [
    {"approver": "agent"}, {"approver": "Agent"}, {"approver": "agent:session-1"},
    {"approver": " "}, {"role": " "}, {"scope": ""},
    {"approver": "mallory"}, {"approver": "owner"},
    {"check": "open-check"}, {"check": "no-such-check"}, {"check": "dor-summary-filled"},
])
def test_ha_18_the_verb_refuses_and_writes_nothing(tmp_path, change):
    root, task_dir = _cli_project(tmp_path)
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = _approve(root, **change)
    assert code == 2, out + err
    assert (task_dir / "manifest.yml").read_text(encoding="utf-8") == before


def test_ha_18_a_refusal_names_the_reason(tmp_path):
    root, _ = _cli_project(tmp_path)
    for name in ("agent", "agent:session-1"):
        assert "an agent cannot approve" in "".join(_approve(root, approver=name)[1:])
    assert "not a human check" in "".join(_approve(root, check="dashboard-current")[1:])
    text = "".join(_approve(root, approver="mallory")[1:])
    assert "jed72" in text and "maria" in text
    assert "lists no approvers" in "".join(_approve(root, check="open-check")[1:])


def test_ha_18_a_decision_other_than_approved_or_rejected_is_refused(tmp_path):
    root, _ = _cli_project(tmp_path)
    assert _approve(root, "--decision", "maybe")[0] == 2


def test_ha_19_a_rejection_is_recorded_and_withdraws_the_approval(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    assert _approve(root)[0] == 0 and _sign_off_row(root)["status"] == "pass"
    assert _approve(root, "--decision", "rejected")[0] == 0
    row = _sign_off_row(root)
    assert row["status"] == "fail" and "approval withdrawn" in row["detail"]


def test_ha_20_owner_and_a_named_person_are_accepted_approvers(tmp_path):
    root, _ = _cli_project(tmp_path)
    assert _approve(root, approver="jed72")[0] == 0
    assert _approve(root, approver="maria")[0] == 0


# --- HA-21: the --json document is pinned ---------------------------------------------

def _masked(text):
    document = json.loads(text)
    document["at"] = "..."
    return json.dumps(document, indent=2)


def _example_output(tmp_path):
    root, _ = _cli_project(tmp_path)
    return _approve(root, "--json")


def test_ha_21_the_json_document_has_these_keys(tmp_path):
    code, out, err = _example_output(tmp_path)
    assert code == 0, err
    document = json.loads(out)
    assert set(document) == {"outcome", "check", "answer", "evidence_id", "approver",
                             "role", "scope", "issue", "generation", "at", "detail"}
    assert document["evidence_id"] == "EV-APPROVAL-sign-off-1"


def test_ha_21_the_pinned_example_is_the_real_output_and_the_doc_shows_it(tmp_path):
    code, out, err = _example_output(tmp_path)
    pinned = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.is_file() else ""
    assert code == 0 and pinned == _masked(out) + "\n"
    shown = [block for block in re.findall(r"```json\n(.*?)```", DOC.read_text(encoding="utf-8"),
                                           re.S) if '"evidence_id"' in block]
    assert len(shown) == 1 and shown[0].strip() == pinned.strip()


# --- HA-22: help, owning doc, router, schema, hint, corpus ------------------------------

def test_ha_22_the_help_text_names_the_flags_the_terminal_and_the_exit_code():
    from compass_pkg import verb_help
    text = verb_help.VERB_DESCRIPTIONS.get("evidence approve", "")
    for needle in ("--check", "--approver", "--role", "--scope", "--decision", "terminal",
                   "agent", "exit 2"):
        assert needle in text, needle
    out = subprocess.run([sys.executable, str(CLI), "evidence", "approve", "--help"],
                         capture_output=True, text=True).stdout
    for flag in ("--check", "--approver", "--role", "--scope", "--decision", "--issue"):
        assert flag in out, flag


def test_ha_22_the_owning_doc_says_what_is_protected_and_what_is_not():
    doc = " ".join(DOC.read_text(encoding="utf-8").split())
    for needle in ("compass evidence approve", "needs a terminal", "refuses the approver `agent`",
                   "Anyone who can write `manifest.yml`", "an agent included",
                   "`owner` names the project's owner", "Any other entry is read as a person id"):
        assert needle in doc, needle
    router = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert any("cli/compass_pkg/approve_cmd.py" in line and "entry-exit-evaluation.md" in line
               for line in router.splitlines())
    kinds = [line for line in DOC.read_text(encoding="utf-8").splitlines()
             if line.startswith("| `human` |")]
    assert kinds and "approvers" in kinds[0]


def test_ha_22_the_manifest_reference_lists_the_approval_keys():
    reference = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8")
    start = reference.index("human-approval")
    for key in ("check:", "issue:", "generation:", "approver:", "role:", "scope:", "decision:",
                "timestamp:"):
        assert key in reference[start:start + 2500], key
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]["evidence"]["items"]["properties"]
    for key in ("check", "issue", "generation"):
        assert key in properties, key


def test_ha_22_the_sign_off_hint_names_the_verb():
    from compass_pkg import check_cmd
    hint = check_cmd.CHECK_GUIDANCE["human-approval-present"]["do"]
    assert "compass evidence approve" in hint


def test_ha_22_the_failure_detail_names_the_verb(tmp_path, monkeypatch):
    row = _row(tmp_path, monkeypatch, ["alice"])
    assert "compass evidence approve" in row.detail


def test_ha_22_the_corpus_has_the_verb_with_its_exit_codes():
    import compat_commands as cc
    entries = {e["id"]: e for e in cc.load()}
    expected = {"evidence-approve-unknown-check": 2, "evidence-approve-agent-refused": 2}
    assert set(expected) <= set(entries)
    assert {i: entries[i]["exit"] for i in expected} == expected
