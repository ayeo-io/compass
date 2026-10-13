"""The sessions that worked on an issue, and what they cost.

The pre-tool hook appends each session id it sees to the issue's
`usage.sessions`, once, with no Python process once an id is recorded. When
an issue lands, `compass ship-commit` reads those sessions' transcripts into a
`usage` block that holds only numbers, model names, times, session ids and
fixed reason words.

GitHub is off and a `gh` on PATH fails the test if anything calls it.
Transcripts are fixture files under a temporary `CLAUDE_CONFIG_DIR`.

Scenario ids: ARC-9 to ARC-13 and ARC-15, in the acceptance criteria of the
issue `autonomy-ratio-and-cost`. Each test name starts with its id.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(HERE))

import compass_pkg  # noqa: E402,F401 - puts the bundled PyYAML first
import yaml  # noqa: E402

import test_issue_dependencies as dbi  # noqa: E402

HOOK = ROOT / "hooks" / "pre-tool.sh"
FIXTURES = HERE / "fixtures" / "autonomy-ratio-and-cost"
LOCK = ".manifest.lock"


# --- the hook -------------------------------------------------------------------

def hook_call(root, tool, target, session=None, hook_path=HOOK, path=None, timeout=120,
              **extra):
    """Run the pre-tool hook on one tool call, as Claude Code does."""
    env = dbi.env_for(root, CLAUDE_PROJECT_DIR=str(root), **extra)
    if path is not None:
        env["PATH"] = path
    event = {"tool_name": tool, "tool_input": {"file_path": str(target)}}
    if session is not None:
        event["session_id"] = session
    return subprocess.run(["bash", str(hook_path)], input=json.dumps(event),
                          capture_output=True, text=True, env=env, timeout=timeout)


def document(root, slug="a"):
    return Path(root) / "docs" / "compass" / f"2026-10-01-{slug}" / "acceptance-criteria.md"


def hook_project(root, slugs=("a",), at="define"):
    """A project whose issues sit at `at`, the first named by the pointer."""
    project = dbi.Project(root)
    for slug in slugs:
        project.issue(slug, at)
    (project.root / ".compass" / "current-task").write_text(slugs[0] + "\n")
    return project


def folder_files(project, slug):
    """The issue folder's files, less the manifest lock, which is the issue's
    own lock file and not a temporary one."""
    folder = project.dir(slug)
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*")
                  if p.is_file() and p.name != LOCK)


def _masked(text, root):
    for form in {str(root), os.path.realpath(root)}:
        text = text.replace(form, "<root>")
    return text


def judgements(tmp_path, hook_path=HOOK):
    """The hook's exit code and refusal, for a document write and a code edit,
    with the session id `../x` and with none."""
    found = {}
    for session in ("../x", None):
        project = hook_project(Path(tmp_path) / ("bad" if session else "none"))
        before = project.bytes("a")
        for name, tool, target in (("document", "Write", document(project.root)),
                                   ("code", "Edit", dbi.code_file(project))):
            done = hook_call(project.root, tool, target, session, hook_path=hook_path)
            found[f"{name}, session {session}"] = {
                "exit": done.returncode, "stderr": _masked(done.stderr, project.root)}
        assert project.bytes("a") == before
        assert not (project.dir("a") / LOCK).exists()
    return found


#: Replaces the manifest's rename with a failure, in every Python process the
#: hook starts: the write itself fails after the temporary file is written.
FAILING_RENAME = """
import os
_real = os.replace


def _replace(src, dst, *args, **kwargs):
    if str(dst).endswith("manifest.yml"):
        raise OSError("planted: the manifest write fails")
    return _real(src, dst, *args, **kwargs)


