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

set -euo pipefail
# The issue this hook works on is resolved below. Clear it first, so a
# TASK_DIR exported by the caller's environment is never taken for it.
TASK_DIR=""

# shellcheck source=../scripts/lib/compass-python.sh
# The shared loader in scripts/lib/compass-python.sh: compass_python() below
# reaches the bundled PyYAML the same way cli/compass does, rather than this
# hook inventing its own answer to "where is the vendored copy".
#
# A missing helper must not end this script under `set -e` with exit 1, which
# the runtime lets through. Without it, a stand-in answers every reader with
# exit 3 and a reason, so an opted-in project refuses and names the file, and
# a repository that never opted in reaches its silent exit 0 as before.
HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPASS_PYTHON_SH="$HOOK_ROOT/scripts/lib/compass-python.sh"
if [ -f "$COMPASS_PYTHON_SH" ]; then
  source "$COMPASS_PYTHON_SH"
else
  compass_python() {
    cat >/dev/null
    echo "the shared loader $COMPASS_PYTHON_SH is missing" >&2
    return 3
  }
fi

# Whether the project has a settings file, so the code_globs reader below
# starts Python only when there is one to read. A missing helper answers yes:
# the reader then runs, and a reader that cannot run refuses, so a broken
# install never turns "unknown" into "not guarded".
SETTINGS_FILES_SH="$HOOK_ROOT/scripts/lib/settings-files.sh"
if [ -f "$SETTINGS_FILES_SH" ]; then
  source "$SETTINGS_FILES_SH"
else
  compass_has_settings_file() { return 0; }
fi

# --- one registry, one shape, for every refusal ------------------------------
# cli/compass_pkg/refusals.py is the one place a refusal's wording lives
# (spec D38); `compass _refusal <code> key=value ...` is the CLI command
# that reads it, for docs generation and any external caller. This hook
# reaches the registry directly - `import compass_pkg.refusals`, the same
# narrow import every other reader in this file makes - rather than through
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
  out="$(compass_python - "$code" "$@" 2>&1 <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.refusals import render

code = sys.argv[1]
params = dict(arg.split("=", 1) for arg in sys.argv[2:])
print(render(code, **params))
PYEOF
)"
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
  compass_python - "$(dirname "$(dirname "$TASK_DIR")")" "$(basename "$TASK_DIR")" \
    >/dev/null 2>&1 <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.interruptions import record

record(sys.argv[1], sys.argv[2], "hook_blocks")
PYEOF
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
    errline="$(sed -n '1p' "$errfile")"
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
INPUT="$(cat || true)"

# Pull the target file path out of the JSON. Prefer jq; fall back to grep so the
# hook still works on a machine without jq installed.
if command -v jq >/dev/null 2>&1; then
  TARGET="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"
  TOOL="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)"
  SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)"
  COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
  TRANSCRIPT="$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
else
  # A JSON string runs to the first quote that no backslash escapes, so a
  # command such as `bash -c "..."` is read in full, as jq reads it. The
  # bracket expression `[^"\\]` means the same to BSD and GNU grep.
  _json_string() {
    local found
    found="$(printf '%s' "$INPUT" | grep -oE "\"$1\"[[:space:]]*:[[:space:]]*\"([^\"\\\\]|\\\\.)*\"" | head -n1 | sed -E 's/^"[^"]*"[[:space:]]*:[[:space:]]*"(.*)"$/\1/' || true)"
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
  TARGET="$(_json_string file_path)"
  # A Grep names its folder as `path`, as jq's `// .tool_input.path` reads it.
  # The opening quote keeps `"transcript_path"` from matching.
  [ -n "$TARGET" ] || TARGET="$(_json_string path)"
  TRANSCRIPT="$(_json_string transcript_path)"
  SESSION_ID="$(_json_string session_id)"
  TOOL="$(_json_string tool_name)"
  COMMAND="$(_json_string command)"
fi

# --- resolve the project this hook is enforcing -----------------------------
# The resolution order, and why each step exists:
#   1. The edited file's own path, when the tool call names one. It is the
#      only input that names the tree being changed - Compass creates git
#      worktrees at breakdown, so on a multiagent approach the session
#      directory and the edited file can be in different trees, and resolving
#      from the session reads the wrong project either way: it can miss a red
#      recorded in the edited tree, or borrow one recorded in the session's
#      tree.
#   2. CLAUDE_PROJECT_DIR, when the tool call names no file (a Bash call with
#      no write target). The session is the best answer there.
#   3. The ancestor walk from that starting point up to the nearest
#      .compass/ directory, bounded by .git so the walk does not cross into
#      another repository.
#
# Not resolved from this script's own location: the hook is installed from
# the plugin cache, and Compass self-hosts, so its own tree has a .compass/
# of its own. Resolving from there would enforce the framework's own issue
# against the user's edits.
#
# resolve_project() runs twice: once here, for a tool that names a file
# directly, and again once a Bash command's target has been extracted
# further down.
SESSION_DIR="$(pwd)"

# Resolve `.`, `..` and repeated slashes in an absolute path, as text, into
# NORMALISED. A global, not a printed value, so the hook starts no subshell
# for every candidate. `..` above the root stays at the root, as the kernel
# treats it.
normalise_path() {
  local part out=""
  local -a parts stack=()
  IFS=/ read -r -a parts <<<"$1"
  # `${a[@]+"${a[@]}"}`: bash 3.2 under `set -u` calls an empty array unbound.
  for part in ${parts[@]+"${parts[@]}"}; do
    case "$part" in
      ""|.) ;;
      ..) if [ "${#stack[@]}" -gt 0 ]; then
            unset "stack[$((${#stack[@]} - 1))]"
          fi ;;
      *) stack[${#stack[@]}]="$part" ;;
    esac
  done
  for part in ${stack[@]+"${stack[@]}"}; do out="$out/$part"; done
  NORMALISED="${out:-/}"
}

resolve_project() {
  _from="$SESSION_DIR"
  if [ -n "${1:-}" ]; then
    case "$1" in
      # Resolved as text first: a directory on the way, such as the missing
      # one in `/x/missing/../project/src/app.ts`, need not exist for a Write
      # to create the path, and the project is where the path points.
      /*) normalise_path "$1"; _dir="$(dirname "$NORMALISED")" ;;
      # A relative path from the host is relative to the PROJECT, not to
      # wherever the hook happens to be running. Resolved against the
      # session, a relative path can leave the project and reach the
      # framework's own .compass/, whose red would allow the edit.
      *)  _dir="$(dirname "${CLAUDE_PROJECT_DIR:-$SESSION_DIR}/$1")" ;;
    esac
    # The file may not exist yet - a Write creates one - so climb to the
    # nearest ancestor that does. Falling back to the session instead would
    # resolve a different project whenever the session sits outside the tree
    # being edited, which is the case this exists for.
    while [ -n "$_dir" ] && [ "$_dir" != "/" ] && [ ! -d "$_dir" ]; do
      _dir="$(dirname "$_dir")"
    done
    [ -d "$_dir" ] && _from="$_dir"
  fi
  INVOKED_FROM="$_from"
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -z "${1:-}" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
    return 0
  fi
  PROJECT_RESOLVED=1
  PROJECT_DIR=""
  _search="$INVOKED_FROM"
  while [ -n "$_search" ]; do
    if [ -d "$_search/.compass" ]; then
      PROJECT_DIR="$_search"
      break
    fi
    # Stop at the repository root. A walk past it can reach another
    # project's .compass/ (a monorepo sibling, a stray one in $HOME) and
    # allow the edit if that issue has a red on record.
    #
    # -e, not -d: in a git worktree .git is a file, and Compass creates
    # worktrees itself for multiagent orchestrations.
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
  if [ -z "$PROJECT_DIR" ]; then
    PROJECT_RESOLVED=0
    # Provisional, so path classification still has something to compare
    # against. Nothing is permitted on the strength of it.
    PROJECT_DIR="$INVOKED_FROM"
  fi
}

# Whether the walk found anything is recorded, not acted on yet. The refusal
# lives further down, at the point the hook actually needs issue state - a
# read-only Bash call is allowed without a project at all, and refusing here
# would make the cheap path expensive and wrong.
#
# Trust an explicit CLAUDE_PROJECT_DIR without checking for .compass/. The
# missing-.compass/work/ branch below gives the useful message.
PROJECT_RESOLVED=1

# Bash keeps the session as its project: its target is extracted much later,
# by a classifier that resolves candidates against PROJECT_DIR, and
# re-running resolution inside that loop would break every write shape it
# guards. So the worktree fix covers the tools that name a file directly -
# Edit and Write - which is where a builder in a worktree actually works. A
# Bash redirect inside a worktree still resolves from the session;
# docs/safety-contract.md states that scope.
if [ "${TOOL:-}" = "Bash" ]; then
  resolve_project ""
else
  resolve_project "${TARGET:-}"
fi

# --- record the session on the issue (usage.sessions) ------------------------
# `compass ship-commit` reads the transcripts of every session that worked on
# an issue, so the hook notes each session id in the issue's manifest the
# first time it sees one. It runs before the path classification, so a
# document write and a Bash call are recorded too.
#
# The issue comes from COMPASS_ISSUE or the pointer only, read in shell: with
# neither, nothing is recorded, and the most recently changed issue is never
# guessed. An id already recorded costs one `grep` and no python3 process; a
# new one starts one, which tries the manifest lock once without waiting
# (cli/compass_pkg/session_record.py). This never refuses a call: every
# fault, a bad id or a recorder that cannot run returns 0 with its output
# discarded, and the checks below judge the call as before. A broken install
# still refuses through those checks.
compass_record_session() {
  [ "${PROJECT_RESOLVED:-0}" -eq 1 ] || return 0
  case "${SESSION_ID:-}" in ""|*[!A-Za-z0-9_-]*) return 0 ;; esac
  local slug="" via="pointer" pointer="$PROJECT_DIR/.compass/current-task"
  if [ -n "${COMPASS_ISSUE:-}" ]; then
    slug="$COMPASS_ISSUE"; via="env"
  elif [ -f "$pointer" ]; then
    IFS= read -r slug < "$pointer" || true
    slug="${slug//[[:space:]]/}"
  fi
  case "$slug" in ""|.|..|*/*|*\\*) return 0 ;; esac
  local folder="$PROJECT_DIR/.compass/work/$slug"
  [ -f "$folder/manifest.yml" ] || return 0
  grep -qE "^[[:space:]]*- ['\"]?${SESSION_ID}['\"]?[[:space:]]*\$" \
    "$folder/manifest.yml" 2>/dev/null && return 0
  compass_python - "$folder" "$SESSION_ID" "$via" >/dev/null 2>&1 <<'PYEOF' || true
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.session_record import record

record(*sys.argv[1:])
PYEOF
  return 0
}
set +e
compass_record_session
set -e

