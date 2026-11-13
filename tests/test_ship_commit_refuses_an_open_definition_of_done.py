"""`compass ship-commit` refuses to land while `dod-evidence-typed` fails (ADR-091, ADR-099).

Before 9.0.0 the landing ran `artifacts-approved`, a blocking check, and refused on
its failure. 9.0.0 removed that check with the document statuses. Since ADR-099
the landing runs the whole of `compass check` first, so a Definition of Done with
an open item stops the landing through the failing check `dod-evidence-typed`.
A path issue owes a Definition of Done only where the project's `compass.yml`
adds it. The older refusal code `definition-of-done-open` is reached only after
`compass check` has passed.

Issue: ayeo-io/compass-delivery#353.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_status_support as sup  # noqa: E402
from test_quick_fix_verbs import _finish, _ready_to_finish, e2e, repo  # noqa: E402,F401

SLUG = sup.SLUG

NOTE = "Ship the feature."
#: A Definition of Done is owed only where the project asks for it (ADR-099
#: decision 9), here for every change.
DOD_SETTING = "require_evidence:\n  - when: {}\n    add: [definition-of-done]\n"


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


def _finished(repo, dod):
    """A started and finished path issue with its fix unstaged: `finish --no-commit`
    wrote the whole record. With `dod`, the project's `compass.yml` adds the
    Definition of Done, so `finish` says it is still owed."""
    if dod:
        (repo / "compass.yml").write_text(DOD_SETTING)
    _ready_to_finish(repo, SLUG)
    done = _finish(repo, SLUG, "--no-commit")
    if dod:
        assert done.returncode == 1, done.stdout + done.stderr
        assert "definition-of-done" in sup.manifest(repo, SLUG)["evidence_required"]
        # Resolve the requirement rows, so the one thing still open is the
        # Definition of Done items.
        spec = next((repo / "docs" / "compass").glob(f"*-{SLUG}/acceptance-criteria.md"))
        spec.write_text(re.sub(r"^\| (\w+) \| \| \|$", r"| \1 | | no effect here |",
                               spec.read_text(), flags=re.M))
        again = _finish(repo, SLUG, "--no-commit")
        assert again.returncode == 1, again.stdout + again.stderr
    else:
        assert done.returncode == 0, done.stdout + done.stderr
    sup.git(repo, "add", "data/greeting.txt")
    return repo


def _land(repo):
    return sup.run(repo, "ship-commit", "--issue", SLUG, "-m", "land it",
                   "--release-note", NOTE)


def test_an_open_definition_of_done_stops_the_landing(repo):
    """The landing runs `compass check` first (ADR-099), which fails
    `dod-evidence-typed` while an item is open, so the refusal names that check."""
    _finished(repo, dod=True)
    head = sup.git(repo, "log", "-1", "--format=%s")
    code, out, err = _land(repo)
    assert code != 0, out + err
    assert "`compass check` fails" in err, err
    assert "FAIL dod-evidence-typed" in err, err
    assert sup.git(repo, "log", "-1", "--format=%s") == head
    assert not yaml.safe_load(sup.manifest_file(repo, SLUG).read_text()).get("land_commit")


def test_an_open_definition_of_done_stops_a_landing_at_head(repo):
    _finished(repo, dod=True)
    sup.git(repo, "commit", "-q", "-m", "the work")
    code, out, err = _land(repo)
    assert code != 0, out + err
    assert "FAIL dod-evidence-typed" in err, err
    assert not yaml.safe_load(sup.manifest_file(repo, SLUG).read_text()).get("land_commit")


def test_an_approach_that_owes_no_definition_of_done_lands(tmp_path):
    # An issue assessed before the path owes no Definition of Done when its
    # verify stage is not thorough.
    root = _ready(tmp_path, verify="lightweight")
    code, out, err = sup.run(root, "ship-commit", "--issue", sup.SLUG, "-m", "land it",
                             "--release-note", NOTE)
    assert code == 0, out + err
    assert sup.git(root, "log", "-1", "--format=%s") == "land it"


def test_a_path_issue_that_owes_no_definition_of_done_lands(repo):
    # On the path no change owes a `definition-of-done` unless the project asks.
    _finished(repo, dod=False)
    assert "definition-of-done" not in sup.manifest(repo, SLUG)["evidence_required"]
    assert e2e.person_approves(repo)
    code, out, err = _land(repo)
    assert code == 0, out + err
    assert sup.git(repo, "log", "-1", "--format=%s") == "land it"
