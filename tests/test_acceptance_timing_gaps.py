"""A refactor acceptance with no change is refused in a fresh repository.

`compass acceptance record` refuses a refactor whose source tree has not
changed since `acceptance start`. The tree hash counted pytest's cache
folder, which the refactor's own baseline run creates, so in a repository
with no cache yet the refusal never fired.

Scenario id: AT-1 (issue `acceptance-timing-gaps`).
"""
from __future__ import annotations

from test_quick_fix_verbs import _git, _run, _start, repo  # noqa: F401

SLUG = "tidy-add"
TEST = ["--", "python3", "-m", "pytest", "-q", "tests/test_calc.py"]


def _calc(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    total = a + b\n    return total\n")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    assert _start(repo, SLUG, test="tests/test_calc.py::test_add").returncode == 0


def test_at_1_a_refactor_with_no_edit_is_refused_in_a_fresh_repository(repo):
    _calc(repo)
    assert not (repo / ".pytest_cache").exists()
    assert _run(repo, "acceptance", "start", "--kind", "refactor", "--issue",
                SLUG, *TEST).returncode == 0
    recorded = _run(repo, "acceptance", "record", "--issue", SLUG, *TEST)
    assert recorded.returncode != 0, recorded.stdout
    assert "has not changed" in recorded.stderr, recorded.stderr
