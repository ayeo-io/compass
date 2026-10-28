"""Refusals added to the approval path of ayeo-io/compass#577 (issue
`approval-guard-hardening`).

- Group A: the agent may not Read or Grep a delegation file, and the code
  that confirms a guardrail 5 delegation holds 64 bits
  (compass-delivery-record#164).
- Group B: a delegated approval is checked against the caller however the
  command is wrapped, and every `--as` must name the caller
  (compass-delivery-record#163).
- Group C: an approval or delegation event with no prompt id is refused, and
  a delegation's prompt id is single-use (compass-delivery-record#165).
- Group D: the transcript cannot be read through the Claude Code
  configuration folder or any folder above it, with or without `jq`
  (compass-delivery-record#146).
- Group E (issue `approval-guard-ifs-as-and-delegation-globs`): an `--as`
  word built from a shell variable, and a Grep or Bash glob that can match
  the delegation files.

Every test pairs the calls it refuses with ordinary calls that must still
pass, so a refusal that is too wide fails here too. Each test name starts
with its scenario id.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml
from tests.path_folder import link_programs  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import (OWNER, event, manifest_of, pending_dir,  # noqa: E402
                              project, task_dir)
from test_pre_tool_hook import HOOK_PATH, _guarded_project  # noqa: E402

ARCHITECT = "compass:architect"


# --- helpers -----------------------------------------------------------------------------

def _hook(project_dir, tool, tool_input, env_extra=None, path=None, **fields):
    """Run the pre-tool hook on one tool call."""
    body = {"tool_name": tool, "session_id": "sess-guard", "tool_input": tool_input}
    body.update(fields)
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    env.update(env_extra or {})
    if path is not None:
        env["PATH"] = path
    return subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(body),
                          capture_output=True, text=True, env=env)


def _refused(result, code):
    return result.returncode == 2 and f"[{code}]" in result.stderr


@pytest.fixture
def guarded():
    project_dir, _ = _guarded_project()
    yield project_dir
    shutil.rmtree(project_dir, ignore_errors=True)


@pytest.fixture
def home(tmp_path):
    """A home folder with a Claude Code configuration folder and a transcript,
    outside the project, as on a real machine."""
    home = (tmp_path / "home").resolve()
    folder = home / ".claude-x" / "projects" / "-p"
    folder.mkdir(parents=True)
    transcript = folder / "s.jsonl"
    transcript.write_text('{"content": "confirm 1a2b-3c4d-5e6f-7a8b"}\n', encoding="utf-8")
    (home / ".claude-x" / "settings.json").write_text("{}\n", encoding="utf-8")
    return home, transcript


def _type(root, args, command="compass:delegate", session="sess-1", **kw):
    from compass_pkg import prompt_approval
    return prompt_approval.handle(event(root, command=command, args=args, session=session,
                                        **kw), {}, plugin_root=str(ROOT))


def _without_prompt_id(root, command, args="", value=None):
    from compass_pkg import prompt_approval
    body = event(root, command=command, args=args)
    if value is None:
        del body["prompt_id"]
    else:
        body["prompt_id"] = value
    return prompt_approval.handle(body, {}, plugin_root=str(ROOT))


def _delegations(root):
    folder = root / ".compass" / "delegations"
    return {p.stem: yaml.safe_load(p.read_text(encoding="utf-8"))
            for p in sorted(folder.glob("DL-*.yml"))} if folder.is_dir() else {}


def _soon(hours=2):
    when = datetime.datetime.now().astimezone() + datetime.timedelta(hours=hours)
    return when.strftime("%H:%M")


def _code(message):
    return re.search(r"/compass:delegate confirm (\S+)", message).group(1)


def _state(root):
    """Every file of the issue and the delegation folder, with its bytes, to
    show nothing was written. The lock file is left out: taking the lock
    creates it. The session lease, which records every command, is not
    approval state."""
    base = root / ".compass"
    return {str(p.relative_to(base)): p.read_bytes()
            for sub in ("work", "delegations") for p in sorted((base / sub).rglob("*"))
            if p.is_file() and p.name != ".approval.lock"}


# --- group A: delegation files and the confirmation code -----------------------------------

def test_a1_read_and_grep_under_delegations_refused(guarded):
    folder = guarded / ".compass" / "delegations"
    folder.mkdir(parents=True)
    confirm = folder / "confirm-s.yml"
    confirm.write_text("salt: x\ncode_hash: y\n", encoding="utf-8")
    refused = [
        ("Read", {"file_path": str(confirm)}),
        ("Read", {"file_path": ".compass/delegations/confirm-s.yml"}),
        ("Grep", {"pattern": "salt", "path": str(folder)}),
        ("Grep", {"pattern": "salt", "path": str(folder) + "/"}),
        ("Grep", {"pattern": "salt", "path": ".compass/delegations"}),
        ("Grep", {"pattern": "salt", "path": str(guarded / ".compass"),
                  "glob": "delegations/*"}),
        ("Read", {"file_path": str(guarded / ".COMPASS" / "Delegations" / "confirm-s.yml")}),
    ]
    for tool, tool_input in refused:
        r = _hook(guarded, tool, tool_input, cwd=str(guarded))
        assert _refused(r, "delegation-protected"), (tool, tool_input, r.returncode, r.stderr)
    for tool, tool_input in (("Grep", {"pattern": "salt", "path": str(guarded)}),
                             ("Read", {"file_path": str(guarded / "src" / "app.py")})):
        r = _hook(guarded, tool, tool_input, cwd=str(guarded))
        assert r.returncode == 0, (tool, tool_input, r.stderr)


def test_a2_confirmation_code_is_64_bits_and_typeable(tmp_path):
    for n, typed in enumerate((lambda c: c, lambda c: c.replace("-", ""), lambda c: c.upper())):
        (tmp_path / str(n)).mkdir()
        root = project(tmp_path / str(n))
        first = _type(root, f"--agent main --until {_soon()} --for g5")
        assert first.block, first
        code = _code(first.message)
        assert re.fullmatch(r"[0-9a-f]{4}(-[0-9a-f]{4}){3}", code), code
        done = _type(root, f"confirm {typed(code)}")
        assert not done.block, (typed(code), done)
        assert list(_delegations(root)) == ["DL-1"]


def test_a3_short_or_wrong_code_refused(tmp_path):
    root = project(tmp_path)
    first = _type(root, f"--agent main --until {_soon()} --for g5")
    code = _code(first.message)
    plain = code.replace("-", "")
    wrong = ("0" if plain[0] != "0" else "1") + plain[1:]
    for attempt in (plain[:8], code[:9], wrong, plain + "0", ""):
        assert _type(root, f"confirm {attempt}").block, attempt
    assert not _delegations(root)
    # A confirmation file the earlier version wrote holds the hash of an
    # 8-character code; that code is refused even though its hash matches.
    from compass_pkg import delegations
    path = root / ".compass" / "delegations" / "confirm-sess-1.yml"
    waiting = yaml.safe_load(path.read_text(encoding="utf-8"))
    waiting["code_hash"] = delegations._hash(waiting["salt"], "1a2b3c4d")
    path.write_text(yaml.safe_dump(waiting), encoding="utf-8")
    assert _type(root, "confirm 1a2b3c4d").block
    assert not _delegations(root)


# --- group B: the caller of a delegated approval -------------------------------------------

_APPROVE = "compass evidence approve --guardrail G5 --scope x --delegated --as {}"


def _wrapped(who):
    inner = _APPROVE.format(who)
    return [
        f'bash -c "{inner}"',
        f"sh -c '{inner}'",
        f"zsh -c '{inner}'",
        f"eval '{inner}'",
        f"eval {inner}",
        f"bash -c \"bash -c '{inner}'\"",
        f'echo "{inner}" | sh',
        f"cd /tmp && bash -c '{inner}'",
        f"bash -lc '{inner}'",
    ]


def test_b1_wrapped_delegated_approval_checked(guarded):
    for command in _wrapped(ARCHITECT):
        r = _hook(guarded, "Bash", {"command": command})
        assert _refused(r, "delegation-caller-mismatch"), (command, r.returncode, r.stderr)
    # A wrapped delegated approval with no --as, or a subagent naming the main agent.
    r = _hook(guarded, "Bash", {"command": "bash -c 'compass evidence approve --check x "
                                           "--delegated'"})
    assert _refused(r, "delegation-caller-mismatch"), r.stderr
    for command in _wrapped("main"):
        r = _hook(guarded, "Bash", {"command": command}, agent_type=ARCHITECT, agent_id="a1")
        assert _refused(r, "delegation-caller-mismatch"), (command, r.stderr)
    # The same wrapped command run by the agent it names is not refused.
    for command in _wrapped("main"):
        r = _hook(guarded, "Bash", {"command": command})
        assert r.returncode == 0, (command, r.stderr)
    for command in _wrapped(ARCHITECT):
        r = _hook(guarded, "Bash", {"command": command}, agent_type=ARCHITECT, agent_id="a2")
        assert r.returncode == 0, (command, r.stderr)
    # A search for the word approve with an ordinary --delimiter or --delete
    # flag is not a delegated approval.
    for command in ("grep -rn approve . | cut --delimiter=: -f1",
                    "git branch --delete approve"):
        r = _hook(guarded, "Bash", {"command": command})
        assert r.returncode == 0, (command, r.stderr)


def test_b1_quoted_or_escaped_flag_checked(guarded):
    """A `--delegated` flag spelled with empty quotes, a backslash or ANSI-C
    quoting is still checked, by the hook and by the guard."""
    who = f"--as {ARCHITECT}"
    base = "compass evidence approve --guardrail G5 --scope x"
    for command in (f"{base} --d''elegated {who}",
                    f"{base} -\\-delegated {who}",
                    f'{base} --""delegated {who}',
                    f"{base} $'--delegated' {who}",
                    f"compass evidence $'approve' --guardrail G5 --scope x --delegated {who}"):
        r = _hook(guarded, "Bash", {"command": command})
        assert _refused(r, "delegation-caller-mismatch"), (command, r.returncode, r.stderr)
    for command in (f"{base} $'--delegated' --as main", "echo $'a\\tb'"):
        r = _hook(guarded, "Bash", {"command": command})
        assert r.returncode == 0, (command, r.stderr)


def test_b2_every_as_must_name_the_caller(guarded):
    base = "compass evidence approve --check x --scope x --delegated"
    for command in (f"{base} --as main --as {ARCHITECT}",
                    f"{base} --as=main --as={ARCHITECT}",
                    f"{base} --as main --as={ARCHITECT}",
                    f"bash -c '{base} --as main' --as {ARCHITECT}"):
        r = _hook(guarded, "Bash", {"command": command})
        assert _refused(r, "delegation-caller-mismatch"), (command, r.returncode, r.stderr)
    for command in (f"{base} --as main", f"{base} --as main --as main"):
        r = _hook(guarded, "Bash", {"command": command})
        assert r.returncode == 0, (command, r.stderr)


# --- group C: one typed command, one record ------------------------------------------------

def test_c1_event_without_prompt_id_refused(tmp_path):
    from compass_pkg import approval_requests
    root = project(tmp_path)
    req = approval_requests.write(str(task_dir(root)), "guardrail", "G5", "refund migration")
    approval_requests.mark_shown(str(task_dir(root)), req)
    for value in (None, "", "   "):
        for command, args in (("compass:approve", ""), ("compass:reject", "no"),
                              ("compass:delegate", f"--agent main --until {_soon()}"),
                              ("compass:delegate", f"--agent main --until {_soon()} --for g5")):
            before = _state(root)
            result = _without_prompt_id(root, command, args, value)
            assert result.block, (command, value, result)
            assert "prompt id" in result.message, result.message
            assert _state(root) == before, (command, value)
    assert list(pending_dir(root).glob("*.yml"))
    assert not [e for e in manifest_of(root).get("evidence") or []
                if e.get("type") == "human-approval"]


def test_c2_revoke_without_prompt_id_revokes(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()}").block
    result = _without_prompt_id(root, "compass:revoke")
    assert not result.block, result
    assert _delegations(root)["DL-1"]["revoked_by"] == OWNER


def test_c3_replayed_delegation_refused(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"--agent {ARCHITECT} --until {_soon()}", prompt_id="p-1").block
    again = _type(root, f"--agent {ARCHITECT} --until {_soon()}", prompt_id="p-1")
    assert again.block and "already answered" in again.message, again
    assert list(_delegations(root)) == ["DL-1"]
    # A revoked delegation's prompt id is still used.
    assert not _type(root, "", command="compass:revoke", prompt_id="p-2").block
    assert _type(root, f"--agent {ARCHITECT} --until {_soon()}", prompt_id="p-1").block
    # A g5 delegation: the first command, replayed, is refused while it waits
    # and after it is confirmed; so is a replayed confirm.
    first = _type(root, f"--agent main --until {_soon()} --for g5", prompt_id="p-3")
    code = _code(first.message)
    replay = _type(root, f"--agent main --until {_soon()} --for g5", prompt_id="p-3")
    assert replay.block and "already answered" in replay.message, replay
    assert code not in replay.message
    assert not _type(root, f"confirm {code}", prompt_id="p-4").block
    assert list(_delegations(root)) == ["DL-1", "DL-2"]
    dl = _delegations(root)["DL-2"]
    assert dl["prompt_id"] == "p-4" and dl["requested_prompt_id"] == "p-3"
    for prompt_id, args in (("p-3", f"--agent main --until {_soon()} --for g5"),
                            ("p-4", f"--agent main --until {_soon()}"),
                            ("p-4", f"confirm {code}")):
        result = _type(root, args, prompt_id=prompt_id)
        assert result.block and "already answered" in result.message, (prompt_id, result)
    assert list(_delegations(root)) == ["DL-1", "DL-2"]


# --- group D: the transcript's folders -----------------------------------------------------

def test_d1_config_folder_and_ancestors_refused(guarded, home):
    home_dir, transcript = home
    config = home_dir / ".claude-x"
    common = {"transcript_path": str(transcript), "cwd": str(guarded)}
    env = {"HOME": str(home_dir)}
    refused = [
        ("Grep", {"pattern": "confirm", "path": str(config)}),
        ("Grep", {"pattern": "confirm", "path": str(config) + "/"}),
        ("Grep", {"pattern": "confirm", "path": str(home_dir)}),
        ("Grep", {"pattern": "confirm", "path": "/"}),
        ("Grep", {"pattern": "confirm", "path": "//"}),
        ("Grep", {"pattern": "confirm", "path": str(home_dir).replace("/", "//")}),
        ("Grep", {"pattern": "confirm", "path": "~/.claude-x"}),
        ("Grep", {"pattern": "confirm", "path": "~"}),
        ("Read", {"file_path": str(config)}),
        ("Read", {"file_path": "~/.claude-x/projects/-p/s.jsonl"}),
        # macOS opens a path in any letter case.
        ("Read", {"file_path": str(home_dir / ".Claude-X" / "projects" / "-p" / "s.jsonl")}),
        ("Grep", {"pattern": "confirm", "path": str(home_dir / ".CLAUDE-x")}),
    ]
    for tool, tool_input in refused:
        r = _hook(guarded, tool, tool_input, env, **common)
        assert _refused(r, "transcript-protected"), (tool, tool_input, r.returncode, r.stderr)
    # A relative path, or no path, resolves against the call's working folder.
    inside = home_dir / "dev" / "proj"
    inside.mkdir(parents=True)
    for tool_input, cwd in (({"pattern": "confirm", "path": "../.."}, inside),
                            ({"pattern": "confirm", "path": ".claude-x"}, home_dir),
                            ({"pattern": "confirm"}, home_dir)):
        r = _hook(guarded, "Grep", tool_input, env, transcript_path=str(transcript),
                  cwd=str(cwd))
        assert _refused(r, "transcript-protected"), (tool_input, cwd, r.stderr)
    # Ordinary reads, with the transcript outside the project, are not refused,
    # and an unrefused Grep is answered within 2 seconds.
    allowed = [
        ("Grep", {"pattern": "x", "path": str(guarded)}),
        ("Grep", {"pattern": "x"}),
        ("Grep", {"pattern": "x", "path": str(inside)}),
        ("Read", {"file_path": str(config / "settings.json")}),
        ("Read", {"file_path": str(guarded / "src" / "app.py")}),
        # The project's own .claude folder is not a configuration folder.
        ("Grep", {"pattern": "x", "path": str(guarded / ".claude")}),
        ("Read", {"file_path": str(guarded / ".claude" / "settings.json")}),
    ]
    for tool, tool_input in allowed:
        started = time.monotonic()
        r = _hook(guarded, tool, tool_input, env, **common)
        took = time.monotonic() - started
        assert r.returncode == 0, (tool, tool_input, r.stderr)
        assert took < 2.0, (tool, tool_input, took)


def test_d2_bash_naming_config_or_home_refused(guarded, home):
    home_dir, transcript = home
    common = {"transcript_path": str(transcript)}
    env = {"HOME": str(home_dir)}
    for command in ("grep -r confirm ~/.claude-x",
                    "grep -r confirm ~/.claude-x/",
                    "grep -r confirm ~/.claude-x/*",
                    f"grep -r confirm {home_dir}/.claude-x",
                    "grep -r confirm ~",
                    "grep -r confirm ~/",
                    "grep -r confirm $HOME",
                    "grep -r confirm ${HOME}",
                    'grep -r confirm "$HOME"',
                    f"grep -r confirm {home_dir}",
                    f"grep -r confirm '{home_dir}/'",
                    "cd ~ && grep -r confirm .",
                    f"grep -r confirm {home_dir}/.",
                    f"grep -r confirm {home_dir}/dev/..",
                    "grep -r confirm " + str(home_dir).replace("/", "//"),
                    "cat ~/.claude-x/*/-p/s.jsonl",
                    "cat ~/.claude-x/proj*/*/*.jsonl",
                    "grep -r confirm ~/.Claude-X"):
        r = _hook(guarded, "Bash", {"command": command}, env, **common)
        assert _refused(r, "transcript-protected"), (command, r.returncode, r.stderr)
    for command in ("ls ~/dev/projects-list", "cat ~/.claude-x/settings.json",
                    f"ls {home_dir}/dev", "echo $HOME/dev", "ls /usr/share", "git status",
                    "tr / _ < notes.txt", "ls ./.claude", f"ls -la {guarded}/.claude/",
                    "cp settings.json ./.claude/", "curl -s https://example.com/x"):
        r = _hook(guarded, "Bash", {"command": command}, env, **common)
        assert r.returncode == 0, (command, r.stderr)


def _path_without_jq(tmp_path):
    """Every tool in /usr/bin and /bin except jq, and the python3 running
    the tests, which the hook's loader needs."""
    d = tmp_path / "nojq"
    d.mkdir()
    (d / "python3").symlink_to(sys.executable)
    return link_programs(d, lambda name: name == "jq" or name.startswith("python"))


