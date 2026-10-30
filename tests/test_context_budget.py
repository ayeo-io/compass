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

from size_targets import OverTarget, warn_if_over

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
    "write for a person": "**Write for a person in the spirit of ASD-STE100.**",
    "approvals": "**Approvals.**",
}

# The four rules for sign-off, staging, lint fixes and edge cases (issue
# `contract-handoff-and-staging-rules`). The sign-off rule is the
# "Approvals." paragraph, so its pin is that paragraph's request to the
# person. Compared with whitespace collapsed, because the contract wraps its
# lines inside a phrase.
NEW_RULES = {
    "signoff request": ("ask the person to type `/compass:approve` or "
                        "`/compass:reject`, and stop."),
    "staging heading": "**Commit only what you mean to.**",
    "staging by path": "Stage each file by its path",
    "staging no compass": "never `.compass/`",
    "lint fix": "A lint fix never weakens an assertion",
    "edge cases heading": "**Settle edge cases before scenarios**",
}

# Raised from 2,250 by the one line that asks the agent to record friction it
# observes (issue `agent-recorded-friction`, which allows 40 resident words):
# the agent meets that friction mid-run, so the line must be resident.
# Raised again, to 2,700, by the approval rule (issue `approve-inside-claude-code`,
# ADR-068 and ADR-069): the agent must know, before it acts, that it records an
# approval only under a delegation and otherwise asks, so the rule must be
# resident. Decided by compass:architect under jed72's overnight delegation.
#
# Raised to 2,750 by the staging, lint-fix and edge-case rules (issue
# `contract-handoff-and-staging-rules`), net of the passages tightened to
# make room: 2,704 characters measured, rounded up to the next 50. The
# sign-off rule is the approval rule above, so it adds nothing. These rules
# apply at moments a session cannot predict, in any stage including a quick
# fix, which reads only its own command and skill, so the rules must be
# resident in the contract.
#
# Since issue `size-caps-as-targets` the number is a target, not a limit:
# a contract over it passes and pytest warns, so the growth shows in every
# run without blocking a rule the owner agreed to.
#
# Moved to 2,900 by the ASD-STE100 writing rule (issue `ste100-writing-rule`):
# 2,873 characters measured, rounded up to the next 50. Every message a
# session writes to a person depends on it, so it must be resident.
CONTRACT_TARGET = 2900

# Set from the rewrite of 2026-10-04 (2,581, 1,476, 1,436 and 1,216
# characters at 80 columns), with a little room; before it, 2,805, 1,643,
# 1,539 and 1,285. The rest of each is the usage line and option help, which
# the README quotes and tests read flags from.
# quick-fix start rose by about 190 characters on 2026-10-06 for
# --raised-by and --found-at (lineage): two options cannot fit in the 21
# characters that were left, and hiding them would leave a session no way
# to learn them from --help.
# quick-fix finish rose by about 155 characters on 2026-10-14 for
# --release-note (ADR-065): a landing refuses a quick fix with no release
# line, so the flag must be learnable from --help, and 16 characters were left.
# quick-fix start rose by 100 characters on 2026-10-30 for
# --expected-acceptance (strategy `S17`): a docs or config quick fix must say it
# is out of the four-layer acceptance strategy's scope, and the option and its
# shortest help need about 80 characters.
HELP_BUDGETS = {
    ("quick-fix", "start"): 2900,
    ("quick-fix", "finish"): 1650,
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
    ("quick-fix", "finish"): {"-m", "--message", "--no-commit", "--issue",
                              "--release-note"} | COMMON,
    ("tdd-red",): {"--scenario", "--issue", "--verified-by"} | COMMON,
    ("tdd-green",): {"--scenario", "--issue", "--verified-by"} | COMMON,
}


RULES.update(NEW_RULES)


def missing_rules(text):
    # Whitespace collapsed, because the contract wraps lines inside a phrase.
    text = " ".join(text.split())
    return [name for name, phrase in RULES.items() if phrase not in text]


def test_tc_1_the_contract_keeps_every_rule_within_its_budget():
    text = CONTRACT.read_text(encoding="utf-8")
    assert missing_rules(text) == []
    warn_if_over("compass-contract.md", len(text), CONTRACT_TARGET, "characters")


