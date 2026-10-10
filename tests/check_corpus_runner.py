"""Builds each check-corpus case and computes the verdict the check gives.

ADR-038 makes the corpus the only evidence that a check's behaviour held
across a release, so a case must run the implementation rather than record a
label. Each case is a function here that writes the small project the check
reads (a manifest, evidence files, a document) into a temporary directory.
`run_case` then calls the implementation from the registry on it and maps
the result to `pass`, `fail` or `nothing-to-check`. The verdict is never
read from `expected.yml`; the test compares the two.

Every implementation has a `broken` case (the input its mutation proof breaks)
and a `restored` case (the input put right, or an input the check declines).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

from compass_pkg import check_registry
from compass_pkg.check_results import NOTHING_TO_CHECK

ROOT = Path(__file__).resolve().parent.parent
SLUG = "case"
CASES: dict[tuple[str, str], object] = {}


def case(impl: str, name: str):
    def register(fn):
        CASES[(impl, name)] = fn
        return fn
    return register


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _issue(root: Path, manifest: dict, slug: str = SLUG) -> tuple[dict, Path]:
    """Write `manifest` as the record of issue `slug` under a project at `root`."""
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)
    manifest = dict(manifest, task=slug)
    _write(task_dir / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    return manifest, task_dir


def _scenario(**extra) -> dict:
    return dict({"id": "S-1", "intent": "INT-1"}, **extra)


def verdict(result) -> str:
    passed = result[0]
    if passed is NOTHING_TO_CHECK:
        return "nothing-to-check"
    return "pass" if passed else "fail"


def run_case(impl: str, name: str, root: Path) -> str:
    """Build the case under `root` and return the implementation's verdict."""
    task, task_dir = CASES[(impl, name)](root)
    fn = check_registry.REGISTRY[impl].fn
    here = os.getcwd()
    os.chdir(root)
    try:
        return verdict(fn(task, str(task_dir)))
    finally:
        os.chdir(here)


def computed_verdicts(impl: str, scratch: Path) -> dict[str, str]:
    out = {}
    for (name_impl, name) in sorted(CASES):
        if name_impl == impl:
            root = scratch / impl / name
            root.mkdir(parents=True)
            out[name] = run_case(impl, name, root)
    return out


# --- scenario and trace checks -----------------------------------------------------

@case("scenarios-have-tests", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()]})


@case("scenarios-have-tests", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario(tests=["tests/test_a.py"])]})


@case("scenario-has-id-and-intent", "broken")
def _(root):
    return _issue(root, {"scenarios": [{"id": "S-1"}]})


@case("scenario-has-id-and-intent", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario()]})


@case("changed-code-traces-to-scenario", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "changed_files": [{"path": "src/a.py"}]})


@case("changed-code-traces-to-scenario", "restored")
def _(root):
    _write(root / "src" / "a.py", "x = 1\n")
    return _issue(root, {"scenarios": [_scenario()],
                         "changed_files": [{"path": "src/a.py",
                                            "scenarios": ["S-1"]}]})


@case("claim-traces-to-scenario", "broken")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "claims": [{"id": "C-1", "scenario": "S-9"}]})


@case("claim-traces-to-scenario", "restored")
def _(root):
    return _issue(root, {"scenarios": [_scenario()],
                         "claims": [{"id": "C-1", "scenario": "S-1"}]})


@case("declared-tests-resolve", "broken")
def _(root):
    _write(root / "tests" / "test_a.py", "def test_other():\n    pass\n")
    return _issue(root, {"gates": [{"id": "verify.correctness", "status": "pass"}],
                         "scenarios": [_scenario(
                             tests=["tests/test_a.py::test_missing"])]})


@case("declared-tests-resolve", "restored")
def _(root):
    _write(root / "tests" / "test_a.py", "def test_there():\n    pass\n")
    return _issue(root, {"gates": [{"id": "verify.correctness", "status": "pass"}],
                         "scenarios": [_scenario(
                             tests=["tests/test_a.py::test_there"])]})


@case("scenarios-are-executable", "broken")
def _(root):
    _write(root / ".compass" / "config.yml", "project:\n  bdd_runner: behave\n")
    return _issue(root, {"scenarios": [_scenario()]})


