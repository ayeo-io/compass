# Walkthrough: labels on GitHub

This page takes one issue from a project with no GitHub link to an issue whose labels follow its work. It needs the `gh` command, logged in with `gh auth login`, and a repository where you can edit labels. For the full rules, see [github-labels.md](github-labels.md).

## 1. Switch the labels on

Add the setting to `compass.yml` at the project root:

```yaml
schema: 1
github_labels:
  domain: true
  status: true
```

Both switches are off until you set them to `true`. With them off, Compass never calls GitHub.

## 2. Declare the labels your rules use

Compass writes only labels the project declared. The shipped default declares `auth`, `payments`, `personal-data`, `migrations`, `public-api`, `infra` and `ci`. To declare another, and to give a rule a label to match, edit `compass.yml`:

```yaml
dimensions:
  labels:
    set:
      common:
        add: [billing]
```

A rule can name a label too. The labels it names in `labels_any` count as declared. See [configuration.md](configuration.md) and [policy-lint.md](policy-lint.md).

## 3. Link an issue

Link the Compass issue to a GitHub issue by repository and number, or by URL:

```text
compass issue link set --github acme/widgets#42
compass issue link set --github https://github.com/acme/widgets/issues/42
```

The command stores `github: {repo: acme/widgets, number: 42}` in the manifest and then writes the labels. If you linked before switching the labels on, run `compass issue labels sync` once.

On GitHub, the issue now carries its domain labels, such as `infra`, and one status label, such as `status:ready`. Compass created any label the repository lacked.

## 4. Watch the labels change as work moves

Each command that changes the issue's records brings the labels up to date:

| You run | The GitHub issue then carries |
|---|---|
| `compass approach evaluate --write` | The assessment's declared labels and the status label for the state. |
| `compass issue subtask add subtask-1 --brief ...` | `status:in-progress` in place of `status:ready`. |
| `compass tdd-red --scenario <scenario id> -- <test command>`, or `compass evidence add EV-1 --type test-run --path evidence/green-<scenario id>.json` | `status:in-progress`, once a test is on record. |
| `compass gate pass verify.correctness --evidence EV-1` | `status:in-review`, once a gate has left `pending`. |
| `compass issue status set backlog` | `status:backlog`. |
| `compass issue status remove` | The state the records show again, here `status:in-review`. |
| `compass issue status set done --close-reason not-planned` | `status:done` and `close:not-planned`. |
| `compass issue status remove` on a closed issue | The `status:done` and `close:` labels are gone. |

Closing as `completed` is refused until every gate has passed, so the table closes as `not-planned`. Once every gate has passed, `compass issue status set done --close-reason completed` writes `status:done` and `close:completed`.

Labels that you or your team added, such as `bug` or `customer-x`, stay. Compass removes only the labels it owns.

## 5. See drift, and put it right

Remove `infra` from the GitHub issue by hand, then run:

```text
compass issue lint
```

The result is unchanged, and a line under it says the issue is out of sync and that `infra` is missing. Lint reads GitHub and writes nothing. To put the label back, run:

```text
compass issue labels sync
```

## 6. When gh is missing or logged out

The command you ran still succeeds. Compass prints one line on standard error, such as `gh is not logged in (run gh auth login)`, and `compass issue lint` reports the issue as out of sync until `compass issue labels sync` works.
