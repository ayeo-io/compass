# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: the long-command fuse and the approval guard.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

# --- a Bash command too long to scan in time ---------------------------------
# Claude Code stops a hook that runs too long, and before 2.1.295 a stopped
# hook lets the call run. The scans below take longer the longer the command
# is, so a command over COMMAND_LIMIT bytes is not scanned.
#   - In a project that opted in (it has `.compass/`, the test the opt-in
#     exits near the end make), the command is refused whole. A cut command
#     would pass any write placed after the cut.
#   - Elsewhere it is not refused, because the hook runs in every repository.
#     Only the write scan is skipped (SKIP_WRITE_SCAN, read where the Bash
#     decision starts). The approval guard below still reads the whole command:
#     it protects the transcript and the delegation files wherever the hook
#     runs.
# Write and Edit have no command, so they are never counted. The count is in
# bytes: `${#COMMAND}` counts characters in a UTF-8 locale, and a character is
# at most four bytes, so a command of COMMAND_LIMIT / 4 characters or fewer is
# under the limit and starts no process. If `wc` fails, the count is the upper
# bound, so a fault refuses and never allows.
#
# Three more limits, for a command under COMMAND_LIMIT that is still slow, with
# the same rule for where they apply (the refusal in a project that opted in,
# a skipped write scan elsewhere). The numbers come from timings of the
# worst commands the write scan accepts (result.md of the issue):
#   - OPENER_LIMIT: `$(` openers. Each opener that never closes is scanned to
#     the end of the text. The count starts a process only for a command of
#     2 * (OPENER_LIMIT + 1) characters or more, the least that many `$(`
#     take, so an ordinary command starts none.
#   - TARGET_LIMIT: different write targets (the candidate loop). Each costs
#     the judging of one path. The count is made where the targets are found.
#   - NAME_LIMIT: different variable names that targets start with. A target
#     that starts with a variable reads the whole command to find the value,
#     once for each name, and the count of targets does not bound that: 400
#     names took 26 s at 90 KB. The count is made as the names are read.
#   - SCAN_WORK_LIMIT: steps the flattening of substitutions may take. The
#     openers that never close make its work grow with their number times the
#     length of the text, which a count alone does not bound: 700 openers
#     before 85 KB of text took 224 s. A scan that passes the limit tells the
#     caller in a file (SCAN_WORK_FILE), and the command is refused as too
#     complex.
#   - TARGET_BYTES_LIMIT: bytes in one write target. The fuse and the budget
#     are checked between targets, never inside one, and the quote strip and
#     the path normaliser take time that grows with the square of its length
#     in a UTF-8 locale: one target of 10 KB ran for 20 s and 90 KB for 25 s.
#     A target over the limit is refused as too complex (and the write scan is
#     skipped where Compass is not in use). The length is counted in bytes by
#     awk in the C locale, so a multibyte character counts as its bytes.
#
# The limits above each bound one shape, and the time of a command that holds
# several is their sum. One shared counter, WORK_USED, bounds the sum: each
# scan that grows with the command adds its steps, in microseconds of the time
# they were measured to take (bash 3.2, UTF-8), and a command past WORK_BUDGET
# is refused as too complex, or has only its write scan skipped where Compass
# is not in use. The worst command accepted took 1.9 s on a machine with a
# load average of 2 to 4 (docs/safety-contract.md lists the shapes).
#   - WORK_BUDGET: the most the counter may reach.
#   - COST_AWK_STEP: one step of the flattening in awk (the largest count of
#     steps the awk scan reports, SCAN_WORK_LIMIT at the most).
#   - COST_STATEMENT: one pass of the walk over the leading statements, which
#     runs once for all the variable names.
#   - COST_STATEMENT_CHAR: the same pass, for each character it consumes.
#   - COST_NAME_PER_KB: the reading of the command for one variable name, for
#     each 1024 characters of the command.
#   - COST_CANDIDATE: the judging of one write target.
#   - COST_CANDIDATE_CHAR: the same, for each character of the target.
#   - COST_GLOB: the same, for each glob of the settings that the target is
#     tried against one by one.
#   - COST_EDIT_START: the start of the comment-only check of an Edit
#     (comment_only_edit_allowed): python3 with the package and the yaml
#     importer loaded, before it reads anything.
#   - COST_EDIT_PARSE_PY: one parse and comparison of a Python text of three
#     lines, less the start. The check charges it twice, once for each text.
#   - COST_EDIT_PARSE_YAML: the same for a YAML file.
#   - COST_EDIT_KB_PY: for each 1024 bytes of the larger of the file before and
#     after the Edit, the two texts together: the slowest Python shape that was
#     measured, statements of two bytes each (2.7 ms), against 0.03 ms for
#     comment lines and 1.9 ms for calls.
#   - COST_EDIT_KB_YAML: the same for a YAML file, which the pure Python parser
#     reads far more slowly than Python is parsed: flow sequences of one-digit
#     numbers took 9.5 ms.
#   - EDIT_ALARM_SECONDS: the most seconds the comment-only check may run. The
#     alarm is the smaller of this and what is left before FUSE_SECONDS, less
#     one second for the rest of the hook, and the check ends at the alarm. A
#     hostile file (PyYAML needs 90 s for 100,000 opening brackets) is stopped
#     by it, not by the table, and the Edit is judged as before.
#
# The budget is an estimate from a table, and the hook reads no clock to check
# it, so a slower machine, or an interaction the table does not charge (bash
# slows down as the number of shell variables grows), could still run past the
# 15 s time limit. FUSE_SECONDS is the backstop: the scan checks `$SECONDS`,
# bash's own count of whole seconds (no process starts), at each write target,
# each variable name and each pass of the walk, and past FUSE_SECONDS it stops
# as it does for the budget. The count has a granularity of one second, so the
# fuse trips between FUSE_SECONDS - 1 and FUSE_SECONDS seconds after the start
# of the script (HOOK_START). A scan waiting on a process (the settings
# reader) is not interrupted, only stopped at the next check. The value is
# assigned and not read from the environment: an override would be a bypass.
COMMAND_LIMIT=98304
OPENER_LIMIT=700
TARGET_LIMIT=400
NAME_LIMIT=20
SCAN_WORK_LIMIT=1000000
FUSE_SECONDS=8
WORK_BUDGET=2400000
COST_AWK_STEP=2
COST_STATEMENT=110
COST_STATEMENT_CHAR=5
COST_NAME_PER_KB=200
COST_CANDIDATE=3000
COST_CANDIDATE_CHAR=10
COST_GLOB=20
COST_EDIT_START=40000
COST_EDIT_PARSE_PY=5000
COST_EDIT_PARSE_YAML=5000
COST_EDIT_KB_PY=3000
COST_EDIT_KB_YAML=10000
EDIT_ALARM_SECONDS=3
TARGET_BYTES_LIMIT=2048
SKIP_WRITE_SCAN=0
COMPASS_IN_USE=0
if [ "${PROJECT_RESOLVED:-0}" -eq 1 ] && [ -d "$PROJECT_DIR/.compass" ]; then
  COMPASS_IN_USE=1
