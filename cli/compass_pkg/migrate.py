# =============================================================================
# The archive migration core - 1.x issue directories to schema 2.0.
#
# This module owns the v1-to-v2 on-disk mapping: manifest keys (through
# core.normalize_spine) and artifact filenames (the map below). The runtime
# resolves v2 names only; this module reads old trees. `compass issue migrate`
# wraps migrate_tree with a dry run and a report; the private
# `_migrate-archive` verb migrates this repository's own archive.
# =============================================================================
import copy
import os
import re

import yaml

from compass_pkg import migrate_kinds, retired
from compass_pkg.core import COMPASS_SCHEMA_VERSION, CompassError, docs_dir, manifest_path, normalize_spine, prepare_manifest_write

# v1 filename -> v2 filename, applied inside each issue directory.
V1_ARTIFACT_NAMES = {
    # Spelled from parts for the same reason core.MANIFEST_NAMES is: the
    # enforced CLI must not carry a retired name as a plain string literal,
    # so a blanket rename over the tree cannot turn a compatibility pair
    # into an identity.
    "task" + ".yml": "manifest.yml",
    "brief.md": "intent.md",
    "spec.feature.md": "acceptance-criteria.md",
    "route.md": "delivery-approach.md",
    "clarifications.md": "requirements-review.md",
    "plan.md": "technical-design.md",
    "design.md": "technical-design.md",
    "prd.md": "intent.md",
    "spec.feature": "acceptance-criteria.feature",
}


# The reader lives in `core` - see its note. `migrate` imports `core` already,
# so keeping it there is what stops the import cycle.
from compass_pkg.core import migrate_map_path as _map_path
from compass_pkg.core import migrate_map_section as _map_section


def artifact_name_map():
    """The v1-to-v2 artifact map, read from the exempt data file
    (cli/migrate-map.yml) so the enforced CLI never teaches a v1 spelling;
    the in-module copy is the fallback for a bare checkout."""
    return _map_section("artifacts", V1_ARTIFACT_NAMES)


# The stage-key renames, in the same shape and for the same reason as the
# artifact names above: the enforced CLI must not carry a retired spelling in a
# string literal, so the mapping lives in the exempt data file and this is only
# the fallback for a bare checkout with no framework install.
V1_STAGE_KEYS = {
    "frame": "assess",
    "specify": "define",
    "clarify": "refine",
    "distribute": "breakdown",
    "build": "implement",
    "land": "ship",
}


def stage_key_map():
    """The retired-to-current stage keys, read from the exempt data file."""
    return _map_section("stage_keys", V1_STAGE_KEYS)


def colliding_artifacts(task_dir):
    """Retired filenames in this directory that claim the same current name.

    `artifacts:` is many-to-one in two places, because two renames landed on
    the same document: `brief.md` and `prd.md` both become `intent.md`, and
    `plan.md` and `design.md` both become `technical-design.md`. A directory
    holding both members of a pair has two files claiming one name, and no
    rule in the map says which is the real one.

    Returns {current_name: [retired names present]}, entries with two or more
    sources only. The caller refuses; picking by dict order would keep the
    older, out-of-date file.
    """
    sources = {}
    for old_name, new_name in artifact_name_map().items():
        if os.path.exists(os.path.join(task_dir, old_name)):
            sources.setdefault(new_name, []).append(old_name)
    return {new: sorted(olds) for new, olds in sources.items() if len(olds) > 1}


def repoint_spine_references(task_dir, node, renamed):
    """Rewrite manifest values that name a file this migration renamed away.

    A manifest points at its own documents in several places - `evidence:` paths,
    the artifact registry's `path:`, `changed_files:` - and renaming the file
    without repointing them leaves every one of those naming something that is
    no longer there. `compass check` then fails gate-evidence-present with
    "path does not resolve" on an issue nothing is wrong with.

    Driven by what was ACTUALLY renamed in this directory, plus a check that
    the old file is gone and the new one is there. A blanket rewrite of every
    retired spelling would break the records the compatibility path exists to
    preserve - a directory that still holds `plan.md` keeps pointing at it.

    Mutates `node` in place. Returns True if anything changed.
    """
    def resolves(name):
        return (not os.path.exists(os.path.join(task_dir, name))
                and os.path.isfile(os.path.join(task_dir, renamed[name])))

    def fix(value):
        if not isinstance(value, str):
            return value, False
        head, sep, tail = value.rpartition("/")
        if tail not in renamed or not resolves(tail):
            return value, False
        # THE WHOLE PATH, NOT THE TAIL. A manifest names files outside its own
        # directory too - `changed_files:` lists repository paths - and
        # `commands/plan.md` is a shipped command file, not this issue's
        # design. Deciding on the filename alone would rewrite it to
        # `commands/technical-design.md`, a path that does not exist.
        if head and not os.path.isfile(os.path.join(task_dir, value)):
            return value, False
        return head + sep + renamed[tail], True

    changed = False
    if isinstance(node, dict):
        for key, value in node.items():
            new, hit = fix(value)
            if hit:
                node[key] = new
                changed = True
            elif isinstance(value, (dict, list)):
                changed |= repoint_spine_references(task_dir, value, renamed)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            new, hit = fix(value)
            if hit:
                node[i] = new
                changed = True
            elif isinstance(value, (dict, list)):
                changed |= repoint_spine_references(task_dir, value, renamed)
    return changed


MIGRATED_REASON = "migrated from a 6.0.0 record"


