"""The contribution guide says what judges an outside pull request.

`CONTRIBUTING.md` names the CI check `main` needs, how review works now
that the automatic review starts only by hand (governance/decisions,
`ci-review-manual-only`), the review rules file, the code owners and the
house rules a reviewer checks. Every file it names must exist. The
CODEOWNERS comment says what the ruleset needs, not more (issue
`contribution-guide`).

Scenario id: CG-1.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "CONTRIBUTING.md"


def test_cg_1_the_guide_names_what_judges_a_pull_request():
    text = GUIDE.read_text(encoding="utf-8")
    for needed in ("self-check", "governance/review-rules.yml", ".github/CODEOWNERS",
                   "make test", "em dash", "good first issue"):
        assert needed in text, needed
    assert "starts only by hand" in text or "started by hand" in text, text


def test_cg_1_every_path_the_guide_names_exists():
    text = GUIDE.read_text(encoding="utf-8")
    paths = set(re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.\w+)`", text))
    paths |= set(re.findall(r"\]\(((?!https?:)[^)#]+)\)", text))
    missing = sorted(p for p in paths if not (ROOT / p).exists())
    assert not missing, missing


def test_cg_1_codeowners_claims_no_review_requirement_the_ruleset_lacks():
    text = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    assert "require_code_owner_review: true" not in text, text


def test_cg_1_the_readme_points_to_the_guide():
    assert "(CONTRIBUTING.md)" in (ROOT / "README.md").read_text(encoding="utf-8")
