"""The agent asks for an approval with `compass evidence request`
(issue `approve-inside-claude-code`, ADR-068 decision 1).

The verb takes the five subject forms of `compass evidence approve`, runs the
same refusals, and writes one pending request under the issue. The request
holds facts the CLI derives (issue, generation, subject, labels, a document's
digest) and the agent's description of the scope. A request is not evidence,
and no check reads it.

Scenario ids: `TRC-B1`, `TRC-B3`, `TRC-B4`, `TRC-D1`, `TRC-E3`. Each test name
starts with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (CHECK, LABELS, SLUG, closed_dir, manifest_of,  # noqa: E402
                              pending_dir, project, read_request, run, task_dir)


def _request(root, *argv, **extra_env):
    return run(root, "evidence", "request", "--issue", SLUG, *argv, **extra_env)


# --- TRC-B1: the agent asks for an approval with the CLI -----------------------------------

def test_b1_request_written_with_derived_facts(tmp_path):
    root = project(tmp_path)
    code, out, err = _request(root, "--guardrail", "G5", "--scope", "refund table migration")
    assert code == 0, out + err
    files = sorted(pending_dir(root).glob("*.yml"))
    assert [f.name for f in files] == ["1.yml"], files
    req = read_request(files[0])
    assert req["number"] == 1
    assert req["issue"] == SLUG and req["generation"] == 1
    assert req["form"] == "guardrail" and req["value"] == "G5"
    assert req["labels"] == LABELS
    assert req["scope"] == "refund table migration"
    assert req["nonce"] and req["requested_at"]
    assert "shown_at" not in req
    assert "/compass:approve" in out and "/compass:reject" in out, out
    assert "compass evidence approve" not in out + err, out + err
    # A request is not evidence.
    assert manifest_of(root)["evidence"] == []


# --- TRC-B3: a new request for the same subject replaces the pending one ---------------------

def test_b3_same_subject_replaces(tmp_path):
    root = project(tmp_path)
    assert _request(root, "--check", CHECK, "--scope", "first look")[0] == 0
    code, out, err = _request(root, "--check", CHECK, "--scope", "after the fixes")
    assert code == 0, out + err
    assert [f.name for f in pending_dir(root).glob("*.yml")] == ["2.yml"]
    second = read_request(pending_dir(root) / "2.yml")
    assert second["scope"] == "after the fixes" and "shown_at" not in second
    first = read_request(closed_dir(root) / "1.yml")
    assert first["outcome"] == "replaced" and first["closed_at"]
    # Another subject does not replace it.
    assert _request(root, "--guardrail", "G5", "--scope", "x")[0] == 0
    assert sorted(f.name for f in pending_dir(root).glob("*.yml")) == ["2.yml", "3.yml"]


# --- TRC-B4: a request the approval would refuse is refused when asked ------------------------

def test_b4_request_refuses_like_approve(tmp_path):
    root = project(tmp_path)
    body = manifest_of(root)
    body["artifacts"] = [{"id": "ART-TD", "kind": "technical-design", "status": "draft",
                          "path": "docs/td.md"}]
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "td.md").write_text("# design\n", encoding="utf-8")
    from approval_support import save_manifest
    save_manifest(root, body)
    for argv in (["--check", "made-up-check", "--scope", "x"],
                 ["--artifact", "technical-design"],
                 ["--guardrail", "g5", "--scope", "x"]):
        code, out, err = _request(root, *argv)
        assert code != 0, (argv, out + err)
        approve_argv = [a for a in argv]
        acode, aout, aerr = run(root, "evidence", "approve", "--issue", SLUG, *approve_argv,
                                "--approver", "jed72", "--role", "owner", terminal=True)
        assert acode != 0, aout + aerr
        reason = (aout + aerr).strip().split("compass evidence approve: ", 1)[1]
        assert reason in out + err, (argv, out + err, reason)
    assert not pending_dir(root).exists() or not list(pending_dir(root).glob("*.yml"))


# --- TRC-D1: the request shows facts the CLI derived beside the agent's words --------------------

def test_d1_display_shows_derived_facts_and_agent_scope(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path)
    code, out, err = _request(root, "--guardrail", "G5", "--scope", "fix a README typo")
    assert code == 0, out + err
    req = read_request(pending_dir(root) / "1.yml")
    text = approval_requests.shown_text(req)
    assert "guardrail 5 sign-off" in text
    assert "payments" in text and "migrations" in text
    assert "generation 1" in text and SLUG in text
    assert 'agent\'s description: "fix a README typo"' in text, text
    assert "/compass:approve" in text and "/compass:reject" in text
    # The derived facts come before the agent's words.
    assert text.index("payments") < text.index("fix a README typo")


# --- TRC-E3: a host whose adapter cannot show a typed command uses the terminal ------------------

def test_e3_no_prompt_host_prints_terminal_command(tmp_path):
    root = project(tmp_path)
    code, out, err = _request(root, "--guardrail", "G5", "--scope", "refund migration",
                              COMPASS_APPROVAL_CHANNEL="terminal")
    assert code == 0, out + err
    assert ("compass evidence approve --issue feature --guardrail G5 --approver <you> "
            "--role <role> --scope 'refund migration'") in out, out
    assert "with no `!` prefix" in out, out
    assert "/compass:approve" not in out
    # No code under cli/ or hooks/ branches on an adapter's name.
    for folder in ("cli/compass_pkg", "hooks"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".sh"):
                text = path.read_text(encoding="utf-8")
                assert "== \"codex\"" not in text and "== 'codex'" not in text, path
