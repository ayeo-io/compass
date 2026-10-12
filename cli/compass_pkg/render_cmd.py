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
- only files under `docs/compass/` are written;
- each write re-reads the file just before the rename and refuses when it
  changed since the render read it;
- there is no rollback across files. A failure part way leaves the files already
  written as they are, and a second run converges.

The plan also covers the project index, the README.md directly in `docs/compass`. It is written under its own
lock, `.compass/cache/render-index.lock`, and a failure to read it never refuses an issue's
render: the index is a cross-issue block (ADR-051).

`--all` plans every readable issue from one `project_scan.ProjectScan`, skips an issue whose
inputs are unchanged (`render_skip`), and renders the rest. Each issue that cannot be rendered
is named; the others are rendered and the command exits 1 (ADR-051).
"""
# DEPENDENCY: standard library (dataclasses, os); compass_pkg.core, atomic_io,
# block_renderers, rendered_blocks, issue_layout, terminal, project_scan, project_index,
# render_skip, render_inputs.
from __future__ import annotations

import os
from dataclasses import dataclass, field

from compass_pkg import (atomic_io, block_renderers, issue_layout, project_index, project_scan,
                         render_inputs, render_skip)
from compass_pkg import rendered_blocks as rb
from compass_pkg.core import (CompassError, _registered_path, docs_dir_for, find_compass_dir,
                              find_upwards, load_manifest, resolve_issue_dir)
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
    #: `{kind: scope}` of the changed kinds, `own` or `cross` (see `block_renderers.Part`).
    scopes: dict = field(default_factory=dict)
    #: True for the project index, which is shared by every issue.
    is_index: bool = False
    #: For the index: whether this issue's row differs from a fresh render. The other rows
    #: are other issues' business.
    row_stale: bool = False

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
    #: Why the project index could not be rendered, or None. It never refuses the issue.
    index_problem: object = None
    #: The inputs the index was planned with, so a write that lost a race can plan it again.
    index_inputs: object = None
    #: The path of the issue page when a person wrote it and it holds no block, else None.
    hand_page: object = None

    def to_write(self):
        return [f for f in self.files if f.changed]


def _project_root(task_dir):
    root = find_upwards(task_dir, ".compass")
    if root is None:
        raise CompassError(f"compass issue render: no .compass folder above {task_dir}.")
    return os.path.abspath(root)


def project_of(task_dir):
    """The project root above an issue's work folder."""
    return _project_root(os.path.abspath(task_dir))


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


def unsafe_document_path(task_dir, rel, project, allow_work=False):
    """Why a path built from a manifest cannot be written, or None: it leaves the project, is
    not under docs/compass (or, with `allow_work`, the issue's own folder), or is, or sits
    under, a symbolic link. A caller that writes a document checks it before any change."""
    resolved, refused = _registered_path(task_dir, rel)
    if refused:
        return "it resolves outside the project"
    resolved = os.path.abspath(resolved)
    folders = [os.path.join(project, "docs", "compass") + os.sep]
    if allow_work:
        folders.append(os.path.abspath(task_dir) + os.sep)
    if not resolved.startswith(tuple(folders)):
        return "it is not under docs/compass"
    return _link_problem(project, resolved)


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


def _strip_cross(lines, prefix):
    return [x for x in lines if not x.startswith(prefix)]


def _plan_file(path, rel, raw, inputs, refusals, is_index=False):
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
    bodies, changed, cache, scopes = {}, [], {}, {}
    for index, block in enumerate(parsed.blocks):
        renderer = block_renderers.RENDERERS.get(block.kind)
        if renderer is None:
            continue
        if block.kind not in cache:
            part = renderer(inputs, rel)
            cache[block.kind] = part
        part = cache[block.kind]
        lines = part.lines
        bodies[index] = lines
        current = [x.rstrip("\r\n") for x in parsed.lines[block.start + 1:block.end]]
        if current != lines and block.kind not in changed:
            changed.append(block.kind)
            scope = part.scope
            if part.cross_prefix and scope == render_inputs.OWN and _strip_cross(
                    current, part.cross_prefix) == _strip_cross(lines, part.cross_prefix):
                # Only the lines that draw on the project differ.
                scope = render_inputs.CROSS
            scopes[block.kind] = scope
    try:
        new_text = rb.build(rel, text, bodies)
    except rb.PostConditionError as exc:
        refusals.append(str(exc))
        return None
    if new_text == text:
        changed, scopes = [], {}
    found = FilePlan(path, rel, new_text, rb.file_digest(path), False, changed,
                     sorted({b.kind for b in parsed.blocks}), scopes, is_index)
    if is_index and changed:
        block = next(b for b in parsed.blocks if b.kind == "index")
        fresh = cache["index"].lines
        old = [x.rstrip("\r\n") for x in parsed.lines[block.start + 1:block.end]]
        found.row_stale = (project_index.row_lines(old, inputs.slug)
                           != project_index.row_lines(fresh, inputs.slug))
    return found


