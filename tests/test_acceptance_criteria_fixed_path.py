"""The acceptance criteria are read at their fixed path (ADR-091).

9.0.0 registers no document, so `nfr-rows-resolved` reads
`docs/compass/<created>-<slug>/acceptance-criteria.md` whenever that file exists. An
issue created on or after 2026-11-04 owes it there. An older issue with no spec there
and none registered keeps the verdict it had.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402
from compass_pkg.section_checks import _check_nfr_rows_resolved  # noqa: E402

SPEC = """# Spec

## Non-functional requirements

| Concern | Scenario | Reason |
|---|---|---|
| performance | | |
| capacity | | not a service |
| compatibility | | no interface |
| security | | no input |
| privacy | | no personal data |
| operability | | nothing runs |
| accessibility | | no screen |
"""


def _issue(root, created, *, spec=True, define="thorough"):
    task_dir = root / ".compass" / "work" / "probe"
    task_dir.mkdir(parents=True)
    manifest = {"schema_version": "3.0", "issue": "probe", "created": created,
                "generation": 1, "delivery_approach": "regular",
                "stages": {"define": define}, "scenarios": []}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    if spec:
        docs = root / "docs" / "compass" / f"{created}-probe"
        docs.mkdir(parents=True)
        (docs / "acceptance-criteria.md").write_text(SPEC, encoding="utf-8")
    return manifest, str(task_dir)


def test_a_new_issue_is_judged_on_the_spec_at_its_fixed_path(tmp_path):
    task, task_dir = _issue(tmp_path, "2026-11-05")
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is False, detail
    assert '"performance" has neither a scenario nor a reason' in detail, detail
    assert "acceptance-criteria.md" in detail, detail


def test_a_new_issue_with_no_spec_yet_has_nothing_to_check(tmp_path):
    task, task_dir = _issue(tmp_path, "2026-11-05", spec=False)
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is NOTHING_TO_CHECK, detail
    assert "acceptance-criteria.md" in detail, detail


def test_an_older_issue_with_no_spec_keeps_its_verdict(tmp_path):
    task, task_dir = _issue(tmp_path, "2026-10-01", spec=False)
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is NOTHING_TO_CHECK, detail
    assert "registered" in detail, detail


def test_an_older_issue_is_judged_on_a_spec_at_its_fixed_path(tmp_path):
    task, task_dir = _issue(tmp_path, "2026-10-01")
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is False, detail
    assert '"performance" has neither a scenario nor a reason' in detail, detail
