#!/usr/bin/env bash
# =============================================================================
# Compass script: validate.sh  -  SELF-CHECK FOR THE FRAMEWORK REPO
# =============================================================================
# A consistency check for the Compass repository ITSELF - not for a project using
# Compass. It checks the directory structure is intact and that the adapter
# layer's internal references resolve: commands referencing skills, agents, and
# templates that actually exist; no dangling pointers.
#
# Run it locally before committing, and in CI on every push.
#
# USAGE
#   scripts/validate.sh            # full check, human-readable
#   scripts/validate.sh --quiet    # only print failures + the final verdict
#   scripts/validate.sh --help
#
# EXIT CODES
#   0  everything resolves
#   1  one or more checks failed (details printed)
#
# WHAT IT CHECKS
#   1. The directories and top-level files the repo needs are present.
#   2. Every expected artifact template exists in templates/.
#   3. Every agent referenced anywhere in commands/ exists in agents/.
#   4. Every skill referenced anywhere in commands/ exists in skills/.
#   5. Every template referenced in commands/ exists in templates/.
#   6. Every script and hook referenced in the repo exists and is executable.
#      It skips an issue's own documents under docs/compass/<created>-<slug>/:
#      they record what was true when written, and a script renamed since is
#      not a broken reference in a living file.
#   7. The five reference approach docs exist and the rubric references them.
#   8. The kit layer is present: the CLI, the machine-readable governance,
#      the schemas, and the manifest.yml template - and `compass policy lint`
#      passes if python3 and the CLI are runnable.
#
# This script is deliberately dependency-free (pure bash + coreutils + grep).
# PyYAML ships in cli/vendor/yaml/, so a `compass policy lint` failure is a
# real lint failure and the script reports it as one.
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPASS_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$COMPASS_HOME"

QUIET=0
case "${1:-}" in
  --quiet) QUIET=1 ;;
  # The header from USAGE to its closing rule, with the comment marker
  # stripped. A line filter picked lines by their indent, missed the
  # numbered ones, and printed headings with nothing under them.
  -h|--help) sed -n '/^# USAGE/,/^# =====/p' "$0" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
  "") ;;
  *) echo "validate.sh: unknown argument: $1" >&2; exit 1 ;;
esac

FAILURES=0
say()  { [ "$QUIET" -eq 1 ] || echo "$@"; }
ok()   { [ "$QUIET" -eq 1 ] || echo "  ok   $*"; }
fail() { echo "  FAIL $*" >&2; FAILURES=$((FAILURES + 1)); }

say "Compass repo self-check - $COMPASS_HOME"
say ""

# --- 1. required structure --------------------------------------------------
say "1. Directory structure and top-level files"
for d in docs governance approaches templates commands \
         agents skills hooks scripts .compass; do
  if [ -d "$d" ]; then ok "dir  $d/"; else fail "missing directory: $d/"; fi
done
for f in CLAUDE.md AGENTS.md README.md docs/methodology.md \
         approaches/rubric.md governance/guardrails.md governance/strategies.md \
         governance/strategies-rationale.md \
         governance/routing-policy.md .compass/config.yml; do
  if [ -f "$f" ]; then ok "file $f"; else fail "missing file: $f"; fi
done
say ""

# --- 2. expected artifact templates -----------------------------------------
say "2. Artifact templates"
for t in delivery-approach intent bug-report incident acceptance-criteria \
         requirements-review technical-design distribution-map \
         threat-model rollback-plan \
         positioning launch-readiness ui-contract verification-report devlog; do
  if [ -f "templates/$t.md" ]; then ok "template $t.md"; else fail "missing template: templates/$t.md"; fi
done
say ""

