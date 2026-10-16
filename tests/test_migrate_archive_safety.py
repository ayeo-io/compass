"""Scenarios MAS-1 to MAS-17 of the issue `migrate-archive-safety`, and MCG-2 to MCG-6
of the issue `migrate-copy-check-gaps`.

`compass issue migrate` must be safe to run on an archive nobody can rebuild:

  * a dry run lists only what the next `--apply` changes (MAS-1, MAS-2);
  * a pair of registry entries reported for a person stays as it is, entries
    and files, on every run (MAS-3 to MAS-5);
  * `--apply` without `--i-have-a-copy` runs only when the HEAD commit holds,
    with the bytes on disk, every file the migrate can change in each issue
    folder (MAS-6 to MAS-8), and the root's real path is inside the project's
    repository (MCG-2 to MCG-4);
  * a distribution map whose real path is outside the project is never renamed (MCG-5),
    and one under a link that stays inside the project still is (MCG-6).

Every test works on a copy of the archive sample, or a fixture, in pytest's
temporary folder. Each one reaches the migrate only through `_migrate`, which
refuses a root outside that folder or inside this repository, and git only
through `_git`. MAS-9 checks both rules, also with COMPASS_FULL_ARCHIVE=1.
"""
from __future__ import annotations

import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "tests"))

CREATED = "2026-09-01"
OLDER = {"status": "approved", "approved_by": "jed72", "approved_at": "2026-09-02T09:00:00Z",
         "digest": "sha256:OLD"}
NEWER = {"status": "approved", "approved_by": "jed72", "approved_at": "2026-10-10T09:00:00Z",
         "digest": "sha256:NEW"}
#: The fields of a registry entry a reported pair must keep.
FIELDS = ("id", "kind", "round", "path", "status", "approved_by", "approved_at", "digest")

BOTH = "planted-both-places"
IN_PLACE = "planted-pair-in-place"
RENAME = "planted-pair-rename"
PLANTED = (BOTH, IN_PLACE, RENAME)

#: pytest's base temporary folder for this worker, set by the fixture below.
_BASE = {}


@pytest.fixture(autouse=True)
def _base_temp(tmp_path_factory):
    _BASE["dir"] = Path(os.path.realpath(tmp_path_factory.getbasetemp()))


def _home(slug):
    return f"docs/compass/{CREATED}-{slug}"


def _inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder + os.sep)


def _env(root, path_first=None, path_only=None):
    """A small environment: no GIT_* variable from the caller, and git never looks
    above the fixture's own folder for a repository. `path_first` is a folder put at
    the front of PATH, for a test that replaces git; `path_only` is the whole PATH, for
    a test that hides git."""
    path = os.environ.get("PATH", "/usr/bin:/bin")
    if path_first:
        path = str(path_first) + os.pathsep + path
    if path_only:
        path = str(path_only)
    return {"PATH": path, "HOME": str(root),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "200",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "CLAUDE_PROJECT_DIR": str(root),
            "GIT_CEILING_DIRECTORIES": os.path.realpath(Path(root).parent)}


def _check_root(root):
    assert "dir" in _BASE, "the base temporary folder is not known"
    assert _inside(root, _BASE["dir"]), f"{root} is not inside {_BASE['dir']}"
    assert not _inside(root, ROOT), f"{root} is inside the repository"


def _migrate(root, *flags, path_first=None, path_only=None):
    """`compass issue migrate` on the project at `root`, which must be a fixture in
    the temporary folder. Returns (exit code, stdout + stderr)."""
    _check_root(root)
    for folder in (path_first, path_only):
        if folder:
            _check_root(folder)
    run = subprocess.run(
        [sys.executable, str(CLI), "issue", "migrate", str(Path(root) / ".compass" / "work"),
         *flags], cwd=root, env=_env(root, path_first, path_only), capture_output=True,
        text=True, timeout=300)
    return run.returncode, run.stdout + run.stderr


def _git(root, *args):
    """git in the fixture at `root`, under the same environment as `_migrate`."""
    _check_root(root)
    run = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                         cwd=root, env=_env(root), capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    return run.stdout


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _plant(root, slug, artifacts=(), beside=None, docs=None, elsewhere=None):
    """One issue whose manifest is already current, so the only change a run can
    make to it is the one its scenario is about. `beside`, `docs` and `elsewhere`
    map a file name (or project-relative path) to its text."""
    work = root / ".compass" / "work" / slug
    manifest = {"schema_version": "3.0", "issue": slug, "created": CREATED,
                "delivery_approach": "regular",
                "artifacts": list(artifacts), "evidence": [], "gates": [], "scenarios": [],
                "changed_files": [], "claims": [], "follow_ups": []}
    _write(work / "manifest.yml", yaml.safe_dump(manifest, sort_keys=False))
    for name, text in (beside or {}).items():
        _write(work / name, text)
    for name, text in (docs or {}).items():
        _write(root / _home(slug) / name, text)
    for rel, text in (elsewhere or {}).items():
        _write(root / rel, text)


