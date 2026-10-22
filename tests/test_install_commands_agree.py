"""The install docs give the same plugin install commands.

Claude Code installs a plugin from the shell in one line, and from inside a
session with two commands. Four docs show both. If one doc drifts, a new
adopter gets a different command depending on where they started reading.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = (
    "README.md",
    "docs/quickstart.md",
    "docs/five-minutes.md",
    "docs/install-smoke-test.md",
)
SHELL_FORM = "claude plugin install compass --marketplace ayeo-io/compass"
SESSION_ADD = "/plugin marketplace add ayeo-io/compass"
SESSION_INSTALL = "/plugin install compass@compass"


def test_install_docs_show_the_shell_form_first_and_the_session_form_second():
    problems = []
    for doc in DOCS:
        text = (ROOT / doc).read_text(encoding="utf-8")
        for needed in (SHELL_FORM, SESSION_ADD, SESSION_INSTALL):
            if text.count(needed) != 1:
                problems.append(f"{doc}: expected {needed!r} once, found {text.count(needed)}")
        if SHELL_FORM in text and SESSION_ADD in text:
            if text.index(SHELL_FORM) > text.index(SESSION_ADD):
                problems.append(f"{doc}: the shell form must come before the session form")
    assert not problems, "\n".join(problems)
