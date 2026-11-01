"""The CLI driver: reaches the todo service through its command line, as a person at a terminal does."""
from __future__ import annotations

import subprocess
import sys

from tests.acceptance.drivers import TodoDriver

TIMEOUT_SECONDS = 30


class Driver(TodoDriver):
    def _request(self, action, email, name=None):
        args = [action, email] + ([] if name is None else [name])
        run = self._todo(*args)
        return None if run.returncode == 0 else run.stderr.strip().removeprefix("error: ")

    def _listed(self, email, state):
        run = self._todo("list", email, "--state", state)
        if run.returncode != 0:
            raise RuntimeError(f"listing the {state} todos of {email} failed: {run.stderr.strip()}")
        return run.stdout.splitlines()

    def _todo(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "todo.cli", "--data-dir", self.system.data_dir, *args],
            cwd=self.system.root, capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
