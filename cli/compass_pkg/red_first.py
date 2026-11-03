#!/usr/bin/env python3
# =============================================================================
# compass - a failure observed first
# =============================================================================
# A green record shows the suite passes; it does not show that a test ever
# failed. `suite-passed`, the check behind "tested before it lands"
# (guardrail `G1`), accepted any green, and an unbound green needs no red. So
# an issue could pass it having never seen a failure: 9 of 110 archived
# issues did, as the issue `unbound-green-needs-no-red` measured. This module
# holds the two extra conditions `suite-passed` now applies: a red on the
# issue, and on a newer issue a red for each scenario before its first green
# (ADR-088).
#
# Kept apart from checks.py, which is near its line cap.
#
# It also gives the one verdict on an issue's red records that the pre-tool
# hook and `suite-passed` both use, so the two cannot disagree about what
# counts as a red.
#
# DEPENDENCY: standard library (datetime, hashlib, json, os, stat) and
# compass_pkg.core for the config reader. tdd.py imports from here, so this
# module must not import tdd.py.
# =============================================================================
"""Does an issue that declares scenarios show a failure observed first?"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import stat

from compass_pkg import project_settings
from compass_pkg.core import CompassError, find_upwards, load_yaml

#: Issues created on or after this date, or with evidence recorded on or
#: after it, must show a failure first. Issues created and worked before it
#: keep the result they had: their records say what was required when they
#: were written, and failing them now would rewrite that. A manifest with no
#: `created:` predates the field and counts as before, unless its evidence
#: is dated since.
RED_REQUIRED_FROM = datetime.date(2026, 9, 24)

#: The kinds `compass acceptance start` accepts, for work with no natural red.
#: Defined here, not in tdd.py, so the check and the verb read one list.
ACCEPTANCE_KINDS = ("validation", "refactor")


def _load(path):
    """A record's payload, or {} for anything that is not a JSON object in a
    regular file. A FIFO would block the read, and a symlink could stand
    another issue's record in for this one's."""
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return {}
    if not stat.S_ISREG(mode):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


#: The public name for other modules; `_load` stays for this module's own use.
load_record = _load

#: An outer-loop record's file name ends in this before `.json` (ADR-082), so an
#: inner-loop record with the same binding does not replace it.
OUTER = ".outer"


def record_stem(kind, scenario=None, loop=None):
    """The file name, without `.json`, of a `red` or `green` record: the binding
    and the loop decide it. `red-A.outer` is an outer-loop red bound to A."""
    stem = kind + ("-" + scenario.replace("/", "_") if scenario else "")
    return stem + (OUTER if loop == "outer" else "")


def record_paths(task_dir, kind, scenario=None):
    """The inner-loop and outer-loop files of one binding, in that order."""
    return [os.path.join(task_dir, "evidence", record_stem(kind, scenario, loop) + ".json")
            for loop in ("inner", "outer")]


def is_record_name(kind, name):
    """Is `name` a `kind` record file, of either loop, bound or not?"""
    return name in (kind + ".json", kind + OUTER + ".json") \
        or (name.startswith(kind + "-") and name.endswith(".json"))


def _is_failed_run(record):
    """True only for what `compass tdd-red` writes: `passed` false and an
    integer exit code that is not 0. Either field alone is not enough - a
    green record with `passed` flipped still says exit code 0."""
    code = record.get("exit_code")
    return (record.get("passed") is False and isinstance(code, int)
            and not isinstance(code, bool) and code != 0)


def signed_since(task_dir, compass_dir=None):
    """The project's `records_signed_since` date, or None when it declares none.

    From that date on, a red record must carry the identity `compass tdd-red`
    stamps on it. A project that declares nothing keeps the older allowance
    for unstamped records.

    `compass_dir` names the project's `.compass/` when the caller has already
    resolved it, as the pre-tool hook has; the issue directory's own ancestors
    are the fallback.

    Returns None - no cutoff - only when the key is absent or empty, or when
    there is no config file. Anything else that cannot be read as a date,
    including a config file that does not parse, counts as a cutoff in the far
    past: a broken config must not turn the cutoff off without a word.
    """
    if compass_dir is None:
        root = find_upwards(task_dir, ".compass")
        if not root:
            return None
        compass_dir = os.path.join(root, ".compass")
    project_root = os.path.dirname(os.path.normpath(compass_dir))
    if project_settings.state_source(project_root) is None:
        return None
    try:
        config = project_settings.state(project_root)
    except (CompassError, OSError, ValueError):
        return datetime.date.min
    value = config.get("records_signed_since")
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return datetime.date.min


def content_digest(payload):
    """A stable digest over a record's content, excluding the digest itself.
    `compass tdd-red` stamps records with it, and `red_verdict` checks them
    with it, so writer and reader cannot drift apart."""
    body = {k: v for k, v in payload.items() if k != "content_digest"}
    encoded = json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _written_before(record, cutoff):
    """Does the record's own timestamp put it before the cutoff? A record
    with no readable timestamp is not."""
    try:
        written = datetime.date.fromisoformat(str(record.get("timestamp"))[:10])
    except ValueError:
        return False
    return written < cutoff


def red_verdict(task_dir, compass_dir=None):
    """The verdict on an issue's red records, as one word:

      ok               a failed run is on record and counts
      no-record        no red record file at all
      unsigned         failed runs are on record, but each lacks the identity
                       this project has required since `records_signed_since`
      no-valid-record  anything else: no failed run, or a stamped record
                       edited after it was written

    `compass tdd-red` writes `evidence/red.json` unbound and
    `evidence/red-<scenario>.json` bound, with `.outer` before `.json` for the
    outer loop (`record_stem`). A red record is not registered in `evidence:`,
    so this reads the directory.
    """
    evidence = os.path.join(task_dir, "evidence")
    if os.path.islink(evidence):
        return "no-valid-record"
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return "no-record"
    names = [n for n in names if is_record_name("red", n)]
    if not names:
        return "no-record"
    cutoff = signed_since(task_dir, compass_dir)
    unsigned = False
    for name in names:
        verdict = _record_verdict(_load(os.path.join(evidence, name)), cutoff)
        if verdict == "ok":
            return "ok"
        unsigned = unsigned or verdict == "unsigned"
    return "unsigned" if unsigned else "no-valid-record"


def _record_verdict(record, cutoff):
    """`ok`, `unsigned` or None for one red record, under the signing cutoff
    `cutoff` (`signed_since`). `red_verdict` judges the issue with it, and the
    rule for each scenario judges each scenario's records with it, so the two
    cannot disagree about what counts as a red."""
    if not _is_failed_run(record):
        return None
    if record.get("content_digest"):
        return "ok" if content_digest(record) == record["content_digest"] else None
    # Written before records carried an identity. Accepted unless the
    # project has declared a date from which every record must carry one.
    if cutoff is None or _written_before(record, cutoff):
        return "ok"
    return "unsigned"


def verdict_line(task_dir, compass_dir=None):
    """The verdict and the cutoff it applied, on one line, for the pre-tool
    hook: `unsigned 2026-09-24`. The hook prints the date from here rather
    than parsing the config itself, so the refusal names the date the reader
    actually used."""
    verdict = red_verdict(task_dir, compass_dir)
    if verdict != "unsigned":
        return verdict
    cutoff = signed_since(task_dir, compass_dir)
    shown = "an unreadable value" if cutoff == datetime.date.min else cutoff.isoformat()
    return "unsigned " + shown


def has_red(task_dir):
    """Is a failed run on record that counts? See `red_verdict`."""
    return red_verdict(task_dir) == "ok"


def _test_runs(task, task_dir):
    """`(scenario, entry, record)` for each `test-run` entry of the registry whose
    path is inside the issue directory. `scenario` is the entry's binding, or the
    record's when the entry names none, or None when unbound."""
    root = os.path.realpath(task_dir)
    for entry in task.get("evidence") or []:
        if not isinstance(entry, dict) or entry.get("type") != "test-run":
            continue
        full = os.path.realpath(os.path.join(task_dir, entry.get("path") or ""))
        if os.path.commonpath([root, full]) != root:
            continue
        record = _load(full)
        scenario = entry.get("scenario") or record.get("scenario")
        yield (scenario if isinstance(scenario, str) and scenario else None), entry, record


