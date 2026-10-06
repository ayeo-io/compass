# compass_pkg.spec_refresh - `compass issue refresh-spec`
"""Bring a branch up to date with its base without resolving the derived
living spec by hand.

Every landing re-derives `docs/system-spec.md` and its archive, so two open
pull requests each carry their own copy, and the second to merge conflicts
on both files though nobody wrote a line of either. This merges the base,
takes the base's side of those two files only, re-derives (which keeps the
base's issues and adds the branch's own, ADR-034) and commits. A conflict in
any other file is a person's to resolve: the merge is aborted and the files
are named.
"""
# DEPENDENCY: standard library (os, subprocess); compass_pkg.core, flow.
from __future__ import annotations

import os
import subprocess

from compass_pkg.core import CompassError, find_compass_dir
from compass_pkg.flow import LIVING_SPEC_FILES, derive_system_spec


def _git(root, *args, check=False):
    proc = subprocess.run(["git", "-C", root, *args], capture_output=True,
                          text=True)
    if check and proc.returncode != 0:
        raise CompassError(f"compass issue refresh-spec: git {' '.join(args)} failed: "
                           f"{(proc.stderr or proc.stdout).strip()}")
    return proc


def refresh(root, base):
    """Merge `base` into the current branch, resolve only the derived spec,
    re-derive and commit. Returns the lines to print."""
    # A merge already under way is the person's: this command never takes
    # it over, and its `merge --abort` must never undo it.
    if _git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0:
        raise CompassError(
            "compass issue refresh-spec: a merge is already in progress; finish or "
            "abort it first. This command starts and owns its own merge.")
    if _git(root, "rev-parse", "-q", "--verify", base).returncode != 0:
        raise CompassError(
            f"compass issue refresh-spec: the base {base} does not exist here; "
            f"fetch it first (git fetch) or name another with --base.")
    dirty = _git(root, "status", "--porcelain", "--untracked-files=no").stdout
    if dirty.strip():
        raise CompassError(
            "compass issue refresh-spec: the working tree has uncommitted changes; "
            "commit or stash them first, so the merge holds only the base.")

    def abort(why):
        _git(root, "merge", "--abort")
        raise CompassError(f"compass issue refresh-spec: {why} The merge was aborted "
                           f"and the branch is as it was.")

    said = []
    merge = _git(root, "merge", "--no-edit", base)
    if merge.returncode != 0:
        conflicted = [p for p in _git(root, "diff", "--name-only",
                                      "--diff-filter=U").stdout.splitlines() if p]
        others = [p for p in conflicted if p not in LIVING_SPEC_FILES]
        if others:
            abort(f"merging {base} conflicts in {', '.join(others)}; those are "
                  f"a person's to resolve.")
        if not conflicted:
            abort(f"merging {base} failed: "
                  f"{(merge.stderr or merge.stdout).strip()}.")
        for rel in conflicted:
            for step in (("checkout", "--theirs", "--", rel), ("add", "--", rel)):
                done = _git(root, *step)
                if done.returncode != 0:
                    abort(f"could not take {base}'s side of {rel}: "
                          f"{(done.stderr or done.stdout).strip()}.")
        done = _git(root, "commit", "--no-edit")
        if done.returncode != 0:
            abort(f"committing the merge failed: "
                  f"{(done.stderr or done.stdout).strip()}.")
        said.append(f"merged {base}; took its side of {', '.join(conflicted)}")
    elif "Already up to date" in merge.stdout:
        said.append(f"already up to date with {base}")
    else:
        said.append(f"merged {base}")
    try:
        derive_system_spec(root)
    except CompassError as exc:
        raise CompassError(
            f"compass issue refresh-spec: the merge of {base} is committed, but "
            f"re-deriving the living spec failed: {exc}\nFix that, then run "
            f"`compass issue refresh-spec --base {base}` again; the merge is not "
            f"repeated.")
    present = [rel for rel in LIVING_SPEC_FILES
               if os.path.exists(os.path.join(root, rel))]
    if _git(root, "status", "--porcelain", "--", *present).stdout.strip():
        _git(root, "add", "--", *present, check=True)
        _git(root, "commit", "-m",
             f"Re-derive the living spec after merging {base}", check=True)
        said.append("re-derived the living spec and committed it")
    else:
        said.append("the living spec was already current")
    return said


def cmd_spec_refresh(args):
    root = os.path.dirname(find_compass_dir())
    lines = refresh(root, args.base)
    print("compass issue refresh-spec: " + lines[0] + ".")
    for line in lines[1:]:
        print(f"  {line}")
    return 0


def register(issue_subs):
    """Add `compass issue refresh-spec` to the `issue` group. Not a top-level
    verb: Compass grows by groups, and the spec is derived from issues."""
    r = issue_subs.add_parser(
        "refresh-spec", help="merge a base branch and re-derive the living spec",
        description="Merge a base branch into this one, take the base's side "
                    "where only the derived living spec conflicts, re-derive "
                    "it and commit. Any other conflict aborts the merge.")
    r.add_argument("--base", default="origin/main",
                   help="the branch to merge (default: origin/main)")
    r.set_defaults(func=cmd_spec_refresh, output_kind="hand-off")