def _settle_done_artifacts(data, when=None):
    """Settle the artifact status of a done issue, in place.

    A 6.0.0 record left every document `draft`, because no command wrote
    anything else. On a done issue each `draft` or `awaiting-approval` entry
    becomes `approved` for close reason `completed`, and `superseded`
    otherwise. Every other status is a decision and stays. Returns
    (approved, superseded); both are 0 for an open issue and for an issue
    already settled, which makes a second run change nothing.
    """
    from compass_pkg import artifact_status as ast, status_words
    if not status_words.is_closed(data):
        return 0, 0
    completed = status_words.is_completed(data)
    approved = superseded = 0
    for entry in data.get("artifacts") or []:
        if not isinstance(entry, dict) \
                or entry.get("status") not in (ast.DRAFT, ast.AWAITING):
            continue
        if completed:
            ast._set_approved(entry, ast.BY_MIGRATE, when or ast.now())
            approved += 1
        else:
            entry["status"] = ast.SUPERSEDED
            ast.clear_approver(entry)
            superseded += 1
        # A reason that names the file a document came from stays: the rename map reads it.
        if not str(entry.get("reason") or "").startswith("migrated from "):
            entry["reason"] = MIGRATED_REASON
    return approved, superseded


# The first line of a work-folder `README.md` written by the review page generator that
# 7.0.0 removed. A page that opens with it is kept as `README.md.v6.bak` and not read again;
# a README a person wrote has no such line and stays as it is.
OLD_PAGE_MARKER = "<!-- GENERATED by `compass issue dashboard`"
OLD_PAGE_KEPT_AS = "README.md.v6.bak"


def _old_page(task_dir):
    """The path of the work folder's old generated page, or None."""
    path = os.path.join(task_dir, "README.md")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            first = next((line for line in fh if line.strip()), "")
    except (OSError, UnicodeDecodeError):
        return None
    return path if first.lstrip().startswith(OLD_PAGE_MARKER) else None


def aside_old_page(task_dir, would, problems=None):
    """Keep the old generated page, byte for byte, as `README.md.v6.bak` beside it. Text a
    person appended under the marker goes with it. Returns the change notes."""
    path = _old_page(task_dir)
    if path is None:
        return []
    kept = os.path.join(task_dir, OLD_PAGE_KEPT_AS)
    if os.path.exists(kept):
        if problems is not None:
            problems.append("%s: README.md carries the old generated marker and %s already "
                            "exists, so README.md was left where it is."
                            % (os.path.basename(os.path.normpath(task_dir)), OLD_PAGE_KEPT_AS))
        return []
    if would:
        return ["would rename the old review page README.md aside to %s" % OLD_PAGE_KEPT_AS]
    os.rename(path, kept)
    return ["renamed the old review page README.md aside to %s" % OLD_PAGE_KEPT_AS]


def _read_manifest(task_dir):
    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        return path, None
    with open(path, encoding="utf-8") as fh:
        return path, yaml.safe_load(fh) or {}


def _write_manifest(path, data):
    """Serialise first, then replace atomically: a dump that raises must not
    leave an empty manifest behind."""
    data = prepare_manifest_write(data, path)
    body = yaml.safe_dump(data, sort_keys=False,
                          default_flow_style=False, allow_unicode=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, path)


def _status_note(approved, superseded, would):
    return "%s %d artifact entries approved and %d superseded" % (
        "would mark" if would else "marked", approved, superseded)


def plan_artifact_status(task_dir, data=None):
    """The dry-run twin of settle_artifact_status. `data` is the manifest as the dry run
    has changed it in memory; the apply settles the manifest after its earlier steps have
    registered and superseded entries, so settling the disk would count other entries."""
    if data is None:
        _path, data = _read_manifest(task_dir)
    if not isinstance(data, dict):
        return []
    approved, superseded = _settle_done_artifacts(copy.deepcopy(data))
    return [_status_note(approved, superseded, True)] if approved + superseded else []


def settle_artifact_status(task_dir):
    """Write the settled status of a done issue."""
    path, data = _read_manifest(task_dir)
    if not isinstance(data, dict):
        return []
    approved, superseded = _settle_done_artifacts(data)
    if not approved + superseded:
        return []
    _write_manifest(path, data)
    return [_status_note(approved, superseded, False)]


def plan_issue_dir(task_dir, problems=None, totals=None):
    """The dry-run twin of migrate_issue_dir: compute the change notes
    without writing anything. Items that need a person are appended to
    `problems` when it is given. Raises `RoundCollision` for an issue the
    apply would refuse."""
    _make_plan(task_dir)
    notes = aside_old_page(task_dir, True, problems)
    renamed = artifact_name_map()
    for old_name, new_name in renamed.items():
        old_p = os.path.join(task_dir, old_name)
        new_p = os.path.join(task_dir, new_name)
        if os.path.exists(old_p) and not os.path.exists(new_p):
            notes.append(f"would rename {old_name} -> {new_name}")
    # The manifest is found AFTER the artifact renames above, because it is
    # one of them: the retired manifest filename becomes `manifest.yml` on
    # the same pass. Looking the manifest up by its old name here would find
    # nothing, and the issue would keep the retired root key.
    manifest = manifest_path(task_dir)
    # The registry as the apply leaves it before its status step, held in memory:
    # the rewrite into current words, the relocation registrations, the stub map's
    # supersession and the verification note's entry. The status step settles it,
    # so the dry run counts what the apply counts.
    simulated = None
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        before = copy.deepcopy(raw)          # see migrate_issue_dir
        migrated = normalize_spine(raw)
        # Reported here as well as done in the apply, or the dry run
        # promises less than the apply does - which is the same class of
        # mismatch as promising more, and just as hard to trust afterwards.
        if repoint_spine_references(task_dir, migrated, renamed):
            notes.append("would repoint the manifest at the renamed files")
        if str(migrated.get("schema_version", "")).split(".")[0] not in ("2", "3"):
            migrated["schema_version"] = "2.0"
        if migrated != before:
            notes.append("would rewrite the manifest in the current words, schema 3.0")
        if isinstance(migrated, dict):
            simulated = copy.deepcopy(migrated)
    notes.extend(plan_relocations(task_dir, problems, totals, simulated))
    notes.extend(_blocks(task_dir, True, problems))
    if simulated is not None:
        from compass_pkg import migrate_blocks
        migrate_blocks.register_planned(task_dir, simulated)
    notes.extend(plan_artifact_status(task_dir, simulated))
    notes.extend(_pin_generation(task_dir, True, problems))
    return notes


