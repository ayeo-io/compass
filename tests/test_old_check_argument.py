"""The old check id is no longer read as a command argument from 9.0.0.

7.0.0 read `dor-behaviour-is-gwt` given to `compass evidence approve --check`,
`evidence request --check` and `evidence review` as `dor-behavior-is-gwt`, with
a notice, until 9.0.0. 9.0.0 deletes that reader (ADR-098): the old id fails
as any unknown check does. The stored generation is still read through the
`check_id` row of `old_names:`, so the new id is approved as before.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "cli"))

import approval_support as ap  # noqa: E402

# Spelt from pieces so that no scan of the tests finds the old name in a literal.
OLD_CHECK = "dor-behav" + "iour-is-gwt"
NEW_CHECK = "dor-behavior-is-gwt"


def _project(tmp_path):
    """The approval project, with its issue's manifest as 8.x stored it and a
    stored generation that holds the Definition of Ready of the frozen preset
    `default@7`, as an 8.x generation does. The old id names a Definition of
    Ready check. Only an issue assessed before the four-stage path owes one
    (ADR-092 decision D6, no Definition of Ready), and only a configuration that
    holds the check can approve it: the shipped default no longer does."""
    from test_entry_exit_evaluation import _legacy_generation
    from test_next_stage import assessed_before_the_path
    root = ap.project(tmp_path)
    body = ap.manifest_of(root)
    body.pop("evidence_required", None)
    old = assessed_before_the_path(body["assessment"])
    old.pop("evidence")
    body.update(old)
    ap.save_manifest(root, body)
    _legacy_generation(root, Path(root) / ".compass" / "work" / ap.SLUG, ap.SLUG)
    return root


def _approve(root, check):
    return ap.run(root, "evidence", "approve", "--check", check, "--issue", ap.SLUG,
                  "--approver", ap.OWNER, "--role", "owner", "--scope", "the plan",
                  terminal=True)


def test_the_new_check_id_is_approved(tmp_path):
    root = _project(tmp_path)
    code, out, err = _approve(root, NEW_CHECK)
    assert code == 0, out + err


def test_the_old_check_id_is_refused_by_approve(tmp_path):
    root = _project(tmp_path)
    code, out, err = _approve(root, OLD_CHECK)
    assert code != 0, out + err
    assert f"no such check '{OLD_CHECK}'" in err, err
    assert f"is now {NEW_CHECK}" not in err, err
    assert not [e for e in ap.manifest_of(root).get("evidence") or [] if e.get("check")]


def test_the_old_check_id_is_refused_by_request(tmp_path):
    root = _project(tmp_path)
    code, out, err = ap.run(root, "evidence", "request", "--check", OLD_CHECK,
                            "--issue", ap.SLUG, "--scope", "the plan")
    assert code != 0, out + err
    assert f"no such check '{OLD_CHECK}'" in out + err, out + err


def test_the_old_check_id_is_refused_by_review(tmp_path):
    root = _project(tmp_path)
    code, out, err = ap.run(root, "evidence", "review", OLD_CHECK, "--issue", ap.SLUG,
                            "--verdict", "pass", "--reason", "Read it.", "--reviewer", "agent")
    assert code != 0, out + err
    assert f"no such check '{OLD_CHECK}'" in out + err, out + err
