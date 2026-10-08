"""Every node of `schemas/compass.schema.json` carries a description.

The schema is a public contract from 6.0.0: a person or an editor reads what
each field means from it. A node is the root, a property, a pattern property,
an array item, a definition, an alternative of `oneOf`, `anyOf` or `allOf`,
and a schema given as `additionalProperties`.
"""
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import catalogue_check  # noqa: E402

SCHEMA_FILE = ROOT / "schemas" / "compass.schema.json"

_MAPS = ("properties", "patternProperties", "$defs", "definitions")
_LISTS = ("oneOf", "anyOf", "allOf")


def nodes(schema, path="$"):
    """Every sub-schema as `(path, node)`, the root first."""
    yield path, schema
    if not isinstance(schema, dict):
        return
    for key in _MAPS:
        for name, child in (schema.get(key) or {}).items():
            yield from nodes(child, f"{path}.{key}[{name}]")
    for key in _LISTS:
        for i, child in enumerate(schema.get(key) or []):
            yield from nodes(child, f"{path}.{key}[{i}]")
    for key in ("items", "additionalProperties"):
        if isinstance(schema.get(key), dict):
            yield from nodes(schema[key], f"{path}.{key}")


def undescribed(schema):
    """The path of every node whose `description` is missing or blank."""
    return [p for p, n in nodes(schema)
            if not (isinstance(n, dict) and isinstance(n.get("description"), str)
                    and n["description"].strip())]


def test_every_schema_node_has_a_description():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    missing = undescribed(schema)
    assert not missing, (
        f"{len(missing)} node(s) of schemas/compass.schema.json have no description:\n  "
        + "\n  ".join(missing))


def test_a_node_without_a_description_is_reported_by_path():
    schema = copy.deepcopy(json.loads(SCHEMA_FILE.read_text(encoding="utf-8")))
    del schema["properties"]["autonomy"]["description"]
    schema["properties"]["owner"]["description"] = "   "
    assert undescribed(schema) == ["$.properties[autonomy]", "$.properties[owner]"]


def test_the_walk_reaches_nested_nodes():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    paths = [p for p, _ in nodes(schema)]
    assert len(paths) > 200
    assert any(".oneOf[" in p for p in paths)
    assert any(".patternProperties[" in p for p in paths)


def test_a_description_is_one_or_two_sentences_without_trailing_space():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    bad = []
    for path, node in nodes(schema):
        text = node.get("description", "")
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
        if text != text.strip() or not text.endswith(".") or len(sentences) > 2:
            bad.append(path)
    assert not bad, "descriptions that are not short sentences:\n  " + "\n  ".join(bad)


def test_the_generator_describes_the_schema_it_builds():
    assert undescribed(catalogue_check.schema()) == []


def test_a_description_names_every_value_its_enumeration_allows():
    # The text is written by hand beside the constants it describes, so a value
    # added to a constant without a word in the text must fail here.
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    bad = []
    for path, node in nodes(schema):
        for value in node.get("enum", []):
            word = {True: "true"}.get(value, str(value))
            if word not in node["description"]:
                bad.append(f"{path} does not name {word!r}")
    assert not bad, "\n".join(bad)


def test_the_schema_allows_governance_drift_with_the_values_the_docs_give():
    # `compass policy migrate` writes this setting into compass.yml, and the
    # layer check already accepts it, so the schema must too.
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    node = schema["properties"]["governance_drift"]
    assert node["enum"] == ["advisory", "strict"]
    assert "advisory" in node["description"] and "strict" in node["description"]
    assert "governance_drift" in schema["properties"]
    assert catalogue_check.check_layer({"schema": 1, "governance_drift": "strict"},
                                       "project") == []
