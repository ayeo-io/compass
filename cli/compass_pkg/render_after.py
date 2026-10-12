# compass_pkg.render_after - render the documents after a command that changed records
"""The after-command render (ADR-051).

The entry point calls `after_command` after `github_labels.after_command`, for
every command. When the command exits 0 and is in `record_triggers.RENDER_TRIGGERS`,
it renders:

1. the issue the command named, and
2. every issue the manifest links to in either direction, so a block that draws
   on another issue's records (`related`) is current there too.

Nothing else is written: an issue the manifest does not link to keeps its bytes
and its modification time.

A render that fails never fails the command and never stops the others. When any
render fails, one line on standard error gives the count and the first failure.
A command that exits non-zero renders nothing. The step shares
no code with the label sync and imports nothing from it: both read
`record_triggers`, and each catches its own failure.

The environment variable `COMPASS_RENDER_AFTER=0` switches the step off. Any other
value, or none, leaves it on. It exists so a test suite does not pay for rendering
after every command: the suite sets it to `0` and a test of the step sets it to
`1`. An explicit `compass issue render` ignores it.
"""
# DEPENDENCY: standard library (os, sys, yaml via compass_pkg.core); compass_pkg.core,
# record_triggers, render_cmd, project_scan. It imports neither github_labels nor check_cmd.
from __future__ import annotations

import os
import sys

import yaml

from compass_pkg import project_scan, record_triggers, render_cmd
from compass_pkg.core import load_manifest, manifest_path, resolve_issue_dir
from compass_pkg.issue_layout import is_one_segment


def _name_of(value):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return _name_of(value.get("issue"))
    return ""


def links_of(task):
    """The slugs of the issues one manifest links to."""
    found = set()
    for key in ("raised_by", "parent", "depends_on", "repairs", "landed_by", "delivered"):
        value = task.get(key)
        for one in value if isinstance(value, list) else [value]:
            found.add(_name_of(one))
    for follow_up in task.get("follow_ups") or []:
        if isinstance(follow_up, dict):
            found.add(_name_of(follow_up.get("target_task")))
    found.discard("")
    # A name from a manifest is joined onto the work folder, so it must be one path segment.
    return {name for name in found if is_one_segment(name)}


def linked_issue_dirs(task_dir, task):
    """The work folders of the issues this issue links to and of the issues that
    link to it, other than itself."""
    work = os.path.dirname(os.path.abspath(task_dir))
    slug = os.path.basename(os.path.abspath(task_dir))
    names = {n for n in links_of(task) if n != slug}
    try:
        entries = sorted(os.listdir(work))
    except OSError:
        entries = []
    for entry in entries:
        if entry == slug or entry in names:
            continue
        path = manifest_path(os.path.join(work, entry))
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        # Cheap test first: parse only a manifest that mentions this issue at all.
        if slug not in text:
            continue
        try:
            other = yaml.safe_load(text) or {}
        except yaml.YAMLError:
            continue
        if isinstance(other, dict) and slug in links_of(other):
            names.add(entry)
    return [os.path.join(work, n) for n in sorted(names)
            if os.path.isfile(manifest_path(os.path.join(work, n)))]


#: The project, read once for the issues one command renders (set by `after_command`).
_scan = None


def render_issue(task_dir):
    """Render one issue. Raises on a refusal or a failed write."""
    if _scan is None:
        return render_cmd.render_issue(task_dir)
    return render_cmd.render_issue(task_dir, scan=_scan)


def _cause(exc):
    """The first cause in an error: the file, the line and the fault."""
    lines = [x.strip() for x in str(exc).splitlines() if x.strip()]
    pick = next((x for x in lines if ":" in x and "refused" not in x), lines[0] if lines else "")
    return " ".join(pick.split())


def _failure_line(failures, total):
    slug, exc = failures[0]
    return ("compass: %d of %d renders failed - first: %s: %s. Run `compass issue render "
            "--issue %s` to see it." % (len(failures), total, slug, _cause(exc), slug))


def after_command(args, code):
    """Render after a record-changing command, and return `code` unchanged."""
    if code != 0 or os.environ.get("COMPASS_RENDER_AFTER") == "0":
        return code
    name = getattr(getattr(args, "func", None), "__name__", "")
    table = record_triggers.RENDER_TRIGGERS
    if name not in table or (table[name] and not getattr(args, table[name], False)):
        return code
    try:
        task_dir = resolve_issue_dir(getattr(args, "task", None))
        task, _ = load_manifest(task_dir)
        directories = [task_dir] + linked_issue_dirs(task_dir, task)
    except Exception:                                   # noqa: BLE001 - never fail the command
        return code
    failures = []
    for name in project_scan.rejected_links(task):
        sys.stderr.write("compass: the link '%s' in %s is not an issue name (an issue name is one "
                         "path segment), so it was not followed.\n"
                         % (name, os.path.basename(os.path.abspath(task_dir))))
    global _scan
    try:
        # Read once for every issue this step renders; each render still reads its own
        # manifest without the cache.
        _scan = project_scan.ProjectScan.build(render_cmd.project_of(task_dir))
    except Exception:                                   # noqa: BLE001
        _scan = None
    try:
        for directory in directories:
            try:
                render_issue(directory)
            except Exception as exc:                    # noqa: BLE001 - one failure hides no other
                failures.append((os.path.basename(os.path.abspath(directory)), exc))
    finally:
        _scan = None
    if failures:
        sys.stderr.write(_failure_line(failures, len(directories)) + "\n")
    return code
