# allow-project-commands-moves-to-compass-yml

## Decided by

jed72

## Date

2026-10-06

## Supersedes

Nothing.

## Decision

`allow_project_commands` moves into `compass.yml`, the file that also declares the commands it authorises. It stays a project-file-only key, and the trust decision still runs first.

## Why

The old separation was never a security control: one pull request could change both files. `docs/security.md` states this.

## Evidence

The maintainer's approval on 6 October 2026 of the recommendation for question Q-24 of the configurable-framework technical specification.
