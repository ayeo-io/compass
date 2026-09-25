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
#   or docs/compass/ - is resolved on the spot: the base branch's copy wins,
#   the merge completes, and the script names which file it kept. Any other
#   conflict is NOT auto-resolved: the merge aborts, the repo is left clean,
#   and the script reports exactly which subtask and which files conflicted,
#   then stops. Resolving a cross-subtask conflict outside Compass's own
#   records is the orchestrator's job and no one else's - the script just
#   surfaces it.
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
COMPASS_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
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

# --- parse subtasks + branches (same parser shape as multiagent.sh) ---------------
SUBTASKS=(); BRANCHES=()
while IFS= read -r line; do
  # A map written before ADR-023 says stream-N. Read both (ADR-006).  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  case "$line" in \|*subtask-*|\|*stream-*) ;; *) continue ;; esac  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  IFS='|' read -r _ c1 c2 c3 c4 _rest <<<"$line"
  sid="$(echo "${c1:-}" | xargs 2>/dev/null || true)"
  branch="$(echo "${c4:-}" | xargs 2>/dev/null || true)"
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

# Every conflicted path is one of Compass's own records - Q4 of
# requirements-review.md: anything under .compass/ or docs/compass/, and
# nothing else. Reads the list from stdin, one path per line.
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
  if git -C "$PROJECT_DIR" merge --no-ff --no-edit \
        -m "compass($TASK_SLUG): integrate $sid" "$branch" >/dev/null 2>&1; then
    echo "         merged cleanly."
    MERGED+=("$sid")
    continue
  fi

  # Conflict (or a merge git refused to even start, such as one that would
  # overwrite an untracked file - that case shows no conflicted path below).
  CONFLICTS="$(git -C "$PROJECT_DIR" diff --name-only --diff-filter=U || true)"

  if [ -n "$CONFLICTS" ] && printf '%s\n' "$CONFLICTS" | _all_paths_are_compass_records; then
    # Confined to Compass's own records - keep the base branch's copy of
    # each conflicted file and complete the merge. The builder's own record
    # of its own subtask stays on its branch; only the base's copy, the one
    # the orchestrator has been updating, survives.
    echo "         conflict confined to Compass's own records; kept the base branch's copy of:"
    while IFS= read -r f; do
      [ -n "$f" ] || continue
      git -C "$PROJECT_DIR" checkout --ours -- "$f"
      git -C "$PROJECT_DIR" add -- "$f"
      echo "           - $f"
    done <<<"$CONFLICTS"
    git -C "$PROJECT_DIR" commit --no-edit >/dev/null
    echo "         merged."
    MERGED+=("$sid")
    continue
  fi

  # Any other conflict is not auto-resolved: abort, report, stop.
  git -C "$PROJECT_DIR" merge --abort || true
  echo ""
  echo "  CONFLICT integrating $sid ($branch)."
  echo "  Conflicted files:"
  echo "$CONFLICTS" | sed 's/^/    - /'
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

# --- write status: landed and derive the living system spec -----------------
echo ""
echo "Writing status: landed to manifest.yml and deriving living system spec..."

TASK_YML="$TASK_DIR/manifest.yml"
if [ -f "$TASK_YML" ]; then
  # Parenthesised into its own subshell: this call - unlike the ones above
  # that already sit inside `$(...)` - is a plain statement, not a captured
  # substitution. compass_python forks python3; it does not replace the
  # calling shell, so worktree cleanup and the final summary below still run
  # whatever this block does.
  ( compass_python - <<PYEOF
import compass_pkg
import yaml, datetime, sys
path = "$TASK_YML"
try:
    with open(path, 'r', encoding='utf-8') as f:
        task = yaml.safe_load(f) or {}
    if not isinstance(task, dict):
        task = {}
    task['status'] = 'landed'
    task['land_timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    with open(path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(task, f, sort_keys=False, default_flow_style=False)
    print("  manifest.yml: status=landed, land_timestamp written.")
except Exception as exc:
    print(f"WARNING: could not write status: landed to {path}: {exc}", file=sys.stderr)
PYEOF
  )
else
  echo "  WARNING: no manifest.yml found at $TASK_YML - skipping status write."
fi

COMPASS_CLI="$COMPASS_HOME/cli/compass"
if [ -x "$COMPASS_CLI" ] || [ -f "$COMPASS_CLI" ]; then
  if ( cd "$PROJECT_DIR" && python3 "$COMPASS_CLI" _derive-system-spec --internal ); then
    echo "  docs/system-spec.md updated (living spec derived)."
  else
    echo "  WARNING: living spec derivation failed - docs/system-spec.md may be stale."
    echo "  Re-run: python3 cli/compass _derive-system-spec --internal"
  fi
else
  echo "  WARNING: compass CLI not found at $COMPASS_CLI - skipping derivation."
fi

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
