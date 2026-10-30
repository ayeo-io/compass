"""The todo system a run tests: its data folder, and its API server once a driver asks for it.

The server starts on the first request for its address and stops when the
run ends. It is started with `--exit-with-parent`, so it stops even when the
run is killed. Nothing is cleared between scenarios: aliased data cannot
collide, so it stays.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
START_SECONDS = 15


class RunningSystem:
    def __init__(self, data_dir):
        self.root = ROOT
        self.data_dir = str(data_dir)
        self._server = None
        self._log = None
        self._url = None

    @property
    def api_url(self):
        if self._url is None:
            self._start_server()
        return self._url

    def stop(self):
        if self._server is None:
            return
        self._server.stdin.close()
        try:
            self._server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._server.kill()
            self._server.wait()
        self._log.close()

    def _start_server(self):
        self._log = tempfile.TemporaryFile(mode="w+")
        self._server = subprocess.Popen(
            [sys.executable, "-m", "todo.server", "--data-dir", self.data_dir,
             "--port", "0", "--exit-with-parent"],
            cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
            text=True)
        # Wait for the line that says where it listens, with a limit: a server
        # that never says it is ready must fail the run, not hang it.
        first = []
        reader = threading.Thread(target=lambda: first.append(self._server.stdout.readline()),
                                  daemon=True)
        reader.start()
        reader.join(START_SECONDS)
        line = first[0].strip() if first else ""
        if not line.startswith("listening on "):
            self._server.kill()
            self._log.seek(0)
            raise RuntimeError(f"the todo server did not start within {START_SECONDS} seconds: "
                               f"{line!r}\n{self._log.read()}")
        self._url = line.removeprefix("listening on ")
