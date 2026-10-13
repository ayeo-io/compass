# compass_pkg.publish_check - the checks text must pass before it leaves the project
"""Two checks on text Compass is about to post to GitHub, run before any call.

`check(texts, project_root)` reads the comment and, when given, the issue body,
exactly as they would be posted, and returns the first refusal or None:

- **private paths**: a file under `.compass/private/`, or a file git ignores
  in the project, refuses the post. The whole text is decoded first, before
  any path is picked out of it: `_decode` undoes HTML character references
  and percent-encoding until the text stops changing, and reads a backslash
  as a slash. It decodes the text twice, once taking only references closed
  by `;` and once taking those without one too, and checks both results. A
  decoded text that names a file under `.compass/private/`, at any position
  and joined to any word, refuses. The decoded text is then cut
  into pieces at every character that cannot be part of a path, and each
  piece with a slash is normalised by `_normalise` and asked of git as
  written; symlinks are followed only for the private-folder test. Files
  under `.compass/work/` and `docs/compass/` are posted, because the issue
  page is made of them, a folder named without a file is posted, and a web
  link names a path outside the project, so only the private-folder test
  reads it.
- **credentials**: text that `redact` would replace refuses the post. It is
  given an empty environment, so no environment variable is read.

A refusal names the check and the README block that holds the hit, never the
hit itself, so the line can go to standard error and to `github-sync.yml`.
A hit refuses the whole post: nothing is redacted and sent.
"""
# DEPENDENCY: compass_pkg.redact; subprocess for `git check-ignore`.
# Imported only by github_page.
from __future__ import annotations

import html
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
#: A piece of decoded text that can be a path. Every other character, such as
#: whitespace, a control character, `;`, `&`, `#`, `?`, a quote or a bracket,
#: ends a piece, so a word joined to a path does not hide it.
_PIECE = re.compile(r"[\w.~/-]+")
#: A file under the private folder: the folder name followed by a file name.
#: The folder named on its own is posted, like any folder.
_PRIVATE_FILE = re.compile(r"\.compass/private/[\w.~-]")
#: An HTML character reference closed by `;`.
_REFERENCE = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")
#: The authority of a URL, `//host`, at the start of a piece. Without it the
#: rest is the path the URL names, as `vscode://file/<path>` names `<path>`.
_AUTHORITY = re.compile(r"^//[^/]*")
#: `/.` as a whole path segment, which names the folder it ends.
_DOT_SEGMENT = re.compile(r"/\.(?=/|[^\w.~-]|$)")
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


def _strict_unescape(text):
    """HTML character references closed by `;`, the only ones Markdown reads."""
    return _REFERENCE.sub(lambda m: html.unescape(m.group(0)), text)


def _decode(text, loose):
    """`text` with HTML character references and percent-encoding undone until
    it stops changing, so `%252E`, `&#46;` and `&amp;#46;` are all `.`, and a
    backslash read as a slash, as a browser reads it in a web address. Each
    pass that changes the text shortens it, so the loop ends.

    Markdown reads only references closed by `;`, but an HTML parser also
    reads some without one, such as `&#46` or `&not`. Neither decoding is
    safe alone - the loose one turns `&notes/` into `¬es/` - so the text is
    decoded both ways (`loose` False, then True) and both are checked."""
    unescape = html.unescape if loose else _strict_unescape
    while True:
        decoded = unescape(unquote(text))
        if decoded == text:
            return text.replace("\\", "/")
        text = decoded


def _fold_text(text):
    """`text` with `//` collapsed and `/.` segments dropped, so the folder test
    reads `.compass/./private/` and `.compass//private/` as the folder."""
    while True:
        folded = _DOT_SEGMENT.sub("", re.sub(r"/{2,}", "/", text))
        if folded == text:
            return text
        text = folded


def _fold(path):
    """`path` with `./`, `//` and `..` folded, keeping a trailing slash, because
    a directory named without a file is posted."""
    folded = posixpath.normpath(path)
    if folded.startswith("//"):
        folded = "/" + folded.lstrip("/")
    return folded + ("/" if path.endswith("/") and folded != "/" else "")


def _from_root(path, roots):
    """An absolute `path` as a path from the first root holding it, or None."""
    for root in roots:
        if path.startswith(root.rstrip(os.sep) + os.sep):
            return os.path.relpath(path, root).replace(os.sep, "/")
    return None


def _normalise(piece, project_root):
    """`(forms, written)` for a piece of decoded text.

    `written` is the piece folded against the project root without following
    symlinks, because git tracks a symlink by its own path: that is the form
    git is asked about. `forms` adds the form `os.path.realpath` resolves it
    to, which only the private-folder test reads, so a symlink into the
    private folder is still refused. A form inside the project is a path from
    its root; a web link's path is outside it."""
    real = os.path.realpath(project_root)
    roots = (real, os.path.abspath(project_root))
    trailing = "/" if piece.endswith("/") else ""
    written, resolved = [], []
    for spelling in dict.fromkeys((piece, _AUTHORITY.sub("", piece) or piece)):
        lexical = posixpath.normpath(os.path.join(real, spelling))
        inside = _from_root(lexical, roots)
        written.append(inside + trailing if inside is not None else _fold(spelling))
        full = os.path.realpath(os.path.join(real, spelling))
        inside = _from_root(full, (real,))
        resolved.append(inside + trailing if inside is not None
                        else _fold(full + trailing))
    written = tuple(dict.fromkeys(written))
    return tuple(dict.fromkeys(written + tuple(resolved))), written


def _scan(decoded, project_root):
    """`(path, index)` for each piece git must be asked about, and the index of
    the first file under `.compass/private/`, or None. Indexes are into the
    decoded text."""
    private = None
    if _PRIVATE_FILE.search(_fold_text(decoded)):
        # The fold drops characters, so the hit is placed at the first
        # `.compass` whose folded continuation names a private file. The
        # place is only a label: the post is refused either way.
        starts = [m.start() for m in re.finditer(r"\.compass", decoded)]
        private = next((i for i in starts
                        if _PRIVATE_FILE.match(_fold_text(decoded[i:i + 4096]))),
                       starts[0] if starts else 0)
    asked = []
    for match in _PIECE.finditer(decoded):
        piece = match.group(0).rstrip(".")
        if "/" not in piece:
            continue
        forms, written = _normalise(piece, project_root)
        # Before the folder test, so a trailing "/" or "/." after a private
        # file's name does not pass it as a folder.
        if any(_PRIVATE_FILE.search(form) for form in forms):
            private = match.start() if private is None else min(private, match.start())
            continue
        for path in written:
            if path.endswith("/"):
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
    decoded = [(name, variant) for name, text in items
               for variant in dict.fromkeys((_decode(text, False), _decode(text, True)))]
    found = [(name, text, _scan(text, project_root)) for name, text in decoded]
    for name, text, (_, private) in found:
        if private is not None:
            return _private_refusal(name, text, private)
    asked = sorted({path for _, _, (pairs, _) in found for path, _ in pairs})
    if not asked:
        return None
    ignored = _ignored(asked, project_root)
    if ignored is None:
        return Refusal("private-path", "cannot check ignored files: `git check-ignore` failed")
    for name, text, (pairs, _) in found:
        for path, index in pairs:
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
