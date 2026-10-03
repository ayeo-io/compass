"""Reading an existing brief into an issue - the source reader.

A team arriving with a brief already written should not have to retype it. The
reader is the mechanical half of that: resolve a source, read it, hash it, and
say clearly when it cannot. Reshaping the document into `intent.md` is the
session's job, not this module's.

Scenario ids: ING-A1, A2, A4, D2 in
ingest-an-existing-brief/acceptance-criteria.md
"""
from __future__ import annotations

import os

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

import compass_pkg  # noqa: E402,F401  - resolves the bundled yaml
from compass_pkg.core import CompassError  # noqa: E402


def test_ing_a1_a_local_file_is_read_and_hashed(tmp_path):
    """ING-A1: a local file becomes a source document, and is not modified.

    "And the source file is unchanged" is asserted rather than assumed: this
    module reads someone else's document, and the one thing it must never do is
    write to it.
    """
    from compass_pkg.ingest import read_source

    src = tmp_path / "search-v2.md"
    body = "# Search v2\n\nThe problem is that search is slow.\n"
    src.write_text(body, encoding="utf-8")
    before = src.read_bytes()

    doc = read_source(str(src))

    assert doc.text == body
    assert doc.origin == str(src)
    assert doc.scheme == "file"
    assert len(doc.sha256) == 64, "the source is hashed so provenance can pin it"
    assert src.read_bytes() == before, "the source document was modified"


def test_ing_a2_the_source_may_be_called_anything(tmp_path):
    """ING-A2: no particular filename is needed.

    The whole point is that the document already exists, under whatever
    name its author gave it - so this walks several shapes rather than
    asserting one.
    """
    from compass_pkg.ingest import read_source

    for name in ("notes/2026-q3-search.txt", "BRIEF", "a.b.c.markdown",
                 "Product Requirements (final).md"):
        src = tmp_path / name
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("anything\n", encoding="utf-8")
        assert read_source(str(src)).text == "anything\n", (
            "%r was not read on the same terms as any other source" % name)


def test_ing_a4_a_source_that_is_not_there_names_what_it_looked_for(tmp_path):
    """ING-A4: a missing source fails, and the message names the path.

    "Could not read the source" sends the reader nowhere. The path it tried is
    the whole content of a useful failure - most of the time the answer is a
    typo the reader can see the moment it is quoted back.
    """
    from compass_pkg.ingest import read_source

    missing = tmp_path / "does-not-exist.md"
    with pytest.raises(CompassError) as exc:
        read_source(str(missing))
    assert str(missing) in str(exc.value), (
        "the failure does not name what it looked for: %s" % exc.value)


def test_ing_a4b_a_directory_is_refused_as_a_source(tmp_path):
    """A path that exists but is not a readable document.

    `os.path.exists` is true for a directory, so a reader that checks only
    existence gets an IsADirectoryError from deep inside `open` - a traceback
    rather than a message. The failure mode is different from "not there" and
    so is the fix, so the message has to be different too.
    """
    from compass_pkg.ingest import read_source

    with pytest.raises(CompassError) as exc:
        read_source(str(tmp_path))
    assert "director" in str(exc.value).lower(), (
        "a directory was not distinguished from a missing file: %s" % exc.value)


def test_ing_d2_a_fetch_that_fails_says_so_loudly():
    """ING-D2: no network, no silent failure.

    The danger is not the error - it is an empty document arriving as if it
    were the brief, and the whole issue being built on nothing. The opener is
    injected so this runs with no network at all.
    """
    from compass_pkg.ingest import read_source

    def dead_opener(url):
        raise OSError("[Errno 8] nodename nor servname provided")

    with pytest.raises(CompassError) as exc:
        read_source("https://example.invalid/brief.md", opener=dead_opener)

    message = str(exc.value)
    assert "https://example.invalid/brief.md" in message, (
        "the failure does not name the source it tried to fetch: " + message)
    assert "nodename" in message, (
        "the underlying reason was swallowed, so the reader cannot tell a "
        "typo from an outage: " + message)


