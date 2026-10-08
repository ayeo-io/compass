#!/usr/bin/env bash
# Build the headless runner's demo and run `compass run` on it.
#
# The demo is a project with one known bug: an upload error that names the
# limit in GB when it means MB. The script records the failing test as a
# quick fix, then runs the build stage with nobody in the session, at most
# DEMO_MAX_CYCLES sessions (3 by default), 15 minutes and 3 US dollars. It
# prints the run record and exits with the run's code: 0 when the stage is
# done, 4 when it stopped.
#
# DEMO_DIR names where the project is built (a new temporary folder by
# default). CLAUDE_BIN names the claude executable, for the tests' stub.
# .github/workflows/compass-run-demo.yml runs this in CI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPASS="$ROOT/cli/compass"
DEMO="${DEMO_DIR:-$(mktemp -d)/demo}"

rm -rf "$DEMO"
mkdir -p "$DEMO/src" "$DEMO/tests"
cp "$ROOT/scripts/run-demo/upload.py" "$DEMO/src/upload.py"
cp "$ROOT/scripts/run-demo/upload_check.py" "$DEMO/tests/test_upload.py"
cd "$DEMO"
git init -q
git -c user.email=demo@example.invalid -c user.name=demo add -A
git -c user.email=demo@example.invalid -c user.name=demo commit -qm "the demo project"

# The sessions call `compass`, so the CLI this script belongs to comes first.
export PATH="$ROOT/bin:$PATH"

python3 "$COMPASS" quick-fix start fix-upload-limit-unit \
  --risk "trivial - one message string" \
  --familiarity "brownfield-mapped - one module and its test" \
  --size "atomic - one line" --intent INT-1 --scenario-id UP-1 \
  --scenario "Given an upload over the limit, then the error names the limit in megabytes." \
  --test tests/test_upload.py >/dev/null
python3 "$COMPASS" tdd-red --scenario UP-1 --quiet -- python3 -m pytest -q tests/test_upload.py

set +e
python3 "$COMPASS" run fix-upload-limit-unit --stage implement \
  --stop-file .compass/STOP --max-cycles "${DEMO_MAX_CYCLES:-3}" \
  --max-minutes 15 --max-cost-usd 3 ${CLAUDE_BIN:+--claude "$CLAUDE_BIN"}
code=$?
set -e
cat docs/compass/*/run-1.md
exit "$code"
