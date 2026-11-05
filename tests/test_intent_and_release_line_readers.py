"""The release line in `compass release notes`.

The `release notes` verb lists the issues completed since a git reference
with each issue's `release_note`. It is a read: it writes no issue record.
9.0.0 derives no living spec (ADR-091), but a revision made before then still
holds one, and the verb reads it there to place an issue.

Each verb run happens in a fresh interpreter on a parser the test builds, so
the run shows which modules it loaded and never touches `cli/compass`.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli"
sys.path.insert(0, str(CLI))

SCENARIOS = [{"id": "S-1", "title": "the first scenario", "intent": "INT-1"},
             {"id": "S-2", "title": "the second scenario", "intent": "INT-1"}]

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def _git(root, *args):
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, env={**os.environ, **GIT_ENV})
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def _repo(root):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    _commit(root, "start", {"README.md": "start\n"})
    return root


def _commit(root, message, files):
    for rel, text in files.items():
        target = Path(root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        _git(root, "add", rel)
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _issue(root, slug, approach="regular", stamp="2026-10-08T09:00:00Z",
           status="done", close_reason="completed", **fields):
    task = Path(root) / ".compass" / "work" / slug
    task.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
            "delivery_approach": approach, "scenarios": SCENARIOS,
            "status": status, "close_reason": close_reason,
            "land_timestamp": stamp}
    body.update(fields)
    (task / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                       encoding="utf-8")


RUNNER = textwrap.dedent("""
    import argparse, sys
    sys.path.insert(0, {cli!r})
    from compass_pkg import release_notes
    from compass_pkg.core import CompassError
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command")
    release_notes.register(sub)
    try:
        args = parser.parse_args(sys.argv[1:])
    except SystemExit as stop:
        sys.stderr.write("PARSE_CACHE_LOADED=%s\\n"
                         % ("compass_pkg.parse_cache" in sys.modules))
        raise
    try:
        code = args.func(args) or 0
    except CompassError as exc:
        sys.stderr.write("compass: %s\\n" % exc)
        code = 2
    sys.stderr.write("PARSE_CACHE_LOADED=%s\\n"
                     % ("compass_pkg.parse_cache" in sys.modules))
    sys.exit(code)
