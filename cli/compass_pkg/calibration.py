#!/usr/bin/env python3
# =============================================================================
# compass_pkg.calibration - `compass retro` and its `--friction` and `--impact` views
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
from compass_pkg.core import CompassError, find_compass_dir, find_governance, load_manifest, load_yaml, manifest_path, migrate_map_section, normalize_spine, resolve_issue_dir, save_manifest



# --- command: retro -----------------------------------------------------
# `compass retro` reads the re-assessment log across every issue and reports
# whether assessment is systematically over- or under-sizing the process.
# Read-only: it advises and never gates.

def _load_scope_bloat_phrases():
    """Load scope_bloat_phrases from signals.yml at runtime.

    Patterns are never hardcoded in the CLI - always read from the
    governance file. Returns an empty list if signals.yml is absent or
    unreadable (graceful degradation).
    """
    try:
        gov = find_governance()
        sig_path = os.path.join(gov, "signals.yml")
        if not os.path.isfile(sig_path):
            return []
        sig = load_yaml(sig_path)
        return list(sig.get("scope_bloat_phrases") or [])
    except CompassError:
        return []


def _find_reframe_debt(tasks, work):
    """Return a list of absorbed mis-assessment records.

    For each issue, scan its devlog.md for scope_bloat_phrases.  An issue
    qualifies as 'reframe debt' when:
      - at least one scope-bloat phrase appears as the start of a devlog line
        (column-0 anchor - same rule as the stop-hook, for consistency), AND
      - manifest.yml's `reassessments` has no entry whose date is >= the date
        of the matching devlog line.

    This function is strictly READ-ONLY; it never writes to any
    manifest.yml or any other file.
    The caller passes the patterns, read from signals.yml.
    """
    phrases = _load_scope_bloat_phrases()
    if not phrases:
        return []

    debts = []
    for slug, task in tasks:
        devlog_path = os.path.join(work, slug, "devlog.md")
        if not os.path.isfile(devlog_path):
            continue

        try:
            with open(devlog_path, "r", encoding="utf-8") as fh:
                devlog_lines = fh.readlines()
        except OSError:
            continue

        # Latest reframe date for this issue
        reframes = task.get("reassessments") or []
        reframe_dates = sorted(
            r.get("date", "") for r in reframes if r.get("date")
        )
        latest_reframe_date = reframe_dates[-1] if reframe_dates else ""

        # Match a phrase as a top-level statement (not nested in
        # quotes/indentation).  The phrase must appear at column 0 OR
        # immediately after an optional YYYY-MM-DD[: ] date prefix.
        # Lines starting with whitespace are skipped (indented/quoted context
        # must not fire - consistency with the stop-hook's own rule).
        import re as _re
        _DATE_PREFIX_PAT = r'^(?:\d{4}-\d{2}-\d{2}[: ]+)?'

        for phrase in phrases:
            compiled = _re.compile(_DATE_PREFIX_PAT + _re.escape(phrase))
            for raw_line in devlog_lines:
                line = raw_line.rstrip("\n")
                # Skip lines with leading whitespace (quoted/indented context)
                if line and line[0].isspace():
                    continue
                if not compiled.match(line):
                    continue
                # Extract a date from the line start (YYYY-MM-DD prefix, if any)
                line_date = ""
                m = _re.match(r'^(\d{4}-\d{2}-\d{2})', line)
                if m:
                    line_date = m.group(1)
                # Suppression: a reframe filed after (or on) the line date
                if latest_reframe_date:
                    if not line_date:
                        # No date on the devlog line → can't order; suppress
                        break
                    if latest_reframe_date >= line_date:
                        break  # reframe filed after or on the bloat line
                # Record the debt
                debts.append({
                    "task": slug,
                    "devlog_line": line,
                    "phrase": phrase,
                })
                break  # one match per phrase per issue is enough

    return debts


def _load_friction_threshold():
    """Load friction.recurrence_threshold from signals.yml at runtime.

    Mirrors _load_scope_bloat_phrases (never hardcode the value in
    the CLI - read it from the governance file). Defaults to 2 when signals.yml
    is absent or the block is unset (ADR-006: clean no-op for non-adopters; and
    2 mirrors `retro`'s own >=2 up/down-sizing thresholds).
    """
    default = 2
    try:
        gov = find_governance()
        sig_path = os.path.join(gov, "signals.yml")
        if not os.path.isfile(sig_path):
            return default
        sig = load_yaml(sig_path)
        fr = sig.get("friction") or {}
        n = fr.get("recurrence_threshold", default)
        n = int(n)
        return n if n >= 1 else default
    except (CompassError, ValueError, TypeError):
        return default


