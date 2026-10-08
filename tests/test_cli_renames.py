"""CLI verb renames, the alias table and the verb convention (scenario group E).

Every renamed verb follows `compass <noun> <verb>`. A spelling that a release
tag holds keeps an alias until 7.0.0, listed in `cli/aliases.yml`. A spelling
no release holds is an unknown command whose error names the new spelling.

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


# Each released alias: the old spelling with sample arguments, and the
# new spelling that must do the same work. Written out by hand so the table
# is checked against an independent list.
RELEASED = [
    (["approach", "summary"], ["approach", "show"]),
    (["issue", "set-status", "parked", "--reason", "later"],
     ["issue", "status", "set", "backlog", "--reason", "later"]),
    (["policy", "review-rules", "--changed-files", "cli/compass"],
     ["review-rule", "list", "--changed-files", "cli/compass"]),
    (["issue", "dashboard", "--check"], ["issue", "dashboard", "render", "--check"]),
    (["issue", "artifact", "design", "--status", "omitted", "--reason", "x"],
     ["issue", "artifact", "set", "design", "--status", "omitted", "--reason", "x"]),
    (["migrate"], ["issue", "migrate"]),
    (["issue", "subtask", "update", "s1", "--status", "done"],
     ["issue", "subtask", "set", "s1", "--status", "done"]),
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
    (["issue", "dashboard", "render", "--check"], 1, "STALE - no README.md"),
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
    r"compass issue dashboard(?! render)",
    r"compass issue artifact(?![\w-]| set)",
    r"compass issue template(?! show)",
    r"compass scenario tests(?! set)",
    r"compass policy test", r"compass policy init-preset",
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
    ("cli/compass_pkg/dashboard.py", "GENERATED by `compass issue dashboard`"),
    ("cli/compass_pkg/dashboard.py", "compass issue dashboard format: traceability"),
    # The 5.0.0 upgrade notes name the command a reader of that release ran,
    # beside its new name; tests/test_upgrade_notes_5_0_0.py needs the old one.
    ("docs/releasing.md", "run compass migrate"),
    # The review workflow runs the base branch's CLI, which holds only the old
    # spelling until this change merges. The alias keeps it working on both.
    (".github/workflows/claude-review.yml", "compass policy review-rules"),
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


def test_vr_e1_no_live_text_teaches_a_retired_spelling():
    import re
    found = []
    # A line break, or a comment mark after one, can sit between the words of
    # a command, so the words are joined by any run of those.
    joined = [re.sub(r" ", r"(?:\\s|#|>|\\*)+", p) for p in RETIRED_SPELLINGS]
    for rel, text in _live_text_files():
        lines = text.splitlines()
        for pattern in joined:
            for match in re.finditer(pattern, text):
                number = text.count("\n", 0, match.start()) + 1
                line = lines[number - 1]
                if any(p == rel and marker in line for p, marker in KEPT_MARKERS):
                    continue
                found.append(f"{rel}:{number}: {line.strip()[:110]}")
    assert not found, f"{len(found)} lines teach a retired spelling:\n" + "\n".join(found[:80])


def test_vr_e1_the_retired_spelling_scan_reports_a_planted_line():
    import re
    planted = "run `compass issue artifact design --status draft`"
    assert any(re.search(p, planted) for p in RETIRED_SPELLINGS)
    fine = "run `compass issue artifact set design` or `compass issue artifact-path design`"
    assert not any(re.search(p, fine) for p in RETIRED_SPELLINGS)


# --- VR-E2: each released alias does the new verb's work ---------------------

def test_vr_e2_the_table_lists_exactly_the_released_spellings(tmp_path):
    rows = _table()["aliases"]
    listed = sorted(" ".join(r["old"]) for r in rows)
    expected = sorted(" ".join(old[:len(r["old"])]) for old, _ in RELEASED
                      for r in rows if old[:len(r["old"])] == r["old"])
    assert listed == expected, (listed, expected)
    assert len(listed) == len(RELEASED) == 7, listed


@pytest.mark.parametrize("old,new", RELEASED, ids=_ids(RELEASED))
def test_vr_e2_an_alias_does_the_new_verbs_work(tmp_path, old, new):
    a = _project(tmp_path / "a")
    b = _project(tmp_path / "b")
    rc_old, out_old, err_old = _run(old, a)
    rc_new, out_new, err_new = _run(new, b)
    assert len(_notices(err_old)) == 1, err_old
    notice = _notices(err_old)[0]
    assert "compass: '" in notice and "' is now '" in notice, notice
    assert " ".join(new[:2]) in notice or " ".join(new[:3]) in notice, notice
    assert not _notices(err_new), err_new
    # Both spellings failing alike would pass the comparison below, so a
    # parse error on the new spelling is refused first.
    assert "usage:" not in err_new and "invalid choice" not in err_new, err_new
    assert rc_old == rc_new
    assert _norm(out_old, a) == _norm(out_new, b)
    without = "\n".join(l for l in err_old.splitlines() if "works until 7.0.0" not in l)
    assert _norm(without.strip(), a) == _norm(err_new.strip(), b)
    # The same work on disk: the two manifests end alike.
    ma = (a / ".compass/work/sample/manifest.yml").read_text()
    mb = (b / ".compass/work/sample/manifest.yml").read_text()
    drop = lambda t: "\n".join(l for l in t.splitlines()
                               if not l.startswith(("parked_at", "updated")))
    assert drop(ma) == drop(mb)


# --- VR-E3: JSON output stays clean ------------------------------------------

def test_vr_e3_an_alias_run_with_json_keeps_standard_output_clean(tmp_path):
    a = _project(tmp_path / "a")
    b = _project(tmp_path / "b")
    rc_old, out_old, err_old = _run(["approach", "summary", "--json"], a)
    rc_new, out_new, err_new = _run(["approach", "show", "--json"], b)
    assert rc_old == rc_new == 0
    assert json.loads(out_old) == json.loads(out_new)
    assert "works until 7.0.0" not in out_old
    assert len(_notices(err_old)) == 1, err_old
    assert not err_new.strip()


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
    assert {"status", "migrate", "dashboard", "artifact", "template"} <= issue
    assert not issue & {"set-status", "migrate-config", "refresh-spec"}
    assert {"set", "add"} <= _choices(["issue", "subtask"], p)
    assert "update" not in _choices(["issue", "subtask"], p)
    assert "show" in _choices(["policy"], p)
    assert not _choices(["policy"], p) & {"effective", "review-rules"}
    assert _choices(["review-rule"], p) == {"list"}
    assert _choices(["issue", "dashboard"], p) == {"render"}
    assert _choices(["issue", "artifact"], p) == {"set"}


def test_vr_e4_no_alias_old_spelling_is_a_verb_in_any_help(tmp_path):
    p = _project(tmp_path / "p")
    for row in _table()["aliases"]:
        old = row["old"]
        parent = old[:-1]
        if not parent:
            continue
        assert old[-1] not in _choices(parent, p) or old[-1] in row["new"], row


# --- VR-E5: aliases end at 7.0.0 ---------------------------------------------

def test_vr_e5_a_test_fails_at_7_0_0_while_any_alias_remains():
    from compass_pkg import aliases
    table = aliases.load_table()
    assert table["aliases"], "the table has no rows to prove the check on"
    assert aliases.removal_problems("5.6.0", table) == []
    planted = aliases.removal_problems("7.0.0", table)
    assert planted, "a version of 7.0.0 with rows left must fail"
    assert aliases.removal_problems("7.0.0", {"aliases": [], "hints": []}) == []
    assert aliases.removal_problems("7.1.2", table)
    assert aliases.removal_problems("6.9.9", table) == []


def test_vr_e5_the_real_table_is_empty_once_the_package_reaches_7_0_0():
    from compass_pkg import aliases, core
    assert aliases.removal_problems(core.COMPASS_VERSION, aliases.load_table()) == [], (
        "the package version is 7.0.0 or later and the alias table still has rows")


# --- VR-E6: an unreleased spelling is refused, with a hint -------------------

UNRELEASED = [
    (["policy", "effective"], "policy show"),
    (["approach", "diagram"], "approach render"),
    (["issue", "refresh-spec"], "spec sync"),
    (["issue", "migrate-config"], "issue migrate --config"),
    (["issue", "template", "requirements-review"], "issue template show"),
    (["scenario", "tests", "SCN-1", "--test", "tests/x.py::t"], "scenario tests set"),
]


@pytest.mark.parametrize("old,new", UNRELEASED, ids=[" ".join(o[:3]) for o, _ in UNRELEASED])
def test_vr_e6_an_unreleased_spelling_is_refused_and_names_the_new_one(tmp_path, old, new):
    project = _project(tmp_path / "p")
    rc, out, err = _run(old, project)
    assert rc == 2, (rc, out, err)
    assert out == ""
    assert "works until 7.0.0" not in err
    assert f"is now '{new}'" in err, err
    assert err.count("is now '") == 1, err


def test_vr_e6_no_hint_spelling_is_held_by_a_release(tmp_path):
    """A hint exists because no release holds the old spelling; a spelling the
    tag holds would need an alias, not a hint."""
    cli = _tag_cli()
    if cli is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    project = _project(tmp_path / "p")
    for row in _table()["hints"]:
        rc, out, err = _run(row["old"] + ["--help"], project, cli=cli)
        assert rc != 0, f"{TAG} holds {' '.join(row['old'])}, so it needs an alias, not a hint"


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
    "quick-fix start": "assesses and records a quick fix in one call",
    "quick-fix finish": "traces, checks, gates and lands a quick fix in one call",
    "decision record": "writes a decision entry",
    "decision check": "compares decision entries with a base ref",
    "lesson propose": "holds a lesson for acceptance",
    "lesson accept": "turns a pending proposal into a lesson",
    "lesson decline": "drops a pending proposal",
    "record restore": "restores a record from its sync",
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


def _tag_cli():
    """The CLI of the release tag, extracted once; None when the tag is absent."""
    if "path" in _TAG_CLI:
        return _TAG_CLI["path"]
    probe = subprocess.run(["git", "rev-parse", "--verify", "-q", f"{TAG}^{{commit}}"],
                           cwd=str(ROOT), capture_output=True, text=True)
    if probe.returncode != 0:
        _TAG_CLI["path"] = None
        return None
    import tempfile
    dest = Path(tempfile.mkdtemp(prefix="compass-tag-"))
    data = subprocess.run(["git", "archive", TAG, "cli"], cwd=str(ROOT),
                          capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(dest)
    _TAG_CLI["path"] = dest / "cli" / "compass"
    return _TAG_CLI["path"]


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
        rc, out, err = _run(row["old"] + ["--help"], cwd, cli=cli)
        if rc != 0:
            problems.append(f"{name}: {TAG} does not hold this spelling")
    return problems


def test_vr_e13_each_row_names_a_release_that_holds_the_old_spelling(tmp_path):
    cli = _tag_cli()
    if cli is None:
        pytest.skip(f"tag {TAG} is not available in this clone")
    rows = _table()["aliases"]
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


def test_vr_e13_the_table_file_has_a_release_on_every_row():
    for row in _table()["aliases"]:
        assert row.get("released_in", "").startswith("v"), row
        assert row["kind"] == "verb", row


# --- VR-E14: one rewrite step; the bare artifact spelling --------------------

def test_vr_e14_the_bare_artifact_spelling_is_rewritten_with_one_notice(tmp_path):
    from compass_pkg import aliases
    argv, notice = aliases.rewrite(["issue", "artifact", "design", "--status", "omitted"])
    assert argv == ["issue", "artifact", "set", "design", "--status", "omitted"]
    assert notice and notice.count("\n") == 0 and "'issue artifact' is now 'issue artifact set'" in notice
    assert aliases.rewrite(["issue", "artifact", "set", "design"]) == (
        ["issue", "artifact", "set", "design"], None)
    assert aliases.rewrite(["issue", "artifact", "--help"])[1] is None
    assert aliases.rewrite(["issue", "artifact-path", "design"])[1] is None
    a = _project(tmp_path / "a")
    b = _project(tmp_path / "b")
    rc_old, out_old, err_old = _run(
        ["issue", "artifact", "design", "--status", "omitted", "--reason", "x"], a)
    rc_new, out_new, err_new = _run(
        ["issue", "artifact", "set", "design", "--status", "omitted", "--reason", "x"], b)
    assert (rc_old, _norm(out_old, a)) == (rc_new, _norm(out_new, b))
    assert len(_notices(err_old)) == 1 and not _notices(err_new)


def test_vr_e14_the_rewrite_reads_arguments_only_from_the_command_line():
    from compass_pkg import aliases
    assert aliases.rewrite(["check"]) == (["check"], None)
    assert aliases.rewrite([]) == ([], None)
    argv, notice = aliases.rewrite(["migrate", "--apply"])
    assert argv == ["issue", "migrate", "--apply"] and notice
    argv, _ = aliases.rewrite(["issue", "dashboard", "--check"])
    assert argv == ["issue", "dashboard", "render", "--check"]
    assert aliases.rewrite(["issue", "dashboard", "render"])[1] is None
