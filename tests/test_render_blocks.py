"""Rendered blocks and the `compass issue render` verb (issue
`documents-carry-judgement`, group A: DCJ-1 to DCJ-10 and DCJ-68, DCJ-70 to
DCJ-74).

Each test builds a temporary git repository (`rendered_blocks_support`) and
drives `cli/compass` the way a person does. A few tests run the render in this
process so they can plant a fault: a splice that writes outside a block, a
disabled escape, an edit made between the read and the replace.

Each test name starts with its scenario id. No test reads or writes this
checkout's own `.compass/work` or `docs/compass` (DCJ-63 proves it).
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest
import yaml

import rendered_blocks_support as sup
from rendered_blocks_support import (CLOSE, DOCS, OPEN, SLUG, WORK, block, doc_path, inproc,
                                     manifest, manifest_file, render, rich_issue, run,
                                     snapshot, write_doc)



def _rb():
    """The engine module, imported when a test needs it."""
    from compass_pkg import rendered_blocks
    return rendered_blocks


GATES = OPEN.format(kind="gates")


def _blocks(path):
    """`[(kind, interior text)]` of the document at `path`."""
    text = Path(path).read_bytes().decode("utf-8")
    found = _rb().parse(text, str(path))
    return [(b.kind, "".join(found.lines[b.start + 1:b.end])) for b in found.blocks]


def _register_at(root, kind, rel):
    """Point the registry entry of `kind` at `rel` by editing the manifest: the command
    that does it (`compass issue artifact set`) is followed by a render, which would fill
    the blocks these tests want to find stale."""
    if kind not in sup.base.entries(root):
        sup.base.add_entry(root, kind, path=False)       # a kind the approach did not earn
    body = manifest(root)
    for entry in body["artifacts"]:
        if entry["kind"] == kind:
            entry["path"] = rel
    sup.base.write_manifest(root, body)


def _full_issue(tmp_path):
    root = rich_issue(tmp_path)
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("coverage"))
    write_doc(root, "verification-report", "# VR\n\n" + "".join(
        block(k) for k in ("coverage", "gates", "dod", "evidence", "decisions-taken")))
    write_doc(root, "requirements-review", "# RR\n\n" + block("dor"))
    return root


# --- DCJ-1 ------------------------------------------------------------------

def test_dcj_1_render_rewrites_every_block_from_records(tmp_path, monkeypatch):
    root = _full_issue(tmp_path / "one")
    write_doc(root, "technical-design", "# TD\n", register_it=True)
    doc_path(root, "technical-design").unlink()

    code, out, err = render(root)

    assert code == 0, out + err
    found = {}
    for name in ("acceptance-criteria", "verification-report", "requirements-review"):
        for kind, body in _blocks(doc_path(root, name)):
            found.setdefault(kind, []).append(body)
            assert "stale" not in body, (name, kind)
            assert body.strip(), (name, kind)
    assert set(found) == {"coverage", "gates", "dod", "evidence", "decisions-taken", "dor"}
    assert found["gates"][0].splitlines()[0] == "Gates: 7 of 9 pass"
    assert (Path(root) / DOCS / "README.md").is_file()
    assert "technical-design" in out and "not on disk" in out
    assert "verification-report.md" in out
    # Parsed again, each document holds exactly the blocks it held before.
    assert [k for k, _ in _blocks(doc_path(root, "verification-report"))] == [
        "coverage", "gates", "dod", "evidence", "decisions-taken"]

    # Every document is parsed before the first one is written.
    second = _full_issue(tmp_path / "two")
    events = []
    real_parse, real_write = _rb().parse, _rb().write_rendered

    def spy_parse(*a, **k):
        events.append("parse")
        return real_parse(*a, **k)

    def spy_write(*a, **k):
        events.append("write")
        return real_write(*a, **k)

    monkeypatch.setattr(_rb(), "parse", spy_parse)
    monkeypatch.setattr(_rb(), "write_rendered", spy_write)
    code, out, err = inproc(second, monkeypatch)
    assert code == 0, out + err
    assert "write" in events
    assert events.index("write") > max(i for i, e in enumerate(events) if e == "parse"), events


# --- DCJ-2 ------------------------------------------------------------------

_CRLF_DOC = (
    "# Title é ü 日本\r\n\r\n"
    "Use `<!-- compass:render gates -->` inline mid-sentence.\r\n\r\n"
    "```\r\n<!-- compass:render coverage -->\r\nquoted\r\n<!-- /compass:render -->\r\n```\r\n\r\n"
    "<!-- a note\r\n<!-- compass:render dod -->\r\nafter the note\r\n\r\n"
    "<!-- compass:render gates -->\r\nstale\r\n<!-- /compass:render -->\r\n"
    "Tail with no newline at the end").encode("utf-8")


def _crlf_issue(tmp_path):
    root = rich_issue(tmp_path)
    write_doc(root, "verification-report", _CRLF_DOC, binary=True)
    return root


def test_dcj_2_text_outside_markers_byte_identical(tmp_path, monkeypatch):
    root = _crlf_issue(tmp_path / "ok")
    path = doc_path(root, "verification-report")
    before = path.read_bytes()
    opening = b"<!-- compass:render gates -->\r\n"
    head = before[:before.index(opening) + len(opening)]
    closing = b"<!-- /compass:render -->\r\n"
    tail = before[before.rindex(closing):]

    code, out, err = render(root)

    assert code == 0, out + err
    after = path.read_bytes()
    assert after != before
    assert after.startswith(head) and after.endswith(tail)
    body = after[len(head):len(after) - len(tail)]
    lines = body.split(b"\r\n")
    assert lines[-1] == b"" and all(b"\n" not in line for line in lines)
    assert body.count(b"\n") == body.count(b"\r\n") > 0

    # A splice that writes one line after the closing marker is refused: the
    # text outside the markers differs from the text read.
    planted = _crlf_issue(tmp_path / "planted")
    path = doc_path(planted, "verification-report")
    before = path.read_bytes()
    real = _rb().splice

    def bad_splice(*a, **k):
        done = real(*a, **k)
        if CLOSE + "\r\n" not in done:
            return done                      # the issue page, not this document
        at = done.rindex(CLOSE + "\r\n") + len(CLOSE) + 2
        return done[:at] + "planted line\r\n" + done[at:]

    monkeypatch.setattr(_rb(), "splice", bad_splice)
    code, out, err = inproc(planted, monkeypatch)
    assert code == 2, out + err
    assert "verification-report.md" in err and "outside the markers" in err
    assert path.read_bytes() == before


# --- DCJ-3 ------------------------------------------------------------------

def test_dcj_3_second_render_changes_no_byte(tmp_path):
    root = _full_issue(tmp_path)
    assert render(root)[0] == 0
    first = snapshot(root)
    time.sleep(1.1)
    code, out, err = render(root)
    assert code == 0, out + err
    docs = {k: v for k, v in snapshot(root).items() if k.startswith("docs/")}
    assert docs == {k: v for k, v in first.items() if k.startswith("docs/")}


# --- DCJ-4 ------------------------------------------------------------------

def test_dcj_4_coverage_block_tests_records_and_descoped_modes(tmp_path):
    root = _full_issue(tmp_path)
    assert render(root)[0] == 0
    body = dict(_blocks(doc_path(root, "acceptance-criteria")))["coverage"]
    lines = body.splitlines()
    row = {sid: next(line for line in lines if f"| {sid} |" in line)
           for sid in ("TRC-1", "TRC-2", "TRC-3")}
    assert "First scenario" in row["TRC-1"] and "tests/test_a.py::test_one" in row["TRC-1"]
    assert "red-TRC-1.json" in row["TRC-1"] and "green-TRC-1.json" in row["TRC-1"]
    assert "passed" in row["TRC-1"]
    assert "failing test only" in row["TRC-2"] and "red-TRC-2.json" in row["TRC-2"]
    assert "green-TRC-2" not in row["TRC-2"]
    assert "no test record" in row["TRC-3"]
    at = body.index("a disk that fills mid-write")
    assert at > body.index("| TRC-3 |")
    assert "no portable way to force it" in body[at:]


# --- DCJ-5 ------------------------------------------------------------------

def test_dcj_5_gates_block_status_and_evidence(tmp_path):
    root = _full_issue(tmp_path)
    assert render(root)[0] == 0
    body = dict(_blocks(doc_path(root, "verification-report")))["gates"]
    lines = body.splitlines()
    assert lines[0] == "Gates: 7 of 9 pass"
    rows = [line for line in lines if line.startswith("- ")]
    assert len(rows) == 9
    for n, row in enumerate(rows):
        assert f"verify.g{n}" in row
        assert ("pass" in row) == (n < 7)
        assert (f"EV-{n}" in row) == (n < 7)
        if n >= 7:
            assert "pending" in row


# --- DCJ-6 ------------------------------------------------------------------

def test_dcj_6_evidence_follow_ups_decisions_taken_blocks(tmp_path):
    root = _full_issue(tmp_path)
    write_doc(root, "runbook", "# RB\n\n" + block("follow-ups"))
    assert render(root)[0] == 0
    report = dict(_blocks(doc_path(root, "verification-report")))

    evidence = report["evidence"]
    for entry in ("EV-A", "test-run", "evidence/green-TRC-1.json", "EV-B", "command-output",
                  "EV-C", "manual-review"):
        assert entry in evidence
    assert "scenario" not in evidence and "passed" not in evidence      # no record contents
    work_line = next(x for x in evidence.splitlines() if "EV-A" in x)
    docs_line = next(x for x in evidence.splitlines() if "EV-B" in x)
    assert "](" not in work_line
    assert "](technical-design.md)" in docs_line

    follow = dict(_blocks(doc_path(root, "runbook")))["follow-ups"]
    one = next(x for x in follow.splitlines() if "FU-1" in x)
    two = next(x for x in follow.splitlines() if "FU-2" in x)
    assert "outstanding" in one and "Add the second thing" in one and "other-issue" in one
    assert "resolved" in two and "Fixed the first thing" in two

    taken = report["decisions-taken"]
    q1 = next(x for x in taken.splitlines() if "Q1" in x)
    q2 = next(x for x in taken.splitlines() if "Q2" in x)
    for word in ("Which folder?", "The docs folder", "spec-author", "confirmed"):
        assert word in q1
    for word in ("Which flag?", "Neither", "planner", "open"):
        assert word in q2
    assert taken.index("Q2") < taken.index("The change reached more modules")


# --- DCJ-7 ------------------------------------------------------------------

_FAULTS = {
    "opening with no closing": ["<!-- compass:render gates -->", "prose"],
    "closing with no opening": [CLOSE, "prose"],
    "opening inside an open block": [OPEN.format(kind="dod"), GATES, CLOSE],
    "unknown kind": [OPEN.format(kind="summary"), CLOSE],
    "no spaces": ["<!--compass:render gates-->", CLOSE],
    "merge left the opening twice": [GATES, GATES, "body", CLOSE],
}


@pytest.mark.parametrize("fault", sorted(_FAULTS))
def test_dcj_7_malformed_marker_refused_nothing_written(tmp_path, fault):
    root = rich_issue(tmp_path)
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("gates"))
    prose = [f"line {n}" for n in range(1, 12)]            # lines 1 to 11
    lines = _FAULTS[fault]
    if fault in ("opening inside an open block", "merge left the opening twice"):
        # The first marker is line 11; the fault is the second, line 12.
        text = "\n".join(prose[:10] + [lines[0]] + lines[1:]) + "\n"
    else:
        text = "\n".join(prose + lines) + "\n"
    write_doc(root, "verification-report", text)
    before = snapshot(root)

    code, out, err = render(root)

    assert code == 2, out + err
    assert "verification-report.md:12" in err, err
    assert snapshot(root) == before
    assert not (Path(root) / DOCS / "README.md").exists()


# --- DCJ-8 ------------------------------------------------------------------

def test_dcj_8_document_without_block_left_alone(tmp_path):
    root = _full_issue(tmp_path)
    path = write_doc(root, "runbook", "# RB\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n- [ ] a box\n- [x] another\n")
    os.utime(path, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    before, stamp = path.read_bytes(), path.stat().st_mtime_ns

    code, out, err = render(root)

    assert code == 0, out + err
    assert path.read_bytes() == before and path.stat().st_mtime_ns == stamp
    assert "runbook" not in out


# --- DCJ-9 ------------------------------------------------------------------

def test_dcj_9_non_utf8_document_refused(tmp_path):
    root = _full_issue(tmp_path)
    write_doc(root, "runbook", b"# RB \xff\xfe\n" + block("gates").encode(), binary=True)
    before = snapshot(root)

    code, out, err = render(root)

    assert code == 2, out + err
    assert "runbook.md" in err and "not UTF-8" in err
    assert snapshot(root) == before


# --- DCJ-10 -----------------------------------------------------------------

def _tmp_files(root):
    return [p for p in (Path(root) / DOCS).rglob(".compass-render-*")]


@pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0,
                    reason="a superuser can write to a read-only folder")
def test_dcj_10_failed_write_leaves_document_unchanged(tmp_path):
    root = _full_issue(tmp_path)
    sub = Path(root) / DOCS / "sub"
    sub.mkdir()
    (sub / "technical-design.md").write_text("# TD\n\n" + block("gates"))
    _register_at(root, "technical-design", f"{DOCS}/sub/technical-design.md")
    target = sub / "technical-design.md"
    body = manifest(root)
    body["artifacts"].sort(key=lambda a: a["kind"] == "technical-design")
    manifest_file(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    before = target.read_bytes()
    sub.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        code, out, err = render(root)
        assert code == 2, out + err
        assert "technical-design.md" in err
        assert target.read_bytes() == before
        assert _tmp_files(root) == []
        # The first two documents were written and are not rolled back.
        assert "stale" not in doc_path(root, "acceptance-criteria").read_text()
        assert "stale" not in doc_path(root, "verification-report").read_text()
        assert not (Path(root) / DOCS / "README.md").exists()
    finally:
        sub.chmod(stat.S_IRWXU)

    # Fault cleared: the next render converges, and a second one has nothing to do.
    code, out, err = render(root)
    assert code == 0, out + err
    assert "stale" not in target.read_text()
    code, out, err = render(root, "--dry-run")
    assert code == 0 and "0 document(s) to rewrite" in out, out


def test_dcj_10_leftover_temporary_file_is_deleted_before_writing(tmp_path):
    root = _full_issue(tmp_path)
    leftover = Path(root) / DOCS / ".compass-render-killed"
    leftover.write_text("half a document")
    code, out, err = render(root)
    assert code == 0, out + err
    assert not leftover.exists()
    assert "stale" not in doc_path(root, "acceptance-criteria").read_text()


# --- DCJ-68 -----------------------------------------------------------------

_HOSTILE = "\n".join(["Plain start", "<!-- compass:render gates -->", "```", "<!--",
                      "<<<<<<< HEAD", "=======", "tail HEAD"])
_SOURCES = {
    "scenario title": ("acceptance-criteria", "coverage"),
    "follow-up summary": ("runbook", "follow-ups"),
    "decisions_taken resolution": ("verification-report", "decisions-taken"),
    "artifact entry reason": ("technical-design", "artifacts"),
    "intent.md Problem section": ("intent", "ask"),
    "technical design DD heading": ("technical-design", "decisions"),
}


def _hostile_issue(tmp_path, source):
    root = rich_issue(tmp_path)
    body = manifest(root)
    if source == "scenario title":
        body["scenarios"][0]["title"] = _HOSTILE
    elif source == "follow-up summary":
        body["follow_ups"][0]["summary"] = _HOSTILE
    elif source == "decisions_taken resolution":
        body["decisions_taken"][0]["resolution"] = _HOSTILE
    elif source == "artifact entry reason":
        pass
    elif source == "intent.md Problem section":
        Path(root, DOCS, "intent.md").write_text(
            "# Intent\n\n## Problem\n\n" + _HOSTILE + "\n\n## Desired outcome\n\nOne.\n",
            encoding="utf-8")
    manifest_file(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("coverage"))
    write_doc(root, "verification-report", "# VR\n\n" + block("decisions-taken"))
    write_doc(root, "runbook", "# RB\n\n" + block("follow-ups"))
    write_doc(root, "technical-design", "# TD\n\n" + block("artifacts"))
    if source == "technical design DD heading":
        write_doc(root, "technical-design",
                  "# TD\n\n### DD-1 - Plain start <!-- compass:render gates --> tail HEAD\n\n"
                  "Scope: project\n\n" + block("artifacts"))
    if source == "artifact entry reason":
        body = manifest(root)
        for entry in body["artifacts"]:
            entry["reason"] = _HOSTILE
        manifest_file(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return root


def _clean(line):
    stripped = line.strip()
    return not ("<!--" in line or "-->" in line
                or stripped.startswith(("```", "~~~", "<<<<<<<", "=======", ">>>>>>>", "|||||||")))


@pytest.mark.parametrize("source", sorted(_SOURCES))
def test_dcj_68_recorded_markup_cannot_break_page(tmp_path, monkeypatch, source):
    root = _hostile_issue(tmp_path / "ok", source)
    for _ in range(2):
        code, out, err = render(root)
        assert code == 0, out + err
    names = ("acceptance-criteria", "verification-report", "runbook", "technical-design")
    for name in names:
        parsed = _blocks(doc_path(root, name))
        assert len(parsed) == 1
        for line in parsed[0][1].splitlines():
            assert _clean(line), (name, line)
    page = Path(root) / DOCS / "README.md"
    for kind, body in _blocks(page):
        # The one fence a renderer writes is the Mermaid chart of the traceability block
        # (DCJ-43), opened and closed by these exact lines.
        chart = ("```mermaid", "```") if kind == "traceability" else ()
        assert all(_clean(line) or line in chart for line in body.splitlines()), kind
    shown = "".join(b for n in names for _, b in _blocks(doc_path(root, n)))
    shown += "".join(b for _, b in _blocks(page))
    assert "tail HEAD" in shown and "compass:render gates" in shown     # still readable

    # Escaping switched off: the engine's own re-parse refuses, writing nothing.
    planted = _hostile_issue(tmp_path / "planted", source)
    before = snapshot(planted)
    monkeypatch.setattr(_rb(), "neutralise", lambda line: line)
    code, out, err = inproc(planted, monkeypatch)
    assert code == 2, out + err
    assert snapshot(planted) == before


def test_dcj_68_reparse_catches_a_wrong_splice(tmp_path, monkeypatch):
    """The engine parses what it built and compares it with what it meant. A
    splice that puts a block's text in another block passes the other guards
    (nothing outside the markers moved, no line is markup) and only this one
    catches it."""
    root = rich_issue(tmp_path)
    write_doc(root, "verification-report", "# VR\n\n" + block("gates") + "\n" + block("evidence"))
    before = snapshot(root)
    real = _rb().splice

    def swapped(parsed, bodies):
        keys = sorted(bodies)
        if len(keys) == 2:
            bodies = {keys[0]: bodies[keys[1]], keys[1]: bodies[keys[0]]}
        return real(parsed, bodies)

    monkeypatch.setattr(_rb(), "splice", swapped)
    code, out, err = inproc(root, monkeypatch)
    assert code == 2, out + err
    assert "does not give the blocks that were meant" in err
    assert snapshot(root) == before


# --- DCJ-70 -----------------------------------------------------------------

_SPEC = textwrap.dedent("""\
    # Spec

    <!-- compass:render coverage -->
    | TRC-9 | Block only | tests/x.py | red | green |
    ### Scenario: Block only
    <!-- traceability id: TRC-9 · serves: INT-9 -->

    ```gherkin
    Scenario: Block only
      Given a block
      When it is read
      Then nobody finds it
    ```
    <!-- /compass:render -->

    ### Scenario: The real one
    <!-- traceability id: TRC-1 · serves: INT-1 -->

    ```gherkin
    Scenario: The real one
      Given a document
      When it is read
      Then it is found
    ```

    | TRC-1 | The real one | tests/y.py |
    """)

_REVIEW = textwrap.dedent("""\
    # Review

    <!-- compass:render decisions-taken -->
    ### Q9 - Block only question
    - **Question:** Is this read?
    - **Resolution:** No.
    - **Decided by:** spec-author
    <!-- /compass:render -->

    ### Q1 - Real question
    - **Question:** Is this read?
    - **Resolution:** Yes.
    - **Decided by:** spec-author
    """)


def _without_blocks(text):
    return _rb().masked_text(text)


def test_dcj_70_readers_never_read_block_text(tmp_path):
    from compass_pkg import analyze, bdd, checks, decisions_taken, tdd
    root = rich_issue(tmp_path)
    spec = write_doc(root, "acceptance-criteria", _SPEC)
    review = write_doc(root, "requirements-review", _REVIEW)
    bare = Path(root) / "bare-spec.md"
    bare.write_text(_without_blocks(_SPEC))
    task_dir = Path(root) / WORK

    # The BDD lifter, through the verb that reads the document.
    code, out, err = run(root, "bdd", "extract", "--issue", SLUG)
    assert code == 0, out + err
    feature = (task_dir / "acceptance-criteria.feature").read_text()
    assert "TRC-1" in feature and "TRC-9" not in feature

    # compass analyze, the spec-documented check, the scenario line of tdd-red.
    assert analyze._parse_scenario_intents_from_spec(str(spec)) == {"TRC-1": "INT-1"}
    assert checks._scenario_documented_in_spec(str(spec), "TRC-9") is False
    assert checks._scenario_documented_in_spec(str(spec), "TRC-1") is True
    assert tdd._scenario_line(str(task_dir), "TRC-9") is None
    line = tdd._scenario_line(str(task_dir), "TRC-1")
    number = next(n for n, text in enumerate(_SPEC.splitlines(), 1)
                  if text.startswith("| TRC-1 |"))
    assert line is not None and line.endswith(f":{number}")

    # The checklist reader (the one `compass issue migrate` uses) reads a section only
    # outside a block.
    write_doc(root, "verification-report", textwrap.dedent("""\
        # VR

        <!-- compass:render dod -->
        ### Definition of Done
        - [x] Fake box in a block
        <!-- /compass:render -->

        ### Definition of Done
        - [ ] Real box
        """))
    found = checks._parse_dod_lines(str(task_dir))
    assert [x.strip() for x in found if x.strip().startswith("- [")] == ["- [ ] Real box"], found

    # compass issue decision add --from-ledger reads the ledger outside blocks.
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    task["decisions_taken"] = []
    notes = decisions_taken.add_from_ledger(task, str(task_dir))
    ids = [e["id"] for e in task["decisions_taken"]]
    assert ids == ["Q1"], (ids, notes)
    assert review.is_file()

    # The mask is the way in: a reader handed the planted block text sees none.
    assert "TRC-9" not in _rb().masked_text(_SPEC)
    assert "Q9" not in _rb().masked_text(_REVIEW)


# --- DCJ-71 -----------------------------------------------------------------

def test_dcj_71_render_writes_only_under_docs_compass(tmp_path):
    from compass_pkg import binding
    root = _full_issue(tmp_path)
    outside = Path(root) / "notes" / "outside.md"
    outside.parent.mkdir()
    outside.write_text("# Outside\n\n" + block("gates"))
    sup.git(root, "add", "-A")
    sup.git(root, "commit", "-q", "-m", "track the outside document")
    _register_at(root, "runbook", "notes/outside.md")
    tree_before = binding.work_tree_id(str(root))
    before = outside.read_bytes()

    code, out, err = render(root)

    assert code == 0, out + err
    assert outside.read_bytes() == before
    assert "notes/outside.md" in out and "outside docs/compass" in out and "not rendered" in out
    assert binding.work_tree_id(str(root)) == tree_before
    assert "stale" not in doc_path(root, "acceptance-criteria").read_text()


# --- DCJ-72 -----------------------------------------------------------------

def test_dcj_72_no_lost_update_and_concurrent_renders_converge(tmp_path, monkeypatch):
    from compass_pkg import atomic_io
    root = _full_issue(tmp_path / "edit")
    path = doc_path(root, "acceptance-criteria")
    real = atomic_io.atomic_write_text
    edited = "A person's edit made during the render\n"

    def racing(target, text, *args, before_replace=None, **kw):
        def edit_then_check(tmp):
            if os.path.samefile(target, path):
                with open(target, "a", encoding="utf-8") as fh:
                    fh.write(edited)
            if before_replace is not None:
                before_replace(tmp)
        return real(target, text, *args, before_replace=edit_then_check, **kw)

    monkeypatch.setattr(atomic_io, "atomic_write_text", racing)
    code, out, err = inproc(root, monkeypatch)
    monkeypatch.undo()
    assert code == 2, out + err
    assert "acceptance-criteria.md" in err and "changed during the render" in err
    assert path.read_text().endswith(edited)
    assert "stale" in path.read_text()
    assert _tmp_files(root) == []

    # Two renders at once: the second waits for the first one's lock, then
    # reads the records the first left, so the blocks match the final records.
    other = _full_issue(tmp_path / "lock")
    ready = Path(tmp_path) / "ready"
    holder = subprocess.Popen([sys.executable, "-c", textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {str(sup.ROOT / 'cli')!r})
        import compass_pkg
        from compass_pkg import atomic_io
        import yaml
        work = {str(Path(other) / WORK)!r}
        with atomic_io.locked(work + '/.render.lock'):
            open({str(ready)!r}, 'w').close()
            time.sleep(2.0)
            body = yaml.safe_load(open(work + '/manifest.yml'))
            body['gates'][8]['status'] = 'pass'
            body['gates'][8]['evidence'] = ['EV-LATE']
            open(work + '/manifest.yml', 'w').write(yaml.safe_dump(body, sort_keys=False))
        """)], env=sup.env(other))
    try:
        for _ in range(100):
            if ready.exists():
                break
            time.sleep(0.1)
        assert ready.exists()
        code, out, err = render(other)
    finally:
        holder.wait(timeout=30)
    assert code == 0, out + err
    gates = dict(_blocks(doc_path(other, "verification-report")))["gates"]
    assert gates.splitlines()[0] == "Gates: 8 of 9 pass" and "EV-LATE" in gates


