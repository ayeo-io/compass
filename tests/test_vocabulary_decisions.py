"""The decisions behind the vocabulary and CLI renames are recorded, and the
vocabulary file, glossary and guards agree with them.

The scenarios are group G of the issue `vocabulary-and-cli-renames`. Each
increment of that issue adds the tests for its own scenarios to this file.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADRS = ROOT / "architecture" / "decisions"
LEDGER = ROOT / "governance" / "decisions"

# The record that amends the frozen vocabulary (ADR-012) and the rule for an
# unobserved adopter (ADR-024), and the record for the derived lifecycle.
VOCABULARY_SLUG = "vocabulary-and-cli-naming"
LIFECYCLE_SLUG = "the-issue-lifecycle-is-derived-from-records"

NEW_LEDGER = [
    "2026-10-08-the-living-spec-heading-word-is-completed",
    "2026-10-08-a-cli-spelling-is-released-only-when-a-tag-holds-it",
]

# The records that use a retired word and are read through the new names.
READ_THROUGH = ["ADR-008", "ADR-026", "ADR-034", "ADR-036", "ADR-038"]


def _record(slug: str) -> Path | None:
    found = sorted(ADRS.glob(f"ADR-*-{slug}.md"))
    return found[0] if len(found) == 1 else None


def _section(text: str, heading: str) -> str:
    """The body of a `## heading` section, up to the next `## `."""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    return m.group(1) if m else ""


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _base_ref(root: Path) -> str | None:
    """The commit the branch started from, or None when there is no main."""
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=root,
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def changed_since(root: Path, base: str, paths: list[str]) -> list[str]:
    """The paths whose content differs from `base`, committed or not."""
    r = subprocess.run(["git", "diff", "--name-only", base, "--", *paths],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def alias_section_problems(text: str) -> list[str]:
    """What the alias section of the vocabulary record fails to say."""
    section = _section(text, "Aliases")
    wanted = {
        "7.0.0": "the end of the aliases",
        "release tag": "a spelling counts as released only when a tag holds it",
        "renamed": "aliases cover renamed CLI verbs",
        "no alias": "an unreleased spelling gets no alias",
        "read through": "vocabulary values are read through the rename tables",
        "not redirected": "a vocabulary value is not redirected",
    }
    if not section:
        return ["no `## Aliases` section"]
    return [f"the alias section does not say {why} ({needle!r})"
            for needle, why in wanted.items() if needle not in section]


# --- the records exist and the amended ones are unchanged -------------------

def test_vr_g1_one_new_record_amends_the_freeze_and_the_adopter_rule():
    path = _record(VOCABULARY_SLUG)
    assert path is not None, (
        f"expected exactly one architecture/decisions/ADR-*-{VOCABULARY_SLUG}.md")
    text = path.read_text(encoding="utf-8")
    front = _frontmatter(text)
    number = int(front["id"].split("-")[1])
    assert number > 43, "the record takes a number after ADR-043"
    assert front["status"] == "accepted"
    assert front["supersedes"] == "" and front["superseded_by"] == ""
    assert re.search(r"[Aa]mends ADR-012", text)
    assert "ADR-024" in text
    assert re.search(r"[Aa]mends ADR-012[^\n]*ADR-024|ADR-024[^\n]*amend",
                     text, re.I), "the record says it amends both"
    for heading in ("Context", "Decision", "Alternatives considered",
                    "Consequences", "References"):
        assert _section(text, heading).strip(), f"empty section: {heading}"
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    row = next((ln for ln in index.splitlines()
                if f"[{front['id']}]" in ln), "")
    assert "amends ADR-012" in row and "ADR-024" in row, (
        "the index row names the records this one amends")


def test_vr_g1_the_amended_records_are_unchanged_from_main():
    base = _base_ref(ROOT)
    if base is None:
        pytest.skip("no main branch to compare with")
    names = [p.name for p in ADRS.glob("ADR-012-*.md")]
    names += [p.name for p in ADRS.glob("ADR-024-*.md")]
    assert len(names) == 2
    rel = [f"architecture/decisions/{n}" for n in names]
    assert changed_since(ROOT, base, rel) == [], (
        "a merged decision record never changes; amend it with a new record")


def test_vr_g1_the_unchanged_check_reports_an_edit(tmp_path):
    """Plant an edit: the check must name the file."""
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (tmp_path / "ADR-012.md").write_text("one\n")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True).stdout.strip()
    assert changed_since(tmp_path, base, ["ADR-012.md"]) == []
    (tmp_path / "ADR-012.md").write_text("two\n")
    assert changed_since(tmp_path, base, ["ADR-012.md"]) == ["ADR-012.md"]


def test_vr_g1_the_record_reads_older_records_through_the_new_names():
    path = _record(VOCABULARY_SLUG)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    for adr in READ_THROUGH:
        assert adr in text, f"the record does not say how {adr} now reads"


def test_vr_g1_the_lifecycle_record_and_the_ledger_entries_exist():
    path = _record(LIFECYCLE_SLUG)
    assert path is not None, (
        f"expected exactly one architecture/decisions/ADR-*-{LIFECYCLE_SLUG}.md")
    text = path.read_text(encoding="utf-8")
    assert _frontmatter(text)["status"] == "accepted"
    assert "schema_version" in text and "3.0" in text
    for slug in NEW_LEDGER:
        entry = LEDGER / f"{slug}.md"
        assert entry.is_file(), f"missing ledger entry {slug}"
        body = entry.read_text(encoding="utf-8")
        for heading in ("Decided by", "Date", "Supersedes", "Decision", "Why",
                        "Evidence"):
            assert _section(body, heading).strip(), (
                f"{slug}: empty section {heading}")


# --- the alias section limits aliases ---------------------------------------

def test_vr_g2_the_alias_section_limits_aliases_and_says_values_are_read():
    path = _record(VOCABULARY_SLUG)
    assert path is not None
    assert alias_section_problems(path.read_text(encoding="utf-8")) == []


def test_vr_g2_the_alias_check_reports_a_section_that_says_too_little():
    bad = "## Aliases\n\nEvery retired word keeps an alias.\n"
    problems = alias_section_problems(bad)
    assert any("7.0.0" in p for p in problems)
    assert any("not redirected" in p for p in problems)
    assert alias_section_problems("## Decision\n\nx\n") == [
        "no `## Aliases` section"]