def _aggregate_friction(tasks, threshold):
    """Aggregate the `friction:` lists across issues into recurring clusters.

    Grouping is by case/whitespace-normalised `proposed_change` (clarifications
    Q2 - exact-normalised, never semantic: the aggregator is mechanism, so it
    must be reproducible, ADR-001). A cluster is `recurring` when it is proposed
    by at least `threshold` distinct issues. Pure function; reads nothing, writes
    nothing.
    """
    import re as _re

    def _norm(s):
        return _re.sub(r"\s+", " ", (s or "").strip()).lower()

    clusters = {}
    by_category = {}
    n_with_friction = 0
    for slug, t in tasks:
        fr = t.get("friction") or []
        if fr:
            n_with_friction += 1
        for e in fr:
            if not isinstance(e, dict):
                continue
            cat = e.get("category", "other")
            by_category[cat] = by_category.get(cat, 0) + 1
            pc = e.get("proposed_change") or ""
            key = _norm(pc)
            if not key:
                continue  # nothing to cluster on; still counted by category
            c = clusters.setdefault(
                key, {"proposed_change": pc.strip(), "categories": set(),
                      "tasks": set()})
            c["categories"].add(cat)
            c["tasks"].add(slug)

    recurring, below = [], []
    for c in clusters.values():
        item = {
            "proposed_change": c["proposed_change"],
            "categories": sorted(c["categories"]),
            "tasks": sorted(c["tasks"]),
            "count": len(c["tasks"]),
        }
        (recurring if item["count"] >= threshold else below).append(item)
    recurring.sort(key=lambda x: (-x["count"], x["proposed_change"]))
    below.sort(key=lambda x: x["proposed_change"])
    return {
        "threshold": threshold,
        "tasks_with_friction": n_with_friction,
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "recurring": recurring,
        "below_threshold": below,
    }


def _cmd_calibration_friction(args, tasks):
    """The `compass retro --friction` view. Read-only; exit 0 always
    (Inv: friction advises, never gates - like rework-scan and flow)."""
    threshold = _load_friction_threshold()
    agg = _aggregate_friction(tasks, threshold)

    fmt = getattr(args, "format", "markdown") or "markdown"
    if fmt == "json":
        print(json.dumps(agg, indent=2))
        return 0

    print(f"compass retro --friction - {agg['tasks_with_friction']} "
          f"issue(s) with recorded friction\n")
    if agg["tasks_with_friction"] == 0:
        print("No friction recorded - nothing to aggregate. Either Compass is "
              "staying out of the way, or\nthere is not enough history yet.")
        return 0

    print("Friction by category:")
    for cat, n in agg["by_category"].items():
        print(f"  {cat:<16}: {n}")
    print()
    print(f"Recurring friction (>= {threshold} issues) - candidate framework "
          f"changes:")
    if agg["recurring"]:
        for c in agg["recurring"]:
            cats = ", ".join(c["categories"])
            print(f"  [{cats}] {c['proposed_change']}")
            print(f"      {c['count']} issues: {', '.join(c['tasks'])}")
    else:
        print("  (none yet - no proposed change has recurred across enough "
              "issues)")
    if agg["below_threshold"]:
        print()
        print(f"Below threshold (not yet a trend): "
              f"{len(agg['below_threshold'])} item(s)")
    print()
    print("Advisory only. Claude or a human reads these and drafts targeted "
          "changes to\ngovernance/ or the routes - the loop never edits "
          "governance itself (ADR-001).")
    return 0


def derive_friction(slug, task, work):
    """Assemble the `source: derived` friction entries for one issue from signals
    the CLI already computes - recorded reframes and absorbed reframe-debt.

    A re-assessment records an assessment that misjudged the work.
    Reframe debt is a misjudgement nobody recorded. Both are friction
    by definition. Pure: it
    reads manifest.yml + devlog (via _find_reframe_debt) and writes nothing. Derived
    entries carry no `proposed_change` - a reframe does not propose a specific
    governance change; it is the recurrence of *human*-proposed changes that the
    aggregator clusters on.
    """
    entries = []
    for rf in (task.get("reassessments") or []):
        if not isinstance(rf, dict):
            continue
        fr = rf.get("from_route", "?")
        to = rf.get("to_route", "?")
        reason = (rf.get("reason") or "").strip()
        obs = f"reframe {fr} -> {to}"
        if reason:
            obs += f": {reason}"
        entries.append({
            "phase": "frame",
            "category": "mis-route",
            "observation": obs,
            "source": "derived",
        })
    for d in _find_reframe_debt([(slug, task)], work):
        entries.append({
            "phase": "frame",
            "category": "mis-route",
            "observation": ("absorbed scope-bloat without a reframe: "
                            f"{d['devlog_line']}"),
            "source": "derived",
        })
    return entries