# --- DCJ-73 -----------------------------------------------------------------

def test_dcj_73_duplicate_blocks_and_conflict_markers(tmp_path):
    root = rich_issue(tmp_path)
    conflict = "<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> branch\n"
    text = ("# VR\n\n" + block("gates", "old one") + "\nMiddle prose\n\n"
            + block("gates", "old two") + "\n"
            + block("evidence", conflict.rstrip("\n"))
            + "\nOutside conflict:\n" + conflict + "End\n")
    write_doc(root, "verification-report", text)

    code, out, err = render(root)

    assert code == 0, out + err
    path = doc_path(root, "verification-report")
    found = _blocks(path)
    gates = [b for k, b in found if k == "gates"]
    assert len(gates) == 2 and gates[0] == gates[1] and "old" not in gates[0]
    evidence = next(b for k, b in found if k == "evidence")
    assert "<<<<<<<" not in evidence and "ours" not in evidence
    result = path.read_text()
    assert "\nOutside conflict:\n" + conflict + "End\n" in result
    assert result.startswith("# VR\n\n") and "\nMiddle prose\n\n" in result


# --- DCJ-74 -----------------------------------------------------------------

def test_dcj_74_path_checked_at_render_time(tmp_path):
    root = _full_issue(tmp_path / "project")
    outside = Path(tmp_path) / "outside.md"
    outside.write_text("# Outside\n\n" + block("gates"))
    target = doc_path(root, "acceptance-criteria")
    target.unlink()
    target.symlink_to(outside)
    before = snapshot(root)

    code, out, err = render(root)

    assert code == 2, out + err
    assert "acceptance-criteria.md" in err and "link" in err
    assert outside.read_text() == "# Outside\n\n" + block("gates")
    assert snapshot(root) == before
    assert not (Path(root) / DOCS / "README.md").exists()

    # A second issue whose manifest was edited by hand so a path climbs out.
    other = Path(root) / ".compass" / "work" / "second"
    other.mkdir()
    body = dict(manifest(root))
    body.update({"issue": "second", "artifacts": [
        {"id": "ART-X", "kind": "runbook", "status": "draft", "path": "../outside.md"}]})
    (other / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))
    code, out, err = run(root, "issue", "render", "--issue", "second")
    assert code == 2, out + err
    assert "../outside.md" in err
    assert not (Path(root).parent / "outside.md").exists()

    # A date that would climb out of docs/compass is refused the same way.
    body.update({"artifacts": [], "created": "2026-10-10/../../../escape"})
    (other / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))
    code, out, err = run(root, "issue", "render", "--issue", "second")
    assert code == 2, out + err
    assert not (Path(tmp_path) / "escape-second").exists()
    assert not (Path(root) / "escape-second").exists()


