# a-comment-only-edit-of-code-needs-no-failing-test

## Decided by

jed72

## Date

2026-10-19

## Supersedes

Nothing. It builds on the pre-tool hook's red-before-green rule and changes none of the entries that state it.

## Decision

An Edit of a Python or YAML file that changes only comments, docstrings or layout needs no failing test and no assessed issue. The hook proves this from the file on disk: it reads the file once, applies the Edit in memory and compares the file before and after. Every doubt gives the verdict the hook gave before, so the check fails closed. Shell is not covered. Eval fixture input, `evals/*/seed/`, is not production code. The five other path classes in question stay guarded.

**What comment-only means, per language.**

- Python (`*.py`): the syntax tree is the same before and after. A docstring may change its text only when it stays the first statement of the same module, class or function, is not an f-string, and the file mentions none of `__doc__`, `getdoc`, `help`, `doctest`, `exec` and `eval`.
- YAML (`*.yml`, `*.yaml`): the parser's events are the same: data, key order, anchors, aliases, tags and merge keys. A duplicate key, aliases that expand to more than 100000 nodes, and a file that does not parse are refused.
- Every other language, shell included, keeps its verdict.

**What counts as code even when it looks like a comment.** A pragma: `# type: ignore`, `# noqa`, `# nosec`, `# fmt: off`, `# pragma: no cover`, `# pylint:`, `# mypy:` and the other linter directives that the check lists. A shebang line and an encoding line. An Edit that adds a hidden character: a control character, a NUL byte, a bidirectional control or a zero-width character. The directives of common scanners and formatters: `# nosemgrep`, `# gitleaks`, `# checkov`, `# lgtm`, `# NOSONAR`, `# codeql`, `# yapf`, `# trivy` and `# tfsec`. A file whose first line is a template header such as cloud-init's `## template: jinja`. The encoding cookie of a Python file (PEP 263): Python decodes the source with it before it parses a line, so a cookie such as `utf-7` or `unicode_escape` turns text inside a comment into a line break. An Edit is code when the cookie before or after it is not `utf-8`, `utf8` or `ascii`, and when the Edit adds, removes, changes or moves the cookie. When the cookie is `ascii`, an Edit that leaves a non-ASCII character in the file is code, because Python cannot load such a file. The test for a pragma is a superset of the list, so it refuses more and never less.

**Why the check fails closed.** The check can only allow, so a doubt must never allow. A file over 1048576 bytes, a file that is not a regular file or is a symbolic link, an old text that is not found once, a file that does not parse before or after, a check that fails or runs out of budget, and a check that runs past its alarm are all judged as before: the Edit is refused unless a failing test is on record. A missing `python3` refuses with `python-missing`, as every reader of the hook does. The check runs before the issue lookup, because a comment cannot change what code does, so a damaged manifest or a missing issue changes nothing for it. A parser can be made slow on purpose (PyYAML takes about 90 seconds for 100000 `[` characters), so the charge to the work budget is computed from the file size before any parse and `signal.alarm` bounds the rest.

**Path classes.** A file is production code when it ships and runs for users, or runs the project's own delivery.

- `evals/*/seed/` is exempt. It holds input that the eval harness copies into a sandbox and never runs it in place. The pattern starts at the project root, and a `..` step cannot borrow it.
- `examples/` stays guarded: a project can keep production code there, and the contract does not define it as non-code.
- `cli/vendor/` stays guarded: every Compass process runs it.
- `.github/scripts/` stays guarded: CI runs it.
- `src/examples/` and `db/seed/` stay guarded: they are real code, and only `evals/*/seed/` is fixture input.
- `evals/` outside `seed/` stays guarded: it is the harness.

`enforcement.code_globs` only ratchets up. A project can add to the guarded set and cannot remove from it, so a built-in exemption that is wider than what Compass can show is not production code would take away a guarantee from every adopter.

