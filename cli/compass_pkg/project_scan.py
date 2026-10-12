# compass_pkg.project_scan - what the render reads from the rest of the project
"""One read of every issue's manifest, the decision entries and the ADR records.

A block that draws on other issues (`related`, the governance lines of
`decisions`, the project index) needs the whole project, not one issue. This module
reads it once per command and builds the indexes the renderers ask:

- the reverse links of every issue (who depends on it, who raised it, which
  follow-up targets it);
- the entries of `governance/decisions/`, by the issue slugs their Evidence
  section names;
- the ADR records, by id;
- each issue's state, read once.

Manifests are read through the parse cache (ADR-049, widened by ADR-052). The
cache serves the render under three conditions: the issue's own manifest is read
by `render_cmd.plan_issue` with `load_manifest`, never through the cache; no
command that saves a manifest reads through it; and a planted payload is accepted
only for the blocks that are advisory (`related`, the governance lines of
`decisions` and the index row). This module and `flow.py` are the only modules
that name the cache, and a test pins the list.

The scan reads and writes no document. It reads no clock, no git configuration and
no absolute path into a block.
"""
# DEPENDENCY: standard library (hashlib, os, re); compass_pkg.core, parse_cache,
# issue_detail, issue_layout, approval_records.
from __future__ import annotations

import hashlib
import os
import re

from compass_pkg import issue_detail, parse_cache
from compass_pkg.core import CompassError, manifest_path, normalize_spine
from compass_pkg.issue_layout import docs_dir_for, is_one_segment

LEDGER = os.path.join("governance", "decisions")
ADR_FOLDER = os.path.join("architecture", "decisions")
_ENTRY_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-(.+)\.md$")
_ADR_NAME = re.compile(r"^(ADR-\d+)-.*\.md$")
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")

#: Forward link label to the label the other issue reads under. A link with no
#: reverse label is not shown on the other issue.
REVERSE = {"depends on": "depended on by", "parent": "child", "repairs": "repaired by",
           "follow-up target": "follow-up from", "delivered by": None,
           "raised from": "raised here"}


def _names(value, rejected=None):
    """The issue slugs a link field names: a slug, a `{issue: slug}` mapping or a
    list of either. A name that is not one path segment is not an issue name: it is
    left out (and added to `rejected` when given), because it would be joined onto the
    work folder and could leave the project (ADR-051, decision 7)."""
    if isinstance(value, str):
        name = value.strip()
        if name and not is_one_segment(name):
            if rejected is not None:
                rejected.append(name)
            return []
        return [name] if name else []
    if isinstance(value, dict):
        return _names(value.get("issue"), rejected)
    if isinstance(value, list):
        return [name for one in value for name in _names(one, rejected)]
    return []


def rejected_links(task):
    """The names in a manifest's link fields that are not one path segment."""
    rejected = []
    if isinstance(task, dict):
        for key in ("depends_on", "parent", "repairs", "landed_by", "raised_by", "delivered"):
            _names(task.get(key), rejected)
        for follow_up in task.get("follow_ups") or []:
            if isinstance(follow_up, dict):
                _names(follow_up.get("target_task"), rejected)
    return rejected


def forward_links(task):
    """`[(label, slug)]` for the links one manifest holds, in the order the
    `related` block shows them. A field that is absent gives no line."""
    out = []
    if not isinstance(task, dict):
        return out
    for label, key in (("depends on", "depends_on"), ("parent", "parent"),
                       ("repairs", "repairs")):
        out += [(label, name) for name in _names(task.get(key))]
    for follow_up in task.get("follow_ups") or []:
        if isinstance(follow_up, dict):
            out += [("follow-up target", name) for name in _names(follow_up.get("target_task"))]
    out += [("delivered by", name) for name in _names(task.get("landed_by"))]
    out += [("raised from", name) for name in _names(task.get("raised_by"))]
    return out


#: The scan `ProjectScan.shared` last built, with the signature it was built under.
_SHARED = {}


class DecisionEntry:
    """One file of `governance/decisions/`: its slug, its file name, the first
    line of its Decision section and the issue slugs its Evidence section names."""

    def __init__(self, slug, file, title, tokens):
        self.slug, self.file, self.title, self.tokens = slug, file, title, tokens