def _planted_sample(tmp_path, only=PLANTED):
    """A copy of the archive sample in the temporary folder, with the planted issues
    named in `only`. Never the real archive: it reads `sample_root()` only."""
    from archive import sample_root
    root = tmp_path / "project"
    shutil.copytree(sample_root(), root)
    if BOTH in only:
        _plant(root, BOTH,
               beside={"technical-design.md": "# Technical design\n\nBeside the manifest.\n"},
               docs={"technical-design.md": "# Technical design\n\nIn the documents folder.\n"})
    if IN_PLACE in only:
        _plant(root, IN_PLACE, artifacts=[
            {"id": "ART-REVIEW-2", "kind": "review-2", **NEWER,
             "path": f"{_home(IN_PLACE)}/review-2.md"},
            {"id": "ART-ROUND-2", "kind": "review", "round": 2, **OLDER,
             "path": "notes/review-2.md"},
        ], docs={"review-2.md": "# Review 2\n\nIn the documents folder.\n"},
            elsewhere={"notes/review-2.md": "# Review 2\n\nIn the notes folder.\n"})
    if RENAME in only:
        _plant(root, RENAME, artifacts=[
            {"id": "ART-REVIEW", "kind": "review", **NEWER, "path": f"{_home(RENAME)}/review.md"},
            {"id": "ART-ROUND-1", "kind": "review", "round": 1, **OLDER,
             "path": "notes/review-1.md"},
        ], beside={"intent.md": "# Intent\n\nBeside the manifest.\n"},
            docs={"review.md": "# Review\n\nIn the documents folder.\n"},
            elsewhere={"notes/review-1.md": "# Review 1\n\nIn the notes folder.\n"})
    return root


def _sections(out):
    """{issue directory: [change line]} from a run's report."""
    found, slug, inside = {}, None, False
    for line in out.splitlines():
        if line.startswith("compass issue migrate: ") and (" would change under " in line
                                                          or " migrated under " in line):
            inside = True
            continue
        if not inside:
            continue
        if not line.strip():
            break
        if line.startswith("    - ") and slug:
            found[slug].append(line[6:])
        elif line.startswith("  ") and not line.startswith("   "):
            slug = line.strip()
            found[slug] = []
    return found


def _totals(out):
    lines = out.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln == "compass issue migrate: totals"), None)
    if start is None:
        return []
    block = [lines[start]]
    for line in lines[start + 1:]:
        if not line.startswith("  "):
            break
        block.append(line)
    return block


def _items(out):
    """The items left for a person, in order."""
    lines = out.splitlines()
    start = next((i for i, ln in enumerate(lines) if "left for a person to record:" in ln), None)
    if start is None:
        return []
    items = []
    for line in lines[start + 1:]:
        if not line.startswith("  - "):
            break
        items.append(line[4:])
    return items


def _issue_items(out, slug):
    return [item for item in _items(out) if item.startswith(slug + ":")]


def _merge_lines(out, slug):
    return [n for n in _sections(out).get(slug, []) if "merge" in n]


def _registry(root, slug):
    data = yaml.safe_load((root / ".compass" / "work" / slug / "manifest.yml")
                          .read_text(encoding="utf-8"))
    return data.get("artifacts") or []


def _pair_fields(root, slug, ids):
    entries = {e.get("id"): e for e in _registry(root, slug) if isinstance(e, dict)}
    return {i: tuple(entries.get(i, {}).get(f) for f in FIELDS) for i in ids}


def _bytes(root, *rels):
    return {rel: (root / rel).read_bytes() if (root / rel).is_file() else None for rel in rels}


def _nothing_to_do(out):
    return "nothing to do" in out and not _sections(out)


# --- group A: the dry run agrees with the apply ---------------------------------------


