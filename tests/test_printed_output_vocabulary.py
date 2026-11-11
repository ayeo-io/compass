"""No retired vocabulary name reaches a screen.

The fix is at the print boundary: the machine keys are unchanged, so no
retired name can be printed whatever the underlying key is called.

Scenario ids: see identifiers-and-vocabulary-in-printed-output/
acceptance-criteria.md (groups B, C, E). The test that held the receipt to the
words "policy rules" went when 9.0.0 removed the receipt (ADR-091).
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


def _evaluate(*extra, cwd=None):
    args = [sys.executable, str(CLI), "approach", "evaluate", "--verbose"]
    for pair in ASSESSMENT:
        args += ["--assessment", pair]
    args += list(extra)
    r = subprocess.run(args, cwd=str(cwd or ROOT), capture_output=True, text=True,
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

#: The eight stage keys of a manifest written before the four-stage path.
LEGACY_STAGE_KEYS = {"assess", "define", "refine", "plan", "breakdown", "implement",
                     "verify", "ship"}


def test_trc_b3_spine_keys_are_the_current_ones(tmp_path):
    """The manifest is written with the current keys, and old ones still read.

    A manifest written today is on the four-stage path (ADR-092): it records
    the evidence owed and no stage map, and its stages are the path's. One
    written before still loads (ADR-006), to the eight stage keys of 8.x.
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
    # What the write prints holds no retired machine name either.
    assert not _strict_hits(r.stdout), _strict_hits(r.stdout)

    manifest = yaml.safe_load(
        (root / ".compass" / "work" / "demo" / "manifest.yml").read_text())
    # ADR-092 decision: no stage modes, so a manifest written today has no stage
    # map. Its stages are the four path stages, fixed in code.
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import path_stages
    from compass_pkg.stable_ids import PATH_STAGE_IDS
    assert "stages" not in manifest, sorted(manifest["stages"])
    assert manifest["evidence_required"], manifest
    assert path_stages.stages_of(manifest) == PATH_STAGE_IDS

    # A manifest written before the rename still loads (ADR-006).
    from compass_pkg.core import normalize_spine
    old_spine = {"stages": {"frame": "full", "specify": "full", "clarify": "light",
                            "plan": "full", "distribute": "solo-or-pair",
                            "build": "full", "verify": "full", "land": "full"}}
    assert set(normalize_spine(old_spine)["stages"]) == LEGACY_STAGE_KEYS, (
        "a manifest written before the rename does not normalise to the 8.x "
        "stage set")
    # The stored approach value is the current one. ADR-092 decision: no
    # approaches, so the critical, `auth` change that was `full` is `delivery`.
    assert manifest["delivery_approach"] == "delivery", (
        f"the stored approach value changed; only the printed word should: "
        f"{manifest['delivery_approach']!r}")


# ---------------------------------------------------------------------------
# `TRC-E1` - a shared effect prints once
# ---------------------------------------------------------------------------

def test_trc_e1_shared_effect_printed_once(tmp_path):
    """Two rules of a project's `require_evidence` both add the architecture
    review. The rules are NOT merged - they fire on different conditions and
    both conditions are worth seeing - so each still prints, and the evidence
    and the gate they share are each named once. (The check set
    no longer holds the floors `RP-REQUIRE-003` and `RP-REQUIRE-004` since
    ADR-099, so a project's own rules carry the case.)
    """
    (tmp_path / "compass.yml").write_text(
        "schema: 1\n"
        "require_evidence:\n"
        "  - when: {risk: [cross-cutting, critical]}\n"
        "    add: [architecture]\n"
        "  - when: {labels_any: [auth, payments, personal-data, migrations]}\n"
        "    add: [architecture]\n", encoding="utf-8")
    out = _evaluate(cwd=tmp_path)

    owed = [ln for ln in out.splitlines() if ln.strip().startswith("evidence owed   :")]
    assert len(owed) == 1, owed
    assert owed[0].split(", ").count("architecture") == 1, owed[0]
    gates = [ln for ln in out.splitlines() if ln.strip().startswith("gate set")]
    assert len(gates) == 1 and gates[0].count("verify.architecture") == 1, gates

    for rule in ("RP-SETTING-1", "RP-SETTING-2"):
        assert rule in out, (
            f"{rule} stopped printing - the rules were merged rather than "
            f"their duplicate output deduplicated:\n{out}")
