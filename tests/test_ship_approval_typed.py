"""The typed ship approval: a person approves the change of an issue at ship.

Step 3 of #355 [Read the ship approval from the merged PR review]. Where no
review of the merged pull request by another person gives the ship approval,
a person types it. It is one `human-approval` record with `ship: <slug>` and
the issue's generation, which `ship-approval-present` reads. These tests
show that:

- a person records it at a terminal, or by typing `/compass:approve` for a
  request the agent made with `compass evidence request --ship`;
- an agent session with no terminal cannot record it;
- a delegation covers it only when typed `--for ship`, and only after the
  person types back the confirmation code;
- the record never clears guardrail `G5`, and a `G5` sign-off is not a ship
  approval (VD-029);
- `/compass:reject <record id>` withdraws a delegated one.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (OWNER, SLUG, event, manifest_of, project,  # noqa: E402
                              run, save_manifest)
from delegation_support import delegated  # noqa: E402

SHIP_CHECK = "ship-approval-present"
G5_CHECK = "human-approval-present"
AGENT = "compass:architect"


def _owing(tmp_path):
    """The template project, with its issue owing the ship approval."""
    root = project(tmp_path)
    body = manifest_of(root)
    owed = list(body.get("evidence_required") or [])
    if "ship-approval" not in owed:
        body["evidence_required"] = owed + ["ship-approval"]
        save_manifest(root, body)
    return root


def _hook(root, args, command="compass:approve", session="sess-1"):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session),
                                  {}, plugin_root=str(ROOT))


def _statuses(root):
    code, out, err = run(root, "check", "--json", "--issue", SLUG)
    body = json.loads(out)
    return {c["name"]: c["status"] for c in body["checks"]}


def _ship_records(root):
    return [e for e in manifest_of(root).get("evidence") or [] if e.get("ship") == SLUG]


def _terminal(root, *extra):
    return run(root, "evidence", "approve", "--ship", "--approver", OWNER, "--role", "owner",
               *extra, terminal=True)


# --- a terminal --------------------------------------------------------------------------------

def test_a_person_approves_at_a_terminal(tmp_path):
    root = _owing(tmp_path)
    assert _statuses(root)[SHIP_CHECK] == "nothing-to-check"
    code, out, err = _terminal(root)
    assert code == 0, out + err
    [record] = _ship_records(root)
    assert {k: record[k] for k in ("type", "ship", "approver", "decision", "issue",
                                   "generation", "via")} == {
        "type": "human-approval", "ship": SLUG, "approver": OWNER, "decision": "approved",
        "issue": SLUG, "generation": manifest_of(root)["generation"], "via": "terminal"}
    assert record["id"] == "EV-SHIP-APPROVAL-1" and "head" in record
    assert _statuses(root)[SHIP_CHECK] == "pass"
    # A second approval while one stands is refused.
    code, out, err = _terminal(root)
    assert code != 0 and "already approved at ship" in err, out + err
    assert len(_ship_records(root)) == 1


def test_the_terminal_refuses_a_rejection_a_non_approver_and_an_issue_that_does_not_owe_it(
        tmp_path):
    root = _owing(tmp_path)
    code, out, err = _terminal(root, "--decision", "rejected")
    assert code != 0 and "--ship records an approval only" in err, out + err
    code, out, err = run(root, "evidence", "approve", "--ship", "--approver", "someone-else",
                         "--role", "dev", terminal=True)
    assert code != 0 and "is not an approver of this project" in err, out + err
    body = manifest_of(root)
    body["evidence_required"] = [t for t in body["evidence_required"] if t != "ship-approval"]
    save_manifest(root, body)
    code, out, err = _terminal(root)
    assert code != 0 and "does not owe the ship approval" in err, out + err
    assert not _ship_records(root)


def test_an_agent_without_a_terminal_cannot_approve(tmp_path):
    root = _owing(tmp_path)
    code, out, err = run(root, "evidence", "approve", "--ship", "--approver", OWNER,
                         "--role", "owner")
    assert code != 0 and "terminal" in err, out + err
    assert not _ship_records(root)


# --- a typed prompt ----------------------------------------------------------------------------

def test_a_person_approves_a_request_by_typing_approve(tmp_path):
    from compass_pkg import approval_requests
    root = _owing(tmp_path)
    code, out, err = run(root, "evidence", "request", "--ship", "--issue", SLUG)
    assert code == 0, out + err
    assert "the ship approval of the change of issue feature" in out, out
    shown = approval_requests.stop_message(str(root / ".compass"), {"COMPASS_ISSUE": SLUG})
    assert "the ship approval of the change of issue feature" in shown, shown
    done = _hook(root, "")
    assert not done.block, done.message
    [record] = _ship_records(root)
    assert (record["via"], record["approver"]) == ("prompt", OWNER)
    assert _statuses(root)[SHIP_CHECK] == "pass"


def test_the_request_names_the_terminal_command_on_a_host_with_no_prompt_event(tmp_path):
    root = _owing(tmp_path)
    code, out, err = run(root, "evidence", "request", "--ship", "--issue", SLUG,
                         COMPASS_APPROVAL_CHANNEL="terminal")
    assert code == 0, out + err
    assert "evidence approve --issue feature --ship --approver <you> --role <role>" in out, out
    assert not _ship_records(root)


# --- a delegation ------------------------------------------------------------------------------

def test_a_default_delegation_does_not_cover_the_ship_approval(tmp_path):
    root = _owing(tmp_path)
    done = _hook(root, f"--agent {AGENT}", command="compass:delegate")
    assert not done.block, done.message
    assert "not the ship approval" in done.message, done.message
    code, out, err = delegated(root, AGENT, "--ship", "--issue", SLUG)
    assert code != 0 and "not the ship approval of a change" in err, out + err
    assert not _ship_records(root)


def test_a_delegation_typed_for_ship_needs_the_code_then_approves(tmp_path):
    root = _owing(tmp_path)
    first = _hook(root, f"--agent {AGENT} --for ship", command="compass:delegate")
    assert first.block and "give the ship approval of a change" in first.message, \
        first.message
    # Before the code is typed back, nothing covers the ship approval.
    code, out, err = delegated(root, AGENT, "--ship", "--issue", SLUG)
    assert code != 0, out + err
    assert not _ship_records(root)
    code_text = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    done = _hook(root, f"confirm {code_text}", command="compass:delegate")
    assert not done.block, done.message
    code, out, err = delegated(root, AGENT, "--ship", "--issue", SLUG)
    assert code == 0, out + err
    [record] = _ship_records(root)
    assert (record["via"], record["approver"], record["approved_by_agent"]) == (
        "delegation", OWNER, AGENT)
    assert _statuses(root)[SHIP_CHECK] == "pass"
    # The person overrules it: the approval is withdrawn and no longer counts.
    done = _hook(root, f"{record['id']} not yet", command="compass:reject")
    assert not done.block, done.message
    assert manifest_of(root)["evidence"][-1]["withdraws"] == record["id"]
    assert _statuses(root)[SHIP_CHECK] == "nothing-to-check"


# --- guardrail `G5` ----------------------------------------------------------------------------

def test_a_ship_approval_never_clears_guardrail_5(tmp_path):
    from compass_pkg import approval_records
    root = _owing(tmp_path)
    assert _statuses(root)[G5_CHECK] == "fail"
    assert _terminal(root)[0] == 0
    [record] = _ship_records(root)
    assert not approval_records.gives_g5(record)
    assert approval_records.subject_of(record) == f"ship '{SLUG}'"
    statuses = _statuses(root)
    assert (statuses[SHIP_CHECK], statuses[G5_CHECK]) == ("pass", "fail")


def test_a_g5_signoff_is_not_a_ship_approval(tmp_path):
    root = _owing(tmp_path)
    code, out, err = run(root, "evidence", "approve", "--guardrail", "G5", "--approver", OWNER,
                         "--role", "owner", "--scope", "the migration", terminal=True)
    assert code == 0, out + err
    statuses = _statuses(root)
    assert (statuses[G5_CHECK], statuses[SHIP_CHECK]) == ("pass", "nothing-to-check"), \
        statuses
    # With the pull request recorded as merged, the `G5` sign-off does not pass it.
    body = manifest_of(root)
    body["pull_request"] = {"repo": "acme/widgets", "number": 42,
                            "merged_at": "2026-11-07T01:48:47Z"}
    save_manifest(root, body)
    assert _statuses(root)[SHIP_CHECK] == "fail"
    assert _terminal(root)[0] == 0
    assert _statuses(root)[SHIP_CHECK] == "pass"
