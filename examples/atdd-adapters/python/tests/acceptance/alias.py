"""Aliases for the identifiers a scenario names.

A scenario names an account `ann@example.com`; the system sees
`ann@example.com-3f9a1c2e-gw0-17`. The same scenario can then run twice, or
beside itself on another worker, without meeting its own earlier data.

- The run id is made once, when the run starts, and every worker of the run
  reads it from ACCEPTANCE_RUN_ID (conftest.py sets it before the workers
  start).
- The counter is shared by the run: each worker counts on its own, and the
  worker's id in the alias keeps two workers' numbers apart.
- Each scenario has its own map, so a name gives the same alias every time
  that scenario asks for it.
"""
from __future__ import annotations

import itertools
import os
import threading

_counter = itertools.count(1)
_lock = threading.Lock()


def run_id():
    return os.environ["ACCEPTANCE_RUN_ID"]


def worker_id():
    # pytest-xdist names its workers gw0, gw1 and so on. A run without
    # workers counts as one worker.
    return os.environ.get("PYTEST_XDIST_WORKER", "gw0")


class Aliases:
    """The alias map of one scenario."""

    def __init__(self):
        self._names = {}

    def __call__(self, name):
        if name not in self._names:
            with _lock:
                number = next(_counter)
            self._names[name] = f"{name}-{run_id()}-{worker_id()}-{number}"
        return self._names[name]
