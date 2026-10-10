"""Shared scratch-project helpers for the artifact-status tests (issue
`artifact-status-written-by-stages`).

Every project is a real git repository set up with `compass init` and
`compass approach evaluate --write`, driven through `cli/compass`, so the tests
see what a person sees. `approve` gives the verb a pseudo-terminal, as a person
at a keyboard has one.
"""
from __future__ import annotations

import os
import pty
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "feature"
CREATED = "2026-10-10"
DOCS = f"docs/compass/{CREATED}-{SLUG}"

MANIFEST = {
    "schema_version": "2.0", "issue": SLUG, "created": CREATED,
    "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                   "size": "medium", "goal": "delivery", "role": "engineer",
                   "labels": []},
    "evidence": [],
}

#: A project layer that gives technical-design a human check naming jed72.
HUMAN_DESIGN = {
    "schema": 1, "owner": "jed72",
    "checks": {"design-review": {
        "statement": "A person reviewed the design.", "kind": "human",
        "severity": "blocking", "on_skipped": "not-applicable",
        "approvers": ["jed72"]}},
    "artifacts": {"technical-design": {"set": {"checks": ["design-review"]}}},
}


def env(root):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "200", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "CLAUDE_PROJECT_DIR": str(root)}


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def run(root, *argv, terminal=False, cwd=None):
    """`(code, stdout, stderr)` of one CLI call. With `terminal`, standard
    input is a pseudo-terminal; otherwise it is empty, as in an agent session."""
    master = slave = None
    if terminal:
        master, slave = pty.openpty()
    try:
        r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd or root,
                           env=env(root), capture_output=True, text=True, timeout=300,
                           stdin=slave if terminal else subprocess.DEVNULL)
    finally:
        for fd in (master, slave):
            if fd is not None:
                os.close(fd)
    return r.returncode, r.stdout, r.stderr


def manifest_file(root, slug=SLUG):
    return Path(root) / ".compass" / "work" / slug / "manifest.yml"


def manifest(root, slug=SLUG):
    return yaml.safe_load(manifest_file(root, slug).read_text(encoding="utf-8"))


def write_manifest(root, body, slug=SLUG):
    manifest_file(root, slug).write_text(yaml.safe_dump(body, sort_keys=False),
                                         encoding="utf-8")


def edit(root, **changes):
    body = manifest(root)
    body.update(changes)
    write_manifest(root, body)
    return body


def entries(root):
    """The artifact entries of the issue, by kind."""
    return {a["kind"]: a for a in manifest(root).get("artifacts") or []}


def add_entry(root, kind, status="draft", path=True, **more):
    """Add a registry entry directly: a fixture for a kind the approach did
    not earn, such as `delivery-approach` on a regular issue."""
    body = manifest(root)
    entry = {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind,
             "status": status, "depth": "thorough", "reason": "fixture"}
    if path:
        entry["path"] = f"{DOCS}/{kind}.md"
    entry.update(more)
    body["artifacts"] = [a for a in body.get("artifacts") or []
                         if a.get("kind") != kind] + [entry]
    write_manifest(root, body)
    return entry


def project(tmp_path, compass_yml=None, assessment=None, evaluate=True):
    """A git repository holding one regular issue at generation 1, with the
    documents of the shipped regular approach written (not registered)."""
    root = Path(tmp_path) / "repo"
    root.mkdir(parents=True)
    git(root, "init", "-q")
    (root / "README.md").write_text("base\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    assert run(root, "init")[0] == 0
    task_dir = root / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    body = dict(MANIFEST)
    if assessment:
        body["assessment"] = dict(body["assessment"], **assessment)
    write_manifest(root, body)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    if compass_yml is not None:
        (root / "compass.yml").write_text(
            compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(compass_yml),
            encoding="utf-8")
    if evaluate:
        code, out, err = run(root, "approach", "evaluate", "--issue", SLUG, "--write")
        assert code == 0, out + err
    docs = root / DOCS
    docs.mkdir(parents=True)
    for kind in ("delivery-approach", "acceptance-criteria", "technical-design",
                 "distribution-map", "verification-report", "requirements-review",
                 "runbook"):
        (docs / f"{kind}.md").write_text(f"# {kind}\n\nFirst version.\n")
    return root


def register(root, kind, status="draft", *more):
    """`compass issue artifact set <kind> --status <s> --path <its file>`."""
    return run(root, "issue", "artifact", "set", kind, "--status", status,
               "--path", f"{DOCS}/{kind}.md", "--issue", SLUG, *more)


def approve(root, *extra, approver="jed72", role="maintainer", scope="review"):
    return run(root, "evidence", "approve", "--issue", SLUG, "--approver", approver,
               "--role", role, "--scope", scope, *extra, terminal=True)


def statuses(root):
    return {k: a.get("status") for k, a in entries(root).items()}


def add_evidence(root, evidence_id, kind="test-run"):
    """Write a small record under the issue's `evidence/` and register it.
    A `test-run` record is the JSON a green writes; any other type is a note."""
    folder = Path(root) / ".compass" / "work" / SLUG / "evidence"
    folder.mkdir(exist_ok=True)
    name = f"{evidence_id}.json" if kind == "test-run" else f"{evidence_id}.txt"
    (folder / name).write_text(
        '{"command": "pytest", "exit_code": 0, "passed": true}\n' if kind == "test-run"
        else "ok\n")
    code, out, err = run(root, "evidence", "add", evidence_id, "--type", kind, "--path",
                         f"evidence/{name}", "--issue", SLUG)
    assert code == 0, out + err
