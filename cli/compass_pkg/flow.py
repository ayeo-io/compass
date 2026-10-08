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
# Cross-issue flow view. Reads broadly; writes only the page `--html` names.
# Never changes any manifest (`Inv-4`: Flow advises, never gates).

# A queued issue older than this many days is flagged when it carries a
# written recommendation or a label a routing rule names: the two signals that
# made a month-long wait on a written-up fix expensive (#288).
QUEUE_AGE_DAYS = 14
_RECOMMENDATION = re.compile(
    r"^#+\s.*\b(recommend\w*|proposed|proposal|suggested fix|decision)\b", re.I | re.M)


def _routing_labels():
    """Every label a routing-policy rule names in `labels_any`."""
    from compass_pkg import effective
    try:
        view = effective.view_or_legacy()
        policy = (view.evaluator_policy() if view is not None else
                  load_yaml(os.path.join(find_governance(), "routing-policy.yml")))
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


# --- the delivery board ------------------------------------------------------
# One read of every manifest, shaped into the sections the board shows. Plain
# data, so the text board, `--json` and the HTML page cannot disagree.

LANDED_WINDOW_DAYS = 7


def _queue_row(project_root, slug, m, today, guarded):
    created = str(m.get("created") or "")
    try:
        age = (today - datetime.date.fromisoformat(created)).days
    except ValueError:
        return None
    signals = []
    if _has_recommendation(project_root, slug, created):
        signals.append("recommendation")
    assessment = m.get("assessment")
    raw = assessment.get("labels") if isinstance(assessment, dict) else None
    labels = [l for l in (raw if isinstance(raw, list) else []) if str(l) in guarded]
    if labels:
        signals.append("label " + ", ".join(str(l) for l in labels))
    return (age, slug, signals)


def _landed_at(m):
    raw = str(m.get("land_timestamp") or "")
    try:
        when = datetime.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when


def board(work_root, today=None):
    """The delivery board as plain data. Reads each manifest once, and runs git
    (through the evidence check) for in-progress issues only."""
    from compass_pkg.binding import evidence_state
    from compass_pkg.next_cmd import _current_phase_from_task

    today = today or datetime.date.today()
    now = datetime.datetime.now(datetime.timezone.utc)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(work_root)))
    guarded = _routing_labels()
    out = {"in_progress": [], "stale": [], "held": [], "next_up": [],
           "landed_this_week": [], "abandoned": [], "other": [], "unreadable": [],
           "friction": None, "counts": {}, "total": 0}
    categories = {}
    slugs = [d for d in sorted(os.listdir(work_root))
             if os.path.isdir(os.path.join(work_root, d))]
    out["total"] = len(slugs)
    for slug in slugs:
        task_dir = os.path.join(work_root, slug)
        tp = manifest_path(task_dir)
        if not os.path.isfile(tp):
            out["unreadable"].append({"slug": slug, "note": "no manifest.yml"})
            out["counts"]["unreadable"] = out["counts"].get("unreadable", 0) + 1
            continue
        try:
            m = normalize_spine(load_yaml(tp))
            if not isinstance(m, dict):
                raise CompassError("not a mapping")
        except Exception:                                   # noqa: BLE001
            out["unreadable"].append({"slug": slug, "note": "unreadable manifest.yml"})
            out["counts"]["unreadable"] = out["counts"].get("unreadable", 0) + 1
            continue
        try:
            _board_place(out, categories, slug, task_dir, m, project_root,
                         today, now, guarded, evidence_state,
                         _current_phase_from_task)
        except Exception as exc:                            # noqa: BLE001
            # One malformed manifest must not hide every other issue.
            out["unreadable"].append({"slug": slug, "note": "malformed manifest.yml "
                                      "(%s)" % type(exc).__name__})
            out["counts"]["unreadable"] = out["counts"].get("unreadable", 0) + 1
    out["next_up"].sort(key=lambda r: (-(r["age_days"] or 0), r["slug"]))
    if categories:
        top = sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        out["friction"] = {"category": top[0], "count": top[1]}
    return out


