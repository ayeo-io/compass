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

# Strip leading zeros from an already-validated numeric string, so "02" and
# "2" compare and print alike, and $(( )) never misreads a wave number as
# octal (bash treats a leading-zero literal as octal in arithmetic context,
# and "008" is not valid octal).
_norm_wave() {
  local v="$1"
  v="${v#"${v%%[!0]*}"}"
  [ -n "$v" ] || v="0"
  printf '%s' "$v"
}

# A seeded document's destination can resolve outside the worktree even when
# the destination itself does not yet exist: the branch just checked out can
# make a PATH COMPONENT (e.g. "docs") a symlink to outside the worktree, and
# `mkdir -p` plus `cp` would then create real files under that outside
# target. Python's realpath() resolves every symlink already on disk - the
# checked-out branch's own files - and leaves any NOT-YET-CREATED trailing
# component untouched, which is exactly the containment check needed before
# a single directory is made. See finding 1 of the dispatch-protocol
# security review.
_seed_dest_is_inside_worktree() {
  local dest="$1" wt="$2"
  compass_python - "$dest" "$wt" <<'PY' 2>/dev/null
import os
import sys
dest, wt = sys.argv[1], sys.argv[2]
rp_dest = os.path.realpath(dest)
rp_wt = os.path.realpath(wt)
inside = rp_dest == rp_wt or rp_dest.startswith(rp_wt + os.sep)
sys.exit(0 if inside else 1)
PY
}

# --- args -------------------------------------------------------------------
TASK_SLUG=""
DRY_RUN=0
WAVE_ARG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --wave)
      [ $# -ge 2 ] || { echo "multiagent.sh: --wave needs a value - a whole number naming the wave to provision." >&2; exit 1; }
      WAVE_ARG="$2"; shift ;;
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
#
# issue_doc_path already reports WHY a lookup failed - refused, omitted,
# unresolvable, or a resolver that could not even run - on stderr.
# multiagent.sh's own follow-up line ("the design stage must produce it
# first") is right only for a genuine ABSENT; adding it after every other
# reason blames the wrong stage for a document that IS there but refused,
# or deliberately omitted, or that crashed while being read.
_required_doc() {
  local kind="$1" out err_file err
  err_file="$(mktemp 2>/dev/null || printf '%s' "/tmp/multiagent-doc-err.$$")"
  if out="$(issue_doc_path "$TASK_SLUG" "$kind" 2>"$err_file")" && [ -n "$out" ] && [ -f "$out" ]; then
    rm -f "$err_file"
    printf '%s\n' "$out"
    return 0
  fi
  err="$(cat "$err_file" 2>/dev/null)"
  rm -f "$err_file"
  [ -n "$err" ] && echo "$err" >&2
  case "$err" in
    *"$kind: absent "*) return 2 ;;  # true absence - the design-stage message applies
    *) return 1 ;;                    # refused/omitted/unresolvable/crash - already reported above
  esac
}

if MAP="$(_required_doc distribution-map)"; then
  :
else
  _map_rc=$?
  [ "$_map_rc" -eq 2 ] && echo "multiagent.sh: no distribution-map.md for issue '$TASK_SLUG' - the design stage must produce it first." >&2
  exit 1
fi

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

# --- find the subtask table's own header row ---------------------------------
# A map can carry more than one markdown table (§1, §2, §3...); only the
# table whose rows carry a subtask id (current or retired spelling, see the
# row-parsing loop below) governs provisioning, so "Wave" and "Branch name"
# must be read from THAT table's header, not any other table's. A table is
# a header row immediately followed by a "|---|" separator row;
# PENDING_HEADER tracks the most recent header-shaped row seen, and is
# handed to SUBTASK_HEADER the first time a subtask row appears.
PENDING_HEADER=""
SUBTASK_HEADER=""
while IFS= read -r line; do
  case "$line" in \|*) ;; *) continue ;; esac
  # A separator row (only |, -, : and spaces) belongs to the table
  # PENDING_HEADER already names - skip it without disturbing PENDING_HEADER.
  case "$(echo "$line" | tr -d '|: -')" in '') continue ;; esac
  # A row belongs to the subtask table only when its FIRST cell is a
  # subtask id - the same test the row-parsing loop below applies to
  # `sid`. Matching "subtask-" anywhere in the line would also catch a
  # note in some OTHER table's cell (an independence table's Verdict
  # saying "subtask-3 waits for subtask-1"), which would pick that
  # table's header instead and the real subtask table's Wave column
  # would never be read.
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

