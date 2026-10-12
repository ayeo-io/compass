"""The `rendered-blocks-current` check, the after-command render and the trigger
table (issue `documents-carry-judgement`, group B: DCJ-14 to DCJ-23, DCJ-75,
DCJ-76 and DCJ-79).

Each test builds a temporary git repository (`rendered_blocks_support`) and
drives `cli/compass` the way a person does. A few tests run the check in this
process so they can plant a renderer for a kind that a later unit builds.

Each test name starts with its scenario id. No test reads or writes this
checkout's own `.compass/work` or `docs/compass` (DCJ-63 proves it).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

import rendered_blocks_support as sup
from rendered_blocks_support import (DOCS, ROOT, SLUG, WORK, block, doc_path, manifest,
                                     manifest_file, render, rich_issue, run, snapshot,
                                     write_doc)

CHECK = "rendered-blocks-current"
GATES_PATH = f"{DOCS}/verification-report.md"


def _verify_issue(tmp_path, phase="verify"):
    """A rich issue whose acceptance criteria hold a coverage block and whose
    verification report holds a gates block, rendered, at stage `phase`."""
    root = rich_issue(tmp_path)
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("coverage"))
    write_doc(root, "verification-report", "# VR\n\n" + block("gates"))
    # The issue page shows the stage, so the stage is set before the render writes it.
    sup.base.edit(root, current_phase=phase)
    code, out, err = render(root)
    assert code == 0, out + err
    return root


def _report(root):
    code, out, err = run(root, "check", "--issue", SLUG, "--json")
    assert out.strip().startswith("{"), out + err
    return code, json.loads(out)


def _row(report, name=CHECK):
    rows = [c for c in report["checks"] if c["name"] == name]
    assert rows, [c["name"] for c in report["checks"]]
    return rows[0]


def _edit_inside(path, kind, new_line="edited by hand"):
    """Replace the first interior line of the block `kind` in the document."""
    text = Path(path).read_text(encoding="utf-8")
    opening = sup.OPEN.format(kind=kind) + "\n"
    head, _, rest = text.partition(opening)
    _, _, tail = rest.partition("\n")
    Path(path).write_text(head + opening + new_line + "\n" + tail, encoding="utf-8")


# --- DCJ-14 -----------------------------------------------------------------

def test_dcj_14_stale_block_fails_at_verify(tmp_path):
    root = _verify_issue(tmp_path)
    _edit_inside(doc_path(root, "verification-report"), "gates")
    code, report = _report(root)
    row = _row(report)
    assert row["status"] == "fail", row
    assert GATES_PATH in row["detail"] and "gates" in row["detail"], row["detail"]
    assert "compass issue render" in row["detail"], row["detail"]
    assert code != 0 and CHECK in [c["name"] for c in report["checks"]
                                   if c["status"] == "fail"]
    # The same issue once it is done fails in the same way.
    sup.base.edit(root, status="done", current_phase=None)
    _, report = _report(root)
    assert _row(report)["status"] == "fail"
    assert GATES_PATH in _row(report)["detail"]


# --- DCJ-15 -----------------------------------------------------------------

def test_dcj_15_stale_block_before_verify_is_advisory(tmp_path):
    root = _verify_issue(tmp_path, phase="implement")
    code_current, current = _report(root)
    assert _row(current)["status"] == "pass", _row(current)
    _edit_inside(doc_path(root, "acceptance-criteria"), "coverage")
    code, report = _report(root)
    row = _row(report)
    assert row["status"] == "advisory", row
    assert f"{DOCS}/acceptance-criteria.md" in row["detail"] and "coverage" in row["detail"]
    # The advisory failure adds no failure to the run, so the exit code is the
    # one the same issue gives with the block current.
    assert report["failed"] == current["failed"]
    assert code == code_current
    assert report["advisory"] == current["advisory"] + 1


# --- DCJ-16 -----------------------------------------------------------------

def test_dcj_16_missing_issue_page_fails_at_verify(tmp_path):
    root = _verify_issue(tmp_path)
    (Path(root) / DOCS / "README.md").unlink()
    _, report = _report(root)
    row = _row(report)
    assert row["status"] == "fail", row
    assert "issue page is missing" in row["detail"], row["detail"]
    assert "compass issue render" in row["detail"]
    sup.base.edit(root, current_phase="implement")
    _, report = _report(root)
    assert _row(report)["status"] == "advisory"


# --- DCJ-17 -----------------------------------------------------------------

def _preset(name):
    return yaml.safe_load((ROOT / "governance" / "presets" / "default" / name)
                          .read_text(encoding="utf-8"))


def test_dcj_17_rendered_blocks_current_replaces_dashboard_current(tmp_path):
    gates = _preset("gates.yml")["gates"]
    assert CHECK in gates["G4"]["checks"] and "dashboard-current" not in gates["G4"]["checks"]
    checks = _preset("checks.yml")["checks"]
    assert "dashboard-current" not in checks
    assert checks[CHECK]["impl"] == CHECK and checks[CHECK].get("locked") is True
    locks = _preset("preset.yml")["locks"]["locked"]
    assert f"checks.{CHECK}" in locks and "checks.dashboard-current" not in locks
    # The two generated views carry the same change.
    guardrails = yaml.safe_load((ROOT / "governance" / "guardrails.yml").read_text("utf-8"))
    assert CHECK in guardrails["checks"] and "dashboard-current" not in guardrails["checks"]
    g4 = next(g for g in guardrails["defaults"] if g["id"] == "G4")
    assert CHECK in g4["checks"] and "dashboard-current" not in g4["checks"]
    # The corpus and the lock file.
    lock = yaml.safe_load((ROOT / "tests" / "fixtures" / "impls" / "versions.lock.yml")
                          .read_text("utf-8"))["implementations"]
    assert lock[CHECK]["version"] == "1.0.0" and "dashboard-current" not in lock
    assert lock["dod-evidence-typed"]["version"] == "2.0.0"
    assert (ROOT / "tests" / "fixtures" / "impls" / CHECK).is_dir()
    assert not (ROOT / "tests" / "fixtures" / "impls" / "dashboard-current").exists()
    # The CLI reports and lints it the same way.
    root = sup.project(tmp_path)
    code, out, err = run(root, "policy", "lint")
    assert code == 0 and "PASS" in out, out + err
    code, out, err = run(root, "policy", "show")
    assert CHECK in out and "dashboard-current" not in out, out[:2000]
    # A project layer that names the removed check is told what replaced it.
    (Path(root) / "compass.yml").write_text(yaml.safe_dump({
        "schema": 1, "checks": {"dashboard-current": {"set": {"severity": "advisory"}}}}),
        encoding="utf-8")
    code, out, err = run(root, "policy", "lint")
    text = out + err
    assert code != 0, text
    assert "dashboard-current" in text and "unknown" in text.lower() and CHECK in text, text


# --- DCJ-76 -----------------------------------------------------------------

def _rewrite_generation(task_dir, edit_resolved=None, edit_versions=None, n=1):
    """Rewrite what generation `n` stored, and the marker's digests, as an
    earlier release would have stored it."""
    from compass_pkg.atomic_io import digest
    folder = Path(task_dir) / "generations" / str(n)
    marker = yaml.safe_load((folder / "complete").read_text("utf-8"))
    for name, edit in (("resolved.yml", edit_resolved), ("versions.yml", edit_versions)):
        if edit is None:
            continue
        data = yaml.safe_load((folder / name).read_text("utf-8"))
        edit(data)
        (folder / name).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        marker["files"][name] = digest(data)
    (folder / "complete").write_text(yaml.safe_dump(marker, sort_keys=False), encoding="utf-8")


def _as_stored_before(task_dir):
    """The generation lists `dashboard-current` under `G4` and not
    `rendered-blocks-current`."""
    def resolved(data):
        g4 = data["gates"]["G4"]
        g4["checks"] = [c for c in g4["checks"] if c != CHECK] + ["dashboard-current"]
        data["checks"].pop(CHECK, None)
        data["checks"]["dashboard-current"] = {
            "statement": "The generated README matches the manifest.", "kind": "deterministic",
            "impl": "dashboard-current", "severity": "blocking",
            "on_skipped": "not-applicable", "locked": True}

    def versions(data):
        data["implementations"].pop(CHECK, None)
        data["implementations"]["dashboard-current"] = "1.0.0"
    _rewrite_generation(task_dir, resolved, versions)


def test_dcj_76_stored_generation_before_change(tmp_path):
    root = _verify_issue(tmp_path / "a", phase="verify")
    sup.base.edit(root, status="done", current_phase=None)
    assert render(root)[0] == 0          # the page shows the state
    task_dir = Path(root) / WORK
    _as_stored_before(task_dir)
    code, report = _report(root)
    old = _row(report, "dashboard-current")
    assert old["status"] == "nothing-to-check", old
    assert "removed in 7.0.0" in old["detail"] and CHECK in old["detail"], old["detail"]
    assert _row(report)["status"] == "pass", _row(report)
    # The removed check neither passes nor fails the issue.
    assert old["status"] != "fail"
    # A stale own-record block fails the replacement.
    _edit_inside(doc_path(root, "verification-report"), "gates")
    _, report = _report(root)
    assert _row(report)["status"] == "fail"
    assert _row(report, "dashboard-current")["status"] == "nothing-to-check"
    # A generation written now lists the new check and not the removed one.
    fresh = sup.project(tmp_path / "b")
    resolved = yaml.safe_load((Path(fresh) / WORK / "generations" / "1" / "resolved.yml")
                              .read_text("utf-8"))
    assert CHECK in resolved["gates"]["G4"]["checks"]
    assert "dashboard-current" not in resolved["gates"]["G4"]["checks"]


def test_dcj_76_a_stored_dod_evidence_typed_major_one_is_refused(tmp_path):
    root = _verify_issue(tmp_path)
    task_dir = Path(root) / WORK
    _rewrite_generation(task_dir, edit_versions=lambda d: d["implementations"].update(
        {"dod-evidence-typed": "1.0.0"}))
    _, report = _report(root)
    row = _row(report, "dod-evidence-typed")
    assert row["status"] == "refused" and "refused" in row["detail"], row


def test_dcj_62_a_a_copied_governance_folder_naming_the_removed_check_lints():
    """A governance folder copied from 5.6.0 names `dashboard-current` as a check and as its
    implementation. The copy is old, not wrong: `compass check` reports it as nothing to check,
    so the lint accepts the name. An implementation no release held is still refused."""
    from types import SimpleNamespace

    from compass_pkg import policy_lint
    layer = SimpleNamespace(name="legacy", kind="project", doc={"checks": {
        "dashboard-current": {"impl": "dashboard-current"},
        "typo": {"impl": "no-such-implementation"}}})
    found = policy_lint._impl_findings(layer)
    assert [f.path for f in found] == ["checks.typo.impl"], found


# --- DCJ-79 -----------------------------------------------------------------

def _other_issue(root, slug):
    folder = Path(root) / ".compass" / "work" / slug
    folder.mkdir(parents=True)
    (folder / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-10-09",
        "follow_ups": [{"id": "FU-1", "status": "resolved", "summary": "x",
                        "target_task": SLUG}]}), encoding="utf-8")


def test_dcj_79_ci_checkout_cross_issue_blocks_advisory(tmp_path, monkeypatch):
    from compass_pkg import render_check
    from compass_pkg.check_cmd import ADVISORY_FAILURE
    root = _verify_issue(tmp_path / "full")
    write_doc(root, "technical-design", "# TD\n\n" + block("related"))
    for other in ("other-a", "other-b"):
        _other_issue(root, other)
    monkeypatch.chdir(root)
    code, out, err = sup.inproc(root, monkeypatch)
    assert code == 0, out + err
    task_dir = str(Path(root) / WORK)
    task = yaml.safe_load(manifest_file(root).read_text("utf-8"))
    passed, detail = render_check.check(task, task_dir)
    assert passed is True, detail
    # The issue's folders alone, as a CI checkout holds them.
    fresh = Path(tmp_path) / "ci"
    (fresh / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(Path(root) / WORK, fresh / WORK)
    shutil.copytree(Path(root) / DOCS, fresh / DOCS)
    monkeypatch.chdir(fresh)
    passed, detail = render_check.check(task, str(fresh / WORK))
    assert passed is ADVISORY_FAILURE, (passed, detail)
    assert "related" in detail and "technical-design.md" in detail, detail
    for own in ("coverage", "gates", "artifacts", "follow-ups"):
        assert f"block {own}" not in detail, detail
    # The blocking verdict reads the issue's own manifest, never the parse cache.
    source = (ROOT / "cli" / "compass_pkg" / "render_check.py").read_text("utf-8")
    assert "parse_cache" not in source and "project_scan" not in source


# --- the after-command step -------------------------------------------------------

import ast
import os
import subprocess
import sys
import time


def _current_issue(tmp_path, layer=None):
    """A rich issue at `verify` whose documents hold every block the eight kinds
    draw on, rendered, with an issue page."""
    root = rich_issue(tmp_path)
    if layer is not None:
        (Path(root) / "compass.yml").write_text(yaml.safe_dump(layer), encoding="utf-8")
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("coverage"))
    write_doc(root, "verification-report", "# VR\n\n" + "".join(
        block(k) for k in ("coverage", "gates", "evidence", "decisions-taken", "dod")))
    sup.base.edit(root, current_phase="verify")
    code, out, err = render(root)
    assert code == 0, out + err
    return root


def _dry_run_rewrites(root):
    code, out, err = render(root, "--dry-run")
    assert code == 0, out + err
    return [line for line in out.splitlines() if line.strip().startswith("to rewrite")]


def _write_other(root, slug, **body):
    folder = Path(root) / ".compass" / "work" / slug
    folder.mkdir(parents=True, exist_ok=True)
    base = {"schema_version": "2.0", "issue": slug, "created": "2026-10-09"}
    base.update(body)
    (folder / "manifest.yml").write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    return folder


# --- DCJ-18 -----------------------------------------------------------------

def _rows(root):
    """Each is `(label, argv, at_a_terminal)`; they run in order on one issue."""
    path = _file_for(root)
    return [
        ("scenario add", ["scenario", "add", "TRC-9", "--title", "Ninth", "--intent", "INT-1",
                          "--test", "tests/test_a.py::test_nine"], False),
        ("evidence add", ["evidence", "add", "EV-X", "--type", "command-output",
                          "--path", path], False),
        ("gate pass", ["gate", "pass", "verify.g8", "--evidence", "EV-X"], False),
        ("issue artifact set", ["issue", "artifact", "set", "acceptance-criteria",
                                "--status", "awaiting-approval"], False),
        ("scenario descope", ["scenario", "descope", "clock skew", "--reason",
                              "cannot be forced"], False),
        ("follow-up add", ["follow-up", "add", "FU-9", "--defers", "dod-living-docs-updated",
                           "--summary", "Update the living docs"], False),
        ("follow-up resolve", ["follow-up", "resolve", "--issue", SLUG, "FU-9"], False),
        ("decision add", ["issue", "decision", "add", "D-1", "--question", "Which flag?",
                          "--resolution", "Neither", "--by", "planner", "--stage", "plan"], False),
        ("decision set", ["issue", "decision", "set", "D-1", "--status", "reopened",
                          "--reason", "needs a second look"], True),
        ("evidence approve", ["evidence", "approve", "--check", "dod-no-lint-errors",
                              "--approver", "jed72", "--role", "maintainer",
                              "--scope", "lint"], True),
        ("issue raised-by", ["issue", "raised-by", "parent-issue", "--found-at", "verify"],
         False),
    ]


def _file_for(root):
    folder = Path(root) / WORK / "evidence"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "x.txt").write_text("ok\n", encoding="utf-8")
    return "evidence/x.txt"


def test_dcj_18_record_changing_command_re_renders(tmp_path, monkeypatch):
    root = _current_issue(tmp_path, layer={**sup.base.HUMAN_DESIGN})
    _write_other(root, "parent-issue")
    assert render(root)[0] == 0          # the project index lists the new issue
    assert _dry_run_rewrites(root) == []
    for label, argv, terminal in _rows(root):
        if terminal:
            code, out, err = sup.base.run(root, *argv, "--issue", SLUG, terminal=True)
        else:
            code, out, err = run(root, *argv, "--issue", SLUG)
        assert code == 0, (label, out, err)
        assert "no longer matches" not in out + err and "dashboard" not in out + err, (label, out)
        assert _dry_run_rewrites(root) == [], label
    _, report = _report(root)
    assert _row(report)["status"] == "pass", _row(report)
    # The trigger table is the label sync's table plus a named list, read from one place.
    from compass_pkg import github_labels, record_triggers
    assert github_labels.TRIGGERS is record_triggers.LABEL_TRIGGERS
    assert set(record_triggers.RENDER_TRIGGERS) == (set(record_triggers.LABEL_TRIGGERS)
                                                    | set(record_triggers.RENDER_FURTHER))
    for name in ("cmd_evidence_approve", "cmd_follow_up_add", "cmd_backfill_pay",
                 "cmd_decision_add", "cmd_decision_set", "cmd_issue_raised_by"):
        assert name in record_triggers.RENDER_FURTHER, name


def test_dcj_18_every_command_in_the_table_renders_the_named_issue(tmp_path, monkeypatch):
    import argparse
    from compass_pkg import record_triggers, render_after
    root = _current_issue(tmp_path)
    monkeypatch.chdir(root)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    monkeypatch.setenv("COMPASS_RENDER_AFTER", "1")
    for name, flag in sorted(record_triggers.RENDER_TRIGGERS.items()):
        called = []
        monkeypatch.setattr(render_after, "render_issue", lambda d, _c=called: _c.append(d) or [])

        def func(args):
            return 0
        func.__name__ = name
        args = argparse.Namespace(func=func, task=SLUG)
        if flag:
            setattr(args, flag, False)
            assert render_after.after_command(args, 0) == 0 and not called, name
            setattr(args, flag, True)
        assert render_after.after_command(args, 0) == 0
        assert [os.path.basename(d) for d in called] == [SLUG], (name, called)
        called.clear()
        assert render_after.after_command(args, 2) == 2 and not called, name


# --- DCJ-19 -----------------------------------------------------------------

def test_dcj_19_failed_command_renders_nothing(tmp_path):
    root = _current_issue(tmp_path)
    _edit_inside(doc_path(root, "verification-report"), "gates")
    before = snapshot(root)
    code, out, err = run(root, "scenario", "add", "TRC-1", "--intent", "INT-1",
                         "--issue", SLUG)
    assert code == 2, out + err
    assert snapshot(root) == before
    # A command that succeeds renders the same stale block, so the guard above is not idle.
    code, out, err = run(root, "scenario", "add", "TRC-9", "--intent", "INT-1",
                         "--test", "tests/test_a.py::t", "--issue", SLUG)
    assert code == 0, out + err
    assert "edited by hand" not in doc_path(root, "verification-report").read_text("utf-8")


# --- DCJ-20 -----------------------------------------------------------------

def _malformed(root, name="verification-report", at=30):
    """The document's text, with an opening marker and no closing one at line `at`."""
    lines = ["# VR", ""] + [f"line {n}" for n in range(3, at)]
    lines.append(sup.OPEN.format(kind="gates"))
    lines.append("never closed")
    path = doc_path(root, name)
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return path


