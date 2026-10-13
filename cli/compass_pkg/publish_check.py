# compass_pkg.publish_check - the checks text must pass before it leaves the project
"""Two checks on text Compass is about to post to GitHub, run before any call.

`check(texts, project_root)` reads the comment and, when given, the issue body,
exactly as they would be posted, and returns the first refusal or None:

- **private paths**: a path under `.compass/private/`, or a path to a file git
  ignores in the project, refuses the post. Files under `.compass/work/` and
  `docs/compass/` are posted, because the issue page is made of them, and a
  directory named without a file is posted.
- **credentials**: text that `redact` would replace refuses the post. It is
  given an empty environment, so no environment variable is read.

A refusal names the check and the README block that holds the hit, never the
hit itself, so the line can go to standard error and to `github-sync.yml`.
A hit refuses the whole post: nothing is redacted and sent.
"""
# DEPENDENCY: compass_pkg.redact; subprocess for `git check-ignore`.
# Imported only by github_page.
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass

from compass_pkg import redact

#: Seconds `git check-ignore` may take, the same bound as a `gh` call.
_TIMEOUT = 15
_BLOCK = re.compile(r"<!-- compass:render ([a-z-]+) -->")
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s)>\]`'\"]+")
_CANDIDATE = re.compile(r"[A-Za-z0-9._/-]*/[A-Za-z0-9._/-]*")
_PRIVATE = ".compass/private/"
#: Folders whose files make up the issue page itself, so naming one is not a leak.
_POSTED = (".compass/work/", "docs/compass/")


@dataclass(frozen=True)
class Refusal:
    check: str     # "private-path" or "credential"
    line: str      # one line for a person; it names the place, never the hit


def _place(name, text, index):
    """Where a hit is: the README block before it, or the issue body."""
    if name == "body":
        return "the issue body"
    blocks = [m.group(1) for m in _BLOCK.finditer(text, 0, index)]
    return f"the README's {blocks[-1]} block" if blocks else "the README"


def _credentials(items):
    for name, text in items:
        cleaned = redact.redact(text, env={})
        if cleaned != text:
            index = next((i for i, (a, b) in enumerate(zip(text, cleaned)) if a != b),
                         min(len(text), len(cleaned)))
            return Refusal("credential",
                           f"the page holds a credential, in {_place(name, text, index)}")
    return None


def _candidates(text, project_root):
    """`(path, index)` for each path-like run that git must be asked about, and the
    index of the first `.compass/private/` path, or None."""
    blanked = _URL.sub(lambda m: " " * len(m.group(0)), text)
    asked, private = [], None
    for match in _CANDIDATE.finditer(blanked):
        path = match.group(0).rstrip(".,;:")
        if "/" not in path or path.endswith("/"):
            continue
        if path.startswith("./"):
            path = path[2:]
        parts = path.split("/")
        # git cannot be asked about an absolute path or one that climbs out of the
        # project, but a file in the private folder is refused by its name alone.
        if path.startswith("/") or ".." in parts:
            if "/" + _PRIVATE in path:
                private = match.start() if private is None else private
            continue
        if os.path.isdir(os.path.join(project_root, *parts)):
            continue
        if path.startswith(_PRIVATE):
            private = match.start() if private is None else private
            continue
        if path.startswith(_POSTED):
            continue
        asked.append((path, match.start()))
    return asked, private


def _ignored(paths, project_root):
    """The paths git ignores in the project, or None when git cannot say."""
    try:
        done = subprocess.run(["git", "check-ignore", "--stdin"], cwd=project_root,
                              input="\n".join(paths) + "\n", capture_output=True,
                              text=True, timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode not in (0, 1):
        return None
    return {line.strip() for line in done.stdout.splitlines() if line.strip()}


def _private_paths(items, project_root):
    found = {name: _candidates(text, project_root) for name, text in items}
    for name, text in items:
        if found[name][1] is not None:
            return _private_refusal(name, text, found[name][1])
    asked = sorted({path for _, (pairs, _) in found.items() for path, _ in pairs})
    if not asked:
        return None
    ignored = _ignored(asked, project_root)
    if ignored is None:
        return Refusal("private-path", "cannot check ignored files: `git check-ignore` failed")
    for name, text in items:
        for path, index in found[name][0]:
            if path in ignored:
                return _private_refusal(name, text, index)
    return None


def _private_refusal(name, text, index):
    return Refusal("private-path", "the page names a file the project keeps out of git, in "
                                   + _place(name, text, index))


def check(texts, project_root):
    """The first refusal for the texts to post, or None. `texts` is
    `{"comment": str, "body": str | None}`; a body of None is not checked."""
    items = [(name, texts.get(name)) for name in ("comment", "body")
             if isinstance(texts.get(name), str)]
    return _private_paths(items, project_root) or _credentials(items)
