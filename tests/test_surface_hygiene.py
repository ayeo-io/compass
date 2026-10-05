"""Surface hygiene (issue executable-bdd-and-richer-plans).

Two pieces of tidying:

  * `skills/constitution-check/` is removed: it only redirected to
    `governance-check` and nothing loaded it. A dead skill in the plugin's
    skill list costs a reader attention every time they scan it.

  * The define stage's self-review and the requirements review overlap.
    Both files state the split: the self-review is four quick scans; the
    requirements review does the work that needs a decision.

Spec: executable-bdd-and-richer-plans/acceptance-criteria.md
      (`TRC-D1`..`D4`, `TRC-F7`).
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
BDD_SKILL = SKILLS / "bdd-specification" / "SKILL.md"
CLARIFY_CMD = ROOT / "commands" / "refine.md"

# The four scans the spec-author runs inline at the end of the define stage.
FOUR_SCANS = ["placeholder", "orphan", "untestable", "ambiguous"]


# ---------------------------------------------------------------------------
# The superseded skill is gone (TRC-D1)
# ---------------------------------------------------------------------------

def test_trc_d1_constitution_check_skill_deleted():
    assert not (SKILLS / "constitution-check").exists(), (
        "skills/constitution-check/ still exists; it is a tombstone that "
        "redirects to governance-check and is loaded by nothing"
    )
    assert (SKILLS / "governance-check" / "SKILL.md").is_file(), (
        "governance-check must survive - it is what constitution-check "
        "redirected to"
    )


# ---------------------------------------------------------------------------
# Nothing points at the deleted skill (TRC-D2)
# ---------------------------------------------------------------------------

SEARCHED_SUFFIXES = {".md", ".yml", ".yaml", ".json", ".py", ".sh"}
# .compass/, docs/proposals/ and docs/analysis/ are gitignored local working
# notes, not part of the shipped framework. They record what Compass looked
# like when they were written - including that this skill was still on disk -
# and rewriting history to match the present would destroy their value.
SKIPPED_DIRS = {".git", "__pycache__", ".compass", "dist", "node_modules",
                "proposals", "analysis"}


def _is_issue_archive(path):
    """A document belonging to one issue's own record.

    `.compass` is skipped above because an issue's documents record what
    Compass looked like when they were written, and rewriting history to match
    the present destroys their value. Issue documents live in
    `docs/compass/<created>-<slug>/`, so the same exemption covers those
    subdirectories.

    Scoped to the per-issue SUBDIRECTORIES, not to `docs/compass/` itself.
    Two hand-written documents sit flat in that directory - a cross-issue
    intake and a spike conclusion - and they are live prose that must stay
    scanned. Exempting the whole directory would quietly stop covering them.
    """
    parts = path.parts
    try:
        i = parts.index("docs")
    except ValueError:
        return False
    return (len(parts) > i + 3 and parts[i + 1] == "compass")


def _repo_files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SEARCHED_SUFFIXES:
            continue
        if any(part in SKIPPED_DIRS for part in path.parts):
            continue
        if _is_issue_archive(path.relative_to(ROOT)):
            continue
        yield path


def test_trc_d2_no_references_to_deleted_skill():
    """No file may point at constitution-check as a skill to load.

    Prose about the historic "constitution" model is fine and expected -
    governance/README.md explains what Compass replaced. What must not survive
    is a pointer to a skill that no longer exists.
    """
    offenders = []
    for path in _repo_files():
        # This file necessarily names the string it hunts for, the same way
        # `compass plan lint` has to exempt the documents that explain it.
        if path.resolve() == pathlib.Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if "constitution-check" not in line:
                continue
            offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")

    assert not offenders, (
        "these still reference the deleted constitution-check skill:\n  "
        + "\n  ".join(offenders)
    )


# ---------------------------------------------------------------------------
# The specification skill states what it leaves to the requirements review (TRC-D3)
# ---------------------------------------------------------------------------

def test_trc_d3_bdd_skill_documents_the_split():
    text = BDD_SKILL.read_text(encoding="utf-8").lower()

    for scan in FOUR_SCANS:
        assert scan in text, (
            f"the bdd-specification skill does not name the {scan!r} scan"
        )

    # it must say what the requirements review does that the self-review does not
    assert re.search(
        r"(?:requirements )?review (?:still )?(?:does|runs|resolves|hunts)",
        text), (
        "the skill never says what work the requirements review does that "
        "the inline self-review does not"
    )
    # and which delivery approaches run each: quick fix or regular.
    assert "quick fix" in text and re.search(r"regular", text), (
        "the skill does not say which delivery approaches run the inline "
        "self-review and which run the requirements review"
    )


# ---------------------------------------------------------------------------
# The /compass:refine command states the same split from its side (TRC-D4)
# ---------------------------------------------------------------------------

def test_trc_d4_clarify_command_documents_the_split():
    text = CLARIFY_CMD.read_text(encoding="utf-8").lower()

    assert "self-review" in text or "self review" in text, (
        "commands/refine.md never mentions the inline self-review the "
        "spec-author has already run, so Clarify looks like it starts from "
        "nothing"
    )
    assert re.search(r"(does not repeat|not repeat|already (been )?run|already "
                     r"covered|no need to re-?run)", text), (
        "commands/refine.md does not say that Clarify does not repeat the "
        "inline scans"
    )
    # it names the same four scans the skill names
    for scan in FOUR_SCANS:
        assert scan in text, (
            f"commands/refine.md does not name the {scan!r} scan; the two "
            f"descriptions of the split must agree"
        )


# ---------------------------------------------------------------------------
# The skill count does not grow on net (TRC-F7)
# ---------------------------------------------------------------------------

def test_trc_f7_skill_count_unchanged_on_net():
    """One skill in, one out.

    Compass grows by adding artifacts and skills rather than guardrails or
    routing dimensions (architecture/decisions/ADR-002), and every new
    user-facing concept is meant to be scrutinised before it lands. This makes
    the arithmetic a checked fact rather than a claim.
    """
    present = {p.name for p in SKILLS.iterdir()
               if p.is_dir() and (p / "SKILL.md").is_file()}

    assert "plan-authoring" in present, "plan-authoring was not added"
    assert "constitution-check" not in present, (
        "constitution-check was not removed")

    # No skill appears or disappears without an edit to this list.
    expected = {
        "adaptive-routing", "bdd-specification", "behaviour-mapping",
        "compass-runtime", "evidence-gates", "flow-management",
        "governance-check", "plan-authoring",
        "tdd-discipline", "worktree-multiagent",
        "receiving-code-review",  # a second pass over someone else's diff
        "systematic-debugging",   # notices three failed fixes in a row
        # Turns a brief that already exists into intent.md by asking rather
        # than assuming: "the discipline is the skill".
        "intent-interview",
        # Traceability lives in skills/evidence-gates/traceability.md and
        # role-translation lives in skills/intent-interview/role-translation.md,
        # each read beside the skill it merged into.
        "quick-fix",  # the inlined light path: one command and one skill
    }
    assert present == expected, (
        "the skill set changed without this allowlist being updated.\n"
        f"  unexpected: {sorted(present - expected)}\n"
        f"  missing   : {sorted(expected - present)}"
    )
    assert len(present) == len(expected), (
        f"expected {len(expected)} skills, found {len(present)}")


def test_the_archive_exemption_is_scoped_to_per_issue_directories():
    """The control for `_is_issue_archive`.

    An exemption that quietly widened to all of `docs/compass/` would stop
    covering the two hand-written documents sitting flat in it - a cross-issue
    intake and a spike conclusion - which are live prose, not an issue's own
    record.
    """
    P = pathlib.Path
    assert _is_issue_archive(P("docs/compass/2026-08-03-a-slug/technical-design.md"))
    for live in ("docs/compass/2026-08-26-first-hour-intent.md",
                 "docs/methodology.md",
                 "skills/quick-fix/SKILL.md"):
        assert not _is_issue_archive(P(live)), (
            f"{live} is exempt from the scan, and it is not an issue's record")

    # The two flat documents exist. An exemption checked against filenames that
    # have gone would prove nothing.
    flat = sorted(p.name for p in (ROOT / "docs" / "compass").glob("*.md"))
    assert flat, "docs/compass/ holds no flat documents - this check is moot"