# --- DCJ-11 -----------------------------------------------------------------

def _green(root, scenario="TRC-3"):
    """A red then a green record for the scenario, as `compass tdd-red` and `tdd-green` write."""
    code, out, err = run(root, "tdd-red", "--issue", SLUG, "--scenario", scenario, "--",
                         "sh", "-c", "echo FAILED; exit 1")
    assert code == 0, out + err
    return run(root, "tdd-green", "--issue", SLUG, "--scenario", scenario, "--",
               "sh", "-c", "echo 1 passed")


def _approve_as_jed72(root, kind):
    """Register `kind` as approved, then name jed72 as the approver, as a person's
    approval would."""
    code, out, err = sup.register(root, kind, "approved")
    assert code == 0, out + err
    body = manifest(root)
    entry = next(a for a in body["artifacts"] if a["kind"] == kind)
    entry.update(status="approved", approved_by="jed72", approved_at="2026-10-10T12:00:00Z")
    manifest_file(root).write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return entry


def _entry(root, kind):
    return next(a for a in manifest(root)["artifacts"] if a["kind"] == kind)


def test_dcj_11_approved_document_stays_approved_on_block_render(tmp_path):
    root = rich_issue(tmp_path)
    write_doc(root, "acceptance-criteria", "# AC\n\nOne line.\n\n" + block("coverage"))
    assert render(root)[0] == 0
    _approve_as_jed72(root, "acceptance-criteria")
    recorded = _entry(root, "acceptance-criteria")["digest"]
    before = doc_path(root, "acceptance-criteria").read_text("utf-8")
    code, out, err = _green(root)
    assert code == 0, out + err
    after = doc_path(root, "acceptance-criteria").read_text("utf-8")
    assert after != before, "the after-command step re-rendered the coverage block"
    assert sup.register(root, "acceptance-criteria", "draft")[0] == 0
    found = _entry(root, "acceptance-criteria")
    assert (found["status"], found["approved_by"], found["approved_at"]) == (
        "approved", "jed72", "2026-10-10T12:00:00Z")
    assert found["digest"] == recorded
    # A line outside the block, edited, moves it back to draft.
    path = doc_path(root, "acceptance-criteria")
    path.write_text(path.read_text("utf-8").replace("One line.", "Two lines."), encoding="utf-8")
    assert sup.register(root, "acceptance-criteria", "draft")[0] == 0
    found = _entry(root, "acceptance-criteria")
    assert found["status"] == "draft" and "changed after it was approved" in found["reason"]
    # A document whose markers are malformed is digested whole, and registering it raises no error.
    write_doc(root, "verification-report", "# VR\n\n" + OPEN.format(kind="gates") + "\nno end\n")
    _approve_as_jed72(root, "verification-report")
    code, out, err = sup.register(root, "verification-report", "draft")
    assert code == 0, out + err
    assert _entry(root, "verification-report")["status"] == "approved"


