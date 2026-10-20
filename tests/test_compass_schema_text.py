"""The generated settings schema describes the `language` setting.

The scenario number in the test name is from the acceptance criteria of the
issue `language-key-and-us-english`. The check that every schema node has text
is in `tests/test_schema_descriptions.py`; this file reuses its helpers.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import catalogue_check  # noqa: E402
from test_schema_descriptions import SCHEMA_FILE, undescribed  # noqa: E402


def test_trc_068():
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    node = schema["properties"]["language"]
    assert node["type"] == "string"
    text = node["description"]
    for fact in ("BCP 47", "a language, an optional script and an optional region",
                 "`en-US`", "Unset: no instruction", "only the project's own `compass.yml`"):
        assert fact in text, (fact, text)
    assert schema == catalogue_check.schema()
    assert undescribed(schema) == []
    # A language node with no text is reported by its path.
    bare = copy.deepcopy(schema)
    del bare["properties"]["language"]["description"]
    assert undescribed(bare) == ["$.properties[language]"]