def _print_open_items(open_items):
    """What migration could not record from the pages, one line each. They are reported on
    every run, because the items stay open until a person records them."""
    if not open_items:
        return
    print()
    print("compass issue migrate: %d item(s) left for a person to record:" % len(open_items))
    for line in open_items:
        print("  - %s" % line)


def _unread_fields(task_dir):
    """The manifest fields of one issue that no command reads any more. The
    migrate keeps them: the manifest is a record, and a field nothing reads
    loses nothing by staying (ADR-070)."""
    try:
        raw = _read_manifest(task_dir)[1]
    except Exception:                               # noqa: BLE001 - reported elsewhere
        return []
    assessment = raw.get("assessment") if isinstance(raw, dict) else None
    return [f"assessment.{name}" for name in retired.DIMENSIONS
            if isinstance(assessment, dict) and name in assessment]


def _print_unread(unread):
    if not unread:
        return
    print()
    print("compass issue migrate: %d field(s) no longer read, kept as they are (%s):"
          % (len(unread), retired.NOT_READ))
    for slug, field in unread:
        print(f"  {slug}: {field}")


def cmd_migrate(args):
    """`compass issue migrate [root]` - dry-run by default; --apply makes the changes.

    Idempotent: a migrated tree reports nothing to do.

    Refuses before writing anything if any directory holds two retired files
    that claim the same current name - see colliding_artifacts. The whole run
    stops rather than that one directory, because a partly-migrated tree is
    harder to reason about than one that was not touched."""
    root = getattr(args, "root", None) or os.path.join(".compass", "work")
    if not os.path.isdir(root):
        print(f"compass issue migrate: no issue directories under {root} - "
              "nothing to examine.")
        return 0
    apply_mode = bool(getattr(args, "apply", False))
    # Checked before anything is read, let alone written. A refusal that
    # arrives after the first directory has moved has protected nothing.
    if apply_mode and not getattr(args, "i_have_a_copy", False):
        # Both folders are asked, so one refusal names every copy a person must
        # take. Naming only the first would send them back with a copy of one.
        docs = os.path.join(_project_root(root), "docs", "compass")
        shown = os.path.relpath(docs)
        if os.path.isabs(root) or shown.startswith(os.pardir):
            shown = docs
        from compass_pkg import migrate_copy_check as check
        project = _project_root(root)
        in_work, in_docs = check.registered_files(root, docs, project)
        lost = [found for found in (check.unrestorable_folders(root, None, in_work, project),
                                    check.unrestorable_folders(docs, shown, in_docs, project))
                if found.unrestorable]
        if lost:
            raise CompassError(check.refusal(lost))
    dirs = [e for e in sorted(os.listdir(root))
            if os.path.isdir(os.path.join(root, e))]

    # Checked across the whole tree BEFORE anything is written, and reported
    # on a dry run too - a dry run that promises a rename the apply cannot
    # make is worse than the refusal.
    collisions = []
    for entry in dirs:
        for new_name, olds in colliding_artifacts(
                os.path.join(root, entry)).items():
            collisions.append("  %s: %s both become %s"
                              % (entry, " and ".join(olds), new_name))
    if collisions:
        raise CompassError(
            "two retired filenames claim the same current name, and nothing "
            "in the map says which is the real document:\n"
            + "\n".join(collisions)
            + "\n\nNothing was changed. Open both files, keep the one that is "
              "current, and move or delete the other - then re-run. Picking "
              "one automatically would silently keep whichever came first, "
              "which is the older file.")

    # One directory failing must not take the report with it. Report each
    # directory as it goes, so one unparseable manifest cannot hide the
    # renames already made. Both spellings resolve, so a half-migrated tree
    # still works, and nobody would notice it.
    changed = {}
    failed = {}
    collided = []
    open_items = []
    totals = Totals()
    for entry in dirs:
        d = os.path.join(root, entry)
        try:
            notes = (migrate_issue_dir(d, open_items, totals) if apply_mode
                     else plan_issue_dir(d, open_items, totals))
        except migrate_kinds.RoundCollision as exc:
            collided.append(exc)
            continue
        except Exception as exc:                    # noqa: BLE001
            # Deliberately broad: whatever one directory does wrong, the other
            # 109 still get migrated and reported. The reason is carried into
            # the report rather than swallowed.
            failed[entry] = "%s: %s" % (type(exc).__name__, exc)
            continue
        if notes:
            changed[entry] = notes

    unread = [(entry, field) for entry in dirs
              for field in _unread_fields(os.path.join(root, entry))]
    if not changed and not failed and not collided:
        print("compass issue migrate: nothing to do - every issue directory "
              "already speaks schema %s." % COMPASS_SCHEMA_VERSION)
        _print_open_items(open_items)
        _print_unread(unread)
        return 0

    if changed:
        verb = "migrated" if apply_mode else "would change"
        noun = "issue directory" if len(changed) == 1 else "issue directories"
        print(f"compass issue migrate: {len(changed)} {noun} {verb} "
              f"under {root}:")
        for slug, notes in changed.items():
            print(f"  {slug}")
            for n in notes:
                print(f"    - {n}")

    if changed:
        print()
        for line in totals.lines():
            print(line)

    _print_open_items(open_items)
    _print_unread(unread)

    if collided:
        print()
        print("compass issue migrate: %d issue(s) left exactly as they were, because two review "
              "files claim one round:" % len(collided))
        for exc in collided:
            print("  - %s" % exc)
        print()
        print("Resolve the named files and re-run; the other issues were %s."
              % ("migrated" if apply_mode else "planned"))
        return 1

    if failed:
        noun = "directory" if len(failed) == 1 else "directories"
        print()
        print(f"compass issue migrate: {len(failed)} {noun} could NOT be migrated:")
        for slug, why in failed.items():
            print(f"  {slug}")
            print(f"    - {why}")
        print()
        print(f"{len(changed)} migrated, {len(failed)} left as they were. "
              "Fix the files named above and re-run - migration is "
              "idempotent, so the ones already done are skipped.")
        return 1

    if not apply_mode:
        print()
        print("This was a dry run - nothing was written. "
              "Run `compass issue migrate --apply` to execute.")
    return 0


