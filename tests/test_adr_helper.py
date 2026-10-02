"""Tests for the `compass adr new <slug>` subcommand.

Covers:
  `TRC-A3` - compass adr new <slug> creates a numbered ADR file
"""
from __future__ import annotations

from pathlib import Path



# conftest.py defines the project, run_cli and make_task fixtures.
# FRAMEWORK_ROOT / CLI_PATH are also available via conftest


# ---------------------------------------------------------------------------
# `TRC-A3` - creates a numbered ADR file
# ---------------------------------------------------------------------------

def test_creates_numbered_adr(project: Path, run_cli):
    """`TRC-A3`: `compass adr new <slug>` creates ADR-<N+1>-<slug>.md inside
    architecture/decisions/ and registers it in architecture/decisions/README.md.

    When there are N existing ADR-*.md files the new file is numbered N+1.
    """
    # Set up: two existing ADRs so N=2, next is ADR-003
    decisions = project / "architecture" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "ADR-001-first.md").write_text(
        "---\nid: ADR-001\ntitle: First\nstatus: accepted\ndate: 2026-01-01\n"
        "supersedes: ''\nsuperseded_by: ''\n---\n# First\n",
        encoding="utf-8",
    )
    (decisions / "ADR-002-second.md").write_text(
        "---\nid: ADR-002\ntitle: Second\nstatus: proposed\ndate: 2026-01-02\n"
        "supersedes: ''\nsuperseded_by: ''\n---\n# Second\n",
        encoding="utf-8",
    )

    result = run_cli("adr", "new", "example-decision", cwd=project)
    assert result.returncode == 0, \
        f"compass adr new should exit 0, got {result.returncode}\n{result.combined}"

    # The new file must exist
    new_file = decisions / "ADR-003-example-decision.md"
    assert new_file.exists(), \
        f"Expected {new_file} to be created; decisions dir: {list(decisions.iterdir())}"

    # It must contain the required frontmatter fields
    text = new_file.read_text(encoding="utf-8")
    assert "id:" in text,            "frontmatter must include id:"
    assert "title:" in text,         "frontmatter must include title:"
    assert "status:" in text,        "frontmatter must include status:"
    assert "date:" in text,          "frontmatter must include date:"
    assert "supersedes:" in text,    "frontmatter must include supersedes:"
    assert "superseded_by:" in text, "frontmatter must include superseded_by:"

    # ADR-003 must appear in the README
    readme = decisions / "README.md"
    assert readme.exists(), "README.md must be created/updated in decisions/"
    readme_text = readme.read_text(encoding="utf-8")
    assert "ADR-003" in readme_text, \
        f"README.md must list ADR-003; content:\n{readme_text}"


def test_adr_numbering_from_zero(project: Path, run_cli):
    """When decisions/ is empty, the first ADR is numbered 001."""
    decisions = project / "architecture" / "decisions"
    decisions.mkdir(parents=True)

    result = run_cli("adr", "new", "initial-decision", cwd=project)
    assert result.returncode == 0, result.combined

    new_file = decisions / "ADR-001-initial-decision.md"
    assert new_file.exists(), \
        f"Expected ADR-001-initial-decision.md; got: {list(decisions.iterdir())}"


def test_adr_readme_updated_multiple_times(project: Path, run_cli):
    """Creating two ADRs back to back both appear in the README."""
    decisions = project / "architecture" / "decisions"
    decisions.mkdir(parents=True)

    run_cli("adr", "new", "first", cwd=project)
    run_cli("adr", "new", "second", cwd=project)

    readme = decisions / "README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "ADR-001" in text
    assert "ADR-002" in text


# ---------------------------------------------------------------------------
# The row goes in the table, not at the end of the file (#272)
# ---------------------------------------------------------------------------

_INDEX = """# Decisions

## Index

| ID | Title | Status |
|---|---|---|
| [ADR-001](ADR-001-first.md) | First | accepted |

## Authoring a new ADR

Use `compass adr new <slug>`.
"""


def _decisions_with_index(project: Path) -> Path:
    decisions = project / "architecture" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "ADR-001-first.md").write_text(
        "---\nid: ADR-001\ntitle: First\nstatus: accepted\ndate: 2026-01-01\n"
        "supersedes: ''\nsuperseded_by: ''\n---\n# First\n", encoding="utf-8")
    (decisions / "README.md").write_text(_INDEX, encoding="utf-8")
    return decisions


def test_the_row_goes_after_the_last_adr_row(project: Path, run_cli):
    decisions = _decisions_with_index(project)
    result = run_cli("adr", "new", "second-decision", cwd=project)
    assert result.returncode == 0, result.combined
    lines = (decisions / "README.md").read_text(encoding="utf-8").splitlines()
    first = next(i for i, l in enumerate(lines) if l.startswith("| [ADR-001]"))
    assert lines[first + 1].startswith("| [ADR-002](ADR-002-second-decision.md) |"), lines
    assert lines[-1] == "Use `compass adr new <slug>`.", "nothing is appended after the last section"


def test_the_row_goes_under_an_empty_table(project: Path, run_cli):
    decisions = project / "architecture" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "README.md").write_text(
        "# Decisions\n\n| ID | Title | Status |\n|---|---|---|\n\n## Later\n\nText.\n",
        encoding="utf-8")
    result = run_cli("adr", "new", "first-decision", cwd=project)
    assert result.returncode == 0, result.combined
    lines = (decisions / "README.md").read_text(encoding="utf-8").splitlines()
    sep = lines.index("|---|---|---|")
    assert lines[sep + 1].startswith("| [ADR-001](ADR-001-first-decision.md) |"), lines
    assert lines[-1] == "Text."
