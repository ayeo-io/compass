"""The cross-issue sweep lints every manifest, and its summary says what it did.

`compass ci` lints every manifest, queued ones included, because structure
is checkable at any stage; its summary counts the issues it fully checked.
An issue that has been assessed but not yet defined has no acceptance
criteria yet, which is true of the check and not of the lint - so a
`continue` placed above both `cmd_task_lint` and `cmd_check` let a
not-yet-started issue skip the lint too, and the run still ended:

    compass ci: PASS - governance valid; every issue lints clean and checks green.

against a manifest declaring a schema version this CLI does not handle.

Two consequences:
- a malformed manifest could sit in a repository indefinitely without the
  sweep noticing;
- `status: parked` became a one-word way to leave the sweep while it still
  reported everything clean.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

NOT_IN_FLIGHT = ("queued", "parked", "abandoned")

# A manifest the CLI can read: well formed, simply not yet defined.
WELL_FORMED = """schema_version: "2.0"
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

# A manifest the CLI cannot accept: a schema version it does not handle, and a
# risk outside the assessment vocabulary. `compass issue lint` rejects this
# outright; the sweep must not report it clean.
MALFORMED = """schema_version: "9.9"
task: "{slug}"
created: "2026-08-12"
status: {status}
assessment:
  risk: nonsense-value
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
"""


def _project(tmp_path, slug, status, manifest):
    work = tmp_path / ".compass" / "work" / slug
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    (work / "manifest.yml").write_text(
        manifest.format(slug=slug, status=status), encoding="utf-8")
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    return tmp_path


def _run_ci(project):
    return subprocess.run(
        ["python3", str(CLI), "ci"],
        cwd=str(project), capture_output=True, text=True, timeout=180,
    )


@pytest.mark.parametrize("status", NOT_IN_FLIGHT)
def test_trc_1_a_malformed_spine_fails_the_sweep_at_any_status(tmp_path, status):
    project = _project(tmp_path / status, "bad", status, MALFORMED)
    result = _run_ci(project)
    combined = result.stdout + result.stderr

    assert result.returncode != 0, (
        f"the sweep reported success on a manifest its own linter rejects, "
        f"because the issue's status is {status!r}. A malformed manifest can "
        f"then sit in a repository indefinitely.\n{combined}"
    )


@pytest.mark.parametrize("status", NOT_IN_FLIGHT)
def test_trc_2_a_well_formed_queued_issue_still_passes(tmp_path, status):
    """The control.

    Without this, `TRC-1` would pass against a sweep that simply failed
    everything - which would undo `sweep-respects-queued` and put back the
    defect that assessing work early makes the build red.
    """
    project = _project(tmp_path / status, "fine", status, WELL_FORMED)
    result = _run_ci(project)
    combined = result.stdout + result.stderr

    assert result.returncode == 0, (
        f"an issue that is correctly triaged-but-not-yet-defined failed the "
        f"sweep at status {status!r}. Framing work early is what the "
        f"framework asks for.\n{combined}"
    )


def test_trc_3_the_summary_reports_what_was_and_was_not_checked(tmp_path):
    """The last line is the one a CI reader actually reads.

    The last line must not claim every issue was checked when some were
    skipped. A skip line further up does not repair that, because the skip
    line is the part nobody scrolls back for.
    """
    project = _project(tmp_path, "fine", "queued", WELL_FORMED)
    result = _run_ci(project)
    combined = result.stdout + result.stderr
    summary = [ln for ln in combined.splitlines() if ln.startswith("compass ci:")]
    assert summary, f"no summary line in the sweep output:\n{combined}"
    last = summary[-1]

    assert "every issue" not in last, (
        f"the summary claims coverage of every issue while the run did not "
        f"fully check at least one:\n  {last}"
    )
    # The scenario asks for counts, not for particular words - so this looks
    # for the numbers rather than a phrase the implementation is free to
    # word better. One issue exists and it was not fully checked, so the
    # summary must show a fully-checked count of 0 and account for the one.
    assert re.search(r"\b0\b", last) and re.search(r"\b1\b", last), (
        f"the summary does not say how many issues were fully checked and "
        f"how many were not:\n  {last}"
    )