def _fake_gh(tmp_path):
    folder = Path(tmp_path) / "fake-bin"
    folder.mkdir(parents=True, exist_ok=True)
    gh = folder / "gh"
    gh.write_text("#!/bin/sh\necho 'not logged in: gh auth login' >&2\nexit 1\n")
    gh.chmod(0o755)
    return f"{folder}:/usr/bin:/bin"


def test_dcj_20_failed_render_one_stderr_line_command_succeeds(tmp_path):
    root = _current_issue(tmp_path / "one")
    path = _malformed(root)
    before = path.read_bytes()
    code, out, err = run(root, "scenario", "add", "TRC-9", "--intent", "INT-1",
                         "--test", "tests/test_a.py::t", "--issue", SLUG)
    assert code == 0, out + err
    assert "TRC-9" in [s["id"] for s in manifest(root)["scenarios"]]
    lines = [x for x in err.splitlines() if x.strip()]
    assert len(lines) == 1, err
    assert "verification-report.md" in lines[0] and ":30" in lines[0], lines[0]
    assert "compass issue render" in lines[0]
    assert path.read_bytes() == before

    # Two of two renders fail: one line, with the count, naming the first failure.
    root = _current_issue(tmp_path / "two")
    _malformed(root)
    _write_other(root, "parent-issue", artifacts=[{
        "id": "ART-AC", "kind": "acceptance-criteria", "status": "draft",
        "path": "docs/compass/2026-10-09-parent-issue/acceptance-criteria.md"}])
    other = Path(root) / "docs" / "compass" / "2026-10-09-parent-issue"
    other.mkdir(parents=True)
    (other / "acceptance-criteria.md").write_text(
        "# AC\n\n" + sup.OPEN.format(kind="coverage") + "\nno closing marker\n", encoding="utf-8")
    sup.base.edit(root, raised_by={"issue": "parent-issue", "found_at": "verify"})
    code, out, err = run(root, "scenario", "add", "TRC-8", "--intent", "INT-1",
                         "--test", "tests/test_a.py::t8", "--issue", SLUG)
    assert code == 0, out + err
    lines = [x for x in err.splitlines() if x.strip()]
    assert len(lines) == 1, err
    assert "2 of 2 renders failed" in lines[0] and "verification-report.md" in lines[0], lines[0]

    # The label sync fails on the same command: its own line is printed as well.
    root = _current_issue(tmp_path / "three", layer={"schema": 1, "github_labels": {"status": True}})
    _malformed(root)
    assert run(root, "issue", "link", "set", "--github", "o/r#1", "--issue", SLUG)[0] == 0
    code, out, err = run(root, "scenario", "add", "TRC-7", "--intent", "INT-1",
                         "--test", "tests/test_a.py::t7", "--issue", SLUG,
                         extra_env={"PATH": _fake_gh(tmp_path)})
    assert code == 0, out + err
    lines = [x for x in err.splitlines() if x.strip()]
    assert len([x for x in lines if "github labels" in x]) == 1, err
    assert len([x for x in lines if "compass issue render" in x]) == 1, err
    assert len(lines) == 2, err


