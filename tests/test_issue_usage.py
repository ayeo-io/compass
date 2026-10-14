"""The sessions that worked on an issue, and what they cost.

The pre-tool hook appends each session id it sees to the issue's
`usage.sessions`, once, with no Python process once an id is recorded. When
an issue lands, `compass ship-commit` reads those sessions' transcripts into a
`usage` block that holds only numbers, model names, times, session ids and
fixed reason words.

GitHub is off and a `gh` on PATH fails the test if anything calls it.
Transcripts are fixture files under a temporary `CLAUDE_CONFIG_DIR`.

Scenario ids: ARC-9 to ARC-13, ARC-15, ARC-25 and ARC-26, in the acceptance criteria of the
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
    from compass_pkg import session_record
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
#: new-id marginal 1.36 and 0.93 references. A third run, after the recorder
#: came to import compass_pkg.core: 0.267s, 0.340s, 0.412s and 0.057s; 1.27
#: and 1.28. The recorded id adds the base
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


# --- usage at ship: fixtures --------------------------------------------------------

import shutil  # noqa: E402

import test_checkpoint_outcomes as co  # noqa: E402

FIXED_CLOCK = HERE / "fixed_clock.py"
CLI_DIR = ROOT / "cli"
S1, S2 = "sess-one-0001", "sess-two-0002"

#: Dollars per million tokens of each kind, for both fixture models.
PRICES = {"model-a": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
          "model-b": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.1}}


def at(root, when, *argv, cli_dir=CLI_DIR, **extra):
    """One CLI call with the clock held at `when`."""
    cmd = [sys.executable, str(FIXED_CLOCK), "--cli", str(cli_dir), "--at", when, "--", *argv]
    return subprocess.run(cmd, cwd=str(root), env=co.env(root, **extra), capture_output=True,
                          text=True, timeout=300, stdin=subprocess.DEVNULL)


def claude_home(root, which):
    """The fixture transcripts, copied into the project's temporary config folder."""
    shutil.copytree(FIXTURES / "transcripts" / which, Path(root) / ".claude-config",
                    dirs_exist_ok=True)
    return Path(root) / ".claude-config"


