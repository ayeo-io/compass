# compass_pkg.artifact_kinds - what the catalogue says about each kind of document
"""Read a document kind's catalogue entry, with the gaps of an old one filled.

The artifacts catalogue describes each kind of document: the stage that owns
it, the role that writes it, who reads it, the name the industry uses for it
and its headings per depth. Every reader that needs one of those facts asks
here, so a stored generation that predates a field is read the same way by
all of them.

A generation stores the configuration as it was resolved. One stored before
the descriptive fields existed holds entries with a `file` and sometimes a
`stage`, and nothing else. `entry` returns such an entry with each absent
descriptive field taken from the shipped default, for a kind the shipped
default declares. A project's own kind is returned as stored, because the
framework knows nothing about it. `required_when` and `every_approach` are
never filled: they decide what an issue owes, and a stored generation keeps
the obligations it was stored with.
"""
# DEPENDENCY: standard library; compass_pkg.core (FRAMEWORK_ROOT, load_yaml).
# It is a leaf: it imports no command module, so every reader can import it.
from __future__ import annotations

import copy
import fnmatch
import os
import re

from compass_pkg.core import FRAMEWORK_ROOT, CompassError, docs_dir, load_yaml
from compass_pkg.stable_ids import NOT_AN_ARTIFACT

#: The fields read from the shipped default when a stored entry lacks them.
FILLED_FIELDS = ("stage", "owner", "audience", "stands_for", "sections", "depends_on")

_SHIPPED = {}


def shipped():
    """The shipped default's artifacts catalogue, or {} when it cannot be read.
    Read once per process."""
    if "artifacts" not in _SHIPPED:
        path = os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default",
                            "artifacts.yml")
        try:
            body = (load_yaml(path) or {}).get("artifacts")
        except (CompassError, OSError):
            body = None
        _SHIPPED["artifacts"] = body if isinstance(body, dict) else {}
    return _SHIPPED["artifacts"]


def entry(view, kind):
    """The catalogue entry of `kind` in `view`'s configuration, or None when
    the catalogue does not declare it. A shipped kind's absent descriptive
    fields are filled from the shipped default. The result is a copy."""
    config = getattr(view, "config", None) if view is not None else None
    catalogue = config.get("artifacts") if isinstance(config, dict) else None
    stored = catalogue.get(kind) if isinstance(catalogue, dict) else None
    if not isinstance(stored, dict):
        return None
    found = copy.deepcopy(stored)
    default = shipped().get(kind)
    if isinstance(default, dict):
        for field in FILLED_FIELDS:
            if field not in found and field in default:
                found[field] = copy.deepcopy(default[field])
    return found


def catalogue(view):
    """Every kind `view`'s configuration declares, as `{kind: entry}` with each
    entry read by `entry`. With no configuration to read (a project on copied
    5.x governance, or no project), the shipped default's catalogue."""
    config = getattr(view, "config", None) if view is not None else None
    declared = config.get("artifacts") if isinstance(config, dict) else None
    if not isinstance(declared, dict):
        return copy.deepcopy(shipped())
    return {kind: entry(view, kind) for kind in declared
            if isinstance(declared[kind], dict)}


def _flat(text):
    return " ".join(str(text).split())


def rows(artifacts):
    """One row per kind of `artifacts`, in its order, for the documents that
    list the catalogue. `sections` is `{depth: [headings]}`; the other fields
    are the catalogue's own text, on one line."""
    found = []
    for kind, body in (artifacts or {}).items():
        if not isinstance(body, dict):
            continue
        found.append({
            "kind": kind, "file": _flat(body.get("file", "")),
            "stage": _flat(body.get("stage", "")), "owner": _flat(body.get("owner", "")),
            "stands_for": _flat(body.get("stands_for", "")),
            "audience": _flat(body.get("audience", "")),
            "sections": {depth: [str(h) for h in (listed or [])]
                         for depth, listed in (body.get("sections") or {}).items()}})
    return found


