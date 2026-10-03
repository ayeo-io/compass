"""CMP-3: fourteen comparison scenarios under evals/scenarios/, one per
class, each with hidden tests that fail on the seed and pass on a correct
change. Eight also have a careless change that passes the seed's own tests
and fails the hidden ones, so the comparison can tell a careful session
from a careless one: the four from the first comparison (CMP-3), and four where careful process
should beat a careless change (issue #340).

Every one of the scenarios is copied into a fresh temporary directory before any
test command runs, so nothing here ever writes into the tracked seed. The
"correct change" is a reference solution kept in this file, never in the
seed: applying it is how this file proves a hidden test can both fail (on
the untouched seed) and pass (once the change is actually made), which is
the CMP-3 contract for all of them.
"""
from __future__ import annotations

import json
import re
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
    "cmp-hidden-requirement",
    "cmp-call-sites",
    "cmp-refactor",
    "cmp-edge-case",
    "cmp-late-tidy",
    "cmp-shared-helper",
    "cmp-resume-decision",
    "cmp-second-change",
)

OWN_TEST_COMMAND = ("python3", "-m", "pytest", "-q")

# A prompt must read as a real request. None of these words, which name the
# evaluation itself rather than what it asks for, may appear in one.
META_WORDS = (
    "eval", "harness", "hidden", "framework", "scenario",
    "rubric", "judge", "condition", "compass",
)

# The record overlay directory per condition, for the scenarios that start
# from earlier work (cmp-resume, cmp-resume-decision, cmp-second-change), named the way
# evals/harness.py names them: "seed_" plus the condition, hyphens turned to
# underscores.
CONDITION_OVERLAY_DIRS = {
    "bare": "seed_bare",
    "compass": "seed_compass",
    "superpowers": "seed_superpowers",
    "spec-kit": "seed_spec_kit",
}


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


def _overlay_dir(task_id: str, condition: str) -> Path:
    return _scenario_dir(task_id) / CONDITION_OVERLAY_DIRS[condition]


def _overlay_markdown_text(overlay_dir: Path) -> str:
    """Every markdown file's text under overlay_dir, joined - so a test can
    check that every condition's record describes the same thing without
    caring which framework's own shape it is written in."""
    return "\n".join(
        p.read_text(encoding="utf-8") for p in sorted(overlay_dir.rglob("*.md"))
    )


# ---------------------------------------------------------------------------
# Reference solutions - the correct change for each scenario, applied
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


# A second correct change, for cmp-risky: the outward function the prompt
# names, `total_with_service_charge`, is the same - but it is built from a
# private helper under a different name. The hidden tests must pass this
# too: they check the one name the prompt asks for, not how the file gets
# there.
_RISKY_SOURCE_WITH_A_DIFFERENT_HELPER_NAME = '''"""Splitting a shared bill in whole cents, with no floating point."""

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


def _extra_charge_for(total_cents: int) -> int:
    """A private helper under its own name - only total_with_service_charge
    is the name the prompt asks for."""
    if total_cents <= SERVICE_CHARGE_THRESHOLD_CENTS:
        return 0
    return SERVICE_CHARGE_CENTS


def total_with_service_charge(total_cents: int) -> int:
    """Return total_cents plus a flat service charge, once the bill goes
    past the threshold. At exactly the threshold there is no charge."""
    if total_cents < 0:
        raise ValueError("total_cents must not be negative")
    return total_cents + _extra_charge_for(total_cents)
'''


_SPIKE_FINDINGS = (
    "Yes - the Cache class can expire entries on its own using only the "
    "Python standard library, no new dependency needed. Store the expiry "
    "time per key with time.monotonic() when set() is called, and check it "
    "in get(), dropping the entry once that time has passed.\n"
)

