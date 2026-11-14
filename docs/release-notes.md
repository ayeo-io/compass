# Release notes from the release line

`compass release notes --since <ref>` lists the issues completed since a git reference, each with its release line (`docs/release-line.md`). It writes no file and runs no git command that writes.

## The command

| Part | Meaning |
|---|---|
| `--since REF` | Required. A tag, branch or commit. |
| Exit 0 | The run printed a list, or one line saying no shipping issue completed since `REF`. |
| Exit 2 | `REF` is not a git reference that names a commit, or a configured names key is missing. Nothing prints. |

Each issue prints `### <slug> (completed <date>)`, a blank line and its release line on one line. An issue with no line prints `No release line recorded.` Issues are ordered by landing time, then by slug.

Two closing lines follow when they apply:

- `<n> of <total> issues have no release line.`
- `<n> completed issue(s) could not be placed against <ref> (...)`

## Which issues are listed

The verb reads every completed issue under `.compass/work/` whose approach ships. A spike ships nothing. An issue closed as not planned or as a duplicate is not completed.

It places each issue in this order:

1. It leaves the issue out when the living spec at the reference names it, or when the reference reaches its `land_commit`.
2. Otherwise it lists the issue when HEAD reaches its `land_commit`, or when the living spec committed at HEAD names it.
3. Otherwise it counts the issue in the closing line and does not list it.

The living spec is the pair of files that `LIVING_SPEC_FILES` in `cli/compass_pkg/shipped_issues.py` names. The verb reads them with `git show`. A `land_commit` that git cannot resolve counts as unreachable.

### A revision with no living spec

9.0.0 derives no living spec (ADR-091). A revision made with 9.0.0 or later holds no living spec, so only the `land_commit` places an issue there.

**Limit:** an issue squash-merged after 9.0.0 has a `land_commit` that HEAD never reaches. The verb does not list it and counts it in the closing line. An issue squash-merged before 9.0.0 is still placed by the living spec of the older revision.

## Public text

The output is meant for public release text. When `record.names_key` is set, the output goes through the same redaction as the delivery record, so a rival name prints as its code. A configured key that is missing stops the verb.

## Modules

| Module | Holds |
|---|---|
| `cli/compass_pkg/shipped_issues.py` | The rule for a completed issue that ships, the pattern that reads issue headings out of an older living spec, and `completed_issues`. |
| `cli/compass_pkg/release_notes.py` | `register`, `cmd_release_notes` and `placement`. |

`release_notes.py` and `shipped_issues.py` must not import `flow.py` or the parse cache. `tests/test_intent_and_release_line_readers.py` checks this in a fresh interpreter.
