# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: whether the call needs a red on record, and the current issue.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

# --- decide whether this tool call needs a red on record ---------------------
if [ "${TOOL:-}" = "Bash" ]; then
  [ -z "${COMMAND:-}" ] && exit 0
  [ "${SKIP_WRITE_SCAN:-0}" = 1 ] && exit 0

  # Cheap pre-filter, before any filesystem work: this hook now runs on every
  # Bash call in the session, and most of them write nothing.
  case "$COMMAND" in
    *">"*|*"sed -i"*|*perl[[:space:]]*|*ruby[[:space:]]*|*"tee "*|*cp\ *|*mv\ *|\
    *patch\ -p*|*"git apply"*|*open\(*|*write_text*|*write_bytes*|\
    *writeFileSync*|*appendFileSync*|*File.write*|*os.replace*|*os.rename*|\
    *shutil.copy*|*shutil.move*) ;;
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
    # A target written again judges the same, so each is judged once, in the
    # order it first appears: 200 identical `cp` lines cost one.
    #
    # awk (in the C locale, so in bytes and in time that grows with the length)
    # also prepares each target for the loops below, so no bash string
    # operation runs on a long target: the quotes are taken out (both kinds
    # from a target that holds a single quote, which the shell does not
    # expand; the double quotes only from the others), and a letter in front
    # says which it was: L for a literal target, E for one that can be
    # expanded. A target over TARGET_BYTES_LIMIT bytes becomes X and its
    # length. Every line starts with one of the three letters, put there by
    # awk, so the text of a command cannot make a line of another kind.
    SCAN_WORK_FILE=""
    case "$COMMAND" in
      *tee*|*cp*|*mv*)
        SCAN_WORK_FILE="$(mktemp 2>/dev/null)" \
          || compass_reader_failed "write scan" tmp ;;
    esac
    TARGET_LIST="$(bash_write_targets "$COMMAND" | LC_ALL=C awk -v limit="$TARGET_BYTES_LIMIT" '
      $0 == "" { next }
      !seen[$0]++ {
        if (length($0) > limit) { print "X" length($0); next }
        if (index($0, "\047")) { gsub("\047", ""); gsub(/"/, ""); print "L" $0 }
        else { gsub(/"/, ""); print "E" $0 }
      }')" || true
    _scan_nl=$'\n'

    # The steps the flattening took, and whether it ran out of its own budget,
    # are in the file it wrote, which the text of the command cannot write.
    # Anything that is not two small numbers is a fault, and a fault refuses.
    _scan_work=0 _scan_blown=0
    if [ -n "$SCAN_WORK_FILE" ]; then
      _scan_line="$(cat "$SCAN_WORK_FILE" 2>/dev/null)" || _scan_line=""
      rm -f "$SCAN_WORK_FILE"
      _scan_extra=""
      read -r _scan_work _scan_blown _scan_extra <<<"$_scan_line"
      case "$_scan_work" in
        ""|*[!0-9]*|??????????*) _scan_work="$SCAN_WORK_LIMIT"; _scan_blown=1 ;;
      esac
      case "$_scan_blown$_scan_extra" in 0|1) ;; *) _scan_blown=1 ;; esac
    fi
    WORK_USED=$((WORK_USED + _scan_work * COST_AWK_STEP))

    # Too much to scan in time (see the limits above). The scan marks a
    # command it gave up on; the count of targets needs a process only when
    # the list is long enough to hold TARGET_LIMIT + 1 of them (a target, its
    # letter and its line end take three characters at least).
    _too_complex=""
    if [ "$_scan_blown" -eq 1 ]; then
      _too_complex="has=substitutions that stay open|over=that many unclosed command substitutions"
    fi
    case "$_scan_nl$TARGET_LIST" in
      *"$_scan_nl"X*)
        if [ -z "$_too_complex" ]; then
          _long="$_scan_nl$TARGET_LIST"
          _long="${_long#*"$_scan_nl"X}"
          _long="${_long%%"$_scan_nl"*}"
          _too_complex="has=a write target of $_long bytes|over=more than $TARGET_BYTES_LIMIT bytes in one write target"
        fi ;;
    esac
    if [ -z "$_too_complex" ] && [ "${#TARGET_LIST}" -ge $((2 * (TARGET_LIMIT + 1))) ]; then
      _targets="$(printf '%s\n' "$TARGET_LIST" | grep -c . 2>/dev/null)" || _targets=0
      _targets="${_targets//[[:space:]]/}"
      case "$_targets" in ""|*[!0-9]*) _targets=0 ;; esac
      if [ "$_targets" -gt "$TARGET_LIMIT" ]; then
        _too_complex="has=$_targets different write targets|over=more than $TARGET_LIMIT write targets"
      fi
    fi
    if [ -z "$_too_complex" ] && [ "$WORK_USED" -gt "$WORK_BUDGET" ]; then
      _too_complex="$WORK_REFUSAL"
    fi
    if [ -n "$_too_complex" ]; then
      [ "$COMPASS_IN_USE" -eq 1 ] \
        && compass_block bash-command-too-complex "${_too_complex%%|*}" "${_too_complex#*|}"
      exit 0
    fi

    # The variable names the targets start with (at most NAME_LIMIT + 1, the
    # most that is read before the command is refused), so that the walk over
    # the leading statements keeps only those names.
    WALK_PRELOAD=""
    _preload_count=0
    _preload_brace='^\$\{([A-Za-z_][A-Za-z0-9_]*)\}'
    _preload_bare='^\$([A-Za-z_][A-Za-z0-9_]*)'
    while IFS= read -r candidate; do
      [ "${candidate:0:1}" = E ] || continue
      candidate="${candidate:1}"
      case "$candidate" in '$'*) ;; *) continue ;; esac
      if [[ $candidate =~ $_preload_brace ]] || [[ $candidate =~ $_preload_bare ]]; then
        case " $WALK_PRELOAD " in
          *" ${BASH_REMATCH[1]} "*) ;;
          *) WALK_PRELOAD="$WALK_PRELOAD ${BASH_REMATCH[1]}"
             _preload_count=$((_preload_count + 1)) ;;
        esac
        if [ "$_preload_count" -gt "$NAME_LIMIT" ]; then break; fi
      fi
    done <<<"$TARGET_LIST"

    GLOB_DEFER=1
    GLOB_PENDING="" GLOB_PENDING_CANDIDATES=""
    while IFS= read -r candidate; do
      _kind="${candidate:0:1}"
      candidate="${candidate:1}"
      [ -z "$candidate" ] && continue
      # Judging a path costs more for a long path and for each glob it is
      # tried against (charged in is_enforced_path).
      WORK_USED=$((WORK_USED + COST_CANDIDATE + COST_CANDIDATE_CHAR * ${#candidate}))
      if [ "$WORK_USED" -gt "$WORK_BUDGET" ] \
          || [ $((SECONDS - HOOK_START)) -ge "$FUSE_SECONDS" ]; then work_over; fi
      # A quoted target names the same file as an unquoted one, so awk took the
      # quotes out above (`> "src/app.ts"`). Inside single quotes the shell
      # expands nothing, so `'$S/x'` is a literal path (kind L) and is not
      # expanded. Only a target that starts with `$` can be expanded, and
      # passing the whole command to the function costs about 3 ms in a UTF-8
      # locale at 90 KB, so the others do not call it.
      if [ "$_kind" = E ]; then
        case "$candidate" in
          '$'*)
            if [ -n "$EXPAND_MEMO_CMD" ]; then
              expand_command_variable_into "$candidate" "" same
            else
              expand_command_variable_into "$candidate" "$COMMAND"
            fi
            candidate="$EXPANDED"
            if [ "$WORK_OVER" -eq 1 ]; then work_over; fi
            # Past NAME_LIMIT the command is too slow to read for every name.
            if [ "$EXPAND_NAMES" -gt "$NAME_LIMIT" ]; then
              [ "$COMPASS_IN_USE" -eq 1 ] \
                && compass_block bash-command-too-complex \
                     "has=$EXPAND_NAMES different variable names" \
                     "over=more than $NAME_LIMIT variable names"
              exit 0
            fi ;;
        esac
      fi
      [ -z "$candidate" ] && continue
      # 0: enforced, 1: not, 2: only a glob bash cannot decide could enforce it.
      # The paths of the third kind are kept for one Python start below.
      _verdict=0
      is_enforced_path "$candidate" || _verdict=$?
      if [ "$_verdict" -eq 0 ]; then
        DETECTED="$candidate"
        break
      elif [ "$_verdict" -eq 2 ]; then
        GLOB_PENDING_CANDIDATES="$GLOB_PENDING_CANDIDATES$candidate"$'\n'
      fi
    done <<<"$TARGET_LIST"
    GLOB_DEFER=0
    # A path set aside comes before the one that ended the loop, so a glob that
    # matches one of them names the first such path, as when each was judged in
    # turn.
    settle_deferred_globs
    if [ "$GLOB_HIT_INDEX" -gt 0 ]; then
      _rest="$GLOB_PENDING_CANDIDATES"
      _n=1
      while [ "$_n" -lt "$GLOB_HIT_INDEX" ]; do
        _rest="${_rest#*$'\n'}"
        _n=$((_n + 1))
      done
      DETECTED="${_rest%%$'\n'*}"
      MATCHED_RULE="enforcement.code_globs pattern '$GLOB_HIT' in $GLOBS_FILE"
    fi
  fi

  # Nothing recognisable is written → allow. See docs/safety-contract.md.
  [ -z "$DETECTED" ] && exit 0
  TARGET="$DETECTED"
else
  # No file path → nothing to enforce (e.g. a non-file tool). Allow.
  [ -z "${TARGET:-}" ] && exit 0
  is_enforced_path "$TARGET" || exit 0
  # An Edit that changes only comments needs no failing test and no issue.
  if [ "${TOOL:-}" = "Edit" ] && comment_only_edit_allowed; then
    exit 0
  fi
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
  _rec="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_opt_in_record.py" "$PROJECT_DIR" 2>/dev/null </dev/null)" || return 0
  _by="$(printf '%s\n' "$_rec" | sed -n '1p')"
  _at="$(printf '%s\n' "$_rec" | sed -n '2p')"
  [ -n "$_by" ] || return 0
  if [ -n "$_at" ]; then
    echo "  This project was initialized by $_by on $_at, which is when it opted into Compass." >&2
  else
    echo "  This project was initialized by $_by, which is when it opted into Compass." >&2
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
  compass_block not-initialized "detail=no .compass/work/ exists in $PROJECT_DIR"
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
#
# A foreign project (a sibling worktree) is the exception: it is judged by its
# own pointer. A pointer that names anything is not empty, so a pointer to a
# missing issue refuses. COMPASS_ISSUE applies only to an empty pointer. There
# is no guess and no lease. A tree that cannot be tied to the session's
# repository refuses.
if [ "$FOREIGN" -eq 1 ]; then
  tied_to_session_repo || compass_block tree-not-tied "project=$PROJECT_DIR"
  SLUG=""
  if [ -f "$POINTER" ]; then
    SLUG="$(tr -d '[:space:]' < "$POINTER" 2>/dev/null || true)"
    case "$SLUG" in
      .|..|*/*|*\\*)
        compass_block bad-current-task "slug=$SLUG" ;;
    esac
  fi
  if [ -z "$SLUG" ]; then
    SLUG="${COMPASS_ISSUE:-}"
    case "$SLUG" in
      "") compass_block bad-session-issue "slug=none" "project=$PROJECT_DIR" ;;
      .|..|*/*|*\\*)
        compass_block bad-session-issue "slug=$SLUG" "project=$PROJECT_DIR" ;;
    esac
  fi
  [ -d "$WORK_DIR/$SLUG" ] || compass_block bad-session-issue "slug=$SLUG" "project=$PROJECT_DIR"
  TASK_DIR="$WORK_DIR/$SLUG"
