#!/usr/bin/env python3
"""Build, check and commit the plugin copy of one commit.

An installed Compass needs only the files `scripts/plugin-files.txt` lists:
the CLI, the hooks, the commands, the skills, the agents and the governance
they read. The plugin directory holds a plugin of more than 512 files, or with
a non-image file over 256 KiB, for a reviewer, and the whole repository is
1,700 files. So each release publishes this copy to the `plugin` branch, and
the marketplace entry fetches the plugin from there.

The copy is taken from the commit's tracked files with `git ls-tree`, never
from the working folder. Before it changes a branch, the script checks the
file limits, that `plugin.json`'s version equals `VERSION` and a `vX.Y.Z`
tag's number, and that every path the copy reads from its own root exists in
it. `--commit` adds the copy as one commit to `plugin`, whose only parent is
the previous copy, so no commit of `main` is in that branch's history.
Only a `vX.Y.Z` tag newer than the branch's release can be committed, and a
local branch that is missing or behind `origin/plugin` is refused, so the
branch never starts a second history. Pushing the branch is the owner's step
(docs/releasing.md, step 11).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FILE_LIST = "scripts/plugin-files.txt"
BRANCH = "plugin"
MAX_FILES = 512
MAX_BYTES = 256 * 1024
# The directory's size limit leaves out images and fonts.
EXEMPT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ttf", ".otf", ".woff", ".woff2")
TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")
# A path a command, skill, agent or hook reads from the plugin's own root.
PLUGIN_ROOT_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")
# A file the CLI reads from its own root, written with literal parts only.
FRAMEWORK_JOIN = re.compile(
    r"os\.path\.join\(\s*(?:core\.)?FRAMEWORK_ROOT\s*,\s*((?:\"[^\"]+\"\s*,\s*)*\"[^\"]+\")\s*\)")


def git(repo, *args, data=None, env=None, text=True):
    return subprocess.run(["git", "-C", repo, *args], input=data, capture_output=True,
                          text=text, check=True, env=env).stdout


def wanted(repo, ref):
    """The include and leave-out lines of the file list, as `ref` holds it.
    A release older than the list, such as v8.0.0, takes this checkout's."""
    keep, drop = [], []
    try:
        text = git(repo, "show", f"{ref}:{FILE_LIST}")
    except subprocess.CalledProcessError:
        with open(os.path.join(os.path.dirname(HERE), FILE_LIST), encoding="utf-8") as fh:
            text = fh.read()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        (drop if line.startswith("!") else keep).append(line.lstrip("!"))
    return keep, drop


def _matches(path, rules):
    return any(path == r or (r.endswith("/") and path.startswith(r)) for r in rules)


def _selected(path, keep, drop):
    """Listed and not left out; a file listed by its full path ships even
    from a folder that is left out."""
    return path in keep or (_matches(path, keep) and not _matches(path, drop))


def entries(repo, ref):
    """The commit's tracked files the list names, as (mode, sha, size, path)."""
    keep, drop = wanted(repo, ref)
    out = []
    for line in git(repo, "ls-tree", "-r", "-z", "--long", ref).split("\0"):
        if not line:
            continue
        meta, path = line.split("\t", 1)
        mode, kind, sha, size = meta.split()
        if _selected(path, keep, drop):
            out.append((mode, kind, sha, int(size) if size != "-" else 0, path))
    return out


def problems(repo, ref, files):
    """Each reason the copy cannot ship, one line per reason."""
    found = []
    paths = {f[4] for f in files}
    folders = {p.rsplit("/", i)[0] for p in paths for i in range(1, p.count("/") + 1)}
    if len(files) > MAX_FILES:
        found.append(f"{len(files)} files; the plugin directory holds a plugin of more than "
                     f"{MAX_FILES} for a reviewer")
    for mode, kind, sha, size, path in files:
        if kind != "blob" or mode == "120000":
            what = "symbolic link" if mode == "120000" else kind
            found.append(f"{path}: a {what}, not a file; the directory needs plain files")
        elif size > MAX_BYTES and not path.lower().endswith(EXEMPT):
            found.append(f"{path}: {size} bytes, over the 256 KiB limit for a file that is "
                         "not an image")

    def blob(path):
        return git(repo, "show", f"{ref}:{path}")

    version = blob("VERSION").strip()
    manifest = json.loads(blob(".claude-plugin/plugin.json")).get("version")
    if manifest != version:
        found.append(f".claude-plugin/plugin.json names version {manifest}; VERSION is {version}")
    tag = TAG.match(ref)
    if tag and tag.group(1) != version:
        found.append(f"the tag {ref} names {tag.group(1)}; VERSION is {version}")

    named = 0
    for mode, kind, sha, size, path in files:
        if kind != "blob" or mode == "120000" or path.lower().endswith(EXEMPT) or path.startswith("cli/vendor/"):
            continue
        try:
            text = git(repo, "cat-file", "blob", sha)
        except UnicodeDecodeError:
            continue
        if path.endswith(".py") or path.startswith("cli/compass"):
            # A Python comment can name another plugin's path; only code reads.
            text = "\n".join(line for line in text.splitlines()
                             if not line.lstrip().startswith("#"))
        targets = [m.rstrip(".") for m in PLUGIN_ROOT_PATH.findall(text)]
        targets += ["/".join(re.findall(r"\"([^\"]+)\"", m)) for m in FRAMEWORK_JOIN.findall(text)]
        for target in targets:
            named += 1
            if target.rstrip("/") not in paths | folders:
                found.append(f"{path} names {target}, which is not in the copy")
    return found, named


