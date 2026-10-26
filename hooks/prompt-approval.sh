#!/usr/bin/env bash
# =============================================================================
# Compass hook: prompt-approval.sh  -  RECORD A TYPED APPROVAL
# =============================================================================
# Runs as a Claude Code UserPromptExpansion hook, matched on the four plugin
# commands /compass:approve, /compass:reject, /compass:delegate and
# /compass:revoke (hooks/hooks.json). Each command file sets
# `disable-model-invocation: true`, so the model cannot invoke it and a
# scheduled job delivers it as plain text with no expansion (the host
# measurement, ADR-068). The decision is made in
# cli/compass_pkg/prompt_approval.py; this script only runs it.
#
# I/O CONTRACT
#   stdin : the UserPromptExpansion input JSON.
#   stdout: Claude Code's JSON. A recorded answer:
#             {"systemMessage": ..., "hookSpecificOutput": {...}}
#           A refusal: {"decision": "block", "reason": ...}, which Claude Code
#           shows to the person and not to the model. Nothing for an input
#           that is not one of the four commands.
#   exit  : 0 whenever JSON is printed; 2, with the cause on stderr, only if
#           even the fixed refusal cannot be printed.
#
# FAILS CLOSED. When Compass's Python cannot run, or it raises, the prompt is
# blocked and nothing is written. A hook that cannot check must not let an
# approval through on the strength of a typed command alone.
# =============================================================================

set -u

HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INPUT="$(cat || true)"

# A refusal printed without Python, for when Python is the fault. The cause is
# reduced to characters that need no JSON escaping.
block_without_python() {
  local cause
  cause="$(printf '%s' "$1" | tr -d '\000-\037"\\' | cut -c1-300)"
  printf '{"decision": "block", "reason": "Compass could not check this command (%s). Nothing was written."}\n' "$cause" \
    || { echo "Compass: the approval hook could not run: $cause" >&2; exit 2; }
  exit 0
}

if [ ! -f "$HOOK_ROOT/scripts/lib/compass-python.sh" ]; then
  block_without_python "the shared loader scripts/lib/compass-python.sh is missing"
fi
# shellcheck source=../scripts/lib/compass-python.sh
source "$HOOK_ROOT/scripts/lib/compass-python.sh"

ERR_FILE="$(mktemp 2>/dev/null)" || block_without_python "it could not create a temporary file"
OUT="$(printf '%s' "$INPUT" | compass_python "$HOOK_ROOT/hooks/py/prompt_approval.py" \
  "${CLAUDE_PLUGIN_ROOT:-$HOOK_ROOT}" 3<&0 2>"$ERR_FILE" </dev/null)"
STATUS=$?
if [ "$STATUS" -ne 0 ]; then
  CAUSE="$(sed -n '1p' "$ERR_FILE" 2>/dev/null)"
  rm -f "$ERR_FILE"
  block_without_python "python3 exited $STATUS${CAUSE:+: $CAUSE}"
fi
rm -f "$ERR_FILE"
[ -n "$OUT" ] && printf '%s\n' "$OUT"
exit 0
