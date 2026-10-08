#!/usr/bin/env python3
# =============================================================================
# compass - where an issue's documents live on disk
# =============================================================================
# One answer to "where does this issue's <document> go", used by every writer,
# by `compass issue migrate`, by the two hooks and by the repository-wide scans.
# Three copies of the same string join is how they stop agreeing.
#
# It sits apart from core.py because it is a naming rule, not a reader: nothing
# here opens a document or decides whether one is there. `docs_dir` needs the
# manifest for the created date and imports core inside the function, so the
# two modules do not depend on each other at import time.
#
# DEPENDENCY: os from the standard library, and core.py at call time.
# =============================================================================
"""Where an issue's documents live, and which paths belong to an issue."""
from __future__ import annotations

import os

#: Where human documents live, under the project root. Machine state - the
#: manifest, the evidence records, the TDD markers, the devlog - stays in
#: `.compass/work/<slug>/`, because that is what the CLI reads.
DOCS_ROOT = os.path.join("docs", "compass")


def is_issue_document(rel_path):
    """Is this path one of an issue's own documents?

    True for anything under a `docs/compass/<created>-<slug>/` directory, at
    any depth. False for a file sitting flat in `docs/compass/` - a
    cross-issue intake or a spike conclusion is not an issue's record.

    Repository-wide scans use this. An issue's documents state the vocabulary,
    the commands and the file layout in force WHEN THEY WERE WRITTEN, so a scan
    that enforces today's surface over them reports the account as a defect and
    pushes an author to rewrite history. Every such scan skipped
    `.compass/work/` for that reason; these are the same documents, in the
    place `compass issue migrate` moved them to.

    THE CALLER DECIDES THE SCOPE. This answers one question and does not anchor
    the path. A scan that treats the worked examples as shipped surface must
    apply it to the repository root only, because
    `examples/<x>/docs/compass/...` is read by an adopter learning the pipeline
    and a retired command name there teaches the wrong command.

    Takes a path relative to whatever root the caller scans, as a string or a
    PurePath.
    """
    parts = os.fspath(rel_path).replace("\\", "/").split("/")
    try:
        i = parts.index("docs")
    except ValueError:
        return False
    # Four segments at minimum - `docs/compass/<dir>/<file>` - so a flat file
    # directly under `docs/compass/` does not match.
    return len(parts) > i + 3 and parts[i + 1] == "compass"


def docs_dir_for(created, slug):
    """`docs/compass/<created>-<slug>/`, from the two facts that name it.

    Takes the values rather than the issue directory, so this module never
    reads a manifest and never imports the reader that would. `core.docs_dir`
    is the thin wrapper that looks both up.

    THE DATE IS THE MANIFEST'S `created:`, NOT TODAY. An issue that sits queued
    for a fortnight and is then worked on would otherwise put its first
    document in one directory and its second in another, and an issue whose
    documents are written either side of midnight would split in two.
    `created:` does not move when an issue is picked up and put down.

    An issue with no `created:` falls back to the slug alone rather than to
    today's date. A directory named for the day someone happened to run a
    command is worse than one with no date: it looks like a record of when the
    work happened, and is not.
    """
    created = str(created or "").strip()
    name = "%s-%s" % (created, slug) if created else slug
    return os.path.join(DOCS_ROOT, name)
