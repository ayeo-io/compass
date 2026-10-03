# The delivery record

Compass keeps each issue's records out of the project's git history, so a public repository does not publish working notes. `compass record` keeps them in a second repository instead, so they survive the machine they were made on (ADR-031).

## Setting it up

Name the repository and the paths it holds in `.compass/config.yml`:

```yaml
record:
  remote: https://github.com/<owner>/<project>-delivery-record.git
  paths:
    - .compass/work
    - docs/compass
```

The repository must be private: Compass cannot check that. A project with no `record:` is unchanged.

## What happens

- `compass record sync` copies the paths into a clone of the record repository, redacts credentials in text, and commits and pushes, naming the project's commit. It adds and updates files; it never deletes from the record, so a checkout that holds only part of the record loses nothing from it. With nothing changed it makes no commit.
- `compass record sync --prune` also deletes from the record what this checkout no longer has. Run it only from a full checkout.
- From a linked worktree, which holds only part of the record, a full sync is refused. `ship-commit` there syncs just the landed issue's own folders.
- `ship-commit` runs the sync after every landing. If the sync fails for any reason, ship exits 2: the commit stands and the issue is landed, and `compass record sync` is the fix once the cause is fixed.
- `compass record restore` copies the record back into this project, such as a fresh clone. It refuses to overwrite a file that differs from the record unless `--force` is given.

A record path must be a folder or file inside the project; `.`, `.git` and anything inside `.git` are refused. Symbolic links are not followed. Text that is not UTF-8 is copied as it is, without redaction.

One record repository serves one project. The clone lives in the user's cache folder (`$XDG_CACHE_HOME/compass/record/`, or `~/.cache/compass/record/`), never inside the project, and a cached clone whose remote changed is replaced.

## Restoring onto a new machine

1. Clone the project.
2. Run `compass record restore` in it.

## Code

| File | Role |
|---|---|
| `cli/compass_pkg/record.py` | `sync`, `restore`, and the settings. |
| `cli/compass_pkg/manifest.py` | `ship-commit` runs the sync after a landing. |