def test_mas_1_both_places_is_a_change_once_then_an_item(tmp_path):
    root = _planted_sample(tmp_path, only=(BOTH,))
    work_copy = f".compass/work/{BOTH}/technical-design.md"
    docs_copy = f"{_home(BOTH)}/technical-design.md"
    before = _bytes(root, work_copy, docs_copy)

    def both_places_lines(out):
        return [n for n in _sections(out).get(BOTH, [])
                if "technical-design.md" in n and "in both places" in n]

    def both_copies_items(out):
        return [i for i in _issue_items(out, BOTH) if work_copy in i and docs_copy in i]

    code, dry = _migrate(root)
    assert code == 0, dry
    assert len(both_places_lines(dry)) == 1, dry
    code, applied = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, applied
    assert len(both_places_lines(applied)) == 1, applied
    entry = next(e for e in _registry(root, BOTH) if e.get("kind") == "technical-design")
    assert entry["path"] == docs_copy, entry
    assert _bytes(root, work_copy, docs_copy) == before

    for flags in ((), ("--apply", "--i-have-a-copy")):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        assert _nothing_to_do(out), (flags, out)
        assert len(both_copies_items(out)) == 1, (flags, out)
    assert _bytes(root, work_copy, docs_copy) == before

    (root / work_copy).unlink()
    for flags in ((), ("--apply", "--i-have-a-copy")):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        assert _issue_items(out, BOTH) == [], (flags, out)


def test_mas_2_dry_run_matches_apply_on_the_sample(tmp_path):
    root = _planted_sample(tmp_path)
    code, dry = _migrate(root)
    assert code == 0, dry
    # The dry run sees each planted case, so the comparison cannot pass on an empty walk.
    assert set(PLANTED) <= set(_sections(dry)) | {i.split(":")[0] for i in _items(dry)}, dry
    code, applied = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, applied
    assert sorted(_sections(dry)) == sorted(_sections(applied)), (dry, applied)
    assert _totals(dry) and _totals(dry) == _totals(applied), (dry, applied)
    assert _items(dry) == _items(applied), (dry, applied)

    code, dry = _migrate(root)
    assert code == 0, dry
    code, applied = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, applied
    assert _nothing_to_do(dry), dry
    assert _nothing_to_do(applied), applied
    assert _items(dry) == _items(applied), (dry, applied)


def test_mas_2_folder_without_manifest_is_not_planned(tmp_path):
    # The real archive holds work folders with a document and no manifest. The apply
    # leaves such a folder alone, so the dry run must not plan a move for it.
    root = _planted_sample(tmp_path, only=())
    _write(root / ".compass" / "work" / "no-manifest" / "bug-report.md", "# Bug report\n")
    for flags in ((), ("--apply", "--i-have-a-copy"), ()):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        assert "no-manifest" not in _sections(out), (flags, out)
    assert (root / ".compass" / "work" / "no-manifest" / "bug-report.md").is_file()


# --- group B: a reported pair stays as it is ------------------------------------------


def _pair_item(out, slug, first, second):
    return [i for i in _issue_items(out, slug) if first in i and second in i]


def test_mas_3_pair_in_place_left_untouched(tmp_path):
    root = _planted_sample(tmp_path, only=(IN_PLACE,))
    stem_file, held_file = f"{_home(IN_PLACE)}/review-2.md", "notes/review-2.md"
    ids = ("ART-REVIEW-2", "ART-ROUND-2")
    fields = _pair_fields(root, IN_PLACE, ids)
    files = _bytes(root, stem_file, held_file)
    assert all(files.values()), files
    code, out = _migrate(root)
    assert code == 0, out
    assert len(_pair_item(out, IN_PLACE, stem_file, held_file)) == 1, out
    for flags in (("--apply", "--i-have-a-copy"), (), ("--apply", "--i-have-a-copy"), ()):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        assert len(_pair_item(out, IN_PLACE, stem_file, held_file)) == 1, (flags, out)
        assert _pair_fields(root, IN_PLACE, ids) == fields, (flags, out)
        assert _bytes(root, stem_file, held_file) == files, (flags, out)
        assert _merge_lines(out, IN_PLACE) == [], (flags, out)


def test_mas_4_pair_rename_left_untouched_rest_migrates(tmp_path):
    root = _planted_sample(tmp_path, only=(RENAME,))
    stem_file, held_file = f"{_home(RENAME)}/review.md", "notes/review-1.md"
    intent_beside = f".compass/work/{RENAME}/intent.md"
    intent_home = f"{_home(RENAME)}/intent.md"
    ids = ("ART-REVIEW", "ART-ROUND-1")
    fields = _pair_fields(root, RENAME, ids)
    files = _bytes(root, stem_file, held_file)
    intent = (root / intent_beside).read_bytes()
    code, out = _migrate(root)
    assert code == 0, out
    assert len(_pair_item(out, RENAME, stem_file, held_file)) == 1, out
    for run, flags in enumerate((("--apply", "--i-have-a-copy"), (), ("--apply", "--i-have-a-copy"))):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        assert _bytes(root, stem_file, held_file) == files, (flags, out)
        assert not (root / _home(RENAME) / "review-1.md").exists(), (flags, out)
        assert _pair_fields(root, RENAME, ids) == fields, (flags, out)
        assert len(_pair_item(out, RENAME, stem_file, held_file)) == 1, (flags, out)
        assert _merge_lines(out, RENAME) == [], (flags, out)
        if run == 0:
            assert any(n.startswith("moved intent.md -> %s" % intent_home)
                       for n in _sections(out).get(RENAME, [])), out
            entry = [e for e in _registry(root, RENAME) if e.get("kind") == "intent"]
            assert [e.get("path") for e in entry] == [intent_home], entry
            assert not (root / intent_beside).exists()
            assert (root / intent_home).read_bytes() == intent