# --- relocating and renaming documents ----------------------------------------
#
# Machine state stays where the CLI reads it. `evidence/`, the markers, the TDD
# state file, the manifest and the devlog do not move; moving `evidence/` would
# break every gate in a repository at once, and the devlog is appended to by
# the CLI. Every other document an issue holds is written for a person. The
# mapping table (`migrate_kinds`) says which kind it is: a document of a kind
# goes to `docs/compass/<created>-<slug>/` under that kind's filename, a review
# becomes a round of `review`, and a name the table does not know stays where it
# is and is reported.
STAYS_BESIDE_THE_MANIFEST = {
    "manifest.yml", "devlog.md", "README.md", "architecture-loaded.yml",
    ".red", ".spike", ".acceptance", ".tdd-state.json",
}

#: The one document whose absence beside the manifest used to stop work.
#: `hooks/pre-tool.sh` asks the registry for it, and has since before 5.0.0.
BLOCKING_DOCUMENT = "delivery-approach.md"

#: How the pointer opens that an earlier release left at the old name of the
#: record. The migrate removes a file with this line once the record is at its
#: registered path. It never writes one.
POINTER_MARKER = "<!-- compass: moved -->"


def _project_root(task_dir):
    """The project `docs/compass/` is measured from.

    Walked up to `.compass/` the way the resolver does, rather than counted
    three levels from the issue directory: counting gives the same answer for
    the usual layout and a silently wrong one in a worktree or a fixture, and a
    wrong root here MOVES FILES into a tree nobody pointed at.
    """
    from compass_pkg.core import find_upwards

    task_dir = os.path.abspath(task_dir)
    return find_upwards(task_dir, ".compass") or task_dir


#: The subtask keys that hold a path to a document. `compass issue subtask`
#: writes each one measured from the project root.
_SUBTASK_PATH_KEYS = ("brief", "report", "review_brief", "package")


def _reference_slots(data):
    """Every (container, key, anchor) in a manifest that can hold a path to
    one of the issue's documents.

    `anchor` is where the reader measures the value from, and a rewritten
    value keeps it:

      * `"project"` - the subtask fields (`brief`, `earlier_briefs`,
        `report`, `review_brief`, `package`) and the stop evidence of a
        subtask and of a run. `compass issue subtask` writes the subtask
        fields, and `compass run` writes a run's stop evidence, both from the
        project root. `multiagent-run-recorded` joins a subtask's stop
        evidence to the project root.
      * `"issue"` - an `evidence:` entry's `path`, and a gate's evidence when
        it holds a path (an inline `{type, path}`, or a list item that is
        one or names a `.md` file). Gates join these to the issue directory.
      * `"issue-line"` - a `friction:` note's `evidence`, which is read from
        the issue directory and may end in `:<line>`.

    `artifacts[].path` is not listed: the register step writes it.
    `changed_files[].path` names repository files, not issue documents, and
    `next_task` names an issue by its slug.
    """
    def dicts(value):
        return [v for v in (value or []) if isinstance(v, dict)] \
            if isinstance(value, list) else []

    for sub in dicts(data.get("subtasks")):
        for key in _SUBTASK_PATH_KEYS:
            if isinstance(sub.get(key), str):
                yield sub, key, "project"
        earlier = sub.get("earlier_briefs")
        if isinstance(earlier, list):
            for i, value in enumerate(earlier):
                if isinstance(value, str):
                    yield earlier, i, "project"
        stop = sub.get("stopped_reason")
        if isinstance(stop, dict) and isinstance(stop.get("evidence"), str):
            yield stop, "evidence", "project"
    for run in dicts(data.get("runs")):
        stop = run.get("stopped_reason")
        if isinstance(stop, dict) and isinstance(stop.get("evidence"), str):
            yield stop, "evidence", "project"
    for entry in dicts(data.get("evidence")):
        if isinstance(entry.get("path"), str):
            yield entry, "path", "issue"
    for gate in dicts(data.get("gates")):
        held = gate.get("evidence")
        if isinstance(held, dict) and isinstance(held.get("path"), str):
            yield held, "path", "issue"
        elif isinstance(held, list):
            for i, item in enumerate(held):
                if isinstance(item, dict) and isinstance(item.get("path"), str):
                    yield item, "path", "issue"
                elif isinstance(item, str) and item.endswith(".md"):
                    yield held, i, "issue"
    for note in dicts(data.get("friction")):
        if isinstance(note.get("evidence"), str):
            yield note, "evidence", "issue-line"


def _split_line(raw):
    """(path, ':<line>' or '') for a value that may end in a line number."""
    head, sep, tail = raw.rpartition(":")
    if sep and head and tail.isdigit():
        return head, sep + tail
    return raw, ""


def _is_pointer(path):
    """Is this file a compatibility pointer rather than a real document?"""
    return migrate_kinds.is_pointer(path, POINTER_MARKER)