def test_d3_grep_path_read_without_jq(guarded, home, tmp_path):
    home_dir, transcript = home
    path = _path_without_jq(tmp_path)
    probe = subprocess.run(["bash", "-c", "command -v jq || echo none"], capture_output=True,
                           text=True, env={"PATH": path})
    assert probe.stdout.strip() == "none", probe.stdout
    common = {"transcript_path": str(transcript), "cwd": str(guarded)}
    env = {"HOME": str(home_dir)}
    for tool_input in ({"pattern": "confirm", "path": str(transcript.parent)},
                       {"pattern": "confirm", "path": str(home_dir / ".claude-x")}):
        r = _hook(guarded, "Grep", tool_input, env, path=path, **common)
        assert _refused(r, "transcript-protected"), (tool_input, r.returncode, r.stderr)
    r = _hook(guarded, "Grep", {"pattern": "x", "path": str(guarded)}, env, path=path, **common)
    assert r.returncode == 0, r.stderr


def test_d3_quoted_command_read_without_jq(guarded, home, tmp_path):
    """Without jq, a command holding an escaped quote is read in full, so the
    guard sees what the jq path sees."""
    home_dir, transcript = home
    path = _path_without_jq(tmp_path)
    common = {"transcript_path": str(transcript), "cwd": str(guarded)}
    env = {"HOME": str(home_dir)}
    for command in (f'bash -c "{_APPROVE.format(ARCHITECT)}"',
                    'compass evidence approve --guardrail G5 --scope "x" --delegated '
                    f'--as {ARCHITECT}'):
        r = _hook(guarded, "Bash", {"command": command}, env, path=path, **common)
        assert _refused(r, "delegation-caller-mismatch"), (command, r.returncode, r.stderr)
    command = f'cat "{transcript}"'
    r = _hook(guarded, "Bash", {"command": command}, env, path=path, **common)
    assert _refused(r, "transcript-protected"), (command, r.returncode, r.stderr)
    r = _hook(guarded, "Read", {"file_path": str(transcript)}, env, path=path, **common)
    assert r.returncode == 2, r.stderr
    for command in ('echo "hello \\"world\\""', 'git commit -m "a \\"quoted\\" word"'):
        r = _hook(guarded, "Bash", {"command": command}, env, path=path, **common)
        assert r.returncode == 0, (command, r.stderr)


