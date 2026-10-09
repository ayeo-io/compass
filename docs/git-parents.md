# Git parents

This page is the owning doc for a git parent: a project's `extends:` that names a
`compass.yml` published in a git repository and pinned to one commit. It states the
spelling, how a parent is fetched and cached, what Compass refuses and why, and what an
issue records. From 6.0.0 the spelling, the finding codes, the cache layout and the
`seen.yml` and `versions.yml` entries are a public contract.

The code is `cli/compass_pkg/parents.py`, `cli/compass_pkg/parent_states.py` for the parent
states and `cli/compass_pkg/chain_class.py` for the stored classification.
`cli/compass_pkg/policy_lint.py` calls `parents.py` when it
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
  approved_by: acme-team
  approved_on: "2026-10-08"
```

The map holds `from` (required text), `approved_by` (text) and `approved_on` (text or a date). `approved_by` and `approved_on` are read from the project's own `compass.yml`, in the `extends:` map, and nowhere else. The layer check refuses an `approved_on` that is not a date written `YYYY-MM-DD` (`2026-13-45` and `yesterday` are not) or that is in the future, with `L-SCHEMA`. Nothing else uses the two keys yet: they are not stored in `versions.yml`, and nothing checks `approved_by` against an approver list. Any other key in the map is `L-SCHEMA`. A `from` that is not text is `L-PARENT-FORM`, the same code as a bad spelling in the string form. The layer digest includes the whole `extends:` value, so the two forms of one parent give the project layer a different digest and the parent layer the same one.

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
identifies its content. `compass policy update` moves the pin: it resolves the ref to the
commit it names now (`git ls-remote`), fetches it, re-checks the project's waivers across
the old and new commit and rewrites the `#<sha>`. See [policy-update.md](policy-update.md).
A person writes the first sha.

The ref label is not checked against the content. Nothing tests that the pinned commit is
reachable from the ref. `compass policy update` reads only where the ref points now.

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
| `compass policy lint`, `compass policy show` | Yes |
| `compass policy update` | Yes, always for the ref (`git ls-remote`), and for the current pin and the new commit when they are not cached. With `COMPASS_OFFLINE=1` it asks nothing and reports `offline` |
| `compass policy diff`, when a reference is a git parent | Yes, and it prints one line on stderr (`compass policy diff: fetching <ref> into .compass/cache/parents/`) before each fetch. It also adds `cache/` to `.compass/.gitignore` if the file does not list it. These are the only files `policy diff` writes |
| `compass preset test` | Yes, for a git parent the preset names that is not cached. With `--offline` it fetches nothing |
| `compass approach evaluate --write` (assess and reassess, including a reassess that commits a `compass issue configure` proposal) | Yes |
| `compass issue configure` (the preview and the proposal it records) | Never. It reads the cache and commits no generation, so an uncached pin is `L-PARENT-NOT-CACHED`. Run `compass policy lint` first |
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

