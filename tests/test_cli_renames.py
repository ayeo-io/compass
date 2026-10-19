"""CLI verb renames, the alias table and the verb convention (scenario group E).

Every renamed verb follows `compass <noun> <verb>`. The aliases for released
spellings ended at 7.0.0, so `cli/aliases.yml` lists none. The rewrite code
stays, and the tests below prove it on a planted table. A spelling that is not
a verb is an unknown command. Only the two removed released verbs that carry
`removed_in` keep a hint line in the error.

The expected outputs below are what each old spelling printed before the
rename, recorded by running it, so a new spelling is checked against the old
behaviour and not against itself.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import io
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TAG = "v5.6.0"
sys.path.insert(0, str(ROOT / "cli"))

MANIFEST = (
    "schema_version: '3.0'\n"
    "issue: sample\n"
    "created: '2026-10-08'\n"
    "assessment:\n"
    "  risk: contained\n"
    "  familiarity: brownfield-mapped\n"
    "  size: atomic\n"
    "  goal: delivery\n"
    "  urgency: none\n"
    "  role: engineer\n"
    "  labels: []\n"
    "evidence: []\ngates: []\nscenarios: []\nchanged_files: []\n"
    "claims: []\nfollow_ups: []\nreassessments: []\n")


def _project(path: Path) -> Path:
    """A project with one issue, `sample`, set as the current issue."""
    work = path / ".compass" / "work" / "sample"
    work.mkdir(parents=True)
    shutil.copytree(ROOT / "governance", path / "governance")
    shutil.copytree(ROOT / "schemas", path / "schemas")
    (path / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    (work / "manifest.yml").write_text(MANIFEST, encoding="utf-8")
    (path / ".compass" / "current-task").write_text("sample", encoding="utf-8")
    return path


def _run(args, cwd, cli=CLI):
    env = dict(os.environ)
    env.pop("COMPASS_ISSUE", None)
    proc = subprocess.run([sys.executable, str(cli), *args], cwd=str(cwd),
                          capture_output=True, text=True, env=env, timeout=120)
    return proc.returncode, proc.stdout, proc.stderr


def _norm(text, *dirs):
    for d in dirs:
        for form in {str(d), os.path.realpath(d)}:
            text = text.replace(form, "<P>")
    return text


def _table():
    from compass_pkg import aliases
    return aliases.load_table()


def _notices(stderr):
    return [l for l in stderr.splitlines() if "works until 7.0.0" in l]


# The 7 alias rows that 7.0.0 removed, kept here as a planted table. The rewrite
# code stays, so these rows prove it. The real table lists none of them.
PLANTED_ALIASES = [
    {"old": ["approach", "summary"], "new": ["approach", "show"],
     "kind": "verb", "released_in": "v5.6.0"},
    {"old": ["issue", "set-status"], "new": ["issue", "status", "set"],
     "kind": "verb", "released_in": "v5.6.0", "value_flags": ["--issue", "--reason"],
     "values": {"active": ["issue", "status", "remove"],
                "queued": ["issue", "status", "set", "backlog"],
                "parked": ["issue", "status", "set", "backlog"],
                "landed": ["issue", "status", "set", "done", "--close-reason", "completed"],
                "abandoned": ["issue", "status", "set", "done", "--close-reason",
                              "not-planned"]}},
    {"old": ["policy", "review-rules"], "new": ["review-rule", "list"],
     "kind": "verb", "released_in": "v5.6.0"},
    {"old": ["issue", "artifact"], "new": ["issue", "artifact", "set"],
     "kind": "verb", "released_in": "v5.6.0"},
    {"old": ["migrate"], "new": ["issue", "migrate"], "kind": "verb",
     "released_in": "v5.6.0"},
    {"old": ["issue", "subtask", "update"], "new": ["issue", "subtask", "set"],
     "kind": "verb", "released_in": "v5.6.0"},
    {"old": ["run", "--stage", "build"], "new": ["run", "--stage", "implement"],
     "kind": "value", "released_in": "v5.6.0"},
]
PLANTED_TABLE = {"aliases": PLANTED_ALIASES, "hints": []}

# For each planted row: the old spelling with sample arguments, and the new
# spelling that the rewrite must give.
RELEASED = [
    (["approach", "summary"], ["approach", "show"]),
    (["issue", "set-status", "parked", "--reason", "later"],
     ["issue", "status", "set", "backlog", "--reason", "later"]),
    (["policy", "review-rules", "--changed-files", "cli/compass"],
     ["review-rule", "list", "--changed-files", "cli/compass"]),
    (["issue", "artifact", "design", "--status", "omitted", "--reason", "x"],
     ["issue", "artifact", "set", "design", "--status", "omitted", "--reason", "x"]),
    (["migrate"], ["issue", "migrate"]),
    (["issue", "subtask", "update", "s1", "--status", "done"],
     ["issue", "subtask", "set", "s1", "--status", "done"]),
    (["run", "multi", "--stage", "build"], ["run", "multi", "--stage", "implement"]),
]


def _ids(pairs):
    return [" ".join(old[:3]) for old, _ in pairs]


# --- VR-E1: each new spelling does what the old one did ----------------------

# (new spelling, expected exit code, text the old spelling printed)
NEW_SPELLINGS = [
    (["approach", "show"], 0, "Approach:  (risk contained"),
    (["approach", "render"], 0, "<!doctype html>"),
    (["policy", "show"], 0, "capabilities.artifact-freshness"),
    (["review-rule", "list", "--changed-files", "cli/compass"], 0, "RR-001"),
    (["issue", "template", "show", "requirements-review"], 0,
     "TEMPLATE: requirements-review.md"),
    (["issue", "migrate"], 0, "nothing to do"),
    (["issue", "migrate", "--config"], 0, "committed generation 1"),
    (["issue", "status", "set", "backlog"], 0, "sample -> backlog"),
]


@pytest.mark.parametrize("args,code,text", NEW_SPELLINGS,
                         ids=[" ".join(a[:3]) for a, _, _ in NEW_SPELLINGS])
def test_vr_e1_each_new_spelling_gives_the_old_output(tmp_path, args, code, text):
    project = _project(tmp_path / "p")
    rc, out, err = _run(args, project)
    assert rc == code, (rc, out, err)
    assert text in out, out
    assert not _notices(err), err


def test_vr_e1_scenario_tests_set_replaces_the_declared_tests(tmp_path):
    project = _project(tmp_path / "p")
    manifest = project / ".compass" / "work" / "sample" / "manifest.yml"
    data = yaml.safe_load(manifest.read_text())
    data["scenarios"] = [{"id": "SCN-1", "title": "first", "intent": "INT-1",
                          "tests": ["tests/test_old.py::test_old_name"]}]
    manifest.write_text(yaml.safe_dump(data), encoding="utf-8")
    (project / "tests").mkdir()
    (project / "tests" / "test_new.py").write_text("def test_new_name():\n    pass\n")
    (project / "tests" / "test_old.py").write_text("def test_old_name():\n    pass\n")
    rc, out, err = _run(["scenario", "tests", "set", "SCN-1", "--test",
                         "tests/test_new.py::test_new_name"], project)
    assert rc == 0, (out, err)
    saved = yaml.safe_load(manifest.read_text())
    assert saved["scenarios"][0]["tests"] == ["tests/test_new.py::test_new_name"]


# Text a person or an agent reads must teach the new spelling. A message or a
# page that names `compass issue set-status` sends the reader to a spelling
# that works only until 7.0.0, or to one that no longer works.
RETIRED_SPELLINGS = [
    r"compass approach summary", r"compass approach diagram",
    r"compass policy effective", r"compass policy review-rules",
    r"compass issue set-status", r"compass issue refresh-spec",
    r"compass issue migrate-config", r"compass migrate(?![\w-])",
    r"compass issue subtask update",
    r"compass issue dashboard",
    r"compass issue artifact(?![\w-]| set)",
    r"compass issue template(?! show)",
    r"compass scenario tests(?! set)",
    r"compass policy test", r"compass policy init-preset",
    r"--stage build", r"--stage=build", r"--phase(?![\w-])", r"--note-phase",
]

# Paths that record history or are derived from it, so they name old spellings.
NOT_SCANNED = (
    "tests/", "docs/compass/", "governance/decisions/", "architecture/decisions/",
    "CHANGELOG.md", "docs/system-spec", "cli/aliases.yml", "cli/compass_pkg/aliases.py",
    "docs/upgrade", "evals/",
)

# Markers written into pages on disk. A page made before the rename holds the
# old text, and the check that a page is generated reads it, so the text must
# not change with the verb.
KEPT_MARKERS = (
    ("cli/compass_pkg/migrate.py", "GENERATED by `compass issue dashboard`"),
    # The 5.0.0 upgrade notes name the command a reader of that release ran,
    # beside its new name; tests/test_upgrade_notes_5_0_0.py needs the old one.
    ("docs/releasing.md", "run compass migrate"),
    # The release guide lists the removed `run` stage spelling beside its
    # replacement, in one table row. Only that row is exempt.
    ("docs/releasing.md", "`run --stage build` | `run --stage implement`"),
)


def _live_text_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                         text=True, check=True).stdout
    for rel in sorted(p for p in out.split("\0") if p):
        if rel.startswith(NOT_SCANNED):
            continue
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".png", ".xz", ".gz", ".tar", ".svg"):
            continue
        try:
            yield rel, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def retired_spelling_problems(files, kept=KEPT_MARKERS):
    """The lines of `files` (pairs of path and text) that teach a retired spelling,
    except a line that holds the marker kept for its path."""
    import re
    found = []
    # A line break, or a comment mark after one, can sit between the words of
    # a command, so the words are joined by any run of those.
    joined = [re.sub(r" ", r"(?:\\s|#|>|\\*)+", p) for p in RETIRED_SPELLINGS]
    for rel, text in files:
        lines = text.splitlines()
        for pattern in joined:
            for match in re.finditer(pattern, text):
                number = text.count("\n", 0, match.start()) + 1
                line = lines[number - 1]
                if any(p == rel and marker in line for p, marker in kept):
                    continue
                found.append(f"{rel}:{number}: {line.strip()[:110]}")
    return found


def test_vr_e1_no_live_text_teaches_a_retired_spelling():
    found = retired_spelling_problems(_live_text_files())
    assert not found, f"{len(found)} lines teach a retired spelling:\n" + "\n".join(found[:80])


def test_vr_e1_the_releasing_table_row_is_exempt_and_no_other_line_is():
    row = "| `run --stage build` | `run --stage implement` | the stage was renamed |"
    planted = [("docs/releasing.md", f"# Releasing\n\n{row}\n")]
    assert retired_spelling_problems(planted) == []
    # A second line in the same file that holds the spelling is still reported.
    second = [("docs/releasing.md",
               f"# Releasing\n\n{row}\nRun `compass run x --stage build` to start.\n")]
    problems = retired_spelling_problems(second)
    assert len(problems) == 1 and problems[0].startswith("docs/releasing.md:4:"), problems
    # The same row in another file is not exempt.
    elsewhere = [("docs/other.md", f"{row}\n")]
    assert retired_spelling_problems(elsewhere)


def test_vr_e1_the_retired_spelling_scan_reports_a_planted_line():
    import re
    planted = "run `compass issue artifact design --status draft`"
    assert any(re.search(p, planted) for p in RETIRED_SPELLINGS)
    fine = "run `compass issue artifact set design` or `compass issue artifact-path design`"
    assert not any(re.search(p, fine) for p in RETIRED_SPELLINGS)


# --- VR-E2: each released alias does the new verb's work ---------------------

@pytest.mark.parametrize("old,new", RELEASED, ids=_ids(RELEASED))
def test_vr_e2_a_planted_alias_row_rewrites_to_the_new_verb(old, new):
    """The rewrite code stays after 7.0.0, so a planted row proves it."""
    from compass_pkg import aliases
    argv, notice = aliases.rewrite(old, PLANTED_TABLE)
    assert argv == new, (argv, new)
    assert notice and notice.count("\n") == 0, notice
    assert "compass: '" in notice and "' is now '" in notice, notice
    # The new spelling is left as it is, and prints no notice.
    assert aliases.rewrite(new, PLANTED_TABLE) == (new, None)


def test_vr_e2_the_real_table_rewrites_no_removed_spelling():
    from compass_pkg import aliases
    for old, _ in RELEASED:
        assert aliases.rewrite(old) == (old, None), old


# --- VR-E3: JSON output stays clean ------------------------------------------

def test_vr_e3_a_removed_spelling_with_json_prints_nothing_on_standard_output(tmp_path):
    project = _project(tmp_path / "p")
    rc, out, err = _run(["approach", "summary", "--json"], project)
    assert rc == 2 and out == "", (rc, out, err)
    assert not _notices(err), err


# --- VR-E4: help lists the new verbs and no alias ----------------------------

def _choices(args, cwd):
    rc, out, err = _run(args + ["--help"], cwd)
    assert rc == 0, err
    import re
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out)
    assert m, out
    return set(m.group(1).split(","))


def test_vr_e4_group_help_lists_new_verbs_and_no_alias(tmp_path):
    p = _project(tmp_path / "p")
    top = _choices([], p)
    assert {"review-rule", "spec"} <= top
    assert "migrate" not in top
    assert {"show", "render", "evaluate"} == _choices(["approach"], p)
    issue = _choices(["issue"], p)
    assert {"status", "migrate", "render", "artifact", "template"} <= issue
    assert "dashboard" not in issue
    assert not issue & {"set-status", "migrate-config", "refresh-spec"}
    assert {"set", "add"} <= _choices(["issue", "subtask"], p)
    assert "update" not in _choices(["issue", "subtask"], p)
    assert "show" in _choices(["policy"], p)
    assert not _choices(["policy"], p) & {"effective", "review-rules"}
    assert _choices(["review-rule"], p) == {"list"}
    assert _choices(["issue", "artifact"], p) == {"set"}


def test_vr_e4_no_alias_old_spelling_is_a_verb_in_any_help(tmp_path):
    p = _project(tmp_path / "p")
    for row in _table()["aliases"]:
        if row["kind"] != "verb":
            continue            # a value of a flag is not a verb in any help
        old = row["old"]
        parent = old[:-1]
        if not parent:
            continue
        assert old[-1] not in _choices(parent, p) or old[-1] in row["new"], row


# --- VR-E5: aliases end at 7.0.0 ---------------------------------------------

def test_vr_e5_a_test_fails_at_7_0_0_while_any_alias_remains():
    """The check is proved on a planted table, because the real one is empty."""
    from compass_pkg import aliases
    table = PLANTED_TABLE
    assert aliases.removal_problems("5.6.0", table) == []
    planted = aliases.removal_problems("7.0.0", table)
    assert len(planted) == len(PLANTED_ALIASES), "each planted alias row must be reported"
    assert aliases.removal_problems("7.0.0", {"aliases": [], "hints": []}) == []
    assert aliases.removal_problems("7.1.2", table)
    assert aliases.removal_problems("6.9.9", table) == []
    # A planted hint row without `removed_in` is reported, and one with both is not.
    hint = {"old": ["frob", "nicate"], "new": ["frob", "set"]}
    assert len(aliases.removal_problems("7.0.0", {"aliases": [], "hints": [hint]})) == 1
    kept = dict(hint, released_in="v5.6.0", removed_in="7.0.0")
    assert aliases.removal_problems("7.0.0", {"aliases": [], "hints": [kept]}) == []


def test_vr_e5_the_real_table_is_empty_once_the_package_reaches_7_0_0():
    from compass_pkg import aliases, core
    assert aliases.removal_problems(core.COMPASS_VERSION, aliases.load_table()) == [], (
        "the package version is 7.0.0 or later and the alias table still has rows")


# --- VR-E6: an unreleased spelling is refused, with a hint -------------------

# The 9 hint rows for spellings no release held ended at 7.0.0, and
# tests/test_removed_spellings_fail_with_the_parser_error.py proves each prints
# no hint. The hint code stays for the two removed released verbs, so a planted
# table proves it here.
PLANTED_HINTS = {"aliases": [], "hints": [
    {"old": ["policy", "effective"], "new": ["policy", "show"]},
    {"old": ["issue", "friction", "--phase"], "new": ["issue", "friction", "--stage"]},
]}


def test_vr_e6_a_planted_hint_row_names_the_new_spelling_and_runs_nothing():
    from compass_pkg import aliases
    assert aliases.hint_for(["policy", "effective"], PLANTED_HINTS) == (
        "'policy effective' is now 'policy show'.")
    assert aliases.hint_for(["policy", "show"], PLANTED_HINTS) is None
    assert aliases.hint_for(
        ["issue", "friction", "--category", "tooling", "--phase=assess"], PLANTED_HINTS) == (
        "'issue friction --phase' is now 'issue friction --stage'.")
    assert aliases.hint_for(["policy", "effective"], {"aliases": [], "hints": []}) is None
    assert aliases.rewrite(["policy", "effective"], PLANTED_HINTS) == (
        ["policy", "effective"], None)


def hint_problems(rows, project):
    """What is wrong with the hint rows against the releases. A row for a verb a
    release held and 7.0.0 removed (ADR-051) is checked against the tag its own
    `released_in` names, which must hold the spelling. Any other row is a spelling
    no release holds, checked against TAG. A row whose tag is not in this clone is
    skipped."""
    problems = []
    for row in rows:
        name = " ".join(row["old"])
        tag = row.get("released_in") if row.get("removed_in") else TAG
        cli = _tag_cli(tag)
        if cli is None:
            continue
        rc, out, err = _run(row["old"] + ["--help"], project, cli=cli)
        if row.get("removed_in") and rc != 0:
            problems.append(f"{tag} does not hold {name}, which the row says it does")
        elif not row.get("removed_in") and rc == 0:
            problems.append(f"{tag} holds {name}, so it needs an alias, not a hint")
    return problems


def test_vr_e6_no_hint_spelling_is_held_by_a_release(tmp_path):
    """A hint exists because no release holds the old spelling; a spelling the
    tag holds would need an alias, not a hint."""
    if _tag_cli() is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    project = _project(tmp_path / "p")
    assert hint_problems(_table()["hints"], project) == []
    # A removed verb whose named release never held it is reported.
    planted = [{"old": ["issue", "labels", "sync"], "new": ["issue", "github", "sync"],
                "released_in": TAG, "removed_in": "7.0.0"}]
    assert hint_problems(planted, project) == [
        f"{TAG} does not hold issue labels sync, which the row says it does"]


# --- VR-E10: the verb convention ---------------------------------------------

FIXED = {"show", "list", "add", "remove", "set", "render", "lint", "test", "diff",
         "update", "migrate", "sync", "init"}
TOP = {"init", "check", "ci", "run", "next", "retro", "flow", "analyze"}

EXCEPTIONS = {
    "tdd-red": "named for the red step of red-green-refactor, which the pre-tool hook and every command file call by this name",
    "tdd-green": "the green step, paired with tdd-red",
    "ship-commit": "the commit step inside shipping; named in the contract and the ship command",
    "rework-scan": "a report verb named for what it scans; renaming it needs an alias no release owes yet",
    "terminology": "prints the vocabulary; a noun that is its own command",
    "readiness": "measures the repository and writes the readiness record; a noun that is its own command, named by the spec that added it",
    "release notes": "prints the release lines since a ref; the spelling the requirement that added it names",
    "approach evaluate": "applies the routing policy; the determinism boundary is named by this verb in the contract",
    "bdd extract": "turns acceptance criteria into a feature file; a verb of the bdd group",
    "bdd verify": "runs the BDD suite and records the result; a verb of the bdd group",
    "intent ingest": "reads an existing brief; a verb of the intent group",
    "issue diagnose": "explains one run from its records; a verb of the issue group",
    "issue use": "moves the current-issue pointer; the pointer verb every session reads",
    "issue friction": "records one process-friction entry; a noun the retro report groups by",
    "issue configure": "proposes a change to one issue's configuration",
    "issue raised-by": "records the issue this one was found in; the maintainer named it an exception",
    "issue receipt": "renders a landed issue's receipt; the maintainer named it an exception",
    "issue artifact-path": "prints where a document is; two hooks read its exit code, so its name stays",
    "issue subtask next": "prints the next subtask to dispatch; a verb of the subtask group",
    "issue subtask replan": "re-plans the subtasks; a verb of the subtask group",
    "issue subtask package": "packages a subtask's brief; a verb of the subtask group",
    "acceptance start": "opens an acceptance record for a change with no natural red",
    "acceptance record": "closes an acceptance record",
    "adr new": "creates the next numbered decision record",
    "follow-up resolve": "marks an owed follow-up settled",
    "gate pass": "marks a gate passed with typed evidence",
    "scenario descope": "records a failure mode no scenario covers",
    "evidence approve": "records a person's approval; the maintainer named it an exception",
    "evidence review": "records a judgement against a judged check; the maintainer named it an exception",
    "evidence request": "asks a person for an approval; named in ADR-068 and approved by compass:architect under jed72's overnight delegation",
    "quick-fix start": "assesses and records a quick fix in one call",
    "quick-fix finish": "traces, checks, gates and lands a quick fix in one call",
    "decision record": "writes a decision entry",
    "decision check": "compares decision entries with a base ref",
    "lesson propose": "holds a lesson for acceptance",
    "lesson accept": "turns a pending proposal into a lesson",
    "lesson decline": "drops a pending proposal",
    "record restore": "restores a record from its sync",
    "board refresh": "rewrites the board page in place and never opens a browser; the maintainer chose two commands, so refresh is not a flag of render",
}


def _load_root():
    import compass_pkg  # noqa: F401  - resolves the bundled yaml
    spec = importlib.util.spec_from_loader(
        "compass_entry_renames", SourceFileLoader("compass_entry_renames", str(CLI)))
    module = importlib.util.module_from_spec(spec)
    old = sys.argv
    sys.argv = ["compass"]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.argv = old
    return module.build_parser()


def _subparsers_action(parser):
    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            return a
    return None


def _leaf_paths(parser, path=()):
    action = _subparsers_action(parser)
    if action is None:
        yield path
        return
    for name, child in action.choices.items():
        yield from _leaf_paths(child, path + (name,))


def convention_problems(root, exceptions=EXCEPTIONS):
    problems, seen = [], set()
    for path in _leaf_paths(root):
        if not path or path[0].startswith("_"):
            continue
        key = " ".join(path)
        follows = path[0] in TOP if len(path) == 1 else path[-1] in FIXED
        if key in exceptions:
            seen.add(key)
            if not exceptions[key].strip():
                problems.append(f"{key}: the exception has no reason")
            if follows:
                problems.append(f"{key}: listed as an exception but it follows the convention")
        elif not follows:
            problems.append(f"{key}: not a fixed verb, not an allowed top-level verb, and not a named exception")
    for key in sorted(set(exceptions) - seen):
        problems.append(f"{key}: a named exception that the parser does not register")
    return problems


def test_vr_e10_every_registered_verb_follows_the_convention_or_is_a_named_exception():
    problems = convention_problems(_load_root())
    assert not problems, "\n".join(problems)


def test_vr_e10_a_planted_verb_in_neither_list_fails():
    root = _load_root()
    issue = _subparsers_action(root).choices["issue"]
    _subparsers_action(issue).add_parser("frobnicate")
    problems = convention_problems(root)
    assert any(p.startswith("issue frobnicate:") for p in problems), problems


# --- VR-E11: issue artifact-path is untouched --------------------------------

def test_vr_e11_artifact_path_keeps_its_name_and_exit_codes(tmp_path):
    from compass_pkg import aliases
    argv = ["issue", "artifact-path", "design"]
    assert aliases.rewrite(argv) == (argv, None)
    project = _project(tmp_path / "p")
    (project / ".compass" / "work" / "sample" / "design.md").write_text("# design\n")
    rc, out, err = _run(["issue", "artifact-path", "design"], project)
    assert rc == 0 and out.strip().endswith("design.md"), (rc, out, err)
    assert not _notices(err)
    rc, out, err = _run(["issue", "artifact-path", "requirements-review"], project)
    assert rc != 0 and out == "", (rc, out, err)
    assert not _notices(err)


# --- VR-E12: spec sync says what it does -------------------------------------

def test_vr_e12_spec_sync_help_says_merge_derive_and_commit(tmp_path):
    project = _project(tmp_path / "p")
    rc, out, err = _run(["spec", "sync", "--help"], project)
    assert rc == 0, err
    text = " ".join(out.split()).lower()
    for phrase in ("merges the base branch", "re-derives the living spec", "commits"):
        assert phrase in text, (phrase, text)


# --- VR-E13: the table agrees with the release tag ---------------------------

_TAG_CLI = {}


def _tag_cli(tag=TAG):
    """The CLI of a release tag, extracted once per tag; None when the tag is absent."""
    if tag in _TAG_CLI:
        return _TAG_CLI[tag]
    probe = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{tag}^{{commit}}"],
                           cwd=str(ROOT), capture_output=True, text=True)
    if probe.returncode != 0:
        _TAG_CLI[tag] = None
        return None
    import tempfile
    dest = Path(tempfile.mkdtemp(prefix="compass-tag-"))
    data = subprocess.run(["git", "archive", tag, "cli"], cwd=str(ROOT),
                          capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest)
    _TAG_CLI[tag] = dest / "cli" / "compass"
    return _TAG_CLI[tag]


def release_problems(rows, cli, cwd):
    problems = []
    for row in rows:
        name = " ".join(row.get("old", []))
        if not row.get("released_in"):
            problems.append(f"{name}: no released_in")
            continue
        if row["released_in"] != TAG:
            problems.append(f"{name}: names {row['released_in']}, which this test cannot read")
            continue
        if row.get("kind") == "value":
            # The command and flag are `old` up to its last token, the value.
            # The tag holds the spelling when its help lists the value.
            rc, out, err = _run(row["old"][:-2] + ["--help"], cwd, cli=cli)
            if rc != 0 or row["old"][-1] not in out:
                problems.append(f"{name}: {TAG} does not hold this spelling")
            continue
        rc, out, err = _run(row["old"] + ["--help"], cwd, cli=cli)
        if rc != 0:
            problems.append(f"{name}: {TAG} does not hold this spelling")
    return problems


def test_vr_e13_each_row_names_a_release_that_holds_the_old_spelling(tmp_path):
    cli = _tag_cli()
    if cli is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    # The real table lists no alias row, so the planted rows prove the check.
    assert _table()["aliases"] == []
    rows = [r for r in PLANTED_ALIASES if r["kind"] == "verb"]
    assert rows
    assert release_problems(rows, cli, _project(tmp_path / "p")) == []


def test_vr_e13_a_planted_row_for_an_unreleased_spelling_fails(tmp_path):
    cli = _tag_cli()
    if cli is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    p = _project(tmp_path / "p")
    planted = [{"old": ["policy", "effective"], "new": ["policy", "show"],
                "kind": "verb", "released_in": TAG}]
    assert release_problems(planted, cli, p)
    assert release_problems([{"old": ["approach", "summary"], "new": ["approach", "show"],
                              "kind": "verb"}], cli, p) == ["approach summary: no released_in"]


def table_shape_problems(table):
    """What is wrong with the shape of a table: an alias row without a release or
    a kind, or a hint row for a removed verb without both `released_in` and
    `removed_in`."""
    problems = []
    for row in table["aliases"]:
        if not row.get("released_in", "").startswith("v"):
            problems.append(f"{' '.join(row['old'])}: alias row has no released_in")
        if row.get("kind") not in ("verb", "value"):
            problems.append(f"{' '.join(row['old'])}: alias row has no kind")
    for row in table["hints"]:
        if row.get("removed_in") and not row.get("released_in", "").startswith("v"):
            problems.append(f"{' '.join(row['old'])}: hint row has removed_in, no released_in")
        if row.get("released_in") and not row.get("removed_in"):
            problems.append(f"{' '.join(row['old'])}: hint row has released_in, no removed_in")
    return problems


def test_vr_e13_the_table_file_has_a_release_on_every_row():
    table = _table()
    assert table_shape_problems(table) == []
    # The two hint rows that remain each name the release that held the verb.
    assert {tuple(r["old"]): r["released_in"] for r in table["hints"]} == {
        ("issue", "dashboard"): "v5.6.0", ("issue", "labels", "sync"): "v6.0.0"}


def test_vr_e13_a_planted_table_with_a_row_missing_its_release_is_reported():
    planted = {
        "aliases": [{"old": ["a", "b"], "new": ["a", "c"], "kind": "verb"},
                    {"old": ["x"], "new": ["y"], "released_in": "v5.6.0"}],
        "hints": [{"old": ["h"], "new": ["i"], "removed_in": "7.0.0"},
                  {"old": ["j"], "new": ["k"], "released_in": "v5.6.0"}],
    }
    assert table_shape_problems(planted) == [
        "a b: alias row has no released_in",
        "x: alias row has no kind",
        "h: hint row has removed_in, no released_in",
        "j: hint row has released_in, no removed_in"]


def test_vr_e13_the_routing_module_has_no_stale_summary_comment():
    text = (Path(__file__).resolve().parent.parent / "cli" / "compass_pkg" / "routing.py"
            ).read_text(encoding="utf-8")
    assert "# --- command: approach summary" not in text
    assert "# --- command: approach show" in text


# --- VR-E14: one rewrite step; the bare artifact spelling --------------------

def test_vr_e14_a_planted_bare_artifact_row_is_rewritten_with_one_notice():
    from compass_pkg import aliases
    table = PLANTED_TABLE
    argv, notice = aliases.rewrite(["issue", "artifact", "design", "--status", "omitted"], table)
    assert argv == ["issue", "artifact", "set", "design", "--status", "omitted"]
    assert notice and notice.count("\n") == 0 and "'issue artifact' is now 'issue artifact set'" in notice
    assert aliases.rewrite(["issue", "artifact", "set", "design"], table) == (
        ["issue", "artifact", "set", "design"], None)
    assert aliases.rewrite(["issue", "artifact", "--help"], table)[1] is None
    assert aliases.rewrite(["issue", "artifact-path", "design"], table)[1] is None


def test_vr_e14_the_rewrite_reads_arguments_only_from_the_command_line():
    from compass_pkg import aliases
    assert aliases.rewrite(["check"]) == (["check"], None)
    assert aliases.rewrite([]) == ([], None)
    argv, notice = aliases.rewrite(["migrate", "--apply"], PLANTED_TABLE)
    assert argv == ["issue", "migrate", "--apply"] and notice
    # A removed verb is no alias: the line is left as it is and the parser refuses it.
    assert aliases.rewrite(["issue", "dashboard", "render"]) == (["issue", "dashboard", "render"], None)


# --- VR-E7, VR-E8, VR-E14 (the run half): the run stage implement -------------
# The headless-runner tests own the stub `claude` and the project it runs in.

sys.path.insert(0, str(ROOT / "tests"))
from test_headless_runner import project as headless_project  # noqa: E402,F401
from test_headless_runner import (_calls as _stub_calls,  # noqa: E402
                                  _last_run as _stub_last_run,
                                  _run as _stub_run)


def test_vr_e7_run_stage_implement_runs_the_implement_stage(headless_project):
    result = _stub_run(headless_project, "--max-cycles", "1", plan=("touch",),
                       stage="implement")
    assert result.returncode == 4, result.stdout + result.stderr   # one cycle, no stage done
    assert not _notices(result.stderr), result.stderr
    assert "usage:" not in result.stderr
    message = _stub_calls(headless_project)[0]
    assert "/compass:implement" in message[message.index("-p") + 1]
    assert _stub_last_run(headless_project)["stage"] == "implement"
    assert "build" not in result.stdout
    # The run is a writer too: the manifest it saved holds no old word.
    from compass_pkg import word_map
    saved = yaml.safe_load((headless_project / ".compass" / "work" / "multi"
                            / "manifest.yml").read_text(encoding="utf-8"))
    assert word_map.old_words(saved) == [], word_map.old_words(saved)


def test_vr_e7_the_stage_help_lists_implement_and_not_build(tmp_path):
    rc, out, err = _run(["run", "--help"], _project(tmp_path / "p"))
    assert rc == 0, err
    words = out.lower().replace("|", " ").replace(",", " ").split()
    assert "implement" in words and "verify" in words, out
    assert "build" not in words, out


def test_vr_e8_run_stage_build_is_refused_and_runs_no_stage(headless_project):
    result = _stub_run(headless_project, "--max-cycles", "1", plan=("touch",),
                       stage="build")
    assert result.returncode == 2, result.stdout + result.stderr
    assert not _notices(result.stderr), result.stderr
    assert "is now '" not in result.stderr, result.stderr
    assert _stub_calls(headless_project) == []


def test_vr_e8_the_equals_form_is_refused_too(headless_project):
    import subprocess as sp
    done = sp.run([sys.executable, str(CLI), "run", "multi", "--stage=build"],
                  cwd=str(headless_project), capture_output=True, text=True)
    assert done.returncode == 2, done.stderr
    assert not _notices(done.stderr), done.stderr
    assert "cannot run unattended" in done.stderr, done.stderr


def test_vr_e14_a_planted_value_row_is_rewritten_in_both_forms():
    from compass_pkg import aliases
    table = PLANTED_TABLE
    argv, notice = aliases.rewrite(["run", "multi", "--stage", "build", "--stop-file", "S"], table)
    assert argv == ["run", "multi", "--stage", "implement", "--stop-file", "S"]
    assert notice and "\n" not in notice
    assert "'run --stage build' is now 'run --stage implement'" in notice
    assert aliases.rewrite(["run", "multi", "--stage=build"], table)[0] == [
        "run", "multi", "--stage=implement"]
    # Nothing else is touched: another stage, the new word, another command,
    # and a slug or a path that spells the old word.
    for untouched in (["run", "multi", "--stage", "verify"],
                      ["run", "multi", "--stage", "implement"],
                      ["run", "build", "--stage", "verify"],
                      ["flow", "--stage", "build"],
                      ["run", "multi", "--stop-file", "build"]):
        assert aliases.rewrite(untouched, PLANTED_TABLE) == (untouched, None), untouched
    assert aliases.rewrite(["run", "--help"], PLANTED_TABLE)[1] is None


def test_vr_e13_a_planted_value_row_for_an_unreleased_value_fails(tmp_path):
    cli = _tag_cli()
    if cli is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    p = _project(tmp_path / "p")
    held = {"old": ["run", "--stage", "build"], "new": ["run", "--stage", "implement"],
            "kind": "value", "released_in": TAG}
    assert release_problems([held], cli, p) == []
    planted = dict(held, old=["run", "--stage", "implement"], new=["run", "--stage", "x"])
    assert release_problems([planted], cli, p), "a value the tag does not list must fail"


# --- VR-E9: issue friction takes --stage; --phase is an unknown option ---------

def test_vr_e9_issue_friction_with_stage_records_an_entry_keyed_stage(tmp_path):
    project = _project(tmp_path / "p")
    task = project / ".compass" / "work" / "sample"
    (task / "evidence").mkdir()
    (task / "evidence" / "red.log").write_text("1 failed\n", encoding="utf-8")
    rc, out, err = _run(["issue", "friction", "--category", "tooling", "--stage",
                         "implement", "--observed", "evidence/red.log",
                         "--fix", "Run the suite once"], project)
    assert rc == 0, (out, err)
    assert "(tooling, implement)" in out and not _notices(err), (out, err)
    [entry] = yaml.safe_load((task / "manifest.yml").read_text())["friction"]
    assert entry["stage"] == "implement" and "phase" not in entry, entry


def test_vr_e9_the_stage_flag_lists_the_stage_ids_and_the_help_has_no_phase_flag(tmp_path):
    rc, out, err = _run(["issue", "friction", "--help"], _project(tmp_path / "p"))
    assert rc == 0, err
    assert "--stage" in out and "--phase" not in out, out


def test_vr_e9_the_phase_flag_records_nothing(tmp_path):
    project = _project(tmp_path / "p")
    task = project / ".compass" / "work" / "sample"
    (task / "evidence").mkdir()
    (task / "evidence" / "red.log").write_text("1 failed\n", encoding="utf-8")
    before = (task / "manifest.yml").read_text()
    rc, out, err = _run(["issue", "friction", "--category", "tooling", "--phase",
                         "implement", "--observed", "evidence/red.log",
                         "--fix", "Run the suite once"], project)
    assert rc == 2 and out == "", (rc, out, err)
    assert "is now '" not in err, err
    assert "works until 7.0.0" not in err
    assert (task / "manifest.yml").read_text() == before
