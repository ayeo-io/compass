"""The partial-bump guard covers every place a version lives.

This test finds every version string in the published surfaces and asserts
the guard has a case for each, so the list of locations cannot go out of
date.

`tests/test_version_consistency.py` parametrises the locations it checks. It
covered five; there are seven. `cli/compass_pkg/core.py` holds the constant
`cli/compass` asserts equality against, and the smoke-test banner is the one
`docs/releasing.md` calls "the one that gets forgotten, because it lives in
prose rather than in a manifest". Neither was in the list.

Three documents also disagreed about the count: the guard's docstring said
five, `docs/releasing.md` said six, and there were seven.

This is the fourth instance in one release of a check reporting success while
checking nothing - alongside the smoke-test guard that searched for a retired
spelling, an evidence record with no identity, and `OLD_VERSIONS`, which no
code read and which a missing comma had silently corrupted. A check that
cannot fail gives false confidence, which is worse than no check.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
GUARD = ROOT / "tests" / "test_version_consistency.py"

# Every file that publishes the version, and how to find it in that file.
# A location added here without a matching case in the guard fails `TRC-1`.
PUBLISHED_LOCATIONS = {
    "VERSION": None,
    ".claude-plugin/plugin.json": "version",
    ".claude-plugin/marketplace.json": "version",
    "cli/compass": "COMPASS_VERSION",
    "cli/compass_pkg/core.py": "COMPASS_VERSION",
    "docs/install-smoke-test.md": "compass",
}


def _declared_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_trc_1_every_published_location_reports_the_declared_version():
    """The property that matters, checked against the files themselves.

    Independent of how any guard is written: if a published file carries a
    version string that is not the declared one, a release shipped a partial
    bump.
    """
    version = _declared_version()
    stale = []
    compared = {rel: 0 for rel in PUBLISHED_LOCATIONS}
    for rel in PUBLISHED_LOCATIONS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for m in re.finditer(r"\b\d+\.\d+\.\d+\b", text):
            found = m.group(0)
            # Match the neighbouring token, not the whole line: the
            # smoke-test banner line contains "schema", and a line filter
            # drops its version.
            # An explicit, individually-justified exemption for a version
            # the file talks about rather than publishes. No published
            # surface carries an exemption now; the mechanism stays for the
            # next historical reference.
            # tests/test_version_guard_exemptions.py counts them so the list
            # cannot grow into the wide skip pattern this guard's history
            # warns about.
            line_start = text.rfind("\n", 0, m.start()) + 1
            line_end = text.find("\n", m.end())
            line = text[line_start:line_end if line_end != -1 else len(text)]
            if "version-guard: allow" in line:
                continue

            before = text[max(0, m.start() - 24):m.start()]
            after = text[m.end():m.end() + 12]
            if "PyYAML" in before or "python" in before.lower():
                continue
            if "schema" in before[-9:] or after.startswith(")"):
                # "issue schema 2.0" and the ")" that closes it: the schema
                # version, not the CLI's.
                if "schema" in before[-9:]:
                    continue
            compared[rel] += 1
            if found != version:
                lineno = text.count("\n", 0, m.start()) + 1
                stale.append(f"{rel}:{lineno}: {found} (declared: {version})")
    assert not stale, (
        "a published surface carries a version that is not the declared "
        "one - a partial bump:\n  " + "\n  ".join(stale)
    )
    # A filter that drops every candidate makes a guard that cannot fail,
    # so check each location still has something to compare.
    silent = sorted(rel for rel, n in compared.items() if n == 0)
    assert not silent, (
        "these locations yielded no version comparison at all, so a wrong "
        "version in them would pass unnoticed:\n  " + "\n  ".join(silent)
    )


def test_trc_2_the_guard_has_a_case_for_every_published_location():
    """The guard's own coverage, so it cannot quietly cover fewer than exist."""
    guard = GUARD.read_text(encoding="utf-8")
    missing = [rel for rel in PUBLISHED_LOCATIONS if rel not in guard]
    assert not missing, (
        "tests/test_version_consistency.py has no case for these published "
        "version locations, so a partial bump there would pass:\n  "
        + "\n  ".join(missing)
    )


def test_trc_3_the_guard_declares_no_constant_nothing_reads():
    """The guard declares no constant that no code reads: an unread
    constant cannot fail and hides errors such as a missing comma."""
    guard = GUARD.read_text(encoding="utf-8")
    # The declaration, not the word. The comment recording why it went is
    # worth keeping; a set nobody reads is not.
    declared = re.search(r"^OLD_VERSIONS\s*=", guard, re.MULTILINE)
    assert not declared, (
        "OLD_VERSIONS was removed because nothing read it and a missing "
        "comma had silently corrupted its contents. If a use for it comes "
        "back, give it one in the same change - do not reintroduce a set "
        "that only exists to look careful."
    )
