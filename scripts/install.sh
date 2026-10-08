#!/usr/bin/env bash
# =============================================================================
# Compass script: install.sh  -  WIRE COMPASS INTO CLAUDE CODE
# =============================================================================
# Installs the Claude Code adapter layer (commands/, agents/, skills/, hooks/)
# into the right Claude Code locations and registers the hooks in settings.
#
# The methodology layer (docs/, governance/, approaches/, templates/) is NOT
# installed anywhere - it is read in place from this repo. What this script
# wires up is only the runtime adapter.
#
# USAGE
#   scripts/install.sh                 # project-local install (default)
#   scripts/install.sh --global        # user-global install (~/.claude)
#   scripts/install.sh --project DIR   # project-local into a specific project
#   scripts/install.sh --copy          # copy instead of symlink
#   scripts/install.sh --uninstall     # remove what a previous run installed
#
# DESTINATIONS
#   --global  : ~/.claude/{commands,agents,skills}/  + ~/.claude/settings.json
#   project   : <project>/.claude/{commands,agents,skills}/
#                                     + <project>/.claude/settings.json
#   hooks are referenced in place from this repo (COMPASS_HOME/hooks/), so the
#   settings.json entries point at absolute paths under this repo.
#
# IDEMPOTENT: re-running is safe. Existing Compass symlinks are refreshed;
# existing non-Compass files are never clobbered (the script stops and tells
# you). Hook registration removes any entry whose command is one of this
# repo's hook paths, then adds each hook once.
# =============================================================================

set -euo pipefail

# --- locate this repo (COMPASS_HOME) ----------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPASS_HOME="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- parse args -------------------------------------------------------------
MODE="project"          # project | global
PROJECT_DIR="$(pwd)"
LINK_MODE="symlink"     # symlink | copy
ACTION="install"        # install | uninstall

while [ $# -gt 0 ]; do
  case "$1" in
    --global)     MODE="global" ;;
    --project)    MODE="project"; PROJECT_DIR="$(cd "$2" && pwd)"; shift ;;
    --copy)       LINK_MODE="copy" ;;
    --uninstall)  ACTION="uninstall" ;;
    -h|--help)
      grep -E '^# (USAGE|  scripts)' "$0" | sed 's/^# //'
      exit 0 ;;
    *) echo "install.sh: unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

# --- resolve the Claude Code destination root -------------------------------
if [ "$MODE" = "global" ]; then
  CLAUDE_ROOT="$HOME/.claude"
else
  CLAUDE_ROOT="$PROJECT_DIR/.claude"
fi
SETTINGS="$CLAUDE_ROOT/settings.json"

echo "Compass installer"
echo "  source (COMPASS_HOME): $COMPASS_HOME"
echo "  mode:                  $MODE"
echo "  destination:           $CLAUDE_ROOT"
echo "  link mode:             $LINK_MODE"

# Compass's CLI and the pre-tool hook's checks need Python 3.10 or later. Say
# so here, before anything is installed, rather than let a refused edit be how
# the person finds out. It warns and carries on: the files can be installed
# first and Python added after.
# shellcheck source=scripts/lib/python-check.sh
. "$SCRIPT_DIR/lib/python-check.sh"
if [ "$ACTION" = "install" ]; then
  PY_STATUS="$(compass_python_status)"
  case "$PY_STATUS" in
    ok\ *) echo "  python3:               ${PY_STATUS#ok } (Python 3.10 or later, as needed)" ;;
    *)
      case "$PY_STATUS" in
        missing) echo "  python3:               not found" ;;
        broken)  echo "  python3:               on the PATH, but it did not run" ;;
        *)       echo "  python3:               ${PY_STATUS#old } (too old)" ;;
      esac
      echo ""
      echo "  WARNING: Compass needs Python 3.10 or later. Without it, its commands"
      echo "           do not run, so the pre-tool hook refuses code edits in a"
      echo "           Compass project. Install it and put python3 on the PATH;"
      echo "           this install carries on, and works once Python is there."
      ;;
  esac
fi
echo ""

