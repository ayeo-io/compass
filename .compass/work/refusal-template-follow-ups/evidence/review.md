# Review - refusal-template-follow-ups

**PASS** after two rounds and one fix made after the second round. It is a code-level review against `acceptance-criteria.md` and `technical-design.md` beside this file. The reviewer ran the full suite in scratch copies of the checkout: one with the change applied and one with it reversed.

## Round 1: fail

Blockers:

1. Four tests in `tests/test_hook_failure_matrix.py` still expected "re-try". Fixed: they expect "retry".
2. The call-site test counted `python-missing` as called because of a comment in `hooks/pre-tool.sh`. Fixed: the test drops comment lines, and it accepts a code in brackets inside a `printf` line. The control test plants that comment.
3. Criterion RTF-6 says the hook has no idiom, but its comments said "front door" and "low bar". Fixed: both are reworded.

Suggestions, all applied:

- The Python 3.9 test never reached a refusal. It now removes `.red` and asserts exit 2 and `[no-red-on-record]`.
- The registry-comment test checked only wording. It now calls `render()` with an extra field, and without a needed one.
- The fallback test now checks the order Blocked, Why, Fix, and that python3's output is indented after the Fix line.
- The last "re-try" string in the hook is now "retry".
- `emit_refusal` ends with `return 0`.
- `_cap` splits on runs of whitespace.
- A new test fails if any fixture renders a doubled word. The reviewer showed that it can fail.

## Round 2: fail

1. `tests/test_hook_enforces_g2.py:137` expected "frame" in the refusal for missing acceptance criteria (`no-acceptance-criteria`). Fixed: it expects `/compass:assess --reassess`, and its message says "re-assess". The full suite in the checkout had caught the same failure, and the fix was in place before this round's report arrived.

The reviewer confirmed that every round 1 fix holds and adds no new defect. The only difference between the full-suite runs with the change and without it was this test. The other 58 failures in the copies come from missing git metadata and fail the same way without the change.

## Eval

The measured run matches the run for PR #216 on every behaviour. "Assessed before first edit" is 0/5 in both. Each session tries an edit before it assesses, and the hook blocks that edit.

## Filed separately

Spec D47 (`printed-wording-sweep`): the reviewer found this printed text outside this change:

- "REFRAME NUDGE" and "file a reframe now" in `hooks/stop.sh`;
- "Re-frame:" in `cli/compass_pkg/routing.py`;
- "accretion" in `scripts/install.sh`;
- "Needs Python 3" in `README.md` and `docs/five-minutes.md`.
