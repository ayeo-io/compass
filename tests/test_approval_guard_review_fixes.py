"""The calls the adversarial review of issue `hooks-stop-refusing-harmless-work`
found that the first version of the approval guard let through.

Scenarios: `TRC-057` to `TRC-062`. The rule that every one of them guards is the
contract of the change: the guard never allows a call that the earlier guard
refused, unless the call holds only harmless text. Each scenario runs the real
`hooks/pre-tool.sh` on the rows of `tests/approval_guard_cases.py` that pair with
it: the refused rows are the bypasses (each is refused by the installed hook), and
the allowed rows are the ordinary calls that must keep passing.

| Scenario | The route it closes |
|---|---|
| `TRC-057` | text inside `$(...)`, backticks or `<(...)` |
| `TRC-058` | a text sink that reads a list of files from its input |
| `TRC-059` | a backslash and newline in a quoted heredoc body or a comment |
| `TRC-060` | the heredoc of a `gh` command that runs a shell (`gh alias import -`) |
| `TRC-061` | a script written and run in one call, in the shapes that can be followed |
| `TRC-062` | `rg --files`, `chmod` and `git mv` or `git rm` of the prompt hook script, a brace glob |
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import (build_world, controls_for, drop_world,  # noqa: E402
                                  payload, refused_for, run_hook, verdict)


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


def _verdicts(world, rows, want):
    """The rows whose verdict through the real hook is not what the row wants."""
    found = []
    for case in rows:
        body = payload(case, home=world.home, project=world.project, transcript=world.transcript)
        got = verdict(run_hook(world, body))
        if got != want(case):
            found.append(f"{case.id} {case.command or case.tool_input!r}: wanted {want(case)}, "
                         f"got {got}")
    return found


def _check(world, twin, minimum):
    refused, allowed = refused_for(twin), controls_for(twin)
    assert len(refused) >= minimum, f"{twin} has {len(refused)} refused rows, wanted {minimum}"
    found = _verdicts(world, refused, lambda case: case.code)
    found += _verdicts(world, allowed, lambda case: "allowed")
    assert not found, "\n".join(found)


def test_trc_057_text_inside_a_substitution_is_judged_unless_it_is_a_message(world):
    _check(world, "TRC-057", 20)


def test_trc_058_a_command_that_reads_a_list_of_files_is_no_sink_for_text(world):
    _check(world, "TRC-058", 12)


def test_trc_059_a_quoted_heredoc_and_a_comment_keep_their_line_ends(world):
    _check(world, "TRC-059", 8)


def test_trc_060_the_heredoc_of_gh_is_text_only_for_issue_pr_and_release(world):
    _check(world, "TRC-060", 5)


def test_trc_061_a_script_written_and_run_in_one_call_is_followed(world):
    _check(world, "TRC-061", 20)


def test_trc_062_a_search_listing_a_chmod_a_git_move_and_a_brace_glob(world):
    _check(world, "TRC-062", 12)