# --- approval state the agent must not touch ---------------------------------
# Request files, delegation files, the prompt hook's entry point, the session
# transcript (which holds the code that confirms a g5 delegation) and a
# delegated approval's caller (cli/compass_pkg/approval_guard.py; ADR-068
# decision 10, ADR-069 decisions 3, 4 and 8). This runs before the path
# classification, which exempts every `.compass/` path from the red check.
# python3 starts only when the call names one of these, so an ordinary call
# costs a few `case` tests. A guard that cannot run refuses. Every input names
# the transcript, so the match is on the command and the target, not the input.
#
# Every Grep runs the guard: one with no path, or a relative one, can search a
# folder above the transcript, and only the guard resolves it against the
# call's `cwd`. A Bash command runs it when it names `~`, HOME, a `.claude`
# folder, `/.` or `//` (a spelling the guard normalises), the transcript's
# folder anywhere, or a folder above the transcript as a whole word or
# followed by a glob, a brace or a quote. The loop walks those
# folders with parameter expansion, so it starts no process, and only for an
# absolute transcript path, so it always ends. The match ignores letter case,
# as macOS does, and the shell option is put back afterwards.
GUARD_RUN=0
_nocase=0
shopt -q nocasematch && _nocase=1
shopt -s nocasematch
case "${TOOL:-}" in
  Grep) GUARD_RUN=1 ;;
  Read) case "${TARGET:-}" in
          *projects*|*.claude*|*CLAUDE_CONFIG_DIR*|*delegations*|*approval-requests*|\
          *'~'*|*HOME*) GUARD_RUN=1 ;;
        esac ;;
  *) # The patterns are also tried with every quote and backslash removed,
     # since the shell drops them: `--d''elegated`, `-\-delegated` and
     # `$'--delegated'` all run as `--delegated`.
     _text="${COMMAND:-}${TARGET:-}"
     _bare="${_text//[\'\"\\]/}"
     case "$_text $_bare" in
       *approval-requests*|*prompt-approval.sh*|*.compass/delegations*|*--del*|\
       *.claude*|*CLAUDE_CONFIG_DIR*) GUARD_RUN=1 ;;
     esac
     if [ "$GUARD_RUN" = 0 ] && [ "${TOOL:-}" = "Bash" ]; then
       case "${COMMAND:-}" in *'~'*|*HOME*|*/.*|*//*) GUARD_RUN=1 ;; esac
       _above=""
       case "${TRANSCRIPT:-}" in /*) _above="${TRANSCRIPT%/*}" ;; esac
       case "${COMMAND:-}" in *"${_above:-//no transcript//}"*) GUARD_RUN=1 ;; esac
       while [ "$GUARD_RUN" = 0 ] && [ -n "$_above" ]; do
         case " ${COMMAND:-} " in
           *[[:space:]\"\']"$_above"[[:space:]\"\']*|\
           *[[:space:]\"\']"$_above"/[[:space:]\"\'*]*|\
           *[[:space:]\"\']"$_above"/*[*?[{\"\'\\]*)
             GUARD_RUN=1 ;;
         esac
         _next="${_above%/*}"
         [ "$_next" = "$_above" ] && break
         _above="$_next"
       done
     fi ;;
esac
[ "$_nocase" = 1 ] || shopt -u nocasematch
case "$GUARD_RUN" in
  1)
    GUARD_ERR="$(mktemp 2>/dev/null)" || compass_reader_failed "approval guard" tmp
    set +e
    GUARD="$(printf '%s' "$INPUT" | compass_python -c '
import json, sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.approval_guard import check

try:
    event = json.load(sys.stdin)
except ValueError:
    event = {}
found = check(event if isinstance(event, dict) else {})
if found:
    code, params = found
    print(code)
    for key, value in params.items():
        print("%s=%s" % (key, " ".join(str(value).split())))
' 2>"$GUARD_ERR")"
    GUARD_STATUS=$?
    set -e
    [ "$GUARD_STATUS" -eq 0 ] || compass_reader_failed "approval guard" "$GUARD_STATUS" "$GUARD_ERR"
    rm -f "$GUARD_ERR"
    if [ -n "$GUARD" ]; then
      GUARD_CODE="$(printf '%s\n' "$GUARD" | sed -n '1p')"
      GUARD_PARAMS=()
      while IFS= read -r line; do
        [ -n "$line" ] && GUARD_PARAMS+=("$line")
      done <<GUARDPARAMS
$(printf '%s\n' "$GUARD" | sed -n '2,$p')
GUARDPARAMS
      case "$GUARD_CODE" in
        approval-request-protected)
          compass_block approval-request-protected "${GUARD_PARAMS[@]}" ;;
        delegation-protected)
          compass_block delegation-protected "${GUARD_PARAMS[@]}" ;;
        delegation-caller-mismatch)
          compass_block delegation-caller-mismatch "${GUARD_PARAMS[@]}" ;;
        transcript-protected)
          compass_block transcript-protected "${GUARD_PARAMS[@]}" ;;
      esac
    fi
    ;;
esac
# Read and Grep are matched only for the transcript and delegation checks
# above; reading a file never needs a red.
case "${TOOL:-}" in Read|Grep) exit 0 ;; esac


# --- classify a target file -------------------------------------------------
# A "code file" here means: a production-impacting file whose change must be
# preceded by a failing test. That is broader than application source - a
# Terraform file, a SQL migration, a Kubernetes manifest, or a CI workflow can
# be more dangerous than ordinary code. Test files, docs, and Compass's own
# artifacts are exempt.
#
# This is a function rather than a straight-line sequence because a single
# tool call can name more than one path: a Bash command may redirect into one
# file and copy over another. Both branches share this one implementation so
# the rules cannot differ - a path exempt for an Edit is exempt for a shell
# redirect, by construction.
#
# Returns 0 (true) if a change to $1 must be preceded by a failing test.
MATCHED_RULE=""
is_enforced_path() {
  local target="$1" rel base is_code=0 abs

  # CONTAINMENT FIRST: only guard what is inside the project Compass governs.
  #
  # Without this, the extension rules below would fire on any .py/.ts/.go file
  # on the machine, such as a scratch file in a temp directory, and demand a
  # failing test for a file that cannot reach main.
  #
  # The target is resolved first, because a Bash redirect yields a RELATIVE
  # path: comparing `src/app.py` against an absolute project directory would
  # answer "outside" and switch enforcement off for exactly the writes the
  # hook is here for.
  # Resolved against PROJECT_DIR, not the hook's own working directory. The
  # hook cannot know the shell's cwd, and guessing wrong in that direction
  # fails OPEN - a relative write would be judged outside the project and
  # allowed. A relative path in an agent's command is against the project root
  # in practice, and being wrong the other way costs only a visible refusal.
  abs="$target"
  case "$abs" in
    /*) ;;
    *) abs="$PROJECT_DIR/$abs" ;;
  esac
  # Judge where the path points, not how it is spelled: `/tmp/../<project>/x`,
  # `//<project>/x` and `<project>/./x` all reach the project, and
  # `<project>/../elsewhere/x` leaves it. The steps are resolved as text; a
  # symbolic link is not followed. A path that differs from the project only
  # in letter case is treated as inside it, because macOS and Windows file
  # systems ignore case; on a file system that does not, that costs a visible
  # refusal, never a missed one.
  #
  # A `..` after a part the hook cannot know - an unexpanded `$NAME`, a
  # backtick, `~` or a brace list - would cancel that part as text, though
  # the shell may expand it to several directories or to none. Such a path
  # points somewhere unknowable, so it is judged inside the project, as the
  # text comparison did before.
  local proj inside=0 unknowable=0
  normalise_path "$PROJECT_DIR"; proj="$NORMALISED"
  case "$abs" in
    *'$'*|*'`'*|*'~'*|*'{'*)
      case "/$abs/" in
        */../*) unknowable=1; inside=1 ;;
      esac ;;
  esac
  if [ "$unknowable" -eq 0 ]; then
    normalise_path "$abs"; abs="$NORMALISED"
  fi
  case "$abs" in
    "$proj"/*) inside=1 ;;
  esac
  if [ "$inside" -eq 0 ] && [ "${#abs}" -gt "${#proj}" ] \
      && [ "${abs:${#proj}:1}" = "/" ] \
      && [ "$(printf '%s' "${abs:0:${#proj}}" | tr '[:upper:]' '[:lower:]')" = \
           "$(printf '%s' "$proj" | tr '[:upper:]' '[:lower:]')" ]; then
    inside=1
  fi
  [ "$inside" -eq 1 ] || return 1
  # From here every rule reads the resolved path, so a `..` step cannot
  # borrow an exemption: `.compass/../src/app.py` is `src/app.py`. A target
  # given as a relative path stays relative, and an absolute one absolute,
  # as before.
  if [ "$unknowable" -eq 1 ]; then
    # Judged by its text, as written.
    rel="${target#"$PROJECT_DIR"/}"
  else
    rel="${abs:$((${#proj} + 1))}"
    case "$target" in
      /*) target="$abs" ;;
      *) target="$rel" ;;
    esac
  fi

  # Always exempt: Compass artifacts, docs, lockfiles, the obvious non-code.
  #
  # A path judged by its text after an unknown part and a `..` step does not
  # get the `.compass/` exemption, or the test-directory one below: the
  # directories named before the last `..` say nothing about where the file
  # lands, so `$X/../.compass/../src/app.py` may be `src/app.py`
  # (ayeo-io/compass-delivery-record#187). The file-name and extension rules
  # still apply, because a `..` step cannot change the last part of a path.
  if [ "$unknowable" -eq 0 ]; then
    case "$target" in
      *.compass/*|*/.compass/*) return 1 ;;
    esac
  fi
  case "$target" in
    *.md|*.markdown|*.txt|*.rst|*.adoc) return 1 ;;
    *.lock|*.gitignore|*.gitkeep|*.gitattributes|*.editorconfig) return 1 ;;
  esac

  # Exempt: test files - you have to be able to write the red. Tune these globs
  # to the project's test conventions.
  #
  # Match the basename and the project-relative path, never the absolute
  # path: matching `*test*` against an absolute path also matches every
  # ancestor directory, so a repository living under any path containing
  # "test" or "spec" - /Users/testuser/..., .../latest/... - would have
  # red-before-green silently disabled for the entire tree. `rel` was set by
  # the containment check above.
  base="$(basename "$target")"
  # Match anchored patterns, never `*test*`: a bare substring match would call
  # latest.py, inspector.py and protest.py tests, and silently skip both
  # guardrail checks for them on the allow path, which prints nothing.
  #
  # The conventions covered: pytest/go (test_x, x_test), jest/vitest
  # (x.test.ts, x.spec.js), JUnit/RSpec class names (XTest.java, XSpec.rb),
  # and Ruby's x_spec.rb. Directory rules below catch the rest.
  case "$base" in
    test_*|spec_*) return 1 ;;
    *_test.*|*_spec.*|*.test.*|*.spec.*) return 1 ;;
    *Test.*|*Spec.*|*Tests.*|*Specs.*) return 1 ;;
    conftest.py) return 1 ;;
  esac
  if [ "$unknowable" -eq 0 ]; then
    case "$rel" in
      tests/*|*/tests/*|test/*|*/test/*|spec/*|*/spec/*|\
      __tests__/*|*/__tests__/*|testdata/*|*/testdata/*) return 1 ;;
    esac
  fi

  # (a) recognised application source extensions.
  case "$target" in
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) is_code=1 ;;
    *.py|*.rb|*.go|*.rs|*.java|*.kt|*.kts) is_code=1 ;;
    *.c|*.h|*.cc|*.cpp|*.hpp|*.cs|*.swift|*.m|*.mm) is_code=1 ;;
    *.php|*.scala|*.ex|*.exs|*.clj|*.elm|*.dart) is_code=1 ;;
  esac

  # (b) infrastructure / data / pipeline files - production-impacting even though
  #     they are not "application code". A SQL migration or a Terraform plan
  #     deserves a failing test (or a tested rollback) as much as a service does.
  case "$target" in
    *.tf|*.tfvars|*.hcl) is_code=1 ;;                       # Terraform / HCL
    *.sql) is_code=1 ;;                                     # SQL incl. migrations
    Dockerfile|*/Dockerfile|*.dockerfile) is_code=1 ;;      # container images
  esac

  # (c) path-scoped: YAML/JSON are exempt by default (config, data) - EXCEPT
  #     under infrastructure-ish paths, where a yaml IS the production change
  #     (k8s manifests, Helm charts, CI workflows, migrations, dbt models).
  #     Note: in a `case` glob, `*` also matches `/`, so `*migrations/*` catches
  #     both `migrations/x` and `db/migrations/x` - leading `*` with no slash.
  case "$target" in
    *migrations/*|*db/migrate/*) is_code=1 ;;
    *.github/workflows/*|*.gitlab-ci.yml) is_code=1 ;;
    *k8s/*|*kubernetes/*|*helm/*|*charts/*|*manifests/*|*deploy/*) is_code=1 ;;
    *terraform/*|*infra/*|*infrastructure/*) is_code=1 ;;
    *dbt/*|*models/*.sql) is_code=1 ;;
  esac

  if [ "$is_code" -eq 1 ]; then
    MATCHED_RULE="the built-in production-code set"
    return 0
  fi

  # (d) the project's own declaration, in the project's settings file
  # (`compass.yml`, or `.compass/config.yml` for a project that has not moved
  # its settings):
  #
  #     enforcement:
  #       code_globs: ["*.sh", "packaging/**"]
  #
  # This ADDS to the set above. There is deliberately no key that removes
  # framework enforcement: Compass's model is that project rules ratchet UP - a
  # project guardrail may exceed a floor, never fall short of one - and a key
  # that exempted `*.py` would switch enforcement off, and someone would add
  # it the first time a red got in the way.
  #
  # Why this exists: without a declared list an author cannot predict which
  # edit will block (`.github/workflows/ci.yml` is guarded, `docker-compose.yml`
  # is not).
  #
  # Which file holds the declaration, and how it is read, is
  # project_settings's question, not this hook's. The hook only asks whether a
  # settings file exists, through the one helper that names them, so a project
  # with none costs no Python start on an edit to a path the sets above
  # neither guard nor exempt.
  if [ -d "$PROJECT_DIR/.compass" ] && compass_has_settings_file "$PROJECT_DIR"; then
    local hit glob_status glob_err glob_out settings_name
    # A reader that ran and matched nothing means the path is not
    # project-guarded. A reader that could not run - no python3, a broken
    # install, or a config it cannot parse - means we do not know whether it
    # is, and answering "not guarded" to a question we could not ask is how a
    # broken install quietly stops guarding the very scripts that broke it.
    glob_err="$(mktemp 2>/dev/null)" \
      || compass_reader_failed "enforcement.code_globs reader" tmp
    set +e
    # The reader prints the settings file it read on its first line, so a
    # refusal can name that file, and a match follows on the second line. On a
    # failure the file is the one the error names, which can be the old file
    # when `compass.yml` was the one read.
    glob_out="$(compass_python - "$PROJECT_DIR" "$rel" 2>"$glob_err" <<'PYEOF'
import fnmatch, sys
import compass_pkg
from compass_pkg import project_settings
try:
    cfg = project_settings.settings(sys.argv[1])
    globs = ((cfg.get("enforcement") or {}).get("code_globs")) or []
    # A string would be walked one character at a time, and `*` alone
    # guards every path. Any other shape is a config this cannot read.
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        raise ValueError("enforcement.code_globs must be a list of strings, "
                         "not %r" % (globs,))
except Exception as exc:            # unreadable config -> cannot answer
    # The refusal already says which file could not be read, so this is the
    # reason alone. A conflict is not a read failure and has its own status
    # and refusal; its stderr line is the keys, and the registry words the rest.
    print(getattr(exc, "file", None) or project_settings.settings_file(sys.argv[1]))
    conflict = isinstance(exc, project_settings.SettingsConflict)
    print(exc.shown if conflict else exc, file=sys.stderr)
    sys.exit(5 if conflict else 4)
print(project_settings.settings_file(sys.argv[1]))
path = sys.argv[2]
for g in globs:
    if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.rstrip("/") + "/*") \
            or fnmatch.fnmatch("/" + path, "*/" + g.lstrip("/")):
        print(g)
        break