**Shell, and the condition for adding it back.** Shell is not covered. A line that starts with `#` is data inside a heredoc, a multi-line string or a command substitution, and each of the 12 files that `enforcement.code_globs` declares in this repository uses a heredoc, `$(`, a backtick, `${` or a trailing backslash. A reader that handles those must track nested quotes and heredocs as the shell does, and a miss lets a data line change with no failing test. Shell comes back only with a parser that is shown to fail closed on the 13 shapes of the acceptance criteria for shell and on those 12 files. The contract line that said shell files are not classified as production code is corrected: a file that `enforcement.code_globs` declares is guarded.

**Messages.** The refusal `no-red-on-record` names `compass tdd-red` and `compass acceptance start`. A `.compass/current-task` that names an issue with no folder says so, and the verdict still comes from the issue that changed most recently. The code `bad-session-issue` serves a worktree and says to run `compass issue use <slug>` there. A second code, `bad-session-issue-restart`, serves the session's own project, where `COMPASS_ISSUE` outranks the pointer, and says to restart the session.

**Stated limits.** These are not fixed in this decision. Each lets an Edit through that a stricter check would refuse.

- The docstring rule is a word list. A docstring that a framework reads as grammar or help is not detected: a PLY grammar rule, the help text of click or typer, a FastAPI description.
- The directive rule is a deny list of words. A scanner or formatter directive that is not on the list passes as a comment. The list holds the common ones.
- A YAML comment that a template engine reads as text (`# {{ ... }}` in a Helm template) passes the YAML check. It matters only where `enforcement.code_globs` guards a template.
- A symbolic link under `evals/*/seed/` that points at production code is exempt, because a path is judged by its text. The same holds for `tests/` and `.compass/`.
- The check runs in `python3`. A check that is over budget or fails returns "no", and the hook then judges the Edit as before.
- The budget is measured on one machine. A file near the limit (780 KiB of Python of two-byte statements takes 1.9 seconds, charged 2.15) runs past the 3 second alarm on a machine that is 1.6 times slower, and the Edit keeps the old verdict. A GitHub-hosted Linux runner did this. The refusal is safe. The tests that check the model use files of about 40% of the limit, and a second test at the limit asserts only a safe result.
- The hook uses awk. It was written and tested on the awk of macOS only, and the continuous-integration runners use Linux awk.

**Unit D was dropped.** The issue first planned a second unit, which stopped the hook from reading the prose of a git message or a heredoc body as a write target, and the architect dropped it from this decision after its own adversarial review. The review wrote code with no failing test: a heredoc wrote a document (`cat > run.md <<'EOF'`, a line that copies a file into `src/`, `EOF`, a comment line), and a later `bash run.md` ran it, because the pass that looks for a runner stops at the comment. A word list cannot close that class, so the unit moves to GitHub issue #247 with the shell-grammar work.

## Why

A comment cannot change what code does, so a failing test has nothing to guard, and a refusal for a comment edit taught people to write a test that greps a file for a string. A text rule such as "the changed lines start with `#`" cannot tell a comment from a `#` inside a string or a block scalar, or a docstring from a string that a name holds, so the proof is a comparison of the file before and after. A pragma and a hidden character change what a tool reports or what a reader sees without changing the tree, so each is code. Shell has no parser here that fails closed, and a wrong answer lets code change with no failing test and no sign, so shell keeps its verdict. Each exempt path class is judged by whether the code ships or runs, and not by its name.

## Evidence

Issue ayeo-io/compass-delivery-record#239, "The pre-tool hook refuses comment edits and prose, and gives advice that does not work". Each case was reproduced against the hook on main. The compass architect set the rules in the requirements review of that issue (the answers on what comment-only means, pragmas, shell, file size and cost, path classes, hostile YAML and the second refusal code) and in its technical design, for jed72 to confirm. The tests that hold each rule are in `tests/test_pre_tool_hook_comment_only_edit.py`, `tests/test_pre_tool_hook_comment_only_edit_file_header.py`, `tests/test_pre_tool_hook_refusal_wording.py`, `tests/test_pre_tool_hook_example_and_fixture_paths.py`, `tests/test_safety_contract_hook_exemptions.py` and `tests/test_hook_decision_record.py`. The budget figures are in `docs/safety-contract.md`.