def _renames(task_dir, data, moving=None):
    """{old absolute path: new project-relative path} for every document of this
    issue that sits at a new path and no longer at an old one.

    Read from the registry, so a run that was stopped after the move finds the
    same renames as the run that made them: an entry whose reason is "migrated from
    <name>" was that file before, in either folder; an entry whose path ends in a
    name that is gone beside the manifest was moved from there unchanged. `moving`
    adds the moves a dry run is about to make."""
    project = _project_root(task_dir)
    task_abs = os.path.abspath(task_dir)
    docs_abs = os.path.join(project, docs_dir(task_dir))
    out = dict(moving or {})
    for entry in data.get("artifacts") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        new = entry["path"]
        if not os.path.isfile(os.path.join(project, new)):
            continue
        olds = {os.path.basename(new)}
        found = re.match(r"migrated from (\S+\.md)$", str(entry.get("reason") or ""))
        if found:
            olds.add(found.group(1))
        for name in olds:
            for base in (task_abs, docs_abs):
                old = os.path.abspath(os.path.join(base, name))
                if os.path.normpath(os.path.join(project, new)) == old:
                    continue
                if not os.path.exists(old) or (base == task_abs and _is_pointer(old)):
                    out.setdefault(old, new)
    return out


def _stale_references(task_dir, data, renames):
    """[(container, key, new value, old file name)] for every field that names a
    document at a path it has left. `renames` is `_renames`.

    Matched by where the path RESOLVES for its reader, not by how it is spelled.
    A project-root field is measured from the project root only. An issue-folder
    field accepts `technical-design.md` and also `.compass/work/<slug>/technical-design.md`,
    and manifests on disk carry both."""
    project = _project_root(task_dir)
    task_abs = os.path.abspath(task_dir)
    out = []
    for container, key, anchor in _reference_slots(data):
        path, suffix = container[key], ""
        if anchor == "issue-line":
            path, suffix = _split_line(path)
        raw = (path or "").strip()
        if not raw:
            continue
        bases = [project] if anchor == "project" else [task_abs, project]
        new_rel = next((renames[found] for found in
                        (os.path.abspath(os.path.join(base, raw)) for base in bases)
                        if found in renames), None)
        if new_rel is None:
            continue
        if anchor == "project":
            new = new_rel
        else:
            new = os.path.relpath(os.path.join(project, new_rel), task_abs).replace(os.sep, "/")
        new += suffix
        if new != container[key]:
            out.append((container, key, new, os.path.basename(raw)))
    return out


def _stale_names(task_dir, moving=None):
    """The documents some manifest field names at a place they have left, sorted."""
    data = migrate_kinds.load_manifest(task_dir)
    if data is None:
        return []
    return sorted({name for _c, _k, _n, name
                   in _stale_references(task_dir, data, _renames(task_dir, data, moving))})


def _write_manifest_data(manifest, data):
    data = prepare_manifest_write(data, manifest)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False, allow_unicode=True)
    tmp = manifest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, manifest)


def _repoint_references(task_dir):
    """Repoint every manifest field that names a document at a path it has left.
    Returns the sorted names of the documents repointed.

    A manifest names its issue's documents in several fields, and each one that
    still names the old place fails a check on an issue nothing is wrong with.
    Each value is rewritten in the form its reader measures from, and the
    evidence registry stays anchored to the issue directory: re-anchoring it to
    the project root would break every gate in a repository at once. So an
    `evidence:` path becomes a relative path from the issue directory to the
    document's new home, and a subtask field becomes `docs/compass/...`.
    """
    manifest = manifest_path(task_dir)
    data = migrate_kinds.load_manifest(task_dir)
    if data is None:
        return []
    fixes = _stale_references(task_dir, data, _renames(task_dir, data))
    if not fixes:
        return []
    for container, key, new, _name in fixes:
        container[key] = new
    _write_manifest_data(manifest, data)
    return sorted({name for _c, _k, _n, name in fixes})


def _entry_id(kind, number):
    return "ART-%s%s" % (kind.upper().replace("-", "_"), "-%d" % number if number else "")


def _find_entry(entries, kind, number):
    return next((e for e in entries if isinstance(e, dict) and e.get("kind") == kind
                 and (number is None or e.get("round") == number)), None)


def _register(task_dir, move, data=None):
    """Point the registry entry of a move's kind (and round) at its new path,
    adding the entry when there is none, and write the manifest. Returns True when
    the manifest changed."""
    data = data if data is not None else migrate_kinds.load_manifest(task_dir)
    if data is None or not _register_in(data, move):
        return False
    _write_manifest_data(manifest_path(task_dir), data)
    return True


def _register_in(data, move):
    """The registration of `_register` on a manifest held in memory; it reads and
    writes no file. The dry run calls it on a copy and the apply on the manifest it
    then writes, so both decide alike whether a registration changes the registry.
    Returns True when `data` changed."""
    entries = data.get("artifacts")
    if not isinstance(entries, list):
        entries = data["artifacts"] = []
    entry = _find_entry(entries, move.kind, move.round)
    if entry is None:
        entry = {"id": _entry_id(move.kind, move.round), "kind": move.kind}
        if move.round:
            entry["round"] = move.round
        entry["status"] = "draft"
        if move.kind == BLOCKING_DOCUMENT[:-3]:
            entry["depth"] = migrate_kinds.depth_of(data)
        entry["reason"] = move.reason
        entry["path"] = move.new_rel
        entries.append(entry)
    elif entry.get("path") == move.new_rel:
        return False
    else:
        entry["path"] = move.new_rel
        if move.renamed:
            entry["reason"] = move.reason
    return True


def _needs_register(data, move):
    entry = _find_entry((data or {}).get("artifacts") or [], move.kind, move.round)
    return entry is None or entry.get("path") != move.new_rel