# --- helper: link or copy one component directory ---------------------------
# Each of commands/agents/skills is installed as a subdirectory named
# "compass" so it cannot collide with anything else the user has - the
# resolved Claude Code path is ~/.claude/<name>/compass/<file>. The "compass"
# destination dir is also what gives the slash-command namespace, so the
# repo's flat commands/*.md resolve as /compass:assess (not /compass:compass:…).
# The repo layout is uniform: commands/*.md, agents/*.md, skills/*/SKILL.md -
# all installed the same way. (The plugin path uses the plugin name for the
# same namespace; see .claude-plugin/plugin.json.)
install_component() {
  local name="$1"                      # commands | agents | skills
  local src="$COMPASS_HOME/$name"
  local dest_parent="$CLAUDE_ROOT/$name"
  local dest="$dest_parent/compass"

  [ -d "$src" ] || { echo "  skip $name (not present in repo)"; return 0; }
  mkdir -p "$dest_parent"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    # Only refresh something we own - a symlink, or a dir we copied before
    # (marked with .compass-installed). Never clobber the user's own files.
    if [ -L "$dest" ] || [ -f "$dest/.compass-installed" ]; then
      rm -rf "$dest"
    else
      echo "  ERROR: $dest exists and was not created by Compass - refusing to overwrite." >&2
      echo "         Move it aside and re-run." >&2
      exit 1
    fi
  fi

  if [ "$LINK_MODE" = "symlink" ]; then
    ln -s "$src" "$dest"
    echo "  linked  $name/compass -> $src"
  else
    cp -R "$src" "$dest"
    touch "$dest/.compass-installed"
    echo "  copied  $name/compass <- $src"
  fi
}

uninstall_component() {
  local name="$1"
  local dest="$CLAUDE_ROOT/$name/compass"
  if [ -L "$dest" ] || { [ -d "$dest" ] && [ -f "$dest/.compass-installed" ]; }; then
    rm -rf "$dest"
    echo "  removed $name/compass"
  fi
}

