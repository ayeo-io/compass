"""What 9.0.0 removed with the stage agents, and how an old record or call reads.

ADR-090 removes the stage agents, the multiagent breakdown, model tiers,
effort per dispatch, execution profiles and the headless runner. A command
line, a project file or a stored record can still name one of them:

- a removed verb or flag fails to parse, and the error names the removal;
- a removed `compass.yml` key is read as before and `compass policy lint`
  names it;
- a stored generation that lists the removed check reports it as nothing to
  check, so no archived issue goes from pass to fail.

Issue: ayeo-io/compass-delivery#352.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))


def _run(args, cwd):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


# --- a removed verb or flag -------------------------------------------------------

REMOVED_CALLS = [
    ["run", "demo", "--stage", "implement", "--stop-file", "stop"],
    ["profile", "show", "default"],
]


@pytest.mark.parametrize("argv", REMOVED_CALLS, ids=lambda a: " ".join(a[:2]))
def test_a_removed_verb_or_flag_names_its_removal(tmp_path, argv):
    proc = _run(argv, tmp_path)
    assert proc.returncode == 2, proc.stderr
    assert "removed in 9.0.0" in proc.stderr, proc.stderr
    assert "ADR-090" in proc.stderr, proc.stderr


def test_a_kept_verb_that_fails_to_parse_gets_no_removal_line(tmp_path):
    proc = _run(["approach", "show", "--no-such-flag"], tmp_path)
    assert proc.returncode == 2
    assert "removed in 9.0.0" not in proc.stderr


def test_the_removal_line_matches_tokens_not_prefixes():
    from compass_pkg import removed_parts
    assert removed_parts.line_for(["running"]) is None
    assert removed_parts.line_for(["profiles"]) is None
    assert "compass run" in removed_parts.line_for(["run", "x"])
    assert "compass profile" in removed_parts.line_for(["profile", "show", "x"])
