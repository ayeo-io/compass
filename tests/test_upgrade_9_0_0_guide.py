"""The 9.0.0 upgrade guide agrees with the code (#359 step 12, ADR-098).

`docs/upgrade-9-0-0.md` holds four tables that `scripts/render-upgrade-guide.py`
writes from data: the removed settings, the removed verbs and flags, the
removed slash commands and the deleted checks. These tests fail when a table
is stale, when a slash command that 8.0.4 shipped is gone with no row, and when
the 8.x support line is missing from the guide, `SECURITY.md` or
`docs/releasing.md`.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
GUIDE = ROOT / "docs" / "upgrade-9-0-0.md"
SUPPORT = "8.x gets security fixes only, for 90 days after 9.0.0 is released"


def _script():
    spec = importlib.util.spec_from_file_location(
        "render_upgrade_guide", ROOT / "scripts" / "render-upgrade-guide.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SCRIPT = _script()


def _text(path):
    return path.read_text(encoding="utf-8")


def test_every_generated_table_equals_a_fresh_render():
    text = _text(GUIDE)
    assert SCRIPT.render(text) == text, (
        "docs/upgrade-9-0-0.md is stale: run scripts/render-upgrade-guide.py")


@pytest.mark.parametrize("name", sorted(SCRIPT.RENDERERS))
def test_each_table_is_between_its_markers(name):
    assert SCRIPT.held(_text(GUIDE), name) == SCRIPT.RENDERERS[name]()


def test_the_settings_table_is_the_one_in_the_configuration_page():
    """Two pages show `REPLACEMENTS`; they must not disagree."""
    text = _text(ROOT / "docs" / "configuration.md")
    start, end = "<!-- compass:replacements-table -->", "<!-- /compass:replacements-table -->"
    held = text.split(start, 1)[1].split(end, 1)[0].strip().splitlines()
    assert held == SCRIPT.settings_lines()


def test_every_removed_command_has_a_row():
    from compass_pkg import removed_parts
    rows = SCRIPT.held(_text(GUIDE), "commands")
    for _tokens, name, _instead, adr in removed_parts.COMMANDS:
        spelling = name.removeprefix("compass ")
        assert any(row.startswith(f"| `{spelling}` |") and row.endswith(f"| {adr} |")
                   for row in rows), name


def test_every_deleted_check_has_a_row():
    from compass_pkg import check_registry
    rows = SCRIPT.held(_text(GUIDE), "checks")
    named = {m.group(1) for row in rows if (m := re.match(r"\| `([^`]+)` \|", row))}
    assert named == set(check_registry.DELETED_CHECKS)


def _shipped_commands():
    return {p.stem for p in (ROOT / "commands").glob("*.md")}


def test_each_slash_command_8_0_4_shipped_and_9_0_0_lacks_has_a_row():
    removed = {n for names, _instead, _adr in SCRIPT.REMOVED_SLASH for n in names}
    gone = set(SCRIPT.COMMANDS_8_0_4) - _shipped_commands()
    assert removed == gone, (sorted(removed - gone), sorted(gone - removed))


def test_each_replacement_names_a_shipped_slash_command():
    shipped = _shipped_commands()
    for _names, instead, _adr in SCRIPT.REMOVED_SLASH:
        for name in re.findall(r"/compass:([a-z][a-z-]*)", instead):
            assert name in shipped, instead


def test_the_8_0_4_list_is_the_tagged_one():
    """The list in the script is what `v8.0.4` shipped. A clone without the tag
    skips this, and the list in the script still holds."""
    found = subprocess.run(["git", "ls-tree", "--name-only", "v8.0.4", "commands/"],
                           cwd=ROOT, capture_output=True, text=True)
    if found.returncode != 0 or not found.stdout.strip():
        pytest.skip("the tag v8.0.4 is not in this clone")
    tagged = {Path(line).stem for line in found.stdout.split() if line.endswith(".md")}
    assert tagged == set(SCRIPT.COMMANDS_8_0_4)


def test_outside_its_table_the_guide_names_only_shipped_slash_commands():
    """`tests/test_documented_slash_commands_exist.py` skips this page, so that
    the table can name each removed command. Everywhere else on the page a
    slash command must exist."""
    start, end = SCRIPT.MARKERS["slash"]
    text = _text(GUIDE)
    before, rest = text.split(start, 1)
    outside = before + rest.split(end, 1)[1]
    # The closing marker of each table, `<!-- /compass:...`, is not a command.
    named = set(re.findall(r"(?<!<!-- )/compass:([a-z][a-z-]*)", outside))
    assert named <= _shipped_commands(), sorted(named - _shipped_commands())


@pytest.mark.parametrize("path", ["docs/upgrade-9-0-0.md", "SECURITY.md", "docs/releasing.md"])
def test_the_support_line_is_stated(path):
    text = " ".join(_text(ROOT / path).replace(">", " ").split())
    assert SUPPORT in text, path


def test_the_check_mode_of_the_script_passes():
    done = subprocess.run([sys.executable, str(ROOT / "scripts" / "render-upgrade-guide.py"),
                           "--check"], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stdout + done.stderr
