# GitHub links

`compass issue link set` records an issue's GitHub issue, the request it
answers and who asked, and its pull request. After the merge it copies the
ship approval from the pull request's reviews.

| Flag | Value | Writes |
|---|---|---|
| `--github` | `owner/repo#number`, or the issue's URL on github.com | `github: {repo, number}` |
| `--request` | An `https://` URL with no white space, at most 2,000 characters, or `owner/repo#number` | `request.link` |
| `--requester` | One line of free text, at most 100 characters, no control character | `request.requester` |
| `--pr` | `owner/repo#number`, the pull request's URL on github.com, or a bare number in the repository of `origin` | `pull_request: {repo, number}` |

- Give at least one flag. You can give them together.
- A value that fails its check is refused, and nothing is written. A
  repository name cannot start with a dash or be `.` or `..`.
- Only `--pr` calls `gh`. Compass writes nothing to GitHub.

## The request link and the requester

Every delivery issue owes the token `request`: who asked for the change and
a link to the request.

```sh
compass issue link set --request acme/widgets#42 --requester "Dana Smith"
```

- A `--request` that names a GitHub issue also writes `github`. `--github`
  alone also writes `request.link`, when none is held.
- A `--github` and a `--request` that name two different GitHub issues are
  refused.
- Each flag can be given alone. A part already recorded stays.
- The record holds `recorded_at` and `recorded_by`: `compass issue link
  set`, `compass quick-fix start` or `compass migrate`.
- The requester is a claim, not an approval. Compass does not check it, and
  no approval rule reads it.
- `compass quick-fix start` takes the same two flags and does not refuse
  without them.

The check `request-recorded` fails until both parts are recorded, and
`compass next` asks for them first (`governance/guardrails.md`). No command
refuses on it. An approved waiver excuses a change with no request
([waivers](waivers.md)).

9.0.0 removed the label sync (ADR-093): `compass issue github sync` fails to
parse, and `compass policy lint` warns `L-SETTING-REMOVED` on
`github_labels`.

## The pull request and the landing commit

Run `compass issue link set --pr <n>` when the pull request opens, and again
after the merge. A squash merge puts a new commit on the default branch.
Without the second run, a stored `land_commit` names a commit the default
branch does not hold.

The command reads `gh pr view <number> --repo <repo> --json
number,state,mergeCommit,mergedAt,author,headRefOid,url`, then:

- **Not merged, or the issue has not landed:** it records the link only.
  `compass ship-commit` writes `land_commit` when the issue lands.
- **Merged:** it also writes `merged_at`, `merge_commit` and `author`, and
  reads the ship approval.
- **Merged, and the issue has landed:** it also writes the merge commit to
  `land_commit` and prints the old and new ids.
- **Merged, and the record landed with the code** (`landed_with_record:
  true`): it writes no `land_commit`, and ends with `next: compass record
  commit --issue <slug>`.
