#!/usr/bin/env bash
# =============================================================================
# Compass hook: stop.sh  -  END-OF-SESSION GATE-STATE WARNER
# =============================================================================
# Runs as a Claude Code Stop hook, when a session ends. It does not block - a
# session is allowed to end. It prints a warning for each unfinished issue, so
# the next session or a person does not have to find it.
#
# WHAT IT CHECKS, per issue under .compass/work/
#   1. the delivery-approach record missing on in-progress work
#        => an issue directory exists but has no delivery-approach.md. Work
#           with no delivery-approach record has no computed process, so the
#           hook warns.
#   2. a stage whose gate is not cleared
#        => a still-present .red marker means implementation is unfinished (a
#           failing test is on record and was never taken green). The verify stage
#           cannot have passed cleanly.
#        => artifacts present out of order, or a verification-report.md whose
#           gate decision is RED / blank, mean the verify stage was entered
#           and not cleared.
#   3. a hotfix with an outstanding follow-up
#        => the delivery-approach record names a hotfix and its outstanding
#           follow-ups section still has an unchecked item, or
#           acceptance-criteria.md still lacks the promoted reproduction
#           scenario.
#   4. a scope-bloat phrase in the devlog with no re-assessment after it.
#
# A closed issue is not checked: its warnings are about work that is over,
# and on a project with hundreds of them they hid the open issues' warnings.
# All issues are read in ONE Python process, through the parse cache that
# the board uses (ADR-049). The hook runs at the end of every turn, and
# starting Python for each issue made a 515-issue project wait 513 seconds
# (ayeo-io/compass-delivery-record#218).
#
# This mirrors what /compass:status reports, but fires automatically at
# session end, so an unfinished issue is reported at every session end.
#
# WIRING  (.claude/settings.json)
#   {
#     "hooks": {
#       "Stop": [
#         { "hooks": [ { "type": "command",
#                        "command": "$CLAUDE_PROJECT_DIR/hooks/stop.sh" } ] }
#       ]
#     }
#   }
#   `scripts/install.sh` registers this for you.
#
# I/O CONTRACT
#   stdin : JSON session-stop payload. Only its string `cwd` is read, to find
#           the project of a session isolated to a git worktree; the rest is
#           disk state.
#   stdout: {"systemMessage": ...} when an approval request of the session's
#           issue has not been shown yet (below). Claude Code shows it to the
#           person under the reply; the model does not see it (measured on
#           Claude Code 2.1.300, ADR-068).
#   exit  : always 0. Warnings go to stderr. This hook never blocks a stop.
#
# APPROVAL REQUESTS (ADR-068 decision 1)
#   Each pending request of the session's issue (COMPASS_ISSUE, else the
#   pointer) that has not been shown is shown once, in Compass's words, and
#   stamped with the time and the digest shown. The prompt hook records only
#   a request whose digest still equals the one shown, so an approval binds to
#   what Compass showed, not to what the agent said. A display that cannot be
#   built is left out: the prompt hook still blocks an unshown request.
# =============================================================================

set -euo pipefail

# shellcheck source=../scripts/lib/compass-python.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/scripts/lib/compass-python.sh"

# Claude Code passes the session's folder as `cwd`. In a session isolated to a
# git worktree, CLAUDE_PROJECT_DIR is the folder the session started in, not the
# worktree that holds the issue, so `cwd` is the second place to look.
STOP_INPUT="$(cat || true)"

# Under `set -e`, a failing `compass_python` would end the script with exit
# 127 on a machine without python3, so check first and exit 0.
#
# Note the asymmetry with hooks/pre-tool.sh, which is deliberate: a hook that
# cannot CHECK must not permit, so it refuses; a warner that cannot READ has
# nothing to say, so it exits 0. Same missing interpreter, opposite correct
# answers.
if ! compass_python -c "pass" >/dev/null 2>&1; then
  echo "Compass: python3 is not available, so the end-of-session check did not run." >&2
  exit 0
fi

# Find the project with the same ancestor walk as hooks/pre-tool.sh, so the
# check runs from any subdirectory.
INVOKED_FROM="$(pwd)"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
  PROJECT_DIR=""
  _search="$INVOKED_FROM"
  while [ -n "$_search" ]; do
    [ -d "$_search/.compass" ] && { PROJECT_DIR="$_search"; break; }
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
  if [ -z "$PROJECT_DIR" ]; then
    # A repository that never opted into Compass hears nothing. This hook is
    # installed at user scope, so it runs at the end of every session on the
    # machine. Any output here would make Compass appear in unrelated work.
    exit 0
  fi
fi

# The project root of the hook input's `cwd`, by the same ancestor walk. A
# missing, malformed or non-string `cwd` leaves it empty and changes nothing.
CWD_ROOT=""
_cwd="$(printf '%s' "$STOP_INPUT" | compass_python -c '
import json, sys
try:
    cwd = json.load(sys.stdin).get("cwd")
except Exception:
    cwd = None
if isinstance(cwd, str) and cwd.startswith("/") and "\n" not in cwd:
    print(cwd)
' 2>/dev/null || true)"
if [ -n "$_cwd" ]; then
  _search="$_cwd"
  while [ -n "$_search" ]; do
    [ -d "$_search/.compass" ] && { CWD_ROOT="$_search"; break; }
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
fi

COMPASS_DIR="$PROJECT_DIR/.compass"
WORK_DIR="$COMPASS_DIR/work"
if [ ! -d "$WORK_DIR" ]; then
  # CLAUDE_PROJECT_DIR holds no work folder: use the project of `cwd` instead.
  if [ -n "$CWD_ROOT" ] && [ -d "$CWD_ROOT/.compass/work" ]; then
    PROJECT_DIR="$CWD_ROOT"
    COMPASS_DIR="$PROJECT_DIR/.compass"
    WORK_DIR="$COMPASS_DIR/work"
  else
    exit 0
  fi
