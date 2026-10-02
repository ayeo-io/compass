#!/usr/bin/env python3
# =============================================================================
# compass_pkg.flow - `compass flow` and the living system spec derivation
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
import glob
from compass_pkg.core import (CompassError, find_compass_dir, find_governance, load_yaml,
                              manifest_path, normalize_spine)
from compass_pkg.rework import cmd_rework_scan



# --- command: flow ----------------------------------------------------------
# Cross-issue flow view. Reads broadly; writes only when --digest is given.
# Never changes any manifest (`Inv-4`: Flow advises, never gates).

# A queued issue older than this many days is flagged when it carries a
# written recommendation or a label a routing rule names: the two signals that
# made a month-long wait on a written-up fix expensive (queue-ageing-signal).
QUEUE_AGE_DAYS = 14
_RECOMMENDATION = re.compile(
    r"^#+\s.*\b(recommend\w*|proposed|proposal|suggested fix|decision)\b", re.I | re.M)


def _routing_labels():
    """Every label a routing-policy rule names in `labels_any`."""
    try:
        policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
    except CompassError:
        return set()
    found, stack = set(), [policy]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "labels_any" and isinstance(v, list):
                    found |= {str(x) for x in v}
                else:
                    stack.append(v)
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _has_recommendation(project_root, slug, created):
    """True when one of the issue's documents has a heading that names a
    recommendation, a proposal or a decision. A heading match, not a reading."""
    dirs = [os.path.join(project_root, "docs", "compass", f"{created}-{slug}"),
            os.path.join(project_root, ".compass", "work", slug)]
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.md"))):
            try:
                with open(path, encoding="utf-8") as fh:
                    if _RECOMMENDATION.search(fh.read()):
                        return True
            except OSError:
                continue
    return False


def queue_ageing(work_root, today=None):
    """(top line, table) for the digest: queued issues by age, and the old
    ones that carry a recommendation or a guarded label."""
    today = today or datetime.date.today()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(work_root)))
    guarded = _routing_labels()
    rows = []
    for slug in sorted(os.listdir(work_root)) if os.path.isdir(work_root) else []:
        tp = manifest_path(os.path.join(work_root, slug))
        if not os.path.isfile(tp):
            continue
        try:
            m = load_yaml(tp)
        except CompassError:
            continue
        if not isinstance(m, dict) or m.get("status") != "queued":
            continue
        created = str(m.get("created") or "")
        try:
            age = (today - datetime.date.fromisoformat(created)).days
        except ValueError:
            continue
        signals = []
        if _has_recommendation(project_root, slug, created):
            signals.append("recommendation")
        labels = [l for l in ((m.get("assessment") or {}).get("labels") or [])
                  if str(l) in guarded]
        if labels:
            signals.append("label " + ", ".join(str(l) for l in labels))
        rows.append((age, slug, signals))
    rows.sort(key=lambda r: (-r[0], r[1]))
    if not rows:
        return "**Queue ageing:** No queued issues.", "## Queue age\n\nNo queued issues.\n"
    flagged = [f"{slug} ({age} days, {'; '.join(sig)})"
               for age, slug, sig in rows if age > QUEUE_AGE_DAYS and sig]
    if flagged:
        top = (f"**Queue ageing:** {len(flagged)} queued issue(s) older than "
               f"{QUEUE_AGE_DAYS} days carry a recommendation or a guarded label: "
               + ", ".join(flagged) + ".")
    else:
        top = (f"**Queue ageing:** no queued issue older than {QUEUE_AGE_DAYS} days "
               f"carries a recommendation or a guarded label.")
    table = ["## Queue age", "", "| Issue | Age (days) | Signal |", "|---|---|---|"]
    table += [f"| {slug} | {age} | {'; '.join(sig) or '-'} |" for age, slug, sig in rows]
    return top, "\n".join(table) + "\n"


