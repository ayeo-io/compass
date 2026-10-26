# shellcheck shell=bash
# shellcheck disable=SC2034,SC2154  # the parts share variables; checked joined, none is unused or unset
# Part of hooks/pre-tool.sh: classify a target file, and the comment-only Edit.
# hooks/pre-tool.sh sources each part in order, at its top level, so the parts
# run as one script in one shell. This file is not a hook of its own.

# --- classify a target file -------------------------------------------------
# A "code file" here means: a production-impacting file whose change must be
# preceded by a failing test. That is broader than application source - a
# Terraform file, a SQL migration, a Kubernetes manifest, or a CI workflow can
# be more dangerous than ordinary code. Test files, docs, and Compass's own
# artifacts are exempt.
#
# This is a function rather than a straight-line sequence because a single
# tool call can name more than one path: a Bash command may redirect into one
# file and copy over another. Both branches share this one implementation so
# the rules cannot differ - a path exempt for an Edit is exempt for a shell
# redirect, by construction.
#
# Returns 0 (true) if a change to $1 must be preceded by a failing test.
MATCHED_RULE=""
# The settings read once by is_enforced_path (see the code_globs block): whether
# it ran, how it ended, the file it read, whether bash can match the globs
# itself ("safe"), the globs as a JSON list, and the safe globs one to a line.
GLOBS_LOADED=0 GLOBS_STATUS=0 GLOBS_ERR="" GLOBS_FILE="" GLOBS_KIND="" GLOBS_JSON="" GLOBS_LIST=""
# While GLOB_DEFER is 1, a path that only a glob bash cannot decide could
# enforce is not judged: its project-relative text is added to GLOB_PENDING
# (one per line) and is_enforced_path returns 2 for it.
GLOB_DEFER=0 GLOB_PENDING="" GLOBS_COUNT=0
is_enforced_path() {
  local target="$1" rel base is_code=0 abs

  # CONTAINMENT FIRST: only guard what is inside the project Compass governs.
  #
  # Without this, the extension rules below would fire on any .py/.ts/.go file
  # on the machine, such as a scratch file in a temp directory, and demand a
  # failing test for a file that cannot reach main.
  #
  # The target is resolved first, because a Bash redirect yields a RELATIVE
  # path: comparing `src/app.py` against an absolute project directory would
  # answer "outside" and switch enforcement off for exactly the writes the
  # hook is here for.
  # Resolved against PROJECT_DIR, not the hook's own working directory. The
  # hook cannot know the shell's cwd, and guessing wrong in that direction
  # fails OPEN - a relative write would be judged outside the project and
  # allowed. A relative path in an agent's command is against the project root
  # in practice, and being wrong the other way costs only a visible refusal.
  abs="$target"
  case "$abs" in
    /*) ;;
    *) abs="$PROJECT_DIR/$abs" ;;
  esac
  # Judge where the path points, not how it is spelled: `/tmp/../<project>/x`,
  # `//<project>/x` and `<project>/./x` all reach the project, and
  # `<project>/../elsewhere/x` leaves it. The steps are resolved as text; a
  # symbolic link is not followed. A path that differs from the project only
  # in letter case is treated as inside it, because macOS and Windows file
  # systems ignore case; on a file system that does not, that costs a visible
  # refusal, never a missed one.
  #
  # A `..` after a part the hook cannot know - an unexpanded `$NAME`, a
  # backtick, `~` or a brace list - would cancel that part as text, though
  # the shell may expand it to several directories or to none. Such a path
  # points somewhere unknowable, so it is judged inside the project, as the
  # text comparison did before.
  local proj inside=0 unknowable=0
  normalise_path "$PROJECT_DIR"; proj="$NORMALISED"  # us-english-scan: allow - shell variable name, not prose
  case "$abs" in
    *'$'*|*'`'*|*'~'*|*'{'*)
      case "/$abs/" in
        */../*) unknowable=1; inside=1 ;;
      esac ;;
  esac
  if [ "$unknowable" -eq 0 ]; then
    normalise_path "$abs"; abs="$NORMALISED"  # us-english-scan: allow - shell variable name, not prose
  fi
  case "$abs" in
    "$proj"/*) inside=1 ;;
  esac
  if [ "$inside" -eq 0 ] && [ "${#abs}" -gt "${#proj}" ] \
      && [ "${abs:${#proj}:1}" = "/" ] \
      && [ "$(printf '%s' "${abs:0:${#proj}}" | tr '[:upper:]' '[:lower:]')" = \
           "$(printf '%s' "$proj" | tr '[:upper:]' '[:lower:]')" ]; then
    inside=1
  fi
  [ "$inside" -eq 1 ] || return 1
  # From here every rule reads the resolved path, so a `..` step cannot
  # borrow an exemption: `.compass/../src/app.py` is `src/app.py`. A target
  # given as a relative path stays relative, and an absolute one absolute,
  # as before.
  if [ "$unknowable" -eq 1 ]; then
    # Judged by its text, as written.
    rel="${target#"$PROJECT_DIR"/}"
  else
    rel="${abs:$((${#proj} + 1))}"
    case "$target" in
      /*) target="$abs" ;;
      *) target="$rel" ;;
    esac
  fi

  # Always exempt: Compass artifacts, docs, lockfiles, the obvious non-code.
  #
  # A path judged by its text after an unknown part and a `..` step does not
  # get the `.compass/` exemption, or the test-directory one below: the
  # directories named before the last `..` say nothing about where the file
  # lands, so `$X/../.compass/../src/app.py` may be `src/app.py`
  # (ayeo-io/compass-delivery-record#187). The file-name and extension rules
  # still apply, because a `..` step cannot change the last part of a path.
  if [ "$unknowable" -eq 0 ]; then
    case "$target" in
      *.compass/*|*/.compass/*) return 1 ;;
    esac
  fi
  case "$target" in
    *.md|*.markdown|*.txt|*.rst|*.adoc) return 1 ;;
    *.lock|*.gitignore|*.gitkeep|*.gitattributes|*.editorconfig) return 1 ;;
  esac

  # Exempt: test files - you have to be able to write the red. Tune these globs
  # to the project's test conventions.
  #
  # Match the basename and the project-relative path, never the absolute
  # path: matching `*test*` against an absolute path also matches every
  # ancestor directory, so a repository living under any path containing
  # "test" or "spec" - /Users/testuser/..., .../latest/... - would have
  # red-before-green silently disabled for the entire tree. `rel` was set by
  # the containment check above.
  base="$(basename "$target")"
  # Match anchored patterns, never `*test*`: a bare substring match would call
  # latest.py, inspector.py and protest.py tests, and silently skip both
  # guardrail checks for them on the allow path, which prints nothing.
  #
  # The conventions covered: pytest/go (test_x, x_test), jest/vitest
  # (x.test.ts, x.spec.js), JUnit/RSpec class names (XTest.java, XSpec.rb),
  # and Ruby's x_spec.rb. Directory rules below catch the rest.
  case "$base" in
    test_*|spec_*) return 1 ;;
    *_test.*|*_spec.*|*.test.*|*.spec.*) return 1 ;;
    *Test.*|*Spec.*|*Tests.*|*Specs.*) return 1 ;;
    conftest.py) return 1 ;;
  esac
  if [ "$unknowable" -eq 0 ]; then
    case "$rel" in
      tests/*|*/tests/*|test/*|*/test/*|spec/*|*/spec/*|\
      __tests__/*|*/__tests__/*|testdata/*|*/testdata/*) return 1 ;;
    esac
    # Exempt: eval fixture input. `evals/<group>/<name>/seed/` holds files the
    # eval harness copies into a sandbox and never runs in place, so it is not
    # production code. `rel` is resolved and relative to the project, so the
    # pattern starts at the project root and a `..` step cannot borrow it.
    # `examples/`, `cli/vendor/`, `.github/scripts/`, `evals/` outside `seed/`,
    # `src/examples/` and `db/seed/` stay guarded: enforcement.code_globs only
    # ratchets up (ADR-011). In `case`, `*` also matches `/`.
    case "$rel" in
      evals/*/seed/*) return 1 ;;
    esac
  fi

  # (a) recognised application source extensions.
  case "$target" in
    *.ts|*.tsx|*.js|*.jsx|*.mjs|*.cjs) is_code=1 ;;
    *.py|*.rb|*.go|*.rs|*.java|*.kt|*.kts) is_code=1 ;;
    *.c|*.h|*.cc|*.cpp|*.hpp|*.cs|*.swift|*.m|*.mm) is_code=1 ;;
    *.php|*.scala|*.ex|*.exs|*.clj|*.elm|*.dart) is_code=1 ;;
  esac

  # (b) infrastructure / data / pipeline files - production-impacting even though
  #     they are not "application code". A SQL migration or a Terraform plan
  #     deserves a failing test (or a tested rollback) as much as a service does.
  case "$target" in
    *.tf|*.tfvars|*.hcl) is_code=1 ;;                       # Terraform / HCL
    *.sql) is_code=1 ;;                                     # SQL incl. migrations
    Dockerfile|*/Dockerfile|*.dockerfile) is_code=1 ;;      # container images
  esac

  # (c) path-scoped: YAML/JSON are exempt by default (config, data) - EXCEPT
  #     under infrastructure-ish paths, where a yaml IS the production change
  #     (k8s manifests, Helm charts, CI workflows, migrations, dbt models).
  #     Note: in a `case` glob, `*` also matches `/`, so `*migrations/*` catches
  #     both `migrations/x` and `db/migrations/x` - leading `*` with no slash.
  case "$target" in
    *migrations/*|*db/migrate/*) is_code=1 ;;
    *.github/workflows/*|*.gitlab-ci.yml) is_code=1 ;;
    *k8s/*|*kubernetes/*|*helm/*|*charts/*|*manifests/*|*deploy/*) is_code=1 ;;
    *terraform/*|*infra/*|*infrastructure/*) is_code=1 ;;
    *dbt/*|*models/*.sql) is_code=1 ;;
  esac

  if [ "$is_code" -eq 1 ]; then
    MATCHED_RULE="the built-in production-code set"
    return 0
  fi

  # (d) the project's own declaration, in the project's settings file
  # (`compass.yml`, or `.compass/config.yml` for a project that has not moved
  # its settings):
  #
  #     enforcement:
  #       code_globs: ["*.sh", "packaging/**"]
  #
  # This ADDS to the set above. There is deliberately no key that removes
  # framework enforcement: Compass's model is that project rules ratchet UP - a
  # project guardrail may exceed a floor, never fall short of one - and a key
  # that exempted `*.py` would switch enforcement off, and someone would add
  # it the first time a red got in the way.
  #
  # Why this exists: without a declared list an author cannot predict which
  # edit will block (`.github/workflows/ci.yml` is guarded, `docker-compose.yml`
  # is not).
  #
  # Which file holds the declaration, and how it is read, is
  # project_settings's question, not this hook's. The hook only asks whether a
  # settings file exists, through the one helper that names them, so a project
  # with none costs no Python start on an edit to a path the sets above
  # neither guard nor exempt.
  if [ -d "$PROJECT_DIR/.compass" ] && compass_has_settings_file "$PROJECT_DIR"; then
    local hit="" glob_out glob_status g g2 g3
    # A reader that ran and matched nothing means the path is not
    # project-guarded. A reader that could not run - no python3, a broken
    # install, or a config it cannot parse - means we do not know whether it
    # is, and answering "not guarded" to a question we could not ask is how a
    # broken install quietly stops guarding the very scripts that broke it.
    #
    # The settings are read once per hook run, not once per path: a command
    # with hundreds of write targets would otherwise start Python for each one
    # (about 50 ms each). The outcome is kept in the GLOBS_* variables,
    # including a failure, and every path is judged against it below, so a
    # reader that failed refuses for every path, never only the first.
    if [ "$GLOBS_LOADED" -eq 0 ]; then
      GLOBS_LOADED=1
      GLOBS_ERR="$(mktemp 2>/dev/null)" \
        || compass_reader_failed "enforcement.code_globs reader" tmp
      set +e
      # The reader prints the settings file it read on its first line, so a
      # refusal can name that file. Then come "safe" or "unsafe", the globs as
      # a JSON list, and, when safe, the globs one to a line. A failure prints
      # the file the error names, which can be the old file when `compass.yml`
      # was the one read. A glob is safe when bash's `case` matches it as
      # Python's fnmatch does: letters, digits, `*`, `?` and a few punctuation
      # marks. Any other glob (a bracket set, a backslash, an empty glob) is
      # matched by Python: one start for a single path, and one start for all
      # the write targets of a Bash command (settle_deferred_globs).
      glob_out="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_code_globs.py" "$PROJECT_DIR" 2>"$GLOBS_ERR" </dev/null)"
      GLOBS_STATUS=$?
      set -e
      GLOBS_FILE="${glob_out%%$'\n'*}"
      if [ "$GLOBS_STATUS" -eq 0 ]; then
        # A warning the reader wrote (a `compass.yml` it ignored) is for the
        # person, once; it does not change the decision.
        [ -s "$GLOBS_ERR" ] && cat "$GLOBS_ERR" >&2 || true
        rm -f "$GLOBS_ERR"
        GLOBS_KIND="$(printf '%s\n' "$glob_out" | sed -n '2p')"
        GLOBS_JSON="$(printf '%s\n' "$glob_out" | sed -n '3p')"
        GLOBS_LIST="$(printf '%s\n' "$glob_out" | sed -n '4,$p')"
        # (A substitution that deletes every character but the line ends took
        # 2 s on 300 globs, so the lines are counted in a loop.)
        GLOBS_COUNT=0
        while IFS= read -r g; do
          GLOBS_COUNT=$((GLOBS_COUNT + 1))
        done <<<"$GLOBS_LIST"
      fi
    fi
    # The same outcome for every path: a failed read refuses each time.
    if [ "$GLOBS_STATUS" -eq 5 ]; then
      emit_refusal settings-conflict "target=${TARGET:-${candidate:-?}}" \
        "tool=${TOOL:-?}" \
        "keys=$(sed -n '1p' "$GLOBS_ERR")"
      rm -f "$GLOBS_ERR"
      exit 2
    elif [ "$GLOBS_STATUS" -eq 4 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$GLOBS_STATUS" \
        "$GLOBS_ERR" "$GLOBS_FILE"
    elif [ "$GLOBS_STATUS" -ne 0 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$GLOBS_STATUS" "$GLOBS_ERR"
    fi
    if [ "$GLOBS_KIND" = safe ]; then
      # Python's three tests, in the order it ran them: the glob as written,
      # the glob as a folder, and the glob after any leading folders.
      WORK_USED=$((WORK_USED + COST_GLOB * GLOBS_COUNT))
      while IFS= read -r g; do
        [ -n "$g" ] || continue
        g2="$g"; while [ "${g2%/}" != "$g2" ]; do g2="${g2%/}"; done
        g3="$g"; while [ "${g3#/}" != "$g3" ]; do g3="${g3#/}"; done
        case "$rel" in
          $g|$g2/*) hit="$g"; break ;;
        esac
        case "/$rel" in
          */$g3) hit="$g"; break ;;
        esac
      done <<<"$GLOBS_LIST"
    elif [ "$GLOB_DEFER" -eq 1 ]; then
      # The candidate loop of a Bash command settles every path that reaches
      # this point in one Python start, after the loop (settle_deferred_globs).
      GLOB_PENDING="$GLOB_PENDING$rel"$'\n'
      return 2
    else
      set +e
      hit="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_glob_match.py" "$rel" "$GLOBS_JSON" 2>"$GLOBS_ERR.m" </dev/null)"
      glob_status=$?
      set -e
      [ "$glob_status" -eq 0 ] \
        || compass_reader_failed "enforcement.code_globs reader" "$glob_status" "$GLOBS_ERR.m"
      rm -f "$GLOBS_ERR.m"
    fi
    if [ -n "${hit:-}" ]; then
      MATCHED_RULE="enforcement.code_globs pattern '$hit' in $GLOBS_FILE"
      return 0
    fi
  fi

  # Anything still unrecognised is allowed - the enforcer blocks KNOWN
  # production-impacting files; it does not block the unknown. If a project has
  # a production-impacting file type that slips through, declare it above.
  return 1
}

