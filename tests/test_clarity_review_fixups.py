"""Production-code comments and headers corrected against two clarity
reviews of the prose-breaks-the-writing-style sweep.

Two clarity reviews, one covering batches 1 to 4 and one covering batches 5
to 9, each read the rewritten prose against the code beside it and found
comments and module headers that state something the code does not do. Both
are recorded in this issue's evidence registry, which git does not
distribute, so they are named here rather than cited by path (`PBW-A6`). This file pins the corrected text so a later rewrite cannot
reintroduce the same contradiction silently.

Findings covered (numbered as the batch 5-9 review numbers them):
  1. `cli/compass_pkg/policy.py` claimed `compass policy lint`, which is
     `governance.py`'s verb.
  2. `cli/compass_pkg/core.py` claimed the delivery-approach evaluator, which
     is `routing.py`'s.
  3. `cli/compass_pkg/receipt.py` said an evidence type with no renderer
     entry "lands as a path-only entry"; the renderer has no path column.
  4. `scripts/release.sh` gave a tar-exclude cause for a hard-fail check that
     no longer exists - the script never passes `--exclude` to tar.
  10. `cli/compass_pkg/terminal.py` attached "under every `add_parser` call"
      to the wrong noun.
  11. `cli/compass_pkg/manifest.py` led a sentence with a bare code, `G1`,
      with no plain word in front of it.
  12. `scripts/multiagent.sh` shipped the reviewing agent's own first-person
      uncertainty in a comment with no owner.
  14. `cli/compass_pkg/calibration.py` used three names for one thing across
      three lines; two matched the CLI's printed output, one did not.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read(rel):
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def test_policy_module_header_claims_only_its_own_verbs():
    text = _read("cli/compass_pkg/policy.py")
    header = text.split("\n", 20)
    header_block = "\n".join(header[:6])
    assert "compass policy lint" not in header_block
    assert "compass issue lint" in header_block
    assert "compass plan lint" in header_block


def test_core_module_header_does_not_claim_the_evaluator():
    text = _read("cli/compass_pkg/core.py")
    header_block = "\n".join(text.split("\n")[:6])
    assert "delivery-approach evaluator" not in header_block
    assert "governance discovery" in header_block


def test_receipt_comment_does_not_claim_a_path_only_entry():
    text = _read("cli/compass_pkg/receipt.py")
    assert "path-only entry" not in text
    assert "lands as a path-only entry" not in text


def test_release_sh_does_not_claim_a_live_unanchored_exclude():
    """The COMMENTS no longer claim a live unanchored exclude.

    The printed failure message still does, and deliberately so. Correcting
    it changes what a person running the command sees, and this issue claims
    no printed string changed - `tests/test_printed_strings_unchanged.py`
    holds that claim and reported this very line. The message correction is
    filed with the other printed-output fixes, and the assertion that pinned
    it went with them.
    """
    text = _read("scripts/release.sh")
    assert "unanchored .compass/work exclude strips them" not in text
    assert "The noise check below still checks." not in text


def test_multiagent_sh_comment_has_no_first_person_uncertainty():
    text = _read("scripts/multiagent.sh")
    assert "I have not checked whether that is" not in text


def test_terminal_py_subparser_comment_attaches_to_the_right_noun():
    text = _read("cli/compass_pkg/terminal.py")
    assert "under every\n    `add_parser` call" not in text
    assert "and eight more - under every `add_parser` call" not in text
    assert "belong on every leaf" in text


def test_manifest_py_g1_sentence_leads_with_a_plain_word():
    text = _read("cli/compass_pkg/manifest.py")
    assert "# `G1` is checked at the verify stage and at ship." not in text
    assert "tested-before-ship guardrail (`G1`)" in text


def test_calibration_py_uses_one_name_for_reframe_debt():
    text = _read("cli/compass_pkg/calibration.py")
    assert "Reframe debt is a misjudgement nobody recorded" not in text
    assert "An unrecorded re-assessment is a misjudgement nobody recorded" in text


def test_terminal_py_has_no_empty_comment_line():
    text = _read("cli/compass_pkg/terminal.py")
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "#" and 0 < i < len(lines) - 1:
            prev_is_comment = lines[i - 1].strip().startswith("#")
            next_is_code = lines[i + 1].strip() and not lines[i + 1].strip().startswith("#")
            assert not (prev_is_comment and next_is_code), (
                f"line {i + 1}: bare '#' where a paragraph was deleted")


def test_next_cmd_py_documents_the_format_it_prints():
    text = _read("cli/compass_pkg/next_cmd.py")
    assert "<phase> is collapsed on this route" not in text
    assert "<phase> collapsed on this route" in text


def test_checks_py_names_the_spec_file_once():
    text = _read("cli/compass_pkg/checks.py")
    assert "lives only in the spec (it has no structured" not in text
    assert "acceptance-criteria.md (it has no structured" in text


def test_analyze_py_names_where_the_invariants_are_defined():
    text = _read("cli/compass_pkg/analyze.py")
    assert "architecture/ownership.md" in text
