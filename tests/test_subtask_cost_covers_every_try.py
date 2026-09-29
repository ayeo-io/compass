"""A subtask's recorded cost covers every try.

`compass issue subtask update --cost N` replaced the subtask's `cost`, so a
subtask sent back for another try kept only the last try's tokens, and a
run record had to sum the tries by hand. Each try's cost is now kept in
`costs`, keyed by the try, and `cost` is their total.

`--cost` keyed a cost by the subtask's current `attempts` count, so a cost
recorded in the same call as the flag that opens a new try landed on the
try just opened, not the try that call was closing out - a real run lost a
try's cost this way. `--try N` now names the try a cost belongs to; without
it, a cost in a call that also opens a new try belongs to the try before
the new one, and a try beyond what has been dispatched is refused.

Scenario ids: SCT-1 and SCT-2, in the delivery approach of issue
`subtask-cost-keeps-last-try-only`; EGB-8, in the delivery approach of issue
`eval-gaps-after-d33`.
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


def test_egb_8_a_cost_alongside_attempt_belongs_to_the_try_before_it(repo):
    _add(repo)
    assert _cli(repo, "update", "S1", "--attempt", "--cost", "50").returncode == 0
    s = _subtasks(repo)["S1"]
    assert s["attempts"] == 2
    assert s["costs"] == {"1": 50}
    assert s["cost"] == 50


def test_egb_8_try_names_the_cost_explicitly(repo):
    _add(repo)
    assert _cli(repo, "update", "S1", "--cost", "100", "--try", "1").returncode == 0
    assert _cli(repo, "update", "S1", "--attempt").returncode == 0
    assert _cli(repo, "update", "S1", "--cost", "60", "--try", "2").returncode == 0
    s = _subtasks(repo)["S1"]
    assert s["costs"] == {"1": 100, "2": 60}
    assert s["cost"] == 160


def test_egb_8_a_named_try_replaces_only_that_trys_figure(repo):
    _add(repo)
    _cli(repo, "update", "S1", "--cost", "100", "--try", "1")
    _cli(repo, "update", "S1", "--attempt")
    _cli(repo, "update", "S1", "--cost", "30", "--try", "2")
    result = _cli(repo, "update", "S1", "--cost", "50", "--try", "1")
    assert result.returncode == 0, result.stderr
    s = _subtasks(repo)["S1"]
    assert s["costs"] == {"1": 50, "2": 30}
    assert s["cost"] == 80


def test_egb_8_a_cost_for_a_try_beyond_attempts_is_refused(repo):
    _add(repo)
    result = _cli(repo, "update", "S1", "--cost", "100", "--try", "5")
    assert result.returncode != 0
    assert not _subtasks(repo)["S1"].get("costs")


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
