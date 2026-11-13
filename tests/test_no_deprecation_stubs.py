"""No deprecation stub outlives the version it was scheduled for removal in.

The v2 vocabulary freeze renamed the pipeline's commands and verbs, leaving a
redirect behind each one for "one major version". ADR-014 removed those at
3.0.0, while Compass had no adopters and the removal cost nothing.

ADR-019 supersedes that rule now Compass is published and released at 3.3.0.
A name retired INSIDE a major version keeps working until the next one, so
an adopter who upgrades is not broken; a name retired AT a major version is
still deleted outright. Every surviving stub is named individually below,
with the version it goes at - which is what stops a redirect layer becoming
open-ended, and is the thing ADR-014 was actually protecting against.

What stays either way is the migrator's v1-to-v2 mapping. That is a
translation table rather than a redirect: a stub answers a caller who used the
old name, a mapping reads a file that used it.

Scenario ids: see the issue's acceptance criteria (group F).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
COMMANDS = ROOT / "commands"

# Retired pipeline commands, removed at a major version and never to reappear.
# `plan` is the planning stage's live command, so it is not listed. A removed
# name is not reserved for ever - it is free to be reused for the thing it
# best describes.
#
# The first six went at 3.0.0. The last three were redirect stubs through 3.x
# and went at 4.0.0, the boundary ADR-019 scheduled them for; ADR-024 records
# why the redirects were not carried further.
RETIRED_COMMANDS = (
    "build.md", "clarify.md", "distribute.md", "frame.md",
    "land.md", "specify.md",
    "triage.md", "wireframe.md", "roundtable.md",
)

# The retired verbs and verb pairs. Each used to exit 2 with a one-line
# pointer naming its replacement. The full set is listed so no retired
# spelling drops out of the check silently.
RETIRED_VERBS = (
    ("route", "evaluate"),
    ("backfill", "pay"),
    ("calibration",),
    ("land-commit",),
    ("task", "lint"),
)


def test_rcd_f1_no_retired_slash_commands():
    """No command file exists whose only content is a redirect."""
    present = [name for name in RETIRED_COMMANDS if (COMMANDS / name).is_file()]
    assert not present, (
        f"retired slash-command stubs are still shipped: {', '.join(present)}. "
        f"ADR-014 removes them at the major version."
    )

    # And nothing new has quietly taken their place: no shipped command may
    # describe itself as a retired name. Checked by content as well as by
    # filename, so a rename of the stub file does not slip past.
    #
    # No exemptions. 4.0.0 removed the last three stubs, so every command file
    # is covered. Re-introducing a stub means adding a name here
    # deliberately, and this comment is where the argument for it goes.
    redirects = [
        p.name for p in COMMANDS.glob("*.md")
        if "retired name" in p.read_text(encoding="utf-8").lower()
    ]
    assert not redirects, (
        f"command file(s) still describe themselves as a retired name: "
        f"{', '.join(redirects)}"
    )


def test_rcd_f2_retired_verb_is_unknown():
    """A retired verb fails the way any unrecognised verb fails.

    Distinguished from the old behaviour by the pointer's own wording, not by
    the exit code: the pointer exited 2 and so does argparse on an unknown
    verb, so an exit-code assertion alone would pass against the stub.
    """
    for argv in RETIRED_VERBS:
        spelling = " ".join(argv)
        result = subprocess.run(
            [sys.executable, str(CLI), *argv],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        combined = (result.stdout + result.stderr).lower()

        assert result.returncode != 0, (
            f"`compass {spelling}` succeeded - a retired verb must fail"
        )
        assert "renamed" not in combined, (
            f"`compass {spelling}` still prints the retired-spelling "
            f"pointer:\n{combined}"
        )
        assert "for one major version" not in combined, (
            f"`compass {spelling}` still promises the retired spelling is "
            f"kept:\n{combined}"
        )


def test_rcd_f2b_the_live_verb_still_works():
    """The control: removing the pointer must not remove the replacement.

    Without this, F2 passes against a CLI where `approach` was deleted too.
    """
    result = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--help"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"`compass approach evaluate` - the live spelling - does not work:\n"
        f"{result.stdout}{result.stderr}"
    )


def test_rcd_f3_retired_flag_is_unknown():
    """A retired flag spelling fails as any unrecognised flag would.

    `--task` and `--reading` were tolerated alongside `--issue` and
    `--assessment` "for one major version". Both live spellings already
    worked, so removing the old ones changes no behaviour - only what the
    parser accepts.
    """
    # Each retired spelling is probed on the subcommand that carried it:
    # `--reading` lived only on `approach evaluate`. The retired spellings
    # are literals so a rename sweep cannot invert the test.
    for argv in (
        ["issue", "lint", "--task", "demo"],
        ["approach", "evaluate", "--reading", "risk=contained"],
    ):
        flag = next(a for a in argv if a.startswith("--"))
        result = subprocess.run(
            [sys.executable, str(CLI), *argv],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
        )
        combined = (result.stdout + result.stderr).lower()

        assert result.returncode != 0, (
            f"`{flag}` was accepted - a retired flag spelling must fail"
        )
        # Matches argparse's exact wording, because `approach evaluate` also
        # fails a parsed `--reading` with "invalid assessment".
        assert "unrecognized arguments" in combined, (
            f"`{flag}` failed, but not as an unrecognised flag - it parsed, "
            f"so it may still be wired up:\n{combined}"
        )


def test_rcd_f3b_the_live_flag_still_works(tmp_path):
    """The control: removing the alias must not remove the real flag.

    Without this, F3 passes against a CLI where `--issue` was deleted too.
    """
    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\n", encoding="utf-8")
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: "demo"\ncreated: "2026-08-13"\n'
        'status: queued\nassessment:\n  risk: contained\n'
        '  familiarity: brownfield-mapped\n  size: small\n  goal: delivery\n'
        '  role: engineer\n  labels: []\n',
        encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(CLI), "issue", "lint", "--issue", "demo"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, (
        f"`--issue`, the live spelling, no longer works:\n"
        f"{result.stdout}{result.stderr}"
    )


def test_rcd_f3c_the_flag_alias_data_is_gone():
    """The tolerated spellings go out of the map with the pointer data."""
    import yaml
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg                                   # noqa: F401

    data = yaml.safe_load((ROOT / "cli" / "migrate-map.yml").read_text()) or {}
    assert "flags" not in data, (
        "migrate-map.yml still carries `flags:`, the tolerated retired flag "
        "spellings that ADR-014 removes"
    )


def test_rcd_f2c_the_pointer_machinery_is_gone():
    """The data that fed the pointer goes with it.

    Leaving `verbs:`/`subverbs:` in migrate-map.yml would be dead data that
    reads like a live contract to the next person who opens the file.
    """
    import yaml
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg                                   # noqa: F401

    data = yaml.safe_load((ROOT / "cli" / "migrate-map.yml").read_text()) or {}
    for section in ("verbs", "subverbs"):
        assert section not in data, (
            f"migrate-map.yml still carries `{section}:`, which existed only "
            f"to feed the retired-verb pointer that ADR-014 removes"
        )
