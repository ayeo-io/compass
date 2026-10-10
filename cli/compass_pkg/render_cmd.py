# compass_pkg.render_cmd - `compass issue render`
"""Render the blocks of one issue's documents from its records (ADR-051).

`plan_issue` reads the records and every registered document, parses all of
them, renders every block and checks the engine's post-conditions, and returns
what would be written. It writes nothing. `apply` writes the plan. The verb, its
`--dry-run`, and (in later units) the check and the after-command step all call
the same plan, so they differ only in whether they write.

Safety, in the order it acts:

- the per-issue lock is held while the records are read and the files written;
- every document is read and parsed before any is written, so a malformed
  marker in the last document stops the render before it changes the first;
- a registered path is checked again here: one that leaves the project, one
  that is or sits under a symbolic link, and the page path are refused;
- only files under `docs/compass/` are written (DCJ-71);
- each write re-reads the file just before the rename and refuses when it
  changed since the render read it;
- there is no rollback across files. A failure part way leaves the files already
  written as they are, and a second run converges.
"""
# DEPENDENCY: standard library (dataclasses, os); compass_pkg.core, atomic_io,
# block_renderers, rendered_blocks, issue_layout, terminal.
from __future__ import annotations

import os
from dataclasses import dataclass, field

from compass_pkg import atomic_io, block_renderers, issue_layout
from compass_pkg import rendered_blocks as rb
from compass_pkg.core import (CompassError, _registered_path, docs_dir_for, find_upwards,
                              load_manifest, resolve_issue_dir)
from compass_pkg.terminal import say

#: The lock file in the issue's work folder.
LOCK = ".render.lock"
_DOCS = issue_layout.DOCS_ROOT.replace(os.sep, "/") + "/"


@dataclass
class FilePlan:
    path: str
    rel: str
    new_text: str
    read_digest: object = None
    is_new: bool = False
    #: The kinds of the blocks whose interior changes.
    changed_kinds: list = field(default_factory=list)
    #: Every kind the file holds a rendered block of.
    kinds: list = field(default_factory=list)

    @property
    def changed(self):
        return self.is_new or bool(self.changed_kinds)


@dataclass
class IssueRender:
    slug: str
    task_dir: str
    project: str
    files: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def to_write(self):
        return [f for f in self.files if f.changed]


def _project_root(task_dir):
    root = find_upwards(task_dir, ".compass")
    if root is None:
        raise CompassError(f"compass issue render: no .compass folder above {task_dir}.")
    return os.path.abspath(root)


def _link_problem(project, resolved):
    """Why `resolved` cannot be written, or None: it is, or sits under, a
    symbolic link. Only the parts below the project are checked."""
    rel = os.path.relpath(resolved, project)
    cur = project
    for part in rel.split(os.sep):
        cur = os.path.join(cur, part)
        if os.path.islink(cur):
            return f"{rel} is, or sits under, a symbolic link ({part})"
    return None


def _view(task_dir):
    from compass_pkg import effective
    try:
        return effective.view_or_legacy(task_dir)
    except Exception:                                   # noqa: BLE001
        return None


def _page_rel(task, slug):
    """The issue page path from the manifest's `created` date and the slug, or
    a reason it cannot be one."""
    created = str(task.get("created") or "").strip()
    rel = docs_dir_for(created, slug).replace(os.sep, "/") + "/README.md"
    parts = rel.split("/")
    if len(parts) != 4 or os.path.normpath(rel).replace(os.sep, "/") != rel or ".." in parts:
        return None, (f"the issue page path built from created '{created}' and the slug "
                      f"'{slug}' would leave docs/compass")
    return rel, None