def test_ing_d2b_an_empty_document_is_not_silently_accepted(tmp_path):
    """A source that reads as nothing is refused rather than ingested.

    The control on ING-D2 from the other side: a fetch can succeed and return
    an empty body - a login page that redirected to nothing, a file someone
    truncated. Accepting it produces an `intent.md` built on no material at
    all, and every downstream stage would proceed as though there were an
    intent.
    """
    from compass_pkg.ingest import read_source

    empty = tmp_path / "empty.md"
    empty.write_text("   \n\n", encoding="utf-8")
    with pytest.raises(CompassError) as exc:
        read_source(str(empty))
    assert "empty" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# U2 - the fetch, and the scheme rule on every hop
# ---------------------------------------------------------------------------

def test_ing_d4_a_url_that_is_not_https_is_refused():
    """ING-D4: only https sources are fetched, and the refusal says what to do.

    A brief becomes the issue's intent, so a document changed in transit
    shapes the acceptance criteria and everything after them. Recording that
    it arrived over plain HTTP would not prevent any of that.
    """
    from compass_pkg.ingest import read_source

    def must_not_run(url):                      # pragma: no cover - the point
        raise AssertionError("a non-https source reached the fetch: %s" % url)

    for url in ("http://example.com/brief.md",
                "ftp://example.com/brief.md",
                "file:///etc/passwd"):
        with pytest.raises(CompassError) as exc:
            read_source(url, opener=must_not_run)
        message = str(exc.value)
        assert "https" in message, message
        assert "export it to a file" in message.lower(), (
            "the refusal does not tell the person what to do instead: "
            + message)


def test_ing_d1_an_authenticated_source_is_refused_with_a_way_forward():
    """ING-D1: 401 and 403 are refused. Compass does not handle authentication.

    The whole behaviour is refusing well: the person is told the document
    needs credentials Compass does not have, and given the one way that
    always works.
    """
    import urllib.error

    from compass_pkg.ingest import read_source

    for code in (401, 403):
        def denied(url, code=code):
            raise urllib.error.HTTPError(url, code, "Unauthorized", {}, None)

        with pytest.raises(CompassError) as exc:
            read_source("https://wiki.internal/brief.md", opener=denied)
        message = str(exc.value)
        assert str(code) in message or "credential" in message.lower(), message
        assert "export it to a file" in message.lower(), (
            "a %d gave no way forward: %s" % (code, message))


def test_ing_d3_provenance_records_where_the_fetch_landed():
    """ING-D3: after a redirect, the origin is the final address.

    The risk the redirect rule exists for is ingesting a different document
    from the one asked for. Recording the address that was typed would hide
    exactly that.
    """
    from compass_pkg.ingest import read_source

    def redirected(url):
        return "# the real brief\n", "https://elsewhere.example/actual.md"

    doc = read_source("https://short.example/b", opener=redirected)
    assert doc.origin == "https://elsewhere.example/actual.md", (
        "provenance kept the typed address rather than where the fetch landed")


def test_ing_d4b_a_redirect_that_leaves_https_is_refused():
    """The downgrade case, proven by a refusal rather than by a passing test.

    `urllib.request` follows redirects AUTOMATICALLY, through
    HTTPRedirectHandler. An https URL redirecting to http would be fetched
    with the caller never seeing it - so a scheme check on the typed URL alone
    passes here while failing in fact. `governance/strategies.md` `S10`: a guard
    is accepted on a demonstrated failure, and this is the demonstration.
    """
    from compass_pkg.ingest import _https_only_redirect_handler

    handler = _https_only_redirect_handler()
    with pytest.raises(Exception) as exc:
        handler.redirect_request(
            None, None, 302, "Found", {}, "http://downgraded.example/brief.md")
    message = str(exc.value)
    assert "https" in message.lower(), message
    assert "downgraded.example" in message, (
        "the refusal does not name where the redirect tried to go: " + message)