def test_mas_5_pair_signal_survives_two_applies_on_the_sample(tmp_path):
    root = _planted_sample(tmp_path, only=(IN_PLACE, RENAME))
    pairs = {IN_PLACE: (("ART-REVIEW-2", "ART-ROUND-2"),
                        (f"{_home(IN_PLACE)}/review-2.md", "notes/review-2.md")),
             RENAME: (("ART-REVIEW", "ART-ROUND-1"),
                      (f"{_home(RENAME)}/review.md", "notes/review-1.md"))}
    fields = {slug: _pair_fields(root, slug, ids) for slug, (ids, _f) in pairs.items()}
    files = {slug: _bytes(root, *rels) for slug, (_i, rels) in pairs.items()}
    seen = []
    for flags in ((), ("--apply", "--i-have-a-copy"), (), ("--apply", "--i-have-a-copy"), ()):
        code, out = _migrate(root, *flags)
        assert code == 0, out
        items = []
        for slug, (_ids, rels) in pairs.items():
            found = _pair_item(out, slug, *rels)
            assert len(found) == 1, (slug, flags, out)
            items += found
            assert _merge_lines(out, slug) == [], (slug, flags, out)
        seen.append(items)
    assert all(items == seen[0] for items in seen), seen
    for slug, (ids, rels) in pairs.items():
        assert _pair_fields(root, slug, ids) == fields[slug], slug
        assert _bytes(root, *rels) == files[slug], slug


# --- group C: the copy check judges each issue folder -----------------------------------


def _tree(root):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts}


def _copy_lines(out):
    return [ln.strip() for ln in out.splitlines() if ln.strip().startswith("cp -R")]


def test_mas_6_one_committed_file_per_root_is_refused_on_the_sample(tmp_path):
    root = _planted_sample(tmp_path, only=(BOTH,))
    code, dry = _migrate(root)
    assert code == 0 and _sections(dry), dry
    work_file = root / ".compass" / "work" / BOTH / "technical-design.md"
    docs_file = root / _home(BOTH) / "technical-design.md"
    _git(root, "init", "-q", "-b", "main")
    _git(root, "add", "--", str(work_file.relative_to(root)), str(docs_file.relative_to(root)))
    _git(root, "commit", "-q", "-m", "one file under each root")
    assert len(_git(root, "ls-files").split()) == 2
    before = _tree(root)
    code, out = _migrate(root, "--apply")
    assert code == 2, out
    assert _tree(root) == before
    assert out.count("cannot be put back") == 1, out
    copies = _copy_lines(out)
    assert len(copies) == 2, out
    assert any(".compass/work" in ln for ln in copies), out
    assert any("docs/compass" in ln for ln in copies), out
    code, out = _migrate(root, "--apply", "--i-have-a-copy")
    assert code == 0, out


def _two_issues(folder):
    """A git repository holding two issues, alpha and beta, each with a work folder and
    a documents folder, every file committed. Each issue has `intent.md` beside its
    manifest, which the migrate moves, so a run that is not refused changes files."""
    for slug in ("alpha", "beta"):
        _plant(folder, slug, beside={"intent.md": f"# Intent of {slug}\n"},
               docs={"technical-design.md": f"# Design of {slug}\n"})
    _write(folder / _home("alpha") / "notes é 1.md", "# Notes\n")
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "base")


