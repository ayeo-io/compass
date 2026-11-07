"""What a resolved configuration holds, the order `at_least:` compares by, and
the schema of `compass.yml`.

`catalogue_spec` names the catalogues a resolved configuration holds and the
fields of each, which the retired-word tables and the reader of a governance
copy read. The 8.x validator of a configuration layer, the merge and the
classifier read the same table until 9.0.0 removed them with the layers
(ADR-094); their cases went with them.

Scenario ids: `CS-1`, `CS-4` and `CS-5` (issue `catalogue-spec`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_spec, settings_lint  # noqa: E402
from compass_pkg.core import reading_matches  # noqa: E402


# --- the field table (`CS-1`) ----------------------------------------------------

def test_cs_1_the_table_names_the_nine_catalogues_and_their_fields():
    assert catalogue_spec.CATALOGUES == (
        "dimensions", "stages", "approaches", "rules", "checks", "gates",
        "artifacts", "readiness", "vocabulary")
    for name in catalogue_spec.CATALOGUES:
        fields = catalogue_spec.FIELDS[name]
        assert fields, name
        for field, spec in fields.items():
            assert spec["type"] and isinstance(spec["required"], bool), (name, field)
    assert catalogue_spec.FIELDS["checks"]["severity"]["required"] is True


# --- at_least in when-clauses (`CS-4`) -----------------------------------------------------

def test_cs_4_at_least_matches_by_order():
    when = {"risk": {"at_least": "cross-cutting"}}
    assert reading_matches(when, {"risk": "critical"})
    assert reading_matches(when, {"risk": "cross-cutting"})
    assert not reading_matches(when, {"risk": "contained"})
    assert not reading_matches(when, {"risk": "trivial"})
    orders = {"size": ["s", "m", "l"]}
    assert reading_matches({"size": {"at_least": "m"}}, {"size": "l"}, orders=orders)
    assert not reading_matches({"size": {"at_least": "m"}}, {"size": "s"}, orders=orders)


def test_cs_4_the_existing_forms_match_as_before():
    assert reading_matches({"risk": ["critical", "cross-cutting"]}, {"risk": "critical"})
    assert reading_matches({"labels_any": ["auth"]}, {"labels": ["auth"]})
    assert reading_matches({"any_of": [{"risk": "critical"}, {"labels_any": ["auth"]}]},
                           {"risk": "trivial", "labels": ["auth"]})
    assert not reading_matches({"risk": "critical"}, {"risk": "trivial"})


def test_cs_4_orders_given_are_used_even_when_empty_and_reach_any_of():
    assert not reading_matches({"risk": {"at_least": "trivial"}}, {"risk": "critical"},
                               orders={"risk": []})
    orders = {"tier": ["a", "b"]}
    assert reading_matches({"any_of": [{"tier": {"at_least": "b"}}]}, {"tier": "b"},
                           orders=orders)

# --- the generated schema (`CS-5`) ------------------------------------------------------

def test_cs_5_the_committed_schema_is_the_generated_one():
    committed = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    assert committed == settings_lint.schema(), (
        "schemas/compass.schema.json is out of date; regenerate it with "
        "json.dumps(settings_lint.schema(), indent=2, sort_keys=True)")


def test_cs_5_the_schema_holds_the_settings_and_their_enumerations():
    schema = settings_lint.schema()
    assert set(schema["properties"]) == set(settings_lint.KEYS)
    assert schema["additionalProperties"] is False
    assert schema["properties"]["autonomy"]["enum"] == list(catalogue_spec.AUTONOMY)


# --- every documented setting is a settings key ---------------------------------------

def test_governance_drift_is_accepted_as_a_setting():
    assert settings_lint.lint({"schema": 1, "governance_drift": "strict"}) == []
    assert "governance_drift" in catalogue_spec.SETTINGS_KEYS


def test_every_documented_setting_is_a_settings_key():
    import re
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    table = text.split("## Settings", 1)[1].split("\n###", 1)[0]
    documented = set(re.findall(r"^\| `([a-z_]+)`", table, flags=re.M))
    assert documented - set(catalogue_spec.SETTINGS_KEYS) == set()
