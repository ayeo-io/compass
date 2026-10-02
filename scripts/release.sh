#!/usr/bin/env bash
# =============================================================================
# Compass - release packaging script
# =============================================================================
# Produces a clean tarball of the framework: `dist/compass-<version>.tar.gz`.
#
# What it does, in order:
#   1. Runs the self-check (validate.sh) - refuses to package a broken repo.
#   2. Runs `compass policy lint` - refuses to package broken governance.
#   3. Runs the test suite - refuses to package with a red CLI.
#   4. Confirms the worked examples are present.
#   5. Builds the tarball, excluding noise (.DS_Store, __pycache__, *.bak,
#      .pytest_cache, __MACOSX, *.pyc) and dev-only state (.git, .compass/work).
#   6. Prints what is inside the tarball and its size.
#
# A tarball carrying .DS_Store looks careless, so the build excludes noise
# and fails if any is found.
# =============================================================================

set -euo pipefail

# --- portable archive prefixing ---------------------------------------------
# Every entry in the tarball is prefixed with `compass-<version>/` so the
# archive extracts into its own directory rather than over the user's cwd.
# The two tars spell that operation differently and each rejects the other's
# flag outright:
#
#   GNU tar (Linux, CI)   --transform 's,^\./,compass-<v>/,'
#   BSD tar (macOS)       -s ',^\./,compass-<v>/,'
#
# Choose the flag at run time: the wrong one makes tar exit 1 after every
# check has passed. Detection runs `tar --version`, because that is the one
# command both tars answer.
#
# The pattern anchors on `^\./` rather than `^` because the archive is built
# from `.`, so entries arrive as `./path`. Anchoring on `^` alone would produce
# `compass-<v>/./path`.
tar_prefix_flags() {
  local version="$1"
  if tar --version 2>/dev/null | grep -qi 'gnu tar'; then
    printf '%s\n' "--transform" "s,^\./,compass-${version}/,"
  else
    printf '%s\n' "-s" ",^\./,compass-${version}/,"
  fi
}

# --- what goes in the tarball -----------------------------------------------
# The list of paths to package, one per line, each prefixed `./`.
#
# This is driven from `git ls-files` rather than from the working tree, and
# the excludes below are shell `grep -Ev` patterns anchored with `^`, never a
# tar `--exclude`:
#
#   * A tar `--exclude` of `.compass/work` is not anchored on BSD tar, so it
#     would match at any depth and strip
#     examples/<x>/.compass/work/<slug>/manifest.yml along with the real
#     target. Selecting paths in shell and handing tar a fixed list (`-T`)
#     avoids the flag, and the anchor, entirely.
#   * An untracked file, such as a local .mcp.json, matches no noise
#     pattern, so a working-tree archive ships it. Tracked-only excludes it
#     by construction, and gitignored dev state (the repo's `.compass/work`)
#     never appears.
#
# The remaining excludes are for paths that ARE tracked but are not part of
# what an adopter installs.
release_file_list() {
  git ls-files \
    | grep -Ev '^\.github/' \
    | grep -Ev '^\.gitignore$|^\.gitattributes$' \
    | grep -Ev '^dist/' \
    | grep -Ev '^\.compass/(work|flow)/' \
    | grep -Ev '^\.compass/current-task$' \
    | sed 's,^,./,'
}

# --- is the vendored PyYAML copy actually in a built tarball? (TRC-F6) ------
# Factored out of the packaging steps below so the test suite can drive this
# specific check red-to-green against a fake tarball listing, without running
# a full `make release` (build + lint + test + tar) just to exercise one
# `grep`. Prints the vendored paths missing from `$1` (a tarball's file
# listing, one path per line) for version `$2`; empty output means nothing
# is missing.
vendor_integrity_missing() {
  local tar_list="$1" version="$2"
  local f missing=""
  for f in "cli/vendor/yaml/__init__.py" "cli/vendor/LICENSE-PyYAML" "THIRD-PARTY-NOTICES.md"; do
    if ! printf '%s\n' "$tar_list" | grep -qF "compass-${version}/$f"; then
      missing="$missing $f"
    fi
  done
  printf '%s' "$missing"
}

