# compass_pkg.compliance - `compass retro --compliance`
"""How often real sessions followed the process, from their transcripts.

Behaviour is otherwise measured only on eval fixtures. This scores the
sessions behind this project's issues with the behaviours in
`evals/judge.py` that a transcript can decide: whether a session assessed
before its first edit, wrote a failing test before code, changed evidence
or other protected files the issue did not trace, and wrote around a
pre-tool hook refusal.

- A session is matched to an issue only through the `usage.session` its
  manifest records; a transcript no issue names is counted as unmatched,
  never assigned by time or path.
- One session can cover many issues, so each issue is scored on its own
  slice: from its `quick-fix start` call to its `quick-fix finish` call or
  the next start call. The assessment behaviour alone also reads back to
  the previous finish call, so an edit made before the start call is seen.
- The transcript is read only by `session_usage`. Its text is held here in
  memory while scoring; what is printed or written is issue ids, behaviour
  names, results and tool-call indices. The judge's reasons can quote a
  command, so they are never printed.

Advisory: no check or gate reads this, and a pattern becomes a pending
lesson only, which takes effect on `compass lesson accept`.
"""
# DEPENDENCY: standard library (datetime, importlib, json, os, re);
# compass_pkg.core, lessons, session_usage; evals/judge.py.
from __future__ import annotations

import datetime
import importlib.util
import json
import os
import re

from compass_pkg import session_usage
from compass_pkg.core import FRAMEWORK_ROOT, find_compass_dir, load_yaml, manifest_path

LESSON_AFTER = 3   # distinct issues a behaviour must fail in

# The advice for each behaviour, the ones a transcript cannot decide and the
# ones judged on the lead-in all live in `evals/judge.py` (`REAL_SESSION_*`),
# so no behaviour id reaches the eval plugin copy, which leaves `evals/` out.

_START = re.compile(r"(?:^|[\s/])compass\s+quick-fix\s+start\b")
_FINISH = re.compile(r"(?:^|[\s/])compass\s+quick-fix\s+finish\b")


def _judge():
    path = os.path.join(FRAMEWORK_ROOT, "evals", "judge.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("compass_compliance_judge", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _since(days):
    return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)


def _issues(work, only, days):
    since = _since(days)
    found = []
    for slug in sorted(os.listdir(work)) if os.path.isdir(work) else []:
        if only and slug != only:
            continue
        path = manifest_path(os.path.join(work, slug))
        if not os.path.isfile(path):
            continue
        try:
            data = load_yaml(path)
        except Exception:  # an unreadable manifest is lint's to report
            continue
        if not isinstance(data, dict) or data.get("status") not in ("landed", "active"):
            continue
        # The window reads when the issue began: `started_at`, else the date
        # it was created, which every manifest carries.
        began = (session_usage._parse_time(data.get("started_at"))
                 or session_usage._parse_time(f"{data.get('created')}T00:00:00+00:00"))
        if began is not None and began < since:
            continue
        found.append((slug, data))
    return found


def _command(event):
    return str(event["input"].get("command") or "") if event["kind"] == "call" else ""


def _slices(events, slug):
    """Two parts of a session for `slug`, or None when no start call names
    it. A start call names the slug as a whole word anywhere among its
    arguments, since the slug comes after the options.

    - `own`: from the start call to the first finish call after it, or to
      just before the next start call. Every behaviour is judged on this.
    - `lead_in`: `own` plus what came before it back to the previous finish
      call. Only the assessment behaviour is judged on this, since an
      edit before the start call is what it looks for; the same stretch can
      hold work on a regular-approach issue, which has no start call to
      mark where it ends, so nothing else reads it."""
    named = re.compile(r"(?<![\w-])" + re.escape(slug) + r"(?![\w-])")
    starts = [i for i, e in enumerate(events) if _START.search(_command(e))]
    mine = next((i for i in starts if named.search(_command(events[i]))), None)
    if mine is None:
        return None
    finishes = [i for i, e in enumerate(events) if _FINISH.search(_command(e))]
    begin = max([i + 1 for i in finishes if i < mine], default=0)
    end = min([i + 1 for i in finishes if i > mine]
              + [i for i in starts if i > mine], default=len(events))
    return {"own": events[mine:end], "lead_in": events[begin:end]}


def _record_and_scenario(root, slug, data, events):
    calls = [e for e in events if e["kind"] == "call"]
    texts = [e["text"] for e in events if e["kind"] == "text"]
    changed = [c["path"] for c in data.get("changed_files") or []
               if isinstance(c, dict) and c.get("path")]
    tests = [str(t).split("::")[0] for s in data.get("scenarios") or []
             if isinstance(s, dict) for t in s.get("tests") or []]
    # The issue's red records, as the judge reads them on a harness record:
    # `compass tdd-red --quiet` prints nothing, so its record is the proof.
    evidence = os.path.join(root, ".compass", "work", slug, "evidence")
    reds = sorted(f".compass/work/{slug}/evidence/{name}"
                  for name in (os.listdir(evidence) if os.path.isdir(evidence) else [])
                  if name.startswith("red-") and name.endswith(".json"))
    record = {"tool_calls": [{"index": i, "name": c["name"], "input": c["input"],
                              "output": c["output"], "is_error": c["is_error"],
                              "denied": False} for i, c in enumerate(calls)],
              "changed_paths": changed, "cwd": root, "compass_files": reds,
              # An edit to a protected file the issue traces is the issue's
              # change - a hook in a framework's own repository - not tampering.
              "traced_paths": changed,
              "final_text": texts[-1] if texts else "",
              "finished": True, "contained": True}
    scenario = {"in_scope": sorted(set(changed + tests)) or ["**"]}
    return record, scenario