def test_ing_d4c_a_redirect_that_stays_https_is_allowed():
    """The control. Without it, a handler that refused every redirect would
    pass the test above while breaking every real fetch."""
    from compass_pkg.ingest import _https_only_redirect_handler
    import urllib.request

    handler = _https_only_redirect_handler()
    req = urllib.request.Request("https://a.example/brief.md")

    class _Resp:
        def __init__(self):
            self.headers = {}

        def geturl(self):
            return "https://a.example/brief.md"

    out = handler.redirect_request(
        req, _Resp(), 302, "Found", {}, "https://b.example/brief.md")
    assert out is not None, "a same-scheme https redirect was refused"


# ---------------------------------------------------------------------------
# U3 - the verb, the snapshot, and provenance
# ---------------------------------------------------------------------------

def _project(tmp_path, slug="demo"):
    """A minimal project with one assessed issue."""
    import yaml

    work = tmp_path / ".compass" / "work" / slug
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (tmp_path / ".compass" / "current-task").write_text(slug + "\n")
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": slug, "created": "2026-08-25",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery"},
        "delivery_approach": "feature",
        "stages": {"assess": "full", "define": "full"},
        "evidence": [], "gates": [], "scenarios": [], "changed_files": [],
    }, sort_keys=False))
    return tmp_path, work


def _run_ingest(project, *args):
    import subprocess

    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "cli" / "compass"),
         "intent", "ingest", *args],
        cwd=str(project), capture_output=True, text=True, timeout=120)


def test_ing_c1_the_verb_writes_a_snapshot_and_records_where_it_came_from(tmp_path):
    """ING-C1: an ingested brief says where it came from.

    Two records, deliberately. The manifest's block is what `compass check` can
    read; the snapshot is what makes the invention rule auditable afterwards,
    because nobody can check "every statement traces to the source" against a
    document that is not there.
    """
    import yaml

    project, work = _project(tmp_path)
    src = tmp_path / "brief.md"
    src.write_text("# Search v2\n\nSearch is slow.\n", encoding="utf-8")

    run = _run_ingest(project, "--from", str(src))
    assert run.returncode == 0, run.stdout + run.stderr

    snapshot = work / "intent-source.md"
    assert snapshot.is_file(), "no intent-source.md snapshot was written"
    assert snapshot.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")

    manifest = yaml.safe_load((work / "manifest.yml").read_text())
    rec = manifest.get("intent_source")
    assert rec, "the manifest has no intent_source block"
    assert rec["origin"] == str(src)
    assert rec["scheme"] == "file"
    assert len(rec["sha256"]) == 64
    assert rec.get("ingested_at")

    assert not (work / "intent.md").exists(), (
        "the verb wrote intent.md - reshaping is the session's job, not the "
        "CLI's (technical-design.md DD-1)")


def test_ing_c1b_the_verb_refuses_to_overwrite_a_snapshot(tmp_path):
    """Re-ingesting must not silently replace the record of what arrived.

    The snapshot is evidence. Overwriting it on a second run would destroy the
    thing a reviewer checks `intent.md` against, and the second run is exactly
    when someone is unsure what happened on the first.
    """
    project, work = _project(tmp_path)
    src = tmp_path / "brief.md"
    src.write_text("# one\n", encoding="utf-8")
    assert _run_ingest(project, "--from", str(src)).returncode == 0

    src.write_text("# two, different\n", encoding="utf-8")
    run = _run_ingest(project, "--from", str(src))

    assert run.returncode != 0, "a second ingest silently replaced the snapshot"
    combined = (run.stdout + run.stderr).lower()
    assert "intent-source.md" in combined and "already" in combined, combined
    assert (work / "intent-source.md").read_text(encoding="utf-8") == "# one\n", (
        "the original snapshot was overwritten before the refusal")