def test_d3_the_jq_free_reader_decodes_as_json_does():
    """Without jq, the hook's own reader decodes each string as jq does,
    `\\/` included. The reader it replaced left `\\/` in place under bash
    3.2, the macOS `/bin/bash`."""
    text = HOOK_PATH.read_text(encoding="utf-8")
    reader = re.search(r"^  _json_string\(\) \{\n.*?^  \}\n", text, re.M | re.S).group(0)
    values = ['plain', 'a/b', 'git commit -m "a \\"q\\" word"', 'C:\\path\\to', 'end\\',
              'tab\there', 'line\nbreak', '\\t literal', '\\/ literal', 'mix / \\ " \t \n *?[]$']
    for value in values:
        encoded = json.dumps({"command": value})
        for document in (encoded, encoded.replace("/", "\\/")):
            r = subprocess.run(["bash", "-c", reader + '_json_string command; printf x'],
                               capture_output=True, text=True,
                               env={"PATH": os.environ["PATH"], "INPUT": document})
            assert r.stdout[:-1] == value, (document, r.stdout[:-1], r.stderr)


def test_d2_named_home_folder_refused():
    """`~<name>` is the home folder of that user."""
    import getpass
    from compass_pkg import approval_guard
    user = getpass.getuser()
    real_home = os.path.expanduser(f"~{user}")
    event = {"tool_name": "Bash", "tool_input": {"command": f"grep -r confirm ~{user}"},
             "transcript_path": f"{real_home}/.claude-x/projects/-p/s.jsonl"}
    found = approval_guard.check(event)
    assert found and found[0] == "transcript-protected", found


