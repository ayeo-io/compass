"""Group A and the Bash scenarios of group F of issue
`hooks-stop-refusing-harmless-work`: the guard reads a Bash command as words,
so text that only names a protected thing passes, and every call that reads,
writes, enters or runs the thing is still refused.

Scenarios: `TRC-001` to `TRC-012`, `TRC-044` to `TRC-046`, `TRC-050`, `TRC-051`.

Each loosening scenario (an "allowed" test) runs the real `hooks/pre-tool.sh`
on the controls of `tests/approval_guard_cases.py` that belong to it, and is
red before the change because the guard refuses a word inside a message. Each
twin scenario (a "refused" test) names a harmful call nearby and passes before
and after the change: a twin that passed only after the change would not guard
anything. `test_table_controls_are_allowed` runs every control of the table in
process.

Red before the change: `TRC-001`, `TRC-003`, `TRC-005`, `TRC-007`, `TRC-009`, `TRC-011`,
the scenario `TRC-050` and the table test. Green before the change, kept as
regression guards: `TRC-002`, `TRC-004`, `TRC-006`, `TRC-008`, `TRC-010`, `TRC-012`
and also the scenarios `TRC-044`, `TRC-045`, `TRC-046` and `TRC-051`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import (ALLOWED, CALLER, DEL, REQ, TRN, bash_event,  # noqa: E402
                                  build_world, controls_for, drop_world, misses, payload)


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


def _refused(world, commands, code):
    found = misses(world, [bash_event(world, c) for c in commands], code)
    assert not found, "\n".join(found)


def _allowed(world, scenario):
    rows = controls_for(scenario)
    assert rows, f"the table holds no control for {scenario}"
    found = misses(world, [bash_event(world, c.command) for c in rows], "allowed")
    assert not found, "\n".join(found)


# --- the request folder and the prompt hook script -------------------------------------------

def test_trc_001_request_words_in_text_are_not_judged(world):
    _allowed(world, "TRC-001")


def test_trc_002_a_message_does_not_hide_a_request_path_command_or_redirect(world):
    _refused(world, [
        'git commit -m "$(cat {request})"',
        "gh issue comment 5 --body-file {request}",
        "echo x > {request}",
        'echo "cat {request}" | sh',
        "bash <<'EOF'\ncat {request}\nEOF",
        'bash -c "cat {request}"',
        "grep -rn x .compass/work/issue-a/approval-requests",
        'git commit -m "$(<{request})"',
        'git commit -m "`cat {request}`"',
    ], REQ)


# --- the transcript --------------------------------------------------------------------------

def test_trc_003_transcript_words_in_text_are_not_judged(world):
    _allowed(world, "TRC-003")


def test_trc_004_a_message_does_not_hide_a_transcript_path(world):
    _refused(world, [
        "cat ~/.claude/projects/-p/{session}.jsonl",
        'tail "$CLAUDE_CONFIG_DIR"/projects/x/y.jsonl',
        'git commit -m "$(cat ~/.claude/projects/-p/{session}.jsonl)"',
        "echo x | tee ~/.claude/projects/-p/{session}.jsonl",
        "grep confirm ~/.claude-ayeo/projects/*/*.jsonl",
        'cat "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/projects/-p/{session}.jsonl"',
    ], TRN)


def test_trc_005_a_listing_above_the_transcript_is_not_refused(world):
    _allowed(world, "TRC-005")


def test_trc_006_a_listing_into_the_transcript_folder_or_a_read_above_it_is_refused(world):
    _refused(world, [
        "ls ~/.claude/projects/-p",
        "ls ~/.claude",
        "ls -R ~",
        "ls ~/*",
        "cd ~",
        "grep -r confirm ~",
        "cd ~ && grep -r confirm .",
    ], TRN)


# --- a delegated approval and the delegation folder ------------------------------------------

def test_trc_007_compass_in_a_path_beside_ansi_c_quoting_is_not_a_delegated_approval(world):
    _allowed(world, "TRC-007")


def test_trc_008_compass_run_with_an_ansi_c_escape_is_still_refused(world):
    _refused(world, [
        r"$'\x63ompass' evidence approve --check c",
        r"compass $'\x65vidence' $'appro\x76e' --check c --delegated --as main",
        r"./cli/compass $'\x65vidence' $'appro\x76e' --check c --delegated --as main",
        r'bash -c "compass $' + r"'\x65vidence' $'appro\x76e'" + r' --delegated --as main"',
    ], CALLER)


def test_trc_009_a_message_naming_evidence_braces_or_delegated_is_not_a_delegated_approval(world):
    _allowed(world, "TRC-009")


def test_trc_010_a_real_delegated_approval_beside_a_message_is_still_checked(world):
    _refused(world, [
        'git commit -m "x" && compass evidence approve --check c --delegated',
        'compass evidence approve --check c --scope "text" --delegated --as compass:architect',
        'echo "compass evidence approve --check c --delegated" | sh',
    ], CALLER)


def test_trc_011_the_delegation_folder_named_in_text_is_not_judged(world):
    _allowed(world, "TRC-011")


def test_trc_012_a_delegation_file_named_as_a_path_is_still_refused(world):
    _refused(world, [
        "cat .compass/delegations/DL-1.yml",
        "rm .compass/delegations/DL-1.yml",
        'git commit -m "$(cat .compass/delegations/DL-1.yml)"',
        "echo x > .compass/delegations/DL-2.yml",
        "cat .compass/deleg*/*",
    ], DEL)


# --- a script written and run in one command -------------------------------------------------

def test_trc_044_text_written_to_a_file_and_run_in_the_same_command_is_judged(world):
    cases = (
        ("cat > /tmp/s.sh <<'EOF'\ncat {request}\nEOF\nsh /tmp/s.sh", REQ),
        ('echo "cat {request}" > /tmp/s.sh && bash /tmp/s.sh', REQ),
        ("printf 'cat {request}' | tee /tmp/s.sh ; source /tmp/s.sh", REQ),
        ("cat > /tmp/s.sh <<'EOF'\ncat ~/.claude/projects/-p/{session}.jsonl\nEOF\n. /tmp/s.sh",
         TRN),
        ("cat > /tmp/s.sh <<'EOF'\ncat .compass/delegations/DL-1.yml\nEOF\nsh /tmp/s.sh", DEL),
        ("cat > ./s.sh <<'EOF'\nbash hooks/prompt-approval.sh < event.json\nEOF\n./s.sh", REQ),
    )
    found = []
    for command, code in cases:
        found += misses(world, [bash_event(world, command)], code)
    assert not found, "\n".join(found)


def test_trc_045_a_script_that_names_nothing_protected_is_not_refused(world):
    _allowed(world, "TRC-045")


# --- spellings of a path ---------------------------------------------------------------------

def test_trc_046_a_listing_above_the_transcript_is_judged_after_the_path_is_normalised(world):
    _refused(world, [
        "ls ~/dev/../.claude/projects/-p",
        "ls {home}//.claude",
        "ls ~ada/.claude/projects/-p",
        "ls ~/.CLAUDE/projects/-p",
        "ls ~/./.claude",
        "ls ~/.cl*",
        "ls -d ~/.claude*",
        "ls -R {home}",
    ], TRN)


# --- options that take text, and options that take a path -----------------------------------

def test_trc_050_text_options_in_either_form_are_not_judged(world):
    _allowed(world, "TRC-050")


def test_trc_051_an_option_whose_value_is_a_path_is_judged_as_a_path(world):
    _refused(world, [
        "gh issue comment 5 --body-file={request}",
        "gh pr create --body-file {request}",
        "git commit -F {request}",
        "git commit --file={request}",
    ], REQ)


# --- the shared table, in process -----------------------------------------------------------

def test_table_controls_are_allowed(world, monkeypatch):
    """Every control of the shared table passes `check`, for a Bash call and for
    each tool, so the table both refuses and allows."""
    monkeypatch.setenv("HOME", str(world.home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    from compass_pkg import approval_guard
    assert len(ALLOWED) >= 40
    found = []
    for case in ALLOWED:
        got = approval_guard.check(payload(case, home=world.home, project=world.project,
                                           transcript=world.transcript))
        if got is not None:
            found.append(f"{case.id} {case.command or case.tool_input}: refused with {got[0]}")
    assert not found, "\n".join(found)