def cmd_friction_capture(args):
    """Private entry point for `compass _friction-capture --internal`, called
    at ship. Assembles the issue's `friction:` list from derived signals plus
    an optional human note and writes it into the manifest.

    It writes ONLY the friction section - never a follow-up or a gate. Friction
    is a strategy-class signal and must never become something that blocks
    shipping (ADR-002). The derivation is mechanism; the `--note` is the only
    judgement input, given by a person (ADR-001).
    """
    if not getattr(args, "internal", False):
        raise CompassError(
            "compass _friction-capture: the --internal flag is required - this "
            "is an in-framework entry point called by the ship procedure, not a "
            "public verb.")
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    slug = os.path.basename(os.path.normpath(task_dir))
    work = os.path.join(find_compass_dir(), "work")

    entries = derive_friction(slug, task, work)

    note = getattr(args, "note", None)
    if note:
        human = {
            "phase": getattr(args, "note_phase", None) or None,
            "category": getattr(args, "note_category", None) or "other",
            "observation": note,
            "source": "human",
        }
        if human["phase"] is None:
            del human["phase"]
        entries.append(human)

    # Merge rather than replace. Derived entries are a pure function of the
    # issue's current state, so they are recomputed and replace the previous
    # derived set; human notes are observations that cannot be recomputed, so
    # they accumulate. Assigning the whole list would discard every note an
    # earlier run recorded.
    existing = task.get("friction") or []
    kept_human = [e for e in existing if e.get("source") == "human"]
    new_human = [e for e in entries if e.get("source") == "human"]
    seen = {e.get("observation") for e in kept_human}
    kept_human += [e for e in new_human if e.get("observation") not in seen]
    entries = [e for e in entries if e.get("source") != "human"] + kept_human

    if entries:
        task["friction"] = entries
        save_manifest(task, path)
        print(f"compass _friction-capture: recorded {len(entries)} friction "
              f"entry(ies) -> {path}")
        for e in entries:
            print(f"  [{e['source']}/{e['category']}] {e.get('observation', '')}")
    else:
        # Recording nothing is a valid, common outcome. Leave the key
        # absent so an issue that hit no friction stays a clean no-op (ADR-006).
        print("compass _friction-capture: no friction derived and no note "
              "supplied - nothing recorded (a valid, common outcome).")
    return 0



# --- process-impact telemetry ------------------------------------------------
# "Earn the gate": does the process weight a delivery approach adds correlate
# with shipping faster or breaking less? Computed from manifest.yml alone -
# `created` and `land_timestamp` are already in the manifest, so no git call
# is needed and the report is deterministic by construction rather than by
# discipline.
#
# The hard part is not the arithmetic, it is refusing to report what the data
# cannot support. A project with no hotfixes has a change-fail rate that is
# UNMEASURABLE, not zero; printing "0%" would read as excellent stability and
# mean silence.

IMPACT_SAMPLE_FLOOR = 20   # landed issues before any correlation is reported
IMPACT_GROUP_FLOOR = 3     # issues in a delivery-approach group before that group is shown