# --- the hook ends on any transcript path --------------------------------------------------

def test_f2_hook_ends_on_any_transcript_path(guarded):
    """A transcript path that does not start with `/` must not stop the hook
    from answering, so a call the hook refused before is still refused."""
    for transcript in ("C:/Users/u/.claude/projects/p/s.jsonl", "s.jsonl", ""):
        for command, code in (("echo hi", 0),
                              (_APPROVE.format(ARCHITECT), 2)):
            body = {"tool_name": "Bash", "session_id": "sess-guard",
                    "tool_input": {"command": command}, "transcript_path": transcript}
            env = dict(os.environ, CLAUDE_PROJECT_DIR=str(guarded))
            try:
                r = subprocess.run(["bash", str(HOOK_PATH)], input=json.dumps(body),
                                   capture_output=True, text=True, env=env, timeout=10)
            except subprocess.TimeoutExpired:
                pytest.fail(f"the hook did not answer within 10 seconds for {transcript!r}")
            assert r.returncode == code, (transcript, command, r.stderr)


def test_d2_transcript_named_in_full_refused(guarded, tmp_path):
    """A configuration folder that is not named `.claude*`, as
    CLAUDE_CONFIG_DIR allows: a Bash command naming the transcript, a brace
    expansion of its folder, or a quote spliced into its path is refused."""
    home_dir = (tmp_path / "home2").resolve()
    folder = home_dir / "cfg" / "work" / "projects" / "-p"
    folder.mkdir(parents=True)
    transcript = folder / "s.jsonl"
    transcript.write_text("{}\n", encoding="utf-8")
    common = {"transcript_path": str(transcript)}
    env = {"HOME": str(home_dir)}
    work = home_dir / "cfg" / "work"
    for command in (f"cat {transcript}",
                    f"tail -n 50 {transcript}",
                    f"cat {work}/{{projects,x}}/-p/s.jsonl",
                    f"cat {work}/proj''ects/-p/s.jsonl",
                    f"cat {work}/proj\\ects/-p/s.jsonl"):
        r = _hook(guarded, "Bash", {"command": command}, env, **common)
        assert _refused(r, "transcript-protected"), (command, r.returncode, r.stderr)
    for command in (f"ls {home_dir}/dev", "cat notes.txt"):
        r = _hook(guarded, "Bash", {"command": command}, env, **common)
        assert r.returncode == 0, (command, r.stderr)


