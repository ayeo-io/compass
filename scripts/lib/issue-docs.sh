#!/usr/bin/env bash
# =============================================================================
# Compass library: issue-docs.sh  -  FIND ONE OF AN ISSUE'S DOCUMENTS
# =============================================================================
# multiagent.sh and integrate.sh both need to know where one of an issue's
# documents is before they can read it. A document used to live only at
# .compass/work/<slug>/<kind>.md; some now live at the path recorded in
# manifest.yml's `artifacts:` list, usually under
# docs/compass/<created>-<slug>/. One lookup, shared by both scripts, so the
# shell and the resolver never come to disagree about where a document is.
#
# `issue_doc_path <slug> <kind>` prints the path and returns 0, or prints
# nothing, reports why on stderr, and returns 1 when the document is not
# there.
#
# SOURCING THIS FILE HAS NO SIDE EFFECT - it only defines the function below.
# =============================================================================

issue_doc_path() {
  local slug="$1" kind="$2"
  local lib_dir compass_home project_dir out err_file err fallback

  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  compass_home="$(cd "$lib_dir/../.." && pwd)"
  project_dir="$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || pwd)"

  # shellcheck source=compass-python.sh
  source "$lib_dir/compass-python.sh"

  # The resolver itself, run through compass_python rather than a bare
  # `compass`: a bare command can resolve to an installed plugin copy that
  # knows nothing about this project's worktree. Its stderr is captured,
  # not discarded - a reader that could not start and a reader that ran and
  # found nothing are different failures, and only the second is silent.
  err_file="$(mktemp 2>/dev/null || printf '%s' "/tmp/issue-doc-path.$$")"
  if out="$(cd "$project_dir" && compass_python "$compass_home/cli/compass" \
      issue artifact-path "$kind" --issue "$slug" 2>"$err_file")"; then
    rm -f "$err_file"
    printf '%s\n' "$out"
    return 0
  fi
  err="$(cat "$err_file" 2>/dev/null)"
  rm -f "$err_file"

  # The resolver ran to a definitive answer of the shape
  # "compass: <kind>: <state> (<reason>)" - see resolve_artifact() in
  # cli/compass_pkg/core.py. Only ABSENT - no registry entry for this kind,
  # and the resolver's own flat-file check already found nothing either -
  # gets a second, independent look at the flat layout below. REFUSED,
  # OMITTED and UNRESOLVABLE all mean a registry entry exists and the
  # resolver has already ruled on it; rescuing those here with the file
  # beside the manifest would mean the ruling only ever fires when a
  # fallback already agrees there is nothing to find - a check that cannot
  # fail.
  case "$err" in
    "compass: $kind: absent "*)
      fallback="$project_dir/.compass/work/$slug/$kind.md"
      if [ -f "$fallback" ]; then
        printf '%s\n' "$fallback"
        return 0
      fi
      ;;
  esac

  # Anything else - refused, omitted, unresolvable, or the resolver could
  # not even run (a Python traceback, not a CompassError) - is reported to
  # the caller, not swallowed. A crash reported as "not there" blames the
  # wrong stage.
  if [ -n "$err" ]; then
    echo "issue_doc_path: $err" >&2
  else
    echo "issue_doc_path: the resolver for '$kind' produced no output." >&2
  fi
  return 1
}

# `map_row_problem <subtask id> <branch>` prints why a distribution map's row
# must be refused, or nothing when it is fine. Both scripts build a worktree
# path from the id and pass the branch to git, so neither may carry a path
# separator, a `..`, or a leading `-` that git would read as an option.
map_row_problem() {
  local sid="$1" branch="$2"
  case "$sid" in
    subtask-*|stream-*) ;;  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
    *) echo "subtask id '$sid' is not subtask-<name>"; return 0 ;;
  esac
  # After the prefix: letters, digits, spaces, `.`, `_`, `(`, `)` and `-`,
  # and never `..` - an id such as `subtask-1`, `subtask-A-docs` or
  # `subtask-1 (wave 2)`, as maps already in use write them. Paths built from
  # it are quoted, so a space is safe; a `/` or `..` would leave the
  # worktree root.
  local rest="${sid#*-}"
  case "$rest" in
    ''|*..*|*[!A-Za-z0-9\ ._\(\)-]*)
      echo "subtask id '$sid' is not subtask-<name>, with letters, digits, spaces, '.', '_', '(', ')' or '-' after it and no '..'"
      return 0 ;;
  esac
  case "$branch" in
    -*) echo "branch '$branch' for $sid starts with '-', which git reads as an option"; return 0 ;;
  esac
  if ! git check-ref-format --branch "$branch" >/dev/null 2>&1; then
    echo "branch '$branch' for $sid is not a name git accepts for a branch"
  fi
  return 0
}
