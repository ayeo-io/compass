"""The stop hook checks the artifacts that exist today.

The stop hook reads `acceptance-criteria.md` and the manifest's
`follow_ups:`, which are what a 9.0.0 issue writes.

  * The reproduction-scenario check reads `acceptance-criteria.md`. A check
    that can never pass is worse than one that can never fail: people learn
    to ignore it.

  * The outstanding-follow-up scan reads the manifest's `follow_ups:`. 9.0.0
    writes no delivery-approach record to hold a follow-up section (ADR-091).

Scenario ids: see the issue's acceptance criteria (group G).
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "stop.sh"

SPEC_WITH_REPRO = """# Acceptance criteria - demo

### SCN-1 - the reproduction, promoted

```gherkin
Given the defect reproduces
 When the fix is applied
 Then the regression test covers it
```
"""


SPINE = '''schema_version: "2.0"
task: "demo"
created: "2026-08-13"
status: active
assessment: {risk: contained, familiarity: brownfield-mapped, size: small,
  goal: delivery, urgency: live-defect, role: engineer, labels: []}
delivery_approach: hotfix
topology: solo
policy_rules_fired: []
stages: {frame: full, specify: light, clarify: collapsed, plan: collapsed,
  distribute: skipped, build: full, verify: full, land: full}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups:
- id: FU-1
  status: outstanding
  description: promote the reproduction test into a real scenario
reassessments: []
friction: []
'''


def _project(tmp_path, *, spec_body=None, spec_name="acceptance-criteria.md"):
    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    (work / "manifest.yml").write_text(SPINE, encoding="utf-8")
    if spec_body is not None:
        (work / spec_name).write_text(spec_body, encoding="utf-8")
    return tmp_path


def _run(project):
    return subprocess.run(
        ["bash", str(HOOK)], input="{}", cwd=str(project),
        capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(project),
             "CLAUDE_PROJECT_DIR": str(project)},
    )


def test_a_promoted_reproduction_is_recognised(tmp_path):
    """The live acceptance artifact, with a reproduction scenario in it."""
    project = _project(tmp_path, spec_body=SPEC_WITH_REPRO)
    out = _run(project).stderr

    assert "never promoted" not in out and "does not exist" not in out, (
        f"the hook reported the reproduction scenario missing, though "
        f"acceptance-criteria.md contains one - it is still reading the "
        f"retired artifact name:\n{out}"
    )


def test_a_missing_reproduction_is_still_reported(tmp_path):
    """The control. Reading the live artifact must not stop the check firing."""
    project = _project(tmp_path, spec_body="# Acceptance criteria - demo\n")
    out = _run(project).stderr

    assert "reproduction" in out.lower(), (
        f"a hotfix whose acceptance criteria contain no reproduction scenario "
        f"was not reported:\n{out}"
    )


def test_an_outstanding_follow_up_is_reported(tmp_path):
    """The follow-up the manifest records as outstanding is reported."""
    project = _project(tmp_path, spec_body=SPEC_WITH_REPRO)
    out = _run(project).stderr

    assert "follow-up" in out.lower() or "follow up" in out.lower(), (
        f"the outstanding follow-up in the manifest was not reported:\n{out}"
    )