elif [ -n "${COMPASS_ISSUE:-}" ]; then
  SLUG="$COMPASS_ISSUE"
  # The session's own project: COMPASS_ISSUE outranks the pointer, so only a
  # restart of the session changes the answer (bad-session-issue-restart).
  case "$SLUG" in
    .|..|*/*|*\\*)
      compass_block bad-session-issue-restart "slug=$SLUG" "project=$PROJECT_DIR" ;;
  esac
  [ -d "$WORK_DIR/$SLUG" ] || compass_block bad-session-issue-restart "slug=$SLUG" "project=$PROJECT_DIR"
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
# names one session's issue, and the fallback names none. Only in the
# session's own project: a session that visits a foreign project neither
# reads nor writes that project's table.
if [ "$FOREIGN" -eq 0 ] && [ -z "${COMPASS_ISSUE:-}" ] && [ -n "${SESSION_ID:-}" ] && [ -n "$TASK_DIR" ]; then
  LEASE_ERR="$(mktemp 2>/dev/null)" || compass_reader_failed "session lease reader" tmp
  set +e
  LEASE="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_session_lease.py" "$COMPASS_DIR" "$SESSION_ID" "$SLUG" 2>"$LEASE_ERR" </dev/null)"
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
  # The warning says which fault it is: a pointer that names an issue with no
  # folder is not a missing pointer. An empty pointer file names nothing, so it
  # keeps the first wording. The words after the dash are pinned by
  # tests/compat_hook.py.
  if [ -n "$TASK_DIR" ]; then
    if [ -n "${SLUG:-}" ] && [ -f "$POINTER" ]; then
      echo "Compass: .compass/current-task names '$SLUG', which has no folder under .compass/work/ - falling back to the most recently modified issue ($(basename "$TASK_DIR")). Run compass issue use <slug> to be unambiguous." >&2
    else
      echo "Compass: no .compass/current-task pointer - falling back to the most recently modified issue ($(basename "$TASK_DIR")). Run compass issue use <slug> to be unambiguous." >&2
    fi
  fi
fi

if [ -z "${TASK_DIR:-}" ]; then
  compass_say_how_this_project_opted_in
  compass_block not-initialized "detail=no issue exists under $PROJECT_DIR/.compass/work/"
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
ROUTE_PROBE="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_route_probe.py" "$TASK_DIR" 2>"$ROUTE_PROBE_ERR" </dev/null)"
ROUTE_PROBE_STATUS=$?
set -e
if [ "$ROUTE_PROBE_STATUS" -ne 0 ] || [ -z "$ROUTE_PROBE" ]; then
  compass_reader_failed "delivery-approach reader" "$ROUTE_PROBE_STATUS" "$ROUTE_PROBE_ERR"
fi
rm -f "$ROUTE_PROBE_ERR"
if [ "$ROUTE_PROBE" != "found" ]; then
  compass_block no-delivery-approach "slug=$TASK_SLUG"
fi