# --- DCJ-21 -----------------------------------------------------------------

def _stale_follow_ups(root, slug, created):
    folder = Path(root) / "docs" / "compass" / f"{created}-{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    page = folder / "README.md"
    page.write_text(f"# {slug}\n\n" + block("follow-ups", "stale text")
                    + block("related", "stale text"), encoding="utf-8")
    return page


def test_dcj_21_after_command_renders_linked_issues_only(tmp_path):
    root = _current_issue(tmp_path)
    parent_page = _stale_follow_ups(root, "parent", "2026-10-09")
    bystander_page = _stale_follow_ups(root, "bystander", "2026-10-09")
    _write_other(root, "parent")
    _write_other(root, "bystander")
    pages = {"parent": parent_page, "bystander": bystander_page}
    os.utime(bystander_page, (1_000_000, 1_000_000))
    before = bystander_page.read_bytes()
    code, out, err = run(root, "issue", "raised-by", "parent", "--found-at", "verify",
                         "--issue", SLUG)
    assert code == 0, out + err
    assert "stale text" not in pages["parent"].read_text(encoding="utf-8")
    assert "No follow-ups recorded." in pages["parent"].read_text(encoding="utf-8")
    # The related blocks and the index rows of both issues are current.
    child = (Path(root) / DOCS / "README.md").read_text(encoding="utf-8")
    assert any("raised from" in x and "parent" in x for x in child.splitlines())
    assert any("raised here" in x and SLUG in x
               for x in pages["parent"].read_text(encoding="utf-8").splitlines())
    index = (Path(root) / "docs" / "compass" / "README.md").read_text(encoding="utf-8")
    assert f"| [{SLUG}](" in index and "| [parent](" in index and "| [bystander](" in index
    code, out, err = run(root, "check", "--issue", SLUG, "--verbose")
    assert "PASS rendered-blocks-current" in out, out
    assert bystander_page.read_bytes() == before
    assert int(bystander_page.stat().st_mtime) == 1_000_000
    # The reverse direction: the parent's own command renders the issue raised from it.
    _edit_inside(doc_path(root, "verification-report"), "gates")
    code, out, err = run(root, "follow-up", "add", "FU-5", "--summary", "later", "--issue", "parent")
    assert code == 0, out + err
    text = doc_path(root, "verification-report").read_text(encoding="utf-8")
    assert "edited by hand" not in text


