"""Policy provenance in the audit trail (issue governance-drift-detection).

`delivery-approach.md` records which guardrails fired and why. It said
nothing about WHICH POLICY produced those answers - so a reader six months
later could not tell whether a light delivery approach reflected the
assessment or stale governance.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-C1`..`TRC-C3`).
9.0.0 removed the drift report (ADR-098), and `TRC-C2`, which said a project
whose policy lacked shipped rules saw the drift, with it.
"""

# The "which policy file" line is provenance and prints under --verbose.
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import yaml
from check_set_files import view as shipped_view  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"

READINGS = ["--assessment", "risk=cross-cutting", "--assessment",
            "familiarity=brownfield-mapped", "--assessment", "size=medium",
            "--assessment", "intent=delivery", "--assessment", "role=engineer"]


def _project(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(GOVERNANCE, proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    return proj


def _evaluate(proj):
    return subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", *READINGS],
        cwd=str(proj), capture_output=True, text=True, timeout=60,
    )


# ---------------------------------------------------------------------------
# `TRC-C1` - approach evaluate reports which policy it read
# ---------------------------------------------------------------------------

def test_trc_c1_route_evaluate_should_report_which_policy_it_read(tmp_path):
    proj = _project(tmp_path)
    result = _evaluate(proj)
    assert result.returncode == 0, result.stderr

    out = result.stdout
    # 9.0.0 reads the check set (ADR-094); no project copy is read (ADR-098).
    assert "the check set" in out, f"the policy is not named:\n{out}"


# `TRC-C3` read the delivery-approach template, which 9.0.0 deleted (ADR-091).
# The issue's stored generation records which policy produced the approach.
