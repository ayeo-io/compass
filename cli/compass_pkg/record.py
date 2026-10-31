#!/usr/bin/env python3
# =============================================================================
# compass - keep the delivery record in a second repository
# =============================================================================
# A project keeps its issue records out of its own git history (.compass/work,
# docs/compass/<created>-<slug>/), so they exist on one machine. `compass
# record sync` copies the paths the project's settings name under `record:`
# into the repository it names, with credentials redacted, and commits and
# pushes them. `ship-commit` runs it after every landing (ADR-031). `compass
# record restore` copies the record back into a project, such as a fresh
# clone.
#
# The clone of the record repository lives in the user's cache folder, never
# inside the project, so the project can never commit it by mistake.
#
# DEPENDENCY: standard library (hashlib, os, shutil, subprocess) and
# compass_pkg (core, effective, redact, rival_names).
# =============================================================================
"""`compass record sync|restore`: the delivery record in its own repository."""
from __future__ import annotations

import hashlib
import os
import posixpath
import shutil
import subprocess

from compass_pkg import project_settings
from compass_pkg.core import CompassError, find_compass_dir, load_yaml
from compass_pkg.redact import MARK as REDACTED, redact
from compass_pkg import rival_names

#: The branch the record is kept on.
BRANCH = "main"

#: Settings that turn LFS filters off in the clone: a record's own
#: `.lfsconfig` must not make git contact another server, and the record
#: is copied as it is stored.
_NO_LFS = (("filter.lfs.process", ""), ("filter.lfs.smudge", "cat"),
           ("filter.lfs.clean", "cat"), ("filter.lfs.required", "false"))


def settings(project_root):
    """`(remote, paths)` from the project's settings, or None when the
    project names no record."""
    try:
        config = project_settings.settings(project_root)
    except Exception as exc:                            # noqa: BLE001
        raise CompassError(f"compass record: the project's settings cannot "
                           f"be read: {exc}")
    record = config.get("record")
    if not record:
        return None
    remote = record.get("remote") if isinstance(record, dict) else None
    paths = record.get("paths") if isinstance(record, dict) else None
    if not isinstance(remote, str) or not remote.strip() \
            or not isinstance(paths, list) or not paths \
            or not all(isinstance(p, str) and p.strip() for p in paths):
        raise CompassError(
            "compass record: %s needs a `remote:` (the record repository) "
            "and a list of `paths:`." % project_settings.named(
                project_root, "record"))
    cleaned = []
    for raw in paths:
        stripped = raw.strip()
        rel = posixpath.normpath(stripped) if stripped else ""
        parts = rel.split("/")
        # Checked after trimming and normalising, so " ../x" and "./.git"
        # cannot slip past. `.` and any `.git` part are refused: syncing
        # either would carry git's own state, and could point the record
        # at another remote.
        # Compared without case: on a file system that ignores case, `.Git`
        # is the same folder as `.git`.
        if not rel or os.path.isabs(rel) or ".." in parts or rel == "." \
                or ".git" in (p.lower() for p in parts):
            raise CompassError(f"compass record: the path {raw!r} is not a "
                               f"folder or file inside the project.")
        cleaned.append(rel)
    return remote.strip(), cleaned


def names_key(project_root):
    """The names key `record.names_key` sets, or None when it sets none.
    Found from `COMPASS_RIVALS_KEY`, then the configured path in the
    project, then the same path in the main checkout: the key is never
    committed, so a linked worktree, where ship syncs from, has none of its
    own. A key that is configured but found nowhere is refused, so the
    record never receives names for want of it."""
    record = project_settings.settings(project_root).get("record")
    configured = record.get("names_key") if isinstance(record, dict) else None
    if not configured:
        return None
    if not isinstance(configured, str) or os.path.isabs(configured) \
            or ".." in configured.replace("\\", "/").split("/"):
        raise CompassError("compass record: `record.names_key` must be a "
                           "path inside the project.")
    candidates = [os.environ.get("COMPASS_RIVALS_KEY", ""),
                  _inside(project_root, configured)]
    common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"],
                  project_root).stdout.strip()
    if common:
        main = os.path.dirname(common)
        candidates.append(_inside(main, configured))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    raise CompassError(
        f"compass record sync: the names key {configured} is configured but "
        f"missing, so the record would receive rival product names. Nothing "
        f"was synced. Put the key there, or set COMPASS_RIVALS_KEY.")


