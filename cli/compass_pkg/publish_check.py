# compass_pkg.publish_check - the checks text must pass before it leaves the project
"""Two checks on text Compass is about to post to GitHub, run before any call.

`check(texts, project_root)` reads the comment and, when given, the issue body,
exactly as they would be posted, and returns the first refusal or None:

- **private paths**: a path under `.compass/private/`, or a path to a file git
  ignores in the project, refuses the post. Files under `.compass/work/` and
  `docs/compass/` are posted, because the issue page is made of them, and a
  directory named without a file is posted. The path part of a URL whose
  scheme is not http or https, such as `file://` or `vscode://`, is checked
  like any other path. A web link is posted unless its path names a file
  under `.compass/private/`. Every path is checked in the form it resolves
  to: `_normalise` percent-decodes it until it stops changing, collapses
  `./` and `//`, and resolves `..` before either test runs.
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
import posixpath
import subprocess
from dataclasses import dataclass
from urllib.parse import unquote

from compass_pkg import redact

#: Seconds `git check-ignore` may take, the same bound as a `gh` call.
_TIMEOUT = 15
_BLOCK = re.compile(r"<!-- compass:render ([a-z-]+) -->")
_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s)>\]`'\"]+")
#: A path-like run. `%` is kept so an encoded slash or dot reaches `_normalise`;
#: a run with no slash once decoded is not a path.
_CANDIDATE = re.compile(r"[A-Za-z0-9._%/-]+")
#: A decoded control character ends the path: `git check-ignore --stdin` reads
#: one path a line, so a newline would ask git about a different path.
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_PRIVATE = ".compass/private/"
_WEB = ("http", "https")
#: A file under the private folder named inside a web link.
_PRIVATE_IN_URL = re.compile(re.escape(_PRIVATE) + r"[^/?#]")
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


def _decode(path):
    """`path` percent-decoded until it stops changing, so `%252E` is `.` too."""
    while True:
        decoded = unquote(path)
        if decoded == path:
            return _CONTROL.split(path, maxsplit=1)[0]
        path = decoded


def _normalise(path, project_root=None):
    """The form `path` resolves to, which both private-path tests read.

    Without a project root, `path` is the path part of a web link: it is
    decoded and `./`, `//` and `..` are folded by `posixpath.normpath`. With
    one, it is a path on disk: it is decoded and resolved against the root
    with `os.path.realpath`, and returned as a path from the root when it lies
    inside the project, else as the folded path. A trailing slash is kept,
    because a directory named without a file is posted."""
    decoded = _decode(path)
    trailing = "/" if decoded.endswith("/") else ""
    if project_root is None:
        return posixpath.normpath(decoded) + trailing if decoded else decoded
    root = os.path.realpath(project_root)
    full = os.path.realpath(os.path.join(root, decoded))
    if full.startswith(root + os.sep):
        return os.path.relpath(full, root).replace(os.sep, "/") + trailing
    folded = posixpath.normpath(decoded)
    if folded.startswith("//"):
        folded = "/" + folded.lstrip("/")
    return folded + trailing


def _names_private(path):
    """Whether a normalised path names a file under `.compass/private/`."""
    return bool(_PRIVATE_IN_URL.search(path)) and (
        path.startswith(_PRIVATE) or "/" + _PRIVATE in path)


def _url_paths(text):
    """The text with each URL blanked except the path part of a non-web URL, and
    the index of the first web link into `.compass/private/`, or None. A web
    link names a published file, which git cannot be asked about; a `file://`
    or editor URL names a file on disk, so its path is checked like a path."""
    private = None

    def keep(match):
        nonlocal private
        url = match.group(0)
        scheme, rest = url.split("://", 1)
        slash = rest.find("/")
        start = len(scheme) + 3 + (slash if slash >= 0 else len(rest))
        path = re.split(r"[?#]", url[start:], maxsplit=1)[0]
        if scheme.lower() in _WEB:
            if _names_private(_normalise(path)) and private is None:
                private = match.start()
            return " " * len(url)
        return " " * start + path + " " * (len(url) - start - len(path))

    return _URL.sub(keep, text), private


def _candidates(text, project_root):
    """`(path, index)` for each path-like run that git must be asked about, and the
    index of the first `.compass/private/` path, or None."""
    blanked, private = _url_paths(text)
    asked = []
    for match in _CANDIDATE.finditer(blanked):
        raw = match.group(0).rstrip(".,;:")
        if "/" not in _decode(raw):
            continue
        path = _normalise(raw, project_root)
        if path.endswith("/"):
            continue
        # A file in the private folder is refused by its name alone, inside the
        # project or out of it.
        if _names_private(path):
            private = match.start() if private is None else private
            continue
        # git cannot be asked about a path outside the project.
        if path.startswith("/") or path == ".." or path.startswith("../"):
            continue
        if os.path.isdir(os.path.join(project_root, *path.split("/"))):
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
