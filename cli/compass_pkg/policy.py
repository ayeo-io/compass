#!/usr/bin/env python3
# =============================================================================
# compass_pkg.policy - `compass issue lint`
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg import status_words
from compass_pkg.stable_ids import (
    APPROACH_DELIVERY, APPROACH_FULL, APPROACH_HOTFIX, APPROACH_QUICK_FIX, APPROACH_REGULAR,
    APPROACH_SPIKE)
from compass_pkg.core import (AUTONOMY_VALUES, LEGACY_ROUTE_NAMES, ROUTE_NAMES, assessment_key_errors, CompassError, canonical_shape, FRAMEWORK_ROOT,
                              load_manifest, load_yaml, normalize_spine,
                              resolve_issue_dir)
# The routing gives an issue assessed before 9.0.0 the legacy hand-off stages only,
# so its checkpoints stay as they were. A configuration's `autonomy_checkpoints`
# table may also name the path stages (ADR-092): `TABLE_CHECKPOINT_STAGES`.
from compass_pkg.path_readers import CHECKPOINT_STAGES as TABLE_CHECKPOINT_STAGES
from compass_pkg.path_readers import LEGACY_CHECKPOINT_STAGES as CHECKPOINT_STAGES
from compass_pkg.manifest_store import load_manifest_mapping



# --- commands: policy lint / issue lint --------------------------------------

# The built-in lint functions below are the no-dependency floor: they always
# run. `_jsonschema_errors` adds fuller structural validation against the JSON
# Schema files in schemas/, but only when the optional `jsonschema` library is
# installed. PyYAML stays the CLI's only *hard* dependency.