# --- group E: IFS-built --as words and delegation globs ------------------------------------
# Scenario ids are in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md.

_BASE = "compass evidence approve --check x --scope x --delegated"


def _passes(project_dir, command, **fields):
    r = _hook(project_dir, "Bash", {"command": command}, **fields)
    assert r.returncode == 0, (command, fields, r.stderr)


def _caller_refused(project_dir, command, named=None, **fields):
    r = _hook(project_dir, "Bash", {"command": command}, **fields)
    assert _refused(r, "delegation-caller-mismatch"), (command, fields, r.returncode, r.stderr)
    if named:
        assert named in r.stderr, (command, named, r.stderr)


def _wrap(inner):
    return [f'bash -c "{inner}"', f"sh -c '{inner}'", f"eval '{inner}'",
            f"bash -c \"bash -c '{inner}'\"", f'echo "{inner}" | sh']


def test_trc_001_second_as_built_with_shell_variable_refused(guarded):
    """Scenario id: `TRC-001` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for word, named in (("--as${IFS}compass:architect", "--as${IFS}compass:architect"),
                        ("--as$IFS", "--as$IFS"),
                        ("--as$X", "--as$X"),
                        ('--as"$X"', "--as$X"),
                        ("--as'$X'", "--as$X"),
                        ("--as${IFS}main", "--as${IFS}main")):
        _caller_refused(guarded, f"{_BASE} --as main {word} compass:architect", named)


def test_trc_002_wrapped_second_as_refused(guarded):
    """Scenario id: `TRC-002` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for command in _wrap(f"{_BASE} --as main --as${{IFS}}compass:architect"):
        _caller_refused(guarded, command, "--as${IFS}compass:architect")
    for command in _wrap(f"{_BASE} --as compass:architect --as${{IFS}}compass:architect"):
        _caller_refused(guarded, command, "--as${IFS}compass:architect",
                        agent_type=ARCHITECT, agent_id="a1")


def test_trc_003_quoted_as_read_as_shell_reads_it(guarded):
    """Scenario id: `TRC-003` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for spelling in ('"--as" main', "--a''s main", "$'--as' main"):
        _passes(guarded, f"{_BASE} {spelling}")
    for spelling in ('"--as" compass:architect', "--a''s compass:architect",
                     "$'--as' compass:architect"):
        _caller_refused(guarded, f"{_BASE} {spelling}", "compass:architect")
    for spelling in ('"--as"${IFS}compass:architect', "$'--as'${IFS}compass:architect",
                     "--a''s${IFS}compass:architect"):
        # No exact --as is given, so the earlier rule refuses it as "no --as".
        _caller_refused(guarded, f"{_BASE} {spelling}")


def test_trc_004_other_as_word_refused(guarded):
    """Scenario id: `TRC-004` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for word in ("--asmain", "--assume-yes", "--as-main", "${IFS}--as${IFS}compass:architect",
                 "$IFS--as", "x--as"):
        _caller_refused(guarded, f"{_BASE} --as main {word}", word)
        _caller_refused(guarded, f"bash -c '{_BASE} --as main {word}'", word)