def _first_green(task, task_dir):
    """The earliest timestamp among the issue's green records that are not
    acceptance records, as an ISO string, or None."""
    stamps = [record["timestamp"] for _, _, record in _test_runs(task, task_dir)
              if record.get("kind") not in ACCEPTANCE_KINDS
              and isinstance(record.get("timestamp"), str)]
    return min(stamps) if stamps else None


def _in_time(record, first_green):
    """Was an acceptance declared before the issue's first green? A record with
    no `declared_at` was written before records carried one, and counts as it
    did then."""
    declared = record.get("declared_at")
    return not isinstance(declared, str) or first_green is None or declared < first_green


def _acceptance(task, task_dir):
    """Is an acceptance record among the issue's test-run evidence, and was
    it declared in time? Returns (counts, late) where `late` names a record
    declared after the first green, for the failure message.

    Only a path inside the issue directory counts."""
    first_green = _first_green(task, task_dir)
    late = None
    for _, entry, record in _test_runs(task, task_dir):
        if record.get("kind") not in ACCEPTANCE_KINDS:
            continue
        if _in_time(record, first_green):
            return True, None
        late = (entry.get("path"), record.get("declared_at"), first_green)
    return False, late


def _has_acceptance(task, task_dir):
    return _acceptance(task, task_dir)[0]