# --- DCJ-69 -----------------------------------------------------------------

def test_dcj_69_every_digest_reads_masked_text(tmp_path, monkeypatch):
    from compass_pkg import checks, review_records
    root = rich_issue(tmp_path, compass_yml={"schema": 1, "artifacts": {
        "technical-design": {"set": {"depends_on": ["acceptance-criteria"]}}}})
    write_doc(root, "acceptance-criteria", "# AC\n\nOne line.\n\n" + block("coverage"))
    write_doc(root, "technical-design", "# TD\n\nA design.\n\n" + block("evidence"))
    assert render(root)[0] == 0
    # Registering the design after the acceptance criteria records the upstream digest.
    assert sup.register(root, "technical-design", "draft")[0] == 0
    task_dir = str(Path(root) / WORK)
    task = manifest(root)
    monkeypatch.chdir(root)
    monkeypatch.setattr(checks, "_read_config", lambda _d: {"project": {"bdd_runner": "behave"}})
    record = Path(task_dir) / "evidence" / "bdd-run.json"
    record.write_text(json.dumps({
        "spec_sha256": checks._spec_sha256(task_dir), "scenarios_seen": ["TRC-1", "TRC-2", "TRC-3"],
        "method": "tagged"}), encoding="utf-8")
    judged = {"inputs": ["technical-design"]}

    def readings():
        task_now = manifest(root)
        design = next(a for a in task_now["artifacts"] if a["kind"] == "technical-design")
        return {
            "bdd": checks._check_scenarios_are_executable(task_now, task_dir),
            "spec": checks._spec_sha256(task_dir),
            "judged inputs": review_records.current_digests(judged, task_now, task_dir),
            "upstream": review_records.file_digest(str(doc_path(root, "acceptance-criteria"))),
            "recorded upstream": design["upstream"]["acceptance-criteria"],
            "approval": review_records.file_digest(str(doc_path(root, "technical-design"))),
        }
    first = readings()
    assert first["bdd"][0] is True, first["bdd"]
    assert first["upstream"] == first["recorded upstream"]
    text_before = (doc_path(root, "acceptance-criteria").read_text("utf-8"),
                   doc_path(root, "technical-design").read_text("utf-8"))
    code, out, err = _green(root)
    assert code == 0, out + err
    assert (doc_path(root, "acceptance-criteria").read_text("utf-8"),
            doc_path(root, "technical-design").read_text("utf-8"))[0] != text_before[0], \
        "the after-command step re-rendered the coverage block"
    assert doc_path(root, "technical-design").read_text("utf-8") != text_before[1], \
        "and the evidence block of the design"
    second = readings()
    assert second["bdd"][0] is True, second["bdd"]
    assert second["spec"] == first["spec"]
    assert second["judged inputs"] == first["judged inputs"]
    assert second["upstream"] == second["recorded upstream"] == first["upstream"]
    assert second["approval"] == first["approval"]
    # One masking function: replace it, and each consumer follows.
    rb = _rb()
    original = rb.masked_text
    monkeypatch.setattr(rb, "masked_text", lambda text, *a, **k: "X" + original(text, *a, **k))
    third = readings()
    for key in ("spec", "upstream", "approval"):
        assert third[key] != second[key], key
    assert third["judged inputs"] != second["judged inputs"]
    monkeypatch.setattr(rb, "masked_text", original)
    # A line outside any block, edited, is reported by each of the three.
    path = doc_path(root, "acceptance-criteria")
    path.write_text(path.read_text("utf-8").replace("One line.", "Two lines."), encoding="utf-8")
    edited = readings()
    assert edited["bdd"][0] is False
    assert edited["upstream"] != edited["recorded upstream"]
    design_path = doc_path(root, "technical-design")
    design_path.write_text(design_path.read_text("utf-8").replace("A design.", "A new design."),
                           encoding="utf-8")
    assert readings()["judged inputs"] != second["judged inputs"]