fi

WARNINGS=()

# --- 0. the current-task pointer should resolve -----------------------------
# The hooks and the CLI rely on .compass/current-task. A dangling pointer is a
# quiet way for the wrong issue to be acted on next session.
POINTER="$COMPASS_DIR/current-task"
# With COMPASS_ISSUE set, the session works on that issue, so that is the
# name that must resolve; the person's pointer is theirs to keep.
if [ -n "${COMPASS_ISSUE:-}" ]; then
  if [ ! -d "$WORK_DIR/$COMPASS_ISSUE" ] || case "$COMPASS_ISSUE" in */*|.|..) true ;; *) false ;; esac; then
    WARNINGS+=("COMPASS_ISSUE names '$COMPASS_ISSUE' but no such issue directory exists - set it to a real issue slug, or unset it to use .compass/current-task.")
  fi
elif [ -f "$POINTER" ]; then
  PSLUG="$(tr -d '[:space:]' < "$POINTER" 2>/dev/null || true)"
  if [ -n "$PSLUG" ] && [ ! -d "$WORK_DIR/$PSLUG" ]; then
    WARNINGS+=(".compass/current-task points at '$PSLUG' but no such issue directory exists - fix or clear the pointer.")
  fi
fi

# --- 1-4. every open issue, in one Python process ---------------------------
# The scope-bloat phrases come from governance/signals.yml at runtime and are
# never hardcoded: the project's copy first, then the framework's.
SIGNALS=""
if [ -f "$PROJECT_DIR/governance/signals.yml" ]; then
  SIGNALS="$PROJECT_DIR/governance/signals.yml"
else
  _fw_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  [ -f "$_fw_root/governance/signals.yml" ] && SIGNALS="$_fw_root/governance/signals.yml"
fi

# Each line of output is a kind, a tab and a message: W for a gate-state
# warning, N for a scope-bloat reminder. A scan that cannot start prints
# nothing, which reads as "nothing to report", as an unreadable install did
# before.
NUDGES=()
SCAN="$(compass_python - "$WORK_DIR" "$SIGNALS" 2>/dev/null <<'PYEOF'
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
# vocabulary-scan: allow - matches the retired wording in older reports too
FAILING = re.compile(
    r"Overall:.*\bRED\b|Overall:.*FAIL|FAIL[^0-9A-Za-z]+(issue|task) does not advance",
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
        entries = task.get("reassessments") or task.get("reframes") or []
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
PYEOF
)" || true

while IFS= read -r _line; do
  case "$_line" in
    W$'\t'*) WARNINGS+=("${_line#*$'\t'}") ;;
    N$'\t'*) NUDGES+=("${_line#*$'\t'}") ;;
  esac
done <<< "$SCAN"

# --- emit gate-state warnings ------------------------------------------------
if [ "${#WARNINGS[@]}" -gt 0 ]; then
  {
    echo ""
    echo "================================================================"
    echo " COMPASS - SESSION ENDING WITH OPEN GATE STATE"
    echo "================================================================"
    for w in "${WARNINGS[@]}"; do
      echo "  ! $w"
    done
    echo "----------------------------------------------------------------"
    echo "  Run /compass:status next session to pick these up cleanly."
    echo "  Nothing here blocked the stop - but nothing here is finished."
    echo "================================================================"
    echo ""
  } >&2
fi

# --- emit scope-bloat reminders ---------------------------------------------
# NON-BLOCKING, like everything here.
if [ "${#NUDGES[@]}" -gt 0 ]; then
  {
    echo ""
    echo "================================================================"
    echo " COMPASS - RE-ASSESSMENT REMINDER"
    echo "================================================================"
    echo "  The following scope-bloat signals were found in devlog.md"
    echo "  but no re-assessment has been recorded after them:"
    echo ""
    for n in "${NUDGES[@]}"; do
      echo "  ! $n"
    done
    echo ""
    echo "  If the scope grew during Build, re-assess now:"
    echo "    /compass:assess --reassess --reason \"<what changed and why>\""
    echo ""
    echo "  This preserves the calibration signal (compass retro)."
    echo "  This reminder does not block - the session ends regardless."
    echo "================================================================"
    echo ""
  } >&2
fi

# --- approval requests the person has not seen ------------------------------
# The only output on stdout: Claude Code reads it as the hook's JSON.
# Each distinct root is asked once: the hook's project and the project of the
# input's `cwd`. A folder without `.compass` is never asked.
#
# The same pass deletes the call tickets of the session that no command used,
# so a ticket never outlives the turn that wrote it. The input goes in on
# standard input, and the program is a variable, so one Python start does both.
STOP_PROGRAM="$(cat <<'PYEOF'
import json
import os
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import approval_requests, delegation_tickets

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
session = str(event.get("session_id") or "") if isinstance(event, dict) else ""
seen, texts = set(), []
for folder in sys.argv[1:]:
    if not folder or not os.path.isdir(folder):
        continue
    real = os.path.realpath(folder)
    if real in seen:
        continue
    seen.add(real)
    delegation_tickets.drop_session(os.path.dirname(folder), session)
    text = approval_requests.stop_message(folder, os.environ)
    if text:
        texts.append(text)
if texts:
    print(json.dumps({"systemMessage": "\n\n".join(texts)}))
PYEOF
)"
printf '%s' "$STOP_INPUT" | compass_python -c "$STOP_PROGRAM" "$COMPASS_DIR" "${CWD_ROOT:+$CWD_ROOT/.compass}" 2>/dev/null || true

exit 0
