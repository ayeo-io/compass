"""The Definition of Ready and the Definition of Done are data in the default preset.

The seven Definition of Ready items of `templates/requirements-review.md` and
the seven Definition of Done items of `templates/verification-report.md` are
`human` checks in `governance/presets/default/checks.yml`. Each statement is the
template's text, so the two cannot drift. The `plan` stage's `entry` list holds
the first seven and the `verify` stage's `exit` list holds the second seven.
The capability `entry-exit-evaluation` is off in `default@6`, so nothing runs
them yet and the generated legacy views do not name them.

Scenario ids: `RD-1` to `RD-8` (issue `ready-and-done-as-data`).
"""
from __future__ import annotations

import copy
import importlib
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

PRESET = ROOT / "governance" / "presets" / "default"
READY_TEMPLATE = ROOT / "templates" / "requirements-review.md"
DONE_TEMPLATE = ROOT / "templates" / "verification-report.md"
CAPABILITY = "entry-exit-evaluation"

READY_IDS = [
    "dor-summary-filled", "dor-problem-traces-up", "dor-behaviour-is-gwt",
    "dor-traceability-ids", "dor-affected-surface-named", "dor-no-open-questions",
    "dor-approach-still-fits",
]
DONE_IDS = [
    "dod-every-scenario-passes", "dod-suite-green", "dod-coverage-floor",
    "dod-no-lint-errors", "dod-traceability-intact", "dod-living-docs-updated",
    "dod-follow-ups-settled",
]

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_ITEM = re.compile(r"^- \[[ xX]\] ")
_TAG = re.compile(r"^\((?:evidence|follow-up): [^)]*\) ")


def template_items(path: Path, heading: str) -> list[str]:
    """The statements of the checkbox items under `heading`.

    A statement is the item with its checkbox, its inline tag and its emphasis
    marks removed and its line breaks joined. Items inside an HTML comment are
    syntax examples and do not count.
    """
    text = _COMMENT.sub("", path.read_text(encoding="utf-8"))
    start = text.index(f"\n{heading}\n") + len(heading) + 2
    section = re.split(r"\n#{1,6} |\nNext stage:", text[start:], maxsplit=1)[0]
    items: list[list[str]] = []
    for line in section.splitlines():
        if _ITEM.match(line):
            items.append([_ITEM.sub("", line)])
        elif items and line.startswith(" ") and line.strip():
            items[-1].append(line.strip())
        elif line.strip():
            raise AssertionError(f"stray line in {heading!r} of {path.name}: {line!r}; "
                                 "a section holds only checkbox items and their "
                                 "indented continuation lines")
    out = []
    for lines in items:
        joined = " ".join(part.strip() for part in lines)
        joined = _TAG.sub("", joined).replace("**", "").replace("*", "")
        out.append(" ".join(joined.split()))
    return out


def load_preset() -> dict:
    out = {}
    for name in ("checks", "stages", "preset"):
        doc = yaml.safe_load((PRESET / f"{name}.yml").read_text(encoding="utf-8"))
        out[name] = doc.get(name, doc) if name != "preset" else doc
    return out


def _check(preset: dict, check_id: str) -> dict:
    check = preset["checks"].get(check_id)
    assert check is not None, f"checks.{check_id} is missing from the preset"
    return check


def problems(preset: dict, ready_items: list[str], done_items: list[str]) -> list[str]:
    """Every way the preset's lists differ from the template text."""
    found: list[str] = []
    checks, stages = preset["checks"], preset["stages"]
    for label, ids, items, stage, side in (
        ("Definition of Ready", READY_IDS, ready_items, "plan", "entry"),
        ("Definition of Done", DONE_IDS, done_items, "verify", "exit"),
    ):
        if len(items) != len(ids):
            found.append(f"the {label} template has {len(items)} items, expected {len(ids)}")
        listed = stages.get(stage, {}).get(side)
        if listed != ids:
            found.append(f"stages.{stage}.{side} is {listed}, expected {ids}")
        for check_id, item in zip(ids, items):
            check = checks.get(check_id)
            if check is None:
                found.append(f"checks.{check_id} is missing for the {label} item {item!r}")
                continue
            if check.get("kind") != "human":
                found.append(f"checks.{check_id} is not kind human")
            if check.get("statement") != item:
                found.append(f"checks.{check_id} statement {check.get('statement')!r} "
                             f"differs from the template item {item!r}")
    return found


def _problems_now() -> list[str]:
    return problems(load_preset(),
                    template_items(READY_TEMPLATE, "### Definition of Ready"),
                    template_items(DONE_TEMPLATE, "### Definition of Done"))


def test_rd_1_the_ready_checks_equal_the_template_items():
    items = template_items(READY_TEMPLATE, "### Definition of Ready")
    assert len(items) == 7, items
    preset = load_preset()
    assert preset["stages"]["plan"].get("entry") == READY_IDS
    for check_id, item in zip(READY_IDS, items):
        check = _check(preset, check_id)
        assert check["kind"] == "human", check_id
        assert check["statement"] == item, check_id


def test_rd_2_the_done_checks_equal_the_template_items():
    items = template_items(DONE_TEMPLATE, "### Definition of Done")
    assert len(items) == 7, items
    preset = load_preset()
    assert preset["stages"]["verify"].get("exit") == DONE_IDS
    for check_id, item in zip(DONE_IDS, items):
        check = _check(preset, check_id)
        assert check["kind"] == "human", check_id
        assert check["statement"] == item, check_id


