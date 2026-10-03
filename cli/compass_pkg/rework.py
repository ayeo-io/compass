#!/usr/bin/env python3
# =============================================================================
# compass_pkg.rework - the cross-issue rework scanner (compass rework-scan)
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


# --- command: rework-scan ---------------------------------------------------
# Cross-issue rework scanner. Reads every manifest.yml under --root (default:
# .compass/work/) and detects add-then-delete patterns within the configured
# window. Output is Markdown (default) or JSON (--format json). This is a
# SIGNAL, not a gate - exit code is always 0 unless the scan itself errors.
# Patterns are loaded from governance/signals.yml at runtime, never hardcoded.
# Suitable for piping into .compass/flow/rework-<date>.md.
#
# Detection modes:
#   1. Simple add-then-delete: file added by issue A, deleted by issue B
#      within window_days.
#   2. Public-surface churn: the path matches a public_surface_patterns regex
#      AND the same file is added then deleted.
#   3. Migration pair: a file matching migration_paths (glob) is added in
#      issue A, and a semantically paired drop migration is added in issue B
#      within window_days.
#
# Read-only over the issue directories (Inv-4); it writes nothing.

import fnmatch
import re as _re
from compass_pkg.core import CompassError, FRAMEWORK_ROOT, find_compass_dir, find_upwards, load_manifest, load_yaml, manifest_path, normalize_spine, resolve_issue_dir, save_manifest


_SIGNALS_ENV_VAR = "COMPASS_SIGNALS_YML"


def _find_signals_yml(root_arg):
    """Locate governance/signals.yml.

    Resolution order:
      1. COMPASS_SIGNALS_YML environment variable (tests use this to inject
         a per-test signals.yml without touching the real governance/).
      2. Project-local governance/ walking up from the scan root.
      3. The framework's shipped governance/ next to the CLI.
    """
    # 1. Environment override (used in tests)
    env_path = os.environ.get(_SIGNALS_ENV_VAR)
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. Walk up from the scan root
    proj = find_upwards(root_arg, os.path.join("governance", "signals.yml"))
    if proj:
        return os.path.join(proj, "governance", "signals.yml")

    # 3. Framework shipped default
    shipped = os.path.join(FRAMEWORK_ROOT, "governance", "signals.yml")
    if os.path.isfile(shipped):
        return shipped

    return None


def _load_signals(root_arg):
    """Load the rework_scan configuration from signals.yml."""
    path = _find_signals_yml(root_arg)
    if path is None:
        # Minimal safe defaults if no signals.yml is found anywhere
        return {
            "window_days": 14,
            "public_surface_patterns": ["/api/v[0-9]+/", "pb\\."],
            "migration_paths": ["migrations/*.sql", "**/migrations/*.sql"],
        }
    try:
        data = load_yaml(path)
    except CompassError:
        return {
            "window_days": 14,
            "public_surface_patterns": [],
            "migration_paths": [],
        }
    rs = data.get("rework_scan") or {}
    return {
        "window_days": int(rs.get("window_days", 14)),
        "public_surface_patterns": list(rs.get("public_surface_patterns") or []),
        "migration_paths": list(rs.get("migration_paths") or []),
    }


def _matches_migration_glob(path, migration_paths):
    """Return True if `path` matches any of the migration glob patterns."""
    for pattern in migration_paths:
        if fnmatch.fnmatch(path, pattern):
            return True
        # Also try matching just the filename against simple patterns
        filename = os.path.basename(path)
        base_pattern = os.path.basename(pattern)
        if base_pattern and fnmatch.fnmatch(filename, base_pattern):
            return True
    return False


def _is_drop_migration(path_b, path_a):
    """Heuristic: does path_b look like a 'drop' counterpart to path_a?

    A drop migration typically has a higher sequential number and contains
    a word like 'drop', 'remove', 'revert', or 'rollback' in its name.
    Both must be migration files.
    """
    name_a = os.path.basename(path_a).lower()
    name_b = os.path.basename(path_b).lower()
    drop_words = ("drop", "remove", "revert", "rollback", "delete")
    if not any(w in name_b for w in drop_words):
        return False
    # Extract the table/entity name from path_a (rough heuristic)
    # e.g. "024_create_runs.sql" -> "runs"
    # Try to find a noun from path_a in path_b
    # We look for alphanumeric segments in path_a that also appear in path_b
    segments_a = _re.findall(r"[a-z][a-z0-9]+", name_a)
    segments_b = set(_re.findall(r"[a-z][a-z0-9]+", name_b))
    stop_words = {"sql", "migration", "migrations", "create", "add", "update",
                  "alter", "drop", "remove", "revert", "rollback", "delete",
                  "table", "index", "column", "schema"}
    for seg in segments_a:
        if seg not in stop_words and seg in segments_b:
            return True
    return False


