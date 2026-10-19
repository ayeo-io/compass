"""Scenarios WCL-3 to WCL-10, WCL-14 and WCL-16 to WCL-19 of the issue `word-ceilings-and-lld`.

The check `design-within-word-ceiling`, the word-limit and missing-unit notes of
`compass issue lint`, and the archive boundary: an issue with no stored
generation, a closed issue, an issue on a catalogue with no word limit and an
issue before plan exit is due are never judged.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import artifact_status_support as sup  # noqa: E402
from test_document_set_sections import (  # noqa: E402
    _u3_check, _u3_copy_archive, _u3_evaluate, _u3_exit_without)

CHECK = "design-within-word-ceiling"
PRESET = ROOT / "governance" / "presets" / "default"
FULL = {"risk": "cross-cutting", "size": "large"}
HOTFIX = {"urgency": "live-defect", "size": "small"}
QUICK_FIX = {"risk": "trivial", "size": "small"}
SPIKE = {"goal": "exploration"}
UNITS = ("U1", "U2", "U3")
WAIVER = {"reason": "A fixture of the word-limit tests.", "approved_by": "jed72",
          "approved_on": "2026-10-15"}
#: The text of each lint note, as `design_size` words it.
WORD_NOTE = "words, over the"
UNIT_NOTE = "a work unit with no low-level design"


# --- fixtures -----------------------------------------------------------------------

def _filler(count, start=0):
    """`count` distinct words, so no writing rule reads them as repeated text."""
    return " ".join("w%d" % n for n in range(start, start + count))


def _units_table(units):
    lines = ["| Unit | Scenario group(s) it satisfies | Code surface it touches | "
             "Independent of | Low-level design |", "|---|---|---|---|---|"]
    lines += ["| %s | group | module | none | - |" % unit for unit in units]
    return "\n".join(lines) + "\n"


def _document(words, units=None, title="# Plan - feature"):
    """A document of exactly `words` words, by the shared count, with a Work units
    table naming `units` when given."""
    from compass_pkg import word_ceiling

    head = title + "\n\n<!-- compass:render document-header -->\n> rendered\n" \
                   "<!-- /compass:render -->\n\n## Approach\n\n"
    tail = "\n\n## Work units\n\n" + _units_table(units) if units else "\n"
    fixed = word_ceiling.count_words(head + tail)
    assert words >= fixed, (words, fixed)
    text = head + _filler(words - fixed) + tail
    assert word_ceiling.count_words(text) == words
    return text


def _project(tmp_path, assessment=None, compass_yml=None, stage="implement"):
    root = sup.project(tmp_path, compass_yml=compass_yml or {"schema": 1, "owner": "jed72"},
                       assessment=assessment)
    if stage:
        sup.edit(root, current_phase=stage)
    return root


def _write(root, kind, text, depth="thorough", path=True):
    """Write `kind`'s document and give its registry entry a path at `depth`."""
    (root / sup.DOCS / ("%s.md" % kind)).write_text(text, encoding="utf-8")
    sup.add_entry(root, kind, path=path, depth=depth)


def _register_units(root, units):
    """Write and register a low-level design for each of `units`."""
    body = sup.manifest(root)
    folder = root / sup.DOCS / "low-level-design"
    folder.mkdir(parents=True, exist_ok=True)
    for unit in units:
        rel = "%s/low-level-design/%s.md" % (sup.DOCS, unit)
        (root / rel).write_text("# Low-level design %s\n\n## Signatures\n\nNone.\n" % unit,
                                encoding="utf-8")
        body["artifacts"].append({"id": "ART-LOW_LEVEL_DESIGN-" + unit,
                                  "kind": "low-level-design", "unit": unit,
                                  "status": "draft", "path": rel,
                                  "reason": "registered by hand; no rule of the assessment "
                                            "asked for it"})
    sup.write_manifest(root, body)


def _lint(root):
    """`(exit code, word-limit notes, missing-unit notes)` of `compass issue lint`."""
    code, out, err = sup.run(root, "issue", "lint", "--issue", sup.SLUG)
    lines = [line.strip() for line in (out + err).splitlines()]
    return (code, [line for line in lines if WORD_NOTE in line],
            [line for line in lines if UNIT_NOTE in line])


def _row(root):
    """`(exit code, status, detail)` of the check's row, or a None row when absent."""
    code, rows = _u3_check(root)
    status, detail = rows.get(CHECK, (None, None))
    return code, status, detail, rows


