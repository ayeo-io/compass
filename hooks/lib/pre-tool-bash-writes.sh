# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: what a shell command can be known to write.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

# --- what a shell command can be known to write ------------------------------
# A shell command is arbitrary: `bash deploy.sh` may rewrite the whole repo and
# nothing in the string says so. So detection here recognises a fixed set of
# write shapes and lets everything else through. That is deliberate - blocking
# on suspicion would block `make`, `npm test`, and every unrecognised command,
# and enforcement that people switch off protects nothing. The limit is written
# down in docs/safety-contract.md rather than left to be discovered.
#
# Being generous is safe: every candidate goes through is_enforced_path(),
# which allows anything it does not recognise as production code. A token that
# is not a path simply falls through.
bash_write_targets() {
  local cmd="$1"
  {
    # Redirects into a file: `> f`, `>> f`, `1> f`, and the `cat > f <<EOF`
    # heredoc form. `2>&1` and `>&2` duplicate a file descriptor rather than
    # write a file, so `&` is excluded from the target. A quoted target is
    # taken whole, spaces included; the candidate loop removes the quotes.
    # `>|` writes as `>` does, and a line continuation after the operator
    # is joined first, so the target is not on a line of its own.
    # The continuations are joined by awk and not by the bash substitution
    # `${cmd//"$continuation"/ }`: in a UTF-8 locale that took 1.2 s for each
    # continuation in 98 KB, so 100 of them took 116 s. The final line end is
    # kept out of the join, as the substitution kept it.
    printf '%s\n' "$cmd" \
      | awk '{ s = s $0 "\n" }
             END { s = substr(s, 1, length(s) - 1); gsub(/\\\n/, " ", s); print s }' \
      | grep -oE "[0-9]?>(>|\|)?[[:space:]]*(\"[^\"]*\"|'[^']*'|[^&<>|;()[:space:]]+)" \
      | sed -E 's/^[0-9]?>(>|\|)?[[:space:]]*//' || true

    # In-place editors: hand over every argument and let the classifier
    # decide which of them is a production file.
    # perl and ruby edit in place with `-i` in any flag group, wherever it
    # stands among the switches (`-pi`, `-lpi`, `-i.bak`, `-I lib -pi`,
    # `-pe '...' -i`), so the literal text `perl -i` misses most real uses.
    # Only switches that take no value may come before the i in its group:
    # `-Mstrict`, `-I<dir>`, `-Fi` and ruby's `-rdigest` hold an i and edit
    # nothing. Each quoted span is first read as one word, so code such as
    # `-e 'print -int(2)'` is not a switch, and the switches end at the first
    # other word or at `--`, so `perl gen.pl -i` passes `-i` to a script.
    # The string a shell runs (`bash -c "perl -pi ..."`) is read as well,
    # because agents are told to run a script that needs bash that way.
    case "$cmd" in
      *"sed -i"*|*"perl -i"*)
        printf '%s\n' "$cmd" | tr ' \t' '\n\n' | grep -vE '^-' || true ;;
      *perl*|*ruby*)
        if { printf '%s\n' "$cmd"
             printf '%s\n' "$cmd" \
               | grep -oE "(^|[^[:alnum:]_])(ba|z|da)?sh[[:space:]]+-c[[:space:]]+('[^']*'|\"([^\"\\\\]|\\\\.)*\")" \
               | sed -E "s/^[^'\"]*['\"]//; s/['\"]$//" || true
           } \
            | sed -E "s/'[^']*'/__Q__/g; s/\"([^\"\\\\]|\\\\.)*\"/__Q__/g" \
            | grep -E '(^|[^[:alnum:]_.-])(perl|ruby)([[:space:]]+(-[ICr][[:space:]]+[^-[:space:]][^[:space:]]*|-[^-[:space:]][^[:space:]]*|__Q__))*[[:space:]]+-[0-9alnpsSwWtTuUcv]*i' \
            >/dev/null; then
          printf '%s\n' "$cmd" | tr ' \t' '\n\n' | grep -vE '^-' || true
        fi ;;
    esac

    # `tee` writes its own arguments; `cp` and `mv` write the LAST argument of
    # their own command. Neither writes a file that another command in the
    # same line names: in `python3 x.py | tee out.txt` the script is only run,
    # and in `cp a b && grep x src/app.ts` the source file is only read.
    #
    # So the command is cut into simple commands at `;`, `&`, `|`, `(` and
    # line ends, and redirects and comments are removed. In each simple
    # command, any word that names tee, cp or mv - `/bin/cp` and `\cp`
    # included - counts, wherever it stands, so a write behind a wrapper such
    # as `sudo`, `timeout 10`, `xargs` or `git` is still found. A word after
    # `tee` is a target; for `cp` and `mv` the last word is. This over-reports
    # (`grep -n tee src/app.ts`), as the hook did before; it must never miss a
    # write the earlier, broader rules caught.
    #
    # Before the cut, the command is flattened, so that nothing inside a
    # command can split it: line continuations are joined, and each
    # `$(...)`, `<(...)`, `>(...)` and backtick span becomes one placeholder
    # word, so `cp $(mktemp) src/app.ts` keeps its destination. The text of
    # each span is then judged as a command of its own, so a write inside
    # one, such as `x=$(cp a src/app.ts)`, is still found.
    #
    # The flattening runs twice and the targets of both passes count
    # (ayeo-io/compass-delivery-record#186). The first pass counts brackets
    # without regard to quotes, and a span it cannot close takes the rest of
    # the text. So a quoted `(`, as in `cp "$(echo '(')" src/app.ts`, keeps
    # the span open and hides the destination. The second pass ignores a
    # bracket inside quotes or after a backslash, and follows a `$(` inside
    # double quotes. A span it still cannot close stays as text, so the words
    # after it are still read. Either pass can misread a command the other
    # reads correctly, and an extra target can only add a refusal, so the
    # hook keeps both. A line both passes print is printed once.
    case "$cmd" in
      *tee*|*cp*|*mv*)
        printf '%s\n' "$cmd" \
          | awk -v budget="$SCAN_WORK_LIMIT" -v workfile="${SCAN_WORK_FILE:-}" '
              function emit(line) {
                if (!(line in seen)) { seen[line] = 1; print line }
              }
              function flatten(s, quoted,    q, n, k, t, out, rest, e, d, j, L, ch, st, top, closed) {
                q[1] = s; n = 1
                for (k = 1; k <= n; k++) {
                  t = q[k]; out = ""
                  while (match(t, /[$<>]\(|`/)) {
                    if (substr(t, RSTART, 1) == "`") {
                      rest = substr(t, RSTART + 1)
                      e = index(rest, "`")
                      if (e == 0 && quoted) {
                        out = out substr(t, 1, RSTART); t = rest; continue
                      }
                      out = out substr(t, 1, RSTART - 1) "_SPAN_"
                      if (e == 0) { q[++n] = rest; t = "" }
                      else { q[++n] = substr(rest, 1, e - 1); t = substr(rest, e + 1) }
                      continue
                    }
                    j = RSTART + 2; L = length(t)
                    if (quoted) {
                      # A stack of open contexts, innermost last: P is code
                      # inside a span or bracket, S a single-quoted string
                      # and D a double-quoted one.
                      st = "P"
                      while (j <= L && st != "") {
                        ch = substr(t, j, 1); top = substr(st, length(st))
                        if (top == "S") {
                          if (ch == "\047") st = substr(st, 1, length(st) - 1)
                        } else if (ch == "\\") {
                          j++
                        } else if (top == "D") {
                          if (ch == "\"") st = substr(st, 1, length(st) - 1)
                          else if (ch == "$" && substr(t, j + 1, 1) == "(") { st = st "P"; j++ }
                        } else if (ch == "\047") st = st "S"
                        else if (ch == "\"") st = st "D"
                        else if (ch == "(") st = st "P"
                        else if (ch == ")") st = substr(st, 1, length(st) - 1)
                        j++
                      }
                      if ((work += j - RSTART - 2) > budget) { blown = 1; return }
                      closed = (st == "")
                      if (!closed) {
                        out = out substr(t, 1, RSTART + 1); t = substr(t, RSTART + 2)
                        continue
                      }
                    } else {
                      d = 1
                      while (j <= L && d > 0) {
                        ch = substr(t, j, 1)
                        if (ch == "(") d++
                        else if (ch == ")") d--
                        j++
                      }
                      if ((work += j - RSTART - 2) > budget) { blown = 1; return }
                      closed = (d == 0)
                    }
                    out = out substr(t, 1, RSTART - 1) "_SPAN_"
                    q[++n] = substr(t, RSTART + 2, (closed ? j - 1 : j) - RSTART - 2)
                    t = substr(t, j)
                  }
                  emit(out t)
                }
              }
              { s = s $0 "\n" }
              END {
                gsub(/\\\n/, " ", s)
                flatten(s, 0)
                if (!blown) flatten(s, 1)
                # The steps taken, for the shared work budget, and whether the
                # scan ran out of its own budget (whatever it found stays),
                # in a file the caller made. The text of the command cannot
                # write that file: it is not on the path the targets take.
                if (workfile != "") { print (work + 0), (blown + 0) > workfile; close(workfile) }
              }' \
          | tr ';&|(' '\n\n\n\n' \
          | sed -E 's/(^|[[:space:]])#.*//; s/[0-9]*>>?[[:space:]]*[^[:space:]]*//g; s/<[[:space:]]*[^[:space:]]*//g; s/\)//g' \
          | awk '
              {
                for (i = 1; i <= NF; i++) {
                  w = $i
                  sub(/^\\/, "", w)
                  sub(/^.*\//, "", w)
                  if (w == "tee") {
                    for (j = i + 1; j <= NF; j++) if ($j !~ /^-/) print $j
                  } else if ((w == "cp" || w == "mv") && NF > i) {
                    print $NF
                  }
                }
              }' || true ;;
    esac

    # An inline interpreter script that opens a file FOR WRITING - the shape
    # this whole branch exists for, since `python3 -c` and a `python3 - <<PY`
    # heredoc are the easiest way to edit a file without an Edit tool call.
    #
    # Two things this deliberately does NOT do:
    #   - `open(path)` with no mode is a READ, not a write. Treating it as a
    #     write would block read-only verification commands - the hook
    #     stopping an author from checking their own work, which inverts what
    #     it is for.
    #   - A path counts only when a write call takes it: as a string inside
    #     the call, or through a name the call takes (below). Lifting every
    #     path out of a heredoc body would demand a failing test for a
    #     migration that a document merely *named*.
    # A missed write is recoverable; a false block trains people to bypass the
    # hook, and nothing recovers from that.

    # open(PATH, "w"|"a"|"x"|"r+"|"wb"…) - a mode containing w, a, x or + .
    printf '%s\n' "$cmd" \
      | grep -oE "open\([[:space:]]*\\\\?['\"][^'\"\\\\]+\\\\?['\"][[:space:]]*,[[:space:]]*\\\\?['\"][^'\"]*[waxWAX+][^'\"]*['\"]" \
      | sed -E "s/^open\([[:space:]]*\\\\?['\"]([^'\"\\\\]+)\\\\?['\"].*/\1/" || true

    # pathlib. Covers both `Path(TARGET).write_text(...)` and the commoner
    # two-step form, where the write happens on a variable:
    #     p = pathlib.Path(TARGET)
    #     p.write_text(...)
    # When the command contains a pathlib write at all, every Path(...)
    # argument in it is a candidate. The one exception is a Path(...) used
    # immediately for a read, which keeps "read a source file, generate a doc
    # from it" from being blocked on the file it only read.
    case "$cmd" in
      *write_text\(*|*write_bytes\(*)
        printf '%s\n' "$cmd" \
          | grep -oE "Path\([[:space:]]*\\\\?['\"][^'\"\\\\]+\\\\?['\"][[:space:]]*\)(\.[a-z_]+)?" \
          | grep -v "\.read_" \
          | sed -E "s/^Path\([[:space:]]*\\\\?['\"]([^'\"\\\\]+)\\\\?['\"].*/\1/" || true ;;
    esac

    # node / ruby equivalents, where the path is the first argument.
    printf '%s\n' "$cmd" \
      | grep -oE "(writeFileSync|appendFileSync|File\.write)\([[:space:]]*\\\\?['\"][^'\"\\\\]+\\\\?['\"]" \
      | sed -E "s/^[A-Za-z_.]+\([[:space:]]*\\\\?['\"]([^'\"\\\\]+)\\\\?['\"].*/\1/" || true

    # os.replace, os.rename, shutil.copy and shutil.move write their second
    # argument.
    printf '%s\n' "$cmd" \
      | grep -oE "(os\.replace|os\.rename|shutil\.copy2?|shutil\.copyfile|shutil\.move)\([^,()]*,[[:space:]]*\\\\?['\"][^'\"\\\\]+\\\\?['\"]" \
      | sed -E "s/.*,[[:space:]]*\\\\?['\"]([^'\"\\\\]+)\\\\?['\"]$/\1/" || true

    # A write call whose target is a name rather than a string:
    #     target = 'src/app.py'
    #     open(target, 'w')
    # Every string the same command assigns to that name is a target. Only
    # names a write call takes count, so a script that reads a source file
    # through one name and writes a report through another is judged on the
    # report alone. A path built at run time is still not seen. A quote may
    # be escaped (`\"`), as it is inside `python3 -c "..."`.
    #
    # The names and the assignments are each found in one pass over the
    # command and joined in awk, so the cost does not grow with the number
    # of names: one scan per name took 54 s for 5000 names.
    local _names
    _names="$(printf '%s\n' "$cmd" | {
      grep -oE "open\([[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*,[[:space:]]*\\\\?['\"][^'\"]*[waxWAX+][^'\"]*['\"]" \
        | sed -E 's/^open\([[:space:]]*([A-Za-z_][A-Za-z0-9_]*).*/\1/' || true
      printf '%s\n' "$cmd" \
        | grep -oE "Path\([[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\)\.(write_text|write_bytes)\(" \
        | sed -E 's/^Path\([[:space:]]*([A-Za-z_][A-Za-z0-9_]*).*/\1/' || true
      printf '%s\n' "$cmd" \
        | grep -oE "(os\.replace|os\.rename|shutil\.copy2?|shutil\.copyfile|shutil\.move)\([^,()]*,[[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*[,)]" \
        | sed -E 's/.*,[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*[,)]$/\1/' || true
      printf '%s\n' "$cmd" \
        | grep -oE "(writeFileSync|appendFileSync|File\.write)\([[:space:]]*[A-Za-z_][A-Za-z0-9_]*[[:space:]]*," \
        | sed -E 's/^[A-Za-z_.]+\([[:space:]]*([A-Za-z_][A-Za-z0-9_]*).*/\1/' || true
    })"
    if [ -n "$_names" ]; then
      printf '%s\n' "$cmd" \
        | grep -oE "(^|[^A-Za-z0-9_.])[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=[[:space:]]*\\\\?['\"][^'\"\\\\]+\\\\?['\"]" \
        | sed -E "s/^[^A-Za-z_]?([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*\\\\?['\"]([^'\"\\\\]+)\\\\?['\"]$/\1	\2/" \
        | NAMES="$_names" LC_ALL=C awk -F '\t' '
            BEGIN { n = split(ENVIRON["NAMES"], list, "\n"); for (i = 1; i <= n; i++) want[list[i]] = 1 }
            ($1 in want) { print $2 }' || true
    fi
  } | grep -vE '^[[:space:]]*$' || true
}