def write_out(repo, files, out):
    for mode, kind, sha, size, path in files:
        dest = os.path.join(out, path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as fh:
            fh.write(git(repo, "cat-file", "blob", sha, text=False))
        os.chmod(dest, 0o755 if mode == "100755" else 0o644)


def _ref(repo, name):
    return subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", name],
                          capture_output=True, text=True).stdout.strip()


def _version(text):
    return tuple(int(part) for part in text.split("."))


def commit(repo, ref, files, version):
    """Add the copy to the plugin branch. Returns (exit code, message)."""
    tag = TAG.match(ref)
    if not tag:
        return 1, f"--commit takes a vX.Y.Z release tag, not {ref}"
    source = git(repo, "rev-parse", f"{ref}^{{commit}}").strip()
    tip = _ref(repo, f"refs/heads/{BRANCH}")
    remote = _ref(repo, f"refs/remotes/origin/{BRANCH}")
    if remote and (not tip or subprocess.run(
            ["git", "-C", repo, "merge-base", "--is-ancestor", remote, tip]).returncode != 0):
        return 1, (f"the local {BRANCH} branch is missing or behind origin/{BRANCH}; run "
                   f"`git fetch origin {BRANCH}:{BRANCH}` first, so this release follows the "
                   "published one")
    if tip:
        last = git(repo, "log", "-1", "--format=%B", tip)
        if f"Source-commit: {source}" in last:
            return 0, f"the {BRANCH} branch already holds {ref} ({source[:8]}); nothing added"
        held = re.search(r"^Source-tag: v(\d+\.\d+\.\d+)$", last, re.M)
        if held and _version(tag.group(1)) <= _version(held.group(1)):
            return 1, (f"the {BRANCH} branch holds {held.group(1)}; {ref} is not newer, so it "
                       "would replace a later release")
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": os.path.join(tmp, "index")}
        git(repo, "read-tree", "--empty", env=env)
        git(repo, "update-index", "-z", "--index-info", env=env,
            data="".join(f"{mode} {sha}\t{path}\0" for mode, kind, sha, size, path in files))
        tree = git(repo, "write-tree", env=env).strip()
    message = (f"Compass {version} from {ref} ({source[:8]})\n\n"
               f"Source-tag: {ref}\nSource-commit: {source}\n")
    parents = ["-p", tip] if tip else []
    new = git(repo, "commit-tree", tree, *parents, "-m", message).strip()
    # The old value makes the update fail if the branch moved meanwhile; ""
    # means it must not exist yet.
    git(repo, "update-ref", f"refs/heads/{BRANCH}", new, tip or "")
    return 0, f"added {new[:8]} to {BRANCH}. Push it with: git push origin {BRANCH}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--ref", required=True, help="the commit or vX.Y.Z tag to build from")
    parser.add_argument("--repo", default=os.path.dirname(HERE),
                        help="the repository to read and commit in (default: this one)")
    parser.add_argument("--out", help="also write the copy's files to this folder")
    parser.add_argument("--commit", action="store_true",
                        help=f"add the copy to the local {BRANCH} branch")
    args = parser.parse_args(argv)

    files = entries(args.repo, args.ref)
    found, named = problems(args.repo, args.ref, files)
    if found:
        print(f"build-plugin-copy: the copy of {args.ref} cannot ship:")
        for line in found:
            print(f"  - {line}")
        return 1
    print(f"build-plugin-copy: {len(files)} files from {args.ref}; {named} paths checked")
    if args.out:
        write_out(args.repo, files, args.out)
        print(f"  wrote the copy to {args.out}")
    if args.commit:
        version = git(args.repo, "show", f"{args.ref}:VERSION").strip()
        code, message = commit(args.repo, args.ref, files, version)
        print(f"  {message}")
        return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
