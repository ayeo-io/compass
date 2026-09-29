#!/usr/bin/env bash
# =============================================================================
# Compass hook: pre-tool.sh  -  THE RED-BEFORE-GREEN STRATEGY ENFORCER
# =============================================================================
# Enforces the red-before-green strategy mechanically - in service of the
# guardrail that every change lands with a passing automated test covering it.
#
#   * The GUARDRAIL is the hard line: no code ships without a passing test it
#     traces to. It is checked at the verify stage and at ship time, with
#     evidence.
#   * Red-before-green is a STRATEGY - the strong, shipped-on *way* to satisfy
#     that guardrail. This hook enforces the strategy, and a strategy is aware
#     of the delivery approach.
#
# This hook therefore BLOCKS code edits with no failing test on record -
# EXCEPT on a spike, where the strategy is deliberately suspended so
# exploratory edits are not blocked. A spike still cannot cross the
# guardrail: nothing ships from a spike without being reassessed
# (`/compass:assess --reassess`) into a delivery approach first, where this
# hook applies in full.
#
# WHAT IT DOES
#   Runs as a Claude Code PreToolUse hook. On a tool call that edits or writes a
#   *code* file (not a test, not docs, not a Compass artifact):
#     - if the current issue is a spike (a ".spike" marker exists) → ALLOW.
#     - else, need a recorded failing test - a ".red" marker file under
#       .compass/work/<issue-slug>/. No .red marker → the edit is BLOCKED.
#
# THE MARKER CONVENTION
#   .compass/work/<issue-slug>/.red    "a failing test exists for this
#                                      issue". It is NOT a bare `touch` - it is
#                                      written by `compass tdd-red <test-cmd>`,
#                                      which runs the test, confirms it really
#                                      fails, writes evidence/red.json with the
#                                      command + exit code + log, and only THEN
#                                      drops the .red marker. So the marker
#                                      means "a real, observed failure is on
#                                      record", not "someone touched a file".
#     1. The implement stage: `compass tdd-red -- <your failing test command>`.
#     2. Edit the production code - this hook sees .red and allows it.
#     3. `compass tdd-green -- <test command>` confirms green, writes
#        evidence/green.json, and clears .red - the hand-off to the verify stage.
#   .compass/work/<issue-slug>/.spike  "this issue is a spike - the red-
#                                      before-green strategy is suspended".
#                                      /compass:assess
#                                      writes this when it composes a Spike.
#   Markers are deliberately plain files so they are inspectable and auditable;
#   the evidence/*.json records next to them are the audit trail.
#
# EXEMPTIONS
#   Test files, docs, config, and .compass/ artifacts are never blocked - you
#   must be able to write the failing test in the first place. A spike is the
#   deliberate exemption for exploratory work. There is no env var to disable
#   the check on delivery work: that would not be suspending a strategy, it
#   would be crossing the tested-before-ship guardrail.
#
# WIRING  (.claude/settings.json)
#   {
#     "hooks": {
#       "PreToolUse": [
#         { "matcher": "Edit|Write|Bash",
#           "hooks": [ { "type": "command",
#                        "command": "$CLAUDE_PROJECT_DIR/hooks/pre-tool.sh" } ] }
#       ]
#     }
#   }
#   `scripts/install.sh` registers this for you.
#
# I/O CONTRACT  (Claude Code hook format)
#   stdin : JSON describing the tool call.
#   block : exit code 2  (Claude Code treats exit 2 on PreToolUse as "deny").
#   allow : exit code 0.
#   We also emit a short human-readable reason on stderr when blocking.
# =============================================================================

set -euo pipefail

# shellcheck source=../scripts/lib/compass-python.sh
# The shared loader in scripts/lib/compass-python.sh: compass_python() below
# reaches the bundled PyYAML the same way cli/compass does, rather than this
# hook inventing its own answer to "where is the vendored copy".
#
# A missing helper must not end this script under `set -e` with exit 1, which
# the runtime lets through. Without it, a stand-in answers every reader with
# exit 3 and a reason, so an opted-in project refuses and names the file, and
# a repository that never opted in reaches its silent exit 0 as before.
HOOK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPASS_PYTHON_SH="$HOOK_ROOT/scripts/lib/compass-python.sh"
if [ -f "$COMPASS_PYTHON_SH" ]; then
  source "$COMPASS_PYTHON_SH"
