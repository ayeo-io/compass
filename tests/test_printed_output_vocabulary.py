"""No retired vocabulary name reaches a screen.

The fix is at the print boundary: the machine keys are unchanged, so no
retired name can be printed whatever the underlying key is called.

Scenario ids: see identifiers-and-vocabulary-in-printed-output/
acceptance-criteria.md (groups B, C, E).
"""

# These tests read the detail `compass approach evaluate --verbose` prints.
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

sys.path.insert(0, str(ROOT / "tests"))
from test_terminology import BAN_PATTERNS                       # noqa: E402

# Layer 2 of the guard (see below): the retired machine values that are never
# ordinary English in printed output.
#
# `land` and `standard` are DELIBERATELY ABSENT. "before critical changes
# land" and "the standard of proof" are correct English, and banning them
# outright would force governance prose to contort around the guard. They stay
# covered by layer 1, whose patterns fire on the capitalised and heading forms
# that show the retired *name* rather than the ordinary word.
STRICT_RETIRED = ("expedition", "express", "frame", "specify", "clarify",
                  "distribute", "route")

ASSESSMENT = ["risk=critical", "familiarity=brownfield-mapped", "size=small",
              "goal=delivery", "role=engineer", "labels=auth"]


def _evaluate(*extra):
    args = [sys.executable, str(CLI), "approach", "evaluate", "--verbose"]
    for pair in ASSESSMENT:
        args += ["--assessment", pair]
    args += list(extra)
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                       timeout=60)
    assert r.returncode == 0, f"evaluate failed:\n{r.stdout}{r.stderr}"
    return r.stdout


def _strict_hits(text):
    """Retired machine values appearing as whole words."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for name in STRICT_RETIRED:
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", line, re.I):
                hits.append((lineno, name, line.strip()))
    return hits


def _prose_hits(text):
    """Layer 1 - the repository's own prose ban patterns."""
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for term, patterns in BAN_PATTERNS.items():
            if any(p.search(line) for p in patterns):
                hits.append((lineno, term, line.strip()))
                break
    return hits


# ---------------------------------------------------------------------------
# `TRC-B1` - the evaluator speaks one vocabulary
# ---------------------------------------------------------------------------

def test_trc_b1_evaluator_prints_no_retired_name():
    out = _evaluate()

    strict = _strict_hits(out)
    assert not strict, (
        "the approach evaluator prints retired machine names:\n" +
        "\n".join(f"  line {n}: {term!r} in {line}" for n, term, line in strict))

    prose = _prose_hits(out)
    assert not prose, (
        "the approach evaluator prints retired vocabulary in prose:\n" +
        "\n".join(f"  line {n}: {term!r} in {line}" for n, term, line in prose))


# ---------------------------------------------------------------------------
# `TRC-B2` - the guard can fail
# ---------------------------------------------------------------------------

def test_trc_b2_the_scan_can_fail():
    """The control. Without it, `TRC-B1` passes against a scan matching nothing.

    The line below is the real output this issue exists to remove, quoted
    exactly. Both layers are exercised: `expedition` is a machine value that
    only layer 2 catches, and `Land` capitalised is a prose form that only
    layer 1 catches.
    """
    machine = "    [RP-FLOOR-003] ... - route raised standard -> expedition"
    found = {name for _, name, _ in _strict_hits(machine)}
    assert {"route", "expedition"} <= found, (
        f"the strict scan missed the retired names in the real defect line - "
        f"it found {found or 'nothing'}")

    prose = "requirement: Irreversible-surface tasks have fitness before Land."
    assert _prose_hits(prose), (
        "the prose scan reports nothing for a line carrying a retired stage "
        "name in its heading form")

    # ...and it does not fire on correct output, or it would be unusable.
    clean = "  FINAL APPROACH  : initiative"
    assert not _strict_hits(clean) and not _prose_hits(clean), (
        "the scan fires on correct v2 output")


# ---------------------------------------------------------------------------
# `TRC-B3` - the machine contract is untouched
# ---------------------------------------------------------------------------