@case("scenarios-are-executable", "restored")
def _(root):
    _write(root / ".compass" / "config.yml", "project:\n  bdd_runner: behave\n")
    task, task_dir = _issue(root, {"scenarios": [_scenario()]})
    spec = "# Acceptance criteria\n\nS-1\n"
    _write(task_dir / "acceptance-criteria.md", spec)
    _write(task_dir / "evidence" / "bdd-run.json", json.dumps({
        "spec_sha256": hashlib.sha256(spec.encode()).hexdigest(),
        "scenarios_seen": ["S-1"]}))
    return task, task_dir


# --- evidence checks ---------------------------------------------------------------

def _record(task_dir: Path, name: str, body: dict) -> str:
    _write(task_dir / "evidence" / name, json.dumps(body))
    return f"evidence/{name}"


@case("suite-passed", "broken")
def _(root):
    return _issue(root, {})


@case("suite-passed", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("gate-evidence-present", "broken")
def _(root):
    return _issue(root, {"gates": [{"id": "verify.correctness",
                                    "status": "pass", "evidence": []}]})


@case("gate-evidence-present", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    task["gates"] = [{"id": "verify.correctness", "status": "pass",
                      "evidence": ["EV-1"]}]
    return task, task_dir


@case("human-approval-present", "broken")
def _(root):
    return _issue(root, {})


@case("human-approval-present", "restored")
def _(root):
    return _issue(root, {"evidence": [{
        "id": "EV-1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "maintainer", "scope": "the change",
        "timestamp": "2026-10-06T10:00:00Z"}]})


@case("backfills-paid", "broken")
def _(root):
    return _issue(root, {"follow_ups": [{"id": "FU-1", "status": "outstanding"}]})


@case("backfills-paid", "restored")
def _(root):
    return _issue(root, {"follow_ups": [{"id": "FU-1", "status": "resolved"}]})


def _approved_issue(root, status):
    return _issue(root, {
        "delivery_approach": "regular",
        "gates": [{"id": "verify.correctness", "status": "pass", "evidence": ["EV-1"]}],
        "artifacts": [{"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
                       "status": status, "path": "docs/technical-design.md",
                       "reason": "every regular approach carries one"}]})


@case("artifacts-approved", "broken")
def _(root):
    return _approved_issue(root, "draft")


@case("artifacts-approved", "restored")
def _(root):
    return _approved_issue(root, "approved")


@case("spike-conclusion-present", "broken")
def _(root):
    return _issue(root, {})


@case("spike-conclusion-present", "restored")
def _(root):
    return _issue(root, {"evidence": [{"id": "EV-1", "type": "spike-conclusion",
                                       "decision": "discard"}]})


@case("spike-no-production-changes", "broken")
def _(root):
    return _issue(root, {"changed_files": [{"path": "src/a.py"}]})


@case("spike-no-production-changes", "restored")
def _(root):
    return _issue(root, {})


@case("consistency-check-passes", "broken")
def _(root):
    return _issue(root, {"gates": [{"id": "verify.analyze", "status": "pending"}]})


@case("consistency-check-passes", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "analyze.json", {"finding_count": 0})
    task["gates"] = [{"id": "verify.analyze", "status": "pending"}]
    task["evidence"] = [{"id": "EV-1", "type": "consistency-check", "path": path}]
    return task, task_dir


def _rerun(root, attempts):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", {"exit_code": 0, "attempts": attempts,
                                            "rerun_without_change": attempts > 1,
                                            "test": "tests/test_a.py::test_x"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("no-trusted-rerun", "broken")
def _(root):
    return _rerun(root, 2)


@case("no-trusted-rerun", "restored")
def _(root):
    return _rerun(root, 1)


def _stamped(root, record_on_disk):
    task, task_dir = _issue(root, {})
    path = _record(task_dir, "green.json", record_on_disk)
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path,
                         "record_id": "rec-a"}]
    return task, task_dir


@case("evidence-identity-matches", "broken")
def _(root):
    return _stamped(root, {"record_id": "rec-b"})


@case("evidence-identity-matches", "restored")
def _(root):
    return _stamped(root, {"record_id": "rec-a"})


