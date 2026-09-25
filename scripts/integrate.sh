#!/usr/bin/env bash
# =============================================================================
# Compass script: integrate.sh  -  LAND THE WORKTREES BACK TOGETHER
# =============================================================================
# The ship-stage counterpart to multiagent.sh. It merges the per-subtask branches
# back into the base branch in a coordinated order, runs the project's test
# command for combined regression, reports any conflicts for the `orchestrator`
# to resolve, and cleans up the worktrees on success. Only the `orchestrator`
# agent runs this (the lead builder on a pair) - see CLAUDE.md and the
# worktree-multiagent skill.
#
# USAGE
#   scripts/integrate.sh <issue-slug>             # integrate every subtask
#   scripts/integrate.sh <issue-slug> --no-clean  # integrate but keep worktrees
#   scripts/integrate.sh --help
#
# ORDER
#   Subtasks are merged in the order they appear in distribution-map.md §3.
#   The map must list shared foundations first (subtask-zero pattern, see the
#   worktree-multiagent skill) so dependents merge onto a base that already
#   has what they need.
#
# CONFLICTS
#   A conflict confined to Compass's own records - any path under .compass/
#   or docs/compass/ - is resolved on the spot: the base branch's side wins
#   (its deletion counts as its side too), the merge completes, and the
#   script names which file it kept or removed. Any other conflict is NOT
#   auto-resolved: the merge aborts, the repo is left clean, and the script
#   reports exactly which subtask and which files conflicted, then stops.
#   Resolving a cross-subtask conflict outside Compass's own records is the
#   orchestrator's job and no one else's - the script just surfaces it. If
#   resolving a records-only conflict itself fails part way (a commit hook
#   rejects it, say), the merge is aborted the same way - nothing is ever
#   left half done.
#
#   A merge git refuses to even start (e.g. an untracked file at a path the
#   merge would write) is not a conflict - no MERGE_HEAD exists, so there is
#   nothing to abort. The script reports git's own reason and stops.
#
# STARTING CLEAN
#   integrate.sh refuses to start when a tracked file has an uncommitted
#   change. An untracked file does not block the start - git itself already
#   refuses a merge that would overwrite one, so this script does not
#   duplicate that check.
#
# COMBINED REGRESSION
#   After all subtasks merge cleanly, the project's test command runs once
#   against the integrated result. Per-subtask green does not imply integrated
#   green - proving the combination is the whole point of ship. If combined
#   regression fails, worktrees are NOT cleaned up (you will need them) and the
#   script exits non-zero.
#
# IDEMPOTENT & SAFE
#   - A branch already merged is detected and skipped.
#   - Worktrees are only removed after both a clean merge AND green combined
#     regression. --no-clean keeps them regardless.
#   - On any failure the working tree is left in a clean, inspectable state.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || pwd)"

# shellcheck source=lib/compass-python.sh
source "$SCRIPT_DIR/lib/compass-python.sh"
source "$SCRIPT_DIR/lib/issue-docs.sh"

# --- args -------------------------------------------------------------------
TASK_SLUG=""
CLEAN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-clean) CLEAN=0 ;;
    -h|--help)  grep -E '^# (USAGE|  scripts)' "$0" | sed 's/^# //'; exit 0 ;;
    -*) echo "integrate.sh: unknown flag: $1" >&2; exit 1 ;;
    *)  TASK_SLUG="$1" ;;
  esac
  shift
done
[ -n "$TASK_SLUG" ] || { echo "integrate.sh: need an issue slug. See --help." >&2; exit 1; }

TASK_DIR="$PROJECT_DIR/.compass/work/$TASK_SLUG"
CONFIG="$PROJECT_DIR/.compass/config.yml"