def cmd_flow(args):
    """Produce the flow board; with --digest also output a dated digest section
    to stdout. The digest includes the rework-scan section and a retro
    summary. Exit code is always 0 - this is advisory.
    """
    work_root = getattr(args, "work_root", None)
    do_digest = getattr(args, "digest", False)

    # Resolve the work root
    if work_root is None:
        try:
            compass_dir = find_compass_dir()
            work_root = os.path.join(compass_dir, "work")
        except CompassError:
            work_root = ".compass/work"

    if not do_digest:
        # Live board mode: minimal - list issues and their delivery approaches
        if not os.path.isdir(work_root):
            print("compass flow: no issues found - work root does not exist.")
            return 0
        slugs = [d for d in sorted(os.listdir(work_root))
                 if os.path.isdir(os.path.join(work_root, d))]
        if not slugs:
            print("compass flow: no issues under work root.")
            return 0
        # Group by lifecycle state. A flat list counts parked work as active,
        # and parked issues accumulate, so the active count gets more wrong
        # over time.
        groups = {"active": [], "queued": [], "parked": [], "landed": [],
                  "abandoned": [], "unreadable": []}
        for slug in slugs:
            task_yml = manifest_path(os.path.join(work_root, slug))
            if not os.path.isfile(task_yml):
                groups["unreadable"].append((slug, "?", "no manifest.yml"))
                continue
            try:
                t = normalize_spine(load_yaml(task_yml))
                # The live manifest key, `delivery_approach`.
                route = t.get("delivery_approach", "?")
                # Absent means active: every manifest.yml written before the status
                # field existed omits it (ADR-006).
                status = t.get("status") or "active"
                note = t.get("parked_reason", "") if status == "parked" else ""
                groups.setdefault(status, []).append((slug, route, note))
            except Exception:                                   # noqa: BLE001
                groups["unreadable"].append((slug, "?", "unreadable manifest.yml"))

        # The board is a REPORT: every issue is listed, because a board that
        # omits part of the work looks complete when it is not. What it owes a
        # reader is a summary they can stop at - the counts - before 150 rows
        # of detail.
        from compass_pkg.terminal import Report

        headings = [
            ("active", "IN PROGRESS"),
            ("queued", "NEXT UP"),
            ("parked", "PARKED - stopped, can resume"),
            ("landed", "DONE"),
            ("abandoned", "ABANDONED - will not resume"),
        ]
        named = {k for k, _ in headings} | {"unreadable"}
        counts = {k: len(v) for k, v in groups.items() if v}
        rep = Report(args, title="compass flow - cross-issue board (advisory)")
        rep.summary(
            "compass flow - %d issue(s) across %d state(s). Advisory: this "
            "changes no issue state." % (len(slugs), len(counts)),
            ", ".join("%s %d" % (k, n) for k, n in sorted(counts.items()))
            or "nothing to report")

        def _row(r):
            slug, route, note = r
            return "%-40s approach=%s%s" % (slug, route,
                                            "  - %s" % note if note else "")

        for key, heading in headings:
            rep.section(heading, groups.get(key) or [], _row)
        for key in sorted(set(groups) - named):
            rep.section(key.upper(), groups[key], _row)
        rep.section("UNPLACEABLE - no readable manifest.yml, so no state to report",
                    groups["unreadable"], _row)
        rep.data(counts=counts)
        return rep.emit()

    # --digest mode: produce a digest including rework-scan
    import io as _io
    import contextlib as _cl

    today = datetime.date.today().isoformat()
    print(f"# Flow digest - {today}\n")
    print("> Advisory only. This digest does not modify any issue state (Inv-4).\n")
    top, table = queue_ageing(work_root)
    print(top + "\n")
    print(table)

    # --- Rework scan section (TRC-D5) ---
    # Capture rework-scan output by invoking the scan logic directly
    import types as _types
    scan_args = _types.SimpleNamespace(
        root=work_root,
        window_days=None,
        format="markdown",
    )

    buf = _io.StringIO()
    with _cl.redirect_stdout(buf):
        cmd_rework_scan(scan_args)
    rework_section = buf.getvalue()

    print(rework_section)

    # --- Calibration summary ---
    print("## Calibration signal\n")
    # Enumerate issues for the retro summary
    tasks = []
    if os.path.isdir(work_root):
        for d in sorted(os.listdir(work_root)):
            tp = manifest_path(os.path.join(work_root, d))
            if os.path.isfile(tp):
                try:
                    data = load_yaml(tp)
                    tasks.append((d, data))
                except CompassError:
                    pass
    total_reframes = sum(len(t.get("reassessments") or []) for _, t in tasks)
    if total_reframes == 0:
        print(f"No re-assessments recorded across {len(tasks)} issue(s). "
              f"Either the sizing is well-calibrated, or there is not enough history yet.\n")
    else:
        print(f"{total_reframes} re-assessment(s) recorded across {len(tasks)} issue(s). "
              f"Run `compass retro` for the full breakdown.\n")

    return 0


# --- living system spec derivation (ADR-008) ---------------------------------
#
# derive_system_spec(project_root) is the internal helper that produces
# docs/system-spec.md by walking every .compass/work/*/manifest.yml whose
# status == 'landed'.
#
# Design constraints honoured here:
#   `Inv-5`  - annotation over per-issue specs, never a parallel spec; the
#            derived file carries the DERIVED FILE header.
#   `Inv-6`  - all derivation inputs live on disk; no in-memory accumulation
#            beyond the walk (reconstructibility).
#   `Inv-8`  - backward compat: manifest.yml files with no `status` field
#            (schema 1.0) are treated as active (not landed), so they are
#            excluded from the derivation.
#   ADR-008 §3 - idempotent; deterministic order (land_timestamp, then
#             issue slug as tiebreaker); supersession (same intent id →
#             latest-landed wins for current section, earlier → archive).
#   ADR-008 §4 - never source-of-truth; DERIVED FILE header on line 1;
#             silent overwrite on next ship.
#   brand-new project with no landed issues produces a stub file.

