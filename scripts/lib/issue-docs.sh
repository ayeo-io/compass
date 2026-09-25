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
# nothing and returns 1 when the document is not there.
#
# SOURCING THIS FILE HAS NO SIDE EFFECT - it only defines the function below.
# =============================================================================

issue_doc_path() {
  local slug="$1" kind="$2"
  local lib_dir compass_home project_dir out fallback

  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  compass_home="$(cd "$lib_dir/../.." && pwd)"
  project_dir="$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || pwd)"

  # shellcheck source=compass-python.sh
  source "$lib_dir/compass-python.sh"

  # The resolver itself, run through compass_python rather than a bare
  # `compass`: a bare command can resolve to an installed plugin copy that
  # knows nothing about this project's worktree.
  if out="$(cd "$project_dir" && compass_python "$compass_home/cli/compass" \
      issue artifact-path "$kind" --issue "$slug" 2>/dev/null)"; then
    printf '%s\n' "$out"
    return 0
  fi

  # An issue whose documents predate the artifact registry keeps them flat
  # under .compass/work/<slug>/. The resolver above already tries that
  # layout first; this is a second, independent check for the same file, so
  # a caller never trusts one broken read as the only word on where a
  # document is.
  fallback="$project_dir/.compass/work/$slug/$kind.md"
  if [ -f "$fallback" ]; then
    printf '%s\n' "$fallback"
    return 0
  fi
  return 1
}
