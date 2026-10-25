# compass_pkg.render_inputs - the snapshot of records the block renderers read
"""What a renderer is given, and the one function that reads it from disk.

`gather` reads the manifest's evidence folder and the registered documents' presence once,
before any renderer runs. A renderer takes a `RenderInputs` and the project-relative path
of the document it renders into, and returns a `Part`: the lines of the block and
whether they depend on this issue's own records (`own`) or on other issues or
the project (`cross`). The renderers read no clock, no git configuration and no
absolute path, so the same records give the same text on every machine.

A document a renderer quotes (`intent.md`, `technical-design.md`,
`delivery-approach.md`) is read on first use through `RenderInputs.doc_text`, from
the masked text, so a block's own earlier output is never read back.
"""
# DEPENDENCY: standard library (dataclasses, glob, json, os); compass_pkg.rendered_blocks,
# compass_pkg.issue_layout, compass_pkg.core (the registered-path resolver).
from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, field

from compass_pkg import rendered_blocks as rb
from compass_pkg.issue_layout import DOCS_ROOT, docs_dir_for

OWN, CROSS = "own", "cross"


@dataclass(frozen=True)
class Part:
    """The lines of one block. `scope` is `own` when they depend only on this
    issue's records and `cross` when they depend on another issue or the project."""
    scope: str
    lines: list
    #: When set, the lines that start with it depend on the project and the others on
    #: the issue's own records: a stale block whose only changed lines start with it is
    #: a `cross` block, any other stale block is `own`.
    cross_prefix: object = None


@dataclass
class RenderInputs:
    """A snapshot of everything the renderers read."""
    task: dict
    slug: str
    #: The project-relative directory of the issue's work folder.
    work_rel: str
    #: The issue's work folder on disk; read to find the records a state needs, never written
    #: into a block.
    task_dir: object = None
    #: The configuration view, or a callable that gives it on first use (an issue
    #: read without one gives None). Most blocks need no configuration.
    view: object = None
    #: `{(kind, scenario): file name}` for the red, green and acceptance records.
    records: dict = field(default_factory=dict)
    unbound: list = field(default_factory=list)
    #: The project-relative targets of registered documents that are files on disk.
    present: set = field(default_factory=set)
    #: A `project_scan.ProjectScan`, or None when no other issue was read.
    scan: object = None
    #: A function from a document kind to its masked text, or None.
    loader: object = None
    _texts: dict = field(default_factory=dict)
    _view_done: bool = False

    def list_of(self, key):
        value = self.task.get(key)
        return [e for e in value if isinstance(e, dict)] if isinstance(value, list) else []

    def get_view(self):
        """The configuration view of the issue, read on first use."""
        if not self._view_done:
            if callable(self.view):
                try:
                    self.view = self.view()
                except Exception:                           # noqa: BLE001
                    self.view = None
            self._view_done = True
        return self.view

    def doc_text(self, kind):
        """The masked text of the issue's document of this kind, '' when it is not there."""
        if kind not in self._texts:
            self._texts[kind] = (self.loader(kind) if self.loader else "") or ""
        return self._texts[kind]


def gather(task, task_dir, project_root, view=None, scan=None):
    """The snapshot for one issue: the manifest as loaded, the record files in the
    issue's `evidence/` folder, which registered documents exist, and the lazy readers
    of the documents a block quotes."""
    records, unbound = _records(task_dir)
    work_rel = os.path.relpath(os.path.abspath(task_dir), project_root).replace(os.sep, "/")
    slug = os.path.basename(os.path.normpath(task_dir))
    inputs = RenderInputs(task=task, slug=slug, work_rel=work_rel, task_dir=os.path.abspath(task_dir),
                          view=view, records=records, unbound=unbound, scan=scan)
    present = set()
    for entry in inputs.list_of("artifacts"):
        if entry.get("path"):
            target = link_target(inputs, entry["path"])
            if target and os.path.isfile(os.path.join(project_root, *target.split("/"))):
                present.add(target)
    inputs.present = present
    inputs.loader = lambda kind: _load_doc(inputs, project_root, kind)
    return inputs


def _load_doc(inputs, project_root, kind):
    path = None
    for entry in inputs.list_of("artifacts"):
        if entry.get("kind") == kind and entry.get("path"):
            path = link_target(inputs, entry["path"])
    if path is None:
        path = docs_dir_for(inputs.task.get("created"), inputs.slug).replace(os.sep, "/") \
            + "/%s.md" % kind
    full = os.path.join(project_root, *path.split("/"))
    try:
        with open(full, encoding="utf-8") as fh:
            return rb.masked_text(fh.read())
    except (OSError, UnicodeDecodeError):
        return ""


def _records(task_dir):
    out, unbound = {}, []
    for path in sorted(glob.glob(os.path.join(task_dir, "evidence", "*.json"))):
        name = os.path.basename(path)
        kind = next((k for k in ("red", "green", "acceptance")
                     if name == f"{k}.json" or name.startswith(f"{k}-")), None)
        if kind is None or name == "acceptance-baseline.json":
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        scenario = (data.get("scenario") if isinstance(data, dict) else None) \
            or name[len(kind) + 1:-5]
        if scenario:
            out.setdefault((kind, str(scenario)), name)
        else:
            unbound.append(name)
    return out, unbound


# --- helpers shared by the renderers ---------------------------------------

def code(text):
    """Text as inline code: neutralised, and a backtick written as an
    apostrophe so it cannot end the span."""
    return "`%s`" % rb.field(text).replace("`", "'")


def link_target(inputs, path):
    """The project-relative path a manifest path names, or None when it
    leaves the project. A path under `docs/` or `.compass/` is measured from the
    project root; any other is measured from the issue's work folder, as the
    evidence registry's paths are."""
    path = str(path or "").replace("\\", "/")
    if not path or os.path.isabs(path):
        return None
    if not path.startswith(("docs/", ".compass/")):
        path = inputs.work_rel + "/" + path
    norm = os.path.normpath(path).replace(os.sep, "/")
    return None if norm.startswith("..") else norm


def safe_relative(target, doc_rel):
    """`target` as a link from the document `doc_rel`, or None when the target is not
    under `docs/compass/` or holds a character a link could not carry."""
    safe = target is not None and all(c.isalnum() or c in "._-/" for c in target)
    if not (safe and target.startswith(DOCS_ROOT.replace(os.sep, "/") + "/")):
        return None
    return os.path.relpath(target, os.path.dirname(doc_rel) or ".").replace(os.sep, "/")


def relative_to(target, doc_rel):
    """The path from the document `doc_rel` to any project-relative `target`."""
    return os.path.relpath(target, os.path.dirname(doc_rel) or ".").replace(os.sep, "/")


def link(inputs, path, doc_rel, text):
    """A relative Markdown link to `path`, shown as `text`, when the path is
    under `docs/compass/` (a folder a project commits); None otherwise. The work
    folder is untracked in many projects, so a link there would not resolve."""
    relative = safe_relative(link_target(inputs, path), doc_rel)
    if relative is None:
        return None
    return "[%s](%s)" % (rb.field(text).replace("[", "\\[").replace("]", "\\]"), relative)


def shown_path(inputs, path, doc_rel):
    """A path as the block shows it: a link when `link` gives one, else code."""
    return link(inputs, path, doc_rel, path) or code(path)


def md_link(text, relative):
    return "[%s](%s)" % (rb.field(text).replace("[", "\\[").replace("]", "\\]"), relative)
