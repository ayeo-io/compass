# GitHub labels

Compass can write an issue's domain labels and workflow state to the GitHub issue it is linked to. This page is the reference: the setting, the labels, when Compass writes, and what it does not do. For a first run, see [github-labels-walkthrough.md](github-labels-walkthrough.md).

The code is `cli/compass_pkg/github_labels.py`. The settings key is `github_labels` in `compass.yml` (see [configuration.md](configuration.md)).

## What it does

- A manifest field `github: {repo, number}` links a Compass issue to a GitHub issue.
- When a project switches it on, Compass writes labels to that GitHub issue through the `gh` command.
- The Compass manifest is the source of truth. Compass writes to GitHub and never reads a label back into the manifest.
- Nothing is written unless the project asks. With both switches off, no Compass command calls GitHub.

## The setting

```yaml
# compass.yml
github_labels:
  domain: true   # write the issue's declared domain labels
  status: true   # write status:<state>, and on close status:done and close:<reason>
```

| Switch | Default | Writes |
|---|---|---|
| `domain` | `false` | The assessment's labels that the project declared. |
| `status` | `false` | One `status:` label, and `close:<reason>` on a closed issue. |

Only the value `true` turns a switch on. Any other value reads as off. The setting is read from the project's own `compass.yml` only, so a parent cannot switch it on.

## The labels

| Label | When it is written |
|---|---|
| `status:backlog` | The issue is in the backlog: held by a person, or not yet defined and refined. |
| `status:ready` | The issue is defined and refined and work has not started. |
| `status:in-progress` | Plan, breakdown or implementation has started. |
| `status:in-review` | A gate has left `pending`, or a verification report is registered. |
| `status:done` | The issue is closed. |
| `close:completed`, `close:not-planned`, `close:duplicate` | The issue is closed, with that close reason. |
| a domain label such as `infra` | The label is in the issue's assessment and the project declared it. |

The status label is the issue's lifecycle state, read from its records. A change of state replaces the previous status label. Reopening a closed issue removes `status:done` and the `close:` label.

### Declared domain labels

A domain label is declared when it is in the labels dimension's `common` list in the configuration the issue runs against, or when a rule names it in `labels_any`. The shipped default declares `auth`, `payments`, `personal-data`, `migrations`, `public-api`, `infra` and `ci`. A project adds its own with `compass.yml`:

```yaml
dimensions:
  labels:
    set:
      common:
        add: [billing]
```

An assessed label that is not declared is not written. A declared label whose name holds a comma, a quote, a shell character or a leading dash is skipped, and Compass prints one line naming it.

## What Compass owns

Compass adds and removes only these labels:

- the five `status:` labels in the table above;
- the three `close:` labels in the table above;
- the declared domain labels, when `domain` is on.

Every other label on the GitHub issue stays, including a label of your own under the `status:` prefix such as `status:legal-hold`. Compass creates a missing label in the repository, with one fixed colour for `status:` labels, one for `close:` labels and one for domain labels. It creates only labels it owns.

## When Compass writes

After one of these commands succeeds on a linked issue, with a switch on:

- `compass approach evaluate --write` (assess and reassess)
- `compass issue status set` and `compass issue status remove` (including a close)
- `compass issue link`
- `compass ship-commit`
- `compass quick-fix finish`
- the commands that change the records that decide the state: `compass scenario add` and `descope`, `compass tdd-red`, `compass tdd-green`, `compass evidence add`, `compass acceptance record`, `compass gate pass`, `compass issue artifact set`, `compass issue subtask add` and `replan`

A label name is compared without regard to case, as GitHub does. Compass sends its own spelling: the declared name, or the fixed owned name.

`compass issue labels sync` does the same on demand, for any issue. Use it after the first link, after turning a switch on, or to put back a label someone removed.

Each write compares the labels Compass owns with the labels now on the GitHub issue and sends only the difference. A write that has nothing to change calls `gh issue view` once and edits nothing.

## When GitHub does not match

A label removed or added on GitHub is reported, not pulled back. `compass issue lint` prints a `github:` line under its result when the issue is linked and a switch is on:

- `github: out of sync - missing on GitHub: ...` or `not wanted on GitHub: ...` when the labels differ;
- `github: out of sync - the last sync failed: ...` when the last write failed;
- `github: out of sync - cannot read the labels on GitHub: ...` when the lint itself cannot reach GitHub.

The lint keeps its exit code, so an unreachable GitHub does not fail `compass ci`. The lint reads GitHub and never writes to it. The next write, or `compass issue labels sync`, puts the labels right.

## When gh fails

A sync never fails the command that triggered it. Each `gh` call is abandoned after 15 seconds, so a hung `gh` holds a command, or one linked issue in `compass ci`, for 15 seconds at most.

- If `gh` is not installed, is not logged in, or cannot reach GitHub, the command still succeeds.
- Compass prints one line on standard error that names the problem, and writes the failure to `github-sync.yml` in the issue's folder. `compass issue lint` then reports the issue as out of sync.
- `compass issue labels sync` is the one command whose purpose is the sync. It exits non-zero and names the problem when `gh` fails.

## Security

- Compass calls `gh` with an argument list and no shell.
- The repository and issue number are checked against a strict pattern when linking and before every call. A repository name cannot start with a dash.
- Compass stores no token and reads none. `gh` uses the person's own login.
- Compass sends label names and the issue number. It sends no issue text, path or evidence.

## Limits

- One GitHub issue per Compass issue.
- Compass does not create GitHub issues, close them or read their state.
- Compass writes the state when a command that changes the records runs. A state that changes by hand-editing a file, such as the `current_phase` key, is written at the next command or at `compass issue labels sync`.
- A GitHub issue in another host (an enterprise server) is not supported by the link command, which accepts `github.com` URLs only.

## Files

| File | What it holds |
|---|---|
| `manifest.yml`, key `github` | The link: `repo` and `number`. |
| `compass.yml`, key `github_labels` | The two switches. |
| `.compass/work/<slug>/github-sync.yml` | The time of the last sync, the labels wanted, and the last error. Issue state; not committed. |
