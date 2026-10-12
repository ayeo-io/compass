# compass_pkg.render_after_entry - load the after-command render only when a command can trigger it
"""The entry point's hook for the after-command render (ADR-051).

`render_after` pulls in the render modules and the project scan. A command
outside `record_triggers.RENDER_TRIGGERS`, such as `next`, must not pay for
them, so this module imports `render_after` only for a command that can
trigger a render. It lives here, not in the entry point, because the entry
point holds `main` and the parser only.
"""
# DEPENDENCY: compass_pkg.record_triggers (standard library only); compass_pkg.render_after,
# imported only when a command is in RENDER_TRIGGERS.
from __future__ import annotations

from compass_pkg import record_triggers


def after_command(args, code):
    """Render after a command in `RENDER_TRIGGERS`; return `code` unchanged otherwise."""
    name = getattr(getattr(args, "func", None), "__name__", "")
    if name not in record_triggers.RENDER_TRIGGERS:
        return code
    from compass_pkg.render_after import after_command as render
    return render(args, code)
