# shellcheck shell=bash
# =============================================================================
# Compass library: python-check.sh  -  IS A USABLE python3 ON THE PATH?
# =============================================================================
# Sourced by hooks/session-start.sh and scripts/install.sh, so a person learns
# that Compass needs Python 3.10 or later at install or session start, not from
# the first edit the pre-tool hook refuses.
#
# compass_python_status prints one line:
#   ok <version>       python3 is 3.10 or later
#   old <version>      python3 runs but is older than 3.10
#   broken             a python3 is on the PATH but does not run, such as
#                      macOS's placeholder that asks to install developer tools
#   missing            no python3 on the PATH
#
# One python3 call gives both the version and the verdict, so a session start
# pays for one interpreter launch. The version comes from sys.version_info,
# never from `python3 -V` text, so it is always digits and dots and a caller
# can put it in JSON or a message without escaping it.
# =============================================================================

compass_python_status() {
  local out rc
  if ! command -v python3 >/dev/null 2>&1; then
    echo "missing"
    return 0
  fi
  out="$(python3 -c 'import sys; v = sys.version_info; print("%d.%d.%d" % tuple(v[:3])); sys.exit(0 if v >= (3, 10) else 1)' 2>/dev/null)"
  rc=$?
  case "$out" in
    ''|*[!0-9.]*) echo "broken" ;;
    *) if [ "$rc" -eq 0 ]; then echo "ok $out"; else echo "old $out"; fi ;;
  esac
}