else
  compass_python() {
    cat >/dev/null
    echo "the shared loader $COMPASS_PYTHON_SH is missing" >&2
    return 3
  }
fi

# --- one registry, one shape, for every refusal ------------------------------
# cli/compass_pkg/refusals.py is the one place a refusal's wording lives
# (spec D38); `compass _refusal <code> key=value ...` is the CLI's front
# door onto it, for docs generation and any external caller. This hook
# reaches the registry directly - `import compass_pkg.refusals`, the same
# narrow import every other reader in this file makes - rather than through
# `cli/compass`, which pulls in every command module at start-up and needs
# newer syntax than this hook's other readers do. A refusal is printed on
# every blocked call in every session, so it keeps the same low bar for
# what has to run as the rest of the hook.
#
# python3 existing but failing every call (not merely missing - a broken
# install, exit 1/2/3/127 on anything) would otherwise render THIS call
# silent too, since rendering a refusal about python3 failing is itself a
# python3 call. So a failed render falls back to a fixed line in shell
# rather than nothing - tests/test_evidence_gaps.py::test_evg_c1_* plants
# exactly this. `command -v python3` failing outright (python3-missing
# below) is the one case that never reaches this function at all.
emit_refusal() {
  local code="$1"; shift
  local out status
  set +e
  out="$(compass_python - "$code" "$@" 2>&1 <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.refusals import render

code = sys.argv[1]
params = dict(arg.split("=", 1) for arg in sys.argv[2:])
print(render(code, **params))
PYEOF
)"
  status=$?
  if [ -z "$out" ]; then
    # Nothing at all came back - not even the underlying failure's own
    # message (test_evidence_gaps.py's shim exits non-zero and prints
    # nothing). A non-zero status WITH output is still shown as-is just
    # below: it is real diagnostic text (an import-time "install is
    # incomplete" message, a missing-helper notice), and more useful than
    # this generic line.
    printf 'Blocked: this edit\nWhy: python3 could not render the %s refusal (it exited %s).\nFix: check the python3 install (python3 --version), then retry. [%s]\n' \
      "$code" "$status" "$code" >&2
    return
  fi
  printf '%s\n' "$out" >&2
}

# Renders a refusal from the registry and exits 2 - always, even if the
# render call itself fails (a python3 broken in some way not yet covered
# here). A refusal that cannot render nicely must still block, not fall
# through to exit 1 (which the runtime treats as non-blocking) or exit 0.
compass_block() {
  set +e
  emit_refusal "$@"
  exit 2
}

# --- one failure rule -------------------------------------------------------
# Inside an opted-in project, a check that cannot run refuses with exit 2 and
# names what could not run. Exit 1 is not a refusal - the runtime treats it as
# a non-blocking error and lets the edit through - and a refusal that blames
# the issue when the install is broken sends the user to the wrong fix. Every
# Python reader below calls this on any non-zero status.
compass_reader_failed() {
  local reader="$1" status="$2" errfile="${3:-}" fix_override="${4:-}"
  local target="${TARGET:-${candidate:-?}}" tool="${TOOL:-?}" errline=""
  if [ -n "$errfile" ] && [ -s "$errfile" ]; then
    errline="$(sed -n '1p' "$errfile")"
  fi
  set +e
  if [ "$status" = "tmp" ]; then
    emit_refusal reader-failed "target=$target" "tool=$tool" "reader=$reader" \
      "cause=It could not create a temporary file for its output." \
      "detail=${errline:+ ($errline)}"
  elif ! command -v python3 >/dev/null 2>&1; then
    # python3 itself is missing - there is no CLI left to render this with,
    # so this is a byte-identical static copy of
    # render("python-missing", target=..., tool=...). Kept in step by
    # tests/test_refusal_registry.py::test_rtp_3_no_python3_names_python_missing_and_matches_the_registry.
    printf 'Blocked: edit to %s (tool: %s)\nWhy: python3 was not found on the PATH, so Compass cannot check whether this edit is allowed.\nFix: install python3 (3.9+) or put it on PATH, then retry. [python-missing]\n' "$target" "$tool" >&2
  elif [ -n "$fix_override" ]; then
    emit_refusal config-invalid "target=$target" "tool=$tool" "detail=$errline"
  else
    emit_refusal reader-failed "target=$target" "tool=$tool" "reader=$reader" \
      "cause=It exited $status." "detail=${errline:+ ($errline)}"
  fi
  [ -n "$errfile" ] && rm -f "$errfile"
  exit 2
}

