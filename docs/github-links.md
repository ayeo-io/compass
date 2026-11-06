# GitHub links

An issue can record the GitHub issue it is linked to and the pull request that carries it. This page is the reference: the command, the pull request and the landing commit, how `gh` is run, and the limits.

The code is `cli/compass_pkg/issue_link.py` (the link and the `gh` runner), `cli/compass_pkg/pull_request_link.py` (the pull request and `land_commit`) and `cli/compass_pkg/github_links.py` (origin's repository and default branch). The tests use a fake `gh` on `PATH`, `tests/fake_gh.py`.

## The link

`compass issue link set --github <target>` writes the manifest field `github: {repo, number}`. The target is `owner/repo#number` or the issue's URL on github.com:

```sh
compass issue link set --github acme/widgets#42
compass issue link set --github https://github.com/acme/widgets/issues/42
```

- The target is checked against a strict pattern before it is stored. A repository name cannot start with a dash, and `.` or `..` is not a repository name. A target that fails the check is refused, and nothing is written.
- Linking writes nothing to GitHub and calls no `gh` command.
- `--github` and `--pr` can be given together, and at least one is needed.

9.0.0 removed the label sync (ADR-093). Compass no longer writes labels to the linked GitHub issue, and `compass issue github sync` fails to parse with a line naming ADR-093. A project `compass.yml` that still sets `github_labels` gets an `L-SETTING-REMOVED` warning from `compass policy lint`, and the key is not read.

## The pull request and the landing commit

`compass issue link set --pr <n>` records the pull request that carries the issue, as `pull_request: {repo, number}` in the manifest. `<n>` is `owner/repo#number`, the pull request's URL on github.com, or a bare number in the repository of the project's `origin`. The command reads the pull request with `gh pr view <number> --repo <repo> --json number,state,mergeCommit`:

- When the pull request is merged and the issue has landed, it writes the merge commit to `land_commit` and prints the old and new ids.
- When the pull request is not merged, or the issue has not landed, it records the link only and leaves `land_commit` as it is. `compass ship-commit` writes `land_commit` when the issue lands.
- When `gh` cannot read the pull request, or the value names no pull request, it exits non-zero and writes nothing, the `--github` link included.

Run it when the pull request opens, and again after the merge. `compass ship-commit` writes `land_commit` from the commit it made on the branch. A squash merge puts a different commit on the default branch, so without the second run the record names a commit the default branch does not hold.

`compass check` reports a landed issue's `land_commit` that origin's default branch does not reach, as the advisory check `land-commit-on-default-branch`. The default branch is `refs/remotes/origin/HEAD`, as `git clone` records it. The check never fails the run, because a record written before the merge, or a clone that has not fetched, is not wrong work. It adds no row for an issue in flight, an issue with no `land_commit`, or a clone with no `origin/HEAD`.

## How gh is run

- Compass calls `gh` with an argument list and no shell.
- Compass passes `gh` only the environment variables it needs: where to find programs and its configuration, the locale, `GH_*` and `GITHUB_*`, the session bus, certificates and proxies. Any other variable is not passed. `GH_PROMPT_DISABLED` is set, so `gh` never waits for input.
- Each `gh` call is abandoned after 15 seconds.
- Compass stores no token and reads none. `gh` uses the person's own login.
- From a pull request Compass reads only its number, state and merge commit. It sends no issue text, path or evidence. See [security.md](security.md).

## Limits

- One GitHub issue and one pull request per Compass issue.
- Compass does not create GitHub issues or pull requests, close them or read an issue's state.
- A GitHub issue on another host (an enterprise server) is not supported. The link command accepts `github.com` URLs only.

## Files

| File | What it holds |
|---|---|
| `manifest.yml`, key `github` | The link: `repo` and `number`. |
| `manifest.yml`, key `pull_request` | The pull request that carries the issue: `repo` and `number`. |
| `.compass/work/<slug>/github-sync.yml` | Written by the label sync before 9.0.0. Nothing reads it now. Issue state; not committed. |
