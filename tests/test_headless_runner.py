"""`compass run` runs one stage of one issue with nobody in the session.

Each cycle is a fresh `claude -p` session; between cycles the runner reads
only the manifest and the evidence on disk. It stops at a cycle ceiling, a
minute ceiling, a stop file, or when cycles stop making progress, records
why, and never lands the issue. Error text is redacted before it reaches a
record.

Every test here runs a stub `claude` (`_STUB` below), never the real one:
each call writes a marker, and `_calls` fails a test whose session count
does not match the markers, so a run that reached any other `claude`
fails.

Scenario ids: HR-A to HR-I, in the acceptance criteria of the issue
`headless-runner` (GitHub issue #302).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "multi"
CREATED = "2026-10-03"
DOCS = f"docs/compass/{CREATED}-{SLUG}"
TOKEN = "sk-ant-api03-FAKEfakeFAKEfake0123456789abcdef"
ENV_SECRET = "hunter2-not-a-real-service-token"

# The stub `claude`. It reads its plan from STUB_PLAN: one action per call,
# the last repeated. It logs each call's arguments and writes one marker per
# call, so a test can tell its own stub ran and nothing else did.
_STUB = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
log = Path(os.environ["STUB_LOG"])
calls = log.read_text().splitlines() if log.exists() else []
n = len(calls) + 1
with log.open("a") as fh:
    fh.write(json.dumps(sys.argv[1:]) + "\n")
Path(os.environ["STUB_MARKERS"], f"call-{n}").write_text("stub\n")
plan = json.loads(os.environ["STUB_PLAN"])
action = plan[min(n, len(plan)) - 1]
task = Path(os.environ["STUB_TASK"])
manifest = task / "manifest.yml"
if action == "touch":
    (task / "evidence").mkdir(exist_ok=True)
    (task / "evidence" / f"stub-{n}.txt").write_text("progress\n")
elif action == "pass_gates":
    manifest.write_text(manifest.read_text().replace("status: pending", "status: pass"))
elif action == "land":
    manifest.write_text(manifest.read_text().replace("status: active", "status: landed"))
elif action == "stop_file":
    (task / "evidence").mkdir(exist_ok=True)
    (task / "evidence" / f"stub-{n}.txt").write_text("progress\n")
    Path(os.environ["STUB_STOP"]).write_text("stop\n")
elif action == "leak":
    sys.stderr.write("Error: request refused for key " + os.environ["STUB_TOKEN"]
                     + " (service token " + os.environ["MY_SERVICE_TOKEN"] + ")\n")
    print(json.dumps({"type": "result", "subtype": "error", "is_error": True,
                      "session_id": f"s{n}", "total_cost_usd": 0.0}))
    sys.exit(1)
elif action == "green":
    (task / "evidence").mkdir(exist_ok=True)
    (task / "evidence" / "green-X-1.json").write_text("{}\n")
elif action == "corrupt":
    manifest.write_text("issue: [unclosed\n")
elif action == "long_leak":
    # The token first, then enough text that keeping only the last 2,000
    # characters would cut the token after its recognisable prefix.
    sys.stderr.write(os.environ["STUB_TOKEN"] + " " + "x" * 1960 + "\n")
    sys.exit(1)
elif action == "corrupt_sleep":
    manifest.write_text("issue: [unclosed\n")
    time.sleep(30)
elif action == "spawn_sleep":
    import subprocess
    child = subprocess.Popen(["sleep", "30"])
    Path(os.environ["STUB_PIDFILE"]).write_text(str(child.pid))
    time.sleep(30)
elif action == "rm_lock":
    (task / "run.lock").unlink()
elif action == "done_bad_runs":
    text = manifest.read_text().replace("status: pending", "status: pass")
    manifest.write_text(text + "runs: oops\n")
elif action == "bad_runs":
    manifest.write_text(manifest.read_text() + "runs: oops\n")
elif action == "sleep":
    Path(os.environ["STUB_PIDFILE"]).write_text(str(os.getpid()))
    time.sleep(30)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "session_id": f"s{n}",
                  "total_cost_usd": float(os.environ.get("STUB_COST", "0.01"))}))
'''


def _evaluate(root):
    result = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue", SLUG,
         "--write"], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "repo"
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{CREATED}'\n"
        "status: active\nassessment: {risk: contained, familiarity: "
        "brownfield-mapped, size: small, goal: delivery, role: engineer, "
        "labels: []}\n")
    _evaluate(root)
    (root / DOCS).mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    stub = bin_dir / "claude"
    stub.write_text(_STUB)
    stub.chmod(0o755)
    (tmp_path / "markers").mkdir()
    return root


def _run(root, *extra, plan=("touch",), stage="verify", stop=True,
         claude=True, path=None):
    tmp = root.parent
    args = [sys.executable, str(CLI), "run", SLUG, "--stage", stage]
    if stop:
        args += ["--stop-file", str(tmp / "STOP")]
    if claude:
        args += ["--claude", str(tmp / "bin" / "claude")]
    env = {**os.environ,
           "STUB_LOG": str(tmp / "stub.log"),
           "STUB_MARKERS": str(tmp / "markers"),
           "STUB_PLAN": json.dumps(list(plan)),
           "STUB_TASK": str(root / ".compass" / "work" / SLUG),
           "STUB_STOP": str(tmp / "STOP"),
           "STUB_TOKEN": TOKEN,
           "STUB_PIDFILE": str(tmp / "child.pid"),
           "MY_SERVICE_TOKEN": ENV_SECRET}
    if path is not None:
        env["PATH"] = path
    return subprocess.run([*args, *extra], cwd=root, capture_output=True,
                          text=True, env=env, timeout=120)


def _recorded_sessions(root):
    """The sessions the runner says it started: one table row per cycle in
    every run record it wrote."""
    import re
    return sum(len(re.findall(r"^\| \d+ \| ", p.read_text(), re.M))
               for p in (root / DOCS).glob("run-*.md"))


def _calls(root):
    """Each stub call's arguments. Fails unless the stub left one marker for
    every session the runner recorded: a session that was not the stub
    leaves none, so the counts differ."""
    log = root.parent / "stub.log"
    calls = [json.loads(line) for line in
             (log.read_text().splitlines() if log.exists() else [])]
    markers = list((root.parent / "markers").iterdir())
    assert len(markers) == len(calls) == _recorded_sessions(root), (
        "a session ran that was not the stub")
    return calls


def _task(root):
    return yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml")
                          .read_text())


def _record(root, n=1):
    return (root / DOCS / f"run-{n}.md").read_text()


def _last_run(root):
    return _task(root)["runs"][-1]


# --- HR-A: refusals before any session ---------------------------------------

def test_hr_a_refuses_without_a_stop_file(project):
    result = _run(project, stop=False)
    assert result.returncode != 0
    assert "--stop-file" in result.stderr
    assert _calls(project) == []


def test_hr_a_refuses_a_stage_other_than_build_or_verify(project):
    for stage in ("ship", "land", "assess"):
        result = _run(project, stage=stage)
        assert result.returncode != 0, stage
    assert _calls(project) == []


def test_hr_a_refuses_an_unknown_issue_and_a_project_without_compass(project, tmp_path):
    result = subprocess.run(
        [sys.executable, str(CLI), "run", "nope", "--stage", "verify",
         "--stop-file", str(tmp_path / "STOP"), "--claude",
         str(tmp_path / "bin" / "claude")], cwd=project, capture_output=True,
        text=True)
    assert result.returncode != 0
    bare = tmp_path / "bare"
    bare.mkdir()
    result = subprocess.run(
        [sys.executable, str(CLI), "run", SLUG, "--stage", "verify",
         "--stop-file", str(tmp_path / "STOP"), "--claude",
         str(tmp_path / "bin" / "claude")], cwd=bare, capture_output=True,
        text=True)
    assert result.returncode != 0 and ".compass" in result.stderr
    assert _calls(project) == []


def test_hr_a_refuses_when_claude_cannot_be_found(project):
    result = _run(project, claude=False, path="/usr/bin:/bin")
    assert result.returncode != 0
    assert "claude" in result.stderr
    assert _calls(project) == []


def test_hr_a_refuses_a_flag_above_its_policy_ceiling(project):
    high_cycles = _run(project, "--max-cycles", "31")
    assert high_cycles.returncode == 2 and "RP-LOOP-006" in high_cycles.stderr
    high_minutes = _run(project, "--max-minutes", "241")
    assert high_minutes.returncode == 2 and "RP-LOOP-007" in high_minutes.stderr
    for flag, value in (("--max-cycles", "0"), ("--max-minutes", "0")):
        assert _run(project, flag, value).returncode == 2, flag
    assert _calls(project) == []
    assert "runs" not in _task(project)


# --- HR-B: the cycle ceiling ---------------------------------------------------

def test_hr_b_the_cycle_ceiling_stops_the_run_unlanded(project):
    result = _run(project, "--max-cycles", "2", plan=("touch",))
    assert result.returncode == 4, result.stdout + result.stderr
    assert len(_calls(project)) == 2
    run = _last_run(project)
    assert run["outcome"] == "stopped" and run["cycles"] == 2
    assert "cycle ceiling" in run["stopped_reason"]["reason"]
    assert run["stopped_reason"]["evidence"] == f"{DOCS}/run-1.md"
    assert _task(project)["status"] != "landed"
    assert "cycle ceiling" in _record(project)
    lint = subprocess.run([sys.executable, str(CLI), "issue", "lint",
                           "--issue", SLUG], cwd=project, capture_output=True,
                          text=True)
    assert lint.returncode == 0, lint.stdout + lint.stderr


# --- HR-C: the stop file -------------------------------------------------------

def test_hr_c_a_stop_file_ends_the_run_before_the_next_session(project):
    result = _run(project, "--max-cycles", "5", plan=("stop_file",))
    assert result.returncode == 4
    assert len(_calls(project)) == 1
    assert "stop file" in _last_run(project)["stopped_reason"]["reason"]


def test_hr_c_a_stop_file_present_at_the_start_starts_nothing(project):
    (project.parent / "STOP").write_text("stop\n")
    result = _run(project)
    assert result.returncode == 4
    assert _calls(project) == []
    assert "stop file" in _last_run(project)["stopped_reason"]["reason"]


# --- HR-D: done ----------------------------------------------------------------

def test_hr_d_a_verify_run_ends_when_every_gate_passes(project):
    result = _run(project, plan=("pass_gates",))
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_calls(project)) == 1
    run = _last_run(project)
    assert run["outcome"] == "done" and "stopped_reason" not in run


def test_hr_d_a_build_run_ends_when_every_scenario_is_green(project):
    task = project / ".compass" / "work" / SLUG
    manifest = task / "manifest.yml"
    manifest.write_text(manifest.read_text() + (
        "scenarios:\n- id: X-1\n  title: Given a thing, then it works.\n"
        "  intent: INT-1\n"))
    result = _run(project, plan=("touch", "green"), stage="build")
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(_calls(project)) == 2
    assert _last_run(project)["outcome"] == "done"


def test_hr_d_a_session_that_lands_the_issue_stops_the_run(project):
    result = _run(project, plan=("land",))
    assert result.returncode == 4
    assert "landed" in _last_run(project)["stopped_reason"]["reason"]


# --- HR-E: redaction -------------------------------------------------------------

def test_hr_e_a_credential_in_error_text_is_redacted(project):
    result = _run(project, "--max-cycles", "1", plan=("leak",))
    assert result.returncode == 4
    record = _record(project)
    manifest = (project / ".compass" / "work" / SLUG / "manifest.yml").read_text()
    for text in (record, manifest, result.stdout, result.stderr):
        assert TOKEN not in text
        assert ENV_SECRET not in text
    assert "[REDACTED]" in record
    assert "request refused" in record


# --- HR-F: one fresh session per cycle --------------------------------------------

def test_hr_f_each_cycle_is_a_fresh_unattended_session(project):
    _run(project, "--max-cycles", "2", plan=("touch",))
    calls = _calls(project)
    assert len(calls) == 2
    for argv in calls:
        assert "-p" in argv
        message = argv[argv.index("-p") + 1]
        assert "/compass:verify" in message and SLUG in message
        assert "unattended" in message
        for word in ("land", "push", "merge"):
            assert word in message
        assert "--resume" not in argv and "--continue" not in argv
        assert argv[argv.index("--plugin-dir") + 1] == str(ROOT)
        denied = argv[argv.index("--disallowedTools") + 1]
        assert "git push" in denied and "ship-commit" in denied


def test_hr_f_build_names_the_implement_command(project):
    _run(project, "--max-cycles", "1", plan=("touch",), stage="build")
    message = _calls(project)[0]
    assert "/compass:implement" in message[message.index("-p") + 1]


# --- HR-G: no progress -------------------------------------------------------------

def test_hr_g_cycles_without_progress_stop_the_run(project):
    result = _run(project, "--max-cycles", "10", plan=("nothing",))
    assert result.returncode == 4
    assert len(_calls(project)) == 3
    reason = _last_run(project)["stopped_reason"]["reason"]
    assert "no progress" in reason and "RP-LOOP-005" in reason


def test_hr_g_an_unreadable_manifest_stops_the_run(project):
    result = _run(project, "--max-cycles", "5", plan=("corrupt",))
    assert result.returncode == 4
    assert len(_calls(project)) == 1
    assert "cannot be read" in _record(project)


# --- HR-H: the minute ceiling ---------------------------------------------------------

def test_hr_h_the_minute_ceiling_ends_a_long_session(project):
    result = _run(project, "--max-minutes", "0.03", plan=("sleep",))
    assert result.returncode == 4
    assert "minute ceiling" in _last_run(project)["stopped_reason"]["reason"]
    assert len(_calls(project)) == 1


# --- HR-I: one launcher ----------------------------------------------------------------

def test_hr_i_the_eval_harness_starts_claude_through_the_shared_launcher(
        monkeypatch, tmp_path):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import host_launch
    from evals import harness
    seen = []

    def fake(claude_exe, message, args, cwd, env, timeout=None):
        seen.append((claude_exe, message))
        return host_launch.Launch(0, "", "", False)

    monkeypatch.setattr(host_launch, "launch_claude", fake)
    state = harness._new_run_state()
    harness._invoke_claude("claude-stub", "hello", [], tmp_path, state,
                           resume=None, remaining_budget=1.0, env={})
    assert seen == [("claude-stub", "hello")]


# --- HR-J: the decision record, the reference workflow and the doc -----------

def test_hr_j_the_exception_is_accepted_and_the_workflow_is_inactive():
    adr = next((ROOT / "architecture" / "decisions").glob("ADR-030-*.md"))
    text = adr.read_text()
    # Accepted by the maintainer on 2026-10-03.
    assert "status: accepted" in text and "ADR-025" in text
    workflow = (ROOT / "ci" / "headless-verify.yml").read_text()
    on = yaml.safe_load(workflow)[True]
    assert list(on) == ["workflow_dispatch"]
    assert "ANTHROPIC_API_KEY" in workflow
    assert not any("compass run" in p.read_text()
                   for p in (ROOT / ".github" / "workflows").glob("*.y*ml"))
    doc = (ROOT / "docs" / "headless-runner.md").read_text()
    assert "not met" in doc
    readme = (ROOT / "docs" / "README.md").read_text()
    assert "`docs/headless-runner.md`" in readme
    assert "run_cmd.py" in readme and "host_launch.py" in readme


# --- found in review --------------------------------------------------------

def test_hr_f_the_guard_fails_when_another_claude_runs(project):
    _run(project, "--max-cycles", "1", plan=("touch",))
    true_exe = "/usr/bin/true" if os.path.exists("/usr/bin/true") else "/bin/true"
    subprocess.run([sys.executable, str(CLI), "run", SLUG, "--stage", "verify",
                    "--stop-file", str(project.parent / "STOP"), "--claude",
                    true_exe, "--max-cycles", "1"], cwd=project,
                   capture_output=True, text=True)
    with pytest.raises(AssertionError):
        _calls(project)


def test_hr_e_a_credential_cut_by_the_tail_is_still_redacted(project):
    _run(project, "--max-cycles", "1", plan=("long_leak",))
    record = _record(project)
    assert TOKEN[-30:] not in record


def test_hr_b_a_run_never_reuses_a_record_number(project):
    _run(project, "--max-cycles", "1", plan=("corrupt",))
    first = _record(project, 1)
    (project / ".compass" / "work" / SLUG / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {SLUG}\ncreated: '{CREATED}'\n"
        "status: active\nassessment: {risk: contained, familiarity: "
        "brownfield-mapped, size: small, goal: delivery, role: engineer, "
        "labels: []}\n")
    _evaluate(project)
    _run(project, "--max-cycles", "1", plan=("touch",))
    assert _record(project, 1) == first
    assert (project / DOCS / "run-2.md").is_file()
    assert _last_run(project)["n"] == 2


def test_hr_g_a_timed_out_session_that_breaks_the_manifest_is_not_overwritten(project):
    result = _run(project, "--max-minutes", "0.03", plan=("corrupt_sleep",))
    assert result.returncode == 4
    manifest = (project / ".compass" / "work" / SLUG / "manifest.yml").read_text()
    assert manifest == "issue: [unclosed\n"
    assert "cannot be read" in _record(project)


def test_hr_h_the_minute_ceiling_ends_what_the_session_started(project):
    import time
    _run(project, "--max-minutes", "0.03", plan=("spawn_sleep",))
    pid = int((project.parent / "child.pid").read_text())
    time.sleep(0.5)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, 9)
    assert not alive, "a process the session started outlived the run"


def test_hr_b_a_second_run_of_the_same_issue_is_refused(project):
    lock = project / ".compass" / "work" / SLUG / "run.lock"
    lock.write_text("")
    result = _run(project, "--max-cycles", "1")
    assert result.returncode == 2 and "in progress" in result.stderr
    assert _calls(project) == []
    lock.unlink()
    assert _run(project, "--max-cycles", "1").returncode == 4
    assert not lock.exists()



def _interrupt(project, signame):
    """Start a run whose session sleeps, send the runner `signame`, and
    return the session's pid once the runner has exited."""
    import signal
    import time
    tmp = project.parent
    env = {**os.environ, "STUB_LOG": str(tmp / "stub.log"),
           "STUB_MARKERS": str(tmp / "markers"),
           "STUB_PLAN": json.dumps(["sleep"]),
           "STUB_TASK": str(project / ".compass" / "work" / SLUG),
           "STUB_STOP": str(tmp / "STOP"), "STUB_TOKEN": TOKEN,
           "STUB_PIDFILE": str(tmp / "child.pid"),
           "MY_SERVICE_TOKEN": ENV_SECRET}
    runner = subprocess.Popen(
        [sys.executable, str(CLI), "run", SLUG, "--stage", "verify",
         "--stop-file", str(tmp / "STOP"), "--claude", str(tmp / "bin" / "claude")],
        cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pidfile = tmp / "child.pid"
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.1)
    runner.send_signal(getattr(signal, signame))
    runner.wait(timeout=20)
    return int(pidfile.read_text())


