"""The writing-voice reference and its worked examples (issue human-voice).

The prose Compass sessions generate narrated the framework instead of
communicating a decision - session dialogue announced pipeline stages, and
review artifacts read as filled forms. This file pins what a test can pin
about a voice fix: presence, structure, and bounds. It cannot pin whether a
sentence sounds human - that stays the maintainer's ear at the clarity gate
(`verify.clarity`), the same way `tests/test_house_style.py` pins the
mechanical half of strategy `S7` and leaves the rest to review.

Two test files split the issue's behaviour in two, on purpose: this one
asserts what the prose surfaces carry (TRC-A1..A4, B1..B3, C1..C3, D1, F3);
`tests/test_voice_tells.py` asserts how the standalone check behaves
(TRC-D2, D3, F1, F2), by running it as a subprocess over fixtures.

Criteria: docs/system-spec.md
Design:   human-voice/technical-design.md (DD-4 names
          what each function asserts). `TRC-A2` and `TRC-C2` check quotes through
          `scripts/verify-archive-quotes.py` against the committed hash
          manifest (`skills/compass-runtime/archive-quote-manifest.json`).
          They skip only when the hash matches and no archive file is
          present to compare against directly, and the skip names the spans
          it means, by id. See `tests/test_archive_quote_manifest.py` for
          how that check itself is proven to fail on a fabricated quote in
          an archive-less environment, hermetically, with a synthetic
          reference, manifest, and archive root.
"""

# These tests assert the current names (technical-design.md, intent.md).
# Older manifests and documents still load (ADR-006, backward compatibility).
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
REFERENCE = REPO_ROOT / "skills" / "compass-runtime" / "writing-voice.md"
WORKED_EXAMPLE = (
    REPO_ROOT / "skills" / "compass-runtime" / "writing-voice-worked-example.md"
)
# The archive moved: `compass migrate` relocated every issue's documents to
# `docs/compass/<created>-<slug>/`. Built from segments, not a literal path.
ORIGINAL = (REPO_ROOT / "docs" / "compass"
            / "2026-05-26-make-receipt-render" / "requirements-review.md")
ORIGINAL_CITE = "make-receipt-render/requirements-review.md"


