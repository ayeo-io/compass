"""Fixes from the review of issue `documents-carry-judgement`. The fixes to the render (DCJ-84,
DCJ-87 and DCJ-96) went with it in 9.0.0 (ADR-091).

Each test builds a temporary git repository (`rendered_blocks_support`) and drives
`cli/compass` the way a person does. No test reads or writes this checkout's own archive.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

import rendered_blocks_support as sup
from rendered_blocks_support import SLUG, WORK, manifest, manifest_file, run


# --- DCJ-85: a migrated issue reads dod-evidence-typed as 2.0.0 defines it ---------------------

from test_migrate_rendered_blocks import _apply, _done_issue, _row, _rewrite_generation  # noqa: E402


def _stored_before_7_0_0(root):
    """The generation as 6.x stored it: dod-evidence-typed 1.0.0, and the `on_skipped: fail`
    the shipped definition then held."""
    def resolved(data):
        data["checks"]["dod-evidence-typed"]["on_skipped"] = "fail"
    _rewrite_generation(Path(root) / WORK, lambda d: d["implementations"].update(
        {"dod-evidence-typed": "1.0.0"}))
    folder = Path(root) / WORK / "generations" / "1"
    from compass_pkg.atomic_io import digest
    marker = yaml.safe_load((folder / "complete").read_text("utf-8"))
    data = yaml.safe_load((folder / "resolved.yml").read_text("utf-8"))
    resolved(data)
    (folder / "resolved.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    marker["files"]["resolved.yml"] = digest(data)
    (folder / "complete").write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")


def test_dcj_85_a_migrated_issue_with_no_list_to_check_does_not_fail(tmp_path):
    # A done issue with no verification report, and a done issue whose report has no
    # Definition of Done section: 1.0.0 passed both, and 2.0.0 reads them as nothing to check.
    cases = {"no report": _done_issue(tmp_path / "a", [], evidence=False, heading=None),
             "no section": _done_issue(tmp_path / "b", [], evidence=False, heading=None)}
    (Path(cases["no report"]) / "docs").joinpath(
        *("compass", sup.DOCS.split("/")[-1], "verification-report.md")).unlink()
    body = manifest(cases["no report"])
    body["artifacts"] = [a for a in body["artifacts"] if a["kind"] != "verification-report"]
    sup.base.write_manifest(cases["no report"], body)
    for name, root in cases.items():
        _stored_before_7_0_0(root)
        before = _row(root, "dod-evidence-typed")
        assert before["status"] == "refused", (name, before)
        code, out, err = _apply(root)
        assert code == 0, out + err
        row = _row(root, "dod-evidence-typed")
        assert row["status"] == "nothing-to-check", (name, row)
        # The pin changed the definition of this one locked check and nothing else.
        resolved = yaml.safe_load((Path(root) / WORK / "generations" / "2" / "resolved.yml")
                                  .read_text("utf-8"))
        assert resolved["checks"]["dod-evidence-typed"]["on_skipped"] == "not-applicable"


# --- DCJ-86: a design decision's scope is read from its declared field only -----------------



# --- DCJ-93: an issue with no verification report still waits on its outstanding follow-ups ---

from test_migrate_rendered_blocks import _extra_issue  # noqa: E402


def test_dcj_93_an_issue_with_no_verification_report_is_blocked_by_an_inbound_follow_up(tmp_path):
    # A quick fix has no verification report. Another issue's outstanding follow-up that
    # targets it must still fail dod-evidence-typed, as it does for an issue with a report.
    root = sup.project(tmp_path)
    (Path(root) / sup.DOCS / "verification-report.md").unlink()
    body = manifest(root)
    body["artifacts"] = [a for a in body.get("artifacts") or []
                         if a["kind"] != "verification-report"]
    sup.base.write_manifest(root, body)
    row = _dod_status(root)
    assert row["status"] == "nothing-to-check", row
    _extra_issue(root, "raiser", status="in-progress", follow_ups=[
        {"id": "FU-IN", "status": "outstanding", "summary": "Do this first",
         "target_task": SLUG}])
    row = _dod_status(root)
    assert row["status"] == "fail", row
    assert "FU-IN" in row["detail"], row


def _dod_status(root):
    import json
    out = run(root, "check", "--issue", SLUG, "--json")[1]
    return next(c for c in json.loads(out)["checks"] if c["name"] == "dod-evidence-typed")


# --- DCJ-94: a judged check's evidence input is digested from every byte ---------------------

def test_dcj_94_an_evidence_input_keeps_a_full_byte_digest(tmp_path):
    from compass_pkg import review_records
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    note = evidence / "out.txt"
    note.write_text("before\n<!-- compass:render dod -->\nfirst\n<!-- /compass:render -->\n",
                    encoding="utf-8")
    document = tmp_path / "notes.md"
    document.write_text(note.read_text("utf-8"), encoding="utf-8")
    task = {"evidence": [{"id": "EV-1", "type": "note", "path": "evidence/out.txt"}],
            "artifacts": [{"id": "ART-NOTES", "kind": "notes", "path": "notes.md"}]}
    check = {"inputs": ["EV-1"]}
    before = review_records.current_digests(check, task, str(tmp_path))
    doc_before = review_records.file_digest(str(document))
    for path in (note, document):
        path.write_text(path.read_text("utf-8").replace("first", "second"), encoding="utf-8")
    after = review_records.current_digests(check, task, str(tmp_path))
    assert before["EV-1"] != after["EV-1"], (before, after)
    # A document's digest still ignores the inside of a rendered block.
    assert review_records.file_digest(str(document)) == doc_before


# --- DCJ-95: a verification note a person wrote first gets the block it needs -----------------



# --- DCJ-98: migration does not edit a verification report outside the documents folder -------

def test_dcj_98_migrate_does_not_edit_a_report_outside_the_documents_folder(tmp_path):
    from test_migrate_rendered_blocks import _apply, _done_issue
    outside = tmp_path / "outside"
    outside.mkdir()
    cases = {"parent": ("../outside.md", "{case}/proj/outside.md"),
             "absolute": (str(outside / "report.md"), str(outside / "report.md")),
             "symlink": ("docs/compass/link/report.md", str(outside / "report.md")),
             "elsewhere": ("notes/report.md", "{root}/notes/report.md")}
    for name, (registered, where) in cases.items():
        case = tmp_path / name
        root = Path(_done_issue(case / "proj", ["x"] * 3))
        original = Path(root / sup.DOCS / "verification-report.md")
        text = original.read_text("utf-8")
        target = Path(where.format(case=case, root=root))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if name == "symlink":
            os.symlink(outside, root / "docs" / "compass" / "link")
        body = manifest(root)
        for entry in body["artifacts"]:
            if entry["kind"] == "verification-report":
                entry["path"] = registered
        sup.base.write_manifest(root, body)
        code, out, err = _apply(root)
        assert code == 0, (name, out + err)
        assert target.read_text("utf-8") == text, (name, "the file outside was edited")
        assert original.read_text("utf-8") == text, (name, "a fallback report was edited")
        assert "verification-report" in out + err and "not edited" in out + err, (name, out + err)
    # A report inside the documents folder is read for its records and, since 9.0.0,
    # left as it is too: no block is rendered into it (ADR-091).
    root = Path(_done_issue(tmp_path / "good" / "proj", ["x"] * 3))
    path = root / sup.DOCS / "verification-report.md"
    before = path.read_text("utf-8")
    assert _apply(root)[0] == 0
    assert path.read_text("utf-8") == before
    assert manifest(root).get("page_ticks"), "the report's ticked boxes wrote no record"