# --- Wave and Branch name, read by header from the subtask table only -------
# Position 0 means absent for WAVE_COL (never a real column: the leading
# "|" makes cell 0 empty). BRANCH_COL defaults to the template's usual
# position 4, for a hand-filled map whose header text does not match
# "Branch name" exactly.
WAVE_COL=0
BRANCH_COL=4
if [ -n "$SUBTASK_HEADER" ]; then
  IFS='|' read -r -a _hdr_cells <<<"$SUBTASK_HEADER"
  for _idx in "${!_hdr_cells[@]}"; do
    _cell="$(echo "${_hdr_cells[$_idx]}" | xargs 2>/dev/null || true)"
    case "$_cell" in
      Wave) WAVE_COL="$_idx" ;;
      "Branch name") BRANCH_COL="$_idx" ;;
    esac
  done
fi

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
  # git ref-validation rejects such names anyway. BRANCH_COL is found by the
  # "Branch name" header above, not a fixed position - Q3 says Wave can sit
  # anywhere in the table, so a fixed cell 4 would read the wrong column.
  branch="$(echo "${_row_cells[$BRANCH_COL]:-}" | xargs 2>/dev/null | sed -E 's/^[`*]+//; s/[`*]+$//' || true)"
  case "$sid" in subtask-*|stream-*) ;; *) continue ;; esac  # vocabulary-scan: allow - reads the retired spelling for back-compat (ADR-006)
  # default branch name if the map left it blank
  [ -n "$branch" ] || branch="compass/$TASK_SLUG/$sid"
  _row_problem="$(map_row_problem "$sid" "$branch")"
  if [ -n "$_row_problem" ]; then
    echo "multiagent.sh: distribution-map.md's row is refused: $_row_problem. Nothing was created." >&2
    exit 1
  fi
  wave=""
  if [ "$WAVE_COL" -gt 0 ]; then
    wave="$(echo "${_row_cells[$WAVE_COL]:-}" | xargs 2>/dev/null || true)"
    # Q3 says the Wave cell holds a positive whole number. A blank or
    # non-numeric cell must refuse the map, naming the row - not drop the
    # row from every wave silently.
    case "$wave" in
      ''|*[!0-9]*)
        echo "multiagent.sh: distribution-map.md's Wave cell for $sid is '$wave' - it must be a positive whole number." >&2
        exit 1 ;;
    esac
    # A Wave cell this long either hangs the wave-counting arithmetic below
    # or overflows bash's integer comparisons outright, which silently drops
    # the row from every wave (finding 2, dispatch-protocol security
    # review). Three digits covers any map this project stages.
    if [ "${#wave}" -gt 3 ]; then
      echo "multiagent.sh: distribution-map.md's Wave cell for $sid is '$wave' - refuse a wave number longer than 3 digits." >&2
      exit 1
    fi
    if [ "$wave" -lt 1 ]; then
      echo "multiagent.sh: distribution-map.md's Wave cell for $sid is '$wave' - it must be a positive whole number." >&2
      exit 1
    fi
    wave="$(_norm_wave "$wave")"
  fi
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
# The map's total, kept apart from SUBTASK_COUNT: the wave block below
# narrows SUBTASK_COUNT to one wave's rows, but the orchestrator-agent
# decision at the end of the run is about the whole map, not one wave.
MAP_TOTAL_SUBTASKS="$SUBTASK_COUNT"

