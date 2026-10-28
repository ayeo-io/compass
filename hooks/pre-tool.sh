#!/usr/bin/env bash
# =============================================================================
# Compass hook: pre-tool.sh  -  THE RED-BEFORE-GREEN STRATEGY ENFORCER
# =============================================================================
# Enforces the red-before-green strategy mechanically - in service of the
# guardrail that every change lands with a passing automated test covering it.
#
#   * The GUARDRAIL is the hard line: no code ships without a passing test it
#     traces to. It is checked at the verify stage and at ship time, with
#     evidence.
#   * Red-before-green is a STRATEGY - the strong, shipped-on *way* to satisfy
#     that guardrail. This hook enforces the strategy, and a strategy is aware
#     of the delivery approach.
#
# This hook therefore BLOCKS code edits with no failing test on record -
# EXCEPT on a spike, where the strategy is deliberately suspended so
# exploratory edits are not blocked. A spike still cannot cross the
# guardrail: nothing ships from a spike without being reassessed
# (`/compass:assess --reassess`) into a delivery approach first, where this
# hook applies in full.
#
# WHAT IT DOES
#   Runs as a Claude Code PreToolUse hook. On a tool call that edits or writes a
#   *code* file (not a test, not docs, not a Compass artifact):
#     - if the current issue is a spike (a ".spike" marker exists) → ALLOW.
#     - else, need a recorded failing test - a ".red" marker file under
#       .compass/work/<issue-slug>/. No .red marker → the edit is BLOCKED.
#
# THE MARKER CONVENTION
#   .compass/work/<issue-slug>/.red    "a failing test exists for this
#                                      issue". It is NOT a bare `touch` - it is
#                                      written by `compass tdd-red <test-cmd>`,
#                                      which runs the test, confirms it really
#                                      fails, writes evidence/red.json with the
#                                      command + exit code + log, and only THEN
#                                      drops the .red marker. So the marker
#                                      means "a real, observed failure is on
#                                      record", not "someone touched a file".
#     1. The implement stage: `compass tdd-red -- <your failing test command>`.
#     2. Edit the production code - this hook sees .red and allows it.
#     3. `compass tdd-green -- <test command>` confirms green, writes
#        evidence/green.json, and clears .red - the hand-off to the verify stage.
#   .compass/work/<issue-slug>/.spike  "this issue is a spike - the red-
#                                      before-green strategy is suspended".
#                                      /compass:assess
#                                      writes this when it composes a Spike.
#   Markers are deliberately plain files so they are inspectable and auditable;
#   the evidence/*.json records next to them are the audit trail.
#
# EXEMPTIONS
#   Test files, docs, config, and .compass/ artifacts are never blocked - you
#   must be able to write the failing test in the first place. A spike is the
#   deliberate exemption for exploratory work. There is no env var to disable
#   the check on delivery work: that would not be suspending a strategy, it
#   would be crossing the tested-before-ship guardrail.
#
# WIRING  (.claude/settings.json)
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Edit|Write|Bash",
#           "hooks": [ { "type": "command",
#                        "command": "$CLAUDE_PROJECT_DIR/hooks/pre-tool.sh" } ] }
#       ]
#     }
#   }
#   `scripts/install.sh` registers this for you.
#
# I/O CONTRACT  (Claude Code hook format)
#   stdin : JSON describing the tool call.
#   block : exit code 2  (Claude Code treats exit 2 on PreToolUse as "deny").
#   allow : exit code 0.
#   We also emit a short human-readable reason on stderr when blocking.
# =============================================================================

# The seconds bash has counted when the script starts, for the wall-clock fuse
# (FUSE_SECONDS, set with the limits below). It is read here, before anything
# else runs, so the fuse counts the whole run, the input read and the guards
# included. A difference is used, so an inherited SECONDS changes nothing.
HOOK_START=$SECONDS

