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
        first = _type(root, f"main until {_soon()} for g5")
        assert first.block, first
        code = _code(first.message)
        assert re.fullmatch(r"[0-9a-f]{4}(-[0-9a-f]{4}){3}", code), code
        done = _type(root, f"confirm {typed(code)}")
        assert not done.block, (typed(code), done)
        assert list(_delegations(root)) == ["DL-1"]


def test_a3_short_or_wrong_code_refused(tmp_path):
    root = project(tmp_path)
    first = _type(root, f"main until {_soon()} for g5")
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
                              ("compass:delegate", f"main until {_soon()}"),
                              ("compass:delegate", f"main until {_soon()} for g5")):
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
    assert not _type(root, f"{ARCHITECT} until {_soon()}").block
    result = _without_prompt_id(root, "compass:revoke")
    assert not result.block, result
    assert _delegations(root)["DL-1"]["revoked_by"] == OWNER


def test_c3_replayed_delegation_refused(tmp_path):
    root = project(tmp_path)
    assert not _type(root, f"{ARCHITECT} until {_soon()}", prompt_id="p-1").block
    again = _type(root, f"{ARCHITECT} until {_soon()}", prompt_id="p-1")
    assert again.block and "already answered" in again.message, again
    assert list(_delegations(root)) == ["DL-1"]
    # A revoked delegation's prompt id is still used.
    assert not _type(root, "", command="compass:revoke", prompt_id="p-2").block
    assert _type(root, f"{ARCHITECT} until {_soon()}", prompt_id="p-1").block
    # A g5 delegation: the first command, replayed, is refused while it waits
    # and after it is confirmed; so is a replayed confirm.
    first = _type(root, f"main until {_soon()} for g5", prompt_id="p-3")
    code = _code(first.message)
    replay = _type(root, f"main until {_soon()} for g5", prompt_id="p-3")
    assert replay.block and "already answered" in replay.message, replay
    assert code not in replay.message
    assert not _type(root, f"confirm {code}", prompt_id="p-4").block
    assert list(_delegations(root)) == ["DL-1", "DL-2"]
    dl = _delegations(root)["DL-2"]
    assert dl["prompt_id"] == "p-4" and dl["requested_prompt_id"] == "p-3"
    for prompt_id, args in (("p-3", f"main until {_soon()} for g5"),
                            ("p-4", f"main until {_soon()}"),
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
    for base in ("/usr/bin", "/bin"):
        for entry in sorted(Path(base).iterdir()):
            if entry.name == "jq" or entry.name.startswith("python") or (d / entry.name).exists():
                continue
            (d / entry.name).symlink_to(entry)
    return str(d)


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