@pytest.mark.parametrize("signame", ["SIGINT", "SIGTERM"])
def test_rre_1_an_interrupted_run_leaves_a_record_naming_it(project, signame):
    _interrupt(project, signame)
    record = _record(project)
    assert "Outcome:** stopped" in record
    assert "interrupted" in record
    assert "interrupted" in _last_run(project)["stopped_reason"]["reason"]


def test_rre_1_the_record_outcome_matches_the_exit_code(project):
    result = _run(project, "--max-cycles", "1", plan=("done_bad_runs",))
    assert result.returncode == 4
    assert "Outcome:** stopped" in _record(project)


def test_rre_1_an_empty_runs_key_is_read_as_no_runs(project):
    manifest = project / ".compass" / "work" / SLUG / "manifest.yml"
    manifest.write_text(manifest.read_text() + "runs:\n")
    result = _run(project, "--max-cycles", "1", plan=("touch",))
    assert result.returncode == 4, result.stderr
    assert _last_run(project)["n"] == 1


@pytest.mark.parametrize("signame", ["SIGINT", "SIGTERM"])
def test_hr_h_an_interrupted_run_ends_its_session(project, signame):
    import signal
    import time
    tmp = project.parent
    env = {**os.environ, "STUB_LOG": str(tmp / "stub.log"),
           "STUB_MARKERS": str(tmp / "markers"),
           "STUB_PLAN": json.dumps(["sleep"]),
           "STUB_TASK": str(project / ".compass" / "work" / SLUG),
           "STUB_STOP": str(tmp / "STOP"), "STUB_TOKEN": TOKEN,
           "STUB_PIDFILE": str(tmp / "child.pid"),
           "MY_SERVICE_TOKEN": ENV_SECRET}
    runner = subprocess.Popen(
        [sys.executable, str(CLI), "run", SLUG, "--stage", "verify",
         "--stop-file", str(tmp / "STOP"), "--claude", str(tmp / "bin" / "claude")],
        cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pidfile = tmp / "child.pid"
    for _ in range(100):
        if pidfile.exists() and pidfile.read_text():
            break
        time.sleep(0.1)
    runner.send_signal(getattr(signal, signame))
    runner.wait(timeout=20)
    pid = int(pidfile.read_text())
    time.sleep(0.5)
    try:
        os.kill(pid, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(pid, 9)
    assert not alive, "the session outlived an interrupted run"


def test_hr_b_a_session_that_removes_the_lock_still_ends_cleanly(project):
    result = _run(project, "--max-cycles", "1", plan=("rm_lock",))
    assert result.returncode == 4, result.stderr


def test_hr_g_a_runs_entry_that_is_not_a_list_stops_cleanly(project):
    result = _run(project, "--max-cycles", "3", plan=("bad_runs",))
    assert result.returncode in (2, 4), result.stderr
    assert "Traceback" not in result.stderr



# --- RC-1: the cost ceiling ---------------------------------------------------------

def test_rc_1_the_cost_ceiling_stops_the_run_and_bounds_each_session(project, monkeypatch):
    monkeypatch.setenv("STUB_COST", "2.0")
    result = _run(project, "--max-cycles", "10", plan=("touch",))
    assert result.returncode == 4, result.stdout + result.stderr
    calls = _calls(project)
    assert len(calls) == 3
    budgets = [argv[argv.index("--max-budget-usd") + 1] for argv in calls]
    assert budgets == ["5.00", "3.00", "1.00"]
    reason = _last_run(project)["stopped_reason"]["reason"]
    assert "cost ceiling" in reason and "RP-LOOP-008" in reason


def test_rc_1_a_cost_flag_above_the_policy_is_refused(project):
    result = _run(project, "--max-cost-usd", "6")
    assert result.returncode == 2 and "RP-LOOP-008" in result.stderr
    assert _run(project, "--max-cost-usd", "0").returncode == 2
    assert _calls(project) == []
