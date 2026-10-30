"""A shell write from a linked worktree is judged by that worktree's issue.

A subagent started with worktree isolation keeps the parent session's
`CLAUDE_PROJECT_DIR`, so the pre-tool hook judged every Bash write it made by
the main checkout's issue (ayeo-io/compass-delivery#337). The hook now reads
the `cwd` field of a Bash call: when the Compass project found from it is a
tree other than the session's own and git ties it to the session's
repository, that tree's pointer names the issue, as ADR-074 rules for Edit
and Write. Every other Bash write is judged as before.

Every scenario uses a real `git worktree add`, the real hook, and
`CLAUDE_PROJECT_DIR` set to the main checkout, as a subagent with worktree
isolation has it. Scenario ids are in
bash-follows-worktree-cwd/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_session_issue import _issue
from test_worktree_issue_precedence import (_env, _linked, _repo, _setup,
                                            _wt_issues)

ROOT = Path(__file__).resolve().parent.parent
PRE = ROOT / "hooks" / "pre-tool.sh"
sys.path.insert(0, str(ROOT))
from tests.path_folder import link_programs  # noqa: E402

_NO_CWD = object()


def _bash(session_project, command, *, cwd=_NO_CWD, session=None,
          issue=None, path=None):
    """Run the hook on a Bash call. `cwd` is the call's working folder, as
    Claude Code puts it in the input; the hook process itself runs in the
    session's project."""
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    if cwd is not _NO_CWD:
        payload["cwd"] = str(cwd)
    if session:
        payload["session_id"] = session
    env = _env(session_project, issue)
    if path is not None:
        env["PATH"] = path
    return subprocess.run(
        ["bash", str(PRE)], input=json.dumps(payload), capture_output=True,
        text=True, env=env, cwd=str(session_project), timeout=60)


def _flat(result):
    return " ".join((result.stdout + result.stderr).split())


def _main_and_worktree(tmp_path, *, main_red, wt_red):
    """The session's project `main`, whose pointer names "alpha", and a
    linked worktree whose pointer names "beta"."""
    main = _setup(tmp_path, main_issues=(("alpha", main_red),),
                  main_pointer="alpha")
    wt = _linked(main)
    _wt_issues(wt, [("beta", wt_red)], "beta")
    return main, wt


# --- group A: a shell write from a worktree ----------------------------------

@pytest.mark.parametrize("where", ["root", "sub-folder"])
def test_trc_001_the_worktree_red_allows_the_write(tmp_path, where):
    """Scenario id: `TRC-001`"""
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=True)
    cwd = wt if where == "root" else wt / "src"
    r = _bash(main, "echo x > src/app.py", cwd=cwd)
    assert r.returncode == 0, r.stderr


def _path_without_jq(tmp_path):
    """Every tool in /usr/bin and /bin except jq, and the python3 running
    the tests, which the hook's loader needs."""
    d = tmp_path / "nojq"
    d.mkdir()
    (d / "python3").symlink_to(sys.executable)
    return link_programs(
        d, lambda name: name == "jq" or name.startswith("python"))


def test_trc_001_without_jq(tmp_path):
    """Scenario id: `TRC-001`. The grep fallback reads `cwd` too."""
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=True)
    path = _path_without_jq(tmp_path)
    probe = subprocess.run(["bash", "-c", "command -v jq || echo none"],
                           capture_output=True, text=True, env={"PATH": path})
    assert probe.stdout.strip() == "none", probe.stdout
    r = _bash(main, "echo x > src/app.py", cwd=wt, path=path)
    assert r.returncode == 0, r.stderr


def test_trc_002_the_worktree_missing_red_refuses_and_names_the_worktree(
        tmp_path):
    """Scenario id: `TRC-002`"""
    main, wt = _main_and_worktree(tmp_path, main_red=True, wt_red=False)
    r = _bash(main, "echo x > src/app.py", cwd=wt)
    assert r.returncode == 2, r.stderr
    text = _flat(r)
    assert "[no-red-on-record]" in text, text
    assert "'beta'" in text, text
    assert str(wt) in text, text
    assert "alpha" not in text, text


def _table(compass_dir, session, slug):
    (compass_dir / "sessions.json").write_text(json.dumps({session: {
        "issue": slug, "at": "2099-01-01T00:00:00+00:00",
        "root": str(compass_dir.resolve())}}), encoding="utf-8")


