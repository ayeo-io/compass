"""The docs and governance prose speak v2, and the ratchet reaches zero.

These tests assert:

- the last pending surfaces (README, five-minutes, methodology, the
  governance prose) are rewritten and enforced;
- routes/ is the delivery-approach reference docs under approaches/; <!-- vocabulary-scan: allow - names the retired directory these tests assert is gone -->
- the remaining docs prose is in scan.surfaces, enforced and never-pending;
- the worked-example directories carry their v2 change-type names (a
  directory name teaches vocabulary before any file is opened);
- the install.sh plugin-source refusal points at the path the plugin
  source actually uses.
"""
from __future__ import annotations

import re

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def _scan_cfg() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text(
            encoding="utf-8"))["scan"]


def test_the_ratchet_reaches_zero():
    """`TRC-1`: pending_surfaces is empty and the committed baseline with it -
    every user-facing surface is enforced, forever."""
    from test_terminology import PENDING_BASELINE
    assert _scan_cfg()["pending_surfaces"] == [], (
        "pending_surfaces is not empty - the ratchet has not reached zero")
    assert PENDING_BASELINE == frozenset(), (
        "the committed baseline still tolerates a surface")


def test_reference_docs_carry_v2_names():
    """`TRC-2`: approaches/ holds the rubric and the five shape docs under
    v2 names; routes/ is gone; no live surface points at the old path. <!-- vocabulary-scan: allow - names the retired directory this test asserts is gone -->"""
    approaches = REPO_ROOT / "approaches"
    for name in ("rubric.md", "quick-fix.md", "feature.md",
                 "initiative.md", "hotfix.md", "spike.md"):
        assert (approaches / name).is_file(), (
            f"approaches/{name} is missing")
    assert not (REPO_ROOT / "routes").exists(), (
        "routes/ still exists - the reference docs did not rename")
    stale = []
    surfaces = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "AGENTS.md"]
    for pat in ("commands/*.md", "skills/*/SKILL.md", "agents/*.md",
                "templates/**/*.md", "docs/*.md", "governance/*.md",
                "approaches/*.md", "cli/compass_pkg/*.py"):
        surfaces += sorted(REPO_ROOT.glob(pat))
    for path in surfaces:
        if not path.is_file() or path.name in ("system-spec.md", "system-spec-archive.md"):
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if "routes/" in line and "tests/fixtures" not in line:
                stale.append(f"{path.relative_to(REPO_ROOT)}:{lineno}")
    assert not stale, (
        "live surfaces still point at routes/:\n  " + "\n  ".join(stale[:15]))


def test_examples_carry_v2_names():
    """`TRC-3`: the worked-example directories carry v2 change-type names -
    the manual teaches vocabulary from the directory listing."""
    names = {p.name for p in (REPO_ROOT / "examples").iterdir()
             if p.is_dir()}
    expected = {"quick-fix-typo", "feature-api-change",
                "initiative-new-subsystem", "hotfix-regression",
                "spike-technical-unknown", "bdd-adapters"}
    missing = expected - names
    assert not missing, f"missing v2-named examples: {sorted(missing)}"
    v1 = {"express-typo", "standard-api-change", "expedition-new-subsystem"}
    stale = v1 & names
    assert not stale, f"v1-shape-named example dirs remain: {sorted(stale)}"


def test_remaining_docs_are_enforced():
    """`TRC-4`: all six remaining docs are scanned surfaces, and the
    doctrine document is enforced with them."""
    scan = _scan_cfg()
    for f in ("docs/roles-guide.md", "docs/safety-contract.md",
              "docs/security.md", "docs/quickstart.md",
              "docs/portability.md", "docs/routing-deep-dive.md"):
        assert f in scan["surfaces"], f"{f} is not a scanned surface"
    # Asserted as "not scanned", which is the property that matters, rather
    # than as "exempt". `scan.exempt` applies only to files under
    # `scan.surfaces`, and this file is under none, so the test asserts
    # "not scanned".
    reachable = [sfc for sfc in scan["surfaces"]
                 if "docs/system-spec.md".startswith(sfc.rstrip("/") + "/")
                 or sfc == "docs/system-spec.md"]
    assert not reachable, (
        f"docs/system-spec.md is now reachable from {reachable} and would be "
        f"scanned. It is derived at ship time from landed scenarios, so it "
        f"carries whatever words those scenarios used")


