"""Moving an issue's documents out from beside its manifest.

Scenario group E of `docs-compass-artifacts`, plus `TRC-G2`.

`compass migrate` already renames v1 filenames and rewrites manifests to schema
2.0. This adds the relocation: human documents move to
`docs/compass/<created>-<slug>/` and the manifest's artifact registry is
written to name each one. Machine state - the manifest, `evidence/`, the
markers, the devlog - does not move, because that is what the CLI reads.

The dry run is the default and it has to promise exactly what the apply does.
A dry run that promises less is as hard to trust afterwards as one that
promises more.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
COMPASS_CLI = ROOT / "cli" / "compass"

sys.path.insert(0, str(ROOT / "cli"))
from compass_pkg import core  # noqa: E402

SLUG = "an-old-issue"
CREATED = "2026-09-08"

#: Written beside the manifest by an issue that predates the relocation.
DOCUMENTS = ("delivery-approach.md", "acceptance-criteria.md",
             "technical-design.md", "verification-report.md")

#: Read and written by the CLI. Never moves.
MACHINE_STATE = ("manifest.yml", "devlog.md")


def _old_style_issue(tmp_path, slug=SLUG, created=CREATED, registry=None):
    work = tmp_path / ".compass" / "work" / slug
    (work / "evidence").mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n",
                                                      encoding="utf-8")
    for name in DOCUMENTS:
        (work / name).write_text(f"# {name}\n", encoding="utf-8")
    (work / "devlog.md").write_text("# devlog\n", encoding="utf-8")
    (work / ".red").write_text("", encoding="utf-8")
    (work / "evidence" / "green.json").write_text("{}", encoding="utf-8")
    manifest = {
        "schema_version": "2.0", "issue": slug, "created": created,
        "status": "active",
        "artifacts": registry if registry is not None else [
            {"id": "ART-" + n[:-3].upper().replace("-", "_"),
             "kind": n[:-3], "status": "draft", "reason": "earned"}
            for n in DOCUMENTS
        ],
        "evidence": [], "gates": [], "scenarios": [], "changed_files": [],
        "claims": [], "follow_ups": [],
    }
    (work / "manifest.yml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return work


def _is_pointer(path):
    """The compatibility pointer `TRC-E5` leaves, told apart from a real
    document by the marker the migration writes into it."""
    return "<!-- compass: moved -->" in path.read_text(encoding="utf-8")


def _migrate(project, *args):
    return subprocess.run(
        [sys.executable, str(COMPASS_CLI), "migrate", *args],
        capture_output=True, text=True, timeout=300, cwd=str(project))


def _tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


# --- `TRC-E1` ------------------------------------------------------------------

def test_trc_e1_migration_moves_documents_and_writes_the_registry(tmp_path):
    work = _old_style_issue(tmp_path)
    r = _migrate(tmp_path, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr

    docs = tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
    for name in DOCUMENTS:
        assert (docs / name).is_file(), (
            f"{name} was not moved to {docs}:\n{r.stdout}")
        assert not (work / name).exists(), (
            f"{name} is still beside the manifest as well - a move, not a copy")

    entries = {a["kind"]: a for a in
               yaml.safe_load((work / "manifest.yml").read_text())["artifacts"]}
    for name in DOCUMENTS:
        kind = name[:-3]
        got = entries[kind].get("path")
        assert got == f"docs/compass/{CREATED}-{SLUG}/{name}", (
            f"the registry records {got!r} for {kind}, not the path it moved "
            f"the document to")

    state, found, reason = core.resolve_artifact(str(work), "technical-design")
    assert state == core.FOUND, (
        f"after migrating, the resolver answers {state} ({reason})")
    assert os.path.samefile(found, docs / "technical-design.md")


def test_trc_e1_machine_state_does_not_move(tmp_path):
    """What the CLI reads stays where the CLI reads it. Moving `evidence/`
    would break every gate in the repository at once."""
    work = _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    for name in MACHINE_STATE:
        assert (work / name).is_file(), f"{name} moved and must not have"
    assert (work / "evidence" / "green.json").is_file(), "evidence/ moved"
    assert (work / ".red").is_file(), "the .red marker moved"
    assert not (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
                / "devlog.md").exists(), "devlog.md was moved"


def test_trc_e1_the_old_review_page_is_kept_aside_not_regenerated(tmp_path):
    """The generated `README.md` an earlier release wrote beside the manifest is no longer
    made. Migration keeps it, byte for byte, as `README.md.v6.bak` and never rewrites it:
    a rewrite after the move would have changed the page to say the registry this run
    rewrote, and a README a person wrote would have been replaced."""
    work = _old_style_issue(tmp_path, registry=[
        {"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
         "status": "draft", "reason": "earned"}])
    old_page = ("<!-- GENERATED by `compass issue dashboard` - do not edit. "
                "Regenerate after any stage. -->\n\n# old page\n")
    (work / "README.md").write_text(old_page)

    _migrate(tmp_path, "--apply")
    assert not (work / "README.md").exists(), "the old page kept its name"
    assert (work / "README.md.v6.bak").read_text() == old_page, (
        "the old page was not kept byte for byte")


def test_trc_e1_migration_is_idempotent(tmp_path):
    """Run twice, second run reports nothing to do and changes nothing."""
    _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    before = _tree(tmp_path)
    r = _migrate(tmp_path, "--apply")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tree(tmp_path) == before, (
        "a second apply changed the tree:\n" + r.stdout)


# --- `TRC-E2` ------------------------------------------------------------------

def test_trc_e2_the_dry_run_changes_nothing(tmp_path):
    work = _old_style_issue(tmp_path)
    before = _tree(tmp_path)
    manifest_before = (work / "manifest.yml").read_text()

    r = _migrate(tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _tree(tmp_path) == before, (
        "the dry run changed the tree:\n" + r.stdout)
    assert (work / "manifest.yml").read_text() == manifest_before, (
        "the dry run rewrote the manifest")


def test_trc_e2_the_dry_run_reports_every_move_the_apply_makes(tmp_path):
    """The dry run promises exactly what the apply does.

    Promising less is the same class of mismatch as promising more, and just as
    hard to trust the next time.
    """
    _old_style_issue(tmp_path)
    dry = _migrate(tmp_path).stdout
    for name in DOCUMENTS:
        assert name in dry, (
            f"the dry run does not mention moving {name}:\n{dry}")
    assert "docs/compass" in dry, (
        f"the dry run does not say where the documents would go:\n{dry}")


# --- `TRC-E3` ------------------------------------------------------------------

def test_trc_e3_an_unmigrated_issue_keeps_working(tmp_path):
    """No registry at all - the 148 issue directories that predate it.

    Everything still resolves by the flat filename, and nothing tells the
    reader to migrate. Compass does not nag about state it can read.
    """
    work = _old_style_issue(tmp_path, registry=[])
    state, found, _reason = core.resolve_artifact(str(work), "technical-design")
    assert state == core.FOUND and os.path.samefile(
        found, work / "technical-design.md"), (
        "an issue with no registry stopped resolving its own documents")

    r = subprocess.run(
        [sys.executable, str(COMPASS_CLI), "check", "--issue", SLUG,
         "--verbose"],
        capture_output=True, text=True, timeout=120, cwd=str(tmp_path))
    assert "migrat" not in r.stdout.lower(), (
        f"compass check tells an unmigrated issue to migrate:\n{r.stdout}")


# --- `TRC-G2` ------------------------------------------------------------------

def test_trc_g2_a_half_finished_migration_is_visible(tmp_path):
    """Documents moved, registry not written.

    The reader must say the document is not written rather than find it by
    scanning `docs/compass/` - a scan finds another issue's document as
    readily as this one's. And `compass migrate` must offer to write the
    registry for the files it finds, because that is the state a person is in
    after a move that was interrupted.
    """
    work = _old_style_issue(tmp_path, registry=[
        {"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
         "status": "draft", "reason": "earned"}])
    docs = tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
    docs.mkdir(parents=True)
    (work / "technical-design.md").rename(docs / "technical-design.md")

    state, _found, reason = core.resolve_artifact(str(work), "technical-design")
    assert state == core.ABSENT, (
        f"a document that was moved without the registry being updated "
        f"resolved as {state} ({reason}) - a half-finished migration reads as "
        f"a finished one")

    dry = _migrate(tmp_path).stdout
    assert "technical-design.md" in dry and "register" in dry.lower(), (
        f"compass migrate does not offer to write the registry for a document "
        f"it can see under docs/compass/:\n{dry}")


def test_trc_g2_the_offer_is_taken_up_by_apply(tmp_path):
    """An offer the apply does not honour is worse than no offer."""
    work = _old_style_issue(tmp_path, registry=[
        {"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design",
         "status": "draft", "reason": "earned"}])
    docs = tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
    docs.mkdir(parents=True)
    (work / "technical-design.md").rename(docs / "technical-design.md")

    _migrate(tmp_path, "--apply")
    entry = next(a for a in
                 yaml.safe_load((work / "manifest.yml").read_text())["artifacts"]
                 if a["kind"] == "technical-design")
    assert entry.get("path") == f"docs/compass/{CREATED}-{SLUG}/technical-design.md", (
        f"apply did not adopt the document it offered to register: {entry}")


# --- `TRC-E4` ------------------------------------------------------------------

#: The five worked examples the scenario names. `examples/bdd-adapters/` holds
#: four adapter reference fixtures rather than worked examples: each is a
#: minimal `reset-password` issue that shows how one BDD runner is wired, and
#: none of them has ever had gates or a recorded green, so `compass check`
#: fails on all four and did before this change. They hold documents an
#: adopter reads, so the layout check below covers every example issue.
#: Only the `compass check` clause is scoped to the five.
WORKED_EXAMPLES = ("feature-api-change", "hotfix-regression",
                   "initiative-new-subsystem", "quick-fix-typo",
                   "spike-technical-unknown")


def _example_issue_dirs():
    return sorted(p.parent for p in ROOT.glob("examples/**/manifest.yml"))


def _worked_example_dirs():
    return [d for d in _example_issue_dirs()
            if any(f"examples/{name}/" in d.as_posix()
                   for name in WORKED_EXAMPLES)]


def test_trc_e4_the_shipped_examples_use_the_new_layout():
    """The examples are what an adopter copies. One still showing documents
    beside the manifest teaches the old layout more loudly than any prose."""
    dirs = _example_issue_dirs()
    assert dirs, "no example issues found - this check is inspecting nothing"
    stale = []
    for d in dirs:
        for doc in sorted(d.glob("*.md")):
            if doc.name in ("devlog.md", "README.md"):
                continue
            stale.append(str(doc.relative_to(ROOT)))
    assert not stale, (
        "shipped examples still keep human documents beside the manifest:\n  "
        + "\n  ".join(stale))


def test_trc_e4_compass_check_passes_against_each_example():
    dirs = _worked_example_dirs()
    assert len(dirs) == len(WORKED_EXAMPLES), (
        f"expected one issue in each of the {len(WORKED_EXAMPLES)} worked "
        f"examples, found {len(dirs)}: {[d.name for d in dirs]}")
    failures = []
    for d in dirs:
        # <example root>/.compass/work/<slug> -> <example root>
        project = d.parent.parent.parent
        r = subprocess.run(
            [sys.executable, str(COMPASS_CLI), "check", "--issue", d.name],
            capture_output=True, text=True, timeout=120, cwd=str(project))
        if r.returncode != 0:
            failures.append(f"--- {d.relative_to(ROOT)} ---\n{r.stdout[-800:]}")
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("cited_as", [
    "technical-design.md",
    ".compass/work/an-old-issue/technical-design.md",
])
def test_trc_e1_an_evidence_entry_is_repointed_however_it_named_the_file(
        tmp_path, cited_as):
    """An evidence entry can cite a document, and it can spell the path two
    ways.

    `path: technical-design.md` is measured from the issue directory.
    `path: .compass/work/<slug>/technical-design.md` is measured from the
    project root, and manifests on disk carry both. A repoint that matched
    only the bare filename left the second kind dangling, which fails the gate
    on an issue nothing is wrong with - the exact failure this issue exists to
    remove.
    """
    work = _old_style_issue(tmp_path)
    manifest = work / "manifest.yml"
    data = yaml.safe_load(manifest.read_text())
    data["evidence"] = [{"id": "EV-D", "type": "manual-review",
                         "path": cited_as}]
    manifest.write_text(yaml.safe_dump(data, sort_keys=False),
                        encoding="utf-8")

    _migrate(tmp_path, "--apply")
    got = yaml.safe_load(manifest.read_text())["evidence"][0]["path"]
    resolved = (work / got).resolve()
    expected = (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
                / "technical-design.md").resolve()
    assert resolved == expected, (
        f"the evidence entry cited as {cited_as!r} was rewritten to {got!r}, "
        f"which resolves to {resolved} rather than {expected}")


# --- the undo has to exist before the move happens ---------------------------

def _git(project, *args):
    return subprocess.run(["git", *args], cwd=str(project),
                          capture_output=True, text=True, timeout=120)


def test_apply_refuses_when_the_move_could_not_be_undone(tmp_path):
    """`--apply` moves files. The undo has to exist first.

    The way back is `git reset --hard` on a clean tree.
    That holds only where the work root is TRACKED, which is the case in a
    project using Compass. In this framework's own repository `.compass/work/`
    is gitignored, so git has nothing to restore and the reset is a complete
    undo of everything except the thing that moved.

    So the refusal is on the property that matters - is this recoverable - and
    not on "is the tree clean", which answers a different question and answers
    it wrongly here.
    """
    _old_style_issue(tmp_path)
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("/.compass/work/\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@e", "-c", "user.name=t",
         "commit", "-qm", "base")

    r = _migrate(tmp_path, "--apply")
    assert r.returncode != 0, (
        "--apply moved documents git cannot restore, without saying so:\n"
        + r.stdout + r.stderr)
    combined = r.stdout + r.stderr
    assert "gitignored" in combined or "not tracked" in combined, (
        "the refusal does not say why the move is unrecoverable:\n" + combined)
    assert (tmp_path / ".compass" / "work" / SLUG
            / "technical-design.md").is_file(), (
        "the refusal came after the move - nothing was protected")


def test_the_refusal_can_be_overridden_once_a_copy_exists(tmp_path):
    """A refusal with no override blocks a maintainer who has already taken
    a copy.

    The maintainer who has taken a copy says so and proceeds. The flag names
    what it asserts rather than switching a safety check off.
    """
    _old_style_issue(tmp_path)
    _git(tmp_path, "init", "-q")
    (tmp_path / ".gitignore").write_text("/.compass/work/\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@e", "-c", "user.name=t",
         "commit", "-qm", "base")

    r = _migrate(tmp_path, "--apply", "--i-have-a-copy")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}"
            / "technical-design.md").is_file(), (
        "the override was accepted but nothing moved:\n" + r.stdout)


def test_a_tracked_work_root_needs_no_override(tmp_path):
    """Where git CAN restore the move, the refusal must not fire.

    A guard that refuses everywhere protects nothing and trains people to pass
    the flag by reflex.
    """
    _old_style_issue(tmp_path)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@e", "-c", "user.name=t",
         "commit", "-qm", "base")

    r = _migrate(tmp_path, "--apply")
    assert r.returncode == 0, (
        "--apply refused on a tracked work root, where `git reset --hard` is "
        "a complete undo:\n" + r.stdout + r.stderr)


def test_a_repository_path_is_not_rewritten_by_the_filename_rename(tmp_path):
    """`repoint_spine_references` must look at the whole path, not the tail.

    The v1 rename map turns `plan.md` into `technical-design.md`. The rewrite
    splits a manifest value on its last `/` and tests only the filename, so a
    `changed_files:` entry naming `commands/plan.md` - a shipped command file,
    nothing to do with this issue - becomes `commands/technical-design.md`,
    which does not exist.

    Nothing fails at the time. `compass check` reports it later as a traced
    path that no longer exists, on an issue whose records were correct before
    the migration touched them.
    """
    work = _old_style_issue(tmp_path)
    manifest = work / "manifest.yml"
    data = yaml.safe_load(manifest.read_text())
    # The issue's own document, which SHOULD be repointed, and a repository
    # path that must be left alone.
    (work / "plan.md").write_text("# an old-style design\n", encoding="utf-8")
    (work / "technical-design.md").unlink()
    data["changed_files"] = [
        {"path": "commands/plan.md", "scenarios": ["S-1"]},
        {"path": "cli/compass_pkg/plan.md", "scenarios": ["S-1"]},
    ]
    manifest.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    _migrate(tmp_path, "--apply")
    got = [c["path"] for c in
           yaml.safe_load(manifest.read_text())["changed_files"]]
    assert got == ["commands/plan.md", "cli/compass_pkg/plan.md"], (
        f"the rename rewrote paths outside the issue directory: {got}")


# --- `TRC-E5`, as Q3 of artifact-catalogue-fields changed it --------------------
#
# The migrate no longer leaves a pointer where the delivery-approach record was. The
# registry has served the hook since before 5.0.0, and the pointer was generated
# text that named a path. The migrate removes the pointer an earlier run left.

BLOCKING_DOCUMENT = "delivery-approach.md"
POINTER = "<!-- compass: moved -->\n# Moved\n\nThis issue's delivery-approach.md is now elsewhere.\n"


def test_trc_e5_no_pointer_is_left_where_the_record_used_to_be(tmp_path):
    work = _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    assert not (work / BLOCKING_DOCUMENT).exists(), (
        "something was left where the delivery-approach record used to be")
    real = (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}" / BLOCKING_DOCUMENT)
    assert real.is_file(), "the record itself did not move"


def test_trc_e5_a_registry_reader_gets_the_record(tmp_path):
    work = _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    state, found, reason = core.resolve_artifact(str(work), "delivery-approach")
    assert state == core.FOUND, f"{state}: {reason}"
    real = (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}" / BLOCKING_DOCUMENT)
    assert os.path.samefile(found, real)


def test_trc_e5_only_the_devlog_stays_beside_the_manifest(tmp_path):
    work = _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    left = sorted(p.name for p in work.glob("*.md"))
    assert left == ["devlog.md"], f"more than the devlog stayed beside the manifest: {left}"


def test_trc_e5_a_second_run_leaves_the_record_as_it_is(tmp_path):
    _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    real = (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}" / BLOCKING_DOCUMENT)
    before = real.read_text(encoding="utf-8")
    r = _migrate(tmp_path, "--apply")
    assert real.read_text(encoding="utf-8") == before, r.stdout
    assert "nothing to do" in r.stdout, r.stdout


def test_trc_e5_a_pointer_of_an_earlier_run_is_removed(tmp_path):
    """A tree an earlier release migrated holds the record at its registered path and a
    pointer beside the manifest. The pointer goes, the record stays, and the dry run says so."""
    work = _old_style_issue(tmp_path)
    _migrate(tmp_path, "--apply")
    (work / BLOCKING_DOCUMENT).write_text(POINTER, encoding="utf-8")
    real = (tmp_path / "docs" / "compass" / f"{CREATED}-{SLUG}" / BLOCKING_DOCUMENT)
    before = real.read_bytes()

    dry = _migrate(tmp_path)
    assert "pointer" in dry.stdout and BLOCKING_DOCUMENT in dry.stdout, dry.stdout
    assert (work / BLOCKING_DOCUMENT).is_file(), "the dry run removed the pointer"
    r = _migrate(tmp_path, "--apply")
    assert "pointer" in r.stdout, r.stdout
    assert not (work / BLOCKING_DOCUMENT).exists()
    assert real.read_bytes() == before
    assert "nothing to do" in _migrate(tmp_path, "--apply").stdout
