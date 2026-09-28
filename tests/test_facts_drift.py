"""The checkable claims in the most-read documents match the live policy.

The vocabulary scan guards words. Numbers and claims were not guarded, and
they drifted: the routing deep dive gave gate counts the evaluator does not
compute, called `verify.claims` immovable when the policy says it is
role-scoped, and the derived-spec header named an input and a path the
derivation does not use.

This is a small, explicit registry, not a document compiler. Each entry names
a document, the sentence that makes a claim, and the live fact it claims. The
fact is computed from `governance/routing-policy.yml` through the same
evaluator `compass approach evaluate` runs, or from the CLI's own code. A claim
that is reworded so its pattern no longer matches fails too, so the registry
moves with the prose.

Scenario ids: FDG-1 to FDG-5, in the delivery approach of issue
`facts-drift-guard`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.flow import _DERIVED_HEADER  # noqa: E402
from compass_pkg.issue_layout import docs_dir_for  # noqa: E402

DEEP_DIVE = ROOT / "docs" / "routing-deep-dive.md"
POLICY = yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                        .read_text(encoding="utf-8"))["routing_guardrails"]

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9}


def _gates(tmp_path, name, assessment):
    """The gate ids the evaluator computes for an assessment."""
    task = tmp_path / ".compass" / "work" / name
    task.mkdir(parents=True)
    body = "".join(f"  {k}: {v}\n" for k, v in assessment.items())
    (task / "manifest.yml").write_text(
        f"schema_version: '2.0'\nissue: {name}\ncreated: '2026-09-25'\n"
        f"status: active\nassessment:\n{body}evidence: []\ngates: []\n"
        "scenarios: []\n")
    result = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--issue", name,
         "--write"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    manifest = yaml.safe_load((task / "manifest.yml").read_text())
    return [g["id"] for g in manifest.get("gates") or []]


def _section(heading):
    """The deep dive's text from a `## ` heading to the next one."""
    text = DEEP_DIVE.read_text(encoding="utf-8")
    start = text.index(heading)
    end = text.find("\n## ", start + len(heading))
    return " ".join(text[start:end if end != -1 else None].split())


def _one(pattern, text, where):
    found = re.findall(pattern, text)
    assert len(found) == 1, (
        f"{where}: expected the claim /{pattern}/ exactly once, found "
        f"{len(found)}. If the prose was reworded, update this registry.")
    return found[0]


BASE = {"familiarity": "brownfield-mapped", "goal": "delivery",
        "role": "engineer"}

#: (case heading, claim pattern, assessment the case scores)
GATE_CLAIMS = [
    ("## Case 1 - A typo fix", r"(\w+) (?:light )?gates? at verify",
     dict(BASE, risk="trivial", size="atomic", labels="[]")),
    ("## Case 2 - A normal-sized new feature", r"(\w+) gates? at verify",
     dict(BASE, risk="contained", size="standard", labels="[]")),
    ("## Case 5 - A production hotfix", r"runs (\w+) gates, not the base",
     dict(BASE, risk="cross-cutting", size="small", urgency="live-defect",
          labels="[]")),
    ("## Case 6", r"The (\w+) gate is",
     dict(BASE, risk="contained", familiarity="brownfield-unmapped",
          size="small", goal="exploration", labels="[]")),
]


@pytest.mark.parametrize("heading, pattern, assessment", GATE_CLAIMS,
                         ids=[c[0][3:10] for c in GATE_CLAIMS])
def test_fdg_1_the_deep_dive_gate_counts_match_the_evaluator(
        tmp_path, heading, pattern, assessment):
    claimed = _one(pattern, _section(heading), heading)
    gates = _gates(tmp_path, "case", assessment)
    assert WORDS.get(claimed.lower()) == len(gates), (
        f"{heading}: the deep dive says {claimed} gate(s); the evaluator "
        f"computes {len(gates)}: {gates}")


