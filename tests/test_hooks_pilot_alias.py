"""The hooks pilot's alias helper gives one run id to every worker of a run.

pytest-xdist starts each worker as its own process, so a run id made at
import is one per worker, and two workers' counters both start at 1. The
helper reads the id xdist shares with all workers of one run, and puts the
worker's name in the alias, so two workers never give the same alias
(issue hooks-pilot-alias-run-id).
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ALIAS = Path(__file__).resolve().parent / "acceptance" / "hooks" / "alias.py"


def _load_as_worker(monkeypatch, run_uid, worker):
    """The helper as a fresh worker process would import it."""
    monkeypatch.setenv("PYTEST_XDIST_TESTRUNUID", run_uid)
    monkeypatch.setenv("PYTEST_XDIST_WORKER", worker)
    spec = importlib.util.spec_from_file_location(f"alias_{worker}", ALIAS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trc_001_two_workers_of_one_run_share_the_run_id_and_never_collide(monkeypatch):
    first = _load_as_worker(monkeypatch, "a1b2c3d4e5f60718", "gw0").Aliases()("matrix")
    second = _load_as_worker(monkeypatch, "a1b2c3d4e5f60718", "gw1").Aliases()("matrix")
    assert "a1b2c3d4" in first and "a1b2c3d4" in second
    assert first != second
    assert "gw0" in first and "gw1" in second
