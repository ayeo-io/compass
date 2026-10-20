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
    """`quick-fix start`'s flags are fixed by the design (subtask-1); the
    command must teach the exact set, not a paraphrase."""
    text = _text(COMMAND)
    assert "compass quick-fix start" in text
    for flag in ("--risk", "--familiarity", "--size", "--goal", "--role",
                 "--intent", "--scenario", "--scenario-id", "--test"):
        assert flag in text, f"commands/quick-fix.md does not name {flag}"


def test_qfo_6_the_command_names_finish_with_its_fixed_flags():
    text = _text(COMMAND)
    assert "compass quick-fix finish" in text
    assert "-m " in text or '-m "' in text, (
        "commands/quick-fix.md does not name finish's -m flag")


def test_qfo_6_the_command_names_the_red_and_the_green():
    text = _text(COMMAND)
    assert "compass tdd-red" in text
    assert "compass tdd-green" in text


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


def test_qfo_6_the_command_keeps_the_wrong_path_list():
    text = _text(COMMAND)
    assert "When this command is the wrong one" in text


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


def test_qfo_6_finish_is_taught_with_the_test_command_and_no_commit():
    """`finish` records the green itself, so it takes the test command, and
    it commits only when the user asked for a commit."""
    text = _text(COMMAND)
    finish_lines = [l for l in text.splitlines()
                    if l.startswith("compass quick-fix finish")]
    assert finish_lines, "commands/quick-fix.md shows no finish command line"
    assert all("-- <test command>" in l and "--no-commit" in l
               for l in finish_lines), finish_lines
    assert "compass tdd-green --scenario" not in text, (
        "a separate green step before finish records a green over the "
        "untraced files")


def test_qfo_6_the_command_lists_every_allowed_value():
    """An agent that guesses `low` or `high` spends a call on the refusal."""
    text = _text(COMMAND)
    for value in ("trivial", "contained", "cross-cutting", "critical",
                  "greenfield", "brownfield-mapped", "brownfield-unmapped",
                  "atomic", "small", "medium", "large", "product"):
        assert f"`{value}`" in text, f"commands/quick-fix.md omits {value}"


def test_qfo_6_assess_sends_a_small_change_to_quick_fix_start():
    """An agent that opens `/compass:assess` for a small change otherwise
    writes the manifest and the approach record by hand."""
    text = _text(ROOT / "commands" / "assess.md")
    assert "compass quick-fix start" in text
    assert "/compass:quick-fix" in text


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


#: Each rule the skill held, with a phrase the command must now carry. Each
#: phrase is the shortest wording that carries the rule, so a rule that is
#: reworded around it still passes, and a rule that is dropped does not.
RULES_MOVED_FROM_THE_SKILL = {
    "an unjustified value is worse than a question": "an unjustified value",
    "risk is consequence, never effort": "never effort",
    "risk: trivial test": "instantly reversible",
    "risk: contained test": "recoverable without an incident",
    "risk: cross-cutting test": "ecovery needs coordination",
    "risk: critical test": "cannot be rolled back",
    "familiarity: greenfield test": "net-new",
    "familiarity: brownfield-mapped test": "trivially readable",
    "familiarity: brownfield-unmapped does not stop a quick fix":
        "pin with a test what the code does now",
    "size: atomic test": "under about half an hour",
    "size: small test": "solution pattern that already exists",
    "size: medium and above test": "design decisions",
    "size: estimate up when unsure": "estimate up",
    "goal: an intent.md or positioning.md pulls the approach up": "positioning.md",
    "goal: exploration is a spike": "exploration",
    "the guardrail is tested before it lands": "tested before it lands",
    "a light approach adapts surface, never whether a test exists": "never whether a test exists",
    "red: fail for the right reason": "right reason",
    "green: the smallest correct change": "smallest correct change",
    "refactor: a changed test means back to red": "go back to red",
    "the hook blocks an edit with no failing test; never work around it": "work around it",
    "no natural failing test: use a guard that can fail": "guard that can fail",
    "no natural failing test: the verified-by kinds": "regression|e2e|typecheck|live",
    "a sanctioned red is not an exemption from red": "not an exemption from red",
}


def test_qfs_176_every_rule_of_the_skill_reaches_the_command():
    """A session that runs `/compass:quick-fix` reads the command and nothing
    else, so a rule must be in the command to be followed."""
    text = " ".join(_text(COMMAND).split())
    missing = sorted(rule for rule, phrase in RULES_MOVED_FROM_THE_SKILL.items()
                     if phrase not in text)
    assert not missing, f"commands/quick-fix.md lacks these rules: {missing}"


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
    """A session opens `/compass:assess` first. With the three commands and
    the allowed values there, it does not spend a call loading
    `/compass:quick-fix` as well."""
    text = _text(ROOT / "commands" / "assess.md")
    assert "compass tdd-red" in text
    finish = [l for l in text.splitlines()
              if l.strip().startswith("compass quick-fix finish")]
    assert finish and all("--no-commit" in l and "-- <test command>" in l
                          for l in finish), finish
    for value in ("trivial", "contained", "brownfield-mapped", "atomic",
                  "small"):
        assert f"`{value}`" in text, f"commands/assess.md omits {value}"
