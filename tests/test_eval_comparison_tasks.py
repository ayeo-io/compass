"""CMP-3: six comparison scenarios under evals/scenarios/, one per class,
each with hidden tests that fail on the seed and pass on a correct change.

Every one of the six is copied into a fresh temporary directory before any
test command runs, so nothing here ever writes into the tracked seed. The
"correct change" is a reference solution kept in this file, never in the
seed: applying it is how this file proves a hidden test can both fail (on
the untouched seed) and pass (once the change is actually made), which is
the CMP-3 contract for all six.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "evals" / "scenarios"

# The repository reads YAML only through compass_pkg.core.load_yaml, so the
# bundled PyYAML is the one used here too.
sys.path.insert(0, str(REPO_ROOT / "cli"))
from compass_pkg.core import load_yaml  # noqa: E402

TASK_IDS = (
    "cmp-small-fix",
    "cmp-feature",
    "cmp-legacy",
    "cmp-risky",
    "cmp-spike",
    "cmp-resume",
)

OWN_TEST_COMMAND = ("python3", "-m", "pytest", "-q")

# A prompt must read as a real request. None of these words, which name the
# evaluation itself rather than what it asks for, may appear in one.
META_WORDS = (
    "eval", "harness", "hidden", "framework", "scenario",
    "rubric", "judge", "condition", "compass",
)


def _scenario_dir(task_id: str) -> Path:
    return SCENARIOS_DIR / task_id


def _load_scenario(task_id: str) -> dict:
    return load_yaml(str(_scenario_dir(task_id) / "scenario.yml"))


def _prepare_seed(task_id: str, workdir: Path) -> Path:
    shutil.copytree(_scenario_dir(task_id) / "seed", workdir, dirs_exist_ok=True)
    return workdir


def _copy_hidden_tests(task_id: str, workdir: Path) -> None:
    shutil.copytree(_scenario_dir(task_id) / "hidden_tests", workdir, dirs_exist_ok=True)


def _run(command, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=60,
    )


def _run_hidden_command(task_id: str, workdir: Path) -> subprocess.CompletedProcess:
    command = shlex.split(_load_scenario(task_id)["hidden_command"])
    return _run(command, workdir)


def _require_python3():
    if shutil.which("python3") is None:
        pytest.skip("python3 is not on PATH")


# ---------------------------------------------------------------------------
# Reference solutions - the correct change for each of the six, applied
# to a copy of the seed, never to the tracked seed itself.
# ---------------------------------------------------------------------------

_SMALL_FIX_SOURCE = '''"""Small date helpers for a scheduling tool."""

from __future__ import annotations

MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def is_leap_year(year: int) -> bool:
    """Return True if year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_month(year: int, month: int) -> int:
    """Return how many days month (1-12) has in year."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    if month == 2 and is_leap_year(year):
        return 29
    return MONTH_LENGTHS[month - 1]


def day_of_year(year: int, month: int, day: int) -> int:
    """Return the day number within year, counting January 1 as day 1."""
    if not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    total = day
    for earlier_month in range(1, month):
        total += days_in_month(year, earlier_month)
    return total
'''


def _apply_small_fix(workdir: Path) -> None:
    (workdir / "src" / "calendar_utils.py").write_text(_SMALL_FIX_SOURCE, encoding="utf-8")


_FEATURE_SOURCE = '''"""A small playlist tracker."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Track:
    title: str
    duration_seconds: int


