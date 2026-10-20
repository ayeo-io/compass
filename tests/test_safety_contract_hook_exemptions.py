"""The safety contract states what the pre-tool hook lets through, and why.

A comment-only Edit, the path classes, the messages and the budget are part of
what Compass guarantees and what it does not: a reader must find each rule and
each limit in `docs/safety-contract.md`, and the figures must be the ones the
hook sets.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "safety-contract.md"
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _section(heading_words: str) -> str:
    """The text of the `###` section whose heading holds `heading_words`, with
    whitespace made single."""
    text = CONTRACT.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^### ", text)
    found = [p for p in parts if p.split("\n", 1)[0].startswith(heading_words)]
    assert found, f"docs/safety-contract.md has no section '### {heading_words}'"
    return " ".join(found[0].split())


def _hook_number(name: str) -> int:
    found = re.search(rf"^{name}=(\d+)$", HOOK.read_text(encoding="utf-8"), re.M)
    assert found, f"hooks/pre-tool.sh does not set {name}"
    return int(found.group(1))


def test_contract_states_comment_only_rule_messages_and_path_classes():
    """Scenario id: `TRC-025` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    section = _section("An Edit that changes only comments")
    page = " ".join(CONTRACT.read_text(encoding="utf-8").split())

    # The covered and uncovered languages.
    for word in ("Python", "YAML", "Shell", "not covered", "every other language"):
        assert word in section, word
    # What counts as code even in a comment.
    for word in ("type: ignore", "noqa", "nosec", "fmt: off", "shebang",
                 "encoding line", "hidden character"):
        assert word in section, word
    # The fail-closed rule and the size limit.
    assert "judged as before" in section
    assert "1048576 bytes" in section
    for word in ("does not parse", "duplicate key", "python3"):
        assert word in section, word
    # The budget: every constant of the cost table, as the hook sets it, and
    # the measured worst cases of the shape table.
    for name in ("COST_EDIT_START", "COST_EDIT_PARSE_PY", "COST_EDIT_PARSE_YAML",
                 "COST_EDIT_KB_PY", "COST_EDIT_KB_YAML", "EDIT_ALARM_SECONDS"):
        assert f"{name} {_hook_number(name)}" in section, name
    assert "signal.alarm" in section
    assert "| Python, statements of two bytes" in section
    assert "| YAML, flow sequences of one-digit numbers" in section
    # The path classes.
    for path in ("evals/*/seed/", "examples/", "cli/vendor/", ".github/scripts/",
                 "src/examples/", "db/seed/"):
        assert path in section, path
    assert "only ratchets up" in section
    # The messages.
    assert "the issue that changed most recently" in section
    assert "names an issue with no folder under" in section
    assert "bad-session-issue-restart" in section
    assert "compass acceptance start" in section
    # The limit the reader cannot lock.
    assert "between the read and the Edit" in section
    # The line that said declared shell files are not guarded is gone.
    assert "Shell scripts, makefiles and extensionless scripts are not classified" \
        not in page
    assert "enforcement.code_globs" in section and "is guarded" in section
