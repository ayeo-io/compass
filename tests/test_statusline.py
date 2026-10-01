"""`bin/compass-statusline`: the current issue's state in Claude Code's status line.

Claude Code runs the status line command with session JSON on stdin and
shows its output to the person; it never enters the model's context, so it
costs no tokens. The line must use the same stage resolver as `compass
next`, so the two cannot disagree, and it must never break the session:
outside a Compass project, or on any error, it prints nothing and exits 0.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SHIM = ROOT / "bin" / "compass-statusline"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def _statusline(cwd, *, columns=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(cwd)}
    if columns is not None:
        env["COLUMNS"] = str(columns)
    cmd = [str(SHIM)]
    payload = json.dumps({"cwd": str(cwd), "workspace": {"current_dir": str(cwd)}})
    return subprocess.run(cmd, input=payload, capture_output=True, text=True,
                          cwd="/", env=env, timeout=30)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def _start(root, slug="fix-login-redirect"):
    r = subprocess.run(
        [sys.executable, str(CLI), "quick-fix", "start", slug,
         "--risk", "trivial - one string", "--familiarity",
         "brownfield-mapped - the file and its test exist",
         "--size", "atomic - one line", "--intent", "the redirect is right",
         "--scenario", "Given a login, when it succeeds, then it redirects home",
         "--test", "tests/test_login.py"],
        cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return root / ".compass" / "work" / slug


def test_silent_outside_a_compass_project(tmp_path):
    r = _statusline(tmp_path)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_shows_the_issue_state_with_a_red_on_record(repo):
    task = _start(repo)
    (task / "evidence").mkdir(exist_ok=True)
    (task / "evidence" / "red-TRC-001.json").write_text(json.dumps(
        {"exit_code": 1, "passed": False, "scenario": "TRC-001"}))
    r = _statusline(repo)
    assert r.returncode == 0 and r.stderr == "", r.stderr
    line = r.stdout.strip()
    assert "\n" not in line, line
    for part in ("compass", "fix-login-redirect", "quick fix", "gates 0/3", "TRC-001 red"):
        assert part in line, (part, line)


def test_a_scenario_id_with_a_slash_finds_its_evidence(repo):
    """`compass tdd-red` writes `red-a_b.json` for scenario `a/b`, so the
    status line must look for the same name."""
    import yaml
    task = _start(repo)
    path = task / "manifest.yml"
    m = yaml.safe_load(path.read_text())
    m["scenarios"][0]["id"] = "login/redirect"
    path.write_text(yaml.safe_dump(m, sort_keys=False))
    (task / "evidence").mkdir(exist_ok=True)
    (task / "evidence" / "red-login_redirect.json").write_text(json.dumps(
        {"exit_code": 1, "passed": False, "scenario": "login/redirect"}))
    line = _statusline(repo, columns=200).stdout
    assert "login/redirect red" in line, line


def test_a_corrupt_manifest_prints_nothing(repo):
    task = _start(repo)
    (task / "manifest.yml").write_text("issue: [unclosed\n  : : :\n")
    r = _statusline(repo)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_garbage_on_stdin_prints_nothing(tmp_path):
    r = subprocess.run([str(SHIM)], input="not json",
                       capture_output=True, text=True, cwd=tmp_path, timeout=30)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def _next_stage(root):
    out = subprocess.run([sys.executable, str(CLI), "next"], cwd=root,
                         capture_output=True, text=True).stdout.strip()
    return "done" if out == "all phases complete" else out.split()[0].split("[")[0]


@pytest.mark.parametrize("change", [
    {}, {"current_phase": "implement"}, {"status": "landed"},
    {"current_phase": "build"}, {"gates": "all-pass"}, {"gates": "with-junk"},
])
def test_the_stage_agrees_with_compass_next(repo, change):
    import yaml
    task = _start(repo)
    path = task / "manifest.yml"
    m = yaml.safe_load(path.read_text())
    for key, value in change.items():
        if value == "all-pass":
            for g in m["gates"]:
                g["status"] = "pass"
        elif value == "with-junk":
            m["gates"] = [dict(m["gates"][0], status="pass"), 5]
        else:
            m[key] = value
    path.write_text(yaml.safe_dump(m, sort_keys=False))
    line = _statusline(repo).stdout
    assert f" · {_next_stage(repo)}" in line, (change, _next_stage(repo), line)


def test_no_approach_record_shows_no_stage(repo):
    """`compass next` reports no stage when delivery-approach.md is missing,
    so the line shows none either; the other fields stay."""
    _start(repo)
    for record in repo.rglob("delivery-approach.md"):
        record.unlink()
    nxt = subprocess.run([sys.executable, str(CLI), "next"], cwd=repo,
                         capture_output=True, text=True)
    assert nxt.returncode == 2, nxt.stdout
    fields = _statusline(repo).stdout.strip().split(" · ")
    assert fields[:3] == ["compass", "fix-login-redirect", "quick fix"], fields
    assert fields[3].startswith("gates "), fields


def test_a_nested_repository_without_compass_is_not_its_parents_project(repo):
    """The hook stops at the first `.git`; so does the status line."""
    _start(repo)
    inner = repo / "vendor" / "lib"
    inner.mkdir(parents=True)
    subprocess.run([*GIT, "init", "-q"], cwd=inner, check=True)
    r = _statusline(inner)
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_a_narrow_terminal_drops_fields_and_keeps_the_slug_last(repo):
    _start(repo)
    r = _statusline(repo, columns=30)
    line = r.stdout.rstrip("\n")
    assert len(line) <= 30, line
    assert line.startswith("compass · fix-login"), line
    cut = _statusline(repo, columns=20).stdout.rstrip("\n")
    assert len(cut) <= 20 and cut.startswith("compass · fix") and cut.endswith("…"), cut


def test_a_zero_width_falls_back_to_80(repo):
    _start(repo)
    line = _statusline(repo, columns=0).stdout
    assert "fix-login-redirect" in line, line


def test_the_shim_does_not_load_the_full_cli(repo):
    """The status line runs after every message, so it loads only its own
    module and what that needs, never the full command set."""
    _start(repo)
    # The shim's own one-liner, read from the file, so an import added to
    # the shim is caught as well as one added to the module.
    match = re.search(r"python3 -c '([^']*)'", SHIM.read_text())
    assert match, "bin/compass-statusline no longer runs python3 -c '...'"
    code = match.group(1) + (
        "; print('LOADED' if 'compass_pkg._all' in sys.modules else 'LEAN')")
    payload = json.dumps({"cwd": str(repo)})
    r = subprocess.run([sys.executable, "-c", code, str(ROOT / "cli")],
                       input=payload, capture_output=True, text=True)
    assert "fix-login-redirect" in r.stdout, r.stdout + r.stderr
    assert r.stdout.strip().endswith("LEAN"), r.stdout + r.stderr


def test_the_shim_is_fast_enough(repo):
    """The status line runs after every message, so it should take under
    100 ms on a warm repository. A shared CI runner cannot hold that
    exactly, so this pins a generous ceiling against a large regression;
    the test above checks the module stays lean."""
    _start(repo)
    _statusline(repo)
    times = []
    for _ in range(7):
        t = time.perf_counter()
        r = _statusline(repo)
        times.append(time.perf_counter() - t)
        assert r.returncode == 0 and "fix-login-redirect" in r.stdout, r.stdout + r.stderr
    times.sort()
    assert times[len(times) // 2] < 0.25, times


def test_the_session_contract_is_unchanged():
    """The status line costs no model context: nothing the session start
    injects mentions it."""
    for name in ("compass-contract.md", "hooks/session-start.sh"):
        p = ROOT / name
        if p.is_file():
            assert "statusline" not in p.read_text(encoding="utf-8").lower(), name
