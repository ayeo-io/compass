"""The quick-fix command teaches the two verbs, not the hand-run steps the
verbs now carry out.

Before this issue, the command walked an agent through five hand-run
stages - `compass init`, a manifest written from a template, `compass
approach evaluate`, `compass tdd-red`/`tdd-green`, `compass check`, `compass
evidence add`, `compass gate pass` three times, a hand-written devlog line,
`compass ship-commit` - each one a model call. `compass quick-fix start` and
`compass quick-fix finish` now do the mechanical half of that in two calls;
this file pins that the one prose file that teaches them describes the two
verbs, names no template to read, and stays under a word ceiling. The command
once had a skill of the same name beside it. The Skill tool resolved the name
to the command, so the skill never loaded; its rules now live in the command
(issue quick-fix-skill-not-hidden).

Scenario id: QFO-6, in acceptance-criteria.md of issue quick-fix-overhead.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / "commands" / "quick-fix.md"
SKILL = ROOT / "skills" / "quick-fix" / "SKILL.md"

#: The old reading path (one command and one skill) measured 11,203 words
#: before the light path was inlined; the one file that carries it now stays
#: far under that.
WORD_CEILING = 1300


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _words(path: Path) -> int:
    return len(_text(path).split())


def test_qfo_6_the_command_exists_and_the_skill_does_not():
    assert COMMAND.is_file(), "commands/quick-fix.md is missing"
    assert not SKILL.exists(), (
        "skills/quick-fix/SKILL.md is back: the command of the same name hides "
        "it, so its text never reaches a session")


def test_qfo_6_the_command_names_start_with_its_fixed_flags():
    """`quick-fix start`'s flags are fixed by the design (ADR-099); the
    command must teach the exact set, not a paraphrase. The scenarios and the
    tests are no longer flags: `finish` reads them from the issue's
    acceptance-criteria.md and from git."""
    text = _text(COMMAND)
    assert "compass quick-fix start" in text
    for flag in ("--intent", "--request", "--requester", "--labels", "--risk"):
        assert flag in text, f"commands/quick-fix.md does not name {flag}"
    for flag in ("--familiarity", "--size", "--goal", "--scenario", "--test"):
        assert flag not in text, f"commands/quick-fix.md still names {flag}"


def test_qfo_6_the_command_names_finish_with_its_fixed_flags():
    text = _text(COMMAND)
    assert "compass quick-fix finish" in text
    assert "-m " in text or '-m "' in text, (
        "commands/quick-fix.md does not name finish's -m flag")


def test_qfo_6_the_command_names_no_red_or_green_step():
    """`finish` proves the red on a copy of the base commit and records the
    green (ADR-099 decision 2), so the command names neither verb."""
    text = _text(COMMAND)
    assert "compass tdd-red" not in text
    assert "compass tdd-green" not in text


def test_qfo_6_no_template_is_named_to_read():
    assert "templates/" not in _text(COMMAND), (
        "commands/quick-fix.md still names a template to read")


def test_qfo_6_no_hand_run_gate_or_evidence_step():
    """The verbs pass the gates and record the evidence internally now; an
    agent following this file must never be told to run either by hand."""
    text = _text(COMMAND)
    assert "compass gate pass" not in text, (
        "commands/quick-fix.md still instructs a hand-run `compass gate pass`")
    assert "compass evidence add" not in text, (
        "commands/quick-fix.md still instructs a hand-run `compass evidence add`")
    assert "compass scenario add" not in text and "compass changed-file add" not in text


def test_qfo_6_the_command_has_no_wrong_path_list():
    """On the path (ADR-092) no size is wrong for the two calls, so the list
    of cases where this command was the wrong one went. The description says
    the issue takes two commands, and `finish` names what a person still owes
    on its `next:` line."""
    text = _text(COMMAND)
    assert "When this command is the wrong one" not in text
    flat = " ".join(text.split())
    assert "Start, change and finish an issue in two commands" in flat
    assert "its `next:` line asks for a person's approval, stop" in flat


def test_qfo_6_the_command_keeps_the_reassess_rule():
    text = _text(COMMAND)
    assert "Stop and re-assess" in text or "stop and re-assess" in text


def test_qfo_6_the_command_keeps_the_directory_announcement_rule():
    """`compass init` and a first `docs/compass/` write both print the line
    the verb wrote it; the command must tell the agent to report that line,
    not to announce a directory itself by hand."""
    text = _text(COMMAND)
    assert ".compass/" in text and "docs/compass/" in text
    assert "report" in text.lower()


def test_qfo_6_the_command_is_under_the_word_ceiling():
    words = _words(COMMAND)
    assert words < WORD_CEILING, (
        f"commands/quick-fix.md reads {words} words, over the "
        f"{WORD_CEILING}-word ceiling")


def test_qfo_6_finish_is_taught_with_the_test_command_and_it_commits_after_approval():
    """`finish` records the red and the green itself, so it takes the test
    command. It commits once a person has approved (ADR-099 decision 7), so
    the command shows no `--no-commit` and no separate green step."""
    text = _text(COMMAND)
    finish_lines = [l.strip() for l in text.splitlines()
                    if l.strip().startswith("compass quick-fix finish")]
    assert finish_lines, "commands/quick-fix.md shows no finish command line"
    assert all("-- <test command>" in l and "--no-commit" not in l
               for l in finish_lines), finish_lines
    assert "It commits once a person has approved" in " ".join(text.split())
    assert "compass tdd-green --scenario" not in text, (
        "a separate green step before finish records a green over the "
        "untraced files")


def test_qfo_6_the_command_names_the_labels_and_the_risk_that_owe_an_approval():
    """An agent that guesses a label spends a call on the refusal. Only the
    four labels and critical risk need a flag on `start` (ADR-099 decision 5)."""
    text = _text(COMMAND)
    for value in ("auth", "payments", "personal-data", "migrations", "critical"):
        assert f"`{value}`" in text or f"{value} - " in text, (
            f"commands/quick-fix.md omits {value}")


def test_qfo_6_assess_carries_the_start_and_finish_commands():
    """`/compass:assess` is the entry point for every request, so it carries
    both commands and a session does not load `/compass:quick-fix` as well."""
    text = _text(ROOT / "commands" / "assess.md")
    assert "compass quick-fix start" in text
    assert "compass quick-fix finish" in text


def _skill_names() -> dict[str, str]:
    """Each skill's `name:` from its frontmatter, keyed by its directory."""
    names = {}
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        for line in _text(path).splitlines():
            if line.startswith("name:"):
                names[path.parent.name] = line.split(":", 1)[1].strip().strip("\"'")
                break
    return names


