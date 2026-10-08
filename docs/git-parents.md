# Git parents

This page is the owning doc for a git parent: a project's `extends:` that names a
`compass.yml` published in a git repository and pinned to one commit. It states the
spelling, how a parent is fetched and cached, what Compass refuses and why, and what an
issue records. From 6.0.0 the spelling, the finding codes, the cache layout and the
`seen.yml` and `versions.yml` entries are a public contract.

The code is `cli/compass_pkg/parents.py`. `cli/compass_pkg/policy_lint.py` calls it when it
loads the project, and `cli/compass_pkg/effective.py` stores the result in a generation.

## The spelling

```yaml
extends: github:acme/compass-banking@1.2.0#3f9c1a2e5b7d4c6a8e0f1b2c3d4e5f6a7b8c9d0e
```

| Part | Rule |
|---|---|
| `github:<owner>/<repo>` | A repository on the remote. The owner and the repository start with a letter, a digit or (repository only) an underscore, so neither can be read by git as an option |
| `@<ref>` | A label for people, such as a release tag. It is required, and Compass never resolves it here |
| `#<sha>` | The pin: 40 lowercase hexadecimal characters |

The map form works too. `from:` holds the same text:

```yaml
extends:
  from: github:acme/compass-banking@1.2.0#3f9c1a2e5b7d4c6a8e0f1b2c3d4e5f6a7b8c9d0e
```

Compass refuses every other spelling with `L-PARENT-FORM` before it runs git. That covers
spaces, shell characters, `..`, a leading `-` in any part, an `https://` URL, an uppercase
sha and a sha that is not hexadecimal. A remote ref with no sha is `L-PARENT-NO-SHA`.
`compass:default@<major>` is the shipped default and needs no sha, because the CLI version
is the pin.

A sha of 7 to 39 characters is accepted only when exactly one commit cached for the same
repository starts with it, because git fetches a full sha only. Two matches are
`L-PARENT-SHA-AMBIGUOUS`. No match is `L-PARENT-FORM`, which asks for all 40 characters. A
sha that names a tree or a file instead of a commit is also `L-PARENT-FORM`.

There is no lock file. The sha in `compass.yml` is the pin, and a git commit sha already
identifies its content. `compass policy update` will resolve a ref to a sha in a later
release. Until then a person writes the sha.

The ref label is not checked against the content. Nothing here tests that the commit is
reachable from the ref, or that the ref still points at it. A later release checks
reachability, when `compass policy update` resolves refs.

## Where it is fetched from

| Setting | Meaning |
|---|---|
| (default) | `https://github.com/<owner>/<repo>.git` |
| `COMPASS_PARENT_REMOTE_BASE` | Replaces `https://github.com` for a mirror, and for tests. It must be an `https://` URL or an absolute folder that holds `<owner>/<repo>.git`. Anything else is `L-PARENT-FETCH` |

The pin is a commit, so a mirror cannot change what a project reads: a commit with another
sha is refused.

## When Compass fetches

| Command | Fetches an uncached pin? |
|---|---|
| `compass check`, and any reader of an issue's stored generation | Never. It reads the cache, and an uncached pin is `L-PARENT-NOT-CACHED` |
| `compass policy lint`, `compass policy effective` | Yes |
| `compass approach evaluate --write` (assess and reassess) | Yes |
| any of the above with `--offline`, or with `COMPASS_OFFLINE=1` in the environment | Never |

A fetch asks for the exact commit, so it cannot return different content later.

## How a parent is fetched

Compass runs git with an argument list and never through a shell:

1. It creates a scratch folder under `.compass/cache/parents/` and a new bare repository in it, with an empty template and hooks switched off, and names the remote `origin`.
2. It fetches the one commit as a partial fetch (`--filter=blob:limit=1048576`), at depth 1, with no tags and no submodules, and with `transfer.fsckObjects` on. Files of 1 MiB or more are left out, so an unrelated large file is not downloaded, and git never fetches a missing file afterwards (`GIT_NO_LAZY_FETCH`). Only `https` is allowed (and `file` when the base is a local folder). Git cannot prompt.
3. It checks that the fetched object is the pinned sha (`L-PARENT-SHA-MISMATCH`) and that it is a commit (`L-PARENT-FORM`).
4. It lists the root entry for `compass.yml` and nothing else in the tree. A symbolic link there is refused (`L-PARENT-SYMLINK`). A missing entry, a folder, a submodule, or a file of 1 MiB or more is `L-PARENT-CONTENT`. A symbolic link or any other file elsewhere in the tree is never read and does not matter.
5. It reads that one file. A git failure while reading is `L-PARENT-FETCH`, and nothing is cached. No other file is read, written or run.
6. It moves the result to `.compass/cache/parents/<owner>/<repo>/<sha>/compass.yml` and removes the scratch folder. If another run cached the same commit first, that is fine when the file is identical, and `L-PARENT-CACHE` when it differs. A refusal at any step leaves nothing in the cache.

Git sees an allow-list of the caller's environment. These pass on purpose: the PATH, `HOME`, `XDG_CONFIG_HOME`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`, `GIT_ASKPASS`, locale, certificate and proxy settings. They bring in your own git configuration, so your credential helper runs and your `url.<base>.insteadOf` rules apply. A private repository needs that. A variable that moves the repository (`GIT_DIR`), names a helper program (`GIT_SSH_COMMAND`, `GIT_EXEC_PATH`) or injects configuration (`GIT_CONFIG_COUNT`) is not passed on.

CI needs credentials of its own for a private parent: Compass never prompts, so a runner with no credential helper or token configured fails with `L-PARENT-FETCH`. A public parent needs none. Run `compass policy lint` once with network access to fill the cache, or cache `.compass/cache/parents/` between CI runs and use `--offline`.

## The cache

```
.compass/cache/parents/
  seen.yml
  <owner>/<repo>/<sha>/compass.yml
```

The cache is keyed by repository and commit, so `github:someone/else@1#<sha>` never loads a commit cached for another repository, and a short sha matches only commits cached for the same repository.

The cache is not configuration. It is listed in `.compass/.gitignore`, and a person can delete it. Compass writes only below `.compass/cache/parents/`. If `.compass/cache` or `.compass/cache/parents` is a symbolic link, or a cached parent or the owner or repository folder above it is a link or resolves outside `.compass/`, Compass refuses with `L-PARENT-CACHE` and neither reads nor writes there.

Compass does not check a cached file against `seen.yml`. If someone edits a cached `compass.yml` under `.compass/cache/parents/`, Compass reads the edited file without warning until the parent-state check ("edited in the cache") lands.

`seen.yml` records what this machine has fetched:

```yaml
refs:
  github:acme/compass-banking@1.2.0:
    content_digest: sha256:...   # over the bytes of the cached compass.yml
    fetched: '2026-10-08T09:12:00Z'
    sha: 3f9c1a2e...
    version: 1.2.0               # the ref when it reads as a version, else empty
schema: 1
```

## What a parent may hold

A parent is data. Compass reads its `compass.yml` as strict YAML and runs nothing from it. The parent is a `parent` layer, so the layer checks apply before anything merges: a settings key (`L-SETTINGS-KEY`, which covers `allow_project_commands`), an `unlock:` (`L-UNLOCK-PLACEMENT`) and an `impl` outside the check registry (`L-IMPL-UNKNOWN`) fail the lint, and each finding names the parent's layer. A parent that is not a mapping is `L-SCHEMA`, and a non-text key is `L-KEY-NOT-TEXT`.

A parent's own `extends:` may name `compass:default@<major>` or another git parent, in the same spelling. The settings keys are `autonomy`, `adoption`, `allow_project_commands`, `enforcement`, `record`, `project`, `prices`, `multiagent`, `governance_drift` and `preset_index`. A parent may hold `schema`, `extends`, `owner`, `approvers`, `capabilities`, `preset` and the catalogues, and nothing else. This holds for every parent in a chain.