def test_trc_005_accepted_as_spellings_pass(guarded):
    """Scenario id: `TRC-005` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for flags in ("--as main", "--as main --as main", "--as=main", "--as main --as=main"):
        _passes(guarded, f"{_BASE} {flags}")
    for flags in ("--as=compass:architect", "--as compass:architect --as=compass:architect"):
        _passes(guarded, f"{_BASE} {flags}", agent_type=ARCHITECT, agent_id="a1")
    _passes(guarded, f"bash -c '{_BASE} --as main'")


def test_trc_006_as_word_outside_delegated_approval_passes(guarded):
    """Scenario id: `TRC-006` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    from compass_pkg import approval_guard
    for command in ("git update-index --assume-unchanged src/app.py",
                    "gh issue edit 7 --add-assignee octocat --assignee octocat",
                    "ls --ascii",
                    "compass evidence approve --check x --scope x --approver ada --role po",
                    "grep -rn approve . --assume-unchanged"):
        _passes(guarded, command)
        # The hook starts the guard only for some of these commands, so the
        # guard is also asked directly.
        assert approval_guard.check({"tool_name": "Bash", "tool_input": {"command": command}}
                                    ) is None, command


@pytest.fixture
def delegated(guarded):
    folder = guarded / ".compass" / "delegations"
    folder.mkdir(parents=True)
    (folder / "DL-1.yml").write_text("x: 1\n", encoding="utf-8")
    (folder / "confirm-s.yml").write_text("salt: x\ncode_hash: y\n", encoding="utf-8")
    return guarded


def _grep(project_dir, path, glob, expect):
    tool_input = {"pattern": "salt", "glob": glob}
    if path is not None:
        tool_input["path"] = path
    r = _hook(project_dir, "Grep", tool_input, cwd=str(project_dir))
    if expect:
        assert _refused(r, "delegation-protected"), (path, glob, r.returncode, r.stderr)
    else:
        assert r.returncode == 0, (path, glob, r.stderr)


def test_trc_007_grep_glob_naming_folder_refused(delegated):
    """Scenario id: `TRC-007` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    here = str(delegated)
    for path, glob in ((".compass", "deleg*/*"), (".compass", "d*/*"),
                       (".compass", "deleg?tions"), (".compass", "[d]elegations/*"),
                       (".Compass", "DELEG*/*"), (here, ".compass/deleg*/*"),
                       (here, ".compass/d*"), (".compass", "x d*/*")):
        _grep(delegated, path, glob, True)


def test_trc_008_grep_glob_naming_files_refused(delegated):
    """Scenario id: `TRC-008` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for path, glob in ((".compass", "**/confirm-*"), (".compass", "**/delegations/**"),
                       (".compass", "confirm-*"), (".compass", "**/DL-*.yml"),
                       (".compass", "delegations/*"), (str(delegated), "**/confirm-*"),
                       (str(delegated.parent), "**/confirm-*"), (None, "**/delegations/**")):
        _grep(delegated, path, glob, True)


def test_trc_009_grep_glob_matching_everything_accepted(delegated):
    """Scenario id: `TRC-009` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    here = str(delegated)
    for path, glob in ((".compass", "**/*"), (".compass", "**/*.md"), (".compass", "*"),
                       (".compass", "*.yml"), (".compass", "**/*.yml"), (here, "**/*"),
                       (here, "src/**/*.py"), (here, ".compass/*"), (here, "*.yml"),
                       (here, "**/*.yml")):
        _grep(delegated, path, glob, False)


def test_trc_010_grep_glob_from_unreachable_path_accepted(delegated):
    """Scenario id: `TRC-010` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for path, glob in (("src", "d*/*"), ("src", "**/confirm-*"), (".compass/work", "d*/*"),
                       (".compass/work", "**/DL-*.yml")):
        _grep(delegated, path, glob, False)


def _bash_glob(project_dir, command, expect):
    r = _hook(project_dir, "Bash", {"command": command}, cwd=str(project_dir))
    if expect:
        assert _refused(r, "delegation-protected"), (command, r.returncode, r.stderr)
    else:
        assert r.returncode == 0, (command, r.stderr)


def _refused_bash_globs(project_dir):
    return ["cat .compass/deleg*/*", "cat ./.compass/deleg*/*",
            "cat .compass/deleg?tions/DL-1.yml", "cat .compass/[d]eleg*/*", "ls .compass/d*",
            "cat .compass/**/confirm-*", "cat .compass/'deleg'*/*", "cat .Compass/Deleg*/*",
            f"cat {project_dir}/.compass/deleg*/*", "bash -c 'cat .compass/deleg*/*'",
            'eval "cat .compass/deleg*/*"', "cat<.compass/deleg*/*", "A=.compass/deleg*/*"]


def test_trc_011_bash_glob_reaching_folder_refused(delegated):
    """Scenario id: `TRC-011` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    Some rows start the guard only through the hook prefilter line of the
    other subtask, so this test stays red until that line is merged.
    """
    for command in _refused_bash_globs(delegated):
        _bash_glob(delegated, command, True)


def test_trc_011_guard_refuses_every_bash_glob_row(delegated):
    """Scenario id: `TRC-011` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    The guard module alone, so the rows are proved without the prefilter.
    """
    from compass_pkg import approval_guard
    for command in _refused_bash_globs(delegated):
        found = approval_guard.check({"tool_name": "Bash", "cwd": str(delegated),
                                      "tool_input": {"command": command}})
        assert found and found[0] == "delegation-protected", (command, found)


