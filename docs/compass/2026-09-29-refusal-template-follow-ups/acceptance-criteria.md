# Acceptance criteria - refusal-template-follow-ups

Intent `INT-1`: a refusal keeps its shape when python3 fails, and every
refusal text and guard is exact. Source: spec D45.

| Id | Scenario |
|---|---|
| RTF-1 | Given a python3 that fails and prints something, when the hook refuses, then it prints a `Blocked:` line naming the edit target, a `Why:`, a `Fix:` with the code, and then python3's own output. |
| RTF-2 | Given the registry's Fix lines, then `python-missing` says 3.10+, each `tdd-red` fix shows `--scenario <id>`, `no-acceptance-criteria` names `/compass:assess --reassess`, and every line says "retry" one way. |
| RTF-3 | Given a template parameter longer than 20 words at run time, when a refusal renders, then the parameter is cut and the refusal stays under 60 words. |
| RTF-4 | Given the guards, then the call-site test finds a code only as an argument to the hook's refusal functions or `render()`, the literal scan's own test runs the real scan, the registry's comment says only a missing field fails, and a test runs the hook under a python3 older than 3.10 when one is present. |
| RTF-5 | Given `scripts/`, then no string the scripts print says "triage", and the literal scan covers `scripts/`. |
| RTF-6 | Given the texts, then `docs/refusal-codes.md` does not claim the CLI refuses with these codes, no fixture renders "the the", no comment describes the old refusal blocks, and `hooks/pre-tool.sh` has no idiom. |
