"""The decisions behind the vocabulary and CLI renames are recorded, and the
vocabulary file, glossary and guards agree with them.

The scenarios are group G of the issue `vocabulary-and-cli-renames`. Each
increment of that issue adds the tests for its own scenarios to this file.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
ADRS = ROOT / "architecture" / "decisions"
LEDGER = ROOT / "governance" / "decisions"

# The record that amends the frozen vocabulary (ADR-012) and the rule for an
# unobserved adopter (ADR-024), and the record for the derived lifecycle.
VOCABULARY_SLUG = "vocabulary-and-cli-naming"
LIFECYCLE_SLUG = "the-issue-lifecycle-is-derived-from-records"

NEW_LEDGER = [
    "2026-10-08-the-living-spec-heading-word-is-completed",
    "2026-10-08-a-cli-spelling-is-released-only-when-a-tag-holds-it",
]

# The records that use a retired word and are read through the new names.
READ_THROUGH = ["ADR-008", "ADR-026", "ADR-034", "ADR-036", "ADR-038"]


def _record(slug: str) -> Path | None:
    found = sorted(ADRS.glob(f"ADR-*-{slug}.md"))
    return found[0] if len(found) == 1 else None


def _section(text: str, heading: str) -> str:
    """The body of a `## heading` section, up to the next `## `."""
    m = re.search(rf"^## {re.escape(heading)}[^\n]*\n(.*?)(?=^## |\Z)",
                  text, re.M | re.S)
    return m.group(1) if m else ""


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert m, "no frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        out[key.strip()] = value.strip().strip("'\"")
    return out


def _base_ref(root: Path) -> str | None:
    """The commit the branch started from, or None when there is no main."""
    for ref in ("origin/main", "main"):
        r = subprocess.run(["git", "merge-base", "HEAD", ref], cwd=root,
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def changed_since(root: Path, base: str, paths: list[str]) -> list[str]:
    """The paths whose content differs from `base`, committed or not."""
    r = subprocess.run(["git", "diff", "--name-only", base, "--", *paths],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()


def alias_section_problems(text: str) -> list[str]:
    """What the alias section of the vocabulary record fails to say."""
    section = _section(text, "Aliases")
    wanted = {
        "7.0.0": "the end of the aliases",
        "release tag": "a spelling counts as released only when a tag holds it",
        "renamed": "aliases cover renamed CLI verbs",
        "no alias": "an unreleased spelling gets no alias",
        "read through": "vocabulary values are read through the rename tables",
        "not redirected": "a vocabulary value is not redirected",
    }
    if not section:
        return ["no `## Aliases` section"]
    return [f"the alias section does not say {why} ({needle!r})"
            for needle, why in wanted.items() if needle not in section]


# --- the records exist and the amended ones are unchanged -------------------

def test_vr_g1_one_new_record_amends_the_freeze_and_the_adopter_rule():
    path = _record(VOCABULARY_SLUG)
    assert path is not None, (
        f"expected exactly one architecture/decisions/ADR-*-{VOCABULARY_SLUG}.md")
    text = path.read_text(encoding="utf-8")
    front = _frontmatter(text)
    number = int(front["id"].split("-")[1])
    assert number > 43, "the record takes a number after ADR-043"
    assert front["status"] == "accepted"
    assert front["supersedes"] == "" and front["superseded_by"] == ""
    assert re.search(r"[Aa]mends ADR-012", text)
    assert "ADR-024" in text
    assert re.search(r"[Aa]mends ADR-012[^\n]*ADR-024|ADR-024[^\n]*amend",
                     text, re.I), "the record says it amends both"
    for heading in ("Context", "Decision", "Alternatives considered",
                    "Consequences", "References"):
        assert _section(text, heading).strip(), f"empty section: {heading}"
    index = (ADRS / "README.md").read_text(encoding="utf-8")
    row = next((ln for ln in index.splitlines()
                if f"[{front['id']}]" in ln), "")
    assert "amends ADR-012" in row and "ADR-024" in row, (
        "the index row names the records this one amends")


def test_vr_g1_the_amended_records_are_unchanged_from_main():
    base = _base_ref(ROOT)
    if base is None:
        pytest.skip("no main branch to compare with")
    names = [p.name for p in ADRS.glob("ADR-012-*.md")]
    names += [p.name for p in ADRS.glob("ADR-024-*.md")]
    assert len(names) == 2
    rel = [f"architecture/decisions/{n}" for n in names]
    assert changed_since(ROOT, base, rel) == [], (
        "a merged decision record never changes; amend it with a new record")


def test_vr_g1_the_unchanged_check_reports_an_edit(tmp_path):
    """Plant an edit: the check must name the file."""
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True,
                       capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (tmp_path / "ADR-012.md").write_text("one\n")
    git("add", ".")
    git("commit", "-q", "-m", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path,
                          capture_output=True, text=True).stdout.strip()
    assert changed_since(tmp_path, base, ["ADR-012.md"]) == []
    (tmp_path / "ADR-012.md").write_text("two\n")
    assert changed_since(tmp_path, base, ["ADR-012.md"]) == ["ADR-012.md"]


def test_vr_g1_the_record_reads_older_records_through_the_new_names():
    path = _record(VOCABULARY_SLUG)
    assert path is not None
    text = path.read_text(encoding="utf-8")
    for adr in READ_THROUGH:
        assert adr in text, f"the record does not say how {adr} now reads"


def test_vr_g1_the_lifecycle_record_and_the_ledger_entries_exist():
    path = _record(LIFECYCLE_SLUG)
    assert path is not None, (
        f"expected exactly one architecture/decisions/ADR-*-{LIFECYCLE_SLUG}.md")
    text = path.read_text(encoding="utf-8")
    assert _frontmatter(text)["status"] == "accepted"
    assert "schema_version" in text and "3.0" in text
    for slug in NEW_LEDGER:
        entry = LEDGER / f"{slug}.md"
        assert entry.is_file(), f"missing ledger entry {slug}"
        body = entry.read_text(encoding="utf-8")
        for heading in ("Decided by", "Date", "Supersedes", "Decision", "Why",
                        "Evidence"):
            assert _section(body, heading).strip(), (
                f"{slug}: empty section {heading}")


# --- the alias section limits aliases ---------------------------------------

def test_vr_g2_the_alias_section_limits_aliases_and_says_values_are_read():
    path = _record(VOCABULARY_SLUG)
    assert path is not None
    assert alias_section_problems(path.read_text(encoding="utf-8")) == []


def test_vr_g2_the_alias_check_reports_a_section_that_says_too_little():
    bad = "## Aliases\n\nEvery retired word keeps an alias.\n"
    problems = alias_section_problems(bad)
    assert any("7.0.0" in p for p in problems)
    assert any("not redirected" in p for p in problems)
    assert alias_section_problems("## Decision\n\nx\n") == [
        "no `## Aliases` section"]


# --- the terminology file: issue types, workflow and levels ------------------

TERMINOLOGY = ROOT / "governance" / "terminology.yml"
GLOSSARY = ROOT / "docs" / "glossary.md"
# The route-noun guard covers only these three directories. Widening it to
# docs/, governance/ and the other scanned surfaces is a larger sweep, owed
# before 7.0.0 and tracked in the repository's issue #524.
SCAN_ROOTS = ("commands", "skills", "agents")


def _terms() -> dict:
    return yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))["terms"]


def _flat(entry: dict, key: str = "means") -> str:
    return " ".join(str(entry.get(key, "")).split())


def test_vr_g3_the_issue_type_entry_lists_feature_bug_and_task():
    terms = _terms()
    means = _flat(terms["issue-type"])
    assert re.search(r"\bfeature, bug or task\b", means), means
    for kind in ("feature", "bug", "task"):
        assert kind in terms, f"no entry for the issue type {kind}"
        assert kind in terms["issue-type"]["related"]
    assert "bug-fix" not in terms, "bug fix is not an issue type; bug is"
    assert "quick fix, hotfix and spike are delivery approaches" in means


def test_vr_g3_quick_fix_hotfix_and_spike_are_delivery_approaches_only():
    terms = _terms()
    for name in ("quick-fix", "hotfix", "spike"):
        entry = terms[name]
        assert "delivery approach" in _flat(entry), name
        assert "issue-type" not in (entry.get("related") or []), name
        assert "issue type" not in _flat(entry), name


def test_vr_g4_task_is_flagged_as_an_issue_but_not_as_an_issue_type():
    from test_terminology import _scan_text
    as_type = "The issue types are feature, bug and task.\n"
    as_type_2 = "Set the issue type to task when nothing a user sees changes.\n"
    as_issue = "Close the task when its tests pass.\n"
    assert _scan_text(as_type) == []
    assert _scan_text(as_type_2) == []
    hits = _scan_text(as_issue)
    assert len(hits) == 1 and "banned 'task'" in hits[0]
    mixed = _scan_text(as_type + as_issue)
    assert len(mixed) == 1 and ":2:" in mixed[0]


def test_vr_g5_the_workflow_entries_name_the_states_reasons_and_flag():
    terms = _terms()
    states = _flat(terms["workflow-state"])
    for state in ("backlog", "ready", "in-progress", "in-review", "done"):
        assert state in states, state
    reasons = _flat(terms["close-reason"])
    for reason in ("completed", "not-planned", "duplicate"):
        assert reason in reasons, reason
    assert _flat(terms["blocked"]).startswith("A flag, not a state")
    assert "close-reason" in terms["workflow-state"]["related"]


def test_vr_g6_epic_initiative_and_milestone_each_have_an_entry():
    terms = _terms()
    for level in ("epic", "initiative", "milestone"):
        assert level in terms, f"no entry for {level}"
        assert len(_flat(terms[level]).split()) >= 8, level
    everything = " ".join(_flat(e) for e in terms.values())
    assert not re.search(r"\bepic\b[^.]*\b(?:is|was) dropped|"
                         r"\bthat word is dropped", everything), (
        "an entry still says epic is dropped")


def test_vr_g6_levels_follow_the_decision_of_8_october():
    """An epic is one outcome in one milestone under one intent; an
    initiative is several outcomes across milestones; a milestone is a
    release checkpoint, not a level."""
    terms = _terms()
    epic = _flat(terms["epic"], "means").lower()
    assert "one outcome" in epic and "one milestone" in epic
    assert "one intent" in epic
    initiative = _flat(terms["initiative"], "means").lower()
    assert "several outcomes" in initiative
    assert "milestones" in initiative
    milestone = _flat(terms["milestone"], "means").lower()
    assert "release checkpoint" in milestone
    assert "not a level" in milestone
    glossary = GLOSSARY.read_text(encoding="utf-8")
    assert "one outcome" in glossary and "release checkpoint" in glossary


# --- the retired list and the read-side tables hold the same triples ---------

def _retired_in_terminology() -> list[tuple[str, str, str | None]]:
    data = yaml.safe_load(TERMINOLOGY.read_text(encoding="utf-8"))
    rows = data.get("retired_values")
    assert isinstance(rows, list), "terminology.yml has no `retired_values:` list"
    return sorted((r["field"], r["old"], r["new"]) for r in rows)


def _word_map():
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        from compass_pkg import word_map
    except ImportError:
        raise AssertionError("cli/compass_pkg/word_map.py does not exist") from None
    return word_map


def test_vr_g7_the_retired_list_and_the_mapping_tables_hold_the_same_triples():
    word_map = _word_map()
    assert _retired_in_terminology() == word_map.retired_triples()


def test_vr_g7_the_parity_check_reports_a_row_held_by_one_side_only(monkeypatch):
    """A check that cannot fail proves nothing: add a row to the tables only."""
    word_map = _word_map()
    rows = {"size": {"standard": "medium"}}
    monkeypatch.setattr(word_map, "tables", lambda: rows)
    assert word_map.retired_triples() == [("size", "standard", "medium")]
    assert _retired_in_terminology() != word_map.retired_triples()


def test_vr_g7_the_fallback_tables_equal_the_file_with_the_file_unreadable(
        monkeypatch):
    """The in-module copy is for a checkout with no framework install; a test
    that reads the file both times compares it with itself."""
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import core
    word_map = _word_map()
    from_file = word_map.tables()
    monkeypatch.setattr(core, "migrate_map_path",
                        lambda: str(ROOT / "no-such-dir" / "migrate-map.yml"))
    assert word_map.tables() == from_file
    assert word_map.FALLBACK == from_file


# --- "route" is a verb only in the prose that teaches ------------------------

ROUTE_RE = re.compile(r"\b(?:route|routes|routed|off-route)\b", re.I)
ROUTE_MARKER = "vocabulary-scan: allow - route is a verb here"


def route_hits(text: str, name: str) -> list[str]:
    """Lines that use the word without the reviewed-verb marker."""
    return [f"{name}:{n}: {line.strip()[:80]}"
            for n, line in enumerate(text.splitlines(), 1)
            if ROUTE_RE.search(line) and ROUTE_MARKER not in line]


def test_vr_g8_every_use_of_route_in_shipped_prose_carries_the_marker():
    hits = []
    for top in SCAN_ROOTS:
        for path in sorted((ROOT / top).rglob("*.md")):
            hits += route_hits(path.read_text(encoding="utf-8"),
                               str(path.relative_to(ROOT)))
    assert hits == [], "route is a verb only; mark a verb use:\n" + "\n".join(hits)


def test_vr_g8_a_planted_noun_fails_and_a_marked_verb_passes():
    noun = "Where the route plans in full, add section 5a.\n"
    assert route_hits(noun, "sample.md") == ["sample.md:1: " + noun.strip()]
    assert route_hits("A stalled issue is off-route.\n", "sample.md")
    assert route_hits("It routed the work.\n", "sample.md")
    verb = f"Run assess; it routes a spike. <!-- {ROUTE_MARKER} -->\n"
    assert route_hits(verb, "sample.md") == []


# --- the glossary paragraph on check, gate, guardrail and obligation ---------

def test_vr_g10_one_glossary_paragraph_relates_guardrail_gate_and_obligation():
    text = GLOSSARY.read_text(encoding="utf-8")
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", text)]
    wanted = ("a guardrail is made of checks",
              "a gate is cleared by evidence",
              "an obligation is anything the configuration asks for")
    holders = [p for p in paragraphs
               if all(w in p.lower() for w in wanted)]
    assert len(holders) == 1, (
        "expected one paragraph that says all three; found %d" % len(holders))


# --- no module compares an issue status with a retired word ------------------
#
# After the status words change, a comparison with a retired word never
# matches and nothing reports it. `status_words` is the one place that knows
# the words, so any other literal in a comparison, a table, a default or a
# subscript is a finding. A string built at run time is not seen.

RETIRED_STATUS_WORDS = frozenset(
    {"landed", "queued", "parked", "abandoned", "active"})

# A hook line that names a status and compares or assigns a retired word.
HOOK_STATUS_RE = re.compile(
    r"""status["']?\)?\s*(?:==|!=|=~|=|-eq|-ne)\s*["']?(?:%s)\b"""
    % "|".join(sorted(RETIRED_STATUS_WORDS)))