# Judge the paths is_enforced_path set aside (GLOB_PENDING) against the globs
# bash cannot match, in one Python start. The first path, in the order the
# command wrote them, that a glob matches is the answer: the number of its line
# in GLOB_PENDING is printed, then the glob. The paths go in a file, so their
# number and length are not limited by the size of an argument list. The
# matcher is the one a single path uses, so the two cannot differ. A matcher
# that cannot run refuses, and so does it for every path, because none was
# judged. Sets GLOB_HIT_INDEX to that number (0 for none) and GLOB_HIT to the
# glob.
GLOB_HIT_INDEX=0 GLOB_HIT=""
settle_deferred_globs() {
  local out status
  GLOB_HIT_INDEX=0 GLOB_HIT=""
  [ -n "$GLOB_PENDING" ] || return 0
  printf '%s' "$GLOB_PENDING" > "$GLOBS_ERR.r" 2>/dev/null \
    || compass_reader_failed "enforcement.code_globs reader" tmp
  set +e
  out="$(compass_python "$HOOK_ROOT/hooks/py/pre_tool_settle_globs.py" "$GLOBS_JSON" "$GLOBS_ERR.r" 2>"$GLOBS_ERR.m" </dev/null)"
  status=$?
  set -e
  rm -f "$GLOBS_ERR.r"
  [ "$status" -eq 0 ] \
    || compass_reader_failed "enforcement.code_globs reader" "$status" "$GLOBS_ERR.m"
  rm -f "$GLOBS_ERR.m"
  if [ -n "$out" ]; then
    GLOB_HIT_INDEX="${out%%$'\n'*}"
    GLOB_HIT="${out#*$'\n'}"
  fi
  return 0
}

