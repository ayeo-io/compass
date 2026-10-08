"""This repository keeps its own settings in a settings-only `compass.yml`.

The framework repository is also a Compass project. Its governance files are
the set every adopter gets, so its `compass.yml` extends the shipped default
and holds settings keys only: no catalogue key, no waiver, no unlock and no
capability. Its issues then run the shipped default unchanged, which keeps its
delivery record valid evidence for the default. The old `.compass/config.yml`
is gone, and the state the CLI wrote (`records_signed_since`) is in the state
file.

Scenario ids: IDR-5 and IDR-6, in the acceptance criteria of the issue
`init-docs-release`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import project_settings  # noqa: E402
from compass_pkg.atomic_io import load_yaml_strict  # noqa: E402
from compass_pkg.catalogue_spec import CATALOGUES, SETTINGS_KEYS  # noqa: E402

# `schema` and `extends` make the file a layer. Everything else must be a
# settings key.
ALLOWED = set(SETTINGS_KEYS) | {"schema", "extends"}
# Layer keys that are not settings and not catalogues, and that this
# repository's file must not declare either.
FORBIDDEN_LAYER_KEYS = {"waiver", "waived", "unlock", "capabilities", "approvers", "owner"}


def disallowed_keys(doc):
    """The top-level keys of `doc` that a settings-only file may not hold."""
    return sorted(k for k in doc if k not in ALLOWED
                  or k in CATALOGUES or k in FORBIDDEN_LAYER_KEYS)


def test_idr_5_the_checker_reports_a_planted_catalogue_key():
    assert disallowed_keys({"schema": 1, "autonomy": "balanced"}) == []
    assert disallowed_keys({"schema": 1, "checks": {}}) == ["checks"]
    assert disallowed_keys({"schema": 1, "capabilities": {"x": True}}) == ["capabilities"]
    assert disallowed_keys({"schema": 1, "unlock": True}) == ["unlock"]


def test_idr_5_compass_yml_holds_settings_keys_only_and_extends_the_default():
    doc = load_yaml_strict(str(ROOT / "compass.yml"))
    assert doc["schema"] == 1
    assert doc["extends"] == "compass:default@6"
    assert disallowed_keys(doc) == []


def test_idr_5_the_old_settings_file_and_the_shipped_project_file_are_gone():
    assert not (ROOT / ".compass" / "config.yml").exists()
    assert not (ROOT / "governance" / "policy.yml").exists()
    assert not (ROOT / "governance" / "compass.yml").exists()


def test_idr_5_the_settings_the_old_file_held_are_read_from_compass_yml():
    assert project_settings.settings_source(str(ROOT)) == str(ROOT / "compass.yml")
    settings = project_settings.settings(str(ROOT))
    assert settings["autonomy"] == "autonomous"
    assert settings["adoption"] == "enforced"
    assert settings["governance_drift"] == "advisory"
    assert settings["project"]["test_command"] == "pytest -q"
    assert settings["project"]["name"] == "Compass (framework)"
    assert settings["multiagent"]["worktree_root"] == "../.compass-worktrees"
    assert settings["record"]["names_key"] == ".compass/private/rival-codes.yml"
    assert ".compass/work" in settings["record"]["paths"]


def test_idr_5_the_cli_state_is_in_the_state_file():
    state = project_settings.state(str(ROOT))
    assert str(state["records_signed_since"]) == "2026-09-24"
    assert project_settings.state_source(str(ROOT)) == str(ROOT / ".compass" / "state.yml")


def test_idr_6_the_hook_still_guards_the_repositorys_shell_scripts():
    settings = project_settings.settings(str(ROOT))
    assert settings["enforcement"]["code_globs"] == ["hooks/*.sh", "scripts/*.sh"]


def test_idr_6_the_self_check_requires_compass_yml_not_the_old_file():
    text = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")
    assert "compass.yml" in text
    assert ".compass/config.yml" not in text
