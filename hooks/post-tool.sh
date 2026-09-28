#!/usr/bin/env bash
# =============================================================================
# Compass hook: post-tool.sh  -  DEVLOG APPENDER
# =============================================================================
# Runs as a Claude Code PostToolUse hook, after an Edit or Write tool
# call completes. It does one thing: appends a short line to the current
# issue's devlog.md, so "persistence over conversation" holds without the
# agent having to remember to log every touch.
#
# It does not run tests or clear .red. `compass tdd-green` does that, because
# it runs the test and writes evidence/green.json before it clears the
# marker.
#
# THE CURRENT ISSUE
#   Named by the .compass/current-task pointer (written by /compass:assess and
#   /compass:resume); most recently changed is only the fallback.
#
# WIRING  (.claude/settings.json)
#   {
#     "hooks": {
#       "PostToolUse": [
#         { "matcher": "Edit|Write",
#           "hooks": [ { "type": "command",
#                        "command": "$CLAUDE_PROJECT_DIR/hooks/post-tool.sh" } ] }
#       ]
#     }
#   }
#   `scripts/install.sh` registers this for you.
#
# I/O CONTRACT
#   stdin : JSON describing the completed tool call.
#   exit  : always 0. This hook is advisory; it never blocks.
# =============================================================================

set -euo pipefail

INPUT="$(cat || true)"
# Find the project with the same ancestor walk as hooks/pre-tool.sh, so the
# devlog line is written from any subdirectory. The hook never blocks. When
# it finds no project it prints a note on stderr and exits 0.
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
    echo "Compass: could not locate a Compass project at or above $INVOKED_FROM - no devlog line was written." >&2
    exit 0
  fi
fi
COMPASS_DIR="$PROJECT_DIR/.compass"
WORK_DIR="$COMPASS_DIR/work"

# Nothing to do if Compass is not initialised for this project.
[ -d "$WORK_DIR" ] || exit 0

# --- extract the tool call details ------------------------------------------
if command -v jq >/dev/null 2>&1; then
  TARGET="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"
  TOOL="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)"
else
  TARGET="$(printf '%s' "$INPUT" | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
  TOOL="$(printf '%s' "$INPUT" | grep -oE '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
fi
[ -z "${TARGET:-}" ] && exit 0

# Ignore edits to Compass's own artifacts - they are not "the work", they are
# the record of it, and the devlog logs the work.
case "$TARGET" in
  *.compass/*|*/.compass/*) exit 0 ;;
esac

# Log only an edit inside the project, named relative to it. The devlog is
# the record a later session reads to pick the issue up; a scratch file or a
# worktree of another branch is not this issue's work. `cd` and `pwd -P`
# resolve a relative path, `..` and symlinks, so the comparison is between
# real directories. The target's directory exists: the tool just wrote it.
case "$TARGET" in
  /*) ABS_TARGET="$TARGET" ;;
  *)  ABS_TARGET="$INVOKED_FROM/$TARGET" ;;
esac
TARGET_DIR="$(cd "$(dirname "$ABS_TARGET")" 2>/dev/null && pwd -P)" || exit 0
REAL_ROOT="$(cd "$PROJECT_DIR" 2>/dev/null && pwd -P)" || exit 0
ABS_TARGET="$TARGET_DIR/$(basename "$ABS_TARGET")"
case "$ABS_TARGET" in
  "$REAL_ROOT"/*) TARGET="${ABS_TARGET#"$REAL_ROOT"/}" ;;
  *) exit 0 ;;
esac

# --- find the current issue (pointer first, most-recent as fallback) --------
TASK_DIR=""
POINTER="$COMPASS_DIR/current-task"
if [ -f "$POINTER" ]; then
  SLUG="$(tr -d '[:space:]' < "$POINTER" 2>/dev/null || true)"
  if [ -n "$SLUG" ] && [ -d "$WORK_DIR/$SLUG" ]; then
    TASK_DIR="$WORK_DIR/$SLUG"
  fi
fi
if [ -z "$TASK_DIR" ]; then
  TASK_DIR="$(ls -dt "$WORK_DIR"/*/ 2>/dev/null | head -n1 || true)"
  TASK_DIR="${TASK_DIR%/}"
fi
[ -z "${TASK_DIR:-}" ] && exit 0

DEVLOG="$TASK_DIR/devlog.md"
NOW="$(date '+%Y-%m-%d %H:%M')"

# --- append a devlog line ---------------------------------------------------
# devlog.md is append-only; we only ever add to the bottom.
if [ -f "$DEVLOG" ]; then
  {
    printf '\n## %s - edit: %s\n\n' "$NOW" "$TARGET"
    printf -- '- **Tool:** %s\n' "${TOOL:-edit}"
  } >> "$DEVLOG"
fi

exit 0