# --- a variable the command itself sets --------------------------------------
# A Bash write often names its target through a variable that the same
# command sets: `S=/tmp/scratch && cat > $S/plant.ts`. Read literally,
# `$S/plant.ts` is a relative path. is_enforced_path() joins it to the project
# root and refuses a scratch file outside the project as production code. A
# usage audit on 16 October 2026 counted 116 such refusals.
#
# This prints the target with a leading $NAME or ${NAME} replaced by its
# value, but only when the command states that value for certain. Otherwise
# it prints the target unchanged, and is_enforced_path() judges it inside the
# project exactly as before. An expansion can therefore only allow a write
# whose real path the hook can see; it never guesses.
#
# "For certain" means all of these hold:
#   - The command opens with leading statements, each ended by `;`, `&&` or
#     a line end. Each is either `[export ]NAME=value`, or a plain command
#     such as `cd /x`, `set -e` or `export A=1`: words of path characters
#     only, with no word that opens a block (`if`, `for`, `{`), defines a
#     function or trap, sources a file, evaluates text or makes a variable
#     read-only. NAME is assigned exactly once among them. Any other
#     assignment does not count, because at the write the variable may still
#     hold the environment's value: one inside a block or subshell, one after
#     `||`, or `S=x cmd`, which sets S for that one command only.
#   - If `&&` comes before the assignment, the assignment runs only when the
#     commands before it succeed. Every use of NAME must then be in the same
#     `&&` chain, so that it runs only if the assignment did.
#   - The value is a plain absolute path: no `$`, backtick, `~`, space or
#     `..` step. So the shell uses the same text the hook judges, and `..`
#     cannot step back into the project past a containment check that
#     compares text.
#   - After the assignment, NAME appears only as `$NAME` or `${NAME}`, and
#     nothing runs that can set a variable without naming it: eval, source,
#     `.`, trap, declare, typeset, local, readonly, export, read, mapfile,
#     readarray, unset, getopts, let, `printf -v` or `((`.
#   - NAME is not one the shell sets itself, such as PWD (changed by cd), _,
#     REPLY or UID (read-only, so the assignment fails).
# These checks read the command's text; they do not parse the shell. A word
# that only looks like one of them, such as `S` in a heredoc body, leaves the
# target unexpanded, which refuses as before. A function inherited from the
# environment that reassigns NAME, a builtin spelt to dodge the list
# (`ev""al`), or an arithmetic context that evaluates another variable's
# text, is deliberate evasion, which shell-write detection does not claim to
# stop (docs/safety-contract.md).
#
# The work is in two functions so that a command with many `$NAME/...` targets
# reads the command once for each NAME and not once for each target. The
# reading (`expand_command_variable_resolve`) depends on NAME and the command
# and not on the rest of the target, and the caller keeps its answers in
# EXPAND_MEMO. Each target after a heredoc of 85 KB cost about 50 ms, and 400
# of them took 21 s. The caller runs `expand_command_variable_into` in the
# hook's own shell, because a command substitution would lose the memo.
# `expand_command_variable` prints the answer, for the tests and for a caller
# that wants text. EXPAND_NAMES counts the names read for this command, which
# the caller compares with NAME_LIMIT.
EXPAND_MEMO_CMD="" EXPAND_MEMO="" EXPANDED="" RESOLVED="" EXPAND_NAMES=0 WORK_USED=0 WORK_OVER=0 WALK_CMD="" WALK_DIRTY=0 WALK_WANT=""
expand_command_variable() {
  expand_command_variable_into "$@"
  printf '%s\n' "$EXPANDED"
}