# --- helpers for reference checks -------------------------------------------
# Collect the names that actually exist.
EXISTING_AGENTS="$(cd agents 2>/dev/null && ls *.md 2>/dev/null | sed 's/\.md$//' || true)"
EXISTING_SKILLS="$(cd skills 2>/dev/null && ls -d */ 2>/dev/null | sed 's:/$::' || true)"
EXISTING_TEMPLATES="$(cd templates 2>/dev/null && ls *.md 2>/dev/null | sed 's/\.md$//' || true)"

has() { # needle  haystack(newline-separated)
  # A here-string, not a pipe: under pipefail a `grep -q` that exits at its
  # first match can fail the pipe and turn a found line into a missing one.
  grep -qxF "$1" <<<"$2"
}

# --- 3. agents referenced by commands exist ---------------------------------
say "3. Agent references in commands/"
# Match the patterns the command files actually use, e.g. "the `builder` agent",
# "`orchestrator` agent", "invoke the `router` agent".
REFS="$(grep -rohE '`[a-z][a-z-]+`[[:space:]]+agent' commands/ 2>/dev/null \
        | sed -E 's/`([a-z-]+)`.*/\1/' | sort -u || true)"
if [ -z "$REFS" ]; then
  say "  (no agent references found in commands/ - nothing to check)"
else
  for a in $REFS; do
    if has "$a" "$EXISTING_AGENTS"; then ok "agent  $a  <- referenced, exists"
    else fail "command references agent '$a' but agents/$a.md does not exist"; fi
  done
fi
say ""

# --- 4. skills referenced by commands exist ---------------------------------
say "4. Skill references in commands/"
# Commands say things like "Load the `adaptive-routing` skill".
REFS="$(grep -rohE '`[a-z][a-z-]+`[[:space:]]+skill' commands/ 2>/dev/null \
        | sed -E 's/`([a-z-]+)`.*/\1/' | sort -u || true)"
if [ -z "$REFS" ]; then
  say "  (no skill references found in commands/ - nothing to check)"
else
  for s in $REFS; do
    if has "$s" "$EXISTING_SKILLS"; then ok "skill  $s  <- referenced, exists"
    else fail "command references skill '$s' but skills/$s/ does not exist"; fi
  done
fi
say ""

# --- 5. templates referenced by commands exist ------------------------------
say "5. Template references in commands/"
# Commands say "from `templates/delivery-approach.md`" or "templates/verification-report.md".
REFS="$(grep -rohE 'templates/[a-z][a-z.-]+\.md' commands/ 2>/dev/null \
        | sed -E 's:templates/([a-z.-]+)\.md:\1:' | sort -u || true)"
if [ -z "$REFS" ]; then
  say "  (no template references found in commands/ - nothing to check)"
else
  for t in $REFS; do
    if has "$t" "$EXISTING_TEMPLATES"; then ok "template  $t  <- referenced, exists"
    else fail "command references templates/$t.md but it does not exist"; fi
  done
fi
say ""

# --- 6. scripts and hooks referenced exist and are executable ---------------
say "6. Script and hook references"
# Scan tracked files only. A recursive grep also reads untracked trees such
# as the cucumber-js adapter's node_modules/, whose package.json files name
# scripts that are not ours. Fall back to the recursive form outside a git
# checkout, e.g. inside an unpacked release tarball.
#
# Both forms skip an issue's own documents, `docs/compass/<created>-<slug>/`.
# They record what was true when written - many name a script that 4.0.0
# renamed - and rewriting them to satisfy this scan would falsify the record. It is the rule issue_layout.is_issue_document
# states for every repository-wide scan, anchored at the root so the worked
# examples under examples/ stay in scope. A flat file directly under
# docs/compass/ is not an issue's record and is still scanned.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  REFS="$(git ls-files -- '*.md' '*.json' 2>/dev/null \
          | grep -vE '^docs/compass/[^/]+/' | tr '\n' '\0' \
          | xargs -0 grep -ohE '(scripts|hooks)/[a-z-]+\.sh' 2>/dev/null \
          | sort -u || true)"