def _rule_applies(created, cutoff=RED_REQUIRED_FROM):
    """Was the issue created on or after the cutoff? A missing or blank
    `created:` is the one exemption. A value that is present but not an ISO
    date is not trusted to mean "old", so the rule applies to it."""
    if isinstance(created, datetime.datetime):
        created = created.date()
    if isinstance(created, datetime.date):
        return created >= cutoff
    text = "" if created is None else str(created).strip()
    if not text:
        return False
    try:
        return datetime.date.fromisoformat(text[:10]) >= cutoff
    except ValueError:
        return True


def _dated_work(task_dir):
    """`[(relative path, date)]` of each evidence record with a readable
    timestamp, in name order. Symlinks and anything that is not a JSON object
    are skipped by `_load`, as for red records."""
    evidence = os.path.join(task_dir, "evidence")
    if os.path.islink(evidence):
        return []
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return []
    out = []
    for name in names:
        if not name.endswith(".json"):
            continue
        stamp = _load(os.path.join(evidence, name)).get("timestamp")
        try:
            out.append(("evidence/" + name, datetime.date.fromisoformat(str(stamp)[:10])))
        except ValueError:
            continue
    return out


def _work_dated_since(task_dir):
    """The first evidence record dated on or after the cutoff, as
    (relative path, date), or None.

    `created:` can be edited; the evidence the CLI writes carries the time of
    the run. So work recorded since the cutoff brings an issue under the rule
    whatever `created:` says.
    """
    return next(((path, day) for path, day in _dated_work(task_dir)
                 if day >= RED_REQUIRED_FROM), None)


def missing_first_failure(task, task_dir):
    """The failure message when the rule applies and is not met, else None.

    The rule applies to an issue created on or after the cutoff, or with any
    evidence record dated on or after it."""
    if not task.get("scenarios"):
        return None
    applies, started = _per_scenario_scope(task, task_dir)
    if applies:
        faults = _faults(scenario_reds(task, task_dir))
        if faults:
            return _per_scenario_failure(
                faults, started, _rule_applies(task.get("created"), RED_PER_SCENARIO_FROM))
    dated_by = None
    if not _rule_applies(task.get("created")):
        dated_by = _work_dated_since(task_dir)
        if dated_by is None:
            return None
    if has_red(task_dir):
        return None
    counts, late = _acceptance(task, task_dir)
    if counts:
        return None
    why = ""
    if late:
        why += (" The acceptance in %s was declared at %s, after the first "
                "green at %s, so it does not stand in for a red."
                % late)
    if dated_by:
        why = (" The rule applies although `created:` is earlier, because "
               "%s is dated %s." % (dated_by[0], dated_by[1].isoformat()))
    return ("the greens on record show the suite passes, but no red is on "
            "record for this issue, so nothing shows a test failed first. Run "
            "`compass tdd-red -- <test command>` on a failing test. For work "
            "with no natural red - config, docs, a behavior-preserving "
            "refactor - declare it before the change with `compass "
            "acceptance start --kind validation|refactor -- <command>` and "
            "finish with `compass acceptance record`." + why)


# --- a red for each scenario -------------------------------------------------------
#
# One red on the issue showed that some test failed first, not which. On an
# issue under the per-scenario rule, each scenario that needs a test must have
# a red bound to it, of either loop, dated no later than the scenario's first
# green (ADR-088). The rule adds to the one above: an
# issue it covers must still pass that one too.

#: Issues created on or after this date get the per-scenario rule. An issue
#: created earlier keeps the rule above, with a notice of what it lacks under
#: this one, unless all of its work is recorded on or after the date.
RED_PER_SCENARIO_FROM = datetime.date(2026, 11, 3)