def _declared(root):
    from compass_pkg import effective

    view = effective.view_or_legacy(str(root / ".compass" / "work" / sup.SLUG))
    return set((view.config.get("checks") or {}))


def _earlier_layer():
    """A project layer that stores the configuration as it was before this change:
    no word limits, no low-level-design kind and no design-size check."""
    artifacts = yaml.safe_load((PRESET / "artifacts.yml").read_text(encoding="utf-8"))
    entries = {}
    for kind in ("technical-design", "acceptance-criteria"):
        body = dict(artifacts["artifacts"][kind])
        body.pop("word_ceiling")
        entries[kind] = dict(body, replace=True, waiver=WAIVER)
    entries["low-level-design"] = {"remove": True}
    return {"schema": 1, "owner": "jed72", "artifacts": entries,
            "checks": {CHECK: {"remove": True, "waiver": WAIVER}},
            "vocabulary": {"checks." + CHECK: {"remove": True}}}


def _no_limit_layer():
    """A project layer whose catalogue has no word limit, with the check declared."""
    layer = _earlier_layer()
    del layer["checks"], layer["vocabulary"]
    del layer["artifacts"]["low-level-design"]
    return layer


# --- WCL-3: words are counted from the visible text only ---------------------------

_COUNTED = """\
# Spec

<!-- compass:render document-header -->
> **Issue:** feature · **Approach:** full
<!-- /compass:render -->

{prose}

| a | b |
|---|---|
| c | d |
| e | f |

<!-- {comment} -->

```python
{code}
```

## Coverage ledger

<!-- compass:render coverage -->
{coverage}
<!-- /compass:render -->
"""


def _counted(coverage):
    return _COUNTED.format(prose=_filler(100), comment=_filler(50, 1000),
                           code=_filler(10, 2000), coverage=coverage)


def test_wcl_3_word_count_visible_text(tmp_path, monkeypatch):
    from compass_pkg import design_size, word_ceiling

    # By hand: "# Spec" is 2 tokens, the prose 100, the table 4 rows of 5, 1, 5 and 5
    # tokens (16), the fence its 2 marker lines and 10 words (12), and "## Coverage
    # ledger" 3. The comment, the two blocks and their marker lines add 0.
    text = _counted(_filler(300, 3000))
    assert word_ceiling.count_words(text) == 2 + 100 + 16 + 12 + 3 == 133
    # A render that changes only block text changes the count by 0.
    assert word_ceiling.count_words(_counted(_filler(7, 9000))) == 133

    # The lint note and the check report the same figure, through one function.
    root = _project(tmp_path, assessment=FULL)
    _write(root, "technical-design", text)
    task_dir = str(root / ".compass" / "work" / sup.SLUG)
    task = sup.manifest(root)
    calls = []
    real = word_ceiling.count_words

    def spy(value):
        calls.append(value)
        return real(value)

    monkeypatch.setattr(word_ceiling, "count_words", spy)
    monkeypatch.setattr(word_ceiling, "limit",
                        lambda view, kind, depth: 100 if kind == "technical-design" else None)
    monkeypatch.setattr(design_size, "plan_exit_due", lambda task, task_dir: True)
    notes = design_size.lint_notes(task, task_dir)
    assert len(calls) == 1
    passed, detail = design_size._check_design_within_word_ceiling(task, task_dir)
    assert len(calls) == 2
    assert [n for n in notes if "technical-design.md: 133 words" in n], notes
    assert passed is True and "holds 133 words" in detail, detail


# --- WCL-4 to WCL-6: the word-limit note ---------------------------------------------

def test_wcl_4_lint_note_over_limit(tmp_path):
    root = _project(tmp_path)
    _write(root, "technical-design", _document(3000))
    base, words, _ = _lint(root)
    assert words == []
    _write(root, "technical-design", _document(4001))
    code, words, _ = _lint(root)
    assert len(words) == 1, words
    assert ("technical-design.md: 4,001 words, over the thorough limit of 4,000"
            in words[0]), words
    assert code == base
    _write(root, "acceptance-criteria", _document(5001, title="# Spec - feature"))
    code, words, _ = _lint(root)
    assert len(words) == 2, words
    assert any("acceptance-criteria.md: 5,001 words, over the thorough limit of 5,000" in w
               for w in words), words
    assert code == base