# --- waves: a staged map is provisioned one wave at a time -------------------
NEXT_WAVE=""
WAVE_REQUESTED=""
if [ "$WAVE_COL" -gt 0 ]; then
  # Every WAVES[i] is already a validated, leading-zero-free positive
  # integer (the row-parsing loop above refuses anything else), so a plain
  # numeric scan is enough here.
  WAVE_MAX=0
  for w in "${WAVES[@]}"; do
    [ "$w" -gt "$WAVE_MAX" ] && WAVE_MAX="$w"
  done
  # The distinct waves the map actually has, ascending. Q3 does not say
  # waves must be consecutive, so "the next wave" and "the waves the map
  # has" are both read from this list rather than assumed from WAVE_MAX -
  # a map staged 1, 3 has no wave 2, and naming one that does not exist
  # would send the reader to a run that is then refused. Built from the
  # VALUES PRESENT, via `sort -nu` - not by counting up to the highest one,
  # which takes as long as the highest wave number names (finding 2,
  # dispatch-protocol security review: a Wave cell of 20000 took over a
  # second to count to, and the trend does not stop there).
  DISTINCT_WAVES=()
  while IFS= read -r _dw; do
    [ -n "$_dw" ] && DISTINCT_WAVES+=("$_dw")
  done < <(printf '%s\n' "${WAVES[@]}" | sort -nu)
  WAVE_REQUESTED="${WAVE_ARG:-1}"
  case "$WAVE_REQUESTED" in
    ''|*[!0-9]*) echo "multiagent.sh: --wave needs a whole number, got '$WAVE_ARG'." >&2; exit 1 ;;
  esac
  # Numbers, not strings: "02" must match a row whose Wave cell is 2.
  WAVE_REQUESTED="$(_norm_wave "$WAVE_REQUESTED")"
  if [ "$WAVE_REQUESTED" -gt "$WAVE_MAX" ]; then
    echo "multiagent.sh: wave $WAVE_REQUESTED is above the map's highest wave ($WAVE_MAX)." >&2
    exit 1
  fi
  WAVE_SUBTASKS=()
  WAVE_BRANCHES=()
  for i in "${!SUBTASKS[@]}"; do
    [ "${WAVES[$i]}" -eq "$WAVE_REQUESTED" ] || continue
    WAVE_SUBTASKS+=("${SUBTASKS[$i]}")
    WAVE_BRANCHES+=("${BRANCHES[$i]}")
  done
  # A wave number with no matching rows - --wave 0, or a wave number between
  # the map's staged ones - is refused with a clear message, the same way
  # on bash 3.2 and bash 5, naming the waves the map actually has. This also
  # sidesteps bash 3.2's "unbound variable" on expanding an empty array
  # under `set -u`: the empty case exits before either array is expanded.
  if [ "${#WAVE_SUBTASKS[@]}" -eq 0 ]; then
    WAVE_LIST=""
    for w in "${DISTINCT_WAVES[@]}"; do
      WAVE_LIST="${WAVE_LIST:+$WAVE_LIST, }$w"
    done
    echo "multiagent.sh: wave $WAVE_REQUESTED has no rows; the map's waves are $WAVE_LIST." >&2
    exit 1
  fi
  SUBTASKS=("${WAVE_SUBTASKS[@]}")
  BRANCHES=("${WAVE_BRANCHES[@]}")
  SUBTASK_COUNT="${#SUBTASKS[@]}"
  # The next wave named is the smallest the map actually has above the one
  # just provisioned - not WAVE_REQUESTED + 1, which can name a gap (waves
  # 1, 3 have no 2) that a later run would then refuse for having no rows.
  for w in "${DISTINCT_WAVES[@]}"; do
    if [ "$w" -gt "$WAVE_REQUESTED" ]; then
      NEXT_WAVE="$w"
      break
    fi
  done
elif [ -n "$WAVE_ARG" ]; then
  echo "multiagent.sh: --wave given but the map has no Wave column." >&2
  exit 1
fi

# --- enforce the cap --------------------------------------------------------
# Measured against the chosen wave's row count on a staged map, and against
# the map's total otherwise - a map staged over several waves must not be
# refused for a total it is never asked to provision in one pass. The
# message names the wave when one is chosen, not the map's total, so a
# reader is not sent to fold the wrong count.
if [ "$SUBTASK_COUNT" -gt "$CAP" ]; then
  if [ -n "$WAVE_REQUESTED" ]; then
    echo "multiagent.sh: wave $WAVE_REQUESTED has $SUBTASK_COUNT subtasks but the cap is $CAP." >&2
  else
    echo "multiagent.sh: the distribution map has $SUBTASK_COUNT subtasks but the cap is $CAP." >&2
  fi
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
  [ -n "$_kind" ] || continue
  # A kind comes straight from manifest.yml's artifacts: list and is used to
  # build a worktree-relative path below. Accept only lower-case letters and
  # hyphens - never a path segment such as "../../../../outside" or an
  # absolute path (finding 8, dispatch-protocol security review).
  case "$_kind" in
    *[!a-z-]*)
      echo "multiagent.sh: manifest.yml names an artifact kind '$_kind' that is not lower-case letters and hyphens - skipped." >&2
      continue ;;
  esac
  ARTIFACT_KINDS+=("$_kind")
done < <(compass_python - "$TASK_YML" <<'PY'
import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
import yaml
try:
    d = yaml.safe_load(open(sys.argv[1])) or {}
except Exception as e:
    sys.stderr.write(
        "multiagent.sh: could not read manifest.yml's artifacts: %s\n" % e)
    d = {}
arts = d.get("artifacts") if isinstance(d, dict) else None
for a in (arts or []):
    if isinstance(a, dict) and a.get("kind"):
        print(a["kind"])
PY
)

