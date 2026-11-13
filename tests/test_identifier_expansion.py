"""An identifier never appears without its meaning on first use.

An agent reading `guardrails.yml` uses the id as the name, because the id is
each guardrail's primary key in the file. `compass check` already prints the
id with its statement - `G5 A human signs off on the irreversible` - so this
test holds the guidance to that. The tests that held the receipt to it went
when 9.0.0 removed the receipt (ADR-091).

The rule has two halves and both matter. Expand on first use; leave the bare
id everywhere after that. Always-expand would be its own readability defect,
and the ids carry the traceability the machine checks depend on.

Scenario ids: see identifiers-and-vocabulary-in-printed-output/
acceptance-criteria.md (group A).
"""
from __future__ import annotations

import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
STRATEGIES = ROOT / "governance" / "strategies.md"
TERMINOLOGY = ROOT / "governance" / "terminology.yml"

# ---------------------------------------------------------------------------
# `TRC-A1` - the rule is stated where agent speech is governed
# ---------------------------------------------------------------------------

def test_trc_a1_the_rule_is_stated():
    """The cold-reader strategy and the vocabulary agree on one rule.

    Checked in both places on purpose: `strategies.md` is what an agent
    reads, `terminology.yml` is what the scan reads. Both must say to add
    the meaning, not replace the code, because the machine checks run on
    the code.
    """
    text = STRATEGIES.read_text(encoding="utf-8")
    s7 = text.split("(`S7`)", 1)
    assert len(s7) == 2, "no S7 section found in strategies.md"
    body = s7[1].split("(`S8`)")[0]

    assert re.search(r"identifier", body, re.I), (
        "the cold-reader strategy says nothing about identifiers - the rule "
        "that a code carries its meaning on first use has no home")
    assert re.search(r"first use", body, re.I), (
        "the identifier rule does not say WHEN to expand. 'Always expand' is "
        "its own defect; the rule is first use, then the bare id")
    for surface in ("speech", "printed output", "generated artifact"):
        assert re.search(surface, body, re.I), (
            f"the rule does not name '{surface}' as a surface it governs")
    assert re.search(r"compass check", body), (
        "the rule does not point at `compass check`, which already prints "
        "the identifier and its plain statement together")

    doc = yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))
    entry = next((b for b in (doc.get("banned") or [])
                  if "G1" in str(b.get("term", ""))), None)
    assert entry, "the vocabulary no longer carries the guardrail-code entry"
    joined = f"{entry.get('replacement', '')} {entry.get('context', '')}"
    assert re.search(r"first use", joined, re.I), (
        f"the vocabulary entry still tells a writer to drop the code rather "
        f"than expand it on first use: {entry!r}")
    assert "S14" in str(entry.get("term", "")), (
        f"the entry still names S1..S7; the strategies run to S14: {entry!r}")