def test_wcl_5_no_note_at_limit_or_no_limit(tmp_path):
    root = _project(tmp_path / "at")
    _write(root, "technical-design", _document(4000))
    _write(root, "acceptance-criteria", _document(5000, title="# Spec - feature"))
    _write(root, "requirements-review", _document(9000, title="# Review - feature"))
    _, words, _ = _lint(root)
    assert words == []
    layer = {"schema": 1, "owner": "jed72", "artifacts": {"intent": {
        "set": {"word_ceiling": {"thorough": 800}}, "waiver": WAIVER}}}
    root = _project(tmp_path / "intent", compass_yml=layer)
    _write(root, "intent", _document(801, title="# Intent - feature"))
    _, words, _ = _lint(root)
    assert len(words) == 1 and "intent.md: 801 words, over the thorough limit of 800" in words[0]


def test_wcl_6_lightweight_limit(tmp_path):
    root = _project(tmp_path, assessment=HOTFIX)
    assert sup.manifest(root)["delivery_approach"] == "hotfix"
    _write(root, "acceptance-criteria", _document(1501, title="# Spec - feature"),
           depth="lightweight")
    _, words, _ = _lint(root)
    assert len(words) == 1, words
    assert "1,501 words, over the lightweight limit of 1,500" in words[0]
    _write(root, "acceptance-criteria", _document(1500, title="# Spec - feature"),
           depth="lightweight")
    _, words, _ = _lint(root)
    assert words == []


# --- WCL-7 to WCL-10: the plan-exit refusal -----------------------------------------

def _full_over(tmp_path, words=6001, stage="implement", **more):
    root = _project(tmp_path, assessment=FULL, stage=stage, **more)
    assert sup.manifest(root)["delivery_approach"] == "full"
    _write(root, "technical-design", _document(words, UNITS))
    return root


def test_wcl_7_check_refuses_far_over(tmp_path):
    root = _full_over(tmp_path)
    code, status, detail, rows = _row(root)
    assert status == "fail", (status, detail)
    for words in ("6,001 words", "threshold of 6,000", "1.5 times the thorough limit of 4,000",
                  "Units with no low-level design: U1, U2, U3.",
                  "Move each unit's detail to low-level-design/<unit>.md until the design "
                  "is at or under 6,000 words."):
        assert words in detail, (words, detail)
    assert code == 1


def test_wcl_8_refusal_threshold(tmp_path):
    root = _full_over(tmp_path / "at", words=6000)
    _, status, detail, _ = _row(root)
    assert status == "pass", detail
    _, words, _ = _lint(root)
    assert len(words) == 1, words
    # Lightweight: refused at 1,801 words, passes at 1,800.
    for count, expected in ((1801, "fail"), (1800, "pass")):
        root = _project(tmp_path / ("light-%d" % count), assessment=FULL)
        _write(root, "technical-design", _document(count, UNITS), depth="lightweight")
        _, status, detail, _ = _row(root)
        assert status == expected, (count, detail)
    # The spec is never refused: an 8,000-word spec with a 3,000-word design.
    root = _project(tmp_path / "spec", assessment=FULL)
    _write(root, "technical-design", _document(3000, UNITS))
    _write(root, "acceptance-criteria", _document(8000, title="# Spec - feature"))
    _, status, detail, _ = _row(root)
    assert status == "pass", detail
    _, words, _ = _lint(root)
    assert len(words) == 1 and "acceptance-criteria.md" in words[0], words
    # A project layer with the factor 2.
    layer = {"schema": 1, "owner": "jed72", "checks": {CHECK: {
        "set": {"params": {"factor": 2}}, "waiver": WAIVER}}}
    for count, expected in ((6001, "pass"), (8001, "fail")):
        root = _full_over(tmp_path / ("factor-%d" % count), words=count, compass_yml=layer)
        _, status, detail, _ = _row(root)
        assert status == expected, (count, detail)


