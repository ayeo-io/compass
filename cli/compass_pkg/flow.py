#!/usr/bin/env python3
# =============================================================================
# compass_pkg.flow - `compass flow` and the delivery board
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
from compass_pkg import parse_cache, path_stages, status_words
from compass_pkg.core import (CompassError, find_compass_dir, find_governance,
                              load_yaml, manifest_path, normalize_spine)
from compass_pkg.stable_ids import APPROACH_SPIKE, PATH_STAGE_IDS, STAGE_IDS, STAGE_SHIP



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
    """(top line, table) for the digest: backlog issues by age, and the old
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
        if not isinstance(m, dict) or not status_words.is_queued(m):
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
        return "**Queue aging:** No backlog issues.", "## Queue age\n\nNo backlog issues.\n"
    flagged = [f"{slug} ({age} days, {'; '.join(sig)})"
               for age, slug, sig in rows if age > QUEUE_AGE_DAYS and sig]
    if flagged:
        top = (f"**Queue aging:** {len(flagged)} backlog issue(s) older than "
               f"{QUEUE_AGE_DAYS} days carry a recommendation or a guarded label: "
               + ", ".join(flagged) + ".")
    else:
        top = (f"**Queue aging:** no backlog issue older than {QUEUE_AGE_DAYS} days "
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


THIS_CHECKOUT = "this checkout"
_NO_MANIFEST = "no manifest.yml"
_UNREADABLE = "unreadable manifest.yml"
# Role is no longer an assessment dimension (ADR-070), so a recorded one is not shown.
_ASSESSMENT_DIMENSIONS = ("risk", "familiarity", "size", "goal")


def _schema_major_is_read(schema_version):
    """True for an absent version or a major of 1, 2 or 3: the majors
    `core.load_manifest` reads. The board keeps its own copy so that this
    issue leaves manifest loading alone; the two answer alike."""
    if not schema_version:
        return True
    return str(schema_version).split(".")[0] in ("1", "2", "3")


def _issue_folders(work_root):
    if not os.path.isdir(work_root):
        return []
    return [d for d in sorted(os.listdir(work_root))
            if os.path.isdir(os.path.join(work_root, d))]


def _parse_manifest(task_dir, cache):
    """`(manifest, None)`, or `(None, why it could not be read)`. `cache` is
    the parse cache of the checkout doing the reading (ADR-049)."""
    tp = manifest_path(task_dir)
    if not os.path.isfile(tp):
        return None, _NO_MANIFEST
    try:
        m = normalize_spine(cache.load_yaml(tp))
        if not isinstance(m, dict):
            raise CompassError("not a mapping")
    except Exception:                                       # noqa: BLE001
        return None, _UNREADABLE
    return m, None


def read_checkout(work_root):
    """Every folder under this checkout's work root, parsed once: slug to the
    parsed manifest (a dict), or to the reason it could not be read (text).
    `board(parsed=...)` reuses the result, so a manifest is read once."""
    cache = parse_cache.for_work_root(work_root)
    found = {}
    for slug in _issue_folders(work_root):
        m, why = _parse_manifest(os.path.join(work_root, slug), cache)
        found[slug] = m if why is None else why
    cache.finish()
    return found


def _checkout_sources(work_root):
    """The sources of a board that reads this checkout only."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(work_root)))
    return [{"slug": slug, "task_dir": os.path.join(work_root, slug),
             "tree": THIS_CHECKOUT, "tree_root": project_root, "also_in": 0,
             "refused": None} for slug in _issue_folders(work_root)]


def _where(src):
    """The keys every row carries about where its manifest was read."""
    rel = os.path.relpath(manifest_path(src["task_dir"]), src["tree_root"])
    return {"tree": src["tree"], "manifest_path": rel.replace(os.sep, "/"),
            "also_in": src["also_in"]}