def _parse_created_date(task_data, slug):
    """Parse the issue creation date. Returns a datetime.date or None."""
    raw = task_data.get("created")
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return None


def _read_tasks_from_root(root):
    """Yield (slug, task_data) pairs. Emits warnings to stderr for bad files."""
    if not os.path.isdir(root):
        raise CompassError(f"rework-scan: root directory not found: {root}")
    warnings = []
    tasks = []
    for entry in sorted(os.listdir(root)):
        entry_path = os.path.join(root, entry)
        if not os.path.isdir(entry_path):
            continue
        task_yml = manifest_path(entry_path)
        if not os.path.isfile(task_yml):
            continue
        try:
            with open(task_yml, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValueError("top-level value is not a mapping")
            data = normalize_spine(data)
            tasks.append((entry, data))
        except Exception as exc:
            warnings.append((task_yml, str(exc)))
            sys.stderr.write(f"WARNING: skipped {task_yml}: {exc}\n")
    return tasks, warnings


def cmd_rework_scan(args):
    """Cross-issue rework scanner. Exit code: 0 always (signal not gate).

    Only exits non-zero if the scan itself errors (e.g. --root not found).
    """
    root = args.root
    fmt = getattr(args, "format", "markdown") or "markdown"

    # Resolve default root from .compass/work/ if not given
    if root is None:
        try:
            compass_dir = find_compass_dir()
            root = os.path.join(compass_dir, "work")
        except CompassError:
            root = ".compass/work"

    # Load signals from disk at runtime, never hardcoded
    signals = _load_signals(root)
    window_days = int(getattr(args, "window_days", None) or signals["window_days"])
    public_patterns = signals["public_surface_patterns"]
    migration_paths = signals["migration_paths"]

    # Read all manifest.yml files under root
    try:
        tasks, skipped_warnings = _read_tasks_from_root(root)
    except CompassError as exc:
        sys.stderr.write(f"compass rework-scan: {exc}\n")
        return 1  # scan itself errored - non-zero is correct here

    # Build a list of (slug, path, action, date) records
    records = []
    for slug, task_data in tasks:
        created = _parse_created_date(task_data, slug)
        for cf in (task_data.get("changed_files") or []):
            path = cf.get("path", "")
            action = (cf.get("action") or "").lower()
            if path and action in ("added", "deleted"):
                records.append({
                    "slug": slug,
                    "path": path,
                    "action": action,
                    "date": created,
                })

    # Detect rework instances
    rework_instances = []

    # Build index: path -> list of records
    by_path = {}
    for r in records:
        by_path.setdefault(r["path"], []).append(r)

    # Mode 1 & 2: simple add-then-delete (and public-surface subset)
    for path, path_records in by_path.items():
        adds = [r for r in path_records if r["action"] == "added"]
        deletes = [r for r in path_records if r["action"] == "deleted"]
        for add in adds:
            for delete in deletes:
                # The delete must be from a different issue
                if add["slug"] == delete["slug"]:
                    continue
                # Both must have dates; delete must be after add
                if add["date"] is None or delete["date"] is None:
                    in_window = True  # no date - assume within window
                else:
                    if delete["date"] < add["date"]:
                        continue
                    gap = (delete["date"] - add["date"]).days
                    in_window = gap <= window_days
                if not in_window:
                    continue
                # Determine the kind
                kind = "add-then-delete"
                # Check if path matches a public_surface_patterns regex
                for pattern in public_patterns:
                    try:
                        if _re.search(pattern, path):
                            kind = "public-surface-churn"
                            break
                    except _re.error:
                        pass
                gap_days = None
                if add["date"] and delete["date"]:
                    gap_days = (delete["date"] - add["date"]).days
                rework_instances.append({
                    "kind": kind,
                    "path": path,
                    "added_by": add["slug"],
                    "removed_by": delete["slug"],
                    "add_date": str(add["date"]) if add["date"] else None,
                    "remove_date": str(delete["date"]) if delete["date"] else None,
                    "gap_days": gap_days,
                })

    # Mode 3: migration pairs
    # For each migration added by issue A, look for a drop migration added by issue B
    add_migrations = [r for r in records
                      if r["action"] == "added"
                      and _matches_migration_glob(r["path"], migration_paths)]
    for add in add_migrations:
        # Look for a corresponding drop migration added by another issue
        drop_candidates = [
            r for r in records
            if r["action"] == "added"
            and r["slug"] != add["slug"]
            and _matches_migration_glob(r["path"], migration_paths)
            and _is_drop_migration(r["path"], add["path"])
        ]
        for drop in drop_candidates:
            if add["date"] is None or drop["date"] is None:
                in_window = True
            else:
                if drop["date"] < add["date"]:
                    continue
                gap = (drop["date"] - add["date"]).days
                in_window = gap <= window_days
            if not in_window:
                continue
            gap_days = None
            if add["date"] and drop["date"]:
                gap_days = (drop["date"] - add["date"]).days
            rework_instances.append({
                "kind": "migration-pair",
                "path": add["path"],
                "counterpart_path": drop["path"],
                "added_by": add["slug"],
                "removed_by": drop["slug"],
                "add_date": str(add["date"]) if add["date"] else None,
                "remove_date": str(drop["date"]) if drop["date"] else None,
                "gap_days": gap_days,
            })

    # Emit output
    if fmt == "json":
        import json as _json
        out = {
            "rework_instances": rework_instances,
            "instance_count": len(rework_instances),
            "tasks_scanned": len(tasks),
            "skipped": len(skipped_warnings),
            "window_days": window_days,
        }
        print(_json.dumps(out, indent=2))
    else:
        # Markdown output (default)
        _emit_markdown_report(rework_instances, tasks, skipped_warnings,
                              window_days, root)

    # Always exit 0 - detection is a signal, not a gate
    return 0


def _emit_markdown_report(instances, tasks, skipped, window_days, root):
    n = len(instances)
    print("## Rework scan")
    print("")
    from compass_pkg.terminal import relative_to_project
    print(f"Scanned {len(tasks)} issue(s) under `{relative_to_project(root)}` "
          f"(window: {window_days} days).")
    if skipped:
        print(f"Skipped {len(skipped)} issue(s) due to parse errors "
              f"(see stderr for details).")
    print("")
    if n == 0:
        print("**0 rework instances detected.** No add-then-delete patterns "
              "within the window.")
        return
    print(f"**{n} rework instance(s) detected** - these are informational "
          f"signals; no issue state has been modified.")
    print("")
    for i, inst in enumerate(instances, 1):
        kind = inst["kind"]
        path = inst.get("path", "")
        added_by = inst.get("added_by", "?")
        removed_by = inst.get("removed_by", "?")
        gap = inst.get("gap_days")
        gap_str = f" ({gap} day(s) apart)" if gap is not None else ""
        if kind == "migration-pair":
            counterpart = inst.get("counterpart_path", "")
            print(f"{i}. **migration-pair** - `{path}` added by `{added_by}`, "
                  f"drop migration `{counterpart}` added by `{removed_by}`"
                  f"{gap_str}.")
        else:
            label = "public-surface-churn" if kind == "public-surface-churn" else "add-then-delete"
            print(f"{i}. **{label}** - `{path}` added by `{added_by}`, "
                  f"deleted by `{removed_by}`{gap_str}.")
    print("")
    print("> This report is advisory only. Flow advises, never gates (Inv-4).")


# --- command: follow-up resolve ----------------------------------------------
# Marks a named follow-up resolved, which lets the target issue ship. It is
# the only command here that writes a manifest; flow and retro are
# read-only.

def cmd_backfill_pay(args):
    """Flip the named follow-up to status: resolved in the issue's
    manifest.yml. (Internal name unchanged - the public verb is
    `compass follow-up resolve`.)"""
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    bf_id = args.backfill_id
    follow_ups = task.get("follow_ups") or []
    found = None
    for bf in follow_ups:
        if isinstance(bf, dict) and bf.get("id") == bf_id:
            found = bf
            break
    if not found:
        raise CompassError(
            f"follow-up '{bf_id}' not found in issue '{args.task}'. "
            f"Available follow-ups: "
            f"{[b.get('id') for b in follow_ups if isinstance(b, dict)]}"
        )
    if found.get("status") == "resolved":
        print(f"compass follow-up resolve: '{bf_id}' is already resolved.")
        return 0
    found["status"] = "resolved"
    task["follow_ups"] = follow_ups
    save_manifest(task, task_path)
    target = found.get("target_task")
    target_note = (f" (cross-issue debt on '{target}' is now cleared)"
                   if target else "")
    print(f"compass follow-up resolve: '{bf_id}' in issue '{args.task}' "
          f"marked resolved{target_note}.")
    return 0