def test_qfs_176_no_skill_shares_a_command_name():
    """The Skill tool resolves `compass:quick-fix` to the command, so a skill
    of the same name is never loaded and its text never reaches a session. In
    86 recorded Skill calls the command loaded 83 times and the skill never."""
    commands = {p.stem for p in (ROOT / "commands").glob("*.md")}
    shadowed = sorted(f"skills/{directory}/SKILL.md"
                      for directory, name in _skill_names().items()
                      if directory in commands or name in commands)
    assert not shadowed, (
        f"a skill shares its name with a command, so the command hides it: "
        f"{shadowed}")


#: Each rule the skill held, with the file that holds it now and a phrase it
#: must carry. The command is under 300 words (ADR-099): the session no longer scores
#: risk, familiarity or size, so the rubric holds those rules, and the
#: test-first rules are in the `tdd-discipline` skill.
RULES = Path("approaches") / "rubric.md"
TDD = Path("skills") / "tdd-discipline" / "SKILL.md"
NO_RED = Path("skills") / "tdd-discipline" / "no-natural-red.md"
RULES_NOW_HELD_ELSEWHERE = {
    "an unjustified value is worse than a question": (RULES, "an unjustified value"),
    "risk is consequence, never effort": (Path("skills/adaptive-routing/SKILL.md"),
                                          "never effort"),
    "risk: trivial test": (RULES, "instantly reversible"),
    "risk: contained test": (RULES, "recoverable without incident"),
    "risk: cross-cutting test": (RULES, "ecovery needs coordination"),
    "risk: critical test": (RULES, "cannot be cleanly rolled back"),
    "familiarity: greenfield test": (RULES, "Net-new"),
    "familiarity: brownfield-mapped test": (RULES, "trivially readable"),
    "size: atomic test": (RULES, "< ~30 min"),
    "size: small test": (RULES, "known solution pattern"),
    "size: medium and above test": (RULES, "design decisions"),
    "size: estimate up when unsure": (RULES, "estimates *up*"),
    # The rule that an intent.md or positioning.md pulls the approach up went in
    # 9.0.0: no command reads which documents an issue has on disk (ADR-091).
    "goal: exploration is a spike": (RULES, "goal: exploration"),
    "the guardrail is tested before it lands": (Path("approaches/path.md"),
                                                "tested before it lands"),
    "red: fail for the right reason": (TDD, "right reason"),
    "green: the smallest correct change": (TDD, "smallest *correct*"),
    "refactor: a changed test means back to red": (TDD, "going back to red"),
    "a sanctioned red is not an exemption from red": (NO_RED, "not an exemption"),
    # The older kinds of proof (regression, e2e, typecheck, live) became the kinds of a
    # declared acceptance: `validation` and `refactor`.
    "no natural failing test: the declared acceptance kinds": (
        NO_RED, "compass acceptance start --kind validation"),
}

