"""A person delegates approvals to a named agent for a stated time and scope
(issue `approve-inside-claude-code`, ADR-069).

Only the prompt hook writes a delegation, from a typed `/compass:delegate`. A
delegation that covers the guardrail 5 sign-off takes effect only when the
person types back a code the hook showed them (the owner's answer of
2026-10-15). The named agent approves with `compass evidence approve
--delegated --as <agent>`, which needs no terminal and refuses anything the
delegation does not cover.

Scenario ids: `TRC-F1` to `TRC-F7`, `TRC-F11`. Each test name starts with its
scenario id.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (CHECK, OWNER, SLUG, event, manifest_of,  # noqa: E402
                              project, run, save_manifest, task_dir)
from delegation_support import delegated  # noqa: E402

ARCHITECT = "compass:architect"


def _delegations(root):
    folder = root / ".compass" / "delegations"
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("DL-*.yml"))} if folder.is_dir() else {}


def _type(root, args, command="compass:delegate", session="sess-1", env=None):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session),
                                  dict(env or {}), plugin_root=str(ROOT))


@pytest.fixture
def clock(monkeypatch):
    """A fixed local time of 22:10 today."""
    local = datetime.datetime.now().astimezone()
    fixed = local.replace(hour=22, minute=10, second=0, microsecond=0)
    try:
        from compass_pkg import delegations
    except ImportError:          # before the module exists, the test fails on its asserts
        return fixed
    monkeypatch.setattr(delegations, "_now", lambda: fixed)
    return fixed


def _soon(hours=2):
    """An end time `hours` ahead, as a person types it."""
    when = datetime.datetime.now().astimezone() + datetime.timedelta(hours=hours)
    return when.strftime("%H:%M")


def _approve(root, *argv, agent=ARCHITECT):
    """A delegated approval, with the ticket the pre-tool hook would write for it."""
    return delegated(root, agent, "--issue", SLUG, *argv)


# --- a person delegates approvals to a named agent (`TRC-F1`) ---------------------------------

def test_f1_delegate_written_and_confirmed(tmp_path, clock):
    root = project(tmp_path)
    result = _type(root, f"--agent {ARCHITECT} --until 08:00 --on {SLUG} "
                         f"--for checks,documents")
    assert not result.block, result
    found = _delegations(root)
    assert list(found) == ["DL-1"], found
    dl = found["DL-1"]
    end = datetime.datetime.combine((clock + datetime.timedelta(days=1)).date(),
                                    datetime.time(8, 0)).astimezone()
    assert dl["agent"] == ARCHITECT and dl["delegated_by"] == OWNER
    assert dl["created_via"] == "prompt" and dl["session_id"] == "sess-1" and dl["nonce"]
    assert datetime.datetime.fromisoformat(dl["until"].replace("Z", "+00:00")) == end
    assert dl["issues"] == {SLUG: 1}
    assert dl["forms"] == ["checks", "documents"]
    message = result.message
    assert "\n" not in message.strip()
    for needle in (ARCHITECT, end.strftime("%Y-%m-%d"), "08:00", SLUG, "checks",
                   "documents", "not the guardrail 5 sign-off"):
        assert needle in message, (needle, message)


# --- the guardrail 5 sign-off is covered only when named (`TRC-F2`) --------------------------

def test_f2_g5_only_when_named(tmp_path, clock):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until 08:00").block
    assert _delegations(root)["DL-1"]["forms"] == ["checks", "documents", "checkpoints",
                                                    "decisions"]
    # Naming g5 is blocked until the person types back the code shown to them.
    first = _type(root, f"--agent {ARCHITECT} --until 08:00 --for g5,checks")
    assert first.block and list(_delegations(root)) == ["DL-1"]
    code = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    assert code not in (first.context or "")
    # The code is not on disk in clear.
    folder = root / ".compass" / "delegations"
    assert not any(code in p.read_text() for p in folder.rglob("*") if p.is_file())
    # A wrong code, or the right code from another session, writes nothing.
    assert _type(root, "confirm 000000").block
    assert _type(root, f"confirm {code}", session="sess-2").block
    assert list(_delegations(root)) == ["DL-1"]
    done = _type(root, f"confirm {code}")
    assert not done.block, done
    dl = _delegations(root)["DL-2"]
    assert dl["forms"] == ["g5", "checks"]
    for needle in ("irreversible work", "archive migration", "release tag", "08:00"):
        assert needle in done.message, (needle, done.message)
    # A code is used once.
    assert _type(root, f"confirm {code}").block


# --- a delegation outside its limits is refused (`TRC-F3`) -----------------------------------

def test_f3_limits_refused(tmp_path, clock):
    root = project(tmp_path)
    for args, cause in ((ARCHITECT, ARCHITECT),
                        (f"--agent {ARCHITECT} --until 23:00 tomorrow", "tomorrow"),
                        ("--agent any --until 08:00", "any"),
                        (f"--agent {ARCHITECT} --until 08:00 --for everything", "everything"),
                        (f"--agent {ARCHITECT} --until 08:00 --on no-such-issue",
                         "no-such-issue"),
                        (f"--agent {ARCHITECT} --until 08:00 --on ..", "'..'"),
                        (f"--agent {ARCHITECT} --until 08:00 --on .", "'.'")):
        result = _type(root, args)
        assert result.block and cause in result.message, (args, result.message)
    # The 24-hour and five-in-force limits of 7.0.0 are gone: a delegation can end
    # 25 hours ahead, and a sixth can be in force.
    end = clock + datetime.timedelta(hours=25)
    assert not _type(root, f"--agent {ARCHITECT} --until {end.strftime('%Y-%m-%dT%H:%M')}"
                     ).block
    for n in range(5):
        assert not _type(root, f"--agent agent-{n} --until 08:00").block
    assert len(_delegations(root)) == 6


# --- a delegated agent records the guardrail 5 sign-off (`TRC-F4`) ---------------------------

def _g5_delegation(root, hours=2):
    first = _type(root, f"--agent {ARCHITECT} --until {_soon(hours)} "
                        f"--for g5,checks,documents")
    code = re.search(r"/compass:delegate confirm (\S+)", first.message).group(1)
    assert not _type(root, f"confirm {code}").block


def test_f4_delegated_g5_recorded(tmp_path):
    root = project(tmp_path)
    _g5_delegation(root)
    code, out, err = _approve(root, "--guardrail", "G5", "--scope", "refund migration")
    assert code == 0, out + err
    rec = manifest_of(root)["evidence"][-1]
    assert {k: rec[k] for k in ("type", "guardrail", "approver", "approved_by_agent",
                                "delegation", "via")} == {
        "type": "human-approval", "guardrail": "G5", "approver": OWNER,
        "approved_by_agent": ARCHITECT, "delegation": "DL-1", "via": "delegation"}
    from compass_pkg import checks
    ok, detail = checks._check_human_approval(manifest_of(root), str(task_dir(root)))
    assert ok and f"by {OWNER} via {ARCHITECT} under DL-1" in detail, detail
    assert _delegations(root)["DL-1"]["uses"] == 1
    devlog = (task_dir(root) / "devlog.md").read_text(encoding="utf-8")
    assert rec["id"] in devlog and ARCHITECT in devlog and "DL-1" in devlog


# --- an agent with no delegation cannot approve (`TRC-F5`) -----------------------------------

def test_f5_no_delegation_refused(tmp_path):
    root = project(tmp_path)
    before = (task_dir(root) / "manifest.yml").read_bytes()
    code, out, err = _approve(root, "--check", CHECK, "--scope", "x")
    assert code != 0, out + err
    assert "compass evidence request" in out + err, out + err
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


# --- an expired delegation cannot be used (`TRC-F6`) -----------------------------------------

def test_f6_expired_refused(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()}").block
    path = root / ".compass" / "delegations" / "DL-1.yml"
    body = yaml.safe_load(path.read_text())
    body["until"] = "2026-01-01T08:00:00Z"
    path.write_text(yaml.safe_dump(body, sort_keys=False))
    before = (task_dir(root) / "manifest.yml").read_bytes()
    code, out, err = _approve(root, "--check", CHECK, "--scope", "x")
    assert code != 0, out + err
    assert "DL-1" in out + err and "2026-01-01" in out + err, out + err
    assert (task_dir(root) / "manifest.yml").read_bytes() == before


# --- an approval outside the delegation's scope is refused (`TRC-F7`) -------------------------

def test_f7_out_of_scope_refused(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()} --on {SLUG} "
                           f"--for checks,documents --max 1").block
    code, out, err = _approve(root, "--guardrail", "G5", "--scope", "x")
    assert code != 0 and "DL-1" in out + err and "checks" in out + err, out + err
    # Another issue.
    other = root / ".compass" / "work" / "other"
    other.mkdir()
    (other / "manifest.yml").write_text((task_dir(root) / "manifest.yml").read_text())
    code, out, err = delegated(root, ARCHITECT, "--issue", "other", "--check", CHECK,
                               "--scope", "x")
    assert code != 0 and "DL-1" in out + err, out + err
    # Another generation.
    body = manifest_of(root)
    body["generation"] = 2
    save_manifest(root, body)
    code, out, err = _approve(root, "--check", CHECK, "--scope", "x")
    assert code != 0 and "generation" in out + err, out + err
    body["generation"] = 1
    save_manifest(root, body)
    # One approval is allowed, then max_uses is reached.
    code, out, err = _approve(root, "--check", CHECK, "--scope", "x")
    assert code == 0, out + err
    code, out, err = _approve(root, "--check", CHECK, "--scope", "y")
    assert code != 0 and "max" in out + err, out + err
    # A delegation not written by the prompt hook is refused.
    path = root / ".compass" / "delegations" / "DL-1.yml"
    body = yaml.safe_load(path.read_text())
    body.update(created_via="cli", max_uses=None, uses=0)
    path.write_text(yaml.safe_dump(body, sort_keys=False))
    code, out, err = _approve(root, "--check", CHECK, "--scope", "z")
    assert code != 0 and "created_via" in out + err, out + err


# --- a person revokes a delegation early (`TRC-F11`) -----------------------------------------

def test_f11_revoke_ends_delegation(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()}").block
    result = _type(root, "", command="compass:revoke")
    assert not result.block and "DL-1" in result.message, result
    dl = _delegations(root)["DL-1"]
    assert dl["revoked_by"] == OWNER and dl["revoked_at"]
    code, out, err = _approve(root, "--check", CHECK, "--scope", "x")
    assert code != 0 and "DL-1" in out + err and "revoked" in out + err, out + err
    # Nothing in force: revoke says so and writes nothing.
    assert _type(root, "", command="compass:revoke").block
    # A use counted from a copy read before the revoke keeps the revoke.
    from compass_pkg import approvals, delegations
    stale = dict(dl, revoked_by=None, revoked_at=None)
    done = approvals.Recorded("x", [], {}, ["EV-X"])
    delegations.record_use(str(task_dir(root)), stale, ARCHITECT, done, "x")
    after = _delegations(root)["DL-1"]
    assert after["revoked_at"] == dl["revoked_at"] and after["uses"] == 1


# --- the person sees what was approved under a delegation (`TRC-F12`) -------------------------

def _hook_json(script, root, body, **env_extra):
    import json
    import os
    import subprocess
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root / ".home"),
           "CLAUDE_CONFIG_DIR": str(root / ".claude-config"), "LANG": "C.UTF-8",
           "CLAUDE_PROJECT_DIR": str(root), "PYTHONDONTWRITEBYTECODE": "1"}
    env.update(env_extra)
    r = subprocess.run(["bash", str(ROOT / "hooks" / script)], input=json.dumps(body),
                       cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout) if r.stdout.strip() else {}


def _overnight(root):
    """Three approvals under DL-1: a check, a document the agent registered in
    the same session, and the decisions taken."""
    body = manifest_of(root)
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "td.md").write_text("# design\n", encoding="utf-8")
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design",
                          "status": "awaiting-approval", "path": "docs/td.md",
                          "registered_session": "sess-agent"}]
    body["decisions_taken"] = [{"id": "DEC-1", "question": "q", "resolution": "r",
                                "by": "spec-author", "stage": "define", "status": "open"}]
    save_manifest(root, body)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()}").block
    for argv in (["--check", CHECK, "--scope", "the review"],
                 ["--artifact", "technical-design"], ["--decisions"]):
        code, out, err = delegated(root, ARCHITECT, "--issue", SLUG, *argv,
                                   session="sess-agent")
        assert code == 0, out + err
    return [e["id"] for e in manifest_of(root)["evidence"] if e.get("via") == "delegation"]


def test_f12_review_summary_until_acknowledged(tmp_path, monkeypatch):
    root = project(tmp_path)
    # With no delegation file the summary reads no manifest, so a prompt in a
    # project with hundreds of issues costs nothing.
    from compass_pkg import delegations
    monkeypatch.setattr(delegations, "load_manifest",
                        lambda *_a: (_ for _ in ()).throw(AssertionError("scanned")))
    assert delegations.review_summary(str(root / ".compass")) == ""
    monkeypatch.undo()
    ids = _overnight(root)
    assert len(ids) == 3, ids
    start = _hook_json("session-start.sh", root, {"session_id": "s", "source": "startup"})
    prompt = _hook_json("approval-summary.sh", root,
                        {"session_id": "s", "hook_event_name": "UserPromptSubmit",
                         "prompt": "good morning", "cwd": str(root)})
    for shown in (start["systemMessage"], prompt["systemMessage"]):
        for needle in ids + [SLUG, ARCHITECT, "/compass:approve", "/compass:reject"]:
            assert needle in shown, (needle, shown)
        flagged = [line for line in shown.splitlines() if "technical-design" in line]
        assert flagged and "wrote" in flagged[0], shown
    # Shown again until the person marks them reviewed; nothing was written.
    before = (task_dir(root) / "manifest.yml").read_bytes()
    again = _hook_json("approval-summary.sh", root,
                       {"session_id": "s", "hook_event_name": "UserPromptSubmit",
                        "prompt": "next", "cwd": str(root)})
    assert again["systemMessage"] == prompt["systemMessage"]
    assert (task_dir(root) / "manifest.yml").read_bytes() == before
    result = _type(root, "", command="compass:approve")
    assert not result.block and "3" in result.message, result
    for rec in manifest_of(root)["evidence"]:
        if rec["id"] in ids:
            assert rec["reviewed_by"] == OWNER and rec["reviewed_at"], rec
    after = _hook_json("approval-summary.sh", root,
                       {"session_id": "s", "hook_event_name": "UserPromptSubmit",
                        "prompt": "next", "cwd": str(root)})
    assert "systemMessage" not in after, after


# --- the person overrules a delegated check or document approval (`TRC-F14`) ------------------

def test_f14_overrule_check_and_document(tmp_path):
    from compass_pkg import approval_records, effective, review_records
    root = project(tmp_path)
    ids = _overnight(root)
    check_id = next(i for i in ids if CHECK in i)
    doc_id = next(i for i in ids if "ARTIFACT" in i)
    result = _type(root, f"{check_id} the review missed the migration",
                   command="compass:reject")
    assert not result.block, result
    last = manifest_of(root)["evidence"][-1]
    assert last["check"] == CHECK and last["decision"] == "rejected"
    assert last["overrules"] == check_id and last["via"] == "prompt"
    view = effective.view_or_legacy(str(task_dir(root)))
    status, detail = approval_records.judge(CHECK, view.config["checks"][CHECK],
                                            manifest_of(root), str(task_dir(root)))
    assert status == "fail" and detail.startswith("approval withdrawn"), detail
    result = _type(root, f"{doc_id} the threat model is missing", command="compass:reject")
    assert not result.block, result
    entry = manifest_of(root)["artifacts"][0]
    assert entry["status"] == "draft" and entry["rejected_by"] == OWNER
    assert entry["rejected_digest"] == review_records.file_digest(str(root / "docs" / "td.md"))
    # A record that was not made under a delegation is not overruled this way.
    result = _type(root, "EV-NOPE reason", command="compass:reject")
    assert result.block
