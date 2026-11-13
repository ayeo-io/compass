# GitHub links

An issue can record the GitHub issue it is linked to, the request it answers and who asked, and the pull request that carries it. This page is the reference: the command, the request link, the pull request and the landing commit, the ship approval read from the merged pull request, how `gh` is run, and the limits.

The code is `cli/compass_pkg/issue_link.py` (the link and the `gh` runner), `cli/compass_pkg/request_link.py` (the request link and the requester), `cli/compass_pkg/pull_request_link.py` (the pull request, its reviews and `land_commit`), `cli/compass_pkg/landing.py` (the land commit every reader uses), `cli/compass_pkg/ship_approval.py` (which reviews count) and `cli/compass_pkg/github_links.py` (origin's repository and default branch). The tests use a fake `gh` on `PATH`, `tests/fake_gh.py`.

## The link

`compass issue link set --github <target>` writes the manifest field `github: {repo, number}`. The target is `owner/repo#number` or the issue's URL on github.com:

```sh
compass issue link set --github acme/widgets#42
compass issue link set --github https://github.com/acme/widgets/issues/42
```

- The target is checked against a strict pattern before it is stored. A repository name cannot start with a dash, and `.` or `..` is not a repository name. A target that fails the check is refused, and nothing is written.
- Linking writes nothing to GitHub and calls no `gh` command.
- `--github`, `--pr`, `--request` and `--requester` can be given together, and at least one is needed.

## The request link and the requester

Every delivery issue owes the token `request`: who asked for the change and a link to the request (#356). `--request` and `--requester` write the manifest's `request` record, with the time the session recorded it (`recorded_at`) and the command that wrote it (`recorded_by`: `compass issue link set`, `compass quick-fix start` or `compass migrate`):

```sh
compass issue link set --request https://github.com/acme/widgets/issues/42 --requester "Dana Smith"
compass issue link set --request acme/widgets#42 --requester "Dana Smith"
```

- `--request` takes an `https://` URL with no white space, at most 2,000 characters, or `owner/repo#number`. `owner/repo#number` and a GitHub issue URL also write `github`, as `--github` does. `--github` and `--request` that name two different GitHub issues are refused.
- `--github` alone also counts as the link: when no `request.link` is held, the GitHub issue's URL is written there.
- `--requester` is free text on one line, at most 100 characters, with no control character. It is a claim the session records, not an approval. Compass does not check it, and no approval rule reads it.
- Each flag can be given alone. A part already recorded stays when the other is given.
- A value that fails a check is refused, and nothing is written. Neither flag calls `gh`.
- `compass quick-fix start` takes the same two flags, so assess records both in its one call. It does not refuse without them.

The check `request-recorded` fails until both parts are recorded, and `compass next` asks for them first (`governance/guardrails.md`). It is not a stop: no command refuses on it. A change with no request to link is excused by a waiver that a person approves (`docs/waivers.md`).

9.0.0 removed the label sync (ADR-093). Compass no longer writes labels to the linked GitHub issue, and `compass issue github sync` fails to parse with a line naming ADR-093. A project `compass.yml` that still sets `github_labels` gets an `L-SETTING-REMOVED` warning from `compass policy lint`, and the key is not read.

## The pull request and the landing commit

`compass issue link set --pr <n>` records the pull request that carries the issue, as `pull_request: {repo, number}` in the manifest. `<n>` is `owner/repo#number`, the pull request's URL on github.com, or a bare number in the repository of the project's `origin`. The command reads the pull request with `gh pr view <number> --repo <repo> --json number,state,mergeCommit,mergedAt,author,headRefOid,url`:

- When the pull request is merged, `pull_request` also gets `merged_at`, `merge_commit` and `author`, and the command reads the ship approval (next section).
- When the pull request is merged and the issue has landed, it writes the merge commit to `land_commit` and prints the old and new ids. An issue whose record landed with the code (`landed_with_record: true`, no stored `land_commit`) is the exception: nothing is written, because `landing.land_commit` gives the land commit from git and a stored value would win over it.
- With `--pr` it writes `trail.md` again after the save (`docs/delivery-record.md`). In committed mode, when the pull request is merged and the issue has landed, it ends with `next: compass record commit --issue <slug>`, the command that commits the merge fields (`--json` gives it as `next`).
- When the pull request is not merged, or the issue has not landed, it records the link only and leaves `land_commit` as it is. `compass ship-commit` writes `land_commit` when the issue lands.
- When `gh` cannot read the pull request or its reviews, or the value names no pull request, it exits non-zero and writes nothing, the `--github` link included.

Run it when the pull request opens, and again after the merge. `compass ship-commit` writes `land_commit` from the commit it made on the branch. A squash merge puts a different commit on the default branch, so without the second run the record names a commit the default branch does not hold.

### The land commit

Every command that reads the land commit gets it from `landing.land_commit`:

- A stored `land_commit` wins. Every issue landed before 9.0.0 has one, and so has an issue whose record stays out of the code commit.
- Else, when the issue is completed and its manifest holds `landed_with_record: true`, the land commit is the newest commit, from HEAD, that added the manifest's current `land_timestamp` line (`git log -G`), and whose copy of the manifest still holds it (`git show`). The record was committed with the code, so this is the commit that landed the issue. After a squash merge it is the squash commit on the default branch; after a rebase, the rebased commit; after a merge commit, the branch commit.
- Else there is none. A shallow clone that does not hold the commit that added the line has none either, and the checks that compare the landed files decline, as they do for a stored commit the clone does not hold.

A manifest without `landed_with_record` is never read from git, so an issue landed with no `land_commit` keeps the verdict "landed with no land_commit recorded".

`compass check` reports a landed issue's land commit that origin's default branch does not reach, as the advisory check `land-commit-on-default-branch`. The default branch is `refs/remotes/origin/HEAD`, as `git clone` records it. The check never fails the run, because a record written before the merge, or a clone that has not fetched, is not wrong work. It adds no row for an issue in flight, an issue with no land commit, or a clone with no `origin/HEAD`. For a committed record the land commit read from git follows the merge, so the row fails only until the clone fetches the merged default branch.

## The ship approval from the merged pull request

Every delivery issue owes the ship approval: one person's approval of the change at ship (the token `ship-approval`, checked by `ship-approval-present`; see `governance/guardrails.md`). On a project that merges through pull requests, a review approval on GitHub gives it, and `compass issue link set --pr <n>` copies it into the manifest after the merge.

When GitHub reports the pull request merged, the command makes two more calls before it writes anything:

```sh
gh api --paginate repos/<repo>/pulls/<n>/reviews \
  --jq '.[] | {id, state, submitted_at, commit_id, html_url, user: {login: .user.login, type: .user.type}}'
gh api user --jq .login
```

A reviewer counts when all of these hold:

- Their latest review submitted at or before the merge that changes their state is `APPROVED`. `APPROVED`, `CHANGES_REQUESTED` and `DISMISSED` change the state; a `COMMENTED` review does not, as on GitHub.
- Their account type is `User`. A GitHub App reviews as a `Bot` and does not count.
- They are not the pull request's author (compared without letter case). GitHub refuses a self-approval too; the rule guards a hand-made answer.

Each counting reviewer gets one `pr-approval` evidence record:

| Key | Value |
|---|---|
| `id` | `EV-PR-APPROVAL-<n>`, the first number not taken |
| `pull_request` | `{repo, number}` |
| `review_id`, `url` | The review's id and its URL on GitHub, so a reader can check it with `gh api repos/<repo>/pulls/<n>/reviews/<review_id>` |
| `approver`, `pr_author` | The reviewer's login and the pull request author's login |
| `decision`, `timestamp` | `approved`, and the time the review was submitted |
| `reviewed_commit`, `head_commit`, `merge_commit`, `merged_at` | The commit the review approved, the pull request's head, the merge commit and the merge time. An approval of an earlier commit than the head still counts; `compass check` says so on the row |
| `read_at`, `read_as` | When Compass read it, and the login `gh` read as, so a reader sees when the reviewer and the reader are the same account |
| `via`, `issue`, `generation` | `github`, the issue slug and its generation |

A second run replaces the record of the same review in place, and writes nothing new when only `read_at` or `read_as` would change. The command prints a line for each counting reviewer, and a line for each other reviewer who approved, with the reason the approval was set aside: the author, not a `User` account, given after the merge, or a later review that changed the state.

`compass evidence add --type pr-approval` is refused: only this read writes the record.

`compass check` never calls `gh`. It reads the records the manifest holds:

| Case | `compass issue link set --pr` | `compass check` on an issue that owes `ship-approval` |
|---|---|---|
| `gh` is not installed | Refuses; nothing written | Nothing to check; the detail names `compass evidence request --ship` |
| The repository is not on GitHub | A bare number refuses (origin names no repository on github.com); not run | As above |
| `gh` is not logged in, GitHub is down, the call times out, or HTTP 404 | Refuses; nothing written, the `--github` link included | Unchanged |
| The pull request is not merged | Writes the link only; says the approval is read after the merge | Nothing to check |
| Merged, with a counting approval | Writes the link, the merge keys, the records and `land_commit` (not for a record that landed with the code) | Pass, naming the reviewer and the record |
| Merged, with no approving review | Writes the link, the merge keys and `land_commit` (as above); says no person other than the author approved | Fail, until a typed approval (`compass evidence request --ship`, then `/compass:approve`) is on record |
| The only approval is by the author, by a bot, or after the merge | Sets it aside with the reason | As with no approving review |
| The reviews call or `gh api user` fails after `gh pr view` succeeded | Refuses; nothing written | Unchanged |

Compass writes nothing to GitHub in any case. A project not on GitHub, or a person who is the only reviewer, gives the ship approval as a typed approval instead.

## How gh is run

- Compass calls `gh` with an argument list and no shell.
- Compass passes `gh` only the environment variables it needs: where to find programs and its configuration, the locale, `GH_*` and `GITHUB_*`, the session bus, certificates and proxies. Any other variable is not passed. `GH_PROMPT_DISABLED` is set, so `gh` never waits for input.
- Each `gh` call is abandoned after 15 seconds.
- Compass stores no token and reads none. `gh` uses the person's own login.
- From a pull request Compass reads only its number, state, author, head commit, merge commit, merge time and URL; from a review, only the fields of the `--jq` filter above, never its text. It sends no issue text, path or evidence. See [security.md](security.md).

## Limits

- One GitHub issue and one pull request per Compass issue.
- Compass does not create GitHub issues or pull requests, close them, review them or read an issue's state.
- A `pr-approval` record is a copy, read once. `compass check` does not read GitHub again, so a review dismissed after the read still counts, and a second run does not remove its record. A process running as the same operating system user can edit `manifest.yml`, or put another program named `gh` on `PATH`. A reader checks a record by its review id ([safety-contract.md](safety-contract.md)).
- A GitHub issue on another host (an enterprise server) is not supported. The link command accepts `github.com` URLs only.

## Files

| File | What it holds |
|---|---|
| `manifest.yml`, key `github` | The link: `repo` and `number`. |
| `manifest.yml`, key `pull_request` | The pull request that carries the issue: `repo` and `number`, and after the merge `merged_at`, `merge_commit` and `author`. |
| `manifest.yml`, `evidence` of type `pr-approval` | Each approving review that counts as the ship approval. |
| `.compass/work/<slug>/github-sync.yml` | Written by the label sync before 9.0.0. Nothing reads it now. Issue state; not committed. |
