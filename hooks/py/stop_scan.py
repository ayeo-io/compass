# Run by hooks/stop.sh: scan each issue for end-of-session warnings.
# The hook passes its arguments on the command line; standard input is closed.

import os
import re
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
import yaml
from compass_pkg import parse_cache, status_words
from compass_pkg.core import artifact_path

work_dir, signals = sys.argv[1], sys.argv[2]

# Saves no manifest. It stores new parse entries in the cache but never
# calls finish(): pruning the cache is the board's job, and the hook must not
# delete entries the board uses.
cache = parse_cache.for_work_root(work_dir)


def emit(kind, slug, text):
    print("%s\t[%s] %s" % (kind, slug, text))


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def any_line(pattern, path):
    """grep -qiE: does any one line of the file match?"""
    text = read_text(path)
    return text is not None and any(
        pattern.search(line) for line in text.splitlines())


def load_phrases():
    try:
        with open(signals, encoding="utf-8") as fh:
            return [str(p) for p in
                    (yaml.safe_load(fh) or {}).get("scope_bloat_phrases") or []
                    if p]
    except Exception:                                       # noqa: BLE001
        return []


# The separator between "FAIL" and the phrase after it is matched as "one or
# more non-alphanumeric characters" rather than a literal dash. Reports
# written before this repo swapped em dashes for hyphens are still on disk in
# projects using Compass, and both spellings must be recognised.
FAILING = re.compile(
    r"Overall:.*\bRED\b|Overall:.*FAIL|FAIL[^0-9A-Za-z]+(issue|task) does not advance",  # vocabulary-scan: allow - matches the retired wording in older reports too
    re.IGNORECASE)
PASSING = re.compile(r"Overall:.*PASS", re.IGNORECASE)
REPRODUCTION = re.compile(r"reproduc|regression|defect|incident", re.IGNORECASE)
LINE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
PHRASES = load_phrases() if signals else []


def gate_state(task_dir, slug, task):
    # ASKED, NOT GUESSED. Each of these three may sit beside the manifest or
    # under `docs/compass/<created>-<slug>/`, and only the issue's artifact
    # registry knows which. The resolver - the same one `compass check` uses -
    # falls back to the retired filename and to the flat filename, so older
    # archives still resolve. A kind with no document resolves to where it
    # WOULD be, so the isfile tests below read it as "nothing written".
    try:
        approach_doc = artifact_path(task_dir, "delivery-approach.md")
        spec = artifact_path(task_dir, "acceptance-criteria.md")
        vreport = artifact_path(task_dir, "verification-report.md")
    except Exception:                                       # noqa: BLE001
        approach_doc = spec = vreport = ""

    # 1. the delivery-approach record missing on in-progress work. A folder
    # with nothing in it may be an empty scaffold; anything else in it means
    # work started without the assess stage.
    if not os.path.isfile(approach_doc):
        try:
            has_artifacts = bool(os.listdir(task_dir))
        except OSError:
            has_artifacts = False
        if has_artifacts:
            emit("W", slug, "the delivery-approach record is MISSING but the issue "
                 "has artifacts - work started without an assessment. Run /compass:assess.")
        return

    # 2. a stage whose gate is not cleared. An unresolved red: implementation
    # never closed.
    if os.path.isfile(os.path.join(task_dir, ".red")):
        emit("W", slug, ".red marker still present - a failing test is on record "
             "and was never paid off green. implementation is mid-gate.")

    # The verify stage entered but not cleared.
    if os.path.isfile(vreport):
        if any_line(FAILING, vreport):
            emit("W", slug, "verification-report.md records a FAILING gate decision "
                 "- test-and-review did not pass. The issue is mid-gate.")
        elif not any_line(PASSING, vreport):
            emit("W", slug, "verification-report.md exists but its gate decision is "
                 "blank - test-and-review was entered and not completed.")

    # 3. a hotfix with an outstanding follow-up. Both facts come from
    # manifest.yml: the template can rename a heading in the prose record
    # without any check failing, and a grep for the old heading then stops
    # matching with no error.
    if str(task.get("delivery_approach") or "") != "hotfix":
        return
    outstanding = [
        f for f in (task.get("follow_ups") or [])
        if isinstance(f, dict) and str(f.get("status", "")) in ("outstanding", "owed")
    ]
    if outstanding:
        emit("W", slug, "HOTFIX with %d OUTSTANDING FOLLOW-UP(S) recorded in "
             "manifest.yml. The issue is not closeable until they are resolved."
             % len(outstanding))
    # The reproduction test must have been promoted into a real scenario.
    if os.path.isfile(spec):
        if not any_line(REPRODUCTION, spec):
            emit("W", slug, "HOTFIX follow-up incomplete - acceptance-criteria.md "
                 "has no promoted reproduction scenario yet.")
    else:
        emit("W", slug, "HOTFIX follow-up incomplete - acceptance-criteria.md does "
             "not exist; the reproduction test was never promoted to a scenario.")


def scope_bloat(task_dir, slug, task):
    # 4. Each phrase is anchored at the start of the line, after an optional
    # YYYY-MM-DD[: ] date, the way cli/compass_pkg/calibration.py anchors it.
    # A line that starts with whitespace is quoted or indented context and
    # does not fire (TRC-X3).
    devlog = os.path.join(task_dir, "devlog.md")
    if not PHRASES or not os.path.isfile(devlog) \
            or not os.path.isfile(os.path.join(task_dir, "manifest.yml")):
        return
    text = read_text(devlog)
    if text is None:
        return
    lines = [line for line in text.splitlines() if line and not line[0].isspace()]

    # A reassessment dated on or after the matching line suppresses the
    # reminder: it was already filed (TRC-C3). An `unchanged` entry counts: a
    # reassess given a reason after the bloat line is an answer to it.
    try:
        entries = task.get("reassessments") or task.get("reframes") or []  # vocabulary-scan: allow - reads the key an archived pre-v2 manifest holds
        dates = [r.get("date", "") for r in entries if r.get("date")]
        latest = str(max(dates)) if dates else ""
    except Exception:                                       # noqa: BLE001
        latest = ""

    for phrase in PHRASES:
        pattern = re.compile(r"^(?:\d{4}-\d{2}-\d{2}[: ]+)?" + re.escape(phrase))
        matched = next((line for line in lines if pattern.match(line)), None)
        if matched is None:
            continue
        found = LINE_DATE.match(matched)
        line_date = found.group(0) if found else ""
        # A reassessment exists and the line has no date to compare: suppress.
        if latest and (not line_date or latest >= line_date):
            continue
        emit("N", slug, 'Scope-bloat signal detected in devlog: "%s"' % matched)


for slug in sorted(os.listdir(work_dir)):
    task_dir = os.path.join(work_dir, slug)
    if slug.startswith(".") or not os.path.isdir(task_dir):
        continue
    try:
        task = cache.load_yaml(os.path.join(task_dir, "manifest.yml"))
    except Exception:                                       # noqa: BLE001
        task = {}
    if not isinstance(task, dict):
        task = {}
    if status_words.is_closed(task):
        continue
    # Every issue shares this one process, so an error on one issue skips
    # that issue only. Uncaught, it would end the scan and hide the warnings
    # for every issue after it.
    try:
        gate_state(task_dir, slug, task)
        scope_bloat(task_dir, slug, task)
    except Exception:                                       # noqa: BLE001
        continue
