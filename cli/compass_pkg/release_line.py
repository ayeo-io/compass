# compass_pkg.release_line - the one owner of an issue's `release_note`
"""The release line: one text written for users, kept in the manifest's
`release_note:`, that the release notes list (ADR-065).

This module holds every rule about it, so the three verbs that write it
(`compass acceptance record`, `compass ship-commit`, `compass quick-fix finish`)
and the landing refusal agree:

- `owes` decides whether an issue owes a line: it is neither completed nor
  closed, its manifest has a `generation` key, and its stored configuration sets
  `release_line: true` on its approach. An issue that predates the field, or the
  archive, never owes one.
- `landing_refusal` is the entry of `manifest.LANDING_REFUSALS`, so it judges only
  the issue a landing names.
- `clean` and `text_problem` judge a given line before anything is written.
- `write` is the only writer of `release_note`: a locked re-read and write of
  the one key, so a change another command made to the manifest is kept.
- `add_argument` gives the three verbs one `--release-note` flag.

The owning doc is `docs/release-line.md`.
"""
# DEPENDENCY: standard library (copy, os); the bundled PyYAML; compass_pkg.atomic_io,
# core, effective, manifest (title_problem), refusals, status_words.
from __future__ import annotations

import copy
import os

import yaml

from compass_pkg import atomic_io, status_words
from compass_pkg.core import (MANIFEST_LOCK, CompassError, load_manifest, load_yaml,
                              prepare_manifest_write)

#: The manifest key the line is kept under.
KEY = "release_note"

#: A test sets this to a function of the issue folder, to change the manifest on disk
#: after the writer's first read and before its locked write. None in use.
AFTER_FIRST_READ = None

HELP = "the release line, written for a user; stored as release_note"


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
    from compass_pkg import effective
    if not isinstance(task, dict) or status_words.is_closed(task) or "generation" not in task:
        return False
    try:
        # A generation that is not a whole number, or not whole on disk, raises here.
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


# --- a given line ---------------------------------------------------------------------

def clean(text):
    """The given line with leading and trailing space removed, or None when no flag was
    given. Line breaks inside it are kept; a reader prints it on one line."""
    return None if text is None else str(text).strip()


def _project_root(task_dir):
    """The folder that holds `.compass/`, as `compass scenario add` finds it."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(str(task_dir)))))


def text_problem(task_dir, text, verb):
    """Why a cleaned line is refused, or None. Blank is no line at all. A line that
    starts with `#` would read as a heading of the living spec, whose issue headings
    are `### <slug> (completed <date>)`. A line the living spec's checks would refuse
    as a scenario title is refused with the reason `compass scenario add` gives,
    because the living spec prints the line."""
    if not text:
        return missing_text(_slug(task_dir))
    if text.startswith("#"):
        from compass_pkg import refusals
        return refusals.render("release-line-heading", slug=_slug(task_dir))
    from compass_pkg.manifest import title_problem
    problem = title_problem(_project_root(task_dir), text)
    if problem:
        return f"{verb}: release line refused: {problem}"
    return None


def project(task, text):
    """A copy of the manifest with the given line applied, for the refusals to judge
    before anything is written. With no line given it is the manifest as it is."""
    if text is None:
        return task
    out = copy.deepcopy(task)
    out[KEY] = text
    return out


def refuse_landed(task, task_dir, verb):
    """Refuse to write a line on a completed or closed issue: its record is not
    rewritten."""
    if not status_words.is_closed(task):
        return
    word = "completed" if status_words.is_completed(task) else "closed"
    raise CompassError(
        f"{verb}: issue '{_slug(task_dir)}' is {word}, so its record is not rewritten and "
        f"--release-note was not stored. Nothing was written.")


# --- the write --------------------------------------------------------------------------

def write(task_dir, text, verb):
    """Store `text` as the issue's release line and return the value it replaced.

    It reads the manifest once to refuse a landed issue, then takes `.manifest.lock`,
    reads the manifest again and changes only `release_note`, so a change another
    command made since the first read is kept. It writes the file whole with
    `atomic_write_text`; it does not call `save_manifest` inside the lock, which takes
    the same lock on a second descriptor and would wait for itself."""
    task_dir = os.fspath(task_dir)
    task, path = load_manifest(task_dir)
    refuse_landed(task, task_dir, verb)
    if AFTER_FIRST_READ is not None:
        AFTER_FIRST_READ(task_dir)
    with atomic_io.locked(os.path.join(os.path.dirname(os.path.abspath(path)), MANIFEST_LOCK)):
        current = load_yaml(path)
        old = current.get(KEY)
        current[KEY] = text
        prepared = prepare_manifest_write(current, path)
        atomic_io.atomic_write_text(path, yaml.safe_dump(prepared, sort_keys=False,
                                                         default_flow_style=False))
    return old


def replaced_line(old, text):
    """The one line that says a different stored line was replaced, or None."""
    if isinstance(old, str) and old.strip() and old != text:
        return "release line replaced (was: %s)" % " ".join(old.split())
    return None


def store(task_dir, text, verb, held_task=None):
    """Write a given line, print the replaced line, and set the key on a manifest the
    caller holds in memory, so its later whole-manifest save keeps the line. Nothing
    happens with no line given."""
    if text is None:
        return
    line = replaced_line(write(task_dir, text, verb), text)
    if line:
        print(f"{verb}: {line}")
    if held_task is not None:
        held_task[KEY] = text


# --- the flag ------------------------------------------------------------------------------

def add_argument(parser):
    parser.add_argument("--release-note", dest="release_note", metavar="TEXT", help=HELP)


def given(args, task_dir, verb, task=None):
    """The cleaned `--release-note`, judged before anything is written: refused when the
    text is refused or the issue is completed or closed. None when no flag was given."""
    text = clean(getattr(args, "release_note", None))
    if text is None:
        return None
    problem = text_problem(task_dir, text, verb)
    if problem:
        raise CompassError(problem)
    refuse_landed(task if task is not None else load_manifest(task_dir)[0], task_dir, verb)
    return text


def landing_text(args, landing, verb):
    """`given` for a landing, which is also refused when no issue is named."""
    if clean(getattr(args, "release_note", None)) is not None and landing is None:
        raise CompassError(
            f"{verb}: --release-note needs the issue it belongs to, and no issue is named. "
            f"Name it with --issue <slug>. Nothing was staged or written.")
    return given(args, landing[1], verb, landing[0]) if landing is not None else None


def judge_landing(args, landing, verb, run_refusals):
    """`landing_text`, then the landing refusals on the manifest with the given line
    applied, before anything is staged or written. Returns the line, or None."""
    text = landing_text(args, landing, verb)
    if landing is not None:
        run_refusals(project(landing[0], text), landing[1])
    return text