#: Rules that ADR-099 dropped with the command's long form. The `tdd-discipline`
#: skill holds the first two and its `no-natural-red.md` the third; the test
#: below reads every command, skill and approach file for each phrase.
RULES_NO_FILE_CARRIES = {
    "familiarity: brownfield-unmapped does not stop a quick fix":
        "pin with a test what the code does now",
    "a light approach adapts surface, never whether a test exists":
        "never whether a test exists",
    "no natural failing test: use a guard that can fail": "guard that can fail",
}


def test_qfs_176_every_rule_of_the_skill_is_held_by_the_file_that_teaches_it_now():
    """The command no longer carries the rules of the quick-fix skill; the
    file named for each rule must still carry its phrase."""
    missing = sorted(rule for rule, (path, phrase) in RULES_NOW_HELD_ELSEWHERE.items()
                     if phrase not in " ".join(_text(ROOT / path).split()))
    assert not missing, f"these rules are in no file that teaches them: {missing}"


def test_qfs_176_every_other_rule_of_the_skill_is_still_taught_somewhere():
    text = " ".join(" ".join(_text(p).split()) for p in sorted(
        list((ROOT / "commands").glob("*.md")) + list((ROOT / "skills").glob("**/*.md"))
        + list((ROOT / "approaches").glob("*.md"))))
    missing = sorted(rule for rule, phrase in RULES_NO_FILE_CARRIES.items()
                     if phrase not in text)
    assert not missing, f"no command, skill or approach file carries: {missing}"


def test_qfs_176_the_command_does_not_promise_a_skill_load():
    """The old description, `Load with /compass:quick-fix`, described a load
    that does not happen. No file may point a session at a quick-fix skill."""
    stale = []
    for path in sorted(ROOT.glob("skills/**/*.md")) + sorted(
            ROOT.glob("commands/*.md")) + sorted(ROOT.glob("approaches/*.md")):
        for n, line in enumerate(_text(path).splitlines(), 1):
            if "`quick-fix` skill" in line or "quick-fix skill" in line:
                stale.append(f"{path.relative_to(ROOT)}:{n}")
    assert not stale, f"these lines name a quick-fix skill that is gone: {stale}"


def test_qfo_6_assess_carries_the_whole_quick_fix_recipe():
    """A session opens `/compass:assess` first. With the two commands and the
    labels there, it does not spend a call loading `/compass:quick-fix` as
    well."""
    text = _text(ROOT / "commands" / "assess.md")
    assert "compass tdd-red" not in text
    finish = [l for l in text.splitlines()
              if l.strip().startswith("compass quick-fix finish")]
    assert finish and all("--no-commit" not in l and "-- <test command>" in l
                          for l in finish), finish
    for value in ("auth", "payments", "personal-data", "migrations", "critical"):
        assert value in text, f"commands/assess.md omits {value}"