def _moment(value):
    """A record's timestamp as a time with a zone, or None. A time with no
    zone is read as UTC."""
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def _red_moments(task_dir, scenario, cutoff):
    """The timestamp of each red bound to `scenario` (None: unbound) that counts,
    from the files of both loops (`record_paths`). A red with no readable
    timestamp gives None."""
    if os.path.islink(os.path.join(task_dir, "evidence")):
        return []
    out = []
    for path in record_paths(task_dir, "red", scenario):
        record = _load(path)
        if _record_verdict(record, cutoff) == "ok":
            out.append(_moment(record.get("timestamp")))
    return out


def first_time(record):
    """The earliest time a green record stands for, as a time with a zone, or
    None. `compass tdd-green` replaces the record of its binding and loop on
    each run and carries the time of the first run forward in
    `first_timestamp` (ADR-088). A record written before that field has only
    `timestamp`."""
    times = [m for m in (_moment(record.get("first_timestamp")),
                         _moment(record.get("timestamp"))) if m is not None]
    return min(times) if times else None


def carried_first(prior, timestamp):
    """The `first_timestamp` a new green record carries: the earliest of the
    record it replaces and its own `timestamp`. `prior` is the replaced record,
    or {} when there is none or it is not a green. The value can only move
    earlier, so an edited `prior` can make the check stricter, never looser."""
    held = prior.get("first_timestamp") if _moment(prior.get("first_timestamp")) \
        else prior.get("timestamp")
    if _is_green(prior) and _moment(held) and _moment(held) < _moment(timestamp):
        return held
    return timestamp


def _is_green(record):
    code = record.get("exit_code")
    return code == 0 and isinstance(code, int) and not isinstance(code, bool) \
        and record.get("passed") is not False and record.get("kind") not in ACCEPTANCE_KINDS


def scenario_reds(task, task_dir):
    """How each scenario of the issue stands under the per-scenario rule, as a
    dict of lists of scenario ids:

      met       a red that counts, dated no later than the first green
      accepted  closed by an acceptance declared before a green: one bound to
                the scenario, declared before that scenario's first green, or
                one bound to none, declared before the issue's first green
      narrative `verifiable: narrative`, cleared by its written body
      no_red    no red that counts
      late      `(id, red, green)`: every red that counts is after the first
                green, or has no readable time

    A scenario's first green is the earliest of the greens bound to it and the
    unbound greens, each read by `first_time`. An acceptance with no
    `declared_at` was not shown to be declared first, so it closes nothing. An
    unbound red counts only when one scenario needs a red. A scenario with no
    green to compare needs only a red.
    """
    out = {"met": [], "accepted": [], "narrative": [], "no_red": [], "late": []}
    needing = []
    for item in task.get("scenarios") or []:
        sid = item.get("id") if isinstance(item, dict) else None
        if isinstance(sid, str) and sid:
            (out["narrative"] if item.get("verifiable") == "narrative" else needing).append(sid)
    greens, acceptances = {}, []
    for scenario, _, record in _test_runs(task, task_dir):
        if record.get("kind") in ACCEPTANCE_KINDS:
            acceptances.append((scenario, _moment(record.get("declared_at"))))
            continue
        moment = first_time(record)
        if moment is not None and (scenario not in greens or moment < greens[scenario]):
            greens[scenario] = moment

    def first_green(sid):
        held = [greens[k] for k in ((sid, None) if sid else greens) if k in greens]
        return min(held) if held else None

    accepted = {scenario for scenario, declared in acceptances
                if declared is not None and (first_green(scenario) is None
                                             or declared < first_green(scenario))}
    cutoff = signed_since(task_dir)
    unbound = _red_moments(task_dir, None, cutoff) if len(needing) == 1 else []
    for sid in needing:
        if sid in accepted or None in accepted:
            out["accepted"].append(sid)
            continue
        reds = _red_moments(task_dir, sid, cutoff) + unbound
        green = first_green(sid)
        dated = [m for m in reds if m is not None]
        if not reds:
            out["no_red"].append(sid)
        elif green is None or (dated and min(dated) <= green):
            out["met"].append(sid)
        else:
            out["late"].append((sid, min(dated) if dated else None, green))
    return out


def _signed(record, cutoff):
    """Does a record pass the identity test `_record_verdict` applies to a red?"""
    if record.get("content_digest"):
        return content_digest(record) == record["content_digest"]
    return cutoff is None or _written_before(record, cutoff)


