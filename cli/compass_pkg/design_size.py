# compass_pkg.design_size - the design's word count against its limit, and the lint notes
"""The check `design-within-word-ceiling` and the two `issue lint` notes that
read a document's size (ADR-067).

- The check refuses a technical design whose word count is over its limit
  times the check's `params.factor` (1.5 in the shipped default), once plan
  exit is due. Unit files never lift the refusal: the design's own count
  decides. It sits in no gate; `compass check` runs it through `outside_gate`.
- The word-limit note names a registered document over its limit.
- The missing-unit note names a work unit of a full issue's design that has
  no registered low-level design.

The notes never change the `issue lint` exit code. The check and the notes
decline, in this order, when:

1. the manifest has no `generation` key, so the issue predates the rules;
2. the issue is closed;
3. the document is not registered with a path;
4. the catalogue of the issue's generation has no `word_ceiling` for the kind
   at the depth the document is registered at.

The check also declines while plan exit is not yet due. Every count goes
through `word_ceiling.count_words`, so a note and a verdict agree.
"""
# DEPENDENCY: standard library (os); compass_pkg.check_results,
# compass_pkg.section_checks, compass_pkg.status_words, and, inside the
# functions, compass_pkg.effective, artifact_kinds, stage_lists, next_cmd and
# word_ceiling. `stage_lists` imports the check registry, which imports this
# module, and `next_cmd` is a command module, so both are imported inside the
# function that needs them. Nothing here imports a command module at load time.
from __future__ import annotations

import math
import os

from compass_pkg import section_checks, status_words
from compass_pkg.check_results import NOTHING_TO_CHECK

CHECK = "design-within-word-ceiling"
DESIGN_KIND = "technical-design"
LLD_KIND = "low-level-design"
UNITS_HEADING = "Work units"
PLAN_STAGE = "plan"
FULL = "full"
DEFAULT_FACTOR = 1.5


def _view(task_dir):
    from compass_pkg import effective

    return effective.view_or_legacy(task_dir)


def _registered(task, kind):
    """The registry entries of `kind` that hold a path, in order."""
    return [entry for entry in task.get("artifacts") or []
            if isinstance(entry, dict) and entry.get("kind") == kind and entry.get("path")]


def declines(task, task_dir, kind, entry=None):
    """The detail of the first of the four declining conditions that holds for
    `kind`, or None when its size can be judged. `entry` is the registry entry to
    read; by default the first one of `kind` with a path."""
    from compass_pkg import word_ceiling

    if task.get("generation") is None:
        return ("the issue predates the design-size check: its manifest names no stored "
                "configuration")
    if status_words.is_closed(task):
        return "the issue is closed"
    if entry is None:
        found = _registered(task, kind)
        entry = found[0] if found else None
    if entry is None:
        return "no %s is registered with a path" % kind
    depth = entry.get("depth")
    if word_ceiling.limit(_view(task_dir), kind, depth) is None:
        return ("the catalogue of generation %s has no word_ceiling for %s at %s"
                % (task.get("generation"), kind, "depth %s" % depth if depth else "no depth"))
    return None


def plan_exit_due(task, task_dir):
    """Whether the issue is past the plan stage, by the rule the stage lists use."""
    from compass_pkg import stage_lists

    view = _view(task_dir)
    if view is None:
        return False
    order, reached = stage_lists.positions(view, task, task_dir)
    return PLAN_STAGE in order and order.index(PLAN_STAGE) < reached


def _stage_name(task, task_dir):
    from compass_pkg.next_cmd import _current_phase_from_task

    return _current_phase_from_task(task, task_dir)


def work_units(text):
    """The units of a design: the first cell of each data row of the first table
    under `## Work units`, leaving out a cell that holds only a placeholder."""
    lines = section_checks.section_lines(text, UNITS_HEADING)
    if not lines:
        return []
    found = section_checks.tables(lines)
    if not found:
        return []
    units = []
    for row in found[0][1]:
        cell = section_checks.cell_value(row[0] if row else "")
        if cell and cell not in units:
            units.append(cell)
    return units


def units_without_design(task, text):
    """The units of the design `text` with no low-level design registered with a path."""
    held = {str(entry.get("unit")) for entry in _registered(task, LLD_KIND)}
    return [unit for unit in work_units(text) if unit not in held]


def _factor(task_dir):
    """`(factor, None)` from the check's `params.factor`, or `(None, detail)` when
    the value is not a number of at least 1."""
    view = _view(task_dir)
    checks = (view.config.get("checks") if view is not None else None) or {}
    entry = checks.get(CHECK)
    if not isinstance(entry, dict):
        entry = next((one for one in checks.values()
                      if isinstance(one, dict) and one.get("impl") == CHECK), {})
    params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
    value = params.get("factor", DEFAULT_FACTOR)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 1:
        return None, ("params.factor of %s must be a number of at least 1, found %r"
                      % (CHECK, value))
    return value, None