def test_ing_a4c_a_missing_source_leaves_the_issue_untouched(tmp_path):
    """ING-A4's second clause: nothing is left half-created.

    Asserted against the manifest and the directory rather than trusting the exit
    code - a verb that fails after writing is the case this is for.
    """
    import yaml

    project, work = _project(tmp_path)
    before = yaml.safe_load((work / "manifest.yml").read_text())

    missing = tmp_path / "nope.md"
    run = _run_ingest(project, "--from", str(missing))
    assert run.returncode != 0

    # The message must be the READER's, naming the path it looked for. Without
    # this the test passes against a CLI that has no such verb at all - argparse
    # exits non-zero and writes nothing, which is the same shape as success
    # here and proves nothing about the behaviour.
    # Since #293 the path is printed relative to the project root, so look
    # for the source as the project sees it.
    combined = run.stdout + run.stderr
    assert "no such source: " + os.path.relpath(missing, project) in combined, (
        "the failure does not name the source it looked for, so this is not "
        "the reader refusing:\n" + combined)

    assert not (work / "intent-source.md").exists()
    assert yaml.safe_load((work / "manifest.yml").read_text()) == before, (
        "the manifest was modified by a failed ingest")


def test_ing_d4d_a_bad_source_is_refused_for_the_right_reason(tmp_path):
    """The argument is checked before the issue's state is.

    The argument is checked before the snapshot, so a bad `--from` is
    refused for its own reason.

    A refusal that names the wrong cause is worse than a vague one: it sends
    the reader somewhere confidently.
    """
    project, work = _project(tmp_path)
    first = tmp_path / "brief.md"
    first.write_text("# one\n", encoding="utf-8")
    assert _run_ingest(project, "--from", str(first)).returncode == 0

    run = _run_ingest(project, "--from", "http://example.com/brief.md")
    combined = run.stdout + run.stderr

    assert run.returncode != 0
    assert "https" in combined, (
        "a non-https source was refused without mentioning the scheme rule:\n"
        + combined)
    assert "already exists" not in combined, (
        "the scheme problem was reported as a snapshot problem:\n" + combined)


def test_ing_a3_a_url_becomes_a_snapshot_and_a_record(tmp_path, monkeypatch):
    """ING-A3: the whole verb, over https, with no network.

    Patches `_fetch_https` in the module the reader resolves it from - not a
    name imported elsewhere. `read_source` looks up `_fetch_https` in
    `compass_pkg.ingest` at call time, and that is what this replaces.
    """
    from compass_pkg import ingest as ingest_module

    project, work = _project(tmp_path)
    typed = "https://wiki.internal/space/brief"
    landed = "https://wiki.internal/space/brief/v3"

    monkeypatch.setattr(
        ingest_module, "_fetch_https",
        lambda url: ("# Search v2\n\nSearch is slow.\n", landed))

    # The subprocess would not see the patch, so this exercises the verb's
    # handler directly with the arguments the parser would build.
    class _Args:
        source = typed
        task = None
        quiet = summary = verbose = json = False
        evidence_out = None

    monkeypatch.chdir(project)
    assert ingest_module.cmd_intent_ingest(_Args()) in (0, None)

    import yaml

    snapshot = work / "intent-source.md"
    assert snapshot.is_file()
    assert "Search is slow" in snapshot.read_text(encoding="utf-8")

    rec = yaml.safe_load((work / "manifest.yml").read_text())["intent_source"]
    assert rec["scheme"] == "https"
    assert rec["origin"] == landed, (
        "the record names the address that was typed rather than where the "
        "fetch landed, which is what ING-D3 exists to prevent")


def test_ing_a4d_an_oversized_local_source_is_refused_like_a_fetched_one(tmp_path,
                                                                        monkeypatch):
    """The size ceiling applies to both paths, not just the network one.

    `_fetch_https` reads at most MAX_SOURCE_BYTES + 1 so a misdirected fetch
    cannot pull an arbitrary body into memory. The local path needs the same
    bound, or a mistyped path at a database dump gives a MemoryError rather
    than a sentence through the local path.
    """
    from compass_pkg import ingest as ingest_module
    from compass_pkg.ingest import read_source

    monkeypatch.setattr(ingest_module, "MAX_SOURCE_BYTES", 64)
    big = tmp_path / "dump.md"
    big.write_text("x" * 200, encoding="utf-8")

    with pytest.raises(CompassError) as exc:
        read_source(str(big))
    message = str(exc.value)
    assert str(big) in message, message
    assert "larger" in message.lower() or "too large" in message.lower(), message