def config_state(home):
    """Every file under the config folder, with its bytes and modification time."""
    return {str(p.relative_to(home)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(Path(home).rglob("*")) if p.is_file()}


def quick_fix_usage(tmp_path, cli_dir=CLI_DIR, hook_sessions=False):
    """Start and finish a quick fix in the first fixture session under a fixed clock, and
    return its `usage` block and the copy its landing commit holds."""
    root = Path(tmp_path) / "repo"
    root.mkdir(parents=True)
    co.git(root, "init", "-q")
    (root / ".gitignore").write_text(".test-bin/\n.home/\n.gh-calls\n.claude-config/\n")
    (root / "README.md").write_text("base\n")
    co.git(root, "add", "-A")
    co.git(root, "commit", "-q", "-m", "base")
    assert at(root, "2026-10-13T09:00:00Z", "init", cli_dir=cli_dir).returncode == 0
    (root / "compass.yml").write_text(yaml.safe_dump(
        {"schema": 1, "owner": "jed72", "autonomy": "balanced", "prices": PRICES}))
    (root / "data").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi, %s!")
    (root / "tests").mkdir()
    (root / "tests" / "test_greeting.py").write_text(co.GREETING_TEST)
    co.git(root, "add", "-A")
    co.git(root, "commit", "-q", "-m", "greeting")
    claude_home(root, "quick-fix")
    slug = "fix-greeting"
    done = at(root, "2026-10-13T10:00:00Z", "quick-fix", "start", slug,
              "--risk", "trivial - a one-line text change",
              "--familiarity", "brownfield-mapped - the file and its test exist",
              "--size", "atomic - one file, one obvious change",
              "--intent", "The greeting says hello.",
              "--scenario", "Given the greeting, when it is read, then it says hello.",
              "--scenario-id", "QF-1", "--test", "tests/test_greeting.py::test_greeting_says_hello",
              cli_dir=cli_dir, CLAUDE_CODE_SESSION_ID=S1)
    assert done.returncode == 0, done
    folder = root / ".compass" / "work" / slug
    if hook_sessions:
        from compass_pkg import session_record
        session_record.record(str(folder), S1, "env")
        assert yaml.safe_load((folder / "manifest.yml").read_text())["usage"]["sessions"] == [S1]
    done = at(root, "2026-10-13T10:05:00Z", "tdd-red", "--issue", slug, "--scenario", "QF-1",
              *co.GREET_CMD, cli_dir=cli_dir, CLAUDE_CODE_SESSION_ID=S1)
    assert done.returncode == 0, done
    (root / "data" / "greeting.txt").write_text("Hello, %s!")
    done = at(root, "2026-10-13T10:30:00Z", "quick-fix", "finish", "--issue", slug,
              "-m", "Fix it", *co.GREET_CMD, cli_dir=cli_dir, CLAUDE_CODE_SESSION_ID=S1)
    assert done.returncode == 0, done
    landed = yaml.safe_load((folder / "manifest.yml").read_text())
    committed = yaml.safe_load(co.git(root, "show", f"{landed['land_commit']}:"
                                      f".compass/work/{slug}/manifest.yml"))
    co.assert_no_gh_call(root)
    return landed["usage"], committed["usage"]


# --- ARC-13 -----------------------------------------------------------------------

def test_arc_13_quick_fix_usage_block_unchanged(tmp_path):
    base = json.loads((FIXTURES / "base-quick-fix-usage.json").read_text())
    usage, committed = quick_fix_usage(tmp_path / "with-hook", hook_sessions=True)
    assert usage == dict(base, sessions=[S1]), usage
    assert committed == usage
    usage, committed = quick_fix_usage(tmp_path / "without-hook")
    assert usage == base and committed == base, usage


# --- ARC-11 -----------------------------------------------------------------------

AUTONOMOUS = {"schema": 1, "owner": "jed72", "autonomy": "autonomous", "prices": PRICES}
COUNTS = ("input", "output", "cache_write", "cache_read")


def regular_project(tmp_path, sessions=(S1, S2), compass_yml=None, transcripts="regular"):
    """A regular issue ready to land at 12:00, whose define ends at 09:30, plan
    at 10:00 and implement at 11:00 (its green), with the fixture transcripts."""
    root = co.project(tmp_path, compass_yml=compass_yml or AUTONOMOUS)
    co.register(root, "acceptance-criteria", "approved")
    for kind in co.REGULAR_DOCUMENTS:
        co.register(root, kind, "approved")
    body = co.manifest(root)
    body["checkpoint_outcomes"] = [
        {"stage": "define", "outcome": "skipped", "by": "spec-author", "at": "2026-10-13T09:30:00Z"},
        {"stage": "plan", "outcome": "skipped", "by": "planner", "at": "2026-10-13T10:00:00Z"}]
    for gate in body["gates"]:
        gate["status"] = "pass"
    body["changed_files"] = [{"path": "src/new.py", "scenarios": ["S-1"]}]
    if sessions:
        body["usage"] = {"sessions": list(sessions)}
    co.write_manifest(root, body)
    (root / "src").mkdir(exist_ok=True)
    (root / "src" / "new.py").write_text("y = 1\n")
    done = at(root, "2026-10-13T11:00:00Z", "tdd-green", "--issue", co.SLUG, "--",
              sys.executable, "-c", "pass")
    assert done.returncode == 0, done
    co.git(root, "add", "src/new.py")
    home = claude_home(root, transcripts) if transcripts else None
    return root, home


def ship_at(root, when="2026-10-13T12:00:00Z", **extra):
    return at(root, when, "ship-commit", "-m", "Ship it", "--issue", co.SLUG, **extra)


def fixture_requests():
    """Every request of the regular fixture transcripts, one per request id, with
    the highest value of each count across its lines, read here by hand."""
    found = {}
    folder = FIXTURES / "transcripts" / "regular" / "projects" / "-fixture-project"
    for path in sorted(folder.rglob("*.jsonl")):
        for raw in path.read_text().splitlines():
            try:
                line = json.loads(raw)
            except ValueError:
                continue
            if line.get("type") != "assistant":
                continue
            usage = line["message"]["usage"]
            counts = {"input": usage["input_tokens"], "output": usage["output_tokens"],
                      "cache_write": usage["cache_creation_input_tokens"],
                      "cache_read": usage["cache_read_input_tokens"]}
            entry = found.setdefault(line["requestId"], {
                "at": line["timestamp"], "model": line["message"]["model"],
                "subagent": path.parent.name == "subagents", **counts})
            for name, value in counts.items():
                entry[name] = max(entry[name], value)
    return found


def by_hand(requests, ids):
    chosen = [requests[i] for i in ids]
    totals = {"requests": len(chosen), "subagent_requests": sum(r["subagent"] for r in chosen)}
    for name in COUNTS:
        totals[name] = sum(r[name] for r in chosen)
    totals["cost_usd"] = round(sum(r[name] * PRICES[r["model"]][name] / 1_000_000
                                   for r in chosen for name in COUNTS), 6)
    return totals


def test_arc_11_ship_records_usage_on_a_regular_issue(tmp_path):
    root, home = regular_project(tmp_path)
    before = config_state(home)
    done = ship_at(root)
    assert done.returncode == 0, done
    assert "usage not recorded" not in done.stdout + done.stderr
    usage = co.manifest(root)["usage"]
    requests = fixture_requests()
    assert usage["sessions"] == [S1, S2] and usage["source"] == "claude-code"
    assert usage["skipped_lines"] == 1
    # req_t3 is after the landing at 12:00, so it is outside the span.
    in_span = ["req_r1", "req_r2", "req_t1", "req_r3", "req_rs", "req_t2", "req_r4"]
    assert usage["total"] == by_hand(requests, in_span)
    assert usage["unattributed"] == by_hand(requests, ["req_r4"])
    windows = {"define": ["req_r1"], "plan": ["req_r2", "req_t1"],
               "implement": ["req_r3", "req_rs", "req_t2"]}
    stages = co.manifest(root)["stages"]
    ran = [s for s, weight in stages.items() if weight not in ("skipped", "collapsed", "none")]
    assert list(usage["stages"]) == ran
    for stage in ran:
        if stage in windows:
            assert usage["stages"][stage] == by_hand(requests, windows[stage]), stage
        else:
            assert usage["stages"][stage] == {"measured": False, "reason": "no-window"}, stage
    measured = [b for b in usage["stages"].values() if "requests" in b] + [usage["unattributed"]]
    for name in ("requests", "subagent_requests", *COUNTS):
        assert sum(b[name] for b in measured) == usage["total"][name], name
    assert usage["total"]["requests"] == 7
    assert config_state(home) == before
    co.assert_no_gh_call(root)


# --- ARC-12 -----------------------------------------------------------------------

def _not_recorded(root, done, reason, sessions):
    assert done.returncode == 0, done
    landed = co.manifest(root)
    assert landed.get("land_timestamp"), done
    lines = [line for line in done.stdout.splitlines() if "usage not recorded" in line]
    assert lines == [f"compass ship-commit: usage not recorded ({reason})."], done.stdout
    usage = landed["usage"]
    assert usage["recorded"] is False and usage["reason"] == reason, usage
    assert usage.get("sessions") == sessions, usage
    assert not set(usage) & {"total", "unattributed", "stages", "requests", *COUNTS}, usage


def test_arc_12_usage_faults_never_stop_the_landing(tmp_path, monkeypatch):
    transcripts = FIXTURES / "transcripts" / "regular" / "projects" / "-fixture-project"

    root, _ = regular_project(tmp_path / "none", sessions=None)
    _not_recorded(root, ship_at(root), "not-claude-code", None)

    # An issue assessed before outcomes were recorded lands exactly as the base
    # commit lands it: no usage line, and no usage block is written.
    root, _ = regular_project(tmp_path / "older")
    body = co.manifest(root)
    body.pop("checkpoint_outcomes")
    co.write_manifest(root, body)
    done = ship_at(root)
    assert done.returncode == 0 and co.manifest(root).get("land_timestamp"), done
    assert "usage" not in done.stdout + done.stderr, done
    assert co.manifest(root)["usage"] == {"sessions": [S1, S2]}

    root, home = regular_project(tmp_path / "missing")
    (home / "projects" / "-fixture-project" / f"{S2}.jsonl").unlink()
    _not_recorded(root, ship_at(root), "no-transcript", [S1, S2])

    root, home = regular_project(tmp_path / "unreadable")
    locked = home / "projects" / "-fixture-project" / f"{S1}.jsonl"
    locked.chmod(0)
    try:
        _not_recorded(root, ship_at(root), "unreadable", [S1, S2])
    finally:
        locked.chmod(0o644)

    root, _ = regular_project(tmp_path / "unpriced", compass_yml=dict(
        AUTONOMOUS, prices={"model-a": PRICES["model-a"]}))
    done = ship_at(root)
    assert done.returncode == 0 and "usage not recorded" not in done.stdout, done
    usage = co.manifest(root)["usage"]
    assert usage["total"]["requests"] == 7 and usage["total"]["cost_usd"] is None, usage
    assert usage["stages"]["define"]["cost_usd"] is not None, usage
    assert usage["stages"]["implement"]["cost_usd"] is None, usage
    assert usage["stages"]["implement"]["input"] == 30 + 50 + 70, usage

    # Above the read limit nothing is read: the transcript cannot be opened,
    # and the reason is too-large, not unreadable. In-process, so the limit can
    # be lowered from 1 GiB to 1 KiB without a setting.
    import argparse
    from compass_pkg import manifest as manifest_module, session_usage
    root, home = regular_project(tmp_path / "large")
    assert sum(p.stat().st_size for p in transcripts.rglob("*.jsonl")) > 1024
    locked = home / "projects" / "-fixture-project" / f"{S1}.jsonl"
    locked.chmod(0)
    monkeypatch.setattr(session_usage, "USAGE_READ_LIMIT_BYTES", 1024)
    for name, value in co.env(root).items():
        if name.startswith("GIT_") or name == "CLAUDE_CONFIG_DIR":
            monkeypatch.setenv(name, value)
    for name in ("CLAUDE_CODE_SESSION_ID", "COMPASS_ISSUE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(root)
    import contextlib
    import io
    printed = io.StringIO()
    try:
        with contextlib.redirect_stdout(printed):
            code = manifest_module.cmd_land_commit(argparse.Namespace(
                message="Ship it", message_file=None, task=co.SLUG, files=[]))
    finally:
        locked.chmod(0o644)
    _not_recorded(root, subprocess.CompletedProcess([], code, printed.getvalue(), ""),
                  "too-large", [S1, S2])


# --- ARC-15 -----------------------------------------------------------------------

CANARY = "CANARY-7f3a"
MODELS = ("model-a", "model-b")


def canary_transcripts(home):
    """Transcripts for both fixture sessions that hold the canary in a user prompt, an
    assistant text, a tool input, a tool result, an error message and their
    own folder's name."""
    folder = Path(home) / "projects" / f"-work-{CANARY}"
    def usage(n):
        return {"input_tokens": n, "output_tokens": n, "cache_creation_input_tokens": n,
                "cache_read_input_tokens": n}
    for session, base in ((S1, "2026-10-13T09"), (S2, "2026-10-13T10")):
        lines = [
            {"type": "user", "timestamp": f"{base}:05:00Z", "sessionId": session,
             "cwd": f"/home/{CANARY}", "message": {"role": "user", "content": f"Fix {CANARY}."}},
            {"type": "assistant", "timestamp": f"{base}:10:00Z", "requestId": f"{session}-a",
             "sessionId": session, "message": {"id": f"{session}-ma", "model": "model-a",
                                               "content": [{"type": "text", "text": CANARY}],
                                               "usage": usage(10)}},
            {"type": "assistant", "timestamp": f"{base}:20:00Z", "requestId": f"{session}-b",
             "sessionId": session, "message": {"id": f"{session}-mb", "model": "model-b",
                                               "content": [{"type": "tool_use", "id": "toolu_1",
                                                            "name": "Bash",
                                                            "input": {"command": f"echo {CANARY}"}}],
                                               "usage": usage(20)}},
            {"type": "user", "timestamp": f"{base}:21:00Z", "sessionId": session,
             "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_1",
                                                      "is_error": True,
                                                      "content": f"Error: {CANARY} failed"}]}},
            {"type": "system", "timestamp": f"{base}:22:00Z", "sessionId": session,
             "subtype": "api_error", "error": {"message": f"{CANARY} overloaded"}},
        ]
        path = folder / f"{session}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return folder