# --- DCJ-22 -----------------------------------------------------------------

OLD_DECISION = "2026-10-05-remind-when-the-review-page-goes-stale.md"


def test_dcj_22_new_decision_entry_supersedes_reminder(tmp_path):
    decisions = ROOT / "governance" / "decisions"
    new = [p for p in decisions.glob("*.md") if "Supersedes" in p.read_text("utf-8")
           and "remind-when-the-review-page-goes-stale" in
           p.read_text("utf-8").split("## Supersedes", 1)[1].split("##", 1)[0]]
    assert len(new) == 1, new
    entry = new[0].read_text("utf-8")
    assert "re-render" in entry and "instead of printing a reminder" in entry
    repo = Path(tmp_path) / "repo"
    (repo / "governance" / "decisions").mkdir(parents=True)
    (repo / ".compass").mkdir()
    shutil.copy2(decisions / OLD_DECISION, repo / "governance" / "decisions" / OLD_DECISION)
    git = lambda *a: subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                                     *a], cwd=repo, check=True, capture_output=True, text=True)
    git("init", "-q", "-b", "main")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    shutil.copy2(new[0], repo / "governance" / "decisions" / new[0].name)
    code, out, err = run(repo, "decision", "check", "--base", "main")
    assert code == 0, out + err
    assert (repo / "governance" / "decisions" / OLD_DECISION).read_bytes() == \
        (decisions / OLD_DECISION).read_bytes()


