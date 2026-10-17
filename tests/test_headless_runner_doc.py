"""`docs/headless-runner.md` says what a run does at a step that needs a
person's approval.

Scenario id: CHS-15 (issue `contract-handoff-and-staging-rules`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _section():
    doc = (ROOT / "docs" / "headless-runner.md").read_text(encoding="utf-8")
    part = doc.split("## What each session is told", 1)[1]
    return " ".join(part.split("\n## ", 1)[0].split())


def test_headless_runner_documents_approval_stop():
    text = _section()
    assert ("If a step needs a person's approval, record nothing: run "
            "compass evidence request, ask the person to type "
            "/compass:approve or /compass:reject, and stop.") in text
    assert "records nothing as approved" in text
    assert "writes a pending request with `compass evidence request`" in text
    assert "the request to the person as its last line" in text
    assert "`run-<n>.md` keeps that last line" in text
    assert "exact command they must run" not in text
    assert "three unchanged cycles" in text
    assert "`stopped_reason`" in text and "exit code 4" in text
    assert "reads exit code 4 and goes on to its next issue" in text
