"""Stop-hook scope-bloat phrase detection.

Stop-hook prompts when scope-bloat phrases appear in devlog (`TRC-C1`).
Stop-hook stays silent when no scope-bloat is detected (`TRC-C2`).
Stop-hook stays silent when a reassessment has already been filed (`TRC-C3`).
Stop-hook regex does not produce false positives on quoted context
(`TRC-X3`).

The six phrases are a constant in hooks/py/stop_scan.py (ADR-094). The
hook emits a prompt to stderr and exits 0 (non-blocking).

Each test invokes hooks/stop.sh as a subprocess with a crafted temp project.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
STOP_HOOK = FRAMEWORK_ROOT / "hooks" / "stop.sh"


def _make_project(tmp_path: Path, *, signals_extra: dict | None = None) -> Path:
    """Create a minimal Compass project in tmp_path with governance/ copied."""
    compass = tmp_path / ".compass"
    work = compass / "work"
    work.mkdir(parents=True, exist_ok=True)
    (compass / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")

    # Copy governance/, as a project with copied governance has it
    gov_src = FRAMEWORK_ROOT / "governance"
    gov_dst = tmp_path / "governance"
    gov_dst.mkdir(parents=True, exist_ok=True)
    for f in gov_src.iterdir():
        if f.is_file():
            shutil.copy(f, gov_dst / f.name)

    return tmp_path


def _make_task(project: Path, slug: str, *,
               devlog_lines: list[str] | None = None,
               reframes: list[dict] | None = None,
               route: str = "standard") -> Path:
    """Materialise an issue directory with delivery-approach.md, devlog.md,
    and manifest.yml."""
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True, exist_ok=True)

    # delivery-approach.md - minimal so the hook can see it
    (task_dir / "delivery-approach.md").write_text(
        f"# Route - {slug}\n\n> **Reference route:** {route}\n"
    )

    # devlog.md - the content under test
    lines = devlog_lines or []
    (task_dir / "devlog.md").write_text("\n".join(lines) + "\n")

    # manifest.yml - needed by the hook's re-assessments check
    body: dict = {
        "task": slug,
        "created": "2026-05-20",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
        },
        "route": route,
        "reframes": reframes or [],
    }
    with (task_dir / "manifest.yml").open("w") as fh:
        yaml.safe_dump(body, fh, sort_keys=False)

    # Set current-task pointer
    (project / ".compass" / "current-task").write_text(slug)
    return task_dir


def _run_hook(project: Path) -> subprocess.CompletedProcess:
    """Run hooks/stop.sh with CLAUDE_PROJECT_DIR pointed at project."""
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    return subprocess.run(
        ["bash", str(STOP_HOOK)],
        cwd=str(project),
        capture_output=True,
        text=True,
        input="",
        env=env,
        timeout=15,
    )


# ---------------------------------------------------------------------------
# The prompt fires when a scope-bloat phrase is in devlog and no reassessment (TRC-C1)
# ---------------------------------------------------------------------------

def test_nudge_on_bloat(tmp_path):
    """A known scope-bloat phrase in devlog triggers a stderr prompt
    (TRC-C1)."""
    project = _make_project(tmp_path)
    _make_task(
        project,
        "bloat-task",
        devlog_lines=[
            "2026-05-20: Started build",
            "more files than Plan estimated - had to touch core module",
            "Finished for the day",
        ],
        reframes=[],
    )
    result = _run_hook(project)
    assert result.returncode == 0, f"hook must exit 0\n{result.stderr}"
    assert "re-assess" in result.stderr.lower(), (
        "Expected a re-assessment nudge in stderr, got:\n" + result.stderr
    )
    assert "/compass:assess --reassess" in result.stderr, (
        "Expected the exact re-assessment command in stderr"
    )


# ---------------------------------------------------------------------------
# Silent when no scope-bloat detected (TRC-C2)
# ---------------------------------------------------------------------------

def test_silent_on_clean(tmp_path):
    """A clean devlog produces no reassessment prompt (TRC-C2)."""
    project = _make_project(tmp_path)
    _make_task(
        project,
        "clean-task",
        devlog_lines=[
            "2026-05-20: Started build, all good",
            "Completed first scenario green",
        ],
        reframes=[],
    )
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    # No prompt expected
    assert "re-assess" not in result.stderr.lower(), (
        "Expected no re-assessment nudge for a clean devlog, got:\n" + result.stderr
    )


# ---------------------------------------------------------------------------
# Silent when a reassessment has already been filed after the bloat line (TRC-C3)
# ---------------------------------------------------------------------------

def test_silent_when_reframed(tmp_path):
    """An honest reassessment entry after the bloat line suppresses the
    prompt (TRC-C3)."""
    project = _make_project(tmp_path)
    _make_task(
        project,
        "reframed-task",
        devlog_lines=[
            "2026-05-19: more files than Plan estimated",
            "2026-05-20: Filed re-assessment, all good",
        ],
        reframes=[
            {
                "from_route": "standard",
                "to_route": "expedition",
                "reason": "scope larger than estimated",
                "date": "2026-05-20",  # after the bloat line date
            }
        ],
    )
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "re-assess" not in result.stderr.lower(), (
        "Expected no nudge when re-assessment is already filed:\n" + result.stderr
    )


# ---------------------------------------------------------------------------
# No false positives on quoted or cited context (TRC-X3)
# ---------------------------------------------------------------------------

def test_no_false_positive_in_quoted_context(tmp_path):
    """A phrase nested in quotes or backtick context does not fire
    (TRC-X3)."""
    project = _make_project(tmp_path)
    _make_task(
        project,
        "quoted-task",
        devlog_lines=[
            # These lines quote or cite the phrase, not report it as an actual
            # scope-bloat event. The hook must not fire on them.
            '    > "more files than Plan estimated" - quoted from spec discussion',
            "    The pattern `more files than Plan estimated` is a scope-bloat phrase",
            "We avoided narrowing scope by keeping everything in one stream",
        ],
        reframes=[],
    )
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "re-assess" not in result.stderr.lower(), (
        "False positive: hook fired on quoted/indented context:\n" + result.stderr
    )


# ---------------------------------------------------------------------------
# The six phrases warn as they did when signals.yml held them
# ---------------------------------------------------------------------------

# The six phrases signals.yml shipped until 9.0.0 (ADR-094). Each
# must give the same reminder line it gave when the hook read them from the
# file.
SIX_PHRASES = [
    "more files than Plan estimated",
    "narrow scope and spawn sibling",
    "file deeper layer as a sibling issue at ship",
    "soften the gate",
    "(carried to ship)",
    "USER TO APPLY",
]


@pytest.mark.parametrize("phrase", SIX_PHRASES)
@pytest.mark.parametrize("prefix", ["", "2026-05-20: ", "2026-05-20 "])
def test_each_phrase_gives_the_same_reminder(tmp_path, phrase, prefix):
    """Each phrase, bare or after a date, gives the reminder line naming
    the devlog line."""
    project = _make_project(tmp_path)
    line = prefix + phrase + " - touched the core module"
    _make_task(project, "phrase-task", devlog_lines=["2026-05-19: Started build", line])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "COMPASS - RE-ASSESSMENT REMINDER" in result.stderr, result.stderr
    assert '! [phrase-task] Scope-bloat signal detected in devlog: "%s"' % line \
        in result.stderr, result.stderr


@pytest.mark.parametrize("phrase", SIX_PHRASES)
def test_each_phrase_is_silent_after_a_reassessment(tmp_path, phrase):
    """A reassessment dated on or after the line suppresses each phrase."""
    project = _make_project(tmp_path)
    _make_task(project, "phrase-task",
               devlog_lines=["2026-05-19: " + phrase],
               reframes=[{"reason": "scope grew", "date": "2026-05-19"}])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "re-assess" not in result.stderr.lower(), result.stderr


@pytest.mark.parametrize("phrase", SIX_PHRASES)
def test_each_phrase_warns_when_dated_after_the_reassessment(tmp_path, phrase):
    """A line dated after the latest reassessment still warns."""
    project = _make_project(tmp_path)
    line = "2026-05-21: " + phrase
    _make_task(project, "phrase-task", devlog_lines=[line],
               reframes=[{"reason": "scope grew", "date": "2026-05-20"}])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert '! [phrase-task] Scope-bloat signal detected in devlog: "%s"' % line \
        in result.stderr, result.stderr


@pytest.mark.parametrize("phrase", SIX_PHRASES)
def test_each_phrase_is_silent_mid_line_or_indented(tmp_path, phrase):
    """A phrase that does not start the line, or an indented line, does not
    warn (TRC-X3)."""
    project = _make_project(tmp_path)
    _make_task(project, "phrase-task",
               devlog_lines=["We noted " + phrase, "    " + phrase])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "re-assess" not in result.stderr.lower(), result.stderr


# ---------------------------------------------------------------------------
# A project's own signals.yml is no longer read (ADR-094)
# ---------------------------------------------------------------------------

def test_a_project_signals_file_is_not_read(tmp_path):
    """A project that kept its own signals.yml, as copied
    governance does, still gets the six phrases, and its own phrases and
    its design_smell list have no effect. The file does not break the hook.
    """
    project = _make_project(tmp_path)
    custom_signals = {
        "version": "1.0.0",
        "scope_bloat_phrases": ["CUSTOM_BLOAT_MARKER_XYZ"],
        "design_smell": ["tests dominated by mocking or setup"],
    }
    with (project / "governance" / "signals.yml").open("w") as fh:
        yaml.safe_dump(custom_signals, fh)

    _make_task(project, "custom-task",
               devlog_lines=["CUSTOM_BLOAT_MARKER_XYZ occurred during build"])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert "re-assess" not in result.stderr.lower(), (
        "The project's own phrase must not warn:\n" + result.stderr)

    _make_task(project, "custom-task",
               devlog_lines=["soften the gate to land it"])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert 'Scope-bloat signal detected in devlog: "soften the gate to land it"' \
        in result.stderr, result.stderr


def test_an_unreadable_project_signals_file_does_not_break_the_hook(tmp_path):
    """A project signals.yml that is not YAML changes nothing."""
    project = _make_project(tmp_path)
    (project / "governance" / "signals.yml").write_text("scope_bloat_phrases: [\n")
    _make_task(project, "bad-signals",
               devlog_lines=["USER TO APPLY the migration"])
    result = _run_hook(project)
    assert result.returncode == 0, result.stderr
    assert 'Scope-bloat signal detected in devlog: "USER TO APPLY the migration"' \
        in result.stderr, result.stderr