set -euo pipefail
# The issue this hook works on is resolved below. Clear it first, so a
# TASK_DIR exported by the caller's environment is never taken for it.
TASK_DIR=""

# shellcheck source=../scripts/lib/compass-python.sh
# The shared loader in scripts/lib/compass-python.sh: compass_python() below
# reaches the bundled PyYAML the same way cli/compass does, rather than this
# hook inventing its own answer to "where is the vendored copy".
#
# A missing or unreadable helper must not end this script under `set -e` with exit 1, which
# the runtime lets through. Without it, a stand-in answers every reader with
# exit 3 and a reason, so an opted-in project refuses and names the file, and
# a repository that never opted in reaches its silent exit 0 as before.
# Keep this line, and each helper's `source` with a literal path under it,
# as stop.sh writes them: the plugin directory names the functions a helper
# defines only in that form, and blocks a call it cannot name
# (tests/test_directory_validator.py).
HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPASS_PYTHON_SH="$HOOK_ROOT/scripts/lib/compass-python.sh"
if [ -f "$COMPASS_PYTHON_SH" ] && [ -r "$COMPASS_PYTHON_SH" ]; then
  source "$HOOK_ROOT/scripts/lib/compass-python.sh"
else
  compass_python() {
    cat >/dev/null
    echo "the shared loader $COMPASS_PYTHON_SH is missing" >&2
    return 3
  }
fi

# Whether the project has a settings file, so the code_globs reader below
# starts Python only when there is one to read. A missing or unreadable helper answers yes:
# the reader then runs, and a reader that cannot run refuses, so a broken
# install never turns "unknown" into "not guarded".
SETTINGS_FILES_SH="$HOOK_ROOT/scripts/lib/settings-files.sh"
if [ -f "$SETTINGS_FILES_SH" ] && [ -r "$SETTINGS_FILES_SH" ]; then
  source "$HOOK_ROOT/scripts/lib/settings-files.sh"
else
  compass_has_settings_file() { return 0; }
fi

# --- one registry, one shape, for every refusal ------------------------------
# cli/compass_pkg/refusals.py is the one place a refusal's wording lives
# (spec D38); `compass _refusal <code> key=value ...` is the CLI command
# that reads it, for docs generation and any external caller. This hook
# reaches the registry directly - `import compass_pkg.refusals`, the same
# narrow import every other reader in hooks/py/ makes - rather than through
# `cli/compass`, which pulls in every command module at start-up and needs
# newer syntax than this hook's other readers do. A refusal is printed on
# every blocked call in every session, so it needs no more to run than the
# rest of the hook does.
#
# python3 existing but failing every call (not merely missing - a broken
# install, exit 1/2/3/127 on anything) would otherwise render THIS call
# silent too, since rendering a refusal about python3 failing is itself a
# python3 call. So a failed render falls back to a fixed line in shell
# rather than nothing - tests/test_evidence_gaps.py::test_evg_c1_* plants
# exactly this. `command -v python3` failing outright (python3-missing
# below) is the one case that never reaches this function at all.
emit_refusal() {
  local code="$1"; shift
  local out status
  set +e
  out=$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_render_refusal.py" "$code" "$@" 2>&1 </dev/null)
  status=$?
  if [ "$status" -ne 0 ] || [ -z "$out" ]; then
    # The render failed. The refusal keeps its three lines and its code so
    # a reader, or a search of docs/refusal-codes.md, still finds it; what
    # python3 printed (an import error, an "install is incomplete" notice)
    # follows, indented, because it names the real fault.
    local target="this edit" tool="" arg
    for arg in "$@"; do
      case "$arg" in
        target=*) target="edit to ${arg#target=}" ;;
        tool=*)   tool="${arg#tool=}" ;;
      esac
    done
    [ -n "$tool" ] && [ "$target" != "this edit" ] && target="$target (tool: $tool)"
    printf 'Blocked: %s\nWhy: python3 could not render the %s refusal (it exited %s).\nFix: check the python3 install (python3 --version), then retry. [%s]\n' \
      "$target" "$code" "$status" "$code" >&2
    [ -n "$out" ] && printf '%s\n' "$out" | sed 's/^/    /' >&2
    return 0
  fi
  printf '%s\n' "$out" >&2
}

