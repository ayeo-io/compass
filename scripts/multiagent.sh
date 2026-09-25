#!/usr/bin/env bash
# =============================================================================
# Compass script: multiagent.sh  -  CREATE WORKTREES, ONE PER INDEPENDENT SUBTASK
# =============================================================================
# The breakdown-stage tool. Given an issue's distribution-map.md, it creates one
# git worktree per independent subtask under the configured worktree_root, one
# branch per subtask, and prints the launch plan - one `builder` agent per
# worktree. Only the `orchestrator` agent runs this (see CLAUDE.md, the
# worktree-multiagent skill).
#
# USAGE
#   scripts/multiagent.sh <issue-slug>              # read the issue's distribution map
#   scripts/multiagent.sh <issue-slug> --dry-run    # show the plan, create nothing
#   scripts/multiagent.sh <issue-slug> --wave N     # provision one staged wave only
#   scripts/multiagent.sh --help
#
# The map, the approach record and the other issue documents are found
# through the artifact registry - docs/compass/<created>-<slug>/ when the
# manifest registers a document there, .compass/work/<slug>/ for an issue
# whose documents predate the registry. See scripts/lib/issue-docs.sh.
#
# WAVES
#   A map whose subtask table carries a Wave column is staged: --wave N
#   provisions that wave's rows only, and the cap is measured against that
#   wave's row count, not the map's total. Without --wave, wave 1 runs and
#   the next wave is named. A map with no Wave column ignores waves.
#
# WHAT IT RESPECTS
#   - .compass/config.yml  multiagent.worktree_root   (default ../.compass-worktrees)
#   - .compass/config.yml  multiagent.max_worktrees   (default 6) - hard ceiling
#   - the cap in manifest.yml: critical risk (assessment.risk) or a fired
#     RP-CAP-001 rule gives max_worktrees 1.
#     If the cap is below the subtask count, the cap WINS and multiagent.sh refuses to
#     over-provision - it tells you to fold/sequence subtasks in the map first.
#
# IDEMPOTENT & SAFE
#   - A worktree/branch that already exists for a subtask is left as-is (reported
#     as "exists"), not recreated.
#   - It never deletes anything - teardown is integrate.sh's job on success.
#   - On any inconsistency (map missing, count over cap, dirty repo) it stops
#     with a clear message and changes nothing.
# =============================================================================

set -euo pipefail

# --- locate repo + project --------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPASS_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
PROJECT_DIR="$(git -C "$(pwd)" rev-parse --show-toplevel 2>/dev/null || pwd)"

# shellcheck source=lib/compass-python.sh
source "$SCRIPT_DIR/lib/compass-python.sh"
source "$SCRIPT_DIR/lib/issue-docs.sh"

# --- args -------------------------------------------------------------------
TASK_SLUG=""
DRY_RUN=0
WAVE_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --wave) WAVE_ARG="${2:-}"; shift ;;
    -h|--help) grep -E '^# (USAGE|  scripts)' "$0" | sed 's/^# //'; exit 0 ;;
    -*) echo "multiagent.sh: unknown flag: $1" >&2; exit 1 ;;
    *)  TASK_SLUG="$1" ;;
  esac
  shift
done
[ -n "$TASK_SLUG" ] || { echo "multiagent.sh: need an issue slug. See --help." >&2; exit 1; }

TASK_DIR="$PROJECT_DIR/.compass/work/$TASK_SLUG"
TASK_YML="$TASK_DIR/manifest.yml"
CONFIG="$PROJECT_DIR/.compass/config.yml"

# The map and the approach record are found through the artifact registry,
# so an issue whose documents moved to docs/compass/<created>-<slug>/ still
# resolves, and an issue whose documents are still flat under
# .compass/work/<slug>/ works exactly as before.
MAP="$(issue_doc_path "$TASK_SLUG" "distribution-map" || true)"
[ -n "$MAP" ] && [ -f "$MAP" ] || { echo "multiagent.sh: no distribution-map.md for issue '$TASK_SLUG' - the design stage must produce it first." >&2; exit 1; }

ROUTE="$(issue_doc_path "$TASK_SLUG" "delivery-approach" || true)"
if [ -z "$ROUTE" ] || [ ! -f "$ROUTE" ]; then
  # vocabulary-scan: allow - reads the retired artifact name for old archives
  ROUTE="$TASK_DIR/route.md"