MAS_7_ROWS = [
    ("nothing changes", None, 0, None),
    ("untracked lock and evidence", lambda f: (
        _write(f / ".compass/work/beta/.render.lock", ""),
        _write(f / ".compass/work/beta/evidence/extra.json", "{}\n")), 0, None),
    ("untracked md in beta's documents folder",
     lambda f: _write(f / _home("beta") / "extra.md", "# Extra\n"),
     2, ("docs/compass", f"{CREATED}-beta")),
    ("staged md in beta's work folder", lambda f: (
        _write(f / ".compass/work/beta/notes.md", "# Notes\n"),
        _git(f, "add", "--", ".compass/work/beta/notes.md")),
     2, (".compass/work", "beta")),
    ("alpha's manifest edited", lambda f: (f / ".compass/work/alpha/manifest.yml").write_text(
        (f / ".compass/work/alpha/manifest.yml").read_text(encoding="utf-8") + "# edited\n",
        encoding="utf-8"),
     2, (".compass/work", "alpha")),
    ("not a git repository", lambda f: shutil.rmtree(f / ".git"), 0, None),
]


def test_mas_7_folder_restorable_only_when_head_holds_it(tmp_path):
    for number, (label, change, code_wanted, named) in enumerate(MAS_7_ROWS):
        folder = tmp_path / f"row-{number}" / "project"
        _two_issues(folder)
        code, dry = _migrate(folder)
        assert code == 0 and {"alpha", "beta"} <= set(_sections(dry)), (label, dry)
        if change:
            change(folder)
        before = _tree(folder)
        code, out = _migrate(folder, "--apply")
        assert code == code_wanted, (label, out)
        if code_wanted == 0:
            assert "cannot be put back" not in out, (label, out)
            continue
        assert _tree(folder) == before, (label, out)
        root_name, issue_folder = named
        refused = [ln for ln in out.splitlines() if "cannot be restored" in ln]
        assert len(refused) == 1 and root_name in refused[0], (label, out)
        assert refused[0].rsplit(": ", 1)[1] == issue_folder, (label, out)
        copies = _copy_lines(out)
        assert len(copies) == 1 and root_name in copies[0], (label, out)


def test_mas_8_refusal_readable_with_many_folders(tmp_path):
    folder = tmp_path / "project"
    _write(folder / "README.md", "# Project\n")
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "README.md")
    _git(folder, "commit", "-q", "-m", "base")
    slugs = ["issue-%d" % n for n in (7, 3, 1, 6, 2, 5, 4)]
    for slug in slugs:
        _plant(folder, slug, beside={"intent.md": f"# Intent of {slug}\n"},
               docs={"technical-design.md": f"# Design of {slug}\n"})
    code, dry = _migrate(folder)
    assert code == 0 and set(slugs) <= set(_sections(dry)), dry
    before = _tree(folder)
    code, out = _migrate(folder, "--apply")
    assert code == 2, out
    assert _tree(folder) == before
    assert out.count("cannot be put back") == 1, out
    copies = _copy_lines(out)
    assert len(copies) == 2, out
    assert any(".compass/work" in ln for ln in copies) and any("docs/compass" in ln
                                                               for ln in copies), out
    first_five = sorted(slugs)[:5]
    for root_name, names in ((".compass/work", first_five),
                             ("docs/compass", [f"{CREATED}-{s}" for s in first_five])):
        line = next((ln for ln in out.splitlines() if "cannot be restored" in ln
                     and root_name in ln), "")
        assert "7 issue folders cannot be restored" in line, out
        assert line.endswith(": " + ", ".join(names) + ", and 2 more"), line
    flat = " ".join(out.split())
    assert "commit those folders or take a copy, then re-run with --i-have-a-copy" in flat, out


def _opening(out):
    """The refusal's first sentence block: everything before the per-root lines."""
    return " ".join(out.split("\n  ", 1)[0].split())


def test_mas_12_refusal_opening_says_git_could_not_be_asked(tmp_path):
    # A git whose listing calls fail, inside a repository: the check refuses, and the
    # opening gives that as the reason, not only the per-root line.
    folder = tmp_path / "project"
    _two_issues(folder)
    fake = tmp_path / "fake-git"
    real = shutil.which("git")
    assert real, "git is not on PATH"
    _write(fake / "git", "#!/bin/sh\nfor a in \"$@\"; do case \"$a\" in ls-tree|status) "
                         "echo \"fake git: $a failed\" >&2; exit 128;; esac; done\n"
                         f"exec '{real}' \"$@\"\n")
    (fake / "git").chmod(0o755)
    before = _tree(folder)
    code, out = _migrate(folder, "--apply", path_first=fake)
    assert code == 2, out
    assert _tree(folder) == before
    assert "git could not be asked" in _opening(out), out
    # With git working, a refusal for an untracked file does not say git failed.
    _write(folder / _home("beta") / "extra.md", "# Extra\n")
    code, out = _migrate(folder, "--apply")
    assert code == 2, out
    assert "git could not be asked" not in out, out


