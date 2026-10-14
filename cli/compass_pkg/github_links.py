# compass_pkg.github_links - a README's links, made to open on GitHub
"""Rewrites the relative links of a README so they work in a GitHub comment.

A relative link means nothing in a comment, so each one is resolved against
the README's folder to a path in the repository and written as one of:

- `https://github.com/<owner>/<name>/blob/<branch>/<path>`, keeping a
  `#fragment`, when the project's `origin` remote is on github.com and git's
  local copy of origin's default branch holds the path;
- the path in code format followed by `(not on <branch>)`, when it does not,
  so a reader is never sent to a page that does not exist;
- the path in code format alone, when there is no github.com `origin` or git
  records no default branch for it.

A link that resolves outside the repository is written as its text alone.
Links inside a code fence, absolute URLs and links to a heading in the same
document are left as they are.

Everything is decided from local git: no network call, so the result depends
only on the files and refs on disk, and an unchanged README rewrites the same
way every time.
"""
# DEPENDENCY: standard library (posixpath, re, subprocess, urllib.parse). Imported only
# by github_page.
from __future__ import annotations

import posixpath
import re
import subprocess
from dataclasses import dataclass
from urllib.parse import quote

#: Seconds one `git` call may take, the same bound as a `gh` call.
_TIMEOUT = 15
_LINK = re.compile(r"(!?)\[([^\]\n]*)\]\(([^)\s]+)\)")
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_GITHUB = re.compile(r"^(?:https://(?:[^@/]+@)?github\.com/|ssh://git@github\.com/"
                     r"|git@github\.com:)([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEAD_PREFIX = "refs/remotes/origin/"


@dataclass(frozen=True)
class LinkBase:
    repo: str | None      # "owner/name" of origin, when it is a github.com URL
    branch: str | None    # origin's default branch, from refs/remotes/origin/HEAD


def _git(args, project_root):
    try:
        done = subprocess.run(["git", *args], cwd=project_root, capture_output=True,
                              text=True, timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def link_base(project_root):
    """The repository and default branch links point at, each None when git does not say."""
    url = (_git(["config", "--get", "remote.origin.url"], project_root) or "").strip()
    found = _GITHUB.match(url)
    head = (_git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], project_root)
            or "").strip()
    branch = head[len(_HEAD_PREFIX):] if head.startswith(_HEAD_PREFIX) else None
    return LinkBase(found.group(1) if found else None, branch or None)


def _fenced(lines):
    """The indexes of the lines inside a code fence that closes."""
    inside, index = set(), 0
    while index < len(lines):
        opened = _FENCE.match(lines[index])
        if opened:
            marker = opened.group(1)
            for later in range(index + 1, len(lines)):
                closer = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[later])
                if closer and closer.group(1)[0] == marker[0] \
                        and len(closer.group(1)) >= len(marker):
                    inside.update(range(index, later + 1))
                    index = later
                    break
        index += 1
    return inside


def _resolve(target, folder):
    """`(path, fragment)` in the repository, `("", "")` for a path outside it, or None
    for a link that is left as it is."""
    if not target or target.startswith(("#", "/")) or _SCHEME.match(target):
        return None
    path, _, fragment = target.partition("#")
    joined = posixpath.normpath(posixpath.join(folder, path)) if path else folder
    if joined == ".." or joined.startswith("../") or joined in ("", "."):
        return "", ""
    return joined, ("#" + fragment if fragment else "")


def _on_branch(paths, base, project_root):
    """The paths git's copy of origin's default branch holds, as files or folders."""
    if not (paths and base.repo and base.branch):
        return set()
    listed = _git(["--literal-pathspecs", "ls-tree", "-r", "--name-only", "--full-tree",
                   _HEAD_PREFIX + base.branch, "--", *sorted(paths)], project_root) or ""
    files = set(listed.splitlines())
    return {p for p in paths if p in files or any(f.startswith(p + "/") for f in files)}


def _written(label, path, fragment, base, held, image=""):
    if not path:
        return label
    if base.repo and base.branch:
        if path in held:
            url = (f"https://github.com/{base.repo}/blob/{quote(base.branch, safe='/')}/"
                   f"{quote(path, safe='/-._~')}{fragment}")
            return f"{image}[{label}]({url})"
        return f"`{path}` (not on {base.branch})"
    return f"`{path}`"


def rewrite_links(text, readme_rel, project_root, base=None):
    """`text` with each relative link outside a code fence rewritten for GitHub."""
    base = base or link_base(project_root)
    folder = posixpath.dirname(readme_rel)
    lines = text.split("\n")
    fenced = _fenced(lines)
    wanted = set()
    for index, line in enumerate(lines):
        if index in fenced:
            continue
        for match in _LINK.finditer(line):
            resolved = _resolve(match.group(3), folder)
            if resolved and resolved[0]:
                wanted.add(resolved[0])
    held = _on_branch(wanted, base, project_root)

    def one(match):
        resolved = _resolve(match.group(3), folder)
        if resolved is None:
            return match.group(0)
        return _written(match.group(2), resolved[0], resolved[1], base, held, match.group(1))

    return "\n".join(line if index in fenced else _LINK.sub(one, line)
                     for index, line in enumerate(lines))


def link_for(rel_path, project_root, label=None, base=None):
    """One repository path, written as `rewrite_links` writes a link to it."""
    base = base or link_base(project_root)
    held = _on_branch({rel_path}, base, project_root)
    return _written(label or rel_path, rel_path, "", base, held)
