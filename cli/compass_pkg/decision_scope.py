# compass_pkg.decision_scope - a project-scoped design decision needs a decision record
"""The landing refusal for a project-scoped design decision with no decision record.

A design decision (`DD-n`) in `technical-design.md` says `Scope: issue` or `Scope:
project`. A project-scoped decision settles a question for later issues too, so it must
be in `architecture/decisions/` before the issue lands (ADR-071). A record names the
decision when the decision's block cites an ADR id whose file is there, or when a file
there holds both the issue's slug and the decision id. Decision ids restart in every
issue, so the id alone is not enough.

A decision with no scope line is not judged: no design written before 7.0.0 has one.
"""
# DEPENDENCY: standard library (os, re); compass_pkg.core (resolve_artifact, FOUND),
# issue_page (design_decisions), project_scan (read_adrs, ADR_FOLDER), status_words and
# refusals. Imported by compass_pkg.manifest, whose landing refusals list holds
# `landing_refusal`.
from __future__ import annotations

import os
import re

PROJECT = "project"


def _project_root(task_dir):
    """The folder that holds `.compass/`."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(str(task_dir)))))


def _design_text(task_dir):
    """The registered technical design's text, or None when there is none to read."""
    from compass_pkg.core import FOUND, resolve_artifact
    try:
        state, path, _ = resolve_artifact(task_dir, "technical-design")
        if state != FOUND:
            return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def _records(root):
    """`({ADR id: file name}, [file text])` for the records in `architecture/decisions/`."""
    from compass_pkg.project_scan import ADR_FOLDER, read_adrs
    adrs = read_adrs(root)
    texts = []
    for name in adrs.values():
        try:
            with open(os.path.join(root, ADR_FOLDER, name), encoding="utf-8") as fh:
                texts.append(fh.read())
        except (OSError, UnicodeDecodeError):
            continue
    return adrs, texts


def _names(text, slug, dd_id):
    word = r"(?<![\w-]){}(?![\w-])"
    return bool(re.search(word.format(re.escape(slug)), text)
                and re.search(word.format(re.escape(dd_id)), text))


def unrecorded(task_dir, slug, text):
    """`[(DD id, title)]`: the project-scoped decisions of the design `text` that no
    record in the project's `architecture/decisions/` names, in the design's order."""
    from compass_pkg.issue_page import design_decisions
    scoped = [d for d in design_decisions(text) if d[2] == PROJECT]
    if not scoped:
        return []
    adrs, texts = _records(_project_root(task_dir))
    return [(dd_id, title) for dd_id, title, _, cited in scoped
            if not any(ref in adrs for ref in cited)
            and not any(_names(body, slug, dd_id) for body in texts)]


def next_record(task_dir, title):
    """The path `compass adr new` would write for a record of `title`: the next number
    after the count of records, then the title as a slug."""
    from compass_pkg.project_scan import ADR_FOLDER
    folder = os.path.join(_project_root(task_dir), ADR_FOLDER)
    try:
        count = sum(1 for n in os.listdir(folder) if n.startswith("ADR-") and n.endswith(".md")
                    and n != "ADR-template.md")
    except OSError:
        count = 0
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "decision"
    return "architecture/decisions/ADR-%03d-%s.md" % (count + 1, words)


def landing_refusal(task, task_dir):
    """The refusal text for an open issue whose registered design holds a project-scoped
    decision with no record, or None. An entry of `manifest.LANDING_REFUSALS`."""
    from compass_pkg import refusals, status_words
    if not isinstance(task, dict) or status_words.is_closed(task):
        return None
    text = _design_text(task_dir)
    if not text:
        return None
    slug = os.path.basename(os.path.normpath(str(task_dir)))
    missing = unrecorded(task_dir, slug, text)
    if not missing:
        return None
    return refusals.render("project-decision-unrecorded", slug=slug,
                           decisions=", ".join(dd_id for dd_id, _ in missing),
                           it="it" if len(missing) == 1 else "them",
                           path=next_record(task_dir, missing[0][1]))
