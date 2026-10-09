#!/usr/bin/env python3
"""`landed_by` - an issue whose work was done through a different issue.

Kept apart from `checks.py`, which has a 1200-line cap (`test_trc_a2`). This
block is cohesive: one constant, one reader, one predicate and one check.

DEPENDENCY: none beyond the standard library and this package. It reads a manifest
through `core.load_yaml`, which is where the bundled PyYAML is resolved; nothing
here imports yaml directly. Stated rather than omitted so the dependency scan
covers this file instead of listing it as unmarked.
"""
from __future__ import annotations

import os

from compass_pkg import status_words
from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import CompassError, load_yaml, normalize_spine


# =============================================================================
# `landed_by` - an issue whose work was done through a different issue
# =============================================================================
# Use `landed_by:` when the work was delivered through another issue or a
# commit. Marking such an issue `abandoned` misleads `compass retro`, which
# reads the status to judge whether assessment is over- or under-sizing the
# process.
#
# `landed_by:` MOVES the claim; it does not waive it. The named issue must
# exist, must be landed, must carry a record of its own, and must name this
# issue back in `delivered:`. Relaxing a guardrail check is safe only when
# all four conditions are checked.

#: The checks `landed_by` stands down, named rather than derived.
#:
#: Measured: these are exactly the four checks an empty-record landed issue
#: fails. A DERIVED set - "relax whatever fails" - would go wrong the moment
#: a check is added, silently widening the relaxation. A named list fails
#: loudly when the set changes, which is the moment to think about it.
#:
#: What is NOT here is deliberate. `dashboard-current` still applies: the
#: review page must match the manifest whatever the manifest says. `dod-evidence-typed`
#: and `backfills-paid` still apply: an unchecked box or an owed follow-up is
#: this issue's own business regardless of who did the work.
LANDED_BY_RELAXES = (
    "scenarios-have-tests",
    "suite-passed",
    "scenario-has-id-and-intent",
    # Its complaint is "no gates in manifest.yml - has the delivery approach
    # been evaluated?", which is the same class as the three above: this
    # issue never went through the verify stage, because a different one did.
    #
    # Measure this set with `compass check --verbose`: the default view
    # truncates after three failures.
    "gate-evidence-present",
)


def _sibling_spine(task_dir, slug):
    """Another issue's manifest, read from the same work root."""
    path = os.path.join(os.path.dirname(os.path.abspath(task_dir)),
                        slug, "manifest.yml")
    if not os.path.isfile(path):
        return None
    try:
        return normalize_spine(load_yaml(path) or {})
    except CompassError:
        return None


def _git_commit_subject(sha, cwd):
    """The subject line of `sha`, or None when it cannot be resolved.

    None means "could not look" as well as "not there" - the caller
    distinguishes them by asking git whether it is usable at all. A check
    that clears because it could not look must not be counted as a pass.
    """
    import subprocess

    try:
        r = subprocess.run(["git", "log", "-1", "--format=%s", sha],
                           cwd=cwd, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _git_is_usable(cwd):
    import subprocess

    try:
        r = subprocess.run(["git", "rev-parse", "--git-dir"], cwd=cwd,
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def _entries(value):
    """`landed_by` as a list of dicts, whatever shape it was written in.

    A bare string is read as one issue entry. That is not politeness - the
    field shipped as a single slug and an adopter may have written one.
    """
    if not value:
        return []
    if isinstance(value, str):
        return [{"issue": value.strip()}] if value.strip() else []
    if isinstance(value, dict):
        return [value]
    out = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append({"issue": item.strip()})
        elif isinstance(item, dict):
            out.append(item)
    return out


def _issue_entry_holds(entry, task_dir, mine):
    slug = str(entry.get("issue") or "").strip()
    other = _sibling_spine(task_dir, slug)
    if other is None:
        return "`landed_by` names issue %r, and there is no such issue in " \
               "this work root" % slug
    if not status_words.is_completed(other):
        return ("`landed_by` names issue %r, which has not landed (it is %r). "
                "A pointer at an unfinished issue is a promise, not a record."
                % (slug, other.get("status") or "unset"))
    if not (other.get("scenarios") or []):
        return ("`landed_by` names issue %r, which carries no record of its "
                "own - so neither issue has one, and the claim points at "
                "nothing" % slug)
    delivered = [str(x).strip() for x in (other.get("delivered") or [])]
    if mine not in delivered:
        return ("`landed_by` names issue %r, and that issue does not name this "
                "one in its `delivered:` list - so the link is one-way and "
                "anything could claim it" % slug)
    return None


def _commit_entry_holds(entry, project_root, git_reader):
    sha = str(entry.get("commit") or "").strip()
    what = str(entry.get("what") or "").strip()
    if len(what.split()) < 3:
        return ("`landed_by` names commit %s and does not say what it did. A "
                "bare sha is a reference nobody can act on - add `what:` "
                "saying what changed." % (sha[:12] or "(none)"))
    if git_reader(sha, project_root) is not None:
        return None
    if not _git_is_usable(project_root):
        # Declines rather than fails: unreachable is not the same as wrong.
        return ("could not reach git to resolve commit %s, so this claim is "
                "unverified here" % sha[:12])
    return ("`landed_by` names commit %s, and git could not find it in this "
            "repository" % sha[:12])


def landed_by_holds(task, task_dir, git_reader=None):
    """Does this issue's `landed_by` resolve? Returns (ok, detail).

    (False, None) means there is nothing to judge - distinct from a claim that
    fails, so a caller can tell "not claimed" from "claimed and wrong".

    `landed_by` is a LIST, and an entry names either another issue or a commit.
    The single-slug form the field shipped with is read as one issue entry.

    It is a list because work can be delivered by another issue, by a commit
    with no issue, or by several issues.

    `git_reader` is injected so the commit form is testable without depending
    on this repository's history.
    """
    entries = _entries(task.get("landed_by"))
    if not entries:
        return False, None

    if not status_words.is_completed(task):
        return False, (
            "`landed_by` has no effect at status %r - it only applies to a "
            "landed issue, and nothing is relaxed here"
            % status_words.stored(task))

    mine = str(task.get("task") or os.path.basename(os.path.abspath(task_dir)))
    project_root = os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(task_dir))))
    reader = git_reader or _git_commit_subject

    problems, described = [], []
    for entry in entries:
        if entry.get("issue"):
            problem = _issue_entry_holds(entry, task_dir, mine)
            described.append("issue %r" % entry["issue"])
        elif entry.get("commit"):
            problem = _commit_entry_holds(entry, project_root, reader)
            described.append("commit %s" % str(entry["commit"])[:12])
        else:
            problem = ("a `landed_by` entry names neither an issue nor a "
                       "commit: %r" % (entry,))
        if problem:
            problems.append(problem)

    if problems:
        return False, "; ".join(problems)
    return True, "the work was delivered by %s" % ", ".join(described)


def _check_landed_by_resolves(task, task_dir):
    """The pointer is a claim, so it is checked like one."""
    if not str(task.get("landed_by") or "").strip():
        return NOTHING_TO_CHECK, "no `landed_by` pointer on this issue"
    ok, detail = landed_by_holds(task, task_dir)
    if ok:
        return True, detail
    if detail is None:                       # unreachable; kept explicit
        return NOTHING_TO_CHECK, "no `landed_by` pointer on this issue"
    if not status_words.is_completed(task):
        # Inert rather than wrong: say so and pass, so nobody assumes the
        # field is doing something it is not.
        return NOTHING_TO_CHECK, detail
    return False, detail
