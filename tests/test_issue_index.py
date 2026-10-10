"""The project index, `docs/compass/README.md` (issue `documents-carry-judgement`,
group G: DCJ-54 to DCJ-57).

Each test builds a temporary git repository (`pages_support`). Only the test of
DCJ-57 asks git about this checkout, and it reads nothing of `.compass/work` or the
issue folders (DCJ-63 proves it).
"""
from __future__ import annotations

import datetime
import re
import subprocess
from pathlib import Path

import pytest

import pages_support as ps
import rendered_blocks_support as sup
from pages_support import (CREATED, SLUG, add_issue, block, blocks, close_issue, docs_of,
                           manifest, page, run, set_fields, text_of)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

SECTIONS = ["Backlog", "Ready", "In progress", "In review", "Done in the last 30 days", "Closed"]


def index_path(root):
    return Path(root) / "docs" / "compass" / "README.md"


def _fixture(tmp_path):
    """One issue in each state, and two hand-written files in docs/compass/."""
    root = sup.project(tmp_path)
    add_issue(root, "b-one", status="backlog")
    add_issue(root, "r-one", scenarios=[{"id": "R-1", "title": "A", "intent": "INT-1",
                                          "tests": []}],
              stages={"refine": "skipped"})
    add_issue(root, "p-one", current_phase="implement")
    add_issue(root, "v-one", current_phase="verify")
    add_issue(root, "d-new", release_note="Adds the index")
    close_issue(root, "d-new", when="2026-10-05T10:00:00+00:00")
    add_issue(root, "d-recent")
    close_issue(root, "d-recent", when="2026-10-02T10:00:00+00:00")
    add_issue(root, "d-old")
    close_issue(root, "d-old", when="2026-08-26T10:00:00+00:00")
    add_issue(root, "np-one")
    close_issue(root, "np-one", when="2026-09-20T10:00:00+00:00", reason="not-planned")
    bad = ps.work_of(root, "bad-one")
    bad.mkdir(parents=True)
    (bad / "manifest.yml").write_text("schema_version: '2.0'\nissue: [unclosed\n", encoding="utf-8")
    docs = Path(root) / "docs" / "compass"
    (docs / "2026-08-26-first-note.md").write_text("# First note\n", encoding="utf-8")
    (docs / "2026-08-27-second-note.md").write_text("# Second note\n", encoding="utf-8")
    return root


def _rows(lines, section):
    """The table rows under the `### <section>` heading of the index block."""
    start = next(i for i, x in enumerate(lines) if x.startswith("### " + section))
    rows = []
    for line in lines[start + 1:]:
        if line.startswith("### "):
            break
        if line.startswith("| ") and not line.startswith("| Issue") and not line.startswith("|---"):
            rows.append(line)
    return rows


# --- DCJ-54 -----------------------------------------------------------------

def test_dcj_54_index_lists_every_issue_once_by_state(tmp_path):
    root = _fixture(tmp_path)
    code, out, err = ps.render_all(root)
    assert code == 1, out + err          # the unreadable manifest
    assert "bad-one" in out + err

    path = index_path(root)
    found = blocks(path)
    assert [k for k, _ in found] == ["index"]
    lines = found[0][1]
    headings = [x[4:].split(" (")[0] for x in lines if x.startswith("### ")]
    assert headings[:6] == SECTIONS
    assert headings[6:] == ["Unreadable", "Other documents"]

    def slugs(section):
        return [re.match(r"\| \[([^\]]+)\]", row).group(1) for row in _rows(lines, section)]

    assert sorted(slugs("Backlog")) == sorted(["b-one", SLUG])
    assert slugs("Ready") == ["r-one"]
    assert slugs("In progress") == ["p-one"]
    assert slugs("In review") == ["v-one"]
    assert sorted(slugs("Done in the last 30 days")) == ["d-new", "d-recent"]
    closed = _rows(lines, "Closed")
    assert sorted(re.match(r"\| \[([^\]]+)\]", r).group(1) for r in closed) == ["d-old", "np-one"]
    assert any("not-planned" in r for r in closed) and any("completed" in r for r in closed)
    # Every readable issue appears once, as a link to its page, with approach, stage, gates.
    everywhere = [re.match(r"\| \[([^\]]+)\]\(([^)]+)\)", x) for x in lines if x.startswith("| [")]
    names = [m.group(1) for m in everywhere]
    assert len(names) == len(set(names))
    assert SLUG in names
    row = next(x for x in lines if x.startswith("| [p-one]"))
    assert f"({CREATED}-p-one/README.md)" in row
    assert "regular" in row and "implement" in row and "0/0" in row
    text = "\n".join(lines)
    assert "bad-one" in text.split("### Unreadable", 1)[1].split("### ", 1)[0]
    other = text.split("### Other documents", 1)[1]
    assert "(2026-08-26-first-note.md)" in other and "(2026-08-27-second-note.md)" in other
    assert "Adds the index" in next(x for x in lines if x.startswith("| [d-new]"))
    assert "Adds the index" not in next(x for x in lines if x.startswith("| [d-recent]"))
    assert not re.search(r"(?<![\w.])/(Users|home|private|tmp|var)/", text)


