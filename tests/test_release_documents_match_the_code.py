"""Release and reader documents state what the code does (`TRC-D5`).

Each test pins a sentence that was false when it was written: the commands
that fetch a git parent, what a 5.x user sees, what a project without a
`compass.yml` keeps, which v5 commands refuse a schema 3.0 manifest, and four
claims in the README, the methodology and the quickstart. A test that reads a
document cannot show the document is true, so the fetch list also has a source
scan: a module that starts to fetch a git parent fails it until the documents
name the command.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every command that can reach the network through a git parent, as a reader
# types it after `compass`.
FETCHING = ("policy lint", "policy show", "policy diff", "policy update",
            "preset test", "approach evaluate --write")

# The modules that pass a fetch decision to the code that resolves a git
# parent, and the commands each one serves.
FETCH_MODULES = {
    "effective.py": "approach evaluate --write (the generation it commits)",
    "issue_config_cmd.py": "approach evaluate --write (the reassess plan)",
    "policy_cmd.py": "policy lint, policy show, policy diff, preset test",
    "policy_update.py": "policy update",
}


def _text(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """The text with backticks removed and every run of white space one space."""
    return " ".join(text.replace("`", "").split())


def _paragraph(text: str, start: str) -> str:
    """The paragraph or list item that holds `start`."""
    flat = text.replace("\r", "")
    head = flat.index(start)
    begin = flat.rfind("\n\n", 0, head)
    end = flat.find("\n\n", head)
    item = flat.rfind("\n- ", 0, head)
    begin = max(begin, item)
    return _flat(flat[begin:end if end != -1 else len(flat)])


# A call that hands a fetch decision on: any `fetch=` keyword except the two
# that cannot start a fetch (`fetch=False`, and `fetch=fetch`, which passes on
# a decision the caller made and is counted where it is made).
FETCH_CALL = re.compile(r"\bfetch=(?!False\b|fetch\b)|_may_fetch\(args\)")


def fetching_modules(sources):
    """The names of the sources that pass a fetch decision to the resolver."""
    return {name for name, text in sources.items() if FETCH_CALL.search(text)}


def test_the_scan_reports_a_new_module_whatever_it_passes_as_the_decision():
    for planted in ("parents.resolve_chain(root, 'x', fetch=True)",
                    "parents.resolve_chain(root, 'x', fetch=not offline)",
                    "parents.resolve_chain(root, 'x', fetch=args.online)"):
        sources = {"effective.py": "x = 1", "new_module.py": planted}
        assert fetching_modules(sources) == {"new_module.py"}, planted
    assert fetching_modules({"a.py": "def f(root, fetch=False): return g(root, fetch=fetch)"}) == set()


def test_the_source_scan_finds_the_modules_that_fetch_a_git_parent():
    """A new module that fetches fails here, so the lists below are revisited."""
    sources = {path.name: path.read_text(encoding="utf-8")
               for path in sorted((ROOT / "cli" / "compass_pkg").glob("*.py"))}
    found = fetching_modules(sources)
    assert found == set(FETCH_MODULES), (
        f"a module now fetches a git parent, or one stopped: {sorted(found)}. "
        "Name the command in README.md, docs/security.md and docs/git-parents.md.")


def test_the_fetch_list_names_every_command_that_fetches():
    readme = _paragraph(_text("README.md"), "Only `compass")
    security = _paragraph(_text("docs", "security.md"), "Only `compass")
    for name, text in (("README.md", readme), ("docs/security.md", security)):
        for command in FETCHING:
            assert command in text, f"{name} does not list `compass {command}`: {text}"
        assert "compass check" in text, name
    # `issue configure --commit` runs the reassess, which fetches; the preview
    # and the proposal do not.
    assert "issue configure --commit" in security, security
    assert "issue configure never fetch" not in security, security
    table = _text("docs", "git-parents.md").split("## When Compass fetches", 1)[1]
    table = _flat(table.split("\n\n", 2)[1])
    for command in ("policy lint", "policy update", "policy diff", "preset test",
                    "approach evaluate --write"):
        assert command in table, f"docs/git-parents.md does not list {command}"


def test_the_fetch_lists_say_that_policy_update_always_asks_the_remote():
    for name, text in (("README.md", _text("README.md")),
                       ("docs/security.md", _text("docs", "security.md"))):
        flat = _flat(text)
        assert ("policy update always asks the remote which commit its ref names, "
                "unless COMPASS_OFFLINE=1 is set") in flat, name


def test_the_release_notes_say_what_happens_to_a_5x_user_who_does_nothing():
    notes = _text("docs", "releasing.md")
    row = next(l for l in notes.splitlines() if l.startswith("| A 5.x user who does nothing"))
    assert "Nothing changes" not in row, row
    for needed in ("schema 3.0", "manifest.yml.v5.bak", "compass flow --json"):
        assert needed in _flat(row), (needed, row)
    assert "keeps the 5.6.0 output exactly" not in notes
    assert "keeps the 5.6.0 document names" in _flat(notes)


def test_the_upgrade_page_names_the_v5_commands_that_refuse_a_3_0_manifest():
    page = _flat(_text("docs", "upgrade-6-0-0.md"))
    assert "A v5 command refuses a 3.0 file" not in page
    sentence = page.split("A 6.0.0 command reads schemas 1, 2 and 3.", 1)[1].split(" The first save of a manifest", 1)[0]
    for needed in ("v5 check", "issue lint", "ci", "approach evaluate",
                   "refuse", "next", "flow", "read", "do not run a v5"):
        assert needed.lower() in sentence.lower(), (needed, sentence)
    assert "every checkout and plugin" in sentence


def test_the_reader_documents_make_no_claim_the_code_contradicts():
    readme = _flat(_text("README.md"))
    assert "another compatible agent runtime" not in readme
    assert "are hard, checkable and blocking" not in readme
    assert "under enforced adoption" in readme and "cannot see" in readme
    methodology = _flat(_text("docs", "methodology.md"))
    assert "Guardrails are few, checkable and blocking" not in methodology
    assert "under enforced adoption" in methodology
    quickstart = _flat(_text("docs", "quickstart.md"))
    assert "The marker only ever means a real failure was observed" not in quickstart
    assert "refuses the edit" in quickstart and "red record" in quickstart
    assert "Most spec-driven development systems" not in readme
    assert "Compass chooses the process for each change from its assessment" in readme


SHIPPED_TEXT = ("cli/compass_pkg", "hooks", "docs", "README.md", "agents", "skills",
                "commands", "governance", "schemas")
NOT_SCANNED = ("docs/compass/", "docs/system-spec", "governance/decisions/",
               "docs/launch-article")
# Sentences that treated a feature as still to come after it was built: the
# generation store, `policy diff` and `issue migrate --config`.
LANDED_FEATURES_AS_FUTURE = re.compile(
    r"generation store has not landed|until the generation store|"
    r"generation store (lands|exists)|store lands|"
    r"when that command lands|## Not built yet", re.IGNORECASE)


def test_no_shipped_text_treats_a_landed_feature_as_still_to_come():
    """Scenario `TRC-D6`: a sentence that waits for a built feature is wrong."""
    hits = []
    for top in SHIPPED_TEXT:
        base = ROOT / top
        files = [base] if base.is_file() else sorted(p for p in base.rglob("*") if p.is_file())
        for path in files:
            rel = path.relative_to(ROOT).as_posix()
            if rel.startswith(NOT_SCANNED) or path.suffix not in (".py", ".md", ".yml", ".sh", ".json"):
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if LANDED_FEATURES_AS_FUTURE.search(line):
                    hits.append(f"{rel}:{number}: {line.strip()[:90]}")
    assert hits == [], "\n".join(hits)