def test_fdg_2_the_immovable_list_and_never_skip_match_the_policy():
    text = " ".join(DEEP_DIVE.read_text(encoding="utf-8").split())
    listed = _one(r"The immovable gates \(([^)]*)\)", text, "immovable list")
    claimed = re.findall(r"`([\w.]+)`", listed)
    policy = [g["gate"] for g in POLICY["immovable_gates"]]
    assert claimed == policy
    for match in re.findall(r"never_skip: \[([^\]]*)\]", text):
        floor = next(f for f in POLICY["floors"] if f.get("never_skip"))
        assert [s.strip() for s in match.split(",")] == floor["never_skip"]


def _blocks(text):
    """Paragraphs and list items, each with its whitespace collapsed, so a
    claim split across lines or across two sentences stays together."""
    block, out = [], []
    for line in text.splitlines():
        starts_item = re.match(r"^\s*(?:[-*]|\d+\.)\s", line)
        if not line.strip() or starts_item:
            if block:
                out.append(" ".join(" ".join(block).split()))
            block = [line] if line.strip() else []
        else:
            block.append(line)
    if block:
        out.append(" ".join(" ".join(block).split()))
    return out


def _calls_claims_immovable(block):
    """Does the block say the claims gate is immovable? "Immovable" must be
    attached to it - `verify.claims` is (an) immovable, or a claims block
    that says "this/it is an immovable gate" - so a block that lists the
    real immovable gates and mentions claims elsewhere is not counted."""
    low = block.lower()
    if re.search(r"\b(neither|not|never)\b[^.;]*\bimmovable", low):
        return False
    return bool(re.search(r"verify\.claims`?\s+(?:is\s+)?(?:an\s+)?immovable", low)
                or (re.search(r"\bclaims?\b", low) and re.search(
                    r"\b(?:this|it)\s+is\s+an?\s+immovable", low)))


def _shipped_markdown():
    files = subprocess.run(["git", "ls-files", "*.md"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout
    return [f for f in files.split()
            if not re.match(r"docs/compass/[^/]+/", f)
            and f != "docs/system-spec.md"]


def test_fdg_2_no_document_calls_verify_claims_immovable():
    """`verify.claims` is role-scoped, not immovable. The claim stood in the
    deep dive and, after that was fixed, in six more files, because this
    check named four documents. It now reads every tracked Markdown file
    outside the issue records and the derived spec."""
    assert "verify.claims" not in [g["gate"] for g in POLICY["immovable_gates"]]
    hits = []
    for rel in _shipped_markdown():
        for block in _blocks((ROOT / rel).read_text(encoding="utf-8")):
            if _calls_claims_immovable(block):
                hits.append(f"{rel}: {block[:100]}")
    assert not hits, "\n".join(hits)


def test_fdg_2_the_scan_finds_a_planted_claim_and_passes_a_negation():
    assert _calls_claims_immovable(
        "- **claims** - does every claim trace? This is an immovable gate.")
    assert _calls_claims_immovable("`verify.claims` is an immovable gate")
    assert not _calls_claims_immovable(
        "`verify.claims` by the role in play, so neither is immovable.")


def test_fdg_3_the_contract_names_the_clis_document_home():
    text = " ".join((ROOT / "compass-contract.md").read_text(encoding="utf-8")
                    .split())
    home = docs_dir_for("<created>", "<slug>").replace("\\", "/") + "/"
    _one(re.escape(home), text, "compass-contract.md")


def test_fdg_4_the_derived_header_names_the_real_command_and_input():
    header = _DERIVED_HEADER
    assert "compass _derive-system-spec" in header, header
    assert "manifest.yml" in header and "scenarios" in header, header
    # The scenario's prose lives in acceptance-criteria.md, so the header may
    # name it as a file to edit; it must not name the retired `<task>` path.
    assert "<task>" not in header and ".compass/work/<" not in header


def test_fdg_5_every_registered_claim_is_found_exactly_once():
    """The per-claim tests call `_one`; this names the registry as a whole,
    so a reader sees what is guarded in one place."""
    for heading, pattern, _ in GATE_CLAIMS:
        _one(pattern, _section(heading), heading)
