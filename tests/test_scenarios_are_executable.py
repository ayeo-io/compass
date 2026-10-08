"""The scenarios-are-executable check (issue phase-2-skills-check-and-cli-split).

`compass bdd extract` lets a project run its Gherkin. This check confirms
that the project did.

Two constraints shape everything here:

  * `compass check` is the fast mechanical gate. It runs in CI, in hooks, and on
    machines that never installed the project's dev dependencies, so it cannot
    run the BDD suite. It reads a record written by `compass bdd verify`.
  * A record is only evidence if it still describes the spec it claims to
    check. The check detects a stale record by the spec's content hash, never
    by mtime - `git checkout` rewrites mtimes, so a fresh CI clone would read
    every stale record as current. That is a false green in the exact place
    it matters most.

The common path is a project that has wired no runner at all. It must pass,
with a reason - a check that punished projects for not opting in would be worse
than no check.

Spec: phase-2-skills-check-and-cli-split/acceptance-criteria.md (`TRC-C1`..`C6`).
"""

# These tests read `compass check`'s per-check detail, which it prints only
# under `--verbose`.
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"

SPEC = """# Spec - t

### Scenario: one
<!-- traceability id: TRC-A1 · serves: INT-1 -->

```gherkin
Scenario: one
  Given a thing
  When it happens
  Then it holds
```

### Scenario: two
<!-- traceability id: TRC-A2 · serves: INT-1 -->

```gherkin
Scenario: two
  Given another thing
  When it happens
  Then it holds
```
"""

TASK = """schema_version: '1.1'
task: t
created: '2026-08-03'
status: active
readings:
  blast_radius: {blast}
  terrain: greenfield
  magnitude: small
  intent: delivery
  urgency: none
  role: engineer
  touches: []
route: standard
topology: solo
fired_guardrails: []
phases: {{}}
evidence: []
gates: []
scenarios:
- id: TRC-A1
  title: one
  intent: INT-1
  tests: ['tests/t.py::a']
- id: TRC-A2
  title: two
  intent: INT-1
  tests: ['tests/t.py::b']
changed_files: []
claims: []
backfills: []
reframes: []
friction: []
"""


def make(tmp_path, *, runner=None, seen=None, spec_hash=None,
         blast="contained"):
    proj = tmp_path / "proj"
    task_dir = proj / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    shutil.copytree(GOVERNANCE, proj / "governance")

    cfg = "version: 1.0.0\nmode: enforced\n"
    if runner:
        cfg += f"project:\n  bdd_runner: {runner}\n"
    (proj / ".compass" / "config.yml").write_text(cfg)
    (proj / ".compass" / "current-task").write_text("t\n")
    (task_dir / "manifest.yml").write_text(TASK.format(blast=blast))
    (task_dir / "acceptance-criteria.md").write_text(SPEC)

    if seen is not None:
        h = spec_hash if spec_hash is not None else hashlib.sha256(
            SPEC.encode()).hexdigest()
        (task_dir / "evidence").mkdir(exist_ok=True)
        (task_dir / "evidence" / "bdd-run.json").write_text(json.dumps({
            "command": "pytest tests/", "exit_code": 0,
            "timestamp": "2026-08-03T00:00:00Z", "spec_sha256": h,
            "scenarios_seen": seen, "runner": runner or "pytest-bdd",
        }))
    return proj


def check(proj):
    return subprocess.run([sys.executable, str(CLI), "check", "--verbose", "--issue", "t"],
                          cwd=str(proj), capture_output=True, text=True,
                          timeout=120)


def line_for(out, name="scenarios-are-executable"):
    for l in out.splitlines():
        if name in l:
            return l
    return ""


# ---------------------------------------------------------------------------
# Registered and implemented (TRC-C1)
# ---------------------------------------------------------------------------

