"""Scenario sign-off before code (ADR-095 decisions 9 and 10).

On a path issue that owes `scenario-approval` (a `G5` label, a `signoff_labels`
label or critical risk), `compass tdd-red` refuses until the `specify`
checkpoint has a person's answer. It refuses before the test runs, so it writes
no red record and no `.red` marker. An issue that does not owe the approval is
not refused. The person's answer records the spec's path and the `sha256sum`
digest of its bytes, and the prompt hook refuses to record a request whose spec
changed after the person was shown it.

Every project is a real git repository driven through `cli/compass`, with the
helpers of `tests/test_checkpoint_outcomes.py`: GitHub is off, and a person's
command gets a pseudo-terminal.

Issue: #355 [Read the ship approval from the merged PR review].
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from test_checkpoint_outcomes import (BALANCED, CRITICAL, DOCS, SLUG, approve,  # noqa: E402
                                      manifest, project, run, specify_done)

FAILING_TEST = "def test_one():\n    assert False\n"
SPEC = ("# Acceptance criteria\n\n| Id | Scenario |\n|---|---|\n"
        "| TRC-001 | Given one, when it runs, then it passes |\n")
RED = ["tdd-red", "--issue", SLUG, "--scenario", "TRC-001", "--loop", "inner", "--",
       sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
       "tests/test_one.py::test_one"]


def _issue(tmp_path, assessment=None, compass_yml=BALANCED):
    root = project(tmp_path, compass_yml=compass_yml, assessment=assessment)
    specify_done(root)
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_one.py").write_text(FAILING_TEST)
    _spec(root).write_text(SPEC)
    return root


def _task_dir(root):
    return root / ".compass" / "work" / SLUG


def _spec(root):
    return root / DOCS / "acceptance-criteria.md"


def _reds(root):
    return sorted((_task_dir(root) / "evidence").glob("red-*.json")) \
        if (_task_dir(root) / "evidence").is_dir() else []


def test_a_red_is_refused_before_a_person_answers_specify(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    assert "scenario-approval" in manifest(root)["evidence_required"]
    done = run(root, *RED)
    assert done.returncode != 0, done
    text = " ".join(done.stderr.split())
    assert "Blocked: red for issue 'feature'" in text, text
    assert ("Fix: run compass evidence request --checkpoint specify --issue feature and "
            "stop; the person answers with /compass:approve.") in text, text
    assert "[scenarios-not-approved]" in text, text
    # Refused before the test ran: no record, no marker, no freeze.
    assert _reds(root) == []
    assert not (_task_dir(root) / ".red").exists()
    assert "scenario_freeze" not in manifest(root)


def test_a_red_is_recorded_after_a_person_answers_specify(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    assert approve(root, "specify").returncode == 0
    done = run(root, *RED)
    assert done.returncode == 0, done.stdout + done.stderr
    assert len(_reds(root)) == 1
    assert (_task_dir(root) / ".red").exists()


def test_a_skipped_specify_does_not_count_as_a_persons_answer(tmp_path):
    from compass_pkg import scenario_freeze
    task = {"evidence_required": ["scenarios", "scenario-approval"],
            "checkpoints": ["specify"],
            "checkpoint_outcomes": [{"stage": "specify", "outcome": "skipped",
                                     "by": "agent", "at": "2026-11-07T10:00:00Z"}]}
    assert scenario_freeze.refusal(task, "/p/.compass/work/demo")
    task["checkpoint_outcomes"][0].update(outcome="waited", evidence="EV-1")
    assert scenario_freeze.refusal(task, "/p/.compass/work/demo") is None


def test_an_issue_that_does_not_owe_the_approval_is_not_refused(tmp_path):
    root = _issue(tmp_path)
    assert "scenario-approval" not in manifest(root)["evidence_required"]
    done = run(root, *RED)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (_task_dir(root) / ".red").exists()


def test_an_old_issue_is_not_refused():
    from compass_pkg import scenario_freeze
    # No `evidence_required`: an issue assessed before the path owes no token.
    assert scenario_freeze.refusal({"assessment": {"risk": "critical"},
                                    "checkpoints": ["specify"],
                                    "checkpoint_outcomes": []}, "/p/.compass/work/x") is None


def test_controlled_autonomy_still_waits_at_specify_on_every_change(tmp_path):
    controlled = dict(BALANCED, autonomy="controlled")
    root = _issue(tmp_path, compass_yml=controlled)
    body = manifest(root)
    assert "scenario-approval" not in body["evidence_required"]
    assert "specify" in body["checkpoints"]
    # The wait is the project's choice, not the sign-off rule: the red is not refused.
    assert run(root, *RED).returncode == 0


def test_the_specify_approval_names_the_spec_digest(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    assert approve(root, "specify").returncode == 0
    record = [e for e in manifest(root)["evidence"] if e["type"] == "checkpoint-approval"][-1]
    assert record["spec"] == f"{DOCS}/acceptance-criteria.md"
    assert record["spec_sha256"] == hashlib.sha256(_spec(root).read_bytes()).hexdigest()


def test_next_names_the_request_the_refusal_names(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    # With no spec file there are no requirement rows to fill first.
    _spec(root).unlink()
    done = run(root, "next", "--issue", SLUG)
    assert "compass evidence request --checkpoint specify" in done.stdout, done.stdout


# --- the prompt hook --------------------------------------------------------------------

def _plugin(tmp_path):
    folder = tmp_path / "plugin" / "commands"
    folder.mkdir(parents=True)
    for name in ("approve", "reject", "delegate", "revoke"):
        (folder / f"{name}.md").write_text(
            f"---\ndescription: {name}\ndisable-model-invocation: true\n---\n\nBody.\n")
    return tmp_path / "plugin"


def _shown_request(root):
    from compass_pkg import approval_requests
    task_dir = str(_task_dir(root))
    request = approval_requests.write(task_dir, "checkpoint", "specify", "")
    return approval_requests.mark_shown(task_dir, request)


def _approve_by_prompt(root, plugin):
    from approval_support import event
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root), {}, plugin_root=str(plugin))


def test_the_request_holds_the_spec_digest_and_the_prompt_records_it(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    request = _shown_request(root)
    digest = hashlib.sha256(_spec(root).read_bytes()).hexdigest()
    assert request["spec_sha256"] == digest
    assert request["spec"] == f"{DOCS}/acceptance-criteria.md"
    from compass_pkg import approval_requests
    assert f"sha256 {digest[:12]}" in approval_requests.shown_text(request)
    result = _approve_by_prompt(root, _plugin(tmp_path))
    assert not result.block, result.message
    record = [e for e in manifest(root)["evidence"] if e["type"] == "checkpoint-approval"][-1]
    assert record["spec_sha256"] == digest and record["via"] == "prompt"


def test_a_spec_changed_after_the_request_is_refused(tmp_path):
    root = _issue(tmp_path, assessment=CRITICAL)
    _shown_request(root)
    with _spec(root).open("a") as fh:
        fh.write("\nA line added after the person was shown the request.\n")
    result = _approve_by_prompt(root, _plugin(tmp_path))
    assert result.block, result
    assert "the spec changed" in result.message and "again" in result.message
    assert not [e for e in manifest(root)["evidence"] if e["type"] == "checkpoint-approval"]
    from compass_pkg import approval_requests
    closed = approval_requests.closed(str(_task_dir(root)))
    assert closed and closed[-1]["outcome"] == "stale"