def _inside(root, rel):
    """`root/rel`, refused when it resolves outside `root` or into its
    `.git` folder."""
    real_root = os.path.realpath(root)
    full = os.path.realpath(os.path.join(root, rel))
    if os.path.commonpath([real_root, full]) != real_root or \
            _in_git_dir(real_root, full):
        raise CompassError(f"compass record: the path {rel!r} leads outside "
                           f"the project, or into git's own folder.")
    return full


def _in_git_dir(root, full):
    """Is `full`, or a folder above it inside `root`, git's own folder?
    Compared by file identity, not by name, so no spelling of `.git` (other
    capitals, a link, a relative detour) gets past it."""
    git_dir = os.path.join(root, ".git")
    if not os.path.exists(git_dir):
        return False
    path = full
    while os.path.commonpath([root, path]) == root and path != root:
        if os.path.exists(path) and os.path.samefile(path, git_dir):
            return True
        path = os.path.dirname(path)
    return False


def linked_worktree(project_root):
    """Is this a linked worktree, which holds only part of the record?"""
    git_dir = _git(["rev-parse", "--git-dir"], project_root).stdout.strip()
    common = _git(["rev-parse", "--git-common-dir"], project_root).stdout.strip()
    return bool(git_dir and common) and \
        os.path.realpath(os.path.join(project_root, git_dir)) != \
        os.path.realpath(os.path.join(project_root, common))


def _git(args, cwd):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CompassError(f"compass record: git could not run: {exc}")


def _must(result, what):
    if result.returncode != 0:
        raise CompassError(f"compass record: {what} failed: "
                           f"{(result.stderr or result.stdout).strip()}")
    return result


def _clone_dir(remote):
    cache = os.environ.get("XDG_CACHE_HOME", "")
    if not os.path.isabs(cache):
        # A relative cache path would put the clone in the working folder.
        cache = os.path.join(os.path.expanduser("~"), ".cache")
    digest = hashlib.sha256(remote.encode("utf-8")).hexdigest()[:16]
    return os.path.join(cache, "compass", "record", digest)


def _fresh_clone(remote):
    """The record repository's clone, brought up to date. An empty remote
    gives a clone with no commits, which the first sync fills."""
    clone = _clone_dir(remote)
    if os.path.isdir(os.path.join(clone, ".git")):
        origin = _git(["remote", "get-url", "origin"], clone).stdout.strip()
        push = _git(["remote", "get-url", "--push", "origin"], clone).stdout.strip()
        if origin != remote or push != remote:
            # A cache whose origin moved would push the record elsewhere.
            shutil.rmtree(clone, ignore_errors=True)
    if not os.path.isdir(os.path.join(clone, ".git")):
        shutil.rmtree(clone, ignore_errors=True)
        os.makedirs(os.path.dirname(clone), exist_ok=True)
        flags = [arg for key, value in _NO_LFS for arg in ("-c", f"{key}={value}")]
        _must(_git([*flags, "clone", "-q", remote, clone], None),
              "cloning the record")
        for key, value in _NO_LFS:
            _must(_git(["config", key, value], clone), "configuring the clone")
    else:
        _must(_git(["fetch", "-q", "origin"], clone), "fetching the record")
    # Always the record's own branch: a remote whose default branch is
    # another one would otherwise give a clone with nothing checked out,
    # and a restore on a new machine would find an empty record.
    has_branch = _git(["rev-parse", "--verify", "-q",
                       f"origin/{BRANCH}"], clone).returncode == 0
    if has_branch:
        _must(_git(["checkout", "-q", "-B", BRANCH, f"origin/{BRANCH}"],
                   clone), "checking out the record")
        _must(_git(["reset", "-q", "--hard", f"origin/{BRANCH}"], clone),
              "resetting the record")
    _must(_git(["clean", "-qfd"], clone), "cleaning the record clone")
    _refuse_links(clone)
    return clone


def _refuse_links(clone):
    """Refuse a record that holds a symbolic link. Nothing in the record is
    trusted to point anywhere: a link could lead a sync to write into git's
    own folder or outside the clone, or a restore to copy any file on the
    machine into the project."""
    listed = _must(_git(["ls-files", "-s"], clone), "listing the record").stdout
    modules = [line.split("\t", 1)[-1] for line in listed.splitlines()
               if line.startswith("160000 ")]
    if modules:
        raise CompassError(
            f"compass record: the record repository holds a submodule entry "
            f"({', '.join(modules[:5])}), which Compass never writes and which "
            f"can hide files from a sync. Remove it from the record before "
            f"syncing or restoring.")
    links = [line.split("\t", 1)[-1] for line in listed.splitlines()
             if line.startswith("120000 ")]
    if links:
        shown = ", ".join(links[:5])
        raise CompassError(
            f"compass record: the record repository holds a symbolic link "
            f"({shown}), which Compass never writes. Remove it from the "
            f"record before syncing or restoring.")


