"""The settings key `living_spec` decides when a landing re-derives the spec.

`land`, the default, keeps ADR-026: `ship-commit` re-derives
`docs/system-spec.md` after each landing and commits it alone. `refresh`
leaves the spec as it is and says so in one line, so a branch carries no
copy of the spec that conflicts with every other open branch once one
merges. A person then re-derives it with `compass spec sync`. This
repository sets `refresh`, because its spec is built from the issue
archive, which is not tracked, so CI cannot re-derive it
(ayeo-io/compass-delivery#362).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compass_pkg import catalogue_check, catalogue_spec, layers  # noqa: E402
from compass_pkg.atomic_io import load_yaml_strict  # noqa: E402
from test_ship_commit_derives import (_completed, _git, _head, _init_repo,  # noqa: E402
                                      _log_subjects, _open_issue, _run_ship_commit)

NOTE = ("living spec left as it is: compass.yml sets `living_spec: refresh`, "
        "so re-derive it with `compass spec sync`.")


def _repo(tmp_path: Path, setting: str | None) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    doc = {"schema": 1}
    if setting is not None:
        doc["living_spec"] = setting
    (repo / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    _git(repo, "add", "compass.yml")
    _git(repo, "commit", "-q", "-m", "settings")
    return repo


def test_refresh_lands_without_deriving_or_committing_the_spec(cli_path, tmp_path):
    repo = _repo(tmp_path, "refresh")
    slug = "spec-left-alone"
    task_dir = _open_issue(repo, slug)
    before = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert _completed(manifest), manifest
    assert _log_subjects(repo, since=before) == ["land it"]
    assert not (repo / "docs" / "system-spec.md").exists()
    assert r.stdout.count(NOTE) == 1, r.stdout
    assert "re-derived" not in r.stdout, r.stdout


@pytest.mark.parametrize("setting", [None, "land"], ids=["unset", "land"])
def test_land_and_unset_derive_and_commit_the_spec(cli_path, tmp_path, setting):
    repo = _repo(tmp_path, setting)
    slug = "spec-derived"
    _open_issue(repo, slug)
    before = _head(repo)

    r = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", slug)
    assert r.returncode == 0, r.stdout + r.stderr

    assert _log_subjects(repo, since=before) == [
        f"Re-derive the living spec after {slug} landed", "land it"]
    assert slug in (repo / "docs" / "system-spec.md").read_text(encoding="utf-8")
    assert "living spec re-derived and committed." in r.stdout, r.stdout
    assert NOTE not in r.stdout


def test_the_setting_is_a_settings_key_with_two_values():
    assert "living_spec" in catalogue_spec.SETTINGS_KEYS
    assert catalogue_spec.LIVING_SPEC == ("land", "refresh")
    for value in catalogue_spec.LIVING_SPEC:
        doc = {"schema": 1, "living_spec": value}
        assert catalogue_check.check_layer(doc, "project") == [], value
        layer, settings = layers.split_project_file(doc)
        assert settings == {"living_spec": value}
        assert "living_spec" not in layer

    errors = catalogue_check.check_layer({"schema": 1, "living_spec": "never"}, "project")
    assert errors == ["living_spec: 'never' is not one of land, refresh"], errors

    prop = catalogue_check.schema()["properties"]["living_spec"]
    assert prop["enum"] == ["land", "refresh"]
    for value in ("`land`", "`refresh`", "`compass spec sync`", "The default is `land`"):
        assert value in prop["description"], value


def test_this_repository_sets_refresh():
    doc = load_yaml_strict(str(ROOT / "compass.yml"))
    assert doc.get("living_spec") == "refresh"