def _impact_days(created, landed):
    """Whole days between an issue's `created` date and its `land_timestamp`."""
    if not created or not landed:
        return None
    try:
        c = datetime.date.fromisoformat(str(created)[:10])
        l = datetime.date.fromisoformat(str(landed)[:10])
    except ValueError:
        return None
    return max((l - c).days, 0)


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return float(xs[m]) if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def compute_impact(tasks):
    """issues: [(slug, data)]. Returns a dict; pure, no I/O, no clock."""
    landed = [(s, d) for s, d in tasks if (d or {}).get("status") == "landed"]
    hotfixes = [(s, d) for s, d in landed if d.get("delivery_approach") == "hotfix"]
    delivery = [(s, d) for s, d in landed if d.get("delivery_approach") != "hotfix"]

    lead, excluded, by_route = [], 0, {}
    for slug, d in delivery:
        days = _impact_days(d.get("created"), d.get("land_timestamp"))
        if days is None:
            excluded += 1
            continue
        lead.append(days)
        route = d.get("delivery_approach", "?")
        g = by_route.setdefault(route, {"n": 0, "lead": [], "gates": set()})
        g["n"] += 1
        g["lead"].append(days)
        g["gates"].add(len(d.get("gates") or []))

    dates = sorted(str(d.get("land_timestamp"))[:10] for _, d in landed
                   if d.get("land_timestamp"))
    span_days = 0
    if len(dates) >= 2:
        try:
            span_days = (datetime.date.fromisoformat(dates[-1])
                         - datetime.date.fromisoformat(dates[0])).days
        except ValueError:
            span_days = 0

    declared = [(s, d) for s, d in hotfixes if d.get("repairs")]
    delivery_slugs = {s for s, _ in delivery}

    # Count DISTINCT delivery issues that were repaired - not the number of
    # hotfixes that named one. Three hotfixes against one issue is one failed
    # issue, not three.
    repaired = sorted({str(d["repairs"]) for _, d in declared
                       if str(d["repairs"]) in delivery_slugs})
    unknown_targets = sorted({str(d["repairs"]) for _, d in declared
                              if str(d["repairs"]) not in delivery_slugs})

    # None, never 0.0, whenever the number would be a lie. That is not only the
    # "no hotfixes" case: hotfixes that declare no `repairs:` target produce a
    # 0% that means "nobody said what they were fixing", which reads as perfect
    # stability. Both are unmeasurable, and both must render as a sentence.
    rate = None
    if declared and delivery:
        rate = 100.0 * len(repaired) / len(delivery)

    restore = [x for x in (_impact_days(d.get("created"), d.get("land_timestamp"))
                           for _, d in hotfixes) if x is not None]

    return {
        "n_landed": len(landed),
        "n_delivery": len(delivery),
        "lead_median": _median(lead),
        "lead_excluded": excluded,
        "span_days": span_days,
        "lands_per_week": (round(len(landed) / (span_days / 7.0), 2)
                           if span_days >= 7 else None),
        "hotfixes": len(hotfixes),
        "hotfixes_declared": len(declared),
        "repaired": repaired,
        "unknown_targets": unknown_targets,
        "change_fail_rate": rate,
        "restore_median": _median(restore),
        "by_route": by_route,
        "withheld": (None if len(landed) >= IMPACT_SAMPLE_FLOOR else
                     "%d landed issue(s); %d required"
                     % (len(landed), IMPACT_SAMPLE_FLOOR)),
    }


def render_impact(r):
    out = ["compass retro --impact - process signal (advisory)", ""]
    if not r["n_landed"]:
        out.append("  Nothing to measure yet - no landed issues on record.")
        return "\n".join(out)

    out.append("  lead time     median %s day(s) over %d issue(s)%s"
               % (r["lead_median"], r["n_delivery"],
                  "" if not r["lead_excluded"]
                  else ", %d excluded (missing a timestamp)" % r["lead_excluded"]))
    out.append("  land freq     %s per week, over a span of %d day(s)"
               % (r["lands_per_week"] if r["lands_per_week"] is not None
                  else "not computable (span under a week)", r["span_days"]))

    if r["change_fail_rate"] is None:
        # NOT "0%". Gate on the RATE, not on hotfix presence: a project with
        # hotfixes that declare no target is just as unmeasurable, and gating on
        # presence fails on a history of only hotfixes.
        if not r["hotfixes"]:
            why = "no hotfixes recorded"
        elif not r["hotfixes_declared"]:
            why = ("%d hotfix(es) recorded, none declaring a `repairs:` target"
                   % r["hotfixes"])
        else:
            why = "no delivery issues to measure against"
        out.append("  change-fail   %s, so change-fail cannot be measured" % why)
        if r["hotfixes"]:
            out.append("                restore time  median %s day(s) across "
                       "%d hotfix(es)" % (r["restore_median"], r["hotfixes"]))
    else:
        cov = ("%d of %d hotfix(es) declared a `repairs:` target"
               % (r["hotfixes_declared"], r["hotfixes"]))
        out.append("  change-fail   %.1f%% of delivery issues were later repaired "
                   "(%s)" % (r["change_fail_rate"], cov))
        if r["repaired"]:
            out.append("                repaired: %s" % ", ".join(r["repaired"]))
        if r["unknown_targets"]:
            out.append("                %d `repairs:` target(s) name no landed "
                       "delivery issue and were not counted: %s"
                       % (len(r["unknown_targets"]),
                          ", ".join(r["unknown_targets"])))
        out.append("  restore time  median %s day(s) across %d hotfix(es)"
                   % (r["restore_median"], r["hotfixes"]))

    out.append("")
    out.append("  by route:")
    for route, g in sorted(r["by_route"].items()):
        gates = ", ".join(str(x) for x in sorted(g["gates"]))
        if g["n"] < IMPACT_GROUP_FLOOR:
            out.append("    %-12s n=%d  (under %d - not summarised)  gates=%s"
                       % (route, g["n"], IMPACT_GROUP_FLOOR, gates))
        else:
            out.append("    %-12s n=%d  lead median %s day(s)  gates=%s"
                       % (route, g["n"], _median(g["lead"]), gates))

    out.append("")
    if r["withheld"]:
        out.append("  CORRELATIONS WITHHELD - %s." % r["withheld"])
        out.append("  Below that sample any correlation between route, gate count")
        out.append("  and outcome is noise wearing a number.")
    else:
        out.append("  Read the by-route figures as a hypothesis to test, not a")
        out.append("  verdict. This is single-project observational data: the")
        out.append("  variables are not controlled, and a heavier route is chosen")
        out.append("  BECAUSE work looks riskier, so slower lead times on heavy")
        out.append("  routes may reflect the work rather than the process weight.")
    return "\n".join(out)