PYEOF
)"
    glob_status=$?
    set -e
    settings_name="$(printf '%s\n' "$glob_out" | sed -n '1p')"
    hit="$(printf '%s\n' "$glob_out" | sed -n '2p')"
    if [ "$glob_status" -eq 5 ]; then
      emit_refusal settings-conflict "target=${TARGET:-${candidate:-?}}" \
        "tool=${TOOL:-?}" \
        "keys=$(sed -n '1p' "$glob_err")"
      rm -f "$glob_err"
      exit 2
    elif [ "$glob_status" -eq 4 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$glob_status" \
        "$glob_err" "$settings_name"
    elif [ "$glob_status" -ne 0 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$glob_status" "$glob_err"
    fi
    # A warning the reader wrote (a `compass.yml` it ignored) is for the person;
    # it does not change the decision.
    [ -s "$glob_err" ] && cat "$glob_err" >&2 || true
    rm -f "$glob_err"
    if [ -n "${hit:-}" ]; then
      MATCHED_RULE="enforcement.code_globs pattern '$hit' in $settings_name"
      return 0
    fi
  fi

  # Anything still unrecognised is allowed - the enforcer blocks KNOWN
  # production-impacting files; it does not block the unknown. If a project has
  # a production-impacting file type that slips through, declare it above.
  return 1
}

# --- what a shell command can be known to write ------------------------------
# A shell command is arbitrary: `bash deploy.sh` may rewrite the whole repo and
# nothing in the string says so. So detection here recognises a fixed set of
# write shapes and lets everything else through. That is deliberate - blocking
# on suspicion would block `make`, `npm test`, and every unrecognised command,
# and enforcement that people switch off protects nothing. The limit is written
# down in docs/safety-contract.md rather than left to be discovered.
#
# Being generous is safe: every candidate goes through is_enforced_path(),
# which allows anything it does not recognise as production code. A token that
# is not a path simply falls through.
bash_write_targets() {
  local cmd="$1" continuation=$'\\\n'
  {
    # Redirects into a file: `> f`, `>> f`, `1> f`, and the `cat > f <<EOF`
    # heredoc form. `2>&1` and `>&2` duplicate a file descriptor rather than
    # write a file, so `&` is excluded from the target. A quoted target is
    # taken whole, spaces included; the candidate loop removes the quotes.
    # `>|` writes as `>` does, and a line continuation after the operator
    # is joined first, so the target is not on a line of its own.
    printf '%s\n' "${cmd//"$continuation"/ }" \
      | grep -oE "[0-9]?>(>|\|)?[[:space:]]*(\"[^\"]*\"|'[^']*'|[^&<>|;()[:space:]]+)" \
      | sed -E 's/^[0-9]?>(>|\|)?[[:space:]]*//' || true

    # In-place editors: hand over every argument and let the classifier
    # decide which of them is a production file.
    case "$cmd" in
      *"sed -i"*|*"perl -i"*)
        printf '%s\n' "$cmd" | tr ' \t' '\n\n' | grep -vE '^-' || true ;;
    esac

    # `tee` writes its own arguments; `cp` and `mv` write the LAST argument of
    # their own command. Neither writes a file that another command in the
    # same line names: in `python3 x.py | tee out.txt` the script is only run,
    # and in `cp a b && grep x src/app.ts` the source file is only read.
    #
    # So the command is cut into simple commands at `;`, `&`, `|`, `(` and
    # line ends, and redirects and comments are removed. In each simple
    # command, any word that names tee, cp or mv - `/bin/cp` and `\cp`
    # included - counts, wherever it stands, so a write behind a wrapper such
    # as `sudo`, `timeout 10`, `xargs` or `git` is still found. A word after
    # `tee` is a target; for `cp` and `mv` the last word is. This over-reports
    # (`grep -n tee src/app.ts`), as the hook did before; it must never miss a
    # write the earlier, broader rules caught.
    #
    # Before the cut, the command is flattened, so that nothing inside a
    # command can split it: line continuations are joined, and each
    # `$(...)`, `<(...)`, `>(...)` and backtick span becomes one placeholder
    # word, so `cp $(mktemp) src/app.ts` keeps its destination. The text of
    # each span is then judged as a command of its own, so a write inside
    # one, such as `x=$(cp a src/app.ts)`, is still found.
    #
    # The flattening runs twice and the targets of both passes count
    # (ayeo-io/compass-delivery-record#186). The first pass counts brackets
    # without regard to quotes, and a span it cannot close takes the rest of
    # the text. So a quoted `(`, as in `cp "$(echo '(')" src/app.ts`, keeps
    # the span open and hides the destination. The second pass ignores a
    # bracket inside quotes or after a backslash, and follows a `$(` inside
    # double quotes. A span it still cannot close stays as text, so the words
    # after it are still read. Either pass can misread a command the other
    # reads correctly, and an extra target can only add a refusal, so the
    # hook keeps both. A line both passes print is printed once.
    case "$cmd" in
      *tee*|*cp*|*mv*)
        printf '%s\n' "$cmd" \
          | awk '
              function emit(line) {
                if (!(line in seen)) { seen[line] = 1; print line }
              }
              function flatten(s, quoted,    q, n, k, t, out, rest, e, d, j, L, ch, st, top, closed) {
                q[1] = s; n = 1
                for (k = 1; k <= n; k++) {
                  t = q[k]; out = ""
                  while (match(t, /[$<>]\(|`/)) {
                    if (substr(t, RSTART, 1) == "`") {
                      rest = substr(t, RSTART + 1)
                      e = index(rest, "`")
                      if (e == 0 && quoted) {
                        out = out substr(t, 1, RSTART); t = rest; continue
                      }
                      out = out substr(t, 1, RSTART - 1) "_SPAN_"
                      if (e == 0) { q[++n] = rest; t = "" }
                      else { q[++n] = substr(rest, 1, e - 1); t = substr(rest, e + 1) }
                      continue
                    }
                    j = RSTART + 2; L = length(t)
                    if (quoted) {
                      # A stack of open contexts, innermost last: P is code
                      # inside a span or bracket, S a single-quoted string
                      # and D a double-quoted one.
                      st = "P"
                      while (j <= L && st != "") {
                        ch = substr(t, j, 1); top = substr(st, length(st))
                        if (top == "S") {
                          if (ch == "\047") st = substr(st, 1, length(st) - 1)
                        } else if (ch == "\\") {
                          j++
                        } else if (top == "D") {
                          if (ch == "\"") st = substr(st, 1, length(st) - 1)
                          else if (ch == "$" && substr(t, j + 1, 1) == "(") { st = st "P"; j++ }
                        } else if (ch == "\047") st = st "S"
                        else if (ch == "\"") st = st "D"
                        else if (ch == "(") st = st "P"
                        else if (ch == ")") st = substr(st, 1, length(st) - 1)
                        j++
                      }
                      closed = (st == "")
                      if (!closed) {
                        out = out substr(t, 1, RSTART + 1); t = substr(t, RSTART + 2)
                        continue
                      }
                    } else {
                      d = 1
                      while (j <= L && d > 0) {
                        ch = substr(t, j, 1)
                        if (ch == "(") d++
                        else if (ch == ")") d--
                        j++
                      }
                      closed = (d == 0)
                    }
                    out = out substr(t, 1, RSTART - 1) "_SPAN_"
                    q[++n] = substr(t, RSTART + 2, (closed ? j - 1 : j) - RSTART - 2)
                    t = substr(t, j)
                  }
                  emit(out t)
                }
              }
              { s = s $0 "\n" }
              END {
                gsub(/\\\n/, " ", s)
                flatten(s, 0)
                flatten(s, 1)
              }' \
          | tr ';&|(' '\n\n\n\n' \
          | sed -E 's/(^|[[:space:]])#.*//; s/[0-9]*>>?[[:space:]]*[^[:space:]]*//g; s/<[[:space:]]*[^[:space:]]*//g; s/\)//g' \
          | awk '
              {
                for (i = 1; i <= NF; i++) {
                  w = $i
                  sub(/^\\/, "", w)
                  sub(/^.*\//, "", w)
                  if (w == "tee") {
                    for (j = i + 1; j <= NF; j++) if ($j !~ /^-/) print $j
                  } else if ((w == "cp" || w == "mv") && NF > i) {
                    print $NF
                  }
                }
              }' || true ;;
    esac

    # An inline interpreter script that opens a file FOR WRITING - the shape
    # this whole branch exists for, since `python3 -c` and a `python3 - <<PY`
    # heredoc are the easiest way to edit a file without an Edit tool call.
    #
    # Two things this deliberately does NOT do:
    #   - `open(path)` with no mode is a READ, not a write. Treating it as a
    #     write would block read-only verification commands - the hook
    #     stopping an author from checking their own work, which inverts what
    #     it is for.
    #   - The path must come from the write call itself, not from scanning
    #     the whole command. Lifting paths out of a heredoc body would demand
    #     a failing test for a migration that a document merely *named*.
    # A missed write is recoverable; a false block trains people to bypass the
    # hook, and nothing recovers from that.

    # open(PATH, "w"|"a"|"x"|"r+"|"wb"…) - a mode containing w, a, x or + .
    printf '%s\n' "$cmd" \
      | grep -oE "open\([[:space:]]*['\"][^'\"]+['\"][[:space:]]*,[[:space:]]*['\"][^'\"]*[waxWAX+][^'\"]*['\"]" \
      | sed -E "s/^open\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true

    # pathlib. Covers both `Path(TARGET).write_text(...)` and the commoner
    # two-step form, where the write happens on a variable:
    #     p = pathlib.Path(TARGET)
    #     p.write_text(...)
    # When the command contains a pathlib write at all, every Path(...)
    # argument in it is a candidate. The one exception is a Path(...) used
    # immediately for a read, which keeps "read a source file, generate a doc
    # from it" from being blocked on the file it only read.
    case "$cmd" in
      *write_text\(*|*write_bytes\(*)
        printf '%s\n' "$cmd" \
          | grep -oE "Path\([[:space:]]*['\"][^'\"]+['\"][[:space:]]*\)(\.[a-z_]+)?" \
          | grep -v "\.read_" \
          | sed -E "s/^Path\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true ;;
    esac

    # node / ruby equivalents, where the path is the first argument.
    printf '%s\n' "$cmd" \
      | grep -oE "(writeFileSync|appendFileSync|File\.write)\([[:space:]]*['\"][^'\"]+['\"]" \
      | sed -E "s/^[A-Za-z_.]+\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true
  } | grep -vE '^[[:space:]]*$' || true
}

# --- a variable the command itself sets --------------------------------------
# A Bash write often names its target through a variable that the same
# command sets: `S=/tmp/scratch && cat > $S/plant.ts`. Read literally,
# `$S/plant.ts` is a relative path. is_enforced_path() joins it to the project
# root and refuses a scratch file outside the project as production code. A
# usage audit on 16 October 2026 counted 116 such refusals.
#
# This prints the target with a leading $NAME or ${NAME} replaced by its
# value, but only when the command states that value for certain. Otherwise
# it prints the target unchanged, and is_enforced_path() judges it inside the
# project exactly as before. An expansion can therefore only allow a write
# whose real path the hook can see; it never guesses.
#
# "For certain" means all of these hold:
#   - The command opens with leading statements, each ended by `;`, `&&` or
#     a line end. Each is either `[export ]NAME=value`, or a plain command
#     such as `cd /x`, `set -e` or `export A=1`: words of path characters
#     only, with no word that opens a block (`if`, `for`, `{`), defines a
#     function or trap, sources a file, evaluates text or makes a variable
#     read-only. NAME is assigned exactly once among them. Any other
#     assignment does not count, because at the write the variable may still
#     hold the environment's value: one inside a block or subshell, one after
#     `||`, or `S=x cmd`, which sets S for that one command only.
#   - If `&&` comes before the assignment, the assignment runs only when the
#     commands before it succeed. Every use of NAME must then be in the same
#     `&&` chain, so that it runs only if the assignment did.
#   - The value is a plain absolute path: no `$`, backtick, `~`, space or
#     `..` step. So the shell uses the same text the hook judges, and `..`
#     cannot step back into the project past a containment check that
#     compares text.
#   - After the assignment, NAME appears only as `$NAME` or `${NAME}`, and
#     nothing runs that can set a variable without naming it: eval, source,
#     `.`, trap, declare, typeset, local, readonly, export, read, mapfile,
#     readarray, unset, getopts, let, `printf -v` or `((`.
#   - NAME is not one the shell sets itself, such as PWD (changed by cd), _,
#     REPLY or UID (read-only, so the assignment fails).
# These checks read the command's text; they do not parse the shell. A word
# that only looks like one of them, such as `S` in a heredoc body, leaves the
# target unexpanded, which refuses as before. A function inherited from the
# environment that reassigns NAME, a builtin spelt to dodge the list
# (`ev""al`), or an arithmetic context that evaluates another variable's
# text, is deliberate evasion, which shell-write detection does not claim to
# stop (docs/safety-contract.md).
expand_command_variable() {
  local target="$1" cmd="$2" name rest rem value="" count=0 full
  local sep="start" before="" after_sep="" after_name="" stmt w len deny
  local ref1 ref2 head head2
  local sq="'" dq='"' bt='`' nl=$'\n'
  local path_re='^(/[A-Za-z0-9._+@%:,=-]*)*$'
  local dotdot_re='(^|/)\.\.(/|$)'
  local brace_re='^\$\{([A-Za-z_][A-Za-z0-9_]*)\}(.*)$'
  local bare_re='^\$([A-Za-z_][A-Za-z0-9_]*)(.*)$'
  local value_re="(${sq}[^${sq}]*${sq}|${dq}[^${dq}]*${dq}|[^[:space:];&|<>()${sq}${dq}${bt}\\\$]*)"
  local assign_re="^[[:space:]]*(export[[:blank:]]+)?([A-Za-z_][A-Za-z0-9_]*)=${value_re}[[:blank:]]*(;|&&|${nl})"
  local special_re='^(_|PWD|OLDPWD|UID|EUID|PPID|BASHPID|RANDOM|SRANDOM|SECONDS|EPOCHSECONDS|EPOCHREALTIME|LINENO|HISTCMD|REPLY|OPTARG|OPTIND|GROUPS|DIRSTACK|PIPESTATUS|FUNCNAME|SHELLOPTS|BASHOPTS|MAPFILE|COPROC|BASH_[A-Z_]*|BASH)$'
  local binder_re='(^|[^A-Za-z0-9_./-])(eval|source|trap|declare|typeset|local|readonly|export|read|mapfile|readarray|unset|getopts|let)([^A-Za-z0-9_./-]|$)|(^|[;&|({'"${nl}"']|then|do|else)[[:space:]]*\.[[:space:]]|printf[[:space:]]+-v|(^|[^A-Za-z0-9_)])\(\('
  local stripped mention_re
  local plain_re="^[[:space:]]*([A-Za-z0-9._+@%:,=/~-]+([[:blank:]]+[A-Za-z0-9._+@%:,=/~-]+)*)[[:blank:]]*(;|&&|${nl})"
  local deny_re='^(eval|source|\.|declare|typeset|local|readonly|trap|alias|enable|builtin|command|shopt|function|if|then|else|elif|fi|case|esac|for|select|while|until|do|done|coproc)$'

  if [[ $target =~ $brace_re ]] || [[ $target =~ $bare_re ]]; then
    name="${BASH_REMATCH[1]}"
    rest="${BASH_REMATCH[2]}"
  else
    printf '%s\n' "$target"; return 0
  fi
  if [[ $name =~ $special_re ]] || ! [[ $rest =~ $path_re ]]; then
    printf '%s\n' "$target"; return 0
  fi

  # Walk the leading statements. `sep` is the separator that ended the
  # previous one; `after_name` is the command after NAME's assignment.
  rem="$cmd"
  while :; do
    if [[ $rem =~ $assign_re ]]; then
      len=${#BASH_REMATCH[0]}
      if [ "${BASH_REMATCH[2]}" = "$name" ]; then
        count=$((count + 1))
        value="${BASH_REMATCH[3]}"
        before="$sep"
        after_sep="${BASH_REMATCH[4]}"
        after_name="${rem:$len}"
      fi
      sep="${BASH_REMATCH[4]}"
    elif [[ $rem =~ $plain_re ]]; then
      len=${#BASH_REMATCH[0]}
      stmt="${BASH_REMATCH[1]}"
      sep="${BASH_REMATCH[3]}"
      deny=0
      for w in $stmt; do
        if [[ $w =~ $deny_re ]]; then deny=1; fi
      done
      [ "$deny" -eq 1 ] && break
    else
      break
    fi
    rem="${rem:$len}"
  done
  if [ "$count" -ne 1 ]; then
    printf '%s\n' "$target"; return 0
  fi

  # After `&&`, the assignment may not run. Then the text up to the last use
  # of NAME must be one `&&` chain: no `;`, line end, `||` or lone `&`.
  if [ "$before" = "&&" ]; then
    ref1='$'"$name"
    ref2='${'"$name"'}'
    head=""
    case "$after_name" in *"$ref1"*) head="${after_name%"$ref1"*}" ;; esac
    case "$after_name" in *"$ref2"*)
      head2="${after_name%"$ref2"*}"
      [ "${#head2}" -gt "${#head}" ] && head="$head2" ;;
    esac
    head2="${head//&&/}"
    if [ "$after_sep" != "&&" ] || [[ $head == *";"* ]] || [[ $head == *"$nl"* ]] \
        || [[ $head == *"||"* ]] || [[ $head2 == *"&"* ]]; then
      printf '%s\n' "$target"; return 0
    fi
  fi

  case "$value" in
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
  esac
  full="$value$rest"
  if [ -z "$value" ] || ! [[ $value =~ $path_re ]] || [[ $full =~ $dotdot_re ]]; then
    printf '%s\n' "$target"; return 0
  fi

  # Everything after the assignment: remove the plain references, then
  # refuse to expand if NAME is still mentioned, or if something that can
  # set a variable without naming it runs.
  # The tests are bash regex matches on the whole text, not `printf | grep
  # -q`: under pipefail, grep -q stops at its first match, printf then dies
  # of SIGPIPE on a long command, and the pipeline reads as "no match" -
  # which here would expand. Newlines count as separators in both patterns.
  stripped="$(printf '%s\n' "$after_name" \
    | sed -E "s/[\$][{]${name}[}]//g; s/[\$]${name}([^A-Za-z0-9_])/\\1/g; s/[\$]${name}\$//")"
  mention_re="(^|[^A-Za-z0-9_])${name}([^A-Za-z0-9_]|\$)"
  if [[ $stripped =~ $mention_re ]]; then
    printf '%s\n' "$target"; return 0
  fi
  if [[ $after_name =~ $binder_re ]]; then
    printf '%s\n' "$target"; return 0
  fi

  printf '%s\n' "$full"
}

# --- decide whether this tool call needs a red on record ---------------------
if [ "${TOOL:-}" = "Bash" ]; then
  [ -z "${COMMAND:-}" ] && exit 0

  # Cheap pre-filter, before any filesystem work: this hook now runs on every
  # Bash call in the session, and most of them write nothing.
  case "$COMMAND" in
    *">"*|*"sed -i"*|*"perl -i"*|*"tee "*|*cp\ *|*mv\ *|\
    *patch\ -p*|*"git apply"*|*open\(*|*write_text*|*writeFileSync*|*File.write*) ;;
    *) exit 0 ;;
  esac

  DETECTED=""

  # `patch` and `git apply` name their targets inside the diff, not on the
  # command line. They are known writers with an unknowable target, so they are
  # treated as enforced - the escape is the same as any other: record the red.
  case "$COMMAND" in
    *patch\ -p*|*"git apply"*) DETECTED="(the files named in the patch)" ;;
  esac

  if [ -z "$DETECTED" ]; then
    while IFS= read -r candidate; do
      [ -z "$candidate" ] && continue
      # A quoted target names the same file as an unquoted one, so the quotes
      # go before it is judged (`> "src/app.ts"`). Inside single quotes the
      # shell expands nothing, so `'$S/x'` is a literal path and is not
      # expanded.
      case "$candidate" in
        *\'*) candidate="${candidate//\'/}"
              candidate="${candidate//\"/}" ;;
        *) candidate="${candidate//\"/}"
           candidate="$(expand_command_variable "$candidate" "$COMMAND")" ;;
      esac
      [ -z "$candidate" ] && continue
      if is_enforced_path "$candidate"; then
        DETECTED="$candidate"
        break
      fi
    done <<CANDIDATES
