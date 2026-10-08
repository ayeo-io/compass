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

A sha of 7 to 39 characters is accepted only when exactly one commit in the cache starts
with it, because git fetches a full sha only. Two matches are `L-PARENT-SHA-AMBIGUOUS`. No
match is `L-PARENT-FORM`, which asks for all 40 characters.

There is no lock file. The sha in `compass.yml` is the pin, and a git commit sha already
identifies its content. `compass policy update` will resolve a ref to a sha in a later
release. Until then a person writes the sha.

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

1. It creates a scratch folder under `.compass/cache/parents/` and a new bare repository in it, with an empty template and hooks switched off.
2. It fetches the one commit, at depth 1, with no tags and no submodules, and with `transfer.fsckObjects` on. Only `https` is allowed (and `file` when the base is a local folder). Git cannot prompt.
3. It checks that the fetched commit is the pinned sha (`L-PARENT-SHA-MISMATCH`).
4. It lists the whole tree. A symbolic link anywhere is refused (`L-PARENT-SYMLINK`).
5. It reads `compass.yml` at the repository root only (`L-PARENT-CONTENT` when it is missing, is not a file or is larger than 1 MiB). No other file is read, written or run.
6. It moves the result to `.compass/cache/parents/<sha>/compass.yml` and removes the scratch folder. A refusal at any step leaves nothing in the cache.

Git sees a short list of the caller's environment: the PATH and home, locale, certificate and proxy settings, and the git credential settings. A variable that moves the repository, names a helper program or injects configuration (`GIT_DIR`, `GIT_SSH_COMMAND`, `GIT_CONFIG_COUNT` and the like) is not passed on.

## The cache

```
.compass/cache/parents/
  seen.yml
  <sha>/compass.yml
```

The cache is not configuration. It is listed in `.compass/.gitignore`, and a person can delete it. Compass writes only below `.compass/cache/parents/`. If `.compass/cache` or `.compass/cache/parents` is a symbolic link, or a cached parent is a link or resolves outside `.compass/`, Compass refuses with `L-PARENT-CACHE` and neither reads nor writes there.

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

Each parent in a chain is pinned by sha, fetched, cached and read as data in the same way as a single parent. The chain is `default`, then the git parents from the furthest to the nearest, `project`, then the issue. A later layer overrides an earlier one, so the nearest parent wins over the furthest, and `policy effective` names the parent that wrote each field. The classifier judges each git parent against the shipped default like any other layer, so a parent that loosens the default needs a waiver the same way a project does.

| Fault | Code | Reported on |
|---|---|---|
| A third parent names a fourth git parent | `L-PARENT-CHAIN` | The third parent. The fourth is not fetched |
| A parent names a commit that is already in the chain | `L-PARENT-CYCLE` | The parent that names it |
| An ancestor cannot be fetched, is not cached for a reader that does not fetch, or has a bad spelling | The code of the fault | The parent that names the ancestor (a bad file reports on the ancestor itself) |

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
| `L-PARENT-CONTENT` | No usable `compass.yml` at the root of the commit |
| `L-PARENT-SHA-MISMATCH` | The fetch returned another commit |
| `L-PARENT-SYMLINK` | The tree holds a symbolic link |
| `L-PARENT-CACHE` | The cache is a link or leaves `.compass/` |
| `L-PARENT-CHAIN` | A chain holds more than three git parents |
| `L-PARENT-CYCLE` | A parent names a commit that is already in the chain |
| `L-PARENT-SHA-AMBIGUOUS` | A short sha names more than one cached commit |

## What this page does not cover

- `compass policy update`, which resolves a ref to a sha and moves the pin.
- The four parent states (up to date, stale, edited in the cache, both).
- The waiver re-check when a pin moves.
- A host other than GitHub, and private repositories that need a login: git uses the credential settings of the person running Compass, and Compass never prompts.
