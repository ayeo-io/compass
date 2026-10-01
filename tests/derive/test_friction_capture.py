"""Tests for the ship-time friction-capture step (`compass _friction-capture`).

At ship time, a draft `friction:` list is assembled from signals the CLI
already computes (re-assessments, unrecorded re-assessments) plus an optional human note, and
written into the issue manifest (`TRC-A2`..`TRC-A5`). Capture is mechanism;
the human note is the only judgement input (ADR-001). It writes the friction
section and nothing that gates (no follow-up, no gate).

Uses the shared fixtures from tests/conftest.py: project, run_cli, make_task.
"""
from __future__ import annotations

import pathlib
import shutil

import yaml

FRAMEWORK_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _copy_signals(project):
    """Put the shipped signals.yml into the temp project's governance/ so the
    unrecorded re-assessments scan (scope_bloat_phrases) and threshold load can find it."""
    gov = project / "governance"
    src = FRAMEWORK_ROOT / "governance" / "signals.yml"
    if src.is_file() and not (gov / "signals.yml").is_file():
        shutil.copy(src, gov / "signals.yml")


def _base_body(slug, **overrides):
    body = {
        "task": slug,
        "created": "2026-05-20",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "standard",
    }
    body.update(overrides)
    return body


def _capture(run_cli, slug, *extra):
    return run_cli("_friction-capture", "--internal", "--issue", slug, *extra)


def test_reframe_seeds_misroute_friction(run_cli, make_task, project):
    """A recorded re-assessment seeds a derived mis-route friction entry whose
    observation carries the re-assessment's from_route, to_route and reason (`TRC-A2`)."""
    _copy_signals(project)
    task_dir = make_task("ft-reframe", _base_body(
        "ft-reframe",
        reframes=[{
            "from_route": "express", "to_route": "standard",
            "reason": "Build revealed three modules", "date": "2026-05-21",
        }],
    ))
    r = _capture(run_cli, "ft-reframe")
    assert r.returncode == 0, r

    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    friction = task.get("friction") or []
    assert friction, "expected a derived friction entry from the reframe"
    e = next(x for x in friction if x["source"] == "derived")
    assert e["category"] == "mis-route", e
    assert "express" in e["observation"] and "standard" in e["observation"], e
    assert "three modules" in e["observation"], e


def test_reframe_debt_seeds_derived_friction(run_cli, make_task, project):
    """Scope-bloat absorbed without a recorded re-assessment - unrecorded re-assessments - seeds a
    derived friction entry (`TRC-A3`)."""
    _copy_signals(project)
    task_dir = make_task("ft-debt", _base_body("ft-debt", reframes=[]))
    (task_dir / "devlog.md").write_text(
        "2026-05-20: more files than Plan estimated - scope grew\n",
        encoding="utf-8",
    )
    r = _capture(run_cli, "ft-debt")
    assert r.returncode == 0, r

    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    friction = task.get("friction") or []
    assert any(x["source"] == "derived" for x in friction), (
        f"expected a derived friction entry from reframe-debt; got {friction}")


def test_human_note_recorded(run_cli, make_task, project):
    """A note the author gives is recorded with source human, alongside
    any derived entries (`TRC-A4`)."""
    _copy_signals(project)
    task_dir = make_task("ft-human", _base_body(
        "ft-human",
        reframes=[{
            "from_route": "express", "to_route": "standard",
            "reason": "x", "date": "2026-05-21",
        }],
    ))
    r = _capture(run_cli, "ft-human",
                 "--note", "the pre-tool hook blocked a legitimate doc edit",
                 "--note-category", "tooling", "--note-phase", "build")
    assert r.returncode == 0, r

    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    friction = task.get("friction") or []
    human = [x for x in friction if x["source"] == "human"]
    derived = [x for x in friction if x["source"] == "derived"]
    assert human, f"expected a human-sourced entry; got {friction}"
    assert derived, "human note must sit alongside the derived entries"
    assert human[0]["category"] == "tooling", human
    assert "hook" in human[0]["observation"], human


def test_no_friction_lands_unchanged(run_cli, make_task, project):
    """An issue that hit no friction (no re-assessments, no debt, no note)
    records no friction, and capture adds nothing - recording nothing is valid (`TRC-A5`)."""
    _copy_signals(project)
    task_dir = make_task("ft-none", _base_body("ft-none", reframes=[]))
    r = _capture(run_cli, "ft-none")
    assert r.returncode == 0, r

    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    # Either no friction key, or an empty list - both are valid no-op states.
    assert not task.get("friction"), (
        f"expected no friction recorded; got {task.get('friction')}")


def test_capture_adds_no_backfill_or_gate(run_cli, make_task, project):
    """Capture writes only the friction section - never a follow-up or a
    gate. Friction is strategy-class and cannot become something that blocks
    ship (ADR-002) (`TRC-F1`)."""
    _copy_signals(project)
    task_dir = make_task("ft-nogate", _base_body(
        "ft-nogate",
        backfills=[],
        gates=[],
        reframes=[{
            "from_route": "express", "to_route": "standard",
            "reason": "x", "date": "2026-05-21",
        }],
    ))
    r = _capture(run_cli, "ft-nogate")
    assert r.returncode == 0, r

    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert task.get("friction"), "expected friction to be recorded"
    assert not task.get("follow_ups"), "capture must not add a backfill"
    assert not task.get("gates"), "capture must not add a gate"
