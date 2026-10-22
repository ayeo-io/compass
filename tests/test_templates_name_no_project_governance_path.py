"""A template does not send the reader to a governance file the project lacks.

A project that uses the shipped guardrails and strategies has no
`governance/guardrails.md` or `strategies.md`. A template that names either
as a path points at nothing. A template says "the shipped guardrails" or
"the shipped strategies" instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
PROJECT_PATH = re.compile(r"\b(?:guardrails|strategies)\.md\b")


def test_no_template_names_a_project_guardrails_or_strategies_file():
    found = []
    for path in sorted(TEMPLATES.glob("*.md")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PROJECT_PATH.search(line):
                found.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert not found, "templates name a governance file a project may not have:\n" + "\n".join(found)