Compass checks a cached `compass.yml` against the digest in `seen.yml` each time it reads the parent (see [the four parent states](#the-four-parent-states)). The check catches an accidental edit. It does not stop a deliberate one, because `seen.yml` sits beside the cached file: someone who can write the cache can rewrite the digest as well, and the edited file then reads as up to date. If you doubt the cache, delete `.compass/cache/parents/`. The next `compass policy lint` fetches the pinned commit again.

`seen.yml` records what this machine has fetched:

```yaml
refs:
  github:acme/compass-banking@1.2.0:
    content_digest: sha256:...   # over the bytes of the cached compass.yml, for the commit fetched last
    digests:                     # the same digest for every commit of the ref fetched on this machine
      3f9c1a2e...: sha256:...
    fetched: '2026-10-08T09:12:00Z'
    sha: 3f9c1a2e...
    version: 1.2.0               # the ref when it reads as a version, else empty
schema: 1
```

## The four parent states

Each git parent is in one of four states. Compass reads the state from the pin, the cache and `seen.yml`, and never fetches to find it.

| State | Meaning | Lint code and level |
|---|---|---|
| `up to date` | The cache holds the pin, and `seen.yml` knows no other commit for the ref | `S-PARENT-UP-TO-DATE`, info |
| `stale` | `seen.yml` holds another commit for the ref, which this machine fetched last | `S-PARENT-STALE`, warning |
| `locally modified` | The cached `compass.yml` no longer matches the digest recorded when it was fetched | `S-PARENT-MODIFIED`, error |
| `both` | Stale, and the cached file was edited | `S-PARENT-BOTH`, error |

A fetch of an exact pin overwrites the sha in `seen.yml`, so the other commit can be older or newer than the pin. A fresh clone has fetched nothing else, so it is never stale. A stale parent never fails the lint, and the pin stays where it is until a person moves it.

An edited cache fails the lint, because the chain would otherwise run a file that is not the pinned commit's. A cached commit that `seen.yml` holds no digest for counts as edited too, since it cannot be shown to match a fetch. To clear either, delete the cached copy of that commit under `.compass/cache/parents/` and run `compass policy lint`, which fetches it again. A `seen.yml` that cannot be read counts as holding no digest. A cached file that no longer parses is reported as `L-LOAD`, before its state is read.

`compass approach show` adds one line for the project's git parent and nothing for a project with none:

```
Parent: github:acme/compass-banking@1.2.0 at 3f9c1a2 - locally modified
```

It reads the cache only. A parent it cannot read, such as one that is not cached, prints `Parent: not read` followed by the finding code and cause.

## What a parent may hold

A parent is data. Compass reads its `compass.yml` as strict YAML and runs nothing from it. The parent is a `parent` layer, so the layer checks apply before anything merges: a settings key (`L-SETTINGS-KEY`, which covers `allow_project_commands`), an `unlock:` (`L-UNLOCK-PLACEMENT`) and an `impl` outside the check registry (`L-IMPL-UNKNOWN`) fail the lint, and each finding names the parent's layer. A parent that is not a mapping is `L-SCHEMA`, and a non-text key is `L-KEY-NOT-TEXT`.

A parent's own `extends:` may name `compass:default@<major>` or another git parent, in the same spelling. The settings keys are `autonomy`, `adoption`, `allow_project_commands`, `enforcement`, `record`, `project`, `prices`, `multiagent`, `governance_drift` and `preset_index`. A parent may hold `schema`, `extends`, `owner`, `approvers`, `capabilities`, `preset` and the catalogues, and nothing else. This holds for every parent in a chain.

`preset` is reserved for a description of a published preset. It must be a mapping and may hold anything. Compass reads nothing from it, and the layer digest leaves it out, so a change of description does not look like a change of configuration. `preset_index` is a settings key, so only the project's own file may hold it.

## Chains

A parent can name a git parent, which can name another. A chain holds at most three git parents, to a depth of three: the project's direct parent, its parent and that parent's parent. The shipped default at the root is not counted, because it is the CLI's own version and not a fetched parent.

Each parent in a chain is pinned by sha, fetched, cached and read as data in the same way as a single parent. The chain is `default`, then the git parents from the furthest to the nearest, `project`, then the issue. A later layer overrides an earlier one, so the nearest parent wins over the furthest, and `policy show` names the parent that wrote each field. The classifier judges each git parent against the shipped default like any other layer, so a parent that loosens the default needs a waiver the same way a project does. A waiver in a git parent, at any depth, is checked against that parent's own `owner`, or the names in the `approvers.project-waiver` of the layer above it. The project's owner does not count. A parent with no `owner` cannot carry a waiver (`W-NO-OWNER`).

| Fault | Code | Reported on |
|---|---|---|
| A third parent names a fourth git parent | `L-PARENT-CHAIN` | The third parent. The fourth is not fetched |
| A parent names a commit that is already in the chain, at any depth | `L-PARENT-CYCLE` | The parent that names it. A full sha already in the chain is refused before any fetch |
| An ancestor cannot be fetched, is not cached for a reader that does not fetch, or has a bad spelling | The code of the fault | The parent that names the ancestor (a bad file reports on the ancestor itself) |

The refusal from `compass policy lint`, `compass policy show` and `compass check` names that parent in the same way. A stored generation does not read the cache at all: it uses the record of its parents, so a deleted cache does not stop `compass check` for an issue that has one.

Compass checks a parent after it has loaded the parent's ancestors. A parent that is refused for a settings key, an `unlock:` or an unknown `impl` may still be fetched along with its ancestors, which were pinned and read as data only. Nothing in them runs.

## What an issue records

`compass policy show` shows the parent as the source of every field it wrote, and lists it in `layers` with its version and digest. When an issue's configuration is committed, `versions.yml` lists the shipped default and then each git parent, furthest first, so the order is the order of the merge:

```yaml
parents:
  - { ref: "compass:default@6", version: 6.0.0, digest: sha256:..., source: shipped }
  - ref: "github:acme/compass-banking@1.2.0"
    sha: 3f9c1a2e...
    version: 1.2.0
    digest: sha256:...
    source: git
    classification:
      against: "compass:default@6"
      result: loosening
      points: 4608
      raw_points: 51840
      complete: true
      first_looser: { assessment: { risk: trivial, ... }, summary: "at risk trivial, ...: approaches.stages (define) is ..." }
```

`digest` is the digest of the parent's layer keys. An issue with a stored generation keeps the parent it ran against: moving the pin in `compass.yml` changes nothing for it until a new generation is committed.

### The stored classification

Each git parent entry holds the classification of the chain from the shipped default through that parent, compared with the shipped default alone. A chain of three parents stores three blocks, so the nearest parent's block is the whole chain and the others are the chain up to them. The shipped entry has no block. The keys are in this order:

| Key | Value |
|---|---|
| `against` | The reference of the shipped entry, such as `compass:default@6` |
| `result` | `equivalent`, `tightening`, `loosening` or `incomparable`, as the classifier gives it (ADR-037) |
| `points` | The grouped assessments the classifier compared |
| `raw_points` | The assessments before grouping |
| `complete` | `false` when the classifier stopped before the whole grid (more than eight named labels) |
| `first_looser` | The first assessment at which the chain owes less, as `assessment` and `summary`, or `null` when none does |

The result is the one before any waiver. A parent's own waivers were approved by the parent's maintainers, and that approval means nothing to a project that extends it, so a waiver does not change the stored `result`. A later check can read the block without running the classifier again.

Only a commit that writes a new generation computes the blocks, with one scan of the grid for each git parent. A commit that finds no change, and a read of the live configuration (`policy show`), do not. The function is `classify_chain` in `cli/compass_pkg/chain_class.py`.

The cost, measured on 2026-10-08 on a laptop: about 0.6 seconds for one parent with a one-field change, and about 2.3 seconds for a chain of three. A chain of more than eight named labels cannot be committed (the lint cannot prove the locks), so `complete: false` is a guard in the function and not a stored case.

`parents[].version` is the ref when it reads as a version. `preset.version` is not read yet; a later release adds it.

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

- A host other than GitHub, and private repositories that need a login: git uses the credential settings of the person running Compass, and Compass never prompts.