# Renders a refusal from the registry and exits 2 - always, even if the
# render call itself fails (a python3 broken in some way not yet covered
# here). A refusal that cannot render nicely must still block, not fall
# through to exit 1 (which the runtime treats as non-blocking) or exit 0.
compass_block() {
  set +e
  emit_refusal "$@"
  compass_count_block
  exit 2
}

# Counts the block for the current issue in `.compass/interruptions.log`, an
# append-only log outside every issue folder, so `compass retro` can report
# how often the framework stopped work. Only once an issue is known (TASK_DIR is set);
# every error is swallowed and the exit code is untouched, because a count
# must never change the block it counts.
compass_count_block() {
  [ -n "${TASK_DIR:-}" ] && [ -d "$TASK_DIR" ] || return 0
  local issues_dir project_dir issue
  issues_dir=$(dirname "$TASK_DIR")
  project_dir=$(dirname "$issues_dir")
  issue=$(basename "$TASK_DIR")
  compass_python "$HOOK_ROOT/hooks/py/pre_tool_count_block.py" "$project_dir" "$issue" \
    >/dev/null 2>&1 </dev/null
  return 0
}

# --- one failure rule -------------------------------------------------------
# Inside an opted-in project, a check that cannot run refuses with exit 2 and
# names what could not run. Exit 1 is not a refusal - the runtime treats it as
# a non-blocking error and lets the edit through - and a refusal that blames
# the issue when the install is broken sends the user to the wrong fix. Every
# Python reader below calls this on any non-zero status.
compass_reader_failed() {
  local reader="$1" status="$2" errfile="${3:-}" settings_name="${4:-}"
  local target="${TARGET:-${candidate:-?}}" tool="${TOOL:-?}" errline=""
  if [ -n "$errfile" ] && [ -s "$errfile" ]; then
    errline=$(sed -n '1p' "$errfile")
  fi
  set +e
  if [ "$status" = "tmp" ]; then
    emit_refusal reader-failed "target=$target" "tool=$tool" "reader=$reader" \
      "cause=It could not create a temporary file for its output." \
      "detail=${errline:+ ($errline)}"
  elif ! command -v python3 >/dev/null 2>&1; then
    # python3 itself is missing - there is no CLI left to render this with,
    # so this is a byte-identical static copy of
    # render("python-missing", target=..., tool=...). Kept in step by
    # tests/test_refusal_registry.py::test_rtp_3_no_python3_names_python_missing_and_matches_the_registry.
    printf 'Blocked: edit to %s (tool: %s)\nWhy: python3 was not found on the PATH, so Compass cannot check whether this edit is allowed.\nFix: install python3 (3.10+) or put it on PATH, then retry. [python-missing]\n' "$target" "$tool" >&2
  elif [ -n "$settings_name" ]; then
    # A settings file the reader found but could not use. `file` is the one
    # project_settings read, so the refusal never names a file that was not.
    emit_refusal config-invalid "target=$target" "tool=$tool" \
      "file=$settings_name" "detail=$errline"
  else
    emit_refusal reader-failed "target=$target" "tool=$tool" "reader=$reader" \
      "cause=It exited $status." "detail=${errline:+ ($errline)}"
  fi
  [ -n "$errfile" ] && rm -f "$errfile"
  exit 2
}

# --- read the tool call from stdin ------------------------------------------
INPUT=$(cat || true)

# Pull the target file path out of the JSON. Prefer jq; fall back to grep so the
# hook still works on a machine without jq installed.
if command -v jq >/dev/null 2>&1; then
  TARGET=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)
  TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)
  SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)
  COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
  TRANSCRIPT=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)