os.replace = _replace
"""


# --- ARC-9 ------------------------------------------------------------------------

def test_arc_9_hook_records_each_session_once(tmp_path, monkeypatch):
    project = hook_project(tmp_path / "p", slugs=("a", "b"))
    root, doc = project.root, document(project.root)
    original, other = project.bytes("a"), project.bytes("b")
    assert "usage" not in project.manifest("a")

    done = hook_call(root, "Write", doc, "S1")
    assert done.returncode == 0, done
    assert project.manifest("a")["usage"] == {"sessions": ["S1"]}
    once = project.bytes("a")
    assert hook_call(root, "Write", doc, "S1").returncode == 0
    assert project.bytes("a") == once
    assert hook_call(root, "Edit", dbi.code_file(project), "S2").returncode == 2
    assert hook_call(root, "Write", doc, "S1").returncode == 0
    assert project.manifest("a")["usage"] == {"sessions": ["S1", "S2"]}
    assert project.bytes("a") == original + b"usage:\n  sessions:\n  - S1\n  - S2\n"
    assert project.bytes("b") == other

    # A bad session id, or none, is judged as the base commit judges it.
    captured = json.loads((FIXTURES / "base-hook-judgements.json").read_text())
    assert judgements(tmp_path / "judged") == captured

    # No issue resolved for the session: nothing is written.
    (root / ".compass" / "current-task").unlink()
    before = {slug: project.bytes(slug) for slug in ("a", "b")}
    assert hook_call(root, "Write", doc, "S9").returncode == 0
    assert {slug: project.bytes(slug) for slug in ("a", "b")} == before
    (root / ".compass" / "current-task").write_text("a\n")

    # Another process holds the manifest lock: the hook does not wait.
    before = project.bytes("a")
    with open(project.dir("a") / LOCK, "a") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        done = hook_call(root, "Write", doc, "S3", timeout=30)
        assert done.returncode == 0, done
        assert project.bytes("a") == before
        fcntl.flock(held, fcntl.LOCK_UN)
    assert hook_call(root, "Write", doc, "S3").returncode == 0
    assert project.manifest("a")["usage"]["sessions"] == ["S1", "S2", "S3"]

    # The manifest write fails: the edit is allowed and nothing changes.
    folder = project.dir("a")
    listed, before = folder_files(project, "a"), project.bytes("a")
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "sitecustomize.py").write_text(FAILING_RENAME)
    faults = (("read-only file", folder / "manifest.yml", 0o444, {}),
              ("read-only folder", folder, 0o555, {}),
              ("failing write", None, None, {"PYTHONPATH": str(planted)}))
    for name, target, mode, extra in faults:
        if target is not None:
            kept = target.stat().st_mode
            target.chmod(mode)
        try:
            done = hook_call(root, "Write", doc, "S6", **extra)
        finally:
            if target is not None:
                target.chmod(kept)
        assert done.returncode == 0, (name, done)
        assert project.bytes("a") == before, name
        assert folder_files(project, "a") == listed, name
    dbi.assert_no_gh_call(root)
    _concurrent_writer_is_merged(tmp_path / "merged", monkeypatch)


def _concurrent_writer_is_merged(tmp_path, monkeypatch):
    """Two writers at once both end up in the list: a writer that changes the
    file between the recorder's read and its rename is merged, not overwritten.
    In-process, because a shell test cannot stop the hook between the two."""
    from compass_pkg import session_lease, session_record
    # The recorder keeps its own copy of the lease limit to stay small.
    assert session_record.LEASE_HOURS == session_lease.LEASE_HOURS
    project = hook_project(tmp_path)
    folder = str(project.dir("a"))
    session_record.record(folder, "S1", "env")
    session_record.record(folder, "S2", "env")
    real_read = session_record._read
    calls = []

    def read_then_another_writer(path):
        data = real_read(path)
        if not calls:
            body = yaml.safe_load(data)
            body["usage"]["sessions"].append("S5")
            Path(path).write_text(yaml.safe_dump(body, sort_keys=False))
        calls.append(path)
        return data

    monkeypatch.setattr(session_record, "_read", read_then_another_writer)
    session_record.record(folder, "S4", "env")
    assert project.manifest("a")["usage"]["sessions"] == ["S1", "S2", "S5", "S4"]
    assert len(calls) == 2