def _refused_and_kept(folder, path, text):
    """`--apply` without the flag refuses, changes nothing, and `path` still holds `text`."""
    before = _tree(folder)
    code, out = _migrate(folder, "--apply")
    assert code == 2, out
    assert _tree(folder) == before, out
    assert path.read_text(encoding="utf-8") == text, out
    return out


def test_mas_13_git_failure_inside_a_repository_refuses(tmp_path):
    # A repository whose config git cannot read: every git call exits non-zero. That is
    # not "outside git", so an uncommitted edit must not be lost to the apply.
    folder = tmp_path / "project"
    _two_issues(folder)
    manifest = folder / ".compass/work/alpha/manifest.yml"
    edited = manifest.read_text(encoding="utf-8") + "# edited, not committed\n"
    manifest.write_text(edited, encoding="utf-8")
    (folder / ".git" / "config").write_text("[core\nthis is not a config\n", encoding="utf-8")
    out = _refused_and_kept(folder, manifest, edited)
    assert "git could not be asked" in out, out


def test_mas_14_registered_file_in_a_subfolder_is_judged(tmp_path):
    # The migrate edits a verification report wherever the registry puts it, so an
    # untracked report in a subfolder of a documents folder cannot be restored.
    folder = tmp_path / "project"
    report = f"{_home('alpha')}/reports/verification-report.md"
    _plant(folder, "alpha", artifacts=[{"id": "ART-VERIFICATION_REPORT",
                                        "kind": "verification-report", "status": "draft",
                                        "path": report}],
           docs={"technical-design.md": "# Design of alpha\n"})
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "base")
    text = "# Verification report\n\n## Definition of Done\n\n- [ ] Every scenario has a test.\n"
    _write(folder / report, text)
    out = _refused_and_kept(folder, folder / report, text)
    line = next((ln for ln in out.splitlines() if "cannot be restored" in ln), "")
    assert "docs/compass" in line and line.endswith(f"{CREATED}-alpha"), out


def test_mas_15_assume_unchanged_edit_is_judged_by_its_bytes(tmp_path):
    # git status does not report a file flagged assume-unchanged, so only a comparison
    # of the bytes on disk with the HEAD blob sees the edit.
    folder = tmp_path / "project"
    _two_issues(folder)
    rel = ".compass/work/alpha/manifest.yml"
    _git(folder, "update-index", "--assume-unchanged", rel)
    manifest = folder / rel
    edited = manifest.read_text(encoding="utf-8") + "# edited, flagged unchanged\n"
    manifest.write_text(edited, encoding="utf-8")
    assert _git(folder, "status", "--porcelain") == ""
    out = _refused_and_kept(folder, manifest, edited)
    line = next((ln for ln in out.splitlines() if "cannot be restored" in ln), "")
    assert ".compass/work" in line and line.endswith(": alpha"), out


def test_mas_16_git_missing_inside_a_repository_refuses(tmp_path):
    # A `.git` folder on disk and no git on PATH: there is a repository, and git cannot
    # be asked about it, so an uncommitted edit must not be lost to the apply.
    folder = tmp_path / "project"
    _two_issues(folder)
    manifest = folder / ".compass/work/alpha/manifest.yml"
    edited = manifest.read_text(encoding="utf-8") + "# edited, not committed\n"
    manifest.write_text(edited, encoding="utf-8")
    no_git = tmp_path / "no-git-on-path"
    no_git.mkdir()
    before = _tree(folder)
    code, out = _migrate(folder, "--apply", path_only=no_git)
    assert code == 2, out
    assert _tree(folder) == before, out
    assert manifest.read_text(encoding="utf-8") == edited, out
    assert "git could not be asked" in out, out


def test_mas_17_registered_file_outside_both_roots_is_not_judged(tmp_path):
    # The migrate never edits a registered file outside .compass/work and docs/compass,
    # so an untracked one there does not stop the apply.
    folder = tmp_path / "project"
    _plant(folder, "alpha", artifacts=[{"id": "ART-ROUND-1", "kind": "review", "round": 1,
                                        "status": "draft", "path": "notes/review-1.md"}],
           docs={"technical-design.md": "# Design of alpha\n"})
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "base")
    notes = folder / "notes" / "review-1.md"
    _write(notes, "# Review 1\n")
    code, out = _migrate(folder, "--apply")
    assert code == 0, out
    assert "cannot be put back" not in out, out
    assert notes.read_text(encoding="utf-8") == "# Review 1\n"


# --- MCG: a root outside the repository, a map registered outside the project ----------


def _link_out(folder, rel, target):
    """Move the folder at `rel` in the project to `target` and leave a symbolic link to it."""
    shutil.move(str(folder / rel), str(target))
    os.symlink(target, folder / rel)


