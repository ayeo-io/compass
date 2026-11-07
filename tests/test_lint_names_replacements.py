"""`compass policy lint` names what replaces each removed `compass.yml` key.

One table, `removed_parts.REPLACEMENTS`, gives each removed key the settings
that replace it, or none, and whether `compass migrate` rewrites it (ADR-098
decision 7). Every `L-SETTING-REMOVED` finding takes its text from that row:
the message ends "Replacement: `<setting>`." or "Removed: nothing replaces
it.", then "`compass migrate` rewrites it." when migrate handles the key, and
`--json` gives the same settings in a `replacement` field. A pin of
`extends: compass:default@6` or `@7` is replaced by `acceptance_strategy:
off`, because the pin is what keeps the acceptance strategy `S17` off; a pin
of `@8` or later is removed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from compass_pkg import acceptance_strategy, removed_parts, settings_lint

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


def _removed_keys():
    """Every key of the six removed-key tables, as the lint names it."""
    return (set(settings_lint.REMOVED) | set(removed_parts.SETTINGS)
            | set(removed_parts.SETTING_FIELDS) | set(removed_parts.SWITCHES)
            | set(removed_parts.EFFECTS)
            | {f"capabilities.{name}" for name in removed_parts.CAPABILITIES})


# --- the table -------------------------------------------------------------------------

def test_every_removed_key_has_a_row():
    missing = sorted(key for key in _removed_keys() if key not in removed_parts.REPLACEMENTS)
    assert missing == [], f"removed keys with no REPLACEMENTS row: {missing}"


def test_every_row_names_a_removed_key():
    """A row for a key no table removes is a misspelt key, and its own key
    would still have no row."""
    extra = {"extends@6", "extends@7", "extends@8"} | {
        f"rules.*.{effect}" for effect in removed_parts.APPROACH_EFFECTS}
    stray = sorted(set(removed_parts.REPLACEMENTS) - _removed_keys() - extra)
    assert stray == [], f"REPLACEMENTS rows for no removed key: {stray}"


def test_each_row_is_a_tuple_of_settings_and_a_migrate_flag():
    for key, (settings, migrated) in removed_parts.REPLACEMENTS.items():
        assert isinstance(settings, tuple), key
        assert all(isinstance(s, str) and s.strip() for s in settings), key
        assert isinstance(migrated, bool), key


@pytest.mark.parametrize("value, row", [
    ("compass:default@5", "extends@6"),
    ("compass:default@6", "extends@6"),
    ("compass:default@7", "extends@7"),
    ("compass:default@8", "extends@8"),
    ("compass:default@9", "extends@8"),
    ("compass:default", "extends@8"),
    ({"from": "compass:default@7"}, "extends@7"),
    ("compass:strict@6", "extends"),
    ("./team.yml", "extends"),
])
def test_the_extends_row_follows_the_pinned_major(value, row):
    assert removed_parts.extends_row(value) == row


def test_the_extends_rows_split_where_the_strategy_starts():
    """The `@7` row replaces the pin with `acceptance_strategy: off` and the `@8`
    row removes it, so the split must be the first major that carries `S17`."""
    first = acceptance_strategy.FIRST_MAJOR
    assert removed_parts.extends_row(f"compass:default@{first - 1}") != "extends@8"
    assert removed_parts.extends_row(f"compass:default@{first}") == "extends@8"


def test_the_6_7_and_8_rows():
    off = (removed_parts.STRATEGY_OFF,)
    assert removed_parts.STRATEGY_OFF == "acceptance_strategy: {state: off, reason: ...}"
    assert removed_parts.REPLACEMENTS["extends@6"] == (off, True)
    assert removed_parts.REPLACEMENTS["extends@7"] == (off, True)
    assert removed_parts.REPLACEMENTS["extends@8"] == ((), True)


def test_an_approach_effect_of_any_rule_has_a_row():
    for path in ("rules.floors.rules.RP-X.then.force_minimum_approach",
                 "rules.mine.hit.never_skip"):
        assert removed_parts.replacement_of(path) == ((), True), path


def test_a_key_with_no_row_raises():
    with pytest.raises(KeyError, match="no REPLACEMENTS row"):
        removed_parts.replacement_of("nothing.like.this")


# --- the lint ---------------------------------------------------------------------------

def _removed(doc):
    return {f.path: f for f in settings_lint.lint(doc) if f.code == "L-SETTING-REMOVED"}


@pytest.mark.parametrize("major", [6, 7])
def test_a_pin_below_8_names_acceptance_strategy_off(major):
    (finding,) = _removed({"schema": 1, "extends": f"compass:default@{major}"}).values()
    assert finding.replacement == "acceptance_strategy: {state: off, reason: ...}"
    assert finding.message.endswith(
        "Replacement: `acceptance_strategy: {state: off, reason: ...}`. "
        "`compass migrate` rewrites it."), finding.message
    assert "`S17` off" in finding.message, finding.message


def test_a_pin_of_8_names_no_replacement():
    (finding,) = _removed({"schema": 1, "extends": "compass:default@8"}).values()
    assert finding.replacement is None
    assert finding.message.endswith(
        "Removed: nothing replaces it. `compass migrate` rewrites it."), finding.message
    assert "S17" not in finding.message


def test_every_removed_finding_names_its_row():
    doc = {"schema": 1, "extends": "compass:default@6", "gates": {}, "models": {},
           "dimensions": {}, "prices": {}, "capabilities": {"artifact-freshness": True},
           "approvers": {"project-waiver": ["sam"]},
           "project": {"build_command": "make"}}
    found = _removed(doc)
    assert sorted(found) == sorted(["extends", "gates", "models", "dimensions", "prices",
                                    "capabilities.artifact-freshness",
                                    "approvers.project-waiver", "project.build_command"])
    for path, finding in found.items():
        settings, migrated = removed_parts.replacement_of(path, doc.get(path))
        expected = (" Replacement: " + " or ".join(f"`{s}`" for s in settings) + "."
                    if settings else " Removed: nothing replaces it.")
        assert expected in finding.message, finding.message
        assert finding.message.endswith("`compass migrate` rewrites it.") == migrated, path
        assert finding.replacement == (" or ".join(settings) if settings else None), path


# --- the command ------------------------------------------------------------------------

def _run(root, *argv):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(root),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
           "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run([sys.executable, str(CLI), "policy", "lint", *argv], cwd=root,
                          env=env, capture_output=True, text=True, timeout=180)
    assert "Traceback" not in done.stderr, done.stderr
    return done


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """A project that holds a key with a replacement (`checks`) and one with none
    (`prices`)."""
    root = tmp_path_factory.mktemp("replacements")
    (root / ".compass").mkdir()
    (root / "compass.yml").write_text("schema: 1\nchecks: {}\nprices: {}\n", encoding="utf-8")
    return root


def test_the_text_names_each_replacement(project):
    done = _run(project)
    assert done.returncode == 0, done.stdout + done.stderr
    lines = {line.split(" [project] ")[1].split(":")[0]: line
             for line in done.stdout.splitlines() if "L-SETTING-REMOVED" in line}
    assert sorted(lines) == ["checks", "prices"], done.stdout
    assert lines["checks"].endswith(
        "Replacement: `project_checks`. `compass migrate` rewrites it."), lines["checks"]
    assert lines["prices"].endswith(
        "Removed: nothing replaces it. `compass migrate` rewrites it."), lines["prices"]


def test_the_json_gives_each_removed_finding_a_replacement(project):
    done = _run(project, "--json")
    assert done.returncode == 0, done.stdout + done.stderr
    findings = {f["path"]: f for f in json.loads(done.stdout)["findings"]}
    assert findings["checks"]["replacement"] == "project_checks"
    assert findings["prices"]["replacement"] is None
    assert list(findings["prices"]) == ["code", "level", "layer", "path", "group", "message",
                                        "detail", "replacement"]


def test_the_json_gives_no_replacement_to_another_finding(tmp_path):
    (tmp_path / ".compass").mkdir()
    (tmp_path / "compass.yml").write_text("schema: 1\nautonomy: sometimes\n",
                                          encoding="utf-8")
    done = _run(tmp_path, "--json")
    (finding,) = json.loads(done.stdout)["findings"]
    assert finding["code"] == "L-SETTING-INVALID"
    assert "replacement" not in finding


# --- the owning doc ---------------------------------------------------------------------

TABLE_START = "<!-- compass:replacements-table -->"
TABLE_END = "<!-- /compass:replacements-table -->"


def _family(key):
    """`(catalog, id)` for a key that is one entry of a catalog, such as
    `stages.design`, else None."""
    head, _, rest = key.partition(".")
    return (head, rest) if rest and "." not in rest and "*" not in rest else None


def table_lines():
    """The table of `docs/configuration.md` between the two markers, so the
    page cannot disagree with the lint. Each `REPLACEMENTS` key has a row, but
    entries of one catalog that follow each other with the same replacement
    share one row, which lists their ids."""
    groups = []
    for key, row in removed_parts.REPLACEMENTS.items():
        family = _family(key)
        last = groups[-1] if groups else None
        if family and last and last[0] == family[0] and last[2] == row:
            last[1].append(family[1])
        else:
            groups.append((family[0] if family else key, [family[1]] if family else [], row))
    lines = ["| Removed key | Replacement | `compass migrate` |", "|---|---|---|"]
    for head, ids, (settings, migrated) in groups:
        name = (f"`{head}.{ids[0]}`" if len(ids) == 1 else
                f"`{head}.<id>`: " + ", ".join(f"`{i}`" for i in ids)) if ids else f"`{head}`"
        instead = " or ".join(f"`{s}`" for s in settings) if settings else "removed"
        lines.append(f"| {name} | {instead} | {'rewrites it' if migrated else 'no'} |")
    return lines


def test_the_owning_doc_holds_the_table():
    text = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    assert TABLE_START in text and TABLE_END in text
    held = text.split(TABLE_START, 1)[1].split(TABLE_END, 1)[0].strip().splitlines()
    assert held == table_lines(), "\n".join(table_lines())
