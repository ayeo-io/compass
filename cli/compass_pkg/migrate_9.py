# compass_pkg.migrate_9 - `compass migrate`: move an 8.x project's open issues to 9.0.0
"""`compass migrate` turns each open, assessed 8.x issue into a path issue (#359).

It runs the write path of `compass approach evaluate --write` (`routing.
cmd_route_evaluate`, with `path_writer.write`) on each issue, with the reason
`REASON`, so the issue gets the path keys and a new generation from the check
set, as a reassessment under 9.0.0 does (VD-020). What that write drops, and
the 8.x records no path reader uses, move under the manifest's `legacy:` key
(`move_records`) in the same write. No check reads `legacy:`.

The stage follows the records, as on every path issue (ADR-092). The command
prints the 8.x stage, the path stage the records give and, when the records
place the issue earlier than `stable_ids.LEGACY_TO_PATH` maps its 8.x stage,
the reason (`held_back`). It writes no red, green or outcome to move it.

What it never writes: an approval, a checkpoint outcome, a delegation copy, a
gate state, or any file under `evidence/` (ADR-095). It writes the manifest,
the generation the commit stores and, when the issue has one, `trail.md` again,
so the trail's sum lines match the new manifest (ADR-096).

It is a dry run unless `--apply` is given: exit 0 when there is nothing to do,
1 when there is, and 2 when it refuses. It refuses a project 9.0.0 cannot read
without 8.x first: a copied governance folder with no `compass.yml`, and an
`extends:` that names a git parent. A missing request link is not asked for
at a prompt: the issue is listed with the `compass issue link set` command,
and `--request` and `--requester` with `--issue` record it in the same run.

The settings half, `compass_pkg.migrate_settings`, rewrites `compass.yml`
first, so a converted issue reads the new settings. `--settings-only` and
`--issues-only` run one half; `--issue` runs the issues half only.
The owning doc is `docs/upgrade-9-0-0.md`.
"""
# DEPENDENCY: standard library (contextlib, copy, io, os, argparse); compass_pkg.core,
# effective, migrate_settings, next_cmd, path_stages, refusals, request_link, routing,
# stable_ids, status_words, terminal, trail (imported in functions where `routing` would
# otherwise load at import time).
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import os

from compass_pkg import refusals, request_link, status_words
from compass_pkg.core import CompassError, find_compass_dir, load_manifest, manifest_path
from compass_pkg.stable_ids import LEGACY_TO_PATH, PATH_STAGE_IDS, STAGE_BUILD, STAGE_SPECIFY

VERB = "compass migrate"
#: The reason of the `reassessments:` entry each converted manifest gets, so
#: `compass retro` and the trail show the change.
REASON = "compass migrate to 9.0.0"
#: The kind of that entry: the assessment was right, the policy under it moved.
KIND = "policy-correction"
#: The 8.x records no 9.0.0 reader of a path issue uses. Each moves under
#: `legacy:` with the same name.
MOVED_RECORDS = ("subtasks", "models", "page_ticks", "readiness")
#: The one document 9.0.0 keeps (ADR-091). Its entry keeps these fields, so
#: `core._registry` still finds the spec; the rest (`revision`, `round` and the
#: like) go to `legacy.artifact_status`. `status` stays because the manifest
#: schema needs it on every entry.
CRITERIA_KIND = "acceptance-criteria"
CRITERIA_FIELDS = ("id", "kind", "path", "reason", "status")
LEGACY = "legacy"


# --- what moves under legacy: ---------------------------------------------------------

def _path_stage(value):
    """The path stage of a legacy stage value, or None when `value` is not one."""
    mapped = LEGACY_TO_PATH.get(value) if isinstance(value, str) else None
    return mapped if mapped is not None and mapped != value else None