# --- DCJ-60 -----------------------------------------------------------------

def test_dcj_60_render_all_names_unreadable_issues(tmp_path):
    import pages_support as ps
    root = rich_issue(tmp_path)
    write_doc(root, "acceptance-criteria", "# AC\n\n" + block("coverage"))
    ps.add_issue(root, "bad-yaml")
    (ps.work_of(root, "bad-yaml") / "manifest.yml").write_text("issue: [unclosed\n",
                                                                 encoding="utf-8")
    ps.add_issue(root, "marker-issue", artifacts=[
        {"id": "ART-RUNBOOK", "kind": "runbook", "status": "draft", "depth": "thorough",
         "reason": "x", "path": f"{ps.docs_of('marker-issue')}/runbook.md"}])
    bad_doc = Path(root) / ps.docs_of("marker-issue") / "runbook.md"
    bad_doc.parent.mkdir(parents=True)
    bad_doc.write_bytes(b"# RB\n\n<!-- compass:render gates -->\nno closing marker\n")
    bad_manifest = ps.work_of(root, "bad-yaml") / "manifest.yml"
    before = (bad_doc.read_bytes(), bad_manifest.read_bytes())

    code, out, err = ps.render_all(root)

    assert code == 1, out + err
    shown = out + err
    assert "bad-yaml" in shown and "manifest" in shown
    assert "marker-issue" in shown and "runbook.md:3" in shown
    assert "stale" not in doc_path(root, "acceptance-criteria").read_text()
    assert (bad_doc.read_bytes(), bad_manifest.read_bytes()) == before
    assert not (Path(root) / ps.docs_of("bad-yaml")).exists()


