"""`compass flow` as a delivery board, with a static HTML export.

The board shows each in-progress issue's route, stage, gates passed and
whether its newest test record still matches its files; sets stale evidence
and parked issues apart; shows the queue with its age, what landed in the
last seven days and the most common friction among them. `--html` writes
the same board as one static page. It stays advisory and under two seconds
(issue #354; the design records the architect's four changes).

Scenario ids: DB-1 to DB-5 (issue `delivery-board`).
"""
from __future__ import annotations

import datetime
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

from test_quick_fix_verbs import (GREET_CMD, _ready_to_finish, _run,  # noqa: F401
                                  _write_greeting, repo)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import binding, core  # noqa: E402
from compass_pkg.flow import board  # noqa: E402

TODAY = datetime.date.today()


def _manifest(root, slug, **fields):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": "2.0", "issue": slug,
            "created": fields.pop("created", TODAY.isoformat()),
            "status": fields.pop("status", "queued")}
    data.update(fields)
    (d / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    return d


def _green(repo):
    r = _run(repo, "tdd-green", "--issue", "fix-greeting", "--scenario",
             "TRC-001", *GREET_CMD)
    assert r.returncode == 0, r.stdout + r.stderr


def _row(rows, slug):
    return next(r for r in rows if r["slug"] == slug)


# --- DB-1 -------------------------------------------------------------------

def test_db_1_evidence_state_is_none_fresh_or_stale(repo):
    _ready_to_finish(repo, "fix-greeting")
    task_dir = repo / ".compass" / "work" / "fix-greeting"
    task, _ = core.load_manifest(str(task_dir))
    # A red is not evidence of the tree passing: only a registered green is.
    assert binding.evidence_state(task, str(task_dir)) == "none"
    _green(repo)
    task, _ = core.load_manifest(str(task_dir))
    assert binding.evidence_state(task, str(task_dir)) == "fresh"
    _write_greeting(repo, "Hello, %s!\n\n")
    assert binding.evidence_state(task, str(task_dir)) == "stale"
    _manifest(repo, "no-records", status="active")
    task, _ = core.load_manifest(str(repo / ".compass" / "work" / "no-records"))
    assert binding.evidence_state(task, str(repo / ".compass" / "work" / "no-records")) == "none"


def test_db_1_an_in_progress_row_shows_stage_gates_and_evidence(repo):
    _ready_to_finish(repo, "fix-greeting")
    _green(repo)
    data = board(str(repo / ".compass" / "work"), today=TODAY)
    row = _row(data["in_progress"], "fix-greeting")
    assert row["delivery_approach"] == "quick-fix"
    assert row["stage"]
    assert row["gates"] == "0/3", row
    assert row["evidence"] == "fresh", row


# --- DB-2 -------------------------------------------------------------------

def test_db_2_stale_evidence_and_parked_issues_are_set_apart(repo):
    _ready_to_finish(repo, "fix-greeting")
    _green(repo)
    _write_greeting(repo, "Hello, %s!\n\n")
    _manifest(repo, "waiting", status="parked", parked_reason="needs a decision")
    data = board(str(repo / ".compass" / "work"), today=TODAY)
    assert "fix-greeting" in [r["slug"] for r in data["stale"]]
    assert "fix-greeting" not in [r["slug"] for r in data["in_progress"]]
    assert [r["slug"] for r in data["held"]] == ["waiting"]
    text = _run(repo, "flow").stdout
    assert "STALE EVIDENCE" in text and "HELD" in text, text


# --- DB-3 -------------------------------------------------------------------

def test_db_3_queue_landed_this_week_and_friction(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    old = (TODAY - datetime.timedelta(days=30)).isoformat()
    _manifest(root, "old-idea", created=old)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    long_ago = "2026-01-01T00:00:00+00:00"
    friction = [{"category": "tooling", "observation": "x"},
                {"category": "tooling", "observation": "y"},
                {"category": "spec", "observation": "z"}]
    _manifest(root, "shipped-today", status="landed", land_timestamp=now,
              friction=friction)
    _manifest(root, "shipped-long-ago", status="landed", land_timestamp=long_ago,
              friction=[{"category": "spec", "observation": "w"}] * 5)
    data = board(str(root / ".compass" / "work"), today=TODAY)
    queued = _row(data["next_up"], "old-idea")
    assert queued["age_days"] == 30, queued
    assert [r["slug"] for r in data["landed_this_week"]] == ["shipped-today"]
    assert data["friction"] == {"category": "tooling", "count": 2}


# --- DB-4 -------------------------------------------------------------------

def test_db_4_the_html_page_has_the_sections_and_escapes_every_value(repo, tmp_path):
    _ready_to_finish(repo, "fix-greeting")
    _manifest(repo, "waiting", status="parked",
              parked_reason='<script>alert("x")</script> & more')
    out = tmp_path / "board.html"
    r = _run(repo, "flow", "--html", str(out))
    assert r.returncode == 0, r.stdout + r.stderr
    page = out.read_text(encoding="utf-8")
    for heading in ("In progress", "Held", "Next up", "Landed this week"):
        assert heading in page, heading
    assert "fix-greeting" in page and "waiting" in page
    assert "<script" not in page.lower()
    assert "&lt;script&gt;" in page and "&amp; more" in page
    assert "http://" not in page and "https://" not in page


def test_db_4_html_refuses_a_directory_and_compass_folders(repo, tmp_path):
    for target in (tmp_path, repo / ".compass" / "board.html",
                   repo / "docs" / "compass" / "board.html"):
        r = _run(repo, "flow", "--html", str(target))
        assert r.returncode != 0, (target, r.stdout + r.stderr)
    assert not (repo / ".compass" / "board.html").exists()


# --- DB-5 -------------------------------------------------------------------

@pytest.mark.serial
def test_db_5_the_board_is_quick_over_many_issues(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    statuses = ["landed"] * 260 + ["queued"] * 50 + ["abandoned"] * 25 + \
               ["parked"] * 5 + ["active"] * 5
    for i, status in enumerate(statuses):
        _manifest(root, f"issue-{i:03d}", status=status,
                  delivery_approach="feature",
                  stages={"assess": "full", "define": "full", "plan": "full",
                          "implement": "full", "verify": "full", "ship": "full"},
                  gates=[{"id": "verify.correctness", "status": "pending"}],
                  land_timestamp="2026-09-01T00:00:00+00:00")
    start = time.monotonic()
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "flow"],
                       cwd=root, capture_output=True, text=True)
    elapsed = time.monotonic() - start
    assert r.returncode == 0, r.stdout + r.stderr
    assert elapsed < 2.0, f"compass flow took {elapsed:.2f}s over 345 issues"


# --- DB-6 -------------------------------------------------------------------

def test_db_6_a_malformed_manifest_does_not_stop_the_board(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    _manifest(root, "fine", status="queued")
    _manifest(root, "bad-friction", status="landed",
              land_timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              friction=5)
    _manifest(root, "bad-gates", status="active", gates=5)
    _manifest(root, "bad-status", status=["a", "b"])
    _manifest(root, "bad-assessment", status="queued", assessment="a string")
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "flow"],
                       cwd=root, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Traceback" not in r.stderr, r.stderr
    assert "fine" in r.stdout
    for slug in ("bad-gates", "bad-status"):
        row = [l for l in r.stdout.splitlines() if slug in l]
        assert row and ("unreadable" in row[0].lower() or "malformed" in row[0].lower()), r.stdout


def test_db_4_html_refuses_symlinked_and_case_variant_paths(repo, tmp_path):
    (repo / ".compass").mkdir(exist_ok=True)
    (repo / "docs" / "compass").mkdir(parents=True, exist_ok=True)
    link = tmp_path / "into-compass"
    link.symlink_to(repo / ".compass")
    sub = repo / "sub"
    sub.mkdir()
    (sub / "link").symlink_to(repo / "docs" / "compass")
    for target, cwd in ((link / "board.html", repo), ("link/board.html", sub),
                        (repo / ".COMPASS" / "board.html", repo),
                        (repo / "Docs" / "Compass" / "board.html", repo)):
        r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "flow",
                            "--html", str(target)], cwd=cwd, capture_output=True, text=True)
        assert r.returncode != 0, (target, r.stdout + r.stderr)
    assert not list((repo / ".compass").glob("board.html"))
    assert not list((repo / "docs" / "compass").glob("board.html"))


def test_dm_1_the_queue_age_test_holds_across_midnight(tmp_path, monkeypatch):
    """CI ran this file across midnight UTC once: `TODAY` was set before it
    and `board()` read the clock after it, so a 30-day-old issue read 31."""
    from compass_pkg import flow

    class _Tomorrow(datetime.date):
        @classmethod
        def today(cls):
            return TODAY + datetime.timedelta(days=1)

    real = datetime

    class _Clock:
        date = _Tomorrow
        datetime = real.datetime
        timezone = real.timezone
        timedelta = real.timedelta

    monkeypatch.setattr(flow, "datetime", _Clock)
    test_db_3_queue_landed_this_week_and_friction(tmp_path)
