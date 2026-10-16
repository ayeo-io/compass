"""The CLI exits quietly when the reader of its output closes the pipe.

`compass policy show | head -n 5` used to end in a BrokenPipeError
traceback. The handler in `run_with_mode()` must hide that and exit 141, the
status a shell reports for a process that SIGPIPE ended. A broken pipe from
anything else, such as a socket or a child process, is a real fault and must
still raise.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
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
    # A pipe buffer holds 65,536 bytes. Output below that size is written
    # without error even after the close, so the test would pass without
    # exercising the handler.
    full = subprocess.run([sys.executable, str(CLI), "policy", "show"],
                          cwd=ROOT, capture_output=True, timeout=60)
    assert len(full.stdout) > 65536, "policy show output shrank below the pipe buffer"
    assert "Traceback" not in stderr, stderr
    assert "BrokenPipeError" not in stderr, stderr
    assert code == 141


def test_broken_pipe_from_another_pipe_reraises():
    """A verb that breaks a pipe other than stdout must show the error.

    Stdout here is a pipe whose reader stays open, as when the output goes to
    a reader that has not finished. The verb writes to a second pipe whose
    reader is closed, as a dead child process would leave it.
    """
    script = textwrap.dedent(f"""
        import argparse, os, sys
        sys.path.insert(0, {str(ROOT / "cli")!r})
        from compass_pkg import terminal

        def verb(_args):
            read_end, write_end = os.pipe()
            os.close(read_end)
            os.write(write_end, b"lost")

        sys.exit(terminal.run_with_mode(argparse.Namespace(), verb))
    """)
    proc = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=60)
    stderr = proc.stderr.decode()

    assert "BrokenPipeError" in stderr, stderr
    assert proc.returncode != 141