def _leaves(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _leaves(value, path + (key,))
    elif isinstance(node, list):
        for value in node:
            yield from _leaves(value, path)
    else:
        yield path, node


def _is_time(value):
    from compass_pkg import session_usage
    return session_usage._parse_time(value) is not None


def test_arc_15_no_transcript_text_is_stored(tmp_path):
    from compass_pkg import session_usage
    bare = tmp_path / "record.git"
    co.git(tmp_path, "init", "-q", "--bare", str(bare))
    root, _ = regular_project(tmp_path / "work", transcripts=None, compass_yml=dict(
        AUTONOMOUS, record={"remote": str(bare), "paths": [".compass/work", "docs/compass"]}))
    home = root / ".claude-config"
    transcripts = canary_transcripts(home)

    outputs = [ship_at(root)]
    assert outputs[0].returncode == 0, outputs[0]
    for argv in (("retro", "--impact"), ("retro", "--impact", "--json"),
                 ("issue", "diagnose", "--issue", co.SLUG)):
        outputs.append(co.run(root, *argv))
    assert outputs[1].returncode == 0 and outputs[3].returncode == 0, outputs

    clone = tmp_path / "record-copy"
    co.git(tmp_path, "clone", "-q", str(bare), str(clone))
    synced = yaml.safe_load((clone / ".compass" / "work" / co.SLUG / "manifest.yml").read_text())
    assert synced["usage"] == co.manifest(root)["usage"]
    history = co.git(clone, "log", "--all", "-p", "--format=%H %s")
    texts = [o.stdout + o.stderr for o in outputs] + [history]
    for top in (root / ".compass", root / "docs" / "compass", clone):
        for path in top.rglob("*"):
            if path.is_file() and ".git" not in path.relative_to(top).parts:
                texts.append(str(path.relative_to(top)) + "\n"
                             + path.read_bytes().decode("utf-8", "replace"))
    paths = {str(home), os.path.realpath(home), str(transcripts), "-work-", ".jsonl"}
    for text in texts:
        assert CANARY not in text, text[:2000]
        for found in paths:
            assert found not in text, (found, text[:2000])

    usage = co.manifest(root)["usage"]
    assert usage["total"]["requests"] == 4, usage
    sessions = set(usage["sessions"])
    for where, leaf in _leaves(usage):
        assert (leaf is None or isinstance(leaf, (bool, int, float))
                or leaf in MODELS or leaf in sessions or leaf in session_usage.REASONS
                or leaf == session_usage.SOURCE or (isinstance(leaf, str) and _is_time(leaf))), \
            (where, leaf)
    co.assert_no_gh_call(root)


# --- ARC-25 -----------------------------------------------------------------------

def _session_table(compass_dir, session, issue, hours_ago):
    """The session table `session_lease` keeps, with one entry for `session`."""
    from datetime import datetime, timedelta, timezone
    at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    (Path(compass_dir) / "sessions.json").write_text(json.dumps(
        {session: {"issue": issue, "at": at.isoformat(timespec="seconds")}}))


def test_arc_25_moved_pointer_records_nothing(tmp_path):
    """A session whose fresh entry in the session table names another issue
    has had the pointer moved by another session: its id is not recorded on
    the issue the pointer names now. A stale entry moves nothing."""
    from compass_pkg import session_lease, session_record
    project = hook_project(tmp_path, slugs=("a", "b"))
    compass_dir, folder = project.root / ".compass", str(project.dir("a"))

    _session_table(compass_dir, "S1", "b", hours_ago=1)
    before = project.bytes("a")
    session_record.record(folder, "S1", "pointer")
    assert project.bytes("a") == before
    # COMPASS_ISSUE names the issue outright, so the table is not read.
    session_record.record(folder, "S1", "env")
    assert project.manifest("a")["usage"] == {"sessions": ["S1"]}

    _session_table(compass_dir, "S2", "b", hours_ago=session_lease.LEASE_HOURS + 1)
    session_record.record(folder, "S2", "pointer")
    assert project.manifest("a")["usage"] == {"sessions": ["S1", "S2"]}
    # An entry naming this issue is not a move.
    _session_table(compass_dir, "S3", "a", hours_ago=1)
    session_record.record(folder, "S3", "pointer")
    assert project.manifest("a")["usage"] == {"sessions": ["S1", "S2", "S3"]}


# --- ARC-26 -----------------------------------------------------------------------

def landed_issue_before(root):
    """Issue "earlier" records the first fixture session and landed before the
    issue under test started: its define ends at 08:00, its plan at 08:30 and
    it landed at 08:45, before the session's first request at 09:05."""
    folder = Path(root) / ".compass" / "work" / "earlier"
    folder.mkdir(parents=True)
    body = {"task": "earlier", "approach": "regular", "usage": {"sessions": [S1]},
            "land_timestamp": "2026-10-13T08:45:00Z",
            "checkpoint_outcomes": [
                {"stage": "define", "outcome": "skipped", "by": "spec-author",
                 "at": "2026-10-13T08:00:00Z"},
                {"stage": "plan", "outcome": "skipped", "by": "planner",
                 "at": "2026-10-13T08:30:00Z"}]}
    (folder / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))


