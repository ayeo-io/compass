"""Id prefixes are vocabulary, and they have somewhere to be looked up.

Compass artifacts are dense with short codes - `TRC-A1`, INT-1, EV-003, `DD-2`,
BF-1, RP-FLOOR-006 - and every prefix has a `governance/terminology.yml`
entry a reader can look up.

`RG-` was renamed to `RP-` because it said *guardrail* for something that is
not one of the five hard rules. `FLOOR` covers only entries that raise a
minimum; an entry that only attaches a gate is not a floor, so a glossary
could not define `FLOOR` honestly while the two shared a name.

See ADR-016 (id codes are part of the frozen vocabulary). Spec:
docs/system-spec.md.
"""

# These tests read the detail `compass approach evaluate --verbose` prints:
# provenance, per-stage weights, gate list, effect lines.
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(ROOT / "tests"))
from archive import archive_root  # noqa: E402
CLI = ROOT / "cli" / "compass"
TERMINOLOGY = ROOT / "governance" / "terminology.yml"
GLOSSARY = ROOT / "docs" / "glossary.md"
ROUTING = ROOT / "governance" / "routing-policy.yml"

# Surfaces a reader actually meets a code on. The archive is excluded: it is
# historical record, and it keeps the ids that really fired.
CODE_SURFACES = ("templates", "commands", "skills", "docs", "governance",
                 "agents", "approaches", "schemas")

PREFIX_RE = re.compile(r"\b([A-Z]{2,4})-(?:[A-Z]{2,}-)?\d")

# Standards references that happen to look like Compass ids. Not vocabulary,
# and defining them would be worse than not: the glossary would claim
# authorship of somebody else's numbering.
NOT_COMPASS_IDS = {"ISO", "SHA", "RFC", "UTF"}

# docs/system-spec.md is DERIVED from the issue archive, so it inherits every
# per-issue scenario and intent id ever written - GL-, SR-, SS- and so on.
# Those are an issue's local numbering, not framework vocabulary, and the
# archive that produced them is exempt for the same reason.
DERIVED_FROM_ARCHIVE = {"docs/system-spec.md", "docs/system-spec-archive.md",
                        "docs/glossary.md"}


def _vocab() -> dict:
    return yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))


def _terms() -> set[str]:
    terms = _vocab()["terms"]
    if isinstance(terms, dict):
        return set(terms)
    return {e["term"] for e in terms if isinstance(e, dict) and e.get("term")}


def _codes() -> dict:
    codes = _vocab().get("codes") or {}
    if isinstance(codes, list):
        return {e["code"]: e for e in codes if isinstance(e, dict)}
    return codes


