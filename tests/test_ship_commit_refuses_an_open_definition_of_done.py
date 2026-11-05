"""`compass ship-commit` refuses to land while `dod-evidence-typed` fails (ADR-091).

Before 9.0.0 the landing ran `artifacts-approved`, a blocking check, and refused on
its failure. 9.0.0 removed that check with the document statuses. The landing now
runs `dod-evidence-typed` the same way: a Definition of Done with an open item
stops the landing, and a waiver that made the check advisory prints one line and
lets the landing go on. It runs only that check, not the whole of `compass check`.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_status_support as sup  # noqa: E402

NOTE = "Ship the feature."


def _ready(tmp_path, verify=None, assessment=None):
    """An issue created after 2026-11-04 whose live gates have all passed, with no
    Definition of Done item recorded, and one staged change. It is on the
    four-stage path (ADR-092), unless `verify` names its verify stage: then its
    manifest holds the keys 8.x stored, with that verify stage."""
    root = sup.project(tmp_path, assessment=assessment)
    body = sup.manifest(root)
    body["created"] = "2026-11-05"
    if verify is not None:
        from test_next_stage import assessed_before_the_path
        body.pop("evidence_required", None)
        old = assessed_before_the_path(body["assessment"])
        old.pop("evidence")
        body.update(old)
        body["stages"] = dict(body["stages"], verify=verify)
    for gate in body.get("gates") or []:
        gate["status"] = "pass"
    body["checkpoints"] = []
    body["changed_files"] = [{"path": "src/app.py", "scenarios": ["S-1"]}]
    sup.write_manifest(root, body)
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n")
    sup.git(root, "add", "src/app.py")
    return root


def test_an_open_definition_of_done_stops_the_landing(tmp_path):
    root = _ready(tmp_path)
    code, out, err = sup.run(root, "ship-commit", "--issue", sup.SLUG, "-m", "land it",
                             "--release-note", NOTE)
    assert code != 0, out + err
    assert "[definition-of-done-open]" in err, err
    assert "dod-evidence-typed" in err, err
    assert sup.git(root, "log", "-1", "--format=%s") == "base"
    assert not yaml.safe_load(sup.manifest_file(root).read_text()).get("land_commit")


def test_an_open_definition_of_done_stops_a_landing_at_head(tmp_path):
    root = _ready(tmp_path)
    sup.git(root, "commit", "-q", "-m", "the work")
    code, out, err = sup.run(root, "ship-commit", "--issue", sup.SLUG, "-m", "land it",
                             "--release-note", NOTE)
    assert code != 0, out + err
    assert "[definition-of-done-open]" in err, err
    assert not yaml.safe_load(sup.manifest_file(root).read_text()).get("land_commit")


def test_an_approach_that_owes_no_definition_of_done_lands(tmp_path):
    # An issue assessed before the path owes no Definition of Done when its
    # verify stage is not thorough.
    root = _ready(tmp_path, verify="lightweight")
    code, out, err = sup.run(root, "ship-commit", "--issue", sup.SLUG, "-m", "land it",
                             "--release-note", NOTE)
    assert code == 0, out + err
    assert sup.git(root, "log", "-1", "--format=%s") == "land it"


def test_a_path_issue_that_owes_no_definition_of_done_lands(tmp_path):
    # On the path, a small, contained change owes no `definition-of-done`.
    root = _ready(tmp_path, assessment={"size": "small"})
    assert "definition-of-done" not in sup.manifest(root)["evidence_required"]
    code, out, err = sup.run(root, "ship-commit", "--issue", sup.SLUG, "-m", "land it",
                             "--release-note", NOTE)
    assert code == 0, out + err
    assert sup.git(root, "log", "-1", "--format=%s") == "land it"
