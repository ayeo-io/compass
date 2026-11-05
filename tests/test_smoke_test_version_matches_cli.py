"""The documented `compass --version` output is what the CLI actually prints.

This compares the documented `compass --version` banner with what the CLI
prints, not with a phrase written in advance: the primary record for what
the CLI prints is the CLI. A fenced block is not scanned for vocabulary, so
only a comparison with the CLI catches a wrong banner there.

Scenario ids: see the issue's acceptance criteria (`TRC-1`, `TRC-2`).
"""
from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
SMOKE_TEST = ROOT / "docs" / "install-smoke-test.md"

# Any line of the shape `compass 2.1.0 (issue schema 2.0)`, whatever words it
# uses - the point is to find every version banner the doc shows, including
# one spelled in vocabulary nobody uses any more.
_BANNER = re.compile(r"^compass \d+\.\d+\.\d+ \([a-z]+ schema [\d.]+\)$", re.M)


def _cli_version_banner() -> str:
    """The first line of `compass --version`, without the PyYAML line."""
    result = subprocess.run(
        ["python3", str(ROOT / "cli" / "compass"), "--version"],
        cwd=str(ROOT), capture_output=True, text=True, check=True, timeout=30,
    )
    return result.stdout.strip().splitlines()[0].split(" PyYAML")[0].strip()


def test_trc_1_every_documented_version_banner_matches_the_cli():
    doc = SMOKE_TEST.read_text(encoding="utf-8")
    banners = _BANNER.findall(doc)
    assert banners, (
        "the smoke test shows no `compass --version` banner at all - it is "
        "meant to tell a reader what to expect"
    )

    actual = _cli_version_banner()
    wrong = sorted({b for b in banners if b != actual})
    assert not wrong, (
        f"docs/install-smoke-test.md shows version output the CLI does not "
        f"produce.\n  CLI prints: {actual}\n  doc shows:  {wrong}\n"
        f"Compare against the CLI, not against a remembered phrase."
    )


def test_trc_2_the_documented_banner_uses_current_vocabulary():
    """A second check: the retired spelling must not come back.

    `TRC-1` already fails if the doc disagrees with the CLI, so this only
    catches the case where the CLI itself regressed to the old word - which
    is worth catching separately, because then both would agree and be wrong.
    """
    doc = SMOKE_TEST.read_text(encoding="utf-8")
    for banner in _BANNER.findall(doc):
        assert "task schema" not in banner, (
            f"{banner!r} uses the retired v1 word. The vocabulary freeze "
            f"replaced 'task' with 'issue'; a fenced block is not an "
            f"exemption from being correct."
        )