else
  # A JSON string runs to the first quote that no backslash escapes, so a
  # command such as `bash -c "..."` is read in full, as jq reads it. The
  # bracket expression `[^"\\]` means the same to BSD and GNU grep.
  _json_string() {
    local found
    found=$(printf '%s' "$INPUT" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" | head -n1 | sed -E 's/^"[^"]*"[[:space:]]*:[[:space:]]*"(.*)"$/\1/' || true)
    # Undo the JSON escapes jq would undo. A doubled backslash is held as a
    # control character first, so `\\"` reads as a backslash and a quote.
    found="${found//\\\\/$'\001'}"
    found="${found//\\\"/\"}"
    found="${found//\\\//\/}"
    found="${found//\\t/$'\t'}"
    found="${found//\\n/$'\n'}"
    found="${found//$'\001'/\\}"
    printf '%s' "$found"
  }
  TARGET=$(_json_string file_path)
  # A Grep names its folder as `path`, as jq's `// .tool_input.path` reads it.
  # The opening quote keeps `"transcript_path"` from matching.
  [ -n "$TARGET" ] || TARGET=$(_json_string path)
  TRANSCRIPT=$(_json_string transcript_path)
  SESSION_ID=$(_json_string session_id)
  TOOL=$(_json_string tool_name)
  COMMAND=$(_json_string command)
fi

# --- the rest of the hook, in parts ------------------------------------------
# The rest of the hook is in hooks/lib/, cut into parts so that each file stays
# short enough for a reader, and for the plugin directory's checks, to read in
# full. Each part is sourced here, at the top level and in order, so the parts
# run as one script: a variable a part sets is global, and an `exit` ends the
# hook.
#
# Every part is checked before any is sourced. A part that is missing, or that
# cannot be read, refuses the call: sourcing an unreadable file fails without a
# refusal, and an earlier part can end the hook before a later one is reached.
#
# The parts are found from this script's own path, not through `pwd` as
# HOOK_ROOT is: in a working directory that was removed, `pwd` can name a
# folder that does not exist, and the hook must still load to refuse with
# working-directory-gone.
PRE_TOOL_SELF="${BASH_SOURCE[0]}"
case "$PRE_TOOL_SELF" in /*) ;; *) PRE_TOOL_SELF="$PWD/$PRE_TOOL_SELF" ;; esac
PRE_TOOL_PARTS="${PRE_TOOL_SELF%/*}/lib"
compass_part_missing() {
  emit_refusal reader-failed "target=${TARGET:-?}" "tool=${TOOL:-?}" \
    "reader=pre-tool hook part $1" "cause=Its file is missing from the install, or cannot be read." "detail="
  exit 2
}
for _part in pre-tool-project.sh pre-tool-guards.sh pre-tool-targets.sh pre-tool-bash-writes.sh pre-tool-issue.sh pre-tool-checks.sh; do
  [ -f "$PRE_TOOL_PARTS/$_part" ] && [ -r "$PRE_TOOL_PARTS/$_part" ] || compass_part_missing "$_part"
done
# shellcheck source=hooks/lib/pre-tool-project.sh
. "$PRE_TOOL_PARTS/pre-tool-project.sh"
# shellcheck source=hooks/lib/pre-tool-guards.sh
. "$PRE_TOOL_PARTS/pre-tool-guards.sh"
# shellcheck source=hooks/lib/pre-tool-targets.sh
. "$PRE_TOOL_PARTS/pre-tool-targets.sh"
# shellcheck source=hooks/lib/pre-tool-bash-writes.sh
. "$PRE_TOOL_PARTS/pre-tool-bash-writes.sh"
# shellcheck source=hooks/lib/pre-tool-issue.sh
. "$PRE_TOOL_PARTS/pre-tool-issue.sh"
# shellcheck source=hooks/lib/pre-tool-checks.sh
. "$PRE_TOOL_PARTS/pre-tool-checks.sh"
