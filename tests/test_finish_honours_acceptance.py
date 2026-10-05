"""A quick fix with no natural red can finish.

For a behaviour-preserving refactor, config or docs there is no failing test
to write first, and Compass says to declare that instead: `compass acceptance
start --kind refactor|validation` before the change and `compass acceptance
record` after. `quick-fix finish` then refused, demanding a red, and its
refusal recommended the very acceptance the session had recorded. Both
refactor sessions of the 5 October comparison run ended unfinished that way.

Scenario id: FA-1 (issue `finish-honours-acceptance`).
"""
from __future__ import annotations

from test_quick_fix_verbs import (  # noqa: F401
    _gate_statuses, _git, _manifest, _run, _start, repo)

SLUG = "tidy-add"
TEST = ["--", "python3", "-m", "pytest", "-q", "tests/test_calc.py"]


def _calc(repo, body):
    (repo / "calc.py").write_text(body)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")


def test_fa_1_a_refactor_with_a_recorded_acceptance_finishes(repo):
    _calc(repo, "def add(a, b):\n    total = a + b\n    return total\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    start = _start(repo, SLUG, test="tests/test_calc.py::test_add")
    assert start.returncode == 0, start.stderr
    opened = _run(repo, "acceptance", "start", "--kind", "refactor", "--issue", SLUG, *TEST)
    assert opened.returncode == 0, opened.stdout + opened.stderr
    # The refactor: same behaviour, simpler body.
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    recorded = _run(repo, "acceptance", "record", "--issue", SLUG,
                    "--scenario", "TRC-001", *TEST)
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG,
                  "-m", "Simplify add", "--no-commit", *TEST)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert set(_gate_statuses(repo, SLUG).values()) == {"pass"}


def test_fa_1_without_a_red_or_an_acceptance_finish_still_refuses(repo):
    _calc(repo, "def add(a, b):\n    return a + b\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    start = _start(repo, SLUG, test="tests/test_calc.py::test_add")
    assert start.returncode == 0, start.stderr
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG,
                  "-m", "Nothing proved", "--no-commit", *TEST)
    assert finish.returncode != 0
    assert set(_gate_statuses(repo, SLUG).values()) == {"pending"}


def test_fa_1_an_acceptance_recorded_without_a_scenario_also_finishes(repo):
    # The comparison sessions ran `acceptance record` with no --scenario.
    _calc(repo, "def add(a, b):\n    total = a + b\n    return total\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    assert _start(repo, SLUG, test="tests/test_calc.py::test_add").returncode == 0
    assert _run(repo, "acceptance", "start", "--kind", "refactor", "--issue",
                SLUG, *TEST).returncode == 0
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    assert _run(repo, "acceptance", "record", "--issue", SLUG, *TEST).returncode == 0
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG,
                  "-m", "Simplify add", "--no-commit", *TEST)
    assert finish.returncode == 0, finish.stdout + finish.stderr
    assert set(_gate_statuses(repo, SLUG).values()) == {"pass"}


def test_fa_1_a_green_with_an_acceptance_declared_points_at_record(repo):
    _calc(repo, "def add(a, b):\n    total = a + b\n    return total\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    assert _start(repo, SLUG, test="tests/test_calc.py::test_add").returncode == 0
    assert _run(repo, "acceptance", "start", "--kind", "refactor", "--issue",
                SLUG, *TEST).returncode == 0
    green = _run(repo, "tdd-green", "--issue", SLUG, "--scenario", "TRC-001", *TEST)
    assert green.returncode != 0
    assert "compass acceptance record" in green.stderr, green.stderr
    assert "declare it before the change" not in green.stderr, green.stderr


def test_fa_1_finish_refuses_to_swap_a_declared_validator(repo):
    # A validation acceptance proves what its declared command checks; finish
    # must not record its own test command in that command's place.
    _calc(repo, "def add(a, b):\n    return a + b\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "calc")
    assert _start(repo, SLUG, test="tests/test_calc.py::test_add").returncode == 0
    assert _run(repo, "acceptance", "start", "--kind", "validation", "--issue", SLUG,
                "--", "python3", "-c", "import sys; sys.exit(1)").returncode == 0
    (repo / "calc.py").write_text("def add(a, b):\n    return b + a\n")
    finish = _run(repo, "quick-fix", "finish", "--issue", SLUG,
                  "-m", "Swap", "--no-commit", *TEST)
    assert finish.returncode != 0
    assert "declared" in finish.stderr, finish.stderr
    assert set(_gate_statuses(repo, SLUG).values()) == {"pending"}
