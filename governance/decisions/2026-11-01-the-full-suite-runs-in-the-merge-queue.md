# the-full-suite-runs-in-the-merge-queue

## Decided by

jed72

## Date

2026-11-01

## Supersedes

Nothing.

## Decision

The whole test suite of this repository runs once for each pull request, in a GitHub merge queue, on the exact commit that then lands on main:

- `.github/workflows/compass.yml`, `pr-text.yml` and `docs.yml` run on the `merge_group` event, and every required check reports there. In a merge group, `self-check` passes only when every suite job succeeded and the shard counts add up.
- A push to a pull request runs fast jobs only: `checks`, `count`, `fast-tests`, `build` and `pr-text`. `fast-tests` runs the test files the pull request changes and a fixed set of house-rule test files. There, `self-check` passes when the fast jobs succeeded.
- A draft pull request runs no test.
- A push to main skips every job when a merge-group run tested the same commit green with the whole suite. A green pull-request run no longer lets a push skip.
- `compass.yml` at the project root sets `living_spec: refresh`, so a landing does not commit `docs/system-spec.md` on a branch. A maintainer re-derives it in one pull request with `compass spec sync`.

## Why

On 1 November 2026, CI used 3,742 job minutes for 9 pull requests. One full run of `Compass (self-check)` costs about 100 job minutes, 81% of it in the four shard jobs, and the 9 pull requests got 28 full runs. Most extra runs came from the living spec: each pull request committed its own re-derived `docs/system-spec.md`, so every merge made each other open pull request conflict on it, and bringing the branch up to date ran the whole suite again. CI cannot re-derive the spec, because it is built from the issue archive in `docs/compass/`, which is not tracked.

## Evidence

ayeo-io/compass-delivery#362 [Run the full test suite once per pull request in a merge queue], which holds the job-minute figures and the owner's choice of the merge queue, fast checks on a push, no living spec in a pull request and no tests on a draft. The target is about 115 job minutes for each pull request, against about 300 before.
