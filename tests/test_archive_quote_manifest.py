"""How archive-quote verification behaves in each environment it runs in
(archive-quote-verification).

`scripts/verify-archive-quotes.py` runs a two-part check: a committed hash
manifest (`skills/compass-runtime/archive-quote-manifest.json`) records, per
quoted span, a sha256 of its exact text - a fingerprint, not a copy - and
verification always checks the live quote against that hash. Where the
archive is also present, it additionally checks the quote directly against
the real file.

`skills/compass-runtime/writing-voice.md` quotes the real archive verbatim,
citing a path under `.compass/work/` for every pair. `.compass/work/` is
gitignored, so continuous integration never has it. Before this check
existed, comparing a quote against its cited file simply skipped whenever
the file was missing, so a fabricated or changed quote passed the build
every time continuous integration ran it.

The check gives three outcomes:
- the hash does not match the live quote: hard failure;
- the archive is present and the quote is not in the cited file: hard
  failure;
- the hash matches and there is no file to compare it against directly: a
  skip that names, by span, which quotes went unchecked and says the
  manifest is what confirmed them.

Every test below builds its own fixture reference text, fixture manifest,
and fixture archive directory in `tmp_path`, never the real repository
files. `TRC-1` proves the archive-absent path can actually fail, rather than
asserting it never gets exercised. `tests/test_human_voice.py`'s `TRC-A2` and
`TRC-C2` call the same module against the real files, which is why that file
still uses `pytest.skip` when this developer's own checkout happens to be
missing the archive.

Criteria: the issue's acceptance criteria
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify-archive-quotes.py"


def _load_module():
    """The verification module, loaded by path - it has a hyphen in its
    file name, so it cannot be `import`ed as an ordinary package, the same
    reason `tests/test_human_voice.py` and `tests/test_voice_tells.py` load
    `scripts/voice-tells.py` this way."""
    spec = importlib.util.spec_from_file_location(
        "verify_archive_quotes_script", SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reference_with_one_pair(before_text: str) -> str:
    """A minimal writing-voice.md fixture: prose, then exactly one
    '### Pair 1' block quoting `before_text`, in the same shape
    `tests/test_human_voice.py` parses (Source/Before/After/What changed)."""
    return (
        "# Writing voice\n\n"
        "Some prose that is not a pair.\n\n"
        "### Pair 1 - a fixture pair\n\n"
        "Source: `fixture-issue/devlog.md`\n\n"
        "Before:\n\n"
        f"> {before_text}\n\n"
        "After:\n\n"
        "> A rewritten sentence.\n\n"
        "What changed: fixture only.\n"
    )


def _manifest_for(before_text: str, source: str = "fixture-issue/devlog.md") -> dict:
    """The same {span id: entry} shape `verify()`'s `manifest=` parameter
    takes - what `load_manifest()` returns after reading the manifest file
    off disk, not the raw {"entries": [...]} shape the file itself uses."""
    return {"pair-1": {"id": "pair-1", "source": source, "sha256": _sha256(before_text)}}


def test_trc_1_fabricated_quote_fails_when_archive_is_absent(tmp_path):
    """The scenario the issue exists for: continuous integration's own
    environment. The manifest recorded the hash of the original quote; the
    reference now carries a different quote; the archive root passed to
    `verify()` deliberately has no file at the cited path - not because the
    developer's machine happens to lack it, but because the test tells it
    to look nowhere. A guard that cannot fail here proves nothing."""
    module = _load_module()

    original_text = "The original, once-verified sentence."
    manifest = _manifest_for(original_text)

    fabricated_reference = _reference_with_one_pair("A sentence nobody ever verified.")

    empty_archive_root = tmp_path / "no-archive-here"
    empty_archive_root.mkdir()
    # No fixture-issue/devlog.md under this root at all -
    # simulates continuous integration exactly, where .compass/work/ is
    # gitignored and therefore never checked out.

    failures, unverified = module.verify(
        archive_root=empty_archive_root,
        reference_text=fabricated_reference,
        manifest=manifest,
    )

    assert failures, "a fabricated quote must fail even with no archive present"
    assert any("pair-1" in f for f in failures), (
        f"the failure must name the mismatched span: {failures}"
    )
    assert not unverified, (
        "a failed span is not merely 'unverified' - it is a hard failure"
    )


def test_trc_2_unaltered_quote_passes_via_manifest_when_archive_is_absent(tmp_path):
    """The companion case: the quote is exactly what the manifest last
    checked, and the archive still is not here. This must not fail - but
    it must not report a silent, unqualified pass either. It has to name
    the span it could not check directly."""
    module = _load_module()

    text = "A sentence that has not changed since it was verified."
    manifest = _manifest_for(text)
    reference = _reference_with_one_pair(text)

    empty_archive_root = tmp_path / "no-archive-here"
    empty_archive_root.mkdir()

    failures, unverified = module.verify(
        archive_root=empty_archive_root,
        reference_text=reference,
        manifest=manifest,
    )

    assert not failures, f"an unaltered quote must not fail: {failures}"
    assert unverified == ["pair-1"], (
        f"the unverified span must be named explicitly: {unverified}"
    )


def test_trc_3_genuine_quote_passes_by_direct_verification_when_archive_present(tmp_path):
    """With the archive present and the quote genuinely inside it,
    verification takes the direct-comparison branch: no span is left
    unchecked, because there was a real file to check it against."""
    module = _load_module()

    text = "A line that really is inside the archive file."
    manifest = _manifest_for(text)
    reference = _reference_with_one_pair(text)

    archive_root = tmp_path / "archive"
    archive_file = archive_root / ".compass" / "work" / "fixture-issue" / "devlog.md"
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text(
        f"# Devlog\n\nSome other line.\n{text}\nA trailing line.\n",
        encoding="utf-8",
    )

    failures, unverified = module.verify(
        archive_root=archive_root, reference_text=reference, manifest=manifest,
    )

    assert not failures, f"a genuine quote must pass: {failures}"
    assert unverified == [], (
        "with the archive present, nothing should be reported unverified"
    )


def test_trc_4_mismatched_quote_fails_not_skips_when_archive_present(tmp_path):
    """The archive is present and the quote is not in the cited file. This
    must stay a hard failure, not a skip."""
    module = _load_module()

    text = "A sentence that the reference claims is quoted."
    manifest = _manifest_for(text)
    reference = _reference_with_one_pair(text)

    archive_root = tmp_path / "archive"
    archive_file = archive_root / ".compass" / "work" / "fixture-issue" / "devlog.md"
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text(
        "# Devlog\n\nNone of this matches the quote above.\n", encoding="utf-8",
    )

    failures, unverified = module.verify(
        archive_root=archive_root, reference_text=reference, manifest=manifest,
    )

    assert failures, "a quote absent from its cited file must fail"
    assert any("pair-1" in f and "fixture-issue" in f for f in failures), (
        f"the failure must name the span and its source: {failures}"
    )
    assert unverified == [], "a hard failure is not a skip"


def test_trc_5_update_refuses_to_write_an_unverified_hash(tmp_path):
    """The regeneration path (`--update`) is the only sanctioned way to
    change a manifest entry, and it is only sanctioned because it re-checks
    the real file first. A quote the archive cannot confirm must not reach
    the manifest at all - proving that hand-editing a hash into the file
    cannot substitute for this path, because this path itself refuses to
    write one it has not checked."""
    module = _load_module()

    reference = _reference_with_one_pair("A quote the archive does not actually contain.")

    archive_root = tmp_path / "archive"
    archive_file = archive_root / ".compass" / "work" / "fixture-issue" / "devlog.md"
    archive_file.parent.mkdir(parents=True)
    archive_file.write_text("# Devlog\n\nCompletely unrelated content.\n", encoding="utf-8")

    manifest_path = tmp_path / "manifest.json"

    with pytest.raises(SystemExit):
        module.update_manifest(
            archive_root=archive_root,
            reference_text=reference,
            manifest_path=manifest_path,
        )

    assert not manifest_path.exists(), (
        "a manifest that skips an unverifiable span must never be written"
    )