def _cli_work(task_dir):
    """`[(relative path, date or None)]` of each record the CLI writes: a red
    that counts, a green, or an acceptance, each passing the identity test. A
    note or any other file with a `timestamp` is not one, so it cannot hold an
    issue on the older rule."""
    evidence = os.path.join(task_dir, "evidence")
    if os.path.islink(evidence):
        return []
    try:
        names = sorted(os.listdir(evidence))
    except OSError:
        return []
    cutoff = signed_since(task_dir)
    out = []
    for name in names:
        record = _load(os.path.join(evidence, name))
        if is_record_name("red", name):
            ours = _record_verdict(record, cutoff) == "ok"
        elif is_record_name("green", name):
            ours = _is_green(record) and _signed(record, cutoff)
        elif is_record_name("acceptance", name):
            ours = record.get("kind") in ACCEPTANCE_KINDS and _signed(record, cutoff)
        else:
            ours = False
        if ours:
            stamp = record.get("timestamp") or record.get("declared_at")
            try:
                day = datetime.date.fromisoformat(str(stamp)[:10])
            except ValueError:
                day = None
            out.append(("evidence/" + name, day))
    return out


def _per_scenario_scope(task, task_dir):
    """`(applies, started)`: does the per-scenario rule apply? It does to an
    issue created on or after `RED_PER_SCENARIO_FROM`. An issue whose
    `created:` is earlier or missing keeps the older rule only when a record
    the CLI writes (`_cli_work`) is dated before the date, or has no date and
    so predates dated records: it was in flight under the older rule.
    Otherwise the rule applies, since `created:` can be edited, and `started`
    names the earliest such record, or is None when there is none."""
    if _rule_applies(task.get("created"), RED_PER_SCENARIO_FROM):
        return True, None
    work = _cli_work(task_dir)
    if any(day is None or day < RED_PER_SCENARIO_FROM for _, day in work):
        return False, None
    return True, (min(work, key=lambda item: item[1]) if work else None)


def _faults(found):
    """What the per-scenario rule finds missing, as text, or "" when nothing is."""
    parts = []
    if found["no_red"]:
        parts.append("no red: " + ", ".join(found["no_red"]))
    if found["late"]:
        parts.append("red after its first green: " + "; ".join(
            f"{sid} (red at {red.isoformat() if red else 'no readable time'}, "
            f"first green at {green.isoformat()})" for sid, red, green in found["late"]))
    return ". ".join(parts)


def _per_scenario_failure(faults, started, dated):
    why = ""
    if not dated:
        why = (" The rule applies although `created:` is earlier or missing, "
               "because no record the CLI writes is dated before %s."
               % RED_PER_SCENARIO_FROM.isoformat())
    if started:
        why += " The earliest, %s, is dated %s." % (started[0], started[1].isoformat())
    return ("each scenario needs a red recorded no later than its first green, "
            "so a reader can see a test failed for it before the code. Missing - "
            + faults + ". Run `compass tdd-red --scenario <id> -- <test command>` "
            "for each scenario named, before its green; a red of either loop "
            "counts. For a scenario with no natural red, declare an acceptance "
            "before the change with `compass acceptance start --kind "
            "validation|refactor -- <command>` and close it with `compass "
            "acceptance record --scenario <id>`." + why)


def scenario_notice(task, task_dir):
    """Text for the pass detail of `suite-passed`, or "". It starts with the full
    stop that ends the sentence before it. Under the per-scenario
    rule it says how each scenario was met. An issue the rule does not cover
    keeps its result; when it lacks something the rule asks for, the text is a
    notice that names it."""
    if not task.get("scenarios"):
        return ""
    found = scenario_reds(task, task_dir)
    if _per_scenario_scope(task, task_dir)[0]:
        said = [(label, found[key]) for key, label in (
            ("met", "red before its first green"), ("accepted", "closed by an acceptance"),
            ("narrative", "narrative")) if found[key]]
        if not said:
            return ""
        return (". A red for each scenario - "
                + "; ".join(f"{label}: {', '.join(ids)}" for label, ids in said) + ".")
    faults = _faults(found)
    if not faults:
        return ""
    return (". Notice: from %s each scenario needs a red no later than its first "
            "green. This issue was created and worked before that, so it keeps "
            "the rule it was created under and does not fail on it. Under the "
            "new rule it lacks - %s." % (RED_PER_SCENARIO_FROM.isoformat(), faults))
