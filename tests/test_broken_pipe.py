"""The CLI exits quietly when the reader of its output closes the pipe.

`compass policy show | head -n 5` used to end in a BrokenPipeError
traceback. The handler in `main()` must hide that and exit 141, the status a
shell reports for a process that SIGPIPE ended.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def test_policy_show_exits_quietly_when_the_reader_closes_the_pipe():
    proc = subprocess.Popen(
        [sys.executable, str(CLI), "policy", "show"],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    first_line = proc.stdout.readline()   # read one line, as `head` would
    proc.stdout.close()                   # then close the pipe
    stderr = proc.stderr.read().decode()
    code = proc.wait(timeout=60)
    proc.stderr.close()

    assert first_line, "policy show printed nothing"
    assert "Traceback" not in stderr, stderr
    assert "BrokenPipeError" not in stderr, stderr
    assert code == 141