def _unreadable(out, src, note):
    # No manifest was read, so no dependency was judged.
    out["unreadable"].append(dict({"slug": src["slug"], "note": note}, **_where(src),
                                  depends_on=[]))
    out["counts"]["unreadable"] = out["counts"].get("unreadable", 0) + 1


def board(work_root, today=None, sources=None, parsed=None):
    """The delivery board as plain data. Reads each manifest once, and runs git
    (through the evidence check) for in-progress issues only.

    `sources` is None for this checkout (every folder under `work_root`) or a
    list of source dicts, one per issue folder, which may sit in other trees.
    `parsed` is `read_checkout`'s result, reused for this checkout's sources;
    every other source is parsed here, once."""
    from compass_pkg import effective, lifecycle
    from compass_pkg.binding import evidence_state

    today = today or datetime.date.today()
    now = datetime.datetime.now(datetime.timezone.utc)
    guarded = _routing_labels()
    # The one reader that stores parses (ADR-049). The board reads and saves
    # nothing else, so a fault in the cache can only misplace a row here.
    cache = parse_cache.for_work_root(work_root)
    out = {"backlog": [], "ready": [], "in_progress": [], "stale": [],
           "in_review": [], "done_this_week": [], "closed": [], "other": [],
           "unreadable": [], "friction": None, "counts": {}, "total": 0,
           "done_by_reason": {reason: 0 for reason in status_words.CLOSE_REASONS}}
    categories = {}
    if sources is None:
        sources = _checkout_sources(work_root)
    # A slug is one issue however many trees hold it: count slugs, and do not
    # list a copy that was not read (a link out of its tree) for a slug whose
    # other copy has a card.
    read_slugs = {s["slug"] for s in sources if not s.get("refused")}
    out["total"] = len({s["slug"] for s in sources})
    # Every source is read before any is placed, so a dependency is judged by
    # the copy of that issue the board shows (ADR-048), from what was already
    # parsed: the board only advises, so it may read through the cache
    # (ADR-062). A folder with no manifest is left out, and reads as not found.
    read = []
    found = {}
    for src in sources:
        if src.get("refused"):
            read.append((src, None, None))
            continue
        known = parsed.get(src["slug"]) if parsed and src["tree"] == THIS_CHECKOUT else None
        if isinstance(known, dict):
            m, why = known, None
        elif isinstance(known, str):
            m, why = None, known
        else:
            m, why = _parse_manifest(src["task_dir"], cache)
        read.append((src, m, why))
        if why is None:
            found[src["slug"]] = (m, src["task_dir"])
        elif why != _NO_MANIFEST:
            found[src["slug"]] = why
    reader = lifecycle.mapping_reader(found)
    for src, m, why in read:
        if src.get("refused"):
            if src["slug"] not in read_slugs:
                _unreadable(out, src, src["refused"])
            continue
        if why is not None:
            _unreadable(out, src, why)
            continue
        try:
            _board_place(out, categories, src, m, today, now, guarded, evidence_state, reader)
        except effective.MajorRefusal as exc:
            # A generation built by another major refuses its own issue, not the board.
            _unreadable(out, src, str(exc))
        except Exception as exc:                            # noqa: BLE001
            # One malformed manifest must not hide every other issue.
            _unreadable(out, src, "malformed manifest.yml (%s)" % type(exc).__name__)
    out["backlog"].sort(key=lambda r: (-(r["age_days"] or 0), r["slug"]))
    if categories:
        top = sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        out["friction"] = {"category": top[0], "count": top[1]}
    if parsed is None:
        # With `parsed`, this checkout was read and pruned by `read_checkout`.
        # This run reads only other trees, so judging which entries went
        # unused from it would delete this checkout's.
        cache.finish()
    return out


def _text(value):
    return None if value is None else str(value)


def _gate_facts(m):
    """`("passed/total", [{id, status}])` for the gates as recorded."""
    gates = m.get("gates")
    entries = [g for g in gates if isinstance(g, dict)] if isinstance(gates, list) else []
    passed = sum(1 for g in entries if g.get("status") == "pass")
    listed = [{"id": str(g.get("id") or ""), "status": str(g.get("status") or "pending")}
              for g in entries]
    return "%d/%d" % (passed, len(entries)), listed


