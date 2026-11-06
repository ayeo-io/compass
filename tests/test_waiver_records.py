"""A waiver excuses one check on one issue, with a reason and a person's approval.

#357 section 4 and ADR-094. The template project of `approval_support` names
the owner `jed72`; its issue `feature` fails `suite-passed` and
`scenarios-have-tests`, and, labelled payments, `human-approval-present`.

Each rule below has a test that fails when the rule is reverted:

- `compass waiver add` refuses a waiver with no reason;
- a waiver no `human-approval` record approves excuses nothing;
- `compass waiver add` refuses a check the check set never waives, and a
  hand-written waiver of one excuses nothing;
- a delegation typed without `--for waivers` does not approve a waiver;
- an approved waiver excuses its one check, on its one issue.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (OWNER, SLUG, event, manifest_of, project,  # noqa: E402
                              run, save_manifest, task_dir)
from delegation_support import copy_issue, delegated, set_generation  # noqa: E402

CHECK = "suite-passed"
OTHER = "scenarios-have-tests"
NEVER = "human-approval-present"
REASON = "the suite runs only in the nightly CI job"
AGENT = "compass:architect"


def _hook(root, args, command="compass:approve", session="sess-1"):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session),
                                  {}, plugin_root=str(ROOT))


def _statuses(root, slug=SLUG):
    code, out, err = run(root, "check", "--json", "--issue", slug)
    body = json.loads(out)
    return {c["name"]: c["status"] for c in body["checks"]}, body


def _add(root, check=CHECK, reason=REASON, slug=SLUG):
    return run(root, "waiver", "add", "--check", check, "--reason", reason, "--issue", slug)


def _request(root, waiver="W-1", slug=SLUG):
    """Ask for the approval and show the request, as the Stop hook does."""
    from compass_pkg import approval_requests
    code, out, err = run(root, "evidence", "request", "--waiver", waiver, "--issue", slug)
    assert code == 0, out + err
    approval_requests.stop_message(str(root / ".compass"), {"COMPASS_ISSUE": slug})


def _approved_by_prompt(root):
    assert _add(root)[0] == 0
    _request(root)
    done = _hook(root, "waiver W-1")
    assert not done.block, done.message
    return done


# --- add -----------------------------------------------------------------------------------

def test_add_writes_a_waiver_that_excuses_nothing_yet(tmp_path):
    root = project(tmp_path)
    code, out, err = _add(root)
    assert code == 0, out + err
    waiver = manifest_of(root)["waivers"][0]
    assert {k: waiver[k] for k in ("id", "check", "reason")} == {
        "id": "W-1", "check": CHECK, "reason": REASON}
    statuses, body = _statuses(root)
    assert statuses[CHECK] == "fail"
    assert any("W-1" in n and "compass evidence request --waiver W-1" in n
               for n in body["notices"]), body["notices"]


def test_add_refuses_a_waiver_with_no_reason(tmp_path):
    root = project(tmp_path)
    before = (task_dir(root) / "manifest.yml").read_bytes()
    for reason in ("", "   "):
        code, out, err = _add(root, reason=reason)
        assert code != 0 and "needs a reason" in err, out + err
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


def test_add_refuses_a_check_that_is_never_waived(tmp_path):
    from compass_pkg import check_set, waiver_records
    assert NEVER in waiver_records.never_waived(check_set.load())
    root = project(tmp_path)
    before = (task_dir(root) / "manifest.yml").read_bytes()
    code, out, err = _add(root, check=NEVER)
    assert code != 0 and "never waived" in err, out + err
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


def test_every_check_of_gate_g5_is_never_waived():
    from compass_pkg import check_set, waiver_records
    doc = check_set.load()
    assert set(doc["gates"]["G5"]["checks"]) <= waiver_records.never_waived(doc)
    assert "G5" in waiver_records.never_waived_gates(doc)


def test_add_refuses_a_check_the_policy_does_not_hold_and_a_second_waiver(tmp_path):
    root = project(tmp_path)
    code, out, err = _add(root, check="no-such-check")
    assert code != 0 and "holds no check" in err, out + err
    assert _add(root)[0] == 0
    code, out, err = _add(root)
    assert code != 0 and "already waives" in err, out + err


# --- approval ------------------------------------------------------------------------------

def test_a_waiver_without_an_approval_record_excuses_nothing(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    _request(root)
    statuses, body = _statuses(root)
    assert statuses[CHECK] == "fail"
    assert "waived" not in body


def test_an_approved_waiver_excuses_exactly_one_check_on_one_issue(tmp_path):
    root = project(tmp_path)
    copy_issue(root, root, "second")
    _approved_by_prompt(root)
    record = manifest_of(root)["evidence"][-1]
    assert {k: record[k] for k in ("type", "waiver", "waived_check", "waiver_reason",
                                   "approver", "issue", "via")} == {
        "type": "human-approval", "waiver": "W-1", "waived_check": CHECK,
        "waiver_reason": REASON, "approver": OWNER, "issue": SLUG, "via": "prompt"}
    statuses, body = _statuses(root)
    assert statuses[CHECK] == "waived"
    assert statuses[OTHER] == "fail"
    assert body["waived"] == 1
    assert [n for n, s in statuses.items() if s == "waived"] == [CHECK]
    # The other issue still owes the check.
    assert _statuses(root, "second")[0][CHECK] == "fail"
    # A waiver and its record copied to another issue excuse nothing there.
    other = task_dir(root).parent / "second" / "manifest.yml"
    import yaml
    body = yaml.safe_load(other.read_text(encoding="utf-8"))
    body["waivers"] = manifest_of(root)["waivers"]
    body["evidence"] = list(body.get("evidence") or []) + [record]
    other.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    assert _statuses(root, "second")[0][CHECK] == "fail"


def test_the_waiver_record_never_clears_guardrail_5(tmp_path):
    from compass_pkg import approval_records
    root = project(tmp_path)
    _approved_by_prompt(root)
    record = manifest_of(root)["evidence"][-1]
    assert not approval_records.gives_g5(record)
    assert _statuses(root)[0][NEVER] == "fail"


def test_a_hand_written_waiver_of_a_never_waived_check_excuses_nothing(tmp_path):
    root = project(tmp_path)
    _approved_by_prompt(root)
    body = manifest_of(root)
    body["waivers"][0]["check"] = NEVER
    body["evidence"][-1]["waived_check"] = NEVER
    save_manifest(root, body)
    statuses, _ = _statuses(root)
    assert statuses[NEVER] == "fail"
    assert "waived" not in statuses.values()


def test_a_waiver_changed_after_its_approval_is_not_approved(tmp_path):
    root = project(tmp_path)
    _approved_by_prompt(root)
    body = manifest_of(root)
    body["waivers"][0]["check"] = OTHER
    save_manifest(root, body)
    statuses, _ = _statuses(root)
    assert statuses[OTHER] == "fail" and statuses[CHECK] == "fail"


def test_an_approval_holds_only_at_the_generation_it_was_given_for(tmp_path):
    """A reassessment can raise what the issue owes, such as a risk now
    critical, so an approval from an earlier generation excuses nothing."""
    root = project(tmp_path)
    _approved_by_prompt(root)
    assert _statuses(root)[0][CHECK] == "waived"
    set_generation(task_dir(root), 2)
    statuses, body = _statuses(root)
    assert statuses[CHECK] == "fail"
    assert any("W-1" in n and "generation" in n and "new approval" in n
               for n in body["notices"]), body["notices"]


def test_add_refuses_a_reason_with_control_characters(tmp_path):
    root = project(tmp_path)
    before = (task_dir(root) / "manifest.yml").read_bytes()
    for reason in ("nightly CI\x1b[2K approved earlier", "nightly \u202eevil",
                   "two\nlines"):
        code, out, err = _add(root, reason=reason)
        assert code != 0 and "control" in err, (reason, out + err)
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


def test_the_shown_request_holds_no_control_characters(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path)
    code, out, err = run(root, "evidence", "request", "--check", "dod-reviewed", "--issue",
                         SLUG, "--scope", "scope\x1b[1A\x1b[2K x")
    assert code == 0, out + err
    # A reason written by hand, past `waiver add`, is cleaned too.
    assert _add(root)[0] == 0
    body = manifest_of(root)
    body["waivers"][0]["reason"] = "nightly\x1b[1A\x1b[2K \u202eevil"
    save_manifest(root, body)
    _request(root)
    shown = "\n".join(approval_requests.shown_text(r)
                      for r in approval_requests.pending(str(task_dir(root))))
    assert "\x1b" not in shown and "\u202e" not in shown, repr(shown)
    assert "scope[1A[2K x" in shown and "nightly[1A[2K evil" in shown, repr(shown)


def test_the_hook_refuses_a_waiver_changed_after_the_request_was_shown(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    _request(root)
    body = manifest_of(root)
    body["waivers"][0]["reason"] = "another reason"
    save_manifest(root, body)
    done = _hook(root, "waiver W-1")
    assert done.block and "no longer names" in done.message, done.message
    assert not [e for e in manifest_of(root)["evidence"] if e.get("waiver")]


def test_the_hook_refuses_a_waiver_with_no_request(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    done = _hook(root, "waiver W-1")
    assert done.block and "compass evidence request --waiver W-1" in done.message
    assert not manifest_of(root)["evidence"]


def test_a_person_approves_at_a_terminal_and_a_non_approver_is_refused(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    code, out, err = run(root, "evidence", "approve", "--waiver", "W-1", "--approver",
                         "someone-else", "--role", "dev", terminal=True)
    assert code != 0 and "may not approve" in err, out + err
    code, out, err = run(root, "evidence", "approve", "--waiver", "W-1", "--approver", OWNER,
                         "--role", "owner", terminal=True)
    assert code == 0, out + err
    assert manifest_of(root)["evidence"][-1]["via"] == "terminal"
    assert _statuses(root)[0][CHECK] == "waived"
    code, out, err = run(root, "evidence", "approve", "--waiver", "W-1", "--approver", OWNER,
                         "--role", "owner", "--decision", "rejected", terminal=True)
    assert code != 0 and "approval only" in err, out + err


def test_an_agent_without_a_terminal_cannot_approve(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    code, out, err = run(root, "evidence", "approve", "--waiver", "W-1", "--approver", OWNER,
                         "--role", "owner")
    assert code != 0 and "terminal" in err, out + err
    assert not manifest_of(root)["evidence"]


# --- delegation ----------------------------------------------------------------------------

def test_a_delegation_without_for_waivers_does_not_approve_a_waiver(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    done = _hook(root, f"--agent {AGENT}", command="compass:delegate")
    assert not done.block, done.message
    code, out, err = delegated(root, AGENT, "--waiver", "W-1", "--issue", SLUG)
    assert code != 0 and "not waivers" in err, out + err
    assert not manifest_of(root)["evidence"]
    assert _statuses(root)[0][CHECK] == "fail"


def test_a_delegation_typed_with_for_waivers_needs_the_code_then_approves(tmp_path):
    root = project(tmp_path)
    assert _add(root)[0] == 0
    first = _hook(root, f"--agent {AGENT} --for waivers", command="compass:delegate")
    assert first.block and "approve a waiver" in first.message, first.message
    # Before the code is typed back, nothing covers the waiver.
    code, out, err = delegated(root, AGENT, "--waiver", "W-1", "--issue", SLUG)
    assert code != 0, out + err
    code_text = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    done = _hook(root, f"confirm {code_text}", command="compass:delegate")
    assert not done.block, done.message
    code, out, err = delegated(root, AGENT, "--waiver", "W-1", "--issue", SLUG)
    assert code == 0, out + err
    record = manifest_of(root)["evidence"][-1]
    assert (record["via"], record["approver"], record["waiver"]) == ("delegation", OWNER,
                                                                     "W-1")
    assert _statuses(root)[0][CHECK] == "waived"
    # The person overrules it: the approval is withdrawn and the check runs again.
    done = _hook(root, f"{record['id']} not this time", command="compass:reject")
    assert not done.block, done.message
    assert manifest_of(root)["evidence"][-1]["withdraws"] == record["id"]
    assert _statuses(root)[0][CHECK] == "fail"


# --- withdraw ------------------------------------------------------------------------------

def test_withdraw_removes_an_unapproved_waiver_and_closes_its_request(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path)
    assert _add(root)[0] == 0
    _request(root)
    code, out, err = run(root, "waiver", "withdraw", "W-1")
    assert code == 0, out + err
    assert "waivers" not in manifest_of(root)
    assert not approval_requests.pending(str(task_dir(root)))
    # A new waiver does not take the id a request already named.
    assert _add(root)[0] == 0
    assert manifest_of(root)["waivers"][0]["id"] == "W-2"


def test_withdraw_marks_an_approved_waiver_and_the_check_runs_again(tmp_path):
    root = project(tmp_path)
    _approved_by_prompt(root)
    code, out, err = run(root, "waiver", "withdraw", "W-1")
    assert code == 0, out + err
    assert manifest_of(root)["waivers"][0]["withdrawn_at"]
    assert _statuses(root)[0][CHECK] == "fail"


# --- what stays readable -------------------------------------------------------------------

def test_the_manifest_schema_reads_new_waivers_and_old_waiver_approvals(tmp_path):
    root = project(tmp_path)
    _approved_by_prompt(root)
    body = manifest_of(root)
    body["evidence"].append({"id": "EV-OLD-1", "type": "human-approval",
                             "waiver": {"scope": "issue", "entry": "checks.x", "fields": {}},
                             "approver": OWNER, "role": "owner", "scope": "old",
                             "decision": "approved", "timestamp": "2026-10-01T00:00:00Z"})
    body.pop("current_phase", None)     # the template's own key, which the schema refuses
    save_manifest(root, body)
    code, out, err = run(root, "issue", "lint", "--issue", SLUG)
    assert code == 0, out + err
