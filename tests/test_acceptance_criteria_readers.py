"""Every reader of the acceptance criteria finds them at their fixed path (ADR-091).

9.0.0 registers no document, so an issue's acceptance criteria are at
`docs/compass/<created>-<slug>/acceptance-criteria.md` and nowhere else. Each
reader asks one resolver, `spec_location.spec_path`, which gives:

1. the registered path, when the manifest registers one that is on disk;
2. otherwise the fixed path, when that file exists;
3. otherwise the flat file beside the manifest.

Each test below writes the spec only at the fixed path and asks one reader.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  (the bundled PyYAML first)
from compass_pkg import bdd, checks, diagnose, spec_location, tdd  # noqa: E402
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402
from compass_pkg.section_checks import _check_nfr_rows_resolved  # noqa: E402

CREATED = "2026-11-05"

SPEC = """# Acceptance criteria - probe

### Scenario: the regression is fixed
<!-- traceability id: SCN-1 -->

```gherkin
Scenario: the regression is fixed
  Given the defect reproduces
  When the fix is applied
  Then the regression test covers it
```

| SCN-1 | the regression is fixed |

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


def _issue(root, *, created=CREATED, approach="regular", slug="probe", **extra):
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    manifest = {"schema_version": "3.0", "issue": slug, "created": created,
                "generation": 1, "delivery_approach": approach,
                "stages": {"define": "thorough"},
                "scenarios": [{"id": "SCN-1", "verifiable": "narrative"}]}
    manifest.update(extra)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    docs = root / "docs" / "compass" / f"{created}-{slug}"
    docs.mkdir(parents=True)
    spec = docs / "acceptance-criteria.md"
    spec.write_text(SPEC, encoding="utf-8")
    return manifest, str(task_dir), spec


def test_the_resolver_gives_the_fixed_path(tmp_path):
    _, task_dir, spec = _issue(tmp_path)
    assert Path(spec_location.spec_path(task_dir)).resolve() == spec.resolve()


def test_the_resolver_prefers_the_fixed_path_to_a_flat_file(tmp_path):
    _, task_dir, spec = _issue(tmp_path)
    (Path(task_dir) / "acceptance-criteria.md").write_text("# flat\n", encoding="utf-8")
    assert Path(spec_location.spec_path(task_dir)).resolve() == spec.resolve()


def test_the_resolver_keeps_a_registered_path(tmp_path):
    other = tmp_path / "docs" / "elsewhere.md"
    other.parent.mkdir(parents=True)
    other.write_text("# registered\n", encoding="utf-8")
    _, task_dir, _ = _issue(tmp_path, artifacts=[
        {"kind": "acceptance-criteria", "path": "docs/elsewhere.md", "status": "approved"}])
    assert Path(spec_location.spec_path(task_dir)).resolve() == other.resolve()


def test_the_resolver_falls_back_to_the_flat_file(tmp_path):
    _, task_dir, spec = _issue(tmp_path)
    spec.unlink()
    assert spec_location.spec_path(task_dir) == str(Path(task_dir) / "acceptance-criteria.md")


def test_scenarios_have_tests_reads_a_narrative_scenario_at_the_fixed_path(tmp_path):
    task, task_dir, _ = _issue(tmp_path)
    passed, detail = checks._check_scenarios_have_tests(task, task_dir)
    assert passed is True, detail


def test_the_spec_digest_reads_the_fixed_path(tmp_path):
    _, task_dir, _ = _issue(tmp_path)
    assert checks._spec_sha256(task_dir) is not None


def test_bdd_extract_reads_the_fixed_path(tmp_path, monkeypatch, capsys):
    _issue(tmp_path)
    monkeypatch.chdir(tmp_path)
    args = argparse.Namespace(task="probe", out=None, json=False, quiet=False)
    assert bdd.cmd_bdd_extract(args) in (0, None)
    feature = (tmp_path / ".compass" / "work" / "probe" / "acceptance-criteria.feature")
    text = feature.read_text(encoding="utf-8")
    assert "the regression is fixed" in text
    assert f"docs/compass/{CREATED}-probe/acceptance-criteria.md" in text


def test_tdd_names_the_scenario_line_at_the_fixed_path(tmp_path, monkeypatch):
    _, task_dir, _ = _issue(tmp_path)
    monkeypatch.chdir(tmp_path)
    line = tdd._scenario_line(task_dir, "SCN-1")
    assert line is not None
    assert f"{CREATED}-probe/acceptance-criteria.md:" in line


def test_diagnose_shows_the_define_record_at_the_fixed_path(tmp_path):
    task, task_dir, _ = _issue(tmp_path)
    shown = diagnose._stage_records(str(tmp_path), task_dir, task, [])
    assert any("acceptance-criteria.md" in one for one in shown["define"]), shown


def test_an_older_issue_with_the_spec_at_the_fixed_path_is_judged(tmp_path):
    task, task_dir, _ = _issue(tmp_path, created="2026-10-01")
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is False, detail
    assert '"performance" has neither a scenario nor a reason' in detail, detail


def test_an_older_issue_with_no_spec_keeps_its_verdict(tmp_path):
    task, task_dir, spec = _issue(tmp_path, created="2026-10-01")
    spec.unlink()
    passed, detail = _check_nfr_rows_resolved(task, task_dir)
    assert passed is NOTHING_TO_CHECK, detail
    assert "registered" in detail, detail


HOOK = ROOT / "hooks" / "stop.sh"


def test_the_stop_hook_finds_a_hotfix_reproduction_at_the_fixed_path(tmp_path):
    _issue(tmp_path, approach="hotfix", slug="demo")
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n", encoding="utf-8")
    out = subprocess.run(
        ["bash", str(HOOK)], input="{}", cwd=str(tmp_path),
        capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": str(tmp_path),
             "CLAUDE_PROJECT_DIR": str(tmp_path)},
    ).stderr
    assert "does not exist" not in out and "no promoted" not in out, out
