"""A manifest the evaluator wrote passes the linter the same CLI ships.

`compass approach evaluate --write` records a re-assessment with `kind` and
`changed` alongside the required fields. `schemas/manifest.schema.json` set
`additionalProperties: false` on that entry and declared neither, so every
honest re-assessment left the issue failing `compass issue lint`.

That punished the behaviour the methodology asks for. Re-assessing is
described as a normal event, and an approach quietly outgrown is the failure
it warns about - so a tool that fails the build for recording one teaches
people not to record them.

Both keys earn their place: `kind` is what separates a judgement re-assessment
from a scope change in `compass retro`'s re-sizing signal, and `changed` is the
audit detail.

Scenario ids: see docs/system-spec.md (TRC-1, `TRC-2`).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

SPINE = """schema_version: "2.0"
task: "reassessed"
created: "2026-08-12"
status: active
assessment:
  risk: contained
  familiarity: brownfield-mapped
  size: small
  goal: delivery
  role: engineer
  labels: []
delivery_approach: null
topology: null
policy_rules_fired: []
stages: {}
evidence: []
gates: []
scenarios: []
changed_files: []
claims: []
follow_ups: []
reassessments: []
friction: []
"""


def _project(tmp_path):
    work = tmp_path / ".compass" / "work" / "reassessed"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    (work / "manifest.yml").write_text(SPINE, encoding="utf-8")
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    return tmp_path


def _run(project, *args):
    return subprocess.run(
        ["python3", str(CLI), *args],
        cwd=str(project), capture_output=True, text=True, timeout=120,
    )


def test_trc_1_a_recorded_reassessment_still_lints_clean(tmp_path):
    project = _project(tmp_path)

    first = _run(project, "approach", "evaluate", "--issue", "reassessed", "--write")
    assert first.returncode == 0, first.stdout + first.stderr

    manifest = project / ".compass" / "work" / "reassessed" / "manifest.yml"
    manifest.write_text(manifest.read_text().replace("size: small", "size: large", 1))

    again = _run(project, "approach", "evaluate", "--issue", "reassessed",
                 "--write", "--reason", "scope grew")
    assert again.returncode == 0, again.stdout + again.stderr
    assert "RE-ASSESSMENT recorded" in (again.stdout + again.stderr), (
        "the evaluator did not record a re-assessment, so this proves nothing"
    )

    lint = _run(project, "issue", "lint", "--issue", "reassessed")
    assert lint.returncode == 0, (
        "the CLI wrote a manifest its own linter rejects - recording an honest "
        f"re-assessment should not redden the build:\n{lint.stdout}{lint.stderr}"
    )


def test_trc_2_the_schema_declares_both_keys_the_evaluator_writes():
    """Declared, not merely tolerated.

    Loosening `additionalProperties` would also make the lint pass, and would
    trade one caught defect for a whole uncaught class of them.
    """
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    entry = schema["properties"]["reassessments"]["items"]
    assert entry.get("additionalProperties") is False, (
        "the re-assessment entry must stay closed - the fix is to declare "
        "the keys, not to stop checking"
    )
    for key in ("kind", "changed"):
        assert key in entry["properties"], (
            f"the evaluator writes {key!r} into every re-assessment; the "
            f"schema must declare it"
        )
