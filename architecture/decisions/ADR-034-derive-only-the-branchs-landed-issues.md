---
id: ADR-034
title: Derive the living spec from the landed issues on the branch
status: proposed
date: 2026-10-06
supersedes: ''
superseded_by: ''
---

## Context

ADR-008 made the living spec a derived file, rebuilt from the scenarios of every landed issue, and ADR-026 has `ship-commit` derive it at each landing and commit it on the issue's branch.

Issue records (`.compass/work/<slug>/`) are local and never committed. A checkout's records therefore include issues landed on other branches whose pull requests are still open, and the derive took all of them: a branch's committed spec could name an issue that had not landed on it. On 6 October 2026 one derive did exactly that.

And because each branch commits its own derived copy, two open pull requests that each land an issue conflict on `docs/system-spec.md` and `docs/system-spec-archive.md`, though neither changed a line a person wrote. On 6 October #439, #445, #448 and #451 each conflicted only there, and each was resolved by hand: merge main, take main's spec, copy in the right records, re-derive, commit.

## Decision

The derive leaves out a landed issue only when both hold:

- it has a `land_commit` that is not reachable from HEAD, and
- the spec committed at HEAD does not name it as a source issue (labelled `Source issue`, or the retired label in a spec written before 2.0.0).

Every other landed issue is included, as before: one with no `land_commit` (written before `ship-commit` recorded one, or by hand) cannot be judged and is kept.

Every landing re-derives the spec, so main's committed spec names what landed on main, including squash-merged issues whose branch commit is not on main. A branch made from main thus derives main's issues plus the one it is landing. Outside git, or before a first commit, every landed issue is included, as before.

`compass issue refresh-spec [--base <ref>]` merges the base, takes the base's side where only the two derived files conflict, re-derives under this rule and commits. Any other conflict aborts the merge and names the files.

This narrows ADR-008's rule that the spec is reconstructible from landed issues alone: it is reconstructible from the landed issues on the branch, which the committed spec and commit reachability identify. The content of every scenario still comes only from the issue records; the committed spec is read only to decide which records belong. ADR-008's other rules and ADR-026 stand.

## Alternatives considered

- **Derive on main after merge, in CI.** Rejected: CI has no issue records to derive from, because they are not committed.
- **A git merge driver for the two files.** Rejected: GitHub's own merge does not run custom merge drivers, so the conflict would remain on the pull request.
- **Filter by `land_commit` reachability alone.** Rejected: a squash merge leaves the branch's land commit off main, so main would drop every squash-merged issue.

## Consequences

- A derive never adds an issue that has not landed on the branch. A name already in HEAD's spec keeps itself, so a spec contaminated before this change stays so until that name is removed by hand.
- A conflict that touches only the derived spec takes one command to clear.
- A pull request still conflicts when another lands first; GitHub cannot resolve it without a person running `compass issue refresh-spec`.
- The committed spec is now an input to the derive. ADR-008 said the spec is always reconstructible cold from `.compass/work/`; that now holds only together with the committed spec, because a squash-merged issue that main's spec no longer names cannot be restored from records alone.
- After landing, bring a branch up to date with `compass issue refresh-spec`, not a rebase: a rebase rewrites `land_commit`, and taking main's spec during it drops the branch's own issue until `ship-commit` is run again with nothing staged.
- The derive runs one `git` call per landed issue not named in HEAD's spec, usually only the one being landed.

## References

- ADR-008: cross-issue derived artifacts; this record narrows its second rule.
- ADR-026: `ship-commit` lands every issue and derives the living spec.
- `cli/compass_pkg/flow.py` (`_landed_on_this_branch`) and `cli/compass_pkg/spec_refresh.py`.
