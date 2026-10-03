"""`bin/compass-statusline`: the current issue's state, one line, for the person.

Claude Code runs the status line command after each message, with session
JSON on stdin, and shows its output to the person only. It never reaches
the model, so the line costs no tokens. The stage comes from the same
resolver `compass next` uses, so the two cannot disagree; where `next`
prints "all phases complete", the line says "done".

There is no `compass statusline` verb: the CLI's public verbs are frozen,
and Claude Code runs a command path, so `bin/compass-statusline` is the
interface.

A status line must never break the session. Outside a Compass project, with
no current issue, or on any error, it prints nothing and exits 0, and it
never writes to stderr. It loads only what it needs, because it runs often:
`bin/compass-statusline` calls `main()` without loading the full CLI.

DEPENDENCY: compass_pkg.core and compass_pkg.next_cmd (bundled PyYAML).
"""
from __future__ import annotations

import json
import os
import sys

from compass_pkg.render import fit

SEP = " · "


def _project_dir(start: str) -> str | None:
    """The nearest directory at or above `start` that holds `.compass/`,
    stopping at the first repository root (`.git`, a directory or a
    worktree's file) as the pre-tool hook does, so a nested repository is
    never taken for its parent's project."""
    path = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(path, ".compass")):
            return path
        if os.path.exists(os.path.join(path, ".git")):
            return None
        parent = os.path.dirname(path)
        if parent == path:
            return None
        path = parent


def _evidence_state(task_dir: str, scenarios: list) -> str | None:
    """`<id> red`, `<id> none` or `<id> green` for the first scenario that
    has no green on record; the last scenario's green when all are green."""
    if not isinstance(scenarios, list):
        return None
    ids = [s["id"] for s in scenarios if isinstance(s, dict) and isinstance(s.get("id"), str)
           and s["id"]]
    if not ids:
        return None
    evidence = os.path.join(task_dir, "evidence")
    for scn in ids:
        # Named as `compass tdd-red` and `tdd-green` name them.
        name = scn.replace("/", "_")
        if os.path.isfile(os.path.join(evidence, f"green-{name}.json")):
            continue
        red = os.path.isfile(os.path.join(evidence, f"red-{name}.json"))
        return f"{scn} {'red' if red else 'none'}"
    return f"{ids[-1]} green"


def render(cwd: str, width: int = 80) -> str:
    """The status line for the project containing `cwd`, or "" for none."""
    project = _project_dir(cwd)
    if not project:
        return ""
    compass = os.path.join(project, ".compass")
    # COMPASS_ISSUE names this session's issue ahead of the pointer.
    slug = os.environ.get("COMPASS_ISSUE", "")
    if not slug:
        try:
            with open(os.path.join(compass, "current-task"), encoding="utf-8") as fh:
                slug = fh.read().strip()
        except OSError:
            return ""
    if not slug or "/" in slug or slug in (".", ".."):
        return ""
    task_dir = os.path.join(compass, "work", slug)

    from compass_pkg.core import (artifact_path, display_shape, display_stage,
                                  load_yaml, manifest_path, normalize_spine)
    from compass_pkg.next_cmd import _current_phase_from_task, _typed

    path = manifest_path(task_dir)
    if not os.path.isfile(path):
        return ""
    task = normalize_spine(load_yaml(path))
    if not isinstance(task, dict):
        return ""
    task = _typed(task)
    # Every entry counts towards the total, a malformed one included: the
    # stage treats it as a gate not passed, so the count must too.
    gates = task.get("gates") or []
    if not os.path.isfile(artifact_path(task_dir, "delivery-approach.md")):
        # `compass next` reports no stage without the approach record.
        stage = None
    elif task.get("status") == "landed":
        stage = "done"
    else:
        phase = _current_phase_from_task(task, task_dir)
        # Capitalised as `compass next` prints it, so the two read the same.
        stage = display_stage(phase).capitalize() if phase else "done"
    fields = ["compass", slug]
    approach = task.get("delivery_approach")
    if approach:
        fields.append(display_shape(approach))
    if stage:
        fields.append(stage)
    if gates:
        cleared = sum(1 for g in gates if isinstance(g, dict) and g.get("status") == "pass")
        fields.append(f"gates {cleared}/{len(gates)}")
    state = _evidence_state(task_dir, task.get("scenarios") or [])
    if state:
        fields.append(state)
    # The slug is the second field, so it is the last thing cut.
    return fit(fields, width, SEP)


def main() -> int:
    """Read Claude Code's session JSON on stdin and print the line."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
        workspace = data.get("workspace") if isinstance(data, dict) else None
        cwd = ((workspace or {}).get("current_dir")
               or (data.get("cwd") if isinstance(data, dict) else None)
               or os.getcwd())
        try:
            width = int(os.environ.get("COLUMNS") or 80)
        except ValueError:
            width = 80
        if width < 20:
            width = 80
        line = render(str(cwd), width)
        if line:
            sys.stdout.write(line + "\n")
    except Exception:  # noqa: BLE001 - a broken status line must not break the session
        pass
    return 0

