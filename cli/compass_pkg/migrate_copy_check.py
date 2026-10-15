# compass_pkg.migrate_copy_check - could `git reset --hard` undo `compass issue migrate --apply`?
"""The copy check `compass issue migrate --apply` runs before it reads anything.

It judges each issue folder under `.compass/work` and `docs/compass`. A folder is
restorable when the HEAD commit holds every file in it the migrate can change, with
the bytes on disk. Without `--i-have-a-copy`, a root that holds a folder git cannot
restore stops the run with one refusal that names a copy command for each such root.
"""
# DEPENDENCY: standard library; compass_pkg.core. compass_pkg.migrate is imported
# inside `changeable_files`, because migrate imports this module.
from __future__ import annotations

import os
import subprocess
import unicodedata
from dataclasses import dataclass, field


@dataclass
class Judgement:
    """What the copy check found for one root (`.compass/work` or `docs/compass`).

    `state` is "no-git" (git cannot be run, or the root is not in a work tree, so
    there is no reset to promise), "judged", or "git-failed" (the root is in a
    repository and git could not be asked, so nothing counts as restorable).
    `unrestorable` holds the issue folder names, sorted."""
    root: str
    state: str
    unrestorable: list = field(default_factory=list)


#: How many issue folders the refusal names for each root, before "and N more".
REFUSAL_NAMES = 5


def changeable_files(folder):
    """The files directly in an issue folder that the migrate can rewrite, move or
    rename: the manifest under either name, each name the rename map holds, and every
    `.md` file. The migrate writes nothing else that is already there, so lock files,
    evidence and editor files are not judged."""
    from compass_pkg.core import MANIFEST_NAMES
    from compass_pkg.migrate import artifact_name_map
    names = set(MANIFEST_NAMES)
    for old, new in artifact_name_map().items():
        names.update((old, new))
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in entries
            if (n in names or n.endswith(".md")) and os.path.isfile(os.path.join(folder, n))]


def _git_text(name):
    """A path as git prints it and as the disk names it, compared alike: macOS git
    prints precomposed names, and a folder on disk can hold either form."""
    return unicodedata.normalize("NFC", os.fsdecode(name))


def registered_files(work_root, docs_root, project):
    """The files the registries name outside the top level of an issue folder, as
    ({work folder: [path]}, {documents folder: [path]}). The migrate edits a registered
    document wherever it is (a verification report in `reports/`, a distribution map it
    renames), so each is judged with the issue folder that holds it, or with the issue's
    work folder when it is in neither root."""
    from compass_pkg import migrate_kinds
    work, docs = {}, {}
    work_root, docs_root = os.path.realpath(work_root), os.path.realpath(docs_root)
    names = sorted(os.listdir(work_root)) if os.path.isdir(work_root) else []
    for slug in names:
        data = migrate_kinds.load_manifest(os.path.join(work_root, slug)) or {}
        for entry in data.get("artifacts") or []:
            rel = entry.get("path") if isinstance(entry, dict) else None
            path = os.path.realpath(os.path.join(project, rel)) if isinstance(rel, str) else ""
            if not rel or not os.path.isfile(path):
                continue
            for base, found in ((docs_root, docs), (work_root, work)):
                if path.startswith(base + os.sep):
                    found.setdefault(os.path.relpath(path, base).split(os.sep)[0], []).append(path)
                    break
            else:
                work.setdefault(slug, []).append(path)
    return work, docs


def _in_a_repository(path):
    """Is `path` inside a git repository? A `.git` in it or a folder above it, below
    any of GIT_CEILING_DIRECTORIES, or GIT_DIR set. Asked of the disk, not of git, so a
    repository git cannot read is still a repository."""
    if os.environ.get("GIT_DIR"):
        return True
    ceilings = {os.path.realpath(c) for c in
                os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep) if c}
    here = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return True
        parent = os.path.dirname(here)
        if parent == here or parent in ceilings:
            return False
        here = parent


