# compass_pkg.lineage - where each issue was raised from, and what that adds up to
"""An issue raised from another issue records its parent and where it was
found, in the manifest's `raised_by` key. Most of Compass's defects
are found while landing or reviewing other work; recorded at the moment it
is known, the link lets `compass retro --lineage` say how much the `verify`
stage catches before the parent lands. File overlap cannot stand in: it flagged
114 of 128 landed issues.

Advisory only: nothing here gates.
"""
# DEPENDENCY: standard library (collections, os); compass_pkg.core, compass_pkg.stable_ids.
from __future__ import annotations

import collections
import os

from compass_pkg.stable_ids import STAGE_DEFINE, STAGE_IMPLEMENT, STAGE_PLAN, STAGE_VERIFY
from compass_pkg.core import (CompassError, _one_segment, find_compass_dir,
                              load_manifest,
                              load_yaml, manifest_path, resolve_issue_dir,
                              save_manifest)

# Every place a defect can be found. All but `after-landing` are before the
# parent landed, which is the share the report exists to show.
FOUND_AT = (STAGE_DEFINE, STAGE_PLAN, STAGE_IMPLEMENT, STAGE_VERIFY, "review", "ci",
            "after-landing")
AFTER = "after-landing"


def _work(compass_dir):
    return os.path.join(compass_dir, "work")


def check(compass_dir, parent, found_at, named="--raised-by"):
    """Refuse a parent with no issue folder or a place not in FOUND_AT, before
    anything is written. `named` is how the person gave the parent - a flag
    on `quick-fix start`, the first argument of `issue raised-by` - so the
    refusal names what they typed."""
    if (parent is None) != (found_at is None):
        raise CompassError(
            "give --raised-by and --found-at together: the parent issue and "
            "where this was found in it.")
    if parent is None:
        return
    if found_at not in FOUND_AT:
        raise CompassError(
            f"--found-at '{found_at}' is not a place an issue is found; use "
            f"one of {', '.join(FOUND_AT)}.")
    _one_segment(parent, named)
    if not os.path.isfile(manifest_path(os.path.join(_work(compass_dir), parent))):
        raise CompassError(
            f"{named} '{parent}' names no issue in this project "
            f"(no .compass/work/{parent}/manifest.yml).")


def record(compass_dir, task_dir, parent, found_at, named="--raised-by"):
    """Write `raised_by` to the issue's manifest. Return the value it
    replaced, so a correction is shown, and the line for the third issue in
    a chain, or None."""
    check(compass_dir, parent, found_at, named)
    if parent == os.path.basename(task_dir):
        raise CompassError(
            f"'{parent}' cannot be raised from itself; name the issue it was "
            f"found in.")
    task, _ = load_manifest(task_dir)
    earlier = task.get("raised_by")
    task["raised_by"] = {"issue": parent, "found_at": found_at}
    save_manifest(task, manifest_path(task_dir))
    return earlier, hint(compass_dir, os.path.basename(task_dir))


def _parents(compass_dir):
    """{slug: parent slug} for every issue that records one."""
    parents = {}
    work = _work(compass_dir)
    if not os.path.isdir(work):
        return parents
    for slug in sorted(os.listdir(work)):
        path = manifest_path(os.path.join(work, slug))
        if not os.path.isfile(path):
            continue
        try:
            data = load_yaml(path) or {}
        except Exception:  # an unreadable manifest is lint's to report
            continue
        raised = data.get("raised_by") if isinstance(data, dict) else None
        if isinstance(raised, dict) and isinstance(raised.get("issue"), str):
            parents[slug] = raised
    return parents


def chain(parents, slug):
    """`slug` and its ancestors, root first. A loop stops at the first issue
    seen twice, so a hand-edited cycle cannot hang the walk."""
    seen = [slug]
    while slug in parents:
        slug = parents[slug]["issue"]
        if slug in seen:
            break
        seen.append(slug)
    return list(reversed(seen))


def hint(compass_dir, slug):
    """One line for the third issue in a chain: the same problem has now
    produced two follow-ons, which is what the strategy "correct every
    place at once" (`S14`) is about."""
    line = chain(_parents(compass_dir), slug)
    if len(line) < 3:
        return None
    # The point goes first: the terminal cuts a long line at its width.
    return (f"Third issue from '{line[0]}': correct every place at once "
            f"(`S14`, governance/strategies.md): {' -> '.join(line)}")


def report(compass_dir):
    """The lines `compass retro --lineage` prints."""
    parents = _parents(compass_dir)
    if not parents:
        return ["compass retro --lineage: no issue records where it was raised "
                "(`quick-fix start --raised-by` or `compass issue raised-by`)."]
    places = collections.Counter(r.get("found_at") for r in parents.values())
    after = places.get(AFTER, 0)
    # Only a known place counts either way; lint reports the others.
    before = sum(n for p, n in places.items() if p in FOUND_AT and p != AFTER)
    unknown = sum(n for p, n in places.items() if p not in FOUND_AT)
    children = collections.Counter(r["issue"] for r in parents.values())
    lines = [f"compass retro --lineage: {len(parents)} issue(s) raised from another issue",
             f"  found before the parent landed: {before}",
             f"  found after the parent landed: {after}",
             ] + ([f"  where found not recognised: {unknown} (see `compass issue lint`)"]
                  if unknown else []) + [
             "  by where found: " + ", ".join(
                 f"{p} {places[p]}" for p in FOUND_AT if places.get(p))]
    leaves = [s for s in parents if s not in children]
    chains = sorted((chain(parents, s) for s in leaves), key=len, reverse=True)
    chains = [c for c in chains if len(c) >= 3]
    if chains:
        lines.append("  chains of three or more:")
        lines += [f"    {' -> '.join(c)}" for c in chains[:5]]
    lines.append("  most children: " + ", ".join(
        f"{p} ({n})" for p, n in children.most_common(3)))
    return lines


def cmd_retro_lineage(args):
    for line in report(find_compass_dir()):
        print(line)
    return 0


def cmd_issue_raised_by(args):
    compass_dir = find_compass_dir()
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    earlier, said = record(compass_dir, task_dir, args.parent, args.found_at,
                           named="the parent issue")
    print(f"compass issue raised-by: '{os.path.basename(task_dir)}' was raised "
          f"from '{args.parent}' at {args.found_at}.")
    if isinstance(earlier, dict):
        print(f"  was: {earlier.get('issue')} at {earlier.get('found_at')}")
    if said:
        print(f"  {said}")
    return 0
