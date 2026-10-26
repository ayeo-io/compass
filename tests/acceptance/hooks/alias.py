"""Aliases for the identifiers a scenario names.

A scenario names an issue `matrix`; the system sees `matrix-r8f3-17`. The
same scenario can then run twice, or beside itself in parallel, without
meeting its own earlier data. One run ID per run, one counter shared by the
run, and one map per scenario, so a name gives the same alias every time
that scenario asks for it.
"""
from __future__ import annotations

import itertools
import threading
import uuid

RUN_ID = uuid.uuid4().hex[:4]
_counter = itertools.count(1)
_lock = threading.Lock()


class Aliases:
    """The alias map of one scenario."""

    def __init__(self):
        self._names = {}

    def __call__(self, name):
        if name not in self._names:
            with _lock:
                number = next(_counter)
            self._names[name] = f"{name}-{RUN_ID}-{number}"
        return self._names[name]
