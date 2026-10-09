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

import yaml

from compass_pkg.core import COMPASS_SCHEMA_VERSION, CompassError, manifest_path, normalize_spine, prepare_manifest_write

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


def plan_issue_dir(task_dir):
    """The dry-run twin of migrate_issue_dir: compute the change notes
    without writing anything."""
    notes = []
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
    notes.extend(plan_relocations(task_dir))
    return notes


def _work_root_is_recoverable(root):
    """Could `git reset --hard` put back what `--apply` is about to move?

    Only where the work root is TRACKED. In a project using Compass it is, and
    the reset is a complete undo. In this framework's own repository
    `.compass/work/` is gitignored, so git has nothing to restore and a reset
    undoes everything EXCEPT the thing that moved.

    Returns (recoverable, why). `recoverable` is True when git holds a copy, or
    when there is no git repository at all - outside a repository there is no
    undo to promise and no false promise to correct, and refusing there would
    stop the verb working in a plain directory.
    """
    import subprocess
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return True, "git is not available, so there is no undo to promise"
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return True, "not a git repository"
    try:
        tracked = subprocess.run(["git", "ls-files", "--", root],
                                 capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return True, "git could not be asked"
    if tracked.returncode == 0 and tracked.stdout.strip():
        return True, "the work root is tracked, so `git reset --hard` restores it"
    return False, ("%s is not tracked by git - it is gitignored, so "
                   "`git reset --hard` would restore everything except the "
                   "documents this moves" % root)


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
        recoverable, why = _work_root_is_recoverable(root)
        if not recoverable:
            raise CompassError(
                "this would move documents that cannot be put back: %s.\n\n"
                "Nothing was changed. Take a copy first:\n"
                "    cp -R %s <somewhere outside the repository>\n\n"
                "then re-run with --i-have-a-copy. The flag says you have "
                "the copy; it does not switch the check off." % (why, root))
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
    for entry in dirs:
        d = os.path.join(root, entry)
        try:
            notes = (migrate_issue_dir(d) if apply_mode else plan_issue_dir(d))
        except Exception as exc:                    # noqa: BLE001
            # Deliberately broad: whatever one directory does wrong, the other
            # 109 still get migrated and reported. The reason is carried into
            # the report rather than swallowed.
            failed[entry] = "%s: %s" % (type(exc).__name__, exc)
            continue
        if notes:
            changed[entry] = notes

    if not changed and not failed:
        print("compass issue migrate: nothing to do - every issue directory "
              "already speaks schema %s." % COMPASS_SCHEMA_VERSION)
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


# --- relocating human documents to docs/compass/ ----------------------------
#
# Machine state stays where the CLI reads it. `evidence/`, the markers, the TDD
# state file, the manifest and the devlog do not move; moving `evidence/` would
# break every gate in a repository at once, and the devlog is appended to by
# the CLI. Everything else an issue directory holds is a document written for a
# person, and it goes to `docs/compass/<created>-<slug>/`.
STAYS_BESIDE_THE_MANIFEST = {
    "manifest.yml", "devlog.md", "README.md", "architecture-loaded.yml",
    ".red", ".spike", ".acceptance", ".tdd-state.json",
}

#: The one document whose absence beside the manifest stops work.
#: `hooks/pre-tool.sh` reads it to decide whether assessment ran. An install
#: that predates the artifact registry cannot look anywhere else, so moving
#: the file blocks every code edit. Leave a pointer in its place (see
#: `_compatibility_pointer`).
BLOCKING_DOCUMENT = "delivery-approach.md"

#: How the pointer opens. Read to tell a pointer from a real record, so that a
#: second run relocates the record and never the pointer.
POINTER_MARKER = "<!-- compass: moved -->"


def _kind_of(name):
    return name[:-3] if name.endswith(".md") else name


def _relocations(task_dir):
    """(kind, filename, destination) for every document that should move.

    NOTHING MOVES WITHOUT A MANIFEST. The registry is what records where a
    document went, so a directory with no `manifest.yml` has nowhere to record
    it - and a document moved with nothing pointing at it is not relocated, it
    is lost. Such a directory is not an issue anyway; the v1 rename above still
    applies to it and the file stays where the rename left it.

    Two sources, because a migration can be interrupted halfway:

      * a document still beside the manifest - move it, then register it;
      * a document already under `docs/compass/` that the registry does not
        name - leave it where it is and register it.

    The second covers a migration that was interrupted. Without it the only
    way out of an interrupted run is to edit the manifest by hand.
    """
    from compass_pkg.core import docs_dir

    if not os.path.isfile(manifest_path(task_dir)):
        return [], []

    project = _project_root(task_dir)
    dest_rel = docs_dir(task_dir)
    dest_abs = os.path.join(project, dest_rel)

    registry = {}
    manifest = manifest_path(task_dir)
    if os.path.isfile(manifest):
        try:
            with open(manifest, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            for entry in (data.get("artifacts") or []):
                if isinstance(entry, dict) and entry.get("kind"):
                    registry[entry["kind"]] = entry
        except Exception:                            # noqa: BLE001
            registry = {}

    moves, adoptions = [], []
    if os.path.isdir(task_dir):
        for name in sorted(os.listdir(task_dir)):
            if name in STAYS_BESIDE_THE_MANIFEST or not name.endswith(".md"):
                continue
            full = os.path.join(task_dir, name)
            if not os.path.isfile(full):
                continue
            if _is_pointer(full):
                # Left by an earlier run of this migration. Moving it would
                # overwrite the record it points at, with itself.
                continue
            moves.append((_kind_of(name), name,
                          os.path.join(dest_rel, name).replace(os.sep, "/")))

    moved_names = {name for _k, name, _r in moves}
    if os.path.isdir(dest_abs):
        for name in sorted(os.listdir(dest_abs)):
            if not name.endswith(".md") or name in moved_names:
                continue
            kind = _kind_of(name)
            entry = registry.get(kind)
            if entry is not None and entry.get("path"):
                continue                    # already registered - nothing to do
            adoptions.append((kind, name,
                              os.path.join(dest_rel, name).replace(os.sep, "/")))
    return moves, adoptions


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
        `report`, `review_brief`, `package`), the stop evidence of a subtask
        and of a run. `compass issue subtask` and `multiagent-run-recorded`
        join them to the project root.
      * `"issue"` - an `evidence:` entry's `path` and a `friction:` note's
        `evidence`, which gates and readers join to the issue directory.

    `artifacts[].path` is not listed: `_register` rewrites it as each file
    moves. `changed_files[].path` names repository files, not issue
    documents, and `next_task` names an issue by its slug.
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
    for note in dicts(data.get("friction")):
        if isinstance(note.get("evidence"), str):
            yield note, "evidence", "issue"


def _names_file(task_dir, project, raw, source):
    """Does `raw` resolve, from the issue directory or the project root, to
    `source`? Matched by where the path RESOLVES, not by how it is spelled:
    manifests on disk carry both `technical-design.md` and
    `.compass/work/<slug>/technical-design.md`."""
    raw = (raw or "").strip()
    if not raw:
        return False
    task_abs = os.path.abspath(task_dir)
    return source in {os.path.abspath(os.path.join(task_abs, raw)),
                      os.path.abspath(os.path.join(project, raw))}


def _repoint_references(task_dir, filename, project_rel):
    """Repoint every manifest field that named a document we just moved.

    A manifest names its issue's documents in several fields, and each one
    that still names the old place fails a check on an issue nothing is wrong
    with - an evidence entry fails its gate, a stopped subtask's stop evidence
    fails `multiagent-run-recorded`. `_reference_slots` lists the fields.

    Each value is rewritten in the form its reader measures from, and the
    evidence registry stays anchored to the issue directory: re-anchoring it
    to the project root would break every gate in a repository at once.
    So an `evidence:` path becomes a relative path from the issue directory
    to the document's new home - `../../../docs/compass/...` - which is
    exactly what `compass check` resolves against, and a subtask field
    becomes `docs/compass/...`.
    """
    manifest = manifest_path(task_dir)
    if not os.path.isfile(manifest):
        return False
    with open(manifest, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    project = _project_root(task_dir)
    from_issue = os.path.relpath(os.path.join(project, project_rel),
                                 os.path.abspath(task_dir)).replace(os.sep, "/")
    source = os.path.abspath(os.path.join(task_dir, filename))
    changed = False
    for container, key, anchor in list(_reference_slots(data)):
        if _names_file(task_dir, project, container[key], source):
            container[key] = project_rel if anchor == "project" else from_issue
            changed = True
    if not changed:
        return False
    data = prepare_manifest_write(data, manifest)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                          allow_unicode=True)
    tmp = manifest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, manifest)
    return True


