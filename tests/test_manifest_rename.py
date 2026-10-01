"""Compass's central artifact has one name, and old-named files still load.

`issue spine` becomes `issue manifest`. The file is `manifest.yml`, its root
key is `issue:`, the path slug is `<issue-slug>`, and the module is
`manifest.py`.

Measured before the change: `spine` appeared 521 times and had no `terms:`
entry, so the most-used noun in the framework was the one word the vocabulary
scan never checked. 26 of those uses glossed it in place - "the
machine-readable issue spine" - which is the sentence you write when a
reader will not understand the word alone.

The compatibility path is not new. `cli/migrate-map.yml` already maps retired
filenames forward and `normalize_spine()` already maps retired keys; this adds
a row to each. What must stay true is that a file written under the old name
still loads, because `.compass/work/` is gitignored in this repository and
176 records have no git history behind them.

Scenario ids: NIR-A1, NIR-A2, NIR-B1, NIR-B2, NIR-C1, NIR-D1, NIR-D2, NIR-E1
in name-the-issue-record/acceptance-criteria.md
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent / "cli"))
from compass_pkg.core import is_issue_document as _own_archive

#: An issue's own documents live at `docs/compass/<created>-<slug>/` since
#: `compass migrate` relocated them out of `.compass/work/`, which every scan
#: here already skipped. They record the vocabulary and file layout in force
#: when they were written, so enforcing today's surface over them reports
#: their historical wording as a defect. Applied at the repository root
#: only: the worked examples' documents moved too and stay scanned, because
#: an adopter reads them to learn the pipeline.


ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TERMS = ROOT / "governance" / "terminology.yml"
MIGRATE_MAP = ROOT / "cli" / "migrate-map.yml"

OLD_FILE, NEW_FILE = "task.yml", "manifest.yml"
OLD_KEY, NEW_KEY = "task", "issue"


def _terminology():
    return yaml.safe_load(TERMS.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# NIR-A1 - the term is governed like every other
# ---------------------------------------------------------------------------

def test_nir_a1_manifest_has_a_terms_entry():
    """59 terms were governed and the most-used noun was not one of them."""
    doc = _terminology()
    terms = doc.get("terms") or {}
    assert "manifest" in terms, (
        "governance/terminology.yml has no `manifest` entry, so the scan does "
        "not cover the name of the artifact every command reads")

    entry = terms["manifest"]
    for field in ("means", "not", "related"):
        assert entry.get(field), (
            f"the `manifest` term carries no `{field}`. A term entry without "
            f"one is a word in a list, not a definition the scan can hold "
            f"anyone to")


# ---------------------------------------------------------------------------
# NIR-A2 - the name needs no gloss
# ---------------------------------------------------------------------------

# The tell, from the 26 cases that existed before: the name followed straight
# away by an apposition restating what it is. A proxy for "a reader knows what
# it is", and deliberately labelled as one - no check can prove comprehension.
GLOSS = re.compile(
    r"\bmanifest\b\s*[-,(]\s*(?:the\s+)?(?:machine-readable|structured|"
    r"machine)\b", re.I)

LIVE_PROSE = ["CLAUDE.md", "AGENTS.md", "README.md", "compass-contract.md"]


def test_nir_a2_the_name_is_not_glossed_where_it_is_used():
    hits = []
    for rel in LIVE_PROSE:
        p = ROOT / rel
        if not p.is_file():
            continue
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if GLOSS.search(line):
                hits.append(f"{rel}:{n}: {line.strip()[:70]}")
    for d in ("commands", "skills", "agents", "docs"):
        for p in sorted((ROOT / d).rglob("*.md")):
            if _own_archive(p.relative_to(ROOT)):
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if GLOSS.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:70]}")
    assert not hits, (
        "the name is explained at the point of use, which is the tell that it "
        "does not land on its own - the word it replaced was glossed in 26 "
        "places for exactly this reason:\n  " + "\n  ".join(hits[:8]))


# ---------------------------------------------------------------------------
# NIR-B1 / NIR-B2 - the retired word, and where it may survive
# ---------------------------------------------------------------------------

def test_nir_b1_spine_is_banned_in_the_vocabulary():
    doc = _terminology()
    banned = doc.get("banned") or []
    flat = " ".join(str(b) for b in banned)
    assert "spine" in flat, (
        "`spine` is not banned, so the scan will not stop it coming back")


# Where the old name may still appear, and why. Anywhere else is drift.
OLD_NAME_ALLOWED = (
    "cli/migrate-map.yml",              # the rename table names both spellings
    "governance/terminology.yml",       # the ban must name what it bans
    "architecture/decisions/",          # the decision record
    ".compass/",                        # the archive and this issue's own record
    # The same archive, in the place `compass migrate` moved it to. An issue's
    # documents name the vocabulary in force when they were written, and this
    # entry sits beside `.compass/` because it is the same reason, not a new
    # one. Root-anchored, so an examples document is still drift.
    "docs/compass/",
    "tests/test_manifest_rename.py",    # this file
    # The vocabulary machinery has to name the word to ban it: the ban
    # pattern lives in the first, and the last two are the fixtures that
    # prove it fires on the banned form and stays quiet on a book's spine.
    "tests/test_terminology.py",
    "tests/fixtures/terminology/banned_usage.md",
    "tests/fixtures/terminology/innocent_usage.md",
    # Records the count moving from 59 terms to 60, and says which term and
    # why - the note is the decision, so it has to name the old word.
    "tests/test_fresh_eyes_verify_sweeps.py",
    # Issue directories keep the slug they were created under. Four archived
    # issues have `spine` in their slug, and a citation that renames itself
    # points at a directory that does not exist.
    "tests/test_spine_records_the_truth.py",
    "docs/system-spec.md",
    "docs/system-spec-archive.md",
    # Quotes this repository's archive verbatim; the quoted sessions used the
    # old word and scripts/verify-archive-quotes.py hashes the quotes against
    # the real files, so editing one falsifies it.
    "skills/compass-runtime/writing-voice.md",
    # Derived from governance/terminology.yml, which must name what it bans.
    "docs/glossary.md",
    # Lists the retired names that must never be printed, so it has to spell
    # them - the same reason the ban list itself is allowed to.
    "tests/test_printed_output_coverage.py",
)


def test_nir_b2_the_old_name_survives_only_where_history_needs_it():
    # The scan reads tracked files, because the question it asks is what the
    # repository ships. `tests/test_house_style.py` argues this in its module
    # docstring: a guard that reads the working tree answers differently on
    # every machine, since it sees whatever each contributor happens to keep on
    # disk, and it passes in continuous integration where those files are
    # absent. `git grep` searches the content of tracked files only, so an
    # untracked working note is neither read nor reported.
    #
    # `OLD_NAME_ALLOWED` keeps its `.compass/` and `docs/compass/` entries even
    # though this repository does not track either directory. An adopting
    # project commits its issue records, and there the old name is history the
    # entries exist to permit.
    # Reported per LINE, not per file, so a single line that must name the
    # retired word carries a marker instead of the whole file being excused.
    # tests/test_writing_style.py needs it twice: a named exemption there
    # quotes another test's comment verbatim, because that sweep matches on
    # substrings, and the quote is what tells a deliberate mention from a live
    # use. Excusing the file would also excuse any future use anywhere in it.
    # The four entries in OLD_NAME_ALLOWED that are whole files stay whole:
    # the word runs throughout each of them.
    out = subprocess.run(
        ["git", "grep", "-nI", "-e", r"\bspine\b"],
        cwd=str(ROOT), capture_output=True, text=True)
    files = []
    for hit in out.stdout.splitlines():
        if not hit.strip():
            continue
        path, _, rest = hit.partition(":")
        _, _, text = rest.partition(":")
        if "vocabulary-scan: allow" in text:
            continue
        files.append(path)

    stray = [f for f in files
             if not any(f.startswith(a) or f == a for a in OLD_NAME_ALLOWED)]
    assert not stray, (
        "these carry the retired name outside the places history needs it - "
        "the rename table, the ban, the decision record and the archive:\n  "
        + "\n  ".join(sorted(stray)[:12]))


# ---------------------------------------------------------------------------
# NIR-C1 - the file, the CLI and the module agree
# ---------------------------------------------------------------------------

def test_nir_c1_the_module_carries_the_name():
    """The module and the artifact agree.

    NOTE for anyone running a rename sweep over this repository: the retired
    names below are BUILT FROM PARTS on purpose. A sweep that rewrites them
    would rewrite this test's own expectations. The test that checks a
    rename is the one a rename must not touch.
    """
    retired_module = "_".join(("task", "spine")) + ".py"
    pkg = ROOT / "cli" / "compass_pkg"

    assert (pkg / "manifest.py").is_file(), (
        "cli/compass_pkg/manifest.py does not exist - the module still "
        "carries the old name while the artifact carries the new one")
    assert not (pkg / retired_module).is_file(), (
        f"cli/compass_pkg/{retired_module} is still there, so both names "
        "exist at once - which is the half-rename this issue exists to end")


def test_nir_c1b_the_helpers_carry_the_name():
    """Same construction, same reason - see the note above."""
    src = "\n".join(p.read_text(encoding="utf-8")
                    for p in (ROOT / "cli" / "compass_pkg").glob("*.py"))
    pairs = (
        ("_".join(("resolve", "task", "dir")), "resolve_issue_dir"),
        ("_".join(("load", "task")), "load_manifest"),
        ("_".join(("save", "task")), "save_manifest"),
    )
    for gone, now in pairs:
        assert f"def {now}(" in src, f"{now}() is not defined"
        assert f"def {gone}(" not in src, (
            f"{gone}() is still defined, so a reader meets both names")


# ---------------------------------------------------------------------------
# NIR-D1 - a file written under the old name still loads
# ---------------------------------------------------------------------------

OLD_SPINE = """schema_version: '2.0'
task: legacy-issue
created: '2026-08-01'
status: active
assessment: {risk: contained, familiarity: brownfield-mapped, size: atomic, goal: delivery, role: engineer}
delivery_approach: quick-fix
scenarios: []
evidence: []
gates: []
changed_files: []
"""


def _legacy_project(tmp_path):
    root = (tmp_path / "proj").resolve()
    d = root / ".compass" / "work" / "legacy-issue"
    d.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "current-task").write_text("legacy-issue\n")
    (d / OLD_FILE).write_text(OLD_SPINE)          # old filename, old root key
    (d / "delivery-approach.md").write_text("# approach\n")
    return root, d


def test_nir_d1_an_old_named_file_still_loads(tmp_path):
    """ADR-006, and non-negotiable: a project that has not migrated keeps
    working. 176 records in this repository have no git history behind them."""
    root, _ = _legacy_project(tmp_path)
    r = subprocess.run([sys.executable, str(CLI), "issue", "lint",
                        "--issue", "legacy-issue"],
                       cwd=str(root), capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    assert r.returncode == 0, (
        "a file written under the old name no longer loads, so every "
        f"unmigrated project breaks:\n{out}")


# ---------------------------------------------------------------------------
# NIR-D2 - the migrator moves the archive
# ---------------------------------------------------------------------------

def test_nir_d2_migrate_renames_the_file_and_the_key(tmp_path):
    root, d = _legacy_project(tmp_path)

    dry = subprocess.run([sys.executable, str(CLI), "migrate"],
                         cwd=str(root), capture_output=True, text=True, timeout=120)
    assert (d / OLD_FILE).is_file(), (
        "the dry run wrote to disk - it is meant to report and change nothing")

    run = subprocess.run([sys.executable, str(CLI), "migrate", "--apply"],
                         cwd=str(root), capture_output=True, text=True, timeout=120)
    out = run.stdout + run.stderr
    assert (d / NEW_FILE).is_file(), f"migrate did not rename the file:\n{out}"
    assert not (d / OLD_FILE).is_file(), "both names are on disk after migrating"

    doc = yaml.safe_load((d / NEW_FILE).read_text(encoding="utf-8"))
    assert doc.get(NEW_KEY) == "legacy-issue", (
        f"the root key was not mapped forward: {sorted(doc)[:6]}")
    assert OLD_KEY not in doc, "the retired root key is still there"


def test_nir_d2b_migrating_twice_changes_nothing(tmp_path):
    """Idempotence, which the migrator already has - this holds it for the
    new rows rather than assuming they inherit it."""
    root, d = _legacy_project(tmp_path)
    subprocess.run([sys.executable, str(CLI), "migrate", "--apply"],
                   cwd=str(root), capture_output=True, text=True, timeout=120)
    first = (d / NEW_FILE).read_text(encoding="utf-8")

    again = subprocess.run([sys.executable, str(CLI), "migrate", "--apply"],
                           cwd=str(root), capture_output=True, text=True, timeout=120)
    assert again.returncode == 0, (again.stdout + again.stderr)
    assert (d / NEW_FILE).read_text(encoding="utf-8") == first, (
        "a second migration changed the file, so the operation is not "
        "idempotent and running it twice is not safe")


# ---------------------------------------------------------------------------
# NIR-E1 - the freeze needs a decision record
# ---------------------------------------------------------------------------

def test_nir_e1_a_decision_record_covers_the_vocabulary_change():
    """terminology.yml says changing the vocabulary needs a decision record.
    ADR-012 froze it "for years" and a second rename landed three weeks
    later; the decision record is what stops a third being informal."""
    adrs = sorted((ROOT / "architecture" / "decisions").glob("ADR-*.md"))
    hits = [p for p in adrs
            if re.search(r"\bmanifest\b", p.read_text(encoding="utf-8"), re.I)
            and re.search(r"\bspine\b", p.read_text(encoding="utf-8"), re.I)]
    assert hits, (
        "no decision record covers renaming the artifact. terminology.yml "
        "requires the ceremony of a decision record for a vocabulary change, "
        "and this is the largest one the vocabulary has had")


def test_nir_d3_the_compatibility_pair_is_not_an_identity():
    """The fallback must actually be a fallback.

    A blanket rename can make both members of a compatibility pair equal.
    That breaks unmigrated projects silently, so this asserts the members
    differ.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.core import MANIFEST_NAMES

    assert len(MANIFEST_NAMES) >= 2, (
        "the manifest has no retired filename to fall back to, so a project "
        "written before the rename cannot be read")
    assert len(set(MANIFEST_NAMES)) == len(MANIFEST_NAMES), (
        f"the candidate filenames are not distinct: {MANIFEST_NAMES}. A "
        "rename has collapsed the compatibility pair into an identity, which "
        "breaks only unmigrated projects and so passes every other test")
    assert MANIFEST_NAMES[0] == "manifest.yml", (
        f"the current name is not tried first: {MANIFEST_NAMES}. Preferring "
        "the retired name means every reader quietly takes the stale file")


