# Review brief - refusal-template-follow-ups

Review `git diff a68e962` on branch `refusal-template-follow-ups` against `acceptance-criteria.md` and `technical-design.md` beside this file.

1. Does each criterion, RTF-1 to RTF-6, have a test that fails without the change?
2. `emit_refusal` in `hooks/pre-tool.sh`: when python3 fails, with or without output, does the hook still print Blocked, Why and Fix with the code, and still exit 2?
3. Does `_cap` in `cli/compass_pkg/refusals.py` change any refusal text that a test or `docs/refusal-codes.md` compares exactly?
4. Does any user-visible text still say "3.9", "re-try" or "re-frame as a spike"?
5. Do the measured eval's results in `scratchpad/d45-eval/report.md` match those of the run for PR #216 in `scratchpad/d38-eval/report.md`?

Read only. Do not run anything in the checkout while the eval or the suite runs.