def _section(text, name):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "## " + name:
            body = []
            for later in lines[index + 1:]:
                if later.startswith("## "):
                    break
                body.append(later)
            return body
    return []


def read_decision_entries(project):
    """`[DecisionEntry]`, oldest first, for every dated file of the ledger."""
    folder = os.path.join(project, LEDGER)
    out = []
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        match = _ENTRY_NAME.match(name)
        if not match:
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        title = next((x.strip() for x in _section(text, "Decision") if x.strip()), match.group(2))
        tokens = set(_TOKEN.findall("\n".join(_section(text, "Evidence"))))
        out.append(DecisionEntry(match.group(2), name, title, tokens))
    return out


def read_adrs(project):
    """`{ADR-id: file name}` for the records in `architecture/decisions/`."""
    folder = os.path.join(project, ADR_FOLDER)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return {}
    return {m.group(1): name for name in names for m in [_ADR_NAME.match(name)] if m}


def read_flat_documents(project):
    """The names of the Markdown files directly in `docs/compass/`, other than the index:
    hand-written notes, not an issue's record."""
    folder = os.path.join(project, "docs", "compass")
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [n for n in names if n.endswith(".md") and n != "README.md"
            and os.path.isfile(os.path.join(folder, n))]


def folder_digest(folder):
    """A digest of a folder's file names, sizes and contents' lengths: what the skip
    state needs to see that a decision entry was added, changed or removed."""
    h = hashlib.sha256()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return h.hexdigest()
    for name in names:
        path = os.path.join(folder, name)
        try:
            stat = os.stat(path)
        except OSError:
            continue
        h.update(("%s:%d:%d\n" % (name, stat.st_size, stat.st_mtime_ns)).encode("utf-8"))
    return h.hexdigest()