fi
if [ "${TOOL:-}" = "Bash" ]; then
  _chars=${#COMMAND}
  if [ "$_chars" -gt $((COMMAND_LIMIT / 4)) ]; then
    _bytes="$(printf '%s' "$COMMAND" | wc -c 2>/dev/null)" || _bytes=""
    _bytes="${_bytes//[[:space:]]/}"
    case "$_bytes" in ""|*[!0-9]*) _bytes=$((_chars * 4)) ;; esac
    if [ "$_bytes" -gt "$COMMAND_LIMIT" ]; then
      if [ "$COMPASS_IN_USE" -eq 1 ]; then
        compass_block bash-command-too-long "size=$_bytes" "limit=$COMMAND_LIMIT"
      fi
      SKIP_WRITE_SCAN=1
    fi
  fi
  if [ "$SKIP_WRITE_SCAN" -eq 0 ] && [ "$_chars" -ge $((2 * (OPENER_LIMIT + 1))) ]; then
    _openers="$(printf '%s\n' "$COMMAND" | grep -o '\$(' | wc -l 2>/dev/null)" || _openers=""
    _openers="${_openers//[[:space:]]/}"
    # A count that failed is no count: the scan below has its own work limit.
    case "$_openers" in ""|*[!0-9]*) _openers=0 ;; esac
    if [ "$_openers" -gt "$OPENER_LIMIT" ]; then
      if [ "$COMPASS_IN_USE" -eq 1 ]; then
        compass_block bash-command-too-complex "has=$_openers command substitutions" \
          "over=more than $OPENER_LIMIT command substitutions"
      fi
      SKIP_WRITE_SCAN=1
    fi
  fi