def _outside_line(out, root_name):
    return [ln for ln in out.splitlines() if "cannot be restored" in ln and root_name in ln]


def test_mcg_2_documents_root_outside_the_repository_is_refused(tmp_path):
    # Git cannot restore a file whose real path is outside the repository, and the
    # check must not take "no .git above the real folder" to mean "nothing to restore".
    folder = tmp_path / "project"
    _two_issues(folder)
    outside = tmp_path / "outside-docs"
    _link_out(folder, "docs/compass", outside)
    only_copy = outside / f"{CREATED}-alpha" / "uncommitted.md"
    _write(only_copy, "# The only copy\n")
    before, before_outside = _tree(folder), _tree(outside)
    code, out = _migrate(folder, "--apply")
    assert code == 2, out
    assert _tree(folder) == before and _tree(outside) == before_outside, out
    refused = _outside_line(out, "docs/compass")
    assert len(refused) == 1 and "outside the repository" in refused[0], out
    assert not _outside_line(out, ".compass/work"), out
    assert "outside the repository" in _opening(out), out
    code, out = _migrate(folder, "--apply", "--i-have-a-copy")
    assert code == 0, out
    assert only_copy.read_text(encoding="utf-8") == "# The only copy\n"


def test_mcg_3_work_root_outside_the_repository_is_refused(tmp_path):
    folder = tmp_path / "project"
    _two_issues(folder)
    outside = tmp_path / "outside-work"
    _link_out(folder, ".compass/work", outside)
    before, before_outside = _tree(folder), _tree(outside)
    code, out = _migrate(folder, "--apply")
    assert code == 2, out
    assert _tree(folder) == before and _tree(outside) == before_outside, out
    refused = _outside_line(out, ".compass/work")
    assert len(refused) == 1 and "outside the repository" in refused[0], out
    assert refused[0].endswith(": alpha, beta"), out


def test_mcg_4_linked_root_inside_the_repository_is_judged(tmp_path):
    # A link whose real path stays inside the repository is judged by git as before.
    folder = tmp_path / "project"
    _two_issues(folder)
    _link_out(folder, "docs/compass", folder / "kept-docs")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "documents behind a link")
    code, out = _migrate(folder, "--apply")
    assert code == 0, out
    assert "cannot be put back" not in out, out


def test_mcg_5_map_registered_outside_the_project_is_not_renamed(tmp_path):
    # The migrate changes no file outside the project, whatever the manifest names.
    folder = tmp_path / "project"
    _plant(folder, "alpha", artifacts=[{"id": "ART-DISTRIBUTION_MAP", "kind": "distribution-map",
                                        "status": "approved", "depth": "lightweight",
                                        "path": "../outside/distribution-map.md"}],
           docs={"technical-design.md": "# Design of alpha\n"})
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "base")
    outside = tmp_path / "outside"
    text = "# Map\n\n| Subtask | Brief |\n|---|---|\n| subtask-1 | x |\n"
    _write(outside / "distribution-map.md", text)
    entry_before = _registry(folder, "alpha")[0]
    runs = []
    for flags in ((), ("--apply",)):
        code, out = _migrate(folder, *flags)
        assert code == 0, out
        runs.append(out)
        assert sorted(p.name for p in outside.iterdir()) == ["distribution-map.md"], out
        assert (outside / "distribution-map.md").read_text(encoding="utf-8") == text
    for out in runs:
        assert ".v6.bak" not in "\n".join(_sections(out).get("alpha", [])), out
        totals = [ln.strip() for ln in out.splitlines() if "distribution maps to rename" in ln]
        assert all(ln.endswith(": 0") for ln in totals), out
    dry_items, applied_items = (_issue_items(out, "alpha") for out in runs)
    refused = [item for item in applied_items if "distribution map" in item]
    assert len(refused) == 1 and "is not renamed" in refused[0] \
        and "outside the project" in refused[0], runs[1]
    assert refused[0] in dry_items, runs[0]
    entry = _registry(folder, "alpha")[0]
    assert (entry.get("path"), entry.get("status")) == (entry_before["path"],
                                                         entry_before["status"])