$(bash_write_targets "$COMMAND")
CANDIDATES
  fi

  # Nothing recognisable is written → allow. See docs/safety-contract.md.
  [ -z "$DETECTED" ] && exit 0
  TARGET="$DETECTED"
else
  # No file path → nothing to enforce (e.g. a non-file tool). Allow.
  [ -z "${TARGET:-}" ] && exit 0
  is_enforced_path "$TARGET" || exit 0
fi


# Say when and how this project opted into Compass, if the record is there.
# `compass init` writes `initialised: {by, at}` into the project's state file,
# which project_settings.state reads. A user whose project was initialised by
# an entry point never ran init themselves, so an unexplained refusal is their
# first sight of Compass.
compass_say_how_this_project_opted_in() {
  # `|| return 0`: this only adds a sentence to a refusal already on its way.
  # A record that is missing, unreadable or the wrong shape adds nothing, and
  # a Python that cannot run must not end the script under `set -e`.
  _rec="$(compass_python - "$PROJECT_DIR" 2>/dev/null <<'PYEOF'
import sys
import compass_pkg
from compass_pkg import project_settings
try:
    rec = project_settings.state(sys.argv[1]).get("initialised")
except Exception:
    sys.exit(0)
if isinstance(rec, dict) and rec.get("by"):
    print(" ".join(str(rec["by"]).split()))
    print(" ".join(str(rec.get("at") or "").split()))
PYEOF
)" || return 0
  _by="$(printf '%s\n' "$_rec" | sed -n '1p')"
  _at="$(printf '%s\n' "$_rec" | sed -n '2p')"
  [ -n "$_by" ] || return 0
  if [ -n "$_at" ]; then
    echo "  This project was initialised by $_by on $_at, which is when it opted into Compass." >&2
  else
    echo "  This project was initialised by $_by, which is when it opted into Compass." >&2
  fi
}