# --- an Edit that changes only comments ---------------------------------------
# A comment cannot change what code does, so an Edit of a Python or YAML file
# that changes only comments, docstrings or layout needs no failing test and no
# assessed issue. cli/compass_pkg/comment_only_edit.py proves it: it reads the
# file once, applies the Edit in memory and compares the file before and after.
# Shell and every other language are not covered, and every doubt gives "no",
# which is the verdict this hook gave before the check existed: a failed check,
# an over-budget one, an alarm, a file over 1 MiB, a pragma. Only a missing
# python3 refuses here, as every reader of this hook does (python-missing).
#
# The check starts no process for a target that is not an absolute .py, .yml or
# .yaml path, or where Compass is not in use. It is charged to WORK_USED by the
# figure the module prints, and the alarm is the smaller of EDIT_ALARM_SECONDS
# and what is left before FUSE_SECONDS, less one second for the rest of the
# hook; with less than one second left no check starts. A process that the
# alarm ends gives no figure, so the whole alarm is charged. The old and new
# text of the Edit go to python3 on its input, never through the command line.
#
# The check runs after is_enforced_path and before the issue lookup, so a
# comment edit needs no assessed issue. It reads the file once and cannot lock
# it: a change between the read and the Edit is not detected.
comment_only_edit_allowed() {
  [ "${COMPASS_IN_USE:-0}" -eq 1 ] || return 1
  case "${TARGET:-}" in
    /*.py|/*.yml|/*.yaml) ;;
    *) return 1 ;;
  esac
  # An Edit names its old and new text. A call that holds neither has nothing to
  # compare, and the check would answer "no", so it starts no process.
  case "$INPUT" in
    *'"old_string"'*'"new_string"'*|*'"new_string"'*'"old_string"'*) ;;
    *) return 1 ;;
  esac
  if ! command -v python3 >/dev/null 2>&1; then
    compass_reader_failed "comment-only check" 127
  fi
  local alarm remaining out status verdict charge
  alarm=$((FUSE_SECONDS - (SECONDS - HOOK_START) - 1))
  [ "$alarm" -le "$EDIT_ALARM_SECONDS" ] || alarm="$EDIT_ALARM_SECONDS"
  [ "$alarm" -ge 1 ] || return 1
  remaining=$((WORK_BUDGET - WORK_USED))
  [ "$remaining" -gt "$COST_EDIT_START" ] || return 1
  set +e
  # The braces keep the message bash prints for a child ended by the alarm out
  # of this hook's own output.
  out="$({ printf '%s' "$INPUT" | compass_python "$HOOK_ROOT/hooks/py/pre_tool_comment_only_edit.py" "alarm=$alarm" "remaining=$remaining" "start=$COST_EDIT_START" \
    "parse_py=$COST_EDIT_PARSE_PY" "parse_yaml=$COST_EDIT_PARSE_YAML" \
    "kb_py=$COST_EDIT_KB_PY" "kb_yaml=$COST_EDIT_KB_YAML"; } 2>/dev/null)"
  status=$?
  set -e
  verdict="${out%%$'\n'*}"
  charge=""
  case "$out" in *$'\n'*) charge="${out#*$'\n'}" ;; esac
  # Anything but a plain "yes" and a charge of at most nine digits is "no". A
  # run that failed is charged the whole alarm, the most it could have taken.
  case "$charge" in
    ""|*[!0-9]*) status=1 ;;
    *) [ "${#charge}" -le 9 ] || status=1 ;;
  esac
  if [ "$status" -ne 0 ]; then
    WORK_USED=$((WORK_USED + alarm * 1000000))
    return 1
  fi
  WORK_USED=$((WORK_USED + 10#$charge))
  [ "$verdict" = yes ]
}
