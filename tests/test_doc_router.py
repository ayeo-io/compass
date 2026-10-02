"""Every code area names its one owning doc, and every doc is indexed: the
owning-doc-router issue, GitHub issue #253.

The table lives in `docs/README.md` under "## Owning docs", beside the
index. It is not in `CLAUDE.md`, which ships to adopters and must not point
at docs about developing Compass (`tests/test_prompt_layer.py`). Each row names a
code or governance area and the one doc that owns its facts; the rule is
"change the code, change the doc, same commit". `docs/README.md` indexes
the docs under `docs/`. Facts drift when nothing says which doc owns them,
and a new doc goes unread when nothing links it.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADING = "## Owning docs"


def _table_rows(root: Path, text: str | None = None) -> list:
    """(area paths, owning doc paths) for each row of the owning-docs table,
    read from `text` when given, else from the root's docs/README.md."""
    if text is None:
        text = (root / "docs" / "README.md").read_text(encoding="utf-8")
    assert HEADING in text, f"docs/README.md has no '{HEADING}' section"
    section = text.split(HEADING, 1)[1].split("\n## ", 1)[0]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= {"-", " ", ":"} or cells[0] == "Area":
            continue
        rows.append((re.findall(r"`([^`]+)`", cells[0]),
                     re.findall(r"`([^`]+)`", cells[1])))
    return rows


def _missing_paths(root: Path, text: str | None = None) -> list:
    """Paths the table names that do not exist."""
    missing = []
    for areas, owners in _table_rows(root, text):
        for rel in areas + owners:
            if not (list(root.glob(rel)) if "*" in rel else (root / rel).exists()):
                missing.append(rel)
    return missing


def _unindexed_docs(root: Path) -> list:
    """Docs directly under docs/ that neither the index nor the table names."""
    index = (root / "docs" / "README.md").read_text(encoding="utf-8").split(HEADING, 1)[0]
    owned = {p for _, owners in _table_rows(root) for p in owners}
    return sorted(
        f"docs/{p.name}" for p in (root / "docs").glob("*.md")
        if p.name != "README.md" and p.name not in index and f"docs/{p.name}" not in owned)


def test_the_owning_docs_table_has_rows():
    """The table exists and is not a stub."""
    assert len(_table_rows(ROOT)) >= 15, _table_rows(ROOT)


def test_every_path_in_the_table_exists():
    """A row naming a moved or deleted file is stale."""
    assert not _missing_paths(ROOT), _missing_paths(ROOT)


def test_every_doc_is_indexed():
    """A doc under docs/ that nothing links goes unread."""
    assert not _unindexed_docs(ROOT), _unindexed_docs(ROOT)


def test_the_checks_name_a_planted_fault(tmp_path):
    """Both checks can fail. Against the real repository, a planted table
    row naming a missing file is the only missing path reported, and a doc
    planted in a copy of docs/ without an index line is reported by name."""
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    planted = (readme.rstrip()
               + "\n| `cli/compass_pkg/no_such_module.py` | `docs/quickstart.md` |\n")
    assert _missing_paths(ROOT, planted) == ["cli/compass_pkg/no_such_module.py"]

    copy = tmp_path / "repo"
    shutil.copytree(ROOT / "docs", copy / "docs",
                    ignore=shutil.ignore_patterns("compass", "analysis", "proposals"))
    (copy / "docs" / "planted-unindexed.md").write_text("# Planted\n")
    assert _unindexed_docs(copy) == ["docs/planted-unindexed.md"]