# (module, text of the line, reason). A line is allowed only with a reason,
# and an entry that matches no finding fails the test.
STATUS_WORD_ALLOW = (
    ("status_words.py", "_RETIRED_CLOSE_REASON = {",
     "the one table of the words 6.0.0 stops storing and the close reason each stood for"),
    ("status_words.py", "_RETIRED_HOLDS = (",
     "the one list of the retired words that meant a hold"),
    ("status_words.py", "_IN_FLIGHT_WORDS = (",
     "the words accepted and ignored as in flight"),
    ("status_words.py", "RETIRED_STATUSES = (",
     "the five words stored before 6.0.0, read until 7.0.0 and never written"),
    ("word_map.py", '"queued": "backlog",',
     "the fallback copy of the issue status table in cli/migrate-map.yml"),
    ("word_map.py", '"parked": "backlog",',
     "the fallback copy of the issue status table in cli/migrate-map.yml"),
    ("word_map.py", '"active": None,',
     "the fallback copy of the issue status table in cli/migrate-map.yml"),
    ("word_map.py", '"landed": "done",',
     "the fallback copy of the issue status table in cli/migrate-map.yml"),
    ("word_map.py", '"abandoned": "done",',
     "the fallback copy of the issue status table in cli/migrate-map.yml"),
    ("word_map.py", 'FALLBACK["close_reason"]',
     "the fallback copy of the close reason table in cli/migrate-map.yml"),
    ("word_map.py", 'if "parked" in olds and',
     "the rollback map returns a backlog hold that records why as the old parked word"),
)


