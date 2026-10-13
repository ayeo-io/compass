# GitHub labels

Compass can write an issue's domain labels and workflow state to the GitHub issue it is linked to. It can also post the issue page, the issue's README, as one comment on that GitHub issue. This page is the reference: the setting, the labels, the issue page, when Compass writes, and what it does not do. For a first run, see [github-labels-walkthrough.md](github-labels-walkthrough.md).

The label sync is `cli/compass_pkg/github_labels.py`. The issue page is described below by what it does. The settings key is `github_labels` in `compass.yml` (see [configuration.md](configuration.md)).

## What it does

- A manifest field `github: {repo, number}` links a Compass issue to a GitHub issue.
- When a project switches it on, Compass writes labels, and with `page` the issue page, to that GitHub issue through the `gh` command.
- The Compass manifest is the source of truth. Compass writes to GitHub and never reads a label back into the manifest.
- Nothing is written unless the project asks. With all three switches off, no Compass command calls GitHub.

## The setting

```yaml
# compass.yml
github_labels:
  domain: true   # write the issue's declared domain labels
  status: true   # write status:<state>, and on close status:done and close:<reason>
  page: true     # post the issue page as one comment, and the ask into an empty issue body
```

| Switch | Default | Writes |
|---|---|---|
| `domain` | `false` | The assessment's labels that the project declared. |
| `status` | `false` | One `status:` label, and `close:<reason>` on a closed issue. |
| `page` | `false` | The issue page: one comment, and once the ask in an empty issue body. See [The issue page](#the-issue-page). |

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

## The issue page

The page widens the audience of the issue's documents to the readers of the GitHub issue, who can be many more people than can read the repository. That is why `page` is off by default: the issue's prose, decisions and file names leave the project when it is on, and nothing about the label switches turns it on.

### What it posts

With `github_labels.page` on, `domain` and `status` keep their meaning and `page` adds two writes to the linked GitHub issue:

- **One comment.** It holds the issue's README as the last command rendered it. Its first line is the marker `<!-- compass:issue-page -->`. Compass finds its comment by the recorded comment id, and when that is missing or GitHub answers 404, by the oldest comment whose first line is the marker. It edits that comment and never posts a second one.
- **The ask, once.** `<!-- compass:issue-ask -->` is the first line of the text written into the issue body: the Problem and Desired outcome sections of `intent.md`, or the issue line of `delivery-approach.md` when there is no `intent.md`, and a link to the comment. The body counts as empty when it is empty, holds only whitespace, or holds only that marker. Compass writes the body at most once, and only when it counts as empty. A body a person wrote is kept, and Compass does not read it back.

The page step runs after the README render and reads the README file on disk. It does not render. With `COMPASS_RENDER_AFTER=0` the file does not change, so no call is made.

### Refresh and the other issues

The page step syncs only the issue the command named. A linked issue whose README that command also rewrote is refreshed by that issue's own next sync, and `compass issue lint` reports its page as out of date meanwhile. Lint adds a `github:` note when the page has an error, when no digest is recorded, or when the page now composed differs from the one posted. It makes no `gh` call.

### Links

A relative Markdown link in the README is rewritten before posting:

- When the origin remote is a github.com repository and origin's default branch holds the file, it becomes a `blob/<branch>/<path>` link on GitHub, keeping any `#fragment`.
- When origin's default branch does not hold the file, it becomes the path in code format followed by `(not on <branch>)`. A project that never commits its issue folders gets a plain path for each link to an issue's own documents.
- With no github.com origin, or no default branch recorded for origin, every link is the plain path with no suffix.
- A path that resolves outside the repository is posted as the link text alone.

Compass decides each link from local git only and makes no network call to do it.

### The size bound

GitHub limits a comment to 65536 characters, and the limit counts the marker line. When the comment is longer, Compass shortens it in this order and stops as soon as it fits:

1. The traceability chart is replaced by one line that says it was left out and points to the README.
2. Each row of the artifacts table is reduced to its first cell, as a list of links, under one line that says so.
3. If it is still too long, the post is refused, with one line on standard error that names the size and the limit.

The README file is never changed.

### What may not leave the project

Two checks read the comment and the body as it is posted, after the links are rewritten and the size bound applied. A block the size bound leaves out is not posted and is not checked. The checks look for private paths and credentials. The first hit refuses the post, and a refused post is refused whole: no part of it is posted, nothing is redacted and posted in its place, and no `gh` call is made. A refusal writes one line on standard error that names the place, never the hit, and records the refusal in `github-sync.yml`.

| Check | What it refuses |
|---|---|
| Private path | A path under `.compass/private/`, and a path that git ignores. A path under `.compass/work/` or `docs/compass/`, a directory, and a URL are not checked. A relative link that is not rewritten to a URL becomes a plain path and is checked. A failed `git check-ignore` call refuses too. |
| Credential | Text that holds a credential shape the redaction step would replace. This check reads no environment variable. |

A refused or failed page stays as it was on GitHub until the next successful sync. `compass issue lint` reports it meanwhile.

### Calls and cost

- Every page call is `gh api`, with the JSON text on standard input. The text is never an argument, and no shell runs.
- The digest of the comment as posted is recorded in `github-sync.yml`. A page whose digest is unchanged, with no error and the body decided, makes no call.
- A first post makes up to four calls: list the comments, create the comment, read the body, write the body. Each call is abandoned after 15 seconds, so a command that triggers both the label write and the page can wait for the 15-second timeout of each call it makes.

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
- `compass issue link set`
- `compass ship-commit`
- `compass quick-fix finish`
- the commands that change the records that decide the state: `compass scenario add` and `descope`, `compass tdd-red`, `compass tdd-green`, `compass evidence add`, `compass acceptance record`, `compass gate pass`, `compass issue artifact set`, `compass issue subtask add` and `replan`

The commands are listed in `LABEL_TRIGGERS` of `cli/compass_pkg/record_triggers.py`. The step that renders an issue's documents after a command (`docs/rendered-blocks.md`) reads the same list and adds commands of its own, so a command that syncs the labels always renders too.

A label name is compared without regard to case, as GitHub does. Compass sends its own spelling: the declared name, or the fixed owned name.

Every command that can change the README also triggers the page, but the page makes a call only when the posted text changed.

`compass issue github sync` does the same on demand, for any issue: the label write and the page write, each whatever the other's result. Use it after the first link, after turning a switch on, to put back a label someone removed, or to refresh a page that lint reports as out of date. It exits non-zero when either write failed or was refused, says so when all three switches are off, and refuses an issue with no GitHub link, naming `compass issue link set`. `compass issue labels sync` was removed at 7.0.0; the new verb replaces it, and the old spelling exits 2 and names the new one.

Each write compares the labels Compass owns with the labels now on the GitHub issue and sends only the difference. A write that has nothing to change calls `gh issue view` once and edits nothing.

## When GitHub does not match

A label removed or added on GitHub is reported, not pulled back. `compass issue lint` prints a `github:` line under its result when the issue is linked and a switch is on:

- `github: out of sync - missing on GitHub: ...` or `not wanted on GitHub: ...` when the labels differ;
- `github: out of sync - the last sync failed: ...` when the last write failed;
- `github: out of sync - cannot read the labels on GitHub: ...` when the lint itself cannot reach GitHub.

The lint keeps its exit code, so an unreachable GitHub does not fail `compass ci`. The lint reads GitHub and never writes to it. The next write, or `compass issue github sync`, puts the labels right.

## When gh fails

A sync never fails the command that triggered it. Each `gh` call is abandoned after 15 seconds, so a hung `gh` holds a command, or one linked issue in `compass ci`, for 15 seconds at most.

- If `gh` is not installed, is not logged in, or cannot reach GitHub, the command still succeeds.
- Compass prints one line on standard error that names the problem, and writes the failure to `github-sync.yml` in the issue's folder. `compass issue lint` then reports the issue as out of sync.
- `compass issue github sync` is the one command whose purpose is the sync. It exits non-zero and names the problem when `gh` fails.

## Security

- Compass calls `gh` with an argument list and no shell.
- The repository and issue number are checked against a strict pattern when linking and before every call. A repository name cannot start with a dash.
- Compass stores no token and reads none. `gh` uses the person's own login.
- With `page` off, Compass sends label names and the issue number. It sends no issue text, path or evidence.
- With `page` on, Compass also sends the issue page and the ask, after the two checks above. See [security.md](security.md).

## Limits

- One GitHub issue per Compass issue.
- Compass does not create GitHub issues, close them or read their state. It reads back only comment ids and whether the issue body is empty, and stores no text from GitHub.
- A person's edit to the Compass comment on GitHub is overwritten by the next change to the page. Compass does not read it.
- A second comment that also opens with the marker is left as it is. Compass edits the oldest.
- Compass writes the state when a command that changes the records runs. A state that changes by hand-editing a file, such as the `current_phase` key, is written at the next command or at `compass issue github sync`.
- A GitHub issue in another host (an enterprise server) is not supported by the link command, which accepts `github.com` URLs only.

## Files

| File | What it holds |
|---|---|
| `manifest.yml`, key `github` | The link: `repo` and `number`. |
| `compass.yml`, key `github_labels` | The three switches. |
| `.compass/work/<slug>/github-sync.yml` | Two sections, `labels` and `page`. Each holds the time of its last write and its last error. `labels` holds the labels wanted. `page` holds the digest of the comment as posted, the comment id, and whether the body was set by Compass, kept as a person's, or not yet decided. It holds no text from GitHub. Issue state; not committed. |
