"""Shared fixtures for the tests of issue `approve-inside-claude-code`.

`project(tmp_path)` copies one template project, built once per test run:

- `compass.yml` names the owner `jed72` and a human check `dod-reviewed`
  that lists `owner`, in the `plan` entry list;
- issue `feature` is labelled payments and migrations, at generation 1,
  with the `requirements-review.md` box of the check ticked;
- `.compass/current-task` names the issue.

`event(...)` builds the `UserPromptExpansion` input Claude Code sends, in the
shape U0 measured on Claude Code 2.1.300.
"""
from __future__ import annotations

import os
import pty
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

SLUG = "feature"
CHECK = "dod-reviewed"
STATEMENT = "The definition of done is reviewed."
OWNER = "jed72"
LABELS = ["payments", "migrations"]

_TEMPLATE = {}


def env(home, **extra):
    base = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    base.update({k: v for k, v in extra.items() if v is not None})
    return base


def run(root, *argv, terminal=False, **extra_env):
    """Run the CLI. With `terminal` its stdin is a pseudo-terminal, as when a
    person types; without, stdin is empty, as in an agent session."""
    master = slave = None
    if terminal:
        master, slave = pty.openpty()
    try:
        r = subprocess.run([sys.executable, str(CLI), *argv], cwd=root,
                           env=env(root, **extra_env), capture_output=True, text=True,
                           timeout=180, stdin=slave if terminal else subprocess.DEVNULL)
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    return r.returncode, r.stdout, r.stderr


def _build(root):
    human = {"kind": "human", "severity": "blocking", "on_skipped": "fail"}
    config = {"schema": 1, "owner": OWNER, "capabilities": {"entry-exit-evaluation": True},
              "checks": {CHECK: dict(human, statement=STATEMENT, approvers=["owner"])},
              "stages": {"plan": {"set": {"entry": {"add": [CHECK]}}}}}
    task_dir = root / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (root / "compass.yml").write_text(yaml.safe_dump(config), encoding="utf-8")
    manifest = {"schema_version": "2.0", "issue": SLUG, "created": "2026-10-15",
                "status": "active",
                "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                               "size": "medium", "goal": "delivery", "role": "engineer",
                               "labels": list(LABELS)},
                "evidence": []}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    code, out, err = run(root, "approach", "evaluate", "--issue", SLUG, "--write",
                         *[f"--justify={d}=test" for d in
                           ("risk", "familiarity", "size", "goal", "role")])
    assert code == 0, out + err
    body = manifest_of(root)
    assert body["generation"] == 1, body
    body["current_phase"] = "plan"
    save_manifest(root, body)
    (task_dir / "requirements-review.md").write_text(
        f"# R\n\n### Definition of Ready\n\n- [x] {STATEMENT}\n\nNext stage: x\n",
        encoding="utf-8")
    (root / ".compass" / "current-task").write_text(SLUG + "\n", encoding="utf-8")


def project(tmp_path):
    """A copy of the template project; returns its root."""
    if "root" not in _TEMPLATE:
        # The run's base temporary folder, which pytest removes in time.
        base = tmp_path.parent / f"approval-template-{os.getpid()}"
        if base.exists():
            shutil.rmtree(base)
        base.mkdir(parents=True)
        _build(base)
        _TEMPLATE["root"] = base
    root = tmp_path / "proj"
    shutil.copytree(_TEMPLATE["root"], root)
    return root


def task_dir(root):
    return root / ".compass" / "work" / SLUG


def manifest_of(root):
    return yaml.safe_load((task_dir(root) / "manifest.yml").read_text(encoding="utf-8"))


def save_manifest(root, body):
    (task_dir(root) / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                                 encoding="utf-8")


def pending_dir(root):
    return task_dir(root) / "approval-requests" / "pending"


def closed_dir(root):
    return task_dir(root) / "approval-requests" / "closed"


def read_request(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def event(root, command="compass:approve", args="", session="sess-1", prompt_id=None,
          **changes):
    """A `UserPromptExpansion` hook input, as Claude Code 2.1.300 sends it."""
    body = {"session_id": session,
            "transcript_path": str(root / "transcript.jsonl"),
            "cwd": str(root),
            "scratchpad_dir": str(root / "scratch"),
            "prompt_id": prompt_id or str(uuid.uuid4()),
            "permission_mode": "default",
            "hook_event_name": "UserPromptExpansion",
            "expansion_type": "slash_command",
            "command_name": command,
            "command_args": args,
            "command_source": "plugin",
            "prompt": f"/{command} {args}".rstrip()}
    body.update(changes)
    return body
