"""Acceptance tests for issue cli-surface-drift-v1-2.

The tests parse `compass --help` to derive the truth set of subcommands and
assert it appears in the documented CLI blocks. The next new subcommand
that ships without updating the docs fails these tests in CI.

Scenario ids: `TRC-A1`..C1, from the `cli-surface-drift-v1-2` issue. The
issue's record is not in the repository; these ids and this description are
the only record.
"""
import re
import subprocess
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"


def _subcommands_from_help():
    """Parse `compass --help` and return the set of subcommand names."""
    result = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "--help"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    # argparse renders positional choices as: {a,b,c,d}
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", result.stdout)
    assert m, (
        f"Could not find subcommand list in compass --help output:\n{result.stdout}"
    )
    return set(m.group(1).split(","))


def _extract_block_after(text, anchor):
    """Return the contents of the fenced code block that follows `anchor`."""
    i = text.find(anchor)
    assert i >= 0, f"Anchor '{anchor[:80]}' not found"
    after = text[i:]
    m = re.search(r"```(?:[a-z]*)?\n(.*?)\n```", after, re.DOTALL)
    assert m, f"No fenced block after anchor '{anchor[:80]}'"
    return m.group(1)


def _cli_block_in(file_path):
    """Extract the documented CLI surface block from a doc file.

    The convention: each file has a fenced code block that lists `compass
    <subcommand>` lines, one per line. We anchor on a listing line for
    `compass approach evaluate` and grab the surrounding fence.

    The anchor must start the line. The same command also appears in prose
    and in pasted terminal transcripts, where it is quoted inline or
    follows a `$` prompt - matching those would pick up a block that lists
    no verbs at all.
    """
    text = (ROOT / file_path).read_text()
    # Find the fenced block that contains the anchor line.
    pattern = r"```(?:[a-z]*)?\n((?:[^\n`]*\n)*?compass approach evaluate[^\n]*\n(?:[^\n`]*\n)*?)```"
    m = re.search(pattern, text)
    assert m, f"CLI block (containing 'compass approach evaluate') not found in {file_path}"
    return m.group(1)


# ---------------------------------------------------------------------------
# Group A - public-facing CLI surface blocks
# ---------------------------------------------------------------------------

def test_trc_a1_cli_page_block_tracks_compass_help():
    """docs/cli.md's CLI surface block names every subcommand `compass --help`
    reports. docs/cli.md owns the verb list; the README links to it."""
    subs = _subcommands_from_help()
    block = _cli_block_in("docs/cli.md")
    missing = sorted(
        s for s in subs if not re.search(rf"(?<![\w-])compass {re.escape(s)}(?![\w-])", block)
    )
    assert not missing, (
        f"docs/cli.md CLI block is missing {missing} from compass --help's subcommands. "
        f"Full subcommand set: {sorted(subs)}.\n\nBlock content:\n{block}"
    )


def _sub_verbs(parent):
    """Parse `compass <parent> --help` and return the set of sub-verb names."""
    result = subprocess.run(
        [sys.executable, str(COMPASS_CLI), parent, "--help"],
        capture_output=True, text=True, check=True, timeout=10,
    )
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", result.stdout)
    assert m, (
        f"Could not find sub-verb list in `compass {parent} --help` output:\n{result.stdout}"
    )
    return set(m.group(1).split(","))


def test_trc_a3_task_sub_verbs_tracked_in_cli_blocks():
    """docs/cli.md's CLI block names every `compass issue` sub-verb (lint,
    receipt, ...). The earlier tests cover top-level verbs; this one covers
    the sub-verbs under `issue` so a new one cannot ship undocumented
    behind a top-level no-op (e.g. `compass issue receipt` adding to
    existing `compass issue lint`). docs/five-minutes.md carries no CLI
    block of its own - it points readers at docs/cli.md.
    """
    sub_verbs = _sub_verbs("issue")
    for doc_file in ("docs/cli.md",):
        block = _cli_block_in(doc_file)
        missing = sorted(
            v for v in sub_verbs
            if not re.search(rf"(?<![\w-])compass issue {re.escape(v)}(?![\w-])", block)
        )
        assert not missing, (
            f"{doc_file} CLI block does not name {['compass issue ' + v for v in missing]}. "
            f"`compass issue --help` declares: {sorted(sub_verbs)}.\n\n"
            f"Block content:\n{block}"
        )


# ---------------------------------------------------------------------------
# Group B - adapter contract tables (runtime-neutral)
# ---------------------------------------------------------------------------

def _new_cross_task_commands():
    """The six commands that ship between fb092c0 and v1.2.0 - must appear in
    the runtime-neutral adapter contracts."""
    # The contract must name the live verb.
    return ["compass analyze", "compass rework-scan", "compass follow-up",
            "compass flow", "compass next", "compass adr"]


def test_trc_b1_agents_adapter_section_names_new_cross_task_kit_calls():
    """AGENTS.md's adapter contract section names every new cross-issue command."""
    text = (ROOT / "AGENTS.md").read_text()
    m = re.search(
        r"##\s+What a runtime adapter must give.*?(?=^##\s+|\Z)",
        text, re.DOTALL | re.MULTILINE,
    )
    assert m, "'What a runtime adapter must give' section not found in AGENTS.md"
    section = m.group(0)
    missing = [s for s in _new_cross_task_commands() if s not in section]
    assert not missing, (
        f"AGENTS.md adapter section does not name {missing}. "
        f"A port author following AGENTS.md would not wire up these kit calls."
    )


def test_trc_b2_portability_mapping_table_names_new_cross_task_kit_calls():
    """portability.md's mapping table (or surrounding adapter narrative) names the new commands."""
    text = (ROOT / "docs" / "portability.md").read_text()
    m = re.search(
        r"###\s+The mapping table.*?(?=^###\s+|^---|\Z)",
        text, re.DOTALL | re.MULTILINE,
    )
    assert m, "'The mapping table' subsection not found in docs/portability.md"
    section = m.group(0)
    missing = [s for s in _new_cross_task_commands() if s not in section]
    assert not missing, (
        f"portability.md mapping-table section does not name {missing}."
    )


# ---------------------------------------------------------------------------
# Group C - smoke-test version coherence
# ---------------------------------------------------------------------------

def test_trc_c1_install_smoke_test_shows_current_version():
    """install-smoke-test.md's expected `compass --version` output matches the VERSION file.

    The anchor does not name the words after the version.
    `tests/test_smoke_test_version_matches_cli.py` checks the banner
    wording, against the CLI rather than against a phrase written down
    here.
    """
    version = (ROOT / "VERSION").read_text().strip()
    smoke_test = (ROOT / "docs" / "install-smoke-test.md").read_text()
    expected = f"compass {version} ("
    assert expected in smoke_test, (
        f"docs/install-smoke-test.md does not show the current version. "
        f"VERSION file says '{version}'; expected to find a line starting "
        f"'compass {version} (' in the smoke-test doc."
    )