class Totals:
    """The counts the report ends with, added up over the issues."""

    def __init__(self):
        self.kinds = {}
        self.left = self.unmapped = self.pointers = self.stubs = 0

    def lines(self):
        kinds = ", ".join("%s %d" % (k, n) for k, n in sorted(self.kinds.items())) or "none"
        return ["compass issue migrate: totals",
                "  documents by target kind: %s" % kinds,
                "  left on the not-an-artifact list: %d" % self.left,
                "  unmapped files: %d" % self.unmapped,
                "  compatibility pointers to remove: %d" % self.pointers,
                "  distribution maps to rename to distribution-map.md.v6.bak: %d" % self.stubs]


def _count(totals, plan, counted_moves):
    if totals is None:
        return
    for move in counted_moves:
        totals.kinds[move.kind] = totals.kinds.get(move.kind, 0) + 1
    totals.left += len(plan.left)
    totals.unmapped += len(plan.unmapped)


def _move_note(move, would):
    label = "%s round %d" % (move.kind, move.round) if move.round else move.kind
    if not move.moves:
        return "%s %s, already under docs/compass/ and not in the registry" % (
            "would register" if would else "registered", move.new_rel)
    verb = "rename" if move.renamed else "move"
    if would:
        return "would %s %s -> %s, and register it as %s" % (verb, move.old_rel.rsplit("/", 1)[1],
                                                              move.new_rel, label)
    return "%s %s -> %s, and registered it as %s" % (
        "renamed" if move.renamed else "moved", move.old_rel.rsplit("/", 1)[1], move.new_rel, label)


def _rekind_note(rekind, would):
    """One line for an entry the 6.x migrate registered under a filename stem."""
    if rekind.merged:
        # The dry run and the apply print this one line, so the dry run says exactly
        # what the apply keeps and drops. A dropped approval is always named.
        return "%s the registry entry %s (%s) into %s (%s), keeping %s; dropping %s" % (
            "would merge" if would else "merged", rekind.old_kind, rekind.entry_id,
            rekind.label, rekind.held_id, rekind.kept, rekind.dropped)
    return "%s the registry entry %s (%s) to %s, keeping its id, status and approval" % (
        "would re-point" if would else "re-pointed", rekind.old_kind, rekind.entry_id,
        rekind.label)


def _plan_problems(plan, problems, unchanged_both=()):
    """What a person must look at, one line each. The same on a dry run and an apply.
    `unchanged_both` are the documents in both places whose registration changed
    nothing: the registry already names the copy under docs/compass/, and the copy
    beside the manifest is still there for a person to compare."""
    if problems is None:
        return
    for line in plan.rekind_problems:
        problems.append("%s: %s" % (plan.slug, line))
    for move in unchanged_both:
        problems.append("%s: %s is in both places - %s and %s; the registry names %s. Compare "
                        "the two, keep one and delete the other"
                        % (plan.slug, move.name, move.old_rel, move.new_rel, move.new_rel))
    for where, name in plan.unmapped:
        problems.append("%s: %s (%s) is unmapped - no row of the mapping table names it, so it "
                        "was left where it is" % (plan.slug, name, where))
    for old, new in plan.both_stay:
        problems.append("%s: %s and %s are both registered, so both stay as they are"
                        % (plan.slug, old, new))
    for name, kind, path in plan.kept_elsewhere:
        problems.append("%s: %s is left where it is - %s is registered at %s, and the "
                        "migrate keeps that path" % (plan.slug, name, kind, path))
    if plan.pointer_kept:
        problems.append("%s: %s has no pointer marker, so it was left where it is"
                        % (plan.slug, os.path.basename(plan.pointer_kept)))
    if plan.adopted_map:
        problems.append("%s: %s is kept - it was never registered, so it is registered with "
                        "no depth and the stub rule does not rename it, although the issue "
                        "has fewer than two subtasks" % (plan.slug, plan.adopted_map))


def _make_plan(task_dir, data=None):
    return migrate_kinds.plan_issue(task_dir, artifact_name_map(), POINTER_MARKER,
                                    STAYS_BESIDE_THE_MANIFEST, data=data)


def _registry_step3(task_dir, data, plan, would):
    """Step 3 of the apply on the manifest `data`, in place: move each stem-named entry
    onto its kind and round, re-point `design` and `prd`, and drop `recommendation`.
    It reads and writes no file, so the dry run runs it on a copy and the apply on the
    manifest it then writes. Returns the change notes, in the tense `would` chooses."""
    notes = []
    if plan.rekinds:
        done, _problems, _pairs = migrate_kinds.rekind_entries(
            data.get("artifacts"), plan.rekind_moves, _project_root(task_dir),
            migrate_kinds.shipped_catalogue())
        notes.extend(_rekind_note(r, would) for r in done)
    if plan.repoints or plan.dropped:
        wanted = {entry_id: (old, new) for entry_id, old, new in plan.repoints}
        kept = []
        for entry in data.get("artifacts") or []:
            if isinstance(entry, dict) and entry.get("kind") in migrate_kinds.DROPPED_KINDS:
                notes.append("%s the %s registry entry; its file stays where it is"
                             % ("would remove" if would else "removed", entry.get("kind")))
                continue
            if isinstance(entry, dict) and entry.get("id") in wanted \
                    and entry.get("kind") == wanted[entry.get("id")][0]:
                old, new = wanted[entry["id"]]
                entry["kind"] = new
                notes.append("%s the registry entry %s to %s"
                             % ("would re-point" if would else "re-pointed", old, new))
            kept.append(entry)
        data["artifacts"] = kept
    return notes


