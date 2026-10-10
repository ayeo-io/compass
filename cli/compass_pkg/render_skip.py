# compass_pkg.render_skip - which issues `compass issue render --all` can skip
"""The derived state that lets `render --all` skip an issue whose inputs are unchanged (RS-14).

`render-skip.json`, in the cache folder under `.compass`, maps an issue slug to the digest of everything that issue's
render reads. When the digest matches, the issue's documents are what a render would write,
so the run skips it. The file is derived: deleting it makes the next run render every issue and
change no byte (DCJ-58). A run that cannot read or write it renders everything.

An issue's key digests:

- the CLI's version, so a new renderer re-renders every issue;
- the manifest's bytes, the folder's entries (name, size, modification time), the evidence
  folder's entries and the stored configuration generations;
- every registered document and the issue page, byte for byte;
- the manifests of the issues it links to and of those that link to it;
- the listings of `governance/decisions/` and `architecture/decisions/`;
- the project file `compass.yml`, which holds the Ready and Done lists, the approvers and the
  owner.

The key is computed from a `project_scan.ProjectScan`, so it adds no second read of the
manifests. A skipped issue is never written, so skipping can only leave a document as it is.
"""
# DEPENDENCY: standard library (hashlib, json, os); compass_pkg.core, atomic_io,
# project_scan, render_inputs.
from __future__ import annotations

import hashlib
import json
import os

from compass_pkg import atomic_io, project_scan
from compass_pkg.core import COMPASS_VERSION
from compass_pkg.issue_layout import docs_dir_for

STATE_NAME = "render-skip.json"
FORMAT = 1


def state_path(project):
    return os.path.join(project, ".compass", "cache", STATE_NAME)


def load(project):
    """`{slug: key}`; empty when the file is absent, unreadable or from another version."""
    try:
        with open(state_path(project), encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("format") == FORMAT and data.get("cli") == COMPASS_VERSION:
            issues = data.get("issues")
            return dict(issues) if isinstance(issues, dict) else {}
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def cache_folder(project):
    """`.compass/cache/`, created with a `.gitignore` of its own so a project that commits
    `.compass/` does not see the skip state or the index lock in `git status`."""
    folder = os.path.join(project, ".compass", "cache")
    os.makedirs(folder, exist_ok=True)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.exists(ignore):
        atomic_io.atomic_write_text(ignore, "*\n", newline="")
    return folder


def save(project, issues):
    """Write the state. A failure is ignored: the next run renders everything."""
    path = state_path(project)
    try:
        cache_folder(project)
        atomic_io.atomic_write_text(
            path, json.dumps({"format": FORMAT, "cli": COMPASS_VERSION, "issues": issues},
                             sort_keys=True, indent=1) + "\n", newline="")
    except OSError:
        pass


def _file(h, path):
    try:
        with open(path, "rb") as fh:
            h.update(hashlib.sha256(fh.read()).digest())
    except OSError:
        h.update(b"absent")


def _listing(h, folder):
    try:
        with os.scandir(folder) as entries:
            for entry in sorted(entries, key=lambda e: e.name):
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                h.update(("%s:%d:%d;" % (entry.name, stat.st_size, stat.st_mtime_ns)).encode("utf-8"))
    except OSError:
        h.update(b"none")


def key(scan, slug, project_state):
    """The skip key of one readable issue. `project_state` is `project_digest(scan)`."""
    task = scan.manifests[slug]
    task_dir = scan.task_dir(slug)
    h = hashlib.sha256()
    h.update(("%s|%s|%s|" % (COMPASS_VERSION, scan.digests[slug], project_state)).encode("utf-8"))
    _listing(h, task_dir)
    _listing(h, os.path.join(task_dir, "evidence"))
    _listing(h, os.path.join(task_dir, "generations"))
    seen = set()
    for entry in task.get("artifacts") or []:
        if isinstance(entry, dict) and entry.get("path"):
            rel = str(entry["path"]).replace("\\", "/")
            if rel not in seen:
                seen.add(rel)
                h.update(rel.encode("utf-8"))
                _file(h, os.path.join(scan.project, *rel.split("/")))
    page = docs_dir_for(task.get("created"), slug).replace(os.sep, "/") + "/README.md"
    _file(h, os.path.join(scan.project, *page.split("/")))
    linked = {other for _, other in project_scan.forward_links(task)}
    linked |= {other for _, other in scan.reverse.get(slug, [])}
    for other in sorted(linked - {slug}):
        h.update(("%s=%s;" % (other, scan.digests.get(other) or scan.unreadable.get(other)
                              or "absent")).encode("utf-8"))
    return h.hexdigest()


def project_digest(scan):
    """What every issue's render reads about the project: the decision entries and the ADR
    records (their listings), and the project file."""
    h = hashlib.sha256()
    _listing(h, os.path.join(scan.project, project_scan.LEDGER))
    _listing(h, os.path.join(scan.project, project_scan.ADR_FOLDER))
    _file(h, os.path.join(scan.project, "compass.yml"))
    _file(h, os.path.join(scan.project, ".compass", "config.yml"))
    return h.hexdigest()
