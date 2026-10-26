# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: resolve the project, and record the session on the issue.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

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
#
# `pwd` fails in a removed directory, and under `set -e` that ended the hook
# with exit 1, which the runtime reads as non-blocking: the call ran unchecked.
# On a failure the hook enters CLAUDE_PROJECT_DIR (else /) so the readers below
# start in a folder that exists, and CWD_GONE lets the refusal further down
# fire when no project variable names the project.
CWD_GONE=0
if ! { SESSION_DIR="$(pwd 2>/dev/null)" && [ -d "$SESSION_DIR" ]; }; then
  CWD_GONE=1
  SESSION_DIR="${CLAUDE_PROJECT_DIR:-/}"
  [ -d "$SESSION_DIR" ] || SESSION_DIR=/
  cd "$SESSION_DIR" 2>/dev/null || cd /
fi

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
  find_compass_root "$INVOKED_FROM"
  PROJECT_DIR="$FOUND_ROOT"
  if [ -z "$PROJECT_DIR" ]; then
    PROJECT_RESOLVED=0
    # Provisional, so path classification still has something to compare
    # against. Nothing is permitted on the strength of it.
    PROJECT_DIR="$INVOKED_FROM"
  fi
}

# Sets FOUND_ROOT to the nearest ancestor of $1 (or $1 itself) that holds a
# .compass/ folder, or "" when there is none before the repository root.
find_compass_root() {
  local search="$1" parent
  FOUND_ROOT=""
  while [ -n "$search" ]; do
    if [ -d "$search/.compass" ]; then
      FOUND_ROOT="$search"
      break
    fi
    # Stop at the repository root. A walk past it can reach another
    # project's .compass/ (a monorepo sibling, a stray one in $HOME) and
    # allow the edit if that issue has a red on record.
    #
    # -e, not -d: in a git worktree .git is a file, and Compass creates
    # worktrees itself for multiagent orchestrations.
    [ -e "$search/.git" ] && break
    [ "$search" = "/" ] && break
    # A relative path ends at "." and the parent of "." is ".", so stop
    # when the parent is the path itself.
    parent="$(dirname "$search")"
    [ "$parent" = "$search" ] && break
    search="$parent"
  done
}

# Sets REAL_DIR to the real path of directory $1, or "" when it cannot be
# entered. The comparison of two projects is on real paths, so a symbolic link
# to the session's project is still the session's project.
real_dir() {
  REAL_DIR="$(CDPATH= cd -- "$1" 2>/dev/null && pwd -P)" || REAL_DIR=""
}

# Prints the real path of the git common directory of directory $1; fails when
# git cannot read it. A main working tree prints a path relative to $1. The
# GIT_* variables are removed so a session's own settings cannot point git at
# another repository.
git_common_dir() {
  local out
  out="$(unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR
         git -C "$1" rev-parse --git-common-dir 2>/dev/null)" || return 1
  [ -n "$out" ] || return 1
  case "$out" in /*) ;; *) out="$1/$out" ;; esac
  real_dir "$out"
  [ -n "$REAL_DIR" ] || return 1
  printf '%s\n' "$REAL_DIR"
}

# Whether the foreign project is a tree of the session's repository: both git
# common directories are readable and equal. Any other result is "no", so the
# caller refuses. Computed once, because the session record and the issue
# block both need it. This is a consistency check, not a defence against a
# forged .git file: an edit inside a forged folder is not an edit of the
# project's code.
TIED=""
tied_to_session_repo() {
  if [ -z "$TIED" ]; then
    TIED=0
    local mine theirs
    if mine="$(git_common_dir "$PROJECT_DIR")" && [ -n "$mine" ]; then
      # -ef compares the folders on disk, so a case-insensitive file system
      # does not make two spellings of one folder differ.
      if theirs="$(git_common_dir "$SESSION_ROOT")" && [ "$mine" -ef "$theirs" ]; then
        TIED=1
      fi
    fi
  fi
  [ "$TIED" = 1 ]
}

# FOREIGN=1 when the project found from the edited path is not the session's
# own. The session's project is the Compass root found by walking up from
# CLAUDE_PROJECT_DIR, so a session started in a sub-folder is not foreign.
# A session with no Compass project is never foreign: the hook is installed
# at user scope, and such a session has no issue to borrow. When the text of
# both paths is equal, as for every Bash call, nothing else runs.
FOREIGN=0
SESSION_ROOT=""
classify_foreign() {
  [ "${PROJECT_RESOLVED:-0}" -eq 1 ] || return 0
  [ -n "${CLAUDE_PROJECT_DIR:-}" ] || return 0
  [ "$PROJECT_DIR" != "$CLAUDE_PROJECT_DIR" ] || return 0
  find_compass_root "$CLAUDE_PROJECT_DIR"
  [ -n "$FOUND_ROOT" ] || return 0
  SESSION_ROOT="$FOUND_ROOT"
  [ "$PROJECT_DIR" != "$SESSION_ROOT" ] || return 0
  # -ef compares the folders on disk, so a case-insensitive file system
  # does not make two spellings of one folder differ. A folder that cannot
  # be entered is foreign.
  if ! { [ -d "$SESSION_ROOT" ] && [ -d "$PROJECT_DIR" ] \
         && [ "$SESSION_ROOT" -ef "$PROJECT_DIR" ]; }; then
    FOREIGN=1
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

# An Edit or Write whose project is not the session's own (a foreign project,
# such as a sibling git worktree) is judged by that project's issue, not the
# session's: its pointer decides, COMPASS_ISSUE only stands in for an empty
# pointer, the most-recently-changed guess and the pointer-moved check are not
# used, and the tree must be tied to the session's repository.
classify_foreign

# --- record the session on the issue (usage.sessions) ------------------------
# `compass ship-commit` reads the transcripts of every session that worked on
# an issue, so the hook notes each session id in the issue's manifest the
# first time it sees one. It runs before the path classification, so a
# document write and a Bash call are recorded too.
#
# The issue comes from COMPASS_ISSUE or the pointer only, read in shell: with
# neither, nothing is recorded, and the most recently changed issue is never
# guessed. In a foreign project the selection is the one the guard below
# uses: the tree must be tied to the session's repository, the pointer comes
# first and COMPASS_ISSUE only stands in for an empty pointer, and the issue
# is recorded with via=tree so the session table is not read. An id already
# recorded costs one `grep` and no python3 process; a new one starts one,
# which tries the manifest lock once without waiting
# (cli/compass_pkg/session_record.py). This never refuses a call: every
# fault, a bad id or a recorder that cannot run returns 0 with its output
# discarded, and the checks below judge the call as before. A broken install
# still refuses through those checks.
compass_record_session() {
  [ "${PROJECT_RESOLVED:-0}" -eq 1 ] || return 0
  case "${SESSION_ID:-}" in ""|*[!A-Za-z0-9_-]*) return 0 ;; esac
  local slug="" via="pointer" pointer="$PROJECT_DIR/.compass/current-task"
  if [ "${FOREIGN:-0}" -eq 1 ]; then
    tied_to_session_repo || return 0
    via="tree"
    if [ -f "$pointer" ]; then
      IFS= read -r slug < "$pointer" || true
      slug="${slug//[[:space:]]/}"
    fi
    [ -n "$slug" ] || slug="${COMPASS_ISSUE:-}"
  elif [ -n "${COMPASS_ISSUE:-}" ]; then
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
  compass_python "$HOOK_ROOT/hooks/py/pre_tool_record_session.py" "$folder" "$SESSION_ID" "$via" >/dev/null 2>&1 </dev/null || true
  return 0
}
set +e
compass_record_session
set -e