# Resolve each kind's path ONCE here, not once per worktree below: the
# resolver starts a fresh `cli/compass` process, and for N worktrees and M
# kinds that was M*N Python starts for an answer that cannot change between
# them. An empty entry means "not found" and the seeding loop below skips it.
ARTIFACT_PATHS=()
if [ "${#ARTIFACT_KINDS[@]}" -gt 0 ]; then
  for _kind in "${ARTIFACT_KINDS[@]}"; do
    _kind_err_file="$(mktemp 2>/dev/null || printf '%s' "/tmp/multiagent-kind-err.$$")"
    if _resolved="$(issue_doc_path "$TASK_SLUG" "$_kind" 2>"$_kind_err_file")"; then
      rm -f "$_kind_err_file"
    else
      _kind_err="$(cat "$_kind_err_file" 2>/dev/null)"
      rm -f "$_kind_err_file"
      _resolved=""
      case "$_kind_err" in
        *"$_kind: omitted "*)
          # A recorded decision, not a fault - a note, not the resolver's
          # error text. Each kind is resolved once for the whole run (see
          # above), so this prints once, not once per worktree.
          echo "multiagent.sh: note - $_kind is omitted for this issue, not seeded." >&2
          ;;
        *)
          [ -n "$_kind_err" ] && echo "$_kind_err" >&2
          ;;
      esac
    fi
    ARTIFACT_PATHS+=("$_resolved")
  done
fi

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
    # existing file in the worktree is left as it is. Each kind's path was
    # already resolved once, above the worktree loop - read it here rather
    # than asking the resolver again for every worktree.
    if [ "${#ARTIFACT_KINDS[@]}" -gt 0 ]; then
      for _ai in "${!ARTIFACT_KINDS[@]}"; do
        _kind="${ARTIFACT_KINDS[$_ai]}"
        _doc_path="${ARTIFACT_PATHS[$_ai]}"
        [ -n "$_doc_path" ] && [ -f "$_doc_path" ] || continue
        # A registered document that is itself a symlink can point at
        # content outside the project - [ -f ] is true for it, but the
        # CONTENT it names was never checked. Copy only a real file
        # (finding 7, dispatch-protocol security review).
        if [ -L "$_doc_path" ]; then
          echo "      note - $_kind's registered path is a symlink, not seeded" >&2
          continue
        fi
        case "$_doc_path" in
          "$TASK_DIR"/*) continue ;;  # already carried by the copy above
        esac
        case "$_doc_path" in
          "$PROJECT_DIR"/*) _rel="${_doc_path#"$PROJECT_DIR"/}" ;;
          *) continue ;;  # outside the project - resolve_artifact refuses this itself
        esac
        _dest="$wt_path/$_rel"
        [ -f "$_dest" ] && continue
        # The worktree's own checked-out branch can make a PATH COMPONENT of
        # _dest a symlink to outside the worktree, or track _dest itself as
        # a dangling symlink - neither is caught by [ -f "$_dest" ] above,
        # because in both cases the check is false. Resolve where _dest
        # would really land and refuse anything outside the worktree, and
        # refuse an existing symlink at the destination itself (finding 1).
        if [ -L "$_dest" ] || ! _seed_dest_is_inside_worktree "$_dest" "$wt_path"; then
          echo "      skipped $_rel - it resolves outside the worktree" >&2
          continue
        fi
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
# The map's total decides this, not SUBTASK_COUNT - on a staged map that is
# one wave's count, and a 7-subtask map staged in waves of 3 must print the
# message for its whole size, not for one wave's.
if [ "$MAP_TOTAL_SUBTASKS" -ge 4 ]; then
  echo "MULTIAGENT, 4+ subtasks: the session that owns the issue orchestrates -"
  echo "it writes no feature code, watches for subtasks converging on shared surface,"
  echo "and integrates before /compass:verify via scripts/integrate.sh."
else
  echo "MULTIAGENT, 2-3 subtasks: the session that owns the issue orchestrates,"
  echo "the same as on a larger map, and integrates before /compass:verify via"
  echo "scripts/integrate.sh."
fi
echo ""
[ "$DRY_RUN" -eq 1 ] && echo "(dry run - nothing was created)"
if [ -n "$NEXT_WAVE" ]; then
  echo "Next wave: $NEXT_WAVE of $WAVE_MAX - after this wave integrates, run:"
  echo "  scripts/multiagent.sh $TASK_SLUG --wave $NEXT_WAVE"
fi
echo "When every subtask in this wave is green, integrate them with:"
echo "  scripts/integrate.sh $TASK_SLUG              # a wave before the last"
echo "  scripts/integrate.sh $TASK_SLUG --no-clean   # the last wave"
