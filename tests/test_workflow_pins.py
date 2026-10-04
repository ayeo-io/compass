"""Invariants on the framework's own CI workflow.

Two things must stay true of `.github/workflows/compass.yml`. It must SHA-pin
third-party actions, which is the same supply-chain stance `docs/security.md`
asks Compass consumers to take. And it must run the test suite, so that a
failing test can stop a merge rather than only failing on a contributor's
machine.

Traces to: sha-pin-workflow-actions/acceptance-criteria.md SCN-001,
and ci-runs-test-suite/acceptance-criteria.md SCN-001.
"""
from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "compass.yml"
USES_LINE = re.compile(r"uses:\s+([^\s@]+)@(\S+)")
SHA = re.compile(r"^[0-9a-f]{40}$")


def test_third_party_actions_are_sha_pinned():
    unpinned: list[str] = []
    for line in WORKFLOW.read_text().splitlines():
        match = USES_LINE.search(line)
        if match and not SHA.match(match.group(2)):
            unpinned.append(line.strip())
    assert not unpinned, (
        "third-party actions in .github/workflows/compass.yml are not "
        "SHA-pinned; each `uses:` ref must be a 40-char hex SHA:\n  "
        + "\n  ".join(unpinned)
    )


def test_ci_workflow_runs_the_test_suite():
    """CI must run the tests, not only the governance and structure checks.

    `compass ci` is governance lint plus the per-issue guardrail checks. It does
    not run pytest. Without an explicit step, every test in this suite - the
    release invariants that cap the guardrail count, the house-style guards,
    all of it - runs only where someone happens to run it, and a pull request
    that breaks all of them goes green.
    """
    workflow = WORKFLOW.read_text()
    # The packages come from a requirements file of exact versions (#99), so
    # what is installed is the workflow's text plus the files it names.
    root = WORKFLOW.parent.parent.parent
    for req in re.findall(r"pip install -r (\S+)", workflow):
        workflow += "\n" + "\n".join(
            f"pip install {line.strip()}" for line in
            (root / req).read_text().splitlines() if line.strip()
            and not line.startswith("#"))

    assert re.search(r"pip install[^\n]*\bpytest\b", workflow), (
        ".github/workflows/compass.yml does not install pytest. The workflow "
        "installs the CLI's runtime dependencies only, so a test step would "
        "fail with a missing module."
    )

    runs_suite = re.search(r"run:[^\n]*pytest", workflow) or re.search(
        r"run:[^\n]*make test", workflow
    )
    assert runs_suite, (
        ".github/workflows/compass.yml has no step that runs the test suite. "
        "validate.sh, the AST parse and `compass ci` do not run pytest, so "
        "nothing in tests/ gates a merge without one."
    )