# --- find the current issue -------------------------------------------------
# No .compass/ found: this repository never opted in, so allow (exit 0). A
# project exists but cannot be read: refuse (the branches below). This hook
# is installed at user scope - it runs in every repository on the machine -
# and .compass/ is the opt-in, created only by `compass init`, which the five
# entry-point commands run. A repository without it has genuinely never been
# asked, which is what makes exit 0 safe here rather than a guardrail
# switched off silently.
if [ "$PROJECT_RESOLVED" -eq 0 ]; then
  exit 0
fi

COMPASS_DIR="$PROJECT_DIR/.compass"
WORK_DIR="$COMPASS_DIR/work"

# An EXPLICIT root (CLAUDE_PROJECT_DIR) with no .compass/ is the same guest,
# reached by the other branch: the runtime sets CLAUDE_PROJECT_DIR in every
# repository, so its presence does not mean Compass is in use.
if [ ! -d "$COMPASS_DIR" ]; then
  exit 0
fi

if [ ! -d "$WORK_DIR" ]; then
  compass_say_how_this_project_opted_in
  compass_block not-initialised "detail=no .compass/work/ exists in $PROJECT_DIR"
fi

# The current issue is named by the .compass/current-task pointer (written by
# /compass:assess and /compass:resume). The pointer is what makes this
# reliable when more than one issue is in flight - "most recently changed
# directory" is only the fallback, and it is ambiguous, so it warns. If there
# is no issue at all, the assess stage has not run for this change, and the
# hook refuses below.
TASK_DIR=""
POINTER="$COMPASS_DIR/current-task"
# COMPASS_ISSUE names this session's issue ahead of the pointer. `compass
# run` sets it for each unattended session, whose edits must be judged by
# the run's issue, not by whatever issue the person's pointer names. A bad
# value is refused, never passed over for the pointer.
if [ -n "${COMPASS_ISSUE:-}" ]; then
  SLUG="$COMPASS_ISSUE"
  case "$SLUG" in
    .|..|*/*|*\\*)
      compass_block bad-session-issue "slug=$SLUG" ;;
  esac
  [ -d "$WORK_DIR/$SLUG" ] || compass_block bad-session-issue "slug=$SLUG"
  TASK_DIR="$WORK_DIR/$SLUG"
elif [ -f "$POINTER" ]; then
  SLUG="$(tr -d '[:space:]' < "$POINTER" 2>/dev/null || true)"
  # A slug is one path segment. `../side` would resolve outside the work
  # directory, and this hook would judge the edit by that directory's red.
  case "$SLUG" in
    .|..|*/*|*\\*)
      compass_block bad-current-task "slug=$SLUG" ;;
  esac
  if [ -n "$SLUG" ] && [ -d "$WORK_DIR/$SLUG" ]; then
    TASK_DIR="$WORK_DIR/$SLUG"
  fi