def _plan_index(project, inputs, plan):
    """Plan the project index. Its problems are kept in `plan.index_problem`: a hand-written
    or broken index never refuses an issue's render."""
    path = os.path.join(project, *project_index.INDEX_REL.split("/"))
    rel = project_index.INDEX_REL
    problem = _link_problem(project, path)
    if problem:
        plan.index_problem = f"{rel}: {problem}"
        return
    raw = _read(path)
    refusals = []
    if raw is None:
        found = _plan_file(path, rel, project_index.index_text().encode(), inputs, refusals,
                           is_index=True)
        if found is not None:
            found.is_new, found.read_digest = True, None
    else:
        found = _plan_file(path, rel, raw, inputs, refusals, is_index=True)
        if found is None and not refusals:
            plan.notes.append(f"{rel}: holds no rendered block (hand-written), not rendered")
    if refusals:
        plan.index_problem = "; ".join(refusals)
    elif found is not None:
        plan.files.append(found)


def plan_issue(task_dir, scan=None, manifest=None, index=True):
    """What a render of the issue would write. Reads, writes nothing. Raises
    `CompassError` naming every refusal when any document cannot be rendered.

    `scan` is the `project_scan.ProjectScan` of the project (built here when absent).
    `manifest` is what to render from: by default the issue's own, read with
    `load_manifest` and never through the parse cache, so a cached payload cannot
    decide the issue's verdict. A landing passes the manifest as it will leave it.
    `index` says whether to plan the project index."""
    task_dir = os.path.abspath(task_dir)
    own = manifest
    if own is None:
        own, _ = load_manifest(task_dir)
    project = _project_root(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    if scan is None:
        scan = project_scan.ProjectScan.shared(project)
    if scan.manifests.get(slug) != own:
        scan = scan.with_task(slug, own)
    inputs = block_renderers.gather(own, task_dir, project, lambda: _view(task_dir), scan)
    plan = IssueRender(slug, task_dir, project)
    plan.index_inputs = inputs
    refusals, seen = [], set()
    task = own

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
                                   inputs, refusals)
                if found is not None:
                    found.is_new, found.read_digest = True, None
                    plan.files.append(found)
            else:
                found = _plan_file(page, page_rel, raw, inputs, refusals)
                if found is not None:
                    plan.files.append(found)
                elif not refusals:
                    plan.hand_page = page_rel
                    plan.notes.append(f"{page_rel}: the issue page is hand-written and was "
                                      f"not rendered (it holds no rendered block)")
    if refusals:
        raise CompassError("compass issue render: refused, nothing written.\n  "
                           + "\n  ".join(refusals))
    if index:
        _plan_index(project, inputs, plan)
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
            if item.is_index:
                _write_index(plan, item)
            else:
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


def _index_lock(project):
    return os.path.join(render_skip.cache_folder(project), "render-index.lock")


def _write_index(plan, item, attempts=4):
    """Write the index under its lock. Another issue's render may have written it since the
    plan read it; the plan is then made again from the file as it is, a few times."""
    with atomic_io.locked(_index_lock(plan.project)):
        current = item
        for _ in range(attempts):
            try:
                rb.write_rendered(current.path, current.new_text, current.read_digest)
                return
            except rb.ChangedDuringRender:
                raw = _read(current.path)
                fresh = _replan_index(plan, current, raw)
                if fresh is None:
                    raise
                current = fresh
        rb.write_rendered(current.path, current.new_text, current.read_digest)


def _replan_index(plan, item, raw):
    """The index plan again, from the bytes now on disk, with the same rendered body."""
    if raw is None:
        return None
    inputs = plan.index_inputs
    found = _plan_file(item.path, item.rel, raw, inputs, [], is_index=True) if inputs else None
    return found if found is not None and found.changed else None


def render_issue(task_dir, scan=None, manifest=None):
    """Render one issue's blocks under its lock: the plan, then the writes.
    Returns the plans written. Raises `CompassError` on a refusal or a failed
    write. The after-command step calls this for each issue it renders."""
    task_dir = os.path.abspath(task_dir)
    with atomic_io.locked(os.path.join(task_dir, LOCK)):
        return apply(plan_issue(task_dir, scan=scan, manifest=manifest))


def render_projected(task_dir, projected):
    """Render one issue from a manifest as a landing will leave it, under the issue's lock.
    The manifest on disk is not read for the render and not changed. Returns the plans written
    (the documents, the page and the project index)."""
    task_dir = os.path.abspath(task_dir)
    with atomic_io.locked(os.path.join(task_dir, LOCK)):
        return apply(plan_issue(task_dir, manifest=projected))


def _progress(written):
    if not written:
        return "Nothing was written."
    return (f"{len(written)} earlier document(s) were written and stay written; run the "
            f"command again to finish.")


