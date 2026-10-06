"""What a quick fix adds to the model's context has a budget.

In the 4 October comparison run a tidy-up cost Compass 2.3 times the tokens
of no framework for no gain. The session-start contract and the help text
sessions ask for are read again on every later request, so each is held to
a size here, without losing a rule or an option (#387).

Scenario ids: TC-1 and TC-2 (issue `trim-quick-fix-context`).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "compass-contract.md"

# One phrase from each rule. Several are pinned elsewhere word for word
# (tests/invisible/test_invisible_triggering.py, tests/test_contract_facts.py).
RULES = {
    "assess first": "**Assess before you change anything.**",
    "never skip": "**Never skip assessment.**",
    "trigger on intent": "**Trigger on intent, not on the command.**",
    "guardrails hard": "**Guardrails are hard. Strategies are soft.**",
    "guardrail 1": "1. Every change lands with a passing test that covers it.",
    "guardrail 2": "2. Acceptance criteria exist before the code.",
    "guardrail 3": "3. Code traces to a criterion and a reason.",
    "guardrail 4": "4. Evidence is a recorded command output",
    "guardrail 5": "5. A human approves anything irreversible.",
    "evidence": "**Evidence, not assertion.**",
    "use the CLI": "Use the CLI:",
    "five guardrails": "Five guardrails:",
    "on disk": "**If it is not on disk, it did not happen.**",
    "stages": "**Stages, in order**",
    "verify stage": "7. verify",
    "where to look": "`compass <verb> --help`",
    "write for no context": "**Write for someone with no context.**",
}

CONTRACT_BUDGET = 2250

# Set from the rewrite of 2026-10-04 (2,581, 1,476, 1,436 and 1,216
# characters at 80 columns), with a little room; before it, 2,805, 1,643,
# 1,539 and 1,285. The rest of each is the usage line and option help, which
# the README quotes and tests read flags from.
# quick-fix start rose by about 190 characters on 2026-10-06 for
# --raised-by and --found-at (lineage): two options cannot fit in the 21
# characters that were left, and hiding them would leave a session no way
# to learn them from --help.
HELP_BUDGETS = {
    ("quick-fix", "start"): 2800,
    ("quick-fix", "finish"): 1500,
    ("tdd-red",): 1450,
    ("tdd-green",): 1250,
}

# The output options every verb takes.
COMMON = {"-h", "--help", "--quiet", "--summary", "--verbose", "--json",
          "--evidence-out"}

# Every option each verb accepted before the trim; none may be lost.
OPTIONS = {
    ("quick-fix", "start"): {"--risk", "--familiarity", "--size", "--goal",
                             "--role", "--intent", "--scenario",
                             "--scenario-id", "--test", "--labels"} | COMMON,
    ("quick-fix", "finish"): {"-m", "--message", "--no-commit", "--issue"}
                             | COMMON,
    ("tdd-red",): {"--scenario", "--issue", "--verified-by"} | COMMON,
    ("tdd-green",): {"--scenario", "--issue", "--verified-by"} | COMMON,
}


def missing_rules(text):
    return [name for name, phrase in RULES.items() if phrase not in text]


def test_tc_1_the_contract_keeps_every_rule_within_its_budget():
    text = CONTRACT.read_text(encoding="utf-8")
    assert missing_rules(text) == []
    assert len(text) <= CONTRACT_BUDGET, len(text)


def test_tc_1_deleting_any_rule_is_caught():
    text = CONTRACT.read_text(encoding="utf-8")
    for name, phrase in RULES.items():
        assert name in missing_rules(text.replace(phrase, "")), name


def _help(verb):
    env = {**os.environ, "COLUMNS": "80"}
    return subprocess.run([sys.executable, str(ROOT / "cli" / "compass"),
                           *verb, "--help"], capture_output=True, text=True,
                          env=env, check=True).stdout


@pytest.mark.parametrize("verb", sorted(HELP_BUDGETS))
def test_tc_2_help_keeps_every_option_within_its_budget(verb):
    text = _help(verb)
    # Every option named on an option line, in each of its spellings.
    options = {o for line in text.splitlines() if re.match(r"\s{2,}-", line)
               for o in re.findall(r"(?<![\w-])(--?[a-z][\w-]*)", line)}
    assert OPTIONS[verb] <= options, OPTIONS[verb] - options
    assert len(text) <= HELP_BUDGETS[verb], len(text)


# --- TC-3: the settled-decisions listing --------------------------------------

def test_tc_3_the_settled_decisions_listing_stays_within_its_budget(tmp_path):
    """`quick-fix start` prints the newest ledger entries, which the session
    then reads on every later request; a long decision must not make that
    listing long. Every line still names its entry, so the session can open
    the one that touches its change."""
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import decisions
    from test_quick_fix_shows_settled_decisions import _entry
    for day in range(1, 10):
        _entry(tmp_path, f"2026-10-0{day}", f"rule-{day}",
               "Money " + "rounds half up and never to even " * 40 + "today.")
    lines = decisions.settled(str(tmp_path))
    assert all(len(line) <= decisions.LINE_BUDGET for line in lines), lines
    assert len("\n".join(lines)) <= decisions.LISTING_BUDGET, lines
    for day in range(5, 10):
        assert any(line.startswith(f"rule-{day}:") for line in lines), lines
