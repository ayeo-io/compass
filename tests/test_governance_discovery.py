"""Governance discovery never silently substitutes the shipped defaults.

Issue: claims-match-what-is-proved. Scenarios `TRC-A1` to `TRC-A6` and `TRC-F1`.

The bug these cover: `find_governance` looked upward for
`governance/routing-policy.yml`. A project that shipped `governance/guardrails.yml`
beside no routing policy got the framework's own governance instead, with
nothing printed - so their guardrails never ran and nothing said so. That
contradicts the safety contract's promise that a declared guardrail cannot
silently become advisory.

The line drawn here: Compass refuses when a project has declared something it
cannot honour. It stays silent when the project has said nothing, which is the
day-one, zero-setup case and a documented promise.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "cli"))

from compass_pkg.core import CompassError, find_governance  # noqa: E402


SHIPPED = REPO_ROOT / "governance"


def _gov(root: Path, *, policy: bool = False, guardrails: bool = False) -> Path:
    """Make <root>/governance/ holding whichever recognised files are asked for."""
    d = root / "governance"
    d.mkdir(parents=True, exist_ok=True)
    if policy:
        (d / "routing-policy.yml").write_text(
            (SHIPPED / "routing-policy.yml").read_text(encoding="utf-8"),
            encoding="utf-8")
    if guardrails:
        (d / "guardrails.yml").write_text(
            (SHIPPED / "guardrails.yml").read_text(encoding="utf-8"),
            encoding="utf-8")
    return d


@pytest.fixture
def in_dir(monkeypatch):
    """Run the body with the working directory somewhere else."""
    def _cd(path: Path):
        monkeypatch.chdir(path)
    return _cd


def _boundary(root: Path) -> None:
    """Mark `root` as a project boundary the upward walk must not cross."""
    (root / ".compass").mkdir(parents=True, exist_ok=True)


# --- `TRC-A1` ----------------------------------------------------------------

def test_a1_incomplete_project_governance_is_refused(tmp_path, in_dir):
    """`TRC-A1` - guardrails declared with no routing policy is refused, not replaced."""
    proj = tmp_path / "proj"
    _gov(proj, guardrails=True)
    _boundary(proj)
    in_dir(proj)

    # Raising IS the assertion: the old behaviour was to return the shipped
    # directory here, silently. Anything other than a refusal is the bug.
    with pytest.raises(CompassError) as exc:
        find_governance()

    # And the refusal is about the project's own directory, not a general
    # complaint about governance being unfindable.
    assert str(proj / "governance") in str(exc.value), (
        "the refusal does not name the project directory it is refusing")


# --- `TRC-A2` ----------------------------------------------------------------

def test_a2_refusal_names_found_and_missing_paths(tmp_path, in_dir):
    """`TRC-A2` - the message is the migration path, not just a complaint.

    A project in this state works today, because its guardrails are quietly
    ignored, and fails on its first command after upgrading. The message has to
    be actionable without opening the source.
    """
    proj = tmp_path / "proj"
    gov = _gov(proj, guardrails=True)
    _boundary(proj)
    in_dir(proj)

    with pytest.raises(CompassError) as exc:
        find_governance()
    msg = str(exc.value)

    assert str(gov / "guardrails.yml") in msg, "the message does not name the file it found"
    assert str(gov / "routing-policy.yml") in msg, "the message does not name the file it expected"
    # Two ways out, and both must be spelled out - keep your governance by
    # adding the file, or drop it and take the defaults.
    assert "routing-policy.yml" in msg and ("cp " in msg or "copy" in msg.lower()), (
        "the message does not say how to keep the project's own governance")
    assert "remove" in msg.lower() or "delete" in msg.lower(), (
        "the message does not offer the other way out - dropping the "
        "declaration and using the shipped defaults")


# --- `TRC-A3` ----------------------------------------------------------------

def test_a3_no_project_governance_still_falls_back_silently(tmp_path, in_dir, capsys):
    """`TRC-A3` - a project that has said nothing keeps working, silently.

    This is the compatibility promise: assess and go on day one with zero
    project setup. It is why the fix is not 'fail whenever there is no routing
    policy'.
    """
    proj = tmp_path / "proj"
    proj.mkdir(parents=True)
    _boundary(proj)
    in_dir(proj)

    assert Path(find_governance()).resolve() == SHIPPED.resolve()
    out = capsys.readouterr()
    assert out.out == "" and out.err == "", (
        "falling back to the shipped defaults printed something - this is the "
        "ordinary day-one case and must be silent")


def test_a3b_governance_dir_with_neither_file_counts_as_saying_nothing(tmp_path, in_dir):
    """`TRC-A3` - a directory that merely shares the name has declared nothing.

    Refusing here would mean any directory called `governance/` could stop
    Compass. The rule is about what a project has *declared*, not what its
    directories are called.
    """
    proj = tmp_path / "proj"
    (proj / "governance").mkdir(parents=True)
    (proj / "governance" / "notes.md").write_text("unrelated\n", encoding="utf-8")
    _boundary(proj)
    in_dir(proj)

    assert Path(find_governance()).resolve() == SHIPPED.resolve()


# --- `TRC-A4` ----------------------------------------------------------------

def test_a4_complete_project_governance_is_used(tmp_path, in_dir, capsys):
    """`TRC-A4` - the case that already worked keeps working."""
    proj = tmp_path / "proj"
    gov = _gov(proj, policy=True, guardrails=True)
    _boundary(proj)
    in_dir(proj)

    assert Path(find_governance()).resolve() == gov.resolve()
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


# --- `TRC-A5` ----------------------------------------------------------------

def test_a5_replace_or_merge_is_documented():
    """`TRC-A5` - an adopter can find out what happens to the shipped defaults.

    Measured during the requirements review: project governance REPLACES the
    shipped defaults, and a shipped guardrail the project omits is reported
    when it would have applied but does not fail the run. Neither fact was
    written down anywhere.
    """
    doc = (REPO_ROOT / "governance" / "README.md")
    assert doc.is_file(), "governance/README.md is where this is expected to live"

    # Scoped to the section that answers the question. The first version of
    # this test asked whether the word "replace" appeared anywhere in the file.
    # It does, three times, twice for unrelated reasons - so the test passed
    # over a document it had not inspected, and its own mutation proof is what
    # caught that.
    body = doc.read_text(encoding="utf-8")
    marker = "## A project that copied governance under 5.x"
    assert marker in body, (
        "governance/README.md has no section answering what happens to the "
        "shipped defaults when a project declares its own")
    # Whitespace is collapsed because the phrases below wrap across lines in
    # the source and a raw substring search would miss them - a failure about
    # formatting, not about what the document says.
    section = " ".join(
        body.split(marker, 1)[1].split("\n## ", 1)[0].lower().split())

    assert "replaces the shipped defaults" in section, (
        "the section does not say that project governance replaces the "
        "shipped defaults - an adopter could reasonably expect their rules to "
        "be added to the shipped ones, and they are not")
    assert "omits" in section or "omitted" in section, (
        "the section does not say what happens to a shipped guardrail the "
        "project leaves out")
    assert "does not fail the run" in section, (
        "the section does not say whether an omitted shipped guardrail is "
        "enforced or merely reported")


# --- `TRC-A6` ----------------------------------------------------------------

def test_a6_incomplete_governance_outside_the_project_is_ignored(tmp_path, in_dir):
    """`TRC-A6` - a stray directory above the project cannot stop work inside it.

    Discovery walks upward. Refusing on anything it finds would let an outer
    repository, a monorepo root, or a home directory with a stray file break a
    project that is itself fine.
    """
    outer = tmp_path / "outer"
    _gov(outer, guardrails=True)            # incomplete, and outside
    proj = outer / "inner"
    gov = _gov(proj, policy=True, guardrails=True)   # complete, and ours
    _boundary(proj)
    in_dir(proj)

    assert Path(find_governance()).resolve() == gov.resolve()


def test_a6b_the_walk_stops_at_the_project_boundary(tmp_path, in_dir):
    """`TRC-A6` - the boundary holds even when the project declares nothing.

    Nearest-wins alone does not cover this: a project with no governance of its
    own, sitting under a parent that has an incomplete one. Without a boundary
    it would refuse on a directory its author may not know exists.
    """
    outer = tmp_path / "outer"
    _gov(outer, guardrails=True)            # incomplete, and outside
    proj = outer / "inner"
    proj.mkdir(parents=True)
    _boundary(proj)                          # the project boundary
    in_dir(proj)

    assert Path(find_governance()).resolve() == SHIPPED.resolve()


# --- `TRC-F1` ----------------------------------------------------------------

def test_f1_project_governance_without_guardrails_is_refused(tmp_path, in_dir):
    """`TRC-F1` - a routing policy with no guardrails is refused too.

    A project holding a routing policy and no guardrails passed the old
    discovery test, because discovery only looked for the routing policy. The
    behaviour after discovery was not checked.
    """
    proj = tmp_path / "proj"
    gov = _gov(proj, policy=True)
    _boundary(proj)
    in_dir(proj)

    with pytest.raises(CompassError) as exc:
        find_governance()
    assert str(gov / "guardrails.yml") in str(exc.value), (
        "the message does not name the missing file")
