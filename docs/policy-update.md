# Policy update

This page is the owning doc for `compass policy update`. It states what the
command compares, what it asks, what it writes, its exit codes, the codes of
its refusals and the exact shape of the JSON it prints. From 6.0.0 the keys,
their order and their values are a public contract: a change to any of them
is a breaking change.

The code is `cli/compass_pkg/policy_update.py` (the plan, the prompt, the
text edit and the document) and `cli/compass_pkg/policy_cmd.py` (the verb).
The field-level re-check is `waivers.recheck_move`, which calls
`waivers.recheck`. The decisions behind it are ADR-039 (waivers) and ADR-043
(one project file).

## What it does

`compass policy update [--to MAJOR] [--yes]` moves a project from one shipped
default major to another. It rewrites the integer in `extends:
compass:default@<major>` in the project's `compass.yml` and nothing else,
except the `approved_by` and `approved_on` of each waiver a person
re-approves in the same step. A project that extends a git parent moves the
pin instead (see [A git parent](#a-git-parent)).

1. It reads `extends:` for the current major and picks the target: `--to`,
   or the newest major this CLI keeps. A move goes forward only.
2. It lays the project's file over each of the two defaults and compares
   them the way `compass policy diff` does: the classifier's verdict over the
   whole grid, and a replay of assessments (the grid, the label combinations
   and the project's archive). It shows the verdict and the replay counts.
3. It re-checks every project waiver, field by field (below).
4. It refuses until no waiver is left affected, asks for a confirmation, and
   writes `compass.yml` once.

## The two defaults

The CLI ships one default as `governance/presets/default`. When a new major
ships, the previous major must stay in the repository as
`governance/presets/default@<major>` (a copy of its preset files), because the
command needs the old values to tell which waived fields moved. A project
whose major has no kept folder gets exit 2. The tests use a fixture framework
folder that holds `default@6` and a changed `default` at major 7, since only
default@6 ships today.

A project two majors behind (on default@5 when the CLI keeps default@6 and
default@7) can move only if its own major is kept. When it is, `--to` can skip
a major, but only the two ends are compared: a waived field that changed in
default@6 and changed back in default@7 would not be flagged. Move one major
at a time (`--to 6`, then `--to 7`) to see every step. When its major is not
kept, the command exits 2 and the project must be moved by hand from the
release notes.

`tests/test_policy_update.py` fails when a kept folder is not the last preset
that major shipped (checked against `tests/fixtures/preset-digests.yml`), or
when an earlier pinned major is not kept. `docs/releasing.md` has the step.

## The waiver re-check

A waiver records that a person accepted the project's value for a field, given
the parent's value at the time. It stores no copy of that value, so the old
default stands for it. For each project waiver:

- If the parent value of any field the waiver covers differs between the two
  defaults, the waiver is affected. A list or a whole entry compares as a whole.
- If the new default no longer defines the entry, the waiver is affected, and
  the project's file does not resolve over the new default (it is refused
  with the merge errors).
- Otherwise the waiver stays valid. A change anywhere else in the default
  affects no waiver.

An affected waiver is shown with its entry, each field, the old and the new
parent value and the project's value. Only a person on a terminal can clear it.

## What is asked

| Situation | What happens |
|---|---|
| No waiver is affected, with `--yes` | The move is written. Nothing is asked |
| No waiver is affected, on a terminal | One question: move to the new major? |
| A waiver is affected, on a terminal, without `--yes` | For each waiver: approve it against the new default? Then the approver's name, which must be in the allowed list (`approvers.project-waiver` of the new default, or the project's `owner`). An empty answer takes the only allowed name. Three names outside the list count as a no. A last question confirms the move |
| A waiver is affected, with `--yes` | Refused (`yes-cannot-reapprove`). `--yes` never re-approves a waiver, because a script is not the owner |
| A waiver is affected, with no terminal or with `--json` | Refused (`no-terminal`), listing the waivers |
| Nothing affected, no terminal, no `--yes` | The plan is shown and the move is refused (`needs-confirmation`) |

A terminal is standard input and standard output both attached to one. With
`--json` the command never asks.

On a yes, the waiver's `approved_by` becomes the approver's name and its
`approved_on` becomes today's date. If the waiver has no `approved_on`, the
line is added below `approved_by`. A comment at the end of one of those two
lines is replaced with the new value.

## What is written

One atomic write of `compass.yml` holds the new integer and every approval, or
the file is not changed. The file is edited as lines, so comments, order and
every other byte stay. The edited text is parsed and must equal the old
document changed only in those places; if it does not, the command exits 2
before writing. A waiver written as a flow mapping (`waiver: {reason: ...}`)
cannot be edited line by line, so the command exits 2 and names it: write it
in block style and run the command again.

The file is read and written with its own line endings, so a CRLF file keeps
every CRLF. The command reads the file again just before the write. If it has
changed since the plan was made (for example, saved while a question waited)
nothing is written and the command exits 2, naming the first line that differs.

The command never removes a waiver. To drop one, remove it from `compass.yml`
by hand and run the command again. Editing `approved_on` by hand does not
clear an affected waiver: the command compares parent values, not dates.

## A git parent

When `extends:` names a git parent (`github:<owner>/<repo>@<ref>#<sha>`, see
[git-parents.md](git-parents.md)), the command moves the pin. It rewrites the
`#<sha>` and nothing else, except the `approved_by` and `approved_on` of each
waiver a person re-approves. The two pins take the place of the two defaults.

1. It asks the remote which commit `<ref>` names now, with `git ls-remote`. A
   tag is tried before a branch, and an annotated tag gives the commit it
   points at. A ref the remote does not have is exit 2.
2. If that commit is the pin, there is nothing to do.
3. It fetches the current pin (if it is not cached) and the new commit into the
   cache, each with the chain of git parents behind it (the parents its own
   `extends:` names, at most three deep). A cached copy of any parent in the
   current chain or the new chain that was edited, or that nothing records the
   fetch of, stops the move (exit 2) before anything is read from it: the cache
   is ignored by git, so an edit there would otherwise decide the re-check and
   the approvers. Delete the copy under `.compass/cache/parents/` and run the
   command again.
4. It runs every group of `compass policy lint` over the shipped default plus
   the new chain. Any error is refused as `new-parent-invalid`, naming the
   findings: a settings key, an `unlock:`, an `impl` outside the registry, a
   reference to an unknown entry, a loosening of the default with no waiver, a
   chain that is too deep, a cycle, or an ancestor that cannot be fetched.
5. It lays the project's file over the shipped default plus the whole chain at
   each pin, so a waived field that an ancestor changed counts as changed, and
   runs the same re-check, classification, replay, questions and single write as
   a default move. An allowed approver is named by the nearest parent's own
   `approvers.project-waiver` in the new chain, else the project's `owner`.
   Only the project's own `#<sha>` is rewritten: the new commit pins its
   ancestors itself.

`--to` names a shipped major, so it is exit 2 for a git parent. To follow
another ref, change the `@<ref>` in `compass.yml` by hand and run the command.

A fetched commit stays in the cache and in `seen.yml` whether or not the move is
written. After a refusal or a declined question, `compass check` reports the
parent as `stale`: a newer commit is known, and the pin has not moved.

### Offline

When the remote cannot be reached, or `COMPASS_OFFLINE` is set, nothing was
decided. The status is `offline`, the text starts with `offline:`, nothing is
written and the exit code is 1. A refusal has the status `refused` and the text
`not applied (<code>)`. A host that answered with an error (no such repository, a
failed login) is not offline: it is exit 2. A script reads the `status` in
`--json` to tell offline from a refusal.

In `--json` a git move has `"major": null` and a `"sha"` in `from` and `to`
(null in `to` when the ref was not resolved). A move of the shipped default has
no `sha` key.

## Exit codes

| Exit | Meaning |
|---|---|
| 0 | The move was written, or the project already extends the target major (or the commit its ref names) |
| 1 | The move was refused: an affected waiver, no terminal, a declined question, a file that does not resolve, a new git commit that fails its check, or no confirmation. Also `offline`: the remote could not be reached |
| 2 | The request or the file cannot be used: a major this CLI does not keep or one older than the project's, an `extends:` that is neither the shipped default nor a git parent, no `compass.yml`, a waiver that cannot be edited in place, a file changed since the plan, a write that failed, `--to` with a git parent, a ref the remote does not have, an edited cache of the current pin, or a git failure that is not about reaching the host |

Exit 1 on a run with no terminal differs from `policy migrate`'s dry run, which
exits 0: `update` exits 1 whenever it did not write a move it was asked for,
so a script can tell. With `--json`, exit 2 prints only a line on standard
error and no document.

## Open issues

The command does not list open issues whose issue waivers the move affects.
Run `compass policy diff --open` for that. The issue waivers are re-checked at
the next reassess.

## Refusal codes

| Code | Meaning |
|---|---|
| `yes-cannot-reapprove` | `--yes` was given and a waiver is affected |
| `no-terminal` | A waiver is affected and nobody can be asked |
| `nobody-may-approve` | A waiver is affected and no owner is declared, so no approver is allowed |
| `declined` | The approver said no, gave no allowed name, or the move was not confirmed |
| `needs-confirmation` | No waiver is affected, but there is no terminal and no `--yes` |
| `does-not-resolve` | The project's file does not merge over the new default, or over the new git commit |
| `new-parent-invalid` | The new git commit fails the parent checks, or does not merge over the shipped default |
| `offline` | Not a refusal: the status `offline` carries this code when the remote could not be reached |

## `compass policy update --json`

```json
{
  "schema": 1,
  "status": "refused",
  "written": false,
  "from": {
    "ref": "compass:default@6",
    "major": 6,
    "version": "6.0.0"
  },
  "to": {
    "ref": "compass:default@7",
    "major": 7,
    "version": "7.0.0"
  },
  "refusal": {
    "code": "no-terminal",
    "message": "there is no terminal to ask on, and these waivers need re-approval by an allowed approver: approaches.regular. Run the command on a terminal, or remove the waiver from compass.yml"
  },
  "classification": {
    "schema": 1,
    "result": "loosening",
    "reason": "at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency live-defect, role engineer, labels none: approaches.subtask_ceiling is 1 in the parent and 2 in the child",
    "scan": "full",
    "parent": "default@6 + project",
    "child": "default@7 + project",
    "exhaustive": false,
    "complete": true,
    "grid": {
      "labels": [
        "auth",
        "migrations",
        "payments",
        "personal-data"
      ],
      "label_count": 4,
      "label_cap": 8,
      "points": 4608,
      "raw_points": 51840,
      "evaluated": 4608
    },
    "counts": {
      "equal": 4592,
      "tighter": 0,
      "looser": 16,
      "mixed": 0
    },
    "first_looser": {
      "assessment": {
        "risk": "trivial",
        "familiarity": "greenfield",
        "size": "atomic",
        "goal": "delivery",
        "urgency": "live-defect",
        "role": "engineer",
        "labels": []
      },
      "represents": {
        "risk": [
          "trivial",
          "contained"
        ],
        "familiarity": [
          "greenfield",
          "brownfield-mapped"
        ],
        "size": [
          "atomic",
          "small"
        ],
        "goal": [
          "delivery",
          null
        ],
        "urgency": [
          "live-defect"
        ],
        "role": [
          "engineer",
          "qa",
          null
        ]
      },
      "outcome": "looser",
      "summary": "at risk trivial, familiarity greenfield, size atomic, goal delivery, urgency live-defect, role engineer, labels none: approaches.subtask_ceiling is 1 in the parent and 2 in the child",
      "changes": [
        {
          "fact": "ceilings",
          "field": "approaches.subtask_ceiling",
          "key": null,
          "outcome": "looser",
          "parent": 1,
          "child": 2
        }
      ]
    },
    "first_tighter": null,
    "first_mixed": null
  },
  "replay": {
    "sets": [
      {
        "name": "grid",
        "replayed": 288,
        "changed": 16,
        "skipped": null
      },
      {
        "name": "labels",
        "replayed": 4320,
        "changed": 0,
        "skipped": null
      },
      {
        "name": "archive",
        "replayed": 0,
        "changed": 0,
        "skipped": "the project holds no archived issue"
      }
    ],
    "changed": 16
  },
  "waivers": [
    {
      "id": "project:approaches.regular",
      "entry": "approaches.regular",
      "status": "invalidated",
      "reason": "Our work splits into more parallel subtasks than the default allows.",
      "approved_by": "jed72",
      "approved_on": "2026-10-05",
      "fields": [
        {
          "field": "subtask_ceiling",
          "old": 2,
          "new": 3,
          "project": 5,
          "message": "approaches.regular.subtask_ceiling: the parent value changed from 2 to 3; the project value is 5"
        }
      ]
    }
  ]
}
```

The pinned example is `tests/fixtures/policy-update-json-example.json`: a
refused move (no terminal) with one affected waiver. `tests/test_policy_update.py`
compares the command's output with it, byte for byte, and compares the block
above with it.

| Key | Type | Meaning |
|---|---|---|
| `schema` | integer | The version of this shape. It is 1 |
| `status` | string | `applied`, `nothing-to-do` or `refused` |
| `written` | boolean | True when `compass.yml` was written |
| `from`, `to` | object | `ref` (`compass:default@6`), `major` and `version` (the default's version, null when nothing was loaded because there is nothing to do) |
| `refusal` | object or null | `code` and `message` of a refusal |
| `classification` | object or null | The classifier's `to_json()` of the old default against the new one, each with the project's layer. Null when there is nothing to do or the file does not resolve |
| `replay` | object or null | `sets` (the `grid`, `labels` and `archive` sets, as `compass policy diff` reports them) and `changed`, the number of assessments whose result differs |
| `waivers` | list | Every project waiver, below |

Each waiver has these keys, in this order: `id` (such as
`project:approaches.regular`), `entry`, `status` (`kept`, `invalidated` or
`reapproved`), `reason` (the waiver's own), `approved_by`, `approved_on` (the
values in the file after the run) and `fields`. Each entry of `fields` has
`field` (null when the new default dropped the entry), `old` and `new` (the
parent value in each default), `project` (the project's value) and `message`.

The document holds no time and no path, so the same input gives the same bytes.

## Limits

- The approval is a name and a date. The command checks that the name is in the
  allowed list and never authenticates the person (the same limit as any waiver).
- Only the shipped default can be moved. A git parent has its own move, which
  reuses `waivers.recheck_move`.
- `compass policy diff` names only the major this CLI ships, so the full list
  of changed assessments for a move is in the `replay` counts here and not in a
  `policy diff` call.