def test_trc_b3_spine_keys_are_the_current_ones(tmp_path):
    """The manifest is written with the current stage keys, and old ones still read.

    A manifest written today uses the current stage keys, and one written
    before still loads (ADR-006).
    """
    root = tmp_path / "proj"
    (root / ".compass" / "work" / "demo").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "work" / "demo" / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "demo", "created": "2026-08-13",
        "status": "active",
        "assessment": {"risk": "critical", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery", "role": "engineer",
                       "labels": ["auth"]},
    }, sort_keys=False))

    r = subprocess.run(
        [sys.executable, str(CLI), "approach", "evaluate", "--verbose", "--issue", "demo",
         "--write"], cwd=str(root), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"

    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "demo" / "manifest.yml").read_text())
    assert set(manifest["stages"]) == {
        "assess", "define", "refine", "plan", "breakdown", "implement",
        "verify", "ship"}, (
        f"a manifest written today does not carry the current stage keys: "
        f"{sorted(manifest['stages'])}")

    # A manifest written before the rename still loads (ADR-006).
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.core import normalize_spine
    old_spine = {"stages": {"frame": "full", "specify": "full", "clarify": "light",
                            "plan": "full", "distribute": "solo-or-pair",
                            "build": "full", "verify": "full", "land": "full"}}
    assert set(normalize_spine(old_spine)["stages"]) == set(manifest["stages"]), (
        "a manifest written before the rename does not normalise to the same "
        "stage set as one written after it")
    # The stored approach value is already v2 - `canonical_shape` converts it
    # on write.
    assert manifest["delivery_approach"] == "full", (
        f"the stored approach value changed; only the printed word should: "
        f"{manifest['delivery_approach']!r}")


# ---------------------------------------------------------------------------
# `TRC-C1` - a routing rule is not a guardrail
# ---------------------------------------------------------------------------

def _receipt_out(tmp_path, fired):
    root = tmp_path / "proj"
    (root / ".compass" / "work" / "demo").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "work" / "demo" / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "demo", "created": "2026-08-13",
        "status": "landed",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "standard", "topology": "solo",
        "policy_rules_fired": fired,
        "stages": {}, "gates": [], "evidence": [], "scenarios": [],
        "changed_files": [], "claims": [], "follow_ups": [],
        "reassessments": [], "friction": [],
    }, sort_keys=False))
    r = subprocess.run(
        [sys.executable, str(CLI), "issue", "receipt", "--issue", "demo"],
        cwd=str(root), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{r.stdout}{r.stderr}"
    return r.stdout


def test_trc_c1_receipt_says_policy_rules(tmp_path):
    """Both branches of the conditional, which is why this exists.

    The receipt has two sites: the list and the "none" case.
    """
    with_rules = _receipt_out(tmp_path / "a", [
        {"id": "RP-FLOOR-002", "kind": "floor",
         "rationale": "Domain risk overrides size."}])
    without = _receipt_out(tmp_path / "b", [])

    for label, out in (("rules fired", with_rules), ("none", without)):
        assert "routing guardrails" not in out, (
            f"the receipt's {label} branch still calls a routing rule a "
            f"guardrail. `guardrail` is the reserved word for the five hard "
            f"blocking rules:\n{out}")
        assert "policy rules fired" in out, (
            f"the receipt's {label} branch does not name policy rules, which "
            f"is what the evaluator already calls them:\n{out}")


# ---------------------------------------------------------------------------
# `TRC-E1` - a shared effect prints once
# ---------------------------------------------------------------------------

def test_trc_e1_shared_effect_printed_once():
    """Two pairs do this, not one.

    RP-REQUIRE-001/002 both add verify.analyze and RP-REQUIRE-003/004 both add
    verify.architecture. The rules are NOT merged - they fire on different
    conditions and both conditions are worth seeing - so each still prints
    with its own rationale.
    """
    out = _evaluate()

    for gate in ("verify.analyze", "verify.architecture"):
        effect_lines = [ln for ln in out.splitlines()
                        if ln.strip().startswith("-") and gate in ln]
        assert len(effect_lines) == 1, (
            f"the effect line for {gate} is printed {len(effect_lines)} "
            f"times; the tool reads as repeating itself:\n"
            + "\n".join(effect_lines))

    for rule in ("RP-REQUIRE-001", "RP-REQUIRE-002",
                 "RP-REQUIRE-003", "RP-REQUIRE-004"):
        assert rule in out, (
            f"{rule} stopped printing - the rules were merged rather than "
            f"their duplicate output deduplicated:\n{out}")
