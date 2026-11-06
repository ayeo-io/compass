"""Changing the three texts a session acts on most needs a measured run.

The injected contract, the hook's refusal messages and the TDD skill are the
words a session is most likely to act on. `docs/releasing.md` makes a
measured run, compared with a baseline, a precondition for changing any of
them. Since ADR-093 the run is an sdd-bench run: the harness left this
repository, so the guide names the sdd-bench runner and the option that
points it at this checkout.

Scenario id: SPT-4, "The releasing guide needs a run" (issue
`skill-prose-pressure-tests`).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_spt_4_the_releasing_guide_requires_a_run_before_changing_the_three_texts():
    text = " ".join((ROOT / "docs" / "releasing.md").read_text(encoding="utf-8").split())
    section = text[text.index("## Before changing the words sessions act on"):]
    section = section.split("## ", 2)[1]
    for name in ("compass-contract.md", "hooks/pre-tool.sh",
                 "skills/tdd-discipline/SKILL.md", "sdd-bench",
                 "`harness.py`", "`--plugin-source`", "`score.py`"):
        assert name in section, name
    assert "does not merge without a written reason" in section
    assert "five runs per scenario and condition" in section
