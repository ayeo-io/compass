# compass_pkg.next_line - where a verb that writes a record asks for its `next:` line
"""The call each verb that writes a record of an issue makes as it returns.

`next_step.announce` decides and prints the `next:` line (ADR-092 decision 8).
It reads the checks, and the checks import `tdd`, one of the verbs that print
the line, so a verb that imported `next_step` would close an import cycle
(`tests/test_cli_module_split.py`). This module breaks it by dependency
injection: the verbs import only this module, which imports no other, and
`next_step` registers its `announce` here when it loads. The CLI always loads
`next_step` (`_all` imports `next_cmd`, which imports it), so the line is
printed on every run of the CLI. Where nothing registered, nothing is printed
and the verb's result is unchanged.
"""
# DEPENDENCY: none. Keep it so: every verb that writes a record imports it.
from __future__ import annotations

_ANNOUNCER = []


def register(announcer):
    """Make `announcer(args, task_dir, code)` the function that prints the line."""
    _ANNOUNCER[:] = [announcer]


def announce(args, task_dir, code=0):
    """Print the issue's `next:` line through the registered function, and
    return `code`."""
    return _ANNOUNCER[0](args, task_dir, code) if _ANNOUNCER else code
