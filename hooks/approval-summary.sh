#!/usr/bin/env bash
# =============================================================================
# Compass hook: approval-summary.sh  -  DELEGATED APPROVALS TO REVIEW
# =============================================================================
# Runs as a Claude Code UserPromptSubmit hook. When approvals made under a
# delegation wait for the person's review, it shows a summary of them through
# `systemMessage`, on every prompt, until the person types /compass:approve
# with nothing pending, which marks them reviewed (ADR-069 decision 5).
#
# DISPLAY ONLY. It never writes a record and never blocks a prompt: it is not
# how an approval is recorded (that is hooks/prompt-approval.sh, on
# UserPromptExpansion). A summary it cannot build is left out, and the prompt
# goes on.
#
# I/O CONTRACT
#   stdin : the UserPromptSubmit input JSON; only session_id and prompt_id are
#           read, to record what the summary showed. The rest is disk state.
#   stdout: {"systemMessage": ...} when there is something to review.
#   exit  : always 0.
# =============================================================================

set -u
# The input names the session and the prompt, so the summary can record what
# this session was shown (delegations.summary_for_hook).
INPUT="$(cat 2>/dev/null || true)"

HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[ -f "$HOOK_ROOT/scripts/lib/compass-python.sh" ] || exit 0
# shellcheck source=../scripts/lib/compass-python.sh
source "$HOOK_ROOT/scripts/lib/compass-python.sh"

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$PROJECT_DIR" ]; then
  _search="$(pwd)"
  while [ -n "$_search" ]; do
    [ -d "$_search/.compass" ] && { PROJECT_DIR="$_search"; break; }
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
fi
[ -n "$PROJECT_DIR" ] && [ -d "$PROJECT_DIR/.compass/work" ] || exit 0

compass_python - "$PROJECT_DIR" "$INPUT" 2>/dev/null <<'PYEOF' || true
import json
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import delegations

try:
    event = json.loads(sys.argv[2])
except ValueError:
    event = {}
if not isinstance(event, dict):
    event = {}
text = delegations.summary_for_hook(sys.argv[1], str(event.get("session_id") or ""),
                                    str(event.get("prompt_id") or ""))
if text:
    print(json.dumps({"systemMessage": text}))
PYEOF
exit 0