fi
# Another session may have moved the pointer since this one last edited
# (session_lease.py). Only when the pointer named the issue: COMPASS_ISSUE
# names one session's issue, and the fallback names none.
if [ -z "${COMPASS_ISSUE:-}" ] && [ -n "${SESSION_ID:-}" ] && [ -n "$TASK_DIR" ]; then
  LEASE_ERR="$(mktemp 2>/dev/null)" || compass_reader_failed "session lease reader" tmp
  set +e
  LEASE="$(compass_python - "$COMPASS_DIR" "$SESSION_ID" "$SLUG" 2>"$LEASE_ERR" <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.session_lease import check

print(check(*sys.argv[1:]))
PYEOF
)"
  LEASE_STATUS=$?
  set -e
  # Fails closed: a lease check that cannot run refuses, as every reader
  # in this hook does.
  [ "$LEASE_STATUS" -eq 0 ] || compass_reader_failed "session lease reader" "$LEASE_STATUS" "$LEASE_ERR"
  rm -f "$LEASE_ERR"
  case "$LEASE" in
    moved:*)
      # Counted against the issue this session works on, not the pointer's,
      # when the recorded name is one path segment: it was read from a file.
      PREV="${LEASE#moved:}"
      case "$PREV" in
        ""|.|..|*/*|*\\*) ;;
        *) [ -d "$WORK_DIR/$PREV" ] && TASK_DIR="$WORK_DIR/$PREV" ;;
      esac
      compass_block pointer-moved "slug=$SLUG" "previous=${LEASE#moved:}" ;;
  esac
fi
if [ -z "$TASK_DIR" ]; then
  # fallback: most recently changed - ambiguous, so say so.
  TASK_DIR="$(ls -dt "$WORK_DIR"/*/ 2>/dev/null | head -n1 || true)"
  TASK_DIR="${TASK_DIR%/}"
  [ -n "$TASK_DIR" ] && echo "Compass: no .compass/current-task pointer - falling back to the most recently modified issue ($(basename "$TASK_DIR")). Run compass issue use <slug> to be unambiguous." >&2
