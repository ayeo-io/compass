"""What the views show for `depends_on`: the board card and panel, the issue page, and the
owning doc's shape.

Every test runs without a network. The project leaves the GitHub switches off and links no
GitHub issue, and a `gh` shim on PATH fails the test if anything calls it (`assert_no_gh_call`).
The fixture project, the CLI runner and the shim come from `test_issue_dependencies`.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from test_issue_dependencies import Project, assert_no_gh_call, compass, dep

ROOT = Path(__file__).resolve().parent.parent


# --- reading the pages ------------------------------------------------------------

def board_html(project):
    out = project.root / "board.html"
    done = compass(project.root, "board", "render", "--no-open", "--out", str(out))
    assert done.returncode == 0, done
    return out.read_text(encoding="utf-8")


def card(html, slug):
    """The markup of the card for `slug`."""
    found = re.search(r'<a class="card[^"]*" data-approach="[^"]*" href="#issue-\d+">(?:(?!</a>).)*?'
                      r'<span class="slug">%s</span>(?:(?!</a>).)*</a>' % re.escape(slug), html, re.S)
    assert found, "no card for %s" % slug
    return found.group(0)


def panel(html, slug):
    """The markup of the panel for `slug`."""
    found = re.search(r'<section class="panel" id="issue-\d+">\s*<h2>%s</h2>.*?(?=\n<section class="panel"|\n</body>)'
                      % re.escape(slug), html, re.S)
    assert found, "no panel for %s" % slug
    return found.group(0)


def dependency_lines(markup):
    """The text of each line in the panel's Dependencies part."""
    part = re.search(r'<section class="part deps"><h3>Dependencies</h3>(.*?)</section>',
                     markup, re.S)
    if not part:
        return None
    return [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<li[^>]*>(.*?)</li>",
                                                                   part.group(1), re.S)]


def blocked_tile(html):
    return re.search(r"<li>blocked (\d+)</li>", html).group(1)


# --- DBI-17 -----------------------------------------------------------------------

def test_dbi_17_board_card_and_panel(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("a", "implement", depends=[dep("b", "done", "needs the parse cache")])
    html = board_html(project)
    a_card = card(html, "a")
    assert '<span class="meta">waits for b</span>' in a_card
    assert '<span class="flag">blocked: waits for b to reach done</span>' in a_card
    assert " dashed" in a_card.split(">", 1)[0]
    assert blocked_tile(html) == "1"
    assert dependency_lines(panel(html, "a")) == [
        "b - needs the parse cache - until done - in-progress - waiting"]
    # b has no dependencies, so it has no Dependencies part and no "waits for" line.
    assert dependency_lines(panel(html, "b")) is None
    assert "waits for" not in card(html, "b")

    # b is closed as completed: the wait is met.
    manifest = project.manifest("b")
    manifest["status"] = "done"
    manifest["close_reason"] = "completed"
    project.write("b", manifest)
    html = board_html(project)
    a_card = card(html, "a")
    assert "waits for" not in a_card and "blocked" not in a_card
    assert blocked_tile(html) == "0"
    assert dependency_lines(panel(html, "a")) == [
        "b - needs the parse cache - until done - done - met"]

    # An issue at plan: the card names the wait, and nothing is blocked.
    project.issue("b", "implement")
    project.issue("a", "implement")
    project.issue("p", "plan", depends=[dep("b", "done", "needs the parse cache")])
    html = board_html(project)
    p_card = card(html, "p")
    assert '<span class="meta">waits for b</span>' in p_card
    assert "blocked" not in p_card
    assert blocked_tile(html) == "0"

    # A dependency with no manifest is "not found", and a card does not claim to wait for it.
    project.issue("a", "implement", depends=[dep("gone", "plan", "a later issue")])
    html = board_html(project)
    assert dependency_lines(panel(html, "a")) == ["gone - a later issue - until plan - not found"]
    assert "waits for" not in card(html, "a")

    # Several unmet dependencies are listed in the order they are recorded, and a manifest
    # that does not parse reads "unreadable".
    project.issue("c", "implement")
    (project.dir("broken")).mkdir()
    (project.dir("broken") / "manifest.yml").write_text("a: [unclosed\n", encoding="utf-8")
    project.issue("a", "implement", depends=[dep("c"), dep("b"), dep("broken", "plan", "x")])
    html = board_html(project)
    assert '<span class="meta">waits for c, b</span>' in card(html, "a")
    assert dependency_lines(panel(html, "a")) == [
        "c - needs it - until done - in-progress - waiting",
        "b - needs it - until done - in-progress - waiting",
        "broken - x - until plan - unreadable"]
    assert_no_gh_call(project.root)


# --- DBI-19 -----------------------------------------------------------------------

def page_text(project, slug):
    done = compass(project.root, "issue", "render", "--issue", slug)
    assert done.returncode == 0, done
    pages = list((project.root / "docs" / "compass").glob("*-%s/README.md" % slug))
    assert len(pages) == 1, pages
    return pages[0].read_text(encoding="utf-8")


def block(text, kind):
    found = re.search(r"<!-- compass:render %s -->\n(.*?)<!-- /compass:render -->" % kind,
                      text, re.S)
    assert found, "no %s block" % kind
    return found.group(1)


def test_dbi_19_issue_page_related_block(tmp_path):
    project = Project(tmp_path)
    project.issue("b", "implement")
    project.issue("c", "ship", close="completed")
    project.issue("a", "implement", depends=[dep("b"), dep("c", "plan", "needs its design")])
    page = page_text(project, "a")
    related = block(page, "related")
    lines = [x for x in related.splitlines() if x.startswith("- depends on:")]
    assert len(lines) == 2, related
    assert lines[0].endswith("](../2026-10-01-b/README.md) - in-progress - waits for b to reach done")
    assert lines[1].endswith("](../2026-10-01-c/README.md) - done (completed) - met")
    assert "\nBlocked: waits for b to reach done\n" in block(page, "header")
    assert "depended on by: [a](../2026-10-01-a/README.md)" in block(page_text(project, "b"), "related")

    # A dependency that is not found or unreadable keeps the text it had.
    project.issue("a", "implement", depends=[dep("gone")])
    (project.dir("broken")).mkdir()
    (project.dir("broken") / "manifest.yml").write_text("a: [unclosed\n", encoding="utf-8")
    manifest = project.manifest("a")
    manifest["depends_on"].append(dep("broken"))
    project.write("a", manifest)
    related = block(page_text(project, "a"), "related")
    assert "- depends on: `gone` - not found\n" in related + "\n"
    assert "- depends on: `broken` - unreadable\n" in related + "\n"

    # decision-required and follow-ups are the same with and without depends_on.
    project.issue("a", "implement", depends=[dep("b")])
    with_key = page_text(project, "a")
    manifest = project.manifest("a")
    del manifest["depends_on"]
    project.write("a", manifest)
    without_key = page_text(project, "a")
    for kind in ("decision-required", "follow-ups"):
        assert block(with_key, kind) == block(without_key, kind), kind
    assert "waits for" not in without_key
    assert_no_gh_call(project.root)


# --- DBI-20 -----------------------------------------------------------------------

KEYS = ["issue", "reason", "until"]
UNTIL = ["done", "in-review", "define", "refine", "plan", "breakdown", "implement", "verify",
         "ship"]


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
                 "compass issue depends remove", "ADR-062",
                 "risks and dependencies"):
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
