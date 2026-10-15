"""A person approves or rejects by typing `/compass:approve` or
`/compass:reject` in Claude Code (issue `approve-inside-claude-code`,
ADR-068).

`prompt_approval.handle` turns a `UserPromptExpansion` hook input into a
block with a reason, or a recorded answer with a confirmation. It records
only one shown, current request for the session's issue, through
`approvals.record`, then closes the request. These tests drive it in-process
with hook input in the shape U0 measured on Claude Code 2.1.300.

Scenario ids: `TRC-A1` to `TRC-A5`, `TRC-C1` to `TRC-C8`, `TRC-C11`,
`TRC-C12`, `TRC-D2`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (CHECK, OWNER, SLUG, closed_dir, event,  # noqa: E402
                              manifest_of, pending_dir, project, read_request, run,
                              save_manifest, task_dir)

COMMANDS = ("approve", "reject", "delegate", "revoke")


def _plugin(tmp_path, flag=True):
    """A plugin root whose command files set the flag the hook requires."""
    root = tmp_path / "plugin"
    (root / "commands").mkdir(parents=True, exist_ok=True)
    for name in COMMANDS:
        front = "disable-model-invocation: true\n" if flag else ""
        (root / "commands" / f"{name}.md").write_text(
            f"---\ndescription: {name}\n{front}---\n\nBody.\n", encoding="utf-8")
    return root


def _handle(root, plugin, env=None, **kw):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, **kw), dict(env or {}), plugin_root=str(plugin))


def _request(root, form, value=None, scope="", shown=True):
    from compass_pkg import approval_requests
    req = approval_requests.write(str(task_dir(root)), form, value, scope)
    if shown:
        req = approval_requests.mark_shown(str(task_dir(root)), req)
    return req


def _records(root, kind="human-approval"):
    return [e for e in manifest_of(root).get("evidence") or [] if e.get("type") == kind]


def _g5_row(root):
    from compass_pkg import checks
    return checks._check_human_approval(manifest_of(root), str(task_dir(root)))


@pytest.fixture
def setup(tmp_path):
    return project(tmp_path), _plugin(tmp_path)


# --- the guardrail 5 sign-off is recorded from a typed prompt (`TRC-A1`) ------------------

def test_a1_g5_signoff_recorded_from_prompt(setup):
    root, plugin = setup
    req = _request(root, "guardrail", "G5", "refund table migration")
    started = time.monotonic()
    result = _handle(root, plugin, prompt_id="p-a1")
    took = time.monotonic() - started
    assert not result.block, result
    records = _records(root)
    assert len(records) == 1, records
    rec = records[0]
    assert {k: rec[k] for k in ("guardrail", "approver", "role", "decision", "issue",
                                "generation")} == {
        "guardrail": "G5", "approver": OWNER, "role": "owner", "decision": "approved",
        "issue": SLUG, "generation": 1}
    assert rec["via"] == "prompt" and rec["host"] == "claude-code"
    assert rec["session_id"] == "sess-1" and rec["prompt_id"] == "p-a1"
    assert rec["request"] == 1 and rec["nonce"] == req["nonce"]
    assert rec["approver_source"] == "owner"
    assert rec["scope"] == "refund table migration"
    ok, detail = _g5_row(root)
    assert ok, detail
    assert rec["id"] in result.message and "guardrail 5" in result.message, result.message
    assert "\n" not in result.message.strip()
    assert not list(pending_dir(root).glob("*.yml"))
    closed = read_request(closed_dir(root) / "1.yml")
    assert closed["outcome"] == "approved" and closed["evidence"] == [rec["id"]]
    assert rec["id"] in result.context and "go on" in result.context.lower()
    assert took < 2.0, took


# --- each subject form is recorded as its terminal form records it (`TRC-A2`) -------------

_VOLATILE = {"timestamp", "via", "host", "session_id", "prompt_id", "request", "nonce",
             "approver_source"}


def _same_as_terminal(prompt_root, terminal_root, argv, plugin, form, value, scope=""):
    before = len(manifest_of(prompt_root).get("evidence") or [])
    _request(prompt_root, form, value, scope)
    result = _handle(prompt_root, plugin)
    assert not result.block, result
    code, out, err = run(terminal_root, "evidence", "approve", "--issue", SLUG, *argv,
                         "--approver", OWNER, "--role", "owner", terminal=True)
    assert code == 0, out + err
    got = manifest_of(prompt_root)["evidence"][before:]
    want = manifest_of(terminal_root)["evidence"][before:]
    assert got and len(got) == len(want), (got, want)
    for g, w in zip(got, want):
        assert g["via"] == "prompt" and g["request"] >= 1, g
        assert w["via"] == "terminal", w
        assert ({k: v for k, v in g.items() if k not in _VOLATILE}
                == {k: v for k, v in w.items() if k not in _VOLATILE}), (g, w)
    return got


def test_a2_subject_forms_match_terminal(tmp_path):
    plugin = _plugin(tmp_path)
    # A human check, and a document awaiting approval.
    root = project(tmp_path / "a")
    body = manifest_of(root)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "td.md").write_text("# design\n", encoding="utf-8")
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design",
                          "status": "awaiting-approval", "path": "docs/td.md"}]
    save_manifest(root, body)
    twin = tmp_path / "b" / "proj"
    shutil.copytree(root, twin)
    _same_as_terminal(root, twin, ["--check", CHECK, "--scope", "the review"], plugin,
                      "check", CHECK, scope="the review")
    _same_as_terminal(root, twin, ["--artifact", "technical-design"], plugin, "artifact",
                      "technical-design")
    assert manifest_of(root)["artifacts"][0]["status"] == "approved"

    # A checkpoint, and the decisions taken for the person.
    from test_checkpoint_outcomes import _define_done, edit
    from test_checkpoint_outcomes import project as checkpoint_project
    croot = checkpoint_project(tmp_path / "c")
    _define_done(croot)
    edit(croot, decisions_taken=[{"id": "DEC-1", "question": "q", "resolution": "r",
                                  "by": "spec-author", "stage": "define", "status": "open"}])
    ctwin = tmp_path / "d" / "repo"
    shutil.copytree(croot, ctwin)
    _same_as_terminal(croot, ctwin, ["--checkpoint", "define"], plugin, "checkpoint", "define")
    _same_as_terminal(croot, ctwin, ["--decisions"], plugin, "decisions", None)


# --- rejecting a human check withdraws its approval (`TRC-A3`) ----------------------------

def test_a3_reject_check_withdraws(setup):
    root, plugin = setup
    _request(root, "check", CHECK, "the review")
    assert not _handle(root, plugin).block
    _request(root, "check", CHECK, "the review again")
    result = _handle(root, plugin, command="compass:reject",
                     args="the review missed the migration")
    assert not result.block, result
    last = _records(root)[-1]
    assert last["check"] == CHECK and last["decision"] == "rejected"
    assert last["reason"] == "the review missed the migration"
    from compass_pkg import approval_records, effective
    view = effective.view_or_legacy(str(task_dir(root)))
    status, detail = approval_records.judge(CHECK, view.config["checks"][CHECK],
                                            manifest_of(root), str(task_dir(root)))
    assert status == "fail" and detail.startswith("approval withdrawn"), detail
    assert "the review missed the migration" in result.context
    assert "reject" in result.context.lower()


# --- rejecting a document sends it back to draft (`TRC-A4`) --------------------------------

def test_a4_reject_artifact_to_draft(setup):
    root, plugin = setup
    from compass_pkg import artifact_status, review_records
    body = manifest_of(root)
    (root / "docs").mkdir(exist_ok=True)
    doc = root / "docs" / "td.md"
    doc.write_text("# design\n", encoding="utf-8")
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design",
                          "status": "awaiting-approval", "path": "docs/td.md"}]
    save_manifest(root, body)
    _request(root, "artifact", "technical-design")
    before = len(manifest_of(root)["evidence"])
    result = _handle(root, plugin, command="compass:reject", args="the threat model is missing")
    assert not result.block, result
    after = manifest_of(root)
    entry = after["artifacts"][0]
    assert entry["status"] == "draft"
    assert entry["rejected_by"] == OWNER and entry["rejected_at"]
    assert entry["rejected_reason"] == "the threat model is missing"
    assert entry["rejected_digest"] == review_records.file_digest(str(doc))
    assert len(after["evidence"]) == before
    assert not _records(root, "artifact-approval")

    def stage_exit(task):
        return artifact_status.stage_exit(task, None, "ship", "compass ship-commit",
                                          include_own=True, task_dir=str(task_dir(root)))

    # A later stage record leaves the unchanged file in draft.
    task = manifest_of(root)
    assert stage_exit(task) == []
    assert task["artifacts"][0]["status"] == "draft"
    # Once the file changes, it moves as ADR-050 describes.
    doc.write_text("# design\n\nWith a threat model.\n", encoding="utf-8")
    task = manifest_of(root)
    moved = stage_exit(task)
    assert moved and task["artifacts"][0]["status"] in ("approved", "awaiting-approval")


# --- rejecting the guardrail 5 sign-off writes no approval record (`TRC-A5`) -------------

def test_a5_reject_g5_writes_no_record(setup):
    root, plugin = setup
    _request(root, "guardrail", "G5", "refund migration")
    result = _handle(root, plugin, command="compass:reject", args="the rollback plan is missing")
    assert not result.block, result
    assert not _records(root)
    closed = read_request(closed_dir(root) / "1.yml")
    assert closed["outcome"] == "rejected"
    assert closed["reason"] == "the rollback plan is missing"
    ok, _ = _g5_row(root)
    assert not ok
    assert "not" in result.context and "go on" in result.context, result.context


# --- nothing is waiting (`TRC-C1`) ---------------------------------------------------------

def test_c1_nothing_pending_blocks(setup):
    root, plugin = setup
    before = (task_dir(root) / "manifest.yml").read_bytes()
    result = _handle(root, plugin)
    assert result.block
    assert f"Nothing is waiting for your approval on issue {SLUG}" in result.message
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


# --- several requests are waiting (`TRC-C2`) -----------------------------------------------

def test_c2_several_pending_needs_number(setup):
    root, plugin = setup
    _request(root, "check", CHECK, "the review")
    _request(root, "guardrail", "G5", "refund migration")
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    for needle in ("1", "2", "/compass:approve 1", "/compass:approve 2"):
        assert needle in result.message, result.message
    result = _handle(root, plugin, args="2")
    assert not result.block, result
    assert [r.get("guardrail") for r in _records(root)] == ["G5"]
    assert [p.name for p in pending_dir(root).glob("*.yml")] == ["1.yml"]


# --- the issue moved to a new generation after the request (`TRC-C3`) ----------------------

def test_c3_stale_generation_blocks(setup):
    root, plugin = setup
    _request(root, "guardrail", "G5", "refund migration")
    body = manifest_of(root)
    body["generation"] = 2
    save_manifest(root, body)
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert read_request(closed_dir(root) / "1.yml")["outcome"] == "stale"
    for needle in ("generation 1", "generation 2", "ask again"):
        assert needle in result.message, result.message


# --- the document changed after the request (`TRC-C4`) -------------------------------------

def test_c4_changed_document_blocks(setup):
    root, plugin = setup
    body = manifest_of(root)
    (root / "docs").mkdir(exist_ok=True)
    doc = root / "docs" / "td.md"
    doc.write_text("# design\n", encoding="utf-8")
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design",
                          "status": "awaiting-approval", "path": "docs/td.md"}]
    save_manifest(root, body)
    _request(root, "artifact", "technical-design")
    doc.write_text("# design\n\nChanged.\n", encoding="utf-8")
    result = _handle(root, plugin)
    assert result.block and not _records(root, "artifact-approval")
    assert read_request(closed_dir(root) / "1.yml")["outcome"] == "stale"
    assert "changed since the request" in result.message, result.message


# --- the request has not been shown (`TRC-C5`) ---------------------------------------------

def test_c5_unshown_request_blocks_and_shows(setup):
    root, plugin = setup
    _request(root, "guardrail", "G5", "refund migration", shown=False)
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert "guardrail 5 sign-off" in result.message and "refund migration" in result.message
    assert "again" in result.message
    req = read_request(pending_dir(root) / "1.yml")
    assert req["shown_at"] and req["shown_digest"]
    assert not _handle(root, plugin).block


# --- the approve command takes only a request number (`TRC-C6`) ----------------------------

def test_c6_bad_argument_blocks(setup):
    root, plugin = setup
    _request(root, "guardrail", "G5", "refund migration")
    for args in ("everything", "7"):
        result = _handle(root, plugin, args=args)
        assert result.block and not _records(root), args
        assert "no argument or one pending request number" in result.message, result.message


# --- no approver can be named (`TRC-C7`) ---------------------------------------------------

def test_c7_no_approver_blocks(setup):
    root, plugin = setup
    (root / "compass.yml").write_text(
        (root / "compass.yml").read_text(encoding="utf-8").replace(f"owner: {OWNER}\n", ""),
        encoding="utf-8")
    _request(root, "guardrail", "G5", "refund migration")
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert "owner:" in result.message and "COMPASS_APPROVER" in result.message
    # The agent is never an approver.
    result = _handle(root, plugin, env={"COMPASS_APPROVER": "agent"})
    assert result.block and not _records(root)


# --- the approver is not listed for the check (`TRC-C8`) -----------------------------------

def test_c8_unlisted_approver_blocks(setup):
    root, plugin = setup
    _request(root, "check", CHECK, "the review")
    result = _handle(root, plugin, env={"COMPASS_APPROVER": "qa-lead"})
    assert result.block and not _records(root)
    assert f"qa-lead is not an approver of '{CHECK}'" in result.message, result.message


# --- the session's issue cannot be named, or the request is for another (`TRC-C11`) ------

def test_c11_issue_resolution_never_guesses(setup):
    root, plugin = setup
    _request(root, "guardrail", "G5", "refund migration")
    pointer = root / ".compass" / "current-task"
    pointer.unlink()
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert "current-task" in result.message
    # Another session moved the pointer since this session recorded its issue.
    pointer.write_text(SLUG + "\n", encoding="utf-8")
    other = root / ".compass" / "work" / "other"
    other.mkdir()
    (other / "manifest.yml").write_text((task_dir(root) / "manifest.yml").read_text())
    from compass_pkg import session_lease
    session_lease.record(str(root / ".compass"), "sess-1", "other")
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert "other" in result.message
    # A request whose issue is not the session's issue is never recorded.
    session_lease.record(str(root / ".compass"), "sess-1", SLUG)
    from compass_pkg import approval_requests
    req = approval_requests.pending(str(task_dir(root)))[0]
    req["issue"] = "other"
    approval_requests.save(str(task_dir(root)), req)
    approval_requests.mark_shown(str(task_dir(root)), req)
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    # COMPASS_ISSUE names the session's issue ahead of the pointer.
    result = _handle(root, plugin, env={"COMPASS_ISSUE": "missing"})
    assert result.block and not _records(root)


# --- a request is answered once (`TRC-C12`) ------------------------------------------------

def test_c12_request_nonce_single_use(setup):
    root, plugin = setup
    from compass_pkg import approval_requests
    req = _request(root, "guardrail", "G5", "refund migration")
    first = _handle(root, plugin, args="1", prompt_id="p-1")
    assert not first.block, first
    # The same command again, and the same hook input replayed.
    for prompt_id in ("p-2", "p-1"):
        result = _handle(root, plugin, args="1", prompt_id=prompt_id)
        assert result.block and len(_records(root)) == 1
        assert "already answered" in result.message, result.message
    # A pending request whose nonce a record already holds is treated as closed.
    stale = dict(req, number=5)
    approval_requests.save(str(task_dir(root)), stale)
    approval_requests.mark_shown(str(task_dir(root)), stale)
    result = _handle(root, plugin, args="5", prompt_id="p-3")
    assert result.block and len(_records(root)) == 1
    assert "already answered" in result.message
    assert not (pending_dir(root) / "5.yml").exists()
    # A new request answered with a prompt_id a record already holds.
    _request(root, "check", CHECK, "the review")
    result = _handle(root, plugin, prompt_id="p-1")
    assert result.block and len(_records(root)) == 1, result
    assert "already" in result.message


# --- the agent changes the request after it was shown (`TRC-D2`) --------------------------

def test_d2_changed_after_shown_blocks(setup):
    root, plugin = setup
    from compass_pkg import approval_requests
    req = _request(root, "guardrail", "G5", "fix a README typo")
    edited = dict(req, scope="the refund migration")
    approval_requests.save(str(task_dir(root)), edited)
    result = _handle(root, plugin)
    assert result.block and not _records(root)
    assert "the refund migration" in result.message and "again" in result.message
    assert not _handle(root, plugin).block
