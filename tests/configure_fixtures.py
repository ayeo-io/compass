"""Scratch projects and helpers for `issue configure` and the reassess commit.

A project here is a temporary directory with one issue. `committed` runs the
real `compass approach evaluate --write`, so generation 1 is the one the
command stores. Used by `test_issue_configure.py` and
`test_generation_recovery.py` (issue `configure-and-reassess`).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "feature"

MANIFEST = {
    "schema_version": "2.0", "issue": SLUG, "created": "2026-10-07", "status": "active",
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "standard", "goal": "delivery", "role": "engineer",
                   "labels": []},
    "evidence": [],
}


def env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=env(cwd),
                       capture_output=True, text=True, timeout=240)
    return r.returncode, r.stdout, r.stderr


def project(tmp_path, compass_yml=None, manifest=None, slug=SLUG):
    """A scratch project with one issue; returns `(root, task_dir)`."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".compass").mkdir(exist_ok=True)
    task_dir = tmp_path / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    body = dict(MANIFEST, issue=slug) if manifest is None else manifest
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(
            compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(compass_yml),
            encoding="utf-8")
    return tmp_path, task_dir


def manifest_of(task_dir):
    return yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))


def write_manifest(task_dir, **changes):
    body = manifest_of(task_dir)
    body.update(changes)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")


def gen(task_dir, n):
    return task_dir / "generations" / str(n)


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def committed(tmp_path, **kwargs):
    """A project whose issue is at generation 1, committed by the real command."""
    root, task_dir = project(tmp_path, **kwargs)
    code, out, err = run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    assert manifest_of(task_dir)["generation"] == 1
    return root, task_dir


def reassess(root, *extra):
    return run(root, "approach", "evaluate", "--issue", SLUG, "--write",
               "--reason", "test", *extra)


def configure(root, *argv):
    return run(root, "issue", "configure", "--issue", SLUG, *argv)


def team(severity):
    """A project layer that adds one check of its own."""
    return {"schema": 1, "owner": "jed72", "checks": {"team-check": {
        "statement": "A team check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": severity, "on_skipped": "fail"}}}


def waived_project(tmp_path):
    """An issue at generation 1 whose own layer waives the project check's
    severity (blocking -> advisory), with the approval record that backs it."""
    body = dict(MANIFEST)
    body["config"] = {"checks": {"team-check": {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "A one-line fix.", "approved_by": "EV-1"}}}}
    body["evidence"] = [{
        "id": "EV-1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "owner", "scope": "waiver",
        "timestamp": "2026-10-07T09:00:00Z",
        "waiver": {"scope": "issue", "entry": "checks.team-check",
                   "fields": {"severity": {"from": "blocking", "to": "advisory"}}}}]
    root, task_dir = project(tmp_path, compass_yml=team("blocking"), manifest=body)
    code, out, err = reassess(root)
    assert code == 0, out + err
    return root, task_dir
