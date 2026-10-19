"""`compass approach evaluate --help` names the configuration it applies.

The help said the command applies governance/routing-policy.yml. The code
applies the issue's stored generation, or with --write the project's
resolved configuration (compass.yml over the shipped default).

Scenario id: TRC-001, in the delivery approach of issue
`approach-evaluate-help-names-config`.
"""
from __future__ import annotations

from pathlib import Path

import subprocess

ROOT = Path(__file__).resolve().parent.parent


def _help_text() -> str:
    result = subprocess.run(
        [str(ROOT / "cli" / "compass"), "approach", "evaluate", "--help"],
        capture_output=True, text=True, timeout=60, cwd=ROOT)
    return " ".join(result.stdout.split())


def test_help_names_the_configuration_it_applies():
    text = _help_text()
    assert "stored generation" in text
    assert "compass.yml" in text
    assert "resolved configuration" in text
    assert "applies governance/routing-policy.yml" not in text
