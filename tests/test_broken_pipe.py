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


# Any verb that prints more than the 65,536-byte pipe buffer will do. Since
# 9.0.0 `policy show` prints four lines (ADR-094), so the long output is the
# lint's JSON document for a `compass.yml` with one unknown key per finding.
LINT = ["policy", "lint", "--json"]
UNKNOWN_KEYS = 800


def _project(tmp_path):
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text(
        "schema: 1\n" + "".join(f"unknown-{n:04d}: 1\n" for n in range(UNKNOWN_KEYS)),
        encoding="utf-8")
    return tmp_path


def test_policy_lint_exits_quietly_when_the_reader_closes_the_pipe(tmp_path):
    root = _project(tmp_path)
    proc = subprocess.Popen(
        [sys.executable, str(CLI), *LINT],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0,
    )
    # Unbuffered, so the read takes only the first line out of the pipe. A
    # buffered read takes up to 8,192 bytes, and the rest can then fit.
    first_line = proc.stdout.readline()   # read one line, as `head` would
    proc.stdout.close()                   # then close the pipe
    stderr = proc.stderr.read().decode()
    code = proc.wait(timeout=60)
    proc.stderr.close()

    assert first_line, "policy lint printed nothing"
    # A pipe buffer holds 65,536 bytes. Output that fits in it after the
    # first line is written without error even after the close, so the test
    # would pass without exercising the handler.
    full = subprocess.run([sys.executable, str(CLI), *LINT],
                          cwd=root, capture_output=True, timeout=60)
    assert len(full.stdout) - len(first_line) > 65536, (
        "policy lint output shrank below the pipe buffer")
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