- It writes `trail.md` again ([delivery record](https://github.com/ayeo-io/compass/blob/main/docs/delivery-record.md)).

### The land commit

`landing.land_commit` gives the land commit to every command. The first
rule that matches decides:

1. A stored `land_commit`. Each issue landed before 9.0.0 has one, and so
   has an issue whose record is kept out of the code commit.
2. For a completed issue with `landed_with_record: true`: the newest commit
   from HEAD that added the manifest's `land_timestamp` line and still
   holds it. That is the squash commit after a squash merge, the rebased
   commit after a rebase, and the branch commit after a merge commit.
3. None. A shallow clone without that commit has none, and the checks that
   compare the landed files decline.

An issue landed with neither key keeps the verdict "landed with no
land_commit recorded".

The advisory check `land-commit-on-default-branch` reports a land commit
that `refs/remotes/origin/HEAD` does not reach. It never fails the run. It
adds no row for an issue in flight, an issue with no land commit, or a
clone with no `origin/HEAD`.

## The ship approval from the merged pull request

Every delivery issue owes one person's approval of the change at ship: the
token `ship-approval`, the check `ship-approval-present`
(`governance/guardrails.md`). For a merged pull request, `--pr` makes two
more calls:

```sh
gh api --paginate repos/<repo>/pulls/<n>/reviews \
  --jq '.[] | {id, state, submitted_at, commit_id, html_url, user: {login: .user.login, type: .user.type}}'
gh api user --jq .login
```

A reviewer counts when all of these hold:

- Their latest `APPROVED`, `CHANGES_REQUESTED` or `DISMISSED` review, at or
  before the merge, is `APPROVED`. A `COMMENTED` review changes nothing.
- Their account type is `User`. A GitHub App is a `Bot` and does not count.
- They are not the pull request's author, compared without letter case.

Each counting reviewer gets one `pr-approval` evidence record:

| Key | Value |
|---|---|
| `id` | `EV-PR-APPROVAL-<n>`, the first number not taken |
| `pull_request` | `{repo, number}` |
| `review_id`, `url` | The review. Check it with `gh api repos/<repo>/pulls/<n>/reviews/<review_id>` |
| `approver`, `pr_author` | The two logins |
| `decision`, `timestamp` | `approved`, and when the review was submitted |
| `reviewed_commit`, `head_commit`, `merge_commit`, `merged_at` | An approval of a commit before the head still counts; `compass check` says so |
| `read_at`, `read_as` | When Compass read it, and the login `gh` read as |
| `via`, `issue`, `generation` | `github`, the issue slug and its generation |

- A second run replaces the record of the same review. It writes nothing
  when only `read_at` or `read_as` would change.
- The command prints why it set an approval aside: the author, not a `User`
  account, given after the merge, or a later review changed the state.
- `compass evidence add --type pr-approval` is refused.

`compass check` never calls `gh`. It reads the records in the manifest:

| Case | `compass issue link set --pr` | `compass check` on an issue that owes `ship-approval` |
|---|---|---|
| `gh` is not installed | Refuses; nothing written | Nothing to check; names `compass evidence request --ship` |
| The repository is not on GitHub | A bare number refuses | As above |
| `gh` is not logged in, GitHub is down, a call times out or fails, or HTTP 404 | Refuses; nothing written, the `--github` link included | Unchanged |
| Not merged | Writes the link only | Nothing to check |
| Merged, with a counting approval | Writes the link, the merge keys, the records and `land_commit` | Pass, naming the reviewer and the record |
| Merged, with no counting approval (none, or only by the author, by a bot, or after the merge) | Writes the link, the merge keys and `land_commit`; says why | Fail, until a typed approval (`compass evidence request --ship`, then `/compass:approve`) is on record |

A project not on GitHub, or a person who is the only reviewer, gives the
ship approval as a typed approval.

## How gh is run

- With an argument list and no shell.
- With only these environment variables: where to find programs and its
  configuration, the locale, `GH_*` and `GITHUB_*`, the session bus,
  certificates and proxies. `GH_PROMPT_DISABLED` is set, so `gh` never
  waits for input.
- Each call is abandoned after 15 seconds.
- Compass stores no token and reads none. `gh` uses the person's own login.
- Compass reads only the fields named above, never a review's text. It
  sends no issue text, path or evidence ([security](security.md)).

## Limits

- One GitHub issue and one pull request for each Compass issue.
- Compass does not create, close or review a GitHub issue or pull request,
  and does not read an issue's state.
- A `pr-approval` record is a copy, read once. A review dismissed after the
  read still counts, and a second run does not remove its record.
- A process that runs as the same operating system user can edit
  `manifest.yml`, or put another program named `gh` on `PATH`. A reader
  checks a record by its review id ([safety contract](safety-contract.md)).
- Only `github.com` URLs are accepted, not an enterprise server.

## Code

`cli/compass_pkg/issue_link.py` (the link and the `gh` runner),
`request_link.py`, `pull_request_link.py`, `landing.py`, `ship_approval.py`
(which reviews count) and `github_links.py` (origin's repository and default
branch). The tests put a fake `gh` on `PATH`: `tests/fake_gh.py`.
