"""Each refusal's fix line names a command a session can run as written.

#358: the fix line of `no-scenario` passed the scenario id as a flag,
`compass scenario add <slug> --id <scenario id>`, which the CLI refuses with
"unrecognized arguments", and two landing refusals told an agent to run `compass evidence approve`, which
an agent may run only under a delegation. This test parses every `compass`
command a fix line names with the CLI's own parser, built in this process,
with each placeholder filled with a sample value. ADR-097 holds the rule.

- A slash command a fix line names must be a file in `commands/`. A command
  marked `disable-model-invocation` is the person's, so the line must say the
  person types it.
- A code whose fix no single command clears is in `NO_COMMAND`, with the
  reason. A code that names no command and is not in that table fails. A
  code in the table can still name a command, such as one that does not help,
  and that command is not parsed.
- A code whose fix runs the refused command again with one more flag is in
  `RERUN`. The flag must exist on each verb that renders the code.
- No fix line names `compass evidence approve` without `--delegated`.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import re
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg.refusals import REFUSALS, codes  # noqa: E402
from compass_pkg.verb_help import parse_command_line  # noqa: E402

#: The codes no single command clears, and why (ADR-097, plan section 4.1).
NO_COMMAND = {
    "bad-session-issue-restart": "only a restart changes COMPASS_ISSUE",
    "bash-command-too-complex": "a shorter command clears it",
    "bash-command-too-long": "a shorter command clears it",
    "config-invalid": "an edit of the file clears it; compass policy lint does not "
                      "check every fault the reader finds",
    "delegation-protected": "only the person can create or revoke a delegation",
    # #359: `compass policy migrate` runs only on Compass 8.x, and an edit of
    # compass.yml clears a git parent; `compass migrate` comes after either.
    "git-parent-removed": "an edit of compass.yml clears it",
    "governance-copy-removed": "only Compass 8.x clears it, with compass policy migrate",
    "pr-review-protected": "only another person can approve the pull request",
    "python-missing": "installing Python clears it",
    "reader-failed": "repairing the install clears it",
    "settings-conflict": "moving keys by hand clears it",
    "transcript-protected": "nothing: the read is refused",
    "tree-not-tied": "editing in another folder clears it",
    "working-directory-gone": "a restart from a folder that exists clears it",
}

#: The codes whose fix runs the refused command again with one more flag:
#: code -> (flag, the verbs that render the code).
RERUN = {
    "release-line-heading": ("--release-note", (
        "compass acceptance record", "compass quick-fix finish", "compass ship-commit")),
    "release-line-missing": ("--release-note", (
        "compass acceptance record", "compass quick-fix finish", "compass ship-commit")),
}

#: A sample for each placeholder, so the command can be parsed.
SAMPLES = {
    "{slug}": "demo", "{previous}": "demo", "{dependency}": "other",
    "{stage}": "specify", "<slug>": "demo", "<id>": "TRC-001", "<stage>": "specify",
    "<item>": "tests-pass", "<owner/repo#N>": "o/r#1", "<n>": "1", "<type>": "test-run",
    "<file>": "out.txt", "<kind>": "validation",
}

#: A word that ends a command in a fix line.
STOP_WORDS = {"and", "or", "then", "to", "if", "in", "again", "for", "with", "so"}

TOKEN = re.compile(r'"[^"]*"[,;.]?|<[^>]*>[,;.]?|\S+')


def _commands(text):
    """Every `compass ...` command in `text`, as a list of words."""
    found = []
    for match in re.finditer(r"(?<![\w/-])compass (?=[a-z_])", text):
        words = []
        for token in TOKEN.findall(text[match.start():]):
            if token in STOP_WORDS:
                break
            end = token.rstrip(",;.`)")
            if end.startswith("`"):
                end = end[1:]
            if end:
                words.append(end)
            if end != token:
                break
        found.append(words)
    return found


def _filled(words):
    out = []
    for word in words:
        if word.startswith('"') and word.endswith('"'):
            out.append("sample text")
            continue
        for placeholder, sample in SAMPLES.items():
            word = word.replace(placeholder, sample)
        if re.search(r"[<>{}]", word):
            out.append("sample")
        else:
            out.append(word)
    return out


def _entry():
    import compass_pkg  # noqa: F401  - resolves the bundled yaml
    spec = importlib.util.spec_from_loader(
        "compass_entry", SourceFileLoader("compass_entry", str(ROOT / "cli" / "compass")))
    module = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = ["compass"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = saved
    return module


ENTRY = _entry()


def _parse_error(argv):
    """None when the CLI's parser accepts `argv`, or argparse's message."""
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            parse_command_line(ENTRY.build_parser(), argv)
    except SystemExit as exc:
        if exc.code:
            return err.getvalue().strip() or f"exit {exc.code}"
    return None


def _verb_parser(verb):
    parser = ENTRY.build_parser()
    for word in verb.split()[1:]:
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        parser = subs[0].choices[word]
    return parser


def _release_line():
    from compass_pkg import release_line
    return release_line


def _person_commands():
    return {p.stem for p in (ROOT / "commands").glob("*.md")
            if "disable-model-invocation: true" in p.read_text(encoding="utf-8")}


def test_the_tables_name_only_registered_codes():
    assert not (set(NO_COMMAND) | set(RERUN)) - set(codes())


def test_the_extractor_finds_a_command_and_where_it_ends():
    assert _commands("run compass tdd-red --scenario <id> -- <failing test command>, "
                     "or compass acceptance start --kind <kind> if none fits") == [
        ["compass", "tdd-red", "--scenario", "<id>", "--", "<failing test command>"],
        ["compass", "acceptance", "start", "--kind", "<kind>"]]
    assert _commands("in this session, run `compass issue use {previous}` to carry on") == [
        ["compass", "issue", "use", "{previous}"]]


def test_the_parse_check_can_fail():
    """The old `no-scenario` fix line, which the CLI refused."""
    words = _filled(["compass", "scenario", "add", "<slug>", "--id", "TRC-001",
                     "--intent", "..."])
    assert "unrecognized arguments: --id TRC-001" in (_parse_error(words[1:]) or "")


@pytest.mark.parametrize("code", codes())
def test_each_named_command_parses(code):
    fix = REFUSALS[code]["fix"]
    if code in NO_COMMAND:
        return
    rerun = RERUN.get(code, (None, ()))[1]
    for words in _commands(fix):
        if " ".join(words) in rerun:
            continue
        error = _parse_error(_filled(words)[1:])
        assert error is None, (code, " ".join(words), error)


@pytest.mark.parametrize("code", codes())
def test_each_code_names_a_command_or_says_why_not(code):
    fix = REFUSALS[code]["fix"]
    if code in NO_COMMAND:
        return
    names = _commands(fix) or re.findall(r"/compass:[a-z-]+", fix) or code in RERUN
    assert names, (code, fix, "name a command, or add the code to NO_COMMAND with the reason")


@pytest.mark.parametrize("code", sorted(RERUN))
def test_a_rerun_flag_is_on_each_verb(code):
    flag, verbs = RERUN[code]
    assert flag in REFUSALS[code]["fix"], code
    for verb in verbs:
        assert flag in _verb_parser(verb)._option_string_actions, (code, verb)


def test_the_rerun_verbs_are_every_verb_that_passes_a_release_line():
    """The verbs `release_line` is called with, so a new verb is checked too."""
    source = "\n".join(p.read_text(encoding="utf-8")
                       for p in (ROOT / "cli" / "compass_pkg").glob("*.py"))
    passed = set(re.findall(
        r"release_line\.(?:given|judge_landing)\([^)]*?\"(compass [a-z -]+)\"", source))
    landing = set(_release_line().LANDING_VERBS.split(" or "))
    assert landing <= passed, landing
    for code in RERUN:
        assert passed == set(RERUN[code][1]), (code, passed)


@pytest.mark.parametrize("code", codes())
def test_each_slash_command_is_one_the_reader_may_run(code):
    fix = REFUSALS[code]["fix"]
    person = _person_commands()
    for name in re.findall(r"/compass:([a-z-]+)", fix):
        assert (ROOT / "commands" / f"{name}.md").is_file(), (code, name)
        if name in person:
            assert "person" in fix, (code, name, "a person's command, not the agent's")


@pytest.mark.parametrize("code", codes())
def test_no_fix_line_tells_an_agent_to_approve(code):
    for words in _commands(REFUSALS[code]["fix"]):
        if words[1:3] == ["evidence", "approve"]:
            assert "--delegated" in words, (code, " ".join(words))
