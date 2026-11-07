# Upgrading to 9.0.0

This page says how to move a project from Compass 8.x to 9.0.0 and keep its evidence. It lists what changes, what breaks, and what to do about it. The plan behind it is #359 [Add compass migrate and the 9.0.0 upgrade guide].

## 2. Run `compass migrate`

`compass migrate` moves each open issue that 8.x assessed onto the 9.0.0 four-stage path: assess, specify, build and ship (ADR-092). Run it from the project root:

```
compass migrate             # a dry run: lists what it would change, writes nothing
compass migrate --apply     # writes the changes the dry run listed
compass migrate --issue <slug> --apply
```

The dry run exits 0 when there is nothing to do, 1 when there is, and 2 when it refuses. `cli/compass_pkg/migrate_9.py` holds the command.

### What it changes

For each open issue that holds a `delivery_approach` and no `evidence_required`:

- It runs the same write as `compass approach evaluate --write --reason "compass migrate to 9.0.0"`. The issue gets the evidence it owes (`evidence_required`), the gates derived from it, the checkpoints and a new stored generation from the check set. Each gate keeps the state it held; a new gate starts at pending.
- It adds a `reassessments:` entry of kind `policy-correction` with the reason `compass migrate to 9.0.0`. It asks for no justification of an assessed value, because it writes the assessment the issue already holds.
- It moves the 8.x record that no 9.0.0 reader of a path issue uses under the manifest's `legacy:` key. No check reads `legacy:`.

  | Key in 8.x | Under `legacy:` |
  |---|---|
  | `stages`, `subtask_ceiling`, `orchestration`, `max_worktrees` | the same names |
  | `subtasks`, `models`, `page_ticks`, `readiness` | the same names |
  | each `artifacts:` entry that is not the acceptance criteria | `documents` |
  | the fields of the acceptance-criteria entry other than `id`, `kind`, `path`, `reason` and `status` | `artifact_status`, by the entry's id |
  | a legacy stage in `depends_on[].until` or `raised_by.found_at` | `stage_values`, by where it was; the key gets the path stage |

  The acceptance-criteria entry stays in `artifacts:`, so Compass still finds the spec.
- It writes `request.link` from a linked GitHub issue when the link is missing.
- It writes `trail.md` again when the issue has one, so its sum lines match the new manifest.

The scenarios, the evidence registry, the gates, `checkpoint_outcomes`, `delegations_used`, `waivers`, `changed_files`, the landing fields, `github`, `follow_ups`, `friction`, `reassessments`, `depends_on` and `raised_by` stay where they are.

### Where each issue lands

The stage follows the records, as on every path issue. The report prints the 8.x stage, the path stage and, when the records place the issue earlier, the reason.

| 8.x stage | Path stage |
|---|---|
| `define`, `refine`, `plan` | specify |
| `breakdown`, `implement` | build |
| `verify`, `ship` | ship, when each scenario has a red before its green; otherwise build, and the report names the scenario |

An issue can land earlier than this table when its records say so. For example, a scenario with no declared test, or a listed `specify` checkpoint with no outcome, keeps the issue at specify. `compass migrate` writes no red, green or outcome to move an issue.

### What it never does

- It writes no approval, no checkpoint outcome and no delegation copy.
- It writes no file under `evidence/`, no `.red` or `.acceptance` marker, nothing under `approval-requests/` and no `scenario_freeze`. `sha256sum -c` over `evidence/SHA256SUMS` passes after it as before.
- It does not change a closed issue, an issue already on the path, or an issue that was never assessed. The report lists each with the reason.

### The request link

9.0.0 asks each issue who requested it and where (`request`, ADR-096). `compass migrate` does not prompt. It lists each converted issue with no requester, with the command that records it:

```
compass issue link set --issue <slug> --request <url> --requester <name>
```

To record it in the same run, give `--request` and `--requester` with `--issue`:

```
compass migrate --issue <slug> --apply --request owner/repo#12 --requester "Dana Smith"
```

The check `request-recorded` fails until both parts are on record.

### What it refuses

It refuses with exit 2, before it writes anything:

- a project with copies of the two governance files in `governance/` and no `compass.yml` (`governance-copy-removed`). On Compass 8.x, run `compass policy migrate` to write `compass.yml`, then run `compass migrate` again.
- a `compass.yml` whose `extends:` names a git parent (`git-parent-removed`). Move the checks the parent adds into the settings of `compass.yml`, delete `extends:`, then run `compass migrate` again.

It refuses one issue, and lists it under "refused", when the issue has a 1.x manifest (run `compass issue migrate --apply` first) or a stored generation that is not whole.

### What to do

1. Copy `.compass/work` and `docs/compass` outside the project.
2. Run `compass migrate` and read the list.
3. Run `compass migrate --apply`.
4. Run each `compass issue link set` command the report lists.