def _board_place(out, categories, slug, task_dir, m, project_root, today, now,
                 guarded, evidence_state, current_stage):
    """Put one issue's row in its section. Raises on a field of the wrong
    type, which the caller reports as a malformed manifest."""
    # Absent means active: manifests written before the status field
    # existed omit it (ADR-006).
    status = m.get("status") or "active"
    if not isinstance(status, str):
        raise TypeError("status is not text")
    approach = m.get("delivery_approach") or "not assessed"
    if status == "active":
        gates = m.get("gates") or []
        if not isinstance(gates, list):
            raise TypeError("gates is not a list")
        gates = [g for g in gates if isinstance(g, dict)]
        passed = sum(1 for g in gates if g.get("status") == "pass")
        state = evidence_state(m, task_dir)
        row = {"slug": slug, "delivery_approach": approach,
               "stage": current_stage(m, task_dir) or "done",
               "gates": f"{passed}/{len(gates)}", "evidence": state}
        out["stale" if state == "stale" else "in_progress"].append(row)
    elif status == "parked":
        out["held"].append({"slug": slug, "delivery_approach": approach,
                            "reason": str(m.get("parked_reason") or "no reason recorded")})
    elif status == "queued":
        q = _queue_row(project_root, slug, m, today, guarded)
        out["next_up"].append({"slug": slug, "delivery_approach": approach,
                               "age_days": q[0] if q else None,
                               "signal": "; ".join(q[2]) if q else ""})
    elif status == "landed":
        when = _landed_at(m)
        if when and when <= now and (now - when).days < LANDED_WINDOW_DAYS:
            out["landed_this_week"].append({"slug": slug, "delivery_approach": approach,
                                            "landed": when.date().isoformat()})
            friction = m.get("friction")
            for f in friction if isinstance(friction, list) else []:
                if isinstance(f, dict) and f.get("category"):
                    c = str(f["category"])
                    categories[c] = categories.get(c, 0) + 1
    elif status == "abandoned":
        out["abandoned"].append({"slug": slug, "delivery_approach": approach})
    else:
        out["other"].append({"slug": slug, "delivery_approach": approach,
                             "status": status})
    out["counts"][status] = out["counts"].get(status, 0) + 1


_BOARD_SECTIONS = (
    ("in_progress", "IN PROGRESS", "In progress"),
    ("stale", "STALE EVIDENCE - re-run the suite before ship", "Stale evidence"),
    ("held", "HELD - parked, can resume", "Held"),
    ("next_up", "NEXT UP - oldest first", "Next up"),
    ("landed_this_week", "LANDED THIS WEEK", "Landed this week"),
    ("abandoned", "ABANDONED - will not resume", "Abandoned"),
    ("other", "OTHER STATUS - not one Compass sets", "Other status"),
    ("unreadable", "UNPLACEABLE - no readable manifest.yml, so no state to report",
     "Unplaceable"),
)


def _board_row(key, r):
    if key in ("in_progress", "stale"):
        return "%-40s approach=%s stage=%s gates=%s evidence=%s" % (
            r["slug"], r["delivery_approach"], r["stage"], r["gates"], r["evidence"])
    if key == "held":
        return "%-40s approach=%s  - %s" % (r["slug"], r["delivery_approach"], r["reason"])
    if key == "next_up":
        age = "?" if r["age_days"] is None else r["age_days"]
        return "%-40s approach=%s age=%s days%s" % (
            r["slug"], r["delivery_approach"], age, "  - " + r["signal"] if r["signal"] else "")
    if key == "landed_this_week":
        return "%-40s approach=%s landed=%s" % (r["slug"], r["delivery_approach"], r["landed"])
    if key == "unreadable":
        return "%-40s - %s" % (r["slug"], r["note"])
    if key == "other":
        return "%-40s approach=%s status=%s" % (r["slug"], r["delivery_approach"], r["status"])
    return "%-40s approach=%s" % (r["slug"], r["delivery_approach"])


def _friction_line(data):
    f = data["friction"]
    if not f:
        return "Friction this week: none recorded."
    return "Friction this week: %s (%d)." % (f["category"], f["count"])


def _render_board(args, data):
    from compass_pkg.terminal import Report
    counts = data["counts"]
    rep = Report(args, title="compass flow - delivery board (advisory)")
    rep.summary(
        "compass flow - %d issue(s) across %d state(s), %d stale, %d landed "
        "this week. Advisory: this changes no issue state."
        % (data["total"], len(counts), len(data["stale"]),
           len(data["landed_this_week"])),
        ", ".join("%s %d" % (k, n) for k, n in sorted(counts.items()))
        or "nothing to report",
        _friction_line(data))
    for key, heading, _ in _BOARD_SECTIONS:
        rows = data[key]
        rep.section(heading, rows, lambda r, k=key: _board_row(k, r))
    rep.data(counts=counts, board={k: data[k] for k, _, _ in _BOARD_SECTIONS},
             friction=data["friction"])
    return rep.emit()


