"""Group B and the request-path scenarios of group F of issue
`hooks-stop-refusing-harmless-work`: a request folder and the prompt hook
script may be listed or named, never read, written, entered or run, and an
exemption never holds inside a pipe, a substitution or an option that carries a
path.

Scenarios: `TRC-013` to `TRC-016` and `TRC-037` to `TRC-043`. Every call runs the real
`hooks/pre-tool.sh` in a temporary Compass project with issue `issue-a`.

Red before the change: `TRC-013` and `TRC-015`, because the guard refuses any
command that holds the folder or script name. Green before the change, kept as
regression guards: `TRC-014`, `TRC-016` and `TRC-037` to `TRC-043`. The twins pass
today because the guard refuses all of them; they must still pass when the
reader judges words and the exemptions open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import (REQ, bash_event, build_world, controls_for,  # noqa: E402
                                  drop_world, misses)


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


def _refused(world, commands):
    found = misses(world, [bash_event(world, c) for c in commands], REQ)
    assert not found, "\n".join(found)


def _allowed(world, scenario):
    rows = controls_for(scenario)
    assert rows, f"the table holds no control for {scenario}"
    found = misses(world, [bash_event(world, c.command) for c in rows], "allowed")
    assert not found, "\n".join(found)


def test_trc_013_a_listing_of_a_request_folder_is_not_refused(world):
    _allowed(world, "TRC-013")


def test_trc_014_reading_writing_copying_or_entering_a_request_folder_is_still_refused(world):
    _refused(world, [
        "cat {request}",
        "head -3 {request}",
        "cat < {request}",
        "echo x > {request}",
        "cp /tmp/a {request}",
        "sed -i '' 's/a/b/' {request}",
        "cd .compass/work/issue-a/approval-requests",
        "rm -r .compass/work/issue-a/approval-requests",
    ])


def test_trc_015_the_prompt_hook_script_named_but_not_run_is_not_refused(world):
    _allowed(world, "TRC-015")


def test_trc_016_running_the_prompt_hook_script_or_copying_it_is_still_refused(world):
    _refused(world, [
        "bash hooks/prompt-approval.sh < event.json",
        "echo '{}' | hooks/prompt-approval.sh",
        "./hooks/prompt-approval.sh",
        'sh -c "hooks/prompt-approval.sh < event.json"',
        "source hooks/prompt-approval.sh",
        "cp hooks/prompt-approval.sh /tmp/p.sh",
        "git -c alias.x='!hooks/prompt-approval.sh' x",
    ])


def test_trc_037_an_exempt_listing_in_a_pipe_is_judged_without_the_exemption(world):
    _refused(world, [
        "ls -d .compass/work/issue-a/approval-requests/pending/* | xargs cat",
        "wc -l {request} | cat",
        "stat {request} | sh",
        "cat | ls .compass/work/issue-a/approval-requests",
    ])


def test_trc_038_an_exempt_listing_inside_a_substitution_is_judged_without_the_exemption(world):
    _refused(world, [
        "cat $(ls -d .compass/work/issue-a/approval-requests/pending/*)",
        "cat $(<{request})",
        "echo $(wc -l {request})",
        'echo "$(ls .compass/work/issue-a/approval-requests)"',
    ])


def test_trc_039_an_exempt_listing_inside_backticks_is_judged_without_the_exemption(world):
    _refused(world, [
        "cat `ls -d .compass/work/issue-a/approval-requests/pending/*`",
        "cat `<{request}`",
        "echo `stat {request}`",
    ])


def test_trc_040_an_exempt_listing_inside_a_process_substitution_is_judged_without_the_exemption(
        world):
    _refused(world, [
        "echo <(cat {request})",
        "cat <(ls -d .compass/work/issue-a/approval-requests/pending/*)",
        "diff <(wc -l {request}) /dev/null",
    ])


def test_trc_041_a_search_option_that_takes_a_path_makes_its_value_a_path(world):
    _refused(world, [
        "grep -f {request} x",
        "rg --file {request} x",
        "grep -e x {request}",
        "grep -rnf {request} x",
        "grep --file={request} x",
    ])


def test_trc_042_an_exempt_command_given_an_option_that_carries_a_path_is_refused(world):
    _refused(world, [
        "wc --files0-from={request}",
        "wc --files0-from {request}",
        "du --files0-from={request}",
        "wc -l --files0-from=- < {request}",
    ])


def test_trc_043_the_prompt_hook_script_is_allowed_only_as_a_bare_argument_of_a_reader(world):
    _refused(world, [
        "git log --output=hooks/prompt-approval.sh --format=%B -1",
        "git diff --output=hooks/prompt-approval.sh",
        "git show --output=hooks/prompt-approval.sh",
        "rg --pre hooks/prompt-approval.sh x .",
        "GIT_EXTERNAL_DIFF=hooks/prompt-approval.sh git diff",
        "grep x > hooks/prompt-approval.sh",
        "cat hooks/prompt-approval.sh | bash",
        "git log --exec=hooks/prompt-approval.sh",
    ])


def test_text_piped_to_a_stage_that_can_write_it_is_judged(world):
    """Text that names a protected word and pipes into `git`, `gh`, `compass` or an
    unknown command stays refused: those stages can turn piped text into a write
    (`git commit -F -`, `gh api --input -`), so only a short list of readers
    (`tee`, `cat`, `head`, `tail`, `wc`, `sort`, `uniq`, `cut`, `tr`, `less`,
    `more`, `grep`, `egrep`, `fgrep`, `rg`, `diff`, `pbcopy`) lets text pass."""
    _refused(world, [
        'echo "see approval-requests" | git commit -F -',
        'echo "see approval-requests" | gh api --input -',
        'printf "see approval-requests" | compass quick-fix start --note -',
        'echo "see approval-requests" | mystery',
    ])