def _simulate(task_dir, plan, data=None):
    """The apply's registry steps, run on a copy of the manifest held in memory.

    Step 3 runs first, then the plan is made again against the edited copy, as the
    apply makes it again from disk, and each registration runs in the apply's order
    against a registry the earlier ones have changed. Returns (step 3 notes, the second
    plan, [(move, changed)], [(move, note, changed)]). A folder with no manifest the
    plan can read is left alone, as the apply leaves it. `data`, when given, is the
    caller's in-memory copy, and the steps change it in place."""
    if data is None:
        data = migrate_kinds.load_manifest(task_dir)
        if data is None:
            return [], plan, [], []
        data = copy.deepcopy(data)
    notes = _registry_step3(task_dir, data, plan, True)
    second = _make_plan(task_dir, data=data)
    moves = [(move, _register_in(data, move)) for move in second.moves]
    both = [(move, note, _register_in(data, move)) for move, note in second.both_places]
    return notes, second, moves, both


def plan_relocations(task_dir, problems=None, totals=None, data=None):
    """Dry-run notes for the relocation half. Writes nothing. A change line is printed
    only where the apply's own registry steps, run in memory, change something. `data`,
    when given, is the dry run's in-memory manifest, and it is left as the apply's
    relocation leaves the manifest on disk."""
    notes, plan, moves, both = _simulate(task_dir, _make_plan(task_dir), data)
    counted = [m for m, changed in moves if m.moves or changed]
    notes += [_move_note(m, True) for m in counted]
    notes += [note for _m, note, changed in both if changed]
    counted += [m for m, _note, changed in both if changed]
    moving = {os.path.join(_project_root(task_dir), m.old_rel): m.new_rel for m in plan.moves if m.moves}
    notes += ["would repoint the manifest fields that cite %s" % name
              for name in _stale_names(task_dir, moving)]
    if plan.pointer:
        notes.append("would remove the compatibility pointer %s" % os.path.basename(plan.pointer))
        if totals is not None:
            totals.pointers += 1
    # The apply renames the map, and supersedes its entry, only where the stub rule
    # does not block it: not over a kept copy, and not at a path the writers refuse.
    if plan.stub and not plan.stub.get("blocked"):
        notes.append("would rename %s to %s and mark its registry entry superseded"
                     % (os.path.basename(plan.stub["from"]), os.path.basename(plan.stub["to"])))
        if data is not None:
            _supersede_stub_entry(data, plan.stub)
        if totals is not None:
            totals.stubs += 1
    _stub_problem(plan.slug, plan.stub, problems)
    _plan_problems(plan, problems, [m for m, _note, changed in both if not changed])
    _count(totals, plan, counted)
    return notes


