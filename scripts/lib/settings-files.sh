#!/usr/bin/env bash
# =============================================================================
# settings-files.sh - does this project have a settings file at all?
# =============================================================================
# The pre-tool hook runs before every edit, and starting Python costs more than
# the rest of its decision for most edits. A project with no settings file has
# no `enforcement.code_globs` to read, so the hook asks this first and starts
# Python only when the answer is yes.
#
# This is the one shell file that names the two settings files. It only tests
# that one exists; it never reads one. cli/compass_pkg/project_settings.py
# decides which file is read and how, and tests/test_settings_fold_in.py pins
# the two names below to the ones it holds, so they cannot drift apart.

compass_has_settings_file() {
  [ -f "$1/compass.yml" ] ||
  [ -f "$1/.compass/config.yml" ]
}
