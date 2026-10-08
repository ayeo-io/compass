"""The quick-fix command and skill teach the two verbs, not the hand-run
steps the verbs now carry out.

Before this issue, the command walked an agent through five hand-run
stages - `compass init`, a manifest written from a template, `compass
approach evaluate`, `compass tdd-red`/`tdd-green`, `compass check`, `compass
evidence add`, `compass gate pass` three times, a hand-written devlog line,
`compass ship-commit` - each one a model call. `compass quick-fix start` and
`compass quick-fix finish` now do the mechanical half of that in two calls;
this file pins that the two prose files that teach them describe the two
verbs, name no template to read, and stay under the same word ceiling every
other measurement in this issue holds to.

Scenario id: QFO-6, in acceptance-criteria.md of issue quick-fix-overhead.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMAND = ROOT / "commands" / "quick-fix.md"
SKILL = ROOT / "skills" / "quick-fix" / "SKILL.md"

WORD_CEILING = 700


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _words(path: Path) -> int:
    return len(_text(path).split())


def test_qfo_6_both_files_exist():
    missing = [str(p.relative_to(ROOT)) for p in (COMMAND, SKILL) if not p.is_file()]
    assert not missing, f"the quick-fix teaching files are missing: {missing}"


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
    for path in (COMMAND, SKILL):
        text = _text(path)
        assert "templates/" not in text, (
            f"{path.relative_to(ROOT)} still names a template to read")


def test_qfo_6_no_hand_run_gate_or_evidence_step():
    """The verbs pass the gates and record the evidence internally now; an
    agent following these files must never be told to run either by hand."""
    for path in (COMMAND, SKILL):
        text = _text(path)
        assert "compass gate pass" not in text, (
            f"{path.relative_to(ROOT)} still instructs a hand-run "
            f"`compass gate pass`")
        assert "compass evidence add" not in text, (
            f"{path.relative_to(ROOT)} still instructs a hand-run "
            f"`compass evidence add`")


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


def test_qfo_6_the_skill_keeps_the_scoring_tables():
    text = _text(SKILL)
    for dimension in ("Risk", "Familiarity", "Size"):
        assert dimension in text, f"skills/quick-fix/SKILL.md drops {dimension}"
    for value in ("trivial", "contained", "cross-cutting", "critical",
                  "greenfield", "brownfield-mapped", "brownfield-unmapped",
                  "atomic", "small", "medium"):
        assert f"`{value}`" in text, (
            f"skills/quick-fix/SKILL.md drops the `{value}` scoring value")


def test_qfo_6_the_skill_keeps_red_green_refactor():
    text = _text(SKILL)
    assert "**Red.**" in text
    assert "**Green.**" in text
    assert "**Refactor.**" in text


def test_qfo_6_the_skill_description_is_unchanged():
    """The frontmatter `description:` is resident on every turn whether the
    skill loads or not; the intake fixes it and this issue does not touch
    it."""
    text = _text(SKILL)
    assert ('description: "The light path: dimensions, red-green-refactor, '
            'gates. Load with /compass:quick-fix."') in text


def test_qfo_6_each_file_is_under_the_word_ceiling():
    over = {p.relative_to(ROOT): n for p in (COMMAND, SKILL)
            if (n := _words(p)) >= WORD_CEILING}
    assert not over, f"over the {WORD_CEILING}-word ceiling: {over}"


def test_qfo_6_the_two_files_combined_stay_well_under_the_old_reading_path():
    """The path these two replace measured 11,203 words
    (tests/test_prompt_layer.py's `QUICK_FIX_WORD_CEILING` docstring)."""
    total = _words(COMMAND) + _words(SKILL)
    assert total <= 3000, (
        f"commands/quick-fix.md and skills/quick-fix/SKILL.md read {total} "
        "words together, over the 3000-word ceiling")


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