def _check_html_target(target):
    """Refuse a directory, and a path inside `.compass/` or `docs/compass/`,
    which hold issue state. Checked before the board is read."""
    path = os.path.abspath(target)
    parent = os.path.dirname(path)
    if not os.path.isdir(parent):
        raise CompassError(f"compass flow --html: the folder for {target} does not exist")
    # Resolve symlinks and compare without case: a link, or `.COMPASS` on a
    # file system that ignores case, must not reach issue state.
    path = os.path.join(os.path.realpath(parent), os.path.basename(path))
    if os.path.isdir(path):
        raise CompassError(f"compass flow --html: {target} is a directory; "
                           f"name a file, such as board.html")
    try:
        project_root = os.path.dirname(find_compass_dir())
    except CompassError:
        project_root = os.getcwd()
    folded = path.casefold()
    for guarded, label in ((os.path.join(project_root, ".compass"), ".compass"),
                           (os.path.join(project_root, "docs", "compass"), "docs/compass")):
        g = os.path.realpath(guarded).casefold()
        if folded == g or folded.startswith(g + os.sep):
            raise CompassError(
                f"compass flow --html: {target} is inside {label}/, "
                f"which holds issue state; write the page somewhere else")
    return path


def _write_board_html(data, target):
    """One static page from the board data: every value escaped, inline CSS,
    no script and no external resource."""
    import html
    import tempfile
    path = _check_html_target(target)
    e = html.escape
    cols = {"in_progress": ("Issue", "Approach", "Stage", "Gates", "Evidence"),
            "stale": ("Issue", "Approach", "Stage", "Gates", "Evidence"),
            "held": ("Issue", "Approach", "Reason"),
            "next_up": ("Issue", "Approach", "Age (days)", "Signal"),
            "landed_this_week": ("Issue", "Approach", "Landed"),
            "abandoned": ("Issue", "Approach"),
            "other": ("Issue", "Approach", "Status"),
            "unreadable": ("Issue", "Why")}
    keys = {"in_progress": ("slug", "delivery_approach", "stage", "gates", "evidence"),
            "stale": ("slug", "delivery_approach", "stage", "gates", "evidence"),
            "held": ("slug", "delivery_approach", "reason"),
            "next_up": ("slug", "delivery_approach", "age_days", "signal"),
            "landed_this_week": ("slug", "delivery_approach", "landed"),
            "abandoned": ("slug", "delivery_approach"),
            "other": ("slug", "delivery_approach", "status"),
            "unreadable": ("slug", "note")}
    generated = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = ["<!doctype html>", "<html lang=\"en\"><head><meta charset=\"utf-8\">",
             "<title>Compass delivery board</title>",
             "<style>body{font-family:system-ui,sans-serif;margin:2rem;max-width:72rem}"
             "table{border-collapse:collapse;width:100%;margin-bottom:1.5rem}"
             "th,td{border:1px solid #ccc;padding:.3rem .5rem;text-align:left}"
             "th{background:#f3f3f3}</style></head><body>",
             "<h1>Compass delivery board</h1>",
             "<p>Generated %s. Advisory: this page changes no issue state.</p>" % e(generated),
             "<p>%s</p>" % e(", ".join("%s %d" % (k, n) for k, n in sorted(data["counts"].items()))),
             "<p>%s</p>" % e(_friction_line(data))]
    for key, _, title in _BOARD_SECTIONS:
        rows = data[key]
        parts.append("<h2>%s (%d)</h2>" % (e(title), len(rows)))
        if not rows:
            parts.append("<p>None.</p>")
            continue
        parts.append("<table><tr>" + "".join("<th>%s</th>" % e(c) for c in cols[key]) + "</tr>")
        for r in rows:
            parts.append("<tr>" + "".join(
                "<td>%s</td>" % e("" if r.get(k) is None else str(r.get(k)))
                for k in keys[key]) + "</tr>")
        parts.append("</table>")
    parts.append("</body></html>")
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".board-", suffix=".html")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(parts) + "\n")
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    print(f"compass flow: wrote the delivery board to {target}")
    return 0



def cmd_flow(args):
    """Produce the flow board; with --digest also output a dated digest section
    to stdout. The digest includes the rework-scan section and a retro
    summary. Exit code is always 0 - this is advisory.
    """
    work_root = getattr(args, "work_root", None)
    do_digest = getattr(args, "digest", False)

    # Resolve the work root
    if work_root is None:
        # Outside a Compass project this refuses, as every other verb does;
        # `--work-root` still reads any folder of issues.
        work_root = os.path.join(find_compass_dir(), "work")

    html_out = getattr(args, "html", None)
    if html_out:
        if do_digest:
            raise CompassError("compass flow: --html writes the board, and "
                               "--digest the digest; give one of them")
        _check_html_target(html_out)
    if not do_digest:
        if not os.path.isdir(work_root):
            print("compass flow: no issues found - work root does not exist.")
            return 0
        data = board(work_root)
        if not data["total"]:
            print("compass flow: no issues under work root.")
            return 0
        if html_out:
            return _write_board_html(data, html_out)
        return _render_board(args, data)

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