def _jsonschema_errors(instance, schema_name):
    """Check `instance` against schemas/<schema_name>. Returns a list of
    error strings, or None if `jsonschema` is not installed (caller falls back
    to the built-in structural lint, which always runs anyway)."""
    try:
        import jsonschema
    except ImportError:
        return None
    path = os.path.join(FRAMEWORK_ROOT, "schemas", schema_name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft7Validator(schema)
    errs = []
    for e in sorted(validator.iter_errors(instance),
                    key=lambda x: list(x.absolute_path)):
        loc = "/".join(str(p) for p in e.absolute_path) or "<root>"
        errs.append(f"{loc}: {e.message}")
    return errs


# Current route names. A retired name (`express`, `standard`, `expedition`,
# or `feature` and `initiative` before 5 October 2026) is read as its
# current one, so an older project policy keeps working.
# `delivery` is the shipped default's own (ADR-092); the other five are the 8.x
# approaches, which a stored generation still names.
CHECKPOINT_ROUTES = (APPROACH_QUICK_FIX, APPROACH_REGULAR, APPROACH_FULL, APPROACH_HOTFIX, APPROACH_SPIKE,
                     APPROACH_DELIVERY)


def checkpoint_table_errors(p):
    """Problems with the policy's `autonomy_checkpoints:` table. Checked by
    `compass policy lint` and by the evaluator, so a bad table is refused
    whether or not `jsonschema` is installed. Only a checkpoint stage, a path
    stage or a legacy one, can be named: an entry naming a gate or another
    stage would let the setting reach something it must never change."""
    table = p.get("autonomy_checkpoints")
    if table is None:
        return []
    if not isinstance(table, dict):
        return ["`autonomy_checkpoints:` must map each autonomy value to its approaches"]
    errs = []
    for value, routes in table.items():
        if value not in AUTONOMY_VALUES:
            errs.append(f"`autonomy_checkpoints:` names an unknown autonomy value "
                        f"'{value}'; the values are {', '.join(AUTONOMY_VALUES)}")
            continue
        if not isinstance(routes, dict):
            errs.append(f"`autonomy_checkpoints.{value}` must map each approach to a list")
            continue
        seen = {}
        for route in routes:
            name = canonical_shape(route)
            if name not in CHECKPOINT_ROUTES:
                errs.append(f"`autonomy_checkpoints.{value}` names an unknown approach "
                            f"'{route}'; the approaches are {', '.join(CHECKPOINT_ROUTES)}")
            elif name in seen:
                errs.append(f"`autonomy_checkpoints.{value}` names approach '{name}' "
                            f"twice, as '{seen[name]}' and '{route}'")
            else:
                seen[name] = route
        for route, stages in routes.items():
            if not isinstance(stages, list):
                errs.append(f"`autonomy_checkpoints.{value}.{route}` must be a list")
                continue
            for stage in stages:
                if stage not in TABLE_CHECKPOINT_STAGES:
                    errs.append(
                        f"`autonomy_checkpoints.{value}.{route}` names '{stage}', "
                        f"which is not a checkpoint; a checkpoint is one of "
                        f"{', '.join(TABLE_CHECKPOINT_STAGES)}")
    return errs


ARCHITECTURE_PILLARS = ("reliability", "security", "cost",
                        "operational excellence", "performance efficiency",
                        "sustainability")


def architecture_sources_lint_errors(gov):
    """Problems with governance/architecture-sources.yml, the register the
    well-architected alignment strategy (`S15`) reads. An absent register is not an error: a project may leave it out.
    Every entry needs a provider, a name, an https source, pillars in the
    neutral words, a digest and a review date, so a later review can see how
    old each entry is."""
    import datetime
    path = os.path.join(gov, "architecture-sources.yml")
    if not os.path.isfile(path):
        return []
    try:
        data = load_yaml(path) or {}
    except CompassError as exc:
        return [f"[architecture-sources.yml] does not parse: {exc}"]
    frameworks = data.get("frameworks") if isinstance(data, dict) else None
    if not isinstance(frameworks, list) or not frameworks:
        return ["[architecture-sources.yml] needs a non-empty `frameworks:` list"]
    errs = []
    for i, f in enumerate(frameworks):
        label = f"[architecture-sources.yml] entry {i + 1}"
        if not isinstance(f, dict):
            errs.append(f"{label} is not a mapping")
            continue
        label = f"{label} ({f.get('provider', '?')})"
        for key in ("provider", "name", "digest"):
            if not str(f.get(key) or "").strip():
                errs.append(f"{label} has no `{key}`")
        sources = f.get("sources")
        if not isinstance(sources, list) or not sources or not all(
                isinstance(u, str) and u.startswith("https://") for u in sources):
            errs.append(f"{label} needs `sources:` as a list of https URLs")
        pillars = f.get("pillars")
        if not isinstance(pillars, list) or not pillars:
            errs.append(f"{label} needs a `pillars:` list")
        else:
            unknown = [p for p in pillars if p not in ARCHITECTURE_PILLARS]
            if unknown:
                errs.append(f"{label} names pillars outside the neutral words "
                            f"({', '.join(ARCHITECTURE_PILLARS)}): {unknown}")
        reviewed = f.get("last_reviewed")
        try:
            datetime.date.fromisoformat(str(reviewed))
        except ValueError:
            errs.append(f"{label} needs `last_reviewed:` as a date (YYYY-MM-DD), "
                        f"so a review can see how old the entry is")
    return errs


def _schema_note(ran):
    return ("" if ran else
            "  (jsonschema not installed - built-in linter only; "
            "`pip install jsonschema` for full JSON Schema validation)")


def _lint_errors_quarantine(gov_dir):
    """Check governance/quarantine.yml if present.

    Returns a list of error strings. An absent quarantine.yml is not an error
    (zero-setup default, ADR-006). Required fields per entry: test,
    tracking_task, reason, added. An entry without tracking_task is malformed:
    a quarantined test with no tracking issue never gets fixed.
    """
    path = os.path.join(gov_dir, "quarantine.yml")
    if not os.path.isfile(path):
        return []
    try:
        data = load_yaml(path)
    except CompassError as exc:
        return [f"quarantine.yml: {exc}"]
    errs = []
    if not isinstance(data, dict):
        return ["quarantine.yml: top-level value is not a mapping"]
    if "version" not in data:
        errs.append("quarantine.yml: missing required key `version`")
    quarantined = data.get("quarantined")
    if quarantined is None:
        errs.append("quarantine.yml: missing required key `quarantined`")
        return errs
    if not isinstance(quarantined, list):
        errs.append("quarantine.yml: `quarantined` must be a list")
        return errs
    required_fields = ("test", "tracking_task", "reason", "added")
    for i, entry in enumerate(quarantined):
        if not isinstance(entry, dict):
            errs.append(f"quarantine.yml: entry #{i + 1} is not a mapping")
            continue
        for field in required_fields:
            if not entry.get(field):
                errs.append(
                    f"quarantine.yml: entry #{i + 1} (test={entry.get('test', '?')!r}) "
                    f"is malformed - missing or empty `{field}`. A quarantine entry "
                    f"without `tracking_task` is a graveyard, not a registry (TRC-A7)"
                )
    return errs


def delivery_approach_errors(task):
    """An unknown `delivery_approach`, reported by the built-in lint so the
    check does not depend on the optional `jsonschema` package. An old route
    name is accepted: it is read as its current one (ADR-006). A manifest on the
    four-stage path records `delivery` (ADR-092), which is no approach of the
    policy, so it is accepted there only."""
    from compass_pkg.core import SHAPE_VALUE_MAP
    from compass_pkg.path_stages import is_path_issue
    from compass_pkg.stable_ids import APPROACH_DELIVERY
    value = task.get("delivery_approach")
    if value is None or value in LEGACY_ROUTE_NAMES or value in SHAPE_VALUE_MAP:
        return []
    if value == APPROACH_DELIVERY and is_path_issue(task):
        return []
    return [f"`delivery_approach: {value}` is not a delivery approach; the "
            f"approaches are {', '.join(LEGACY_ROUTE_NAMES)}"]


def raised_by_errors(task):
    """A malformed `raised_by`, reported by the built-in lint for the same
    reason as `delivery_approach_errors`: jsonschema is optional."""
    from compass_pkg.lineage import FOUND_AT, places_text
    raised = task.get("raised_by")
    if raised is None:
        return []
    if not isinstance(raised, dict) or not isinstance(raised.get("issue"), str):
        return ["`raised_by` must name the parent issue: {issue: <slug>, found_at: <where>}"]
    if raised.get("found_at") not in FOUND_AT:
        return [f"`raised_by.found_at: {raised.get('found_at')}` is not a place an "
                f"issue is found; use one of {places_text()}"]
    return []


def _unmatched_document_notes(task_dir):
    """One line for each file in the issue's documents folder that is no kind's
    file and not on the not-an-artifact list. A report beside the result: it
    never changes the exit code, because a person can keep any note there."""
    from compass_pkg import artifact_kinds, effective

    try:
        view = effective.effective_for(task_dir)
        names = artifact_kinds.unmatched_documents(view, task_dir)
    except Exception:  # noqa: BLE001 - a report must not fail the lint
        return []
    return ["%s: a file in the documents folder whose name matches no kind. Rename it to "
            "a kind's filename, or leave it: nothing owes it." % name for name in names]


def _unread_config_notes(task, task_dir):
    """A warning for a `config:` that nothing reads. 9.0.0 has no issue layer
    (ADR-094): an 8.x issue keeps the `config:` its stored generation was
    committed with, and any other `config:` changes nothing. A warning, not an
    error: the key stays valid in the schema."""
    if task.get("config") is None:
        return []
    from compass_pkg import effective
    try:
        held = effective.generation_number(task)
        view = effective.effective_for(task_dir, task) if held else None
        unread = view is None or view.pending_config(task)
    except Exception:  # noqa: BLE001 - a report must not fail the lint
        unread = True
    if not unread:
        return []
    return ["warning: config: is not read. An issue has no config layer in 9.0.0 "
            "(ADR-094); delete the key, or record a waiver for one check with "
            "compass waiver add."]


def cmd_task_lint(args):
    from compass_pkg.terminal import relative_to_project
    if args.file:
        path = args.file
        task = normalize_spine(load_manifest_mapping(path))
    else:
        task_dir = resolve_issue_dir(args.task)
        task, path = load_manifest(task_dir)
    # built-in structural lint (always runs)
    errs = []
    # The manifest is normalised above, so this reads the current key.
    errs += delivery_approach_errors(task)
    errs += raised_by_errors(task)
    # The status keys. The loader maps an old status word, so the check for a
    # contradicting close reason reads the file as it is on disk.
    from compass_pkg import lifecycle
    errs += lifecycle.status_errors(task, load_yaml(path),
                                    os.path.dirname(os.path.abspath(path)))
    # The issues it waits for. A manifest linted by path has no checkout to
    # read them from, so only the shape of its entries is checked.
    from compass_pkg import issue_depends
    errs += issue_depends.lint_errors(task, None if args.file else task_dir)
    if "issue" not in task:
        errs.append("missing `issue:` (the issue slug)")
    # Each block below checks the shape before reading it. This command's whole
    # job is to report a malformed manifest.yml, so it must not crash on one -
    # a scenario written as a bare string must be reported, not raise
    # AttributeError.
    if "assessment" not in task:
        # An issue closed without being delivered that never had an assessment
        # was dropped before it entered the pipeline, which is the same case
        # as a queued one.
        if status_words.is_queued(task) or (status_words.close_reason(task)
                                            and not status_words.is_completed(task)):
            # A queued issue has not been assessed yet, so the lint does not
            # ask it for an assessment. Only that field is skipped: the rest
            # of the lint still runs, because a malformed manifest is
            # malformed whether or not work has started.
            pass
        elif task.get("landed_by"):
            # An issue delivered elsewhere never entered the pipeline, so it
            # has no assessment to record. Demanding one leaves inventing a
            # judgement nobody made as the only way to satisfy the lint - and
            # the assessment lives in whatever `landed_by` names, along with
            # the rest of the record.
            pass
        else:
            errs.append(
                "missing `assessment:` - the assess stage records the four "
                "dimensions")
    elif not isinstance(task["assessment"], dict):
        errs.append("`assessment:` must be a mapping of dimension -> value")
    else:
        for dim in ("risk", "familiarity", "size"):
            if dim not in task["assessment"]:
                errs.append(f"assessment is missing required dimension: {dim}")
    for i, s in enumerate(task.get("scenarios") or []):
        if not isinstance(s, dict):
            errs.append(f"scenario #{i + 1} must be a mapping with an `id:`, got: {s!r}")
        elif not s.get("id"):
            errs.append(f"scenario #{i + 1} has no id")
    for cf in task.get("changed_files") or []:
        if not isinstance(cf, dict):
            errs.append(f"a changed_files entry must be a mapping with a `path:`: {cf!r}")
        elif "path" not in cf:
            errs.append(f"a changed_files entry has no `path`: {cf}")
    # Check the `attempts` field on test-run evidence entries
    for ev in task.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "test-run" and "attempts" in ev:
            attempts = ev["attempts"]
            if not isinstance(attempts, int) or attempts < 1:
                errs.append(
                    f"evidence {ev.get('id', '?')}: attempts must be a positive "
                    f"integer (>= 1), got {attempts!r} - "
                    f"an attempt count of 0 or negative is out of domain (TRC-FM2)"
                )
    # JSON Schema validation (when `jsonschema` is installed)
    je = _jsonschema_errors(task, "manifest.schema.json")
    schema_ran = je is not None
    if not schema_ran:
        # jsonschema reports an unknown assessment key itself; without it,
        # the shared check does, so evaluate, check and lint agree (#399).
        errs += assessment_key_errors(task.get("assessment"))
    if je:
        errs += je
    # Notes beside the result. They never change the exit code.
    notes = _unread_config_notes(task, os.path.dirname(os.path.abspath(path)))
    if not args.file:
        task_dir = os.path.dirname(os.path.abspath(path))
        notes += _unmatched_document_notes(task_dir)
    if errs:
        print(f"compass issue lint: FAIL - {relative_to_project(path)}")
        for e in errs:
            print(f"  - {e}")
        for note in notes:
            print(f"  {note}")
        return 1
    print(f"compass issue lint: PASS - {relative_to_project(path)} is structurally valid."
          + ("\n" + _schema_note(schema_ran) if not schema_ran else ""))
    for note in notes:
        print(f"  {note}")
    return 0