# --- DCJ-23 -----------------------------------------------------------------

def test_dcj_23_rendered_documents_not_in_model_read_set():
    import test_instruction_volume as volume
    for name in volume.QUICK_FIX_READS + ["hooks/session-start.sh"]:
        text = (ROOT / name).read_text("utf-8").lower()
        for word in ("issue page", "verification note", "verification-note", "project index"):
            assert word not in text, (name, word)
    reading = sum(volume._words(ROOT / r) for r in volume.QUICK_FIX_READS)
    assert reading <= volume.QUICK_FIX_CEILING


# --- DCJ-75 -----------------------------------------------------------------

def _package_sources():
    sources = {"compass": (ROOT / "cli" / "compass").read_text("utf-8")}
    for path in sorted((ROOT / "cli" / "compass_pkg").glob("*.py")):
        sources[path.name] = path.read_text("utf-8")
    return sources


def commands_that_save(sources):
    """The command functions (the `func=` of a `set_defaults`) from which a call
    reaches `save_manifest`, over a call graph of the given sources `{name: text}`.
    A name defined more than once is not followed, so two unrelated helpers that
    share a name cannot join two unrelated commands."""
    defs, targets = {}, set()
    for text in sources.values():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef):
                calls = set()
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call):
                        func = inner.func
                        calls.add(func.id if isinstance(func, ast.Name)
                                  else func.attr if isinstance(func, ast.Attribute) else "")
                defs.setdefault(node.name, []).append(calls)
            elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                  and node.func.attr == "set_defaults"):
                targets |= {kw.value.id for kw in node.keywords
                            if kw.arg == "func" and isinstance(kw.value, ast.Name)}

    def reaches(start):
        seen, stack = set(), [start]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            if name == "save_manifest":
                return True
            bodies = defs.get(name, [])
            if len(bodies) == 1 or name == start:
                for body in bodies:
                    stack.extend(body)
        return False
    return {t for t in targets if reaches(t)}, targets


