"""The error `compass ship-commit` raises when its commit did not move HEAD.

The error opens with the lines git printed, because git knows why it refused
(no author identity, a failed hook, a rejected message). A guess about the
cause comes after it, and only where the guess can be true.
"""
# DEPENDENCY: standard library (os, subprocess).

import os
import subprocess

# Enough lines for the longest common refusal, the missing identity, which
# prints about ten.
_LINES_KEPT = 12


def _tail(text):
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-_LINES_KEPT:]


def _pre_commit_hook_can_run(cwd):
    """Whether `git commit` would run a pre-commit hook here.

    Asking git for the path follows `core.hooksPath` and linked worktrees. A
    file that is not marked as runnable is skipped by git, so it cannot have
    aborted the commit and is not blamed.
    """
    found = subprocess.run(["git", "rev-parse", "--git-path", "hooks/pre-commit"],
                           cwd=cwd, capture_output=True, text=True)
    if found.returncode != 0 or not found.stdout.strip():
        return False
    path = os.path.join(cwd, found.stdout.strip())
    return os.path.isfile(path) and os.access(path, os.X_OK)


def failure_message(cwd, commit, retried):
    """The text for a commit that left HEAD where it was.

    `commit` is the result of the latest `git commit` that ran, the retry's
    when there was one. `retried` says a second commit was tried.
    """
    reason = _tail(commit.stderr) + _tail(commit.stdout)
    guess = ""
    if _pre_commit_hook_can_run(cwd):
        guess = (" A pre-commit hook may be aborting the commit repeatedly; "
                 "resolve it and re-run.")
    return ("compass ship-commit: git did not commit:\n  "
            + "\n  ".join(reason or ["(git printed nothing)"])
            + "\nHEAD did not advance" + (" after a retry" if retried else "")
            + " - the land did NOT happen." + guess)
