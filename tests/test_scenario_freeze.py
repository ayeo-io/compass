"""The scenario freeze at the first red (ADR-095 decision 11).

On a path delivery issue the first `compass tdd-red` writes `scenario_freeze`
into the manifest: the time, the red record, the spec's path, the `sha256sum`
digest of its bytes and the scenario ids. It is never rewritten. Each red record
holds `spec_sha256` inside its `content_digest`. `compass check` prints a notice,
not a row, and the default view shows it only when the spec changed since the
freeze. An issue assessed before the path writes neither.

Issue: #355 [Read the ship approval from the merged PR review].
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

from test_checkpoint_outcomes import SLUG, manifest, run, write_manifest  # noqa: E402
from test_red_waits_for_scenario_approval import (RED, _issue, _reds, _spec,  # noqa: E402
                                                  _task_dir)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(path):
    return json.loads(path.read_text())


def _check(root, *extra):
    return run(root, "check", "--issue", SLUG, *extra)


def test_the_first_red_writes_the_freeze(tmp_path):
    root = _issue(tmp_path)
    assert "scenario_freeze" not in manifest(root)
    done = run(root, *RED)
    assert done.returncode == 0, done.stdout + done.stderr
    held = manifest(root)["scenario_freeze"]
    assert held["red"] == "evidence/" + _reds(root)[0].name
    assert held["spec"] == str(_spec(root).relative_to(root))
    assert held["spec_sha256"] == _sha(_spec(root))
    assert held["scenarios"] == ["TRC-001"]
    assert held["at"].endswith("Z")
    assert "frozen" in done.stdout, done.stdout
    from test_checkpoint_outcomes import schema_errors
    assert not schema_errors(manifest(root)), schema_errors(manifest(root))


def test_each_red_record_holds_the_spec_digest_inside_its_content_digest(tmp_path):
    from compass_pkg.red_first import content_digest
    root = _issue(tmp_path)
    assert run(root, *RED).returncode == 0
    record = _record(_reds(root)[0])
    assert record["spec_sha256"] == _sha(_spec(root))
    stamped = record.pop("content_digest")
    assert content_digest(record) == stamped
    record["spec_sha256"] = "0" * 64
    assert content_digest(record) != stamped


def test_the_freeze_is_never_rewritten(tmp_path):
    root = _issue(tmp_path)
    assert run(root, *RED).returncode == 0
    first = manifest(root)["scenario_freeze"]
    with _spec(root).open("a") as fh:
        fh.write("\nA line added after the first red.\n")
    assert run(root, *RED).returncode == 0
    assert manifest(root)["scenario_freeze"] == first
    # The later red names the spec it ran against.
    assert _record(_reds(root)[0])["spec_sha256"] == _sha(_spec(root)) != first["spec_sha256"]


def test_check_notes_a_spec_changed_since_the_freeze_without_a_row(tmp_path):
    root = _issue(tmp_path)
    assert run(root, *RED).returncode == 0
    frozen = manifest(root)["scenario_freeze"]["spec_sha256"]
    before = json.loads(_check(root, "--json").stdout)
    line = f"Scenarios: frozen at the red on record (sha256 {frozen[:12]})"
    assert line in before["notices"], before["notices"]
    # Unchanged, the default view leaves the notice out.
    unchanged = _check(root)
    assert "Scenarios:" not in unchanged.stdout

    with _spec(root).open("a") as fh:
        fh.write("\nA line added after the first red.\n")
    changed = _check(root)
    assert f"{line}; the spec has changed since" in changed.stdout, changed.stdout
    after = json.loads(_check(root, "--json").stdout)
    assert after["checks"] == before["checks"]
    assert (after["ran"], after["failed"]) == (before["ran"], before["failed"])
    assert changed.returncode == unchanged.returncode


def test_an_old_issue_has_no_freeze_and_its_red_keeps_its_shape(tmp_path):
    from test_next_stage import assessed_before_the_path
    root = _issue(tmp_path)
    body = manifest(root)
    body.pop("evidence_required", None)
    body.update(assessed_before_the_path(body["assessment"]))
    write_manifest(root, body)
    done = run(root, *RED)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "scenario_freeze" not in manifest(root)
    assert "spec_sha256" not in _record(_reds(root)[0])
    assert "Scenarios:" not in " ".join(json.loads(_check(root, "--json").stdout)["notices"])


def test_a_refused_red_writes_no_freeze(tmp_path):
    from test_checkpoint_outcomes import CRITICAL
    root = _issue(tmp_path, assessment=CRITICAL)
    assert run(root, *RED).returncode != 0
    assert "scenario_freeze" not in manifest(root)
    assert not (_task_dir(root) / ".red").exists()
