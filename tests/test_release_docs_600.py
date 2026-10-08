"""The owning docs say what 6.0.0 does with the settings file.

6.0.0 keeps a project's settings in `compass.yml`, reads `.compass/config.yml`
for a project that has not moved, and moves it with `compass policy migrate`.
The docs that own those facts say so, and `docs/releasing.md` records what the
release contains, the checks to run and the four compatibility configurations.

Scenario ids: IDR-8 and IDR-9, in the acceptance criteria of the issue
`init-docs-release`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _section(text, heading):
    """The body under the `### heading` line, up to the next heading of the
    same or a higher level."""
    m = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert m, f"no heading {heading!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[:end.start()] if end else rest


# --- IDR-8: the owning docs ---------------------------------------------------

def test_idr_8_configuration_md_says_what_writes_compass_yml_and_how_to_move():
    text = _read("docs/configuration.md")
    assert "compass policy migrate" in text
    assert "/compass:init" in text
    assert "because none exists yet" not in text
    assert "nothing writes it yet" not in text
    assert "rewritten `init` will" not in text


def test_idr_8_the_settings_conflict_way_out_is_not_a_command_that_refuses():
    """`policy migrate` refuses while a `compass.yml` holds the project's
    settings, so the doc must not send a conflicted project to it."""
    text = _read("docs/configuration.md")
    way_out = text[text.index("**The way out.**"):]
    way_out = way_out[:way_out.index("\n- **")]
    assert "delete them from `.compass/config.yml`" in way_out
    assert "refuses" in way_out


def test_idr_8_security_md_places_the_project_command_setting_beside_its_checks():
    text = _read("docs/security.md")
    assert re.search(r"same file|beside the checks", text), (
        "docs/security.md does not say allow_project_commands now shares a file "
        "with the checks it authorises")
    assert "compass.yml" in text[text.index("### Safer default"):]


def test_idr_8_safety_contract_states_the_three_new_limits():
    text = _read("docs/safety-contract.md").lower()
    assert "not authenticated" in text, "approvals are a name and a date"
    assert "conformance" in text
    assert "corpus" in text, "implementation compatibility holds on the corpus only"


def test_idr_8_runtime_skill_lays_out_the_project_files_as_6_does():
    text = _read("skills/compass-runtime/SKILL.md")
    assert "compass.yml" in text.split("## Where state lives", 1)[1][:600]
    assert "if `/compass:init` copied one in" not in text


def test_idr_8_receipt_md_describes_the_conformance_line():
    assert "Conformance" in _read("docs/receipt.md")


# --- IDR-9: the release entry -------------------------------------------------

def test_idr_9_releasing_md_has_a_6_0_0_entry_with_the_contents():
    text = _read("docs/releasing.md")
    body = _section(text, "What changed at 6.0.0")
    for needle in ("compass.yml", "policy lint", "policy effective", "policy diff",
                   "policy migrate", "generation", "`.compass/config.yml`",
                   "7.0.0"):
        assert needle in body, f"the 6.0.0 entry does not mention {needle!r}"


def test_idr_9_the_entry_lists_the_behaviour_changes():
    body = _section(_read("docs/releasing.md"), "What changed at 6.0.0")
    assert re.search(r"fails .{0,40}lint.{0,100}--write.{0,20}refuse", body, re.S | re.I)
    assert re.search(r"landed.{0,80}(cannot|refus)", body, re.S | re.I)
    assert re.search(r"unreferenced|leftover", body, re.I)
    assert re.search(r"without a generation|no (stored )?generation", body, re.I)


def test_idr_9_the_release_checks_name_the_full_archive_run_and_contracts_a_to_d():
    text = _read("docs/releasing.md")
    body = _section(text, "Checks for 6.0.0")
    assert "COMPASS_FULL_ARCHIVE=1" in body
    assert "tests/test_compat_contracts.py" in body
    for letter in "ABCD":
        assert re.search(rf"\*\*{letter}\.\*\*", body), f"configuration {letter} missing"
    assert "test_framework_compass_yml" in body
    for rel in ("tests/test_compat_contracts.py", "tests/test_framework_compass_yml.py"):
        assert (ROOT / rel).is_file(), rel


# --- the verbs the 6.0.0 entry names exist ------------------------------------

def _named_verbs(entry):
    """Each `compass <verb> [<subverb>]` code span in `entry`."""
    spans = re.findall(r"`compass\s+([a-z][a-z-]*(?:\s+[a-z][a-z-]*)?)", entry)
    return sorted({" ".join(span.split()) for span in spans})


def _runs(argv):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv,
                        "--help"], capture_output=True, text=True, timeout=60)
    return r.returncode == 0, r.stdout


def _verb_missing(words):
    """True when `compass <words> --help` fails, treating a trailing word as an
    argument only for a verb that has no subcommands."""
    ok, _ = _runs(words)
    if ok:
        return False
    ok_one, out = _runs(words[:1])
    return not (ok_one and "{" not in out)


def test_the_6_0_0_entry_names_only_verbs_the_cli_has():
    entry = _section(_read("docs/releasing.md"), "What changed at 6.0.0")
    verbs = [v.split() for v in _named_verbs(entry)]
    assert len(verbs) >= 8, verbs
    missing = [" ".join(v) for v in verbs if _verb_missing(v)]
    assert not missing, f"the entry names verbs the CLI lacks: {missing}"


def test_the_verb_check_fails_on_a_verb_the_cli_lacks():
    assert _verb_missing(["policy", "no-such-verb"])
    assert "policy update" in _named_verbs("`compass policy update` moves")
