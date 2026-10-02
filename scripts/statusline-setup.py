#!/usr/bin/env python3
"""Point a Claude Code settings file's statusLine at the Compass launcher.

The session-start hook keeps a launcher, `compass-statusline`, in the plugin's
data folder (`~/.claude/plugins/data/<id>/`), which Claude Code keeps across
plugin updates. A statusLine setting that names it keeps working after an
upgrade; one that names a versioned plugin path keeps running old code.

`/compass:init` runs this to show the change, asks the person, and runs it
again with `--apply` only on a yes. Without `--apply` it never writes.

    statusline-setup.py --settings <settings.json> [--launcher PATH] [--apply]

Outcomes:
  - no statusLine: show the entry to add; --apply writes it;
  - a statusLine naming a versioned Compass path: show the replacement,
    keeping its other keys; --apply writes it;
  - a statusLine already naming the launcher: say so, change nothing;
  - any other statusLine: change nothing, and say how to combine the two.
"""
import argparse
import difflib
import glob
import json
import os
import re
import shlex
import shutil
import sys
from pathlib import Path

_VERSIONED = re.compile(r"/compass/[^/]+/bin/compass-statusline$")
# This helper's own plugin root: the launcher to use is the one the hook in
# this same root wrote, whichever data folder it is in.
_ROOT = Path(__file__).resolve().parents[1]


def _target(launcher):
    """The path a launcher runs, from its `target=` line, or None."""
    try:
        with open(launcher, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("target="):
                    return shlex.split(line[len("target="):])[0]
    except (OSError, ValueError, IndexError):
        return None
    return None


def _find_launcher():
    """The launcher, under any Compass data folder, that runs this plugin
    root's status line script. Not the newest file: the hook rewrites a
    launcher only when its content changes."""
    # Compare real paths: the hook records its root as the shell sees it,
    # which can run through a symlink this file's own path resolves.
    want = os.path.realpath(_ROOT / "bin" / "compass-statusline")
    pattern = os.path.expanduser("~/.claude/plugins/data/*compass*/compass-statusline")
    for path in sorted(glob.glob(pattern)):
        target = _target(path)
        if target and os.path.realpath(target) == want:
            return path
    return None


def _home_form(path):
    """`~/...` for a path under the home folder, so the entry reads the same
    as the documented one; the absolute path otherwise."""
    home = os.path.expanduser("~")
    full = os.path.abspath(path)
    if full == home or full.startswith(home + os.sep):
        return "~" + full[len(home):]
    return full


def _same(command, launcher):
    if not isinstance(command, str):
        return False
    return os.path.abspath(os.path.expanduser(command)) == os.path.abspath(
        os.path.expanduser(launcher))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--settings", required=True, help="the Claude Code settings file")
    p.add_argument("--launcher", help="the launcher's path; found under ~/.claude/plugins/data/ by default")
    p.add_argument("--apply", action="store_true", help="write the change; without it, only show it")
    args = p.parse_args(argv)

    launcher = args.launcher or _find_launcher()
    if not launcher:
        print("No Compass status line launcher for this plugin was found under "
              "~/.claude/plugins/data/. Start a new Claude Code session with the "
              "plugin enabled; its session-start hook writes the launcher. Then run "
              "this again.")
        return 1

    path = os.path.expanduser(args.settings)
    raw = None
    data = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        try:
            data = json.loads(raw) if raw.strip() else {}
        except ValueError as exc:
            print(f"{path} is not valid JSON ({exc}), so it was left alone.")
            return 1
        if not isinstance(data, dict):
            print(f"{path} is not a JSON object, so it was left alone.")
            return 1

    current = data.get("statusLine")
    command = current.get("command") if isinstance(current, dict) else None

    if _same(command, launcher):
        print(f"{path} already runs the Compass status line launcher. Nothing to change.")
        return 0
    if current is not None and not (isinstance(command, str) and _VERSIONED.search(command)):
        print(f"{path} already has a status line that is not Compass's, so it was left "
              f"alone. To combine the two, make your status line script also run "
              f"{launcher} and print its output.")
        return 0

    entry = dict(current) if isinstance(current, dict) else {}
    entry.update({"type": "command", "command": _home_form(launcher)})
    new = dict(data)
    new["statusLine"] = entry
    before = raw if raw is not None else ""
    after = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    diff = list(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile=f"{path} (now)", tofile=f"{path} (with the Compass status line)"))
    sys.stdout.writelines(line if line.endswith("\n") else line + "\n" for line in diff)
    if not args.apply:
        print("\nNothing was written. Run again with --apply to make this change.")
        return 0
    # Write through a symlink to its target, and keep the file's mode, so the
    # only change is the one the person saw in the diff.
    real = os.path.realpath(path)
    os.makedirs(os.path.dirname(real) or ".", exist_ok=True)
    tmp = real + ".compass-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(after)
    if os.path.exists(real):
        shutil.copymode(real, tmp)
    os.replace(tmp, real)
    print(f"\nWrote the Compass status line to {path}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
