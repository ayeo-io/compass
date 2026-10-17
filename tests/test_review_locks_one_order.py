"""Two sessions that type `/compass:approve` on two issues at once both finish
(issue `review-locks-one-order`, board issue 145).

With nothing pending, `/compass:approve` marks every delegated approval
reviewed, on every issue a delegation names. The prompt hook takes each
issue's approval lock for that, and the locks wait with no timeout. When a
session took its own issue's lock first and the others after, two sessions on
two issues could each hold one lock and wait for the other's. The hook now
takes every lock it needs in one sorted order before it marks anything.

The test runs the two sessions in two threads of this process: `flock` locks
taken through two separate opens of a file exclude each other even in one
process. A barrier holds each thread just after the hook took its locks, so
the old order deadlocks on every run, not only on an unlucky one. The join
has a bounded timeout, so a regression fails the test rather than hanging it.

Scenario id: `TRC-001`.
"""
from __future__ import annotations

import shutil
import sys
import threading
import time
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import OWNER, SLUG, event, project  # noqa: E402

OTHER = "feature-b"
ARCHITECT = "compass:architect"

#: How long a thread waits at the barrier for the other one. Under one lock
#: order the second thread waits for the first thread's locks, so it never
#: reaches the barrier while the first is there; the first goes on alone.
BARRIER_WAIT = 0.5
#: How long the test waits for both commands together. A deadlock fails here.
JOIN_WAIT = 5


def _delegated(record_id):
    return {"id": record_id, "type": "human-approval", "check": "dod-reviewed",
            "decision": "approved", "approver": OWNER, "role": "owner",
            "via": "delegation", "approved_by_agent": ARCHITECT, "delegation": "DL-1",
            "timestamp": "2026-10-17T01:00:00Z"}


def _two_issues(root):
    """Issues `feature` and `feature-b`, each with one unreviewed approval
    made under a delegation that names both."""
    work = root / ".compass" / "work"
    shutil.copytree(work / SLUG, work / OTHER)
    for slug in (SLUG, OTHER):
        path = work / slug / "manifest.yml"
        body = yaml.safe_load(path.read_text(encoding="utf-8"))
        body["issue"] = slug
        body["evidence"] = [_delegated(f"EV-HUMAN-{slug.upper()}")]
        path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    folder = root / ".compass" / "delegations"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "DL-1.yml").write_text(yaml.safe_dump({
        "id": "DL-1", "agent": ARCHITECT, "delegated_by": OWNER,
        "until": "2026-10-17T08:00:00Z", "issues": {SLUG: 1, OTHER: 1},
        "forms": ["checks"], "created_via": "prompt", "session_id": "sess-0"}),
        encoding="utf-8")


def _reviewed(root, slug):
    path = root / ".compass" / "work" / slug / "manifest.yml"
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [r["id"] for r in body["evidence"] if r.get("reviewed_by") == OWNER]


def test_trc001_two_sessions_approve_at_once_and_both_finish(tmp_path, monkeypatch):
    from compass_pkg import prompt_approval
    root = project(tmp_path)
    _two_issues(root)

    # The barrier stands just after the hook took its locks, where each
    # session holds what it took and is about to ask for any lock it lacks.
    barrier = threading.Barrier(2)
    original = prompt_approval._refuse_used_prompt

    def held_then_go_on(session):
        try:
            barrier.wait(BARRIER_WAIT)
        except threading.BrokenBarrierError:
            pass
        return original(session)

    monkeypatch.setattr(prompt_approval, "_refuse_used_prompt", held_then_go_on)

    results = {}

    def approve(slug, session):
        try:
            results[slug] = prompt_approval.handle(
                event(root, command="compass:approve", args="", session=session,
                      prompt_id=str(uuid.uuid4())),
                {"COMPASS_ISSUE": slug}, plugin_root=str(ROOT))
        except BaseException as exc:          # noqa: BLE001 - reported by the assert
            results[slug] = exc

    # Daemon threads: a deadlocked pair cannot be stopped, and must not keep
    # the test run from exiting.
    threads = [threading.Thread(target=approve, args=(slug, f"sess-{slug}"), daemon=True)
               for slug in (SLUG, OTHER)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + JOIN_WAIT
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    stuck = [t.name for t in threads if t.is_alive()]
    assert not stuck, (f"the two /compass:approve commands deadlocked: {stuck} still "
                       f"waiting after {JOIN_WAIT}s")

    # The first command to take the locks marks both approvals reviewed. The
    # second marks what is left, or finds nothing and says so.
    marked = []
    for slug in (SLUG, OTHER):
        result = results[slug]
        assert not isinstance(result, BaseException), (slug, result)
        if result.block:
            assert "Nothing is waiting for your approval" in result.message, (slug, result)
        else:
            assert "delegated approval(s) reviewed" in result.message, (slug, result)
            marked.append(slug)
    assert marked, results
    assert _reviewed(root, SLUG) == [f"EV-HUMAN-{SLUG.upper()}"]
    assert _reviewed(root, OTHER) == [f"EV-HUMAN-{OTHER.upper()}"]