@case("dod-evidence-typed", "broken")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "verification-report.md",
           "## Definition of Done\n\n- [ ] the thing is done\n")
    return task, task_dir


@case("dod-evidence-typed", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "verification-report.md",
           "## Definition of Done\n\n- [x] the thing is done\n")
    return task, task_dir


# --- checks that read a document or another issue ----------------------------------

@case("borrowed-documents-answered", "broken")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "threat-model.md",
           "| Threat | Answer |\n|---|---|\n| data loss on upgrade | none yet |\n")
    return task, task_dir


@case("borrowed-documents-answered", "restored")
def _(root):
    task, task_dir = _issue(root, {})
    _write(task_dir / "threat-model.md",
           "| Threat | Answer |\n|---|---|\n| data loss on upgrade | TRC-A1 |\n")
    return task, task_dir


def _dashboard(root, move_manifest):
    from compass_pkg.dashboard import render_dashboard
    task, task_dir = _issue(root, {"assessment": {"risk": "contained"}})
    _write(task_dir / "README.md", render_dashboard(str(task_dir)))
    if move_manifest:
        task = dict(task, assessment={"risk": "critical"})
        _write(task_dir / "manifest.yml", yaml.safe_dump(task, sort_keys=False))
    return task, task_dir


@case("dashboard-current", "broken")
def _(root):
    return _dashboard(root, True)


@case("dashboard-current", "restored")
def _(root):
    return _dashboard(root, False)


def _landed_by(root, delivered):
    task, task_dir = _issue(root, {"status": "landed",
                                   "landed_by": [{"issue": "other"}]})
    _issue(root, {"status": "landed", "scenarios": [_scenario()],
                  "delivered": [SLUG] if delivered else []}, slug="other")
    return task, task_dir


@case("landed-by-resolves", "broken")
def _(root):
    return _landed_by(root, False)


@case("landed-by-resolves", "restored")
def _(root):
    return _landed_by(root, True)


def _multiagent(root, subtasks):
    return _issue(root, {"status": "landed", "created": "2026-01-01",
                         "stages": {"breakdown": "multiagent"},
                         "subtasks": subtasks})


@case("multiagent-run-recorded", "broken")
def _(root):
    return _multiagent(root, [])


@case("multiagent-run-recorded", "restored")
def _(root):
    return _multiagent(root, [{"id": "subtask-1", "status": "done",
                               "review_rounds": [{"verdict": "pass"}]}])


# --- checks that read git or run a project command ---------------------------------

def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=root, check=True, capture_output=True)


@case("evidence-matches-tree", "broken")
def _(root):
    task, task_dir = _issue(root, {"status": "landed", "land_commit": "not-a-commit"})
    path = _record(task_dir, "green.json", {"exit_code": 0, "tree_id": "a" * 40,
                                            "timestamp": "2026-10-06T10:00:00Z"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("evidence-matches-tree", "restored")
def _(root):
    from compass_pkg.binding import claimed_paths, work_tree_id
    _write(root / "src" / "a.py", "x = 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "src/a.py")
    _git(root, "commit", "-q", "-m", "seed")
    task, task_dir = _issue(root, {"changed_files": [{"path": "src/a.py",
                                                      "scenarios": ["S-1"]}]})
    tree = work_tree_id(str(root), claimed_paths(task))
    path = _record(task_dir, "green.json", {"exit_code": 0, "tree_id": tree,
                                            "timestamp": "2026-10-06T10:00:00Z"})
    task["evidence"] = [{"id": "EV-1", "type": "test-run", "path": path}]
    return task, task_dir


@case("command-passes", "broken")
def _(root):
    gov = root / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(ROOT / "governance" / name, gov / name)
    rules = yaml.safe_load((gov / "guardrails.yml").read_text(encoding="utf-8"))
    rules["project"] = [{"id": "P-1", "name": "fails", "checks": ["command-passes"],
                         "params": {"command": "false"}}]
    _write(gov / "guardrails.yml", yaml.safe_dump(rules, sort_keys=False))
    _write(root / ".compass" / "config.yml", "allow_project_commands: true\n")
    return _issue(root, {})


# No project guardrail declares a command, so the check has nothing to run.
@case("command-passes", "restored")
def _(root):
    return _issue(root, {})
