"""Group C and `TRC-047` of issue `hooks-stop-refusing-harmless-work`: the Read,
Grep, Edit and Write tools can use the agent's own auto-memory folder
(`<configuration folder>/projects/<one folder>/memory/...`), and no other file
under the transcript folder, whatever the spelling of the path.

Scenarios: `TRC-017`, `TRC-018`, `TRC-019`, `TRC-047`. Every call runs the real
`hooks/pre-tool.sh`, so a Write outside the project also passes the later checks
of the hook. The test home holds a symbolic link, `memory/link`, to the
transcript.

Red before the change: `TRC-017`, because the guard refuses every path under a
`projects` folder. Green before the change, kept as regression guards:
scenarios `TRC-018`, `TRC-019` and `TRC-047`. The twins are the part that stops the opening from
being wider than the memory folder: `..`, a Grep glob that climbs out of it, a
symbolic link, a lookalike folder name and a Bash command.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from approval_guard_cases import (TRN, build_world, controls_for, drop_world,  # noqa: E402
                                  misses, payload, refused_for)


@pytest.fixture(scope="module")
def world():
    built = build_world()
    yield built
    drop_world(built)


def _events(world, cases):
    return [payload(c, home=world.home, project=world.project, transcript=world.transcript)
            for c in cases]


def test_trc_017_the_tools_can_use_the_auto_memory_folder(world):
    cases = controls_for("TRC-017")
    assert len(cases) == 8
    found = misses(world, _events(world, cases), "allowed")
    assert not found, "\n".join(found)


def test_trc_018_the_transcript_and_lookalike_paths_are_still_refused(world):
    cases = refused_for("TRC-018")
    assert len(cases) >= 8
    found = misses(world, _events(world, cases), TRN)
    assert not found, "\n".join(found)


def test_trc_019_a_bash_command_naming_the_auto_memory_folder_is_still_refused(world):
    cases = refused_for("TRC-019")
    assert {c.tool for c in cases} == {"Bash"}
    assert len(cases) >= 4
    found = misses(world, _events(world, cases), TRN)
    assert not found, "\n".join(found)


def test_trc_047_the_tools_cannot_reach_the_transcript_from_the_auto_memory_folder(world):
    link = world.transcript.parent / "memory" / "link"
    assert link.is_symlink() and link.resolve() == world.transcript.resolve()
    cases = refused_for("TRC-047")
    assert len(cases) >= 7
    assert {c.tool for c in cases} == {"Grep", "Read", "Edit", "Write"}
    found = misses(world, _events(world, cases), TRN)
    assert not found, "\n".join(found)