# Allow the test suite to source this file for `tar_prefix_flags`,
# `release_file_list` and `vendor_integrity_missing` without running a
# release. Nothing above this line has side effects.
if [ "${1:-}" = "--source-only" ]; then
  return 0 2>/dev/null || exit 0
fi

# --- locate the repo --------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPASS_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$COMPASS_HOME"

# --- args -------------------------------------------------------------------
SKIP_TESTS=0
SKIP_LINT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-tests) SKIP_TESTS=1 ;;
    --skip-lint)  SKIP_LINT=1 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# //; s/^#//'
      exit 0 ;;
    *) echo "release.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

VERSION="$(tr -d '[:space:]' < VERSION)"
[ -n "$VERSION" ] || { echo "release.sh: VERSION file is empty" >&2; exit 1; }

echo "Compass release packager"
echo "  version  : $VERSION"
echo "  source   : $COMPASS_HOME"
echo ""

# --- 1. self-check ----------------------------------------------------------
echo "[1] scripts/validate.sh"
bash scripts/validate.sh >/dev/null
echo "    PASS"

# --- 2. policy lint ---------------------------------------------------------
echo "[2] compass policy lint"
if [ "$SKIP_LINT" -eq 0 ]; then
  python3 cli/compass policy lint >/dev/null
  echo "    PASS"
else
  echo "    skipped (--skip-lint)"
fi

# --- 3. test suite ----------------------------------------------------------
echo "[3] tests"
if [ "$SKIP_TESTS" -eq 0 ]; then
  if command -v python3 >/dev/null 2>&1 && [ -d tests ]; then
    # Parallel workers when pytest-xdist is installed, as `make test` does.
    XDIST=""
    if python3 -c "import xdist" 2>/dev/null; then
      XDIST="-p xdist.plugin -n auto"
    fi
    # shellcheck disable=SC2086  # XDIST holds several arguments, split on purpose.
    if [ -n "$XDIST" ]; then
      # Timing tests (marked serial) run after the parallel pass, alone.
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q $XDIST -m "not serial" >/dev/null
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q -m serial >/dev/null
    else
      PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/ -q >/dev/null
    fi
    echo "    PASS"
  else
    echo "    skipped (no python3 or no tests/)"
  fi
else
  echo "    skipped (--skip-tests)"
fi