""").format(cli=str(CLI))


def _notes(root, *argv, env=None):
    """(exit code, stdout, stderr without the module marker, parse cache loaded)."""
    done = subprocess.run(
        [sys.executable, "-I", "-c", RUNNER, "release", "notes", *argv],
        cwd=str(root), capture_output=True, text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", **(env or {})})
    *lines, marker = done.stderr.rstrip("\n").split("\n")
    assert marker.startswith("PARSE_CACHE_LOADED="), done.stderr
    return (done.returncode, done.stdout, "\n".join(lines),
            marker.endswith("True"))


def _tree_digest(root, *folders):
    digest = hashlib.sha256()
    for folder in folders:
        for path in sorted((Path(root) / folder).rglob("*")):
            if path.is_file():
                digest.update(str(path.relative_to(root)).encode())
                digest.update(path.read_bytes())
    return digest.hexdigest()


# --- release notes: which issues, in what order --------------------------------

def _tagged_repo(tmp_path):
    root = _repo(tmp_path / "project")
    before = _commit(root, "before the tag", {"a.txt": "a\n"})
    _git(root, "tag", "v1.0.0")
    return root, before


def test_irl_17_release_notes_since_tag(tmp_path):
    root, before = _tagged_repo(tmp_path)
    one = _commit(root, "one", {"one.txt": "1\n"})
    two = _commit(root, "two", {"two.txt": "2\n"})
    three = _commit(root, "three", {"three.txt": "3\n"})
    _issue(root, "old-issue", land_commit=before, release_note="Before the tag.",
           stamp="2026-09-01T09:00:00Z")
    _issue(root, "z-regular", land_commit=one, release_note="Adds the board.",
           stamp="2026-10-05T09:00:00Z")
    _issue(root, "b-fix", approach="quick-fix", land_commit=three,
           release_note="Fixes the title.", stamp="2026-10-07T09:00:00Z")
    _issue(root, "a-regular", land_commit=two, release_note="Lists the issues.",
           stamp="2026-10-07T09:00:00Z")
    status = _git(root, "status", "--porcelain", "--ignored")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "old-issue" not in out and "Before the tag." not in out
    headings = [line for line in out.splitlines() if line.startswith("### ")]
    assert headings == ["### z-regular (completed 2026-10-05)",
                        "### a-regular (completed 2026-10-07)",
                        "### b-fix (completed 2026-10-07)"]
    assert ("### z-regular (completed 2026-10-05)\n\nAdds the board.\n" in out)
    assert ("### a-regular (completed 2026-10-07)\n\nLists the issues.\n" in out)
    assert ("### b-fix (completed 2026-10-07)\n\nFixes the title.\n" in out)
    assert _git(root, "status", "--porcelain", "--ignored") == status


def test_irl_17_the_since_option_is_required(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    code, _, err, _ = _notes(root)
    assert code != 0 and "--since" in err


def test_irl_18_release_notes_no_release_line(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    one = _commit(root, "one", {"one.txt": "1\n"})
    two = _commit(root, "two", {"two.txt": "2\n"})
    three = _commit(root, "three", {"three.txt": "3\n"})
    _issue(root, "a-issue", land_commit=one, release_note="Adds the board.",
           stamp="2026-10-05T09:00:00Z")
    _issue(root, "b-issue", land_commit=two, stamp="2026-10-06T09:00:00Z")
    _issue(root, "c-issue", land_commit=three, release_note="Fixes the title.",
           stamp="2026-10-07T09:00:00Z")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "### b-issue (completed 2026-10-06)\n\nNo release line recorded.\n" in out
    assert out.rstrip("\n").splitlines()[-1] == "1 of 3 issues have no release line."


def test_irl_19_release_notes_exclusions_and_unknown_tag(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    c1 = _commit(root, "one", {"one.txt": "1\n"})
    c2 = _commit(root, "two", {"two.txt": "2\n"})
    c3 = _commit(root, "three", {"three.txt": "3\n"})
    _issue(root, "the-spike", approach="spike", land_commit=c1)
    _issue(root, "not-planned", land_commit=c2, close_reason="not-planned")
    _issue(root, "a-duplicate", land_commit=c3, close_reason="duplicate",
           duplicate_of="the-spike")
    _issue(root, "no-commit")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "### " not in out
    closing = out.rstrip("\n").splitlines()[-1]
    assert "1 completed issue" in closing and "no land commit" in closing
    assert "v1.0.0" in closing

    code, out, err, _ = _notes(root, "--since", "no-such-tag")
    assert code == 2
    assert "no-such-tag" in err and "not a git reference" in err
    assert "### " not in out


def test_irl_19_no_shipping_issue_since_the_tag_is_one_line(tmp_path):
    root, before = _tagged_repo(tmp_path)
    _issue(root, "old-issue", land_commit=before, stamp="2026-09-01T09:00:00Z")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    lines = out.rstrip("\n").splitlines()
    assert len(lines) == 1 and "no shipping issue completed since" in lines[0].lower()
    assert "v1.0.0" in lines[0]


def test_irl_19_an_option_shaped_reference_is_not_a_reference(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    _issue(root, "an-issue")
    code, out, err, _ = _notes(root, "--since=--output=x")
    assert code == 2 and "not a git reference" in err
    assert not (root / "x").exists()


# --- release notes: a squash merge ---------------------------------------------

def test_irl_25_release_notes_two_part_placement(tmp_path):
    root = _repo(tmp_path / "project")
    base = _git(root, "rev-parse", "HEAD")
    _commit(root, "the tag's spec", {
        "docs/system-spec.md": "### old-issue (completed 2026-09-01)\n\n- `S-1` x\n"})
    _git(root, "tag", "v1.0.0")
    # Two commits that main never reaches, as a squash merge leaves them.
    _git(root, "checkout", "-q", "-b", "side", base)
    old_commit = _commit(root, "old work", {"old.txt": "o\n"})
    squashed_commit = _commit(root, "squashed work", {"squashed.txt": "s\n"})
    _git(root, "checkout", "-q", "main")
    _commit(root, "squash merge", {
        "docs/system-spec.md": "### old-issue (completed 2026-09-01)\n\n- `S-1` x\n\n"
                               "### squashed-issue (completed 2026-10-08)\n\n- `S-1` y\n"})
    _issue(root, "squashed-issue", land_commit=squashed_commit,
           release_note="Adds the board.")
    _issue(root, "old-issue", land_commit=old_commit, release_note="Old.",
           stamp="2026-09-01T09:00:00Z")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "### squashed-issue (completed 2026-10-08)\n\nAdds the board.\n" in out
    assert "old-issue" not in out and "Old." not in out
    assert "could not be placed" not in out


def test_irl_25_the_archive_file_names_an_issue_too(tmp_path):
    root = _repo(tmp_path / "project")
    base = _git(root, "rev-parse", "HEAD")
    _commit(root, "the tag's archive", {
        "docs/system-spec-archive.md": "- **Source issue:** `old-issue`\n"})
    _git(root, "tag", "v1.0.0")
    _git(root, "checkout", "-q", "-b", "side", base)
    old_commit = _commit(root, "old work", {"old.txt": "o\n"})
    _git(root, "checkout", "-q", "main")
    _commit(root, "later", {"later.txt": "l\n"})
    _issue(root, "old-issue", land_commit=old_commit, release_note="Old.")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "old-issue" not in out


def test_irl_25_an_older_spec_names_an_issue_under_either_heading_word():
    # A spec derived before 6.0.0 says "landed" where a later one says "completed".
    from compass_pkg import shipped_issues
    text = ("## Current Behaviour\n\n### old-one (landed 2026-08-01)\n\n- `A-1` x\n\n"
            "### new-one (completed 2026-10-01)\n\n- `B-1` y\n\n"
            "### third (finished 2026-10-02)\n")
    assert shipped_issues.issues_named(text) == {"old-one", "new-one"}


def test_irl_25_an_issue_neither_part_places_is_counted(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    _git(root, "checkout", "-q", "-b", "side")
    lost = _commit(root, "elsewhere", {"lost.txt": "x\n"})
    _git(root, "checkout", "-q", "main")
    _commit(root, "later", {"later.txt": "l\n"})
    _issue(root, "lost-issue", land_commit=lost, release_note="Lost.")
    _issue(root, "bad-commit", land_commit="0123456789abcdef", release_note="Bad.")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "### " not in out
    assert "2 completed issues" in out.rstrip("\n").splitlines()[-1]


# --- release notes: public text ------------------------------------------------

def test_irl_29_release_notes_redacts_and_writes_nothing(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    one = _commit(root, "one", {"one.txt": "1\n"})
    private = root / ".compass" / "private"
    private.mkdir(parents=True)
    (private / "key.yml").write_text(yaml.safe_dump(
        {"rivals": {"R1": {"name": "Examplecorp"}}}), encoding="utf-8")
    (root / ".compass" / "config.yml").write_text(
        "record:\n  names_key: .compass/private/key.yml\n", encoding="utf-8")
    _issue(root, "a-issue", land_commit=one,
           release_note="Imports boards from Examplecorp.")
    (root / "docs").mkdir(exist_ok=True)
    (root / "docs" / "kept.md").write_text("kept\n", encoding="utf-8")
    before = _tree_digest(root, ".compass/work", "docs")
    code, out, err, loaded = _notes(root, "--since", "v1.0.0")
    assert code == 0, err
    assert "R1" in out and "Examplecorp" not in out
    assert _tree_digest(root, ".compass/work", "docs") == before
    assert loaded is False


def test_irl_29_a_configured_key_that_is_missing_stops_the_verb(tmp_path):
    root, _ = _tagged_repo(tmp_path)
    one = _commit(root, "one", {"one.txt": "1\n"})
    (root / ".compass").mkdir(exist_ok=True)
    (root / ".compass" / "config.yml").write_text(
        "record:\n  names_key: .compass/private/missing.yml\n", encoding="utf-8")
    _issue(root, "a-issue", land_commit=one, release_note="Anything.")
    code, out, err, _ = _notes(root, "--since", "v1.0.0")
    assert code == 2 and "### " not in out


def test_irl_29_the_module_does_not_import_the_parse_cache():
    done = subprocess.run(
        [sys.executable, "-I", "-c",
         f"import sys; sys.path.insert(0, {str(CLI)!r}); "
         "import compass_pkg.release_notes, compass_pkg.shipped_issues; "
         "sys.exit(1 if 'compass_pkg.parse_cache' in sys.modules "
         "or 'compass_pkg.flow' in sys.modules else 0)"],
        capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    source = (CLI / "compass_pkg" / "release_notes.py").read_text(encoding="utf-8")
    imports = [line for line in source.splitlines()
               if line.startswith(("import ", "from ", "    import ", "    from "))]
    assert not [line for line in imports if "parse_cache" in line or "flow" in line]


# --- the archive renders unchanged ---------------------------------------------

# --- the help text -------------------------------------------------------------

def test_irl_17_the_help_text_describes_the_verb():
    from compass_pkg.verb_help import VERB_DESCRIPTIONS
    text = VERB_DESCRIPTIONS["release notes"]
    for part in ("--since", "landing time", "slug", "no release line",
                 "could not be placed", "writes nothing"):
        assert part in text
