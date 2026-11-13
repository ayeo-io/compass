# Release notes from the release line

`compass release notes --since <ref>` lists the issues completed since a git reference, each with its release line. This document owns the verb, the placement rule and the shared module behind it.

The verb is a read. It writes no file and runs no git command that writes.

## The command

| Part | Meaning |
|---|---|
| `--since REF` | Required. A tag, branch or commit. |
| Exit 0 | The run printed a list, or one line saying no shipping issue completed since `REF`. |
| Exit 2 | `REF` is not a git reference that names a commit, or a configured names key is missing. Nothing prints. |

Each listed issue prints `### <slug> (completed <date>)`, a blank line and its release line on one line. Line breaks in the stored line become single spaces. An issue with no line prints `No release line recorded.`

Issues are ordered by landing time, then by slug.

Two closing lines follow when they apply:

- `<n> of <total> issues have no release line.`
- `<n> completed issue(s) could not be placed against <ref> (...)`, for the issues the rule below could not place.

## Which issues are listed

The verb reads every completed issue under `.compass/work/` whose approach ships. A spike ships nothing, and an issue closed as not planned or as a duplicate is not completed.

An issue squash-merged to main has a `land_commit` that main never reaches. The verb therefore places an issue by two parts, not by reachability alone:

1. The issue is left out when the living spec at the reference names it, or when the reference reaches its `land_commit`.
2. Otherwise the issue is listed when HEAD reaches its `land_commit`, or when the living spec committed at HEAD names it.
3. An issue placed by neither part is counted in the closing line and not listed.

The living spec is the pair of files `cli/compass_pkg/shipped_issues.py` names in `LIVING_SPEC_FILES`: the spec and its archive under `docs/`. A `land_commit` that git cannot resolve counts as unreachable.

### A revision with no living spec

9.0.0 derives no living spec (ADR-091), so a release made with 9.0.0 or later holds neither file. Before then each landing re-derived the spec, so a tag or commit made before 9.0.0 still holds it, and the verb reads it there with `git show`.

At a revision with no living spec, that part names no issue, and only reachability places the issue:

- At the reference, an issue is left out only when the reference reaches its `land_commit`.
- At HEAD, an issue is listed only when HEAD reaches its `land_commit`.

So an issue squash-merged after 9.0.0, whose `land_commit` HEAD never reaches, is not listed. It is counted in the closing line as one that could not be placed. An issue squash-merged before 9.0.0 is still placed by the spec that the older revision holds.

## Public text

The output is meant for public release text. With a names key set in `record.names_key`, the whole output goes through the same redaction as the delivery record, so a rival name prints as its code. A configured key that is missing stops the verb.

## Modules

| Module | Holds |
|---|---|
| `cli/compass_pkg/shipped_issues.py` | The rule for a completed issue that ships, the pattern that reads issue headings out of an older living spec, and `completed_issues`. |
| `cli/compass_pkg/release_notes.py` | `register`, `cmd_release_notes` and `placement`. |

`release_notes.py` and `shipped_issues.py` must not import `flow.py` or the parse cache. `tests/test_intent_and_release_line_readers.py` checks this in a fresh interpreter.