def test_wcl_8_threshold_is_a_whole_number_of_words(tmp_path, monkeypatch):
    # 800 times 1.15 is 919.9999999999999 in floating point. The threshold is the
    # whole number of words, 920, so a 920-word design passes and 921 fails.
    from compass_pkg import design_size, word_ceiling

    root = _project(tmp_path, assessment=FULL)
    task_dir = str(root / ".compass" / "work" / sup.SLUG)
    monkeypatch.setattr(word_ceiling, "limit",
                        lambda view, kind, depth: 800 if kind == "technical-design" else None)
    monkeypatch.setattr(design_size, "_factor", lambda task_dir: (1.15, None))
    for count, expected in ((920, True), (921, False)):
        _write(root, "technical-design", _document(count, UNITS))
        passed, detail = design_size._check_design_within_word_ceiling(sup.manifest(root),
                                                                        task_dir)
        assert passed is expected, (count, detail)
        assert "threshold of 920 " in detail, detail


def test_wcl_9_unit_files_do_not_lift(tmp_path):
    root = _full_over(tmp_path / "full")
    _register_units(root, UNITS)
    _, status, detail, _ = _row(root)
    assert status == "fail" and "Units with no low-level design: none." in detail, detail
    _write(root, "technical-design", _document(3900, UNITS))
    _, status, detail, _ = _row(root)
    assert status == "pass", detail
    # A regular design is refused the same way, with no unit sentence.
    root = _project(tmp_path / "regular")
    _write(root, "technical-design", _document(6001, UNITS))
    code, status, detail, _ = _row(root)
    assert status == "fail" and "6,001 words" in detail and "Units with" not in detail, detail
    assert code == 1


def test_wcl_10_waits_for_plan_exit(tmp_path):
    root = _full_over(tmp_path / "plan", stage="plan")
    _, status, detail, _ = _row(root)
    assert (status, detail) == ("nothing-to-check",
                                "plan exit is not yet due: the issue is at plan")
    _, words, _ = _lint(root)
    assert len(words) == 1, words
    for name, assessment in (("quick-fix", QUICK_FIX), ("spike", SPIKE)):
        root = _project(tmp_path / name, assessment=assessment)
        assert sup.manifest(root)["delivery_approach"] == name
        _, status, detail, _ = _row(root)
        assert (status, detail) == ("nothing-to-check",
                                    "no technical-design is registered with a path"), name
    # An issue waiver makes the refusal advisory: it no longer fails the run.
    root = _full_over(tmp_path / "waived")
    body = sup.manifest(root)
    body["config"] = {"checks": {CHECK: {
        "set": {"severity": "advisory"},
        "waiver": {"reason": "Judged by hand on this issue.", "approved_by": "EV-W1"}}}}
    body["evidence"].append({
        "id": "EV-W1", "type": "human-approval", "decision": "approved",
        "approver": "jed72", "role": "owner", "scope": "waiver",
        "timestamp": "2026-10-15T09:00:00Z",
        "waiver": {"scope": "issue", "entry": "checks.%s" % CHECK,
                   "fields": {"severity": {"from": "blocking", "to": "advisory"}}}})
    sup.write_manifest(root, body)
    _u3_evaluate(root, "waive the design-size check")
    code, status, detail, rows = _row(root)
    assert status == "advisory", detail
    assert code == _u3_exit_without(rows, (CHECK,))


# --- WCL-14 and WCL-16: the missing-unit note and the three-unit measure -----------

def test_wcl_14_missing_unit_note(tmp_path, monkeypatch):
    from compass_pkg import design_size, section_checks

    root = _full_over(tmp_path / "full", words=3000)
    _register_units(root, ("U1", "U2"))
    code, _, units = _lint(root)
    assert len(units) == 1, units
    assert units[0].startswith("U3: a work unit with no low-level design")
    assert "low-level-design/U3.md" in units[0]
    _register_units(root, ("U3",))
    base, _, units = _lint(root)
    assert units == [] and code == base
    # A regular issue gets no such note.
    root = _project(tmp_path / "regular")
    _write(root, "technical-design", _document(3000, UNITS))
    assert _lint(root)[2] == []
    # Nor does a full issue whose design is not registered with a path.
    root = _project(tmp_path / "unregistered", assessment=FULL)
    _write(root, "technical-design", _document(3000, UNITS), path=False)
    assert _lint(root)[2] == []
    # The Work units table is read through the section reader and its table reader.
    seen = []
    for name in ("section_lines", "tables"):
        real = getattr(section_checks, name)

        def spy(*args, real=real, name=name):
            seen.append(name)
            return real(*args)

        monkeypatch.setattr(section_checks, name, spy)
    assert design_size.work_units(_document(3000, UNITS)) == list(UNITS)
    assert seen == ["section_lines", "tables"]


