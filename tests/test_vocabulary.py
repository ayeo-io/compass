"""The `vocabulary` catalogue gives entries display names, and aliases resolve.

A vocabulary entry is keyed `<catalogue>.<id>` and holds a display `name` and
`aliases`. The `vocabulary` module looks names up and resolves aliases to ids;
`catalogue_check.check_vocabulary` refuses a resolved configuration in which a
name or alias is ambiguous. Nothing calls either outside these tests yet.

Scenario ids: `VC-1` to `VC-4` (issue `vocabulary-catalogue`). The ban scan
over display names (`VC-5`) and the terminology wording (`VC-6`) are in
`tests/test_terminology.py`.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_check, merge, vocabulary  # noqa: E402


def _parent():
    """A parent with two checks, an approach and the names of both checks."""
    return {
        "checks": {
            "suite-passed": {"statement": "The suite passes.", "kind": "deterministic",
                             "severity": "blocking", "on_skipped": "fail"},
            "reviewed": {"statement": "A person reviewed it.", "kind": "human",
                         "severity": "advisory", "on_skipped": "pass"},
        },
        "approaches": {
            "regular": {"weight": 2, "stages": {"verify": "full"}},
        },
        "vocabulary": {
            "checks.suite-passed": {"name": "Suite passed",
                                    "aliases": ["tests green", "ci"]},
            "checks.reviewed": {"name": "Reviewed", "aliases": []},
            "approaches.regular": {"name": "regular", "aliases": ["standard"]},
        },
    }


def _config(extra=None):
    config, _ = merge.apply({}, _parent(), "parent", "root")
    if extra:
        config["vocabulary"].update(extra)
    return config


def _codes(errors):
    return {code for code, _, _ in errors}


# --- display names (`VC-1`) ---------------------------------------------------

def test_vc1_a_display_name_comes_from_the_vocabulary():
    assert vocabulary.display_name(_config(), "checks", "suite-passed") == "Suite passed"


def test_vc1_an_entry_without_a_vocabulary_entry_shows_its_id():
    config = _config()
    config["checks"]["lint-clean"] = {"statement": "Lint is clean.", "kind": "deterministic",
                                      "severity": "advisory", "on_skipped": "pass"}
    assert vocabulary.display_name(config, "checks", "lint-clean") == "lint-clean"


def test_vc1_a_blank_name_shows_the_id():
    config = _config({"checks.reviewed": {"name": "  ", "aliases": []}})
    assert vocabulary.display_name(config, "checks", "reviewed") == "reviewed"


def test_vc1_a_project_layer_adds_and_overrides_names():
    project = {
        "checks": {"lint-clean": {"statement": "Lint is clean.", "kind": "deterministic",
                                  "severity": "advisory", "on_skipped": "pass"}},
        "vocabulary": {
            "checks.suite-passed": {"set": {"name": "Tests pass"}},
            "checks.lint-clean": {"name": "Lint clean", "aliases": ["style ok"]},
        },
    }
    config, _ = merge.apply(_config(), project, "project", "compass.yml")
    assert vocabulary.display_name(config, "checks", "suite-passed") == "Tests pass"
    assert vocabulary.display_name(config, "checks", "lint-clean") == "Lint clean"
    assert vocabulary.display_name(config, "checks", "reviewed") == "Reviewed"
    assert vocabulary.resolve(config, "checks", "style ok") == "lint-clean"
    assert catalogue_check.check_vocabulary(config) == []


# --- aliases (`VC-2`) ---------------------------------------------------------

def test_vc2_an_alias_resolves_to_its_id():
    assert vocabulary.resolve(_config(), "checks", "tests green") == "suite-passed"


def test_vc2_an_id_resolves_exactly_and_with_changed_case_and_spacing():
    config = _config()
    assert vocabulary.resolve(config, "checks", "suite-passed") == "suite-passed"
    assert vocabulary.resolve(config, "checks", "SUITE-Passed") == "suite-passed"
    assert vocabulary.resolve(config, "checks", "  suite-passed  ") == "suite-passed"


def test_vc2_a_name_resolves_with_changed_case_and_spacing():
    config = _config()
    assert vocabulary.resolve(config, "checks", "Suite passed") == "suite-passed"
    assert vocabulary.resolve(config, "checks", "  SUITE   passed ") == "suite-passed"


def test_vc2_an_alias_resolves_with_changed_case_and_spacing():
    config = _config()
    assert vocabulary.resolve(config, "checks", "tests green") == "suite-passed"
    assert vocabulary.resolve(config, "checks", "TESTS  Green") == "suite-passed"


def test_vc2_blank_or_non_string_text_resolves_to_nothing():
    config = _config()
    for text in ("", "   ", None, 3, ["ci"]):
        try:
            found = vocabulary.resolve(config, "checks", text)
        except Exception as exc:   # report a raise as a wrong answer, not a crash
            found = f"raised {type(exc).__name__}"
        assert found is None, (text, found)


def test_vc2_text_that_names_nothing_resolves_to_nothing():
    assert vocabulary.resolve(_config(), "checks", "no such thing") is None
    assert vocabulary.resolve({}, "checks", "ci") is None


def test_vc2_resolution_stays_inside_its_catalogue():
    config = _config()
    assert vocabulary.resolve(config, "approaches", "standard") == "regular"
    assert vocabulary.resolve(config, "checks", "standard") is None


# --- collisions (`VC-3`) ------------------------------------------------------

def test_vc3_a_clean_vocabulary_passes():
    assert catalogue_check.check_vocabulary(_config()) == []


def test_vc3_an_alias_equal_to_another_entrys_id_fails():
    config = _config({"checks.reviewed": {"name": "Reviewed", "aliases": ["suite-passed"]}})
    errors = catalogue_check.check_vocabulary(config)
    assert _codes(errors) == {"M-ALIAS-COLLISION"}
    text = " ".join(message for _, _, message in errors)
    assert "suite-passed" in text and "reviewed" in text


def test_vc3_an_alias_equal_to_another_entrys_alias_fails():
    config = _config({"checks.reviewed": {"name": "Reviewed", "aliases": ["CI"]}})
    assert _codes(catalogue_check.check_vocabulary(config)) == {"M-ALIAS-COLLISION"}


def test_vc3_a_name_equal_to_another_entrys_name_or_alias_fails():
    same_name = _config({"checks.reviewed": {"name": "suite  passed", "aliases": []}})
    assert _codes(catalogue_check.check_vocabulary(same_name)) == {"M-ALIAS-COLLISION"}
    name_is_alias = _config({"checks.reviewed": {"name": "Tests Green", "aliases": []}})
    assert _codes(catalogue_check.check_vocabulary(name_is_alias)) == {"M-ALIAS-COLLISION"}


def test_vc3_the_error_names_the_path_text_and_both_entries():
    config = _config({"checks.reviewed": {"name": "Reviewed", "aliases": ["ci"]}})
    (code, path, message), = catalogue_check.check_vocabulary(config)
    assert code == "M-ALIAS-COLLISION"
    assert path == "vocabulary"
    assert "'ci'" in message
    assert "checks.suite-passed" in message and "checks.reviewed" in message


def test_vc3_the_same_text_in_two_catalogues_does_not_collide():
    config = _config({"approaches.regular": {"name": "regular", "aliases": ["ci"]}})
    assert catalogue_check.check_vocabulary(config) == []


def test_vc3_two_ids_that_differ_only_by_case_are_not_a_vocabulary_collision():
    # Every holder of the text is an id, so there is no name or alias to blame.
    config = _config()
    config["checks"]["X"] = dict(config["checks"]["reviewed"])
    config["checks"]["x"] = dict(config["checks"]["reviewed"])
    assert catalogue_check.check_vocabulary(config) == []


def test_vc3_an_empty_or_blank_name_or_alias_fails():
    for entry in ({"name": "", "aliases": []}, {"name": "  ", "aliases": []},
                  {"name": "Reviewed", "aliases": [""]},
                  {"name": "Reviewed", "aliases": ["ok", "   "]}):
        errors = catalogue_check.check_vocabulary(_config({"checks.reviewed": entry}))
        assert _codes(errors) == {"M-FIELD-SHAPE"}, entry
        assert errors[0][1] == "vocabulary.checks.reviewed"


def test_vc3_an_entry_may_repeat_its_own_id_as_its_name():
    config = _config({"checks.reviewed": {"name": "reviewed", "aliases": ["reviewed"]}})
    assert catalogue_check.check_vocabulary(config) == []


# --- keys that name nothing (`VC-4`) ------------------------------------------

def test_vc4_a_key_that_is_not_catalogue_dot_id_fails():
    config = _config({"suite-passed": {"name": "Suite", "aliases": []}})
    errors = catalogue_check.check_vocabulary(config)
    assert _codes(errors) == {"M-REF-UNKNOWN"}
    assert "suite-passed" in errors[0][1]


def test_vc4_a_key_naming_an_unknown_catalogue_fails():
    config = _config({"widgets.thing": {"name": "Thing", "aliases": []}})
    assert _codes(catalogue_check.check_vocabulary(config)) == {"M-REF-UNKNOWN"}


def test_vc4_a_key_naming_an_id_the_catalogue_lacks_fails():
    config = _config({"checks.missing": {"name": "Missing", "aliases": ["gone"]}})
    errors = catalogue_check.check_vocabulary(config)
    assert _codes(errors) == {"M-REF-UNKNOWN"}
    assert errors[0][1] == "vocabulary.checks.missing"


def test_vc4_a_vocabulary_entry_for_the_vocabulary_catalogue_fails():
    config = _config({"vocabulary.checks.reviewed": {"name": "X", "aliases": []}})
    assert _codes(catalogue_check.check_vocabulary(config)) == {"M-REF-UNKNOWN"}