fi
[ -f "$ROUTE" ] || { echo "multiagent.sh: no delivery-approach.md for issue '$TASK_SLUG' - triage must run first." >&2; exit 1; }
[ -f "$TASK_YML" ] || { echo "multiagent.sh: no manifest.yml for issue '$TASK_SLUG' - the worktree cap is read from structured assessment, not delivery-approach.md prose. Run /compass:assess." >&2; exit 1; }

# --- config: worktree_root + max_worktrees ----------------------------------
# Minimal YAML reads - these keys are simple scalars in .compass/config.yml.
read_cfg() { # key default
  local v=""
  [ -f "$CONFIG" ] && v="$(grep -E "^[[:space:]]*$1:" "$CONFIG" 2>/dev/null \
      | head -n1 | sed -E 's/^[^:]*:[[:space:]]*//; s/[[:space:]]*#.*$//; s/^"//; s/"$//')"
  echo "${v:-$2}"
}
WORKTREE_ROOT_REL="$(read_cfg 'worktree_root' '../.compass-worktrees')"
MAX_WORKTREES="$(read_cfg 'max_worktrees' '6')"

# worktree_root is relative to the project root.
case "$WORKTREE_ROOT_REL" in
  /*) WORKTREE_ROOT="$WORKTREE_ROOT_REL" ;;
  *)  WORKTREE_ROOT="$(cd "$PROJECT_DIR" && cd "$(dirname "$WORKTREE_ROOT_REL")" 2>/dev/null && pwd || echo "$PROJECT_DIR/$WORKTREE_ROOT_REL")/$(basename "$WORKTREE_ROOT_REL")" ;;
esac

# --- the cap from manifest.yml ---------------------------------------------
# The cap is a MACHINE FACT and must come from the structured assessment, not
# from grepping delivery-approach.md prose: delivery-approach.md quotes
# "risk: critical" and "RP-CAP-001" in its notes on rules that did not fire,
# so a grep of the prose caps non-critical work at 1.
# The standing cap (RP-CAP-001): critical risk => max_worktrees 1. We read
# it from assessment.risk and policy_rules_fired. Absent assessment is a hard
# error - never a silent cap, never a fall back to prose.
CAP_INFO="$(compass_python - "$TASK_YML" <<'PY'
import sys
import compass_pkg
try:
    import yaml
    d = yaml.safe_load(open(sys.argv[1]))
except Exception as e:
    print("ERR:" + str(e)); sys.exit(0)
if not isinstance(d, dict):
    print("ERR:manifest.yml is not a mapping"); sys.exit(0)
assessment = d.get("assessment") or d.get("readings") or {}
br = assessment.get("risk") or assessment.get("blast_radius")
if not br:
    print("ERR:no assessment.risk in manifest.yml"); sys.exit(0)
fired = d.get("policy_rules_fired") or d.get("fired_guardrails") or []
# Both id spellings: an archived manifest records the id that actually fired,
# and RG-CAP-001 is the retired spelling of RP-CAP-001.
CAP_IDS = ("RP-CAP-001", "RG-CAP-001")
capped = (br == "critical") or any(
    isinstance(f, dict) and f.get("id") in CAP_IDS for f in fired)
print("OK:" + ("1" if capped else "0"))
PY
)"
case "$CAP_INFO" in
  OK:1) CAP=1 ;;
  OK:0) CAP="$MAX_WORKTREES" ;;
  *)    echo "multiagent.sh: cannot read the cap from manifest.yml (${CAP_INFO#ERR:})." >&2
        echo "          The worktree cap is a machine fact in assessment.risk +" >&2
        echo "          fired_guardrails - fix manifest.yml. multiagent.sh does NOT fall back to" >&2
        echo "          grepping delivery-approach.md prose (that was the R4 false-positive)." >&2
        exit 1 ;;
esac
# Never exceed the config ceiling regardless.
[ "$CAP" -gt "$MAX_WORKTREES" ] && CAP="$MAX_WORKTREES"

# --- find an optional Wave column in the map's header row -------------------
# A staged map's §3 table carries one extra column, named "Wave" (an exact
# cell match on the header row). Its position - 0 when absent - tells the
# row-parsing loop below which cell, if any, to read as a row's wave number.
WAVE_COL=0
while IFS= read -r line; do
  case "$line" in \|*) ;; *) continue ;; esac
  IFS='|' read -r -a _hdr_cells <<<"$line"
  for _idx in "${!_hdr_cells[@]}"; do
    _cell="$(echo "${_hdr_cells[$_idx]}" | xargs 2>/dev/null || true)"
    if [ "$_cell" = "Wave" ]; then
      WAVE_COL="$_idx"
      break 2
    fi
  done
done < "$MAP"

# --- parse subtasks from the distribution map --------------------------------
# The map's §3 table has rows like:
#   | subtask-1 | U1 | PBW-A1, PBW-A2 | compass/<slug>/subtask-1 |
# We pull (subtask id, branch name) pairs from any table row whose first cell
# starts with "subtask-". This is intentionally forgiving so a hand-filled map
# still parses.
SUBTASKS=()
BRANCHES=()
WAVES=()
while IFS= read -r line; do
  # row must look like a markdown table row mentioning a subtask id
  case "$line" in
    \|*subtask-*) ;;
    # A map written before ADR-023 says stream-N. Read both (ADR-006).  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
    \|*stream-*) ;;  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
    *) continue ;;
  esac
  # Count only worktree-provisioning subtasks. A map may mark an
  # integration/verify subtask as non-provisioning - exclude it from the cap
  # arithmetic and from worktree creation.
  case "$line" in
    *"not a parallel worktree"*|*"not a worktree"*|*"non-provisioning"*|*"integration/verify"*) continue ;;
  esac
  # split on '|', trim each cell
  IFS='|' read -r -a _row_cells <<<"$line"
  sid="$(echo "${_row_cells[1]:-}" | xargs 2>/dev/null || true)"
  # Trim whitespace AND strip leading/trailing markdown punctuation (`, *).
  # The map's branch-name cell is often wrapped in backticks for readability
  # (`compass/<slug>/subtask-N`) or bold (**...**); the parser must treat the
  # cell as a clean git ref, not the literal-with-markdown string. Bare names
  # round-trip unchanged. Markdown *inside* a ref name is out of scope -
  # git ref-validation rejects such names anyway.
  branch="$(echo "${_row_cells[4]:-}" | xargs 2>/dev/null | sed -E 's/^[`*]+//; s/[`*]+$//' || true)"
  case "$sid" in subtask-*|stream-*) ;; *) continue ;; esac  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  # default branch name if the map left it blank
  [ -n "$branch" ] || branch="compass/$TASK_SLUG/$sid"
  wave=""
  [ "$WAVE_COL" -gt 0 ] && wave="$(echo "${_row_cells[$WAVE_COL]:-}" | xargs 2>/dev/null || true)"
  SUBTASKS+=("$sid")
  BRANCHES+=("$branch")
  WAVES+=("$wave")
done < "$MAP"

SUBTASK_COUNT="${#SUBTASKS[@]}"
if [ "$SUBTASK_COUNT" -eq 0 ]; then
  echo "multiagent.sh: distribution-map.md lists no subtasks (no 'subtask-N' rows in §3; 'stream-N' is also read, for maps written before the rename)." >&2  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  echo "          If the route is solo, breakdown is a no-op - do not run multiagent.sh." >&2
  exit 1
fi

# --- waves: a staged map is provisioned one wave at a time -------------------
NEXT_WAVE=""
WAVE_REQUESTED=""
if [ "$WAVE_COL" -gt 0 ]; then
  WAVE_MAX=0
  for w in "${WAVES[@]}"; do
    case "$w" in ''|*[!0-9]*) continue ;; esac
    [ "$w" -gt "$WAVE_MAX" ] && WAVE_MAX="$w"
  done
  WAVE_REQUESTED="${WAVE_ARG:-1}"
  case "$WAVE_REQUESTED" in
    ''|*[!0-9]*) echo "multiagent.sh: --wave needs a whole number, got '$WAVE_ARG'." >&2; exit 1 ;;
  esac
  if [ "$WAVE_REQUESTED" -gt "$WAVE_MAX" ]; then
    echo "multiagent.sh: wave $WAVE_REQUESTED is above the map's highest wave ($WAVE_MAX)." >&2
    exit 1
  fi
  WAVE_SUBTASKS=()
  WAVE_BRANCHES=()
  for i in "${!SUBTASKS[@]}"; do
    [ "${WAVES[$i]:-}" = "$WAVE_REQUESTED" ] || continue
    WAVE_SUBTASKS+=("${SUBTASKS[$i]}")
    WAVE_BRANCHES+=("${BRANCHES[$i]}")
  done
  # Bash 3.2 (macOS's /bin/bash) treats "${ARR[@]}" on a zero-element array
  # as an unbound variable under `set -u` - guarded rather than expanded
  # unconditionally, so a wave number with no matching rows empties the
  # arrays instead of aborting the script.
  SUBTASKS=()
  BRANCHES=()
  [ "${#WAVE_SUBTASKS[@]}" -gt 0 ] && SUBTASKS=("${WAVE_SUBTASKS[@]}")
  [ "${#WAVE_BRANCHES[@]}" -gt 0 ] && BRANCHES=("${WAVE_BRANCHES[@]}")
  SUBTASK_COUNT="${#SUBTASKS[@]}"
  [ "$WAVE_REQUESTED" -lt "$WAVE_MAX" ] && NEXT_WAVE="$((WAVE_REQUESTED + 1))"
elif [ -n "$WAVE_ARG" ]; then
  echo "multiagent.sh: --wave given but the map has no Wave column." >&2
  exit 1
fi

# --- enforce the cap --------------------------------------------------------
# Measured against the chosen wave's row count on a staged map, and against
# the map's total otherwise - a map staged over several waves must not be
# refused for a total it is never asked to provision in one pass.
if [ "$SUBTASK_COUNT" -gt "$CAP" ]; then
  echo "multiagent.sh: the distribution map has $SUBTASK_COUNT subtasks but the cap is $CAP." >&2
  echo "          The cap wins. Do not over-provision worktrees - go back to" >&2
  echo "          distribution-map.md and fold or sequence subtasks down to $CAP," >&2
  echo "          recording it as cap-driven (not as a de-scope). Then re-run." >&2
  exit 1
fi

# --- repo sanity ------------------------------------------------------------
git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || { echo "multiagent.sh: $PROJECT_DIR is not a git repository." >&2; exit 1; }
BASE_BRANCH="$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)"

echo "Compass multiagent - issue '$TASK_SLUG'"
echo "  base branch:    $BASE_BRANCH"
echo "  worktree root:  $WORKTREE_ROOT"
echo "  subtasks:        $SUBTASK_COUNT   (config max $MAX_WORKTREES, route cap $CAP)"
[ -n "$WAVE_REQUESTED" ] && echo "  wave:            $WAVE_REQUESTED of $WAVE_MAX"
echo ""

# --- the kinds the issue's registry names, read once -------------------------
# Every kind manifest.yml's `artifacts:` list carries is a document the
# worktree may need at its registered path - the map and the approach record
# above are two of these, read individually because the script also needs
# their content; the rest are read here, generically, purely to be seeded.
ARTIFACT_KINDS=()
while IFS= read -r _kind; do
  [ -n "$_kind" ] && ARTIFACT_KINDS+=("$_kind")
done < <(compass_python - "$TASK_YML" <<'PY'
import sys
import compass_pkg
import yaml
try:
    d = yaml.safe_load(open(sys.argv[1])) or {}
except Exception:
    d = {}
arts = d.get("artifacts") if isinstance(d, dict) else None
for a in (arts or []):
    if isinstance(a, dict) and a.get("kind"):
        print(a["kind"])
PY
)

# --- create the worktrees ---------------------------------------------------
mkdir -p "$WORKTREE_ROOT"
LAUNCH_PLAN=()

for i in "${!SUBTASKS[@]}"; do
  sid="${SUBTASKS[$i]}"
  branch="${BRANCHES[$i]}"
  wt_path="$WORKTREE_ROOT/$TASK_SLUG-$sid"

  if [ -d "$wt_path" ]; then
    echo "  $sid: worktree exists -> $wt_path"
  elif [ "$DRY_RUN" -eq 1 ]; then
    echo "  $sid: WOULD create worktree $wt_path on branch $branch"
  else
    # Create the branch if it does not exist, then the worktree on it.
    if git -C "$PROJECT_DIR" show-ref --verify --quiet "refs/heads/$branch"; then
      git -C "$PROJECT_DIR" worktree add "$wt_path" "$branch" >/dev/null
    else
      git -C "$PROJECT_DIR" worktree add -b "$branch" "$wt_path" "$BASE_BRANCH" >/dev/null
    fi
    echo "  $sid: created worktree $wt_path on branch $branch"
  fi

  # --- seed the worktree with the issue's artifacts --------------------------
  # `git worktree add` brings across only what git TRACKS. A project that
  # commits .compass/work/ gets the issue directory in each worktree
  # automatically. One that treats issue state as local - as this framework
  # repo does, see .gitignore - does not, and its builder lands in a worktree
  # with no spec, no plan, and no assignment. `compass next`, `compass check`,
  # and `compass tdd-red` all fail there, because resolve_task_dir has no work
  # directory to resolve against.
  #
  # NON-DESTRUCTIVE ON PURPOSE. multiagent.sh is documented as idempotent, and the
  # second run is the one where a builder has work to lose - a devlog entry, a
  # recorded red. An existing issue directory is left exactly as it is.
  if [ "$DRY_RUN" -eq 0 ] && [ -d "$wt_path" ]; then
    wt_task_dir="$wt_path/.compass/work/$TASK_SLUG"
    if [ -d "$wt_task_dir" ]; then
      echo "      issue dir already present - left as-is"
    else
      mkdir -p "$wt_task_dir"
      # Do not copy .red or evidence/: each records a run in another
      # worktree. The `*` glob also skips dotfiles, so .spike and
      # .acceptance do not copy either - those mark the issue's own state
      # (is it a spike, is it defined), not a per-worktree run, so a spike
      # or already-defined issue loses that marker in the new worktree.
      # Looks unintended; not fixed here (found defects get their own
      # issue).
      for _f in "$TASK_DIR"/*; do
        case "$(basename "$_f")" in
          evidence) continue ;;
          *) cp -R "$_f" "$wt_task_dir/" ;;
        esac
      done
      echo "      seeded issue dir -> .compass/work/$TASK_SLUG"
    fi
    # The pointer every `compass` call resolves "the current issue" through.
    # Written unconditionally: it is one line naming this issue, so there is no
    # builder work in it to lose, and a stale pointer is worse than none.
    mkdir -p "$wt_path/.compass"
    printf '%s\n' "$TASK_SLUG" > "$wt_path/.compass/current-task"

    # --- seed every registered document at its registered path -------------
    # A document still flat under .compass/work/<slug>/ already arrived with
    # the copy above. One the registry moved to
    # docs/compass/<created>-<slug>/ has not: `git worktree add` brings
    # across only what git tracks, and an untracked issue directory is not
    # on that path either. NON-DESTRUCTIVE, same as the copy above: an
    # existing file in the worktree is left as it is.
    if [ "${#ARTIFACT_KINDS[@]}" -gt 0 ]; then
      for _kind in "${ARTIFACT_KINDS[@]}"; do
        _doc_path="$(issue_doc_path "$TASK_SLUG" "$_kind" || true)"
        [ -n "$_doc_path" ] && [ -f "$_doc_path" ] || continue
        case "$_doc_path" in
          "$TASK_DIR"/*) continue ;;  # already carried by the copy above
        esac
        case "$_doc_path" in
          "$PROJECT_DIR"/*) _rel="${_doc_path#"$PROJECT_DIR"/}" ;;
          *) continue ;;  # outside the project - resolve_artifact refuses this itself
        esac
        _dest="$wt_path/$_rel"
        [ -f "$_dest" ] && continue
        mkdir -p "$(dirname "$_dest")"
        cp "$_doc_path" "$_dest"
        echo "      seeded $_rel"
      done
    fi
  fi

  LAUNCH_PLAN+=("$sid|$branch|$wt_path")
done

# --- print the launch plan --------------------------------------------------
echo ""
echo "Launch plan - one 'builder' agent per worktree:"
echo "----------------------------------------------------------------"
for entry in "${LAUNCH_PLAN[@]}"; do
  IFS='|' read -r sid branch wt_path <<<"$entry"
  echo "  builder for $sid"
  echo "    worktree : $wt_path"
  echo "    branch   : $branch"
  echo "    assignment  : owns the scenario set assigned to $sid in distribution-map.md"
  echo "    rule     : works ONLY inside this worktree; cross-subtask needs go via the orchestrator"
  echo ""
done
echo "----------------------------------------------------------------"
if [ "$SUBTASK_COUNT" -ge 4 ]; then
  echo "MULTIAGENT, 4+ subtasks: an 'orchestrator' agent must also run -"
  echo "it writes no feature code, watches for subtasks converging on shared surface,"
  echo "and owns integration at ship via scripts/integrate.sh."
else
  echo "MULTIAGENT, 2-3 subtasks: no dedicated orchestrator - the lead"
  echo "builder integrates at ship via scripts/integrate.sh."
fi
echo ""
[ "$DRY_RUN" -eq 1 ] && echo "(dry run - nothing was created)"
if [ -n "$NEXT_WAVE" ]; then
  echo "Next wave: $NEXT_WAVE of $WAVE_MAX - run:"
  echo "  scripts/multiagent.sh $TASK_SLUG --wave $NEXT_WAVE"
fi
echo "When every subtask is independently green, land them with:"
echo "  scripts/integrate.sh $TASK_SLUG"
