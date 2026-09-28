"""What a session reads is bounded, and the bounds are measured not asserted.

Two numbers, and they are different things:

  RESIDENT   in context on every turn whether used or not - the frontmatter
             descriptions of every skill, command and agent, plus the contract
             the SessionStart hook injects.
  PER RUN    what a session actually reads following the instructions for one
             quick fix, end to end.

Measured at HEAD before this issue: 1,744 words resident (~2,354 tokens) and
19,448 words per run (~26,254), rising to 26,567 (~35,865) with
`governance/strategies.md`, which `CLAUDE.md` told the model to read at the
start of every issue. Superpowers (another Claude Code plugin) is about 900
tokens resident.

The ceilings below are the issue's success signals. They are deliberately not
"whatever it is today plus a bit": a ceiling that tracks the tree cannot fail.

Scenario ids: IV-A1, IV-A2, IV-B1, IV-C1 in
instruction-volume/acceptance-criteria.md
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The success signals from intent.md, in words.
RESIDENT_CEILING = 900
QUICK_FIX_CEILING = 12000
SKILL_LINE_CEILING = 200


def _words(path):
    return len(path.read_text(encoding="utf-8").split())


def _description_words(path):
    """The frontmatter `description:`, which is what the runtime keeps loaded."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        return 0
    d = re.search(r"description:\s*(.+?)(?=\n[a-z_-]+:|\Z)", m.group(1), re.S)
    return len(d.group(1).split()) if d else 0


def _resident_breakdown():
    out = {}
    for label, paths in (
        ("skills", sorted((ROOT / "skills").glob("*/SKILL.md"))),
        ("commands", sorted((ROOT / "commands").glob("*.md"))),
        ("agents", sorted((ROOT / "agents").glob("*.md"))),
    ):
        out[label] = sum(_description_words(p) for p in paths)
    contract = ROOT / "compass-contract.md"
    out["contract"] = _words(contract) if contract.is_file() else 0
    return out


# What a quick fix reads, following the instructions. Listed rather than
# derived: deriving it from the instructions is the thing under test, and a
# measurement that reads its own subject cannot fail.
#
# A quick fix reads the files below. The feature and initiative delivery
# approaches also read the five stage commands and three skills.
QUICK_FIX_READS = [
    "compass-contract.md",
    "CLAUDE.md",
    "commands/quick-fix.md",
    "skills/quick-fix/SKILL.md",
]


def test_iv_a1_resident_cost_is_bounded():
    """Paid on every turn, used or not."""
    parts = _resident_breakdown()
    total = sum(parts.values())
    assert total <= RESIDENT_CEILING, (
        f"{total} words are resident on every turn, over the {RESIDENT_CEILING} "
        f"ceiling: " + ", ".join(f"{k} {v}" for k, v in sorted(parts.items()))
        + ". These are frontmatter descriptions and the injected contract - "
        "everything the runtime keeps loaded whether the session uses it or not."
    )


def test_iv_a2_a_quick_fix_reads_less_than_a_feature_should():
    """The whole point of a light approach is that it is light to run."""
    missing = [r for r in QUICK_FIX_READS if not (ROOT / r).is_file()]
    assert not missing, (
        "the quick-fix reading list names files that do not exist, so this "
        f"measurement is not measuring the real path: {', '.join(missing)}")

    per_file = {r: _words(ROOT / r) for r in QUICK_FIX_READS}
    total = sum(per_file.values())
    worst = sorted(per_file.items(), key=lambda kv: -kv[1])[:5]
    assert total <= QUICK_FIX_CEILING, (
        f"a quick fix reads {total} words, over the {QUICK_FIX_CEILING} "
        f"ceiling. The five largest: "
        + ", ".join(f"{k} ({v})" for k, v in worst))


def test_iv_b1_strategies_is_not_in_the_per_issue_read():
    """7,119 words - 27% of the per-run cost in one file.

    It is the reviewer's reference and the place a strategy is defined. Asking
    the model to read it at the start of every issue put the whole of it in
    context to apply two or three of its entries.
    """
    # The PARAGRAPH, not a character span. `[^.]{0,200}` stopped at the dot
    # inside `guardrails.md` and never reached the word it was looking for -
    # a false pass that looked exactly like a real one.
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    paragraphs = [p for p in text.split("\n\n") if "Read `governance/`" in p]
    if not paragraphs:
        return          # the instruction is gone entirely, which satisfies this
    passage = " ".join(paragraphs[0].split())
    assert "strategies.md" not in passage, (
        "CLAUDE.md still tells the model to read governance/strategies.md at "
        f"the start of every issue:\n  {passage}")


def test_iv_c1_no_skill_file_is_over_the_line_ceiling():
    """A long skill loads whole. Splitting lets the parts load when needed."""
    over = []
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        n = len(p.read_text(encoding="utf-8").splitlines())
        if n > SKILL_LINE_CEILING:
            over.append(f"{p.parent.name} ({n})")
    assert not over, (
        f"these skills are over {SKILL_LINE_CEILING} lines, so they load whole "
        "when any part of them is wanted: " + ", ".join(over))


def test_iv_c2_a_split_skill_still_says_where_its_parts_are():
    """Splitting a skill without pointing at the parts loses them.

    `compass-runtime` is the pattern: it carries the map and names the files
    that carry the rest.
    """
    for p in sorted((ROOT / "skills").glob("*/SKILL.md")):
        siblings = [q for q in p.parent.glob("*.md") if q.name != "SKILL.md"]
        if not siblings:
            continue
        body = p.read_text(encoding="utf-8")
        unreferenced = [q.name for q in siblings if q.name not in body]
        assert not unreferenced, (
            f"skills/{p.parent.name}/SKILL.md does not name "
            f"{', '.join(unreferenced)}, so nothing tells a session those "
            "parts exist")


def test_iv_d1_every_frontmatter_parses():
    """Every skill, command and agent frontmatter is valid YAML.

    A colon followed by a space in an unquoted scalar ends the key, so
    `description: The architect's perspective: reads ...` is a syntax error.
    The runtime reads frontmatter to decide what to load, so a broken one
    hides that file silently.
    """
    import yaml

    broken = []
    for directory, pattern in (("skills", "*/SKILL.md"),
                               ("commands", "*.md"),
                               ("agents", "*.md")):
        for path in sorted((ROOT / directory).glob(pattern)):
            text = path.read_text(encoding="utf-8")
            m = re.match(r"^---\n(.*?)\n---", text, re.S)
            if not m:
                broken.append(f"{path.relative_to(ROOT)}: no frontmatter")
                continue
            try:
                doc = yaml.safe_load(m.group(1))
            except yaml.YAMLError as exc:
                first = str(exc).splitlines()[0]
                broken.append(f"{path.relative_to(ROOT)}: {first}")
                continue
            if not isinstance(doc, dict) or not doc.get("description"):
                broken.append(f"{path.relative_to(ROOT)}: no description")

    assert not broken, (
        "these files have frontmatter the runtime cannot read, so it cannot "
        "know what they are for:\n  " + "\n  ".join(broken))