def test_rd_3_the_checks_are_inactive_blocking_and_say_what_a_skipped_stage_returns():
    preset = load_preset()
    assert preset["preset"]["capabilities"][CAPABILITY] is False
    for check_id in READY_IDS + DONE_IDS:
        check = _check(preset, check_id)
        assert check.get("requires") == [CAPABILITY], check_id
        assert check.get("severity") == "blocking", check_id
        assert "locked" not in check, check_id
        assert "impl" not in check, check_id
    for check_id in READY_IDS:
        assert _check(preset, check_id)["on_skipped"] == "not-applicable", check_id
    for check_id in DONE_IDS:
        assert _check(preset, check_id)["on_skipped"] == "fail", check_id
    lists = {(stage, side) for stage, body in preset["stages"].items()
             for side in ("entry", "exit") if side in body}
    assert lists == {("plan", "entry"), ("verify", "exit")}, lists
    humans = {name for name, c in preset["checks"].items() if c["kind"] == "human"}
    assert humans == set(READY_IDS + DONE_IDS)


def test_rd_4_the_views_do_not_name_the_human_checks():
    views = importlib.import_module("compass_pkg.legacy_views")
    preset = load_preset()
    deterministic = {n for n, c in preset["checks"].items() if views.has_implementation(c)}
    guardrails = yaml.safe_load((ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8"))
    assert set(guardrails["checks"]) == deterministic
    generated = views.generate(ROOT)
    for rel in ("governance/routing-policy.yml", "governance/guardrails.yml"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert text == generated[rel], rel
        for check_id in READY_IDS + DONE_IDS:
            assert check_id not in text, f"{rel} names {check_id}"
    for gate in yaml.safe_load((PRESET / "gates.yml").read_text(encoding="utf-8"))["gates"].values():
        assert not set(gate.get("checks", [])) & set(READY_IDS + DONE_IDS)


def _owed_checks(preset: dict, approaches: dict, approach: str) -> list[str]:
    """The checks an approach owes through the stage lists: those on a list of
    one of its stages whose required capabilities are all on. A stage list does
    not depend on the stage's mode, so a spike's conclude mode lists them too."""
    capabilities = preset["preset"]["capabilities"]
    owed = []
    for stage in approaches[approach]["stages"]:
        body = preset["stages"].get(stage, {})
        for check_id in body.get("entry", []) + body.get("exit", []):
            required = preset["checks"][check_id].get("requires", [])
            if all(capabilities.get(c) for c in required):
                owed.append(check_id)
    return owed


def _approaches() -> dict:
    return yaml.safe_load((PRESET / "approaches.yml").read_text(encoding="utf-8"))["approaches"]


def test_rd_6_a_spike_owes_none_of_the_checks_while_the_capability_is_off():
    preset, approaches = load_preset(), _approaches()
    assert _owed_checks(preset, approaches, "spike") == []
    assert _owed_checks(preset, approaches, "regular") == []
    # The gap is inert only while the capability is off: with it on, a spike
    # owes the Definition of Done in conclude mode, which a later increment
    # must exclude before turning evaluation on.
    planted = copy.deepcopy(preset)
    planted["preset"]["capabilities"][CAPABILITY] = True
    assert sorted(_owed_checks(planted, approaches, "spike")) == sorted(READY_IDS + DONE_IDS)


def test_rd_7_a_stray_line_in_a_template_section_is_refused(tmp_path):
    good = ("# T\n\n### Definition of Ready\n\n- [ ] **One** - first\n      continued\n"
            "- [ ] Two - second\n\nNext stage: x\n")
    path = tmp_path / "t.md"
    path.write_text(good, encoding="utf-8")
    assert template_items(path, "### Definition of Ready") == ["One - first continued",
                                                              "Two - second"]
    for label, stray in (("an unindented continuation", "unindented words\n"),
                         ("a plain bullet", "- a plain bullet\n"),
                         ("a paragraph", "Some prose.\n")):
        path.write_text(good.replace("- [ ] Two", stray + "- [ ] Two"), encoding="utf-8")
        with pytest.raises(AssertionError, match="stray line"):
            template_items(path, "### Definition of Ready")
        assert label


def test_rd_5_the_committed_preset_has_no_problems():
    assert _problems_now() == []


def test_rd_5_a_drifted_preset_or_template_names_the_item_that_differs():
    ready = template_items(READY_TEMPLATE, "### Definition of Ready")
    done = template_items(DONE_TEMPLATE, "### Definition of Done")
    base = load_preset()
    assert problems(base, ready, done) == []

    changed = list(ready)
    changed[2] = changed[2] + " Edited."
    assert any("dor-behaviour-is-gwt" in p and "differs" in p
               for p in problems(base, changed, done))

    missing = copy.deepcopy(base)
    del missing["checks"]["dod-suite-green"]
    assert any("checks.dod-suite-green is missing" in p for p in problems(missing, ready, done))

    reordered = copy.deepcopy(base)
    reordered["stages"]["plan"]["entry"].reverse()
    assert any(p.startswith("stages.plan.entry") for p in problems(reordered, ready, done))

    wrong_kind = copy.deepcopy(base)
    wrong_kind["checks"]["dor-no-open-questions"]["kind"] = "judged"
    assert any("dor-no-open-questions is not kind human" in p
               for p in problems(wrong_kind, ready, done))

    assert any("has 6 items" in p for p in problems(base, ready[:-1], done))


def test_rd_8_the_preset_headers_do_not_claim_the_adapter_wrote_the_files_once():
    """The preset is the source and its files are edited by hand, so a header
    that says the adapter wrote them once misleads the next editor."""
    adapter = (ROOT / "cli" / "compass_pkg" / "legacy_adapter.py").read_text(encoding="utf-8")
    assert "wrote these files once" not in adapter
    files = sorted(PRESET.glob("*.yml"))
    assert len(files) == 10
    for path in files:
        header = path.read_text(encoding="utf-8").split("schema:")[0]
        assert "wrote these files once" not in header, path.name
        assert "source of the shipped defaults" in header, path.name
