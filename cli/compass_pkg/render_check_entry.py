# compass_pkg.render_check_entry - the registry's entry for rendered-blocks-current
"""The check `rendered-blocks-current`, loaded when it runs.

`render_check` pulls in the block renderers and the issue page code, which cost
start-up time that a command outside the render triggers, such as `next`, must not
pay. The registry imports this function, which imports `render_check` on first call.
It sits in its own module because the check-mutation runner replaces a check's
function at the end of the module that defines it.
"""
# DEPENDENCY: none at import; compass_pkg.render_check when the check runs.
from __future__ import annotations


def _check_rendered_blocks_current(task, task_dir):
    from compass_pkg.render_check import check
    return check(task, task_dir)