## Chains

A parent can name a git parent, which can name another. A chain holds at most three git parents, to a depth of three: the project's direct parent, its parent and that parent's parent. The shipped default at the root is not counted, because it is the CLI's own version and not a fetched parent.

Each parent in a chain is pinned by sha, fetched, cached and read as data in the same way as a single parent. The chain is `default`, then the git parents from the furthest to the nearest, `project`, then the issue. A later layer overrides an earlier one, so the nearest parent wins over the furthest, and `policy effective` names the parent that wrote each field. The classifier judges each git parent against the shipped default like any other layer, so a parent that loosens the default needs a waiver the same way a project does. A waiver in a git parent, at any depth, is checked against that parent's own `owner`, or the names in the `approvers.project-waiver` of the layer above it. The project's owner does not count. A parent with no `owner` cannot carry a waiver (`W-NO-OWNER`).

| Fault | Code | Reported on |
|---|---|---|
| A third parent names a fourth git parent | `L-PARENT-CHAIN` | The third parent. The fourth is not fetched |
| A parent names a commit that is already in the chain, at any depth | `L-PARENT-CYCLE` | The parent that names it. A full sha already in the chain is refused before any fetch |
| An ancestor cannot be fetched, is not cached for a reader that does not fetch, or has a bad spelling | The code of the fault | The parent that names the ancestor (a bad file reports on the ancestor itself) |

The refusal from `compass policy lint`, `compass policy effective` and `compass check` names that parent in the same way. A stored generation does not read the cache at all: it uses the record of its parents, so a deleted cache does not stop `compass check` for an issue that has one.

Compass checks a parent after it has loaded the parent's ancestors. A parent that is refused for a settings key, an `unlock:` or an unknown `impl` may still be fetched along with its ancestors, which were pinned and read as data only. Nothing in them runs.

## What an issue records

`compass policy effective` shows the parent as the source of every field it wrote, and lists it in `layers` with its version and digest. When an issue's configuration is committed, `versions.yml` lists the shipped default and then each git parent, furthest first, so the order is the order of the merge:

```yaml
parents:
  - { ref: "compass:default@6", version: 6.0.0, digest: sha256:..., source: shipped }
  - { ref: "github:acme/compass-banking@1.2.0", sha: 3f9c1a2e..., version: 1.2.0, digest: sha256:..., source: git }
```

`digest` is the digest of the parent's layer keys. An issue with a stored generation keeps the parent it ran against: moving the pin in `compass.yml` changes nothing for it until a new generation is committed.

## Finding codes

Every refusal is a lint finding with a code. [policy-lint.md](policy-lint.md) lists them with the rest.

| Code | Cause |
|---|---|
| `L-PARENT-FORM` | The spelling is not supported, or a short sha names no cached commit |
| `L-PARENT-NO-SHA` | A remote ref with no sha |
| `L-PARENT-NOT-CACHED` | The pin is not cached and this run may not fetch |
| `L-PARENT-FETCH` | Git failed, is missing or timed out, or the remote base is not valid |
| `L-PARENT-CONTENT` | No regular `compass.yml` file at the root of the commit, or it is 1 MiB or larger |
| `L-PARENT-SHA-MISMATCH` | The fetch returned another object |
| `L-PARENT-SYMLINK` | The root `compass.yml` is a symbolic link |
| `L-PARENT-CACHE` | The cache is a link, leaves `.compass/`, or holds a different file for the commit |
| `L-PARENT-CHAIN` | A chain holds more than three git parents |
| `L-PARENT-CYCLE` | A parent names a commit that is already in the chain |
| `L-PARENT-SHA-AMBIGUOUS` | A short sha names more than one cached commit |

## What this page does not cover

- `compass policy update`, which resolves a ref to a sha and moves the pin.
- The four parent states (up to date, stale, edited in the cache, both).
- The waiver re-check when a pin moves.
- A host other than GitHub, and private repositories that need a login: git uses the credential settings of the person running Compass, and Compass never prompts.