def move_records(task, kept):
    """Move the 8.x records of the manifest under `legacy:`. `kept` holds the keys
    `path_writer.write` took out (`stages`, `subtask_ceiling`, `orchestration`,
    `max_worktrees`). Returns the names of what moved, for the report."""
    # Copies, so no value is shared with a key the manifest keeps (such as a
    # `reassessments:` entry), which YAML would write as an anchor and alias.
    legacy = copy.deepcopy(kept)
    for key in MOVED_RECORDS:
        if key in task:
            legacy[key] = copy.deepcopy(task.pop(key))
    artifacts = task.get("artifacts")
    if isinstance(artifacts, list):
        documents, criteria, status = [], [], {}
        for entry in artifacts:
            if isinstance(entry, dict) and entry.get("kind") == CRITERIA_KIND:
                criteria.append({k: v for k, v in entry.items() if k in CRITERIA_FIELDS})
                rest = {k: v for k, v in entry.items() if k not in CRITERIA_FIELDS}
                if rest:
                    status[str(entry.get("id") or CRITERIA_KIND)] = copy.deepcopy(rest)
            else:
                documents.append(copy.deepcopy(entry))
        if documents:
            legacy["documents"] = documents
        if status:
            legacy["artifact_status"] = status
        if criteria:
            task["artifacts"] = criteria
        else:
            task.pop("artifacts", None)
    stage_values = {}
    for i, dep in enumerate(task.get("depends_on") or []):
        new = _path_stage(dep.get("until")) if isinstance(dep, dict) else None
        if new:
            stage_values[f"depends_on[{i}].until"] = dep["until"]
            dep["until"] = new
    raised = task.get("raised_by")
    new = _path_stage(raised.get("found_at")) if isinstance(raised, dict) else None
    if new:
        stage_values["raised_by.found_at"] = raised["found_at"]
        raised["found_at"] = new
    if stage_values:
        legacy["stage_values"] = stage_values
    if legacy:
        task[LEGACY] = legacy
    return sorted(legacy)


class Migration:
    """What `routing.cmd_route_evaluate` calls back into for one issue: `kept`
    collects the keys `path_writer.write` takes out, and `before_commit` moves
    the 8.x records and records the request in the same write. With `apply`
    false the evaluator stops before it writes anything."""

    def __init__(self, apply, request=None):
        self.apply = apply
        self.request = request
        self.kept = {}
        self.moved = []
        self.task = None

    def before_commit(self, task):
        self.moved = move_records(task, self.kept)
        github = task.get("github")
        if isinstance(github, dict) and isinstance(github.get("repo"), str) \
                and isinstance(github.get("number"), int):
            request_link.link_from_github(task, (github["repo"], github["number"]))
        if self.request is not None:
            link, target, requester = self.request
            if target is not None and not task.get("github"):
                task["github"] = {"repo": target[0], "number": target[1]}
            request_link.record(task, link, requester)
        self.task = copy.deepcopy(task)


# --- where the issue stands -------------------------------------------------------------

def _scenario_line(task):
    """Why specify is not done on the records, naming the first scenario."""
    from compass_pkg import next_step
    scenarios = [s for s in task.get("scenarios") or [] if isinstance(s, dict)]
    if not scenarios:
        return "the issue has no scenario yet"
    for s in scenarios:
        sid = s.get("id") or "a scenario"
        if not s.get("id"):
            return "a scenario has no id"
        if not s.get("intent"):
            return f"{sid} has no intent"
        if s.get("verifiable") != "narrative" and not next_step._tests_of(s):
            return f"{sid} declares no test"
    return ("the specify checkpoint has no outcome; a person answers it after "
            "compass evidence request --checkpoint specify")


def _build_line(task, task_dir):
    """Why build is not done on the records, naming the first scenario."""
    from compass_pkg import next_step
    from compass_pkg.red_first import scenario_reds
    reds = scenario_reds(task, task_dir)
    if reds["late"]:
        sid = reds["late"][0][0]
        return f"{sid} has a green and no red before it"
    green = next_step.greens(task)
    for s in next_step.needing_tests(task):
        if s["id"] in reds["no_red"]:
            return f"{s['id']} has no red"
        if s["id"] not in green:
            return f"{s['id']} has no green"
    return "build is not done on the records"


def held_back(before, after, task, task_dir):
    """The reason the records place the issue at `after` when its 8.x stage
    `before` maps to a later path stage, or None."""
    want = LEGACY_TO_PATH.get(before, before)
    if want not in PATH_STAGE_IDS or after not in PATH_STAGE_IDS:
        return None
    if PATH_STAGE_IDS.index(after) >= PATH_STAGE_IDS.index(want):
        return None
    if after == STAGE_SPECIFY:
        return _scenario_line(task)
    if after == STAGE_BUILD:
        return _build_line(task, task_dir)
    return None


def _stage(task, task_dir):
    from compass_pkg.next_cmd import _current_phase_from_task
    return _current_phase_from_task(task, task_dir) or "done"


# --- which issues -----------------------------------------------------------------------