# --- DCJ-55 -----------------------------------------------------------------

def test_dcj_55_window_ends_at_newest_completion(tmp_path, monkeypatch):
    root = _fixture(tmp_path)
    ps.render_all(root)
    before = index_path(root).read_bytes()

    shift = datetime.timedelta(days=60)
    real = datetime.datetime

    class Later(real):
        @classmethod
        def now(cls, tz=None):
            return real.now(tz) + shift

        @classmethod
        def utcnow(cls):
            return real.utcnow() + shift

        @classmethod
        def today(cls):
            return real.today() + shift

    class LaterDate(datetime.date):
        @classmethod
        def today(cls):
            return datetime.date.today() + shift

    import time
    real_time = time.time
    monkeypatch.setattr(datetime, "datetime", Later)
    monkeypatch.setattr(datetime, "date", LaterDate)
    monkeypatch.setattr(time, "time", lambda: real_time() + 60 * 86400)
    code, out, err = sup.inproc(root, monkeypatch, all_issues=True, issue=None)
    monkeypatch.undo()
    assert code == 1, out + err          # the unreadable manifest, not the clock
    assert index_path(root).read_bytes() == before

    code, out, err = run(root, "check", "--issue", SLUG, "--verbose")
    assert "PASS rendered-blocks-current" in out, out


# --- DCJ-56 -----------------------------------------------------------------

def test_dcj_56_stale_index_row_fails_that_issue(tmp_path):
    root = sup.project(tmp_path)
    add_issue(root, "ready-one", current_phase="verify")
    add_issue(root, "other-one", current_phase="verify")
    code, out, err = ps.render_all(root)
    assert code == 0, out + err
    clean_code, clean_out, _ = run(root, "check", "--issue", "ready-one", "--verbose")
    assert "PASS rendered-blocks-current" in clean_out, clean_out

    path = index_path(root)
    path.write_text(text_of(path).replace("| [ready-one]", "| [ready-one-edited]", 1),
                    encoding="utf-8")
    code, out, err = run(root, "check", "--issue", "ready-one", "--verbose")
    line = next(x for x in out.splitlines() if "rendered-blocks-current" in x)
    assert line.strip().startswith("ADVISORY"), line
    assert "docs/compass/README.md" in line and "index" in line
    assert code == clean_code, out
    code, out, err = run(root, "check", "--issue", "other-one", "--verbose")
    other = next(x for x in out.splitlines() if "rendered-blocks-current" in x)
    assert other.strip().startswith("PASS") and "docs/compass/README.md" not in other, other


# --- DCJ-57 -----------------------------------------------------------------

def test_dcj_57_repository_ignores_project_index():
    done = subprocess.run(["git", "check-ignore", "docs/compass/README.md"], cwd=REPO,
                          capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.strip() == "docs/compass/README.md", done
    tracked = subprocess.run(
        ["git", "ls-files", "docs/compass/2026-08-26-first-hour-intent.md",
         "docs/compass/2026-08-27-sdd-loop-spike.md"],
        cwd=REPO, capture_output=True, text=True).stdout.split()
    assert tracked == ["docs/compass/2026-08-26-first-hour-intent.md",
                       "docs/compass/2026-08-27-sdd-loop-spike.md"]