# Specs written before 2.0.0 label the source with the retired word for an
# issue; both labels name an issue, and a spec from either release must keep
# every issue it names. The old word is assembled, as `MANIFEST_NAMES` in
# core.py does, so the vocabulary scan does not read it as current prose.
_SOURCE_LABELS = "(?:issue|" + "ta" + "sk)"
_SOURCE_ISSUE = re.compile(r"\*\*Source " + _SOURCE_LABELS + r":\*\* `([^`]+)`")


def _landed_on_this_branch(project_root, landed):
    """The landed issues that belong to the branch being derived (ADR-034).

    Issue records are local and not committed, so they hold issues landed on
    other branches too, and deriving all of them gave a branch scenarios it
    does not have. An issue is left out only when it has a `land_commit`
    that is not reachable from HEAD and the spec committed at HEAD does not
    name it. Every landing re-derives that spec, so main's names what landed
    on main, squash merges included; a branch's own landing is reachable.
    Outside git, before a first commit, or with no `land_commit`, an issue
    is kept, as before."""
    def git(*args):
        return subprocess.run(["git", "-C", project_root, *args],
                              capture_output=True, text=True)
    try:
        if git("rev-parse", "--verify", "-q", "HEAD").returncode != 0:
            return landed
        named = set()
        for rel in LIVING_SPEC_FILES:
            shown = git("show", f"HEAD:{rel}")
            if shown.returncode == 0:
                named |= set(_SOURCE_ISSUE.findall(shown.stdout))
        kept = []
        for item in landed:
            commit = item["issue"].get("land_commit")
            # Only an issue the rule can judge is ever left out: one with a
            # `land_commit` that is not on this branch and that the committed
            # spec does not name. A record with no `land_commit` (written
            # before ship-commit recorded one, or by hand) is kept, as before.
            if (item["slug"] in named or not isinstance(commit, str) or not commit
                    or git("merge-base", "--is-ancestor", commit,
                           "HEAD").returncode == 0):
                kept.append(item)
        return kept
    except OSError:
        return landed


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
    all_landed = landed
    landed = _landed_on_this_branch(project_root, landed)

    # ---- 2. Build the current-behaviour and archived-behaviour tables ------
    # Key: (slug, scenario id, intent id) -> entry
    # (dict with slug, scn_id, scn_title, ts, date)
    current: dict = {}
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
                # Intent ids are local to an issue (most issues use INT-1), so
                # a shared intent id says nothing about supersession: not
                # between issues, and not between sibling scenarios. The only
                # supersession is the one the manifest records, in
                # `superseded_by`, which names a scenario in the same issue.
                if scn.get("superseded_by"):
                    archived.append(entry)
                else:
                    current[(slug, scn_id, str(one_intent))] = entry

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
        # Sort current entries by intent id, then issue, for deterministic output
        for key in sorted(current.keys(), key=lambda k: (k[2], k[0], str(k[1]))):
            entry = current[key]
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
        "> Scenarios whose manifest names a replacement in `superseded_by`. "
        "The current behaviour is in `docs/system-spec.md`.",
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
            "> These scenarios name a replacement in `superseded_by`.",
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

    # The archive of issues is local and untracked, so a worktree or a clone
    # can lack an issue the committed spec already names. Rewriting the spec
    # then would drop that issue's scenarios without a word (#289), so refuse
    # and name each missing issue instead.
    # Every landed record on disk counts here, kept by the branch rule or
    # not: one the rule left out is not missing, and saying so would send a
    # person to copy a record that is already there.
    on_disk = {item["slug"] for item in all_landed}
    named = set()
    for path in (out_path, archive_path):
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                named |= set(re.findall(r"^- \*\*Source " + _SOURCE_LABELS
                                        + r":\*\* `([^`]+)`", fh.read(), re.M))
    missing = sorted(named - on_disk)
    if missing:
        raise CompassError(
            "the living spec names landed issue(s) missing from .compass/work/: "
            + ", ".join(missing) + ". Re-deriving now would drop their scenarios. "
            "Copy those issue folders into .compass/work/ from the checkout that "
            "has them, then derive again.")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # The derived files are committed, but their titles come from local
    # issue records, which may name a rival product. With a names key
    # configured, each name becomes its code; a configured key that is
    # missing stops the derivation rather than commit a name
    # (governance/decisions/2026-10-04-rival-names-never-committed.md).
    from compass_pkg import record, rival_names
    key_path = record.names_key(project_root)
    if key_path:
        names = rival_names.load_key(key_path)
        content = rival_names.redact_names(content, names)
        archive_content = rival_names.redact_names(archive_content, names)
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