def _copy_file(source, target, names=None, written=None):
    """Copy one file, with credentials redacted and, given a names key,
    rival product names replaced by their codes."""
    if os.path.islink(source):
        return  # a link could lead anywhere on the machine
    os.makedirs(os.path.dirname(target), exist_ok=True)
    if written is not None:
        written.append(target)
    with open(source, "rb") as fh:
        data = fh.read()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        shutil.copyfile(source, target)
        return
    text = redact(text)
    if names:
        text = rival_names.redact_names(text, names)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(text)


def _mirror(source_root, target_root, rel, prune, names=None, written=None):
    """Copy `source_root/rel` into `target_root/rel`, redacted. With
    `prune`, first remove what the source no longer has; without it, the
    record only gains and updates files, so a partial checkout loses
    nothing from it."""
    source = _inside(source_root, rel)
    # The record path itself can hold a name, such as an issue folder
    # synced alone from a worktree.
    target = _inside(target_root,
                     rival_names.redact_names(rel, names) if names else rel)
    if prune:
        if os.path.isdir(target):
            shutil.rmtree(target)
        elif os.path.exists(target):
            os.remove(target)
    if os.path.isfile(source):
        _copy_file(source, target, names, written)
        return
    for base, dirs, files in os.walk(source):
        # A nested `.git`, in any case, is git's own state, never record.
        dirs[:] = sorted(d for d in dirs if d != "__pycache__"
                         and d.lower() != ".git"
                         and not os.path.islink(os.path.join(base, d)))
        for name in sorted(files):
            if name.endswith(".pyc") or name == ".DS_Store" \
                    or name.lower() == ".git":
                continue
            full = os.path.join(base, name)
            inner = os.path.relpath(full, source)
            if names:
                inner = rival_names.redact_names(inner, names)
            _copy_file(full, os.path.join(target, inner), names, written)


def _record_files(clone):
    """Every file in the record clone, as `(full path, path in the record)`,
    outside git's own folder, in a stable order."""
    for base, dirs, files in os.walk(clone):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for name in sorted(files):
            full = os.path.join(base, name)
            yield full, os.path.relpath(full, clone)


def _listed(paths, limit):
    """`paths` joined for a message, at most `limit` of them."""
    shown = ", ".join(paths[:limit])
    if len(paths) > limit:
        shown += f" and {len(paths) - limit} more"
    return shown


def _staged_deletions(clone):
    """The record files the staged change deletes: what a push would
    remove from the record."""
    _must(_git(["add", "-A", "--force"], clone), "staging the record")
    listed = _must(_git(["diff", "--cached", "--name-only", "--no-renames",
                         "--diff-filter=D", "-z"], clone),
                   "listing the prune's deletions").stdout
    return [p for p in listed.split("\0") if p]


def _refuse_unconfirmed_prune(deleted, names):
    """Refuse a prune that would delete record files and was not confirmed
    with --apply, naming the files with any rival name masked. A prune
    deletes every record file this checkout lacks, such as an issue landed
    from another worktree or machine, so it is never run blind
    (ayeo-io/compass-delivery#339)."""
    raise CompassError(
        f"compass record sync --prune: would remove {len(deleted)} file(s) "
        f"from the record, at paths this checkout does not hold: "
        f"{_listed(_masked(deleted, names), 20)}. Nothing was committed or "
        f"pushed. Check that this checkout holds the whole record, then run "
        f"`compass record sync --prune --apply` to delete them.")


def _masked(paths, names):
    """`paths` with any rival name masked, when a names key is set."""
    hashes = rival_names.hashes_from_key(names) if names else None
    return [rival_names.mask(p, hashes) if hashes else p for p in paths]