def relocate_documents(task_dir, problems=None, totals=None):
    """Carry out the plan for this issue, in the order that keeps the hook seeing the
    delivery-approach record at every stop:

      3. re-point the registered kinds the table renames, and drop `recommendation`;
      4. for each document, the delivery-approach record first, then by round:
         register its new path, then move the file;
      5. rewrite the manifest paths that named a file that moved;
      6. remove a compatibility pointer, once the record is at its registered path;
      7. rename the stub distribution map of a one-subtask issue.

    Idempotent: an issue already carried out reports nothing."""
    plan = _make_plan(task_dir)
    slug = plan.slug
    project = _project_root(task_dir)
    manifest = manifest_path(task_dir)
    step = migrate_kinds
    notes = []
    data = migrate_kinds.load_manifest(task_dir)
    if data is None:
        return notes
    notes.extend(_registry_step3(task_dir, data, plan, False))
    if plan.rekinds or plan.repoints or plan.dropped:
        _write_manifest_data(manifest, data)
    step.STEP_HOOK(slug, "repoint")
    plan = _make_plan(task_dir)
    counted = []
    for move in plan.moves:
        data = migrate_kinds.load_manifest(task_dir)
        if move.moves or _needs_register(data, move):
            counted.append(move)
        changed = _register(task_dir, move, data)
        step.STEP_HOOK(slug, "register")
        moved = False
        if move.moves:
            src, dest = os.path.join(project, move.old_rel), os.path.join(project, move.new_rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            if os.path.exists(src) and not os.path.exists(dest):
                os.replace(src, dest)
                moved = True
        step.STEP_HOOK(slug, "move")
        if moved or changed:
            notes.append(_move_note(move, False))
    unchanged_both = []
    for move, note in plan.both_places:
        if _register(task_dir, move):
            notes.append(note)
            counted.append(move)
        else:
            unchanged_both.append(move)
        step.STEP_HOOK(slug, "register")
    for name in _repoint_references(task_dir):
        notes.append("repointed the manifest fields that cited %s" % name)
    step.STEP_HOOK(slug, "rewrite")
    if plan.pointer:
        path = os.path.join(project, plan.pointer)
        if _is_pointer(path):
            os.remove(path)
            notes.append("removed the compatibility pointer %s" % os.path.basename(path))
            if totals is not None:
                totals.pointers += 1
    step.STEP_HOOK(slug, "pointer")
    stub = migrate_kinds.stub_map(task_dir, migrate_kinds.load_manifest(task_dir) or {}, project)
    if stub and not stub.get("blocked"):
        notes.append(_stub_apply(task_dir, project, stub))
        if totals is not None:
            totals.stubs += 1
    _stub_problem(slug, stub, problems)
    step.STEP_HOOK(slug, "stub")
    _plan_problems(plan, problems, unchanged_both)
    _count(totals, plan, counted)
    return notes


def _stub_problem(slug, stub, problems):
    """Report a stub map the rename refuses because of its path, on both runs alike. A
    map whose backup is already there needs no line: the backup is the earlier rename."""
    why = (stub or {}).get("blocked")
    if problems is not None and why and why != "kept":
        problems.append("%s: the distribution map at %s is not renamed: %s"
                        % (slug, stub["from"], why))


def _supersede_stub_entry(data, stub):
    """Mark the stub distribution map's registry entry superseded in `data`. The apply
    writes the result; the dry run keeps it in memory for the status step."""
    from compass_pkg import artifact_status as ast
    entry = _find_entry(data.get("artifacts") or [], "distribution-map", None)
    if entry is None:
        return
    entry["status"] = ast.SUPERSEDED
    entry.pop("path", None)
    ast.clear_approver(entry)
    entry["reason"] = ("a map for fewer than two subtasks, kept as %s by the 7.0.0 migrate"
                       % os.path.basename(stub["to"]))


def _stub_apply(task_dir, project, stub):
    manifest = manifest_path(task_dir)
    data = migrate_kinds.load_manifest(task_dir)
    os.replace(os.path.join(project, stub["from"]), os.path.join(project, stub["to"]))
    _supersede_stub_entry(data, stub)
    _write_manifest_data(manifest, data)
    return "renamed %s to %s and marked its registry entry superseded" % (
        os.path.basename(stub["from"]), os.path.basename(stub["to"]))


def _blocks(task_dir, would, problems):
    """The 7.0.0 additions for rendered blocks (see `migrate_blocks`)."""
    from compass_pkg import migrate_blocks
    out = migrate_blocks.run(task_dir, would)
    if problems is not None:
        problems.extend(out.problems)
    return out.notes


def _pin_generation(task_dir, would, problems):
    from compass_pkg import migrate_blocks
    out = migrate_blocks.Outcome()
    migrate_blocks.pin_stale_generation(task_dir, would, out)
    if problems is not None:
        problems.extend(out.problems)
    return out.notes


def migrate_issue_dir(task_dir, problems=None, totals=None):
    """Migrate one issue directory in place: rename v1-named artifacts and
    rewrite the manifest with v2 keys, then give each document its kind. Idempotent -
    a migrated directory is left untouched. Returns a list of human-readable
    change notes. Items that need a person are appended to `problems` when it is given.

    Step 1 is the plan. It is made before anything is written, so an issue that
    cannot be migrated (`RoundCollision`) is byte-identical afterwards."""
    _make_plan(task_dir)
    # First, so the page is kept as it was: nothing below may rewrite it.
    notes = aside_old_page(task_dir, False, problems)
    renamed = artifact_name_map()
    for old_name, new_name in renamed.items():
        old_p = os.path.join(task_dir, old_name)
        new_p = os.path.join(task_dir, new_name)
        if os.path.exists(old_p) and not os.path.exists(new_p):
            os.rename(old_p, new_p)
            notes.append(f"renamed {old_name} -> {new_name}")
    # Same reason as the dry run above: the manifest is one of the files the
    # rename loop just moved, so it is found by its current name first.
    manifest = manifest_path(task_dir)
    if os.path.isfile(manifest):
        with open(manifest, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        # A snapshot that nothing below can reach. `normalize_spine` copies the
        # top level and SHARES every nested list and dict, so repointing - which
        # rewrites values inside `evidence:` and `artifacts:` - would change
        # `raw` too, and the `!= raw` guard would compare a value with itself.
        before = copy.deepcopy(raw)
        migrated = normalize_spine(raw)
        # The manifest points at its own documents. Repointing is part of the
        # rename, not a follow-up: a record naming a file that is no longer
        # there fails `compass check` on an issue nothing is wrong with.
        if repoint_spine_references(task_dir, migrated, renamed):
            notes.append("manifest references -> the renamed files")
        if str(migrated.get("schema_version", "")).split(".")[0] not in ("2", "3"):
            migrated["schema_version"] = "2.0"
        if migrated != before:
            # Serialise first, then replace atomically. `open(manifest, "w")`
            # empties the file before safe_dump writes a byte, so a dump that
            # raises - an unexpected object type in the manifest will do it -
            # would leave manifest.yml empty and the issue with no record at
            # all. os.replace is atomic on every platform Compass supports.
            migrated = prepare_manifest_write(migrated, manifest)
            body = yaml.safe_dump(migrated, sort_keys=False,
                                  default_flow_style=False, allow_unicode=True)
            tmp = manifest + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(body)
            os.replace(tmp, manifest)
            notes.append("manifest keys and values -> schema %s" % COMPASS_SCHEMA_VERSION)
    # After the renames above, which put every document under its current
    # filename. Relocation registers each document before it moves it (steps 3 to 7
    # of `relocate_documents`), so the hook finds the record at every stop.
    notes.extend(relocate_documents(task_dir, problems, totals))
    notes.extend(_blocks(task_dir, False, problems))
    notes.extend(settle_artifact_status(task_dir))
    # Last: the pin keeps the manifest's own text and sets one line.
    notes.extend(_pin_generation(task_dir, False, problems))
    return notes


def migrate_tree(work_root):
    """Migrate every issue directory under a work root. Returns
    {slug: [notes]} for the directories that changed."""
    changed = {}
    if not os.path.isdir(work_root):
        return changed
    for slug in sorted(os.listdir(work_root)):
        d = os.path.join(work_root, slug)
        if not os.path.isdir(d):
            continue
        try:
            notes = migrate_issue_dir(d)
        except migrate_kinds.RoundCollision:
            continue                                # reported by `compass issue migrate`
        if notes:
            changed[slug] = notes
    return changed


def cmd_migrate_archive(args):
    """compass _migrate-archive --internal - migrate this repository's own
    work archive (and any work roots passed) to schema 2.0."""
    if not getattr(args, "internal", False):
        print("compass: compass _migrate-archive: the --internal flag is "
              "required. This is a private entry point - the user-facing "
              "migration verb ships in its own slice.")
        return 2
    roots = args.roots or [os.path.join(".compass", "work")]
    total = 0
    for root in roots:
        changed = migrate_tree(root)
        for slug, notes in changed.items():
            total += len(notes)
            print(f"  {root}/{slug}: {'; '.join(notes)}")
    print(f"compass _migrate-archive: {total} change(s) applied.")
    return 0
