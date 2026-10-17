"""Size targets for text every session loads.

A target is not a limit. A file over its target still passes, and pytest
prints a warning so the growth shows in every run. Each new rule a session
must always carry used to need a separate change to raise a hard cap first;
a target records the size without blocking a rule the owner agreed to
(issue `size-caps-as-targets`).
"""
from __future__ import annotations

import warnings


class OverTarget(UserWarning):
    """A file every session loads is larger than its size target."""


def warn_if_over(what, size, target, unit):
    if size > target:
        warnings.warn(OverTarget(
            f"{what} is {size} {unit}, over its target of {target} {unit}. "
            "It loads into every session, so every extra word costs "
            "attention every time."), stacklevel=2)