def _why_fields(m):
    """The fields that say why an issue has its delivery approach, and the
    first reason the page cannot place the issue (None when it can).

    A field of the wrong type reads as empty and is named in the reason; the
    issue keeps the section it had before these fields were read."""
    problems = []
    if not _schema_major_is_read(m.get("schema_version")):
        problems.append("schema_version %s is not one this Compass reads"
                        % m.get("schema_version"))
    named = m.get("current_phase")
    if isinstance(named, str) and named.strip().lower() not in STAGE_IDS + PATH_STAGE_IDS:
        problems.append("current_phase %r names no stage" % named)
    assessment, raw = None, m.get("assessment")
    if isinstance(raw, dict) and raw:
        labels = raw.get("labels")
        # A dimension the assessment leaves out (a quick fix records no goal it was
        # not given) reads as not assessed, never as a default.
        assessment = {k: _text(raw.get(k)) or "not assessed" for k in _ASSESSMENT_DIMENSIONS}
        assessment["labels"] = [str(x) for x in labels] if isinstance(labels, list) else []
    elif raw is not None and not isinstance(raw, dict):
        problems.append("assessment is not a mapping")
    rules, raw = [], m.get("policy_rules_fired")
    if isinstance(raw, list):
        for rule in raw:
            if not isinstance(rule, dict):
                problems.append("policy_rules_fired holds an entry that is not a mapping")
                continue
            changed = rule.get("changed")
            changed = [str(c) for c in changed] if isinstance(changed, list) else (
                [] if changed is None else [str(changed)])
            rules.append({"id": _text(rule.get("id")), "kind": _text(rule.get("kind")),
                          "rationale": _text(rule.get("rationale")), "changed": changed})
    elif raw is not None:
        problems.append("policy_rules_fired is not a list")
    depths, raw = {}, m.get("stages")
    if isinstance(raw, dict):
        depths = {s: str(raw[s]) for s in STAGE_IDS if raw.get(s) is not None}
    elif raw is not None:
        problems.append("stages is not a mapping")
    if m.get("gates") is not None and not isinstance(m.get("gates"), list):
        problems.append("gates is not a list")
    gates, gate_list = _gate_facts(m)
    created = m.get("created")
    fields = {"gates": gates, "gate_list": gate_list, "assessment": assessment,
              "policy_rules_fired": rules, "stage_depths": depths,
              "created": str(created) if created else None,
              "set_aside": status_words.is_held(m), "recommendation": False}
    return fields, (problems[0] if problems else None)


def _lane_of(row, recorded, held, stage, m):
    """The lane the page puts an open issue in (decided here, never again by
    the page). An unplaceable issue has none. The stage lanes are the issue's
    own stages (`path_stages.stages_of`): a path issue sits in a path stage's
    lane, and an issue assessed before the path keeps its legacy stage's lane."""
    if row["unplaceable"]:
        return None
    if not recorded or held:
        return "backlog"
    if stage in path_stages.stages_of(m) or stage in STAGE_IDS:
        return stage
    return STAGE_SHIP if stage == "done" else None


