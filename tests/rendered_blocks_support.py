"""Shared scratch-project helpers for the rendered-blocks tests (issue
`documents-carry-judgement`).

Every project is a temporary git repository set up the way
`artifact_status_support.project` sets one up, and every CLI call runs with a
git identity in its environment and `user.useConfigOnly=true`, so a command
that commits fails the same way on a machine with no global git identity as it
does on a developer's. No test here reads or writes this checkout's own
`.compass/work` or `docs/compass` (DCJ-63).
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))

import artifact_status_support as base  # noqa: E402
from artifact_status_support import (CREATED, DOCS, ROOT, SLUG, edit, git, manifest,  # noqa: E402,F401
                                     manifest_file, project, register)

CLI = base.CLI
OPEN = "<!-- compass:render {kind} -->"
CLOSE = "<!-- /compass:render -->"
WORK = f".compass/work/{SLUG}"


def env(root):
    values = dict(base.env(root))
    values.update({
        "GIT_AUTHOR_NAME": "Test Author", "GIT_AUTHOR_EMAIL": "author@example.com",
        "GIT_COMMITTER_NAME": "Test Author", "GIT_COMMITTER_EMAIL": "author@example.com",
        "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "user.useConfigOnly",
        "GIT_CONFIG_VALUE_0": "true"})
    return values


def run(root, *argv, extra_env=None, timeout=300):
    """`(code, stdout, stderr)` of one CLI call, standard input empty."""
    values = env(root)
    values.update(extra_env or {})
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=root, env=values,
                          capture_output=True, text=True, timeout=timeout,
                          stdin=subprocess.DEVNULL)
    return done.returncode, done.stdout, done.stderr


def render(root, *extra):
    return run(root, "issue", "render", "--issue", SLUG, *extra)


def block(kind, body="stale"):
    """A block as a document holds it, LF line endings."""
    return f"{OPEN.format(kind=kind)}\n{body}\n{CLOSE}\n"


def doc_path(root, name):
    return Path(root) / DOCS / f"{name}.md"


def write_doc(root, name, text, *, register_it=True, binary=False):
    path = doc_path(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(text)
    else:
        path.write_bytes(text.encode("utf-8"))
    if register_it:
        # Write the registry entry by hand. `compass issue artifact set` is a command that
        # changes a record, so the render after it would fill the blocks this helper's
        # callers want to find as they wrote them.
        if name not in base.entries(root):
            base.add_entry(root, name, path=False)       # a kind the approach did not earn
        body = manifest(root)
        for entry in body["artifacts"]:
            if entry["kind"] == name:
                entry["path"] = f"{DOCS}/{name}.md"
        base.write_manifest(root, body)
    return path


def snapshot(root):
    """`{relative path: bytes}` of every file in the issue's documents folder and
    work folder, to prove a refusal changed nothing."""
    found = {}
    for top in (Path(root) / DOCS, Path(root) / WORK):
        for path in sorted(top.rglob("*")):
            # The lock files are empty and exist only to be locked.
            if path.is_file() and path.name not in (".render.lock", ".manifest.lock"):
                found[str(path.relative_to(root))] = path.read_bytes()
    return found


def add_records(root, **named):
    """Write evidence record files, each bound to a scenario: a record named
    for a scenario writes its file in the issue's evidence folder."""
    folder = Path(root) / WORK / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    for name, scenario in named.items():
        (folder / f"{name}.json").write_text(
            json.dumps({"scenario": scenario, "passed": name.startswith("green")}),
            encoding="utf-8")


def rich_issue(tmp_path, compass_yml=None):
    """A regular issue whose manifest holds every record the eight blocks read."""
    root = project(tmp_path, compass_yml=compass_yml)
    # The render after `approach evaluate --write` wrote the issue page; the engine tests start
    # from an issue that has none, so that the first render is the one they watch.
    (Path(root) / DOCS / "README.md").unlink(missing_ok=True)
    body = manifest(root)
    body["scenarios"] = [
        {"id": "TRC-1", "title": "First scenario", "intent": "INT-1",
         "tests": ["tests/test_a.py::test_one"]},
        {"id": "TRC-2", "title": "Second scenario", "intent": "INT-1",
         "tests": ["tests/test_a.py::test_two"]},
        {"id": "TRC-3", "title": "Third scenario", "intent": "INT-1", "tests": []}]
    body["failure_modes_descoped"] = [
        {"mode": "a disk that fills mid-write", "reason": "no portable way to force it",
         "recorded": "2026-10-10"}]
    body["gates"] = [{"id": f"verify.g{n}", "status": "pass" if n < 7 else "pending",
                      "evidence": [f"EV-{n}"] if n < 7 else []} for n in range(9)]
    body["evidence"] = [
        {"id": "EV-A", "type": "test-run", "path": "evidence/green-TRC-1.json"},
        {"id": "EV-B", "type": "command-output", "path": f"{DOCS}/technical-design.md"},
        {"id": "EV-C", "type": "manual-review", "path": "evidence/review.yml"}]
    body["follow_ups"] = [
        {"id": "FU-1", "status": "outstanding", "summary": "Add the second thing",
         "target_task": "other-issue"},
        {"id": "FU-2", "status": "resolved", "summary": "Fixed the first thing"}]
    body["decisions_taken"] = [
        {"id": "Q1", "question": "Which folder?", "resolution": "The docs folder",
         "by": "spec-author", "stage": "refine", "status": "confirmed"},
        {"id": "Q2", "question": "Which flag?", "resolution": "Neither",
         "by": "planner", "stage": "plan", "status": "open"}]
    body["reassessments"] = [
        {"from_route": "regular", "to_route": "full", "kind": "judgment",
         "changed": {}, "reason": "The change reached more modules", "date": "2026-10-10"}]
    (Path(root) / WORK).mkdir(parents=True, exist_ok=True)
    manifest_file(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    add_records(root, **{"red-TRC-1": "TRC-1", "green-TRC-1": "TRC-1", "red-TRC-2": "TRC-2"})
    return root


def inproc(root, monkeypatch, *, all_issues=False, dry_run=False, issue=SLUG):
    """Run `compass issue render` in this process from `root`; `(code, out, err)`.
    A refusal is a `CompassError`, which the entry point turns into exit 2."""
    from compass_pkg import render_cmd
    from compass_pkg.core import CompassError

    monkeypatch.chdir(root)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    args = argparse.Namespace(task=issue, all=all_issues, dry_run=dry_run, json=False,
                              _mode="plain")
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = render_cmd.cmd_issue_render(args) or 0
        except CompassError as exc:
            err.write(f"compass: {exc}\n")
            code = 2
    return code, out.getvalue(), err.getvalue()


def tracked_digest(*folders):
    """One digest of every file under the folders, for DCJ-63."""
    import hashlib
    h = hashlib.sha256()
    for folder in folders:
        for path in sorted(Path(folder).rglob("*")):
            if path.is_file():
                h.update(str(path.relative_to(folder)).encode())
                h.update(path.read_bytes())
    return h.hexdigest()
