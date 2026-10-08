# compass_pkg.parent_states - the four states of a git parent
"""A git parent is in one of four states, read from the pin, the cache and `seen.yml`:

- `up to date`: the cache holds the pin, and no other commit is known for the ref;
- `stale`: `seen.yml` holds another commit for the ref, so a newer one is known;
- `locally modified`: the cached `compass.yml` no longer matches the digest recorded
  when it was fetched;
- `both`.

"Known" means this machine fetched it. The state is read from files only: it never
fetches, so `compass check` and `compass approach summary` can report it offline.
A cached parent that `seen.yml` holds no digest for cannot be shown to match a fetch,
so it counts as modified.
"""
# DEPENDENCY: standard library (os, textwrap); compass_pkg.parents, compass_pkg.atomic_io.
from __future__ import annotations

import os
import textwrap
from collections import namedtuple

from compass_pkg import parents
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict

UP_TO_DATE, STALE, MODIFIED, BOTH = "up to date", "stale", "locally modified", "both"

# The lint finding code and level of each state. Only a state that puts an edited
# file into the chain fails the lint; a newer commit is news, not a fault.
FINDINGS = {UP_TO_DATE: ("S-PARENT-UP-TO-DATE", "info"),
            STALE: ("S-PARENT-STALE", "warning"),
            MODIFIED: ("S-PARENT-MODIFIED", "error"),
            BOTH: ("S-PARENT-BOTH", "error")}

# `ref` and `sha` name the parent. `newer` is the other known commit, or "".
# `why` is the cause of an edited cache, and `message` the sentence a person reads.
State = namedtuple("State", "ref sha state newer why message")


def locate(root, sha):
    """The path of the cached `compass.yml` of one commit. The cache layout is
    read here and in `seen_path` only."""
    return os.path.join(parents.cache_dir(root), sha, parents.PARENT_FILE)


def seen_path(root):
    return os.path.join(parents.cache_dir(root), parents.SEEN)


def _entry(root, ref):
    """The `seen.yml` record of a ref, or an empty one when there is none or the
    file cannot be read."""
    try:
        doc = load_yaml_strict(seen_path(root))
    except (StrictYamlError, OSError):
        return {}
    held = (doc.get("refs") if isinstance(doc, dict) else None) or {}
    entry = held.get(ref) if isinstance(held, dict) else None
    return entry if isinstance(entry, dict) else {}


def _recorded_digest(entry, sha):
    """The digest recorded when `sha` was fetched. `digests` keeps one per commit;
    `content_digest` is the digest of the commit fetched last."""
    digests = entry.get("digests")
    if isinstance(digests, dict) and isinstance(digests.get(sha), str):
        return digests[sha]
    if entry.get("sha") == sha and isinstance(entry.get("content_digest"), str):
        return entry["content_digest"]
    return None


def _why_modified(root, entry, sha):
    """`""` when the cached file matches its recorded digest, else the cause."""
    recorded = _recorded_digest(entry, sha)
    if recorded is None:
        return "seen.yml holds no digest for it, so it cannot be shown to match a fetch"
    try:
        with open(locate(root, sha), "rb") as fh:
            actual = parents.file_digest(fh.read())
    except OSError:
        return "the cached file cannot be read"
    return "" if actual == recorded else "it no longer matches the digest recorded at fetch"


def read(root, found):
    """The `State` of a resolved `parents.Parent`."""
    entry = _entry(root, found.ref)
    known = entry.get("sha")
    newer = known if isinstance(known, str) and known != found.sha else ""
    why = _why_modified(root, entry, found.sha)
    state = BOTH if newer and why else STALE if newer else MODIFIED if why else UP_TO_DATE
    short = found.sha[:7]
    parts = []
    if why:
        parts.append(f"the cached compass.yml of {short} is not the file that was fetched: "
                     f"{why}; delete the cached copy of {short} under "
                     f".compass/cache/parents/ and run compass policy lint to fetch it again")
    if newer:
        parts.append(f"a newer commit, {newer[:7]}, was fetched on this machine; the pin "
                     f"stays at {short} until it is moved")
    message = "; ".join(parts) or f"the cache holds {short}, the pin, and no other commit is known"
    return State(found.ref, found.sha, state, newer, why, message)


def project_states(root, fetch=False):
    """`([State], [text])` for the git parent in the project's `compass.yml`:
    the states, and one sentence for a parent that could not be read. Nothing
    raises, so a command that prints the result cannot fail because of it."""
    from compass_pkg import layers
    path = os.path.join(os.fspath(root), layers.PROJECT_FILE)
    try:
        doc = load_yaml_strict(path) if os.path.isfile(path) else None
        extends = doc.get("extends") if isinstance(doc, dict) else None
        spec = parents.spec_of(extends)
        if spec is None:
            return [], []
        found = parents.resolve(root, extends, fetch=fetch)
    except parents.ParentError as exc:
        return [], [f"{exc.code}: {exc.detail}"]
    except (StrictYamlError, OSError):
        return [], []
    return [read(root, found)], []


def summary_lines(root):
    """The lines `compass approach summary` prints for the project's git parent:
    one line, or none for a project with no git parent."""
    states, problems = project_states(root)
    lines = [f"Parent: {s.ref} at {s.sha[:7]} - {s.state}" for s in states]
    for text in problems:
        lines += textwrap.wrap(f"Parent: not read - {text}", width=100, subsequent_indent="  ",
                               break_long_words=False, break_on_hyphens=False)
    return lines