# --- read the tool call from stdin ------------------------------------------
INPUT="$(cat || true)"

# Pull the target file path out of the JSON. Prefer jq; fall back to grep so the
# hook still works on a machine without jq installed.
if command -v jq >/dev/null 2>&1; then
  TARGET="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty' 2>/dev/null || true)"
  TOOL="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)"
  COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
else
  TARGET="$(printf '%s' "$INPUT" | grep -oE '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
  TOOL="$(printf '%s' "$INPUT" | grep -oE '"tool_name"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
  COMMAND="$(printf '%s' "$INPUT" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -n1 | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/' || true)"
fi

# --- resolve the project this hook is enforcing -----------------------------
# The resolution order, and why each step exists:
#   1. The edited file's own path, when the tool call names one. It is the
#      only input that names the tree being changed - Compass creates git
#      worktrees at breakdown, so on a multiagent approach the session
#      directory and the edited file can be in different trees, and resolving
#      from the session reads the wrong project either way: it can miss a red
#      recorded in the edited tree, or borrow one recorded in the session's
#      tree.
#   2. CLAUDE_PROJECT_DIR, when the tool call names no file (a Bash call with
#      no write target). The session is the best answer there.
#   3. The ancestor walk from that starting point up to the nearest
#      .compass/ directory, bounded by .git so the walk does not cross into
#      another repository.
#
# Not resolved from this script's own location: the hook is installed from
# the plugin cache, and Compass self-hosts, so its own tree has a .compass/
# of its own. Resolving from there would enforce the framework's own issue
# against the user's edits.
#
# resolve_project() runs twice: once here, for a tool that names a file
# directly, and again once a Bash command's target has been extracted
# further down.
SESSION_DIR="$(pwd)"

