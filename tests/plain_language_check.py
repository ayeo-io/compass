"""Counts short codes that reach a reader before their meaning does.

The rule: the plain words come first, the code follows in brackets. "a human
signs off on the irreversible (G5)" is right. Both "the G5 guard kicked in" and
"G5 fired, which means a human signs off on the irreversible" are wrong - the
second is the one proximity alone gets wrong, because the gloss is adjacent and
the reader still met the code first. **The order is the rule, not the nearness.**

Two design decisions a reader should be able to argue with:

**The registry of meanings is DERIVED from governance, never hand-written.**
the default preset's gates state `G1`-`G5`, the strategy headings state `S1`-`S12`, and
`terminology.yml`'s `codes:` block already carries a `means:` per id prefix. A
hand-written table would go out of date without any check failing - it would
keep passing while describing codes that had been renamed. The cost is that
this couples to the shape of three files and can break for reasons unrelated
to writing. That break is loud; drift is not.

**A place is exempt when the identifier is the WHOLE of its content**, not
because of where it sits. A ledger cell holding `TRC-C6` is an index entry; a
cell holding `TRC-C6 - the baseline records its reach` is a sentence that put
its code first. A positional exemption gets widened by adding positions, which
is what ADR-015 did to markdown fences, Python literals and YAML values before
ADR-018 inverted the default. A content test has nothing to add.

Nothing here can fail a build. `EmptyRegistry` is the one exception and it is
not a style failure: it means the check could not see its own inputs, and a
zero from a blind check is worse than no number at all.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent
BASELINE_PATH = REPO_ROOT / "governance" / "plain-language-baseline.json"

# This covers every id prefix as well as the G and S codes.
CODE = re.compile(
    r"\b(?:TRC-[A-Z]+\d+|INT-\d+|EV-[A-Z0-9-]+|FU-\d+|CLM-\d+|RP-[A-Z]+-\d+"
    r"|ADR-\d+|PX-\d+|G[1-5]|S\d{1,2})\b"
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = {"the", "a", "an", "is", "are", "it", "that", "this", "and", "or",
              "of", "to", "in", "on", "for", "with", "not", "no", "be", "by"}


# Stated in every report this check produces, because an adopter who runs it
# and gets an inflated count either spends time finding out why, or widens
# the matcher until it catches nothing.
KNOWN_LIMIT = (
    "NOTE - this count is HIGH by design-not-yet-fixed: it counts every "
    "occurrence, while the rule (S7) asks only about the FIRST use in each piece "
    "of output. Measured overcount on this repository: 31% (466 vs 321). Do not "
    "widen the matcher to compensate. Tracked in "
    "plain-language-count-first-use-per-output."
)


def report(hits) -> str:
    """The count as a person should read it: the number, then what it does not mean."""
    return f"{len(hits)} bare code(s) found.\n{KNOWN_LIMIT}"


class EmptyRegistry(RuntimeError):
    """A source of code meanings came back empty.

    Raised rather than tolerated. With an empty registry no code has a known
    meaning, nothing can be counted as unexplained, and the count is zero -
    which is indistinguishable from a repository with nothing wrong in it. The
    target for this whole requirement is zero, so a zero that means "nothing
    was inspected" is the worst answer available.
    """


@dataclass(frozen=True)
class Hit:
    code: str
    line: int
    sentence: str


PRESET_DIR = REPO_ROOT / "governance" / "presets" / "default"


def _guardrail_meanings(preset: Path = PRESET_DIR,
                        guardrails: Path | None = None) -> dict[str, set[str]]:
    """Each default guardrail's words, from the preset's gates.

    The preset is the source of the shipped defaults and guardrails.yml is a
    view generated from it, so the preset is read first. The view is read
    only when the preset's gates file is absent.
    """
    gates_file = preset / "gates.yml"
    if gates_file.is_file():
        doc = yaml.safe_load(gates_file.read_text(encoding="utf-8")) or {}
        return {gid: _words(f"{g.get('name','')} {g.get('statement','')}")
                for gid, g in (doc.get("gates") or {}).items()
                if g.get("kind") == "guardrail" and (g.get("applies_to") or {}).get("ships")}
    path = guardrails or REPO_ROOT / "governance" / "guardrails.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = {}
    for g in doc.get("defaults") or []:
        gid = g.get("id")
        if gid:
            out[gid] = _words(f"{g.get('name','')} {g.get('statement','')}")
    return out


def _strategy_meanings() -> dict[str, set[str]]:
    path = REPO_ROOT / "governance" / "strategies.md"
    out = {}
    for m in re.finditer(r"^###\s+(.+?)\s*\(`(S\d+)`\)", path.read_text(encoding="utf-8"), re.M):
        out[m.group(2)] = _words(m.group(1))
    return out


def _prefix_meanings() -> dict[str, set[str]]:
    path = REPO_ROOT / "governance" / "terminology.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: _words(str(v.get("means", "")))
            for k, v in (doc.get("codes") or {}).items()}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", text.lower())
            if w not in _STOPWORDS}


def gloss_registry(guardrails=None, strategies=None, codes=None) -> dict[str, set[str]]:
    """What plain words count as explaining each code, read from governance.

    Every source is checked for emptiness by name. "a source was empty" is not
    actionable; "guardrails.yml returned nothing" is.
    """
    g = _guardrail_meanings() if guardrails is None else guardrails
    s = _strategy_meanings() if strategies is None else strategies
    c = _prefix_meanings() if codes is None else codes
    empty = [name for name, src in (("guardrails", g), ("strategies", s), ("codes", c))
             if not src]
    if empty:
        raise EmptyRegistry(
            f"the gloss registry is empty from: {', '.join(empty)}. "
            f"Derived from the default preset's gates (guardrails.yml, "
            f"generated from them, when the preset is absent), the strategy headings in "
            f"strategies.md, and terminology.yml's codes: block. With no "
            f"meanings on record every code looks unexplainable, so this "
            f"refuses to report a count of zero - a zero here would be "
            f"indistinguishable from a clean repository."
        )
    return {**c, **s, **g}


def is_whole_content(container: str, code: str) -> bool:
    """True when the identifier is the whole of its content.

    Deliberately not a list of exempt positions - see the module docstring.
    """
    return container.strip().strip("`*|").strip() == code


def _containers(line: str, match) -> str:
    """The cell or token this occurrence sits inside."""
    if line.lstrip().startswith("|"):
        start = 0
        for cell in line.split("|"):
            end = start + len(cell)
            if start <= match.start() < end + 1:
                return cell
            start = end + 1
    return line


def count_bare_codes(text: str, registry=None) -> list[Hit]:
    """Every code a reader meets before its meaning.

    A code is glossed when the plain words of its meaning appear BEFORE it, in
    its own sentence or the one before. After it does not count.
    """
    reg = gloss_registry() if registry is None else registry
    if not reg:
        raise EmptyRegistry(
            "the gloss registry is empty, so no code has a known meaning and "
            "the count would be zero for every input. Refusing to report a "
            "zero that means nothing was inspected."
        )
    hits: list[Hit] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        sentences = _SENTENCE_SPLIT.split(line)
        for m in CODE.finditer(line):
            if is_whole_content(_containers(line, m), m.group(0)):
                continue
            code = m.group(0)
            key = code if code in reg else code.split("-")[0]
            meaning = reg.get(key)
            if meaning and _glossed_before(text, lineno, line, m, meaning):
                continue
            hits.append(Hit(code=code, line=lineno,
                            sentence=next((s for s in sentences if code in s), line).strip()))
    return hits


def _glossed_before(text, lineno, line, match, meaning) -> bool:
    """Do the meaning's words appear before this code, here or one sentence back?"""
    lines = text.splitlines()
    prior_line = lines[lineno - 2] if lineno >= 2 else ""
    # "the sentence before" means the previous sentence, which is often on the
    # same line. Looking only at the previous LINE missed every case where two
    # sentences share one.
    sentences = _SENTENCE_SPLIT.split(line)
    same_sentence_before, prior_sentence = "", ""
    for i, s in enumerate(sentences):
        if match.group(0) in s:
            same_sentence_before = s[:s.index(match.group(0))]
            prior_sentence = sentences[i - 1] if i >= 1 else ""
            break
    window = _words(f"{prior_line} {prior_sentence} {same_sentence_before}")
    return len(window & meaning) >= 2


def load_baseline() -> dict:
    if BASELINE_PATH.is_file():
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    return {}
