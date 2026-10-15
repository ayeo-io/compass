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


def unrestorable_folders(root, label=None):
    """Which issue folders directly under `root` could `git reset --hard` not put back?

    A folder is restorable when the HEAD commit holds every file in it the migrate can
    change, with the bytes on disk: listed by `git ls-tree HEAD`, and not reported by
    `git status` as staged or changed. Files directly under `root` are not judged.
    Outside a work tree, or where git cannot be run, there is no reset to promise and
    the root passes. Inside one, a git call that fails or times out refuses every
    folder that holds a changeable file. Four git calls per root, none of which writes
    to `.git`."""
    label = label or root
    folders = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            files = changeable_files(os.path.join(root, name))
            if files:
                folders[name] = files
    if not folders:
        return Judgement(label, "judged")
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")

    def git(*args, timeout=60, cwd=None):
        return subprocess.run(["git", "-C", cwd or root, "--literal-pathspecs", *args],
                              capture_output=True, env=env, timeout=timeout)
    try:
        inside = git("rev-parse", "--is-inside-work-tree", "--show-toplevel", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return Judgement(label, "no-git")
    lines = os.fsdecode(inside.stdout).splitlines()
    if inside.returncode != 0 or not lines or lines[0].strip() != "true" or len(lines) < 2:
        return Judgement(label, "no-git")
    top = os.path.realpath(lines[1])
    failed = Judgement(label, "git-failed", sorted(folders))
    rel_root = os.path.relpath(os.path.realpath(root), top)
    try:
        head = git("rev-parse", "--verify", "-q", "HEAD", cwd=top, timeout=30)
        held = set()
        if head.returncode == 0:
            tree = git("ls-tree", "-r", "-z", "--name-only", "--full-tree", "HEAD", "--",
                       rel_root, cwd=top)
            if tree.returncode != 0:
                return failed
            held = {_git_text(p) for p in tree.stdout.split(b"\0") if p}
        status = git("status", "--porcelain=v1", "-z", "--untracked-files=no", "--",
                     rel_root, cwd=top)
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
    lost = []
    for name, files in folders.items():
        for path in files:
            rel = _git_text(os.path.relpath(os.path.realpath(path), top).replace(os.sep, "/"))
            if rel not in held or rel in changed:
                lost.append(name)
                break
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
