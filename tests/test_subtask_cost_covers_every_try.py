"""A subtask's recorded cost covers every try.

`compass issue subtask update --cost N` replaced the subtask's `cost`, so a
subtask sent back for another try kept only the last try's tokens, and a
run record had to sum the tries by hand. Each try's cost is now kept in
`costs`, keyed by the try, and `cost` is their total.

Scenario ids: SCT-1 and SCT-2, in the delivery approach of issue
`subtask-cost-keeps-last-try-only`.
"""
from __future__ import annotations

from test_subtask_record import _add, _cli, _subtasks, repo  # noqa: F401


def test_sct_1_two_tries_keep_both_costs_and_their_total(repo):
    _add(repo)
    assert _cli(repo, "update", "S1", "--cost", "100").returncode == 0
    assert _cli(repo, "update", "S1", "--attempt").returncode == 0
    assert _cli(repo, "update", "S1", "--cost", "50").returncode == 0
    s = _subtasks(repo)["S1"]
    assert s["cost"] == 150
    assert sorted(s["costs"].values()) == [50, 100]


def test_sct_2_a_second_cost_for_the_same_try_replaces_it(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--cost", "100")
    _cli(repo, "update", "S1", "--cost", "120")
    s = _subtasks(repo)["S1"]
    assert s["cost"] == 120
    assert list(s["costs"].values()) == [120]


def test_sct_1_a_manifest_with_costs_lints(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--cost", "100")
    import subprocess
    import sys
    from test_subtask_record import CLI, SLUG
    lint = subprocess.run([sys.executable, str(CLI), "issue", "lint",
                           "--issue", SLUG], cwd=repo, capture_output=True,
                          text=True)
    assert lint.returncode == 0, lint.stdout + lint.stderr