def test_mcg_6_map_under_a_link_inside_the_project_is_renamed(tmp_path):
    # A documents folder linked to a folder inside the project keeps every file in the
    # project, so the stub rule renames a map there as it renames any other.
    folder = tmp_path / "project"
    _plant(folder, "alpha", artifacts=[{"id": "ART-DISTRIBUTION_MAP", "kind": "distribution-map",
                                        "status": "approved", "depth": "lightweight"}],
           docs={"distribution-map.md": "# Map\n\nSolo.\n"})
    _link_out(folder, "docs/compass", folder / "kept-docs")
    _git(folder, "init", "-q", "-b", "main")
    _git(folder, "add", "-A")
    _git(folder, "commit", "-q", "-m", "documents behind a link")
    renames = []
    for flags in ((), ("--apply",)):
        code, out = _migrate(folder, *flags)
        assert code == 0, out
        assert not [item for item in _issue_items(out, "alpha") if "distribution map" in item], out
        renames.append([n for n in _sections(out).get("alpha", []) if ".v6.bak" in n])
        assert "distribution maps to rename to distribution-map.md.v6.bak: 1" in out, out
    assert len(renames[0]) == len(renames[1]) == 1, renames
    kept = folder / "kept-docs" / f"{CREATED}-alpha"
    assert sorted(p.name for p in kept.iterdir()) == ["distribution-map.md.v6.bak"]


# --- the documents -------------------------------------------------------------------


def _flat(path):
    return " ".join(path.read_text(encoding="utf-8").split())


def test_mas_10_guide_and_adr_state_the_rules():
    guide = _flat(ROOT / "docs" / "upgrade-7-0-0.md")
    copy_first = guide.split("**Copy first.**", 1)[1].split("###", 1)[0]
    assert "judges each issue folder" in copy_first, copy_first
    assert "every file in it that the migrate can change" in copy_first, copy_first
    assert "committed and unchanged" in copy_first, copy_first
    assert "left as it is, entries and files, until a person settles it" in guide
    assert "A dry run after `--apply` reports what a second `--apply` would do" in guide
    adr = (ROOT / "architecture" / "decisions" /
           "ADR-056-the-migrate-maps-documents-by-a-table-and-registers-before-it-moves.md"
           ).read_text(encoding="utf-8")
    last = adr.rsplit("\n## ", 1)[1]
    heading, body = last.split("\n", 1)
    assert re.fullmatch(r"Amendment \(\d{1,2} [A-Z][a-z]+ \d{4}, third\)", heading), heading
    body = " ".join(body.split())
    assert "Decision 7 changes" in body and "the copy check judges each issue folder" in body
    assert "Decision 8" in body and "Second amendment" in body, body
    assert "a reported pair stays as it is" in body, body


def test_mas_18_guide_names_git_clean_to_undo_an_apply():
    # `git reset --hard` alone leaves the moved copies behind as untracked
    # files, so the guide must name `git clean` too, warn what it deletes,
    # and offer a dry run limited to the two folders the migrate touches.
    guide = _flat(ROOT / "docs" / "upgrade-7-0-0.md")
    copy_first = guide.split("**Copy first.**", 1)[1].split("###", 1)[0]
    assert "`git reset --hard`" in copy_first, copy_first
    assert "`git clean -fd -- .compass/work docs/compass`" in copy_first, copy_first
    assert "removes every untracked file" in copy_first, copy_first
    assert "`git clean -n -d -- .compass/work docs/compass`" in copy_first, copy_first


# --- the real archive is never touched ---------------------------------------------------


def test_mas_9_planted_sample_never_the_real_archive(tmp_path, monkeypatch):
    from archive import sample_root
    monkeypatch.setenv("COMPASS_FULL_ARCHIVE", "1")
    root = _planted_sample(tmp_path)
    assert _inside(root, tmp_path) and not _inside(root, ROOT), root
    sample = {p.name for p in (sample_root() / ".compass" / "work").iterdir() if p.is_dir()}
    held = {p.name for p in (root / ".compass" / "work").iterdir() if p.is_dir()}
    assert held == sample | set(PLANTED), held ^ (sample | set(PLANTED))
    real = ROOT / ".compass" / "work"
    own = {p.name for p in real.iterdir() if p.is_dir()} - sample if real.is_dir() else set()
    assert not own & held, own & held
    # Every subprocess call in this file goes through `_migrate` or `_git`, and only
    # `_migrate` names the CLI, so no test can run the migrate on another root.
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    callers = set()
    for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(function):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in ("subprocess", "os") \
                    and node.attr in ("run", "Popen", "call", "check_call", "check_output",
                                      "system", "popen", "execv", "execvp"):
                callers.add((function.name, "subprocess"))
            if isinstance(node, ast.Name) and node.id == "CLI":
                callers.add((function.name, "CLI"))
    assert callers <= {("_migrate", "subprocess"), ("_migrate", "CLI"), ("_git", "subprocess")}, \
        callers
    # The runner refuses this repository before it runs anything.
    with pytest.raises(AssertionError):
        _migrate(ROOT)
    with pytest.raises(AssertionError):
        _git(ROOT, "status")