def _left(task):
    """Why an issue is left as it is, or None to convert it."""
    if status_words.is_closed(task):
        return "closed"
    if "evidence_required" in task:
        return "already on the four-stage path"
    if LEGACY in task:
        # A spike stays off the path, so the `legacy:` key says it was moved.
        return "already moved by compass migrate"
    if not task.get("delivery_approach"):
        return "never assessed"
    if str(task.get("schema_version", "")).split(".")[0] in ("0", "1"):
        return "schema 1.x"
    return None


def _issue_dirs(work, only):
    if only:
        return [os.path.join(work, only)]
    if not os.path.isdir(work):
        return []
    return [os.path.join(work, name) for name in sorted(os.listdir(work))
            if os.path.isfile(manifest_path(os.path.join(work, name)))]


def _refuse_project(root):
    """Refuse a project 9.0.0 cannot read without 8.x first (exit 2)."""
    from compass_pkg import effective
    if effective.has_governance_copy(root):
        raise CompassError(refusals.render("governance-copy-removed", verb=VERB))
    parent = effective.git_parent_of(effective.project_doc(root))
    if parent:
        raise CompassError(refusals.render("git-parent-removed", verb=VERB, parent=parent))


def _evaluate(slug, migration):
    """Run the write path of `approach evaluate --write` on one issue, with its
    output kept from the terminal. Raises what the evaluator raises."""
    from compass_pkg.routing import cmd_route_evaluate
    args = argparse.Namespace(
        reading=None, task=slug, write=True, reason=REASON, kind=KIND, justify=None,
        expected_acceptance=None, json=False, _mode="summary", evidence_out=None,
        migration=migration)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        cmd_route_evaluate(args)


def _rewrite_trail(task_dir):
    from compass_pkg import trail
    if not os.path.isfile(trail.path_of(task_dir)):
        return False
    trail.write(task_dir)
    return True


def migrate_issue(task_dir, apply, request=None):
    """Convert one issue. Returns the row the report prints."""
    slug = os.path.basename(os.path.normpath(task_dir))
    task, _ = load_manifest(task_dir)
    left = _left(task)
    if left == "schema 1.x":
        return {"issue": slug, "result": "refused",
                "detail": "a 1.x manifest; run compass issue migrate --apply first"}
    if left:
        return {"issue": slug, "result": "left", "detail": left}
    from compass_pkg import effective
    effective.require_whole(task_dir)
    before = _stage(task, task_dir)
    migration = Migration(apply, request)
    _evaluate(slug, migration)
    after_task = migration.task
    trail_written = False
    if apply:
        after_task, _ = load_manifest(task_dir)
        trail_written = _rewrite_trail(task_dir)
    after = _stage(after_task, task_dir)
    link, requester = request_link.recorded(after_task)
    row = {"issue": slug, "result": "converted" if apply else "would convert",
           "from": before, "to": after, "legacy": migration.moved,
           "needs_request": not (link and requester), "trail": trail_written}
    reason = held_back(before, after, after_task, task_dir)
    if reason:
        row["held_back"] = reason
    return row


# --- the verb ---------------------------------------------------------------------------

def _request_flags(args):
    request, requester = getattr(args, "request", None), getattr(args, "requester", None)
    if request is None and requester is None:
        return None
    if not getattr(args, "task", None):
        raise CompassError(f"{VERB}: --request and --requester name one issue's request; "
                           "give --issue <slug> too. Nothing was written.")
    return request_link.parse(request, requester, VERB)


def _row_line(row):
    if row["result"] in ("left", "refused"):
        return f"{row['issue']}: {row['result']} - {row['detail']}"
    line = f"{row['issue']}: {row['from']} -> {row['to']}"
    if row.get("held_back"):
        line += f" ({row['held_back']})"
    if row["legacy"]:
        line += f"; legacy: {', '.join(row['legacy'])}"
    if row.get("trail"):
        line += "; trail.md written again"
    return line


def _halves(args):
    """`(settings, issues)`: which halves this run does."""
    settings_only = bool(getattr(args, "settings_only", False))
    issues_only = bool(getattr(args, "issues_only", False))
    if getattr(args, "task", None):
        if settings_only:
            raise CompassError(f"{VERB}: --issue names one issue, and --settings-only "
                               f"runs no issue; give one of them. Nothing was written.")
        issues_only = True
    return not issues_only, not settings_only