def test_trc_003_the_session_is_recorded_on_the_worktree_issue(tmp_path):
    """Scenario id: `TRC-003`

    Each session table says this session last worked on another issue, so a
    lease check in either tree would refuse with pointer-moved.
    """
    main, wt = _main_and_worktree(tmp_path, main_red=True, wt_red=True)
    _issue(main, "other", red=True)
    _issue(wt, "other", red=True)
    _table(main / ".compass", "S1", "other")
    _table(wt / ".compass", "S1", "other")
    before = {p: p.read_bytes() for p in (main / ".compass" / "sessions.json",
                                          wt / ".compass" / "sessions.json")}
    r = _bash(main, "echo x > src/app.py", cwd=wt, session="S1")
    assert r.returncode == 0, r.stderr
    assert "pointer-moved" not in r.stderr
    beta = (wt / ".compass" / "work" / "beta" / "manifest.yml").read_text()
    alpha = (main / ".compass" / "work" / "alpha" / "manifest.yml").read_text()
    assert re.search(r"-\s+['\"]?S1['\"]?\s*$", beta, re.M), beta
    assert "S1" not in alpha, alpha
    for table, data in before.items():
        assert table.read_bytes() == data, table


def test_trc_004_a_worktree_pointer_that_names_no_issue_refuses(tmp_path):
    """Scenario id: `TRC-004`"""
    main, wt = _main_and_worktree(tmp_path, main_red=True, wt_red=True)
    (wt / ".compass" / "current-task").write_text("missing\n")
    r = _bash(main, "echo x > src/app.py", cwd=wt)
    assert r.returncode == 2, r.stderr
    assert "[bad-session-issue]" in r.stderr, r.stderr
    assert str(wt) in _flat(r)


# --- group B: every other shell write is judged as before ---------------------

@pytest.mark.parametrize("shape", ["absolute-only", "with-a-worktree-write"])
def test_trc_005_an_absolute_target_outside_the_worktree_keeps_the_session_issue(
        tmp_path, shape):
    """Scenario id: `TRC-005`

    The worktree's issue has a red and the session's has none. An absolute
    write into the main checkout must still need the session issue's red,
    also when the same command writes a guarded file in the worktree.
    """
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=True)
    command = f"echo y > {main}/src/app.py"
    if shape == "with-a-worktree-write":
        command = f"echo x > src/app.py; {command}"
    r = _bash(main, command, cwd=wt)
    assert r.returncode == 2, r.stderr
    text = _flat(r)
    assert "[no-red-on-record]" in text, text
    assert "'alpha'" in text, text


def _other_repository(tmp_path):
    other = _repo(tmp_path / "other")
    _issue(other, "beta", red=True)
    (other / ".compass" / "current-task").write_text("beta\n")
    return other


@pytest.mark.parametrize("kind", [
    "no-cwd-field", "relative", "main-root", "main-sub-folder",
    "worktree-without-compass", "other-repository", "missing-folder"])
def test_trc_006_the_session_project_judges_as_before(tmp_path, kind):
    """Scenario id: `TRC-006`"""
    main = _setup(tmp_path, main_issues=(("alpha", False),),
                  main_pointer="alpha")
    cwd = {
        "no-cwd-field": lambda: _NO_CWD,
        "relative": lambda: "src",
        "main-root": lambda: main,
        "main-sub-folder": lambda: main / "src",
        "worktree-without-compass": lambda: _linked(main, "bare-wt"),
        "other-repository": lambda: _other_repository(tmp_path),
        "missing-folder": lambda: tmp_path / "gone",
    }[kind]()
    r = _bash(main, "echo x > src/app.py", cwd=cwd)
    assert r.returncode == 2, r.stderr
    text = _flat(r)
    assert "[no-red-on-record]" in text, text
    assert "'alpha'" in text, text


