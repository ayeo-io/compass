"""The quick fix's verification note, and the landing commit (issue
`documents-carry-judgement`, group D: DCJ-35 to DCJ-38 and DCJ-81).

Each test builds a temporary git repository that tracks `docs/compass` and drives
`cli/compass` the way a person does. Each test name starts with its scenario id.
No test reads or writes this checkout's own `.compass/work` or `docs/compass`
(DCJ-63 proves it).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pages_support as ps  # noqa: E402
import rendered_blocks_support as sup  # noqa: E402
import test_quick_fix_verbs as qf  # noqa: E402
from test_quick_fix_verbs import (GREET_CMD, _finish, _git, _manifest, _ready_to_finish,  # noqa: E402,F401
                                  _run, repo)

SLUG = "fix-greeting"


def _note(repo_, slug=SLUG):
    created = _manifest(repo_, slug)["created"]
    return repo_ / "docs" / "compass" / f"{created}-{slug}" / "verification-note.md"


def _three_files(repo_):
    """The fix changes three files: the greeting and two more."""
    (repo_ / "src").mkdir(exist_ok=True)
    (repo_ / "src" / "alpha.py").write_text("ALPHA = 1\n")
    (repo_ / "src" / "beta.py").write_text("BETA = 2\n")


def _finish_ok(repo_):
    _ready_to_finish(repo_, SLUG)
    _three_files(repo_)
    result = _finish(repo_, SLUG)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


# --- DCJ-35 -----------------------------------------------------------------

def test_dcj_35_finish_writes_one_screen_verification_note(repo):
    _ready_to_finish(repo, SLUG)
    # `compass approach show` prints three lines by contract; the artifacts the approach earns
    # are listed by `compass approach evaluate`, and the manifest holds them.
    shown = _run(repo, "approach", "evaluate", "--issue", SLUG, "--json")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    earned = {a["kind"]: a["depth"] for a in json.loads(shown.stdout)["artifacts"]}
    assert earned.get("verification-note") == "lightweight", earned
    assert any(a["kind"] == "verification-note" for a in _manifest(repo, SLUG)["artifacts"])
    _three_files(repo)
    result = _finish(repo, SLUG)
    assert result.returncode == 0, result.stdout + result.stderr

    note = _note(repo)
    assert note.is_file()
    found = ps.blocks(note)
    assert [k for k, _ in found] == ["verification-note"]
    text = "\n".join(found[0][1])
    assert "TRC-001" in text
    assert "tests/test_greeting.py::test_greeting_says_hello" in text
    assert "red-TRC-001.json" in text and "green-TRC-001.json" in text
    for gate in ("verify.correctness", "verify.governance", "verify.traceability"):
        assert gate in text and "pass" in next(x for x in text.splitlines() if gate in x)
    for path in ("data/greeting.txt", "src/alpha.py", "src/beta.py"):
        assert path in text
    assert len(note.read_text().splitlines()) <= 40

    entry = next(a for a in _manifest(repo, SLUG)["artifacts"] if a["kind"] == "verification-note")
    assert entry["status"] == "approved" and entry["approved_by"] == "compass quick-fix finish"
    assert entry["path"].endswith("/verification-note.md")
    done = _manifest(repo, SLUG)
    names = _git(repo, "show", "--name-only", "--format=", done["land_commit"]).splitlines()
    assert any(n.endswith("/verification-note.md") for n in names), names
    assert done["status"] == "done" and done["close_reason"] == "completed"


# --- DCJ-36 -----------------------------------------------------------------

def test_dcj_36_release_line_only_when_recorded(repo):
    # A quick fix lands with a release line (ADR-065), so the note without one is
    # reached by removing the key and rendering, not by a finish that gives none.
    _finish_ok(repo)
    note = _note(repo)
    body = _manifest(repo, SLUG)
    del body["release_note"]
    qf._save_manifest(repo, SLUG, body)
    code = _run(repo, "issue", "render", "--issue", SLUG)
    assert code.returncode == 0, code.stdout + code.stderr
    assert "Release" not in note.read_text()

    body = _manifest(repo, SLUG)
    body["release_note"] = "Greetings now say hello."
    qf._save_manifest(repo, SLUG, body)
    code = _run(repo, "issue", "render", "--issue", SLUG)
    assert code.returncode == 0, code.stdout + code.stderr
    text = note.read_text()
    assert "Greetings now say hello." in text

    body = _manifest(repo, SLUG)
    del body["release_note"]
    qf._save_manifest(repo, SLUG, body)
    code = _run(repo, "issue", "render", "--issue", SLUG)
    assert code.returncode == 0, code.stdout + code.stderr
    assert "Greetings now say hello." not in note.read_text()
    assert "Release" not in note.read_text()


# --- DCJ-37 -----------------------------------------------------------------

def test_dcj_37_prose_above_note_block_survives(repo, monkeypatch):
    monkeypatch.setenv("COMPASS_RENDER_AFTER", "1")
    _finish_ok(repo)
    note = _note(repo)
    text = note.read_text()
    first, rest = text.split("<!-- compass:render verification-note -->", 1)
    prose = "A paragraph a person wrote.\n\nA second paragraph, kept as it is.\n\n"
    note.write_text(first + prose + "<!-- compass:render verification-note -->" + rest)

    result = _run(repo, "follow-up", "add", "FU-9", "--issue", SLUG, "--summary", "later")
    assert result.returncode == 0, result.stdout + result.stderr
    after = note.read_text()
    assert prose in after
    assert after.split("<!-- compass:render verification-note -->")[0] == first + prose
    check = _run(repo, "issue", "render", "--issue", SLUG, "--dry-run")
    assert check.returncode == 0 and "to rewrite docs" not in check.stdout, check.stdout


# --- DCJ-38 -----------------------------------------------------------------

def test_dcj_38_failing_quick_fix_gets_no_note(repo):
    _ready_to_finish(repo, SLUG)
    failing = ["--", "python3", "-c", "import sys; sys.exit(1)"]
    result = _finish(repo, SLUG, command=failing)
    assert result.returncode != 0, result.stdout + result.stderr
    assert not _note(repo).exists()
    entry = next(a for a in _manifest(repo, SLUG)["artifacts"] if a["kind"] == "verification-note")
    assert not entry.get("path")


# --- DCJ-81 -----------------------------------------------------------------

def _clean(repo_):
    return _git(repo_, "status", "--porcelain", "--", "docs/compass")


def test_dcj_81_landing_commit_holds_done_page(repo):
    (repo / "docs" / "compass").mkdir(parents=True)
    (repo / "docs" / "compass" / "README.md").write_text(
        "# Issues\n\n<!-- compass:render index -->\n<!-- /compass:render -->\n")
    _git(repo, "add", "docs")
    _git(repo, "commit", "-q", "-m", "track docs/compass")
    _ready_to_finish(repo, SLUG)
    body = _manifest(repo, SLUG)
    body["release_note"] = "Says hello."
    qf._save_manifest(repo, SLUG, body)
    result = _finish(repo, SLUG, "--release-note", "Says hello.")
    assert result.returncode == 0, result.stdout + result.stderr

    landed = _manifest(repo, SLUG)["land_commit"]
    names = _git(repo, "show", "--name-only", "--format=", landed).splitlines()
    created = _manifest(repo, SLUG)["created"]
    folder = f"docs/compass/{created}-{SLUG}"
    assert f"{folder}/verification-note.md" in names
    assert f"{folder}/README.md" in names
    assert "docs/compass/README.md" in names
    committed_page = _git(repo, "show", f"{landed}:{folder}/README.md")
    assert "done (completed)" in committed_page
    assert "Says hello." in _git(repo, "show", f"{landed}:{folder}/verification-note.md")
    index = _git(repo, "show", f"{landed}:docs/compass/README.md")
    assert SLUG in index and "Done in the last 30 days" in index
    assert _clean(repo) == "", _clean(repo)


def test_dcj_81_landing_commit_holds_done_page_regular(tmp_path):
    from test_ship_commit_refuses_unapproved import _approved, _ready, _ship
    root = sup.project(tmp_path, compass_yml={"schema": 1, "owner": "jed72"})
    _approved(root)
    sup.git(root, "add", "docs")
    sup.git(root, "commit", "-q", "-m", "track docs/compass")
    code, out, err = sup.render(root)
    assert code == 0, out + err
    sup.git(root, "add", "docs")
    sup.git(root, "commit", "-q", "--allow-empty", "-m", "render")
    _ready(root)
    code, out, err = _ship(root)
    assert code == 0, out + err

    folder = f"docs/compass/{sup.base.CREATED}-{sup.SLUG}"
    landed = sup.manifest(root)["land_commit"]
    names = sup.git(root, "show", "--name-only", "--format=", landed).splitlines()
    assert f"{folder}/README.md" in names, names
    assert "docs/compass/README.md" in names, names
    assert "done (completed)" in sup.git(root, "show", f"{landed}:{folder}/README.md")
    assert sup.git(root, "status", "--porcelain", "--", "docs/compass") == ""


# --- DCJ-97 -----------------------------------------------------------------

def test_dcj_97_a_hand_written_note_without_a_block_gets_the_block(repo):
    _ready_to_finish(repo, SLUG)
    _three_files(repo)
    note = _note(repo)
    note.parent.mkdir(parents=True, exist_ok=True)
    prose = "# My own notes\n\nWritten by a person before the finish.\n"
    note.write_text(prose, encoding="utf-8")
    result = _finish(repo, SLUG)
    text = note.read_text(encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert text.startswith(prose)
    assert [k for k, _ in ps.blocks(note)] == ["verification-note"], text
    assert "TRC-001" in text


# --- DCJ-99 -----------------------------------------------------------------

def test_dcj_99_finish_refuses_a_note_path_that_leaves_the_documents_folder(repo):
    _ready_to_finish(repo, SLUG)
    _three_files(repo)
    body = _manifest(repo, SLUG)
    for created in ("../../../elsewhere", "../..", "../not-docs"):
        body["created"] = created
        qf._save_manifest(repo, SLUG, body)
        result = _finish(repo, SLUG)
        text = result.stdout + result.stderr
        stray = [p for p in repo.parent.rglob("verification-note.md")]
        assert stray == [], (created, stray)
        assert result.returncode != 0, (created, text)
        assert "verification note" in text and "not written" in text, (created, text)
        assert _manifest(repo, SLUG).get("status") != "done", created