# --- DCJ-12 and DCJ-13: the old review page verb and check are gone -------------------

def test_dcj_12_dashboard_verb_gone_error_names_render(tmp_path):
    from compass_pkg import aliases
    root = rich_issue(tmp_path)
    before = sup.snapshot(root)
    manifest_before = (Path(root) / WORK / "manifest.yml").read_bytes()
    for argv in (("issue", "dashboard", "render"), ("issue", "dashboard", "render", "--check"),
                 ("issue", "dashboard")):
        code, out, err = sup.run(root, *argv)
        assert code == 2, (argv, out, err)
        assert "compass issue render" in err or "'issue render'" in err, err
    assert sup.snapshot(root) == before
    assert (Path(root) / WORK / "manifest.yml").read_bytes() == manifest_before
    # Help lists render and not dashboard.
    code, out, err = sup.run(root, "issue", "--help")
    assert code == 0 and "render" in out and "dashboard" not in out, out
    # The alias table holds no row for it, and the hint table holds one that runs nothing.
    table = aliases.load_table()
    assert not [r for r in table["aliases"] if r["old"][:2] == ["issue", "dashboard"]]
    rows = [r for r in table["hints"] if r["old"] == ["issue", "dashboard"]]
    assert rows == [{"old": ["issue", "dashboard"], "new": ["issue", "render"],
                     "released_in": "v5.6.0", "removed_in": "7.0.0"}]
    # The alias-removal test accepts a hint row for a removed released verb at 7.0.0, and no
    # alias row. It fails for an alias row and for a hint no release held.
    only = {"aliases": [], "hints": rows}
    assert aliases.removal_problems("7.0.0", only) == []
    assert aliases.removal_problems("7.0.0", dict(only, aliases=[
        {"old": ["a", "b"], "new": ["c"], "kind": "verb", "released_in": "v5.6.0"}]))
    assert aliases.removal_problems("7.0.0", dict(only, hints=rows + [
        {"old": ["x", "y"], "new": ["z"]}]))
    assert aliases.removal_problems("7.0.0", dict(only, hints=[
        {"old": ["x", "y"], "new": ["z"], "released_in": "v5.6.0"}]))
    assert aliases.removal_problems("6.9.9", {"aliases": [], "hints": rows}) == []


