#!/usr/bin/env bash
# =============================================================================
# Compass hook: session-start.sh  -  PUT THE OPERATING CONTRACT IN THE SESSION
# =============================================================================
# Runs as a Claude Code SessionStart hook, on startup, clear and compact.
#
# WHY IT EXISTS
#   Without this hook, the contract reaches a session only when the model
#   loads the `compass-runtime` skill. CLAUDE.md applies only inside the
#   Compass repository, so an adopter's session gets no rules.
#
# WHAT IT DOES
#   Prints a JSON object carrying the contract as `additionalContext`, which
#   Claude Code adds to the session. It never blocks - a SessionStart hook has
#   nothing to refuse - so every path here exits 0.
#
# THE BOUNDARY
#   A repository with no .compass/ has never opted into Compass, and this hook
#   is installed at user scope: it starts in every session on the machine.
#   There it prints nothing at all. Same rule as hooks/pre-tool.sh, minus the
#   half that cannot apply - there is no fail-closed case here, because there
#   is no gate to close.
#
# WHERE THE CONTRACT LIVES
#   compass-contract.md at the framework root, and only there. CLAUDE.md and
#   skills/compass-runtime/SKILL.md point at it and do not restate it.
# =============================================================================
set -uo pipefail

# The contract ships with the framework, so it is found from this script's own
# location. That is right here and wrong in pre-tool.sh: this hook reads a file
# the PLUGIN owns, where that one resolves a project the USER owns and must
# never reach for its own tree instead.
FRAMEWORK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACT="$FRAMEWORK_ROOT/compass-contract.md"

# The status line launcher. A statusLine setting must name a fixed path, but
# the plugin's own path names its version and changes on every upgrade. So
# keep a small launcher in the plugin's data folder, which Claude Code keeps
# across updates, pointing at this version's bin/compass-statusline; the
# setting names the launcher and never has to change. It is written in every
# repository, before the opt-in check, because the status line runs
# everywhere. Rewritten only when its content differs, through a temporary
# file and a rename, so a status line refresh never runs half a script. It
# prints nothing and never fails the session.
compass_write_statusline_launcher() {
  local data="${CLAUDE_PLUGIN_DATA:-}" target launcher want tmp
  [ -n "$data" ] || return 0
  mkdir -p "$data" 2>/dev/null
  [ -d "$data" ] && [ -w "$data" ] || return 0
  target="$FRAMEWORK_ROOT/bin/compass-statusline"
  launcher="$data/compass-statusline"
  want="$(printf '#!/usr/bin/env bash\n# Written by the Compass session-start hook, and rewritten when the plugin\n# moves, so the statusLine setting can name this file and never change.\ntarget=%q\n[ -x "$target" ] || exit 0\nexec "$target"' "$target")"
  if [ -f "$launcher" ] && [ "$(cat "$launcher" 2>/dev/null)" = "$want" ]; then
    return 0
  fi
  tmp="$(mktemp "$data/.compass-statusline.XXXXXX" 2>/dev/null)" || return 0
  if printf '%s\n' "$want" > "$tmp" && chmod 755 "$tmp" && mv -f "$tmp" "$launcher"; then
    return 0
  fi
  rm -f "$tmp"
}
compass_write_statusline_launcher >/dev/null 2>&1 || true

INVOKED_FROM="$(pwd)"
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
  PROJECT_DIR=""
  _search="$INVOKED_FROM"
  while [ -n "$_search" ]; do
    [ -d "$_search/.compass" ] && { PROJECT_DIR="$_search"; break; }
    # The repository is the outer bound. Walking past it would inject the
    # contract because a stranger's project happens to sit above this one.
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
  [ -n "$PROJECT_DIR" ] || exit 0
fi

# Not a Compass project: say nothing. An explicit CLAUDE_PROJECT_DIR is the
# runtime naming a directory, not a statement that Compass lives in it - the
# runtime sets it for every repository.
[ -d "$PROJECT_DIR/.compass" ] || exit 0

[ -f "$CONTRACT" ] || exit 0

# Without Python 3.10 or later the CLI cannot run and pre-tool.sh refuses
# code edits, so say so now, to the person and to the model, rather than let
# the first refused edit be how they find out. The message is fixed ASCII
# built with printf; the one variable part, the version, holds only digits
# and dots (scripts/lib/python-check.sh), so the JSON stays valid. The hook
# still never blocks.
# shellcheck source=../scripts/lib/python-check.sh
. "$FRAMEWORK_ROOT/scripts/lib/python-check.sh"
PY_STATUS="$(compass_python_status)"
case "$PY_STATUS" in
  ok\ *) ;;
  *)
    case "$PY_STATUS" in
      missing) found="python3 was not found on the PATH. Until it is installed, Compass refuses code edits in this project and its commands do not run." ;;
      broken) found="a python3 is on the PATH but did not run. Until it runs, Compass refuses code edits in this project and its commands do not run." ;;
      *) found="python3 ${PY_STATUS#old } was found, which the Compass CLI cannot run on. Without the CLI, an issue's assessment and failing test cannot be recorded, so Compass refuses the code edits that need them." ;;
    esac
    msg="Compass needs Python 3.10 or later, and $found Fix: install Python 3.10 or later and put python3 on the PATH, then start a new session."
    printf '{"systemMessage": "%s", "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "%s"}}\n' "$msg" "$msg"
    exit 0 ;;
esac

# Emitted as JSON by python3, which is how the rest of the kit reads and writes
# JSON. A hand-rolled escape here would break on the first apostrophe in the
# contract.

# The project's `always` lessons follow the contract, under their own
# 150-word cap (cli/compass_pkg/lessons.py, ADR-029). A failure to read them
# loses the lessons, never the contract.
PYTHONPATH="$FRAMEWORK_ROOT/cli${PYTHONPATH:+:$PYTHONPATH}" \
python3 - "$CONTRACT" "$PROJECT_DIR/.compass" <<'PY' 2>/dev/null || exit 0
import json
import sys

with open(sys.argv[1], encoding="utf-8") as fh:
    contract = fh.read()

try:
    from compass_pkg.lessons import render_block
    lessons = render_block(sys.argv[2])
except BaseException:  # noqa: BLE001 - the contract must still reach the session
    lessons = ""
if lessons:
    contract = contract.rstrip("\n") + "\n\n" + lessons + "\n"

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": contract,
    }
}))
PY