def _redact_existing(clone, names, written, pins=()):
    """Rewrite each record file this sync did not write whose text or path
    names a rival: its text with names replaced by codes, and a named path
    moved to its coded path. Nothing is removed without its content being
    written elsewhere in the record. A file is left as it is when its coded
    path is already taken or it is binary with a name in its content; the
    hint then lists it. Returns how many files were rewritten."""
    hashes = rival_names.hashes_from_key(names)
    done = {os.path.realpath(t) for t in written}
    rewritten = 0
    for full, rel in list(_record_files(clone)):
        if os.path.realpath(full) in done:
            continue
        with open(full, "rb") as fh:
            data = fh.read()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        in_path = bool(rival_names.scan(rel, hashes))
        in_text = text is not None and bool(rival_names.scan(text, hashes))
        if not (in_path or in_text):
            continue
        if text is None and not rival_names.is_pinned(rel, data, pins) \
                and rival_names.scan(rival_names.readable_text(data), hashes):
            continue  # a binary file cannot be rewritten safely
        new_rel = rival_names.redact_names(rel, names) if in_path else rel
        new_data = rival_names.redact_names(text, names).encode("utf-8") \
            if in_text else data
        if new_rel == rel and new_data == data:
            continue  # nothing to change; the hint lists it
        target = _inside(clone, new_rel)
        if new_rel != rel and os.path.lexists(target):
            continue  # the coded path holds another file
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
        except (FileExistsError, NotADirectoryError):
            continue  # a file holds the coded folder's name
        with open(target, "wb") as fh:
            fh.write(new_data)
        if new_rel != rel:
            os.remove(full)
        rewritten += 1
    return rewritten


def _check_names(clone, names, written, pins=(), redacted_existing=False):
    """Refuse the sync if a file or path it wrote still names a rival; list
    the earlier record files that do. Only what this sync wrote is refused,
    so files from before the key was configured do not block every sync;
    `--redact-existing` rewrites them in place. The hint never names
    `--prune`, which deletes every record file this checkout lacks. A
    binary file pinned in the gate's pin file, by blob hash and path, is
    not scanned, as in the gate."""
    hashes = rival_names.hashes_from_key(names)
    found = []
    for target in written:
        rel = os.path.relpath(target, clone)
        with open(target, "rb") as fh:
            data = fh.read()
        text = "" if rival_names.is_pinned(rel, data, pins) \
            else rival_names.readable_text(data)
        if rival_names.scan(rel, hashes) or rival_names.scan(text, hashes):
            found.append(rival_names.mask(rel, hashes))
    if found:
        raise CompassError(
            f"compass record sync: {len(found)} file(s) still name a rival "
            f"product after redaction, so nothing was committed: "
            f"{', '.join(found[:5])}")
    done = {os.path.realpath(t) for t in written}
    earlier = []
    for full, rel in _record_files(clone):
        if os.path.realpath(full) in done:
            continue
        with open(full, "rb") as fh:
            data = fh.read()
        text = "" if rival_names.is_pinned(rel, data, pins) \
            else rival_names.readable_text(data)
        if rival_names.scan(rel, hashes) or rival_names.scan(text, hashes):
            earlier.append(rival_names.mask(rel, hashes))
    if not earlier:
        return ""
    shown = _listed(earlier, 5)
    if redacted_existing:
        return (f"; {len(earlier)} earlier record file(s) still name a rival "
                f"product and could not be rewritten in place, because the "
                f"coded path is taken or the file is binary: {shown}. Edit "
                f"them in the record repository")
    return (f"; {len(earlier)} earlier record file(s) still name a rival "
            f"product: {shown}. `compass record sync --redact-existing` "
            f"rewrites them in place and deletes nothing")


def _identity(project_root):
    def value(key, default):
        found = _git(["config", key], project_root)
        return found.stdout.strip() if found.returncode == 0 and \
            found.stdout.strip() else default
    return value("user.name", "compass"), value("user.email", "compass@localhost")


