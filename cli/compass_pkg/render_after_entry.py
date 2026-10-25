# compass_pkg.render_after_entry - load the after-command render only when a command can trigger it
"""The entry point's hooks around a command that changes an issue's records
(ADR-051, ADR-038).

`render_after` pulls in the render modules and the project scan. A command
outside `record_triggers.RENDER_TRIGGERS`, such as `next`, must not pay for
them, so this module imports `render_after` only for a command that can
trigger a render. It lives here, not in the entry point, because the entry
point holds `main` and the parser only.

`before_command` refuses such a command on an issue whose generation was built
by another resolver or schema major, before it writes. A command that only
reads is refused where it loads the generation, so it adds no cost here.
"""
# DEPENDENCY: compass_pkg.record_triggers (standard library only); compass_pkg.core,
# compass_pkg.effective and compass_pkg.render_after, imported only for a command in
# RENDER_TRIGGERS.
from __future__ import annotations

from compass_pkg import record_triggers


def before_command(args):
    """Raise `effective.MajorRefusal` before a command in `RENDER_TRIGGERS` runs
    on the issue it changes, when that issue's generation records another
    resolver or schema major. `record_triggers.ISSUE_FROM` names the argument
    that names the issue, so a command about another issue is not refused. The
    table's argument condition applies, so `approach evaluate` without `--write`
    is left to its own read."""
    name = getattr(getattr(args, "func", None), "__name__", "")
    table = record_triggers.RENDER_TRIGGERS
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


def after_command(args, code):
    """Render after a command in `RENDER_TRIGGERS`; return `code` unchanged otherwise."""
    name = getattr(getattr(args, "func", None), "__name__", "")
    if name not in record_triggers.RENDER_TRIGGERS:
        return code
    from compass_pkg.render_after import after_command as render
    return render(args, code)