def _load_quote_verification_module():
    """`scripts/verify-archive-quotes.py`, loaded by path - it has a hyphen
    in its file name, so it cannot be `import`ed as an ordinary package."""
    script_path = REPO_ROOT / "scripts" / "verify-archive-quotes.py"
    spec = importlib.util.spec_from_file_location(
        "verify_archive_quotes_script", script_path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_quotes_verified(span_ids, label):
    """Run the shared archive-quote check (issue archive-quote-verification)
    against the real repository, scoped to `span_ids`. A hash mismatch or an
    archive-present mismatch is a hard failure - it never reads as a pass.
    The only case that still skips is every span in scope matching its
    manifest hash with no real file here to check it against directly, and
    that skip names every such span so it is never mistaken for silence."""
    module = _load_quote_verification_module()
    failures, unverified = module.verify(archive_root=REPO_ROOT, span_ids=span_ids)
    assert not failures, (
        f"{label}: archive quote verification failed:\n" + "\n".join(failures)
    )
    if unverified:
        pytest.skip(
            f"{label}: the archive is not present on this machine "
            f"(.compass/work/ is gitignored, as it always is in continuous "
            f"integration) - could not check {len(unverified)} span(s) "
            f"directly against the real file: {', '.join(unverified)}. "
            f"The hash manifest already confirmed each is unchanged since "
            f"it was last checked against the real file - see "
            f"skills/compass-runtime/archive-quote-manifest.json."
        )


def _range_is_readable(*revs) -> bool:
    """Are these commits in this checkout?

    False on a shallow clone, where the objects were never fetched. Used to
    skip a historical-range assertion rather than let a missing object read
    as a code defect.
    """
    for rev in revs:
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{rev}^{{commit}}"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if probe.returncode != 0:
            return False
    return True


# The skill directories that existed before the human-voice issue. Written
# down rather than derived, so the check holds on a shallow clone where the
# pre-issue revision is not fetched - and so moving the reference into a new
# skill fails here even when git history is unavailable.
_PRE_ISSUE_SKILLS = {
    "skills/adaptive-routing", "skills/bdd-specification",
    "skills/behaviour-mapping", "skills/compass-runtime",
    "skills/evidence-gates", "skills/flow-management",
    "skills/governance-check", "skills/plan-authoring",
    "skills/receiving-code-review", "skills/role-translation",
    "skills/systematic-debugging", "skills/tdd-discipline",
    "skills/traceability", "skills/worktree-multiagent",
}

PRINCIPLE = (
    "communicate the decision, do not perform the process - say what "
    "happened and what is needed, never announce which stage you are in"
)


def _script_tells() -> list[str]:
    """The three findable tells, read straight from scripts/voice-tells.py.

    `TRC-D2` asks that the reference marks the same three the check greps -
    one list, not two - so a hardcoded second copy here would let the two
    drift silently. `voice-tells.py` has a hyphen in its name, so it is
    loaded by path rather than imported as a package.
    """
    script_path = REPO_ROOT / "scripts" / "voice-tells.py"
    spec = importlib.util.spec_from_file_location("voice_tells_script", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.TELLS)


def _reference_text() -> str:
    assert REFERENCE.is_file(), (
        f"{REFERENCE.relative_to(REPO_ROOT)} must exist - it is the one "
        "reference every other voice surface points at"
    )
    return REFERENCE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Group A - the writing-voice reference
# ---------------------------------------------------------------------------

def test_trc_a1_the_reference_lives_under_an_existing_skill_and_opens_with_the_principle():
    text = _reference_text()

    # It sits inside a skill directory that already existed before this
    # change: compare the skill directories on HEAD (before this issue
    # touched anything) with the skill directories on disk now. Equal sets
    # means no new skill directory was invented to hold the reference.
    # Compared against the revision BEFORE this issue, not HEAD. Once the
    # work is committed, HEAD is the post-change tree and the two sides are
    # equal by construction - so the assertion could only fail on an
    # uncommitted new directory, never in CI or on a merged branch. 519300b
    # is the commit the human-voice work started from; if it is not in this
    # checkout (a shallow clone) the range check below is skipped and the
    # direct assertion still holds.
    pre_issue = "519300b"
    if not _range_is_readable(pre_issue):
        head_dirs = None
    else:
        head = subprocess.run(
            ["git", "ls-tree", "-d", "--name-only", pre_issue, "skills/"],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        head_dirs = {d for d in head.stdout.split() if d}
    current_dirs = {
        f"skills/{p.name}" for p in (REPO_ROOT / "skills").iterdir()
        if p.is_dir()
    }
    # The set comparison that stood here compared the WHOLE skill directory
    # set against the pre-issue tree, so any skill added for any unrelated
    # reason failed it - `intent-interview` did, on 2026-08-25. The rule was
    # never "no skill may be added". It is "the reference must not live in a
    # skill invented to hold it", and the assertion below says exactly that,
    # with or without git history. Removed rather than narrowed, because two
    # assertions of one rule is how the weaker one ends up doing the work.
    assert current_dirs, "no skill directories found, so this checks nothing"

    # Holds with or without git history: the reference's own parent directory
    # must be one that predates the issue. This is the assertion that fails
    # if the file is moved into a new skill, which the HEAD comparison could
    # not do once the work was committed.
    assert f"skills/{REFERENCE.parent.name}" in _PRE_ISSUE_SKILLS, (
        f"the reference lives in skills/{REFERENCE.parent.name}, which is "
        f"not one of the skills that predate this issue"
    )
    assert "skills/compass-runtime" in current_dirs

    lines = text.splitlines()
    assert any(PRINCIPLE in line for line in lines), (
        "the principle must appear as a single line, verbatim: " + PRINCIPLE
    )

    assert "skills/worktree-multiagent/SKILL.md" in text
    assert "Never stash across a worktree hop" in text, (
        "the reference must name that section as the calibration sample "
        "of the register it is asking for"
    )


# ---------------------------------------------------------------------------
# Shared pair parsing - both `TRC-A2` and `TRC-A4` read the same "### Pair N"
# blocks, so the parser lives once here.
# ---------------------------------------------------------------------------

# Which of the three archive artifact kinds a cited path names. Anything
# else is real but does not count towards the "covers at least two kinds"
# requirement.
_KINDS = {
    "devlog.md": "devlog",
    "requirements-review.md": "review artifact",
    "verification-report.md": "verification report",
}


def _pairs() -> list[dict]:
    """Every '### Pair N' block, parsed by `scripts/verify-archive-quotes.py`
    (issue archive-quote-verification) rather than a second copy of the same
    regex here - the parser that decides what gets hashed and the parser
    this file's other assertions read must never be able to disagree about
    what a pair's Source: and Before: lines say."""
    module = _load_quote_verification_module()
    return module.parse_pairs(_reference_text())


def test_trc_a2_every_pair_quotes_a_real_archive_passage():
    pairs = _pairs()
    assert 6 <= len(pairs) <= 10, (
        f"found {len(pairs)} pairs; the scenario asks for six to ten"
    )

    kinds_seen = set()
    for pair in pairs:
        assert pair["source"], f"pair with no Source: line: {pair}"
        # `<slug>/<document>.md`, not a repository path. An issue's documents
        # are not distributed, so prose naming a repo-relative path to one
        # claims a file the reader does not have. `scripts/verify-archive-
        # quotes.py` turns this into a real path where the archive is present.
        assert "/" in pair["source"] and not pair["source"].startswith(
            (".compass/", "docs/", "/")), (
            f"pair cites a repository path rather than an issue and a "
            f"document: {pair['source']}"
        )
        assert pair["before"], f"pair with no Before: quote: {pair}"
        filename = pair["source"].rsplit("/", 1)[-1]
        if filename in _KINDS:
            kinds_seen.add(_KINDS[filename])

    assert len(kinds_seen) >= 2, (
        f"cited files must cover at least two of devlog, review artifact, "
        f"verification report; only saw: {sorted(kinds_seen)}"
    )

    # The verbatim half needs the real archive, which is gitignored and
    # therefore absent in continuous integration and in a fresh clone
    # (issue archive-quote-verification). Everything above this line runs
    # everywhere. Below it, every pair's quote is checked against a
    # committed hash manifest in every environment - a changed hash is a
    # hard failure, archive or no archive - and, wherever the archive is
    # also present, directly against the real file too. The only case that
    # still skips is a hash match with nothing here to compare it against
    # directly, and that skip names every such pair by id.
    _assert_quotes_verified(
        [p["id"] for p in pairs], "TRC-A2 (writing-voice.md pairs)"
    )


# The nine tells, exactly as `TRC-A3` names them. The three findable ones are
# read from scripts/voice-tells.py's own TELLS constant (see _script_tells
# above), so the reference's marked set and the check's grepped set cannot
# drift apart - the two lists `TRC-D2` asks be one.
FINDABLE_TELLS = _script_tells()
JUDGEMENT_TELLS = [
    '"successfully" suffixed to a completed verb',
    '"the X stage" used as dialogue',
    "accordingly",
    "headings inside conversation",
    "restating the request before answering it",
    "status-report framing of something the person just watched happen",
]


def test_trc_a3_the_tells_list_names_all_nine_and_marks_the_findable_ones():
    text = _reference_text()

    for tell in FINDABLE_TELLS + JUDGEMENT_TELLS:
        assert tell in text, f"tell not named in the reference: {tell!r}"

    # Split the tells section into its nine numbered entries and check each
    # tell's own entry, not just the file as a whole - checking the file as
    # a whole would let the reference mark the wrong three findable and
    # still pass.
    section = text.split("## The tells", 1)[1]
    entries = re.split(r"(?m)^\d+\.\s", section)[1:]
    assert len(entries) == 9, (
        f"expected 9 numbered tell entries in the tells section, found "
        f"{len(entries)}"
    )

    for tell in FINDABLE_TELLS:
        entry = next((e for e in entries if tell in e), None)
        assert entry is not None, f"no numbered entry names {tell!r}"
        assert "**findable**" in entry, f"the entry for {tell!r} must be marked findable"
        assert "**judgement**" not in entry, f"the entry for {tell!r} must not also be marked judgement"

    for tell in JUDGEMENT_TELLS:
        entry = next((e for e in entries if tell in e), None)
        assert entry is not None, f"no numbered entry names {tell!r}"
        assert "**judgement**" in entry, f"the entry for {tell!r} must be marked judgement"
        assert "**findable**" not in entry, f"the entry for {tell!r} must not also be marked findable"

    assert text.count("**findable**") == 3, (
        "exactly three tells must be marked findable - the check's set"
    )
    assert text.count("**judgement**") == 6, (
        "exactly six tells must be marked judgement"
    )


def test_trc_a4_no_after_passage_still_carries_a_tell():
    text = _reference_text()
    pairs = _pairs()
    assert pairs, "no pairs found - TRC-A2 must land before this scenario can"

    findable_re = re.compile(
        r"\b(?:" + "|".join(re.escape(t) for t in FINDABLE_TELLS) + r")\b",
        re.IGNORECASE,
    )
    for pair in pairs:
        assert pair["after"], f"pair with no After: quote: {pair}"
        assert not findable_re.search(pair["after"]), (
            f"'after' for {pair['source']} still carries a findable tell: "
            f"{pair['after']!r}"
        )
        assert pair["what_changed"], (
            f"pair for {pair['source']} has no 'What changed:' line - a "
            f"shortened piece of form-speak cannot pass itself off as a "
            f"rewrite without saying what it actually communicates"
        )

    bar = (
        "read it aloud - would you say this sentence to a colleague at "
        "your desk"
    )
    assert bar in text, (
        "the reference must state the bar every 'after' had to clear"
    )


# ---------------------------------------------------------------------------
# Group C - the worked examples
# ---------------------------------------------------------------------------

def _worked_example_text() -> str:
    assert WORKED_EXAMPLE.is_file(), (
        f"{WORKED_EXAMPLE.relative_to(REPO_ROOT)} must exist"
    )
    return WORKED_EXAMPLE.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Collapse every run of whitespace to one space.

    Phrase assertions below are about what the prose says, not about where
    its lines happen to break, so they match against this rather than the
    raw text. It also closes the other half of the same hole: a negative
    assertion against raw text passes when the banned phrase is merely
    wrapped across two lines.
    """
    return " ".join(text.split())


def test_trc_c1_the_worked_example_rewrites_a_named_archive_artifact():
    text = _worked_example_text()
    flat = _flat(text)
    assert ORIGINAL_CITE in flat, (
        "the worked example must cite the original's path"
    )
    # One distinguishing phrase per decision in the original ledger - all
    # four have to survive the rewrite, none invented, none dropped.
    distinguishing_phrases = [
        "compass issue receipt --issue <slug>", # Q1: host command
        "no re-execution",                      # Q2: recorded vs live state
        "Fifty lines, a hundred columns wide",   # Q3: the line cap
        "unified the three on exit 0",           # Q4: exit-code asymmetry
    ]
    for phrase in distinguishing_phrases:
        assert phrase in flat, (
            f"a decision from the original ledger did not survive the "
            f"rewrite: {phrase!r}"
        )

    # Check each of the four decision sections individually - a bare count
    # of "jed72" across the whole file is a loose proxy: four mentions
    # clustered in one section would still pass it.
    sections = re.split(r"(?m)^## ", text)[1:]
    assert len(sections) == 4, (
        f"expected four decision sections, found {len(sections)}"
    )
    for section in sections:
        assert "jed72" in section, (
            f"a decision section does not carry whose call it was: "
            f"{section.splitlines()[0]!r}"
        )


def test_trc_c1_the_worked_example_does_not_misstate_or_embellish_its_source():
    """The exhibit invites a reader to compare it with the cited original,
    so it must say only what that original says - no fact the source
    lacks, no colour dressed as a fact, and no name for a command or a
    stage that is not the one Compass uses today."""
    flat = _flat(_worked_example_text())

    # The original says only that `compass status` does not exist at HEAD;
    # `compass check` demonstrably does, and the very next clause offers it
    # as a live option - the exhibit was self-contradicting in its own
    # first paragraph.
    assert "`status` does not exist" in flat
    assert "`check` does" in flat
    assert "neither of those verbs exists" not in flat

    # The original records the exit-code asymmetry as an open question and
    # unifies it; nobody wrote that it was an accident. Fidelity, not colour.
    assert "accident of drafting" not in flat

    # A new teaching artifact should not teach a retired flag spelling or a
    # retired stage name. `--task` no longer parses (ADR-014 removed
    # retired names).
    assert "--task <slug>" not in flat, (
        "--issue is the CLI's only spelling; --task was removed at the major "
        "version and no longer parses"
    )
    assert "at land" not in flat, "'at land' is the retired stage name"
    assert "ship time" in flat


def test_trc_c2_the_rewritten_original_is_unmodified_and_cited():
    text = _worked_example_text()
    assert str(WORKED_EXAMPLE) != str(ORIGINAL)
    assert ORIGINAL_CITE in text, (
        "the rewrite must say where the original lives"
    )

    # As with `TRC-A2` above: checked against a committed hash manifest in
    # every environment (issue archive-quote-verification), and directly
    # against the real file wherever the archive is present. A hash
    # mismatch or a direct mismatch is a hard failure, never a skip; the
    # only remaining skip is a hash match with no file here to check it
    # against, named by id.
    module = _load_quote_verification_module()
    _assert_quotes_verified(
        module.WORKED_EXAMPLE_SPAN_IDS, "TRC-C2 (worked-example original)"
    )


def test_trc_c3_the_template_worked_example_records_a_decision_in_prose():
    template = REPO_ROOT / "templates" / "requirements-review.md"
    text = template.read_text(encoding="utf-8")
    assert "## Worked example" in text, (
        "templates/requirements-review.md must gain a worked-example section"
    )
    section = text.split("## Worked example", 1)[1]
    # Stop at the next heading so the rest of the template cannot smuggle in
    # a false pass for this section's own checks.
    section = re.split(r"(?m)^## ", section, maxsplit=1)[0]

    assert "Status:" not in section, (
        "the worked example must show a decision in prose, not a "
        "label-and-value row of the 'Status: RESOLVED' kind"
    )
    for tell in FINDABLE_TELLS:
        assert tell.lower() not in section.lower(), (
            f"the worked example must not carry a findable tell: {tell!r}"
        )

    # Every assertion above is negative, so an entirely empty section would
    # still pass them. `TRC-C3`'s actual Then names four things the paragraph
    # must carry.
    assert "was unclear" in section, (
        "the worked example must state what was unclear"
    )
    assert "jed72" in section, "the worked example must state whose call it was"
    assert "fifty lines" in section, "the worked example must state the call itself"
    assert "standard terminal" in section, (
        "the worked example must state what the call rests on"
    )


# ---------------------------------------------------------------------------
# Group D - the reviewer's clarity checks
# ---------------------------------------------------------------------------

def test_trc_d1_the_clarity_dimension_names_the_tells_as_judgement():
    reviewer = (REPO_ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
    gates = _evidence_gates_text()
    reference_path = "skills/compass-runtime/writing-voice.md"

    for name, text in (
        ("agents/reviewer.md", reviewer),
        ("skills/evidence-gates/SKILL.md", gates),
    ):
        assert reference_path in text, (
            f"{name} must point the clarity dimension at the reference"
        )
        assert "scripts/voice-tells.py" in text, (
            f"{name} must tell the reviewer to run the advisory check"
        )
        assert "never an automatic gate failure" in text.lower(), (
            f"{name} must say the finding is assessed, never an automatic "
            f"gate failure"
        )

        # `TRC-B3`: these two surfaces may name only the three tells the check
        # greps, never the full nine-item list. "accordingly" is excluded
        # from this check - it is a single ordinary word, not a distinctive
        # phrase, and would false-positive on innocent prose.
        for tell in JUDGEMENT_TELLS:
            if tell == "accordingly":
                continue
            assert tell not in text, (
                f"{name} names a judgement tell that belongs only in the "
                f"reference: {tell!r}"
            )


# ---------------------------------------------------------------------------
# Group B - the instruction surfaces
# ---------------------------------------------------------------------------

REFERENCE_PATH = "skills/compass-runtime/writing-voice.md"

def _evidence_gates_text():
    """Reads SKILL.md and its sibling files.

    The evidence-gates skill's parts load when needed - the review-dimension
    checklists, the evidence vocabulary, the architecture-check detail and
    the coverage notes are siblings of SKILL.md, not inside it. A guard
    reading only SKILL.md would report them missing.
    """
    import pathlib as _p
    d = _p.Path(__file__).resolve().parent.parent / "skills" / "evidence-gates"
    return "\n".join(sorted(p.read_text(encoding="utf-8") for p in d.glob("*.md")))



def _section_after_heading(text: str, heading: str) -> str:
    marker = f"## {heading}"
    assert marker in text, f"missing heading {marker!r}"
    after = text.split(marker, 1)[1]
    after = re.split(r"(?m)^## ", after, maxsplit=1)[0]
    return after.strip()


def test_trc_b1_claude_md_and_agents_md_carry_the_voice_paragraph():
    claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude_section = _section_after_heading(claude, "Writing voice")
    agents_section = _section_after_heading(agents, "Writing voice")

    for name, section in (
        ("CLAUDE.md", claude_section), ("AGENTS.md", agents_section),
    ):
        assert REFERENCE_PATH in section, (
            f"{name}'s voice paragraph must name the reference by path"
        )
        # The cap exists because these files load on every run, so every
        # word costs attention every time.
        #
        # The section carries two things a writer must have in front of
        # them, not left in a skill a session may never load: the
        # four-part reply shape from `agent-speech-is-unchecked`, and the
        # maintainer's plain-English rules - lead with the point, no idiom
        # or metaphor, one word for one thing, "must" / "can" / "do not",
        # and the table of shorter words.
        #
        # 560 is the larger of the two sections (AGENTS.md, 546 words) plus
        # a small margin, not a round number. A later change that needs
        # more words must raise the cap here, and say why.
        words = len(section.split())
        assert words <= 560, (
            f"{name}'s voice paragraph is {words} words; must be <=560"
        )
        assert "### Pair" not in section, (
            f"{name} must not copy the before/after pairs"
        )

    assert claude_section != agents_section, (
        "the two paragraphs must be written in their own register, not "
        "pasted twice"
    )

    for tell in FINDABLE_TELLS + JUDGEMENT_TELLS:
        if tell == "accordingly":
            continue
        assert tell not in claude_section, f"CLAUDE.md must not copy the tells list ({tell!r})"
        assert tell not in agents_section, f"AGENTS.md must not copy the tells list ({tell!r})"


def test_trc_b2_assess_refine_and_verify_point_at_the_reference():
    """The three commands whose output a person reads most name the writing
    reference; no other command does. Every command file is a real command."""
    command_dir = REPO_ROOT / "commands"
    included = ["assess.md", "refine.md", "verify.md"]
    stubs: set[str] = set()
    for name in included:
        text = (command_dir / name).read_text(encoding="utf-8")
        if name == "assess.md":   # its full procedure is a reference file
            text += (REPO_ROOT / "approaches" / "assess-procedure.md").read_text(encoding="utf-8")
        section = _section_after_heading(text, "Voice")
        assert REFERENCE_PATH in section, (
            f"commands/{name} must name the reference by path"
        )
        words = len(section.split())
        assert words <= 60, (
            f"commands/{name}'s voice note is {words} words; must be <=60"
        )

    for path in sorted(command_dir.glob("*.md")):
        if path.name in included or path.name in stubs:
            continue
        text = path.read_text(encoding="utf-8")
        assert REFERENCE_PATH not in text, (
            f"commands/{path.name} names the writing-voice reference; only "
            f"assess, refine, and verify should"
        )


def test_trc_b3_the_full_tells_list_appears_in_exactly_one_file():
    distinctive = [t for t in (FINDABLE_TELLS + JUDGEMENT_TELLS) if t != "accordingly"]
    surfaces = set()
    for pattern in (
        "skills/**/*.md", "commands/*.md", "templates/*.md", "agents/*.md",
    ):
        surfaces.update(REPO_ROOT.glob(pattern))
    surfaces.add(REPO_ROOT / "CLAUDE.md")
    surfaces.add(REPO_ROOT / "AGENTS.md")

    carriers = [
        p.relative_to(REPO_ROOT) for p in sorted(surfaces)
        if p.is_file()
        and all(t in p.read_text(encoding="utf-8") for t in distinctive)
    ]
    assert carriers == [REFERENCE.relative_to(REPO_ROOT)], (
        f"the full nine-item tells list must appear in exactly one file: "
        f"{carriers}"
    )

    skill = (REPO_ROOT / "skills" / "compass-runtime" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert REFERENCE_PATH in skill, (
        "skills/compass-runtime/SKILL.md must point at the reference file "
        "in its own directory"
    )


# ---------------------------------------------------------------------------
# Failure-mode scenarios
# ---------------------------------------------------------------------------

def test_trc_f3_no_new_guardrail_gate_check_or_cli_verb():
    # Checks that the human-voice commits (519300b..1f00637) did not touch
    # these paths - the direct proof is that git sees no change to them.
    # tests/test_stream_c_no_new_checks_or_gates.py and
    # tests/test_cli_surface_drift.py are the standing nets for the same
    # invariant on every other change; this asserts the stronger claim that
    # this issue specifically never opened these files.
    #
    # Scoped to this committed range, not the working tree against a moving
    # HEAD: a later issue legitimately touching cli/ (zero-friction-install
    # bundles PyYAML there) would otherwise trip this human-voice-specific
    # assertion on someone else's uncommitted work. The historical range is
    # immutable, so the guarantee this test makes - human-voice itself never
    # touched these paths - is unchanged.
    untouched = ["governance/guardrails.yml", "governance/terminology.yml", "cli/"]
    # A pinned range is only immutable if the history is present. CI checks
    # out a shallow clone, where these objects are absent and git exits 128,
    # so ask first rather than letting a missing object read as a failure.
    # The content assertions below need no history and run everywhere; they
    # are what carries this claim when the range cannot be read.
    if _range_is_readable("519300b", "1f00637"):
        diff = subprocess.run(
            ["git", "diff", "--stat", "519300b", "1f00637", "--", *untouched],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        assert diff.stdout.strip() == "", (
            f"this issue must not touch guardrails.yml, terminology.yml, or "
            f"cli/:\n{diff.stdout}"
        )

    # The guardrail count is still five - a direct read, not just "we did
    # not touch the file" (defence in depth against a future edit to this
    # test that loosens the diff check above).
    import yaml
    guardrails = yaml.safe_load(
        (REPO_ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8")
    )
    assert len(guardrails["defaults"]) == 5

    terminology = yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8")
    )
    assert "tell" not in terminology.get("terms", {}), (
        "'tell' must not enter the frozen v2 vocabulary - it stays "
        "ordinary English describing a writing habit"
    )
