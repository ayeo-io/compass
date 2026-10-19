"""The approval guard judges a command by its whole text, or refuses a word, where
the reader cannot tie a piece of text to the command that uses it (issue
`hooks-stop-refusing-harmless-work`, unit 2).

Each refused call below hides a request path in text that a later command runs,
or in a shape the reader does not follow. The matching controls show the guard
does not refuse harmless text in the same shapes. The tests call `check` in
process with the shared world of `tests/approval_guard_cases.py`.

- a pipe into a subshell, a subshell piped into a shell, an output process
  substitution, a runner that reads a substitution, a function or alias that
  renames an exempt command, a `case` or `${...}` that ends a substitution early;
- a heredoc for `git apply`, which is a patch and not text;
- an option of `rg` or `grep` whose value is a command or a file;
- the keyword before a command (`do echo`), which must not hide it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import bash_event, build_world, drop_world  # noqa: E402

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
]

ALLOWED = [
    f'for f in a b; do echo "$f {REQUEST}"; done',
    f"git commit -F - <<'EOF'\nabout {REQUEST}\nEOF",
    f'git commit -m "Add a function that lists {REQUEST} and an alias"',
    f'echo "{REQUEST}" | head -1',
    f"grep -A 2 -rn {REQUEST} docs",
    f"rg -g '*.md' {REQUEST}",
]


@pytest.mark.parametrize("command", REFUSED)
def test_a_shape_the_reader_cannot_tie_to_its_command_is_refused(guard, command):
    found = guard(command)
    assert found and found[0] in ("approval-request-protected", "transcript-protected"), (
        command, found)


@pytest.mark.parametrize("command", ALLOWED)
def test_harmless_text_in_the_same_shapes_is_allowed(guard, command):
    assert guard(command) is None, command