def sync(project_root, prune=False, only=None, apply=False,
         redact_existing=False):
    """Copy the configured paths, or just `only`, into the record
    repository, and commit and push them. Returns a line saying what
    happened.

    A linked worktree holds only part of the record, so a full sync from one
    is refused; ship syncs just the landed issue's folders from it. A
    `prune` that would delete record files is refused, naming them, unless
    `apply` confirms it. `redact_existing` rewrites earlier record files
    that name a rival, in place."""
    if apply and not prune:
        raise CompassError("compass record sync: --apply confirms a prune's "
                           "deletions, so it needs --prune.")
    found = settings(project_root)
    if found is None:
        return "no record is configured (%s)" % project_settings.named(
            project_root, "record")
    remote, paths = found
    key_path = names_key(project_root)
    names = rival_names.load_key(key_path) if key_path else None
    if only is None and linked_worktree(project_root):
        raise CompassError(
            "compass record sync: this is a linked worktree, which holds only "
            "part of the record. Run a full sync from the main checkout.")
    if only is not None:
        # Only what the record holds: an issue folder outside every
        # configured path is not synced.
        paths = [rel for rel in only
                 if os.path.exists(os.path.join(project_root, rel))
                 and any(rel == p or rel.startswith(p + "/") for p in paths)]
    clone = _fresh_clone(remote)
    skipped = []
    written = []
    for rel in paths:
        if not os.path.exists(os.path.join(project_root, rel)):
            # A whole path absent from this checkout, such as an ignored
            # folder a worktree never had, is skipped, not deleted from the
            # record: its absence here says nothing about the record.
            skipped.append(rel)
            continue
        _mirror(project_root, clone, rel, prune, names, written)
    note = (f" ({', '.join(skipped)} not in this checkout, so left as "
            f"recorded)" if skipped else "")
    deleted = _staged_deletions(clone) if prune else []
    if deleted and not apply:
        _refuse_unconfirmed_prune(deleted, names)
    # Named in the output and in the record's commit: a file that reached
    # the record after the listing run is never deleted unseen.
    shown_deleted = _masked(deleted, names)
    if deleted:
        note += (f"; deleted {len(deleted)} record file(s) this checkout "
                 f"does not hold: {_listed(shown_deleted, 20)}")
    pins = rival_names.load_pins(
        os.path.join(project_root, "scripts", rival_names.PINS_NAME)) \
        if names else ()
    if redact_existing and names:
        count = _redact_existing(clone, names, written, pins)
        note += (f"; rewrote {count} earlier record file(s) that named a "
                 f"rival product, deleting none")
    elif redact_existing:
        note += ("; no names key is configured (record.names_key), so "
                 "--redact-existing rewrote nothing")
    if names:
        note += _check_names(clone, names, written, pins, redact_existing)
    # --force: a `.gitignore` in the record must not hide files from it.
    _must(_git(["add", "-A", "--force"], clone), "staging the record")
    if not _git(["status", "--porcelain"], clone).stdout.strip():
        return "nothing to sync: the record already matches" + note
    head = _git(["rev-parse", "--short=12", "HEAD"], project_root).stdout.strip()
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], project_root).stdout.strip()
    name, email = _identity(project_root)
    body = (["-m", "Deleted by --prune --apply:\n" + "\n".join(shown_deleted)]
            if deleted else [])
    _must(_git(["-c", f"user.name={name}", "-c", f"user.email={email}",
                "-c", "commit.gpgsign=false", "commit", "-q", "-m",
                f"Record at {head or 'no commit'} ({branch or 'no branch'})",
                *body], clone), "committing the record")
    _must(_git(["push", "-q", "origin", f"HEAD:{BRANCH}"], clone),
          "pushing the record")
    return f"record synced to {remote} at {head}" + note


def _redacted_generation_file(parts, full):
    """Is the record file at `full`, at path `parts`, one of a generation's
    stored files with a line a sync redacted? A sync before 7.0.0 redacted
    ordinary lines too; a sync now redacts only a line shaped like a
    credential. The generation's marker holds a digest of each file, so a
    restored copy breaks it."""
    # Only `effective` imports the generation store (ADR-036), so the names
    # come from there, and only when a restore runs.
    from compass_pkg.effective import GENERATION_DIRECTORY, GENERATION_FILES
    if len(parts) < 3 or parts[-3] != GENERATION_DIRECTORY \
            or parts[-1] not in GENERATION_FILES:
        return False
    with open(full, "rb") as fh:
        return REDACTED.encode() in fh.read()


def _redacted_refusal(redacted):
    shown = "\n  ".join(sorted(redacted)[:10])
    if len(redacted) > 10:
        shown += f"\n  ... and {len(redacted) - 10} more"
    return (
        f"compass record restore: {len(redacted)} generation file(s) in the record "
        f"hold {REDACTED}, so a restored copy would make the generation broken and "
        f"compass check would refuse the issue:\n  {shown}\n"
        f"Restored nothing. Run `compass record sync` on a machine whose copy of "
        f"the folder is whole, to replace the record's copy. That works only when "
        f"the file has no line shaped like a credential, which a sync redacts again. "
        f"Otherwise remove the folder from the record, restore, then remove the "
        f"`generation:` line of the issue's manifest.yml and run `compass approach "
        f"evaluate --write` to store a new generation.")


