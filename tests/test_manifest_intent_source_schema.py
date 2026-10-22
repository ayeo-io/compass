"""The manifest schema defines `intent_source`, the block `compass intent ingest` writes.

The root of `schemas/manifest.schema.json` sets `additionalProperties: false`, so
a key the schema does not define makes every ingested issue fail validation by a
tool that reads the schema. The value checked here has the keys that
`cli/compass_pkg/ingest.py` writes, plus the `sections` list that the
intent-interview skill adds.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA = Path(__file__).resolve().parent.parent / "schemas" / "manifest.schema.json"

INTENT_SOURCE = {
    "origin": "brief.md",
    "scheme": "file",
    "sha256": "0" * 64,
    "ingested_at": "2026-10-22T09:00:00+00:00",
    "snapshot": "intent-source.md",
    "interview": [{"id": "Q1", "question": "Who is it for?", "answer": None}],
    "sections": [{"name": "problem", "from": "source"}],
}


def _manifest(**extra):
    return {"issue": "demo", "created": "2026-10-22", **extra}


def _schema():
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_the_schema_defines_intent_source():
    assert "intent_source" in _schema()["properties"]


def test_manifest_with_intent_source_validates():
    jsonschema.validate(_manifest(intent_source=INTENT_SOURCE), _schema())


def test_an_intent_source_that_is_not_a_map_is_refused():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_manifest(intent_source="brief.md"), _schema())


def test_an_interview_that_is_not_a_list_is_refused():
    bad = dict(INTENT_SOURCE, interview="none")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(_manifest(intent_source=bad), _schema())