def test_nir_d4_no_module_opens_the_manifest_by_a_hard_coded_name():
    """Every reader resolves the filename through `manifest_path`.

    A hard-coded `os.path.join(task_dir, "manifest.yml")` reads only migrated
    projects. A project still holding task.yml then answers "not found",
    including from the migrator's own reader.

    core.py is excluded because it defines the resolver, and migrate-map.yml is
    data rather than code.
    """
    pkg = ROOT / "cli" / "compass_pkg"
    literal = re.compile(r'os\.path\.join\([^()]*?,\s*["\']manifest\.yml["\']\)')
    offenders = []
    for path in sorted(pkg.glob("*.py")) + [ROOT / "cli" / "compass"]:
        if path.name == "core.py":
            continue
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            if literal.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not offenders, (
        "these open the manifest by a hard-coded filename, so a project that "
        "has not run `compass migrate` gets 'not found' instead of its file. "
        "Call manifest_path(dir) - it tries the current name, then the "
        "retired one:\n  " + "\n  ".join(offenders[:10]))


def test_nir_c1c_the_shipped_template_writes_the_current_root_key():
    """A new issue is born current, not born needing migration.

    templates/manifest.yml is what every issue's record is copied from. A
    template with the retired root key sends every new manifest through the
    compatibility map that exists for records written years ago.

    The placeholder is checked with it. A template that says {{TASK_SLUG}} while
    the key says `issue` teaches the old word in the one file an author copies.
    """
    template = ROOT / "templates" / "manifest.yml"
    data = yaml.safe_load(template.read_text(encoding="utf-8"))
    assert "issue" in data, (
        f"{template.relative_to(ROOT)} has no `issue:` root key - every issue "
        f"copied from it is created under the retired name. Keys: {sorted(data)[:8]}")
    assert "task" not in data, (
        f"{template.relative_to(ROOT)} still carries the retired `task:` root "
        f"key, so a fresh issue is created already needing `compass migrate`")

    stray = sorted(
        p.relative_to(ROOT) for p in ROOT.rglob("*")
        if p.is_file() and p.suffix in {".md", ".yml"}
        and ".git" not in p.parts and ".compass" not in p.parts
        and "{{TASK" + "_SLUG}}" in p.read_text(encoding="utf-8", errors="replace"))
    assert not stray, (
        "these still use the retired slug placeholder, which is the word an "
        f"author copies out of the template:\n  " +
        "\n  ".join(str(s) for s in stray[:10]))
