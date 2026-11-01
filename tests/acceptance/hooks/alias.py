"""Aliases for the identifiers a scenario names.

A scenario names an issue `matrix`; the system sees `matrix-r8f3a2c1-gw0-17`.
The same scenario can then run twice, or beside itself in parallel, without
meeting its own earlier data. One map per scenario, so a name gives the same
alias every time that scenario asks for it.

- The run id is one per run. pytest-xdist starts each worker as its own
  process and gives all workers of one run the same PYTEST_XDIST_TESTRUNUID,
  so the helper reads that; a run without workers makes its own.
- Each worker counts on its own, so the alias carries the worker's name
  (gw0, gw1 and so on) to keep two workers' numbers apart.
"""
from __future__ import annotations

import itertools
import os
import threading
import uuid

RUN_ID = os.environ.get("PYTEST_XDIST_TESTRUNUID", uuid.uuid4().hex)[:8]
WORKER = os.environ.get("PYTEST_XDIST_WORKER", "gw0")
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
            self._names[name] = f"{name}-{RUN_ID}-{WORKER}-{number}"
        return self._names[name]