def _read(path):
    """`(bytes, None)`, or `(None, None)` when the file is gone."""
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def _plan_file(path, rel, raw, inputs, refusals, is_page=False):
    """The `FilePlan` for a document read as `raw`, or None when it holds no
    block. A refusal is added to `refusals`."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        if b"compass:render" in raw:
            refusals.append(f"{rel}: not UTF-8, so it cannot be read safely. Nothing written.")
        return None
    if "compass:render" not in text:
        return None
    try:
        parsed = rb.parse(text, rel)
    except rb.MarkerError as exc:
        refusals.append(f"{rel}:{exc.line}: {exc.fault}")
        return None
    if not parsed.blocks:
        return None
    bodies, changed, cache = {}, [], {}
    for index, block in enumerate(parsed.blocks):
        renderer = block_renderers.RENDERERS.get(block.kind)
        if renderer is None:
            continue
        if block.kind not in cache:
            cache[block.kind] = renderer(inputs, rel).lines
        lines = cache[block.kind]
        bodies[index] = lines
        current = [x.rstrip("\r\n") for x in parsed.lines[block.start + 1:block.end]]
        if current != lines and block.kind not in changed:
            changed.append(block.kind)
    try:
        new_text = rb.build(rel, text, bodies)
    except rb.PostConditionError as exc:
        refusals.append(str(exc))
        return None
    if new_text == text:
        changed = []
    return FilePlan(path, rel, new_text, rb.file_digest(path), False, changed,
                    sorted({b.kind for b in parsed.blocks}))


def plan_issue(task_dir):
    """What a render of the issue would write. Reads, writes nothing. Raises
    `CompassError` naming every refusal when any document cannot be rendered."""
    task_dir = os.path.abspath(task_dir)
    task, _ = load_manifest(task_dir)
    project = _project_root(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    inputs = block_renderers.gather(task, task_dir, project, _view(task_dir))
    plan = IssueRender(slug, task_dir, project)
    refusals, seen = [], set()

    def consider(kind, path_text):
        resolved, refused = _registered_path(task_dir, path_text)
        if refused:
            refusals.append(f"{path_text}: the registered path for {kind} resolves outside "
                            f"the project. Nothing written.")
            return
        rel = os.path.relpath(resolved, project).replace(os.sep, "/")
        problem = _link_problem(project, resolved)
        if problem:
            refusals.append(f"{rel}: the registered path for {kind}: {problem}. "
                            f"Nothing written.")
            return
        if not rel.startswith(_DOCS):
            plan.notes.append(f"{rel}: outside docs/compass, not rendered ({kind})")
            return
        if resolved in seen:
            return
        seen.add(resolved)
        raw = _read(resolved)
        if raw is None:
            plan.notes.append(f"{kind}: registered at {rel} but not on disk, not rendered")
            return
        found = _plan_file(resolved, rel, raw, inputs, refusals)
        if found is not None:
            plan.files.append(found)

    for entry in inputs.list_of("artifacts"):
        if entry.get("path") and entry.get("status") != "omitted":
            consider(entry.get("kind", "document"), str(entry["path"]))

    page_rel, bad = _page_rel(task, slug)
    if bad:
        refusals.append(f"{bad}. Nothing written.")
    else:
        page = os.path.join(project, *page_rel.split("/"))
        problem = _link_problem(project, page)
        if problem:
            refusals.append(f"{page_rel}: the issue page: {problem}. Nothing written.")
        elif page not in seen:
            raw = _read(page)
            if raw is None:
                found = _plan_file(page, page_rel, block_renderers.issue_page_text(slug).encode(),
                                   inputs, refusals, is_page=True)
                if found is not None:
                    found.is_new, found.read_digest = True, None
                    plan.files.append(found)
            else:
                found = _plan_file(page, page_rel, raw, inputs, refusals, is_page=True)
                if found is not None:
                    plan.files.append(found)
    if refusals:
        raise CompassError("compass issue render: refused, nothing written.\n  "
                           + "\n  ".join(refusals))
    return plan


def apply(plan):
    """Write the plan. Returns the plans written. Raises `CompassError` on the
    first failure; the files written before it stay written."""
    for folder in sorted({os.path.dirname(f.path) for f in plan.files}):
        rb.remove_stale_temporaries(folder)
    written = []
    for item in plan.to_write():
        try:
            if item.is_new:
                os.makedirs(os.path.dirname(item.path), exist_ok=True)
            rb.write_rendered(item.path, item.new_text, item.read_digest)
        except rb.ChangedDuringRender as exc:
            raise CompassError(f"compass issue render: {item.rel} changed during the render. "
                               f"It was not replaced and your change is kept. Run the command "
                               f"again. {_progress(written)}") from exc
        except OSError as exc:
            raise CompassError(f"compass issue render: cannot write {item.rel}: {exc}. "
                               f"{_progress(written)}") from exc
        written.append(item)
    return written


def _progress(written):
    if not written:
        return "Nothing was written."
    return (f"{len(written)} earlier document(s) were written and stay written; run the "
            f"command again to finish.")


def cmd_issue_render(args):
    """`compass issue render [--issue SLUG] [--dry-run]`."""
    if getattr(args, "all", False):
        if getattr(args, "task", None):
            raise CompassError("compass issue render: --all renders every issue; give "
                               "--issue or --all, not both.")
        raise CompassError("compass issue render: --all is not built yet. Render one issue "
                           "with --issue SLUG.")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    dry = bool(getattr(args, "dry_run", False))
    if dry:
        plan = plan_issue(task_dir)
        written = []
    else:
        with atomic_io.locked(os.path.join(task_dir, LOCK)):
            plan = plan_issue(task_dir)
            written = apply(plan)
    return _report(args, plan, written, dry)


def _report(args, plan, written, dry):
    detail = []
    pending = plan.to_write()
    for item in (pending if dry else written):
        kinds = ", ".join(item.changed_kinds) or "new page"
        detail.append(("to rewrite %s: %s" if dry else "rendered %s: %s") % (item.rel, kinds))
    current = [f for f in plan.files if not f.changed]
    detail += ["current %s: %s" % (f.rel, ", ".join(f.kinds)) for f in current]
    detail += plan.notes
    count = len(pending)
    if dry:
        outcome = "compass issue render (dry run): %s, %d document(s) to rewrite" % (plan.slug, count)
    else:
        outcome = "compass issue render: %s, %d document(s) rewritten" % (plan.slug, len(written))
    return say(args, outcome, detail=detail, issue=plan.slug, dry_run=dry,
               rewritten=[f.rel for f in (pending if dry else written)],
               current=[f.rel for f in current], notes=plan.notes)
