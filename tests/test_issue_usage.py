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


# --- ARC-10 -----------------------------------------------------------------------

#: python3 processes the base commit's hook (401953ec) starts for a
#: production-code edit on an issue at implement with a red on record, named
#: by the pointer, in a project of 40 issues: with a session id, the session
#: lease reader, the delivery-approach reader, the acceptance-criteria reader
#: and the red-record reader; with none, the last three. A Write to the
#: issue's acceptance-criteria.md started none either way.
BASE_PYTHON3_WITH_SESSION = 4
BASE_PYTHON3_WITHOUT_SESSION = 3

#: The recorded-id call over the call with no session id, and the new-id
#: call's added time over a reference python3 process that imports compass_pkg
#: and loads one manifest. Measured on a development machine (Apple silicon,
#: Python 3.11.9), 2026-10-13, with other test suites running, in two runs:
#: no session 0.367s and 0.331s, recorded id 0.478s and 0.423s, new id 0.569s
#: and 0.479s, reference 0.067s and 0.061s; recorded over none 1.30 and 1.28;
#: new-id marginal 1.36 and 0.93 references. The recorded id adds the base
#: commit's lease reader and one `grep` to the no-session call, so its ratio
#: sits near 4 processes over 3; the new id adds one python3 process, which
#: the reference also measures. Each limit leaves about 50% for a runner whose
#: bash and process start cost more; a second added process fails the second.
MAX_RECORDED_OVER_NO_SESSION = 2.0
MAX_NEW_ID_MARGINAL_OVER_REFERENCE = 2.5


def _budget_project(root):
    project = dbi.Project(root)
    for n in range(39):
        project.issue(f"other-{n:02d}", "implement")
    project.issue("a", "implement", marker=True)
    (project.root / ".compass" / "current-task").write_text("a\n")
    return project


def _counted(project, session):
    """The python3 processes the hook starts, and the manifests its Python
    processes open, for one code edit."""
    root = project.root
    shim = root / ".py-shim"
    shim.mkdir(exist_ok=True)
    log = root / ".python3-calls"
    log.unlink(missing_ok=True)
    (shim / "python3").write_text(dbi.PYTHON_SHIM.format(log=log, real=sys.executable))
    (shim / "python3").chmod(0o755)
    audit = root / ".audit.log"
    audit.unlink(missing_ok=True)
    done = hook_call(root, "Edit", dbi.code_file(project), session,
                     path=f"{shim}:{dbi.env_for(root)['PATH']}",
                     PYTHONPATH=str(dbi._audit_dir(root)), DBI_AUDIT_LOG=str(audit))
    assert done.returncode == 0, done
    count = len(log.read_text().splitlines()) if log.exists() else 0
    opened = {os.path.basename(os.path.dirname(p)) for p in dbi._events(audit, "open")
              if p.endswith("/manifest.yml")}
    return count, opened


@pytest.mark.serial
def test_arc_10_hook_budget(tmp_path):
    import statistics
    import time
    project = _budget_project(tmp_path / "p")
    clean = project.bytes("a")
    assert _counted(project, None)[0] == BASE_PYTHON3_WITHOUT_SESSION

    new_count, opened = _counted(project, "S-new")
    assert project.manifest("a")["usage"]["sessions"] == ["S-new"]
    assert new_count <= BASE_PYTHON3_WITH_SESSION + 1, new_count
    assert opened <= {"a"}, opened
    recorded_count, opened = _counted(project, "S-new")
    assert recorded_count <= BASE_PYTHON3_WITH_SESSION, recorded_count
    assert opened <= {"a"}, opened

    reference = [sys.executable, "-c",
                 "import sys; sys.path.insert(0, sys.argv[1]); import compass_pkg; "
                 "from compass_pkg.core import load_manifest; load_manifest(sys.argv[2])",
                 str(ROOT / "cli"), str(project.dir("other-00"))]
    recorded = project.bytes("a")
    times = {"recorded": [], "new": [], "none": [], "reference": []}
    for round_ in range(12):
        for key, session in (("recorded", "S-new"), ("new", f"S-{round_}"), ("none", None)):
            start = time.perf_counter()
            done = hook_call(project.root, "Edit", dbi.code_file(project), session)
            elapsed = time.perf_counter() - start
            assert done.returncode == 0, done
            if round_:
                times[key].append(elapsed)
        (project.dir("a") / "manifest.yml").write_bytes(recorded)
        start = time.perf_counter()
        subprocess.run(reference, check=True, capture_output=True, timeout=60)
        if round_:
            times["reference"].append(time.perf_counter() - start)
    median = {k: statistics.median(v) for k, v in times.items()}
    ratio = median["recorded"] / median["none"]
    marginal = (median["new"] - median["recorded"]) / median["reference"]
    print("ARC-10 hook medians: no session %.4fs, recorded id %.4fs, new id %.4fs; "
          "reference %.4fs; recorded over none %.2f (limit %.1f); new-id marginal over "
          "reference %.2f (limit %.1f)"
          % (median["none"], median["recorded"], median["new"], median["reference"],
             ratio, MAX_RECORDED_OVER_NO_SESSION, marginal,
             MAX_NEW_ID_MARGINAL_OVER_REFERENCE))
    assert ratio < MAX_RECORDED_OVER_NO_SESSION, median
    assert marginal < MAX_NEW_ID_MARGINAL_OVER_REFERENCE, median
    assert clean != recorded