expand_command_variable_into() {
  local target="$1" cmd="$2" name rest value full tail
  local nl=$'\n'
  local path_re='^(/[A-Za-z0-9._+@%:,=-]*)*$'
  local dotdot_re='(^|/)\.\.(/|$)'
  local brace_re='^\$\{([A-Za-z_][A-Za-z0-9_]*)\}(.*)$'
  local bare_re='^\$([A-Za-z_][A-Za-z0-9_]*)(.*)$'
  local special_re='^(_|PWD|OLDPWD|UID|EUID|PPID|BASHPID|RANDOM|SRANDOM|SECONDS|EPOCHSECONDS|EPOCHREALTIME|LINENO|HISTCMD|REPLY|OPTARG|OPTIND|GROUPS|DIRSTACK|PIPESTATUS|FUNCNAME|SHELLOPTS|BASHOPTS|MAPFILE|COPROC|BASH_[A-Z_]*|BASH)$'

  if [[ $target =~ $brace_re ]] || [[ $target =~ $bare_re ]]; then
    name="${BASH_REMATCH[1]}"
    rest="${BASH_REMATCH[2]}"
  else
    EXPANDED="$target"; return 0
  fi
  if [[ $name =~ $special_re ]] || ! [[ $rest =~ $path_re ]]; then
    EXPANDED="$target"; return 0
  fi

  # The answer for NAME in this command: "D" to decline, or "V" and the value.
  # A caller that has already passed the command gives "same" as the third
  # argument and an empty command: handing a command of 90 KB to a function
  # costs about 3 ms in a UTF-8 locale, once for each target.
  if [ "${3:-}" != same ]; then
    case "$EXPAND_MEMO_CMD" in
      "$cmd") ;;
      *) EXPAND_MEMO_CMD="$cmd"; EXPAND_MEMO=""; EXPAND_NAMES=0; WALK_CMD=""
         WALK_WANT="${WALK_PRELOAD:-}" ;;
    esac
  fi
  case "$nl$EXPAND_MEMO" in
    *"$nl$name="*)
      tail="$nl$EXPAND_MEMO"
      tail="${tail#*"$nl$name="}"
      RESOLVED="${tail%%"$nl"*}" ;;
    *)
      [ "${3:-}" = same ] && cmd="$EXPAND_MEMO_CMD"
      EXPAND_NAMES=$((EXPAND_NAMES + 1))
      # The reading of the command for this name (its text is read about once
      # for each name) is charged to the shared work budget by its length.
      WORK_USED=$((WORK_USED + ${COST_NAME_PER_KB:-0} * ${#cmd} / 1024))
      expand_command_variable_resolve "$name" "$cmd"
      EXPAND_MEMO="$EXPAND_MEMO$name=$RESOLVED$nl"
      if { [ "${WORK_BUDGET:-0}" -gt 0 ] && [ "$WORK_USED" -gt "$WORK_BUDGET" ]; } \
          || { [ "${FUSE_SECONDS:-0}" -gt 0 ] \
               && [ $((SECONDS - HOOK_START)) -ge "$FUSE_SECONDS" ]; }; then
        WORK_OVER=1
      fi ;;
  esac
  case "$RESOLVED" in
    V*) value="${RESOLVED#V}" ;;
    *) EXPANDED="$target"; return 0 ;;
  esac
  full="$value$rest"
  if [[ $full =~ $dotdot_re ]]; then
    EXPANDED="$target"; return 0
  fi
  EXPANDED="$full"
}

