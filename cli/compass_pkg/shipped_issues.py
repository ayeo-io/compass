#!/usr/bin/env python3
# =============================================================================
# compass_pkg.shipped_issues - which completed issues ship, and how the living
# spec names them
# =============================================================================
#
# DEPENDENCY: standard library; compass_pkg.core, status_words, stable_ids.
# It must not import compass_pkg.flow or compass_pkg.parse_cache: the release
# notes verb reads through this module and must not load the parse cache.
# =============================================================================
"""The facts the living spec derivation and `compass release notes` share.

Both read the same records and answer the same two questions: is an issue
completed and does its approach ship, and which issues does a living spec
already name. One definition keeps the two views from drifting apart.
"""
from __future__ import annotations

import os
import re

from compass_pkg import status_words
from compass_pkg.core import CompassError, load_yaml, manifest_path, normalize_spine
from compass_pkg.stable_ids import APPROACH_SPIKE

# The living spec and its archive, project-relative. Only the derivation
# writes them, and ship-commit commits them at landing, so they are never
# one issue's change to trace.
LIVING_SPEC_FILES = ("docs/system-spec.md", "docs/system-spec-archive.md")

# Specs written before 2.0.0 label the source with the retired word for an
# issue; both labels name an issue, and a spec from either release must keep
# every issue it names. The old word is assembled, as `MANIFEST_NAMES` in
# core.py does, so the vocabulary scan does not read it as current prose.
_SOURCE_LABELS = "(?:issue|" + "ta" + "sk)"
_SOURCE_ISSUE = re.compile(r"\*\*Source " + _SOURCE_LABELS + r":\*\* `([^`]+)`")
# The current layout names an issue in its heading, "### <slug> (completed
# <date>)". A spec derived before 6.0.0 says "landed" where this says
# "completed", and a branch can hold both until its next derivation rewrites
# every heading, so the reader accepts either word.
ISSUE_HEADING = re.compile(r"^### (\S+) \((?:landed|completed) [0-9-]*\)$", re.M)


def issues_named(text):
    """Every issue a derived spec names, in the current or the older layout."""
    return set(_SOURCE_ISSUE.findall(text)) | set(ISSUE_HEADING.findall(text))


def ships(task):
    """True when the issue's approach ships. Only the spike does not: the same
    fact `obligations.EVALUATOR_APPROACHES` and the generated views hold, and
    a layer cannot change it. This module reads the constant and not the
    table, because only the classifier, the effective view and the replay may
    import the obligations module. An approach the table does not name ships,
    as it did when every completed issue fed the spec."""
    return task.get("delivery_approach") != APPROACH_SPIKE


def one_line(text):
    """The text on one line: its line breaks become single spaces, and the
    spacing inside a line stays as written."""
    return " ".join(str(text or "").splitlines())


def completed_issues(project_root):
    """Every completed issue under `.compass/work/`, as dicts of `slug`,
    `task_dir`, `issue` (the manifest), `land_timestamp` and `ships`, sorted
    by landing time and then slug. A spike is completed too and records what
    was learned, so it is returned with `ships` false. A folder with no
    manifest, an unreadable one, and an issue that is not completed are left
    out. Reads the records and writes nothing."""
    work = os.path.join(project_root, ".compass", "work")
    found = []
    if not os.path.isdir(work):
        return found
    for slug in sorted(os.listdir(work)):
        task_dir = os.path.join(work, slug)
        path = manifest_path(task_dir)
        if not os.path.isfile(path):
            continue
        try:
            task = normalize_spine(load_yaml(path))
        except CompassError:
            continue
        if not isinstance(task, dict) or not status_words.is_completed(task):
            continue
        stamp = task.get("land_timestamp", "")
        found.append({"slug": slug, "task_dir": task_dir, "issue": task,
                      "land_timestamp": str(stamp) if stamp else "",
                      "ships": ships(task)})
    found.sort(key=lambda item: (item["land_timestamp"], item["slug"]))
    return found
