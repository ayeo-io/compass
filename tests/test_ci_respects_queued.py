"""`compass ci` does not fail an issue that has not started.

The framework asks people to assess work early so nothing happens
unrecorded. Without this rule, doing that turns the sweep red: an issue
with a delivery approach but no acceptance criteria yet fails
`scenarios-have-tests`, `scenario-has-id-and-intent` and `suite-passed`,
and fails the whole sweep. A tool that penalises the behaviour it asks for
teaches people to stop complying.

This repository only avoids the problem because `.compass/work/` is
gitignored, so the sweep in continuous integration finds nothing to check and
passes without checking anything. An adopter who commits their archive - which the framework
tells them to do, since it is their audit trail - meets it on day one.

The sweep still lists every issue it saw and says why one was not checked.
Nothing hides; a queued issue simply does not fail a build for being queued.

Scenario ids: see the issue's acceptance criteria (TRC-1, `TRC-2`).
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

# Lifecycle values for work that has not started or has stopped. An issue in
# one of these states has no acceptance criteria yet, and correctly so.
NOT_IN_FLIGHT = ("queued", "parked", "abandoned")

SPINE = """schema_version: "2.0"
task: "{slug}"
created: "2026-08-12"
status: {status}
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
delivery_approach: quick-fix
topology: solo
policy_rules_fired: []
stages: {{frame: full, specify: light, clarify: collapsed, plan: collapsed,
  distribute: skipped, build: full, verify: light, land: light}}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
friction: []
"""


def _project(tmp_path, slug, status):
    """A minimal project carrying one issue in the given lifecycle state."""
    work = tmp_path / ".compass" / "work" / slug
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    (work / "manifest.yml").write_text(
        SPINE.format(slug=slug, status=status), encoding="utf-8")
    return tmp_path


def _run_ci(project):
    return subprocess.run(
        ["python3", str(CLI), "ci"],
        cwd=str(project), capture_output=True, text=True, timeout=120,
    )


def test_trc_1_a_not_yet_started_issue_does_not_fail_the_sweep(tmp_path):
    for status in NOT_IN_FLIGHT:
        project = _project(tmp_path / status, f"framed-not-started", status)
        result = _run_ci(project)
        assert result.returncode == 0, (
            f"an issue with status {status!r} failed the sweep. Framing work "
            f"early is what the framework asks for; failing the build for it "
            f"teaches people to stop.\n{result.stdout}{result.stderr}"
        )


def test_trc_2_the_sweep_still_names_what_it_did_not_check(tmp_path):
    """Not failing is not the same as hiding.

    A queued issue that vanished from the output would be worse than one that
    failed: nobody would know it was there.
    """
    project = _project(tmp_path, "framed-not-started", "queued")
    result = _run_ci(project)
    combined = result.stdout + result.stderr
    assert "framed-not-started" in combined, (
        f"the sweep did not mention the issue it skipped:\n{combined}"
    )
    assert "queued" in combined.lower(), (
        f"the sweep did not say why the issue was not checked:\n{combined}"
    )


def test_trc_3_an_active_issue_is_still_checked(tmp_path):
    """The guard must not become a way to switch checking off.

    An issue that is genuinely active with no scenarios is a real failure,
    and must stay one.
    """
    project = _project(tmp_path, "in-flight", "active")
    result = _run_ci(project)
    assert result.returncode != 0, (
        f"an active issue with no acceptance criteria passed the sweep - the "
        f"skip has swallowed a real failure:\n{result.stdout}{result.stderr}"
    )