fi

if [ -z "${TASK_DIR:-}" ]; then
  compass_say_how_this_project_opted_in
  compass_block not-initialised "detail=no issue exists under $PROJECT_DIR/.compass/work/"
fi

TASK_SLUG="$(basename "$TASK_DIR")"

# The delivery-approach record must exist - code work without a computed
# approach is process laundering.
#
# ASKED, NOT GUESSED. The record may sit beside the manifest or under
# `docs/compass/<created>-<slug>/`, and which one is a property of the issue's
# artifact registry rather than of the filename. Testing for a file beside the
# manifest was right until documents could move; after that it reads "the
# record is missing" for every migrated issue and blocks EVERY code edit in the
# project. So the resolver answers, and it is the same resolver `compass check`
# uses - a second implementation in bash is how the two halves stop agreeing.
#
# Both filename generations still resolve: the resolver falls back to the
# retired name for an archive that predates the artifact rename, and to the
# flat filename for an issue that has not migrated.
#
# The answer is printed and the status only says whether the reader ran, so a
# crash cannot read as "no record" - that would send the user to re-assess
# when the install is what is broken.
ROUTE_PROBE_ERR="$(mktemp 2>/dev/null)" \
  || compass_reader_failed "delivery-approach reader" tmp
set +e
ROUTE_PROBE="$(compass_python - "$TASK_DIR" 2>"$ROUTE_PROBE_ERR" <<'PYEOF'
import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.core import FOUND, resolve_artifact
state, _path, _reason = resolve_artifact(sys.argv[1], "delivery-approach")
print("found" if state == FOUND else "absent")
PYEOF
)"
ROUTE_PROBE_STATUS=$?
set -e
if [ "$ROUTE_PROBE_STATUS" -ne 0 ] || [ -z "$ROUTE_PROBE" ]; then
  compass_reader_failed "delivery-approach reader" "$ROUTE_PROBE_STATUS" "$ROUTE_PROBE_ERR"
fi
rm -f "$ROUTE_PROBE_ERR"
if [ "$ROUTE_PROBE" != "found" ]; then
  compass_block no-delivery-approach "slug=$TASK_SLUG"
fi

# --- approach-aware: red-before-green is suspended on a spike ----------------
# /compass:assess writes a .spike marker when it computes a spike. On a
# spike, exploratory edits are not blocked - the red-before-green strategy is
# suspended. The tested-before-ship guardrail is NOT: nothing ships from a
# spike without being reassessed (`/compass:assess --reassess`) into a
# delivery approach, where this hook applies in full.
if [ -f "$TASK_DIR/.spike" ]; then
  exit 0
fi

# --- the guardrail: acceptance defined before it is built --------------------
# This check enforces the acceptance-before-code guardrail before the code
# exists. `compass check` sees the same gap only at the verify stage, after
# the code is written.
#
# A guardrail beats a strategy, so this runs BEFORE the red check: you cannot
# write a red for a scenario that does not exist yet.
#
# Only `define: thorough` (or the retired `specify: full`, or `define: full`
# from before the depth words were renamed) triggers it, which
# routing-policy.yml gives to the regular and full approaches. A hotfix
# (reproduce-first) and a spike (collapsed) are exempt by construction, and
# the .spike early exit above suspends this the same way it suspends
# red-before-green.
#
# A false block on unreadable state is how a hook teaches people to bypass it,
# so if there is no manifest.yml, or its YAML does not parse, the hook skips
# this check and goes on to the red check. A reader that cannot RUN is
# different - no python3, a broken install - and refuses.
if [ -f "$TASK_DIR/manifest.yml" ]; then
  # Two failures look alike from here and must not be treated alike. A reader
  # that RAN and found nothing is ordinary - stay quiet, as below. A reader
  # that could not RUN means the install is broken, and a guardrail that
  # cannot read its own state must refuse rather than wave the edit through.
  G2_ERR="$(mktemp 2>/dev/null)" \
    || compass_reader_failed "acceptance-criteria reader" tmp
  set +e
  G2_VERDICT="$(compass_python - "$TASK_DIR/manifest.yml" 2>"$G2_ERR" <<'PYEOF'