def _board_place(out, categories, src, m, today, now, guarded, evidence_state, read=None):
    """Put one issue's row in its section. Raises on a field of the wrong
    type, which the caller reports as a malformed manifest."""
    from compass_pkg import issue_detail
    from compass_pkg import lifecycle, next_cmd
    slug, task_dir = src["slug"], src["task_dir"]
    where = _where(src)
    status = m.get("status")
    if status is not None and not isinstance(status, str):
        raise TypeError("status is not text")
    approach = m.get("delivery_approach") or "not assessed"
    if not (status_words.is_in_flight(m) or status_words.is_held(m)
            or status_words.is_closed(m)):
        # A stored word Compass does not set: shown as it is, not placed.
        out["other"].append(dict(
            {"slug": slug, "delivery_approach": approach, "status": status,
             "note": "the stored status %r is not one Compass sets" % status}, **where,
            depends_on=[d.row() for d in (lifecycle.judge(m, slug, read) if read else ())]))
        out["counts"][status] = out["counts"].get(status, 0) + 1
        return
    # No stored status means in flight: the state comes from the records. The
    # facts come from one function, called through its module so a test can
    # replace it (ADR-051).
    facts = issue_detail.detail(m, task_dir, read=read)
    state = facts.state
    row = {"slug": slug, "delivery_approach": approach, "state": state,
           "readiness": facts.readiness}
    # The stored flag's reason first, then what the issue waits for (ADR-062).
    blocked = lifecycle.blocked_text(facts.blocked, facts.waits)
    if blocked:
        row["blocked"] = blocked
    row["depends_on"] = [d.row() for d in facts.dependencies]
    fields, problem = _why_fields(m)
    fields["gates"] = facts.gates
    fields["documents"] = list(facts.documents)
    row.update(fields)
    row.update(where)
    recorded, held = bool(m.get("delivery_approach")), status_words.is_held(m)
    if state == "backlog":
        q = _queue_row(src["tree_root"], slug, m, today, guarded)
        row.update(age_days=q[0] if q else None, signal="; ".join(q[2]) if q else "",
                   reason=str(m.get("parked_reason") or "") if status_words.is_parked(m) else "")
        row["recommendation"] = ("recommendation" in q[2] if q else _has_recommendation(
            src["tree_root"], slug, str(m.get("created") or "")))
        row["stage"], stage_problem = facts.stage, facts.stage_problem
        row["unplaceable"] = problem or stage_problem
        row["lane"] = _lane_of(row, recorded, held, row["stage"], m)
        out["backlog"].append(row)
    elif state == "ready":
        row["stage"], stage_problem = facts.stage, facts.stage_problem
        row["unplaceable"] = problem or stage_problem
        row["lane"] = _lane_of(row, recorded, held, row["stage"], m)
        out["ready"].append(row)
    elif state == "done":
        row["unplaceable"] = problem
        _board_place_done(out, categories, row, m, now)
    else:
        if not isinstance(m.get("gates") or [], list):
            raise TypeError("gates is not a list")
        evidence = evidence_state(m, task_dir)
        if facts.stage_problem:
            raise TypeError(facts.stage_problem)
        row.update(stage=facts.stage, evidence=evidence, unplaceable=problem)
        row["lane"] = _lane_of(row, recorded, held, row["stage"], m)
        if evidence == "stale":
            out["stale"].append(row)
        else:
            out["in_progress" if state == "in-progress" else "in_review"].append(row)
    out["counts"][state] = out["counts"].get(state, 0) + 1


def _board_place_done(out, categories, row, m, now):
    """A closed issue: completed this week, or closed without delivery. A
    completed issue older than the window is counted and not listed."""
    reason = status_words.close_reason(m)
    if reason in out["done_by_reason"]:
        out["done_by_reason"][reason] += 1
    row.update(stage=None, lane=None)
    if status_words.is_completed(m):
        when = _landed_at(m)
        if when and when <= now and (now - when).days < LANDED_WINDOW_DAYS:
            row["completed"] = when.date().isoformat()
            row["close_reason"] = reason
            row["lane"] = None if row["unplaceable"] else "done"
            out["done_this_week"].append(row)
            friction = m.get("friction")
            for f in friction if isinstance(friction, list) else []:
                if isinstance(f, dict) and f.get("category"):
                    c = str(f["category"])
                    categories[c] = categories.get(c, 0) + 1
    elif reason:
        row["close_reason"] = reason
        out["closed"].append(row)
    else:
        out["other"].append({"slug": row["slug"], "delivery_approach": row["delivery_approach"],
                             "status": m.get("status"),
                             "note": "done with no close reason",
                             "tree": row["tree"], "manifest_path": row["manifest_path"],
                             "also_in": row["also_in"], "depends_on": row["depends_on"]})