def test_trc_007_the_session_project_keeps_the_variable_and_pointer_moved(
        tmp_path):
    """Scenario id: `TRC-007`"""
    main = _setup(tmp_path, main_issues=(("alpha", False), ("gamma", True)),
                  main_pointer="alpha")
    r = _bash(main, "echo x > src/app.py", cwd=main, issue="gamma")
    assert r.returncode == 0, r.stderr

    moved = _setup(tmp_path / "second",
                   main_issues=(("alpha", True), ("beta", True)),
                   main_pointer="alpha")
    first = _bash(moved, "echo x > src/app.py", cwd=moved, session="S1")
    assert first.returncode == 0, first.stderr
    (moved / ".compass" / "current-task").write_text("beta\n")
    r = _bash(moved, "echo x > src/app.py", cwd=moved, session="S1")
    assert r.returncode == 2, r.stderr
    assert "[pointer-moved]" in r.stderr, r.stderr


# --- group C: the refusal and the documents -----------------------------------

def test_trc_008_no_red_on_record_names_the_project():
    """Scenario id: `TRC-008`. The generated page is checked by
    tests/test_refusal_registry.py::test_rtp_4_docs_page_is_not_stale."""
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.refusals import render

    text = render("no-red-on-record", slug="beta", target="src/app.py",
                  tool="Bash", guard="the built-in production-code set",
                  project="/work/wt")
    why = next(line for line in text.splitlines() if line.startswith("Why:"))
    assert "'beta'" in why and "/work/wt" in why, why


def test_trc_009_the_documents_state_the_shell_rule():
    """Scenario id: `TRC-009`"""
    contract = " ".join(
        (ROOT / "docs" / "safety-contract.md").read_text().split())
    for phrase in (
            "A Bash call whose working folder is in a worktree of the "
            "session's repository is judged by that worktree's issue",
            "a `cd` inside the command is not followed",
            "an absolute path into a worktree is judged by the project of "
            "the call's working folder"):
        assert phrase in contract, phrase
    decisions = ROOT / "architecture" / "decisions"
    records = list(decisions.glob("ADR-078-*.md"))
    assert len(records) == 1, records
    record = " ".join(records[0].read_text().split())
    assert "amends ADR-074 decisions 1 and 8" in record, record
    index = " ".join((decisions / "README.md").read_text().split())
    assert "amended by ADR-078 (decisions 1 and 8)" in index


# --- shapes that reach the main checkout from a worktree ---------------------

def _nested(tmp_path, *, main_red, wt_red):
    """The layout Claude Code uses: the worktree inside the main checkout,
    at .claude/worktrees/<name>."""
    from test_worktree_issue_precedence import _git
    main = _setup(tmp_path, main_issues=(("alpha", main_red),),
                  main_pointer="alpha")
    (main / ".claude" / "worktrees").mkdir(parents=True)
    wt = main / ".claude" / "worktrees" / "a"
    _git(main, "worktree", "add", "-q", "--detach", str(wt))
    wt = wt.resolve()
    _wt_issues(wt, [("beta", wt_red)], "beta")
    return main, wt


@pytest.mark.parametrize("layout", ["sibling", "nested"])
def test_trc_005_nested_and_sibling_layouts(tmp_path, layout):
    """Scenario id: `TRC-005`, in both worktree layouts: the worktree's red
    allows a relative write in it, and an absolute write into the main
    checkout still needs the main checkout's red."""
    build = _main_and_worktree if layout == "sibling" else _nested
    main, wt = build(tmp_path, main_red=False, wt_red=True)
    r = _bash(main, "echo x > src/app.py", cwd=wt)
    assert r.returncode == 0, r.stderr
    r = _bash(main, f"echo y > {main}/src/app.py", cwd=wt)
    assert r.returncode == 2 and "'alpha'" in r.stderr, r.stderr