def test_install_refusal_points_at_plugin_dir():
    """`TRC-5`: the plugin-source refusal names the path the plugin source
    actually uses - claude --plugin-dir - not /plugin install, which is
    the answer for a project consuming the plugin."""
    text = (REPO_ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "claude --plugin-dir" in text, (
        "install.sh's plugin-source refusal does not name "
        "claude --plugin-dir")
    assert "/plugin install" not in text.split("plugin source detected")[1].split("exit 0")[0] or "claude --plugin-dir" in text.split("plugin source detected")[1].split("exit 0")[0], (
        "the refusal block still sends the plugin source to /plugin install")


# `compass plan lint` is the live spelling. `compass design lint` was
# removed at 4.0.0 and must not be taught anywhere.
RETIRED_CLI = __import__("re").compile(
    r"compass (?:route|backfill|calibration|land-commit)\b"
    r"|compass task (?:lint|receipt|set-status)"
    r"|compass design lint")


# A line carrying the repository's `vocabulary-scan: allow` marker is exempt,
# for the same reason the vocabulary scan honours it: a page that RECORDS a
# removal has to name the removed spelling, or a reader whose script broke
# cannot match the error they got to the row that fixes it. Recording is not
# teaching.
#
# The REASON is mandatory, and the pattern is the vocabulary scan's own, so
# the two stay identical. A bare `vocabulary-scan: allow` with nothing after
# it would be an unconditional skip - any line in any live document could
# silence this guard, with no reason and no count.
#
# Counted as well as reasoned: `MAX_ALLOW_MARKERS` is a ceiling, so the list
# cannot grow quietly. `grep -rn "vocabulary-scan: allow" .` enumerates every
# one with the reason someone wrote for it.
# Imported rather than defined: see tests/allow_marker.py.
from allow_marker import ALLOW_MARKER_RE  # noqa: E402
MAX_ALLOW_MARKERS = 14


def test_no_live_doc_teaches_a_retired_cli_spelling():
    """Code spans are scan-exempt, so a retired CLI verb inside backticks
    or a fenced example survives the vocabulary scan and only reading
    catches it. This sweep reads everything - a cleaned surface never
    teaches a retired spelling."""
    surfaces = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "AGENTS.md",
                REPO_ROOT / "README.md", REPO_ROOT / "examples" / "README.md"]
    for pat in ("commands/*.md", "skills/*/SKILL.md", "agents/*.md",
                "templates/**/*.md", "docs/*.md", "governance/*.md",
                "approaches/*.md"):
        surfaces += sorted(REPO_ROOT.glob(pat))
    hits = []
    for path in surfaces:
        if not path.is_file() or path.name in ("system-spec.md", "system-spec-archive.md"):
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if RETIRED_CLI.search(line) and not ALLOW_MARKER_RE.search(line):
                rel = path.relative_to(REPO_ROOT)
                hits.append(f"{rel}:{lineno}: {line.strip()[:70]}")
    assert not hits, (
        "live surfaces teach retired CLI spellings:\n  "
        + "\n  ".join(hits[:15]))


def _marker_surfaces():
    """Every live document these two guards read."""
    out = [REPO_ROOT / "CLAUDE.md", REPO_ROOT / "AGENTS.md", REPO_ROOT / "README.md"]
    for pat in ("commands/*.md", "skills/*/SKILL.md", "agents/*.md",
                "templates/**/*.md", "docs/*.md", "governance/*.md",
                "approaches/*.md", "schemas/*.md"):
        out += sorted(REPO_ROOT.glob(pat))
    return [p for p in out if p.is_file()]


def test_the_allow_marker_list_stays_short():
    """A marker mechanism nobody counts becomes the wide skip it replaced.

    Each marker is a line two guards no longer read. Raising this number is a
    deliberate act; doing it twice in a release is the signal that the guard
    is measuring the wrong thing rather than that the file is wrong.
    """
    found = []
    for path in _marker_surfaces():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if ALLOW_MARKER_RE.search(line):
                found.append(f"{path.relative_to(REPO_ROOT)}:{n}")
    assert found, (
        "no `vocabulary-scan: allow` markers were found at all - the pattern "
        "has stopped matching, and both guards in this file are now skipping "
        "nothing while reporting clean")
    assert len(found) <= MAX_ALLOW_MARKERS, (
        f"{len(found)} allow markers now exist, over the ceiling of "
        f"{MAX_ALLOW_MARKERS}:\n  " + "\n  ".join(found)
        + "\nEach is a line these guards no longer read. If the list is "
          "growing, the guard is measuring the wrong thing - fix that rather "
          "than raising this number.")