import sys
import compass_pkg
from compass_pkg import stable_ids, word_map
try:
    import yaml
    with open(sys.argv[1], encoding="utf-8") as fh:
        task = yaml.safe_load(fh) or {}
    if not isinstance(task, dict):
        raise ValueError
except Exception:
    # Exit 0 means ALLOW, and that is deliberate: an unreadable or missing
    # manifest falls back to the behaviour this hook had before the check
    # existed, rather than inventing a block. A false block on unreadable
    # state trains people to bypass the hook, which costs more than the case
    # it would catch. Pinned by
    # tests/test_hook_enforces_g2.py::test_scn_f1_an_unreadable_spine_does_not_block.
    # Any non-zero status below is the check being unable to RUN (a broken
    # install), which is a different thing from the manifest being
    # unreadable.
    sys.exit(0)
stages = task.get("stages") or task.get("phases") or {}
# Read both: `define` is the current key, and archived manifests still carry
# the pre-v2 `specify`. Reading one key only would switch the guardrail off
# for every migrated manifest.
if isinstance(stages, dict):
    weight = stages.get("define", stages.get("specify"))
    # The mode is read through the retired-word table, so a manifest written
    # before the depth words were renamed (`full`) and one written after
    # (`thorough`) both enforce. Comparing the raw value with one word would
    # stop matching the other with no error, and the guardrail would be off.
    weight = word_map.map_manifest({"stages": {"define": weight}})["stages"]["define"]
    if weight == stable_ids.MODE_THOROUGH and not (task.get("scenarios") or []):
        print("block")
        sys.exit(0)
# The issues this one waits for (ADR-062). Only this reader has the manifest
# parsed already, so it says whether the dependency reader below needs to run:
# an issue with no `depends_on`, or an empty one, starts no process for it. A
# value that is not a list says so too, so the dependency reader can warn.
if task.get("depends_on") not in (None, []):
    print("depends")
PYEOF
)"
  G2_STATUS=$?
  set -e
  # Refuse on every non-zero status, with the reader's own stderr as the
  # cause. A test exercising this check's success path also needs a `.red`
  # marker in place, because the red-before-green check further down still
  # runs and refuses without one.
  if [ "$G2_STATUS" -ne 0 ]; then
    compass_reader_failed "acceptance-criteria reader" "$G2_STATUS" "$G2_ERR"
  fi
  rm -f "$G2_ERR"
  if [ "${G2_VERDICT:-}" = "block" ]; then
    compass_block no-acceptance-criteria "target=$TARGET" "tool=${TOOL:-?}"
  fi
fi

# --- the issues this one waits for (ADR-062) ----------------------------------
# An issue at implement whose `depends_on` names an issue that has not reached
# its `until` is refused here, before the declared-acceptance exit below, so a
# declared acceptance does not clear a wait. The spike exit above comes first,
# so a spike is never refused for a dependency.
#
# The reader reads each dependency's manifest from this checkout, uncached, and
# runs no git command (lifecycle.hook_lines). It refuses only on a positive
# read of an unmet dependency. A dependency it cannot judge - no manifest here,
# one that does not parse, an unknown `until`, an entry of the wrong shape, a
# dependency that waits for this issue in turn - allows the edit with one
# warning line, because a false block teaches people to bypass the hook; lint
# reports the same fault. A reader that cannot run at all refuses, as every
# reader in this hook does.
if [ "${G2_VERDICT:-}" = "depends" ]; then
  DEP_ERR="$(mktemp 2>/dev/null)" \
    || compass_reader_failed "dependency reader" tmp
  set +e
  DEP_LINES="$(compass_python - "$TASK_DIR" 2>"$DEP_ERR" <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import lifecycle

for line in lifecycle.hook_lines(sys.argv[1]):
    print(line)
PYEOF
)"
  DEP_STATUS=$?
  set -e
  if [ "$DEP_STATUS" -ne 0 ]; then
    compass_reader_failed "dependency reader" "$DEP_STATUS" "$DEP_ERR"
  fi
  rm -f "$DEP_ERR"
  # `warn <text>` lines go to stderr; at most one `wait` line follows, its
  # fields separated by tabs because a state can hold a space.
  DEP_WAIT=""
  while IFS= read -r DEP_LINE; do
    case "$DEP_LINE" in
      "warn "*) printf '%s\n' "${DEP_LINE#warn }" >&2 ;;
      wait*) DEP_WAIT="$DEP_LINE" ;;
    esac
  done <<DEPEOF
$DEP_LINES
DEPEOF
  if [ -n "$DEP_WAIT" ]; then
    IFS="$(printf '\t')" read -r _ DEP_ISSUE DEP_UNTIL DEP_STATE DEP_MORE <<DEPEOF
$DEP_WAIT
DEPEOF
    compass_block waits-for-issue "slug=$TASK_SLUG" "target=$TARGET" "tool=${TOOL:-?}" \
      "dependency=$DEP_ISSUE" "until=$DEP_UNTIL" "state=$DEP_STATE" "more=${DEP_MORE:-}"
  fi
fi

# --- a declared acceptance (config / docs / behaviour-preserving refactor) ---
# Some legitimate changes have no natural behavioural red - a compose limit, a
# Prometheus rule, a runbook, a dead-code removal. `compass acceptance start`
# declares what the acceptance IS before the change (a validator that must pass,
# or a green suite that must stay green) and writes this marker. Without it,
# the only way past this hook is a fake red, such as a test that greps a file
# for a string.
#
# It is a SEPARATE marker on purpose. `.red` means "a real failure was observed
# here"; overloading it would make the framework's most honest artifact
# ambiguous. `compass acceptance record` clears this one.
if [ -f "$TASK_DIR/.acceptance" ]; then
  exit 0
fi

# --- the red-before-green check (delivery work) -----------------------------
# `.red` is an empty file that `touch` can create, so the marker alone proves
# nothing. The hook checks the marker first because it is cheap - this hook
# runs on every tool call, and globbing plus parsing JSON on each one is a
# constant cost - then reads the record in evidence/ to decide.
#
# WHAT THIS DOES AND DOES NOT BUY. `content_digest` is a plain sha256 over the
# record's own fields with no secret, so anyone who can write the file can
# compute a matching digest. This catches a record EDITED after it was
# written; it does not catch one FABRICATED wholesale by someone who knows the
# format. Forging goes from `touch` to writing plausible JSON with a correct
# digest - a different order of deliberateness, not an impossibility.
# docs/safety-contract.md states both halves.
#
# A record with no digest at all counts only when the project declares no
# `records_signed_since` date, or when the record's own timestamp is earlier.
if [ -f "$TASK_DIR/.red" ]; then
  # `set +e` around the reader: under `set -e` a reader that exits non-zero
  # would end this script with exit 1, which the runtime treats as a
  # non-blocking error and lets the edit through. The status is checked below
  # and a failed reader refuses.
  set +e
  RED_ERR="$(mktemp 2>/dev/null)" \
    || compass_reader_failed "red-record reader" tmp
  RED_VERDICT="$(compass_python - "$TASK_DIR" "$COMPASS_DIR" <<'PYEOF' 2>"$RED_ERR"
# One verdict, shared with `suite-passed`, so the hook and the check cannot
# disagree about what counts as a red. red_first.py documents each word.
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.red_first import verdict_line

print(verdict_line(sys.argv[1], sys.argv[2]))
PYEOF
)"
  RED_STATUS=$?
  set -e

  if [ "$RED_STATUS" -ne 0 ] || [ -z "${RED_VERDICT:-}" ]; then
    compass_reader_failed "red-record reader" "$RED_STATUS" "$RED_ERR"
  fi
  rm -f "$RED_ERR"

  if [ "$RED_VERDICT" = "ok" ]; then
    # An observed failure is on record for this issue. Red came before green.
    exit 0
  fi

  case "$RED_VERDICT" in
    unsigned*)
      compass_block red-unsigned "slug=$TASK_SLUG" \
        "since_date=${RED_VERDICT#unsigned }" ;;
  esac

  compass_block red-marker-no-record "slug=$TASK_SLUG"
fi

# No .red marker → no failing test on record → block the code edit.
compass_block no-red-on-record "slug=$TASK_SLUG" "target=$TARGET" "tool=${TOOL:-?}" \
  "guard=${MATCHED_RULE:-the built-in production-code set}"