def cmd_migrate(args):
    from compass_pkg import migrate_settings
    from compass_pkg.project_settings import find_project_root
    from compass_pkg.terminal import Report
    apply = bool(getattr(args, "apply", False))
    request = _request_flags(args)
    do_settings, do_issues = _halves(args)
    compass_dir = find_compass_dir()
    root = find_project_root(os.path.dirname(compass_dir))
    _refuse_project(root)
    settings = migrate_settings.migrate(root, compass_dir, apply) if do_settings else None
    rows = []
    for task_dir in (_issue_dirs(os.path.join(compass_dir, "work"), getattr(args, "task", None))
                     if do_issues else ()):
        if not os.path.isdir(task_dir):
            raise CompassError(f"{VERB}: no issue directory for slug "
                               f"'{os.path.basename(task_dir)}'")
        try:
            rows.append(migrate_issue(task_dir, apply, request))
        except CompassError as exc:
            rows.append({"issue": os.path.basename(task_dir), "result": "refused",
                         "detail": str(exc).splitlines()[0]})
    converted = [r for r in rows if r["result"] in ("converted", "would convert")]
    refused = [r for r in rows if r["result"] == "refused"]
    needs = [r for r in converted if r["needs_request"]]
    by_stage = {}
    for r in converted:
        by_stage[r["to"]] = by_stage.get(r["to"], 0) + 1
    verb = "converted" if apply else "would convert"
    stages = ", ".join(f"{n} at {s}" for s, n in sorted(
        by_stage.items(), key=lambda kv: PATH_STAGE_IDS.index(kv[0])
        if kv[0] in PATH_STAGE_IDS else len(PATH_STAGE_IDS)))
    report = Report(args)
    if settings is not None:
        report.summary(_settings_summary(settings))
    if do_issues:
        report.summary(
            f"{VERB}: {verb} {len(converted)} issue(s)" + (f" ({stages})." if stages else "."),
            f"Left {len(rows) - len(converted) - len(refused)} as they are; "
            f"refused {len(refused)}.")
    report.summary(None if apply else "Dry run: nothing was written.",
                   f"{len(needs)} issue(s) need a request link." if needs else None)
    if settings is not None:
        report.section("settings", settings["changes"], lambda line: line)
        report.section("settings not carried over", settings["dropped"], lambda line: line)
        report.section("settings left for you to edit", settings["left"],
                       lambda r: f"{r['key']}: left as it is - {r['edit']}")
        report.section("settings refused, nothing written", settings["refused"],
                       lambda line: line)
        report.section("diff", settings["diff"], lambda line: line)
    report.section("issues", converted, _row_line)
    report.section("refused", refused, _row_line)
    report.section("needs a request link", needs,
                   lambda r: request_link.command(r["issue"]))
    report.section("left as they are", [r for r in rows if r["result"] == "left"], _row_line)
    report.data(apply=apply, settings=settings, issues=rows)
    report.emit()
    if refused or (settings and settings["result"] == "refused"):
        return 2
    changing = converted or (settings and settings["result"] == "would change")
    return 1 if changing and not apply else 0


def _settings_summary(result):
    name = result["file"]
    return {
        "nothing": f"{VERB}: {name} holds no key 9.0.0 removed.",
        "would change": f"{VERB}: would rewrite {name} ({len(result['changes'])} change(s)).",
        "changed": f"{VERB}: rewrote {name} ({len(result['changes'])} change(s)).",
        "refused": f"{VERB}: refused to rewrite {name}; nothing was written to it.",
        "left": f"{VERB}: left {name} as it is.",
    }[result["result"]] + (f" {len(result['left'])} key(s) left for you to edit."
                           if result["left"] else "")


def register(sub):
    """Add `compass migrate`."""
    p = sub.add_parser("migrate", help="move an 8.x project's compass.yml and open "
                                       "issues to 9.0.0 (dry run unless --apply)")
    p.add_argument("--apply", action="store_true",
                   help="write the changes the dry run lists")
    p.add_argument("--issue", dest="task", metavar="SLUG",
                   help="only this issue (default: every issue under .compass/work); "
                        "compass.yml is left as it is")
    half = p.add_mutually_exclusive_group()
    half.add_argument("--settings-only", action="store_true",
                      help="rewrite compass.yml only, and no issue")
    half.add_argument("--issues-only", action="store_true",
                      help="move the issues only, and leave compass.yml as it is")
    p.add_argument("--request", metavar="URL",
                   help="with --issue: the request the issue answers, an https:// URL "
                        "or owner/repo#number")
    p.add_argument("--requester", metavar="NAME",
                   help="with --issue: who asked for the change, recorded as a claim")
    p.set_defaults(func=cmd_migrate, output_kind="report")
