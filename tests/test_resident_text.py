"""The text every session reads stays under 600 words, and the contract fits
on one screen.

Resident text is what Claude Code keeps in context on every request, whether
the session uses it or not:

- the operating contract, `compass-contract.md`, which the SessionStart hook
  puts into every session;
- the frontmatter `description:` of each skill and command a model can invoke;
- one word for the name Claude Code lists beside each of those descriptions.

The lessons block and the language line are not counted: a project writes
them, not Compass.

These are limits, not targets (ADR-097, #358 [Cut resident text under 600
words and name the fix in each refusal]): over either one, the build fails,
because the issue says the text must "stay under". The older size targets in
`test_context_budget.py`, `test_session_bootstrap.py` and
`test_prompt_layer.py` still only warn. One screen is 40 lines of at most 80
columns: 80 columns is the width every terminal opens at, and 40 lines is what
a laptop shows with room for a title bar and a prompt.

Each test prints what it measured. Run with `-s` to see the numbers.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "compass-contract.md"

RESIDENT_WORD_LIMIT = 600
CONTRACT_LINE_LIMIT = 40
CONTRACT_COLUMN_LIMIT = 80

#: Words per token, the ratio `tests/test_prompt_layer.py` uses.
TOKENS_PER_WORD = 1.35


def _frontmatter(path):
    m = re.match(r"^---\n(.*?)\n---", path.read_text(encoding="utf-8"), re.S)
    return m.group(1) if m else ""


def _description_words(path):
    """The words of the frontmatter `description:`, which Claude Code keeps loaded."""
    d = re.search(r"description:\s*(.+?)(?=\n[a-z_-]+:|\Z)", _frontmatter(path), re.S)
    return len(d.group(1).split()) if d else 0


def _model_can_invoke(path):
    """A file with `disable-model-invocation: true` is not in the model's context.
    The four approval commands set it (ADR-068), so they cost no resident words."""
    return re.search(r"^disable-model-invocation:\s*true\s*$", _frontmatter(path),
                     re.M) is None


def _resident():
    """The resident words by part, and the files counted."""
    parts, counted = {}, []
    for label, paths in (
        ("skills", sorted((ROOT / "skills").glob("*/SKILL.md"))),
        ("commands", sorted((ROOT / "commands").glob("*.md"))),
        ("agents", sorted((ROOT / "agents").glob("*.md"))),
    ):
        invocable = [p for p in paths if _model_can_invoke(p)]
        parts[label] = sum(_description_words(p) for p in invocable)
        counted += invocable
    parts["names"] = len(counted)
    parts["contract"] = len(CONTRACT.read_text(encoding="utf-8").split())
    return parts


def test_the_resident_text_is_under_600_words():
    parts = _resident()
    total = sum(parts.values())
    breakdown = ", ".join(f"{k} {v}" for k, v in parts.items())
    tokens = round(total * TOKENS_PER_WORD)
    print(f"\nresident text: {total} words, about {tokens} tokens ({breakdown})")
    assert total < RESIDENT_WORD_LIMIT, (
        f"the resident text is {total} words, not under {RESIDENT_WORD_LIMIT} "
        f"({breakdown}). Every request pays for it. Shorten the contract or a "
        "description; do not raise the limit.")


def test_the_contract_fits_on_one_screen():
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    longest = max((len(line) for line in lines), default=0)
    print(f"\ncompass-contract.md: {len(lines)} lines, longest {longest} columns, "
          f"{len(CONTRACT.read_text(encoding='utf-8'))} characters")
    assert len(lines) <= CONTRACT_LINE_LIMIT, (
        f"compass-contract.md is {len(lines)} lines, over the "
        f"{CONTRACT_LINE_LIMIT} lines of one screen")
    wide = [f"line {n}: {len(line)} columns"
            for n, line in enumerate(lines, 1) if len(line) > CONTRACT_COLUMN_LIMIT]
    assert not wide, (
        f"compass-contract.md has lines over {CONTRACT_COLUMN_LIMIT} columns: "
        + "; ".join(wide))