else
  REFS="$(find . \( -path './docs/compass/*' -type d \) -prune \
               -o -name node_modules -prune \
               -o -type f \( -name '*.md' -o -name '*.json' \) -print0 \
          | xargs -0 grep -ohE '(scripts|hooks)/[a-z-]+\.sh' 2>/dev/null \
          | sort -u || true)"
fi
for ref in $REFS; do
  if [ -f "$ref" ]; then
    if [ -x "$ref" ]; then ok "exec $ref  <- referenced, exists, executable"
    else fail "referenced $ref exists but is not executable (chmod +x it)"; fi
  else
    fail "referenced $ref does not exist"
  fi
done
# Also assert the canonical set is present regardless of references.
for f in hooks/pre-tool.sh hooks/post-tool.sh hooks/stop.sh \
         scripts/install.sh scripts/multiagent.sh scripts/integrate.sh scripts/validate.sh; do
  [ -f "$f" ] || fail "expected file missing: $f"
done
say ""

# --- 7. the five reference approach docs -------------------------------------
say "7. Reference approaches"
for r in quick-fix feature initiative hotfix spike; do
  if [ -f "approaches/$r.md" ]; then
    if grep -qiE "(\`|/| )$r\b" approaches/rubric.md 2>/dev/null; then
      ok "shape  $r  <- exists, named in rubric.md"
    else
      ok "shape  $r  <- exists (rubric.md mention not detected - review by eye)"
    fi
  else
    fail "missing reference shape doc: approaches/$r.md"
  fi
done
say ""

# --- 8. the kit layer -------------------------------------------------------
say "8. Kit layer - CLI, machine-readable governance, schemas, issue manifest"
# 8a. the CLI exists and is executable
if [ -f "cli/compass" ]; then
  if [ -x "cli/compass" ]; then ok "exec cli/compass  <- exists, executable"
  else fail "cli/compass exists but is not executable (chmod +x it)"; fi
else
  fail "missing the CLI: cli/compass"
fi
# 8b. the machine-readable governance the CLI runs
for f in governance/routing-policy.yml governance/guardrails.yml; do
  if [ -f "$f" ]; then ok "file $f"; else fail "missing machine-readable governance: $f"; fi
done
# 8c. the schemas directory: an executable JSON Schema and a readable
#     companion for each of the three machine-readable files.
if [ -d "schemas" ]; then
  ok "dir  schemas/"
  # vocabulary-scan: allow - the loop iterates schema basenames on disk
  for s in routing-policy guardrails manifest; do
    if [ -f "schemas/$s.schema.json" ]; then ok "schema $s.schema.json"
    else fail "missing executable schema: schemas/$s.schema.json"; fi
    if [ -f "schemas/$s.reference.yml" ]; then ok "ref    $s.reference.yml"
    else fail "missing schema reference: schemas/$s.reference.yml"; fi
  done
else
  fail "missing directory: schemas/"
fi
# 8d. the issue manifest template
if [ -f "templates/manifest.yml" ]; then ok "file templates/manifest.yml"
else fail "missing issue manifest template: templates/manifest.yml"; fi
# 8e. run `compass policy lint` if python3 and the CLI are runnable.
if command -v python3 >/dev/null 2>&1 && [ -x "cli/compass" ]; then
  if LINT_OUT="$(python3 cli/compass policy lint 2>&1)"; then
    ok "compass policy lint  <- PASS"
  else
    fail "compass policy lint reported a problem:"
    printf '%s\n' "$LINT_OUT" | sed 's/^/         /' >&2
  fi
else
  say "  skip compass policy lint  <- python3 or cli/compass not runnable; skipped"
fi
say ""

# --- verdict ----------------------------------------------------------------
if [ "$FAILURES" -eq 0 ]; then
  echo "validate.sh: PASS - repo structure and internal references are intact."
  exit 0
else
  echo "validate.sh: FAIL - $FAILURES problem(s) above. Fix them before committing." >&2
  exit 1
fi