def unrestorable_folders(root, label=None, extra=None):
    """Which issue folders under `root` could `git reset --hard` not put back?

    A folder is restorable when the HEAD commit holds every file in it the migrate can
    change with the bytes on disk: the blob `git ls-tree HEAD` names equals the one
    `git hash-object` makes of the file, and `git status` reports no staged change.
    The files judged are those `changeable_files` names, plus `extra` ({folder: [path]}),
    the registered files in subfolders. Files directly under `root` are not judged.
    Outside a repository, or where git cannot be run at all, there is no reset to
    promise and the root passes. Inside one, any git call that fails or times out
    refuses every folder that holds a judged file. None of the calls writes to `.git`."""
    label = label or root
    folders = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            files = changeable_files(os.path.join(root, name))
            if files:
                folders[name] = files
    for name, paths in (extra or {}).items():
        held_paths = folders.setdefault(name, [])
        held_paths += [p for p in paths if p not in held_paths]
    if not folders:
        return Judgement(label, "judged")
    if not _in_a_repository(root):
        return Judgement(label, "no-git")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    failed = Judgement(label, "git-failed", sorted(folders))

    def git(*args, timeout=60, cwd=None, data=None):
        return subprocess.run(["git", "-C", cwd or root, "--literal-pathspecs", *args],
                              capture_output=True, env=env, timeout=timeout, input=data)
    try:
        inside = git("rev-parse", "--is-inside-work-tree", "--show-toplevel", timeout=30)
    except OSError:
        return Judgement(label, "no-git")          # git cannot be run at all
    except subprocess.SubprocessError:
        return failed
    lines = os.fsdecode(inside.stdout).splitlines()
    if inside.returncode != 0 or len(lines) < 2 or lines[0].strip() != "true":
        return failed
    top = os.path.realpath(lines[1])
    rel_root = os.path.relpath(os.path.realpath(root), top)
    judged = {name: [_git_text(os.path.relpath(os.path.realpath(p), top).replace(os.sep, "/"))
                     for p in paths] for name, paths in folders.items()}
    wanted = sorted({rel for rels in judged.values() for rel in rels})
    # The root, and each registered file outside it, so the argument list stays short.
    prefix = "" if rel_root == "." else rel_root.replace(os.sep, "/") + "/"
    specs = [rel_root] + [rel for rel in wanted if not rel.startswith(prefix)]
    try:
        head = git("rev-parse", "--verify", "-q", "HEAD", cwd=top, timeout=30)
        held = {}
        if head.returncode == 0:
            tree = git("ls-tree", "-r", "-z", "--full-tree", "HEAD", "--", *specs, cwd=top)
            if tree.returncode != 0:
                return failed
            for record in tree.stdout.split(b"\0"):
                meta, _tab, path = record.partition(b"\t")
                if path and len(meta.split()) == 3:
                    held[_git_text(path)] = meta.split()[2]
        # One call hashes every file HEAD holds, through the same filters `git add` uses.
        asked = [rel for rel in wanted if rel in held and "\n" not in rel]
        made = {}
        if asked:
            hashed = git("hash-object", "--stdin-paths", cwd=top,
                         data=os.fsencode("\n".join(asked) + "\n"))
            sums = hashed.stdout.split()
            if hashed.returncode != 0 or len(sums) != len(asked):
                return failed
            made = dict(zip(asked, sums))
        status = git("status", "--porcelain=v1", "-z", "--untracked-files=no", "--",
                     *specs, cwd=top)
    except (OSError, subprocess.SubprocessError):
        return failed
    if status.returncode != 0:
        return failed
    changed, fields = set(), status.stdout.split(b"\0")
    i = 0
    while i < len(fields):
        record = fields[i]
        i += 1
        if len(record) < 4:
            continue
        changed.add(_git_text(record[3:]))
        # A rename or copy names its source in the next field; neither path is restorable.
        if b"R" in record[:2] or b"C" in record[:2]:
            if i < len(fields) and fields[i]:
                changed.add(_git_text(fields[i]))
            i += 1
    lost = sorted(name for name, rels in judged.items()
                  if any(made.get(rel) is None or made[rel] != held.get(rel) or rel in changed
                         for rel in rels))
    return Judgement(label, "judged", lost)


def refusal(judgements):
    """The one refusal for every root that holds a folder git cannot restore: per root,
    the count and the first few folders, then one `cp -R` line per root."""
    lines = []
    for found in judgements:
        names = found.unrestorable
        shown = ", ".join(names[:REFUSAL_NAMES])
        if len(names) > REFUSAL_NAMES:
            shown += ", and %d more" % (len(names) - REFUSAL_NAMES)
        lines.append("  %s: %s%d issue folder%s cannot be restored: %s" % (
            found.root, "git could not be asked, so " if found.state == "git-failed" else "",
            len(names), "" if len(names) == 1 else "s", shown))
    why = ("a file the migrate can change in each is not tracked, is gitignored, or is "
           "staged or edited since the last commit")
    if any(found.state == "git-failed" for found in judgements):
        why += ", or git could not be asked"
    return (
        "this would change records that cannot be put back. `git reset --hard` could not "
        "restore the issue folders below, because %s:\n%s\n\n"
        "Nothing was changed. A copy can be taken with:\n%s\n\n"
        "To go on, commit those folders or take a copy, then re-run with --i-have-a-copy. "
        "The flag says you have the copy; it does not switch the check off." % (
            why, "\n".join(lines),
            "\n".join("    cp -R %s <somewhere outside the repository>" % found.root
                      for found in judgements)))
