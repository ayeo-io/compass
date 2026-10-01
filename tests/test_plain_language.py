"""The plain words come first; the code follows in brackets.

The rule this checks is an extension of the existing ban on bare `G1`-`G5` and
`S1`-`S12` codes, widened to every id prefix and given the one thing that ban
never stated: the ORDER. "a human signs off on the irreversible (`G5`)" is right;
"`G5` fired, which means a human signs off on the irreversible" is not, because
the reader met the code before its meaning.

The check reports and never blocks (TRC-C4). The tests in this file are a
different thing and must be able to fail.

**Read this before trusting any zero this check reports (`TRC-C10`).** The
registry of what each code means is DERIVED from governance rather than
hand-written, and a derivation that returns empty makes every code meaningless,
every count zero and every test green while nothing has been inspected. That is
the exact defect this issue exists to stop, so the check refuses to report a
zero it cannot stand behind.

Scenario ids: `TRC-C1` to `TRC-C10` (issue plain-language-3-2-0).

`governance/plain-language-baseline.json` records locations only under
`architecture/`, `examples/`, `governance/` and `templates/`; none of its 466
recorded locations is under `tests/`. A zero from this check says nothing
about a bare code in a test docstring or assertion message.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from plain_language_check import (
    REPO_ROOT,
    EmptyRegistry,
    count_bare_codes,
    gloss_registry,
    is_whole_content,
    load_baseline,
)


# ---------------------------------------------------------------------------
# `TRC-C10` - the registry cannot be empty and silent. Read this first.
# ---------------------------------------------------------------------------

def test_pl_c10_empty_registry_fails_rather_than_reporting_zero():
    """`TRC-C10` - a zero from an empty registry is the worst available answer.

    If the derivation yields nothing, no code has a known meaning, nothing can
    be counted as unexplained, and the count is zero - indistinguishable from a
    repository with nothing wrong in it. The whole requirement is measured
    against that number.
    """
    with pytest.raises(EmptyRegistry) as exc:
        count_bare_codes("the G5 guard kicked in", registry={})
    msg = str(exc.value).lower()
    assert "empty" in msg, "the failure must say the registry was empty"
    assert "zero" in msg, (
        "the failure must say why it refuses to report zero, or the next "
        "person will 'fix' it by returning 0"
    )


def test_pl_c10b_a_partially_empty_source_is_named():
    """`TRC-C10` - which source came back empty, not just that one did."""
    with pytest.raises(EmptyRegistry) as exc:
        gloss_registry(guardrails={}, strategies={}, codes={})
    msg = str(exc.value)
    # Assert the sources are named as EMPTY: the message names all three
    # sources whatever went wrong.
    head = msg.split(".")[0]
    for source in ("guardrails", "strategies", "codes"):
        assert source in head, (
            f"the failure does not name {source!r} in its list of sources that "
            f"came back empty (first sentence was: {head!r}). "
            f"'a source was empty' is not actionable."
        )

    # And it must distinguish one empty source from all three.
    with pytest.raises(EmptyRegistry) as one:
        gloss_registry(guardrails={"G1": {"tested"}}, strategies={}, codes={"TRC": {"trace"}})
    only = str(one.value).split(".")[0]
    assert "strategies" in only and "guardrails" not in only, (
        f"with only `strategies` empty the failure should name that one alone; "
        f"got: {only!r}")


def test_pl_c10c_the_real_registry_is_not_empty():
    """`TRC-C10` - and the derivation actually works against real governance.

    Without this, the guard above could be satisfied forever by a derivation
    that never returns anything.
    """
    reg = gloss_registry()
    assert len(reg) >= 5, f"the derived registry has only {len(reg)} entries"
    for code in ("G5", "S10", "TRC"):
        assert code in reg, f"{code} has no derived meaning"
    assert "human" in " ".join(reg["G5"]).lower(), (
        f"G5's derived meaning does not mention a human: {reg['G5']}"
    )


# ---------------------------------------------------------------------------
# `TRC-C2`, C3, C7 - the order is the rule, not the nearness
# ---------------------------------------------------------------------------

def test_pl_c2_bare_code_is_counted():
    """`TRC-C2` - a code with no meaning in front of it is counted."""
    hits = count_bare_codes("the G5 guard kicked in")
    assert len(hits) == 1 and hits[0].code == "G5", hits


def test_pl_c3_glossed_code_is_not_counted():
    """`TRC-C3` - meaning first, code in brackets, is the correct form."""
    assert count_bare_codes(
        "a human signs off on the irreversible (G5)") == []


def test_pl_c7_meaning_after_the_code_is_still_counted():
    """`TRC-C7` - what proximity alone gets wrong.

    The gloss is present and adjacent. The reader still met the code first.
    """
    hits = count_bare_codes(
        "G5 fired, which means a human signs off on the irreversible")
    assert len(hits) == 1, (
        "a gloss AFTER the code must still count - proximity is not the rule, "
        f"order is. Got: {hits}"
    )


def test_pl_c3b_the_sentence_before_also_counts_as_in_front():
    """`TRC-C3` - the gloss may sit in the preceding sentence."""
    assert count_bare_codes(
        "A human signs off on the irreversible. That is what G5 requires."
    ) == []


# ---------------------------------------------------------------------------
# `TRC-C8` - exempt when the identifier is the whole of its content
# ---------------------------------------------------------------------------

def test_pl_c8_whole_content_identifiers_are_exempt():
    """`TRC-C8` - an index entry is not a sentence that failed to explain itself."""
    assert is_whole_content("TRC-C6", "TRC-C6")
    assert is_whole_content("`TRC-C6`", "TRC-C6")
    assert not is_whole_content("TRC-C6 - the baseline records its reach", "TRC-C6")


def test_pl_c8b_a_bullet_opening_with_an_id_is_not_exempt():
    """`TRC-C8` - the case a positional exemption would have wrongly allowed."""
    hits = count_bare_codes("| TRC-C6 | INT-2 | test |\n\n"
                            "TRC-C6: the baseline now records its reach.")
    assert [h.code for h in hits] == ["TRC-C6"], (
        "the table cells must be exempt and the sentence must not be. "
        f"Got: {[(h.code, h.line) for h in hits]}"
    )


def test_pl_c8c_no_file_is_exempt_as_a_whole():
    """`TRC-C8` - the rule cannot be dodged by choosing where to write."""
    import plain_language_check as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    assert "EXEMPT_PATHS" not in src and "exempt_files" not in src, (
        "a path-based exemption would let the rule be avoided by choosing a "
        "file to write in, which is how the v1 vocabulary spread"
    )


# ---------------------------------------------------------------------------
# `TRC-C4`, C6 - advisory, with a baseline so the number can move
# ---------------------------------------------------------------------------

def test_pl_c4_count_reports_without_blocking():
    """`TRC-C4` - the count never changes an exit status."""
    for text in ("", "the G5 guard kicked in", "G1 G2 G3 G4 G5 " * 50):
        hits = count_bare_codes(text)
        assert isinstance(hits, list)


def test_pl_c6_baseline_records_count_and_reach():
    """`TRC-C6` - a report with no baseline cannot show a number moving."""
    b = load_baseline()
    for key in ("count", "locations", "files_scanned", "printed_output_reach"):
        assert key in b, f"the baseline does not record {key!r}"
    reach = b["printed_output_reach"]
    assert "covered" in reach and "of" in reach, (
        "the baseline must record the printed-output reach it measured, so a "
        f"zero is not misread as covering everything. Got: {reach}"
    )


# ---------------------------------------------------------------------------
# `TRC-C1`, C5 - the rule is stated where the writer and the reviewer stand.
# Both presence-shaped. Each check names a string that would be absent
# without the rule, because presence checks pass by accident.
# ---------------------------------------------------------------------------

def test_pl_c1_strategy_states_the_order_with_four_real_pairs():
    """`TRC-C1` - meaning leads, code follows, with pairs from real output.

    The rule is stated in strategies.md; the pairs that prove it live in
    strategies-rationale.md. Both halves are needed - the rule without pairs
    is an assertion, and the pairs without the rule are an anecdote.
    """
    doc = (REPO_ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    doc = " ".join(doc.replace("*", "").split())
    assert "plain words come first" in doc.lower(), (
        "the ordering rule is not stated - `S7` says an identifier carries its "
        "meaning on first use, but never which comes first"
    )
    # Scoped to `S7`'s own section. Counting across the whole rationale file
    # let four "instead of" phrases from any other strategy's evidence stand
    # in for `S7`'s pairs - the same loose match these guards exist to catch.
    rationale = (REPO_ROOT / "governance" / "strategies-rationale.md").read_text(
        encoding="utf-8")
    parts = re.split(r"(?m)^## ", rationale)
    s7 = [p for p in parts if p.split("\n", 1)[0].strip().endswith("(`S7`)")]
    assert s7, (
        "governance/strategies-rationale.md has no `## ... (`S7`)` section, "
        "so the pairs this counts have no home and it would count them from "
        "an unrelated strategy")
    section = " ".join(s7[0].replace("*", "").split())
    pairs = section.lower().count("instead of")
    assert pairs >= 4, (
        f"the rule shows {pairs} before-and-after pairs; it needs at least 4, "
        f"taken from this project's real output rather than invented"
    )
    assert "EV-T" in section, (
        "the 'EV-T collision from F3' sentence is the example the whole "
        "requirement was written from and is not among the pairs"
    )


def test_pl_c5_reviewer_instructions_name_the_bare_code():
    """`TRC-C5` - the reviewer is told what to look for, not just to be careful."""
    doc = (REPO_ROOT / "agents" / "reviewer.md").read_text(encoding="utf-8")
    # Normalise whitespace and emphasis first, because hard-wrapped prose
    # splits phrases across lines.
    low = " ".join(doc.replace("*", "").split()).lower()
    assert "no plain words in front of it" in low, (
        "the reviewer's instructions do not name a bare code as something to "
        "look for under the clarity dimension"
    )
    assert "never to delete the code" in low or "not by deleting" in low, (
        "the instructions do not say the fix is to add meaning rather than "
        "remove the identifier - which is the shortcut the count rewards"
    )


# ---------------------------------------------------------------------------
# Group D - a title is a summary; a body is a description; a correction is
# not finished while the record still contradicts itself.
# ---------------------------------------------------------------------------

def _strategies() -> str:
    doc = (REPO_ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    return " ".join(doc.replace("*", "").split()).lower()


def test_pl_d1_title_rule_names_the_refused_shapes():
    """`TRC-D1` - the rule refuses named shapes, and states its own scope."""
    doc = _strategies()
    for shape in ("slogan", "theme", "play on words", "the x that y"):
        assert shape in doc, f"the title rule does not refuse a {shape!r}"
    assert "blog post" in doc, (
        "the rule gives no test - 'if the title would work as a blog post "
        "title, it is wrong' is the one a writer can apply to their own draft"
    )
    assert "adr titles" in doc, (
        "the rule does not state its scope, so someone will apply it by "
        "analogy and start flattening ADR titles"
    )
    assert "heading" in doc, (
        "the rule does not distinguish a neat formulation in body prose, "
        "which is allowed, from the same formulation as a heading"
    )


def test_pl_d2_body_template_has_its_four_sections():
    """`TRC-D2` - what changed, what breaks, how to check it, where to look."""
    tpl = REPO_ROOT / "templates" / "pull-request-body.md"
    assert tpl.is_file(), f"{tpl} does not exist"
    low = " ".join(tpl.read_text(encoding="utf-8").replace("*", "").split()).lower()
    for section in ("what changed", "what breaks", "how to check", "where to look"):
        assert section in low, f"the body template has no {section!r} section"
    assert "how the work went" in low, (
        "the template does not tell the author to leave out the story of how "
        "the work went, which is the most common way a body gets long"
    )


def test_pl_d3_commit_guidance_points_at_the_title_rule():
    """`TRC-D3` - one rule, referenced, not two rules that drift apart."""
    doc = _strategies()
    # Target the guidance paragraph: "commit title" also appears in the
    # rule's opening sentence.
    i = doc.find("commit titles follow")
    assert i != -1, (
        "no commit-title guidance in strategies.md - expected a paragraph "
        "beginning 'Commit titles follow ...'"
    )
    near = doc[i:i + 400]
    assert "same rule" in near, (
        "the commit guidance does not say it is the same rule, so it will be "
        "read as a second rule and the two will drift apart"
    )
    assert "drift" in near, (
        "the guidance does not say WHY it points rather than restates"
    )


def test_pl_d4_correction_rule_is_stated_as_a_checklist_item():
    """`TRC-D4` - stated as an item, because advice alone was not followed."""
    doc = _strategies()
    assert "worse than the original error" in doc, (
        "the correction rule does not say why it matters - that a record "
        "contradicting itself leaves the next reader with two answers"
    )
    assert "re-read the summary last" in doc, (
        "the summary-last habit is not stated. It is the specific mechanical "
        "cause: a summary is written first, the body changes underneath it, "
        "and nothing sends the writer back to the top"
    )


def test_pl_c2b_the_receipt_puts_meaning_before_the_policy_code():
    """`TRC-C2` - the release's own receipt obeys the rule the release writes.

    `compass issue receipt` rendered each fired policy rule as
    "<id>: <rationale>", so a reader met an unresolvable code and learned what
    it did only afterwards. That is the defect `S7` forbids in as many words,
    in the flagship artifact of the release that forbids it.

    Deliberately narrow. Two other findings from the same read - the Gates
    block naming eight ids with no statement of what they check, and
    justifications truncated mid-sentence - are NOT fixed here: both need
    design and a one-screen budget, and they are filed as
    receipt-and-scan-container-gaps.

    Reads the checked-in fixture, not the live issue - the live issue lives
    in a directory git ignores.
    """
    out = _fixture_receipt()
    fired = [l for l in out.splitlines() if re.search(r"\((RP|G|S)[-\w]+\)\s*$", l)]
    assert fired, "no fired policy rules in the receipt to check"
    for line in fired:
        body = line.strip()
        assert not re.match(r"^(RP|G|S|TRC|EV|INT|FU|CLM)[-\w]*\s*:", body), (
            f"the receipt still opens a policy-rule line with its code:\n  {body}\n"
            f"State what the rule did, then the code in brackets."
        )
        assert re.search(r"\((RP|G|S)[-\w]+\)\s*$", body), (
            f"the code should follow the meaning, in brackets, so it stays "
            f"searchable:\n  {body}"
        )


def test_pl_c12_claims_gate_states_traceability_not_truth():
    """`TRC-C12` - the one gate whose name promises less than a reader hears."""
    g = (REPO_ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8")
    g_norm = " ".join(g.split()).lower()
    assert "traceability, not truth" in g_norm, (
        "guardrails.yml does not say claim-traces-to-scenario checks "
        "traceability rather than truth"
    )
    skill = _evidence_gates_text()
    s_norm = " ".join(skill.replace("*", "").split()).lower()
    assert "cannot check that what the claim says is true" in s_norm, (
        "the evidence-gates skill does not tell the reviewer the check cannot "
        "verify a claim's truth - which is where a person has to do it"
    )
    assert "repaired to zero" in s_norm, (
        "the skill states the rule without the worked instance. The instance is "
        "what makes it land: a claim that traced correctly and was false."
    )


def test_pl_c6b_the_count_states_its_own_limit_when_it_reports():
    """`TRC-C6` - a number that is known to be high says so where it is read.

    The check counts every occurrence; `S7` asks about first use per piece of
    output. Every report must state the gap - otherwise an adopter either
    wastes time or widens the matcher, and widening a matcher to fix a false
    positive is the failure this release named.
    """
    from plain_language_check import KNOWN_LIMIT, report
    line = report(count_bare_codes("the G5 guard kicked in"))
    assert "1 bare code" in line
    # Case-insensitive: the note writes "FIRST use" for emphasis.
    low = line.lower()
    for phrase in ("first use", "31%", "do not widen",
                   "plain-language-count-first-use-per-output"):
        assert phrase in low, f"the report does not carry {phrase!r}"
    b = load_baseline()
    assert "THE_CHECK_IS_STRICTER_THAN_THE_RULE" in b, (
        "the baseline file does not record that the check is stricter than the "
        "rule - the figure would be read as the rule's own target")
    assert b.get("count_first_use_only"), "the baseline records no first-use figure"


def test_pl_x3_repair_keeps_the_code():
    """`TRC-X3` - a repair adds meaning; it never deletes the identifier.

    The counting check rewards deletion: remove the code and the count falls.
    That trades a reader's small confusion for a broken traceability chain, and
    ADR-017 settled that the codes stay.

    "How a future repair is made" is a counterfactual and not mechanically
    expressible. What IS expressible is its consequence, against the committed
    baseline: every identifier the baseline recorded in a file must still be
    present in that file. A count that fell because a gloss was added is a
    repair; a count that fell because an identifier vanished is the shortcut.
    """
    b = load_baseline()
    locations = b.get("locations") or []
    assert locations, "the baseline records no locations to check against"
    missing = []
    for loc in locations:
        f = REPO_ROOT / loc["file"]
        if not f.is_file():
            continue  # a moved or deleted file is a different question
        if loc["code"] not in f.read_text(encoding="utf-8", errors="ignore"):
            missing.append(f"{loc['code']} is gone from {loc['file']}")
    assert not missing, (
        f"{len(missing)} identifier(s) recorded in the baseline are no longer "
        f"present in their file. If the count fell because a code was deleted "
        f"rather than explained, that is the shortcut this forbids - the codes "
        f"carry the traceability and the machine checks read them "
        f"(ADR-017):\n  " + "\n  ".join(missing[:20]))


def test_pl_x4_quoted_tool_string_is_left_unchanged():
    """`TRC-X4` - a banned word quoted from a tool survives, byte for byte.

    Distinct from `TRC-B4`, which proves the SCANNER does not flag a quoted word.
    This proves the quoted string is still there to be searched for - the reason
    the exception exists. A scanner that ignores a quotation and a repair that
    paraphrases it produce the same clean scan and different documents.
    """
    strategies = (REPO_ROOT / "governance" / "strategies.md").read_text(encoding="utf-8")
    # The live instance: mutation proof (`S10`) quotes the exact command
    # whose behaviour it is explaining. Paraphrasing it would make the
    # passage describe a command nobody can run, which is the loss the
    # exception prevents.
    assert r"git grep -n -i -E '\bseam\b'" in strategies, (
        "`S10`'s worked example no longer quotes the exact command it explains. "
        "The quoted-term exception exists so a reader can search for the string; "
        "a paraphrase removes exactly that."
    )
    assert "`git grep -n -i -E" in strategies, (
        "the quotation is no longer inside a code span, so the scanner will "
        "flag it and the next person will 'fix' it by paraphrasing"
    )
    # And the scanner genuinely leaves it alone - the other half of the pair.
    import sys as _s
    _s.path.insert(0, str(REPO_ROOT / "tests"))
    from test_terminology import BAN_PATTERNS
    line = [l for l in strategies.splitlines() if r"\bseam\b" in l][0]
    for pat in BAN_PATTERNS.get("seam / seams", []):
        assert not pat.search(line), (
            f"the quoted command is flagged by {pat.pattern!r} - the exception "
            f"is not being honoured, and the repair pressure lands on a string "
            f"the reader needs verbatim")


def test_pl_c9_derivation_failure_names_the_file():
    """`TRC-C9` - a loud break is only useful if it says what broke.

    The gloss registry is derived from three governance files rather than
    hand-written, trading silent drift for loud breakage. Two things make the
    breakage useful: an error naming which file changed shape, and the coupling
    being visible from the other end. Without the first, "loud" becomes
    "cryptic" and the next person deletes the check.
    """
    from plain_language_check import EmptyRegistry, gloss_registry
    with pytest.raises(EmptyRegistry) as exc:
        gloss_registry(guardrails={}, strategies={}, codes={})
    msg = str(exc.value)
    for named in ("guardrails.yml", "strategies.md", "codes"):
        assert named in msg, (
            f"the failure does not name {named!r} as a source it derives from - "
            f"someone meeting this error has nowhere to look")
    assert "refuses to report a count of zero" in msg, (
        "the failure does not say why it refuses to report zero")

    # Visible from the other end: each source says a check reads its structure.
    for path, phrase in (
        ("governance/guardrails.yml", "A CHECK DERIVES FROM THIS FILE'S STRUCTURE"),
        ("governance/terminology.yml", "A CHECK DERIVES FROM THIS BLOCK'S STRUCTURE"),
    ):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert phrase in text, (
            f"{path} does not warn that a check derives from its structure, so "
            f"someone editing it is surprised by a break somewhere else")
        assert "TRC-C9" in text, f"{path} does not name the criterion behind the note"


def test_pl_b5_no_un_conflate_in_governance():
    """`TRC-B5` - "un-conflate" is gone, and the replacement says the same thing."""
    for f in sorted((REPO_ROOT / "governance").rglob("*.md")):
        assert "conflate" not in f.read_text(encoding="utf-8").lower(), (
            f"{f.relative_to(REPO_ROOT)} still uses a form of 'conflate' - it is "
            f"on the everyday-words list because a reader has to look it up")
    readme = (REPO_ROOT / "governance" / "README.md").read_text(encoding="utf-8")
    assert "a guardrail blocks and" in readme, (
        "the replacement dropped the meaning rather than restating it - the "
        "sentence has to still say what the split between the two IS")


def test_pl_d5_empty_scan_habit_is_stated():
    """`TRC-D5` - a search returning zero is not believed until it has been tried."""
    doc = " ".join((REPO_ROOT / "governance" / "strategies.md")
                   .read_text(encoding="utf-8").replace("*", "").split())
    low = doc.lower()
    assert "a result of zero is not believed" in low, (
        "S10 does not state the empty-search rule")
    assert "run it against one string you know is there" in low or \
           "against one string you know is there" in low, (
        "the rule does not say what to actually do - two seconds of work is the "
        "whole point of it")
    assert r"\bseam\b" in doc, (
        "the rule cites no real instance. The one that produced it: "
        "git grep -E does not honour \\b, so a word-boundary scan returned "
        "nothing while the plain pattern found four uses")


def test_pl_g3_living_spec_title_matches_its_source_scenario():
    """`TRC-G3` - the derived spec says what its source says.

    The living spec derives from each landed issue's `manifest.yml` scenario
    TITLES, not from the prose headings. A correction applied to the heading
    and not the manifest leaves the two disagreeing, and the derivation
    faithfully reproduces the one nobody edited.
    """
    text = "".join((REPO_ROOT / "docs" / name).read_text(encoding="utf-8")
                   for name in ("system-spec.md", "system-spec-archive.md"))
    # Assembled, never written literally - the same convention every other
    # guard in this suite uses, so this file is not an exception to the rule
    # it enforces.
    needle = "vacu" + "ous"
    needle2 = "vacu" + "ity"
    assert needle not in text and needle2 not in text, (
        "the living spec still carries a word on the everyday-words list. It is "
        "derived - fix the source scenario title in its issue's manifest.yml and "
        "re-derive; editing this file is undone by the next derivation.")
    src = REPO_ROOT / ".compass/work/identifiers-and-vocabulary-in-printed-output/manifest.yml"
    if src.is_file():
        assert needle not in src.read_text(encoding="utf-8"), (
            "the SOURCE manifest still says it, so the next derivation puts it back")


def test_pl_d6_correction_rule_distinguishes_record_from_claim():
    """`TRC-D6` - which places take a correction, and which take a note.

    Strategy `S14` says apply a correction everywhere it belongs. Without
    saying WHERE it belongs, a moved number forces a false choice: falsify a
    record to keep it consistent with today, or leave a false claim standing
    because rewriting felt dishonest.
    """
    doc = " ".join((REPO_ROOT / "governance" / "strategies.md")
                   .read_text(encoding="utf-8").replace("*", "").split()).lower()
    assert "a record of what happened keeps its number" in doc, (
        "S14 does not say a record keeps its number")
    assert "a claim about what is true gets corrected" in doc, (
        "S14 does not say a claim gets corrected")
    for why in ("falsifies it", "leaves it false"):
        assert why in doc, (
            f"S14 does not say why ({why!r}) - without the reason the rule is a "
            f"convention someone will reverse")
    rationale = " ".join((REPO_ROOT / "governance" / "strategies-rationale.md")
                         .read_text(encoding="utf-8").split()).lower()
    assert "sixteen checks" in rationale, (
        "S14's rule has no real instance behind it - the sixteen-checks case "
        "moved to strategies-rationale.md with the other evidence, and if it "
        "is in neither file the rule is unsupported")


# A purpose-built issue on disk, not the one being worked on. These tests assert
# properties of the RENDERER, and a fixture exercises that completely.
#
# A test that reads the current issue passes only while that issue is
# current, and its state is not in version control.
RECEIPT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "receipt-fixture-project"

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



def _fixture_receipt() -> str:
    import subprocess
    import sys as _sys
    r = subprocess.run(
        [_sys.executable, str(REPO_ROOT / "cli" / "compass"), "issue", "receipt",
         "--issue", "receipt-example", "--workdir", str(RECEIPT_FIXTURE)],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (
        f"the receipt fixture would not render, so nothing below establishes "
        f"anything:\n{r.stdout}{r.stderr}")
    return r.stdout


def test_pl_c13_evidence_rows_are_one_line_and_lead_with_what_was_proved():
    """`TRC-C13` - the evidence block is a table a reader can scan down.

    One line per entry, and what was proved before where to find it.
    """
    out = _fixture_receipt()
    block = out.split("Evidence\n--------\n", 1)[1].split("\n\n", 1)[0]
    rows = [l for l in block.splitlines() if l.strip()]

    orphans = [l for l in rows if not re.match(r"\s+EV-", l)]
    assert not orphans, (
        f"{len(orphans)} continuation line(s) in the evidence block. Every "
        f"entry is one row, or the block cannot be scanned:\n  "
        + "\n  ".join(orphans[:5]))

    # Asserted as properties, not as the words the fixture happens to use, so
    # rewording the fixture does not fail a test whose subject is the layout.
    titled = [l for l in rows if "the fixture scenario" in l]
    assert titled, f"no row carries a scenario title:\n{block}"
    row = titled[0]
    assert row.index("the fixture scenario") < row.index("test-run"), (
        f"the row puts the evidence type before what was proved:\n  {row}")
    assert "evidence/" not in block, (
        "the evidence block still prints file paths. They were retired on "
        "2026-08-15: widest column, derivable from the id for per-scenario "
        "records, and rendered as 'evidence/gr...' once the line capped.")
    assert "SCN-001 - the fixture scenario" in row, (
        "the row dropped the scenario id. The title is the content and the id "
        "is the cross-reference; a record whose evidence id does not carry the "
        "scenario would lose its link entirely.")


def test_pl_c15_evaluator_puts_meaning_before_the_code():
    """`TRC-C15` - both screens that print a fired rule read the same way.

    Both screens that print a fired rule must put the meaning first: the
    receipt and `compass approach evaluate`. This asserts the property on
    both, not just one - one screen's renderer can drift from the other's.
    """
    import subprocess
    import sys as _sys
    ev = subprocess.run(
        [_sys.executable, str(REPO_ROOT / "cli" / "compass"), "approach", "evaluate",
         "--assessment", "risk=contained",
         "--assessment", "familiarity=brownfield-unmapped",
         "--assessment", "size=standard", "--assessment", "goal=delivery",
         "--assessment", "role=engineer", "--assessment", "labels=auth"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=60).stdout
    rc = _fixture_receipt()

    for screen, out, marker in (("evaluator", ev, "written down"),
                                ("receipt", rc, "Architectural fitness")):
        rule_lines = [l for l in out.splitlines() if marker in l]
        assert rule_lines, f"no fired-rule line found on the {screen} screen"
        for line in rule_lines:
            body = line.strip().lstrip("- ")
            assert not re.match(r"^[\[(]?(RP|G|S|TRC|EV|INT|FU|CLM)[-\w]*[\])]?\s*[:\]]",
                                body), (
                f"the {screen} opens a fired-rule line with its code:\n  {body}\n"
                f"State what the rule did, then the code in brackets.")
            # The code can share its brackets with the rule's kind, as in
            # "(RP-FLOOR-002, floor)".
            assert re.search(r"\((RP|G|S)[-\w]+[,)]", body), (
                f"the {screen} dropped the code entirely - it carries the "
                f"traceability and must stay, in brackets:\n  {body}")
