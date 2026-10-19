"""In advisory mode `compass ci` keeps exit code 0 but must not say PASS
after a check has failed.

A person reading a CI log sees the last line first. Advisory mode changes
the exit code, not what the summary line says about the checks.

Scenario id: `TRC-001` in
advisory-ci-no-pass-after-fail/acceptance-criteria.md.
"""
from __future__ import annotations

import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

SPINE = """schema_version: "2.0"
task: "{slug}"
created: "2026-08-12"
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


def _advisory_project(tmp_path, slug):
    work = tmp_path / ".compass" / "work" / slug
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: advisory\n", encoding="utf-8")
    (work / "manifest.yml").write_text(SPINE.format(slug=slug), encoding="utf-8")
    gov = tmp_path / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        (gov / name).write_text(
            (ROOT / "governance" / name).read_text(encoding="utf-8"),
            encoding="utf-8")
    return tmp_path


def test_advisory_ci_summary_says_fail_after_a_failed_check(tmp_path):
    project = _advisory_project(tmp_path, "in-flight")
    result = subprocess.run(
        ["python3", str(CLI), "ci"],
        cwd=str(project), capture_output=True, text=True, timeout=120)
    out = result.stdout + result.stderr
    assert result.returncode == 0, f"advisory mode must exit 0:\n{out}"
    assert "FAIL" in out, f"the setup must produce a failed check:\n{out}"
    summary = [ln for ln in out.splitlines() if ln.startswith("compass ci:")]
    assert summary, f"no summary line:\n{out}"
    assert "PASS" not in summary[-1], f"summary says PASS after a failure:\n{out}"
    assert "FAIL" in summary[-1] and "check group" in summary[-1], summary[-1]
