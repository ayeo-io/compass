# compass_pkg.command_guard - refuse a record command on an issue of another major
"""The entry point's check before a command that changes an issue's records (ADR-038).

`before_command` refuses such a command on an issue whose generation was built
by another resolver or schema major, before it writes. A command that only
reads is refused where it loads the generation, so it adds no cost here. It
moved out of `render_after_entry.py` when 9.0.0 removed the after-command
render (ADR-091).
"""
# DEPENDENCY: compass_pkg.record_triggers (standard library only); compass_pkg.core and
# compass_pkg.effective, imported only for a command in RECORD_TRIGGERS.
from __future__ import annotations

from compass_pkg import record_triggers


def before_command(args):
    """Raise `effective.MajorRefusal` before a command in `RECORD_TRIGGERS` runs
    on the issue it changes, when that issue's generation records another
    resolver or schema major. `record_triggers.ISSUE_FROM` names the argument
    that names the issue, so a command about another issue is not refused. The
    table's argument condition applies, so `approach evaluate` without `--write`
    is left to its own read."""
    name = getattr(getattr(args, "func", None), "__name__", "")
    table = record_triggers.RECORD_TRIGGERS
    if name not in table or (table[name] and not getattr(args, table[name], False)):
        return
    from compass_pkg import effective
    from compass_pkg.core import CompassError, resolve_issue_dir
    argument = record_triggers.ISSUE_FROM[name]
    named = getattr(args, argument, None)
    # Only `--issue` falls back to the current-task pointer; a positional slug names
    # its issue or none.
    if argument != "task" and not named:
        return
    try:
        task_dir = resolve_issue_dir(named)
    except CompassError:
        return
    effective.refuse_other_major(task_dir)