def uncovered(sources, covered):
    saving, _ = commands_that_save(sources)
    return sorted(saving - set(covered))


def test_dcj_75_trigger_table_complete():
    from compass_pkg import record_triggers
    covered = set(record_triggers.RENDER_TRIGGERS) | set(record_triggers.EXEMPT)
    sources = _package_sources()
    assert uncovered(sources, covered) == []
    # Every entry names a real command, and every exemption carries its reason.
    _, targets = commands_that_save(sources)
    gone = sorted(n for n in covered - targets
                  if n not in ("cmd_route_evaluate", "cmd_issue_raised_by"))
    assert gone == [], gone
    assert all(isinstance(r, str) and len(r.split()) >= 5 for r in record_triggers.EXEMPT.values())
    assert not set(record_triggers.EXEMPT) & set(record_triggers.RENDER_TRIGGERS)
    # A command that saves a manifest and is in neither is named by the test.
    planted = dict(sources)
    planted["planted.py"] = (
        "from compass_pkg.core import save_manifest\n"
        "def cmd_planted(args):\n    save_manifest({}, 'x')\n    return 0\n"
        "def build(p):\n    p.set_defaults(func=cmd_planted)\n")
    assert uncovered(planted, covered) == ["cmd_planted"]
    # The render step is its own module, called after the label sync; neither imports the other.
    pkg = ROOT / "cli" / "compass_pkg"
    for mine, other in (("render_after.py", "github_labels"), ("github_labels.py", "render_after")):
        text = (pkg / mine).read_text("utf-8")
        imports = {a.name for n in ast.walk(ast.parse(text)) if isinstance(n, ast.ImportFrom)
                   for a in n.names} | {n.module or "" for n in ast.walk(ast.parse(text))
                                        if isinstance(n, ast.ImportFrom)}
        assert other not in imports and f"compass_pkg.{other}" not in imports, (mine, other)
        assert "record_triggers" in text
    entry = (ROOT / "cli" / "compass").read_text("utf-8")
    # The label sync runs first: the render step wraps it and receives its exit code.
    assert "render_after_command(a, github_labels.after_command(a, args.func(a)" in entry