def _project_transcripts(root, days):
    """Session ids of this project's main transcripts written in the window,
    from the folder Claude Code names after the project path."""
    folder = os.path.join(session_usage._config_dir(), "projects",
                          re.sub(r"[^A-Za-z0-9]", "-", root))
    if not os.path.isdir(folder):
        return set()
    since = _since(days).timestamp()
    return {name[:-len(".jsonl")] for name in os.listdir(folder)
            if name.endswith(".jsonl")
            and os.path.getmtime(os.path.join(folder, name)) >= since}


def _bump(counts, key):
    counts[key] = counts.get(key, 0) + 1


def report(root, only=None, days=14):
    judge = _judge()
    if judge is None:
        return {"error": "evals/judge.py is not installed, so there is nothing "
                         "to score with"}
    work = os.path.join(root, ".compass", "work")
    rows = {name: {"sessions": 0, "pass": 0, "fail": 0, "undecided": 0}
            for name in judge.BEHAVIOURS}
    failures, skipped, named = [], {}, set()
    for slug, data in _issues(work, only, days):
        usage = data.get("usage") or {}
        session = usage.get("session")
        if not session:
            _bump(skipped, usage.get("reason") or "no-session")
            continue
        named.add(session)
        paths = session_usage.transcript_paths(session)
        if not paths:
            _bump(skipped, "no-transcript")
            continue
        slices = _slices(session_usage.events(paths), slug)
        if slices is None:
            _bump(skipped, "no-start-call")
            continue
        record, scenario = _record_and_scenario(root, slug, data, slices["own"])
        scored = judge.score_record(record, scenario)
        lead_in, _ = _record_and_scenario(root, slug, data, slices["lead_in"])
        for name, behaviour in judge.REAL_SESSION_LEAD_IN.items():
            scored[name] = behaviour(lead_in, scenario)
        for name, reason in judge.REAL_SESSION_NOT_JUDGED.items():
            if name in scored:
                scored[name] = {"status": "undecided", "reason": reason}
        for name, result in scored.items():
            if name not in rows or not isinstance(result, dict):
                continue
            status = result.get("status")
            rows[name]["sessions"] += 1
            rows[name][status if status in ("pass", "fail") else "undecided"] += 1
            if status == "fail":
                failures.append({"issue": slug, "behaviour": name,
                                 "call": result.get("call")})
    for name, row in rows.items():
        decided = row["pass"] + row["fail"]
        row["rate"] = round(row["pass"] / decided, 3) if decided else None
        row["interval"] = ([round(v, 3) for v in judge._wilson_interval(row["pass"], decided)]
                           if decided else None)
        if name in judge.REAL_SESSION_NOT_JUDGED:
            row["not_judged"] = judge.REAL_SESSION_NOT_JUDGED[name]
    unmatched = 0 if only else len(_project_transcripts(root, days) - named)
    return {"days": days, "behaviours": rows, "failures": failures,
            "unmatched": unmatched, "skipped": skipped}


def propose_lessons(result):
    """A behaviour failing in `LESSON_AFTER` distinct issues becomes one
    pending lesson. The rule text names only the behaviour, never a count,
    so a later run with more failures finds it already pending or declined."""
    from compass_pkg.lessons import propose_pending
    judge = _judge()
    advice = getattr(judge, "REAL_SESSION_ADVICE", {}) if judge else {}
    by_behaviour = {}
    for f in result.get("failures") or []:
        by_behaviour.setdefault(f["behaviour"], set()).add(f["issue"])
    added = []
    for name, issues in sorted(by_behaviour.items()):
        if len(issues) < LESSON_AFTER:
            continue
        rule = f"{advice.get(name, name)} (from the compliance report: {name})."
        entry = propose_pending(rule, "compliance", issues)
        if entry:
            added.append(entry)
    return added


def cmd_retro_compliance(args):
    root = os.path.dirname(find_compass_dir())
    days = getattr(args, "days", None)
    result = report(root, getattr(args, "issue_slug", None), 14 if days is None else days)
    if "error" in result:
        print(f"compass retro --compliance: {result['error']}.")
        return 0
    added = propose_lessons(result)
    if getattr(args, "_mode", None) == "json":
        # Structured on purpose: the output layer otherwise wraps a report's
        # lines as unstructured text.
        from compass_pkg.terminal import mark_handled
        mark_handled()
        print(json.dumps({**result, "lessons_proposed": [e["id"] for e in added]},
                         indent=2))
        return 0
    rows = result["behaviours"]
    scored = max((r["sessions"] for r in rows.values()), default=0)
    print(f"compass retro --compliance: {scored} issue session(s) over "
          f"{result['days']} days; {result['unmatched']} unmatched transcript(s)")
    for name, r in rows.items():
        if "not_judged" in r:
            print(f"  {name}: not judged from a transcript ({r['not_judged']})")
            continue
        rate = "-" if r["rate"] is None else f"{r['rate']:.0%}"
        interval = ("" if r["interval"] is None
                    else f" (95% {r['interval'][0]:.0%}-{r['interval'][1]:.0%})")
        print(f"  {name}: {r['pass']} pass, {r['fail']} fail, {r['undecided']} "
              f"undecided; {rate}{interval}")
    for f in result["failures"]:
        call = "" if f["call"] is None else f" at call {f['call']}"
        print(f"  failed: {f['issue']}{call}: {f['behaviour']}")
    for reason, n in sorted(result["skipped"].items()):
        print(f"  not scored: {n} issue(s), {reason}")
    for e in added:
        print(f"  proposed lesson {e['id']} (accept with `compass lesson accept`)")
    return 0