# --- 4. examples present ----------------------------------------------------
echo "[4] worked examples are actually present"
required_examples="quick-fix-typo feature-api-change hotfix-regression initiative-new-subsystem spike-technical-unknown"
missing=""
for e in $required_examples; do
  if [ ! -f "examples/$e/.compass/work"/*/manifest.yml ] 2>/dev/null; then
    # `[ -f glob ]` fails when the glob matches no file or several, so fall
    # back to find.
    if ! find "examples/$e" -name manifest.yml -type f 2>/dev/null | grep -q .; then
      missing="$missing $e"
    fi
  fi
done
if [ -n "$missing" ]; then
  echo "    FAIL - missing example manifest.yml(s):$missing"
  exit 1
fi
echo "    PASS - all 5 example manifest.yml(s) present"

# --- 5. clear stale artifacts and build the tarball -------------------------
echo "[5] building tarball"
mkdir -p dist
# Wipe any previous tarball, so dist/ never carries both an old and the new
# one. The || true handles read-only filesystems / sandbox locks gracefully -
# on a real machine this deletes cleanly.
find dist -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.zip' \) \
  -exec rm -f {} + 2>/dev/null || true
# If an old tarball survives (a sandbox lock), warn that dist/ will hold
# more than one tarball.
STALE="$(find dist -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.zip' \) 2>/dev/null || true)"
if [ -n "$STALE" ]; then
  echo "release.sh: WARNING - dist/ still contains stale artifact(s):" >&2
  echo "$STALE" | sed 's/^/    /' >&2
  echo "    Remove them by hand and re-run \`make release\` so dist/ holds one tarball." >&2
fi
OUT="dist/compass-${VERSION}.tar.gz"

# release_file_list() builds the list from tracked paths only, so noise from
# an untracked file cannot appear. The noise check below still runs, to
# catch a tracked file that should not ship.
TMP_LIST="$(mktemp)"
trap 'rm -f "$TMP_LIST"' EXIT
release_file_list > "$TMP_LIST"
tar -czf "$OUT" $(tar_prefix_flags "${VERSION}") -T "$TMP_LIST"

echo "    wrote $OUT"
echo ""

# --- 6. report --------------------------------------------------------------
SIZE="$(du -h "$OUT" | cut -f1)"
FILES="$(tar -tzf "$OUT" | wc -l | tr -d ' ')"
echo "Tarball summary:"
echo "  path     : $OUT"
echo "  size     : $SIZE"
echo "  files    : $FILES"
echo ""
echo "  top-level entries:"
tar -tzf "$OUT" | awk -F/ 'NF<=2 && $2!=""' | sort -u | sed 's/^/    /'
echo ""
# Materialise the tarball listing once. The verification loops grep against
# this string rather than re-piping `tar | grep` per check - `tar | grep -q`
# under `set -o pipefail` triggers SIGPIPE in tar when grep exits on first
# match, which makes the pipeline status non-zero even though grep matched.
# Reading the listing into a variable avoids that.
TAR_LIST="$(tar -tzf "$OUT")"

# --- noise check (HARD FAIL) -----------------------------------------------
# A release script that reports dirt is not the same as one that refuses to
# ship dirt, so this fails the build rather than only printing a warning.
echo "  noise check (must be empty):"
NOISE="$(printf '%s\n' "$TAR_LIST" | grep -E '\.DS_Store$|__MACOSX|__pycache__|\.pytest_cache|\.bak$|_deltest|pytest-cache-files-' || true)"
if [ -n "$NOISE" ]; then
  echo "$NOISE" | sed 's/^/    !!  /' >&2
  echo "release.sh: FAIL - tarball contains noise files (see above). Fix the excludes in scripts/release.sh and rebuild." >&2
  exit 1
fi
echo "    (clean - none)"

# --- examples integrity check (HARD FAIL) ----------------------------------
# Every example's manifest.yml must be in the tarball. Check the listing
# directly, so a mistake in release_file_list()'s excludes is caught here
# rather than assumed away.
echo "  examples integrity (every example must have its manifest.yml):"
required_examples="quick-fix-typo feature-api-change hotfix-regression initiative-new-subsystem spike-technical-unknown"
missing=""
for e in $required_examples; do
  # vocabulary-scan: allow - greps a real path inside the tarball listing
  if ! printf '%s\n' "$TAR_LIST" | grep -q "examples/$e/\.compass/work/.*/manifest\.yml"; then
    missing="$missing $e"
  fi
done
if [ -n "$missing" ]; then
  echo "    !!  missing example manifest.yml in tarball:$missing" >&2
  # The message below is the pre-issue wording, restored on purpose. Its
  # advice is stale - this script hands tar a fixed list and passes no
  # --exclude at all, as the header now explains - but correcting it changes
  # printed output, and prose-breaks-the-writing-style claims no printed
  # string changed. The correction belongs with the other printed-output
  # fixes, in their own issue.
  echo "release.sh: FAIL - examples were not packaged correctly. Check the .compass/work exclude is root-anchored (./.compass/work, not .compass/work)." >&2
  exit 1
fi
for e in $required_examples; do
  # vocabulary-scan: allow - greps a real path inside the tarball listing
  tf="$(printf '%s\n' "$TAR_LIST" | grep "examples/$e/\.compass/work/.*/manifest\.yml" | head -1)"
  echo "    OK $tf"
done

# --- vendored PyYAML integrity check (HARD FAIL) ----------------------------
# Without the vendored copy or its licence, every install fails with
# "PyYAML required". Fail hard, as the examples check above does.
echo "  vendored PyYAML integrity (bundle + licence must be in the tarball):"
vendor_missing="$(vendor_integrity_missing "$TAR_LIST" "$VERSION")"
if [ -n "$vendor_missing" ]; then
  echo "    !!  missing from tarball:$vendor_missing" >&2
  echo "release.sh: FAIL - the vendored PyYAML copy or its licence did not ship. A machine with only python3 could not run this release." >&2
  exit 1
fi
echo "    OK cli/vendor/yaml/, cli/vendor/LICENSE-PyYAML, THIRD-PARTY-NOTICES.md"

echo ""
echo "Done. Inspect the tarball before uploading:"
echo "  tar -tzf $OUT | less"
