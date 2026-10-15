#!/usr/bin/env python3
# =============================================================================
# compass_pkg.release_notes - `compass release notes --since <ref>`
# =============================================================================
#
# DEPENDENCY: standard library (argparse, os, re, subprocess); compass_pkg.core,
# record, rival_names, shipped_issues. It must not import compass_pkg.flow or
# the manifest cache module: this verb reads the records directly and writes
# nothing.
# =============================================================================
"""List the issues completed since a git reference, with their release lines.

The output is meant to be pasted into public release text, so it is a read:
it writes no file, runs no git command that writes, and prints a rival name
as its code when the project keeps a names key.

An issue is placed against the reference by the two-part rule of the issue
records' decision (ADR-034). A squash merge leaves an issue's `land_commit`
off the branch, so reachability alone would drop it. The living spec
committed at each side says what that side holds.
"""
from __future__ import annotations

import os
import re
import subprocess

from compass_pkg import record, rival_names, shipped_issues
from compass_pkg.core import CompassError, find_compass_dir

NO_LINE = "No release line recorded."

# A land commit is a hexadecimal object name. Anything else, such as text that
# starts with a dash, is never handed to git.
_OBJECT_NAME = re.compile(r"^[0-9a-fA-F]{4,64}$")


def _git(project_root, *args):
    return subprocess.run(["git", "-C", project_root, *args],
                          capture_output=True, text=True)


def _check_reference(project_root, ref):
    """Refuse a reference git cannot resolve to a commit, before any output."""
    problem = CompassError(f"compass release notes: `{ref}` is not a git "
                           "reference that names a commit in this repository.")
    if not ref or ref.startswith("-"):
        raise problem
    try:
        found = _git(project_root, "rev-parse", "--verify", "-q", f"{ref}^{{commit}}")
        head = _git(project_root, "rev-parse", "--verify", "-q", "HEAD")
    except OSError as exc:
        raise CompassError(f"compass release notes: git did not run: {exc}")
    if found.returncode != 0:
        raise problem
    if head.returncode != 0:
        raise CompassError("compass release notes: this repository has no commit yet.")


def _named_at(project_root, revision):
    """The issues the living spec committed at `revision` names."""
    named = set()
    for rel in shipped_issues.LIVING_SPEC_FILES:
        shown = _git(project_root, "show", f"{revision}:./{rel}")
        if shown.returncode == 0:
            named |= shipped_issues.issues_named(shown.stdout)
    return named


def _reaches(project_root, commit, revision):
    if not isinstance(commit, str) or not _OBJECT_NAME.match(commit):
        return False
    return _git(project_root, "merge-base", "--is-ancestor", commit,
                revision).returncode == 0


def placement(project_root, ref, items):
    """Sort the completed shipping issues in `items` against `ref`.

    Returns `(listed, left_out, unplaced)`, each a list of items in the order
    given. An issue is left out when the spec at `ref` names it or `ref`
    reaches its `land_commit`. It is listed when HEAD reaches its
    `land_commit`, or the spec committed at HEAD names it. An issue placed by
    neither part is unplaced. A `land_commit` git cannot resolve counts as
    unreachable."""
    named_at_ref = _named_at(project_root, ref)
    named_at_head = _named_at(project_root, "HEAD")
    listed, left_out, unplaced = [], [], []
    for item in items:
        commit = item["issue"].get("land_commit")
        if item["slug"] in named_at_ref or _reaches(project_root, commit, ref):
            left_out.append(item)
        elif _reaches(project_root, commit, "HEAD") or item["slug"] in named_at_head:
            listed.append(item)
        else:
            unplaced.append(item)
    return listed, left_out, unplaced


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


def render(ref, listed, unplaced):
    """The output text for the placed issues."""
    blocks = []
    if not listed:
        blocks.append(f"No shipping issue completed since {ref}.")
    missing = 0
    for item in listed:
        text = shipped_issues.one_line(item["issue"].get("release_note")).strip()
        missing += 0 if text else 1
        date = item["land_timestamp"][:10]
        blocks.append(f"### {item['slug']} (completed {date})\n\n{text or NO_LINE}")
    if missing:
        blocks.append(f"{missing} of {len(listed)} issues have no release line.")
    if unplaced:
        count = len(unplaced)
        blocks.append(
            f"{_plural(count, 'completed issue', 'completed issues')} could not be "
            f"placed against {ref} (no land commit that HEAD reaches, and the "
            f"living spec at HEAD does not name {'it' if count == 1 else 'them'}).")
    return "\n\n".join(blocks) + "\n"


def cmd_release_notes(args):
    """Print the release lines of the issues completed since `--since`."""
    project_root = os.path.dirname(find_compass_dir())
    ref = args.since
    _check_reference(project_root, ref)
    shipping = [item for item in shipped_issues.completed_issues(project_root)
                if item["ships"]]
    listed, _left_out, unplaced = placement(project_root, ref, shipping)
    text = render(ref, listed, unplaced)
    # The text leaves the repository as public release text. A configured
    # names key that is missing stops the run here, before anything prints
    # (governance/decisions/2026-10-04-rival-names-never-committed.md).
    key_path = record.names_key(project_root)
    if key_path:
        text = rival_names.redact_names(text, rival_names.load_key(key_path))
    print(text, end="")
    return 0


def register(sub):
    """Add `compass release notes` to the top-level parser."""
    release = sub.add_parser(
        "release", help="what a release holds - the release lines of the issues "
                        "completed since a tag (read-only)")
    verbs = release.add_subparsers(dest="subcmd", required=True)
    notes = verbs.add_parser(
        "notes", help="list the issues completed since a git reference, each "
                      "with its release line")
    notes.add_argument(
        "--since", required=True, metavar="REF",
        help="a git tag, branch or commit: list the issues completed after it")
    notes.set_defaults(func=cmd_release_notes, output_kind="report")
