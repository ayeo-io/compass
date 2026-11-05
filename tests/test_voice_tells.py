"""How the standalone tell check behaves (issue human-voice, `TRC-D2`, D3, F1, F2).

`scripts/voice-tells.py` greps the three writing-voice tells a fixed string
can find - "I will now proceed", "Upon completion", "utilize" - over an
issue's markdown artifacts. It is advisory: it always exits 0, it is
registered in no `guardrails.yml` entry, and no test here asserts the
repository is free of tells. `tests/test_human_voice.py` asserts what the
prose surfaces carry; this file asserts how the check itself behaves, run as
a subprocess over fixtures in `tmp_path` (technical-design.md `DD-4`).

Criteria: the issue's acceptance criteria
Design:   human-voice/technical-design.md, section 5 (the script's
          contract) and `DD-2` (what "newly written" scopes to) and `DD-3` (why
          a standalone script rather than a CLI verb).
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "voice-tells.py"


def _load_script_module():
    """The running script, loaded by path (it has a hyphen in its name, so
    it cannot be `import`ed as a package). Reading `TELLS` off the loaded
    module - rather than retyping the three strings here - is what keeps
    this file's fixtures and the script's own greps from drifting apart."""
    spec = importlib.util.spec_from_file_location("voice_tells_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TELLS = _load_script_module().TELLS


def _run_script(args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd) if cwd else str(REPO_ROOT),
        capture_output=True, text=True, timeout=30,
    )


def test_trc_d2_each_hit_is_reported_with_file_and_line(tmp_path):
    fixture = tmp_path / "issue"
    fixture.mkdir()
    md = fixture / "devlog.md"
    # Built from TELLS, not retyped - a fixture spelling its needles
    # independently of the script's own list is exactly the drift `TRC-D2`'s
    # "one list, not two" rules out.
    lines = ["line one is plain prose."] + [
        f"Sentence naming the tell: {tell}." for tell in TELLS
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_script([str(fixture)])
    assert result.returncode == 0

    expected = {(str(md), i + 2, tell) for i, tell in enumerate(TELLS)}
    found = set()
    for line in result.stdout.splitlines():
        m = re.match(r"^\s*(\S+):(\d+):\s*\"(.+)\"\s*$", line)
        if m:
            found.add((m.group(1), int(m.group(2)), m.group(3)))
    assert expected <= found, (
        f"expected {expected} among the reported hits, got {found}\n"
        f"--- stdout ---\n{result.stdout}"
    )


def test_trc_d3_a_clean_run_states_that_it_found_nothing(tmp_path):
    fixture = tmp_path / "issue"
    fixture.mkdir()
    (fixture / "devlog.md").write_text(
        "Nothing to see here, just ordinary prose.\n", encoding="utf-8",
    )

    result = _run_script([str(fixture)])
    assert result.returncode == 0
    assert result.stdout.strip(), "a clean run must still print something"
    assert "clean" in result.stdout.lower()


def test_trc_f1_a_found_tell_never_blocks_or_moves_a_gate(tmp_path):
    fixture = tmp_path / "issue"
    fixture.mkdir()
    (fixture / "devlog.md").write_text("utilize this later.\n", encoding="utf-8")

    result = _run_script([str(fixture)])
    assert result.returncode == 0
    assert "advisory" in result.stdout.lower()

    guardrails_text = (REPO_ROOT / "governance" / "guardrails.yml").read_text(
        encoding="utf-8"
    )
    assert "voice-tells" not in guardrails_text
    assert "voice_tells" not in guardrails_text

    # The trap named at the requirements review: nothing in this suite may
    # run the check against the real repository and assert on the result -
    # that would make the advisory grep a gate wearing a soft label. Every
    # test above calls the script against a tmp_path fixture only.
    for name in ("test_human_voice.py", "test_voice_tells.py"):
        src = (REPO_ROOT / "tests" / name).read_text(encoding="utf-8")
        assert not re.search(r"_run_script\([^)]*REPO_ROOT[^)]*\)", src), (
            f"{name} must never invoke the check against the real "
            f"repository and assert on the result"
        )


def test_trc_f2_the_reference_and_the_archive_originals_are_not_hits(tmp_path):
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK), "scripts/voice-tells.py must be executable"

    reference = REPO_ROOT / "skills" / "compass-runtime" / "writing-voice.md"
    reference_text = reference.read_text(encoding="utf-8")
    for tell in TELLS:
        assert tell in reference_text, (
            f"the reference's own quoted tells must still be findable by a "
            f"plain read: {tell!r}"
        )

    # A default-scoped run never reports a path outside the current issue
    # directory. Proven with an isolated mini-project rather than this
    # repository's own .compass/current-task, so the test is hermetic.
    project = tmp_path / "project"
    issue_dir = project / ".compass" / "work" / "issue-a"
    other_dir = project / ".compass" / "work" / "issue-b"
    reference_dir = project / "skills"
    issue_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)
    reference_dir.mkdir(parents=True)

    (project / ".compass" / "current-task").write_text(
        "issue-a\n", encoding="utf-8"
    )
    (issue_dir / "devlog.md").write_text("utilize this.\n", encoding="utf-8")
    (other_dir / "devlog.md").write_text("utilize that too.\n", encoding="utf-8")
    (reference_dir / "writing-voice.md").write_text(
        "utilize is a tell.\n", encoding="utf-8"
    )

    result = _run_script([], cwd=project)
    assert result.returncode == 0

    # The clean-path banner names the directory it scanned, and that path
    # contains "issue-a" - so asserting "issue-a" appears was satisfied by a
    # run that found nothing at all. Empty tells, a broken needle, or no
    # hits would all have left this green. Anchor on the hit itself first.
    assert "clean" not in result.stdout.lower(), (
        f"the scanner found nothing, so the scope assertions below would "
        f"pass on the 'no findable tell' banner rather than on a hit:\n"
        f"{result.stdout}"
    )
    assert str(issue_dir / "devlog.md") in result.stdout, (
        f"the run did not report the tell planted in the current issue:\n"
        f"{result.stdout}"
    )
    assert "issue-b" not in result.stdout
    assert str(reference_dir) not in result.stdout


def test_a_permission_denied_pointer_never_crashes_the_check(tmp_path):
    """Review finding (verification-report.md 5.3, must-fix 2): the pointer
    read at the heart of the default scope was unguarded, so an unreadable
    .compass/current-task raised a traceback and exited 1 - against the
    exit-0-always contract the script states three times."""
    project = tmp_path / "project"
    (project / ".compass").mkdir(parents=True)
    pointer = project / ".compass" / "current-task"
    pointer.write_text("issue-a\n", encoding="utf-8")
    os.chmod(pointer, 0o000)
    try:
        result = _run_script([], cwd=project)
    finally:
        os.chmod(pointer, 0o644)  # restore so tmp_path cleanup can remove it
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "clean" in result.stdout.lower()


def test_an_undecodable_pointer_never_crashes_the_check(tmp_path):
    """Same contract, the other reachable way to break it: a pointer file
    an editor wrote in UTF-16 is not exotic, and utf-8 decoding must not
    raise past this script's boundary."""
    project = tmp_path / "project"
    (project / ".compass").mkdir(parents=True)
    pointer = project / ".compass" / "current-task"
    pointer.write_bytes(b"\xff\xfe\x00b\x00a\x00d\x00")  # not valid utf-8
    result = _run_script([], cwd=project)
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    assert "clean" in result.stdout.lower()


def test_a_slug_with_a_path_separator_is_rejected_not_followed(tmp_path):
    """Review finding 3 (verification-report.md 5.3, 5.5): the slug read
    from the pointer went into os.path.join unvalidated, so an absolute
    slug replaced the whole prefix and escaped the issue directory -
    exactly the property `TRC-F2` asserts for well-formed input: a
    default-scoped run never reports a path outside the current issue
    directory."""
    project = tmp_path / "project"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "leak.md").write_text("utilize this.\n", encoding="utf-8")
    (project / ".compass" / "work").mkdir(parents=True)
    (project / ".compass" / "current-task").write_text(
        str(outside), encoding="utf-8"
    )

    result = _run_script([], cwd=project)
    assert result.returncode == 0
    assert str(outside) not in result.stdout
    assert "leak" not in result.stdout
