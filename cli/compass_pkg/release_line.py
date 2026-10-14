# compass_pkg.release_line - the one owner of an issue's `release_note`
"""The release line: one text written for users, kept in the manifest's
`release_note:`, that the release notes list (ADR-065).

This module holds every rule about it, so the three verbs that write it
(`compass acceptance record`, `compass ship-commit`, `compass quick-fix finish`)
and the landing refusal agree:

- `owes` decides whether an issue owes a line. It owes one only when all four
  hold: a landing names it, it is neither completed nor closed, its manifest has
  a `generation` key, and its stored configuration sets `release_line: true` on
  its approach. An issue that predates the field, or the archive, never owes one.
- `landing_refusal` is the entry of `manifest.LANDING_REFUSALS`.

The owning doc is `docs/release-line.md`.
"""
# DEPENDENCY: standard library (os); compass_pkg.effective, generation, refusals,
# status_words.
from __future__ import annotations

import os

from compass_pkg import status_words

#: The manifest key the line is kept under.
KEY = "release_note"


def _slug(task_dir):
    return os.path.basename(os.path.normpath(str(task_dir)))


def held(task):
    """The stored line when it holds text, else None. A blank or non-string value is no
    line."""
    value = task.get(KEY) if isinstance(task, dict) else None
    return value if isinstance(value, str) and value.strip() else None


def owes(task, task_dir):
    """True when the issue owes a release line: it is open, it has a stored generation,
    and that generation sets `release_line: true` on its approach. Only the literal
    `true` counts, and a configuration that cannot be read owes nothing."""
    from compass_pkg import effective, generation
    if not isinstance(task, dict) or status_words.is_closed(task):
        return False
    try:
        if generation.number(task) is None:
            return False
        view = effective.view_or_legacy(task_dir, manifest=task)
    except Exception:                                   # noqa: BLE001 - nothing to read, nothing owed
        return False
    if view is None:
        return False
    approaches = view.config.get("approaches")
    body = approaches.get(task.get("delivery_approach")) if isinstance(approaches, dict) else None
    return isinstance(body, dict) and body.get("release_line") is True


def missing_text(slug):
    from compass_pkg import refusals
    return refusals.render("release-line-missing", slug=slug)


def landing_refusal(task, task_dir):
    """The refusal text for an issue that owes a release line and holds none, or None.
    An entry of `manifest.LANDING_REFUSALS`, so it judges the manifest it is given:
    `ship-commit` passes a projection with `--release-note` applied."""
    if held(task) is not None or not owes(task, task_dir):
        return None
    return missing_text(_slug(task_dir))