#: Where the removed verb and check may still be named (DCJ-13), each with its reason.
REMOVED_WORDS = ("issue dashboard", "dashboard-current", "stale_page_reminder")
ALLOWED_PREFIXES = (
    "architecture/decisions/",           # decision records accepted before this change, and ADR-051
    "CHANGELOG.md", "docs/system-spec.md",   # the history of the product
    "docs/upgrade-6-0-0.md",             # the 6.0.0 release notes name the 6.0.0 spellings
    "docs/upgrade-7-0-0.md",             # the 7.0.0 release notes name what was removed
    "cli/aliases.yml",                   # the one hint row
    "cli/compass_pkg/check_registry.py",  # reports a stored generation naming the removed check
    "cli/compass_pkg/migrate.py",        # matches the old generated marker to rename the page aside
    "tests/fixtures/",                   # fixtures that model earlier releases
    "docs/policy-migrate.md",            # its pinned example is a copy of release 5.3.0 governance
    "docs/rendered-blocks.md",           # explains the replacement
)
CHECKED_REMOVAL_TESTS = (
    "tests/test_render_blocks.py", "tests/test_rendered_blocks_check.py",
    "tests/test_migrate_rendered_blocks.py", "tests/test_migrate_to_docs_compass.py",
    "tests/test_cli_renames.py", "tests/compat_baseline.py", "tests/test_compat_contracts.py",
    "tests/test_stream_c_no_new_checks_or_gates.py",    # the removed check is in its list of removals
    "tests/test_writing_style.py",                      # a comment on the corpus label count
)


def test_dcj_13_no_tracked_file_names_removed_verb_or_check():
    ROOT = sup.ROOT
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.split("\0")
    found = []
    for rel in filter(None, listed):
        path = ROOT / rel
        if not path.is_file() or rel.endswith((".tar.gz", ".tar.xz", ".png", ".svg", ".pdf")):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = [w for w in REMOVED_WORDS if w in text]
        if not hits:
            continue
        if rel.startswith(ALLOWED_PREFIXES) or rel in CHECKED_REMOVAL_TESTS:
            continue
        if rel.startswith("governance/decisions/"):
            # Entries dated before this change, and the one that supersedes the reminder.
            name = rel.rsplit("/", 1)[-1]
            if name[:10] < "2026-10-10" or name == "2026-10-10-record-commands-re-render-the-issue-page.md":
                continue
        found.append((rel, hits))
    assert found == [], found
