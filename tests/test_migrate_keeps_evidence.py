"""`compass migrate` keeps an 8.x issue's evidence and approvals as they are (#359).

Step 2 of the #359 plan [Add compass migrate and the 9.0.0 upgrade guide],
section 4.2 "What it never does": it writes no approval, no checkpoint
outcome, no delegation copy and nothing under `evidence/`, and it changes no
gate's status (ADR-095). It writes `trail.md` again, so the trail's sum
lines match the new manifest (ADR-096).

The fixture issue is at `verify` on 8.x, with a real red and green
(`compass tdd-red`, `compass tdd-green`, which write `evidence/SHA256SUMS`), a
`human-approval` and a `checkpoint-approval` record, a checkpoint outcome, a
delegation copy, a pending approval request, a gate that passed, and a
`trail.md` from `compass trail`. The sums are checked with the system's
`sha256sum` (or `shasum -a 256`), on a PATH where no Compass is reachable.
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from migrate_9_helpers import (fix, green, manifest, ok, old_issue, project, red, run,
                               scenario, snapshot, task_dir, write_manifest)

SLUG = "kept"
F = "tests/test_f.py"
#: A gate both the 8.x approach and the path hold.
PASSED = "verify.correctness"
SYSTEM_PATH = "/usr/bin:/bin:/sbin"
APPROVAL_TYPES = ("human-approval", "checkpoint-approval", "pr-approval",
                  "approval-withdrawal")


def _tool():
    """The checker on the system PATH, as a command string, or None."""
    if shutil.which("sha256sum", path=SYSTEM_PATH):
        return "sha256sum -c -"
    if shutil.which("shasum", path=SYSTEM_PATH):
        return "shasum -a 256 -c -"
    return None


def _system(cwd, command):
    env = {"PATH": SYSTEM_PATH, "HOME": str(cwd), "LC_ALL": "C"}
    return subprocess.run(["/bin/bash", "-c", command], cwd=cwd, env=env,
                          capture_output=True, text=True)


def _approvals(body):
    return [e for e in body.get("evidence") or [] if e.get("type") in APPROVAL_TYPES]


@pytest.fixture
def issue(tmp_path):
    root = project(tmp_path)
    folder = old_issue(root, SLUG, scenarios=[scenario("TRC-001", F)])
    red(root, SLUG, "TRC-001", F)
    fix(root)
    green(root, SLUG, "TRC-001", F)
    evidence = folder / "evidence"
    (evidence / "approval-1.yml").write_text("approver: dana\ndecision: approved\n")
    (evidence / "checkpoint-1.yml").write_text("approver: dana\nstage: define\n")
    (folder / "approval-requests" / "pending").mkdir(parents=True)
    (folder / "approval-requests" / "pending" / "1.yml").write_text("subject: G5\n")
    body = manifest(root, SLUG)
    body["evidence"] += [
        {"id": "EV-H1", "type": "human-approval", "path": "evidence/approval-1.yml",
         "approver": "dana", "decision": "approved", "check": "intent-approved",
         "scope": "the intent", "timestamp": "2026-10-02T10:00:00Z"},
        {"id": "EV-C1", "type": "checkpoint-approval", "path": "evidence/checkpoint-1.yml",
         "approver": "dana", "decision": "approved", "checkpoint": "define",
         "scope": "the define hand-off", "timestamp": "2026-10-02T11:00:00Z"}]
    body["checkpoint_outcomes"] = [{"stage": "define", "outcome": "waited", "by": "dana",
                                    "at": "2026-10-02T11:00:00Z", "evidence": "EV-C1"}]
    body["delegations_used"] = {"DL-1": {"delegated_by": "dana", "forms": ["checkpoint"],
                                         "sha256": "0" * 64}}
    passed = next(g for g in body["gates"] if g["id"] == PASSED)
    passed.update(status="pass", evidence=["EV-H1"])
    write_manifest(root, SLUG, body)
    ok(root, "trail", "--issue", SLUG)
    return root


def test_migrate_writes_no_evidence_and_no_approval(issue):
    folder = task_dir(issue, SLUG)
    before = manifest(issue, SLUG)
    evidence = snapshot(folder / "evidence")
    requests = snapshot(folder / "approval-requests")
    done = ok(issue, "migrate", "--apply")
    assert "kept: verify -> ship" in done.stdout, done.stdout
    after = manifest(issue, SLUG)
    assert "evidence_required" in after
    assert snapshot(folder / "evidence") == evidence
    assert snapshot(folder / "approval-requests") == requests
    assert _approvals(after) == _approvals(before)
    assert after["evidence"] == before["evidence"]
    assert after["checkpoint_outcomes"] == before["checkpoint_outcomes"]
    assert after["delegations_used"] == before["delegations_used"]
    assert after.get("scenario_freeze") == before.get("scenario_freeze")
    # The gate keeps its state; a gate the path adds starts at pending.
    gates = {g["id"]: g for g in after["gates"]}
    assert gates[PASSED] == {"id": PASSED, "status": "pass", "evidence": ["EV-H1"]}
    held = {g["id"]: g for g in before["gates"]}
    assert all(g == held[gid] if gid in held else g["status"] == "pending"
               for gid, g in gates.items())


def test_the_sums_still_pass_after_migrate(issue):
    tool = _tool()
    if tool is None:
        pytest.skip("neither sha256sum nor shasum is on the system PATH")
    ok(issue, "migrate", "--apply")
    done = run(issue, "trail", "--check", "--issue", SLUG)
    assert done.returncode == 0, done.stdout + done.stderr
    trail = f".compass/work/{SLUG}/trail.md"
    checked = _system(issue, f"grep -E '^[0-9a-f]{{64}}  ' {trail} | {tool}")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "manifest.yml: OK" in checked.stdout, checked.stdout
    sums = f".compass/work/{SLUG}/evidence/SHA256SUMS"
    checked = _system(issue, f"{tool.removesuffix(' -')} {sums}")
    assert checked.returncode == 0, checked.stdout + checked.stderr


def test_without_migrate_the_trail_check_fails_on_a_changed_manifest(issue):
    """The check above can fail: a manifest write after `trail.md` breaks its
    sum lines until the trail is written again."""
    tool = _tool()
    if tool is None:
        pytest.skip("neither sha256sum nor shasum is on the system PATH")
    body = manifest(issue, SLUG)
    body["created"] = "2026-10-03"
    write_manifest(issue, SLUG, body)
    trail = f".compass/work/{SLUG}/trail.md"
    checked = _system(issue, f"grep -E '^[0-9a-f]{{64}}  ' {trail} | {tool}")
    assert checked.returncode != 0