# --- helper: make sure a settings.json exists --------------------------------
ensure_settings() {
  mkdir -p "$CLAUDE_ROOT"
  [ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"
}

# --- helper: register the four hooks in settings.json -----------------------
# Compass needs PreToolUse (pre-tool.sh), PostToolUse (post-tool.sh), Stop
# (stop.sh) and SessionStart (session-start.sh). We splice them in with jq,
# keyed so re-running does not duplicate.
#
# The matchers must match hooks/hooks.json, which is what a plugin install
# gets. Without Bash in the matcher, a source install does not check shell
# writes (`sed -i`, `>` redirects). MultiEdit is not a Claude Code tool, so
# neither file registers it.
register_hooks() {
  ensure_settings
  local pre="$COMPASS_HOME/hooks/pre-tool.sh"
  local post="$COMPASS_HOME/hooks/post-tool.sh"
  local stop="$COMPASS_HOME/hooks/stop.sh"
  local session="$COMPASS_HOME/hooks/session-start.sh"

  if ! command -v jq >/dev/null 2>&1; then
    echo ""
    echo "  NOTE: jq is not installed - cannot auto-register hooks."
    echo "        Add these to $SETTINGS by hand:"
    cat <<EOF
        "hooks": {
          "PreToolUse":  [ { "matcher": "Edit|Write|Bash",
                             "hooks": [ { "type": "command", "command": "$pre" } ] } ],
          "PostToolUse": [ { "matcher": "Edit|Write",
                             "hooks": [ { "type": "command", "command": "$post" } ] } ],
          "Stop":        [ { "hooks": [ { "type": "command", "command": "$stop" } ] } ],
          "SessionStart": [ { "matcher": "startup|clear|compact",
                             "hooks": [ { "type": "command", "command": "$session" } ] } ]
        }
EOF
    return 0
  fi

  # Build the Compass hook block, then merge it in. We first strip any existing
  # Compass-owned entries (identified by the command path containing
  # "/hooks/pre-tool.sh" etc. under COMPASS_HOME) so the merge is idempotent.
  local tmp
  tmp="$(mktemp)"
  jq \
    --arg pre "$pre" --arg post "$post" --arg stop "$stop" --arg session "$session" '
    # drop any prior Compass entries so re-running does not duplicate
    def notcompass($paths): [ .hooks[]?.command ] as $cmds
      | ($cmds | map(. as $c | $paths | index($c)) | all(. == null));
    .hooks //= {} |
    .hooks.PreToolUse  = ( (.hooks.PreToolUse  // []) | map(select(notcompass([$pre])))  )
      + [ { matcher: "Edit|Write|Bash", hooks: [ { type: "command", command: $pre } ] } ] |
    .hooks.PostToolUse = ( (.hooks.PostToolUse // []) | map(select(notcompass([$post]))) )
      + [ { matcher: "Edit|Write", hooks: [ { type: "command", command: $post } ] } ] |
    .hooks.Stop        = ( (.hooks.Stop        // []) | map(select(notcompass([$stop]))) )
      + [ { hooks: [ { type: "command", command: $stop } ] } ] |
    .hooks.SessionStart = ( (.hooks.SessionStart // []) | map(select(notcompass([$session]))) )
      + [ { matcher: "startup|clear|compact", hooks: [ { type: "command", command: $session } ] } ]
  ' "$SETTINGS" > "$tmp"
  mv "$tmp" "$SETTINGS"
  echo "  registered hooks in $SETTINGS (PreToolUse, PostToolUse, Stop, SessionStart)"
}

unregister_hooks() {
  [ -f "$SETTINGS" ] || return 0
  command -v jq >/dev/null 2>&1 || { echo "  NOTE: jq missing - remove Compass hooks from $SETTINGS by hand."; return 0; }
  local pre="$COMPASS_HOME/hooks/pre-tool.sh"
  local post="$COMPASS_HOME/hooks/post-tool.sh"
  local stop="$COMPASS_HOME/hooks/stop.sh"
  local session="$COMPASS_HOME/hooks/session-start.sh"
  local tmp; tmp="$(mktemp)"
  jq --arg pre "$pre" --arg post "$post" --arg stop "$stop" --arg session "$session" '
    def strip($p): map(select(([ .hooks[]?.command ] | index($p)) == null));
    if .hooks then
      .hooks.PreToolUse   = ((.hooks.PreToolUse   // []) | strip($pre)) |
      .hooks.PostToolUse  = ((.hooks.PostToolUse  // []) | strip($post)) |
      .hooks.Stop         = ((.hooks.Stop         // []) | strip($stop)) |
      .hooks.SessionStart = ((.hooks.SessionStart // []) | strip($session))
    else . end
  ' "$SETTINGS" > "$tmp"
  mv "$tmp" "$SETTINGS"
  echo "  unregistered Compass hooks from $SETTINGS"
}

# --- make the hooks executable (no-op if already) ---------------------------
chmod +x "$COMPASS_HOME"/hooks/*.sh 2>/dev/null || true
chmod +x "$COMPASS_HOME"/scripts/*.sh 2>/dev/null || true

# --- guard: don't double-register hooks in a plugin-source target -----------
# If --project DIR is itself a Claude Code plugin source (it contains
# .claude-plugin/plugin.json), the plugin manifest's own hook registration
# already applies whenever the plugin is enabled. Adding a project-local
# registration in DIR/.claude/settings.json AS WELL means every Edit/Write
# fires pre-tool.sh and post-tool.sh TWICE (symptom: doubled devlog
# entries). The detection looks for the manifest FILE - a stray
# .claude-plugin/ directory without plugin.json is not a plugin source.
#
# The guard is install-only and project-mode-only:
#   - On --uninstall we always want to strip prior registrations, regardless
#     of plugin presence (recovery for users already in the bad state).
#   - On --global we cannot reliably tell whether the user has the plugin
#     enabled in any of their projects, so the guard does not fire there.
PLUGIN_MANIFEST="$PROJECT_DIR/.claude-plugin/plugin.json"
if [ "$ACTION" = "install" ] && [ "$MODE" = "project" ] && [ -f "$PLUGIN_MANIFEST" ]; then
  echo "  plugin source detected: $PLUGIN_MANIFEST exists."
  echo ""
  echo "  This project is itself a Claude Code plugin. When the plugin is"
  echo "  enabled, the plugin manifest's hook registration already applies;"
  echo "  adding a project-local registration here as well would cause every"
  echo "  Edit/Write tool call to fire pre-tool.sh and post-tool.sh TWICE."
  echo ""
  echo "  Refusing to install the adapter layer into a plugin source."
  echo "  Cleaning up any prior Compass adapter wiring left over from an"
  echo "  earlier install.sh run (so this is also the recovery path)..."
  uninstall_component commands
  uninstall_component agents
  uninstall_component skills
  unregister_hooks
  echo ""
  echo "  Done. For the plugin source itself, run Claude Code with the"
  echo "  plugin loaded live from this working tree:"
  echo "      claude --plugin-dir $PROJECT_DIR"
  echo "  (A project that CONSUMES the plugin uses /plugin install instead.)"
  echo "  Or run install.sh --project against a directory that is NOT"
  echo "  itself a plugin source."
  exit 0
fi

# --- run ---------------------------------------------------------------------
if [ "$ACTION" = "uninstall" ]; then
  echo "Uninstalling..."
  uninstall_component commands
  uninstall_component agents
  uninstall_component skills
  unregister_hooks
  echo ""
  echo "Compass adapter layer removed. The methodology layer in $COMPASS_HOME is untouched."
  exit 0
fi

echo "Installing adapter layer..."
install_component commands
install_component agents
install_component skills
register_hooks

echo ""
echo "Done. Compass is wired into Claude Code ($MODE)."
echo ""
echo "Next steps:"
echo "  1. cd into the project you want to use Compass in."
echo "  2. Run  /compass:assess \"<your task>\"  - that's it. The default guardrails"
echo "     and strategies ship active, so assessment computes an approach with zero setup."
echo "  3. Optional, whenever you want project settings or governance of your own:"
echo "     /compass:init  -  it writes a compass.yml that extends the defaults, or"
echo "     migrates a 5.x project to one. It is not a prerequisite."
echo ""
if [ "$MODE" = "global" ]; then
  echo "Note: a global install makes the /compass: commands available everywhere."
  echo "No per-project setup is required - /compass:assess works immediately; run"
  echo "/compass:init only when a project wants a compass.yml of its own."
fi