def _prefixes_in_use() -> set[str]:
    """Derived from the repository, never from a maintained list.

    A hand-kept list of prefixes reads as complete whatever it omits.
    Deriving means a prefix introduced without a definition fails the build
    on arrival rather than years later.
    """
    # Read in Python rather than shelling to `git grep -E`: its ERE has no
    # \b and no non-capturing groups, so the same pattern matched "HIRD-P"
    # inside "THIRD-PARTY" and produced nonsense prefixes.
    listing = subprocess.run(
        ["git", "ls-files", "--", *CODE_SURFACES],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.split()
    found = set()
    for rel in listing:
        if rel in DERIVED_FROM_ARCHIVE:
            continue
        path = ROOT / rel
        if path.suffix not in (".md", ".yml", ".yaml", ".json"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        found.update(m.group(1) for m in PREFIX_RE.finditer(text)
                     if m.group(1) not in NOT_COMPASS_IDS)
    return found


# --------------------------------------------------------------------------
# Group A - the missing terms
# --------------------------------------------------------------------------

@pytest.mark.parametrize("term", ["traceability", "intent", "router"])
def test_the_missing_terms_are_defined(term):
    """Each names something the code depends on, and none was in the vocabulary.

    `TRC-` is the most-used prefix in the repository and names traceability.
    `/compass:intent` is a live command. `router` is a live agent, and the
    word that replaced the banned one.
    """
    assert term in _terms(), (
        f"{term!r} is not in governance/terminology.yml's terms:, though the "
        f"framework uses it in a command, an agent name, or its most-used id "
        f"prefix"
    )


# --------------------------------------------------------------------------
# Group B - the codes section
# --------------------------------------------------------------------------

def test_every_prefix_in_use_is_defined():
    codes = _codes()
    assert codes, "governance/terminology.yml has no codes: section"

    in_use = _prefixes_in_use()
    assert in_use, "no id prefixes found - the detector is broken, not the repo"

    undefined = sorted(in_use - set(codes))
    assert not undefined, (
        f"id prefix(es) used in shipped artifacts with no definition: "
        f"{undefined}. Every code a reader can meet needs an entry."
    )

    for code, entry in codes.items():
        for field in ("means", "referent", "appears_in"):
            assert entry.get(field), (
                f"codes.{code} has no {field!r} - the three fields are what "
                f"make an entry useful rather than decorative"
            )


# --------------------------------------------------------------------------
# Group C - the derived glossary
# --------------------------------------------------------------------------

def test_the_glossary_is_derived_from_the_source():
    assert GLOSSARY.is_file(), "docs/glossary.md does not exist"
    text = GLOSSARY.read_text(encoding="utf-8")

    assert "generated" in text.lower(), (
        "the glossary does not say it is generated, so a reader may edit it "
        "and lose the edit at the next ship"
    )
    assert "governance/terminology.yml" in text, (
        "the glossary does not name its source"
    )

    for code in _codes():
        assert re.search(rf"\b{re.escape(code)}-\b|`{re.escape(code)}-`", text), (
            f"the glossary has no entry for the code {code!r}"
        )
    for term in _terms():
        assert term in text, f"the glossary has no entry for the term {term!r}"


def test_the_drift_guard_catches_a_stale_page(tmp_path):
    """The derived page and its source must be provably in step.

    Checked by regenerating into a temporary location and comparing, so the
    guard tests the generator's current output rather than a stored hash that
    someone must remember to update.
    """
    result = subprocess.run(
        [sys.executable, str(CLI), "_derive-glossary", "--internal",
         "--out", str(tmp_path / "glossary.md")],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, (
        f"could not regenerate the glossary:\n{result.stdout}{result.stderr}"
    )
    fresh = (tmp_path / "glossary.md").read_text(encoding="utf-8")
    committed = GLOSSARY.read_text(encoding="utf-8")
    assert fresh == committed, (
        "docs/glossary.md is stale - governance/terminology.yml has changed "
        "since it was derived. Re-run the derivation and commit the page."
    )


def test_the_cli_renders_a_code():
    one = subprocess.run(
        [sys.executable, str(CLI), "terminology", "TRC"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert one.returncode == 0, one.stdout + one.stderr
    assert "traceability" in one.stdout.lower(), (
        f"`compass terminology TRC` does not render the code:\n{one.stdout}"
    )

    listing = subprocess.run(
        [sys.executable, str(CLI), "terminology"],
        cwd=ROOT, capture_output=True, text=True, timeout=60,
    )
    assert "TRC" in listing.stdout, (
        "the terminology listing does not include codes, so an agent reading "
        "it sees only half the vocabulary"
    )


# --------------------------------------------------------------------------
# Group D - the routing ids
# --------------------------------------------------------------------------

def _routing_rules() -> list[dict]:
    doc = yaml.safe_load(ROUTING.read_text(encoding="utf-8"))
    rules = []
    for block in ("routing_strategies", "routing_guardrails"):
        section = doc.get(block) or {}
        for key, entries in section.items():
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and e.get("id"):
                        rules.append({"block": key, **e})
    return rules


def test_routing_ids_are_rp_and_kinds_are_distinct():
    rules = _routing_rules()
    assert rules, "no routing rule ids found - the reader is broken"

    stale = sorted(r["id"] for r in rules if r["id"].startswith(("RG-", "RS-")))
    assert not stale, (
        f"routing rule id(s) still say guardrail or strategy rather than "
        f"routing policy: {stale}. `guardrail` is a frozen term meaning one "
        f"of the five hard rules; a routing rule is not one of them."
    )

    for r in rules:
        assert r["id"].startswith("RP-"), f"unexpected id prefix: {r['id']}"

    # A floor raises a lower bound on process weight. An entry that only
    # attaches a gate does not, and must not borrow the word.
    for r in rules:
        raises = any(k in r for k in
                     ("force_minimum_route", "require_phase", "require_skill",
                      "never_skip"))
        adds_only = "add_gate" in r and not raises
        if adds_only:
            assert "REQUIRE" in r["id"], (
                f"{r['id']} only attaches a gate and raises no minimum, but "
                f"its id says FLOOR. That is the vague definition this work "
                f"exists to remove."
            )
        if raises:
            assert "FLOOR" in r["id"], (
                f"{r['id']} raises a minimum but its id does not say FLOOR"
            )


def _probe_project(tmp_path):
    """A throwaway project with one cross-cutting issue.

    Built here rather than read from `.compass/work/`, which is gitignored and
    therefore absent from every clean clone - including the one continuous
    integration checks out.
    """
    import shutil
    manifest = tmp_path / ".compass" / "work" / "probe"
    manifest.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (manifest / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: "probe"\ncreated: "2026-08-13"\n'
        'status: active\nassessment:\n  risk: cross-cutting\n'
        '  familiarity: brownfield-mapped\n  size: large\n  goal: delivery\n'
        '  role: engineer\n  labels: [auth]\n', encoding="utf-8")
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    return tmp_path


def test_a_gate_adder_reports_its_kind_as_requirement(tmp_path):
    """The kind follows the effect, not the block the entry sits in.

    Every entry in the `floors:` block was reported as `kind: floor`,
    including the four that only attach a gate. After the id rename that
    printed "[RP-REQUIRE-003] floor:" on screen and wrote the same
    contradiction into the manifest - the id saying one thing and the kind
    saying the other.
    """
    r = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "probe"],
        cwd=str(_probe_project(tmp_path)), capture_output=True, text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    # Asserts the id and the kind share a line, in either order.
    gate_adder = [ln for ln in r.stdout.splitlines() if "RP-REQUIRE-003" in ln]
    assert gate_adder, f"RP-REQUIRE-003 did not fire:\n{r.stdout}"
    assert all("requirement" in ln for ln in gate_adder), (
        f"a rule that only attaches a gate still reports itself as a floor:\n"
        + "\n".join(gate_adder)
    )
    mislabelled = [ln for ln in r.stdout.splitlines()
                   if "floor" in ln and "RP-FLOOR" not in ln
                   and "RP-" in ln]
    assert not mislabelled, (
        f"a rule reports kind floor without a FLOOR id:\n" + "\n".join(mislabelled)
    )


def test_the_rename_does_not_change_any_computed_approach(tmp_path):
    """The ids are data the evaluator copies; renaming must compute the same.

    One test asserts two of these ids by value, so check the computed
    output rather than assume the rename changes nothing.
    """
    manifest = tmp_path / ".compass" / "work" / "probe"
    manifest.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (manifest / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: "probe"\ncreated: "2026-08-13"\n'
        'status: active\nassessment:\n  risk: cross-cutting\n'
        '  familiarity: brownfield-mapped\n  size: large\n  goal: delivery\n'
        '  role: engineer\n  labels: [auth]\n', encoding="utf-8")
    import shutil
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")

    r = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "probe"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=120,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    out = r.stdout
    assert "full" in out, f"the computed approach changed:\n{out}"
    assert "verify.architecture" in out, (
        f"the fitness gate is no longer added on a cross-cutting change - the "
        f"rename changed behaviour:\n{out}"
    )


def test_the_archive_is_untouched():
    """Historical records keep the id that actually fired.

    Checked against the working tree, because `.compass/work/` is gitignored
    and `git diff` over it is always empty.

    The archive holds records naming the pre-rename routing ids. Rewriting one
    would make the audit trail say something that did not happen.
    """
    archive = archive_root() / ".compass" / "work"
    if not archive.is_dir():
        pytest.skip("no archive on this checkout - it is gitignored")

    retired = []
    for manifest in archive.glob("*/manifest.yml"):
        text = manifest.read_text(encoding="utf-8")
        if "RG-" in text or "RS-" in text:
            retired.append(manifest.parent.name)

    assert retired, (
        "no archived manifest records a pre-rename routing id. Either the "
        "archive was rewritten by the rename - which it must not be, since a "
        "record keeps the id that fired - or this check is looking in the "
        "wrong place and can no longer fail."
    )


# --------------------------------------------------------------------------
# Group E - the follow-up drift
# --------------------------------------------------------------------------

def test_follow_up_surfaces_match_the_schema():
    """The manifest has said follow_ups/outstanding/resolved since the rename."""
    template = (ROOT / "templates" / "verification-report.md").read_text(
        encoding="utf-8")
    assert "BF-" not in template, (
        "templates/verification-report.md still uses the retired follow-up id "
        "prefix. It reads `(follow-up: BF-<id>)` - v2 tag word, v1 id, same "
        "line."
    )
    assert "FU-" in template, (
        "templates/verification-report.md does not use the live follow-up id "
        "prefix"
    )


def test_the_parser_still_reads_the_retired_tag():
    """The control: ADR-006 keeps the read side tolerant.

    Archived verification reports use the retired spelling and must keep
    resolving. Without this, the rename could silently orphan every DoD tag
    already on disk.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    import compass_pkg                                    # noqa: F401
    from compass_pkg import checks

    for spelling in ("(follow-up: BF-1)", "(backfill: BF-1)", "(follow-up: FU-1)"):
        assert checks._BACKFILL_TAG_RE.search(spelling), (
            f"the Definition-of-Done tag parser no longer reads {spelling!r} - "
            f"archived reports would stop resolving"
        )