def test_wcl_16_prd_measure_full_fixture(tmp_path):
    root = _full_over(tmp_path / "measure", words=3500)
    _register_units(root, UNITS)
    assert sorted(p.name for p in (root / sup.DOCS / "low-level-design").glob("U*.md")) == [
        "U1.md", "U2.md", "U3.md"]
    _, words, units = _lint(root)
    assert words == [] and units == []
    _, status, detail, _ = _row(root)
    assert status == "pass", detail
    root = _full_over(tmp_path / "refused")
    _, status, detail, _ = _row(root)
    assert status == "fail", detail


# --- WCL-17 to WCL-19: the archive and earlier generations --------------------------

def test_wcl_17_earlier_generation(tmp_path):
    from compass_pkg import artifact_kinds, effective

    root = _full_over(tmp_path, words=7000, compass_yml=_earlier_layer())
    assert sup.manifest(root)["generation"] == 1
    assert CHECK not in _declared(root)
    code, words, units = _lint(root)
    assert words == [] and units == []
    check_code, status, _, rows = _row(root)
    assert status is None and CHECK not in rows
    # The same exit codes as with a short design: the size changes nothing.
    _write(root, "technical-design", _document(500, UNITS))
    assert _lint(root)[0] == code and _row(root)[0] == check_code
    _write(root, "technical-design", _document(7000, UNITS))
    view = effective.view_or_legacy(str(root / ".compass" / "work" / sup.SLUG))
    assert "word_ceiling" not in artifact_kinds.entry(view, "technical-design")
    assert "word_ceiling" in artifact_kinds.shipped()["technical-design"]
    # Assessed onto the configuration now, generation 2 judges the design.
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1, "owner": "jed72"}),
                                      encoding="utf-8")
    _u3_evaluate(root, "move onto the word limits")
    assert sup.manifest(root)["generation"] == 2
    _, words, units = _lint(root)
    assert len(words) == 1 and len(units) == 3, (words, units)
    assert _row(root)[1] == "fail"


def _archive_shapes(tmp_path):
    """The four archived shapes of WCL-18, each a 7,000-word design naming 3 units."""
    shapes = {}
    root = _project(tmp_path / "first", assessment=FULL)
    _write(root, "technical-design", _document(7000, UNITS))
    body = sup.manifest(root)
    body.pop("generation")
    sup.write_manifest(root, body)
    shapes["first"] = (root, "the issue predates the design-size check: its manifest "
                             "names no stored configuration")
    root = _full_over(tmp_path / "second", words=7000)
    sup.edit(root, status="done")
    shapes["second"] = (root, "the issue is closed")
    root = _full_over(tmp_path / "third", words=7000, compass_yml=_no_limit_layer())
    shapes["third"] = (root, "the catalog of generation 1 has no word_ceiling for "
                             "technical-design at depth thorough")
    root = _project(tmp_path / "fourth", assessment=FULL)
    _write(root, "technical-design", _document(7000, UNITS), path=False)
    shapes["fourth"] = (root, "no technical-design is registered with a path")
    return shapes


def test_wcl_18_declines_archive_shapes(tmp_path, monkeypatch):
    import check_corpus_runner as runner
    from compass_pkg import design_size

    for name, (root, why) in _archive_shapes(tmp_path).items():
        assert CHECK in _declared(root), name
        _, status, detail, _ = _row(root)
        assert (status, detail) == ("nothing-to-check", why), name
        _, words, units = _lint(root)
        assert words == [] and units == [], name
    corpus = ROOT / "tests" / "fixtures" / "impls" / CHECK
    cases = {"no-generation", "closed", "no-ceiling", "not-registered", "before-plan-exit"}
    assert cases <= {p.name for p in corpus.iterdir() if p.is_dir()}
    for case in cases:
        expected = yaml.safe_load((corpus / case / "expected.yml").read_text(encoding="utf-8"))
        assert expected["verdict"] == "nothing-to-check", case
        assert runner.run_case(CHECK, case, tmp_path / ("corpus-" + case)) == "nothing-to-check"
    # A planted change that skips the generation test judges the first shape.
    real = design_size.declines

    def planted(task, task_dir, kind, entry=None):
        return real(dict(task, generation=task.get("generation") or 1), task_dir, kind, entry)

    monkeypatch.setattr(design_size, "declines", planted)
    assert runner.run_case(CHECK, "no-generation", tmp_path / "planted") != "nothing-to-check"


