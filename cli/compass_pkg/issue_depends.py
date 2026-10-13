# compass_pkg.issue_depends - `compass issue depends add|remove` and the dependency lines
"""The writers of `depends_on`, and the lines other commands print about it.

`compass issue depends add` and `compass issue depends remove` are the only
commands that write the key (ADR-062). `add` refuses a cycle, found by
following `depends_on` through every readable manifest of this checkout with a
visited set (`find_cycle`). `compass issue lint` reports each dependency fault
through `lint_errors`, and `ship-commit` names the issues that were waiting
for the one it landed through `waiting_lines`.

What a dependency means - whether it is met, and when it blocks - is judged in
`lifecycle`, never here, so this module and every reader agree.
"""
# DEPENDENCY: compass_pkg.lifecycle (the derivation), status_words, core,
# issue_layout and terminal.
from __future__ import annotations

import os
import sys

from compass_pkg import lifecycle, status_words
from compass_pkg.core import CompassError, load_manifest, resolve_issue_dir, save_manifest
from compass_pkg.issue_layout import is_one_segment
from compass_pkg.terminal import say

ADD = "compass issue depends add"
REMOVE = "compass issue depends remove"


def _values():
    return ", ".join(lifecycle.UNTIL_VALUES)


def missing_line(slug):
    """The finding for a dependency on an issue this checkout does not hold."""
    return ("`depends_on`: %s: depends on an issue that does not exist in this checkout"
            % slug)


def find_cycle(start, target, read, first=None, unread=None):
    """The path `[start, ..., target]` along `depends_on` entries, or None.

    The walk follows each issue's well-formed entries through `read`, and
    visits an issue once, so it ends on any graph. `first` names the issues to
    follow from `start` instead of reading `start` (the entry about to be
    written). `unread`, when given, collects `(slug, Unread)` for each issue
    the walk could not read; the walk goes on without it."""
    if first is None:
        first = _next_slugs(start, read, unread)
    visited = {start}
    stack = [(slug, [start, slug]) for slug in reversed(first)]
    while stack:
        slug, path = stack.pop()
        if slug == target:
            return path
        if slug in visited:
            continue
        visited.add(slug)
        for nxt in reversed(_next_slugs(slug, read, unread)):
            stack.append((nxt, path + [nxt]))
    return None


def _next_slugs(slug, read, unread):
    try:
        manifest, _task_dir = read(slug)
    except lifecycle.Unread as exc:
        if unread is not None:
            unread.append((slug, exc))
        return []
    return [entry["issue"] for entry in lifecycle.entries(manifest)[0]]


def lint_errors(manifest, task_dir):
    """What `compass issue lint` reports about `depends_on`. With no
    `task_dir` (a manifest linted by path) only the shape is checked, because
    there is no checkout to read the other issues from."""
    good, errors = lifecycle.entries(manifest)
    if task_dir is None or not good:
        return errors
    slug = os.path.basename(os.path.normpath(task_dir))
    read = lifecycle.checkout_reader(os.path.dirname(os.path.normpath(task_dir)))
    for dep in lifecycle.judge(manifest, slug, read):
        if dep.fault == lifecycle.NOT_FOUND:
            errors.append(missing_line(dep.issue))
        elif dep.fault == lifecycle.UNKNOWN_UNTIL:
            errors.append("`depends_on`: %s: until '%s' is not a value; use one of %s"
                          % (dep.issue, dep.until, _values()))
        elif dep.fault == lifecycle.UNREADABLE:
            errors.append("`depends_on`: %s's manifest cannot be read (%s)"
                          % (dep.issue, dep.cause or "no cause given"))
        elif dep.state == "done" and dep.close_reason != status_words.COMPLETED:
            errors.append("`depends_on`: %s was closed as %s, so the wait can never be "
                          "met; run compass issue depends remove %s"
                          % (dep.issue, dep.close_reason or "no close reason", dep.issue))
    # A cycle is reported on the issues it passes through, so one fault is
    # not repeated on every issue upstream of it.
    cycle = find_cycle(slug, slug, read, first=[e["issue"] for e in good])
    if cycle:
        errors.append("`depends_on` forms a cycle: " + " -> ".join(cycle))
    return errors


def waiting_lines(work_root, slug):
    """The lines `ship-commit` prints after `slug` lands: each issue of this
    checkout that is not closed and whose `depends_on` names it, with its
    `until`, sorted by slug. None when no issue waits for it."""
    waiting = []
    try:
        names = sorted(os.listdir(work_root))
    except OSError:
        return []
    for name in names:
        task_dir = os.path.join(work_root, name)
        if name == slug or not os.path.isdir(task_dir):
            continue
        try:
            manifest, _path = load_manifest(task_dir)
        except Exception:                                   # noqa: BLE001 - lint reports it
            continue
        if not isinstance(manifest, dict) or status_words.is_closed(manifest):
            continue
        for entry in lifecycle.entries(manifest)[0]:
            if entry["issue"] == slug:
                waiting.append("  %s (until %s)" % (name, entry["until"]))
    if not waiting:
        return []
    return ["compass ship-commit: these issues were waiting for %s:" % slug] + waiting


