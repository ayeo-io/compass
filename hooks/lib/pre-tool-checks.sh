# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: the spike, acceptance, dependency and red-before-green checks.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

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
  G2_VERDICT="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_acceptance_verdict.py" "$TASK_DIR/manifest.yml" 2>"$G2_ERR" </dev/null)"
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
  DEP_LINES="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_dependencies.py" "$TASK_DIR" 2>"$DEP_ERR" </dev/null)"
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
  done <<<"$DEP_LINES"
  if [ -n "$DEP_WAIT" ]; then
    IFS="$(printf '\t')" read -r _ DEP_ISSUE DEP_UNTIL DEP_STATE DEP_MORE <<<"$DEP_WAIT"
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
  RED_VERDICT="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_red_verdict.py" "$TASK_DIR" "$COMPASS_DIR" </dev/null 2>"$RED_ERR")"
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

# No .red marker → no failing test on record → block the code edit. The
# refusal names the project whose issue judged the edit: in a worktree that
# is not the session's own folder, and `compass tdd-red` must run there.
compass_block no-red-on-record "slug=$TASK_SLUG" "target=$TARGET" "tool=${TOOL:-?}" \
  "guard=${MATCHED_RULE:-the built-in production-code set}" "project=$PROJECT_DIR"
