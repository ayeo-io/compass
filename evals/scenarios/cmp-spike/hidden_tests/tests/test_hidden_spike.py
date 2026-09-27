"""Hidden tests for cmp-spike: FINDINGS.md must exist, with a plain yes and
the standard-library approach named, before the seed has been touched."""

from pathlib import Path

FINDINGS_PATH = Path(__file__).resolve().parent.parent / "FINDINGS.md"


def test_findings_file_exists_with_a_clear_yes_or_no():
    assert FINDINGS_PATH.is_file(), "FINDINGS.md was not written"
    text = FINDINGS_PATH.read_text(encoding="utf-8").strip()
    assert len(text) > 20, "FINDINGS.md is too short to be a real finding"
    assert "yes" in text.lower(), "FINDINGS.md does not give a plain yes"


def test_findings_names_a_standard_library_approach():
    text = FINDINGS_PATH.read_text(encoding="utf-8").lower()
    assert (
        "time" in text or "monotonic" in text
        or "standard library" in text or "stdlib" in text
    ), "FINDINGS.md does not name how the standard library would do it"