fi

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
     # prefilter-bare-begin (tests/test_pre_tool_hook_time_bounded.py runs it)
     # A text with no quote or backslash is its own bare form. For the rest,
     # bash substitution costs a few milliseconds up to 256 characters and
     # grows faster than the text after that (about 3 s at 4096 characters in
     # a UTF-8 locale), so a longer text goes through one `tr`. `tr -d` removes
     # the same three ASCII characters, byte by byte under LC_ALL=C.
     case "$_text" in
       *[\'\"\\]*)
         if [ "${#_text}" -lt 256 ]; then
           _bare="${_text//[\'\"\\]/}"
         else
           _bare="$(printf '%s' "$_text" | LC_ALL=C tr -d "'\"\\\\")"
         fi ;;
       *) _bare="$_text" ;;
     esac
     # prefilter-bare-end
     # The shell removes a backslash-newline and joins the text around it, so
     # `approval-req\<newline>uests` runs as the whole name
     # (ayeo-io/compass-delivery-record#246). When the text holds one, every
     # check below also reads two joined forms: `_joined`, the bare form with
     # its newlines removed, and `_cjoined`, the command with each line that
     # ends in a backslash joined to the next. Both can join more than the
     # shell does, which only starts the guard; the guard decides.
     _joined="" _cjoined=""
     case "$_text" in
       *\\$'\n'*)
         if [ "${#_text}" -lt 256 ]; then
           _joined="${_bare//$'\n'/}"
           _cjoined="${COMMAND//\\$'\n'/}"
         else
           _joined="$(printf '%s' "$_bare" | LC_ALL=C tr -d '\n')"
           _cjoined="$(printf '%s' "${COMMAND:-}" | LC_ALL=C awk '{ if (sub(/\\$/, "")) printf "%s", $0; else print }')"
         fi ;;
     esac
     case "$_text $_bare $_joined" in
       *approval-requests*|*prompt-approval.sh*|*.compass/delegations*|*--del*|\
       *.claude*|*CLAUDE_CONFIG_DIR*) GUARD_RUN=1 ;;
     esac
     if [ "$GUARD_RUN" = 0 ] && [ "${TOOL:-}" = "Bash" ]; then
       case "${COMMAND:-} ${_cjoined:-}" in *'~'*|*HOME*|*/.*|*//*) GUARD_RUN=1 ;; esac
       case "${_text:-} ${_bare:-} ${_joined:-}" in *.compass/*[*?[]*|*deleg*[*?[]*) GUARD_RUN=1 ;; esac
       # A flag or verb built with ANSI-C quoting or braces (`--{delegated,x}`)
       # shows no `--del`, so evidence beside `$'` or `{` starts the guard.
       case "${_text:-} ${_joined:-}" in
         *evidence*) case "${_text:-} ${_cjoined:-}" in *'$'\'*|*'{'*) GUARD_RUN=1 ;; esac ;;
       esac
       # Every word of `compass $'\x65vidence' $'appro\x76e'` can hold an
       # escape, so `evidence` need not show: `$'` then a backslash starts it.
       case "${_text:-} ${_cjoined:-}" in *'$'\'*'\'*) GUARD_RUN=1 ;; esac
       _above=""
       case "${TRANSCRIPT:-}" in /*) _above="${TRANSCRIPT%/*}" ;; esac
       case "${COMMAND:-} ${_cjoined:-}" in *"${_above:-//no transcript//}"*) GUARD_RUN=1 ;; esac
       while [ "$GUARD_RUN" = 0 ] && [ -n "$_above" ]; do
         case " ${COMMAND:-} ${_cjoined:-} " in
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
    GUARD="$(printf '%s' "$INPUT" | compass_python "$HOOK_ROOT/hooks/py/pre_tool_approval_guard.py" 2>"$GUARD_ERR")"
    GUARD_STATUS=$?
    set -e
    [ "$GUARD_STATUS" -eq 0 ] || compass_reader_failed "approval guard" "$GUARD_STATUS" "$GUARD_ERR"
    rm -f "$GUARD_ERR"
    if [ -n "$GUARD" ]; then
      GUARD_CODE="$(printf '%s\n' "$GUARD" | sed -n '1p')"
      GUARD_PARAMS=()
      while IFS= read -r line; do
        [ -n "$line" ] && GUARD_PARAMS+=("$line")
      done <<<"$(printf '%s\n' "$GUARD" | sed -n '2,$p')"
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
# A removed working directory with no CLAUDE_PROJECT_DIR leaves the project to
# be found from the edited path alone. When that path is inside a Compass
# project, refuse rather than judge by a guess.
if [ "$CWD_GONE" -eq 1 ] && [ -z "${CLAUDE_PROJECT_DIR:-}" ] \
   && [ "${PROJECT_RESOLVED:-0}" -eq 1 ]; then
  compass_block working-directory-gone "target=${TARGET:-}" "tool=${TOOL:-?}"
fi