@pytest.mark.parametrize("command", [
    "cd {main} && echo x > src/app.py",
    "cd {main} && sed -i '' s/1/2/ src/app.py",
    "(cd {main}; echo x > src/app.py)",
    "pushd {main} >/dev/null && echo x > src/app.py",
    "bash -c 'cd {main} && echo x > src/app.py'",
    "cd ../../.. && echo x > src/app.py",
    "echo x > $PWD/../../../src/app.py",
    "sed -i '' s/1/2/ ${{PWD}}/../../../src/app.py",
    "echo x > ../../../src/app.py",
    "echo x > ~/src/app.py",
    "echo x > $HOME/src/app.py",
    "sed -i '' s/1/2/ ${{HOME}}/src/app.py",
    "echo x > $OLDPWD/src/app.py",
    "echo x > $CLAUDE_PROJECT_DIR/src/app.py",
    "python3 -c \"import os; os.chdir('{main}'); open('src/app.py', 'w')\"",
    "node -e \"process.chdir('{main}'); require('fs').writeFileSync('src/app.py', 'x')\"",
    "ruby -e \"Dir.chdir('{main}'); File.write('src/app.py', 'x')\"",
    "env -C {main} sed -i '' s/1/2/ src/app.py",
    "sudo -D {main} tee src/app.py",
    "sudo --chdir={main} tee src/app.py",
    "\"cd\" {main} && echo x > src/app.py",
    "'cd' {main} && echo x > src/app.py",
    "cd {main} && git apply p.diff",
    "sh -c 'cd {main}; git apply p.diff'",
    "patch -p1 -d {main} < p.diff",
    "patch -p1 --directory={main} < p.diff",
    "ruby -C {main} -i -pe 'x' src/app.py",
    "find {main}/src -name app.py -execdir sed -i '' s/1/2/ app.py \\;",
])
def test_trc_005_a_command_that_reaches_the_main_checkout_keeps_the_session_issue(
        tmp_path, command):
    """Scenario id: `TRC-005`. A command that changes folder (in the shell or
    in an inline script), names a folder the hook cannot know (`~`, a
    variable), or climbs out of the worktree with `..` can write the main
    checkout's file. It is judged by the main checkout's issue, as before
    the change. The `~` and `$HOME` cases need no real home folder: the
    hook reads them as text."""
    main, wt = _nested(tmp_path, main_red=False, wt_red=True)
    r = _bash(main, command.format(main=main), cwd=wt)
    assert r.returncode == 2, r.stderr
    assert "'alpha'" in r.stderr, r.stderr


def test_trc_001_a_patch_in_the_worktree_is_judged_by_the_worktree(tmp_path):
    """Scenario id: `TRC-001`. A patch applied where the call runs, with no
    folder change, is judged by the worktree's issue."""
    main, wt = _nested(tmp_path, main_red=False, wt_red=True)
    for command in ("patch -p1 < p.diff", "git apply p.diff"):
        r = _bash(main, command, cwd=wt)
        assert r.returncode == 0, (command, r.stderr)


def test_trc_005_the_session_rules_judge_a_write_into_the_main_checkout(
        tmp_path):
    """Scenario id: `TRC-005`. When an absolute target in the main checkout
    is guarded, the session's own rules apply: COMPASS_ISSUE first, and
    pointer-moved from the main checkout's session table."""
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=True)
    _issue(main, "gamma", red=True)
    r = _bash(main, f"echo y > {main}/src/app.py", cwd=wt, issue="gamma")
    assert r.returncode == 0, r.stderr

    main2, wt2 = _main_and_worktree(tmp_path / "second", main_red=True,
                                    wt_red=True)
    _issue(main2, "other", red=True)
    _table(main2 / ".compass", "S2", "other")
    r = _bash(main2, f"echo y > {main2}/src/app.py", cwd=wt2, session="S2")
    assert r.returncode == 2, r.stderr
    assert "[pointer-moved]" in r.stderr, r.stderr


def test_trc_001_many_targets_cost_the_same_from_a_worktree(tmp_path):
    """Scenario id: `TRC-001`. Each target is charged to the work budget
    once, so a command the main checkout allows is not refused as too
    complex from a worktree."""
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=False)
    command = "echo x | tee " + " ".join(
        f"notes/file{i:04d}.txt" for i in range(390))
    for cwd in (main, wt):
        r = _bash(main, command, cwd=cwd)
        assert r.returncode == 0, (cwd, r.stderr)


def test_trc_001_the_worktree_settings_judge_the_worktree_pass(tmp_path):
    """Scenario id: `TRC-001`. The main checkout declares `*.cfg` as code
    and the worktree declares only `*.ini`. After the session pass reads the
    main checkout's settings, the worktree pass reads the worktree's."""
    main, wt = _main_and_worktree(tmp_path, main_red=False, wt_red=False)
    (main / "compass.yml").write_text(
        "enforcement:\n  code_globs: ['*.cfg']\n", encoding="utf-8")
    (wt / "compass.yml").write_text(
        "enforcement:\n  code_globs: ['*.ini']\n", encoding="utf-8")
    r = _bash(main, f"echo a > {main}/notes.yml; echo b > conf/x.cfg", cwd=wt)
    assert r.returncode == 0, r.stderr