def test_trc_012_bash_glob_matching_everything_accepted(delegated):
    """Scenario id: `TRC-012` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    from compass_pkg import approval_guard
    for command in ("ls .compass/*", "ls .compass/work/*", "cat .compass/work/*/manifest.yml",
                    "ls .compass/**", "ls src/*.py", "cat docs/*.md"):
        _bash_glob(delegated, command, False)
        assert approval_guard.check({"tool_name": "Bash", "cwd": str(delegated),
                                     "tool_input": {"command": command}}) is None, command


def _guard(project_dir, command):
    from compass_pkg import approval_guard
    return approval_guard.check({"tool_name": "Bash", "cwd": str(project_dir),
                                 "tool_input": {"command": command}})


def test_trc_001_backslash_newline_inside_as_word_refused(guarded):
    """Scenario id: `TRC-001` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    The shell drops a backslash and newline inside a word, so `--a\\<newline>s`
    runs as `--as`.
    """
    for word in ("--a\\\ns", "--\\\nas", "-\\\n-as"):
        command = f"{_BASE} --as main {word} compass:architect"
        _caller_refused(guarded, command, "compass:architect")
        _caller_refused(guarded, f"bash -c '{command}'", "compass:architect")
    _passes(guarded, f"{_BASE} --a\\\ns main")


def test_trc_004_brace_expansion_in_delegated_approval_refused(guarded):
    """Scenario id: `TRC-004` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    The shell expands `--a{s=main,s=compass:architect}` to two `--as=` words.
    """
    for word in ("--a{s=main,s=compass:architect}", "--as={main,compass:architect}",
                 "--a{s,x}", "--as={1..2}"):
        named = word.replace("--as=", "")
        _caller_refused(guarded, f"{_BASE} --as main {word}", named)
        _caller_refused(guarded, f"bash -c '{_BASE} --as main {word}'", named)
    # A quoted JSON value holds a space or has no comma or range, and a command
    # that is not a delegated approval is not read at all.
    _passes(guarded, f"""{_BASE} --as main --reason '{{"a": 1}}'""")
    _passes(guarded, f"""{_BASE} --as main --reason '{{"a":1}}'""")
    _passes(guarded, "echo {a,b}")
    assert _guard(guarded, "echo {a,b} --as x") is None


def test_trc_011_backslash_newline_inside_glob_refused(delegated):
    """Scenario id: `TRC-011` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for command in ("cat .compass/deleg\\\n*/*", "cat .compass/d\\\neleg?tions/DL-1.yml"):
        found = _guard(delegated, command)
        assert found and found[0] == "delegation-protected", (command, found)


def test_trc_011_negated_and_posix_class_globs_refused(delegated):
    """Scenario id: `TRC-011` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    Bash and zsh read `[^y]` as `[!y]` and `[[:lower:]]` as a letter, which
    `fnmatch` does not.
    """
    for command in ("cat .compass/deleg[^y]*/*", "cat .compass/deleg[!y]*/*",
                    "cat .compass/d[[:lower:]]leg*/*", "cat .compass/d[[:alpha:]]leg?tions/*"):
        found = _guard(delegated, command)
        assert found and found[0] == "delegation-protected", (command, found)
    # A class that picks every name picks "everything", as `?*` does.
    assert _guard(delegated, "ls .compass/[[:lower:]]*") is None