def test_arc_26_earlier_work_is_not_shared(tmp_path):
    """Work on another issue that ended before counting starts overlaps no
    window: the first window starts where counting starts, so nothing is
    marked shared and every count matches the issue worked alone."""
    alone, _ = regular_project(tmp_path / "alone")
    assert ship_at(alone).returncode == 0
    expected = co.manifest(alone)["usage"]

    root, _ = regular_project(tmp_path / "after")
    landed_issue_before(root)
    done = ship_at(root)
    assert done.returncode == 0, done
    usage = co.manifest(root)["usage"]
    blocks = [usage["total"], usage["unattributed"], *usage["stages"].values()]
    assert not any(b.get("shared") for b in blocks), usage
    assert usage["stages"] == expected["stages"], usage["stages"]
    assert usage["total"] == expected["total"]
    co.assert_no_gh_call(root)


def test_arc_31_other_manifests_are_not_read_without_a_session(tmp_path, monkeypatch):
    """An issue with no session lands without reading any other issue's manifest."""
    from compass_pkg import issue_usage
    work = tmp_path / "work"
    for slug in ("mine", "other-1", "other-2"):
        (work / slug).mkdir(parents=True)
        (work / slug / "manifest.yml").write_text("issue: x\n", encoding="utf-8")
    task_dir = work / "mine"
    reads = []
    real = issue_usage.load_yaml
    monkeypatch.setattr(issue_usage, "load_yaml", lambda p: reads.append(p) or real(p))
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    task = {"delivery_approach": "regular", "checkpoint_outcomes": []}
    line = issue_usage.record_at_ship(task, str(task_dir), "2026-10-13T12:00:00Z")
    assert line == "compass ship-commit: usage not recorded (not-claude-code)."
    assert reads == [], reads