def test_tc_1_deleting_any_rule_is_caught():
    text = CONTRACT.read_text(encoding="utf-8")
    flat = " ".join(text.split())
    for name, phrase in RULES.items():
        assert name in missing_rules(flat.replace(phrase, "")), name


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


# --- CHS: the sign-off, staging, lint and edge-case rules -----------------------

def _flat(text):
    return " ".join(text.split())


def _contract_flat():
    return _flat(CONTRACT.read_text(encoding="utf-8"))


def test_contract_states_signoff_handoff():
    text = _contract_flat()
    assert "**Approvals.**" in text
    assert "Approve only under a delegation naming you" in text
    assert "run `compass evidence request`" in text
    assert ("ask the person to type `/compass:approve` or "
            "`/compass:reject`, and stop.") in text
    # The superseded handoff, a command printed for the person's terminal,
    # must not come back beside the typed approval.
    assert "for their own terminal" not in text
    assert "no `!` prefix" not in text


def test_contract_states_staging_rule():
    text = _contract_flat()
    assert "**Commit only what you mean to.**" in text
    assert "Stage each file by its path" in text
    assert "never `.compass/`" in text
    assert "check the staged list and commit authors" in text
    assert ("If something is staged by mistake, say so and stop; "
            "do not retry a refused unstage.") in text


def test_contract_states_lint_fix_rule():
    text = _contract_flat()
    assert "A lint fix never weakens an assertion" in text
    assert "re-run affected tests" in text


def test_contract_states_id_and_header_rule():
    """The contract keeps the heading and names the skill that holds the
    rule (a pointer, because the full text put the resident words over the
    900-word ceiling). It names the skill, not a path: the contract is loaded
    in every project, where the plugin's `skills/` folder is not on disk."""
    text = _contract_flat()
    assert "**Settle edge cases before scenarios**" in text
    assert "(`bdd-specification` skill)" in text
    assert "skills/bdd-specification/SKILL.md" not in text
    skill = _flat((ROOT / "skills" / "bdd-specification" / "SKILL.md")
                  .read_text(encoding="utf-8"))
    assert "id or header field" in skill
    assert "missing, empty and whitespace cases" in skill
    assert "Reproduce a reported bug on current code" in skill


def test_each_rule_phrase_pin_can_fail():
    """Each rule has a pin in RULES, and removing the phrase is reported by
    name."""
    text = CONTRACT.read_text(encoding="utf-8")
    assert missing_rules(text) == []
    for name in NEW_RULES:
        assert name in RULES, name
    for name in NEW_RULES:
        assert name not in missing_rules(text), name
        broken = _flat(text).replace(NEW_RULES[name], "")
        assert name in missing_rules(broken), name


def _budget_comment():
    source = Path(__file__).read_text(encoding="utf-8")
    start = source.index("CONTRACT_TARGET = ")
    return source[:start].rsplit("\n\n", 1)[-1]


def test_contract_budget_comment_states_reason():
    comment = " ".join(_budget_comment().replace("#", " ").split())
    assert "cannot predict" in comment
    assert "any stage" in comment and "quick fix" in comment
    assert "resident" in comment


def test_contract_target_warns_and_does_not_fail():
    text = CONTRACT.read_text(encoding="utf-8")
    longer = text + "x" * (CONTRACT_TARGET - len(text) + 1)
    with pytest.warns(OverTarget, match=f"{CONTRACT_TARGET + 1} characters"):
        warn_if_over("compass-contract.md", len(longer), CONTRACT_TARGET,
                     "characters")


def test_rule_four_pointer_keeps_heading():
    text = _contract_flat()
    assert "**Settle edge cases before scenarios**" in text
    assert "(`bdd-specification` skill)" in text
    body = (ROOT / "skills" / "bdd-specification" / "SKILL.md").read_text(
        encoding="utf-8")
    assert "Reproduce a reported bug on current code" in _flat(body)
    assert len(body.splitlines()) <= 200


def test_trc_026():
    """The `language` line is added by the session-start hook, so the shipped
    contract does not grow (issue `language-key-and-us-english`)."""
    text = CONTRACT.read_text(encoding="utf-8")
    assert len(text) <= 2900
    assert CONTRACT_TARGET == 2900
    assert "Write all prose in" not in text
    warn_if_over("compass-contract.md", len(text), CONTRACT_TARGET, "characters")