# Sets RESOLVED to "D" (the command does not state NAME for certain) or to "V"
# and the value NAME has at the write.
expand_command_variable_resolve() {
  local name="$1" cmd="$2" value="" count=0
  local sep="start" before="" after_sep="" after_name="" stmt w len deny
  local total off size win after_off=0
  local ref ref1 ref2 head head2
  local sq="'" dq='"' bt='`' nl=$'\n'
  local path_re='^(/[A-Za-z0-9._+@%:,=-]*)*$'
  local value_re="(${sq}[^${sq}]*${sq}|${dq}[^${dq}]*${dq}|[^[:space:];&|<>()${sq}${dq}${bt}\\\$]*)"
  local assign_re="^[[:space:]]*(export[[:blank:]]+)?([A-Za-z_][A-Za-z0-9_]*)=${value_re}[[:blank:]]*(;|&&|${nl})"
  local binder_re='(^|[^A-Za-z0-9_./-])(eval|source|trap|declare|typeset|local|readonly|export|read|mapfile|readarray|unset|getopts|let)([^A-Za-z0-9_./-]|$)|(^|[;&|({'"${nl}"']|then|do|else)[[:space:]]*\.[[:space:]]|printf[[:space:]]+-v|(^|[^A-Za-z0-9_)])\(\('
  local stripped mention_re
  local plain_re="^[[:space:]]*([A-Za-z0-9._+@%:,=/~-]+([[:blank:]]+[A-Za-z0-9._+@%:,=/~-]+)*)[[:blank:]]*(;|&&|${nl})"

  # Walk the leading statements. `sep` is the separator that ended the
  # previous one; `after_off` is where the command after NAME's assignment
  # starts.
  #
  # Each statement is matched against `win`, the next few hundred characters,
  # and not against the whole rest of the command: a match on 80 KB of text
  # for each of 14000 statements took 20 s. This gives the same answer as
  # matching the rest because both patterns are anchored at the start and
  # end at the first separator, so a match that ends inside the window is the
  # match the rest gives. A window that finds no match may have cut a long
  # statement, so it is doubled until it holds all that is left, and only
  # then does the walk stop. The golden corpus in
  # tests/test_pre_tool_hook_time_bounded.py pins the results.
  #
  # The walk does not depend on NAME except in what it keeps, so it runs once
  # for the command and keeps what it found for each name in WALK_WANT (the
  # names the write targets start with, set by the caller, at most
  # NAME_LIMIT + 1): in WK_C_<name> the count of its assignments and in
  # WK_V_/WK_B_/WK_S_/WK_O_<name> the value, the separator before the
  # statement, the separator after it and where the text after it starts, all
  # for the last assignment. A walk for each name took 62 s for 40000
  # statements and 20 names. A name that is not in WALK_WANT is added and the
  # walk runs again, so the answer never depends on the caller's list. Each
  # pass is charged to the shared work budget, and stops at the fuse.
  case " $WALK_WANT " in
    *" $name "*) ;;
    *) WALK_WANT="$WALK_WANT $name"; WALK_CMD="" ;;
  esac
  if [ "$WALK_CMD" != "$cmd" ]; then
    WALK_CMD="$cmd"
    if [ "$WALK_DIRTY" -eq 1 ]; then
      for w in $(compgen -v WK_); do unset "$w"; done
      WALK_DIRTY=0
    fi
    total=${#cmd}
    off=0
    size=512
    win="${cmd:0:$size}"
    while :; do
      WORK_USED=$((WORK_USED + ${COST_STATEMENT:-0}))
      if { [ "${WORK_BUDGET:-0}" -gt 0 ] && [ "$WORK_USED" -gt "$WORK_BUDGET" ]; } \
          || { [ "${FUSE_SECONDS:-0}" -gt 0 ] \
               && [ $((SECONDS - HOOK_START)) -ge "$FUSE_SECONDS" ]; }; then
        WORK_OVER=1; break
      fi
      if [[ $win =~ $assign_re ]]; then
        len=${#BASH_REMATCH[0]}
        WORK_USED=$((WORK_USED + ${COST_STATEMENT_CHAR:-0} * len))
        # Only a name that a write target uses is kept. Bash slows every
        # variable operation as the number of variables grows (1 s more for
        # each 10000), and a command can assign thousands of other names.
        case " $WALK_WANT " in
          *" ${BASH_REMATCH[2]} "*)
            ref="WK_C_${BASH_REMATCH[2]}"
            printf -v "$ref" '%s' $(( ${!ref:-0} + 1 ))
            printf -v "WK_V_${BASH_REMATCH[2]}" '%s' "${BASH_REMATCH[3]}"
            printf -v "WK_B_${BASH_REMATCH[2]}" '%s' "$sep"
            printf -v "WK_S_${BASH_REMATCH[2]}" '%s' "${BASH_REMATCH[4]}"
            printf -v "WK_O_${BASH_REMATCH[2]}" '%s' $((off + len))
            WALK_DIRTY=1 ;;
        esac
        sep="${BASH_REMATCH[4]}"
      elif [[ $win =~ $plain_re ]]; then
        len=${#BASH_REMATCH[0]}
        WORK_USED=$((WORK_USED + ${COST_STATEMENT_CHAR:-0} * len))
        stmt="${BASH_REMATCH[1]}"
        sep="${BASH_REMATCH[3]}"
        deny=0
        for w in $stmt; do
          case "$w" in
            eval|source|.|declare|typeset|local|readonly|trap|alias|enable|builtin|\
            command|shopt|function|if|then|else|elif|fi|case|esac|for|select|\
            while|until|do|done|coproc) deny=1 ;;
          esac
        done
        [ "$deny" -eq 1 ] && break
      elif [ $((off + ${#win})) -lt "$total" ]; then
        size=$((size * 2))
        win="${cmd:$off:$size}"
        continue
      else
        break
      fi
      off=$((off + len))
      win="${win:$len}"
      if [ "${#win}" -gt 1024 ] || {
           [ "${#win}" -lt 256 ] && [ $((off + ${#win})) -lt "$total" ]; }; then
        size=512
        win="${cmd:$off:$size}"
      fi
    done
  fi
  if [ "$WORK_OVER" -eq 1 ]; then
    RESOLVED=D; return 0
  fi
  ref="WK_C_$name"
  count="${!ref:-0}"
  if [ "$count" -eq 1 ]; then
    ref="WK_V_$name"; value="${!ref}"
    ref="WK_B_$name"; before="${!ref}"
    ref="WK_S_$name"; after_sep="${!ref}"
    ref="WK_O_$name"; after_off="${!ref}"
  fi
  if [ "$count" -ne 1 ]; then
    RESOLVED=D; return 0
  fi
  after_name="${cmd:$after_off}"

  # After `&&`, the assignment may not run. Then the text up to the last use
  # of NAME must be one `&&` chain: no `;`, line end, `||` or lone `&`.
  if [ "$before" = "&&" ]; then
    ref1='$'"$name"
    ref2='${'"$name"'}'
    head=""
    case "$after_name" in *"$ref1"*) head="${after_name%"$ref1"*}" ;; esac
    case "$after_name" in *"$ref2"*)
      head2="${after_name%"$ref2"*}"
      [ "${#head2}" -gt "${#head}" ] && head="$head2" ;;
    esac
    head2="${head//&&/}"
    if [ "$after_sep" != "&&" ] || [[ $head == *";"* ]] || [[ $head == *"$nl"* ]] \
        || [[ $head == *"||"* ]] || [[ $head2 == *"&"* ]]; then
      RESOLVED=D; return 0
    fi
  fi

  case "$value" in
    \'*\') value="${value#\'}"; value="${value%\'}" ;;
    \"*\") value="${value#\"}"; value="${value%\"}" ;;
  esac
  if [ -z "$value" ] || ! [[ $value =~ $path_re ]]; then
    RESOLVED=D; return 0
  fi

  # Everything after the assignment: remove the plain references, then
  # refuse to expand if NAME is still mentioned, or if something that can
  # set a variable without naming it runs.
  # The tests are bash regex matches on the whole text, not `printf | grep
  # -q`: under pipefail, grep -q stops at its first match, printf then dies
  # of SIGPIPE on a long command, and the pipeline reads as "no match" -
  # which here would expand. Newlines count as separators in both patterns.
  stripped="$(printf '%s\n' "$after_name" \
    | sed -E "s/[\$][{]${name}[}]//g; s/[\$]${name}([^A-Za-z0-9_])/\\1/g; s/[\$]${name}\$//")"
  mention_re="(^|[^A-Za-z0-9_])${name}([^A-Za-z0-9_]|\$)"
  if [[ $stripped =~ $mention_re ]]; then
    RESOLVED=D; return 0
  fi
  if [[ $after_name =~ $binder_re ]]; then
    RESOLVED=D; return 0
  fi

  RESOLVED="V$value"
}

# The shared work budget (see WORK_BUDGET above) is spent: the same refusal as
# the other limits where Compass is in use, and only the write scan is skipped
# elsewhere.
WORK_REFUSAL="has=too many statements, names and targets to scan together|over=that many statements, names and targets"
work_over() {
  [ "$COMPASS_IN_USE" -eq 1 ] \
    && compass_block bash-command-too-complex "${WORK_REFUSAL%%|*}" "${WORK_REFUSAL#*|}"
  exit 0
}