def _own(task_dir):
    return os.path.basename(os.path.normpath(task_dir))


def _list_of(task, verb):
    raw = task.get("depends_on")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CompassError(
            "%s: depends_on in this manifest is not a list of %s entries; fix it by "
            "hand (compass issue lint names the fault). Nothing was written."
            % (verb, lifecycle.SHAPE_TEXT))
    return raw


def _index_of(entries, slug):
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("issue") == slug:
            return index
    return None


def cmd_depends_add(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    own, other = _own(task_dir), args.slug
    reason = (args.reason or "").strip()
    until = args.until if args.until is not None else lifecycle.DEFAULT_UNTIL
    if not is_one_segment(other):
        raise CompassError(
            "%s: '%s' is not one path segment; a slug names a folder directly under "
            ".compass/work/. Nothing was written." % (ADD, other))
    if other == own:
        raise CompassError("%s: an issue cannot depend on itself. Nothing was written." % ADD)
    if until not in lifecycle.UNTIL_VALUES:
        raise CompassError("%s: '%s' is not an until value; use one of %s. Nothing was "
                           "written." % (ADD, until, _values()))
    if not reason:
        raise CompassError("%s: --reason is empty; say why %s waits for %s. Nothing was "
                           "written." % (ADD, own, other))
    task, path = load_manifest(task_dir)
    entries = _list_of(task, ADD)
    read = lifecycle.checkout_reader(os.path.dirname(os.path.normpath(task_dir)))
    unread = []
    cycle = find_cycle(own, own, read, first=[other], unread=unread)
    if cycle:
        raise CompassError("%s: refusing - %s is a cycle; nothing was written."
                           % (ADD, " -> ".join(cycle)))
    entry = {"issue": other, "reason": reason, "until": until}
    index = _index_of(entries, other)
    if index is None:
        entries.append(entry)
    else:
        entries[index] = entry
    task["depends_on"] = entries
    save_manifest(task, path)
    for slug, exc in unread:
        if slug == other and exc.why == lifecycle.NOT_FOUND:
            sys.stderr.write("%s: %s\n" % (ADD, missing_line(other)))
        elif exc.why == lifecycle.UNREADABLE:
            sys.stderr.write("%s: %s could not be read (%s), so no cycle check ran through "
                             "it.\n" % (ADD, slug, exc.cause or "no cause given"))
    updated = "" if index is None else "; updated the entry for %s" % other
    return say(args, "%s: %s now waits for %s to reach %s%s." % (ADD, own, other, until, updated),
               issue=own, depends_on=entry, updated=index is not None)


def cmd_depends_remove(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    own, other = _own(task_dir), args.slug
    task, path = load_manifest(task_dir)
    raw = task.get("depends_on")
    entries = raw if isinstance(raw, list) else []
    index = _index_of(entries, other)
    if index is None:
        raise CompassError("%s: %s is not a dependency of %s; nothing was written."
                           % (REMOVE, other, own))
    del entries[index]
    if entries:
        task["depends_on"] = entries
    else:
        del task["depends_on"]
    save_manifest(task, path)
    # The saved manifest no longer names `other`, so the after-command render
    # would miss its page, which still lists this issue as depending on it.
    args.unlinked = [other]
    return say(args, "%s: %s no longer waits for %s." % (REMOVE, own, other),
               issue=own, removed=other)


def register(pts, issue_arg):
    """The `depends` group under `compass issue`."""
    group = pts.add_parser("depends", help="the issues this issue waits for")
    verbs = group.add_subparsers(dest="depends_cmd", required=True)
    add = verbs.add_parser("add", help="record that this issue waits for another issue")
    add.add_argument("slug", help="the issue this one waits for")
    add.add_argument("--reason", required=True, help="why this issue waits for it")
    add.add_argument("--until", help="the point it must reach: one of %s (default done)"
                                     % _values())
    issue_arg(add)
    add.set_defaults(func=cmd_depends_add, output_kind="hand-off")
    remove = verbs.add_parser("remove", help="stop waiting for an issue")
    remove.add_argument("slug", help="the issue this one no longer waits for")
    issue_arg(remove)
    remove.set_defaults(func=cmd_depends_remove, output_kind="hand-off")