def cmd_issue_render(args):
    """`compass issue render [--issue SLUG | --all] [--dry-run]`."""
    if getattr(args, "all", False):
        if getattr(args, "task", None):
            raise CompassError("compass issue render: --all renders every issue; give "
                               "--issue or --all, not both.")
        return _render_all(args)
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    dry = bool(getattr(args, "dry_run", False))
    if dry:
        # A dry run stores nothing, not even a parse of a manifest.
        plan = plan_issue(task_dir, scan=project_scan.ProjectScan.build(
            project_of(task_dir), store=False))
        written = []
    else:
        with atomic_io.locked(os.path.join(task_dir, LOCK)):
            plan = plan_issue(task_dir, scan=project_scan.ProjectScan.shared(
                project_of(task_dir), store=True))
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
    if plan.index_problem:
        detail.append("project index not rendered: " + plan.index_problem)
    count = len([f for f in pending if not f.is_index])
    if dry:
        outcome = "compass issue render (dry run): %s, %d document(s) to rewrite" % (plan.slug, count)
    else:
        outcome = "compass issue render: %s, %d document(s) rewritten" % (
            plan.slug, len([f for f in written if not f.is_index]))
    return say(args, outcome, detail=detail, issue=plan.slug, dry_run=dry,
               rewritten=[f.rel for f in (pending if dry else written)],
               current=[f.rel for f in current], notes=plan.notes)


# --- the whole project ---------------------------------------------------------

def _first_line(exc):
    lines = [x.strip() for x in str(exc).splitlines() if x.strip()]
    rest = [x for x in lines if "refused" not in x] or lines
    return rest[0] if rest else "refused"


def _render_all(args):
    """Render every readable issue, skip those whose inputs are unchanged, render the
    project index, and name each issue that could not be rendered."""
    dry = bool(getattr(args, "dry_run", False))
    project = os.path.dirname(find_compass_dir())
    scan = project_scan.ProjectScan.build(project, store=not dry)
    state = render_skip.load(project)
    shared = render_skip.project_digest(scan)
    rendered, skipped, failed, would, kept = [], [], [], [], {}
    for slug in scan.slugs():
        if slug in scan.unreadable:
            failed.append((slug, scan.unreadable[slug]))
            continue
        before = render_skip.key(scan, slug, shared)
        if state.get(slug) == before:
            skipped.append(slug)
            kept[slug] = before
            continue
        task_dir = scan.task_dir(slug)
        try:
            if dry:
                plan = plan_issue(task_dir, scan=scan, manifest=scan.manifests[slug], index=False)
                would += [{"path": f.rel, "kinds": f.changed_kinds or ["new page"]}
                          for f in plan.to_write()]
            else:
                with atomic_io.locked(os.path.join(task_dir, LOCK)):
                    apply(plan_issue(task_dir, scan=scan, manifest=scan.manifests[slug], index=False))
                kept[slug] = render_skip.key(scan, slug, shared)
            rendered.append(slug)
        except CompassError as exc:
            failed.append((slug, str(exc).replace("compass issue render: refused, nothing written.\n", "")
                           .strip()))
    index_note = _render_all_index(project, scan, dry, would)
    if not dry:
        render_skip.save(project, kept)
    detail = ["%s: %s" % (slug, " ".join(why.split())) for slug, why in failed]
    if dry:
        detail += ["would write %s: %s" % (w["path"], ", ".join(w["kinds"])) for w in would]
    if index_note:
        detail.append(index_note)
    outcome = "compass issue render --all%s: %d issue(s) %s, %d skipped as unchanged, %d failed" % (
        " (dry run)" if dry else "", len(rendered), "to render" if dry else "rendered",
        len(skipped), len(failed))
    say(args, outcome, detail=detail, dry_run=dry, rendered=rendered, skipped=skipped,
        failed=[{"issue": s, "reason": " ".join(w.split())} for s, w in failed],
        would_write=would if dry else None)
    return 1 if failed else 0


def _render_all_index(project, scan, dry, would):
    """Plan and write the index once, from the whole scan. Returns a line to print, or None."""
    anchor = next(iter(sorted(scan.manifests)), None)
    if anchor is None:
        return None
    task_dir = scan.task_dir(anchor)
    plan = IssueRender(anchor, task_dir, project)
    inputs = block_renderers.gather(scan.manifests[anchor], task_dir, project, None, scan)
    plan.index_inputs = inputs
    _plan_index(project, inputs, plan)
    if plan.index_problem:
        return "project index not rendered: " + plan.index_problem
    pending = plan.to_write()
    if dry:
        would += [{"path": f.rel, "kinds": f.changed_kinds or ["new page"]} for f in pending]
        return None
    try:
        apply(plan)
    except CompassError as exc:
        return "project index not written: " + _first_line(exc)
    return None