def add_track(playlist: list[Track], title: str, duration_seconds: int) -> None:
    """Append a track to playlist."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    playlist.append(Track(title, duration_seconds))


def total_duration(playlist: list[Track]) -> int:
    """Return the total duration of playlist, in seconds."""
    return sum(track.duration_seconds for track in playlist)


def track_titles(playlist: list[Track]) -> list[str]:
    """Return the titles in playlist, in playlist order."""
    return [track.title for track in playlist]


def longest_track(playlist: list[Track]) -> str:
    """Return the title of the longest track in playlist.

    A tie goes to whichever of the tied tracks was added first.
    """
    if not playlist:
        raise ValueError("playlist must not be empty")
    best = playlist[0]
    for track in playlist[1:]:
        if track.duration_seconds > best.duration_seconds:
            best = track
    return best.title
'''


def _apply_feature(workdir: Path) -> None:
    (workdir / "src" / "playlist.py").write_text(_FEATURE_SOURCE, encoding="utf-8")


_LEGACY_SOURCE = '''"""Turns a raw tag string from an import file into a clean tag list."""

from __future__ import annotations

import re


def parse_tags(raw: str) -> list[str]:
    """Split raw on commas or semicolons into a clean list of tags."""
    seen_lower: set[str] = set()
    tags: list[str] = []
    for chunk in re.split(r"[,;]", raw):
        tag = chunk.strip()
        if not tag:
            continue
        key = tag.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        tags.append(tag)
    return tags
'''


def _apply_legacy(workdir: Path) -> None:
    (workdir / "src" / "tag_parser.py").write_text(_LEGACY_SOURCE, encoding="utf-8")


_RISKY_SOURCE = '''"""Splitting a shared bill in whole cents, with no floating point."""

from __future__ import annotations

SERVICE_CHARGE_THRESHOLD_CENTS = 5000
SERVICE_CHARGE_CENTS = 150


def split_bill(total_cents: int, n_people: int) -> list[int]:
    """Split total_cents as evenly as possible across n_people.

    Every person gets total_cents // n_people, and the first
    total_cents % n_people people get one extra cent, so the parts
    always add up to exactly total_cents.
    """
    if n_people <= 0:
        raise ValueError("n_people must be positive")
    if total_cents < 0:
        raise ValueError("total_cents must not be negative")
    base, remainder = divmod(total_cents, n_people)
    return [base + 1 if i < remainder else base for i in range(n_people)]


def apply_tip(total_cents: int, tip_percent: int) -> int:
    """Return total_cents plus a tip_percent percentage, rounded down."""
    if tip_percent < 0:
        raise ValueError("tip_percent must not be negative")
    return total_cents + total_cents * tip_percent // 100


def total_with_service_charge(total_cents: int) -> int:
    """Return total_cents plus a flat service charge, once the bill goes
    past the threshold. At exactly the threshold there is no charge."""
    if total_cents < 0:
        raise ValueError("total_cents must not be negative")
    if total_cents <= SERVICE_CHARGE_THRESHOLD_CENTS:
        return total_cents
    return total_cents + SERVICE_CHARGE_CENTS
'''


def _apply_risky(workdir: Path) -> None:
    (workdir / "src" / "billing_split.py").write_text(_RISKY_SOURCE, encoding="utf-8")


_SPIKE_FINDINGS = (
    "Yes - the Cache class can expire entries on its own using only the "
    "Python standard library, no new dependency needed. Store the expiry "
    "time per key with time.monotonic() when set() is called, and check it "
    "in get(), dropping the entry once that time has passed.\n"
)


def _apply_spike(workdir: Path) -> None:
    (workdir / "FINDINGS.md").write_text(_SPIKE_FINDINGS, encoding="utf-8")


_RESUME_SOURCE = '''"""Turns a list of raw scores into a grade report."""

from __future__ import annotations


def parse_scores(lines: list[str]) -> list[tuple[str, int]]:
    """Turn lines like "Ada,91" into a list of (name, score) pairs.

    A line with no comma, or a score that is not a whole number, is
    skipped.
    """
    scores: list[tuple[str, int]] = []
    for line in lines:
        if "," not in line:
            continue
        name, _, raw_score = line.partition(",")
        name = name.strip()
        raw_score = raw_score.strip()
        if not raw_score.lstrip("-").isdigit():
            continue
        scores.append((name, int(raw_score)))
    return scores


def summarize(scores: list[tuple[str, int]]) -> dict[str, object]:
    """Return the average score and the names of the highest and lowest
    scorers. A tie goes to whichever student comes first in scores."""
    if not scores:
        raise ValueError("scores must not be empty")
    average = sum(score for _, score in scores) / len(scores)
    highest_name, highest_score = scores[0]
    lowest_name, lowest_score = scores[0]
    for name, score in scores[1:]:
        if score > highest_score:
            highest_name, highest_score = name, score
        if score < lowest_score:
            lowest_name, lowest_score = name, score
    return {"average": average, "highest": highest_name, "lowest": lowest_name}
'''


def _apply_resume(workdir: Path) -> None:
    (workdir / "src" / "grades.py").write_text(_RESUME_SOURCE, encoding="utf-8")


REFERENCE_SOLUTIONS = {
    "cmp-small-fix": _apply_small_fix,
    "cmp-feature": _apply_feature,
    "cmp-legacy": _apply_legacy,
    "cmp-risky": _apply_risky,
    "cmp-spike": _apply_spike,
    "cmp-resume": _apply_resume,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_six_cmp_task_directories_exist():
    found = sorted(p.name for p in SCENARIOS_DIR.glob("cmp-*") if p.is_dir())
    assert found == sorted(TASK_IDS)


def test_every_task_class_has_a_reference_solution():
    assert set(REFERENCE_SOLUTIONS) == set(TASK_IDS)


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_scenario_has_the_fields_a_comparison_task_needs(task_id):
    scenario_dir = _scenario_dir(task_id)
    assert (scenario_dir / "scenario.yml").is_file()
    assert (scenario_dir / "seed").is_dir()
    assert (scenario_dir / "hidden_tests").is_dir()
    data = _load_scenario(task_id)
    assert data["id"] == task_id
    assert isinstance(data["prompt"], str) and data["prompt"].strip()
    assert isinstance(data["budget_usd"], (int, float)) and data["budget_usd"] > 0
    assert isinstance(data["hidden_command"], str) and data["hidden_command"].strip()
    assert "behaviours" not in data


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_prompt_reads_as_a_real_request(task_id):
    prompt = _load_scenario(task_id)["prompt"].lower()
    for word in META_WORDS:
        assert word not in prompt, f"{task_id} prompt names {word!r}"


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_seed_is_small(task_id):
    seed_dir = _scenario_dir(task_id) / "seed"
    line_count = sum(
        len(p.read_text(encoding="utf-8").splitlines())
        for p in seed_dir.rglob("*.py")
    )
    assert line_count < 200, f"{task_id} seed is {line_count} lines of Python"


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_seeds_own_tests_pass(task_id, tmp_path):
    _require_python3()
    _prepare_seed(task_id, tmp_path)
    result = _run(OWN_TEST_COMMAND, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_hidden_tests_fail_on_the_unmodified_seed(task_id, tmp_path):
    _require_python3()
    _prepare_seed(task_id, tmp_path)
    _copy_hidden_tests(task_id, tmp_path)
    result = _run_hidden_command(task_id, tmp_path)
    assert result.returncode != 0, (
        f"{task_id} hidden tests passed on the unmodified seed:\n"
        + result.stdout + result.stderr
    )


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_hidden_tests_pass_after_the_reference_solution(task_id, tmp_path):
    _require_python3()
    _prepare_seed(task_id, tmp_path)
    _copy_hidden_tests(task_id, tmp_path)
    REFERENCE_SOLUTIONS[task_id](tmp_path)

    result = _run_hidden_command(task_id, tmp_path)
    assert result.returncode == 0, (
        f"{task_id} hidden tests still fail after the reference solution:\n"
        + result.stdout + result.stderr
    )

    # The reference solution must not break what already worked.
    own_result = _run(OWN_TEST_COMMAND, tmp_path)
    assert own_result.returncode == 0, own_result.stdout + own_result.stderr