def test_trc_008_grep_glob_split_on_commas_refused(delegated):
    """Scenario id: `TRC-008` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    for path, glob in ((".compass", "*.yml,deleg*/*"), (".compass", "x,d*/*"),
                       (".compass", "*.md, d*/*")):
        _grep(delegated, path, glob, True)
    _grep(delegated, ".compass", "*.yml,*.md", False)


def test_trc_013_glob_before_deleg_still_starts_the_guard(delegated):
    """Scenario id: `TRC-013` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    `cat .c*/delegations` is refused: the hook tests the command twice, so the
    glob character in one copy comes after `deleg` in the other.
    """
    _bash_glob(delegated, "cat .c*/delegations", True)


def test_trc_014_docs_state_refusals_accepted_forms_and_limits():
    """Scenario id: `TRC-014` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    contract = (ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8").lower()
    module = (ROOT / "cli" / "compass_pkg" / "approval_guard.py").read_text(
        encoding="utf-8").split('"""')[1].lower()
    facts = ["--as${ifs}", "--asmain", "--assume-yes", "--as-main",
             "**/*", "*.yml", ".compass/*", "d*/*", "**/confirm-*", "deleg?tions",
             "variable", "command substitution", "environment", "xargs", "printf",
             "brace expansion", "its own glob", "neither .compass nor deleg", "cd",
             "extglob", "rg -g", "find -name", "--include"]
    for name, text in (("docs/safety-contract.md", contract),
                       ("approval_guard.py docstring", module)):
        missing = [f for f in facts if f not in text]
        assert not missing, (name, missing)


def test_trc_014_docs_state_second_review_refusals_and_limits():
    """Scenario id: `TRC-014` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    contract = (ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8").lower()
    module = (ROOT / "cli" / "compass_pkg" / "approval_guard.py").read_text(
        encoding="utf-8").split('"""')[1].lower()
    facts = ["ansi-c quoting", "$'appro\\x76e'", "--{delegated,x}", "appr{ove,x}",
             "grep glob", "**/{dl-*,x}.yml", "only zsh reads", "(deleg\\|x)ations",
             "<->", "[a-z]", "grep -r x", "find .compass -type f -exec cat {} +"]
    for name, text in (("docs/safety-contract.md", contract),
                       ("approval_guard.py docstring", module)):
        missing = [f for f in facts if f not in text]
        assert not missing, (name, missing)


# --- second review: ANSI-C quoting, brace-built words, bracket classes ----------------------


def test_trc_001_ansi_c_quoting_in_evidence_command_refused(guarded):
    """Scenario id: `TRC-001` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    `$'--a\\x73'` runs as `--as` and `$'appro\\x76e'` runs as `approve`; the
    guard does not decode them, so a command that names evidence and holds
    ANSI-C quoting is refused.
    """
    for command in (f"{_BASE} --as main $'--a\\x73' compass:architect",
                    f"{_BASE} --as main $'--a\\163' compass:architect",
                    f"{_BASE} --as main $'\\x2d\\x2das' compass:architect",
                    "compass evidence $'appro\\x76e' --check x --scope x --delegated "
                    "--as compass:architect",
                    "compass evidence approve --check x --scope x $'--delegat\\x65d' "
                    "--as compass:architect",
                    "compass evidence list $'--n\\x6fte'",
                    f"bash -c \"{_BASE} --as main $'--a\\x73' compass:architect\""):
        _caller_refused(guarded, command, "$'")
    # No ANSI-C quoting, or a command that does not name evidence, passes.
    _passes(guarded, "compass evidence list --scope x")
    _passes(guarded, "echo $'a\\x62'")


def test_trc_004_brace_built_flag_or_verb_in_evidence_command_refused(guarded):
    """Scenario id: `TRC-004` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    `--{delegated,x}` and `appr{ove,x}` expand to the flag and the verb, so a
    command that names evidence and holds a brace expansion is refused.
    """
    for command in ("compass evidence approve --check x --scope x --{delegated,x} "
                    "--as compass:architect",
                    "compass evidence appr{ove,x} --check x --scope x --delegated "
                    "--as compass:architect",
                    "compass evidence appr{ove,x} --check x --{delegated,x}",
                    "bash -c 'compass evidence appr{ove,x} --delegated'"):
        _caller_refused(guarded, command, "{")
    for command in ("compass evidence add --check x --note '{\"a\": 1}'",
                    "compass evidence add --check x --note '{\"a\":1}'",
                    "compass evidence list --scope x",
                    "echo {a,b}"):
        _passes(guarded, command)


def test_trc_011_whole_bracket_class_read_as_one_character(delegated):
    """Scenario id: `TRC-011` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    A bracket expression with a POSIX class, a collating symbol or an
    equivalence class beside other members is read as one character.
    """
    for set_ in ("[[:lower:]x]", "[x[:lower:]]", "[[:digit:][:alpha:]]", "[[.d.]]",
                 "[[=d=]]", "[^[:digit:]]"):
        found = _guard(delegated, f"cat .compass/{set_}eleg*/*")
        assert found and found[0] == "delegation-protected", (set_, found)
        _grep(delegated, ".compass", f"{set_}eleg*/*", True)
    # A class that picks every name still picks "everything".
    assert _guard(delegated, "ls .compass/[[:lower:]x]*") is None
    _grep(delegated, ".compass", "[[:lower:]x]*", False)


# --- third review: every word spelled with an escape ----------------------------------------


def test_trc_001_refusal_says_the_word_may_be_built_by_the_shell(guarded):
    """Scenario id: `TRC-001` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    A compact JSON `--note` in `compass evidence add` is refused as a word
    the shell could build; the text says so, within the 60-word cap.
    """
    r = _hook(guarded, "Bash", {"command": "compass evidence add --note '{\"a\":1,\"b\":2}'"})
    assert _refused(r, "delegation-caller-mismatch"), (r.returncode, r.stderr)
    assert "word the shell could build" in r.stderr, r.stderr
    assert len(r.stderr.split("This hook")[0].split()) < 60, r.stderr


def test_trc_014_docs_state_third_review_refusal_and_limit():
    """Scenario id: `TRC-014` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md"""
    contract = (ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8").lower()
    module = (ROOT / "cli" / "compass_pkg" / "approval_guard.py").read_text(
        encoding="utf-8").split('"""')[1].lower()
    facts = ["$'\\x65vidence'", "appro?e", "--a?", "a glob that expands against a file",
             "python3 -c", "ayeo-io/compass#599", "any `compass evidence` command"]
    for name, text in (("docs/safety-contract.md", " ".join(contract.split())),
                       ("approval_guard.py docstring", " ".join(module.split()))):
        missing = [f for f in facts if f not in text]
        assert not missing, (name, missing)


def test_trc_001_every_word_spelled_with_an_escape_refused(guarded):
    """Scenario id: `TRC-001` in approval-guard-ifs-as-and-delegation-globs/acceptance-criteria.md

    The shell runs `compass $'\\x65vidence' $'appro\\x76e' ... $'--a\\x73'` as
    `evidence approve ... --as`, so no literal `evidence` word is needed: a
    command with the word `compass` and ANSI-C quoting with an escape is
    refused. So is an escape-spelled `compass` in command position.
    """
    tail = "--check x --scope x"
    for command in (f"compass $'\\x65vidence' $'appro\\x76e' {tail} $'--delegat\\x65d' "
                    "$'--a\\x73' compass:architect",
                    f"compass $'\\x65vidence' approve {tail} $'--delegat\\x65d' "
                    "--as compass:architect",
                    f"$'\\x63ompass' $'\\x65vidence' $'appro\\x76e' {tail} $'--delegat\\x65d' "
                    "$'--a\\x73' compass:architect",
                    f"c$'\\x6fmpass' $'\\x65vidence' approve {tail} --delegated "
                    "--as compass:architect",
                    f"cd x && $'\\x63ompass' $'\\x65vidence' approve {tail} --delegated "
                    "--as compass:architect",
                    f"$'\\x63ompass' $'\\x65vidence' $'appro\\x76e' {tail} --as main",
                    f"X=1 c$'\\x6fmpass' $'\\x65vidence' $'appro\\x76e' {tail} --as main",
                    "COMPASS_X=1 compass $'\\x65vidence' list"):
        _caller_refused(guarded, command, "$'")
    # No `compass` word, or no escape, passes.
    for command in ("printf $'a\\n'", "echo $'x'", "echo $'a\\tb' | cat",
                    "git commit -m 'x'", "git commit -m $'x'",
                    f"compass evidence approve {tail} $'--as' main",
                    "compass $'status'"):
        _passes(guarded, command)
