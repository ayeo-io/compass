"""No script that sets `pipefail` pipes into `grep -q`.

`grep -q` exits at its first match. The command writing into the pipe can
then die of a broken pipe, and under `pipefail` the pipeline reports that
failure, so a line that was found reads as missing. It depends on timing:
`validate.sh` reported `templates/positioning.md` and
`templates/launch-readiness.md` missing in CI on 2026-10-03, though both
exist (#261). A here-string or a test of captured output has no pipe.

Scenario id: GQ-1 (issue `grep-q-under-pipefail`).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE_INTO_GREP_Q = re.compile(r"\|\s*grep\s+-[A-Za-z]*q")


def test_gq_1_no_script_with_pipefail_pipes_into_grep_q():
    tracked = subprocess.run(
        ["git", "ls-files", "scripts", "hooks", "bin"], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.split()
    found = []
    for rel in tracked:
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        if "pipefail" not in text:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if PIPE_INTO_GREP_Q.search(line):
                found.append(f"{rel}:{n}: {line.strip()}")
    assert not found, "\n".join(found)
