"""`compass issue migrate-config` pins an issue to the installed versions (ADR-038).

It is the second of the three ways a generation is committed: it stores a new
generation holding the same configuration, with the versions of the check
implementations, the resolver and the CLI this CLI has, and it invalidates the
check results recorded under the old ones. It never takes in a project edit;
that is a reassess, which classifies it.

Scenario ids: `IR-8` to `IR-11` (issue `impl-refusal`). Each test name starts
with its scenario id.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from impl_versions_support import (MANIFEST, SLUG, _run, committed,  # noqa: E402,F401
                                   record_versions)


def _load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


# --- IR-8: the new generation holds the same configuration, pinned ----------------------------

def test_ir_8_migrate_config_pins_the_installed_versions_and_keeps_the_configuration(committed):
    root, task_dir = committed
    record_versions(task_dir, cli="5.0.0", implementations={"suite-passed": "0.9.0"})
    _run(root, "check", "--issue", SLUG)                    # records results under generation 1
    before = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    code, out, err = _run(root, "issue", "migrate-config", "--issue", SLUG)
    assert code == 0, out + err
    after = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    assert after.replace("generation: 2", "generation: 1") == before
    first, second = (task_dir / "generations" / "1", task_dir / "generations" / "2")
    versions = _load(second / "versions.yml")
    assert versions["implementations"]["suite-passed"] == "1.0.0"
    assert versions["cli"] != "5.0.0"
    old = _load(first / "resolved.yml")
    new = _load(second / "resolved.yml")
    assert {k: v for k, v in new.items() if k != "generation"} == \
        {k: v for k, v in old.items() if k != "generation"}
    records = {r["id"]: r for r in _load(second / "records.yml")["records"]}
    assert records["result:scenarios-have-tests"]["status"] == "invalidated"
    assert not (second / "results.yml").exists()
    # The checks run again, and the refusal is gone.
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    assert '"refused"' not in out
    assert "suite-passed" in _load(second / "results.yml")["runs"]


def test_ir_8_migrate_config_does_not_take_in_a_project_edit_made_since(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1, "checks": {"extra": {
        "statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": "advisory", "on_skipped": "fail"}}}), encoding="utf-8")
    code, out, err = _run(root, "issue", "migrate-config", "--issue", SLUG)
    assert code == 0, out + err
    stored = _load(task_dir / "generations" / "2" / "resolved.yml")
    assert "extra" not in stored["checks"]
    assert _load(task_dir / "generations" / "2" / "provenance.yml") == \
        _load(task_dir / "generations" / "1" / "provenance.yml")


# --- IR-9: a landed issue is refused ----------------------------------------------------------

def test_ir_9_migrate_config_refuses_a_landed_issue_and_writes_nothing(committed):
    root, task_dir = committed
    record_versions(task_dir, implementations={"suite-passed": "0.9.0"})
    text = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    (task_dir / "manifest.yml").write_text(text.replace("status: active", "status: landed"),
                                           encoding="utf-8")
    held = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _run(root, "issue", "migrate-config", "--issue", SLUG)
    assert code == 2 and "landed" in err, out + err
    assert (task_dir / "manifest.yml").read_bytes() == held
    assert sorted(p.name for p in (task_dir / "generations").iterdir()) == ["1"]


def test_ir_9_a_landed_issue_is_refused_even_when_it_is_already_pinned(committed):
    root, task_dir = committed
    text = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    (task_dir / "manifest.yml").write_text(text.replace("status: active", "status: landed"),
                                           encoding="utf-8")
    code, out, err = _run(root, "issue", "migrate-config", "--issue", SLUG)
    assert code == 2 and "landed" in err, out + err


# --- IR-10: nothing to migrate ---------------------------------------------------------------

def test_ir_10_migrate_config_commits_nothing_when_already_pinned(committed):
    root, task_dir = committed
    held = (task_dir / "manifest.yml").read_bytes()
    code, out, err = _run(root, "issue", "migrate-config", "--issue", SLUG)
    assert code == 0 and "no change" in out, out + err
    assert (task_dir / "manifest.yml").read_bytes() == held
    assert sorted(p.name for p in (task_dir / "generations").iterdir()) == ["1"]


# --- IR-11: an issue with no generation is adopted --------------------------------------------

def test_ir_11_migrate_config_adopts_an_issue_that_has_no_generation(tmp_path):
    task_dir = tmp_path / ".compass" / "work" / SLUG
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(
        "# kept as written\n" + yaml.safe_dump(MANIFEST, sort_keys=False), encoding="utf-8")
    code, out, err = _run(tmp_path, "issue", "migrate-config", "--issue", SLUG)
    assert code == 0, out + err
    manifest = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    assert manifest.startswith("# kept as written\n")
    assert _load(task_dir / "manifest.yml")["generation"] == 1
    assert _load(task_dir / "generations" / "1" / "provenance.yml")["adopted"] == \
        "adopted from live governance"
    assert _load(task_dir / "generations" / "1" / "versions.yml")["implementations"]
