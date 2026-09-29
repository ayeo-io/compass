# Verification report - refusal-template-follow-ups

**Result:** pass · **Date:** 2026-09-29

| Check | Result | Evidence |
|---|---|---|
| RTF-1: a failed render keeps the refusal's shape | pass: the test failed before the change | `tests/test_refusal_registry.py` |
| RTF-2: the Fix texts | pass: the test failed before the change | `tests/test_refusal_registry.py` |
| RTF-3: parameters capped at 20 words | pass: the test failed before the change | `tests/test_refusal_registry.py` |
| RTF-4: guards that can fail | pass: each new test failed before the change | `tests/test_refusal_registry.py` |
| RTF-5: no "triage" in `scripts/*.sh` | pass: the scan failed before the change | `tests/test_printed_strings_name_no_retired_word.py` |
| RTF-6: page claim, fixture, comment, idioms | pass: the test failed before the change | `tests/test_refusal_registry.py` |
| Measured eval | same as the run for PR #216 on every behaviour | the PR's table |
| Review | pass after two rounds | `review.md` |
| The full suite | pass | `EV-T` |

The full suite ran with D46's work directory (`.compass/work/judge-sees-quick-fix-start/`) moved aside. That directory is ignored by git and left on disk from D46's branch, and the living-spec currency test reads it as a landed task. This branch does not contain D46, and CI does not see the directory.
