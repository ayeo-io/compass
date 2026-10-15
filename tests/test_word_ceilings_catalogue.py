"""Scenarios WCL-1, WCL-2 and WCL-11 of the issue `word-ceilings-and-lld`.

The catalogue's `word_ceiling` field, the one word count and the `<unit>`
filename placeholder of the `low-level-design` kind. Each scenario test is
named for its scenario id. The other tests here cover the helpers the later
units call: `word_ceiling.count_words`, `word_ceiling.limit` and
`artifact_kinds.unit_of`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_artifact_catalogue_fields import (  # noqa: E402
    SLUG, _charter, _cli, _evaluate, _fixture, _justify_all, _lint, _manifest_of,
    _scratch, _words)

PRESET = ROOT / "governance" / "presets" / "default"
LLD_HEADINGS = ["Signatures", "Contracts", "File-level plan", "Tests this unit writes"]


def _preset_artifacts():
    return yaml.safe_load((PRESET / "artifacts.yml").read_text(encoding="utf-8"))["artifacts"]


# --- WCL-1: the catalogue carries the two word limits -----------------------------

def test_wcl_1_catalogue_word_limits(tmp_path):
    from compass_pkg import artifact_kinds

    artifacts = _preset_artifacts()
    assert artifacts["technical-design"]["word_ceiling"] == {"thorough": 4000,
                                                             "lightweight": 1200}
    assert artifacts["acceptance-criteria"]["word_ceiling"] == {"thorough": 5000,
                                                                "lightweight": 1500}
    others = [kind for kind, body in artifacts.items()
              if kind not in ("technical-design", "acceptance-criteria")
              and "word_ceiling" in body]
    assert others == [], others
    assert [kind for kind, body in artifacts.items() if "ceiling" in body] == []
    assert "word_ceiling" not in artifact_kinds.FILLED_FIELDS
    code, report, text = _lint(_scratch(tmp_path))
    assert code == 0, text


def test_an_earlier_generation_reads_with_no_word_limit():
    # A stored entry from before the field existed gains the descriptive fields
    # from the shipped default, and never the word limit.
    from compass_pkg import artifact_kinds, word_ceiling

    stored = SimpleNamespace(config={"artifacts": {
        "technical-design": {"file": "technical-design.md", "stage": "plan"}}})
    filled = artifact_kinds.entry(stored, "technical-design")
    assert "sections" in filled and "word_ceiling" not in filled
    assert word_ceiling.limit(stored, "technical-design", "thorough") is None
    # The same kind with the field stored reads its own value, per depth.
    stored.config["artifacts"]["technical-design"]["word_ceiling"] = {"thorough": 900}
    assert word_ceiling.limit(stored, "technical-design", "thorough") == 900
    assert word_ceiling.limit(stored, "technical-design", "lightweight") is None
    assert word_ceiling.limit(stored, "technical-design", None) is None
    assert word_ceiling.limit(stored, "no-such-kind", "thorough") is None


@pytest.mark.parametrize("text, words", [
    ("", 0),
    ("one two  three\nfour\tfive\n", 5),
    ("# Title\n\nSome words here.\n", 5),
    ("| a | b |\n|---|---|\n| c | d |\n", 11),
    ("```python\ndef f(x): ...\n```\n", 5),
    ("before <!-- a hidden comment --> after\n", 2),
    ("<!--\nmany\nhidden\nwords\n-->\nkept\n", 1),
    ("# T\n\n<!-- compass:render coverage -->\nlots of rendered words here\n"
     "<!-- /compass:render -->\n\ntail\n", 3),
])
def test_count_words(text, words):
    from compass_pkg import word_ceiling

    assert word_ceiling.count_words(text) == words


def test_count_words_ignores_a_change_to_block_text_only():
    from compass_pkg import word_ceiling

    template = ("# Design\n\n<!-- compass:render document-header -->\n%s\n"
                "<!-- /compass:render -->\n\nOne two three.\n")
    assert (word_ceiling.count_words(template % "")
            == word_ceiling.count_words(template % "a b c d e f g h")
            == 5)


# --- WCL-2: policy lint refuses a malformed word limit or filename ------------------

MALFORMED = {
    "bare-number": 4000,
    "zero": {"thorough": 0},
    "negative": {"thorough": -5},
    "words": {"thorough": "many"},
    "unknown-depth": {"lightweight": 1500},
}


def test_wcl_2_policy_lint_refuses_malformed(tmp_path):
    # Each shape in a project of its own, so each run reports that shape alone.
    for name, value in MALFORMED.items():
        kind = f"charter-{name}"
        layer = {"schema": 1, "artifacts": {
            kind: _charter(file=f"{kind}.md", word_ceiling=value)}}
        code, report, text = _lint(_scratch(tmp_path / name, layer))
        assert code != 0, (name, text)
        lines = [line for line in _words(report) if "word_ceiling" in line]
        assert len(lines) == 1, (name, _words(report))
        assert lines[0].startswith("error ") and kind in lines[0], (name, lines)
    # Booleans are not whole numbers here.
    layer = {"schema": 1, "artifacts": {
        "charter-bool": _charter(file="charter-bool.md", word_ceiling={"thorough": True})}}
    code, report, text = _lint(_scratch(tmp_path / "bool", layer))
    assert code != 0 and [line for line in _words(report)
                          if "charter-bool" in line and "word_ceiling" in line], text
    # A valid map on intent passes: any kind may carry a limit. Intent lists
    # headings at thorough only, so that is the one depth it can limit. The
    # field is compared by identity, so a project that changes a shipped kind's
    # limit names the change in a waiver, as it would for `required_when`.
    layer = {"schema": 1, "owner": "jed72", "artifacts": {"intent": {
        "set": {"word_ceiling": {"thorough": 2000}},
        "waiver": {"reason": "Our intents stay short.", "approved_by": "jed72",
                   "approved_on": "2026-10-15"}}}}
    code, report, text = _lint(_scratch(tmp_path / "intent", layer))
    assert code == 0, text
    assert not [line for line in _words(report) if "word_ceiling" in line], text
    # A project limit on a shipped kind at a depth the shipped sections do not
    # list is an error, as on a project's own kind: no later layer narrowed them.
    layer = {"schema": 1, "owner": "jed72", "artifacts": {"intent": {
        "set": {"word_ceiling": {"lightweight": 500}},
        "waiver": {"reason": "Our intents stay short.", "approved_by": "jed72",
                   "approved_on": "2026-10-15"}}}}
    code, report, text = _lint(_scratch(tmp_path / "intent-depth", layer))
    assert code != 0, text
    lines = [line for line in _words(report) if "word_ceiling" in line]
    assert len(lines) == 1 and lines[0].startswith(
        "error artifacts.intent.word_ceiling.lightweight"), _words(report)
    # A file holding both placeholders is refused, naming the kind.
    layer = {"schema": 1, "artifacts": {
        "charter-both": _charter(file="charter-both/<unit>-<n>.md")}}
    code, report, text = _lint(_scratch(tmp_path / "both", layer))
    assert code != 0, text
    lines = [line for line in _words(report) if "artifacts.charter-both.file" in line]
    assert len(lines) == 1 and lines[0].startswith("error "), _words(report)
    # A directory part is allowed only with <unit>.
    layer = {"schema": 1, "artifacts": {
        "charter-dir": _charter(file="charter-dir/notes.md"),
        "charter-unit": _charter(file="charter-unit/<unit>.md")}}
    code, report, text = _lint(_scratch(tmp_path / "dir", layer))
    lines = _words(report)
    assert [line for line in lines if "artifacts.charter-dir.file" in line], lines
    assert not [line for line in lines if "artifacts.charter-unit" in line], lines


def test_the_classifier_compares_a_word_limit_by_identity():
    import copy

    from compass_pkg import classify, merge, policy_lint

    parent, _ = policy_lint.load_parent()
    base, provenance = merge.apply({}, parent.doc, parent.kind, parent.name, {})

    def verdict(layer):
        child, _ = merge.apply(copy.deepcopy(base), layer, "project", "project",
                               dict(provenance))
        return classify.classify(base, child).result

    for value in ({"thorough": 3000, "lightweight": 1200},
                  {"thorough": 5000, "lightweight": 1200},
                  {"thorough": 4000}):
        layer = {"schema": 1, "artifacts": {
            "technical-design": {"set": {"word_ceiling": value}}}}
        assert verdict(layer) == "incomparable", value
    same = {"schema": 1, "artifacts": {"technical-design": {"set": {
        "word_ceiling": {"thorough": 4000, "lightweight": 1200}}}}}
    assert verdict(same) == "equivalent"
    # A limit on a kind nothing owes changes no obligation.
    unowed = {"schema": 1, "artifacts": {"review": {"set": {
        "word_ceiling": {"thorough": 900}}}}}
    assert verdict(unowed) == "equivalent"
    from compass_pkg import classify as module
    assert module.CLASSIFIER_VERSION == 6


def test_a_project_that_narrows_the_sections_keeps_a_passing_lint(tmp_path):
    # The shipped design limits both depths. A project that lists headings at
    # thorough only inherits a lightweight limit that never applies: a warning
    # naming the field, and no error.
    layer = {"schema": 1, "artifacts": {"technical-design": {"set": {"sections": {
        "thorough": ["Approach", "Design decisions (ADR-style)", "Work units", "Gate"]}}}}}
    code, report, text = _lint(_scratch(tmp_path, layer))
    assert code == 0, text
    lines = [line for line in _words(report) if "word_ceiling" in line]
    assert len(lines) == 1, _words(report)
    assert lines[0].startswith("warning artifacts.technical-design.word_ceiling.lightweight")


# --- WCL-11: the kind is declared and no approach registers it ----------------------

def test_wcl_11_kind_declared_no_approach(tmp_path):
    lld = _preset_artifacts()["low-level-design"]
    assert lld["file"] == "low-level-design/<unit>.md"
    assert (lld["stage"], lld["owner"], lld["stands_for"]) == ("plan", "planner", "lld")
    assert lld["sections"] == {"thorough": LLD_HEADINGS}
    assert "word_ceiling" not in lld
    # approaches.yml is byte for byte as on main where this branch started.
    base = subprocess.run(["git", "merge-base", "HEAD", "origin/main"], cwd=ROOT,
                          capture_output=True, text=True)
    if base.returncode != 0:
        pytest.skip("origin/main is not available, so there is no base to compare with")
    path = "governance/presets/default/approaches.yml"
    before = subprocess.run(["git", "show", f"{base.stdout.strip()}:{path}"], cwd=ROOT,
                            capture_output=True)
    assert before.returncode == 0, before.stderr
    assert (ROOT / path).read_bytes() == before.stdout
    # A full issue's evaluate registers no low-level design.
    root, task_dir = _fixture(tmp_path, "full", risk="critical", size="large")
    code, out, err = _evaluate(root, *_justify_all(_manifest_of(task_dir)["assessment"]))
    assert code == 0, out + err
    body = _manifest_of(task_dir)
    assert body["delivery_approach"] == "full"
    assert [a for a in body["artifacts"] if a["kind"] == "low-level-design"] == []
    # The kind's template prints through template show.
    code, out, err = _cli(root, "issue", "template", "show", "low-level-design",
                          "--issue", SLUG)
    assert code == 0, out + err


def test_unit_placeholder_helpers():
    from compass_pkg import artifact_kinds

    lld = {"file": "low-level-design/<unit>.md"}
    review = {"file": "review-<n>.md"}
    assert artifact_kinds.UNIT_MARK == "<unit>"
    assert artifact_kinds.per_unit(lld) and not artifact_kinds.per_unit(review)
    assert not artifact_kinds.repeats(lld)
    assert artifact_kinds.filename(lld, unit="U3") == "low-level-design/U3.md"
    assert artifact_kinds.filename(lld) == "low-level-design/<unit>.md"
    assert artifact_kinds.filename(review, 2) == "review-2.md"
    assert artifact_kinds.unit_of(lld, "low-level-design/U3.md") == "U3"
    assert artifact_kinds.unit_of(lld, "low-level-design/U12.md") == "U12"
    for name in ("low-level-design/U0.md", "low-level-design/U01.md",
                 "low-level-design/core.md", "low-level-design/a/U1.md",
                 "low-level-design.md", "U1.md"):
        assert artifact_kinds.unit_of(lld, name) is None, name
    assert artifact_kinds.unit_of(review, "review-1.md") is None
    assert artifact_kinds.home(".compass/work/x", lld, unit="U2").endswith(
        "/low-level-design/U2.md")
    # A per-unit kind matches no top-level name in the documents folder.
    assert not artifact_kinds.matches_kind({"low-level-design": lld}, "U1.md")
    assert not artifact_kinds.matches_kind({"low-level-design": lld},
                                           "low-level-design/U1.md")
