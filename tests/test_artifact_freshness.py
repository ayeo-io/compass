"""Artifact freshness: a document is stale when an artifact it depends on changed after it.

The capability `artifact-freshness` is off in the shipped default. With it on,
`compass issue artifact` records the digest of a document and of each artifact
it `depends_on`. Staleness is computed from those records and the files as
they are now. It shows in `compass check`, `compass next`, the receipt and
the refusal of `compass ship-commit`. With the capability off nothing is
written and no reader changes.

Scenario ids of issue `artifact-freshness`: `FRESH-1` to `FRESH-9`. Each test
name starts with its scenario id.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_entry_exit_evaluation import _config_project  # noqa: E402
from test_generation_store import SLUG, _evaluate_write, _manifest, _run  # noqa: E402

CRITERIA = "# Criteria\n\nGiven a, when b, then c.\n"
DESIGN = "# Design\n\nThe design.\n"
REPORT = "# Report\n\nThe report.\n"
GRAPH = {"technical-design": {"set": {"depends_on": ["acceptance-criteria"]}},
         "verification-report": {"set": {"depends_on": ["technical-design"]}}}
GUARDRAIL = "artifact-freshness"


# --- helpers ---------------------------------------------------------------------

def _sha(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _scene(tmp_path, capability=True, graph=None, phase="plan", write=True):
    """A project whose issue has a stored configuration, with the three
    documents on disk and registered through the CLI. `phase` is the issue's
    current stage."""
    root, task_dir = _config_project(tmp_path, capability=False, current_phase=phase)
    doc = {"schema": 1}
    if capability:
        doc["capabilities"] = {GUARDRAIL: True}
    doc["artifacts"] = GRAPH if graph is None else graph
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert _evaluate_write(root)[0] == 0
    (task_dir / "delivery-approach.md").write_text("# Delivery approach\n", encoding="utf-8")
    if write:
        _write(task_dir, "acceptance-criteria", CRITERIA)
        _write(task_dir, "technical-design", DESIGN)
        _write(task_dir, "verification-report", REPORT)
        for kind in ("acceptance-criteria", "technical-design", "verification-report"):
            _register(root, kind)
    return root, task_dir


def _write(task_dir, kind, text):
    (task_dir / f"{kind}.md").write_text(text, encoding="utf-8")


def _register(root, kind):
    code, out, err = _run(root, "issue", "artifact", kind, "--status", "draft",
                          "--issue", SLUG)
    assert code == 0, out + err


def _entry(task_dir, kind):
    return next(a for a in _manifest(task_dir)["artifacts"] if a["kind"] == kind)


def _check(root):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    rows = [r for r in json.loads(out)["checks"] if r["guardrail"] == GUARDRAIL]
    return code, {r["name"]: r for r in rows}, out


# --- FRESH-1: the capability off changes nothing -----------------------------------

def test_fresh_1_with_the_capability_off_nothing_is_recorded_or_shown(tmp_path):
    root, task_dir = _scene(tmp_path, capability=False, phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    for kind in ("acceptance-criteria", "technical-design"):
        entry = _entry(task_dir, kind)
        assert "digest" not in entry and "upstream" not in entry, entry
    code, rows, out = _check(root)
    assert rows == {}
    assert "freshness" not in out and "stale" not in out
    assert "stale" not in _run(root, "next", "--issue", SLUG)[1]
    assert "freshness" not in _run(root, "issue", "receipt", "--issue", SLUG)[1].lower()


def test_fresh_1_turning_the_capability_off_hides_a_stale_document_from_every_reader(tmp_path):
    root, task_dir = _landing_scene(tmp_path)
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    doc = yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    doc["capabilities"] = {GUARDRAIL: False}
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert _evaluate_write(root)[0] == 0
    assert _check(root)[1] == {}
    assert "stale" not in _run(root, "next", "--issue", SLUG)[1]
    assert "freshness" not in _run(root, "issue", "receipt", "--issue", SLUG)[1].lower()
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert "artifact(s) are stale" not in out + err, out + err


# --- FRESH-2: registering a document records the digests ---------------------------

def test_fresh_2_registering_records_the_digest_of_the_file_and_of_each_upstream(tmp_path):
    root, task_dir = _scene(tmp_path)
    design = _entry(task_dir, "technical-design")
    assert design["digest"] == _sha(DESIGN)
    assert design["upstream"] == {"acceptance-criteria": _sha(CRITERIA)}
    criteria = _entry(task_dir, "acceptance-criteria")
    assert criteria["digest"] == _sha(CRITERIA)
    assert "upstream" not in criteria


def test_fresh_2_registering_an_unchanged_document_does_not_refresh_its_upstream(tmp_path):
    root, task_dir = _scene(tmp_path)
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    _register(root, "technical-design")
    assert _entry(task_dir, "technical-design")["upstream"] == {
        "acceptance-criteria": _sha(CRITERIA)}
    _write(task_dir, "technical-design", DESIGN + "rewritten\n")
    _register(root, "technical-design")
    assert _entry(task_dir, "technical-design")["upstream"] == {
        "acceptance-criteria": _sha(CRITERIA + "changed\n")}


def test_fresh_2_the_manifest_schema_names_the_two_fields():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    props = schema["properties"]["artifacts"]["items"]["properties"]
    assert "digest" in props and "upstream" in props


# --- FRESH-3: a changed upstream makes the document stale ---------------------------

def test_fresh_3_a_changed_upstream_fails_check_once_the_consuming_stage_is_reached(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    code, rows, out = _check(root)
    assert rows["technical-design"]["status"] == "pass", rows
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, rows, out = _check(root)
    row = rows["technical-design"]
    assert row["status"] == "fail", rows
    assert "acceptance-criteria changed" in row["detail"]
    assert "entry to implement" in row["detail"]
    assert code == 1, out


def test_fresh_3_before_the_consuming_stage_a_stale_document_is_reported_and_passes(tmp_path):
    root, task_dir = _scene(tmp_path, phase="plan")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, rows, out = _check(root)
    row = rows["technical-design"]
    assert row["status"] == "pass", rows
    assert row["detail"].startswith("stale"), row
    assert "entry to implement" in row["detail"]


def test_fresh_3_a_missing_upstream_file_is_stale(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    (task_dir / "acceptance-criteria.md").unlink()
    code, rows, out = _check(root)
    assert rows["technical-design"]["status"] == "fail"
    assert "acceptance-criteria is missing now" in rows["technical-design"]["detail"]


def test_fresh_3_the_check_json_keeps_the_four_keys_of_every_row(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    code, rows, out = _check(root)
    assert list(rows["technical-design"]) == ["guardrail", "name", "status", "detail"]


# --- FRESH-4: staleness passes down the graph ------------------------------------------

def test_fresh_4_a_document_is_stale_when_a_stale_artifact_sits_between(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, rows, out = _check(root)
    assert rows["technical-design"]["status"] == "fail"
    report = rows["verification-report"]
    assert "technical-design is stale" in report["detail"], report


def test_fresh_4_rewriting_the_middle_document_leaves_the_last_stale(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    _write(task_dir, "technical-design", DESIGN + "rewritten\n")
    _register(root, "technical-design")
    code, rows, out = _check(root)
    assert rows["technical-design"]["status"] == "pass", rows
    assert "technical-design changed" in rows["verification-report"]["detail"]
    _write(task_dir, "verification-report", REPORT + "rewritten\n")
    _register(root, "verification-report")
    code, rows, out = _check(root)
    assert {r["status"] for r in rows.values()} == {"pass"}, rows


# --- FRESH-5: a presence check does not clear staleness ----------------------------------

def test_fresh_5_checking_again_and_registering_unchanged_do_not_clear_staleness(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    for _ in range(2):
        assert _check(root)[1]["technical-design"]["status"] == "fail"
    _register(root, "technical-design")
    assert _check(root)[1]["technical-design"]["status"] == "fail"


def test_fresh_5_a_document_written_against_the_new_upstream_is_fresh(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    _register(root, "acceptance-criteria")
    assert _check(root)[1]["technical-design"]["status"] == "fail"
    _write(task_dir, "technical-design", DESIGN + "rewritten\n")
    _register(root, "technical-design")
    assert _check(root)[1]["technical-design"]["status"] == "pass"


# --- FRESH-6: ship-commit refuses a stale document -----------------------------------------

def _git(root, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                           *args], cwd=root, capture_output=True, text=True, check=True
                          ).stdout.strip()


def _landing_scene(tmp_path, capability=True):
    root, task_dir = _scene(tmp_path, capability=capability, phase="ship")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    (root / "notes.txt").write_text("a change\n", encoding="utf-8")
    _git(root, "add", "notes.txt")
    return root, task_dir


def test_fresh_6_ship_commit_refuses_a_stale_document_and_commits_nothing(tmp_path):
    root, task_dir = _landing_scene(tmp_path)
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    head = _git(root, "rev-parse", "HEAD")
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert code != 0, out + err
    text = out + err
    assert "technical-design" in text and "acceptance-criteria changed" in text, text
    assert "compass issue artifact" in text
    assert _git(root, "rev-parse", "HEAD") == head


def test_fresh_6_ship_commit_at_head_with_nothing_staged_refuses_a_stale_document(tmp_path):
    root, task_dir = _landing_scene(tmp_path)
    _git(root, "commit", "-q", "-m", "the issue's work")
    body = _manifest(task_dir)
    for gate in body["gates"]:
        gate["status"] = "pass"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert code != 0, out + err
    assert "technical-design" in out + err and "acceptance-criteria changed" in out + err, out + err
    assert _manifest(task_dir)["status"] != "landed"


def test_fresh_6_ship_commit_with_the_capability_off_does_not_look(tmp_path):
    root, task_dir = _landing_scene(tmp_path, capability=False)
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert "stale" not in (out + err), out + err


def test_fresh_6_ship_commit_lands_when_every_document_is_fresh(tmp_path):
    root, task_dir = _landing_scene(tmp_path)
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert "artifact(s) are stale" not in (out + err), out + err


# --- FRESH-7: entry to a stage is refused while a document it consumes is stale ----------

def test_fresh_7_next_names_the_stale_document_at_the_entry_of_implement(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    assert "stale" not in _run(root, "next", "--issue", SLUG)[1]
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    out = _run(root, "next", "--issue", SLUG)[1]
    assert "Implement" in out
    assert "entry not met: technical-design is stale" in out, out


def test_fresh_7_next_says_nothing_before_the_stage_that_consumes_the_document(tmp_path):
    root, task_dir = _scene(tmp_path, phase="plan")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    assert "stale" not in _run(root, "next", "--issue", SLUG)[1]


# --- FRESH-8: the receipt lists freshness ---------------------------------------------------

def test_fresh_8_the_receipt_lists_each_recorded_document(tmp_path):
    root, task_dir = _scene(tmp_path)
    out = _run(root, "issue", "receipt", "--issue", SLUG)[1]
    assert "Artifact freshness" in out, out
    assert "technical-design" in out and "fresh" in out
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    out = _run(root, "issue", "receipt", "--issue", SLUG)[1]
    assert "stale" in out and "acceptance-criteria changed" in out, out


# --- FRESH-2 and FRESH-6: the help text names the capability ----------------------------

def test_fresh_2_the_help_of_the_two_verbs_names_the_capability(tmp_path):
    root, task_dir = _scene(tmp_path, write=False)
    for argv in (("issue", "artifact", "--help"), ("ship-commit", "--help")):
        code, out, err = _run(root, *argv)
        assert code == 0, err
        assert "artifact-freshness" in " ".join(out.split()), (argv, out)


# --- FRESH-9: nothing declared, nothing stale ---------------------------------------------

def test_fresh_9_without_depends_on_nothing_is_stale(tmp_path):
    root, task_dir = _scene(tmp_path, graph={"technical-design": {"set": {"file": "technical-design.md"}}},
                            phase="implement")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, rows, out = _check(root)
    assert [r["status"] for r in rows.values()] == ["nothing-to-check"], rows
    assert "stale" not in _run(root, "next", "--issue", SLUG)[1]


def test_fresh_9_a_document_registered_before_the_capability_is_not_stale(tmp_path):
    root, task_dir = _scene(tmp_path, capability=False, phase="implement")
    doc = yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    doc["capabilities"] = {GUARDRAIL: True}
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert _evaluate_write(root)[0] == 0
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, rows, out = _check(root)
    assert all(r["status"] != "fail" for r in rows.values()), rows


# --- rules the first tests left unguarded --------------------------------------------------

def test_fresh_3_an_upstream_that_appeared_after_writing_is_stale(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement", write=False)
    _write(task_dir, "technical-design", DESIGN)
    _register(root, "technical-design")
    assert _entry(task_dir, "technical-design")["upstream"] == {}
    _write(task_dir, "acceptance-criteria", CRITERIA)
    code, rows, out = _check(root)
    row = rows["technical-design"]
    assert row["status"] == "fail", rows
    assert "acceptance-criteria was not recorded when this was written" in row["detail"]


def test_fresh_3_a_document_no_stage_consumes_blocks_only_from_ship(tmp_path):
    for phase, status in (("verify", "pass"), ("ship", "fail")):
        (tmp_path / phase).mkdir()
        root, task_dir = _scene(tmp_path / phase, phase=phase)
        _write(task_dir, "technical-design", DESIGN + "changed\n")
        code, rows, out = _check(root)
        report = rows["verification-report"]
        assert report["status"] == status, (phase, rows)
        assert report["detail"].startswith("stale"), report
        assert "blocks land" in report["detail"]
        assert ("not yet due" in report["detail"]) == (status == "pass")


def test_fresh_2_an_omitted_document_is_not_stamped_and_not_tracked(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement", write=False)
    _write(task_dir, "acceptance-criteria", CRITERIA)
    _write(task_dir, "technical-design", DESIGN)
    code, out, err = _run(root, "issue", "artifact", "technical-design", "--status", "omitted",
                          "--reason", "the design is in the issue", "--issue", SLUG)
    assert code == 0, out + err
    assert "digest" not in _entry(task_dir, "technical-design")
    _register(root, "technical-design")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    assert _check(root)[1]["technical-design"]["status"] == "fail"
    code, out, err = _run(root, "issue", "artifact", "technical-design", "--status", "omitted",
                          "--reason", "the design is in the issue", "--issue", SLUG)
    assert code == 0, out + err
    code, rows, out = _check(root)
    assert "technical-design" not in rows, rows


def test_fresh_2_a_missing_upstream_record_is_written_again_on_registering(tmp_path):
    root, task_dir = _scene(tmp_path)
    body = _manifest(task_dir)
    for entry in body["artifacts"]:
        entry.pop("upstream", None)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    _register(root, "technical-design")
    assert _entry(task_dir, "technical-design")["upstream"] == {
        "acceptance-criteria": _sha(CRITERIA + "changed\n")}


def test_fresh_2_emptying_depends_on_drops_the_upstream_record(tmp_path):
    root, task_dir = _scene(tmp_path)
    assert "upstream" in _entry(task_dir, "technical-design")
    doc = yaml.safe_load((root / "compass.yml").read_text(encoding="utf-8"))
    doc["artifacts"]["technical-design"] = {"set": {"depends_on": []}}
    (root / "compass.yml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    assert _evaluate_write(root)[0] == 0
    _write(task_dir, "technical-design", DESIGN + "rewritten\n")
    _register(root, "technical-design")
    entry = _entry(task_dir, "technical-design")
    assert "upstream" not in entry and entry["digest"] == _sha(DESIGN + "rewritten\n")


def test_fresh_3_an_unreadable_record_gives_an_error_row_and_fails_check(tmp_path):
    root, task_dir = _scene(tmp_path, phase="implement")
    body = _manifest(task_dir)
    for entry in body["artifacts"]:
        if entry["kind"] == "technical-design":
            entry["upstream"] = {"acceptance-criteria": 5}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    code, rows, out = _check(root)
    assert rows["freshness"]["status"] == "fail", rows
    assert "evaluation errored" in rows["freshness"]["detail"]
    assert code == 1


def test_fresh_4_staleness_passes_over_three_hops_whatever_the_order_of_registering(tmp_path):
    graph = {"acceptance-criteria": {"set": {"depends_on": ["distribution-map"]}},
             "technical-design": {"set": {"depends_on": ["acceptance-criteria"]}},
             "verification-report": {"set": {"depends_on": ["technical-design"]}}}
    root, task_dir = _scene(tmp_path, graph=graph, phase="implement", write=False)
    for kind, text in (("distribution-map", "# Map\n"), ("acceptance-criteria", CRITERIA),
                       ("technical-design", DESIGN), ("verification-report", REPORT)):
        _write(task_dir, kind, text)
    for kind in ("verification-report", "technical-design", "acceptance-criteria"):
        _register(root, kind)
    assert {r["status"] for r in _check(root)[1].values()} == {"pass"}
    _write(task_dir, "distribution-map", "# Map\n\nchanged\n")
    code, rows, out = _check(root)
    assert "distribution-map changed" in rows["acceptance-criteria"]["detail"]
    assert "acceptance-criteria is stale" in rows["technical-design"]["detail"]
    assert "technical-design is stale" in rows["verification-report"]["detail"]


def test_fresh_6_the_refusal_exits_2_and_shows_its_prefix(tmp_path):
    root, task_dir = _landing_scene(tmp_path)
    _write(task_dir, "acceptance-criteria", CRITERIA + "changed\n")
    code, out, err = _run(root, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert code == 2, (code, out, err)
    assert err.startswith("compass: compass ship-commit: refusing to land - 2 artifact(s) are stale:"), err