def _lint_notes_on(root):
    """Every word-limit or missing-unit note `issue lint` prints on any issue under `root`."""
    from compat_baseline import _issues

    found = []
    for slug in _issues(root):
        done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "issue",
                               "lint", "--issue", slug], cwd=root, capture_output=True,
                              text=True, timeout=600,
                              env={"PATH": "/usr/bin:/bin", "HOME": str(root),
                                   "LANG": "C.UTF-8", "NO_COLOR": "1",
                                   "CLAUDE_PROJECT_DIR": str(root),
                                   "PYTHONDONTWRITEBYTECODE": "1"})
        found += ["%s: %s" % (slug, line.strip()) for line in done.stdout.splitlines()
                  if WORD_NOTE in line or UNIT_NOTE in line]
    return found


def test_wcl_19_archive_sweep_and_compat_contract(tmp_path):
    from archive import checkable_root, full_archive
    from compat_baseline import (ARCHIVE, allow_7_0_0_moves, archive_differences,
                                 archive_results)

    base = {"check_exit": 0, "lint_exit": 0, "receipt_exit": 0,
            "verdicts": {"dod-evidence-typed": "pass", "suite-passed": "pass"}}
    good = {"check_exit": 0, "lint_exit": 0, "receipt_exit": 0,
            "verdicts": {"rendered-blocks-current": "pass",
                         "dod-evidence-typed": "nothing-to-check", "suite-passed": "pass"}}

    def differs(old=base, **verdicts):
        now = dict(good, verdicts=dict(good["verdicts"], **verdicts))
        return archive_differences(*allow_7_0_0_moves({"x": old}, {"x": now}))

    # Contract 3 admits a new row only as nothing to check, and only where the recorded
    # verdicts have none.
    assert differs(**{CHECK: "nothing-to-check"}) == []
    for verdict in ("pass", "fail", "advisory", "refused"):
        assert differs(**{CHECK: verdict}), verdict
    recorded_row = dict(base, verdicts=dict(base["verdicts"], **{CHECK: "pass"}))
    assert differs(recorded_row, **{CHECK: "nothing-to-check"})
    assert differs(dict(base, lint_exit=0), **{CHECK: "nothing-to-check"}) == []
    assert archive_differences(*allow_7_0_0_moves({"x": base}, {"x": dict(good, lint_exit=1)}))

    recorded = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    assert not any(CHECK in r["verdicts"] for r in recorded["issues"].values())
    if full_archive():
        # The maintainer's archive, copied, so a check run never writes into it.
        from test_document_set_sections import _u3_sweep
        copy = _u3_copy_archive(checkable_root(), tmp_path / "archive")
        results = _u3_sweep(copy)
        # The maintainer's archive has no recorded baseline to compare with, so this
        # path shows that the check judges no issue and lint prints no new note.
        assert len(results) == len(list((copy / ".compass" / "work").glob("*/manifest.yml")))
        assert sorted(s for s, (_, rows) in results.items()
                      if rows.get(CHECK, "nothing-to-check") != "nothing-to-check") == []
        assert _lint_notes_on(copy) == []
        return
    # The sample as an adopter has it after migrate and render: itself a copy.
    copy = checkable_root()
    now = archive_results(copy)
    old, new = allow_7_0_0_moves(recorded["issues"], now)
    assert archive_differences(old, new) == []
    assert [s for s, r in now.items()
            if r["verdicts"].get(CHECK, "nothing-to-check") != "nothing-to-check"] == []
    failing = sorted(s for s, r in recorded["issues"].items() if r["check_exit"])
    assert sorted(s for s, r in now.items() if r["check_exit"]) == failing
    assert _lint_notes_on(copy) == []
    # A dry render of the copy rewrites no block.
    done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "issue", "render",
                           "--all", "--dry-run", "--json"], cwd=copy, capture_output=True,
                          text=True, timeout=600,
                          env={"PATH": "/usr/bin:/bin", "HOME": str(copy), "LANG": "C.UTF-8",
                               "NO_COLOR": "1", "CLAUDE_PROJECT_DIR": str(copy),
                               "PYTHONDONTWRITEBYTECODE": "1"})
    report = json.loads(done.stdout)
    assert report["would_write"] == [] and report["failed"] == [], report