# A near-miss finding, close enough in surface vocabulary to have passed the
# review's original loose match ("yes" as a substring, "time" as a
# substring), but not a real answer to the question the prompt asks.
_SPIKE_NEAR_MISS_FINDINGS = (
    "Not sure - maybe sometime we could look into it, but for now the "
    "cache keeps everyone's eyes on the data as it is.\n"
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


# --- The four scenarios that separate a careful change from a careless one --

def _write(workdir: Path, rel: str, text: str) -> None:
    (workdir / rel).write_text(text, encoding="utf-8")


_BILLING_HEAD = '''"""Bill helpers for splitting costs between friends."""

from __future__ import annotations


def format_pence(amount: int) -> str:
    """Show an amount of pence as pounds, e.g. 1234 -> '£12.34'."""
    pounds, pence = divmod(amount, 100)
    return f"£{pounds}.{pence:02d}"


def add_tip(total: int, percent: int) -> int:
    """Return total plus a tip of percent, rounded down to whole pence."""
    return total + total * percent // 100
'''


def _apply_hidden_requirement(workdir: Path) -> None:
    _write(workdir, "src/billing.py", _BILLING_HEAD + '''

def split_bill(total: int, people: int) -> list[int]:
    """Split total pence between people; leftover pence go to the first."""
    base, extra = divmod(total, people)
    return [base + 1 if i < extra else base for i in range(people)]
''')


def _careless_hidden_requirement(workdir: Path) -> None:
    _write(workdir, "src/billing.py", _BILLING_HEAD + '''

def split_bill(total: int, people: int) -> list[int]:
    """Split total between people."""
    return [total // people] * people
''')


_PRICING_CORRECT = '''"""Price formatting."""

from __future__ import annotations

SYMBOLS = {"GBP": "£", "EUR": "€"}


def format_price(amount: int, currency: str = "GBP") -> str:
    """Show amount (in the currency's minor unit) with its symbol."""
    whole, minor = divmod(amount, 100)
    return f"{SYMBOLS[currency]}{whole}.{minor:02d}"
'''


def _apply_call_sites(workdir: Path) -> None:
    _write(workdir, "src/pricing.py", _PRICING_CORRECT)


def _careless_call_sites(workdir: Path) -> None:
    _write(workdir, "src/pricing.py", _PRICING_CORRECT.replace(
        'currency: str = "GBP"', "currency: str"))
    invoice = (workdir / "src" / "invoice.py").read_text(encoding="utf-8")
    _write(workdir, "src/invoice.py",
           invoice.replace("format_price(amount)", "format_price(amount, 'GBP')"))
    test = (workdir / "tests" / "test_pricing.py").read_text(encoding="utf-8")
    _write(workdir, "tests/test_pricing.py",
           re.sub(r"format_price\((\d+)\)", r'format_price(\1, "GBP")', test))


def _apply_refactor(workdir: Path) -> None:
    _write(workdir, "src/config.py", '''"""Read the app's key = value settings file."""

from __future__ import annotations


def _strip_comment(line: str) -> str:
    if " #" in line:
        line = line[:line.index(" #")]
    return line.strip()


def _split_setting(line: str, raw: str) -> tuple[str, str]:
    if "=" not in line:
        raise ValueError(f"not a key = value line: {raw!r}")
    key, value = line.split("=", 1)
    return key.strip().lower(), value.strip()


def parse_config(text: str) -> dict[str, str]:
    """Return the settings in text; a later key replaces an earlier one."""
    settings: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, value = _split_setting(_strip_comment(line), raw)
        settings[key] = value
    return settings
''')


def _careless_refactor(workdir: Path) -> None:
    _write(workdir, "src/config.py", '''"""Read the app's key = value settings file."""

from __future__ import annotations


def _is_setting(line: str) -> bool:
    line = line.strip()
    return bool(line) and not line.startswith("#")


def _parse_setting(line: str) -> tuple[str, str]:
    key, value = line.split("=")
    return key.strip(), value.strip()


def parse_config(text: str) -> dict[str, str]:
    """Return the settings in text."""
    return dict(_parse_setting(line) for line in text.splitlines()
                if _is_setting(line))
''')


_PAGING_HEAD = '''"""Paging helpers for long lists."""

from __future__ import annotations


def page_count(total_items: int, size: int) -> int:
    """How many pages of size it takes to show total_items."""
    return -(-total_items // size)
'''


def _apply_edge_case(workdir: Path) -> None:
    _write(workdir, "src/paging.py", _PAGING_HEAD + '''

def page(items: list, number: int, size: int) -> list:
    """The items on page number (from 1) of pages of size."""
    if number < 1 or size < 1:
        raise ValueError("number and size must be at least 1")
    start = (number - 1) * size
    return items[start:start + size]
''')


def _careless_edge_case(workdir: Path) -> None:
    _write(workdir, "src/paging.py", _PAGING_HEAD + '''

def page(items: list, number: int, size: int) -> list:
    """The items on page number of pages of size."""
    start = (number - 1) * size
    return items[start:start + size]
''')


# --- Four scenarios where careful process should beat careless change -------
# (issue #340). Each careless change passes the seed's own tests.

_MONEY_HEAD = '''"""Money helpers for the shop's price list."""

from __future__ import annotations
'''


def _apply_late_tidy(workdir: Path) -> None:
    _write(workdir, "src/money.py", _MONEY_HEAD + '''
from decimal import ROUND_HALF_UP, Decimal


def _clean(text: str) -> str:
    return text.strip().lstrip("£")


def parse_amount(text: str) -> float:
    """Read an amount of pounds, such as "12.34" or " £12.34 ", as a number."""
    return float(_clean(text))


def to_pence(text: str) -> int:
    """Read an amount of pounds as whole pence; half a penny rounds up."""
    pence = Decimal(_clean(text)) * 100
    return int(pence.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
''')


def _careless_late_tidy(workdir: Path) -> None:
    # The fix, then the requested tidy routes the amount back through a float.
    _write(workdir, "src/money.py", _MONEY_HEAD + '''

def parse_amount(text: str) -> float:
    """Read an amount of pounds, such as "12.34" or " £12.34 ", as a number."""
    return float(text.strip().lstrip("£"))


def to_pence(text: str) -> int:
    """Read an amount of pounds as whole pence; half a penny rounds up."""
    return int(parse_amount(text) * 100 + 0.5)
''')


_FMT_SEPARATED = '''"""How amounts of money are shown."""

from __future__ import annotations


def format_amount(pence: int) -> str:
    """Show pence as pounds, for example 123456 -> "£1,234.56"."""
    pounds, rest = divmod(pence, 100)
    return f"£{pounds:,}.{rest:02d}"
'''


def _apply_shared_helper(workdir: Path) -> None:
    _write(workdir, "src/fmt.py", _FMT_SEPARATED)
    export = (workdir / "src" / "export.py").read_text(encoding="utf-8")
    export = export.replace("from __future__ import annotations\n",
                            "from __future__ import annotations\n\nimport csv\nimport io\n")
    _write(workdir, "src/export.py", export.replace(
        '    return f"{name},{format_amount(pence)}"',
        '    out = io.StringIO()\n'
        '    csv.writer(out, lineterminator="").writerow([name, format_amount(pence)])\n'
        '    return out.getvalue()'))


def _careless_shared_helper(workdir: Path) -> None:
    _write(workdir, "src/fmt.py", _FMT_SEPARATED)
    test = (workdir / "tests" / "test_fmt.py").read_text(encoding="utf-8")
    _write(workdir, "tests/test_fmt.py", test + '''

def test_format_amount_separates_thousands():
    assert format_amount(123456) == "£1,234.56"
''')


_SHIPPING_COST = '''

UK_PRICES = {"small": 345, "medium": 595, "large": 1095}


def cost(weight_g: int, zone: str) -> int:
    """A parcel's price in whole pence; an EU price is the UK price plus a
    fifth, rounded up to the next 10 pence."""
    uk = UK_PRICES[band(weight_g)]
    if zone == "UK":
        return uk
    if zone == "EU":
        return -(-uk * 12 // 100) * 10
    raise ValueError(f"unknown zone {zone!r}")
'''


def _apply_resume_decision(workdir: Path) -> None:
    shipping = (workdir / "src" / "shipping.py").read_text(encoding="utf-8")
    _write(workdir, "src/shipping.py", shipping + _SHIPPING_COST)


def _careless_resume_decision(workdir: Path) -> None:
    shipping = (workdir / "src" / "shipping.py").read_text(encoding="utf-8")
    _write(workdir, "src/shipping.py", shipping + _SHIPPING_COST.replace(
        "        return -(-uk * 12 // 100) * 10",
        "        return round(uk * 1.2)"))


_DISCOUNT = '''

def discount(subtotal_pence: int, percent: int) -> int:
    """The amount after taking percent off, in whole pence; half a penny
    rounds up."""
    return (subtotal_pence * (100 - percent) * 2 + 100) // 200
'''


def _apply_second_change(workdir: Path) -> None:
    orders = (workdir / "src" / "orders.py").read_text(encoding="utf-8")
    _write(workdir, "src/orders.py", orders + _DISCOUNT)


def _careless_second_change(workdir: Path) -> None:
    orders = (workdir / "src" / "orders.py").read_text(encoding="utf-8")
    _write(workdir, "src/orders.py", orders + _DISCOUNT.replace(
        "    return (subtotal_pence * (100 - percent) * 2 + 100) // 200",
        "    return round(subtotal_pence * (100 - percent) / 100)"))


CARELESS_CHANGES = {
    "cmp-hidden-requirement": _careless_hidden_requirement,
    "cmp-call-sites": _careless_call_sites,
    "cmp-refactor": _careless_refactor,
    "cmp-edge-case": _careless_edge_case,
    "cmp-late-tidy": _careless_late_tidy,
    "cmp-shared-helper": _careless_shared_helper,
    "cmp-resume-decision": _careless_resume_decision,
    "cmp-second-change": _careless_second_change,
}

# The rule each hidden test checks, which the prompt must leave the
# session to find in the repository.
UNSTATED_RULE_WORDS = {
    "cmp-hidden-requirement": ("pence", "left over", "remainder", "first", "add up"),
    "cmp-refactor": ("comment", "lower", "duplicate", "=", "case"),
}


REFERENCE_SOLUTIONS = {
    "cmp-small-fix": _apply_small_fix,
    "cmp-feature": _apply_feature,
    "cmp-legacy": _apply_legacy,
    "cmp-risky": _apply_risky,
    "cmp-spike": _apply_spike,
    "cmp-resume": _apply_resume,
    "cmp-hidden-requirement": _apply_hidden_requirement,
    "cmp-call-sites": _apply_call_sites,
    "cmp-refactor": _apply_refactor,
    "cmp-edge-case": _apply_edge_case,
    "cmp-late-tidy": _apply_late_tidy,
    "cmp-shared-helper": _apply_shared_helper,
    "cmp-resume-decision": _apply_resume_decision,
    "cmp-second-change": _apply_second_change,
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_every_cmp_task_directory_is_listed():
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
def test_scenario_carries_the_continue_reply(task_id):
    """Every comparison scenario gives a session that stops to ask the
    same one reply, under every condition (CMP-3, the design's
    "Replies" section)."""
    data = _load_scenario(task_id)
    assert data["continue_reply"] == \
        "Go ahead with whichever option you recommend."


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


# ---------------------------------------------------------------------------
# cmp-risky: the hidden tests must measure what the prompt asks for.
# ---------------------------------------------------------------------------

def test_cmp_risky_prompt_names_the_function_and_the_negative_case():
    prompt = _load_scenario("cmp-risky")["prompt"]
    assert "total_with_service_charge" in prompt, (
        "cmp-risky's prompt does not name the function its hidden tests "
        "import, so a correct change under any other name would wrongly "
        "score zero"
    )
    assert re.search(r"negative", prompt, re.IGNORECASE), (
        "cmp-risky's prompt does not say what a negative total does, but "
        "its hidden tests check it"
    )


def test_cmp_risky_hidden_tests_pass_for_a_correct_change_with_a_different_helper_name(tmp_path):
    """The prompt names the one function its hidden tests must call. A
    correct change is still free to use its own private helpers under any
    name it likes - proving the hidden tests measure the named function's
    behaviour, not the rest of the file."""
    _require_python3()
    _prepare_seed("cmp-risky", tmp_path)
    _copy_hidden_tests("cmp-risky", tmp_path)
    (tmp_path / "src" / "billing_split.py").write_text(
        _RISKY_SOURCE_WITH_A_DIFFERENT_HELPER_NAME, encoding="utf-8",
    )

    result = _run_hidden_command("cmp-risky", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# cmp-spike: the hidden tests must not be satisfied by a near-miss, and must
# notice a change to the module the prompt says to leave alone.
# ---------------------------------------------------------------------------

def test_cmp_spike_hidden_tests_reject_a_near_miss_finding(tmp_path):
    _require_python3()
    _prepare_seed("cmp-spike", tmp_path)
    _copy_hidden_tests("cmp-spike", tmp_path)
    (tmp_path / "FINDINGS.md").write_text(_SPIKE_NEAR_MISS_FINDINGS, encoding="utf-8")

    result = _run_hidden_command("cmp-spike", tmp_path)
    assert result.returncode != 0, (
        "cmp-spike hidden tests passed on a near-miss finding:\n"
        + result.stdout + result.stderr
    )


def test_cmp_spike_hidden_tests_reject_a_changed_cache_module(tmp_path):
    _require_python3()
    _prepare_seed("cmp-spike", tmp_path)
    _copy_hidden_tests("cmp-spike", tmp_path)
    REFERENCE_SOLUTIONS["cmp-spike"](tmp_path)
    cache_path = tmp_path / "src" / "cache.py"
    cache_path.write_text(
        cache_path.read_text(encoding="utf-8") + "\n# a change the prompt never asked for\n",
        encoding="utf-8",
    )

    result = _run_hidden_command("cmp-spike", tmp_path)
    assert result.returncode != 0, (
        "cmp-spike hidden tests passed even though src/cache.py changed:\n"
        + result.stdout + result.stderr
    )


# ---------------------------------------------------------------------------
# cmp-resume: every condition needs the record its own framework keeps.
# ---------------------------------------------------------------------------

def test_cmp_resume_prompt_does_not_name_one_condition_s_record():
    prompt = _load_scenario("cmp-resume")["prompt"].lower()
    assert "notes.md" not in prompt, (
        "cmp-resume's prompt names one condition's own record file, but "
        "each condition now keeps a different one"
    )


@pytest.mark.parametrize("condition", sorted(CONDITION_OVERLAY_DIRS))
def test_cmp_resume_has_a_record_for_every_condition(condition):
    overlay_dir = _overlay_dir("cmp-resume", condition)
    assert overlay_dir.is_dir(), (
        f"cmp-resume has no {overlay_dir.name}/ overlay for the {condition} condition"
    )


def test_cmp_resume_bare_overlay_is_a_plain_notes_file():
    overlay_dir = _overlay_dir("cmp-resume", "bare")
    assert (overlay_dir / "NOTES.md").is_file()


def test_cmp_resume_compass_overlay_is_an_in_flight_issue():
    overlay_dir = _overlay_dir("cmp-resume", "compass")
    assert (overlay_dir / ".compass" / "current-task").is_file()
    manifests = list((overlay_dir / ".compass" / "work").rglob("manifest.yml"))
    assert manifests, "seed_compass has no manifest.yml under .compass/work/"


def test_cmp_resume_superpowers_overlay_is_a_plan():
    overlay_dir = _overlay_dir("cmp-resume", "superpowers")
    plans = list((overlay_dir / "docs" / "superpowers" / "plans").glob("*.md"))
    assert plans, "seed_superpowers has no record under docs/superpowers/plans/"


def test_cmp_resume_spec_kit_overlay_is_a_spec_and_its_checklist():
    overlay_dir = _overlay_dir("cmp-resume", "spec-kit")
    specs = list((overlay_dir / "specs").glob("*/spec.md"))
    checklists = list((overlay_dir / "specs").glob("*/tasks.md"))
    assert specs, "seed_spec_kit has no spec.md under specs/"
    assert checklists, "seed_spec_kit has no checklist under specs/"


@pytest.mark.parametrize("condition", sorted(CONDITION_OVERLAY_DIRS))
def test_cmp_resume_every_record_says_what_is_done_and_what_is_next(condition):
    overlay_dir = _overlay_dir("cmp-resume", condition)
    text = _overlay_markdown_text(overlay_dir).lower()
    assert "parse_scores" in text, f"{overlay_dir.name} does not say parse_scores is done"
    assert "average" in text and "highest" in text and "lowest" in text, (
        f"{overlay_dir.name} does not describe what summarize must return"
    )


def test_cmp_resume_superpowers_overlay_uses_its_own_heading_form():
    """Superpowers' plan-writing skill headers each unit of work its own
    way, and says how a plan gets implemented in its own words - a session
    under that framework must read those words, not Compass's paraphrase
    of them."""
    overlay_dir = _overlay_dir("cmp-resume", "superpowers")
    plan_path = next((overlay_dir / "docs" / "superpowers" / "plans").glob("*.md"))
    text = plan_path.read_text(encoding="utf-8")
    assert "### Task 1:" in text and "### Task 2:" in text, (
        f"{plan_path.name} does not use Superpowers' own heading form for a unit of work"
    )
    assert "task-by-task" in text, (
        f"{plan_path.name} does not use Superpowers' own wording for how it is implemented"
    )


def test_cmp_resume_spec_kit_overlay_uses_its_own_heading_form():
    """Spec Kit's own checklist template opens with a title naming what
    the file holds - a session under that framework must read that
    title, not Compass's paraphrase of it."""
    overlay_dir = _overlay_dir("cmp-resume", "spec-kit")
    tasks_path = next((overlay_dir / "specs").glob("*/tasks.md"))
    text = tasks_path.read_text(encoding="utf-8")
    assert text.startswith("# Tasks:"), (
        f"{tasks_path.name} does not open with Spec Kit's own title form"
    )


# ---------------------------------------------------------------------------
# cmp-resume, round 4: Spec Kit's own first step, equal records, and the
# review's other follow-ups against this subtask's files.
# ---------------------------------------------------------------------------

# The three hidden tests for cmp-resume, by name - no record may quote or
# name one, or a session reading it would be told what is graded.
HIDDEN_RESUME_TEST_NAMES = (
    "test_summarize_reports_average_highest_and_lowest",
    "test_a_tie_goes_to_whichever_student_comes_first",
    "test_empty_scores_raises_value_error",
)


def _spec_kit_feature_dir(overlay_dir: Path) -> Path:
    feature_json = json.loads((overlay_dir / ".specify" / "feature.json").read_text(encoding="utf-8"))
    return overlay_dir / feature_json["feature_directory"]


def test_cmp_resume_spec_kit_overlay_has_what_its_own_first_step_needs():
    """Spec Kit's own check-prerequisites script, the first step of
    speckit-implement, reads the feature-tracking file for the feature
    directory, then needs a plan document there always, and a checklist
    there when one is asked for. This checks every file that script
    reads is present, the fallback the brief allows when a test cannot
    reach a real, pinned Spec Kit offline."""
    overlay_dir = _overlay_dir("cmp-resume", "spec-kit")
    feature_json_path = overlay_dir / ".specify" / "feature.json"
    assert feature_json_path.is_file(), "seed_spec_kit has no .specify/feature.json"
    feature_dir = _spec_kit_feature_dir(overlay_dir)
    assert feature_dir.is_dir(), (
        f"{feature_json_path} names a feature_directory that does not exist under seed_spec_kit"
    )
    for name in ("spec.md", "plan.md", "tasks.md"):
        assert (feature_dir / name).is_file(), (
            f"seed_spec_kit's feature directory has no {name}, which "
            f"check-prerequisites.sh requires"
        )


def test_cmp_resume_spec_kit_overlay_has_story_labels_and_paths():
    tasks_path = _spec_kit_feature_dir(_overlay_dir("cmp-resume", "spec-kit")) / "tasks.md"
    text = tasks_path.read_text(encoding="utf-8")
    assert "[US1]" in text, "tasks.md has no story label, which its own template asks for"
    assert "src/grades.py" in text and "tests/test_grades.py" in text, (
        "tasks.md does not give exact paths, which its own template asks for"
    )


def test_cmp_resume_superpowers_overlay_names_files_with_their_directories():
    plan_path = next((_overlay_dir("cmp-resume", "superpowers") / "docs" / "superpowers" / "plans").glob("*.md"))
    text = plan_path.read_text(encoding="utf-8")
    assert "src/grades.py" in text and "tests/test_grades.py" in text, (
        f"{plan_path.name} does not give exact paths"
    )
    for match in re.finditer(r"[\w./]*\bgrades\.py\b", text):
        assert match.group(0) == "src/grades.py", (
            f"{plan_path.name} names a file without its directory: {match.group(0)!r}"
        )
    for match in re.finditer(r"[\w./]*\btest_grades\.py\b", text):
        assert match.group(0) == "tests/test_grades.py", (
            f"{plan_path.name} names a file without its directory: {match.group(0)!r}"
        )


def test_cmp_resume_superpowers_overlay_does_not_quote_a_hidden_test():
    plan_path = next((_overlay_dir("cmp-resume", "superpowers") / "docs" / "superpowers" / "plans").glob("*.md"))
    text = plan_path.read_text(encoding="utf-8")
    for name in HIDDEN_RESUME_TEST_NAMES:
        assert name not in text, f"{plan_path.name} quotes the hidden test {name}"


def test_cmp_resume_compass_overlay_does_not_name_a_hidden_test():
    overlay_dir = _overlay_dir("cmp-resume", "compass")
    text = _overlay_markdown_text(overlay_dir)
    for name in HIDDEN_RESUME_TEST_NAMES:
        assert name not in text, f"the compass record names the hidden test {name}"


def test_cmp_resume_compass_overlay_devlog_names_the_return_keys():
    """Every hidden test reads result["average"], result["highest"] or
    result["lowest"] - the devlog must say summarize returns a dict with
    those three keys, the same as the bare, Superpowers and Spec Kit
    records already do, not just describe the value in words."""
    devlog_path = (
        _overlay_dir("cmp-resume", "compass") / ".compass" / "work"
        / "grade-summary" / "devlog.md"
    )
    text = devlog_path.read_text(encoding="utf-8")
    assert "dict" in text.lower(), "devlog.md does not say summarize returns a dict"
    for key in ('"average"', '"highest"', '"lowest"'):
        assert key in text, f"devlog.md does not name the {key} key"


def test_cmp_resume_compass_overlay_manifest_has_gates_and_a_traceability_id():
    manifest_path = next(
        (_overlay_dir("cmp-resume", "compass") / ".compass" / "work").rglob("manifest.yml")
    )
    data = load_yaml(str(manifest_path))
    assert data.get("gates"), (
        "seed_compass's manifest has no gates - compass check reports "
        '"no gates in manifest.yml - has the route been evaluated?"'
    )
    scenario_id = data["scenarios"][0]["id"]
    assert scenario_id.startswith("TRC-"), (
        f"seed_compass's manifest scenario id {scenario_id!r} is not the "
        f"TRC- form Compass now issues"
    )


_SPIKE_TIME_TIME_FINDINGS = (
    "Yes - store the expiry timestamp per key with time.time() when "
    "set() is called, and check it in get(), dropping the entry once "
    "that timestamp has passed.\n"
)


def test_cmp_spike_hidden_tests_accept_a_finding_naming_only_time_time(tmp_path):
    """A finding that names time.time(), a correct approach, must pass on
    its own technical merit - not only because it happens to repeat the
    prompt's own words "standard library"."""
    _require_python3()
    _prepare_seed("cmp-spike", tmp_path)
    _copy_hidden_tests("cmp-spike", tmp_path)
    (tmp_path / "FINDINGS.md").write_text(_SPIKE_TIME_TIME_FINDINGS, encoding="utf-8")

    result = _run_hidden_command("cmp-spike", tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# The careless change: passes what the session can see, fails what it cannot.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_id", sorted(CARELESS_CHANGES))
def test_a_careless_change_passes_the_seed_tests_and_fails_the_hidden_ones(
        task_id, tmp_path):
    _require_python3()
    _prepare_seed(task_id, tmp_path)
    CARELESS_CHANGES[task_id](tmp_path)
    own = _run(OWN_TEST_COMMAND, tmp_path)
    assert own.returncode == 0, (
        f"{task_id}: the careless change fails the seed's own tests, so a "
        "session would see its mistake:\n" + own.stdout + own.stderr)
    _copy_hidden_tests(task_id, tmp_path)
    hidden = _run_hidden_command(task_id, tmp_path)
    # Exit 1 means tests ran and failed; 2 or 5 would be a collection
    # error or no tests, which proves nothing about the change.
    assert hidden.returncode == 1, (
        f"{task_id}: the hidden tests do not fail cleanly on a careless change:\n"
        + hidden.stdout + hidden.stderr)


@pytest.mark.parametrize("task_id", sorted(UNSTATED_RULE_WORDS))
def test_the_prompt_leaves_the_rule_to_be_found(task_id):
    prompt = _load_scenario(task_id)["prompt"].lower()
    stated = [w for w in UNSTATED_RULE_WORDS[task_id] if w in prompt]
    assert not stated, f"{task_id}'s prompt states the rule: {stated}"