def cmd_calibration(args):
    if getattr(args, "impact", False):
        return _cmd_calibration_impact(args)

    compass_dir = find_compass_dir()
    work = os.path.join(compass_dir, "work")
    weights = {}
    try:
        policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
        weights = {r: s.get("weight")
                   for r, s in (policy.get("route_shapes") or {}).items()
                   if isinstance(s, dict) and isinstance(s.get("weight"), int)}
    except CompassError:
        pass
    # Manifests record the current route names; the policy's keys may still
    # be the machine names. The migration table maps one to the other, so a
    # route weighs the same by either name.
    for machine, name in (migrate_map_section("values", {})
                          .get("delivery_approach") or {}).items():
        if machine in weights and name not in weights:
            weights[name] = weights[machine]

    tasks = []
    if os.path.isdir(work):
        for d in sorted(os.listdir(work)):
            tp = manifest_path(os.path.join(work, d))
            if os.path.isfile(tp):
                try:
                    tasks.append((d, normalize_spine(load_yaml(tp))))
                except CompassError:
                    pass

    # --- friction view - a flag on retro, not a new verb.
    # Read-only, exit 0 always; handles the empty corpus gracefully.
    if getattr(args, "friction", False):
        return _cmd_calibration_friction(args, tasks)

    if not tasks:
        print("compass retro: no issues under .compass/work/ yet - "
              "nothing to calibrate against.")
        return 0

    dist, no_route = {}, []
    for slug, t in tasks:
        r = t.get("delivery_approach")
        if r:
            dist[r] = dist.get(r, 0) + 1
        else:
            no_route.append(slug)

    reframed_tasks, total = 0, 0
    ups = downs = sideways = 0
    unweighed = {}
    transitions = {}
    for slug, t in tasks:
        rfs = t.get("reassessments") or []
        if rfs:
            reframed_tasks += 1
        for rf in rfs:
            total += 1
            fr, to = rf.get("from_route"), rf.get("to_route")
            transitions[f"{fr} -> {to}"] = transitions.get(f"{fr} -> {to}", 0) + 1
            wf, wt = weights.get(fr), weights.get(to)
            if wf is None or wt is None:
                # A route with no weight has no direction to count.
                key = f"{fr} -> {to}"
                unweighed[key] = unweighed.get(key, 0) + 1
            elif wt > wf:
                ups += 1
            elif wt < wf:
                downs += 1
            else:
                sideways += 1

    # The retrospective is a REPORT. Its summary is the SIGNAL - whether
    # assessment is systematically over- or under-sizing - because that is
    # the one thing a reader is here for.
    pct_head = round(100 * reframed_tasks / len(tasks))
    if total == 0:
        _signal = ("no re-frames recorded - either routing is well-calibrated "
                   "or there is not enough history yet")
    elif ups >= 2 and ups > downs * 2:
        _signal = "a lean toward UNDER-sizing (%d up vs %d down)" % (ups, downs)
    elif downs >= 2 and downs > ups * 2:
        _signal = "a lean toward OVER-sizing (%d down vs %d up)" % (downs, ups)
    else:
        _signal = "roughly balanced (%d up / %d down)" % (ups, downs)
    from compass_pkg.terminal import Report
    import contextlib as _cl, io as _io

    _rep = Report(args, title="compass retro")
    _rep.summary("compass retro - %d issue(s), %d re-framed (%d%%): %s."
                 % (len(tasks), reframed_tasks, pct_head, _signal))
    _rep.data(issues=len(tasks), reframed=reframed_tasks,
              reframe_pct=pct_head, up=ups, down=downs, sideways=sideways,
              unweighed=sum(unweighed.values()),
              distribution=dict(dist), no_route=list(no_route),
              transitions=dict(transitions))
    _buf = _io.StringIO()
    _ctx = _cl.redirect_stdout(_buf)
    _ctx.__enter__()
    print("Route distribution:")
    for r in sorted(dist, key=lambda x: (weights.get(x, 99), x)):
        print(f"  {r:<12}: {dist[r]}")
    if no_route:
        print(f"  (no route)  : {len(no_route)}  <- triage did not complete: "
              f"{', '.join(no_route)}")
    print()
    pct = round(100 * reframed_tasks / len(tasks))
    print("Re-framing:")
    print(f"  issues that re-framed : {reframed_tasks} of {len(tasks)} ({pct}%)")
    print(f"  total re-frames      : {total}")
    if total:
        print("  direction:")
        print(f"    up   (assessment under-sized) : {ups}")
        print(f"    down (assessment over-sized)  : {downs}")
        if sideways:
            print(f"    sideways                      : {sideways}")
        if unweighed:
            print(f"    unweighed (a route with no weight in routing-policy.yml): "
                  f"{sum(unweighed.values())}")
            for k, v in sorted(unweighed.items()):
                print(f"      {k} : {v}")
        print("  transitions:")
        for k, v in sorted(transitions.items(), key=lambda x: -x[1]):
            print(f"    {k} : {v}")
    print()
    print("Signal:")
    if total == 0:
        print("  No re-frames recorded - either routing is well-calibrated, or")
        print("  there is not enough history yet. Revisit after more issues.")
    elif ups >= 2 and ups > downs * 2:
        print(f"  {ups} up-reframes vs {downs} down - a lean toward UNDER-sizing.")
        print("  Assess is reading size or risk low. Tune routing-policy.yml")
        print("  `default_shapes`, or sharpen the sizing rubric in the")
        print("  delivery-approach reference docs.")
    elif downs >= 2 and downs > ups * 2:
        print(f"  {downs} down-reframes vs {ups} up - a lean toward OVER-sizing.")
        print("  Assessment is reading risk high; the routes may be heavier")
        print("  than the work warrants. Review routing-policy.yml.")
    else:
        print(f"  {ups} up / {downs} down - roughly balanced, re-frame rate "
              f"{pct}%.")
        print("  Routing looks reasonably calibrated; keep watching the trend.")

    # --- Reframe debt ---------------------------------------------------------
    # Read devlogs for scope-bloat signals that were absorbed without a reframe.
    # Strictly read-only - no manifest.yml is written here.
    # Patterns loaded from signals.yml at runtime (never hardcoded).
    # Advisory only - this section reports, never gates (Inv-4).
    debts = _find_reframe_debt(tasks, work)
    if debts:
        print()
        print("Reframe debt - absorbed mis-frames, signal lost:")
        print("  Each entry below is an issue where a scope-bloat signal was")
        print("  detected in devlog.md but no reframe was filed afterwards.")
        print("  These are missed calibration signals. File a reframe retroactively")
        print("  with: /compass:assess --reassess --reason \"<why scope grew>\"")
        print()
        for d in debts:
            print(f"  issue    : {d['task']}")
            print(f"  signal  : {d['devlog_line']!r}")
            print()
    # Close the capture opened above and hand the prose to the report, which
    # decides what the caller's mode should see. The numbers went in via
    # `data()`, so --json carries the retrospective's findings rather than its
    # paragraphs.
    _ctx.__exit__(None, None, None)
    return _rep.body(_buf.getvalue().rstrip("\n")).emit()


def _cmd_calibration_impact(args):
    """compass retro --impact. Advisory: always exits 0, writes nothing."""
    try:
        work = os.path.join(find_compass_dir(), "work")
    except CompassError:
        work = ".compass/work"
    tasks = []
    if os.path.isdir(work):
        for slug in sorted(os.listdir(work)):
            path = manifest_path(os.path.join(work, slug))
            if os.path.isfile(path):
                try:
                    tasks.append((slug, normalize_spine(load_yaml(path))))
                except CompassError:
                    continue
    print(render_impact(compute_impact(tasks)))
    return 0
