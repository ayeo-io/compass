"""Which issues a delegation covers, across git worktrees (issue
`delegation-everywhere`, group B, the scenarios that need no delegated approval).

`--on` looks an issue up in every worktree that `git worktree list` names, and
the delegation is written to the one common store in the main checkout.

Scenario ids: `TRC-020` to `TRC-032`, `TRC-095` and `TRC-096`. Each test name
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


# --- a delegated approval across worktrees -------------------------------------------------

def _linked(tmp_path, slug="wt-issue", generation=None):
    from delegation_support import copy_issue
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    copy_issue(top, work, slug, generation)
    return top, work


def _approve(cwd, slug, agent="compass:architect", session="sess-S"):
    from approval_support import CHECK
    from delegation_support import delegated
    return delegated(cwd, agent, "--check", CHECK, "--scope", "s", "--issue", slug,
                     session=session)


def _last(task_dir):
    import yaml
    body = yaml.safe_load((Path(task_dir) / "manifest.yml").read_text(encoding="utf-8"))
    return body["evidence"][-1]


def test_TRC_020_with_no_on_an_issue_created_after_the_delegation_is_covered(tmp_path):
    from delegation_support import copy_issue
    top = repo(tmp_path)
    work = add_worktree(top, "w")
    assert not type_(top, "", session="sess-S").block
    new = copy_issue(top, work, "new-issue")
    code, out, err = _approve(work, "new-issue")
    assert code == 0, out + err
    assert _last(new)["delegation"] == "DL-1"


def test_TRC_021_with_no_on_an_issue_at_a_later_generation_is_still_covered(tmp_path):
    from approval_support import task_dir
    from delegation_support import set_generation
    top = repo(tmp_path)
    assert not type_(top, "", session="sess-S").block
    set_generation(task_dir(top), 3)
    code, out, err = _approve(top, SLUG, agent="main")
    assert code == 0, out + err
    assert _last(task_dir(top))["delegation"] == "DL-1"


def test_TRC_026_on_still_narrows_the_delegation_to_the_named_issues(tmp_path):
    top, work = _linked(tmp_path)
    assert not type_(top, f"--on {SLUG}", session="sess-S").block
    code, out, err = _approve(work, "wt-issue")
    assert code != 0 and f"DL-1 covers {SLUG}, not wt-issue" in out + err, out + err


def test_TRC_027_on_still_binds_each_issue_to_its_generation(tmp_path):
    from delegation_support import set_generation
    top, work = _linked(tmp_path, generation=4)
    assert not type_(top, "--on wt-issue", session="sess-S").block
    wt = work / ".compass" / "work" / "wt-issue"
    set_generation(wt, 5)
    code, out, err = _approve(work, "wt-issue")
    assert code != 0, out + err
    assert "DL-1 covers wt-issue at generation 4, and it is at generation 5" in out + err


def test_TRC_095_an_issue_named_with_on_that_is_later_copied_into_a_second(tmp_path):
    from delegation_support import copy_issue, evidence_count
    top, work = _linked(tmp_path)
    assert not type_(top, "--on wt-issue", session="sess-S").block
    copy_issue(top, top, "wt-issue")
    wt = work / ".compass" / "work" / "wt-issue"
    count = evidence_count(wt)
    code, out, err = _approve(work, "wt-issue")
    assert code != 0, out + err
    assert str(top / ".compass" / "work" / "wt-issue") in out + err
    assert str(wt) in out + err or os.path.relpath(wt, work) in out + err
    assert evidence_count(wt) == count


def test_TRC_096_a_delegated_approval_on_an_issue_that_two_worktrees_hold_is_refused(
        tmp_path):
    from delegation_support import copy_issue
    top, work = _linked(tmp_path)
    assert not type_(top, "", session="sess-S").block
    copy_issue(top, top, "wt-issue")
    code, out, err = _approve(work, "wt-issue")
    assert code != 0, out + err
    assert str(top / ".compass" / "work" / "wt-issue") in out + err
    held = work / ".compass" / "work" / "wt-issue"
    assert str(held) in out + err or os.path.relpath(held, work) in out + err
    assert delegations(top)["DL-1"]["uses"] == 0
