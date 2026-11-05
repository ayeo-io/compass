"""`compass ci` - the aggregated mechanical gate suite.

Returns non-zero when ANY issue fails check, zero when everything passes.
The mode interaction is covered in test_modes; here we just check the
exit-code aggregation.
"""
from __future__ import annotations

import json


def _valid_task(slug, with_evidence=True):
    body = {
        "task": slug,
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "express",
        "scenarios": [{"id": "SCN-001", "intent": "INT-1",
                       "tests": ["tests/test_x.py::test_y"]}],
        "changed_files": [{"path": "src/x.py", "scenarios": ["SCN-001"]}],
        "evidence": [],
        "gates": [{"id": "verify.correctness", "status": "pending"}],
        "follow_ups": [],
    }
    if with_evidence:
        body["evidence"].append({
            "id": "EV-T-SCN-001", "type": "test-run",
            "path": "evidence/green.json", "scenario": "SCN-001",
        })
    return body


def _write_green(task_dir):
    ev = task_dir / "evidence"
    ev.mkdir(exist_ok=True)
    (ev / "green.json").write_text(json.dumps({"exit_code": 0, "passed": True}))


def test_ci_passes_when_no_tasks(run_cli, project):
    """A repo with governance but no issues: governance still lints, ci
    returns 0."""
    r = run_cli("ci")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout, r


def test_ci_passes_when_all_tasks_pass(run_cli, make_task):
    task_dir = make_task("ok-1", _valid_task("ok-1"))
    _write_green(task_dir)
    task_dir = make_task("ok-2", _valid_task("ok-2"))
    _write_green(task_dir)
    r = run_cli("ci")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout, r


def test_ci_fails_when_any_task_fails(run_cli, make_task):
    """Two issues; one is missing test-run evidence => ci must exit non-zero."""
    task_dir = make_task("ok", _valid_task("ok"))
    _write_green(task_dir)
    # the second issue is missing the evidence + the green.json file
    make_task("bad", _valid_task("bad", with_evidence=False))
    r = run_cli("ci")
    assert r.returncode != 0, r
    assert "FAIL" in r.stdout, r


def test_ci_fails_on_invalid_policy(run_cli, edit_governance, make_task):
    """Broken governance => ci fails before any issue check."""
    with edit_governance("guardrails.yml") as gr:
        gr.setdefault("project", []).append({
            "id": "Q-BAD",
            "name": "no checks",
            "statement": "...",
        })
    task_dir = make_task("anything", _valid_task("anything"))
    _write_green(task_dir)
    r = run_cli("ci")
    assert r.returncode != 0, r


def test_ci_reports_each_task(run_cli, make_task):
    """The output mentions each issue slug so a user can locate the failure."""
    for slug in ("alpha", "beta"):
        td = make_task(slug, _valid_task(slug))
        _write_green(td)
    r = run_cli("ci")
    assert r.returncode == 0, r
    assert "alpha" in r.stdout, r
    assert "beta" in r.stdout, r
