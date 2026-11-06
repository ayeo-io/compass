"""The owning doc's shape for `depends_on`.

9.0.0 removed the board page, whose card and panel DBI-17 read (ADR-093), and the
issue page (ADR-091). `compass flow` and `--json` are covered in test_issue_dependencies.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent


# --- DBI-20 -----------------------------------------------------------------------

KEYS = ["issue", "reason", "until"]
# The path stages first, then the legacy stages an entry written before the
# four-stage path can name (ADR-092).
UNTIL = ["done", "in-review", "specify", "build", "ship", "define", "refine", "plan",
         "breakdown", "implement", "verify"]


def doc_keys():
    """The key names the owning doc states for an entry: the shape line it opens with."""
    text = (ROOT / "docs" / "issue-dependencies.md").read_text(encoding="utf-8")
    shape = re.search(r"`depends_on: \[\{([^}]*)\}\]`", text)
    assert shape, "docs/issue-dependencies.md states no shape line"
    return [part.split(":")[0].strip() for part in shape.group(1).split(",")], text


def reference_keys():
    """The entry keys under `depends_on` in the reference manifest."""
    lines = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8").splitlines()
    start = next(i for i, x in enumerate(lines) if x.startswith("depends_on:"))
    keys = []
    for line in lines[start + 1:]:
        found = re.match(r"^\s+(?:- )?(\w+):", line)
        if not found:
            break
        keys.append(found.group(1))
    return keys


def test_dbi_20_shape_pinned_in_schema_and_doc():
    import json
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    field = schema["properties"]["depends_on"]
    assert "depends_on" not in schema.get("required", [])
    assert field["type"] == "array"
    item = field["items"]
    assert item["additionalProperties"] is False
    assert list(item["properties"]) == KEYS
    assert sorted(item["required"]) == sorted(KEYS)
    for key in ("issue", "reason"):
        assert item["properties"][key]["type"] == "string"
        assert item["properties"][key]["minLength"] == 1
    until = item["properties"]["until"]
    assert until["enum"] == UNTIL and until["default"] == "done"
    # The three places name the same three keys.
    from_doc, text = doc_keys()
    assert from_doc == KEYS
    assert reference_keys() == KEYS
    # The doc states what the issue asks it to state.
    lowered = text.lower()
    for value in UNTIL:
        assert "`%s`" % value in text, value
    for fact in ("not-planned", "duplicate", "implement stage", "no git", "uncached",
                 "median", "fail-safe", "worktree", "bring that issue's folder",
                 "compass issue depends remove", "ADR-062"):
        assert fact.lower() in lowered, fact
    for name in ("reached", "judge", "dependency_block", "blocked_text", "hook_lines",
                 "entries"):
        assert "`lifecycle.%s`" % name in text, name
    # The owning-docs table and the command surfaces.
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "| `cli/compass_pkg/issue_depends.py` | `docs/issue-dependencies.md` |" in readme
    commands = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    helps = (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(encoding="utf-8")
    for verb in ("issue depends add", "issue depends remove"):
        assert "compass " + verb in commands, verb
        assert "'%s'" % verb in helps, verb
