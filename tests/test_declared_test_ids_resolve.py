"""A declared test id resolves when the test really is on disk.

`declared-tests-resolve` exists because a test being *named* satisfies the
tested-before-ship and traceability guardrails - so a scenario citing a test
nobody wrote is invisible by construction. The check closes that hole by
looking the name up in the file.

The matcher must handle two cases:

  * A jest-style id - `file::outer > inner > the test` - has one `::`, so
    taking only the segment after the final `::` and searching for it
    verbatim finds the entire `outer > inner > the test` chain, which
    appears nowhere in a file that writes those as nested `describe`/`it`
    calls.
  * A test name ending in a non-word character - `@`, `)`, `.` - can never
    satisfy a trailing `\\b` boundary, whatever is on disk.

A matcher that misses either fails at the verify stage, *after* correctness
has been claimed, which is the worst moment to discover a bookkeeping
problem.

Scenario ids: see the issue's acceptance criteria (group C).
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "cli"))

from compass_pkg import checks                                  # noqa: E402

JEST_SUITE = """
describe('AuthService', () => {
  describe('createUser', () => {
    it('rejects an address with no domain', async () => {
      expect(true).toBe(true);
    });
    it('accepts realworld@', async () => {
      expect(true).toBe(true);
    });
  });
});
"""

PY_SUITE = """
def test_plain_name():
    pass
"""


def _project(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "src" / "tests").mkdir(parents=True)
    (tmp_path / "src" / "tests" / "auth.test.ts").write_text(
        JEST_SUITE, encoding="utf-8")
    (tmp_path / "src" / "tests" / "unit.py").write_text(
        PY_SUITE, encoding="utf-8")
    return tmp_path


def test_rcd_c1_nested_id_resolves(tmp_path):
    """A nested describe/it id must resolve to the test it names."""
    root = _project(tmp_path)
    tid = ("src/tests/auth.test.ts::AuthService > createUser > "
           "rejects an address with no domain")

    assert checks._test_id_resolves(tid, str(root)) is True, (
        "a jest-style nested id did not resolve, though the test is in the "
        "file. The matcher searched for the whole 'outer > inner > name' "
        "chain verbatim, which never appears in a file that nests them."
    )


def test_rcd_c2_trailing_non_word_resolves(tmp_path):
    """A test name ending in a non-word character must resolve.

    `\\b` after `@` needs a word character next. The name is followed by a
    quote, so the boundary can never be satisfied - the id is unresolvable
    regardless of what is on disk.
    """
    root = _project(tmp_path)
    tid = "src/tests/auth.test.ts::AuthService > createUser > accepts realworld@"

    assert checks._test_id_resolves(tid, str(root)) is True, (
        "a test name ending in '@' did not resolve, though it is in the file "
        "verbatim - the trailing word-boundary cannot be satisfied by a "
        "non-word final character"
    )


def test_rcd_c3_missing_test_still_fails(tmp_path):
    """The control: loosening the matcher must not stop it catching a test
    that does not exist.

    Without this, C1 and C2 pass against a matcher that returns True for
    everything - which would delete the check while leaving it green.
    """
    root = _project(tmp_path)

    absent_name = ("src/tests/auth.test.ts::AuthService > createUser > "
                   "a test nobody ever wrote")
    assert checks._test_id_resolves(absent_name, str(root)) is False, (
        "a declared test that exists in no file resolved anyway - the check "
        "has stopped checking"
    )

    absent_file = "src/tests/does_not_exist.test.ts::whatever"
    assert checks._test_id_resolves(absent_file, str(root)) is False, (
        "an id naming a file that does not exist resolved anyway"
    )


def test_rcd_c3b_partial_word_still_fails(tmp_path):
    """A name that only appears as part of a longer word must not resolve.

    This is what the word boundaries protect, and dropping them entirely
    would make `test_plain` match `test_plain_name`.
    """
    root = _project(tmp_path)

    assert checks._test_id_resolves(
        "src/tests/unit.py::test_plain", str(root)) is False, (
        "'test_plain' resolved against a file containing only "
        "'test_plain_name' - the matcher now matches substrings, which lets a "
        "misspelled or truncated id pass"
    )

    # And from the front. A check on the trailing boundary alone would
    # still pass with the leading boundary removed, so this tests the
    # front too.
    assert checks._test_id_resolves(
        "src/tests/unit.py::plain_name", str(root)) is False, (
        "'plain_name' resolved against a file containing only "
        "'test_plain_name' - the leading word boundary is not doing anything"
    )
