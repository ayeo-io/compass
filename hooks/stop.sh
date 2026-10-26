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

HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=../scripts/lib/compass-python.sh
source "$HOOK_ROOT/scripts/lib/compass-python.sh"

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
if ! compass_python "$HOOK_ROOT/hooks/py/python_runs.py" </dev/null >/dev/null 2>&1; then
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
_cwd="$(printf '%s' "$STOP_INPUT" | compass_python "$HOOK_ROOT/hooks/py/stop_input_cwd.py" 2>/dev/null || true)"
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
SCAN="$(compass_python "$HOOK_ROOT/hooks/py/stop_scan.py" "$WORK_DIR" "$SIGNALS" 2>/dev/null </dev/null)" || true

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
# standard input, so one Python start does both.
printf '%s' "$STOP_INPUT" | compass_python "$HOOK_ROOT/hooks/py/stop_requests.py" "$COMPASS_DIR" "${CWD_ROOT:+$CWD_ROOT/.compass}" 2>/dev/null || true

exit 0