def _scan_source():
    import sys
    sys.path.insert(0, str(ROOT / "tests"))
    from test_stable_ids import scan_source
    return scan_source


def status_word_hits(source: str, name: str) -> list[tuple[str, int, str, str]]:
    """`(name, line, word, line text)` for each retired word in a scanned
    position of Python source."""
    lines = source.splitlines()
    return [(name, line, value, lines[line - 1].strip())
            for line, _col, value in _scan_source()(source)
            if value in RETIRED_STATUS_WORDS]


def hook_status_hits(text: str, name: str) -> list[tuple[str, int, str, str]]:
    """The same, for a shell hook: a line that is not a comment."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        found = HOOK_STATUS_RE.search(line)
        if found:
            hits.append((name, n, found.group(0), line.strip()))
    return hits


def scan_status_words() -> list[tuple[str, int, str, str]]:
    hits = []
    cli = ROOT / "cli"
    paths = [*sorted((cli / "compass_pkg").glob("*.py")), cli / "compass"]
    for path in paths:
        hits += status_word_hits(path.read_text(encoding="utf-8"), path.name)
    for path in sorted((ROOT / "hooks").glob("*.sh")):
        hits += hook_status_hits(path.read_text(encoding="utf-8"), path.name)
    return hits


def _allowed(hit, allow=STATUS_WORD_ALLOW) -> bool:
    name, _line, _word, text = hit
    return any(m == name and fragment in text for m, fragment, _why in allow)


def test_vr_g11_no_module_compares_a_status_with_a_retired_word():
    open_hits = [h for h in scan_status_words() if not _allowed(h)]
    assert open_hits == [], (
        "read the status through status_words (is_closed, is_completed, is_held, "
        "is_in_flight):\n" + "\n".join(f"  {n}:{ln} {w!r}: {t}" for n, ln, w, t in open_hits))


def test_vr_g11_each_allowed_line_states_a_reason_and_matches_a_finding():
    hits = scan_status_words()
    for module, fragment, reason in STATUS_WORD_ALLOW:
        assert len(reason.split()) >= 4, (module, fragment, "give a reason")
        assert any(m == module and fragment in t for m, _l, _w, t in hits), (
            f"{module}: no finding holds {fragment!r}, so the entry is out of date")


def test_vr_g11_a_planted_comparison_fails_the_guard():
    for planted in ('if task.get("status") == "landed":\n    pass\n',
                    'if status == "landed":\n    pass\n',
                    'if task["status"] in ("queued", "parked"):\n    pass\n',
                    'x = {"abandoned": 1}\n',
                    'def f(status="active"):\n    pass\n'):
        hits = status_word_hits(planted, "planted.py")
        assert hits and not all(_allowed(h) for h in hits), planted


def test_vr_g11_a_planted_hook_comparison_fails_the_guard():
    for planted in ('if [ "$status" = "landed" ]; then\n  :\nfi\n',
                    'status == landed\n',
                    'if task.get("status") == "queued":\n'):
        hits = hook_status_hits(planted, "planted.sh")
        assert hits and not all(_allowed(h) for h in hits), planted
    assert hook_status_hits("# status == landed is gone\n", "planted.sh") == []


def test_vr_g11_a_word_in_a_message_or_a_name_is_not_a_comparison():
    assert status_word_hits('print("the issue landed")\nlanded_by = 1\n', "m.py") == []
    assert hook_status_hits('echo "landed_by is set"\n', "m.sh") == []


# --- VR-G12: the depth words come from the one constants module ---------------

DEPTH_WORDS = ("thorough", "lightweight", "thorough-with-follow-up",
               "light", "full-plus-backfill")
# `full` is a depth word and a delivery approach. The approach scan
# (`tests/test_stable_ids.py`) holds every literal `full`; this scan holds the
# other five, and the constants are the only place that may spell them.
DEPTH_ALLOW = (
    ("word_map.py", '"light": "lightweight"',
     "the in-module copy of the retired-word table, equal to cli/migrate-map.yml by test"),
    ("word_map.py", '"full-plus-backfill": "thorough-with-follow-up"',
     "the in-module copy of the retired-word table, equal to cli/migrate-map.yml by test"),
)


def depth_word_hits(source: str, name: str) -> list[tuple[str, int, str, str]]:
    lines = source.splitlines()
    return [(name, line, value, lines[line - 1].strip())
            for line, _col, value in _scan_source()(source)
            if value in DEPTH_WORDS]


def scan_depth_words(sources: dict[str, str]) -> list[tuple[str, int, str, str]]:
    hits = []
    for name, text in sorted(sources.items()):
        if name != "stable_ids.py":
            hits += depth_word_hits(text, name)
    return hits


def _package_sources() -> dict[str, str]:
    cli = ROOT / "cli"
    paths = [*sorted((cli / "compass_pkg").glob("*.py")), cli / "compass"]
    return {p.name: p.read_text(encoding="utf-8") for p in paths}


def test_vr_g12_stable_ids_holds_each_depth_word_once():
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import stable_ids
    assert stable_ids.MODE_THOROUGH == "thorough"
    assert stable_ids.MODE_LIGHTWEIGHT == "lightweight"
    assert stable_ids.MODE_THOROUGH_WITH_FOLLOW_UP == "thorough-with-follow-up"
    assert stable_ids.DEPTH_THOROUGH == "thorough"
    assert stable_ids.DEPTH_LIGHTWEIGHT == "lightweight"
    ranks = yaml.safe_load((ROOT / "governance" / "presets" / "default" / "stages.yml")
                           .read_text(encoding="utf-8"))["stages"]
    declared = {mode for body in ranks.values() for mode in body["modes"]}
    assert {stable_ids.MODE_THOROUGH, stable_ids.MODE_LIGHTWEIGHT,
            stable_ids.MODE_THOROUGH_WITH_FOLLOW_UP} <= declared


def test_vr_g12_no_module_spells_a_depth_word():
    open_hits = [h for h in scan_depth_words(_package_sources())
                 if not _allowed(h, DEPTH_ALLOW)]
    assert open_hits == [], (
        "import the depth word from compass_pkg.stable_ids:\n"
        + "\n".join(f"  {n}:{ln} {w!r}: {t}" for n, ln, w, t in open_hits))


def test_vr_g12_each_allowed_line_states_a_reason_and_matches_a_finding():
    hits = scan_depth_words(_package_sources())
    for module, fragment, reason in DEPTH_ALLOW:
        assert len(reason.split()) >= 4, (module, fragment, "give a reason")
        assert any(m == module and fragment in t for m, _l, _w, t in hits), (
            f"{module}: no finding holds {fragment!r}, so the entry is out of date")


def test_vr_g12_a_planted_literal_depth_word_fails_the_scan():
    sources = _package_sources()
    for planted in ('if mode == "thorough":\n    pass\n',
                    'MODES = ("lightweight", "collapsed")\n',
                    'x = ranks.get("thorough-with-follow-up")\n',
                    'if depth in {"light"}:\n    pass\n'):
        hits = scan_depth_words({**sources, "routing.py": sources["routing.py"] + "\n" + planted})
        assert [h for h in hits if not _allowed(h, DEPTH_ALLOW)], planted
    assert scan_depth_words({"stable_ids.py": 'MODE_THOROUGH = "thorough"\n'}) == []


# --- VR-G12: retired stored words in a hook, a run stage, a friction key -------
#
# The scans above read Python in `cli/` only. Three comparisons escaped them:
# a quoted `full` inside a Python block of a shell hook, a run's `stage`
# compared with the retired `build`, and a friction record's retired `phase`
# key. A word here is retired as a stored value, so a literal use is a finding.

HOOK_OLD_WORD_RE = re.compile(
    r"""["'](?:full|light|full-plus-backfill|standard|build|phase)["']""")

RETIRED_NAME_WORDS = ("build", "phase")

RETIRED_NAME_ALLOW = (
    ("analyze.py", '"build": STAGE_IMPLEMENT',
     "the table that reads a run stage written before the rename"),
    ("core.py", '"build": "implement"',
     "the table of retired stage names that the loader reads through"),
    ("core.py", 'for key in ("phase", "stage"):',
     "the loader reads a friction record's retired key beside the new one"),
    ("migrate.py", '"build": "implement",',
     "the archive migration's table of retired stage names"),
    ("obligations.py", 'renames.get(b["phase"], b["phase"])',
     "a blocked-phase record has a phase field that is not a friction key"),
    ("pytest_report.py", '"__pycache__", "build", "dist"',
     "build is a directory name to skip, not a stage"),
    ("routing.py", '{"phase": rr["block_phase"]',
     "a blocked-phase record has a phase field that is not a friction key"),
    ("routing.py", '_display_blocked_phase(b["phase"])',
     "a blocked-phase record has a phase field that is not a friction key"),
    ("routing.py", "_display_blocked_phase(b['phase'])",
     "a blocked-phase record has a phase field that is not a friction key"),
    ("word_map.py", 'FALLBACK["run_stage"] = {"build": "implement"}',
     "the in-module copy of the retired run stage table"),
    ("word_map.py", 'FALLBACK["friction_keys"] = {"phase": "stage"}',
     "the in-module copy of the retired friction key table"),
)


def retired_name_hits(source: str, name: str) -> list[tuple[str, int, str, str]]:
    lines = source.splitlines()
    return [(name, line, value, lines[line - 1].strip())
            for line, _col, value in _scan_source()(source)
            if value in RETIRED_NAME_WORDS]


def scan_retired_names(sources: dict[str, str]) -> list[tuple[str, int, str, str]]:
    hits = []
    for name, text in sorted(sources.items()):
        hits += retired_name_hits(text, name)
    return hits


def hook_old_word_hits(text: str, name: str) -> list[tuple[str, int, str, str]]:
    """`(name, line, word, line text)` for each quoted retired word on a line
    of a shell hook that is not a comment. The hooks read these words through
    `word_map`, so none is expected."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for found in HOOK_OLD_WORD_RE.finditer(line):
            hits.append((name, n, found.group(0), line.strip()))
    return hits


def _hook_sources() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8")
            for p in sorted((ROOT / "hooks").glob("*.sh"))}


def test_vr_g12_no_run_stage_or_friction_key_is_spelt_in_its_retired_form():
    open_hits = [h for h in scan_retired_names(_package_sources())
                 if not _allowed(h, RETIRED_NAME_ALLOW)]
    assert open_hits == [], (
        "read the run stage and the friction key through word_map:\n"
        + "\n".join(f"  {n}:{ln} {w!r}: {t}" for n, ln, w, t in open_hits))


def test_vr_g12_each_retired_name_allowance_states_a_reason_and_matches_a_finding():
    hits = scan_retired_names(_package_sources())
    for module, fragment, reason in RETIRED_NAME_ALLOW:
        assert len(reason.split()) >= 4, (module, fragment, "give a reason")
        assert any(m == module and fragment in t for m, _l, _w, t in hits), (
            f"{module}: no finding holds {fragment!r}, so the entry is out of date")


def test_vr_g12_a_planted_run_stage_or_friction_comparison_fails_the_scan():
    sources = _package_sources()
    for planted in ('open_runs = [r for r in runs if r.get("stage") == "build"]\n',
                    'if run["stage"] == "build":\n    pass\n',
                    'old = [f for f in friction if f.get("phase")]\n',
                    'x = friction_entry["phase"]\n'):
        hits = scan_retired_names({**sources, "flow.py": sources["flow.py"] + "\n" + planted})
        assert [h for h in hits if not _allowed(h, RETIRED_NAME_ALLOW)], planted


def test_vr_g12_no_hook_spells_a_retired_stored_word():
    hits = [h for name, text in _hook_sources().items()
            for h in hook_old_word_hits(text, name)]
    assert hits == [], "read the word through word_map:\n" + "\n".join(map(str, hits))


def test_vr_g12_a_planted_hook_comparison_fails_the_scan():
    sources = _hook_sources()
    for planted in ('    if (task.get("stages") or {}).get("verify") == "full":\n',
                    "    if mode == 'light':\n",
                    '    size = "standard"\n'):
        hits = hook_old_word_hits(sources["stop.sh"] + "\n" + planted, "stop.sh")
        assert hits, planted
    assert hook_old_word_hits("# the hook once said 'full' here\n", "stop.sh") == []


def test_the_shipped_example_manifests_are_written_in_the_current_words():
    """An adopter reads the examples to learn the format, and a saving command
    run inside one would write a `.v5.bak` beside a tracked file."""
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import core, word_map            # core binds the table reader
    assert core
    manifests = sorted((ROOT / "examples").rglob("manifest.yml"))
    assert len(manifests) >= 9, manifests
    old = {str(p.relative_to(ROOT)): word_map.old_words(
               yaml.safe_load(p.read_text(encoding="utf-8")))
           for p in manifests}
    assert {k: v for k, v in old.items() if v} == {}


def test_the_release_notes_list_the_removed_flow_keys_and_the_aliases():
    notes = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    section = notes.split("### What changed at 6.0.0", 1)[1].split("**What the release contains**", 1)[0]
    assert "removes nothing" not in section
    # The retired words sit on a page the prose guards do not scan.
    upgrade = (ROOT / "docs" / "upgrade-6-0-0.md").read_text(encoding="utf-8")
    assert "docs/upgrade-6-0-0.md" in section
    for needed in ("held", "next_up", "landed_this_week", "abandoned", "schema `3.0`",
                   "7.0.0", "together", "ship-commit", "thorough"):
        assert needed in section + upgrade, needed
    for needed in ("`approach summary`", "`issue set-status`", "`issue subtask update`",
                   "`run --stage build`", "`full`", "`standard`", "`phase`", "update every checkout"):
        assert needed.lower() in upgrade.lower(), needed
