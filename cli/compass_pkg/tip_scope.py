# compass_pkg.tip_scope - the paths an issue's own commits at the branch tip changed
"""What `compass ship-commit --issue` judges when it lands at HEAD with
nothing staged.

The tip of a branch is not always the issue's own commit. It can be a commit
that only re-derives the living spec, or a merge of the base branch. This
module walks the first parent from HEAD and returns the paths the issue's own
commits changed, so the scope check judges those and not what a merge of the
base brought in.
"""
# DEPENDENCY: standard library (subprocess); compass_pkg.flow
# (LIVING_SPEC_FILES), compass_pkg.spec_refresh (DEFAULT_BASE).
from __future__ import annotations

import subprocess


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _base_ref(cwd):
    """The base branch whose commits a merge may bring in without them
    counting as the issue's: the remote's default branch when git knows
    it, otherwise the base `compass spec sync` merges. None when neither
    resolves, such as in a clone with no remote."""
    from compass_pkg.spec_refresh import DEFAULT_BASE
    named = _git(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"],
                 cwd).stdout.strip()
    for ref in (named, DEFAULT_BASE):
        if ref and _git(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"],
                        cwd).returncode == 0:
            return ref
    return None


def tip_own_paths(cwd):
    """The paths the issue's own commits at the branch tip changed, walking
    the first parent from HEAD, and a note when a merge was judged in full
    because the base branch could not be found.

    - A commit that changes only the living spec is passed over: `ship-commit`
      and `compass spec sync` write it, so it is no issue's change. In a
      commit judged in full, the living spec stays: a hand edit of it is the
      issue's change and the scope check judges it.
    - A merge whose merged-in commits are all on the base branch, such as a
      merge of `origin/main`, counts only the paths it changed against every
      parent, which is its conflict resolution. The living spec is left out
      of that resolution.
    - Any other merge, such as a multiagent integration merge, is judged in
      full and ends the walk, whatever commit the merged branch started
      from. So is every merge when the base branch cannot be resolved.
    - The walk stops at the first other commit, which is the issue's newest
      own commit and is judged in full, or at a commit a merged-in branch
      already holds, which was the base of that branch and not the issue's.
    """
    from compass_pkg.flow import LIVING_SPEC_FILES

    def names(*rng):
        return {n for n in _git(["diff", "--name-only", "-z", *rng],
                                cwd).stdout.split("\0") if n}

    base = _base_ref(cwd)
    note = None
    paths, sides, commit = set(), [], "HEAD"
    while True:
        parents = _git(["rev-parse", f"{commit}^@"], cwd).stdout.split()
        if not parents:
            break
        if any(_git(["merge-base", "--is-ancestor", commit, side],
                    cwd).returncode == 0 for side in sides):
            break
        changed = [names(parent, commit) for parent in parents]
        if len(parents) > 1 and (base is None or any(
                _git(["rev-list", "-n", "1", side, f"^{parents[0]}",
                      f"^{base}"], cwd).stdout.strip()
                for side in parents[1:])):
            # A merged-in commit is not on the base, so what the merge
            # brought may be the work being landed: it is judged in full.
            if base is None:
                note = ("the base branch (origin/HEAD or origin/main) could "
                        "not be found, so the merge at the tip was judged "
                        "in full, including what it merged in")
            paths |= changed[0]
            break
        if len(parents) > 1:
            # A conflict resolution of the living spec is derived output.
            paths |= set.intersection(*changed) - set(LIVING_SPEC_FILES)
            sides += parents[1:]
            commit = parents[0]
            continue
        if changed[0] and changed[0] <= set(LIVING_SPEC_FILES):
            commit = parents[0]
            continue
        paths |= changed[0]
        break
    return sorted(paths), note