resolve_project() {
  _from="$SESSION_DIR"
  if [ -n "${1:-}" ]; then
    case "$1" in
      /*) _dir="$(dirname "$1")" ;;
      # A relative path from the host is relative to the PROJECT, not to
      # wherever the hook happens to be running. Resolved against the
      # session, a relative path can leave the project and reach the
      # framework's own .compass/, whose red would allow the edit.
      *)  _dir="$(dirname "${CLAUDE_PROJECT_DIR:-$SESSION_DIR}/$1")" ;;
    esac
    # The file may not exist yet - a Write creates one - so climb to the
    # nearest ancestor that does. Falling back to the session instead would
    # resolve a different project whenever the session sits outside the tree
    # being edited, which is the case this exists for.
    while [ -n "$_dir" ] && [ "$_dir" != "/" ] && [ ! -d "$_dir" ]; do
      _dir="$(dirname "$_dir")"
    done
    [ -d "$_dir" ] && _from="$_dir"
  fi
  INVOKED_FROM="$_from"
  if [ -n "${CLAUDE_PROJECT_DIR:-}" ] && [ -z "${1:-}" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
    return 0
  fi
  PROJECT_RESOLVED=1
  PROJECT_DIR=""
  _search="$INVOKED_FROM"
  while [ -n "$_search" ]; do
    if [ -d "$_search/.compass" ]; then
      PROJECT_DIR="$_search"
      break
    fi
    # Stop at the repository root. A walk past it can reach another
    # project's .compass/ (a monorepo sibling, a stray one in $HOME) and
    # allow the edit if that issue has a red on record.
    #
    # -e, not -d: in a git worktree .git is a file, and Compass creates
    # worktrees itself for multiagent orchestrations.
    [ -e "$_search/.git" ] && break
    [ "$_search" = "/" ] && break
    _search="$(dirname "$_search")"
  done
  if [ -z "$PROJECT_DIR" ]; then
    PROJECT_RESOLVED=0
    # Provisional, so path classification still has something to compare
    # against. Nothing is permitted on the strength of it.
    PROJECT_DIR="$INVOKED_FROM"
  fi
}

# Whether the walk found anything is recorded, not acted on yet. The refusal
# lives further down, at the point the hook actually needs issue state - a
# read-only Bash call is allowed without a project at all, and refusing here
# would make the cheap path expensive and wrong.
#
# Trust an explicit CLAUDE_PROJECT_DIR without checking for .compass/. The
# missing-.compass/work/ branch below gives the useful message.
PROJECT_RESOLVED=1

# Bash keeps the session as its project: its target is extracted much later,
# by a classifier that resolves candidates against PROJECT_DIR, and
# re-running resolution inside that loop would break every write shape it
# guards. So the worktree fix covers the tools that name a file directly -
# Edit and Write - which is where a builder in a worktree actually works. A
# Bash redirect inside a worktree still resolves from the session;
# docs/safety-contract.md states that scope.
if [ "${TOOL:-}" = "Bash" ]; then
  resolve_project ""
else
  resolve_project "${TARGET:-}"
fi


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
  case "$abs" in
    "$PROJECT_DIR"/*) ;;
    *) return 1 ;;
  esac

  # Always exempt: Compass artifacts, docs, lockfiles, the obvious non-code.
  case "$target" in
    *.compass/*|*/.compass/*) return 1 ;;
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
  # red-before-green silently disabled for the entire tree.
  rel="$target"
  case "$target" in
    "$PROJECT_DIR"/*) rel="${target#"$PROJECT_DIR"/}" ;;
  esac
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
  case "$rel" in
    tests/*|*/tests/*|test/*|*/test/*|spec/*|*/spec/*|\
    __tests__/*|*/__tests__/*|testdata/*|*/testdata/*) return 1 ;;
  esac

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

  # (d) the project's own declaration. `.compass/config.yml`:
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
  if [ -f "$PROJECT_DIR/.compass/config.yml" ]; then
    local hit glob_status glob_err
    # A reader that ran and matched nothing means the path is not
    # project-guarded. A reader that could not run - no python3, a broken
    # install, or a config it cannot parse - means we do not know whether it
    # is, and answering "not guarded" to a question we could not ask is how a
    # broken install quietly stops guarding the very scripts that broke it.
    glob_err="$(mktemp 2>/dev/null)" \
      || compass_reader_failed "enforcement.code_globs reader" tmp
    set +e
    hit="$(compass_python - "$PROJECT_DIR/.compass/config.yml" "$rel" 2>"$glob_err" <<'PYEOF'
import fnmatch, sys
import compass_pkg
try:
    import yaml
    with open(sys.argv[1], encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    globs = ((cfg.get("enforcement") or {}).get("code_globs")) or []
    # A string would be walked one character at a time, and `*` alone
    # guards every path. Any other shape is a config this cannot read.
    if not isinstance(globs, list) or not all(isinstance(g, str) for g in globs):
        raise ValueError("enforcement.code_globs must be a list of strings, "
                         "not %r" % (globs,))
except Exception as exc:            # unreadable config -> cannot answer
    print("could not read enforcement.code_globs from .compass/config.yml: "
          "%s" % exc, file=sys.stderr)
    sys.exit(4)
path = sys.argv[2]
for g in globs:
    if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, g.rstrip("/") + "/*") \
            or fnmatch.fnmatch("/" + path, "*/" + g.lstrip("/")):
        print(g)
        break
PYEOF
)"
    glob_status=$?
    set -e
    if [ "$glob_status" -eq 4 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$glob_status" \
        "$glob_err" "Fix .compass/config.yml and re-try."
    elif [ "$glob_status" -ne 0 ]; then
      compass_reader_failed "enforcement.code_globs reader" "$glob_status" "$glob_err"
    fi
    rm -f "$glob_err"
    if [ -n "${hit:-}" ]; then
      MATCHED_RULE="enforcement.code_globs pattern '$hit' in .compass/config.yml"
      return 0
    fi
  fi

  # Anything still unrecognised is allowed - the enforcer blocks KNOWN
  # production-impacting files; it does not block the unknown. If a project has
  # a production-impacting file type that slips through, declare it above.
  return 1
}

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
    # write a file, so `&` is excluded from the target.
    printf '%s\n' "$cmd" \
      | grep -oE '[0-9]?>>?[[:space:]]*[^&<>|;()[:space:]]+' \
      | sed -E 's/^[0-9]?>>?[[:space:]]*//' || true

    # In-place editors and explicit writers: hand over every argument and let
    # the classifier decide which of them is a production file.
    case "$cmd" in
      *"sed -i"*|*"perl -i"*|*"tee "*)
        printf '%s\n' "$cmd" | tr ' \t' '\n\n' | grep -vE '^-' || true ;;
    esac

    # Copy and move write to their LAST argument. Only the destination counts -
    # reading a source file is not a change to it.
    case "$cmd" in
      cp\ *|mv\ *|*[\;\&\|]\ *cp\ *|*[\;\&\|]\ *mv\ *)
        printf '%s\n' "$cmd" | awk '{print $NF}' || true ;;
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
    #   - The path must come from the write call itself, not from scanning
    #     the whole command. Lifting paths out of a heredoc body would demand
    #     a failing test for a migration that a document merely *named*.
    # A missed write is recoverable; a false block trains people to bypass the
    # hook, and nothing recovers from that.

    # open(PATH, "w"|"a"|"x"|"r+"|"wb"…) - a mode containing w, a, x or + .
    printf '%s\n' "$cmd" \
      | grep -oE "open\([[:space:]]*['\"][^'\"]+['\"][[:space:]]*,[[:space:]]*['\"][^'\"]*[waxWAX+][^'\"]*['\"]" \
      | sed -E "s/^open\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true

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
          | grep -oE "Path\([[:space:]]*['\"][^'\"]+['\"][[:space:]]*\)(\.[a-z_]+)?" \
          | grep -v "\.read_" \
          | sed -E "s/^Path\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true ;;
    esac

    # node / ruby equivalents, where the path is the first argument.
    printf '%s\n' "$cmd" \
      | grep -oE "(writeFileSync|appendFileSync|File\.write)\([[:space:]]*['\"][^'\"]+['\"]" \
      | sed -E "s/^[A-Za-z_.]+\([[:space:]]*['\"]([^'\"]+)['\"].*/\1/" || true
  } | grep -vE '^[[:space:]]*$' || true
}

