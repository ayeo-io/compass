"""8.0.0 ships the delegation rework, and the legacy readers stay until 9.0.0.

8.0.0 was the version at which Compass promised to stop reading old words,
old approach names, copied 5.x governance, the generated governance views and
`.compass/config.yml`. The owner moved that end to 9.0.0 on 25 October 2026.
Two places act on the date in code: `waivers.py` turns a LEGACY waiver into an
error from it, and `old_names.removal_problems()` reports each row as overdue.
A version bump without the date move would do both.

The scenarios, `TRC-001` to `TRC-005`, are in
release-8-0-0/acceptance-criteria.md.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import test_version_consistency as versions  # noqa: E402
import waiver_fixtures as fx  # noqa: E402
from compass_pkg import old_names, waivers  # noqa: E402

RELEASE = "8.0.0"

# Text that records what was promised at the time, and stays as written.
_HISTORY = (
    "docs/compass/", "docs/system-spec", "governance/decisions/",
    "architecture/decisions/", "tests/", "examples/", ".compass/",
)
# A phrase that ends an old form at 8.0.0, in either order, across a line
# break or a markup character.
_ENDS_AT = re.compile(
    r"(?:\b(?:until|removed[_ ]in|ends? at|end at|goes with the views at|"
    r"before|from|version is)\W{0,6}8\.0\.0)"
    r"|(?:8\.0\.0\W{0,3}(?:refuses|stops reading|removes(?! no\b)))", re.I)
# The one true sentence about history: 7.0.0 kept the readers until 8.0.0.
_TRUE_HISTORY = "kept until 8.0.0 by\nthe 7.0.0 release"


def stale_lines(text: str) -> list[str]:
    """Each line of `text` where an old form ends at 8.0.0."""
    text = text.replace(_TRUE_HISTORY, "")
    found = []
    for m in _ENDS_AT.finditer(text):
        no = text.count("\n", 0, m.start()) + 1
        found.append(f"{no}: {' '.join(m.group(0).split())}")
    return found


def test_trc_001_every_version_location_says_8_0_0():
    """Scenario `TRC-001`: every place that states the version says 8.0.0."""
    assert versions.EXPECTED_VERSION == RELEASE
    assert (ROOT / "VERSION").read_text(encoding="utf-8").strip() == RELEASE
    assert versions._read_compass_version_constant() == RELEASE
    assert versions._read_core_version_constant() == RELEASE
    assert versions._read_smoke_test_version() == RELEASE
    for rel in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        found = re.findall(r'"version":\s*"([^"]+)"', text)
        assert found and set(found) == {RELEASE}, (rel, found)


def test_trc_002_every_legacy_reader_still_reads_at_8_0_0(monkeypatch):
    """Scenario `TRC-002`: at 8.0.0 no old-name row is overdue, and a LEGACY
    waiver gives the warning W-LEGACY, not an error."""
    assert old_names.removal_problems(RELEASE) == []
    assert all(r["removed_in"] == "9.0.0" for r in old_names.rows())
    monkeypatch.setattr(waivers, "COMPASS_VERSION", RELEASE)
    found, faults = waivers.find(fx.severity_layer(
        fx.project_waiver(approved_by="LEGACY", approved_on=None)), "project")
    assert not faults, faults
    [finding] = waivers.check_shape(found[0], fx.TODAY)
    assert (finding.code, finding.level) == ("W-LEGACY", "warning"), finding


def test_trc_003_no_current_text_ends_an_old_form_at_8_0_0():
    """Scenario `TRC-003`: no message, comment or current document says an old
    form is read until, or removed at, 8.0.0."""
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                           text=True, check=True).stdout.split()
    hits = []
    for rel in files:
        if rel.startswith(_HISTORY) or not (ROOT / rel).is_file():
            continue
        if rel.endswith(("package-lock.json", "shipped-releases.yml")):
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        hits += [f"{rel}:{line}" for line in stale_lines(text)]
    assert not hits, "these still end an old form at 8.0.0:\n" + "\n".join(hits)


def test_trc_003_the_search_finds_each_form_of_the_old_date():
    """Scenario `TRC-003`: the search catches each way the old date was
    written, so a passing run means something."""
    planted = [
        "the old word is read until 8.0.0.",
        "a row with removed_in: 8.0.0",
        "advisory, and 8.0.0 refuses it.",
        "# for the whole 7.x line. From 8.0.0 it is an error.",
        "into `compass.yml`, and 8.0.0 stops reading it.",
        "| `W-LEGACY` | warning before 8.0.0, error from 8.0.0 |",
        "the old word is read until\n8.0.0. The original is kept.",
        "once the package version is 8.0.0",
    ]
    for text in planted:
        assert stale_lines(text), text
    assert stale_lines("8.0.0 is a major release.") == []
    assert stale_lines("8.0.0 removes no reader.") == []
    assert stale_lines("kept until 8.0.0 by\nthe 7.0.0 release, are kept") == []


def test_trc_004_a_decision_moves_the_date():
    """Scenario `TRC-004`: one entry supersedes the 8.0.0 decision and keeps
    the readers until 9.0.0."""
    entries = [p for p in (ROOT / "governance" / "decisions").glob("*.md")
               if "legacy-readers-readable-until-8-0-0" in p.read_text(encoding="utf-8")
               and "## Supersedes" in p.read_text(encoding="utf-8")
               and not p.name.endswith("legacy-readers-readable-until-8-0-0.md")]
    assert len(entries) == 1, entries
    assert "9.0.0" in entries[0].read_text(encoding="utf-8")


def test_trc_005_the_upgrade_guide_is_named_for_8_0_0():
    """Scenario `TRC-005`: the guide and the release section name 8.0.0."""
    guide = ROOT / "docs" / "upgrade-8-0-0.md"
    assert guide.is_file()
    assert "8.0.0" in guide.read_text(encoding="utf-8").splitlines()[0]
    assert not (ROOT / "docs" / "upgrade-next.md").exists()
    releasing = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert releasing.count("### What changed at 8.0.0") == 1