# The map is found through the artifact registry, so an issue whose
# documents moved to docs/compass/<created>-<slug>/ still resolves, and an
# issue whose map is still flat under .compass/work/<slug>/ works as before.
# issue_doc_path already reports WHY a lookup failed on stderr.
MAP="$(issue_doc_path "$TASK_SLUG" distribution-map)" \
  && [ -f "$MAP" ] \
  || { echo "integrate.sh: no distribution-map.md for '$TASK_SLUG'." >&2; exit 1; }

# --- repo sanity: must start clean ------------------------------------------
git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "integrate.sh: $PROJECT_DIR is not a git repository." >&2; exit 1; }
# Tracked files only - an untracked file does not block the start. Git
# itself already refuses a merge that would overwrite one, and that is the
# only case an untracked file needs to matter for.
if [ -n "$(git -C "$PROJECT_DIR" status --porcelain --untracked-files=no)" ]; then
  echo "integrate.sh: working tree has uncommitted changes - commit or stash before integrating." >&2
  exit 1
fi
BASE_BRANCH="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)"

# --- config: worktree_root --------------------------------------------------
read_cfg() {
  local v=""
  [ -f "$CONFIG" ] && v="$(grep -E "^[[:space:]]*$1:" "$CONFIG" 2>/dev/null \
      | head -n1 | sed -E 's/^[^:]*:[[:space:]]*//; s/[[:space:]]*#.*$//; s/^"//; s/"$//')"
  echo "${v:-$2}"
}
WORKTREE_ROOT_REL="$(read_cfg 'worktree_root' '../.compass-worktrees')"
case "$WORKTREE_ROOT_REL" in
  /*) WORKTREE_ROOT="$WORKTREE_ROOT_REL" ;;
  *)  WORKTREE_ROOT="$PROJECT_DIR/$WORKTREE_ROOT_REL" ;;
esac

# --- find the subtask table's own header row (same shape as multiagent.sh) --
# A map can carry more than one markdown table; only the table whose rows
# carry a subtask id governs merging, so "Branch name" must be read from
# THAT table's header, not any other table's or a fixed cell position - a
# Wave column placed ahead of it (multiagent.sh's staged-map columns) would
# otherwise shift what this script reads as the branch and silently skip
# the subtask (see multiagent.sh's own header-finding block for why).
PENDING_HEADER=""
SUBTASK_HEADER=""
while IFS= read -r line; do
  case "$line" in \|*) ;; *) continue ;; esac
  case "$(echo "$line" | tr -d '|:- ')" in '') continue ;; esac
  IFS='|' read -r -a _hdr_cells <<<"$line"
  _hdr_cell1="$(echo "${_hdr_cells[1]:-}" | xargs 2>/dev/null || true)"
  case "$_hdr_cell1" in
    subtask-*|stream-*)  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
      [ -n "$SUBTASK_HEADER" ] || SUBTASK_HEADER="$PENDING_HEADER"
      ;;
    *)
      PENDING_HEADER="$line"
      ;;
  esac
done < "$MAP"

# Position 4 is the template's usual "Branch name" cell, kept as the
# default for a hand-filled map whose header text does not match exactly.
BRANCH_COL=4
if [ -n "$SUBTASK_HEADER" ]; then
  IFS='|' read -r -a _hdr_cells <<<"$SUBTASK_HEADER"
  for _idx in "${!_hdr_cells[@]}"; do
    _cell="$(echo "${_hdr_cells[$_idx]}" | xargs 2>/dev/null || true)"
    case "$_cell" in
      "Branch name") BRANCH_COL="$_idx" ;;
    esac
  done
fi

# --- parse subtasks + branches (same parser shape as multiagent.sh) ---------------
SUBTASKS=(); BRANCHES=()
while IFS= read -r line; do
  # A map written before ADR-023 says stream-N. Read both (ADR-006).  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  case "$line" in \|*subtask-*|\|*stream-*) ;; *) continue ;; esac  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  IFS='|' read -r -a _row_cells <<<"$line"
  sid="$(echo "${_row_cells[1]:-}" | xargs 2>/dev/null || true)"
  branch="$(echo "${_row_cells[$BRANCH_COL]:-}" | xargs 2>/dev/null | sed -E 's/^[`*]+//; s/[`*]+$//' || true)"
  case "$sid" in subtask-*|stream-*) ;; *) continue ;; esac  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  [ -n "$branch" ] || branch="compass/$TASK_SLUG/$sid"
  SUBTASKS+=("$sid"); BRANCHES+=("$branch")
done < "$MAP"

if [ "${#SUBTASKS[@]}" -eq 0 ]; then
  echo "integrate.sh: no subtasks in distribution-map.md. If the route is solo," >&2
  echo "              ship integrates with a plain commit - integrate.sh is not needed." >&2
  exit 1
fi

# --- discover the project test command (for combined regression) ------------
TEST_CMD="$(read_cfg 'test_command' '')"
if [ -z "$TEST_CMD" ] && [ -f "$PROJECT_DIR/package.json" ] \
   && grep -q '"test"' "$PROJECT_DIR/package.json" 2>/dev/null; then
  TEST_CMD="npm test"
fi
if [ -z "$TEST_CMD" ] && [ -f "$PROJECT_DIR/Makefile" ] \
   && grep -qE '^test:' "$PROJECT_DIR/Makefile" 2>/dev/null; then
  TEST_CMD="make test"
fi

echo "Compass integrate - issue '$TASK_SLUG'"
echo "  base branch:   $BASE_BRANCH"
echo "  subtasks:       ${#SUBTASKS[@]}  (merged in map order)"
echo "  test command:  ${TEST_CMD:-<none resolved - combined regression cannot run automatically>}"
echo ""

# Every conflicted path is one of Compass's own records: anything under
# .compass/ or docs/compass/, and nothing else. The match is a path prefix,
# not a substring, so a look-alike name such as .compass-worktrees/ - a
# builder's live checkout, not a record this script keeps - does not slip
# through: it is a sibling directory outside the repository, so it never
# reaches this check, and even a tracked file with that name at the repo
# root is refused rather than resolved. Reads the list from stdin, one path
# per line.
_all_paths_are_compass_records() {
  local line all_compass=1
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    case "$line" in
      .compass/*|docs/compass/*) ;;
      *) all_compass=0 ;;
    esac
  done
  [ "$all_compass" -eq 1 ]
}

# A conflicted path under .compass/ or docs/compass/ can still be the
# DESTINATION of a rename whose SOURCE sat outside both - a builder who
# moved source code into the records tree and edited it, while the base
# branch edited the original path too. git reports the conflict at the
# destination, which would otherwise read as records-only. Renames are
# looked up in both directions - either side of the merge can be the one
# that moved the file - filtered to R (git diff's rename status); the
# threshold is git's default (-M with no percentage). A match whose
# source is itself outside .compass/ and docs/compass/ means the
# conflicting work began outside the records tree, so the whole conflict
# must abort like any other cross-subtask one, not resolve on the spot.
_rename_into_records_has_outside_source() {
  local dest="$1" range status old new
  for range in "HEAD...MERGE_HEAD" "MERGE_HEAD...HEAD"; do
    while IFS=$'\t' read -r status old new; do
      case "$status" in R*) ;; *) continue ;; esac
      [ "$new" = "$dest" ] || continue
      case "$old" in
        .compass/*|docs/compass/*) ;;
        *) return 0 ;;
      esac
    done < <(git -C "$PROJECT_DIR" diff --name-status -M "$range" 2>/dev/null || true)
  done
  return 1
}

# --- merge each subtask in order ---------------------------------------------
MERGED=()
for i in "${!SUBTASKS[@]}"; do
  sid="${SUBTASKS[$i]}"
  branch="${BRANCHES[$i]}"

  if ! git -C "$PROJECT_DIR" show-ref --verify --quiet "refs/heads/$branch"; then
    echo "  $sid: branch '$branch' does not exist - skipping (was the multiagent ever created?)."
    continue
  fi

  # Already merged?
  if git -C "$PROJECT_DIR" merge-base --is-ancestor "$branch" "$BASE_BRANCH"; then
    echo "  $sid: already merged into $BASE_BRANCH - skipping."
    MERGED+=("$sid")
    continue
  fi

  echo "  $sid: merging $branch -> $BASE_BRANCH ..."
  if MERGE_OUTPUT="$(git -C "$PROJECT_DIR" merge --no-ff --no-edit \
        -m "compass($TASK_SLUG): integrate $sid" "$branch" 2>&1)"; then
    echo "         merged cleanly."
    MERGED+=("$sid")
    continue
  fi

  # Read the conflicted paths NUL-delimited, straight into an array. A
  # quoted, escaped path from a plain `git diff --name-only` (any byte
  # outside plain ASCII, or a space) would not match the prefix check below
  # and would be misreported; -z paired with `read -r -d ''` avoids both.
  CONFLICTS=()
  while IFS= read -r -d '' f; do
    CONFLICTS+=("$f")
  done < <(git -C "$PROJECT_DIR" diff --name-only -z --diff-filter=U 2>/dev/null || true)

  if [ "${#CONFLICTS[@]}" -eq 0 ]; then
    # git refused the merge before it started - e.g. an untracked file at a
    # path the merge would write. No MERGE_HEAD exists, so there is nothing
    # to abort; calling `merge --abort` here would itself fail and hide
    # git's real reason behind a second, misleading error.
    echo ""
    echo "  integrate.sh: git refused to merge $sid ($branch) - nothing changed."
    echo "$MERGE_OUTPUT" | sed 's/^/    /'
    exit 1
  fi

  RECORDS_ONLY=0
  if printf '%s\n' "${CONFLICTS[@]}" | _all_paths_are_compass_records; then
    RECORDS_ONLY=1
    for f in "${CONFLICTS[@]}"; do
      [ -n "$f" ] || continue
      if _rename_into_records_has_outside_source "$f"; then
        RECORDS_ONLY=0
        break
      fi
    done
  fi

  if [ "$RECORDS_ONLY" -eq 1 ]; then
    # Confined to Compass's own records - keep the base branch's side of
    # each conflicted file (a deletion on the base branch counts as its
    # side too) and complete the merge. The builder's own record of its own
    # subtask stays on its branch; only the base's copy, the one the
    # orchestrator has been updating, survives.
    RESOLVE_FAILED=""
    echo "         conflict confined to Compass's own records; kept the base branch's copy of:"
    for f in "${CONFLICTS[@]}"; do
      [ -n "$f" ] || continue
      if git -C "$PROJECT_DIR" cat-file -e ":2:$f" 2>/dev/null; then
        # The base branch still has a version of this file - keep it.
        if git -C "$PROJECT_DIR" checkout --ours -- "$f" 2>/dev/null \
             && git -C "$PROJECT_DIR" add -- "$f" 2>/dev/null; then
          echo "           - $f"
        else
          RESOLVE_FAILED="$f"
          break
        fi
      else
        # The base branch deleted this file - keep the deletion.
        if git -C "$PROJECT_DIR" rm -f -q -- "$f" 2>/dev/null; then
          echo "           - $f (removed - deleted on $BASE_BRANCH)"
        else
          RESOLVE_FAILED="$f"
          break
        fi
      fi
    done
    if [ -z "$RESOLVE_FAILED" ] \
       && git -C "$PROJECT_DIR" commit --no-edit >/dev/null 2>&1; then
      echo "         merged."
      MERGED+=("$sid")
      continue
    fi
    # A step above failed - a checkout, an add, the rm, or the commit
    # itself (a hook can reject it). Leave nothing half done: abort like
    # any other unresolved conflict, instead of exiting mid-merge.
    git -C "$PROJECT_DIR" merge --abort || true
    echo ""
    echo "  integrate.sh: could not resolve the records conflict for $sid ($branch)${RESOLVE_FAILED:+ (failed at $RESOLVE_FAILED)}."
    echo "  The merge was aborted; the repo is clean again."
    exit 2
  fi

  # Any other conflict is not auto-resolved: abort, report, stop.
  git -C "$PROJECT_DIR" merge --abort || true
  echo ""
  echo "  CONFLICT integrating $sid ($branch)."
  echo "  Conflicted files:"
  printf '    - %s\n' "${CONFLICTS[@]}"
  echo ""
  echo "  The merge was aborted; the repo is clean again. This is the"
  echo "  orchestrator's call to resolve - re-cut the boundary, re-sequence,"
  echo "  or escalate to a re-frame. No one else may resolve a cross-subtask"
  echo "  conflict. Subtasks merged so far: ${MERGED[*]:-none}."
  exit 2
done

if [ "${#MERGED[@]}" -eq 0 ]; then
  echo ""
  echo "integrate.sh: nothing was merged. Check the branch names in the map." >&2
  exit 1
fi

# --- combined regression ----------------------------------------------------
echo ""
echo "Combined regression across the integrated result:"
echo "----------------------------------------------------------------"
if [ -n "$TEST_CMD" ]; then
  if ( cd "$PROJECT_DIR" && eval "$TEST_CMD" ); then
    echo "----------------------------------------------------------------"
    echo "Combined regression GREEN. Paste the run above into verification-report.md."
  else
    echo "----------------------------------------------------------------"
    echo "Combined regression FAILED. Per-stream green did not survive integration."
    echo "Worktrees are LEFT IN PLACE so you can fix the subtask that broke."
    echo "The merge commits are on $BASE_BRANCH - revert or fix forward; do not"
    echo "clean up until combined regression is green."
    exit 1
  fi
else
  echo "No test command resolved (set 'test_command:' in .compass/config.yml)."
  echo "Combined regression MUST still be run by hand before ship closes -"
  echo "per-subtask green does not imply integrated green."
fi

# integrate.sh does NOT write status: landed or derive docs/system-spec.md.
# It runs before the verify stage, and on a staged (multi-wave) map it can
# run more than once for the same issue - writing landed here marked the
# issue landed after wave 1, and even on a single-wave run marked it
# landed before the verify stage ever ran. `ship-commit` alone marks an
# issue landed, once HEAD has actually moved and the gates have passed
# (manifest.py); living-spec derivation reads only landed issues, so
# deriving it here was a
# no-op ahead of that point in any case.

# --- clean up the worktrees -------------------------------------------------
echo ""
if [ "$CLEAN" -eq 1 ]; then
  echo "Cleaning up worktrees:"
  for sid in "${SUBTASKS[@]}"; do
    wt_path="$WORKTREE_ROOT/$TASK_SLUG-$sid"
    if [ -d "$wt_path" ]; then
      git -C "$PROJECT_DIR" worktree remove --force "$wt_path" 2>/dev/null \
        && echo "  removed $wt_path" \
        || echo "  could not remove $wt_path - remove by hand with: git worktree remove '$wt_path'"
    fi
  done
  git -C "$PROJECT_DIR" worktree prune
  echo ""
  echo "Per-stream branches are left in place for history - delete them when you"
  echo "are sure: git branch -d <branch>"
else
  echo "(--no-clean) worktrees kept in place."
fi

echo ""
echo "Integration complete for '$TASK_SLUG'. Back in /compass:ship, finish by:"
echo "  - pasting the combined-regression run into verification-report.md"
echo "  - updating living docs"
echo "  - resolving every outstanding follow-up in delivery-approach.md"
echo "  - writing the final devlog.md entry"
echo ""
echo "Next: \`/compass:verify\`, then \`ship-commit\` - only ship-commit marks '$TASK_SLUG' landed."