def _pointer_owed(task_dir):
    """The registered path of a delivery-approach record with nothing at its
    old name, or None.

    Decide from the state of the tree, not from whether this run moved the
    file: a tree an earlier version migrated has nothing left to move but
    still needs the pointer.
    """
    if os.path.exists(os.path.join(task_dir, BLOCKING_DOCUMENT)):
        return None
    manifest = manifest_path(task_dir)
    if not os.path.isfile(manifest):
        return None
    try:
        with open(manifest, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:                                # noqa: BLE001
        return None
    kind = BLOCKING_DOCUMENT[:-3]
    for entry in (data.get("artifacts") or []):
        if not isinstance(entry, dict) or entry.get("kind") != kind:
            continue
        rel = (entry.get("path") or "").strip()
        # Only when the record is really there. Writing a pointer to a file
        # that does not exist would replace one wrong answer with another.
        if rel and os.path.isfile(os.path.join(_project_root(task_dir), rel)):
            return rel
    return None


def _is_pointer(path):
    """Is this file a compatibility pointer rather than a real document?"""
    try:
        with open(path, encoding="utf-8") as fh:
            return POINTER_MARKER in fh.read(400)
    except OSError:
        return False


def _compatibility_pointer(task_dir, name, rel):
    """Leave a pointer where the delivery-approach record used to be.

    An adopter's `hooks/pre-tool.sh` is a copy installed before the artifact
    registry existed. It tests for this file beside the manifest and blocks
    every code edit in the project when it is missing. Nothing in this
    framework can reach that copy; the migration is the only part of the system
    running on their machine when the documents move, so the compatibility has
    to come from here.

    A POINTER, NOT A COPY. Two copies of a record come to disagree, and the
    out-of-date one looks the same as the real one. This says where the
    record went and nothing else, so a person who opens it is not misled and
    a reader that uses the registry never sees it.
    """
    with open(os.path.join(task_dir, name), "w", encoding="utf-8") as fh:
        fh.write(
            "%s\n"
            "# Moved\n"
            "\n"
            "This issue's %s is now at:\n"
            "\n"
            "    %s\n"
            "\n"
            "The manifest's `artifacts:` registry names that path, and every\n"
            "current reader asks the registry. This file is here only so a\n"
            "Compass installed before the registry existed still finds\n"
            "something at the old name instead of blocking every code edit.\n"
            "\n"
            "Delete it once every install reading this project is current.\n"
            % (POINTER_MARKER, name, rel))


def _register(task_dir, kind, rel):
    """Point the registry entry for `kind` at `rel`, adding one if needed."""
    manifest = manifest_path(task_dir)
    if not os.path.isfile(manifest):
        return False
    with open(manifest, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    arts = [a for a in (data.get("artifacts") or []) if isinstance(a, dict)]
    entry = next((a for a in arts if a.get("kind") == kind), None)
    if entry is None:
        entry = {"id": "ART-" + kind.upper().replace("-", "_"), "kind": kind,
                 "status": "draft",
                 "reason": "found on disk when the documents were relocated"}
        arts.append(entry)
    if entry.get("path") == rel:
        return False
    entry["path"] = rel
    data["artifacts"] = arts
    data = prepare_manifest_write(data, manifest)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False,
                          allow_unicode=True)
    tmp = manifest + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.replace(tmp, manifest)
    return True


def _references_cite(task_dir, filename):
    """Does any manifest field `_reference_slots` lists name this file?"""
    manifest = manifest_path(task_dir)
    if not os.path.isfile(manifest):
        return False
    try:
        with open(manifest, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception:                                # noqa: BLE001
        return False
    project = _project_root(task_dir)
    source = os.path.abspath(os.path.join(task_dir, filename))
    return any(_names_file(task_dir, project, container[key], source)
               for container, key, _anchor in _reference_slots(data))


def plan_relocations(task_dir):
    """Dry-run notes for the relocation half. Writes nothing."""
    moves, adoptions = _relocations(task_dir)
    notes = ["would move %s -> %s, and register it" % (name, rel)
             for _kind, name, rel in moves]
    notes += ["would repoint the manifest fields that cite %s" % name
              for _kind, name, _rel in moves
              if _references_cite(task_dir, name)]
    notes += ["would register %s, already under docs/compass/ and not in the "
              "registry" % rel for _kind, _name, rel in adoptions]
    # Reported here as well as done in the apply, or the dry run promises
    # less than the apply does.
    repair = _pointer_owed(task_dir)
    if repair:
        notes.append("would leave a pointer at %s, which an earlier run moved "
                     "away without one" % BLOCKING_DOCUMENT)
    return notes


def relocate_documents(task_dir):
    """Move this issue's human documents under docs/compass/ and register
    each one. Idempotent: a relocated issue reports nothing."""
    moves, adoptions = _relocations(task_dir)
    repair = _pointer_owed(task_dir)
    if not moves and not adoptions and not repair:
        return []
    project = _project_root(task_dir)
    notes = []
    for kind, name, rel in moves:
        dest = os.path.join(project, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.exists(dest):
            # Both places. Not a move we can make silently - the two files may
            # differ, and picking one would keep whichever happened to be
            # there. Registering the destination and leaving the original is
            # the honest half: the reader gets a definite answer and the stray
            # copy is still on disk to compare.
            _register(task_dir, kind, rel)
            notes.append("%s is in both places - registered %s and left the "
                         "copy beside the manifest for you to compare"
                         % (name, rel))
            continue
        os.replace(os.path.join(task_dir, name), dest)
        _register(task_dir, kind, rel)
        note = "moved %s -> %s, and registered it" % (name, rel)
        if name == BLOCKING_DOCUMENT:
            _compatibility_pointer(task_dir, name, rel)
            note += (", and left a pointer at %s so an install that predates "
                     "the artifact registry is not locked out" % name)
        if _repoint_references(task_dir, name, rel):
            note += " (and repointed the manifest fields that cited it)"
        notes.append(note)
    for kind, _name, rel in adoptions:
        if _register(task_dir, kind, rel):
            notes.append("registered %s, which was already under docs/compass/"
                         % rel)
    if repair:
        _compatibility_pointer(task_dir, BLOCKING_DOCUMENT, repair)
        notes.append("left a pointer at %s, which an earlier run moved away "
                     "without one - an install predating the artifact registry "
                     "blocks every code edit while it is missing"
                     % BLOCKING_DOCUMENT)
    if notes and _regenerate_dashboard(task_dir):
        notes.append("re-rendered README.md, which is generated from the "
                     "registry this run rewrote")
    return notes


def _regenerate_dashboard(task_dir):
    """Re-render the issue's review page, if it has one.

    `README.md` is generated from the artifact registry, and `dashboard-current`
    fails when the two disagree. Writing a `path:` into every entry is exactly
    such a disagreement, so a migration that skipped this would leave a check
    red on every issue that has a review page - and a migration whose only
    visible effect is turning checks red is one nobody runs a second time.
    """
    page_path = os.path.join(task_dir, "README.md")
    if not os.path.isfile(page_path):
        return False
    try:
        from compass_pkg.dashboard import render_dashboard
        page = render_dashboard(task_dir)
    except Exception:                                # noqa: BLE001
        # A page that could not be re-rendered is a failure to report, not a
        # reason to abandon a move that has already happened on disk.
        return False
    with open(page_path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return True


def migrate_issue_dir(task_dir):
    """Migrate one issue directory in place: rename v1-named artifacts and
    rewrite the manifest with v2 keys. Idempotent - a migrated directory is
    left untouched. Returns a list of human-readable change notes."""
    notes = []
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
    # Last, on purpose. The renames above put every document under its current
    # filename, and the manifest is repointed at those names - so relocation
    # moves files whose names are already settled and writes one registry
    # entry per document rather than racing the rename.
    notes.extend(relocate_documents(task_dir))
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
        notes = migrate_issue_dir(d)
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
