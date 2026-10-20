"""The approval guard judges a command that is not simple by its whole text (issue
`hooks-stop-refusing-harmless-work`, scenario `TRC-067`).

The rows of `tests/approval_guard_cases.py` that pair with `TRC-067` are the routes the
adversarial review found through a word reader: a variable that carries text into a path,
a heredoc delimiter that the shell decodes, a command or alias that replaces the command
a text position trusts, a sink that writes or runs its input, and a search option in a short
form. Every one names a protected thing, so every one is refused. The controls are the plain
commands that stay allowed.

The tests below call `check` in process with the shared world for the shapes of an earlier
version that the gate keeps refused, and the real hook for the rows of the table.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import (bash_event, build_world, controls_for, drop_world,  # noqa: E402
                                  payload, refused_for, run_hook, verdict)

REQUEST = "approval-" + "requests"
FILE = ".compass/work/issue-a/" + REQUEST + "/pending/1.yml"
SCRIPT = "hooks/prompt-" + "approval.sh"


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


@pytest.fixture
def guard(world, monkeypatch):
    monkeypatch.setenv("HOME", str(world.home))
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    from compass_pkg import approval_guard
    return lambda command: approval_guard.check(bash_event(world, command))


def _verdicts(world, rows, want):
    found = []
    for case in rows:
        body = payload(case, home=world.home, project=world.project, transcript=world.transcript)
        got = verdict(run_hook(world, body))
        if got != want(case):
            found.append(f"{case.id} {case.command!r}: wanted {want(case)}, got {got}")
    return found


def test_trc_067_a_command_that_is_not_simple_is_judged_by_its_whole_text(world):
    refused, allowed = refused_for("TRC-067"), controls_for("TRC-067")
    assert len(refused) >= 35, len(refused)
    assert len(allowed) >= 6, len(allowed)
    found = _verdicts(world, refused, lambda case: case.code)
    found += _verdicts(world, allowed, lambda case: "allowed")
    assert not found, "\n".join(found)


def test_trc_068_an_unquoted_text_value_or_an_unknown_option_is_judged_by_the_whole_text(world):
    refused, allowed = refused_for("TRC-068"), controls_for("TRC-068")
    assert len(refused) >= 30, len(refused)
    assert len(allowed) >= 5, len(allowed)
    found = _verdicts(world, refused, lambda case: case.code)
    found += _verdicts(world, allowed, lambda case: "allowed")
    assert not found, "\n".join(found)


def test_trc_052_a_compass_option_is_not_text(guard):
    """Superseded: no `compass` option is a text position, so a request path in a `--note`
    is refused, and a command that starts with a path ending in `compass` is not simple."""
    for command in (f"compass quick-fix start --note {FILE}", f"./compass --note {FILE}",
                    f"./cli/compass quick-fix start --title t --reason {FILE}"):
        found = guard(command)
        assert found and found[0] == "approval-request-protected", (command, found)


REFUSED = [
    f'echo "cat {FILE}" | (sh)',
    f'( echo "cat {FILE}" ) | sh',
    f'echo "cat {FILE}" > >(sh)',
    f'bash <(echo "cat {FILE}")',
    f'sh -c "$(echo cat {FILE})"',
    f'cat <(echo "cat {FILE}") | sh',
    f'ls() {{ cat "$@"; }}; ls {FILE}',
    f"alias ls=cat; ls {FILE}",
    f'echo "$(case x in x) cat {FILE};; esac)"',
    'echo "${x:-")}"; cat ' + FILE + '; echo "}"',
    f"git apply <<'EOF'\n+++ b/{SCRIPT}\nEOF",
    f"rg --pre {SCRIPT} x .",
    f"rg --hostname-bin {SCRIPT} x",
    f"grep --exclude-from={FILE} x .",
    f"grep -A 2 x {FILE}",
    f"for f in a; do cat {FILE}; done",
    f"ls {FILE} | cat",
    # text that an earlier version skipped and the guard judges now
    f'for f in a b; do echo "$f {REQUEST}"; done',
    f"git commit -F - <<'EOF'\nabout {REQUEST}\nEOF",
    f'echo "{REQUEST}" | head -1',
    f"grep -A 2 -rn {REQUEST} docs",
    f"rg -g '*.md' {REQUEST}",
]

ALLOWED = [
    f'git commit -m "Add a function that lists {REQUEST} and an alias"',
    f"git status && git commit -m 'Name {REQUEST}'",
]


@pytest.mark.parametrize("command", REFUSED)
def test_a_shape_the_gate_does_not_read_is_refused_when_it_names_a_protected_thing(
        guard, command):
    found = guard(command)
    assert found and found[0] in ("approval-request-protected", "transcript-protected"), (
        command, found)


@pytest.mark.parametrize("command", ALLOWED)
def test_message_text_in_a_simple_command_is_allowed(guard, command):
    assert guard(command) is None, command
