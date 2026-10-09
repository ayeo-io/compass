"""`compass plan lint` resolves the artifact it is named after.

The default path goes through `artifact_path`, which knows both `design.md`
and `technical-design.md`. Without it, the plan stage reports a visible
error on an issue that has a design, and the way past it is a `--file`
argument that the default path must make unnecessary.

Scenario ids: see docs/system-spec.md (group B).
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

# No placeholder phrase, so a clean lint means the file was read - not that the
# scanner found nothing because it read nothing.
CLEAN_DESIGN = """# Design - demo

## DD-1 - the chosen approach

Chosen: read the value from the manifest. Rejected: recompute it on each call,
which would drift from the recorded assessment.
"""

SPINE = """schema_version: "2.0"
task: "demo"
created: "2026-08-13"
status: active
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
stages: {frame: full, specify: light, clarify: collapsed, plan: collapsed,
  distribute: skipped, build: full, verify: light, land: light}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
friction: []
"""


def _project(tmp_path: pathlib.Path, *, with_design: bool) -> pathlib.Path:
    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    (tmp_path / ".compass" / "current-task").write_text("demo\n", encoding="utf-8")
    (work / "manifest.yml").write_text(SPINE, encoding="utf-8")
    if with_design:
        (work / "technical-design.md").write_text(CLEAN_DESIGN, encoding="utf-8")
    return tmp_path


def _lint(project: pathlib.Path):
    return subprocess.run(
        [sys.executable, str(CLI), "plan", "lint"],
        cwd=str(project), capture_output=True, text=True, timeout=120,
    )


def test_rcd_b1_defaults_to_design_md(tmp_path):
    """With a technical-design.md present and no --file, the lint must find it."""
    project = _project(tmp_path, with_design=True)
    result = _lint(project)
    combined = result.stdout + result.stderr

    assert "no such file" not in combined.lower(), (
        f"`compass plan lint` could not find the technical-design.md sitting in the "
        f"issue directory, so its default path is not the live artifact "
        f"name:\n{combined}"
    )
    assert result.returncode == 0, (
        f"the lint is advisory and must exit 0 when it finds a clean file; "
        f"got {result.returncode}\n{combined}"
    )


def test_rcd_b2_message_names_path_used(tmp_path):
    """When there is nothing to lint, the message must name what it looked for.

    The message must name only the file the command looked for.
    """
    project = _project(tmp_path, with_design=False)
    result = _lint(project)
    combined = result.stdout + result.stderr

    assert "plan.md" not in combined, (
        f"the not-found message still names the retired artifact filename:\n"
        f"{combined}"
    )
    assert "technical-design.md" in combined, (
        f"the message does not name the file it looked for, so a reader "
        f"cannot tell what to create:\n{combined}"
    )
    assert "compass plan lint" in combined, (
        f"the message does not label itself with the verb that produced it:\n"
        f"{combined}"
    )


def test_rcd_b3_absence_is_explained_against_the_record(tmp_path):
    """The reason given for a missing design must be checked, not assumed.

    The command must explain a missing design from the issue's recorded
    approach, not with a fixed sentence - otherwise a reader is told the
    missing file is fine when it is the thing that is wrong.
    """
    project = _project(tmp_path, with_design=False)
    manifest = project / ".compass" / "work" / "demo" / "manifest.yml"
    manifest.write_text(SPINE.replace("plan: collapsed", "plan: thorough"),
                     encoding="utf-8")
    run = _lint(project)
    combined = run.stdout + run.stderr

    assert "collapses" not in combined, (
        f"the plan stage is recorded as full on this issue, so it cannot have "
        f"collapsed - the message explains away a real absence:\n{combined}"
    )
    assert "thorough" in combined and "missing" in combined, (
        f"the message does not say the design is expected and absent:\n"
        f"{combined}"
    )
