"""`TRC-F5` - jsonschema stays optional and unchanged by zero-friction-install.

This issue bundles PyYAML, Compass's one *hard* dependency. `jsonschema` is
already optional and already not bundled: `_jsonschema_errors()` in
`cli/compass_pkg/policy.py` catches its own ImportError and returns None, and
`compass issue lint` falls back to the built-in structural linter with a note
saying what installing it would add. `compass policy lint` validates nothing
against a JSON Schema since 9.0.0 deleted the two governance views and their
schemas (ADR-098): it is the settings lint, so it passes the same with or
without jsonschema and prints no note about it. Nothing in
this issue touches that path - pinned here so "the dependency is gone" is
never quietly read as covering jsonschema too.

There is no natural red: the behaviour already exists, on any machine that
happens to lack jsonschema (most of them). So this is a characterisation
test, declared through `compass acceptance start --kind refactor` rather
than a manufactured failure. To exercise the "absent" branch on a dev
machine that has jsonschema installed for the test suite's own tooling, a
decoy `jsonschema` module that raises ImportError is put ahead of the real
one on `PYTHONPATH`. `tests/test_bundled_pyyaml.py` uses the same
absence-by-shadowing technique for PyYAML, in the opposite direction:
proving a fallback runs, not that a bundle wins.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


_FAKE_ABSENT_JSONSCHEMA = (
    "raise ImportError('jsonschema is not installed (test double for TRC-F5)')\n"
)


def _hide_jsonschema(tmp_path: Path) -> dict:
    """A PYTHONPATH entry whose `jsonschema.py` always fails to import,
    shadowing any real jsonschema on the site-packages behind it."""
    decoy_dir = tmp_path / "no-jsonschema-here"
    decoy_dir.mkdir()
    (decoy_dir / "jsonschema.py").write_text(_FAKE_ABSENT_JSONSCHEMA, encoding="utf-8")
    return {"PYTHONPATH": str(decoy_dir)}


def test_jsonschema_absent_behaves_exactly_as_before(run_cli, make_task, tmp_path):
    """With jsonschema unimportable, `compass policy lint` and
    `compass issue lint` report the same verdict they report with it.
    `issue lint` still prints the note naming what jsonschema would add;
    `policy lint` reads no schema (ADR-098), so a note would claim a check
    it does not make."""
    env = _hide_jsonschema(tmp_path)

    policy_result = run_cli("policy", "lint", extra_env=env)
    with_it = run_cli("policy", "lint")
    assert policy_result.returncode == 0, policy_result
    assert "compass policy lint: PASS" in policy_result.stdout, policy_result
    assert policy_result.stdout == with_it.stdout, (policy_result, with_it)
    assert "jsonschema not installed" not in policy_result.stdout, policy_result

    body = {
        "task": "no-jsonschema-issue",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "goal": "delivery",
        },
        "delivery_approach": "express",
        "scenarios": [],
        "changed_files": [],
        "evidence": [],
        "gates": [],
        "follow_ups": [],
    }
    make_task("no-jsonschema-issue", body)
    issue_result = run_cli(
        "issue", "lint", "--issue", "no-jsonschema-issue", extra_env=env)
    assert issue_result.returncode == 0, issue_result
    assert "compass issue lint: PASS" in issue_result.stdout, issue_result
    assert "jsonschema not installed" in issue_result.stdout, issue_result
    assert "pip install jsonschema" in issue_result.stdout, issue_result


@pytest.mark.skipif(
    importlib.util.find_spec("jsonschema") is None,
    reason="jsonschema is not installed on this machine - it is optional "
           "test tooling (tests/README.md), not a dependency this issue "
           "bundles or requires. This test is the CONTROL for the decoy "
           "technique above and only makes sense where the real thing is "
           "actually importable; on the ordinary machine that lacks it, "
           "test_jsonschema_absent_behaves_exactly_as_before is the one "
           "that matters, and it needs no jsonschema install to run.",
)
def test_jsonschema_present_is_the_control(run_cli, make_task):
    """The control case, run against this environment's real jsonschema (it
    is installed here as test tooling): both verbs pass and neither prints
    the fallback note, so the decoy above is proven to change something real
    rather than always printing the same text."""
    policy_result = run_cli("policy", "lint")
    assert policy_result.returncode == 0, policy_result
    assert "compass policy lint: PASS" in policy_result.stdout, policy_result
    assert "jsonschema not installed" not in policy_result.stdout, policy_result
