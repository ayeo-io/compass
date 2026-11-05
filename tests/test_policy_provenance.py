"""Policy provenance in the audit trail (issue governance-drift-detection).

`delivery-approach.md` records which guardrails fired and why. It said
nothing about WHICH POLICY produced those answers - so a reader six months
later could not tell whether a light delivery approach reflected the
assessment or stale governance.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-C1`..`TRC-C3`).
"""

# The "which policy file" line is provenance and prints under --verbose.
# POLICY DRIFT prints in the default view, because a project running a
# policy missing rules the framework ships gets a lighter approach than it
# should, and a reader cannot tell that from a genuinely light one - so it
# is a concern on the first screen. The drift test below asserts the
# default view, deliberately.
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"

READINGS = ["--assessment", "risk=cross-cutting", "--assessment",
            "familiarity=brownfield-mapped", "--assessment", "size=standard",
            "--assessment", "intent=delivery", "--assessment", "role=engineer"]


def _project(tmp_path, stale=False):
    proj = tmp_path / "proj"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(GOVERNANCE, proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    if stale:
        rp = proj / "governance" / "routing-policy.yml"
        d = yaml.safe_load(rp.read_text())
        rg = d["routing_guardrails"]
        rg["floors"] = [f for f in rg["floors"]
                        if f["id"] not in ("RP-REQUIRE-003", "RP-REQUIRE-004")]
        d["version"] = "1.0.0"
        rp.write_text(yaml.safe_dump(d, sort_keys=False))
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
    assert "routing-policy.yml" in out, f"the policy file is not named:\n{out}"
    version = str(yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())["version"])
    assert version in out, f"the policy version {version} is not reported:\n{out}"


# ---------------------------------------------------------------------------
# `TRC-C2` - a drifted project's approach output says so
# ---------------------------------------------------------------------------

def test_trc_c2_a_drifted_projects_route_output_should_say_so(tmp_path):
    out = _evaluate(_project(tmp_path, stale=True)).stdout
    assert re.search(r"\b2\b", out), f"the count of missing rules is absent:\n{out}"
    framework_version = str(
        yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())["version"])
    assert framework_version in out, (
        f"the framework version compared against is not named:\n{out}")
    assert "drift" in out.lower() or "missing" in out.lower(), (
        f"the output does not say the project's policy lacks rules:\n{out}")


# `TRC-C3` read the delivery-approach template, which 9.0.0 deleted (ADR-091).
# The issue's stored generation records which policy produced the approach.