#: The rule effects that name a document kind in a rule's `then:`.
ARTIFACT_EFFECTS = ("add_artifact", "require_artifact", "suggest_artifact")

ROUND_MARK = "<n>"


def repeats(entry):
    """Whether a kind repeats: its `file` holds `<n>`, as `review-<n>.md` does."""
    return ROUND_MARK in str((entry or {}).get("file") or "")


def filename(entry, round=None):
    """The filename of a kind's document, or of one round of a repeating kind."""
    name = str((entry or {}).get("file") or "")
    return name.replace(ROUND_MARK, str(round)) if repeats(entry) and round is not None else name


def _pattern(entry):
    left, _, right = str(entry.get("file") or "").partition(ROUND_MARK)
    return re.compile(re.escape(left) + "([0-9]+)" + re.escape(right))


def round_of(entry, name):
    """The round a filename holds for a repeating kind, or None when `name` is
    not that kind's filename. Rounds count from 1 and carry no leading zero, so
    the filename of a round is the one name that gives that round."""
    if not repeats(entry):
        return None
    found = _pattern(entry).fullmatch(str(name))
    if not found or found.group(1) != str(int(found.group(1))) or int(found.group(1)) < 1:
        return None
    return int(found.group(1))


def home(task_dir, entry, round=None):
    """The project-relative path where an issue keeps a kind's document: its
    documents folder and the kind's filename."""
    return "%s/%s" % (docs_dir(task_dir), filename(entry, round))


def voluntary(view):
    """The kinds that no approach, no rule and no `every_approach` flag names.
    Nothing owes one, so a person registers it when it is written, and a
    reassessment never supersedes it. With no configuration to read, none."""
    config = getattr(view, "config", None) if view is not None else None
    if not isinstance(config, dict) or not isinstance(config.get("artifacts"), dict):
        return set()
    named = set()
    for body in (config.get("approaches") or {}).values():
        named |= set((body or {}).get("artifacts") or {})
    for rule_set in (config.get("rules") or {}).values():
        rules = rule_set.get("rules") if isinstance(rule_set, dict) else None
        for rule in (rules or {}).values():
            then = rule.get("then") if isinstance(rule, dict) else None
            for effect in ARTIFACT_EFFECTS:
                value = (then or {}).get(effect)
                named |= set(value if isinstance(value, list) else [value])
    named |= {kind for kind, body in config["artifacts"].items()
              if isinstance(body, dict) and body.get("every_approach")}
    return {kind for kind in config["artifacts"] if kind not in named}


def matches_kind(catalogue, name):
    """Whether a filename in the documents folder is the file of a kind, with
    `<n>` read as any whole number of a repeating kind."""
    for body in catalogue.values():
        if repeats(body):
            if _pattern(body).fullmatch(name):
                return True
        elif body.get("file") == name:
            return True
    return False


def unmatched_documents(view, task_dir):
    """The names in the issue's documents folder that are no kind's file and
    are not on the not-an-artifact list: top-level, non-hidden `.md` files,
    sorted. The list is framework-owned (`stable_ids.NOT_AN_ARTIFACT`), so the
    migrate and `compass issue lint` read the same names.

    A shipped kind's file is known as well as the configuration's. An issue
    stored on an earlier generation keeps that generation's catalogue, which
    may predate a kind the migrate names files for (`review-<n>.md`), and the
    migrate reads the shipped catalogue."""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))
    folder = os.path.join(root, docs_dir(task_dir))
    if not os.path.isdir(folder):
        return []
    known = dict(shipped(), **catalogue(view))
    found = []
    for name in sorted(os.listdir(folder)):
        if (name.startswith(".") or not name.endswith(".md")
                or not os.path.isfile(os.path.join(folder, name))):
            continue
        if matches_kind(known, name) or any(fnmatch.fnmatchcase(name, p) for p in NOT_AN_ARTIFACT):
            continue
        found.append(name)
    return found