# --- decide whether this tool call needs a red on record ---------------------
if [ "${TOOL:-}" = "Bash" ]; then
  [ -z "${COMMAND:-}" ] && exit 0

  # Cheap pre-filter, before any filesystem work: this hook now runs on every
  # Bash call in the session, and most of them write nothing.
  case "$COMMAND" in
    *">"*|*"sed -i"*|*"perl -i"*|*"tee "*|*cp\ *|*mv\ *|\
    *patch\ -p*|*"git apply"*|*open\(*|*write_text*|*writeFileSync*|*File.write*) ;;
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
    while IFS= read -r candidate; do
      [ -z "$candidate" ] && continue
      if is_enforced_path "$candidate"; then
        DETECTED="$candidate"
        break
      fi
    done <<CANDIDATES
$(bash_write_targets "$COMMAND")
CANDIDATES
  fi

  # Nothing recognisable is written → allow. See docs/safety-contract.md.
  [ -z "$DETECTED" ] && exit 0
  TARGET="$DETECTED"
else
  # No file path → nothing to enforce (e.g. a non-file tool). Allow.
  [ -z "${TARGET:-}" ] && exit 0
  is_enforced_path "$TARGET" || exit 0
fi


# Say when and how this project opted into Compass, if the record is there.
# `compass init` writes `initialised: {by, at}` into .compass/config.yml. A
# user whose project was initialised by an entry point never ran init
# themselves, so an unexplained refusal is their first sight of Compass.
compass_say_how_this_project_opted_in() {
  _cfg="$COMPASS_DIR/config.yml"
  [ -f "$_cfg" ] || return 0
  # `|| true`: this only adds a sentence to a refusal already on its way. An
  # unreadable config must not end the script under pipefail with exit 1.
  _by="$(sed -n 's/^  by: *"\{0,1\}\([^"]*\)"\{0,1\} *$/\1/p' "$_cfg" 2>/dev/null | head -1 || true)"
  _at="$(sed -n 's/^  at: *"\{0,1\}\([^"]*\)"\{0,1\} *$/\1/p' "$_cfg" 2>/dev/null | head -1 || true)"
  [ -n "$_by" ] || return 0
  if [ -n "$_at" ]; then
    echo "  This project was initialised by $_by on $_at, which is when it opted into Compass." >&2
  else
    echo "  This project was initialised by $_by, which is when it opted into Compass." >&2
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
  compass_block not-initialised "detail=no .compass/work/ exists in $PROJECT_DIR"
fi

# The current issue is named by the .compass/current-task pointer (written by
# /compass:assess and /compass:resume). The pointer is what makes this
# reliable when more than one issue is in flight - "most recently changed
# directory" is only the fallback, and it is ambiguous, so it warns. If there
# is no issue at all, the assess stage has not run for this change, and the
# hook refuses below.
TASK_DIR=""
POINTER="$COMPASS_DIR/current-task"
if [ -f "$POINTER" ]; then
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
if [ -z "$TASK_DIR" ]; then
  # fallback: most recently changed - ambiguous, so say so.
  TASK_DIR="$(ls -dt "$WORK_DIR"/*/ 2>/dev/null | head -n1 || true)"
  TASK_DIR="${TASK_DIR%/}"
  [ -n "$TASK_DIR" ] && echo "Compass: no .compass/current-task pointer - falling back to the most recently modified issue ($(basename "$TASK_DIR")). Write .compass/current-task to be unambiguous." >&2
fi

if [ -z "${TASK_DIR:-}" ]; then
  compass_say_how_this_project_opted_in
  compass_block not-initialised "detail=no issue exists under $PROJECT_DIR/.compass/work/"
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
ROUTE_PROBE="$(compass_python - "$TASK_DIR" 2>"$ROUTE_PROBE_ERR" <<'PYEOF'
import sys
import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.core import FOUND, resolve_artifact
state, _path, _reason = resolve_artifact(sys.argv[1], "delivery-approach")
print("found" if state == FOUND else "absent")
PYEOF
)"
ROUTE_PROBE_STATUS=$?
set -e
if [ "$ROUTE_PROBE_STATUS" -ne 0 ] || [ -z "$ROUTE_PROBE" ]; then
  compass_reader_failed "delivery-approach reader" "$ROUTE_PROBE_STATUS" "$ROUTE_PROBE_ERR"
fi
rm -f "$ROUTE_PROBE_ERR"
if [ "$ROUTE_PROBE" != "found" ]; then
  compass_block no-delivery-approach "slug=$TASK_SLUG"
fi

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
# Only `define: full` (or the retired `specify: full`) triggers it, which
# routing-policy.yml gives to feature and initiative work. A hotfix
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
  G2_VERDICT="$(compass_python - "$TASK_DIR/manifest.yml" 2>"$G2_ERR" <<'PYEOF'
import sys
import compass_pkg
try:
    import yaml
    with open(sys.argv[1], encoding="utf-8") as fh:
        task = yaml.safe_load(fh) or {}
    if not isinstance(task, dict):
        raise ValueError
except Exception:
    # Exit 0 means ALLOW, and that is deliberate: an unreadable or missing
    # manifest falls back to the behaviour this hook had before the check
    # existed, rather than inventing a block. A false block on unreadable
    # state trains people to bypass the hook, which costs more than the case
    # it would catch. Pinned by
    # tests/test_hook_enforces_g2.py::test_scn_f1_an_unreadable_spine_does_not_block.
    # Any non-zero status below is the check being unable to RUN (a broken
    # install), which is a different thing from the manifest being
    # unreadable.
    sys.exit(0)
stages = task.get("stages") or task.get("phases") or {}
# Read both: `define` is the current key, and archived manifests still carry
# the pre-v2 `specify`. Reading one key only would switch the guardrail off
# for every migrated manifest.
if isinstance(stages, dict):
    weight = stages.get("define", stages.get("specify"))
    if weight == "full" and not (task.get("scenarios") or []):
        print("block")
PYEOF
)"
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
  RED_VERDICT="$(compass_python - "$TASK_DIR" "$COMPASS_DIR" <<'PYEOF' 2>"$RED_ERR"
# One verdict, shared with `suite-passed`, so the hook and the check cannot
# disagree about what counts as a red. red_first.py documents each word.
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg.red_first import verdict_line

print(verdict_line(sys.argv[1], sys.argv[2]))
PYEOF
)"
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

# No .red marker → no failing test on record → block the code edit.
compass_block no-red-on-record "slug=$TASK_SLUG" "target=$TARGET" "tool=${TOOL:-?}" \
  "guard=${MATCHED_RULE:-the built-in production-code set}"
