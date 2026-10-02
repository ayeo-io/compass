#!/usr/bin/env python3
# =============================================================================
# compass_pkg.decisions - `compass decision record|list|show|check`
# =============================================================================
#
# Settled product decisions, one immutable file each, in governance/decisions/
# (ADR-027). An entry records what a named person decided; it does not argue
# it. The decider comes from git, never from an option: in a session, whoever
# passes an option is the model, and an agent never decides.
#
# DEPENDENCY: standard library only (datetime, os, re, subprocess).
# =============================================================================

import datetime
import os
import re
import subprocess

from compass_pkg.core import CompassError, find_compass_dir

LEDGER = os.path.join("governance", "decisions")
_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})-(.+)\.md")

_TEMPLATE = """# {slug}

## Decided by

{decider}

## Date

The day the decision was made, if not {today}.

## Supersedes

{supersedes}

## Decision

One settled outcome, in a sentence or two.

## Why

The reason, in the decider's words.

## Evidence

Where the decision was made: a pull request, an issue, a commit or a
document.
"""


def _project():
    return os.path.dirname(find_compass_dir())


def _git(root, *args):
    """A git command's output, or None when it fails. An argument list,
    never a shell."""
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _decider(root):
    """`compass.decidedBy`, so a person can be recorded by a handle, else
    `user.name`. Never an option or an argument."""
    for key in ("compass.decidedBy", "user.name"):
        name = _git(root, "config", key)
        if name:
            return name
    return None


def _entries(root):
    """(file name, date, slug) for each entry, newest first."""
    d = os.path.join(root, LEDGER)
    out = []
    if os.path.isdir(d):
        for name in os.listdir(d):
            m = _NAME.fullmatch(name)
            if m:
                out.append((name, m.group(1), m.group(2)))
    return sorted(out, reverse=True)


def _find(root, slug):
    return next((e for e in _entries(root) if e[2] == slug), None)


def cmd_decision_record(args):
    root = _project()
    slug = args.slug
    if not _SLUG.fullmatch(slug):
        raise CompassError(f"'{slug}' is not a slug: use lower-case words joined "
                           f"by hyphens, as one path segment.")
    if _find(root, slug):
        raise CompassError(f"an entry for '{slug}' already exists. An entry never "
                           f"changes: record a new one with --supersedes {slug}.")
    supersedes = "Nothing."
    if args.supersedes:
        old = _find(root, args.supersedes)
        if not old:
            raise CompassError(f"--supersedes names '{args.supersedes}', which has "
                               f"no entry in {LEDGER}/.")
        supersedes = f"`{LEDGER}/{old[0]}`"
    decider = _decider(root)
    if not decider:
        raise CompassError("no decider: set `git config compass.decidedBy <name>` "
                           "or `git config user.name <name>`. The ledger records "
                           "the person who decided, from git only.")
    today = datetime.date.today().isoformat()
    os.makedirs(os.path.join(root, LEDGER), exist_ok=True)
    path = os.path.join(root, LEDGER, f"{today}-{slug}.md")
    with open(path, "x", encoding="utf-8") as fh:
        fh.write(_TEMPLATE.format(slug=slug, decider=decider, today=today,
                                  supersedes=supersedes))
    print(f"compass decision record: wrote {os.path.relpath(path, root)}, decided "
          f"by {decider}. Fill in the decision, why and the evidence, then commit.")
    return 0


def _first_decision_line(text):
    part = text.split("## Decision", 1)
    if len(part) < 2:
        return ""
    for line in part[1].splitlines()[1:]:
        if line.startswith("## "):
            return ""
        if line.strip():
            return line.strip()
    return ""


def cmd_decision_list(args):
    root = _project()
    entries = _entries(root)
    if not entries:
        print(f"no entries in {LEDGER}/.")
        return 0
    for name, date, slug in entries:
        with open(os.path.join(root, LEDGER, name), encoding="utf-8") as fh:
            print(f"{date}  {slug}  {_first_decision_line(fh.read())}")
    return 0


def cmd_decision_show(args):
    root = _project()
    found = _find(root, args.slug)
    if not found:
        raise CompassError(f"no entry for '{args.slug}' in {LEDGER}/.")
    with open(os.path.join(root, LEDGER, found[0]), encoding="utf-8") as fh:
        print(fh.read(), end="")
    return 0


def history_problems(root, commit):
    """Entries at `commit` that the working tree changed or removed.

    `git diff` against the commit, run from the project root, so it matches
    git's own view: the pathspec is relative to a project in a subdirectory,
    line-ending conversion is applied before comparing, and `-z` keeps a
    non-ASCII file name unquoted. A diff that cannot run is a problem, not a
    pass.
    """
    try:
        r = subprocess.run(
            ["git", "diff", "--name-status", "-z", "--no-renames", commit,
             "--", LEDGER + "/"],
            cwd=root, capture_output=True, text=True)
    except OSError as exc:
        return [f"git diff could not run: {exc}"]
    if r.returncode != 0:
        return [f"git diff against {commit[:12]} failed: {r.stderr.strip()}"]
    fields = r.stdout.split("\0")
    problems = []
    for status, path in zip(fields[0::2], fields[1::2]):
        if status.startswith("D"):
            problems.append(f"{path} was removed")
        elif not status.startswith("A"):
            problems.append(f"{path} was changed")
    return problems


def resolve_commit(root, ref):
    """The commit id `ref` names, or None."""
    return _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def cmd_decision_check(args):
    root = _project()
    commit = resolve_commit(root, args.base)
    if not commit:
        raise CompassError(f"--base {args.base} does not name a commit in this "
                           f"repository, so nothing was checked.")
    problems = history_problems(root, commit)
    if problems:
        print(f"compass decision check: FAIL - an entry never changes; record a "
              f"new entry with --supersedes instead:")
        for p in problems:
            print(f"  {p}")
        return 1
    print(f"compass decision check: PASS - every entry at {args.base} is unchanged.")
    return 0


def register(sub):
    """Add `compass decision record|list|show|check` to the top-level parser."""
    p = sub.add_parser(
        "decision", help="record, list and check settled product decisions")
    subs = p.add_subparsers(dest="subcmd", required=True)

    rec = subs.add_parser(
        "record", help="write a new entry; the decider comes from git config")
    rec.add_argument("slug", help="lower-case words joined by hyphens")
    rec.add_argument("--supersedes", metavar="SLUG",
                     help="the entry this one replaces; the old entry is not edited")
    rec.set_defaults(func=cmd_decision_record, output_kind="hand-off")

    lst = subs.add_parser("list", help="each entry's date, slug and decision, newest first")
    lst.set_defaults(func=cmd_decision_list, output_kind="hand-off")

    sh = subs.add_parser("show", help="print one entry")
    sh.add_argument("slug")
    sh.set_defaults(func=cmd_decision_show, output_kind="hand-off")

    ch = subs.add_parser(
        "check", help="fail when an entry at a base ref was changed or removed")
    ch.add_argument("--base", required=True, metavar="REF",
                    help="the git ref whose entries must be unchanged")
    ch.set_defaults(func=cmd_decision_check, output_kind="hand-off")
