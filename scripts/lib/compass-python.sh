#!/usr/bin/env bash
# =============================================================================
# compass-python.sh - run python3 with the bundled PyYAML importable
# =============================================================================
# Shell scripts call compass_python, not python3, so every embedded reader
# imports the bundled PyYAML in cli/vendor/yaml/ and not whatever copy the
# machine has. The callers are hooks/pre-tool.sh, hooks/stop.sh,
# scripts/integrate.sh and scripts/multiagent.sh.
#
# This file does NOT know where cli/vendor/ is. It only knows the framework
# root, and puts cli/ on PYTHONPATH so `import compass_pkg` works - the vendor
# path itself is written down in exactly one place,
# cli/compass_pkg/__init__.py. A future move of the vendored tree is a
# one-line edit there, not a search-and-replace across every script that
# reads YAML.
#
# CONTRACT for every caller: open with these two imports, in this order:
#   import compass_pkg   # side effect: puts cli/vendor at sys.path[0]
#   import yaml
#
# Fork python3; do not exec it. exec replaces the calling shell, so a reader
# that cannot start ends the caller's script before its error handling runs.
# That switches hooks/pre-tool.sh off when the vendored copy is missing.
#
# EXIT STATUS 3 means the vendored PyYAML could not be resolved and the reader
# never ran, with the reason on stderr. A broken install must be reported, so
# callers must tell that apart from a reader that ran and found nothing - the
# ordinary absence of state.
# =============================================================================

compass_python() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  PYTHONPATH="$root/cli${PYTHONPATH:+:$PYTHONPATH}" python3 "$@"
}

# compass_setting ROOT KEY DEFAULT - print one project setting for a script.
#
# The value comes from compass_pkg.project_settings, the one reader of the
# project's settings file, so a script follows `compass.yml` as the CLI does
# and no script parses a settings file itself. In `compass.yml` KEY is read at
# its documented path (multiagent.worktree_root, multiagent.max_worktrees,
# project.test_command); in an old project's settings file it is found at any
# depth. A key that is absent or empty gives DEFAULT. A settings file that
# cannot be read returns 1 with the reason on stderr, and the caller must stop:
# a default in its place would be a silent cap or a skipped regression run.
compass_setting() {
  local value
  if value="$(compass_python - "$1" "$2" "$3" <<'PYEOF'
import sys

import compass_pkg                      # noqa: F401 - puts vendor on sys.path
from compass_pkg import project_settings

try:
    print(project_settings.scalar(sys.argv[1], sys.argv[2]))
except project_settings.CompassError as exc:
    print("compass: %s" % exc, file=sys.stderr)
    sys.exit(4)
PYEOF
  )"; then
    printf '%s\n' "${value:-$3}"
  else
    return 1
  fi
}
