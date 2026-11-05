"""A quote the verifier could not read is a failure, not a pass.

`scripts/verify-archive-quotes.py` exists to stop a fabricated archive quote
passing the build. Its own gap was the shape one step before fabrication: a
quote it could not parse at all.

`parse_pairs` sets `before` to `None` when the `Before:` block does not match
its blockquote pattern - a line written `>text` without the space is enough.
Downstream, `sha256_text(span["quoted"] or "")` hashed the empty string and
`_matches_archive("substring", "", archive_text)` reduced to `"" in
archive_text`, which is always true. So the span checked clean, and
`--update` would record `sha256("")` for it against a file it never matched.

That contradicted the script's own promise: `update_manifest` documents that
it "refuses - and writes nothing at all - if any span's archive file is
missing or does not contain the quoted text verbatim". A span that did not
parse belongs in that category and was not in it.

Scenario ids: see the issue's acceptance criteria.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify-archive-quotes.py"

# The quoted line both fixtures use, so the well-formed and malformed cases
# differ only in the one character that decides whether the parser matches.
QUOTED = "the line this pair claims to quote from the archive"

_REFERENCE = """### Pair 1

Source: `{source}`

Before:

{marker}{quoted}

After:

> something a colleague would say

What changed: the register.
"""


def _module():
    spec = importlib.util.spec_from_file_location("verify_archive_quotes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path, marker):
    """A reference plus an archive whose file really does contain the quote.

    `marker` is "> " for a blockquote the parser matches, and ">" for one it
    does not. Everything else is identical, so a difference in outcome can
    only come from the parse.
    """
    archive_rel = ".compass/work/an-issue/devlog.md"
    archive_file = tmp_path / archive_rel
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text(
        f"# Devlog\n\n{QUOTED}\n", encoding="utf-8")

    reference = tmp_path / "writing-voice.md"
    reference.write_text(
        _REFERENCE.format(source=archive_rel, marker=marker, quoted=QUOTED),
        encoding="utf-8")
    return reference, archive_file


def test_trc_1_an_unparsed_span_is_a_failure(tmp_path):
    module = _module()
    reference, _ = _fixture(tmp_path, ">")

    spans = module.current_spans(reference_text=reference.read_text())
    # The hash `--update` would itself have written for this span: the hash of
    # the empty string, because the quote did not parse. Using a wrong hash
    # here instead would make this test pass on a hash mismatch and prove
    # nothing about the parse failure.
    manifest = {
        s["id"]: {"source": s["source"], "sha256": module.sha256_text("")}
        for s in spans
    }

    failures, unverified = module.verify(
        archive_root=tmp_path,
        reference_text=reference.read_text(),
        manifest=manifest,
    )
    assert failures, (
        "a span whose quoted block did not parse was not reported as a "
        "failure. 'I could not find the quote' must not read as 'nothing is "
        f"wrong'.\nunverified={unverified}"
    )
    assert any("pars" in f.lower() or "quoted text" in f.lower()
               for f in failures), (
        f"the failure does not say the quote could not be read:\n{failures}"
    )


def test_trc_2_update_refuses_to_record_an_unparsed_span(tmp_path, capsys):
    module = _module()
    reference, _ = _fixture(tmp_path, ">")
    manifest_path = tmp_path / "archive-quote-manifest.json"
    # Pass `manifest_path` explicitly: without it `update_manifest` writes
    # to the repository's real manifest.
    assert manifest_path != module.MANIFEST, (
        "this test is about to write a manifest; it must not be the real one"
    )

    with pytest.raises(SystemExit):
        module.update_manifest(
            archive_root=tmp_path,
            reference_text=reference.read_text(),
            manifest_path=manifest_path,
        )

    # The scenario is "it refuses and writes nothing", so that is what is
    # asserted - not the wording of the exception, which carries the summary
    # while the per-span reason goes to stderr.
    assert not manifest_path.exists(), (
        "update refused but still wrote a manifest file"
    )
    reason = capsys.readouterr().err.lower()
    assert "did not parse" in reason, (
        f"the refusal does not say the span failed to parse, so a reader "
        f"cannot tell this from a missing archive file:\n{reason}"
    )


def test_trc_3_a_well_formed_span_still_verifies(tmp_path):
    """The control.

    Without it, the two tests above would pass against a script that
    rejected every span.
    """
    module = _module()
    reference, _ = _fixture(tmp_path, "> ")

    spans = module.current_spans(reference_text=reference.read_text())
    assert spans and spans[0].get("quoted"), (
        "the well-formed fixture did not parse - the control proves nothing"
    )
    manifest = {
        s["id"]: {"source": s["source"],
                  "sha256": module.sha256_text(s["quoted"])} for s in spans
    }

    failures, _ = module.verify(
        archive_root=tmp_path,
        reference_text=reference.read_text(),
        manifest=manifest,
    )
    assert not failures, (
        f"an ordinary well-formed quoted pair was rejected:\n{failures}"
    )