def test_trc_c1_the_check_should_be_registered_and_implemented():
    g = yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
    assert "scenarios-are-executable" in g["checks"], (
        "the check is not declared in guardrails.yml")
    g1 = next(x for x in g["defaults"] if x["id"] == "G1")
    assert "scenarios-are-executable" in g1["checks"], (
        "G1 does not run the check")

    # policy lint fails when a guardrail names a check the CLI does not
    # implement, so a clean lint proves CHECK_FNS carries it.
    r = subprocess.run([sys.executable, str(CLI), "policy", "lint"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# No runner wired: pass, with a reason. The common path (TRC-C2).
# ---------------------------------------------------------------------------

def test_trc_c2_a_project_that_has_wired_no_runner_should_pass_with_a_stated_reason(tmp_path):
    out = check(make(tmp_path)).stdout
    line = line_for(out)
    assert line, f"the check did not run at all:\n{out}"
    # Labelled NOTHING TO CHECK since #110: not a failure, and not a PASS.
    assert line.strip().startswith("NOTHING TO CHECK"), (
        f"a project that wired no runner was penalised:\n{line}")
    assert "runner" in line.lower(), (
        f"the pass gives no reason, so a reader cannot tell it was a no-op:\n{line}")


# ---------------------------------------------------------------------------
# Every scenario accounted for, or named (`TRC-C3` / `C4`)
# ---------------------------------------------------------------------------

def test_trc_c3_every_scenario_bound_to_a_collected_step_definition_should_pass(tmp_path):
    proj = make(tmp_path, runner="pytest-bdd", seen=["TRC-A1", "TRC-A2"])
    line = line_for(check(proj).stdout)
    assert line.strip().startswith("PASS"), f"a fully-bound spec failed:\n{line}"
    assert "2" in line, f"the pass does not say how many were accounted for:\n{line}"


def test_trc_c4_a_scenario_the_runner_never_ran_should_be_named(tmp_path):
    proj = make(tmp_path, runner="pytest-bdd", seen=["TRC-A1"],
                blast="cross-cutting")
    result = check(proj)
    line = line_for(result.stdout)
    assert line.strip().startswith("FAIL"), (
        f"a scenario the runner never ran did not fail the check:\n{line}")
    assert "TRC-A2" in result.stdout, (
        f"the unaccounted scenario is not named:\n{result.stdout}")


# ---------------------------------------------------------------------------
# A stale record is not success (TRC-C5)
# ---------------------------------------------------------------------------

def test_trc_c5_a_stale_runner_result_should_not_be_read_as_success(tmp_path):
    proj = make(tmp_path, runner="pytest-bdd", seen=["TRC-A1", "TRC-A2"],
                spec_hash="0" * 64, blast="cross-cutting")
    result = check(proj)
    line = line_for(result.stdout)
    assert line.strip().startswith("FAIL"), (
        f"a record describing a different spec was read as success:\n{line}")
    combined = result.stdout.lower()
    assert "stale" in combined or "predates" in combined or "changed" in combined, (
        f"the message does not say the record no longer matches the spec:\n{result.stdout}")


# ---------------------------------------------------------------------------
# Advisory unless the delivery approach promotes it (TRC-C6)
# ---------------------------------------------------------------------------

def test_trc_c6_the_check_should_be_advisory_unless_the_route_promotes_it(tmp_path):
    contained = make(tmp_path / "a", runner="pytest-bdd", seen=["TRC-A1"],
                     blast="contained")
    line = line_for(check(contained).stdout)
    assert line.strip().startswith("ADVISORY"), (
        f"a contained-blast-radius finding was not shown as advisory:\n{line}")
    assert "FAIL" not in line, (
        f"a contained-blast-radius task was blocked by an advisory check:\n{line}")
    assert "TRC-A2" in line or "advisory" in line.lower(), (
        f"advisory mode hides the finding entirely, which helps nobody:\n{line}")

    crosscutting = make(tmp_path / "b", runner="pytest-bdd", seen=["TRC-A1"],
                        blast="cross-cutting")
    line = line_for(check(crosscutting).stdout)
    assert line.strip().startswith("FAIL"), (
        f"the same finding did not block at cross-cutting blast radius:\n{line}")