def restore(project_root, force=False):
    """Copy the record's paths back into the project. Refuses to overwrite
    a file that differs unless `force`, and refuses, whatever `force`, a
    redacted generation file."""
    found = settings(project_root)
    if found is None:
        raise CompassError("compass record restore: no record is configured "
                           "(%s)." % project_settings.named(
                               project_root, "record"))
    remote, paths = found
    clone = _fresh_clone(remote)
    pairs, differ, redacted = [], [], []
    for rel in paths:
        source = os.path.join(clone, rel)
        files = [source] if os.path.isfile(source) else [
            os.path.join(b, n) for b, _, ns in os.walk(source) for n in ns]
        for full in files:
            parts = os.path.relpath(full, clone).split(os.sep)
            if any(p.lower() == ".git" for p in parts) or os.path.islink(full):
                continue
            target = os.path.join(project_root, os.path.relpath(full, clone))
            if os.path.isfile(target):
                with open(full, "rb") as a, open(target, "rb") as b:
                    if a.read() == b.read():
                        continue
            if _redacted_generation_file(parts, full):
                redacted.append(os.path.relpath(target, project_root))
                continue
            if os.path.isfile(target):
                differ.append(os.path.relpath(target, project_root))
            pairs.append((full, target))
    if redacted:
        raise CompassError(_redacted_refusal(redacted))
    if differ and not force:
        shown = "\n  ".join(sorted(differ)[:10])
        more = f"\n  ... and {len(differ) - 10} more" if len(differ) > 10 else ""
        raise CompassError(
            f"compass record restore: {len(differ)} file(s) here differ from "
            f"the record, and restoring would overwrite them:\n  {shown}{more}\n"
            f"Pass --force to overwrite them.")
    for full, target in pairs:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(full, target)
    if not pairs and not any(
            os.path.exists(os.path.join(clone, rel)) for rel in paths):
        return (f"restored nothing: the record at {remote} holds nothing "
                f"under {', '.join(paths)}")
    return f"restored {len(pairs)} file(s) from {remote}"


def _project_root():
    return os.path.dirname(find_compass_dir())


def cmd_record_sync(args):
    said = sync(_project_root(), prune=args.prune, apply=args.apply,
                redact_existing=args.redact_existing)
    print(f"compass record sync: {said}.")
    return 0


def cmd_record_restore(args):
    print(f"compass record restore: {restore(_project_root(), args.force)}.")
    return 0


def register(sub):
    """Add `compass record sync|restore` to the top-level parser."""
    p = sub.add_parser(
        "record", help="keep the delivery record in a second repository",
        description="The paths the `record:` setting names, kept "
                    "in the repository it names (ADR-031). ship-commit runs "
                    "`sync` after every landing.")
    subs = p.add_subparsers(dest="record_cmd", required=True)
    s = subs.add_parser(
        "sync", help="copy the record's paths, redacted, commit and push",
        description="Copy the paths `record:` names into the record "
                    "repository, redacting credentials, and commit and push "
                    "them. It adds and updates; it deletes only with "
                    "--prune --apply. A full sync from a linked worktree is "
                    "refused; ship-commit there syncs only the landed "
                    "issue's folders. A record that holds a symbolic link "
                    "is refused.")
    s.add_argument("--prune", action="store_true",
                   help="also delete from the record every file this "
                        "checkout does not hold. Without --apply it lists "
                        "those files and commits and pushes nothing")
    s.add_argument("--apply", action="store_true",
                   help="with --prune: delete the files the prune lists")
    s.add_argument("--redact-existing", action="store_true",
                   help="also rewrite earlier record files that name a "
                        "rival product: names become codes in their text and "
                        "paths. It deletes nothing")
    s.set_defaults(func=cmd_record_sync, output_kind="hand-off")
    r = subs.add_parser(
        "restore", help="copy the record's paths back into this project",
        description="Copy the record's paths back into this project, such "
                    "as a fresh clone. Refuses to overwrite a file that "
                    "differs from the record unless --force is given, and "
                    "refuses a record that holds a symbolic link.")
    r.add_argument("--force", action="store_true",
                   help="overwrite files here that differ from the record")
    r.set_defaults(func=cmd_record_restore, output_kind="hand-off")