_BOARD_SECTIONS = (
    ("in_progress", "IN PROGRESS", "In progress"),
    ("stale", "STALE EVIDENCE - re-run the suite before ship", "Stale evidence"),
    ("in_review", "IN REVIEW", "In review"),
    ("ready", "READY - defined and refined, work not started", "Ready"),
    ("backlog", "BACKLOG - oldest first", "Backlog"),
    ("done_this_week", "DONE THIS WEEK", "Done this week"),
    ("closed", "CLOSED - not planned, or a duplicate", "Closed"),
    ("other", "OTHER STATUS - not one Compass sets", "Other status"),
    ("unreadable", "UNPLACEABLE - no readable manifest.yml, so no state to report",
     "Unplaceable"),
)


def _blocked_suffix(r):
    return "  BLOCKED: %s" % r["blocked"] if r.get("blocked") else ""


def _board_row(key, r):
    if key in ("in_progress", "stale", "in_review"):
        return "%-40s approach=%s stage=%s gates=%s evidence=%s%s" % (
            r["slug"], r["delivery_approach"], r["stage"], r["gates"], r["evidence"],
            _blocked_suffix(r))
    if key == "backlog":
        age = "?" if r["age_days"] is None else r["age_days"]
        return "%-40s approach=%s age=%s days%s%s" % (
            r["slug"], r["delivery_approach"], age,
            "  - " + r["signal"] if r["signal"] else "",
            "  - set aside: " + r["reason"] if r["reason"] else "")
    if key == "done_this_week":
        return "%-40s approach=%s completed=%s" % (
            r["slug"], r["delivery_approach"], r["completed"])
    if key == "closed":
        return "%-40s approach=%s  - %s" % (
            r["slug"], r["delivery_approach"], r["close_reason"])
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
        "compass flow - %d issue(s) across %d state(s), %d stale, %d done "
        "this week. Advisory: this changes no issue state."
        % (data["total"], len(counts), len(data["stale"]),
           len(data["done_this_week"])),
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
    which hold issue state. Checked before the board is read. One guard
    serves every board file (`board_file.check_target`); only the command
    name in its message differs."""
    from compass_pkg import board_file
    return board_file.check_target(target, "compass flow --html", _html_project_root())


def _html_project_root():
    try:
        return os.path.dirname(find_compass_dir())
    except CompassError:
        return os.getcwd()


def _write_board_html(work_root, target):
    """Write the board page, the same page `compass board render` writes."""
    from compass_pkg import board_cmd, board_file
    path = _check_html_target(target)
    page = board_cmd.build_page(_html_project_root(), work_root, False,
                                datetime.datetime.now())
    board_file.write_page_or_refuse("compass flow --html", path, page,
                                    board_file.OUT_MODE)
    print(f"compass flow: wrote the delivery board to {target}")
    return 0


def cmd_flow(args):
    """Produce the flow board; with --digest output a dated digest of the
    backlog to stdout instead. Exit code is always 0 - this is advisory.
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
        # The target is checked first, and the page is written even when
        # there are no issues: it shows ten empty lanes and says so.
        return _write_board_html(work_root, html_out)
    if not do_digest:
        if not os.path.isdir(work_root):
            print("compass flow: no issues found - work root does not exist.")
            return 0
        data = board(work_root)
        if not data["total"]:
            print("compass flow: no issues under work root.")
            return 0
        return _render_board(args, data)

    # --digest mode: the dated backlog list.
    today = datetime.date.today().isoformat()
    print(f"# Flow digest - {today}\n")
    print("> Advisory only. This digest does not modify any issue state (Inv-4).\n")
    top, table = queue_ageing(work_root)
    print(top + "\n")
    print(table)
    return 0