def _number(value):
    """A count with thousands separators, or a decimal as it is."""
    return "{:,}".format(int(value)) if float(value).is_integer() else "{:,}".format(value)


def _is_full(task, task_dir):
    """Whether the issue is on the full approach and its catalogue declares the
    low-level design, so a unit with no file is worth a note."""
    from compass_pkg import artifact_kinds

    return (task.get("delivery_approach") == FULL
            and artifact_kinds.entry(_view(task_dir), LLD_KIND) is not None)


def _check_design_within_word_ceiling(task, task_dir):
    """`(passed, detail)`: the design's word count is at or under its limit times
    the factor, once plan exit is due."""
    from compass_pkg import word_ceiling

    held = declines(task, task_dir, DESIGN_KIND)
    if held:
        return NOTHING_TO_CHECK, held
    if not plan_exit_due(task, task_dir):
        return NOTHING_TO_CHECK, "plan exit is not yet due: the issue is at %s" % (
            _stage_name(task, task_dir) or "no stage")
    factor, bad = _factor(task_dir)
    if bad:
        return False, bad
    entry = _registered(task, DESIGN_KIND)[0]
    depth = entry.get("depth")
    limit = word_ceiling.limit(_view(task_dir), DESIGN_KIND, depth)
    text, unreadable = section_checks.read_registered(task_dir, entry)
    if text is None:
        return False, unreadable
    count = word_ceiling.count_words(text)
    # A whole number of words: 800 times 1.15 is 919.9999999999999 in floating
    # point, and a 920-word design must pass. The small margin absorbs that error.
    threshold = math.floor(limit * factor + 1e-9)
    measure = "%s holds %s words, %s the threshold of %s (%s times the %s limit of %s)." % (
        os.path.basename(str(entry.get("path"))), _number(count),
        "over" if count > threshold else "at or under", _number(threshold), "%g" % factor,
        depth, _number(limit))
    if count <= threshold:
        return True, measure
    detail = [measure]
    if _is_full(task, task_dir):
        missing = units_without_design(task, text)
        detail.append("Units with no low-level design: %s." % (", ".join(missing) or "none"))
    detail.append("Move each unit's detail to low-level-design/<unit>.md until the design "
                  "is at or under %s words." % _number(threshold))
    return False, " ".join(detail)


def _word_limit_notes(task, task_dir):
    from compass_pkg import word_ceiling

    notes = []
    for entry in task.get("artifacts") or []:
        if not (isinstance(entry, dict) and entry.get("path") and entry.get("kind")):
            continue
        if declines(task, task_dir, entry["kind"], entry):
            continue
        depth = entry.get("depth")
        limit = word_ceiling.limit(_view(task_dir), entry["kind"], depth)
        text, _ = section_checks.read_registered(task_dir, entry)
        if text is None:
            continue
        count = word_ceiling.count_words(text)
        if count > limit:
            notes.append("%s: %s words, over the %s limit of %s. Shorten it or move detail "
                         "to a low-level design." % (os.path.basename(str(entry["path"])),
                                                     _number(count), depth, _number(limit)))
    return notes


def _missing_unit_notes(task, task_dir):
    from compass_pkg import artifact_kinds

    if declines(task, task_dir, DESIGN_KIND) or not _is_full(task, task_dir):
        return []
    text, _ = section_checks.read_registered(task_dir, _registered(task, DESIGN_KIND)[0])
    if text is None:
        return []
    kind = artifact_kinds.entry(_view(task_dir), LLD_KIND)
    notes = []
    for unit in units_without_design(task, text):
        if not artifact_kinds.UNIT_PATTERN.fullmatch(unit):
            continue
        notes.append("%s: a work unit with no low-level design. Write %s and register it "
                     "with `compass issue artifact set %s --unit %s --path %s`."
                     % (unit, artifact_kinds.filename(kind, unit=unit), LLD_KIND, unit,
                        artifact_kinds.home(task_dir, kind, unit=unit)))
    return notes


def lint_notes(task, task_dir):
    """The word-limit notes, then the missing-unit notes. A report beside the lint
    result: it never changes the exit code, and a configuration that cannot be
    read gives no note."""
    try:
        _view(task_dir)
    except Exception:                                   # noqa: BLE001 - a report must not fail the lint
        return []
    return _word_limit_notes(task, task_dir) + _missing_unit_notes(task, task_dir)