# The living spec and its archive, project-relative. Only the derivation
# writes them, and ship-commit commits them at landing, so they are never
# one issue's change to trace.
LIVING_SPEC_FILES = ("docs/system-spec.md", "docs/system-spec-archive.md")

_DERIVED_HEADER = (
    "<!-- DERIVED FILE - do not hand-edit; `compass _derive-system-spec` "
    "rebuilds it from the scenarios in each landed issue's manifest.yml - "
    "edit the scenario there and in the issue's acceptance-criteria.md -->"
)


def derive_system_spec(project_root: str) -> None:
    """Derive docs/system-spec.md from all landed manifest.yml files.

    This is the sole implementation of the living-system-spec derivation
    (ADR-008).  It is invoked by ``compass _derive-system-spec --internal``
    from ``scripts/integrate.sh`` after combined regression passes.

    It is idempotent: running it twice on unchanged inputs produces a
    byte-identical ``docs/system-spec.md``.

    Args:
        project_root: absolute path to the project root (the directory that
            contains ``.compass/``).
    """
    project_root = os.path.abspath(project_root)
    compass_work = os.path.join(project_root, ".compass", "work")

    # ---- 1. Collect landed issues -------------------------------------------
    # Walk .compass/work/*/manifest.yml; keep only status == 'landed'.
    # Issues without a `status` field (schema 1.0) are treated as active.
    # Process order: land_timestamp ascending, then issue slug ascending.
    landed = []  # list of dicts: {slug, task_dir, issue, land_timestamp}
    if os.path.isdir(compass_work):
        for slug in sorted(os.listdir(compass_work)):
            task_dir = os.path.join(compass_work, slug)
            yml_path = manifest_path(task_dir)
            if not os.path.isfile(yml_path):
                continue
            try:
                with open(yml_path, encoding="utf-8") as fh:
                    task = normalize_spine(yaml.safe_load(fh) or {})
            except yaml.YAMLError:
                continue
            if not isinstance(task, dict):
                continue
            status = task.get("status")
            if status != "landed":
                continue
            land_ts = task.get("land_timestamp", "")
            landed.append({
                "slug": slug,
                "task_dir": task_dir,
                "issue": task,
                "land_timestamp": str(land_ts) if land_ts else "",
            })

    # Sort: land_timestamp ascending, issue slug as tiebreaker
    landed.sort(key=lambda x: (x["land_timestamp"], x["slug"]))

    # ---- 2. Build the current-behaviour and archived-behaviour tables ------
    # Key: intent id → winner entry  (dict with slug, scn_id, scn_title, ts, date)
    current: dict = {}    # intent_id -> entry
    archived: list = []   # list of archived entries

    for item in landed:
        slug = item["slug"]
        task = item["issue"]
        task_dir = item["task_dir"]
        land_ts = item["land_timestamp"]
        # Parse a date string from land_timestamp for display
        land_date = land_ts[:10] if len(land_ts) >= 10 else land_ts

        # Read the scenarios block from manifest.yml
        scenarios = task.get("scenarios") or []
        for scn in scenarios:
            if not isinstance(scn, dict):
                continue
            scn_id = scn.get("id", "")
            scn_title = scn.get("title", "")
            intent = scn.get("intent", "")
            if not intent:
                intent = scn_id  # fall back to id if no intent
            # A scenario may serve more than one intent, and the manifest schema
            # accepts either a string or a list of them. It answers for each
            # id separately: keying on the whole list instead would invent a
            # composite intent that supersedes neither of the real ones.
            intents = intent if isinstance(intent, list) else [intent]
            for one_intent in intents:
                entry = {
                    "slug": slug,
                    "scn_id": scn_id,
                    "scn_title": scn_title,
                    "intent": one_intent,
                    "land_timestamp": land_ts,
                    "land_date": land_date,
                }
                if one_intent in current:
                    # Supersession: the current winner is archived
                    archived.append(current[one_intent])
                current[one_intent] = entry

    # ---- 3. Compose the derived spec text ----------------------------------
    lines = [
        _DERIVED_HEADER,
        "",
        "# System Specification (derived)",
        "",
        "> `compass _derive-system-spec` builds this file from the "
        "`scenarios:` block of each landed issue's "
        "`.compass/work/<slug>/manifest.yml`.",
        "> **Do not hand-edit** - the next derivation overwrites it.",
        "> Edit the source: the scenario in that manifest, and its prose in the "
        "issue's `acceptance-criteria.md` under `docs/compass/<created>-<slug>/`.",
        "",
    ]

    if current:
        lines += [
            "## Current Behaviour",
            "",
        ]
        # Sort current entries by intent id for deterministic output
        for intent_id in sorted(current.keys()):
            entry = current[intent_id]
            lines += [
                f"### {entry['scn_title'] or entry['scn_id']}",
                "",
                f"- **Scenario id:** `{entry['scn_id']}`",
                f"- **Intent:** `{entry['intent']}`",
                f"- **Source issue:** `{entry['slug']}`",
                f"- **Landed:** {entry['land_date']}",
                "",
            ]
    else:
        lines += [
            "## Current Behaviour",
            "",
            "> No landed scenarios yet.",
            "",
        ]

    # The archive is most of the history and almost none of what a reader
    # opens the spec for, so it has its own file; the spec points to it.
    archive_lines = list(lines[:1]) + [
        "",
        "# System Specification - Archive (derived)",
        "",
        "> Scenarios superseded by a later-landed scenario with the same intent "
        "id. The current behaviour is in `docs/system-spec.md`.",
        "",
    ]
    if archived:
        lines += [
            "---",
            "",
            f"{len(archived)} superseded scenario(s) are in "
            "`docs/system-spec-archive.md`.",
            "",
        ]
        archive_lines += [
            "## Archived Behaviour",
            "",
            "> These scenarios were superseded by a later-landed scenario "
            "with the same intent id.",
            "",
        ]
        # Sort archived entries: land_timestamp, then scn_id for determinism
        archived_sorted = sorted(archived, key=lambda x: (x["land_timestamp"], x["scn_id"]))
        for entry in archived_sorted:
            archive_lines += [
                f"### {entry['scn_title'] or entry['scn_id']} _(archived)_",
                "",
                f"- **Scenario id:** `{entry['scn_id']}`",
                f"- **Intent:** `{entry['intent']}`",
                f"- **Source issue:** `{entry['slug']}`",
                f"- **Landed:** {entry['land_date']}",
                "",
            ]

    content = "\n".join(lines)
    archive_content = "\n".join(archive_lines)

    # ---- 3b. Normalise house style on write ---------------------------------
    # Scenario titles from landed issues are copied verbatim, and four historic
    # ones contain em dashes. docs/system-spec.md is tracked, and this
    # repository forbids em dashes in tracked files - so a faithful copy
    # produces a file that fails the repository's own style test.
    #
    # The normalisation happens HERE, on the output, and never on the sources.
    # Those acceptance-criteria.md files are a record of what was specified at the
    # time; editing them to suit a generator would rewrite history, and would
    # have to be repeated in every adopter's archive. A generator owns its
    # output, so it owns its output's style.
    # \u2014 is the em dash, written as an escape: this file is tracked, and
    # the style test would otherwise flag the normaliser for containing the
    # character it exists to remove.
    # Normalise at the substitution site only. Do not add a global
    # `.replace("  -  ", " - ")`: it rewrites titles that never held an em
    # dash.
    # [ \t] not \s: \s matches newlines, so an em dash at the end of a line
    # would remove the line break and join a heading to the list after it.
    content = re.sub(r"[ \t]*\u2014[ \t]*", " - ", content)
    archive_content = re.sub(r"[ \t]*\u2014[ \t]*", " - ", archive_content)

    # ---- 4. Write atomically -----------------------------------------------
    out_path, archive_path = (os.path.join(project_root, *rel.split("/"))
                              for rel in LIVING_SPEC_FILES)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    with open(archive_path, "w", encoding="utf-8") as fh:
        fh.write(archive_content)


def cmd_derive_system_spec(args):
    """Private CLI entry point for ``compass _derive-system-spec --internal``.

    This subcommand is intentionally excluded from ``compass --help`` (a
    leading underscore marks a private verb).  It is only for in-framework
    callers (now ``scripts/integrate.sh``).

    The ``--internal`` flag is mandatory - without it the command errors out
    (a second guard against running it by accident).
    """
    if not getattr(args, "internal", False):
        raise CompassError(
            "compass _derive-system-spec: the --internal flag is required. "
            "This is a private entry point for scripts/integrate.sh - "
            "it is not part of the public CLI surface."
        )

    # Resolve project root from the current working directory
    # (walk up to find .compass/, fall back to cwd for brand-new projects).
    try:
        compass_dir = find_compass_dir()
        project_root = os.path.dirname(compass_dir)
    except CompassError:
        # Brand-new project with no .compass/ yet - use cwd
        project_root = os.getcwd()

    derive_system_spec(project_root)
    print("compass _derive-system-spec: docs/system-spec.md derived.")
