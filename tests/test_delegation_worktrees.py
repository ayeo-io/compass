"""Which issues a delegation covers, across git worktrees (issue
`delegation-everywhere`, group B, the scenarios that need no delegated approval).

`--on` looks an issue up in every worktree that `git worktree list` names, and
the delegation is written to the one common store in the main checkout.

Scenario ids: `TRC-022` to `TRC-025` and `TRC-028` to `TRC-032`. Each test name
starts with its scenario id.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import SLUG, project  # noqa: E402
from delegation_support import (add_issue, add_worktree, delegations,  # noqa: E402
                                project_of, repo, type_)


def _refused(root, args, *needles, absent=()):
    result = type_(root, args)
    assert result.block, (args, result)
    for needle in needles:
        assert needle in result.message, (needle, result.message)
    for needle in absent:
        assert needle not in result.message, (needle, result.message)
    assert not delegations(root), delegations(root)
    return result


def test_TRC_022_on_accepts_an_issue_that_only_another_worktree_holds(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", generation=4)
    result = type_(top, "--on wt-issue")
    assert not result.block, result
    assert delegations(top)["DL-1"]["issues"] == {"wt-issue": 4}


def test_TRC_023_on_accepts_issues_from_two_worktrees_in_one_list(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(top, SLUG, generation=2)
    add_issue(work, "wt-issue", generation=4)
    result = type_(top, f"--on {SLUG},wt-issue")
    assert not result.block, result
    assert delegations(top)["DL-1"]["issues"] == {SLUG: 2, "wt-issue": 4}


def test_TRC_024_on_refuses_an_issue_no_worktree_holds_and_names_the_worktrees_searched(
        tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue")
    _refused(top, "--on gone-issue", "'gone-issue'", str(top / ".compass" / "work"),
             str(work / ".compass" / "work"), absent=("is not an issue in this project",))


def test_TRC_025_on_refuses_an_issue_that_two_worktrees_hold_and_names_both(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(top, "wt-issue")
    add_issue(work, "wt-issue")
    _refused(top, "--on wt-issue", str(top / ".compass" / "work" / "wt-issue"),
             str(work / ".compass" / "work" / "wt-issue"))


@pytest.mark.parametrize("issues", ["..", "main-issue/../x", "main-issue,,wt-issue",
                                    "../wt-1/wt-issue"])
def test_TRC_028_on_refuses_a_name_that_is_not_one_folder_name(tmp_path, issues):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(top, "main-issue")
    add_issue(work, "wt-issue")
    _refused(top, f"--on {issues}")


def test_TRC_029_an_issue_folder_that_is_a_symbolic_link_out_of_its_worktree(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    outside = add_issue(tmp_path / "outside", "link-issue")
    link = work / ".compass" / "work" / "link-issue"
    link.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(outside, link)
    _refused(top, "--on link-issue", "'link-issue'")


def test_TRC_030_a_worktree_whose_folder_is_missing_is_skipped(tmp_path):
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    add_issue(work, "wt-issue", generation=3)
    gone = add_worktree(top, "gonetree")
    shutil.rmtree(gone)
    result = type_(top, "--on wt-issue")
    assert not result.block, result
    assert delegations(top)["DL-1"]["issues"] == {"wt-issue": 3}
    assert "gonetree" not in result.message


def test_TRC_031_when_the_worktrees_cannot_be_listed_only_this_checkout_is_searched(
        tmp_path):
    root = project(tmp_path)
    _refused(root, "--on gone-issue", "'gone-issue'", "worktrees could not be listed",
             "only this checkout was searched",
             absent=("is not an issue in this project",))


def test_TRC_032_a_project_in_a_subfolder_of_the_repository_is_found_at_the_same_path(
        tmp_path):
    top = repo(tmp_path, sub="app")
    work = add_worktree(top, "w")
    add_issue(project_of(work, "app"), "wt-issue", generation=2)
    session_root = project_of(top, "app")
    result = type_(session_root, "--on wt-issue")
    assert not result.block, result
    found = delegations(session_root)
    assert found["DL-1"]["issues"] == {"wt-issue": 2}
    assert not delegations(top)