class ProjectScan:
    """Every issue of one project, read once."""

    def __init__(self, project):
        self.project = os.path.abspath(project)
        self.work_root = os.path.join(self.project, ".compass", "work")
        #: slug to the parsed manifest (a dict).
        self.manifests = {}
        #: slug to why its manifest could not be read.
        self.unreadable = {}
        #: slug to the SHA-256 of its manifest file's bytes.
        self.digests = {}
        self.reverse = {}
        self.decisions = []
        self.decision_index = {}
        self.adrs = {}
        #: The Markdown files directly in docs/compass/ other than the index.
        self.flat_documents = []
        self._detail = {}
        self._state = {}
        self._owner = [False, None]

    # -- building --------------------------------------------------------

    @classmethod
    def empty(cls, project):
        """A scan of a project with no issue read: the blocks that draw on the
        project show only what the issue's own manifest says."""
        scan = cls(project)
        return scan

    @classmethod
    def build(cls, project, store=True):
        """Read the project. With `store=False` the parse cache is read and never written, so
        a dry run leaves no byte behind."""
        scan = cls(project)
        scan._read_manifests(store)
        scan.decisions = read_decision_entries(scan.project)
        for entry in scan.decisions:
            for token in entry.tokens:
                scan.decision_index.setdefault(token, []).append(entry)
        scan.adrs = read_adrs(scan.project)
        scan.flat_documents = read_flat_documents(scan.project)
        scan._link()
        return scan

    @classmethod
    def shared(cls, project, store=False):
        """The scan of a project for a caller that reads it more than once in one process
        (`compass ci` checks every issue in turn). The read is reused while no manifest, no
        decision entry, no ADR record and no hand-written note has changed; the per-issue
        facts (state, stage) are read again, because they depend on files the signature
        does not cover. A reading command (the check) passes `store=False`, so it reads
        the parse cache and never writes an entry."""
        project = os.path.abspath(project)
        signature = cls._signature(project)
        held = _SHARED.get(project)
        if held is None or held[0] != signature:
            held = (signature, cls.build(project, store=store))
            _SHARED.clear()
            _SHARED[project] = held
        return held[1].fresh()

    @staticmethod
    def _signature(project):
        work = os.path.join(project, ".compass", "work")
        parts = []
        try:
            with os.scandir(work) as entries:
                for entry in sorted(entries, key=lambda e: e.name):
                    try:
                        stat = os.stat(manifest_path(entry.path))
                        parts.append((entry.name, stat.st_mtime_ns, stat.st_size))
                    except OSError:
                        parts.append((entry.name, None, None))
        except OSError:
            pass
        return (tuple(parts), folder_digest(os.path.join(project, LEDGER)),
                folder_digest(os.path.join(project, ADR_FOLDER)),
                tuple(read_flat_documents(project)))

    def fresh(self):
        """This scan with the per-issue facts forgotten."""
        other = ProjectScan(self.project)
        other.__dict__.update(self.__dict__)
        other._detail, other._state, other._owner = {}, {}, [False, None]
        return other

    def _read_manifests(self, store=True):
        cache = parse_cache.for_work_root(self.work_root, store=store)
        try:
            slugs = sorted(d for d in os.listdir(self.work_root)
                           if os.path.isdir(os.path.join(self.work_root, d)))
        except OSError:
            slugs = []
        for slug in slugs:
            path = manifest_path(os.path.join(self.work_root, slug))
            if not os.path.isfile(path):
                self.unreadable[slug] = "no manifest.yml"
                continue
            try:
                body = normalize_spine(cache.load_yaml(path))
                if not isinstance(body, dict):
                    raise CompassError("not a mapping")
            except Exception as exc:                        # noqa: BLE001
                self.unreadable[slug] = ("manifest.yml is not valid YAML"
                                         if "invalid YAML" in str(exc) else
                                         "manifest.yml cannot be read")
                continue
            self.manifests[slug] = body
            with open(path, "rb") as fh:
                self.digests[slug] = hashlib.sha256(fh.read()).hexdigest()
        cache.finish()

    def _link(self):
        reverse = {}
        for slug, body in self.manifests.items():
            for label, other in forward_links(body):
                back = REVERSE.get(label)
                if back and other != slug:
                    reverse.setdefault(other, []).append((back, slug))
        for rows in reverse.values():
            rows.sort()
        self.reverse = reverse

    def with_task(self, slug, manifest):
        """A scan in which `slug` has `manifest`: the issue's own manifest, read without
        the cache, or the manifest as a landing will leave it."""
        other = ProjectScan(self.project)
        other.__dict__.update(self.__dict__)
        other.manifests = dict(self.manifests)
        other.manifests[slug] = manifest
        other.unreadable = {k: v for k, v in self.unreadable.items() if k != slug}
        other._detail = {k: v for k, v in self._detail.items() if k != slug}
        other._state = {k: v for k, v in self._state.items() if k != slug}
        other._link()
        return other

    def same_links(self, slug, manifest):
        """True when `manifest` links where the scan's copy of the issue does."""
        return forward_links(manifest) == forward_links(self.manifests.get(slug))

    # -- asking ----------------------------------------------------------

    def task_dir(self, slug):
        return os.path.join(self.work_root, slug)

    def slugs(self):
        return sorted(set(self.manifests) | set(self.unreadable))

    def page_rel(self, slug):
        """The project-relative path of an issue's page, as `/`-separated text."""
        body = self.manifests.get(slug) or {}
        return docs_dir_for(body.get("created"), slug).replace(os.sep, "/") + "/README.md"

    def detail(self, slug):
        """The `IssueDetail` of an issue, read once, through the shared function."""
        if slug not in self._detail:
            self._detail[slug] = issue_detail.detail(self.manifests[slug], self.task_dir(slug))
        return self._detail[slug]

    def state_text(self, slug):
        if slug not in self._state:
            self._state[slug] = issue_detail.state_text(self.manifests[slug], self.task_dir(slug))
        return self._state[slug]

    def decisions_naming(self, slug):
        """The decision entries whose Evidence section names this exact slug."""
        return list(self.decision_index.get(slug, []))

    def owner(self):
        """The project's declared owner, or None."""
        if not self._owner[0]:
            from compass_pkg import approval_records
            try:
                found = approval_records.project_owner(self.project)
            except Exception:                               # noqa: BLE001
                found = None
            self._owner = [True, found]
        return self._owner[1]
